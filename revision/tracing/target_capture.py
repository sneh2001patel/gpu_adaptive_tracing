"""CPU-only capture control in the owned serving fixture, not a GPU profiler."""
import asyncio
import copy
import hashlib
import json

from revision.tracing.arm_session import CpuTargetSession
from revision.tracing.profiler import ReadyEvidence, EvidenceNotReady, CaptureFailed
from revision.tracing.timing import seconds_to_ns


class CpuTargetCaptureBackend:
    def __init__(self,session,recorder):
        if type(session) is not CpuTargetSession or recorder.provenance!='synthetic_simulation':
            raise ValueError('CPU fake target and synthetic recorder required')
        if session.mode=='disabled':raise ValueError('Disabled target cannot own capture backend')
        self.session,self.recorder=session,recorder
        self.attempts={};self.poisoned=False;self.cleanup_done=False

    def start(self,identity,window=None):
        if not identity or identity in self.attempts or not self.can_start_capture():
            raise ValueError('Duplicate/overlapping/poisoned capture')
        self.recorder.begin('evidence_collection',identity);self.recorder.begin('capture_startup',identity)
        self.attempts[identity]=dict(state='starting',ready=None,error=None,task=asyncio.create_task(
            self.session.command('/capture/start',{'capture_id':identity})),phase='capture_startup',hashes={},acquisition=None)

    def state(self,identity):return self.attempts[identity]['state']

    def can_start_capture(self):
        return not self.poisoned and all(a['state'] in ('ready','failed') for a in self.attempts.values())

    def stop(self,identity):
        a=self.attempts[identity]
        if a['state']!='capturing':raise ValueError('No acknowledged capture')
        self.recorder.begin('capture_stop_rpc',identity)
        a.update(state='finalizing',phase='capture_stop_rpc',task=asyncio.create_task(
            self.session.command('/capture/stop',{'capture_id':identity})))

    def poll(self,identity):
        a=self.attempts[identity]
        if a['state'] not in ('starting','finalizing') or not a['task'].done():return a['state']
        try:
            reply=a['task'].result();expected='start' if a['state']=='starting' else 'stop'
            if reply.get('action')!=expected or reply.get('capture_id')!=identity:
                raise ValueError('Foreign capture acknowledgement')
            self.recorder.end(a['phase'],identity);a['phase']=None
            if expected=='start':
                if not reply['capture_active']:raise ValueError('No active capture acknowledgement')
                a['state']='capturing';self.recorder.begin('capture_control_window',identity)
                a['acquisition']=dict(start_ns=self.recorder.clock.now_ns(),end_ns=None)
            else:
                if reply['capture_active'] or reply['report_pending']:raise ValueError('Report not finalized')
                # This control span includes stop RPC/finalization. It is not
                # active GPU time; the report is an explicitly synthetic fixture.
                self.recorder.end('capture_control_window',identity)
                a['acquisition']['end_ns']=self.recorder.clock.now_ns()
                self.recorder.begin('summary_parse',identity);a['phase']='summary_parse'
                payload=reply['report']|{'capture_id':identity}
                if payload.get('source')!='synthetic_fixture' or payload.get('captured_worker_pids')!=[self.session.process.pid]:
                    raise ValueError('Unexpected fixture report identity')
                raw=json.dumps(reply,sort_keys=True,allow_nan=False).encode()
                self.recorder.end('summary_parse',identity);a['phase']='artifact_persist'
                self.recorder.begin('artifact_persist',identity)
                digest=hashlib.sha256(raw).hexdigest();path=self.session.directory/f'report-{digest}.json'
                path.write_bytes(raw);a['hashes']={str(path):digest}
                self.recorder.end('artifact_persist',identity);a['phase']=None
                event=self.recorder.mark('evidence_ready',identity)
                a.update(state='ready',ready=ReadyEvidence(identity,digest,event.timestamp_ns,
                    event.clock_domain,payload,'synthetic_simulation'))
                self.recorder.end('evidence_collection',identity)
        except BaseException as exc:
            self.cancel(identity,type(exc).__name__)
        return a['state']

    def evidence(self,identity):
        a=self.attempts[identity]
        if a['state']=='failed':raise CaptureFailed(a['error'])
        if a['state']!='ready':raise EvidenceNotReady('Fixture report not parsed')
        return copy.deepcopy(a['ready'])

    def next_deadline_ns(self,identity):
        return None if self.state(identity) in ('ready','failed') else self.recorder.clock.now_ns()+seconds_to_ns(.001)

    def cancel(self,identity,reason):
        a=self.attempts[identity]
        if a['state'] in ('ready','failed'):return
        a['task'].cancel();a.update(state='failed',error=reason);self.poisoned=True
        if a['phase'] is not None:
            self.recorder.end(a['phase'],identity,status='cancelled');a['phase']=None
        if self.recorder.duration('capture_control_window',identity) is None:
            # End only if it actually began; startup failure has no such span.
            if any(e.scope==identity and e.name=='capture_control_window_started' for e in self.recorder.events):
                self.recorder.end('capture_control_window',identity,status='cancelled')
        self.recorder.end('evidence_collection',identity,status='cancelled')
        self.recorder.mark('capture_failed',identity,status=reason)

    async def wait_for(self,identity,state,timeout_s=1):
        deadline=asyncio.get_running_loop().time()+timeout_s
        while self.poll(identity)!=state:
            if self.state(identity)=='failed':raise CaptureFailed(self.attempts[identity]['error'])
            if asyncio.get_running_loop().time()>=deadline:raise TimeoutError('Fixture capture wait timeout')
            await asyncio.sleep(.001)
        return self.attempts[identity]

    async def aclose(self):
        if self.cleanup_done:return
        for identity in self.attempts:
            if self.state(identity) not in ('ready','failed'):self.cancel(identity,'arm_capture_cleanup')
        await asyncio.gather(*(a['task'] for a in self.attempts.values()),return_exceptions=True)
        # A cancelled control RPC is not proof tracing stopped in the target.
        # Explicit abort is separate from policy stop/evidence success.
        await self.session.command('/capture/abort',{})
        self.cleanup_done=True

    def snapshot(self):
        return dict(validation='cpu_target_control_only',poisoned=self.poisoned,cleanup_done=self.cleanup_done,
            attempts={i:dict(state=a['state'],error=a['error'],artifact_hashes=a['hashes'],host_acquisition=a['acquisition']) for i,a in self.attempts.items()})
