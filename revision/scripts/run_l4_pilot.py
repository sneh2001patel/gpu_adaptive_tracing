#!/usr/bin/env python3
"""Prospective L4 engineering pilot; no diagnosis-accuracy/savings claims.

Own a persistent Nsight/vLLM session, calibrate separately, stream real HTTP and
NVML observations, consume newly exported kernel evidence and preserve drain.
"""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import shlex
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from revision.tracing.aggregation import StreamingWindowAdapter,WindowConfig,p95
from revision.tracing.controller import StreamingController,ControllerConfig
from revision.tracing.nsys_backend import NsightServingBackend
from revision.tracing.nvml_sampler import NvmlSampler,NvmlConfig
from revision.tracing.policies import POLICIES,PolicyConfig
from revision.tracing.producers import ProducerBridge,ProducerConfig,http_post
from revision.tracing.timing import MonotonicClock,TimingRecorder,seconds_to_ns
from revision.tracing.windows import HealthyBaseline


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.pending')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)


def http_ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint+'/health',timeout=2) as response:return response.status==200
    except Exception:return False


async def calibrate(endpoint,model,directory):
    payload=json.dumps(dict(model=model,prompt='Explain why a queue grows when arrivals exceed service capacity.',
        max_tokens=32,temperature=0,ignore_eos=True,stream=False)).encode()
    config=ProducerConfig(endpoint+'/v1/completions',request_timeout_s=60)
    records=[]
    # Three separate warmup requests, then twelve sequential calibration requests.
    for index in range(15):
        start=time.monotonic_ns()
        status=await asyncio.wait_for(http_post(config,payload),60)
        end=time.monotonic_ns()
        if status!=200:raise RuntimeError('Healthy calibration request failed')
        records.append(dict(index=index,warmup=index<3,start_ns=start,end_ns=end,latency_ms=(end-start)/1e6,status=status))
        await asyncio.sleep(.1)
    save(directory/'calibration_requests.json',records)
    baseline=HealthyBaseline(p95([r['latency_ms'] for r in records if not r['warmup']]),str(directory/'calibration_requests.json'))
    save(directory/'calibration.json',asdict(baseline))
    return baseline


async def episode(args,clock,session,session_dir,prefix,workers,baseline,sampler,ordinal,policy,seed,case):
    directory=args.output/f'{case}-seed{seed}-{policy}'
    directory.mkdir()
    recorder=TimingRecorder(clock,provenance='live_online')
    backend=NsightServingBackend(recorder,session_dir,prefix,workers,args.device_uuid,
        args.endpoint,session,initial_ordinal=ordinal,timeout_s=30)
    controller=StreamingController(backend,baseline,lambda summary:None,
        lambda identity,window:backend.start(identity,window),
        ControllerConfig(policy=policy,policy_config=PolicyConfig(max_bursts=3),
            burst_s=1,startup_timeout_s=25,evidence_timeout_s=60,cooldown_s=2,reactivation_enabled=False))
    start=clock.now_ns()
    adapter=StreamingWindowAdapter(clock,WindowConfig(start,start+seconds_to_ns(args.horizon),
        window_s=2,allowed_lateness_s=.1,require_request_starts=True),controller.on_window,provenance='live_online')
    rate=.5 if case=='healthy' else 8
    tokens=32 if case=='healthy' else 128
    bridge=ProducerBridge(adapter,controller,ProducerConfig(args.endpoint+'/v1/completions',
        rate_rps=rate,max_inflight=16,request_timeout_s=45,drain_s=20,sample_interval_s=.2),
        dict(model=args.model,prompt='Explain why a queue grows when arrivals exceed service capacity.',
            max_tokens=tokens,temperature=0,ignore_eos=True,stream=False,seed=seed),sampler)
    try:
        production=await bridge.run()
    finally:
        controller.finish();await backend.aclose()
    result=dict(evidence_mode='live_online',experiment_role='engineering_pilot',case=case,seed=seed,
        policy=policy,gpu_uuid=args.device_uuid,diagnosis_status='unresolved_classifier_abstains',
        note='Laboratory workload intervention; no independent bottleneck reference or calibrated T2 classifier. No diagnosis accuracy or capture-active savings claim.',
        workload=dict(rate_rps=rate,max_tokens=tokens,observation_horizon_s=args.horizon,window_s=2),
        producer=production,aggregation=adapter.summary(),controller=controller.snapshot(),backend=backend.snapshot())
    save(directory/'results.json',result)
    for name,rows in [('windows',adapter.reports),('producer_events',bridge.events)]:
        (directory/(name+'.jsonl')).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    (directory/'controller_events.jsonl').write_text(controller.jsonl())
    (directory/'aggregation_events.jsonl').write_text(adapter.jsonl())
    (directory/'timing_events.jsonl').write_text(recorder.jsonl())
    print(json.dumps(dict(event='episode_finished',case=case,seed=seed,policy=policy,
        attempts=len(backend.attempts),valid_captures=sum(a['state']=='ready' for a in backend.attempts.values()),
        request_errors=production['errors'],directory=str(directory))),flush=True)
    if any(a['state']=='failed' for a in backend.attempts.values()):
        raise RuntimeError('Capture failure poisoned the session; inspect saved episode before continuing')
    if production['sampler_errors'] or any(r['window']['gpu_util'] is None for r in adapter.reports):
        raise RuntimeError('Incomplete GPU telemetry; preserve this run and stop the matrix')
    return backend.ordinal,result


