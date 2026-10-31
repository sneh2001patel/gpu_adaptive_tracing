"""Owned single-worker L4 engineering feasibility; no study or diagnosis run."""
import asyncio,hashlib,json,os,shlex,shutil,socket,subprocess,sys,uuid
from pathlib import Path
from urllib.parse import urlsplit
from experiments.feasibility.discovery import ReadOnlyDiscovery
from experiments.feasibility.harness import check
from experiments.feasibility.metrics import inspect,GAUGES
from experiments.scripts.run_l4_discovery import close_owned,group_exists,save,ROOT
from experiments.tracing.feature_collection import http_body,response_usage
from experiments.tracing.measured_evidence import integer
from experiments.tracing.nsys_backend import NsightServingBackend
from experiments.tracing.timing import TimingRecorder
from experiments.tracing.worker_barrier import validate_barrier


class OwnedLiveActivity:
    def __init__(self,config,clock,endpoint,model_path):
        self.config,self.clock,self.endpoint=config,clock,endpoint.rstrip('/')
        self.model_path=Path(model_path).resolve();self.sessions=[];self.current=None;self.backend=None
        self.recorder=TimingRecorder(clock,provenance='live_online');self.capture_used=False;self.requests=[];self.tasks=set();self.quiet_evidence={}
        # Reuse strict local endpoint validation before any process is launched.
        ReadOnlyDiscovery(config,clock,endpoint,self.model_path,self.model_path)

    async def start(self,output,generation,reset_token=None,profile=False,event_instrumentation=False,prefix_caching=None):
        if prefix_caching is not None and type(prefix_caching) is not bool:
            raise ValueError('Explicit boolean prefix-cache policy required')
        output=Path(output).resolve()  # Nsight runs callbacks outside the project cwd.
        if self.current is not None and not self.current['closed']:raise RuntimeError('Prior owned session not closed')
        port=urlsplit(self.endpoint).port
        if port is None:raise ValueError('Explicit local port required')
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Serving port already occupied; will not attach')
        directory=output/f'session-{generation}';directory.mkdir()
        nonce=uuid.uuid4().hex
        save(directory/'session.json',dict(clock_domain=self.clock.domain,device_uuid=self.config['device_uuid'],
            generation=generation,session_nonce=nonce,reset_token=reset_token,vllm_expected='0.10.2',nsys_expected='2026.3.1'))
        command=[sys.executable,'-m','experiments.scripts.serve_vllm_cuda','--model',str(self.model_path),
            '--served-model-name',self.config['model'],'--host','127.0.0.1','--port',str(port),'--dtype','half',
            '--enforce-eager','--gpu-memory-utilization','0.85','--max-model-len','2048','--max-num-seqs','16',
            '--max-num-batched-tokens','2048','--worker-cls','experiments.tracing.vllm_cuda_worker.CudaCaptureWorker','--disable-log-requests']
        prefix=directory/'capture'
        if event_instrumentation:
            command+=['--scheduler-cls','experiments.tracing.vllm_event_scheduler.EventScheduler']
        # Preserve commissioning's cache-off opt-in default while allowing
        # collector-on/off controls to set exactly the same cache policy.
        cache_policy=False if event_instrumentation and prefix_caching is None else prefix_caching
        if cache_policy is not None:
            command+=['--enable-prefix-caching' if cache_policy else '--no-enable-prefix-caching']
        if profile:
            callback=ROOT/'experiments/scripts/nsys_callback.py';scripts={}
            for action in ('start','report_ready'):
                path=directory/('callback_'+action+'.sh')
                path.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,str(callback),str(directory),action])+'\n');path.chmod(0o700);scripts[action]=path
            command=['nsys','profile','--trace=cuda,nvtx','--sample=none','--cpuctxsw=none',
                '--capture-range=cudaProfilerApi','--capture-range-end=repeat:120:sync','--kill=none',
                '--after-collection-start='+str(scripts['start']),'--after-report-ready='+str(scripts['report_ready']),
                '--output='+str(prefix)]+command
        env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),VLLM_WORKER_MULTIPROC_METHOD='spawn',VLLM_USE_V1='1',
            VLLM_NO_USAGE_STATS='1',REVISION_SESSION_DIR=str(directory),REVISION_CLOCK_DOMAIN=self.clock.domain,
            REVISION_ENABLE_BARRIER='1',REVISION_SESSION_NONCE=nonce,REVISION_GENERATION=str(generation),REVISION_RESET_TOKEN=reset_token or '')
        # Explicit per-launch opt-in; never inherit an old shell's event setting.
        env.pop('REVISION_ENABLE_EVENTS',None)
        if event_instrumentation:env['REVISION_ENABLE_EVENTS']='1'
        started=self.clock.now_ns()
        with (directory/'server.log').open('wb') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        session=dict(directory=directory,process=process,nonce=nonce,generation=generation,closed=False,prefix=prefix,worker=None)
        self.sessions.append(session);self.current=session
        save(directory/'launch.json',dict(command=command,pid=process.pid,requested_at_ns=started,clock_domain=self.clock.domain))
        deadline=asyncio.get_running_loop().time()+55
        while True:
            if process.poll() is not None:raise RuntimeError('Owned serving/profiler process exited before readiness')
            try:
                status,_=await http_body(self.endpoint+'/health',timeout_s=1)
                if status==200:break
            except (OSError,asyncio.TimeoutError):pass
            if asyncio.get_running_loop().time()>=deadline:raise TimeoutError('Owned serving readiness deadline')
            await asyncio.sleep(.2)
        workers=[json.loads(p.read_text()) for p in directory.glob('worker-*.json')]
        if len(workers)!=1:raise ValueError('Exactly one fresh worker record required')
        worker=workers[0];integer(worker.get('pid'),'worker PID',1)
        expected=dict(device_uuid=self.config['device_uuid'],clock_domain=self.clock.domain,session_nonce=nonce,
            generation=generation,reset_token=reset_token or '')
        if any(worker.get(k)!=v for k,v in expected.items()):raise ValueError('Foreign worker generation/session/reset acknowledgement')
        if not started<=worker['ready_at_ns']<=self.clock.now_ns():raise ValueError('Worker clock not within fresh launch bracket')
        session['worker']=worker
        print(json.dumps(dict(event='owned_server_ready',generation=generation,pid=worker['pid'],profile=profile)),flush=True)
        return session

    def discovery(self):return ReadOnlyDiscovery(self.config,self.clock,self.endpoint,self.model_path,self.current['directory'])

    async def inventory(self,output,context):
        await self.start(output,0)
        return await self.discovery().inventory(output,context)

    async def metrics(self,output,context):return await self.discovery().metrics(output,context)

    async def quiet(self,output,label):
        output=Path(output).resolve()
        if not isinstance(label,str) or not label or label in ('.','..') or '/' in label or '\\' in label:
            raise ValueError('Quiet label must be a single filename component')
        session=self.current;worker=session['worker'];rows=[]
        if not Path(session['directory']).resolve().is_relative_to(output):
            raise ValueError('Quiet evidence output must contain the owned session')
        if output not in self.quiet_evidence and (output/'quiet_evidence.json').exists():
            raise ValueError('Will not replace existing quiet evidence from another activity')
        # One output is one episode. A deliberate restart within that output
        # retains both generations; a different job never inherits its rows.
        evidence=self.quiet_evidence.setdefault(output,[])
        for index in range(self.config['quiet_observations']):
            if any((output/f'{label}-{index}-{side}.txt').exists() for side in ('before','after')):
                raise ValueError('Quiet evidence filename already used; no overwrite')
        for index in range(self.config['quiet_observations']):
            if any(not t.done() for t in self.tasks):raise RuntimeError('Owned request still pending before quiet barrier')
            requested=self.clock.now_ns();status,before=await http_body(self.endpoint+'/metrics');before_received=self.clock.now_ns()
            before_values=inspect(before,model=self.config['model'],engine=self.config['engine'])['gauges']
            if status!=200 or any(not g['available'] or g['value']!=0 for g in before_values.values()):raise RuntimeError('Server is busy or queue gauges unavailable')
            command=dict(token=uuid.uuid4().hex,session_nonce=session['nonce'],generation=session['generation'],clock_domain=self.clock.domain,requested_at_ns=self.clock.now_ns())
            temporary=session['directory']/'barrier_command.pending';save(temporary,command);temporary.replace(session['directory']/'barrier_command.json')
            status,_=await http_body(self.endpoint+'/experiments/barrier',method='POST',payload={},timeout_s=15)
            received=self.clock.now_ns()
            if status!=200:raise RuntimeError('Worker barrier RPC failed')
            path=session['directory']/f'barrier-{command["token"]}-{worker["pid"]}.json'
            receipt=validate_barrier(json.loads(path.read_text()),command,pid=worker['pid'],device_uuid=self.config['device_uuid'],received_at_ns=received)
            status,after=await http_body(self.endpoint+'/metrics');observed=self.clock.now_ns()
            values=inspect(after,model=self.config['model'],engine=self.config['engine'])['gauges']
            if status!=200 or any(not g['available'] or g['value']!=0 for g in values.values()):raise RuntimeError('Server work appeared around worker barrier')
            before_path=output/f'{label}-{index}-before.txt';before_path.write_bytes(before)
            after_path=output/f'{label}-{index}-after.txt';after_path.write_bytes(after)
            rows.append(dict(observed_at_ns=observed,barrier_completed_at_ns=receipt['completed_at_ns'],queued=0,running=0,
                worker_pid=worker['pid'],generation=session['generation'],barrier_source=receipt['source'],barrier_token=receipt['token']))
            evidence.append(dict(label=label,index=index,requested_at_ns=requested,before_received_at_ns=before_received,
                barrier_command=command,barrier_receipt=receipt,barrier_received_at_ns=received,observed_at_ns=observed,
                before_path=before_path.name,before_sha256=hashlib.sha256(before).hexdigest(),after_path=after_path.name,after_sha256=hashlib.sha256(after).hexdigest(),owned_client_outstanding=0))
            save(output/'quiet_evidence.json',evidence)
            await asyncio.sleep(self.config['quiet_hold_ns']/1e9)
        return rows

    async def stop(self,session):
        if session['closed']:return session['cleanup']
        result=await close_owned(session['process'],self.clock)
        if session['worker'] is not None:
            pid=session['worker']['pid']
            try:os.kill(pid,0);absent=False
            except ProcessLookupError:absent=True
            if not absent:raise RuntimeError('Worker survived owned process-group shutdown')
            result['worker_pid']=pid;result['worker_absent']=True
        session['closed']=True;session['cleanup']=result;save(session['directory']/'exit.json',result)
        return result

    async def quiet_reset(self,output,context):
        before=await self.quiet(output,'before-reset');old=self.current;token=uuid.uuid4().hex;requested=self.clock.now_ns()
        await self.stop(old)
        fresh=await self.start(output,1,reset_token=token,profile=True)
        # Recheck pins/compute mapping after restart without replacing old context.
        inventory=await self.discovery().inventory(output,{})
        check('inventory',inventory,self.config,{},output,'live_online',self.clock.domain);save(output/'restart_inventory.json',inventory)
        completed=self.clock.now_ns();after=await self.quiet(output,'after-reset')
        return dict(clock_domain=self.clock.domain,before=before,after=after,reset=dict(method='fresh_owned_worker_restart',
            requested_at_ns=requested,completed_at_ns=completed,generation_before=0,generation_after=1,
            old_worker_pid=old['worker']['pid'],new_worker_pid=fresh['worker']['pid'],request_token=token,
            ack_token=fresh['worker']['reset_token'],old_session_nonce=old['nonce'],new_session_nonce=fresh['nonce'],
            state_semantics='new_engine_worker_and_KV_cache_model_files_and_OS_page_cache_reused'))

    async def request(self,output,identity,tokens):
        start=self.clock.now_ns();status=None;raw=None;error=None
        try:
            status,raw=await http_body(self.endpoint+'/v1/completions',method='POST',payload=dict(model=self.config['model'],
                prompt='Explain in one sentence why a request queue can grow.',max_tokens=tokens,temperature=0,ignore_eos=True,stream=False),timeout_s=40)
            if status!=200:raise RuntimeError('Serving request returned '+str(status))
            prompt,completed,usage_error=response_usage(raw)
            if usage_error:raise RuntimeError(usage_error)
            return status
        except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
        finally:
            end=self.clock.now_ns();filename=identity+'.json'
            if raw is not None:(output/filename).write_bytes(raw)
            self.requests.append(dict(request_id=identity,requested_at_ns=start,completed_at_ns=end,http_status=status,
                error=error,response_path=filename if raw is not None else None,
                response_sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None))
            save(output/'requests.json',self.requests)

    async def wait_capture(self,identity,target):
        while True:
            state=self.backend.poll(identity)
            if state==target:return
            if state=='failed':raise RuntimeError(self.backend.attempts[identity]['error'])
            await asyncio.sleep(.01)

    async def capture(self,output,context):
        if self.capture_used:raise RuntimeError('Exactly one capture attempt allowed; no charged retry')
        self.capture_used=True;session=self.current;pid=session['worker']['pid'];identity='feasibility-capture-1'
        self.backend=NsightServingBackend(self.recorder,session['directory'],session['prefix'],[pid],self.config['device_uuid'],self.endpoint,session['process'],timeout_s=30)
        self.backend.start(identity);await self.wait_capture(identity,'capturing')
        task=asyncio.create_task(self.request(output,'during-capture',32));self.tasks.add(task)
        await asyncio.sleep(self.config['requested_capture_s']);self.backend.stop(identity)
        await self.wait_capture(identity,'ready');ready=self.backend.evidence(identity)
        # A readiness decision only, with no inferred diagnosis or stop policy.
        decision=self.recorder.mark('feasibility_decision_ready',identity).timestamp_ns
        await task
        continuation=await self.request(output,'after-capture',16)
        continued=self.requests[-1]['completed_at_ns'];attempt=self.backend.attempts[identity]
        database=output/'validated_capture.sqlite';shutil.copyfile(attempt['database'],database)
        report_ready=next(e.timestamp_ns for e in self.recorder.events if e.scope==identity and e.name=='report_ready')
        await self.quiet(output,'post-capture')
        save(output/'backend.json',self.backend.snapshot());(output/'timing_events.jsonl').write_text(self.recorder.jsonl())
        return dict(clock_domain=self.clock.domain,source='nsys_sqlite',sqlite_path=database.name,
            sqlite_sha256=hashlib.sha256(database.read_bytes()).hexdigest(),start_ack_ns=attempt['start_ack'][0]['returned_at_ns'],
            stop_ack_ns=attempt['stop_ack'][0]['returned_at_ns'],report_ready_ns=report_ready,parsed_ready_ns=ready.ready_at_ns,
            decision_ns=decision,serving_continued_ns=continued,continuation_http_status=continuation,
            classifier='not_run_readiness_check_only',capture_active_s=None)

    async def cleanup(self,output,context):
        errors=[]
        for task in self.tasks:
            if not task.done():task.cancel()
        if self.tasks:await asyncio.gather(*self.tasks,return_exceptions=True)
        if self.backend is not None:
            try:await self.backend.aclose()
            except Exception as exc:errors.append('backend: '+str(exc))
            save(output/'backend_final.json',self.backend.snapshot());(output/'timing_events.jsonl').write_text(self.recorder.jsonl())
        for session in reversed(self.sessions):
            try:await self.stop(session)
            except Exception as exc:errors.append('session: '+str(exc))
        save(output/'cleanup_sessions.json',dict(sessions=[dict(directory=str(s['directory']),closed=s['closed'],cleanup=s.get('cleanup')) for s in self.sessions],errors=errors))
        if errors:raise RuntimeError('; '.join(errors))
        return dict(scope='all_pilot_owned_process_groups',clock_domain=self.clock.domain,confirmed_absent=all(s['closed'] for s in self.sessions),completed_at_ns=self.clock.now_ns())
