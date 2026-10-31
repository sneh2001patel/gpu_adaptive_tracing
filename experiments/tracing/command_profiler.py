"""CPU contract harness for owned profiler commands, not a validated Nsight driver.

No shell, arbitrary PID attachment, or claimed GPU capture intervals. Commands
implement the versioned file protocol exercised by fake_profiler_command.py.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import signal
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from experiments.tracing.profiler import CaptureFailed, EvidenceNotReady, ReadyEvidence
from experiments.tracing.timing import seconds_to_ns

PROTOCOL = 'capture_command_v1'


@dataclass(frozen=True)
class CommandPlan:
    collect: tuple[str, ...]
    stop: tuple[str, ...]
    export: tuple[str, ...]
    parse: tuple[str, ...]
    driver_id: str
    driver_version: str
    device_uuid: str
    worker_pids: tuple[int, ...]
    startup_s: float = 5
    stop_s: float = 5
    finalization_s: float = 5
    export_s: float = 5
    parse_s: float = 5
    poll_s: float = .01
    cleanup_grace_s: float = .1
    max_artifact_bytes: int = 16 * 1024 * 1024

    def __post_init__(self):
        for command in (self.collect, self.stop, self.export, self.parse):
            if not isinstance(command, tuple) or not command or any(not isinstance(v, str) or not v or '\x00' in v for v in command):
                raise ValueError('Commands must be nonempty argv tuples without NULs')
        if not self.driver_id or not self.driver_version or not self.device_uuid.startswith('GPU-'):
            raise ValueError('Explicit driver/version/device required')
        if not self.worker_pids or len(set(self.worker_pids)) != len(self.worker_pids) or any(
                not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 for pid in self.worker_pids):
            raise ValueError('Expected positive unique worker PIDs required')
        for value in (self.startup_s, self.stop_s, self.finalization_s, self.export_s,
                      self.parse_s, self.poll_s, self.cleanup_grace_s):
            if seconds_to_ns(value) <= 0:
                raise ValueError('Command deadlines must be positive')
        if isinstance(self.max_artifact_bytes, bool) or not isinstance(self.max_artifact_bytes, int) or self.max_artifact_bytes <= 0:
            raise ValueError('Positive artifact size limit required')


@dataclass
class _Attempt:
    identity: str
    directory: Path
    token: str
    plan: CommandPlan
    state: str = 'starting'
    deadline: int | None = None
    processes: dict = field(default_factory=dict)
    phases: set = field(default_factory=set)
    hashes: dict = field(default_factory=dict)
    ready: ReadyEvidence | None = None
    failure: str | None = None
    stopped: bool = False
    report_ready: bool = False
    cleanup_started: float | None = None
    kill_sent: bool = False
    cleanup_complete: bool = False


class CommandProfilerBackend:
    def __init__(self, recorder, output_root: Path):
        if os.name != 'posix':
            raise ValueError('Owned process-group harness currently requires POSIX')
        if recorder.provenance != 'synthetic_simulation':
            raise ValueError('Command harness is CPU-contract-only; live driver is not validated')
        self.recorder = recorder
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.attempts = {}
        self.events = []
        self._cleanup_task = None

    def _event(self, attempt, name, **details):
        event = self.recorder.mark(name, attempt.identity)
        self.events.append(dict(event=name, capture_id=attempt.identity, timestamp_ns=event.timestamp_ns,
                                clock_domain=event.clock_domain, **details))

    def _begin(self, a, phase):
        self.recorder.begin(phase, a.identity)
        a.phases.add(phase)

    def _end(self, a, phase, status='ok'):
        if phase in a.phases:
            self.recorder.end(phase, a.identity, status=status)
            a.phases.remove(phase)

    def _spawn(self, a, stage):
        values = dict(directory=str(a.directory), capture_id=a.identity, token=a.token,
                      device_uuid=a.plan.device_uuid, worker_pids=','.join(map(str, a.plan.worker_pids)))
        # Only whole-argument placeholders are expanded; JSON braces and shell
        # syntax in literal argv remain literal. No command string evaluation.
        argv = [values.get(arg[1:-1], arg) if arg.startswith('{') and arg.endswith('}') else arg
                for arg in getattr(a.plan, stage)]
        with (a.directory / f'{stage}.stdout').open('wb') as stdout, (a.directory / f'{stage}.stderr').open('wb') as stderr:
            process = subprocess.Popen(argv, cwd=a.directory, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, start_new_session=True)
        a.processes[stage] = process
        self._event(a, 'command_started', stage=stage, argv=argv, pid=process.pid)

    def start(self, capture_id, plan: CommandPlan):
        if not capture_id or capture_id in self.attempts:
            raise ValueError('Capture ID must be unique and nonempty')
        if any(not a.cleanup_complete for a in self.attempts.values()):
            raise RuntimeError('Service owned-process cleanup before starting another attempt')
        token = uuid.uuid4().hex
        directory = self.output_root / token
        directory.mkdir()  # Never reuse reports/acknowledgements from an old attempt.
        a = _Attempt(capture_id, directory, token, plan)
        self.attempts[capture_id] = a
        (directory / 'plan.json').write_text(json.dumps(dict(protocol=PROTOCOL, capture_id=capture_id,
            token=token, validation='cpu_contract_only', plan=asdict(plan)), indent=2) + '\n')
        self._begin(a, 'evidence_collection')
        self._begin(a, 'profile_process_wall')
        self._begin(a, 'capture_startup')
        self._event(a, 'capture_attempted')
        a.deadline = self.recorder.clock.now_ns() + seconds_to_ns(plan.startup_s)
        try:
            self._spawn(a, 'collect')
        except Exception as exc:
            self._fail(a, f'collect_launch:{type(exc).__name__}')

    def _bytes(self, a, name):
        path = a.directory / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= a.plan.max_artifact_bytes:
            raise ValueError(f'Invalid/missing/oversized artifact: {name}')
        data = path.read_bytes()
        if len(data) > a.plan.max_artifact_bytes or data.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ValueError(f'Invalid/LFS artifact: {name}')
        return data

    def _json(self, a, name):
        data = self._bytes(a, name)
        record = json.loads(data)
        if not isinstance(record, dict) or any(record.get(key) != value for key, value in
                dict(protocol=PROTOCOL, capture_id=a.identity, token=a.token, source='fake_executable').items()):
            raise ValueError(f'Artifact identity/protocol/source mismatch: {name}')
        return record

    def _ack(self, a, name, kind):
        if not (a.directory / name).exists():
            return False
        record = self._json(a, name)
        if record.get('kind') != kind or record.get('ack_basis') != 'synthetic_fixture':
            raise ValueError('Capture acknowledgement contract failed')
        self._event(a, kind + '_ack_received', ack_basis=record['ack_basis'])
        return True

    def _result(self, a, stage):
        process = a.processes.get(stage)
        if process is None:
            return None
        code = process.poll()
        if code is not None and not getattr(process, '_recorded_exit', False):
            self._event(a, 'command_exited', stage=stage, returncode=code)
            process._recorded_exit = True
        if code is not None and code != 0:
            raise ValueError(f'{stage}_exit:{code}')
        return code

    def stop(self, capture_id):
        a = self.attempts[capture_id]
        if a.state != 'capturing':
            raise ValueError('Stop requires capture-start acknowledgement')
        a.state = 'finalizing'
        a.deadline = self.recorder.clock.now_ns() + seconds_to_ns(a.plan.stop_s)
        self._begin(a, 'stop_command')
        self._event(a, 'capture_stop_requested')
        try:
            self._spawn(a, 'stop')
        except Exception as exc:
            self._fail(a, f'stop_launch:{type(exc).__name__}')

    def _summary(self, a):
        record = self._json(a, 'summary.json')
        required = {'protocol', 'capture_id', 'token', 'source', 'schema', 'device_uuid', 'worker_pids', 'coverage', 'units', 'kernels', 'export_sha256'}
        if set(record) != required or record['schema'] != 'kernel_summary_v1':
            raise ValueError('Unsupported summary schema/fields')
        if (record['device_uuid'] != a.plan.device_uuid or record['worker_pids'] != list(a.plan.worker_pids)
                or not isinstance(record['worker_pids'], list)
                or any(isinstance(pid, bool) or not isinstance(pid, int) for pid in record['worker_pids'])
                or record['coverage'] != 'fixture_verified' or record['units'] != {'kernel_duration': 'ns'}):
            raise ValueError('Device/worker coverage or units mismatch')
        exported = self._json(a, 'export.json')
        if (exported.get('report_sha256') != hashlib.sha256(self._bytes(a, 'report.bin')).hexdigest()
                or record['export_sha256'] != hashlib.sha256(self._bytes(a, 'export.json')).hexdigest()):
            raise ValueError('Summary/export/report integrity mismatch')
        kernels = record['kernels']
        if not isinstance(kernels, list) or not kernels:
            raise ValueError('Empty/unresolved kernel evidence')
        for kernel in kernels:
            if not isinstance(kernel, dict) or set(kernel) != {'name', 'count', 'total_ns'} or not isinstance(kernel['name'], str) or not kernel['name']:
                raise ValueError('Invalid kernel schema')
            if any(isinstance(kernel[k], bool) or not isinstance(kernel[k], int) or kernel[k] <= 0 for k in ('count', 'total_ns')):
                raise ValueError('Invalid kernel count/duration')
        for name in ('report.bin', 'export.json', 'summary.json'):
            a.hashes[name] = hashlib.sha256(self._bytes(a, name)).hexdigest()
        return dict(kernels=copy.deepcopy(kernels), top_kernel_name=max(kernels, key=lambda k:k['total_ns'])['name'],
                    device_uuid=record['device_uuid'], worker_pids=record['worker_pids'],
                    coverage=record['coverage'], source='fake_executable', artifact_hashes=dict(a.hashes))

    def poll(self, capture_id):
        self.service_cleanup()
        a = self.attempts[capture_id]
        if a.state in {'ready', 'failed'}:
            return a.state
        now = self.recorder.clock.now_ns()
        try:
            if a.deadline is not None and now >= a.deadline:
                raise ValueError(f'{a.state}_timeout')
            if a.state == 'starting':
                if self._result(a, 'collect') is not None:
                    raise ValueError('Collector exited before capture/stop lifecycle')
                if self._ack(a, 'start_ack.json', 'capture_started'):
                    self._end(a, 'capture_startup')
                    self._begin(a, 'capture_control_window')
                    a.state, a.deadline = 'capturing', None
            elif a.state == 'capturing':
                if self._result(a, 'collect') is not None:
                    raise ValueError('Collector exited before stop request')
            elif a.state == 'finalizing':
                stop_result = self._result(a, 'stop')
                collect_result = self._result(a, 'collect')
                if not a.stopped and self._ack(a, 'stop_ack.json', 'capture_stopped'):
                    a.stopped = True
                    self._end(a, 'capture_control_window')
                    self._begin(a, 'report_finalization')
                    a.deadline = now + seconds_to_ns(a.plan.finalization_s)
                if stop_result is not None:
                    self._end(a, 'stop_command')
                if collect_result is not None:
                    self._end(a, 'profile_process_wall')
                    if not a.stopped:
                        raise ValueError('Collector exited without stop acknowledgement')
                    if not a.report_ready:
                        self._bytes(a, 'report.bin')
                        self._end(a, 'report_finalization')
                        self._event(a, 'report_ready')
                        a.report_ready = True
                    if stop_result is None:
                        return a.state
                    a.state, a.deadline = 'exporting', now + seconds_to_ns(a.plan.export_s)
                    self._begin(a, 'stats_command')
                    self._spawn(a, 'export')
            elif a.state == 'exporting' and self._result(a, 'export') is not None:
                self._end(a, 'stats_command')
                exported = self._json(a, 'export.json')
                if exported.get('kind') != 'exported_report' or exported.get('report_sha256') != hashlib.sha256(self._bytes(a, 'report.bin')).hexdigest():
                    raise ValueError('Export/report integrity mismatch')
                a.state, a.deadline = 'parsing', now + seconds_to_ns(a.plan.parse_s)
                self._begin(a, 'summary_parse')
                self._spawn(a, 'parse')
            elif a.state == 'parsing' and self._result(a, 'parse') is not None:
                payload = self._summary(a)
                self._end(a, 'summary_parse')
                ready_event = self.recorder.mark('evidence_ready', a.identity)
                a.ready = ReadyEvidence(a.identity, f'{a.identity}:{a.hashes["summary.json"]}',
                    ready_event.timestamp_ns, ready_event.clock_domain, payload, ready_event.provenance)
                self._end(a, 'evidence_collection')
                a.state, a.deadline = 'ready', None
                self._start_cleanup(a)
        except Exception as exc:
            self._fail(a, str(exc))
        return a.state

    def _signal_groups(self, a, sig):
        for stage, process in a.processes.items():
            process.poll()  # Reap direct children; signal the owned group for descendants too.
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                self._event(a, 'cleanup_permission_error', stage=stage)

    def _groups_alive(self, a):
        alive = []
        for stage, process in a.processes.items():
            process.poll()
            try:
                os.killpg(process.pid, 0)
                alive.append(stage)
            except ProcessLookupError:
                pass
            except PermissionError:
                alive.append(stage)
        return alive

    def _start_cleanup(self, a):
        if a.cleanup_started is None:
            a.cleanup_started = time.monotonic()
            self._begin(a, 'owned_process_cleanup')
            self._signal_groups(a, signal.SIGTERM)
            self._event(a, 'owned_cleanup_requested')
        self.service_cleanup()

    def service_cleanup(self):
        for a in self.attempts.values():
            if a.cleanup_started is None or a.cleanup_complete:
                continue
            alive = self._groups_alive(a)
            if not alive:
                a.cleanup_complete = True
                self._end(a, 'owned_process_cleanup')
                self._event(a, 'owned_cleanup_complete')
            elif not a.kill_sent and time.monotonic() - a.cleanup_started >= a.plan.cleanup_grace_s:
                a.kill_sent = True
                self._signal_groups(a, signal.SIGKILL)
                self._event(a, 'owned_cleanup_escalated', groups=alive)

    def _fail(self, a, reason, status='failed'):
        if a.state in {'ready', 'failed'}:
            return
        for phase in list(a.phases):
            self._end(a, phase, status)
        a.state, a.deadline, a.failure = 'failed', None, reason
        self._event(a, 'capture_failed', reason=reason, status=status)
        self._start_cleanup(a)

    def cancel(self, capture_id, reason):
        self._fail(self.attempts[capture_id], reason, status='cancelled')

    def state(self, capture_id):
        return self.attempts[capture_id].state

    def can_start_capture(self):
        self.service_cleanup()
        return all(a.cleanup_complete for a in self.attempts.values())

    def next_cleanup_deadline_ns(self):
        if self.can_start_capture():
            return None
        return self.recorder.clock.now_ns() + seconds_to_ns(.005)

    def next_deadline_ns(self, capture_id):
        a = self.attempts[capture_id]
        if a.state in {'ready', 'failed'}:
            return None
        poll = self.recorder.clock.now_ns() + seconds_to_ns(a.plan.poll_s)
        return min(poll, a.deadline) if a.deadline is not None else poll

    def evidence(self, capture_id):
        a = self.attempts[capture_id]
        if a.state == 'failed':
            raise CaptureFailed(f'{capture_id}: {a.failure}')
        if a.ready is None:
            raise EvidenceNotReady(f'{capture_id}: {a.state}')
        return copy.deepcopy(a.ready)

    async def aclose(self, timeout_s=2):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._close_impl(timeout_s))
        task = self._cleanup_task
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _close_impl(self, timeout_s):
        seconds_to_ns(timeout_s)
        for a in self.attempts.values():
            if a.state not in {'ready', 'failed'}:
                self.cancel(a.identity, 'backend_closed')
            self._start_cleanup(a)
        deadline = asyncio.get_running_loop().time() + timeout_s
        while any(not a.cleanup_complete for a in self.attempts.values()):
            self.service_cleanup()
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError('Owned process groups remain alive after bounded cleanup')
            await asyncio.sleep(.005)

    def snapshot(self):
        return dict(backend_version='command_backend_v1', validation='cpu_contract_only',
            protocol=PROTOCOL, evidence_mode=self.recorder.provenance, events=copy.deepcopy(self.events),
            attempts={key:dict(state=a.state, failure=a.failure, directory=str(a.directory),
                cleanup_complete=a.cleanup_complete, groups_alive=[] if a.cleanup_complete else self._groups_alive(a),
                artifact_hashes=dict(a.hashes), commands={stage:dict(pid=p.pid, returncode=p.poll())
                    for stage,p in a.processes.items()},
                command_timings={phase:self.recorder.duration(phase, key) for phase in
                    ('capture_startup', 'stop_command', 'owned_process_cleanup')})
                for key,a in self.attempts.items()})
