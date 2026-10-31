"""Release-agnostic instrument pieces (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §2).

Capture is controlled from outside the serving process with `nsys start/stop --session`, and cheap metrics come
from the engine's own Prometheus collectors. Nothing here imports vLLM, so the same code serves every release.
Unavailable measures are None, never zero.
"""
from __future__ import annotations

import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from revision.tracing.rule_diagnosis import kernel_identity
except ImportError:  # copied flat next to rule_diagnosis.py on the GPU host (cases/checks/ext)
    from rule_diagnosis import kernel_identity

# Measure -> metric name per engine family; checked in source at each case's release tag (doc §2.2).
METRIC_NAMES = {
    'v0_early': {  # v0.3.x
        'running': 'vllm:num_requests_running', 'waiting': 'vllm:num_requests_waiting',
        'kv_usage': 'vllm:gpu_cache_usage_perc', 'preemptions': None,
        'prompt_tokens': 'vllm:prompt_tokens_total', 'generation_tokens': 'vllm:generation_tokens_total'},
    'v0': {  # v0.5.x, v0.6.x
        'running': 'vllm:num_requests_running', 'waiting': 'vllm:num_requests_waiting',
        'kv_usage': 'vllm:gpu_cache_usage_perc', 'preemptions': 'vllm:num_preemptions_total',
        'prompt_tokens': 'vllm:prompt_tokens_total', 'generation_tokens': 'vllm:generation_tokens_total'},
    'v1': {  # v0.9.x, v0.11.x; counters gain a _total suffix in the exposition format
        'running': 'vllm:num_requests_running', 'waiting': 'vllm:num_requests_waiting',
        'kv_usage': 'vllm:kv_cache_usage_perc', 'preemptions': 'vllm:num_preemptions_total',
        'prompt_tokens': 'vllm:prompt_tokens_total', 'generation_tokens': 'vllm:generation_tokens_total'},
}


def engine_family(vllm_version: str) -> str:
    major, minor = (int(x) for x in vllm_version.split('.')[:2])
    if (major, minor) < (0, 5):
        return 'v0_early'
    return 'v0' if (major, minor) < (0, 8) else 'v1'


def parse_prometheus(text: str) -> dict:
    """Sum samples per metric name across label sets (one model per server). Comments and _created are skipped."""
    values = {}
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        name_part, _, rest = line.partition(' ')
        name = name_part.split('{', 1)[0]
        if name.endswith('_created'):
            continue
        try:
            value = float(rest.split()[0])
        except (IndexError, ValueError):
            continue
        values[name] = values.get(name, 0.0) + value
    return values


def cheap_measures(text: str, family: str) -> dict:
    parsed = parse_prometheus(text)
    return {measure: (None if name is None else parsed.get(name)) for measure, name in METRIC_NAMES[family].items()}


@dataclass
class BurstRecord:
    """Wall-clock stamps (time.time_ns) for one externally controlled capture; each step kept separate."""
    ordinal: int
    output: str
    start_issued_ns: int | None = None
    start_returned_ns: int | None = None
    stop_issued_ns: int | None = None
    stop_returned_ns: int | None = None
    report_present_ns: int | None = None
    export_done_ns: int | None = None
    database: str | None = None
    failure: str | None = None
    commands: list = field(default_factory=list)


