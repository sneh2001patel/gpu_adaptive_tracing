"""CPU event/probe and fake pinned-scheduler hook checks; no Torch or GPU imports."""
import hashlib,importlib.util,json,os,tempfile,types,unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from revision.tracing.server_events import EventJournal,validate_snapshot,scheduler_wait_bounds
from revision.tracing.live_features import ServingBinding
from revision.scripts.prepare_server_event_pilot import specification

MS=1_000_000
class Clock:
    def __init__(self):self.t=0
    def __call__(self):return self.t

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.binding=ServingBinding('owned',1,43,'GPU-test','model','0','host')
        self.j=EventJournal(self.binding,self.clock)
    def event(self,kind,rid,start,end,status=None):
        self.clock.t=end*MS;self.j.record(kind,rid,start*MS,end*MS,terminal_status=status)
    def snapshot(self,j=None,token='a'*32):
        self.clock.t=300*MS;command=dict(token=token,binding=asdict(self.binding),requested_at_ns=290*MS)
        return (j or self.j).probe(command),command
    def lifecycle(self):
        self.event('engine_admitted','r1',10,20)
        self.event('first_positive_schedule','r1',100,110)
        self.event('scheduler_finished','r1',200,210,'FINISHED_STOPPED')
    def test_complete_history_and_wait_interval_are_not_existing_measured_metric(self):
        self.lifecycle();data,cmd=self.snapshot()
        rows=scheduler_wait_bounds(data,cmd,self.binding,received_at_ns=310*MS,start_ns=50*MS,end_ns=150*MS)
        self.assertEqual(rows['observations'],[dict(request_id='r1',wait_lower_ms=80,wait_upper_ms=100)])
        self.assertIsNone(rows['prefill_service_fraction']);self.assertIn('unsupported',rows['existing_request_wait_p95_mapping'])
    def test_batch_brackets_can_overlap_and_repeated_decode_is_not_duplicate_first_schedule(self):
        self.event('engine_admitted','r1',10,20);self.event('engine_admitted','r2',25,30)
        self.clock.t=110*MS;self.j.scheduled(['r1','r2'],100*MS,110*MS)
        self.clock.t=150*MS;self.j.scheduled(['r1','r2'],140*MS,150*MS)
        data,cmd=self.snapshot();states=validate_snapshot(data,cmd,self.binding,310*MS)
        self.assertEqual(data['attempted'],4);self.assertEqual(len(states),2);self.assertTrue(data['history_complete'])
    def test_nested_other_request_terminal_bracket_is_valid(self):
        self.event('engine_admitted','old',10,20);self.event('engine_admitted','new',25,30)
        self.event('scheduler_finished','old',100,110,'FINISHED_ABORTED')
        self.event('first_positive_schedule','new',90,150)
        data,cmd=self.snapshot();self.assertEqual(len(validate_snapshot(data,cmd,self.binding,310*MS)),2)
    def test_pending_and_aborted_without_schedule_are_never_zero_wait(self):
        self.event('engine_admitted','pending',10,20);self.event('engine_admitted','abort',30,40)
        self.event('scheduler_finished','abort',50,60,'FINISHED_ABORTED')
        data,cmd=self.snapshot();rows=scheduler_wait_bounds(data,cmd,self.binding,received_at_ns=310*MS,start_ns=0,end_ns=250*MS)
        self.assertEqual(rows['observations'],[]);self.assertEqual(rows['still_unscheduled_at_probe_request_ids'],['pending'])
        self.assertEqual(rows['finished_without_schedule_at_probe_request_ids'],['abort'])
    def test_window_boundary_uncertainty_is_separate(self):
        self.lifecycle();data,cmd=self.snapshot()
        rows=scheduler_wait_bounds(data,cmd,self.binding,received_at_ns=310*MS,start_ns=50*MS,end_ns=105*MS)
        self.assertEqual(rows['observations'],[]);self.assertEqual(rows['boundary_ambiguous_request_ids'],['r1'])
    def test_event_or_request_budget_drop_invalidates_history(self):
        for kwargs in (dict(max_events=1),dict(max_requests=1)):
            self.clock.t=0;j=EventJournal(self.binding,self.clock,**kwargs)
            self.clock.t=20*MS;j.record('engine_admitted','a',10*MS,20*MS)
            self.clock.t=40*MS;j.record('engine_admitted','b',30*MS,40*MS)
            data,cmd=self.snapshot(j)
            self.assertFalse(data['history_complete']);self.assertGreater(data['dropped'],0)
            with self.assertRaises(ValueError):validate_snapshot(data,cmd,self.binding,310*MS)
    def test_duplicate_unknown_or_reversed_events_mark_faults(self):
        self.event('first_positive_schedule','unknown',10,20)
        self.event('engine_admitted','r1',30,40);self.event('engine_admitted','r1',50,60)
        self.event('engine_admitted','reverse',80,70)
        data,cmd=self.snapshot();self.assertEqual(data['dropped'],3)
        with self.assertRaises(ValueError):validate_snapshot(data,cmd,self.binding,310*MS)
    def test_missing_sequence_or_foreign_snapshot_rejected(self):
        self.lifecycle();data,cmd=self.snapshot()
        broken=data|dict(events=data['events'][:-1])
        with self.assertRaises(ValueError):validate_snapshot(broken,cmd,self.binding,310*MS)
        for change in (dict(token='b'*32),dict(binding=asdict(self.binding)|dict(generation=2)),dict(source_probe_ns=400*MS)):
            with self.assertRaises(ValueError):validate_snapshot(data|change,cmd,self.binding,310*MS)
    def test_probe_scope_token_reuse_and_budget_are_checked(self):
        data,cmd=self.snapshot()
        with self.assertRaises(ValueError):self.j.probe(cmd)
        with self.assertRaises(ValueError):self.j.probe(cmd|dict(token='../escape'))
        with self.assertRaises(ValueError):self.j.probe(cmd|dict(token='b'*32,binding=asdict(self.binding)|dict(worker_pid=44)))
        for i in range(31):self.j.probe(cmd|dict(token=f'{i:032x}'))
        with self.assertRaises(ValueError):self.j.probe(cmd|dict(token='f'*32))
    def test_future_or_unsupported_window_rejected(self):
        data,cmd=self.snapshot()
        with self.assertRaises(ValueError):scheduler_wait_bounds(data,cmd,self.binding,received_at_ns=310*MS,start_ns=0,end_ns=400*MS)
        with self.assertRaises(ValueError):validate_snapshot(data|dict(semantics='GPU_execution_time'),cmd,self.binding,310*MS)


class SchedulerHookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        class FakeScheduler:
            def __init__(self,*args,**kwargs):self.calls=[]
            def add_request(self,r):self.calls.append('add');return 'add-return'
            def schedule(self):self.calls.append('schedule');return types.SimpleNamespace(num_scheduled_tokens={'r1':1,'r2':0})
            def _free_request(self,r):self.calls.append('free');return 'free-return'
        fake=types.ModuleType('vllm.v1.core.sched.scheduler');fake.Scheduler=FakeScheduler
        modules={'vllm.v1.core.sched.scheduler':fake}
        for name in ('vllm','vllm.v1','vllm.v1.core','vllm.v1.core.sched'):
            mod=types.ModuleType(name);mod.__path__=[];modules[name]=mod
        with patch.dict('sys.modules',modules):
            spec=importlib.util.spec_from_file_location('fixture_event_scheduler','revision/tracing/vllm_event_scheduler.py')
            self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.version=patch.object(self.module,'version',return_value='0.10.2');self.version.start();self.addCleanup(self.version.stop)
        self.module.SCHEDULER_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()  # fake source only
        self.config=types.SimpleNamespace(scheduler_config=types.SimpleNamespace(async_scheduling=False,max_num_seqs=16),
            cache_config=types.SimpleNamespace(enable_prefix_caching=False),
            parallel_config=types.SimpleNamespace(tensor_parallel_size=1,pipeline_parallel_size=1,data_parallel_size=1),
            model_config=types.SimpleNamespace(served_model_name=['model']))
        worker=dict(pid=os.getpid(),device_uuid='GPU-fixture',session_nonce='owned',generation=1,clock_domain='host')
        (self.root/f'worker-{os.getpid()}.json').write_text(json.dumps(worker))
        self.env=patch.dict(os.environ,dict(REVISION_SESSION_DIR=str(self.root),REVISION_SESSION_NONCE='owned',REVISION_GENERATION='1',REVISION_CLOCK_DOMAIN='host'))
        self.env.start();self.addCleanup(self.env.stop)
    def test_actual_subclass_wrappers_forward_results_and_only_first_positive_schedule(self):
        obj=self.module.EventScheduler(vllm_config=self.config);r=types.SimpleNamespace(request_id='r1',status=types.SimpleNamespace(name='FINISHED_STOPPED'))
        self.assertEqual(obj.add_request(r),'add-return');obj.schedule();obj.schedule();self.assertEqual(obj._free_request(r),'free-return')
        self.assertEqual([e['kind'] for e in obj._events.events],['engine_admitted','first_positive_schedule','scheduler_finished'])
        self.assertEqual(obj.calls,['add','schedule','schedule','free'])
        startup=json.loads((self.root/'scheduler-events/startup.json').read_text())
        self.assertEqual(startup['binding'],asdict(obj._events.binding))
        self.assertEqual(startup['worker_record']['pid'],os.getpid())
    def test_source_version_async_and_foreign_worker_fail_before_use(self):
        with patch.object(self.module,'version',return_value='other'),self.assertRaises(RuntimeError):self.module.EventScheduler(vllm_config=self.config)
        self.config.scheduler_config.async_scheduling=True
        with self.assertRaises(ValueError):self.module.EventScheduler(vllm_config=self.config)
        self.config.scheduler_config.async_scheduling=False
        p=next(self.root.glob('worker-*'));d=json.loads(p.read_text());d['pid']=99;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.module.EventScheduler(vllm_config=self.config)
    def test_probe_snapshot_is_serviced_by_hook_with_real_process_clock(self):
        obj=self.module.EventScheduler(vllm_config=self.config)
        import time
        command=dict(token='a'*32,binding=asdict(obj._events.binding),requested_at_ns=time.monotonic_ns())
        path=self.root/'scheduler-events';(path/'probe_command.json').write_text(json.dumps(command))
        obj.add_request(types.SimpleNamespace(request_id='r1'))
        data=json.loads((path/('snapshot-'+'a'*32+'.json')).read_text())
        self.assertEqual(len(validate_snapshot(data,command,obj._events.binding,time.monotonic_ns())),1)


