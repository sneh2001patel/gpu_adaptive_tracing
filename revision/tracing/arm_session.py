"""Owned POSIX CPU-fixture sessions with explicit server quiescence/reset.

This accepts only the bundled CPU fake target; it cannot launch/attach a GPU
server. Process absence, reset acknowledgements and server work are distinct.
"""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid
from urllib.parse import urlsplit

from revision.tracing.feature_collection import http_body
from revision.tracing.measured_evidence import integer
from revision.tracing.timing import seconds_to_ns

PROTOCOL='cpu_arm_target_v1'
ROOT=Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SessionConfig:
    startup_s: float = 3
    quiescence_s: float = 1
    quiet_hold_s: float = .01
    quiet_observations: int = 2
    poll_s: float = .005
    command_timeout_s: float = .5
    cleanup_grace_s: float = .15
    cleanup_timeout_s: float = 2
    work_s: float = .03
    report_s: float = .005

    def __post_init__(self):
        integer(self.quiet_observations,'quiet_observations',2)
        for key in self.__dataclass_fields__:
            if key=='quiet_observations':continue
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or seconds_to_ns(value)<=0:
                raise ValueError('Positive finite session durations required')
        if self.cleanup_timeout_s<=self.cleanup_grace_s:raise ValueError('Cleanup deadline must exceed TERM grace')


