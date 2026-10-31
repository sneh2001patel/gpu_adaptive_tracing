#!/usr/bin/env python3
"""Owned CPU HTTP target for arm/reset contracts. Never imports GPU libraries."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import time
import uuid

PROTOCOL='cpu_arm_target_v1'


class Target:
    def __init__(self,args):
        self.args=args;self.instance=uuid.uuid4().hex;self.generation=0
        self.running=0;self.queued=0;self.completed=0;self.capture=None;self.report_pending=0
        self.wait_events=[];self.history_overflow=False;self.epoch_ns=time.monotonic_ns()
        self.tasks=set();self.semaphore=asyncio.Semaphore(2);self.capture_events=[]

    def status(self):
        result=dict(protocol=PROTOCOL,source='cpu_fake_target',nonce=self.args.nonce,instance=self.instance,pid=os.getpid(),
            generation=self.generation,capture_mode=self.args.capture_mode,interval_recording=self.args.interval_recording,running=self.running,queued=self.queued,
            inflight=self.running+self.queued,capture_active=self.capture is not None,report_pending=self.report_pending,
            completed=self.completed,capture_starts=sum(e['action']=='start' for e in self.capture_events),
            capture_stops=sum(e['action']=='stop' for e in self.capture_events))
        if self.args.fault=='missing_metric':result.pop('running')
        if self.args.fault=='stuck_busy':result.update(running=1,inflight=1+self.queued)
        return result

    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task)
        status=200;result=None
        try:
            head=await reader.readuntil(b'\r\n\r\n');request=head.split(b'\r\n')[0].decode().split()
            size=next((int(x.split(b':',1)[1]) for x in head.split(b'\r\n') if x.lower().startswith(b'content-length:')),0)
            if not 0<=size<=1048576:raise ValueError('Invalid request size')
            body=await reader.readexactly(size);payload=json.loads(body) if body else {}
            method,path=request[:2]
            if method=='GET' and path=='/clock':
                result=self.status()|dict(clock_name='time.monotonic_ns',clock_domain=self.args.clock_domain,probe_ns=time.monotonic_ns())
            elif method=='POST' and path=='/interval':
                if payload.get('nonce')!=self.args.nonce:status=403;result={'error':'wrong_nonce'}
                elif not self.args.interval_recording:status=409;result={'error':'interval_recording_disabled'}
                else:
                    start,end=payload['start_ns'],payload['end_ns'];now=time.monotonic_ns()
                    if type(start) is not int or type(end) is not int or not self.epoch_ns<=start<end<=now:raise ValueError('Invalid as-of interval')
                    bounds=(0.,.001,.005,.01,.05,.1,1.,float('inf'))
                    def snapshot(boundary):
                        values=[wait for stamp,wait in self.wait_events if stamp<boundary]
                        return dict(sampled_at_ns=boundary,generation=str(self.generation),
                            cumulative_counts=[sum(v<=b for v in values) for b in bounds],count=len(values))
                    first,last=snapshot(start),snapshot(end)
                    if self.args.fault=='interval_reset':
                        first['cumulative_counts']=[n+100 for n in first['cumulative_counts']];first['count']+=100
                    if self.args.fault=='interval_late':await asyncio.sleep(.03)
                    result=self.status()|dict(interval_schema='cpu_admission_history_v1',
                        clock_domain=self.args.clock_domain,clock_name='time.monotonic_ns',
                        collected_at_ns=time.monotonic_ns(),epoch_ns=self.epoch_ns,
                        history_complete=not self.history_overflow,semantics='queue_wait_seconds_observed_at_service_admission',
                        upper_seconds=list(bounds[:-1])+['+Inf'],previous=first,current=last,
                        phase_attribution='not_instrumented')
                    if self.args.fault=='interval_missing':result['previous']=None
                    if self.args.fault=='interval_clock':result['clock_domain']='foreign-clock'
                    if self.args.fault=='interval_generation':result['previous']['generation']='foreign-generation'
                    if self.args.fault=='interval_overflow':result['history_complete']=False
            elif method=='GET' and path=='/status':result=self.status()
            elif method=='GET' and path=='/metrics':
                data=f'# TYPE fixture_queue gauge\nfixture_queue {self.queued}\n'.encode()
                await self.respond(writer,200,data);return
            elif method=='POST' and path=='/v1/completions':
                queued_at=time.monotonic_ns() if self.args.interval_recording else None;self.queued+=1;acquired=False
                try:
                    await self.semaphore.acquire();acquired=True;self.queued-=1;self.running+=1
                    if self.args.interval_recording:
                        admitted_at=time.monotonic_ns()
                        if len(self.wait_events)<10000:self.wait_events.append((admitted_at,(admitted_at-queued_at)/1e9))
                        else:self.history_overflow=True
                    # Deliberately continue server work after client disconnect.
                    await asyncio.sleep(.005 if payload.get('max_tokens')==1 else self.args.work_s)
                    self.completed+=1
                    result=dict(usage=dict(prompt_tokens=7,completion_tokens=min(3,payload.get('max_tokens',3))))
                finally:
                    if acquired:self.running-=1;self.semaphore.release()
                    else:self.queued-=1
            elif method=='POST' and path in ('/reset','/capture/start','/capture/stop','/capture/abort'):
                if payload.get('nonce')!=self.args.nonce:status=403;result={'error':'wrong_nonce'}
                elif path=='/reset':
                    if self.running or self.queued or self.capture is not None or self.report_pending or self.args.fault=='reset_reject':
                        status=409;result={'error':'not_quiescent'}
                    else:
                        self.generation+=1;self.completed=0;self.capture_events=[]
                        self.wait_events=[];self.history_overflow=False;self.epoch_ns=time.monotonic_ns()
                        result=self.status()|dict(reset_token=payload.get('reset_token'))
                        if self.args.fault=='stale_reset':result['generation']-=1
                elif path=='/capture/start':
                    if self.args.capture_mode=='disabled' or self.capture is not None:status=409;result={'error':'capture_disabled_or_active'}
                    else:
                        self.capture=payload['capture_id'];self.capture_events.append(dict(action='start',capture_id=self.capture))
                        result=self.status()|dict(capture_id=self.capture,action='start')
                elif path=='/capture/abort':
                    self.capture=None;result=self.status()|dict(action='abort')
                else:
                    capture_id=payload.get('capture_id')
                    if self.capture!=capture_id:status=409;result={'error':'wrong_capture'}
                    else:
                        self.capture=None;self.report_pending+=1
                        self.capture_events.append(dict(action='stop',capture_id=capture_id))
                        try:await asyncio.sleep(self.args.report_s)
                        finally:self.report_pending-=1
                        result=self.status()|dict(action='stop',capture_id=capture_id,report=dict(
                            source='synthetic_fixture',kernel_count=20,kernel_time_sum_s=.01,
                            device_uuid='GPU-cpu-fixture',captured_worker_pids=[os.getpid()],
                            coverage='single_configured_worker_and_device_verified'))
            else:status=404;result={'error':'unsupported_path'}
            await self.respond(writer,status,json.dumps(result).encode())
        except (ConnectionError,asyncio.IncompleteReadError,BrokenPipeError):pass
        except (ValueError,KeyError,IndexError):
            try:await self.respond(writer,400,b'{"error":"bad_request"}')
            except ConnectionError:pass
        finally:writer.close();self.tasks.discard(task)

    async def respond(self,writer,status,body):
        writer.write(f'HTTP/1.1 {status} fixture\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()+body)
        await writer.drain()

    async def run(self):
        if self.args.fault=='startup_fail':raise RuntimeError('fixture startup failure')
        server=await asyncio.start_server(self.handle,'127.0.0.1',0)
        endpoint=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
        ready=self.status()|dict(endpoint=endpoint)
        if self.args.fault=='wrong_identity':ready['nonce']='foreign'
        path=Path(self.args.ready);temporary=path.with_suffix('.pending')
        temporary.write_text(json.dumps(ready));temporary.replace(path)
        stop=asyncio.Event();loop=asyncio.get_running_loop()
        if self.args.fault=='ignore_term':signal.signal(signal.SIGTERM,signal.SIG_IGN)
        else:loop.add_signal_handler(signal.SIGTERM,stop.set)
        loop.add_signal_handler(signal.SIGINT,stop.set)
        try:await stop.wait()
        finally:
            server.close();await server.wait_closed();tasks=list(self.tasks)
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready',required=True);parser.add_argument('--nonce',required=True)
    parser.add_argument('--clock-domain',required=True)
    parser.add_argument('--interval-recording',action='store_true')
    parser.add_argument('--capture-mode',choices=('disabled','bounded','continuous'),required=True)
    parser.add_argument('--work-s',type=float,default=.03);parser.add_argument('--report-s',type=float,default=.005)
    parser.add_argument('--fault',choices=('normal','missing_metric','stuck_busy','wrong_identity','startup_fail','ignore_term','reset_reject','stale_reset','interval_reset','interval_missing','interval_late','interval_clock','interval_generation','interval_overflow'),default='normal')
    asyncio.run(Target(parser.parse_args()).run())
