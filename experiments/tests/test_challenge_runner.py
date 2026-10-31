"""CPU transports and concurrent episodes; no serving/GPU processes launched."""
import asyncio,copy,json,tempfile,time,types,unittest,uuid
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch
from experiments.feasibility.challenge_runner import (CampaignBudget,EpisodeOptions,run_episode,run_campaign,
    compare_observers,RawChallengeRequests,EpisodeEvidence,NS)
from experiments.tracing.arrival_schedule import ArrivalSchedule,canonical
from experiments.tracing.live_features import ServingBinding,MetricReceipt
from experiments.tracing.server_events import EventJournal
from experiments.tracing.timing import MonotonicClock
from experiments.tracing.worker_configuration import configuration_receipt,validate_configuration
from experiments.scripts.demo_live_feasibility import metric_text

CONFIG=dict(enable_prefix_caching=False,async_scheduling=False,max_num_seqs=16,tensor_parallel_size=1,pipeline_parallel_size=1,data_parallel_size=1)
PACKET=Path('experiments/examples/event_challenges/prepared_001')


def fixture_schedule(count=4):
    return ArrivalSchedule.from_bytes(canonical(dict(version='offered_arrivals_v1',duration_ns=120_000_000,
        requests=[dict(request_id='r'+str(i),offset_ns=i*30_000_000,payload=dict(model='fixture-model',prompt='CPU fixture',
            max_tokens=32,stream=False,temperature=0,ignore_eos=True)) for i in range(count)])))


class FakeTarget:
    live=False
    def __init__(self,clock):
        self.clock=clock;self.delay=.004;self.probe_delay=0;self.active=set();self.closed=False;self.bad_id=False
        self.bad_config=False;self.bad_metric=False;self.quiets=[];self.close_ok=True;self.probes=0
    async def open(self,job,output,generation):
        self.binding=ServingBinding(uuid.uuid4().hex,generation,43,'GPU-fixture','fixture-model','0',self.clock.domain)
        self.journal=EventJournal(self.binding,self.clock.now_ns);self.job=job
        command=dict(token=uuid.uuid4().hex,session_nonce=self.binding.session_nonce,generation=generation,clock_domain=self.clock.domain,requested_at_ns=self.clock.now_ns())
        config=CONFIG|dict(enable_prefix_caching=self.bad_config)
        receipt=configuration_receipt(command,pid=43,device_uuid='GPU-fixture',session_nonce=self.binding.session_nonce,
            generation=generation,clock_domain=self.clock.domain,capture_active=False,config=config,now_ns=self.clock.now_ns)
        validate_configuration(receipt,command,self.binding,self.clock.now_ns())
        return self.binding
    async def complete(self,payload,timeout_s):
        rid=payload['request_id'];engine='cmpl-'+rid+'-0';self.active.add(rid);terminal='FINISHED_LENGTH_CAPPED'
        began=self.clock.now_ns();self.journal.record('engine_admitted',engine,began,self.clock.now_ns())
        began=self.clock.now_ns();self.journal.scheduled([engine],began,self.clock.now_ns())
        try:
            await asyncio.sleep(.001 if rid=='challenge-warmup' else self.delay)
            return 200,canonical(dict(id='wrong' if self.bad_id and rid!='challenge-warmup' else 'cmpl-'+rid,
                model=payload['model'],usage=dict(prompt_tokens=1072,completion_tokens=32,total_tokens=1104),choices=[dict(finish_reason='length')]))
        except asyncio.CancelledError:terminal='FINISHED_ABORTED';raise
        finally:
            began=self.clock.now_ns();self.journal.record('scheduler_finished',engine,began,self.clock.now_ns(),terminal_status=terminal)
            self.active.remove(rid)
    async def metric(self,sample_id):
        if self.bad_metric:raise OSError('fixture metric unavailable')
        start=self.clock.now_ns();return MetricReceipt(sample_id,self.binding,start,self.clock.now_ns(),200,metric_text(model='fixture-model'),None)
    async def probe(self):
        self.probes+=1
        if self.probes>1:await asyncio.sleep(self.probe_delay)
        command=dict(token=uuid.uuid4().hex,binding=asdict(self.binding),requested_at_ns=self.clock.now_ns())
        data=self.journal.probe(command)
        return dict(command=command,data=data,received_at_ns=self.clock.now_ns())
    async def quiet(self,label):self.quiets.append(label)
    async def close(self):self.closed=True;return dict(confirmed_absent=self.close_ok and not self.active)


class EpisodeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=MonotonicClock();self.target=FakeTarget(self.clock);self.budget=CampaignBudget(self.root)
        self.job=dict(job_id='CPU-fixture',event_instrumentation=True,prefix_caching=False,evidence_withheld_offsets_ns=[40_000_000,80_000_000])
        self.entry=dict(schedule_id='CPU-fixture',event_probe_offsets_ns=[40_000_000,80_000_000,120_000_000])
        self.options=EpisodeOptions(window_s=.04,grace_s=.02,drain_s=.05,timeout_s=.2,metric_interval_s=.02,max_inflight=2,max_lateness_s=.05,tick_s=.001)
    async def run_one(self):
        return await run_episode(self.target,self.clock,self.job,self.entry,fixture_schedule(),self.root/'episode',self.budget,0,options=self.options)
    async def test_complete_event_episode_preserves_warmup_source_ids_and_mask(self):
        result=await self.run_one()
        self.assertTrue(self.target.closed);self.assertFalse(self.target.active)
        self.assertEqual(self.target.quiets,['before','after']);self.assertEqual(self.budget.counts['CPU-fixture'],5)
        self.assertEqual(len(self.target.journal.events),15);self.assertEqual(self.target.probes,5)
        self.assertEqual(len(result['requests']),4);self.assertEqual(len(result['consumer_windows']),3)
        self.assertEqual(result['consumer_windows'][1]['reason'],'deliberately_withheld_consumer_event_evidence')
        self.assertTrue(json.loads((self.root/'episode/RESULT.json').read_text())['passed'])
    async def test_off_role_uses_no_event_rpcs_and_keeps_metrics(self):
        self.job.update(event_instrumentation=False,evidence_withheld_offsets_ns=None)
        result=await self.run_one();self.assertEqual(self.target.probes,0);self.assertTrue(result['metric_receipts'])
        self.assertTrue(all(w['status']=='unresolved' for w in result['consumer_windows']))
    async def test_mismatched_response_fails_work_and_closes_owner(self):
        self.target.bad_id=True
        with self.assertRaisesRegex(RuntimeError,'Incomplete offered work'):await self.run_one()
        self.assertTrue(self.target.closed);self.assertFalse(self.target.active)
        self.assertFalse(json.loads((self.root/'episode/RESULT.json').read_text())['passed'])
    async def test_configuration_mismatch_stops_before_warmup(self):
        self.target.bad_config=True
        with self.assertRaises(ValueError):await self.run_one()
        self.assertTrue(self.target.closed);self.assertEqual(self.budget.counts['CPU-fixture'],0)
    async def test_cancellation_awaits_requests_and_closes_owned_target(self):
        self.target.delay=1
        task=asyncio.create_task(self.run_one())
        while 'r0' not in self.target.active:await asyncio.sleep(.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(self.target.closed);self.assertFalse(self.target.active)
        data=json.loads((self.root/'episode/playback.json').read_text());self.assertEqual(data['live_request_tasks'],0)
    async def test_drain_censoring_and_capacity_skips_do_not_pass(self):
        self.target.delay=1
        with self.assertRaisesRegex(RuntimeError,'Incomplete offered work'):await self.run_one()
        data=json.loads((self.root/'episode/playback.json').read_text())
        self.assertGreater(data['counts']['censored'],0);self.assertGreater(data['counts']['skipped_capacity'],0)
        self.assertFalse(self.target.active);self.assertTrue(self.target.closed)
    async def test_slow_probe_does_not_silently_shift_next_probe(self):
        self.target.probe_delay=.15
        with self.assertRaisesRegex(RuntimeError,'Prior event probe'):await self.run_one()
        self.assertTrue(self.target.closed);self.assertFalse(self.target.active)
    async def test_missing_metrics_fail_eligibility_and_cleanup(self):
        self.target.bad_metric=True
        with self.assertRaisesRegex(RuntimeError,'Incomplete metric sampling'):await self.run_one()
        self.assertTrue(self.target.closed)
    async def test_unconfirmed_cleanup_fails_even_after_successful_work(self):
        self.target.close_ok=False
        with self.assertRaisesRegex(RuntimeError,'Owned cleanup not confirmed'):await self.run_one()
        self.assertFalse(json.loads((self.root/'episode/RESULT.json').read_text())['passed'])
    async def test_scaled_options_cannot_launch_live_target(self):
        self.target.live=True
        with self.assertRaisesRegex(ValueError,'exact prepared'):await self.run_one()
        self.assertFalse((self.root/'episode').exists())


class BudgetAndReviewTests(unittest.TestCase):
    def test_reservations_and_attempt_charges_are_never_refunded(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget=CampaignBudget(tmp,max_total=3,max_session=2);budget.reserve('j',2)
            budget.charge('j');budget.charge('j')
            with self.assertRaises(ValueError):budget.charge('j')
            with self.assertRaises(ValueError):budget.reserve('j',1)
            with self.assertRaises(ValueError):budget.reserve('other',2)
            self.assertEqual(budget.counts['j'],2)
    def results(self):
        data=fixture_schedule().as_dict();data['duration_ns']=20*NS
        data['requests']=[data['requests'][0]|dict(request_id=str(i),offset_ns=i*100_000_000) for i in range(25)]
        schedule=ArrivalSchedule.from_bytes(canonical(data))
        result=dict(schedule_sha256=schedule.file_sha256,case_start_ns=NS,
            requests=[dict(request_id=r.request_id,admitted_at_ns=NS+r.offset_ns,completed_at_ns=NS+r.offset_ns+10_000_000,
                http_status=200,error=None,prompt_tokens=1072,output_tokens=32) for r in schedule.requests])
        return schedule,result,copy.deepcopy(result)
    def test_matched_nearest_rank_ratio_and_low_sample_window(self):
        schedule,off,on=self.results()
        for r in on['requests']:r['completed_at_ns']+=10_000_000
        review=compare_observers(schedule,off,on)
        self.assertEqual(review['windows'][0]['symmetric_ratio'],2);self.assertTrue(review['windows'][0]['review_flag'])
        self.assertIsNone(review['windows'][1]['review_flag']);self.assertFalse(review['equivalence_established'])
    def test_bad_ids_tokens_or_admission_make_pair_ineligible(self):
        for kind in ('id','tokens','late','hash'):
            schedule,off,on=self.results()
            if kind=='id':on['requests'].pop()
            elif kind=='tokens':on['requests'][0]['output_tokens']=31
            elif kind=='late':on['requests'][0]['admitted_at_ns']+=60_000_000
            else:on['schedule_sha256']='f'*64
            self.assertEqual(compare_observers(schedule,off,on)['status'],'ineligible')
    def test_zero_denominator_never_becomes_unflagged_overhead(self):
        schedule,off,on=self.results()
        for r in off['requests']:r['completed_at_ns']=r['admitted_at_ns']
        review=compare_observers(schedule,off,on)
        self.assertEqual(review['windows'][0]['reason'],'nonpositive_denominator');self.assertIsNone(review['windows'][0]['review_flag'])


class CampaignTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_pressure_runs_four_ladders_then_skips_twelve_dependents(self):
        clock=MonotonicClock();target=FakeTarget(clock);calls=[]
        async def episode(target,clock,job,entry,schedule,*args,**kwargs):
            calls.append(job['job_id']);result=dict(job_id=job['job_id'],schedule_sha256=schedule.file_sha256,requests=[],case_start_ns=NS)
            if job['job_id']=='rate_ladder-b0-off':result['selection']=dict(status='no_sampled_pressure_candidate',selected_rate_rps=None)
            return result
        with tempfile.TemporaryDirectory() as tmp,patch('experiments.feasibility.challenge_runner.run_episode',side_effect=episode):
            root=Path(tmp)/'campaign';self.assertTrue(await run_campaign(target,clock,PACKET,root))
            self.assertEqual(len(calls),4)
            self.assertEqual(sum(j['status']=='skipped_no_eligible_rate' for j in json.loads((root/'jobs.json').read_text())),12)
    async def test_failed_episode_aborts_campaign_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp,patch('experiments.feasibility.challenge_runner.run_episode',side_effect=RuntimeError('fixture failure')) as call:
            root=Path(tmp)/'campaign';self.assertFalse(await run_campaign(FakeTarget(MonotonicClock()),MonotonicClock(),PACKET,root))
            self.assertEqual(call.await_count,1);self.assertEqual(json.loads((root/'RESULT.json').read_text())['completed_jobs'],0)


class ConfigurationTests(unittest.TestCase):
    def test_configuration_route_exposes_only_the_fixed_rpc(self):
        from experiments.tracing.worker_configuration import install_configuration_route
        calls=[]
        async def rpc(*args,**kwargs):calls.append((args,kwargs))
        api=types.SimpleNamespace(router=types.SimpleNamespace(post=lambda path:lambda fn:fn),Request=object,
            Response=lambda **kw:kw,engine_client=lambda req:types.SimpleNamespace(collective_rpc=rpc))
        asyncio.run(install_configuration_route(api)(object()))
        self.assertEqual(calls,[(('revision_configuration',),dict(timeout=10))])
    def test_same_host_configuration_requires_exact_boolean_settings_and_binding(self):
        binding=ServingBinding('s',1,43,'GPU-fixture','model','0','host')
        command=dict(token='a'*32,session_nonce='s',generation=1,clock_domain='host',requested_at_ns=1)
        receipt=configuration_receipt(command,pid=43,device_uuid='GPU-fixture',session_nonce='s',generation=1,clock_domain='host',
            capture_active=False,config=CONFIG,now_ns=lambda:2)
        validate_configuration(receipt,command,binding,3)
        for change in (dict(enable_prefix_caching=0),dict(enable_prefix_caching=True),dict(tensor_parallel_size=True)):
            with self.assertRaises(ValueError):validate_configuration(receipt|dict(config=CONFIG|change),command,binding,3)
        with self.assertRaises(ValueError):validate_configuration(receipt,command,replace(binding,generation=2),3)
    def test_configuration_is_not_a_CUDA_barrier_and_excludes_active_capture(self):
        kwargs=dict(pid=43,device_uuid='GPU-fixture',session_nonce='s',generation=1,clock_domain='host',config=CONFIG,now_ns=lambda:2)
        command=dict(token='a'*32,session_nonce='s',generation=1,clock_domain='host',requested_at_ns=1)
        with self.assertRaises(ValueError):configuration_receipt(command,capture_active=True,**kwargs)
        self.assertEqual(configuration_receipt(command,capture_active=False,**kwargs)['scope'],'actual_worker_configuration_not_CUDA_barrier')


if __name__=='__main__':unittest.main()
