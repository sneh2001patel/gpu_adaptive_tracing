"""CPU fixtures for the owned live adapter; real GPU pilot is saved separately."""
import asyncio,hashlib,importlib.util,json,os,tempfile,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from experiments.feasibility.activity import OwnedLiveActivity
from experiments.scripts.demo_live_feasibility import metric_text
from experiments.tracing.worker_barrier import worker_barrier


def configuration():
    data=json.loads(Path('experiments/configs/l4_feasibility_v1.json').read_text());data['device_uuid']='GPU-fixture';return data


class TickClock:
    domain='fixture-clock'
    def __init__(self):self.value=0
    def now_ns(self):self.value+=10_000_000;return self.value


class ActivityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=TickClock();self.adapter=OwnedLiveActivity(configuration(),self.clock,'http://127.0.0.1:8012',self.root)
        self.adapter.current=dict(directory=self.root,nonce='owned',generation=1,worker=dict(pid=43))
    async def http(self,endpoint,**kwargs):
        if endpoint.endswith('/experiments/barrier'):
            command=json.loads((self.root/'barrier_command.json').read_text())
            receipt=worker_barrier(command,pid=43,device_uuid='GPU-fixture',clock_domain=self.clock.domain,
                session_nonce='owned',generation=1,capture_active=False,synchronize=lambda:None,now_ns=self.clock.now_ns)
            (self.root/f'barrier-{command["token"]}-43.json').write_text(json.dumps(receipt));return 200,b''
        return 200,metric_text()
    async def test_quiet_requires_fresh_worker_sync_and_raw_counter_evidence(self):
        with patch('experiments.feasibility.activity.http_body',side_effect=self.http):rows=await self.adapter.quiet(self.root,'check')
        self.assertEqual(len(rows),2);self.assertEqual(len({r['barrier_token'] for r in rows}),2)
        evidence=json.loads((self.root/'quiet_evidence.json').read_text());self.assertEqual(len(evidence),2)
        for r in evidence:
            self.assertEqual(hashlib.sha256((self.root/r['before_path']).read_bytes()).hexdigest(),r['before_sha256'])
            self.assertEqual(r['owned_client_outstanding'],0)
    async def test_busy_server_fails_before_worker_barrier(self):
        with patch('experiments.feasibility.activity.http_body',return_value=(200,metric_text(waiting=1))):
            with self.assertRaises(RuntimeError):await self.adapter.quiet(self.root,'busy')
        self.assertFalse((self.root/'barrier_command.json').exists())
    async def test_pending_owned_request_prevents_quiet(self):
        future=asyncio.get_running_loop().create_future();self.adapter.tasks.add(future)
        with self.assertRaises(RuntimeError):await self.adapter.quiet(self.root,'pending')
        future.cancel()
    async def test_foreign_worker_receipt_fails(self):
        async def foreign(endpoint,**kwargs):
            result=await self.http(endpoint,**kwargs)
            if endpoint.endswith('/experiments/barrier'):
                p=next(self.root.glob('barrier-*.json'));r=json.loads(p.read_text());r['pid']=99;p.write_text(json.dumps(r))
            return result
        with patch('experiments.feasibility.activity.http_body',side_effect=foreign):
            with self.assertRaises(ValueError):await self.adapter.quiet(self.root,'foreign')
    async def test_second_capture_is_rejected_without_launching_backend(self):
        self.adapter.capture_used=True
        with self.assertRaises(RuntimeError):await self.adapter.capture(self.root,{})
        self.assertIsNone(self.adapter.backend)
    async def test_failed_request_is_persisted_not_dropped(self):
        with patch('experiments.feasibility.activity.http_body',return_value=(503,b'{"error":"unavailable"}')):
            with self.assertRaises(RuntimeError):await self.adapter.request(self.root,'failed-request',16)
        data=json.loads((self.root/'requests.json').read_text());self.assertEqual(data[0]['http_status'],503)
        self.assertIsNotNone(data[0]['error']);self.assertTrue((self.root/'failed-request.json').exists())
    async def test_cleanup_attempts_all_owned_sessions_even_after_failure(self):
        self.adapter.sessions=[dict(directory='old',closed=False),dict(directory='new',closed=False)]
        async def close(session):
            session['closed']=True
            if session['directory']=='new':raise RuntimeError('fixture cleanup failure')
        with patch.object(self.adapter,'stop',side_effect=close):
            with self.assertRaises(RuntimeError):await self.adapter.cleanup(self.root,{})
        self.assertTrue(all(s['closed'] for s in self.adapter.sessions))
        self.assertTrue(json.loads((self.root/'cleanup_sessions.json').read_text())['errors'])
    async def test_relative_output_produces_absolute_nsight_callbacks_and_session(self):
        self.adapter.current=None;relative=Path(os.path.relpath(self.root,Path.cwd()));seen=[]
        def stop_before_launch(command,**kwargs):
            seen.extend(command)
            for name in ('--after-collection-start=','--after-report-ready=','--output='):
                value=next(x[len(name):] for x in command if x.startswith(name))
                self.assertTrue(Path(value).is_absolute(),value)
            self.assertTrue(Path(kwargs['env']['REVISION_SESSION_DIR']).is_absolute())
            raise RuntimeError('fixture stops before process launch')
        with patch('experiments.feasibility.activity.socket.socket') as sock,patch('experiments.feasibility.activity.subprocess.Popen',side_effect=stop_before_launch):
            sock.return_value.__enter__.return_value.connect_ex.return_value=1
            with self.assertRaisesRegex(RuntimeError,'fixture stops'):await self.adapter.start(relative,2,profile=True)
        self.assertIn('nsys',seen);self.assertEqual(self.adapter.sessions,[])

    async def test_nonlocal_endpoint_rejected_before_session_creation(self):
        with self.assertRaises(ValueError):OwnedLiveActivity(configuration(),self.clock,'http://example.com:8012',self.root)

    async def test_event_opt_in_changes_only_explicit_launch_and_clears_inherited_flag(self):
        for enabled in (False,True):
            self.adapter.current=None
            target=self.root/str(enabled);target.mkdir()
            def inspect_launch(command,**kwargs):
                self.assertEqual('--scheduler-cls' in command,enabled)
                self.assertEqual('--no-enable-prefix-caching' in command,enabled)
                self.assertEqual(kwargs['env'].get('REVISION_ENABLE_EVENTS'), '1' if enabled else None)
                raise RuntimeError('fixture before launch')
            with patch.dict(os.environ,dict(REVISION_ENABLE_EVENTS='1')),patch('experiments.feasibility.activity.socket.socket') as sock,patch('experiments.feasibility.activity.subprocess.Popen',side_effect=inspect_launch):
                sock.return_value.__enter__.return_value.connect_ex.return_value=1
                with self.assertRaisesRegex(RuntimeError,'fixture before'):await self.adapter.start(target,0,event_instrumentation=enabled)

    async def test_explicit_cache_policy_is_independent_of_event_collector(self):
        for enabled in (False,True):
            for cache in (False,True):
                self.adapter.current=None;target=self.root/(str(enabled)+str(cache));target.mkdir()
                def inspect_launch(command,**kwargs):
                    self.assertEqual('--scheduler-cls' in command,enabled)
                    self.assertEqual('--no-enable-prefix-caching' in command,not cache)
                    self.assertEqual('--enable-prefix-caching' in command,cache)
                    raise RuntimeError('fixture before launch')
                with patch('experiments.feasibility.activity.socket.socket') as sock,patch('experiments.feasibility.activity.subprocess.Popen',side_effect=inspect_launch):
                    sock.return_value.__enter__.return_value.connect_ex.return_value=1
                    with self.assertRaisesRegex(RuntimeError,'fixture before'):
                        await self.adapter.start(target,0,event_instrumentation=enabled,prefix_caching=cache)

    async def test_nonboolean_cache_policy_is_rejected_before_creating_session(self):
        for value in (0,1,'false'):
            with self.assertRaises(ValueError):await self.adapter.start(self.root,0,prefix_caching=value)
        self.assertFalse((self.root/'session-0').exists())

    async def scoped_http(self,endpoint,**kwargs):
        session=self.adapter.current;pid=session['worker']['pid']
        if endpoint.endswith('/experiments/barrier'):
            command=json.loads((session['directory']/'barrier_command.json').read_text())
            receipt=worker_barrier(command,pid=pid,device_uuid='GPU-fixture',clock_domain=self.clock.domain,
                session_nonce=session['nonce'],generation=session['generation'],capture_active=False,
                synchronize=lambda:None,now_ns=self.clock.now_ns)
            (session['directory']/f'barrier-{command["token"]}-{pid}.json').write_text(json.dumps(receipt))
            return 200,b''
        return 200,metric_text()+f'\n# fixture session {session["nonce"]}\n'.encode()

    def owned_session(self,output,nonce,generation,pid):
        directory=output/f'session-{generation}';directory.mkdir(parents=True)
        self.adapter.current=dict(directory=directory,nonce=nonce,generation=generation,worker=dict(pid=pid))

    async def test_multiple_jobs_reuse_names_but_keep_only_their_own_hashes_and_rows(self):
        snapshots={}
        with patch('experiments.feasibility.activity.http_body',side_effect=self.scoped_http):
            for name,generation,pid in [('a',1,43),('b',2,99)]:
                output=self.root/name;self.owned_session(output,name,generation,pid)
                for phase in ('before','after'):await self.adapter.quiet(output,phase)
                evidence=json.loads((output/'quiet_evidence.json').read_text());self.assertEqual(len(evidence),4)
                for row in evidence:
                    self.assertEqual(row['barrier_command']['session_nonce'],name)
                    self.assertEqual(row['barrier_receipt']['pid'],pid)
                    for side in ('before','after'):
                        self.assertEqual(hashlib.sha256((output/row[side+'_path']).read_bytes()).hexdigest(),row[side+'_sha256'])
                snapshots[name]=(output/'quiet_evidence.json').read_bytes()
        self.assertEqual((self.root/'a/quiet_evidence.json').read_bytes(),snapshots['a'])
        self.assertNotEqual((self.root/'a/before-0-before.txt').read_bytes(),(self.root/'b/before-0-before.txt').read_bytes())

    async def test_same_episode_preserves_both_reset_generations(self):
        with patch('experiments.feasibility.activity.http_body',side_effect=self.scoped_http):
            self.owned_session(self.root,'old',0,43);await self.adapter.quiet(self.root,'before-reset')
            self.owned_session(self.root,'fresh',1,99);await self.adapter.quiet(self.root,'after-reset')
        rows=json.loads((self.root/'quiet_evidence.json').read_text())
        self.assertEqual([r['barrier_command']['generation'] for r in rows],[0,0,1,1])
        self.assertEqual(len({r['barrier_command']['token'] for r in rows}),4)

    async def test_reused_quiet_label_fails_before_overwriting_or_rpc(self):
        with patch('experiments.feasibility.activity.http_body',side_effect=self.http):await self.adapter.quiet(self.root,'before')
        original={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        with patch('experiments.feasibility.activity.http_body',new_callable=AsyncMock) as http:
            with self.assertRaisesRegex(ValueError,'already used'):await self.adapter.quiet(self.root,'before')
            http.assert_not_awaited()
        self.assertEqual(original,{p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()})

    async def test_new_activity_cannot_replace_an_existing_evidence_file(self):
        (self.root/'quiet_evidence.json').write_text('[]\n')
        with patch('experiments.feasibility.activity.http_body',new_callable=AsyncMock) as http:
            with self.assertRaisesRegex(ValueError,'another activity'):await self.adapter.quiet(self.root,'fresh')
            http.assert_not_awaited()
        self.assertEqual((self.root/'quiet_evidence.json').read_text(),'[]\n')

    async def test_partial_failure_is_retained_without_leaking_into_next_job(self):
        first=self.root/'first';second=self.root/'second';self.owned_session(first,'first',0,43);calls=0
        async def fail_after_one(endpoint,**kwargs):
            nonlocal calls
            calls+=1
            if calls==4:return 200,metric_text(waiting=1)
            return await self.scoped_http(endpoint,**kwargs)
        with patch('experiments.feasibility.activity.http_body',side_effect=fail_after_one):
            with self.assertRaises(RuntimeError):await self.adapter.quiet(first,'before')
        retained=(first/'quiet_evidence.json').read_bytes();self.assertEqual(len(json.loads(retained)),1)
        self.owned_session(second,'second',1,99)
        with patch('experiments.feasibility.activity.http_body',side_effect=self.scoped_http):await self.adapter.quiet(second,'before')
        self.assertEqual((first/'quiet_evidence.json').read_bytes(),retained)
        self.assertEqual({r['barrier_command']['session_nonce'] for r in json.loads((second/'quiet_evidence.json').read_text())},{'second'})

    async def test_output_alias_retains_prior_phases_and_invalid_destinations_fail(self):
        with patch('experiments.feasibility.activity.http_body',side_effect=self.http):
            await self.adapter.quiet(self.root,'before')
            await self.adapter.quiet(self.root/'unused'/Path('..'),'after')
        self.assertEqual(len(json.loads((self.root/'quiet_evidence.json').read_text())),4)
        for label in ('../escape','a/b','a\\b','..',''):
            with self.assertRaises(ValueError):await self.adapter.quiet(self.root,label)
        outside=self.root/'unrelated';outside.mkdir()
        with self.assertRaisesRegex(ValueError,'contain the owned session'):await self.adapter.quiet(outside,'outside')


class WorkerImplementationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.calls=[]
        torch=types.ModuleType('torch');torch.cuda=types.SimpleNamespace(synchronize=lambda:self.calls.append('sync'),
            get_device_properties=lambda device:types.SimpleNamespace(uuid='fixture'),current_device=lambda:0,
            cudart=lambda:types.SimpleNamespace(cudaProfilerStart=lambda:0,cudaProfilerStop=lambda:0))
        fake=types.ModuleType('vllm.v1.worker.gpu_worker');fake.Worker=type('Worker',(),dict(init_device=lambda self:None))
        modules={'torch':torch,'vllm.v1.worker.gpu_worker':fake}
        for name in ('vllm','vllm.v1','vllm.v1.worker'):
            m=types.ModuleType(name);m.__path__=[];modules[name]=m
        with patch.dict('sys.modules',modules):
            spec=importlib.util.spec_from_file_location('fixture_cuda_worker','experiments/tracing/vllm_cuda_worker.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.worker=module.CudaCaptureWorker();self.worker.device=0
        self.env=patch.dict(os.environ,dict(REVISION_SESSION_DIR=str(self.root),REVISION_CLOCK_DOMAIN='host',
            REVISION_SESSION_NONCE='owned',REVISION_GENERATION='1',REVISION_RESET_TOKEN='reset'))
        self.env.start();self.addCleanup(self.env.stop);self.worker.init_device()
    def command(self,token='a'*32):
        (self.root/'barrier_command.json').write_text(json.dumps(dict(token=token,session_nonce='owned',generation=1,clock_domain='host',requested_at_ns=0)))
    def test_ready_record_has_nonce_generation_and_reset_ack(self):
        record=json.loads(next(self.root.glob('worker-*.json')).read_text())
        self.assertEqual(record['reset_token'],'reset');self.assertEqual(record['generation'],1);self.assertEqual(record['session_nonce'],'owned')

    def test_actual_configuration_method_reads_worker_config_without_cuda_sync(self):
        self.worker.vllm_config=types.SimpleNamespace(cache_config=types.SimpleNamespace(enable_prefix_caching=False),
            scheduler_config=types.SimpleNamespace(async_scheduling=False,max_num_seqs=16),
            parallel_config=types.SimpleNamespace(tensor_parallel_size=1,pipeline_parallel_size=1,data_parallel_size=1))
        command=dict(token='a'*32,session_nonce='owned',generation=1,clock_domain='host',requested_at_ns=0)
        (self.root/'configuration_command.json').write_text(json.dumps(command))
        receipt=self.worker.revision_configuration()
        self.assertFalse(receipt['config']['enable_prefix_caching']);self.assertEqual(self.calls,[])
        self.assertEqual(json.loads((self.root/('configuration-'+'a'*32+'.json')).read_text()),receipt)
        with self.assertRaises(ValueError):self.worker.revision_configuration()
    def test_actual_worker_method_persists_sync_and_rejects_replay(self):
        self.command();receipt=self.worker.revision_barrier();self.assertEqual(self.calls,['sync'])
        self.assertEqual(json.loads(next(self.root.glob('barrier-*.json')).read_text()),receipt)
        with self.assertRaises(ValueError):self.worker.revision_barrier()
        self.assertEqual(self.calls,['sync'])
    def test_active_capture_or_path_token_cannot_be_a_quiet_barrier(self):
        self.command();self.worker._revision_capture_active=True
        with self.assertRaises(ValueError):self.worker.revision_barrier()
        self.worker._revision_capture_active=False;self.command('../escape')
        with self.assertRaises(ValueError):self.worker.revision_barrier()
        self.assertEqual(self.calls,[])

    def test_event_worker_rpc_requires_opt_in_and_never_synchronizes_cuda(self):
        from experiments.tracing.event_probe import register_source
        from experiments.tracing.server_events import EventJournal,atomic_json
        from experiments.tracing.live_features import ServingBinding
        from dataclasses import asdict
        import time
        with patch.dict(os.environ,dict(REVISION_ENABLE_EVENTS='0')),self.assertRaises(ValueError):self.worker.revision_event_probe()
        directory=self.root/'scheduler-events';directory.mkdir()
        binding=ServingBinding('owned',1,os.getpid(),'GPU-fixture','model','0','host')
        register_source(directory,EventJournal(binding,time.monotonic_ns))
        atomic_json(directory/'probe_command.json',dict(token='a'*32,binding=asdict(binding),requested_at_ns=time.monotonic_ns()))
        with patch.dict(os.environ,dict(REVISION_ENABLE_EVENTS='1')):self.worker.revision_event_probe()
        self.assertTrue((directory/('snapshot-'+'a'*32+'.json')).exists());self.assertEqual(self.calls,[])