async def with_fresh_sampler(clock,device_uuid,output,callback,*,sampler_factory=NvmlSampler):
    sampler=sampler_factory(NvmlConfig(device_uuid),clock)
    try:
        async with sampler:
            return await callback(sampler)
    finally:
        save(output/'sampler.json',dict(metadata=sampler.metadata,events=sampler.events))


async def main_async(args):
    args.output=args.output.resolve()
    args.output.relative_to(ROOT/'revision')
    args.output.mkdir(parents=True,exist_ok=False)
    code_paths=[p for directory in ('revision/tracing','revision/scripts','revision/native')
                for p in (ROOT/directory).glob('*') if p.is_file() and p.suffix in ('.py','.cu')]
    versions=subprocess.run(['uv','pip','freeze','--python',sys.executable],text=True,capture_output=True,check=True)
    (args.output/'packages.txt').write_text(versions.stdout)
    source_reference=args.output.parent/'source_snapshot.json'
    base=json.loads(source_reference.read_text()) if source_reference.exists() else {}
    save(args.output/'source_manifest.json',dict(source_mode='uncommitted_revision_snapshot',base_git_commit=base.get('git_head'),working_tree_dirty=True,
        files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths},
        pinned_model_path=args.model_path,configuration=vars(args)|{'output':str(args.output)}))
    session_dir=args.output/'session';session_dir.mkdir()
    clock=MonotonicClock()
    save(session_dir/'session.json',dict(clock_domain=clock.domain,host_monotonic_clock='CLOCK_MONOTONIC',
        device_uuid=args.device_uuid,nsys_expected='2026.3.1',vllm_expected='0.10.2'))
    prefix=session_dir/'capture'
    callback=str(ROOT/'revision/scripts/nsys_callback.py')
    callback_paths={}
    for action in ('start','report_ready'):
        path=session_dir/f'callback_{action}.sh'
        path.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,callback,str(session_dir),action])+'\n')
        path.chmod(0o700)
        callback_paths[action]=str(path)
    command=['nsys','profile','--trace=cuda,nvtx','--sample=none','--cpuctxsw=none',
        '--capture-range=cudaProfilerApi','--capture-range-end=repeat:120:sync','--kill=none',
        '--after-collection-start='+callback_paths['start'],
        '--after-report-ready='+callback_paths['report_ready'],
        '--output='+str(prefix),sys.executable,'-m','revision.scripts.serve_vllm_cuda',
        '--model',args.model_path,'--served-model-name',args.model,'--host','127.0.0.1','--port','8010',
        '--dtype','half','--enforce-eager','--gpu-memory-utilization','0.85','--max-model-len','2048',
        '--max-num-seqs','16','--max-num-batched-tokens','2048',
        '--worker-cls','revision.tracing.vllm_cuda_worker.CudaCaptureWorker','--disable-log-requests']
    env=os.environ.copy()
    env.update(PYTHONPATH=str(ROOT),HF_HOME='/dev/shm/hf-cache',VLLM_WORKER_MULTIPROC_METHOD='spawn',
        VLLM_USE_V1='1',VLLM_NO_USAGE_STATS='1',
        REVISION_SESSION_DIR=str(session_dir),REVISION_CLOCK_DOMAIN=clock.domain)
    save(args.output/'launch.json',dict(command=command,started_at_ns=clock.now_ns(),clock_domain=clock.domain))
    session=None
    sampler=NvmlSampler(NvmlConfig(args.device_uuid),clock)
    try:
        async with sampler:
            await sampler()
        with (args.output/'server.log').open('w') as log:
            session=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+300
        while not await asyncio.to_thread(http_ready,args.endpoint):
            if session.poll() is not None:raise RuntimeError('vLLM/Nsight startup failed; inspect server.log')
            if time.monotonic()>deadline:raise RuntimeError('vLLM startup timeout')
            await asyncio.sleep(1)
        workers=[json.loads(p.read_text()) for p in session_dir.glob('worker-*.json')]
        if len(workers)!=1 or workers[0]['device_uuid']!=args.device_uuid:raise RuntimeError('Worker/device mapping failed')
        worker_pids=[r['pid'] for r in workers]
        print(json.dumps(dict(event='server_ready',workers=workers)),flush=True)
        baseline=await calibrate(args.endpoint,args.model,args.output)
        print(json.dumps(dict(event='calibration_complete',baseline=asdict(baseline))),flush=True)
        ordinal=0;results=[]
        schedule=[('persistent_load',policy,seed) for seed in args.seeds for policy in args.policies]
        random.Random(20261027).shuffle(schedule)
        if args.healthy_controls:schedule=[('healthy','fixed_burst',seed) for seed in args.seeds]+schedule
        save(args.output/'schedule.json',dict(schedule=schedule,shuffle_seed=20261027,role='engineering_pilot_not_confirmatory',
            calibration_frozen=asdict(baseline),classifier='always_abstain_pending_independent_calibration',reactivation_enabled=False))
        for case,policy,seed in schedule:
            # A sampling-task cancellation can close a native sampler. Own a
            # fresh sampler per arm, initialized before its observation horizon.
            async def run_arm(arm_sampler):
                return await episode(args,clock,session,session_dir,prefix,worker_pids,baseline,arm_sampler,ordinal,policy,seed,case)
            ordinal,result=await with_fresh_sampler(clock,args.device_uuid,
                args.output/f'{case}-seed{seed}-{policy}',run_arm)
            results.append(dict(case=case,policy=policy,seed=seed,attempts=len(result['backend']['attempts']),
                valid_captures=sum(a['state']=='ready' for a in result['backend']['attempts'].values())))
            # Allow the previous episode's request drain to finish before a new arm.
            await asyncio.sleep(2)
        save(args.output/'pilot_summary.json',dict(role='engineering_pilot',gpu_used=True,runs=results,
            completed_runs=len(results),total_captures=ordinal,claims='No accuracy, robustness or GPU-active savings established'))
    finally:
        if session is not None:
            # Signal the owned session only; management services remain untouched.
            try:os.killpg(session.pid,signal.SIGINT)
            except ProcessLookupError:pass
            for _ in range(100):
                if session.poll() is not None:break
                await asyncio.sleep(.1)
            if session.poll() is None:
                os.killpg(session.pid,signal.SIGKILL);session.wait(timeout=5)
            save(args.output/'session_exit.json',dict(returncode=session.poll(),finished_at_ns=clock.now_ns()))
        save(args.output/'sampler.json',dict(metadata=sampler.metadata,events=sampler.events))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--device-uuid',required=True)
    p.add_argument('--model',default='Qwen/Qwen2.5-7B-Instruct')
    p.add_argument('--model-path',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8010')
    p.add_argument('--horizon',type=float,default=24)
    p.add_argument('--seeds',type=int,nargs='+',default=[1001,1002,1003])
    p.add_argument('--policies',choices=POLICIES,nargs='+',default=list(POLICIES))
    p.add_argument('--healthy-controls',action='store_true')
    args=p.parse_args()
    if args.horizon<12:p.error('Pilot horizon must be at least 12 seconds')
    asyncio.run(main_async(args))


if __name__=='__main__':main()