class ExternalBursts:
    """Drive `nsys start/stop` for an existing `nsys launch --session=<session>` process.

    `run` executes a command and returns (returncode, output); it is injectable so tests need no Nsight.
    """
    def __init__(self, session: str, out_dir, *, run=None, clock=time.time_ns, sleep=time.sleep, nsys='nsys'):
        self.session, self.out_dir, self.nsys = session, Path(out_dir), nsys
        self.run, self.clock, self.sleep = run or _run, clock, sleep
        self.records: list[BurstRecord] = []

    def capture(self, seconds: float, *, on_started=None, before_stop=None) -> BurstRecord:
        """on_started / before_stop: optional callbacks run right after `start` returns and right before `stop` is
        issued, bracketing the capture window (used to read token counters over exactly that span)."""
        ordinal = len(self.records) + 1
        out = self.out_dir / f'burst_{ordinal:03d}'
        rec = BurstRecord(ordinal, str(out))
        self.records.append(rec)
        # CPU sampling and context switches are start/profile options in current Nsight, not launch options.
        steps = (('start', [self.nsys, 'start', f'--session={self.session}', f'--output={out}', '--force-overwrite=true',
                            '--sample=none', '--cpuctxsw=none'],
                  'start_issued_ns', 'start_returned_ns'),
                 ('stop', [self.nsys, 'stop', f'--session={self.session}'], 'stop_issued_ns', 'stop_returned_ns'))
        for name, cmd, issued, returned in steps:
            if name == 'stop':
                self.sleep(seconds)
                if before_stop:
                    before_stop()
            setattr(rec, issued, self.clock())
            code, output = self.run(cmd)
            setattr(rec, returned, self.clock())
            rec.commands.append(dict(step=name, cmd=cmd, returncode=code, output=output[-2000:]))
            if code != 0:
                rec.failure = f'{name}_failed'
                return rec
            if name == 'start' and on_started:
                on_started()
        report = Path(str(out) + '.nsys-rep')
        if not report.is_file():
            rec.failure = 'report_missing'
            return rec
        rec.report_present_ns = self.clock()
        database = Path(str(out) + '.sqlite')
        code, output = self.run([self.nsys, 'export', '--type=sqlite', f'--output={database}', '--force-overwrite=true', str(report)])
        rec.commands.append(dict(step='export', returncode=code, output=output[-2000:]))
        if code != 0 or not database.is_file():
            rec.failure = 'export_failed'
            return rec
        rec.export_done_ns, rec.database = self.clock(), str(database)
        return rec


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def gpu_activity(database_path, *, device_id: int | None = None) -> dict:
    """Kernel and memcpy intervals plus per-kernel totals from an exported Nsight SQLite file.

    Returns the activity window (first start to last end, in the trace clock), the intervals for busy_fraction,
    and (name, total_ns) kernel totals for kernel_shares. Raises if the capture has no kernels.
    """
    con = sqlite3.connect(f'file:{Path(database_path).resolve()}?mode=ro', uri=True)
    try:
        where, args = ('WHERE k.deviceId=?', (device_id,)) if device_id is not None else ('', ())
        has_short = 'shortName' in {r[1] for r in con.execute('PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)')}
        short_sel, short_join = (',ss.value', 'LEFT JOIN StringIds ss ON ss.id=k.shortName ') if has_short else (',NULL', '')
        rows = con.execute(f'SELECT k.start,k.end,s.value,p.pid{short_sel} FROM CUPTI_ACTIVITY_KIND_KERNEL k '
                           f'JOIN StringIds s ON s.id=k.demangledName {short_join}'
                           f'LEFT JOIN PROCESSES p ON p.globalPid=k.globalPid {where}', args).fetchall()
        kernels = [(s, e, kernel_identity(name, short), pid) for s, e, name, pid, short in rows]
        if not kernels:
            raise ValueError('No CUDA kernels in capture')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        plain = where.replace('k.', '')
        memcpy = (con.execute(f'SELECT start,end FROM CUPTI_ACTIVITY_KIND_MEMCPY {plain}', args).fetchall()
                  if 'CUPTI_ACTIVITY_KIND_MEMCPY' in tables else [])
        memset = (con.execute(f'SELECT start,end FROM CUPTI_ACTIVITY_KIND_MEMSET {plain}', args).fetchall()
                  if 'CUPTI_ACTIVITY_KIND_MEMSET' in tables else [])
        # Graph-level trace (nsys default): one interval per CUDA graph replay, kernels inside it not listed.
        graphs = (con.execute(f'SELECT start,end FROM CUPTI_ACTIVITY_KIND_GRAPH_TRACE {plain}', args).fetchall()
                  if 'CUPTI_ACTIVITY_KIND_GRAPH_TRACE' in tables else [])
        node_kernels = (con.execute('SELECT COUNT(*) FROM CUPTI_ACTIVITY_KIND_KERNEL WHERE graphNodeId IS NOT NULL').fetchone()[0]
                        if 'graphNodeId' in {r[1] for r in con.execute('PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)')} else 0)
        session = (con.execute('SELECT startTime,stopTime FROM ANALYSIS_DETAILS').fetchone()
                   if 'ANALYSIS_DETAILS' in tables else None)
        if session and kernels and max(k[1] for k in kernels) < session[0]:
            # Nsight 2026.3 stores activity relative to the session start while ANALYSIS_DETAILS is absolute
            # (seen in commissioning): the capture window in activity time is then [0, duration].
            session = (0, session[1] - session[0])
    finally:
        con.close()
    intervals = [(s, e) for s, e, _, _ in kernels] + list(memcpy) + list(memset) + list(graphs)
    # The capture's own start/stop is the denominator for busy_fraction; leading/trailing idle time is the
    # host-bound signal, so the activity envelope is only a flagged fallback.
    if session and session[1] > session[0]:
        window, window_source = (session[0], session[1]), 'analysis_details'
    else:
        window, window_source = (min(s for s, _ in intervals), max(e for _, e in intervals)), 'activity_envelope'
    # Records crossing a window edge were in flight at start/stop; their recorded times are not reliable
    # (commissioning saw graph-node kernels "starting" seconds before capture). Shares use only records inside
    # the window; busy_fraction clips intervals to it.
    inside = [k for k in kernels if k[0] >= window[0] and k[1] <= window[1]]
    totals = {}
    for start, end, name, _ in inside:
        totals[name] = totals.get(name, 0) + (end - start)
    return dict(intervals=intervals, window=window, window_source=window_source,
                kernel_totals=sorted(totals.items(), key=lambda kv: -kv[1]),
                kernels_crossing_window=len(kernels) - len(inside),
                pids=sorted({p for *_, p in kernels if p is not None}), kernel_count=len(kernels),
                memcpy_count=len(memcpy), memset_count=len(memset), graph_count=len(graphs),
                graph_node_kernel_count=node_kernels,
                # Graph replays traced only as whole graphs: busy time is complete, kernel shares are not.
                graph_kernels_opaque=bool(graphs) and node_kernels == 0)
