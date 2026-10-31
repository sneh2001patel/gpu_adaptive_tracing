#!/usr/bin/env python3
"""Exact saved arrivals with local workload/metrics fixtures and fake evidence."""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import time

from revision.scripts.play_arrivals import write_sources
from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.tracing.schedule_playback import PlaybackConfig, SchedulePlayback
from revision.tracing.feature_collection import QueueGaugeCollector
from revision.tracing.feature_bridge import FeatureClassifierBridge
from revision.tracing.measured_evidence import Acquisition
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import MonotonicClock, TimingRecorder


class PlaybackService:
    def __init__(self,case):self.case=case;self.tasks=set();self.started=time.monotonic()
    async def __aenter__(self):
        self.server=await asyncio.start_server(self.handle,'127.0.0.1',0)
        self.endpoint=f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        return self
    async def __aexit__(self,*args):
        self.server.close();await self.server.wait_closed();tasks=list(self.tasks)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task)
        try:
            head=await reader.readuntil(b'\r\n\r\n')
            size=next((int(line.split(b':',1)[1]) for line in head.split(b'\r\n') if line.lower().startswith(b'content-length:')),0)
            await reader.readexactly(size)
            if head.startswith(b'GET '):
                queue=0 if self.case=='transition' and time.monotonic()-self.started>.12 else 8
                body=f'# TYPE fixture_queue gauge\nfixture_queue {queue}\n'.encode()
            else:
                delay={'capacity':.08,'timeout':.12,'drain':.2}.get(self.case,.003)
                await asyncio.sleep(delay)
                body=b'{"usage":{"prompt_tokens":7,"completion_tokens":3}}'
            writer.write(f'HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()+body)
            await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError):pass
        finally:writer.close();self.tasks.discard(task)


def offered_bytes():
    return (json.dumps(dict(version='offered_arrivals_v1',duration_ns=250000000,requests=[
        dict(request_id=f'opaque-{index}',offset_ns=round(offset*1e9),payload=dict(model='fixture',
            prompt='Actual fixture request text',max_tokens=99,stream=False,temperature=0,seed=index))
        for index,offset in enumerate((0,.03,.06,.12,.18))]),indent=2)+'\n').encode()


async def run_case(case,schedule):
    clock=MonotonicClock();recorder=TimingRecorder(clock,provenance='synthetic_simulation')
    backend=FakeProfilerBackend(recorder);bridge=FeatureClassifierBridge(clock,provenance='synthetic_simulation',device_uuid='GPU-fixture',worker_pid=1)
    capture={};driver=None
    def on_window(identity,window):
        bridge.register(identity,window)
        if case!='delayed_evidence' or identity!='window-0':bridge.classify(identity)
    def service():
        if case!='delayed_evidence':return
        if not capture:
            backend.start('capture-1',FakeCapturePlan(startup_s=0,finalization_s=.12,stats_s=0,parse_s=0,
                kernel_summary=dict(source='synthetic_fixture',device_uuid='GPU-fixture',captured_worker_pids=[1],
                    kernel_count=20,kernel_time_sum_s=.01,coverage='single_configured_worker_and_device_verified')))
            backend.poll('capture-1');capture.update(start=clock.now_ns(),classified=False)
        if backend.state('capture-1')=='capturing' and clock.now_ns()-capture['start']>=10000000:
            capture['end']=clock.now_ns();backend.stop('capture-1')
        backend.poll('capture-1')
        if backend.state('capture-1')=='ready' and 'window-0' in bridge.windows and not capture['classified']:
            ready=backend.evidence('capture-1')
            bridge.classify('window-0',ready=ready,capture_acquisition=Acquisition(capture['start'],capture['end'],ready.ready_at_ns,clock.domain))
            capture['classified']=True
    async def gpu():return 90
    async with PlaybackService(case) as server:
        config=PlaybackConfig(max_inflight=1 if case=='capacity' else 8,request_timeout_s=.015 if case=='timeout' else 1,
            drain_s=.02 if case=='drain' else .1,max_admission_lateness_s=.05,window_s=.1,
            grace_s=.01,sample_interval_s=.02,min_latency_samples=2)
        driver=SchedulePlayback(schedule,clock,server.endpoint+'/v1/completions',provenance='synthetic_simulation',config=config,
            server_collector=QueueGaugeCollector(server.endpoint+'/metrics','fixture_queue'),gpu_sampler=gpu,
            on_window=on_window,service_evidence=service)
        try:result=await driver.run()
        finally:
            if capture and backend.state('capture-1') not in ('ready','failed'):backend.cancel('capture-1','playback_ended')
    return result|dict(case=case,gpu_used=False,role='synthetic_CPU_workload_driver_validation',
        note='Loopback HTTP durations only. Queue/token/GPU/kernel values are fixtures, not observed GPU workload mechanisms.',
        observations=[asdict(o) for o in bridge.observations],predictions=[asdict(p) for p in bridge.predictions],
        fake_capture=capture,profiler_events=[asdict(e) for e in recorder.events])


async def main(output):
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    raw=offered_bytes();(output/'offered_arrivals.json').write_bytes(raw);schedule=ArrivalSchedule.from_bytes(raw)
    for case in ('normal','capacity','timeout','drain','transition','delayed_evidence'):
        result=await run_case(case,schedule)
        (output/f'{case}.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:result[k] for k in ('case','offered','admitted','counts','accounting_checks')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args().output))