class PilotSpecificationTests(unittest.TestCase):
    def test_prospective_rules_are_bounded_and_not_scientific_thresholds(self):
        corpus=Path('revision/hardware/l4_20261028/capacity_001/corpus.json').read_bytes()
        source=Path('revision/protocol/sources/vllm_0_10_2/events/SOURCE_MANIFEST.json').read_bytes()
        spec=specification(corpus,source)
        self.assertFalse(spec['launch_supported']);self.assertFalse(spec['reference_export_enabled']);self.assertFalse(spec['protocol_frozen'])
        self.assertTrue(all(v is None for v in spec['scientific_limits'].values()))
        self.assertEqual(spec['engineering_guards']['min_successful_completions_for_p95_review'],20)
        self.assertGreater(spec['budget']['max_client_inflight'],spec['budget']['server_max_num_seqs'])
        for case in spec['cases']:
            self.assertLessEqual(case['duration_s'],spec['budget']['max_case_horizon_s'])
            if 'phases' in case:self.assertEqual(sum(p[1] for p in case['phases']),case['duration_s'])
    def test_corpus_tamper_rejected(self):
        corpus=json.loads(Path('revision/hardware/l4_20261028/capacity_001/corpus.json').read_text());corpus['prompts'][0]['prompt']='changed'
        source=Path('revision/protocol/sources/vllm_0_10_2/events/SOURCE_MANIFEST.json').read_bytes()
        with self.assertRaises(ValueError):specification(json.dumps(corpus).encode(),source)


class ParentProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_file_probe_binds_current_source_and_persists_ack(self):
        from revision.tracing.server_events import collect_snapshot,atomic_json
        from revision.tracing.timing import MonotonicClock
        clock=MonotonicClock();binding=ServingBinding('owned',1,43,'GPU-test','model','0',clock.domain)
        journal=EventJournal(binding,clock.now_ns)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            async def trigger():
                data=json.loads((root/'probe_command.json').read_text())
                atomic_json(root/('snapshot-'+data['token']+'.json'),journal.probe(data))
            receipt=await collect_snapshot(clock,binding,root,trigger)
            self.assertEqual(receipt['data']['attempted'],0)
            self.assertLessEqual(receipt['command']['requested_at_ns'],receipt['data']['source_probe_ns'])
            self.assertLessEqual(receipt['data']['source_probe_ns'],receipt['received_at_ns'])
    async def test_missing_ack_timeout_cancels_trigger_without_success(self):
        import asyncio
        from revision.tracing.server_events import collect_snapshot
        from revision.tracing.timing import MonotonicClock
        clock=MonotonicClock();binding=ServingBinding('owned',1,43,'GPU-test','model','0',clock.domain)
        cancelled=[]
        async def trigger():
            try:await asyncio.Future()
            finally:cancelled.append(True)
        with tempfile.TemporaryDirectory() as root,self.assertRaises(TimeoutError):
            await collect_snapshot(clock,binding,root,trigger,timeout_s=.02)
        self.assertTrue(cancelled)
