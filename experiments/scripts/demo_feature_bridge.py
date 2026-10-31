#!/usr/bin/env python3
"""Loopback HTTP features + delayed fake profiler, all synthetic and CPU-only."""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path

from experiments.tracing.aggregation import GpuSample
from experiments.tracing.feature_collection import FeatureWindow, QueueGaugeCollector, collect_completion
from experiments.tracing.feature_bridge import FeatureClassifierBridge
from experiments.tracing.measured_evidence import Acquisition
from experiments.tracing.profiler import FakeCapturePlan, FakeProfilerBackend, EvidenceNotReady
from experiments.tracing.timing import MonotonicClock, TimingRecorder


class LocalFeatureService:
    def __init__(self,case):
        self.case=case;self.queue=8;self.tasks=set()
    async def __aenter__(self):
        self.server=await asyncio.start_server(self.handle,'127.0.0.1',0)
        self.endpoint=f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        return self
    async def __aexit__(self,*args):
        self.server.close();await self.server.wait_closed()
        tasks=list(self.tasks)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task)
        try:
            head=await reader.readuntil(b'\r\n\r\n')
            length=next((int(line.split(b':',1)[1]) for line in head.split(b'\r\n') if line.lower().startswith(b'content-length:')),0)
            await reader.readexactly(length)
            if head.startswith(b'GET '):
                series='unconfigured_queue' if self.case=='missing_queue' else 'fixture_queue'
                body=f'# TYPE fixture_queue gauge\n{series} {self.queue}\n'.encode()
            else:
                payload={} if self.case=='missing_usage' else {'usage':{'prompt_tokens':7,'completion_tokens':3}}
                body=json.dumps(payload).encode()
            writer.write(f'HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()+body)
            await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError):pass
        finally:
            writer.close();self.tasks.discard(task)


async def run_case(case):
    clock=MonotonicClock();recorder=TimingRecorder(clock,provenance='synthetic_simulation')
    backend=FakeProfilerBackend(recorder)
    bridge=FeatureClassifierBridge(clock,provenance='synthetic_simulation',device_uuid='GPU-synthetic',worker_pid=123)
    raw=[];audits=[];pending_checks=0
    async with LocalFeatureService(case) as service:
        collector=QueueGaugeCollector(service.endpoint+'/metrics','fixture_queue')
        for index in range(2 if case=='transition' else 1):
            service.queue=8 if index==0 else 0
            start=clock.now_ns();receipts=[]
            capture_id=f'capture-{index}'
            backend.start(capture_id,FakeCapturePlan(startup_s=0,finalization_s=.3,stats_s=0,parse_s=0,
                kernel_summary=dict(source='synthetic_fixture',device_uuid='GPU-synthetic',captured_worker_pids=[123],
                    kernel_count=20,kernel_time_sum_s=.01,coverage='single_configured_worker_and_device_verified')))
            backend.poll(capture_id);capture_start=clock.now_ns()
            for request_index in range(1 if case=='sparse' else 3):
                request=await collect_completion(clock,f'r-{index}-{request_index}',service.endpoint+'/v1/completions',
                    {'prompt':'fixture','max_tokens':9999},timeout_s=2)
                sample=await collector.sample(clock,f's-{index}-{request_index}')
                gpu=GpuSample(f'g-{index}-{request_index}',clock.now_ns(),clock.now_ns(),clock.domain,90)
                receipts.extend((request,sample,gpu))
                raw.append(dict(request=asdict(request),server=asdict(sample)))
            capture_end=clock.now_ns();backend.stop(capture_id)
            # This is a contract fixture, not an experimental horizon: construct
            # its interval after HTTP acquisition so host contention cannot put
            # that acquisition outside an unrelated fixed 200 ms timer. The
            # exact-arrival workload driver still uses predeclared fixed horizons.
            window=FeatureWindow(clock,start,capture_end+200_000_000,min_latency_samples=2,grace_ns=5_000_000)
            from experiments.tracing.feature_collection import ObservedCompletion,ServerSample
            for record in receipts:
                if type(record) is ObservedCompletion:window.on_completion(record)
                elif type(record) is ServerSample:window.on_server(record)
                else:window.on_gpu(record)
            # A pause after acquisition makes parsed evidence available after
            # closure. The bridge must retain this window instead of latest data.
            await asyncio.sleep(max(0,(window.deadline_ns-clock.now_ns())/1e9))
            window.close();window_id=f'window-{index}';bridge.register(window_id,window)
            try:backend.evidence(capture_id)
            except EvidenceNotReady:pending_checks+=1
            deadline=asyncio.get_running_loop().time()+3
            while backend.poll(capture_id)!='ready':
                if asyncio.get_running_loop().time()>deadline:raise TimeoutError('Fake pipeline did not finish')
                await asyncio.sleep(.001)
            ready=backend.evidence(capture_id)
            bridge.classify(window_id,ready=ready,capture_acquisition=Acquisition(capture_start,capture_end,ready.ready_at_ns,clock.domain))
            audits.append(window.audit())
    return dict(provenance='synthetic_simulation',gpu_used=False,scenario=case,
        note='Loopback HTTP measurements; server values, token usage and profiler kernels are fixtures. No diagnosis accuracy or GPU cost evidence.',
        pending_evidence_checks=pending_checks,observations=[asdict(o) for o in bridge.observations],
        predictions=[asdict(p) for p in bridge.predictions],raw_records=raw,window_audits=audits,
        profiler_events=[asdict(e) for e in recorder.events])


async def main_async(output):
    output.mkdir(parents=True,exist_ok=False)
    for case in ('complete','missing_queue','missing_usage','sparse','transition'):
        result=await run_case(case)
        (output/f'{case}.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps(dict(case=case,observations=len(result['observations']),
            unknown_predictions=sum(p['policy_label'] is None for p in result['predictions']),gpu_used=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main_async(parser.parse_args().output))
