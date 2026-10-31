"""Hardware-pilot backend for Nsight 2026.3 / vLLM 0.10.2, one GPU/worker.

Own capture RPC/export subprocesses; persistent serving-session ownership stays
with the experiment runner. CUDA control span is not asserted as active capture.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

from experiments.tracing.profiler import CaptureFailed, EvidenceNotReady, ReadyEvidence
from experiments.tracing.timing import seconds_to_ns


def parse_kernel_database(path, *, expected_uuid, expected_pids):
    """Parse only measured kernels and validate explicit GPU/worker coverage."""
    connection = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)
    try:
        gpus = connection.execute('SELECT id,uuid,name FROM TARGET_INFO_GPU').fetchall()
        match = [g[0] for g in gpus if g[1].removeprefix('GPU-').lower() == expected_uuid.removeprefix('GPU-').lower()]
        if len(match) != 1:
            raise ValueError('Captured device UUID does not match configured device')
        workers = connection.execute('SELECT DISTINCT p.pid FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN PROCESSES p ON p.globalPid=k.globalPid').fetchall()
        captured_pids = {int(row[0]) for row in workers}
        if captured_pids != set(expected_pids):
            raise ValueError(f'CUDA worker coverage mismatch: {sorted(captured_pids)} vs {sorted(expected_pids)}')
        device_ids = {row[0] for row in connection.execute('SELECT DISTINCT deviceId FROM CUPTI_ACTIVITY_KIND_KERNEL')}
        if device_ids != set(match):
            raise ValueError('Kernel device identity mismatch')
        rows = connection.execute('SELECT s.value,COUNT(*),SUM(k.end-k.start),MIN(k.start),MAX(k.end) FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN StringIds s ON s.id=k.demangledName GROUP BY k.demangledName ORDER BY SUM(k.end-k.start) DESC').fetchall()
        if not rows or any(row[1] <= 0 or row[2] <= 0 or row[3] < 0 or row[4] <= row[3] for row in rows):
            raise ValueError('Empty or invalid CUDA kernel evidence')
        return dict(kernels=[dict(name=r[0],count=r[1],total_ns=r[2]) for r in rows],
            kernel_count=sum(r[1] for r in rows), kernel_time_sum_s=sum(r[2] for r in rows)/1e9,
            kernel_envelope_s=(max(r[4] for r in rows)-min(r[3] for r in rows))/1e9,
            top_kernel_name=rows[0][0], device_uuid=expected_uuid, captured_worker_pids=sorted(captured_pids),
            coverage='single_configured_worker_and_device_verified', source='nsys_sqlite',
            note='Kernel sum/envelope are not capture-active time; no calibrated root-cause classifier.')
    finally:
        connection.close()


class NsightServingBackend:
    def __init__(self, recorder, session_dir, report_prefix, workers, device_uuid,
                 endpoint, session_process, *, initial_ordinal=0, timeout_s=30):
        if recorder.provenance != 'live_online':
            raise ValueError('Live backend requires live_online provenance')
        if len(workers) != 1:
            raise ValueError('Initial hardware pilot supports exactly one CUDA worker')
        self.recorder, self.session_dir, self.report_prefix = recorder, Path(session_dir), Path(report_prefix)
        self.workers, self.device_uuid, self.endpoint = list(workers), device_uuid, endpoint.rstrip('/')
        self.session_process = session_process
        self.ordinal, self.timeout_s = initial_ordinal, timeout_s
        self.attempts, self.events = {}, []

    def _mark(self, identity, event, **details):
        mark = self.recorder.mark(event, identity)
        self.events.append(dict(event=event, capture_id=identity, timestamp_ns=mark.timestamp_ns,
                                clock_domain=mark.clock_domain, **details))

    def _begin(self, a, phase):
        self.recorder.begin(phase, a['id']);a['phases'].add(phase)

    def _end(self, a, phase, status='ok'):
        if phase in a['phases']:
            self.recorder.end(phase, a['id'], status=status);a['phases'].remove(phase)

    def _spawn(self, a, stage, argv):
        with (a['directory']/f'{stage}.log').open('w') as log:
            p=subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,start_new_session=True)
        a['processes'][stage]=p
        self._mark(a['id'], 'command_started', stage=stage, argv=argv, pid=p.pid)

    def _deadline(self, a):
        a['deadline']=self.recorder.clock.now_ns()+seconds_to_ns(self.timeout_s)

    def start(self, identity, window=None):
        if identity in self.attempts or not self.can_start_capture():
            raise ValueError('Duplicate capture or prior capture/cleanup pending')
        if self.session_process.poll() is not None:
            raise RuntimeError('Persistent Nsight/serving session is not alive')
        self.ordinal+=1; token=uuid.uuid4().hex
        directory=self.session_dir/'attempts'/token;directory.mkdir(parents=True)
        a=dict(id=identity,token=token,ordinal=self.ordinal,directory=directory,state='starting',
               phases=set(),processes={},ready=None,error=None,cleanup_complete=False)
        self.attempts[identity]=a
        control=dict(capture_id=identity,token=token,ordinal=self.ordinal)
        temporary=self.session_dir/'control.pending';temporary.write_text(json.dumps(control));temporary.replace(self.session_dir/'control.json')
        self._begin(a,'evidence_collection');self._begin(a,'capture_startup');self._deadline(a)
        try:
            self._spawn(a,'start',[sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/profile_http_command.py'),self.endpoint+'/start_profile'])
        except Exception as exc:
            self._fail(a,str(exc))

    def _exited(self,a,stage):
        p=a['processes'][stage];code=p.poll()
        if code is not None and not getattr(p,'_logged_exit',False):
            self._mark(a['id'],'command_exited',stage=stage,returncode=code);p._logged_exit=True
        if code is not None and code!=0:raise RuntimeError(f'{stage} returned {code}')
        return code is not None

    def _worker_ack(self,a,action):
        records=[]
        for pid in self.workers:
            path=self.session_dir/f'{a["token"]}-{pid}-{action}.json'
            if not path.exists():return None
            record=json.loads(path.read_text())
            expected=dict(capture_id=a['id'],token=a['token'],ordinal=a['ordinal'],action=action,
                          source='cuda_worker_api',pid=pid,device_uuid=self.device_uuid,
                          clock_domain=self.recorder.clock.domain,cuda_return_code=0)
            if any(record.get(k)!=v for k,v in expected.items()):raise ValueError('Foreign worker acknowledgement')
            now=self.recorder.clock.now_ns()
            if not 0<=record['requested_at_ns']<=record['returned_at_ns']<=now:raise ValueError('Worker clock/availability mismatch')
            records.append(record)
        return records

    def stop(self,identity):
        a=self.attempts[identity]
        if a['state']!='capturing':raise ValueError('No acknowledged capture to stop')
        a['state']='finalizing';self._begin(a,'capture_stop_rpc');self._deadline(a)
        try:
            self._spawn(a,'stop',[sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/profile_http_command.py'),self.endpoint+'/stop_profile'])
        except Exception as exc:self._fail(a,str(exc))

    def poll(self,identity):
        self.service_cleanup();a=self.attempts[identity]
        if a['state'] in ('failed','ready'):return a['state']
        try:
            if self.session_process.poll() is not None:raise RuntimeError('Serving/profiler process exited')
            if self.recorder.clock.now_ns()>=a['deadline']:raise RuntimeError(a['state']+'_timeout')
            if a['state']=='starting' and self._exited(a,'start'):
                ack=self._worker_ack(a,'start')
                callbacks=[json.loads(p.read_text()) for p in self.session_dir.glob('callback-start-*.json')]
                callback=next((c for c in callbacks if c.get('token')==a['token'] and c.get('capture_id')==a['id']),None)
                if ack is not None and callback is not None:
                    if (callback.get('source')!='nsys_callback'
                            or callback.get('clock_domain')!=self.recorder.clock.domain
                            or not 0<=callback.get('timestamp_ns',-1)<=self.recorder.clock.now_ns()):
                        raise ValueError('Foreign/future Nsight start callback')
                    a['start_ack']=ack;a['start_callback']=callback
                    self._end(a,'capture_startup');self._begin(a,'capture_control_window');a['state']='capturing';self._deadline(a)
                    self._mark(identity,'capture_started_ack_received',worker_ack=ack,nsys_callback=callback)
            elif a['state']=='finalizing' and self._exited(a,'stop'):
                ack=self._worker_ack(a,'stop')
                if ack is not None:
                    a['stop_ack']=ack;self._end(a,'capture_stop_rpc');self._end(a,'capture_control_window')
                    self._begin(a,'report_readiness_wait');a['state']='waiting_report';self._deadline(a)
                    self._mark(identity,'capture_stopped_ack_received',worker_ack=ack)
            elif a['state']=='waiting_report':
                expected=Path(str(self.report_prefix)+f'.{a["ordinal"]}.nsys-rep')
                callbacks=[json.loads(p.read_text()) for p in self.session_dir.glob('callback-report_ready-*.json')]
                ready=next((c for c in callbacks if c.get('report_path') and Path(c['report_path']).resolve()==expected.resolve()),None)
                if expected.is_file():
                    if ready is not None and (ready.get('source')!='nsys_callback'
                            or ready.get('clock_domain')!=self.recorder.clock.domain
                            or not 0<=ready.get('timestamp_ns',-1)<=self.recorder.clock.now_ns()):
                        raise ValueError('Foreign/future report callback')
                    if not expected.is_file() or expected.stat().st_size<100:raise ValueError('Missing real Nsight report')
                    a['report']=expected;a['report_callback']=ready
                    self._mark(identity,'report_detected',callback=ready,
                        readiness_basis='sync_cudaProfilerStop_return_pending_export_validation')
                    a['database']=a['directory']/'capture.sqlite'
                    self._begin(a,'stats_command');a['state']='exporting';self._deadline(a)
                    self._spawn(a,'export',['nsys','export','--type=sqlite','--output='+str(a['database']),str(expected)])
            elif a['state']=='exporting' and self._exited(a,'export'):
                self._end(a,'stats_command');self._end(a,'report_readiness_wait')
                self._mark(identity,'report_ready',readiness_basis='sync_cudaProfilerStop_ack_and_successful_export')
                self._begin(a,'summary_parse');a['state']='parsing';self._deadline(a)
            elif a['state']=='parsing':
                payload=parse_kernel_database(a['database'],expected_uuid=self.device_uuid,expected_pids=self.workers)
                hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a['report'],a['database'])}
                payload['artifact_hashes']=hashes
                (a['directory']/'kernel_summary.json').write_text(json.dumps(payload,indent=2)+'\n')
                self._end(a,'summary_parse');self._end(a,'evidence_collection')
                event=self.recorder.mark('evidence_ready',identity)
                a['ready']=ReadyEvidence(identity,identity+':'+hashes[str(a['database'])],event.timestamp_ns,event.clock_domain,payload,'live_online')
                a['state']='ready';a['cleanup_complete']=True
        except Exception as exc:self._fail(a,str(exc))
        return a['state']

    def _fail(self,a,error,status='failed'):
        if a['state'] in ('failed','ready'):return
        for phase in list(a['phases']):self._end(a,phase,status=status)
        a['error']=error;a['state']='failed'
        for p in a['processes'].values():
            if p.poll() is None:
                try:os.killpg(p.pid,15)
                except ProcessLookupError:pass
        self._mark(a['id'],'capture_failed',reason=error)
        # A failed start/stop may leave a device capture active. Do not permit
        # another attempt; the runner must shut down its owned session.
        a['poisoned']=True
        self.service_cleanup()

    def service_cleanup(self):
        for a in self.attempts.values():
            if a['state']=='failed':
                for p in a['processes'].values():
                    if p.poll() is None:
                        try:os.killpg(p.pid,9)
                        except ProcessLookupError:pass
                a['cleanup_complete']=all(p.poll() is not None for p in a['processes'].values())

    def can_start_capture(self):
        self.service_cleanup()
        return all(a['state']=='ready' and a['cleanup_complete'] for a in self.attempts.values())

    def next_cleanup_deadline_ns(self):
        # A poisoned session requires external teardown, not more charged retries.
        return None

    def next_deadline_ns(self,identity):
        if self.state(identity) in ('ready','failed'):return None
        return min(self.attempts[identity]['deadline'],self.recorder.clock.now_ns()+seconds_to_ns(.02))

    def state(self,identity):return self.attempts[identity]['state']

    def evidence(self,identity):
        a=self.attempts[identity]
        if a['state']=='failed':raise CaptureFailed(a['error'])
        if a['ready'] is None:raise EvidenceNotReady('Report/export/summary is not ready')
        return copy.deepcopy(a['ready'])

    def cancel(self,identity,reason):self._fail(self.attempts[identity],reason,status='cancelled')

    async def aclose(self):
        import asyncio
        for a in self.attempts.values():
            if a['state'] not in ('failed','ready'):self._fail(a,'backend_closed')
        for _ in range(100):
            self.service_cleanup()
            if all(a['cleanup_complete'] for a in self.attempts.values()):return
            await asyncio.sleep(.01)
        raise RuntimeError('Capture helper process survived cleanup')

    def snapshot(self):
        return dict(backend_version='nsys_serving_pilot_v1',capture_range_end_mode='repeat_sync',nsys_contract='2026.3.1',vllm_contract='0.10.2',
            ordinal=self.ordinal,events=copy.deepcopy(self.events),attempts={key:{k:v for k,v in a.items()
                if k in ('state','error','ordinal','cleanup_complete','poisoned')} for key,a in self.attempts.items()})