class CpuTargetSession:
    def __init__(self,directory,clock,capture_mode,*,config=None,fault='normal',interval_recording=False):
        if os.name!='posix':raise ValueError('CPU owned-group fixture requires POSIX')
        if capture_mode not in ('disabled','bounded','continuous'):raise ValueError('Unknown capture mode')
        self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=False)
        self.clock,self.mode,self.config,self.fault=clock,capture_mode,config or SessionConfig(),fault
        if type(interval_recording) is not bool:raise ValueError("Interval recording flag must be boolean")
        self.interval_recording=interval_recording
        self.nonce=uuid.uuid4().hex;self.process=None;self.endpoint=None;self.instance=None;self.generation=0
        self.events=[];self.quiet_checks=[];self.cleanup=None;self._close_task=None

    def event(self,name,**details):
        self.events.append(dict(event=name,at_ns=self.clock.now_ns(),clock_domain=self.clock.domain,**details))

    async def start(self):
        path=self.directory/'ready.json'
        command=[sys.executable,str(ROOT/'revision/scripts/fake_serving_target.py'),'--ready',str(path),
            '--nonce',self.nonce,'--clock-domain',self.clock.domain,'--capture-mode',self.mode,'--work-s',str(self.config.work_s),
            '--report-s',str(self.config.report_s),'--fault',self.fault]
        if self.interval_recording:command.append('--interval-recording')
        with (self.directory/'target.log').open('wb') as log:
            self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        self.event('target_started',pid=self.process.pid,command=command)
        deadline=asyncio.get_running_loop().time()+self.config.startup_s
        while not path.exists():
            if self.process.poll() is not None:raise RuntimeError('Owned target exited before readiness')
            if asyncio.get_running_loop().time()>=deadline:raise TimeoutError('Target readiness timeout')
            await asyncio.sleep(self.config.poll_s)
        if path.is_symlink() or path.stat().st_size>65536:raise ValueError('Invalid readiness file')
        record=json.loads(path.read_text());self.instance=record.get('instance')
        if not isinstance(self.instance,str) or not self.instance:raise ValueError('Missing target instance')
        self.validate(record)
        endpoint=record.get('endpoint');url=urlsplit(endpoint)
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path or not url.port or url.username or url.password:
            raise ValueError('Owned fixture endpoint must be explicit loopback HTTP')
        self.endpoint=endpoint;await self.status();self.event('target_ready',pid=self.process.pid,instance=self.instance)

    def validate(self,record,*,generation=None):
        if self.process is None:raise ValueError('Target ownership absent')
        expected=dict(protocol=PROTOCOL,source='cpu_fake_target',nonce=self.nonce,instance=self.instance,
            pid=self.process.pid,generation=self.generation if generation is None else generation,capture_mode=self.mode,interval_recording=self.interval_recording)
        if type(record) is not dict or any(record.get(k)!=v for k,v in expected.items()):
            raise ValueError('Stale/foreign target identity, generation or capture mode')
        integer(record.get('pid'),'pid',1);integer(record.get('generation'),'generation')
        for key in ('running','queued','inflight','report_pending','completed','capture_starts','capture_stops'):
            integer(record.get(key),key)
        if type(record.get('capture_active')) is not bool or record['inflight']!=record['running']+record['queued']:
            raise ValueError('Incomplete/inconsistent server activity evidence')
        return record

    async def command(self,path,payload=None,*,timeout_s=None,generation=None):
        if self.process is None or self.process.poll() is not None:raise RuntimeError('Owned target is not alive')
        status,body=await http_body(self.endpoint+path,method='GET' if payload is None else 'POST',
            payload=None if payload is None else payload|{'nonce':self.nonce},
            timeout_s=self.config.command_timeout_s if timeout_s is None else timeout_s,max_bytes=1048576)
        if status!=200:raise RuntimeError(f'Owned target command {path} returned {status}')
        return self.validate(json.loads(body),generation=generation)

    async def status(self,*,timeout_s=None):return await self.command('/status',timeout_s=timeout_s)

    async def wait_quiet(self,phase):
        deadline=asyncio.get_running_loop().time()+self.config.quiescence_s
        quiet_since=None;streak=0;checks=[]
        try:
            while True:
                remaining=deadline-asyncio.get_running_loop().time()
                if remaining<=0:raise TimeoutError('Server quiescence not established: '+phase)
                record=await self.status(timeout_s=min(self.config.command_timeout_s,remaining))
                now=self.clock.now_ns();quiet=not(record['inflight'] or record['running'] or record['queued'] or record['report_pending'] or record['capture_active'])
                checks.append(dict(received_at_ns=now,quiet=quiet,status=record))
                if quiet:
                    if quiet_since is None:quiet_since=now
                    streak+=1
                else:quiet_since=None;streak=0
                if asyncio.get_running_loop().time()>deadline:raise TimeoutError('Late quiescence response')
                if streak>=self.config.quiet_observations and now-quiet_since>=seconds_to_ns(self.config.quiet_hold_s):
                    self.event('quiescence_confirmed',phase=phase,observations=streak)
                    return record
                await asyncio.sleep(min(self.config.poll_s,max(0,deadline-asyncio.get_running_loop().time())))
        finally:self.quiet_checks.append(dict(phase=phase,checks=checks))

    async def reset(self):
        await self.wait_quiet('before_reset')
        token=uuid.uuid4().hex
        record=await self.command('/reset',{'reset_token':token},generation=self.generation+1)
        if record.get('reset_token')!=token or record['capture_active'] or any(
                record[k] for k in ('completed','inflight','running','queued','report_pending','capture_starts','capture_stops')):
            raise ValueError('Reset acknowledgement does not establish a clean generation')
        self.generation+=1;self.event('reset_acknowledged',reset_token=token,generation=self.generation)
        await self.wait_quiet('after_reset')
        return record

    def group_alive(self):
        if self.process is None:return False
        self.process.poll()
        try:os.killpg(self.process.pid,0);return True
        except ProcessLookupError:return False
        except PermissionError:
            self.event('group_visibility_unknown',pid=self.process.pid)
            return True  # Never promote unknown liveness to confirmed absence.

    def signal_owned(self,sig):
        try:os.killpg(self.process.pid,sig);return True
        except ProcessLookupError:return False
        except PermissionError:
            self.event('owned_signal_denied',signal=int(sig));return False

    async def _close(self):
        if self.cleanup is not None:return
        started=self.clock.now_ns();escalated=False
        if self.process is not None:
            if self.group_alive():
                if self.signal_owned(signal.SIGTERM):self.event('owned_term_sent')
            start=asyncio.get_running_loop().time()
            while self.group_alive():
                elapsed=asyncio.get_running_loop().time()-start
                if elapsed>=self.config.cleanup_timeout_s:raise RuntimeError('Owned target group survived cleanup')
                if elapsed>=self.config.cleanup_grace_s and not escalated:
                    if self.signal_owned(signal.SIGKILL):
                        escalated=True;self.event('owned_kill_sent')
                await asyncio.sleep(self.config.poll_s)
            self.process.poll()
        self.cleanup=dict(started_at_ns=started,finished_at_ns=self.clock.now_ns(),escalated=escalated,
            returncode=None if self.process is None else self.process.returncode,group_alive=False)
        self.event('owned_cleanup_complete',**self.cleanup)

    async def aclose(self):
        if self._close_task is None:self._close_task=asyncio.create_task(self._close())
        cancelled=False
        while not self._close_task.done():
            try:await asyncio.shield(self._close_task)
            except asyncio.CancelledError:cancelled=True
        self._close_task.result()
        if cancelled:raise asyncio.CancelledError

    def snapshot(self):
        return dict(validation='cpu_fixture_only',nonce=self.nonce,instance=self.instance,generation=self.generation,
            capture_mode=self.mode,pid=None if self.process is None else self.process.pid,endpoint=self.endpoint,
            events=list(self.events),quiescence_checks=list(self.quiet_checks),cleanup=self.cleanup)
