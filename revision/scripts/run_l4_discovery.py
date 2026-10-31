#!/usr/bin/env python3
"""Own one pinned serving session for discovery and two bounded request probes.

No capture/reset/main matrix. Persistent service ownership belongs to supervisor;
this one-shot wrapper closes only its own serving process group.
"""
import argparse,asyncio,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from revision.feasibility.discovery import ReadOnlyDiscovery
from revision.feasibility.harness import run
from revision.feasibility.metrics import sequence
from revision.scripts.play_arrivals import write_sources
from revision.tracing.feature_collection import collect_completion,http_body
from revision.tracing.timing import MonotonicClock
from dataclasses import asdict

ROOT=Path(__file__).resolve().parents[2]


def save(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def group_exists(pid):
    try:os.killpg(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True  # Unknown liveness is not confirmed absence.


async def close_owned(process,clock):
    if process is None:return dict(owned=False,group_absent=True)
    start=clock.now_ns();escalated=False
    if group_exists(process.pid):
        try:os.killpg(process.pid,signal.SIGINT)
        except (ProcessLookupError,PermissionError):pass
    deadline=asyncio.get_running_loop().time()+15
    while group_exists(process.pid):
        process.poll()
        if asyncio.get_running_loop().time()>=deadline:
            try:os.killpg(process.pid,signal.SIGKILL)
            except (ProcessLookupError,PermissionError):pass
            escalated=True;break
        await asyncio.sleep(.1)
    if escalated:
        deadline=asyncio.get_running_loop().time()+5
        while group_exists(process.pid) and asyncio.get_running_loop().time()<deadline:
            process.poll();await asyncio.sleep(.05)
    process.poll();alive=group_exists(process.pid)
    result=dict(owned=True,pid=process.pid,returncode=process.returncode,group_absent=not alive,
        escalated=escalated,started_at_ns=start,completed_at_ns=clock.now_ns())
    if alive:raise RuntimeError('Owned serving group remains after cleanup')
    return result


async def main(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);write_sources(output)
    config=json.loads((ROOT/'revision/configs/l4_feasibility_v1.json').read_text());config['device_uuid']=args.device_uuid
    clock=MonotonicClock();process=None;status='running';error=None;cleanup=None
    session=output/'session';session.mkdir()
    save(output/'launch_plan.json',dict(role='live_capability_discovery_and_bounded_serving_probe',gpu_used=True,
        config=config,endpoint=args.endpoint,clock_domain=clock.domain,capture_enabled=False,main_matrix_enabled=False))
    try:
        print(json.dumps(dict(event='model_restore_started',revision=config['model_revision'])),flush=True)
        from huggingface_hub import snapshot_download
        model=await asyncio.to_thread(snapshot_download,repo_id=config['model'],revision=config['model_revision'],
            cache_dir=args.cache,allow_patterns=['*.json','*.safetensors','tokenizer.model','merges.txt','vocab.json','*.txt'])
        model=Path(model)
        model_files={p.name:dict(bytes=p.stat().st_size,sha256=sha_file(p)) for p in sorted(model.iterdir()) if p.is_file()}
        save(output/'model_files.json',dict(revision=config['model_revision'],path=str(model),files=model_files))
        print(json.dumps(dict(event='model_restored',files=len(model_files))),flush=True)
        port=args.endpoint.rsplit(':',1)[1]
        command=[sys.executable,'-m','revision.scripts.serve_vllm_cuda','--model',str(model),'--served-model-name',config['model'],
            '--host','127.0.0.1','--port',port,'--dtype','half','--enforce-eager','--gpu-memory-utilization','0.85',
            '--max-model-len','2048','--max-num-seqs','16','--max-num-batched-tokens','2048',
            '--worker-cls','revision.tracing.vllm_cuda_worker.CudaCaptureWorker','--disable-log-requests']
        env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),VLLM_WORKER_MULTIPROC_METHOD='spawn',VLLM_USE_V1='1',
            VLLM_NO_USAGE_STATS='1',REVISION_SESSION_DIR=str(session),REVISION_CLOCK_DOMAIN=clock.domain)
        save(output/'launch.json',dict(command=command,started_at_ns=clock.now_ns(),clock_domain=clock.domain))
        with (output/'server.log').open('wb') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=asyncio.get_running_loop().time()+300
        while True:
            if process.poll() is not None:raise RuntimeError('Serving exited before readiness')
            try:
                http_status,_=await http_body(args.endpoint+'/health',timeout_s=2)
                if http_status==200:break
            except (OSError,asyncio.TimeoutError):pass
            if asyncio.get_running_loop().time()>=deadline:raise TimeoutError('Serving readiness deadline')
            await asyncio.sleep(1)
        print(json.dumps(dict(event='server_ready',pid=process.pid)),flush=True)
        adapter=ReadOnlyDiscovery(config,clock,args.endpoint,model,session)
        result=await run(adapter,config,output/'discovery',provenance='live_online',clock_domain=clock.domain)
        if not result['discovery_passed']:raise RuntimeError('Pinned-stack discovery failed; inspect gates')
        print(json.dumps(dict(event='discovery_passed',activity_feasibility=result['live_feasibility_passed'])),flush=True)
        receipts=[];raws=[]
        async def metrics(index):
            before=clock.now_ns();http_status,raw=await http_body(args.endpoint+'/metrics');after=clock.now_ns()
            path=output/f'probe-metrics-{index}.txt';path.write_bytes(raw)
            receipts.append(dict(path=path.name,sha256=hashlib.sha256(raw).hexdigest(),http_status=http_status,
                requested_at_ns=before,received_at_ns=after,clock_domain=clock.domain))
            if http_status!=200:raise RuntimeError('Probe metrics unavailable')
            raws.append(raw)
        await metrics(0);requests=[]
        for index in range(2):
            record=await collect_completion(clock,f'feasibility-probe-{index}',args.endpoint+'/v1/completions',
                dict(model=config['model'],prompt='Explain in one sentence why a request queue can grow.',
                    max_tokens=16,temperature=0,ignore_eos=True,stream=False),timeout_s=60)
            requests.append(asdict(record));save(output/'probe_requests.json',requests)
            if not record.completion.success:raise RuntimeError('Bounded serving probe failed')
            await asyncio.sleep(1.1);await metrics(index+1)
        save(output/'probe_metric_receipts.json',receipts)
        save(output/'probe_capabilities.json',sequence(raws,model=config['model'],engine=config['engine']))
        status='completed';print(json.dumps(dict(event='bounded_probe_completed',requests=len(requests))),flush=True)
    except BaseException as exc:
        status='aborted' if isinstance(exc,asyncio.CancelledError) else 'failed';error=dict(type=type(exc).__name__,detail=str(exc));raise
    finally:
        task=asyncio.create_task(close_owned(process,clock))
        while not task.done():
            try:await asyncio.shield(task)
            except asyncio.CancelledError:status='aborted'
        try:cleanup=task.result()
        except Exception as exc:status='failed';cleanup=dict(error=type(exc).__name__,detail=str(exc),group_absent=False)
        save(output/'session_exit.json',dict(status=status,error=error,cleanup=cleanup,clock_domain=clock.domain,
            capture_active_s=None,study_ready=False,diagnosis_ready=False,finished_at_ns=clock.now_ns()))
        hashes={str(p.relative_to(output)):sha_file(p) for p in sorted(output.rglob('*')) if p.is_file()}
        save(output/'artifact_manifest.json',dict(files=hashes))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device-uuid',required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:8011')
    parser.add_argument('--cache',default='/dev/shm/hf-cache/hub')
    asyncio.run(main(parser.parse_args()))
