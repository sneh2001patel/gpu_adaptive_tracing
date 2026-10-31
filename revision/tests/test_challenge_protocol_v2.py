"""CPU-only revised plan/gates; original failed data is development input only."""
import asyncio,copy,hashlib,json,math,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from revision.feasibility import challenge_protocol as v1,challenge_protocol_v2 as v2
from revision.feasibility.challenge_runner import run_campaign
from revision.tracing.arrival_schedule import ArrivalSchedule,canonical
from revision.tracing.live_features import ServingBinding,MetricReceipt
from revision.tracing.timing import MonotonicClock
from revision.scripts.demo_live_feasibility import metric_text

PACKET=Path('revision/examples/event_challenges_v2/prepared_001')
OLD=Path('revision/examples/event_challenges/prepared_001')
BASE=Path('revision/hardware/l4_20261028')


def work(schedule,start=v2.NS):
    return [dict(request_id=r.request_id,admitted_at_ns=start+r.offset_ns,completed_at_ns=start+r.offset_ns+1,
        http_status=200,error=None,prompt_tokens=1072,output_tokens=32) for r in schedule.requests]


class CompileTests(unittest.TestCase):
    def test_ladder_has_84_requests_and_never_8rps(self):
        s=v2.make_schedule('rate_ladder','prompt','model')
        self.assertEqual(len(s.requests),84);self.assertEqual(v2.RATES,(.5,1,2,3,4))
        self.assertTrue(all(r.request_id.startswith('v2-') for r in s.requests))
    def test_three_rps_has_exact_counts_without_rounding_extra_request(self):
        s=v2.make_schedule('rate_ladder','prompt','model')
        rows=[r for r in s.requests if 24*v2.NS<=r.offset_ns<32*v2.NS]
        self.assertEqual(len(rows),24)
        self.assertEqual([r.offset_ns-24*v2.NS for r in rows[:4]],[0,333333333,666666666,1000000000])
        self.assertEqual(rows[-1].offset_ns,24*v2.NS+(23*v2.NS)//3)
        s=v2.make_schedule('pressure_then_removal','prompt','model',3)
        self.assertEqual(len(s.requests),95)
    def test_all_phase_counts_and_boundaries_remain_half_open(self):
        for case in v2.CASES:
            for rate in ((None,) if case=='rate_ladder' else v2.RATES):
                s=v2.make_schedule(case,'prompt','model',rate)
                for _,a,b,r in v2.phases(case,rate):
                    self.assertEqual(sum(a*v2.NS<=x.offset_ns<b*v2.NS for x in s.requests),math.ceil((b-a)*r))
                self.assertLessEqual(len(s.requests)+1,146)
    def test_boolean_unknown_and_old_ceiling_rates_are_rejected(self):
        for r in (True,False,8,5,None):
            with self.assertRaises(ValueError):v2.make_schedule('pressure_then_removal','prompt','model',r)
    def test_packet_has_fixed_controls_lower_total_budget_and_development_scope(self):
        plan,bank=v2.load_prepared(PACKET);parent,_=v1.load_prepared(OLD)
        self.assertEqual(len(bank),16);self.assertEqual(plan['budgets']['max_total_requests_including_warmups'],1932)
        for key,value in parent['budgets'].items():
            if key!='max_total_requests_including_warmups':self.assertEqual(plan['budgets'][key],value)
        self.assertEqual(plan['common'],parent['common']);self.assertEqual(plan['selection'],parent['selection'])
        self.assertEqual(plan['jobs'],parent['jobs']);self.assertFalse(plan['development_basis']['retrospective_eligibility_repair'])
        self.assertFalse(plan['development_basis']['pressure_or_complete_delivery_guaranteed'])
        self.assertTrue(all(j['executed'] is False for j in plan['jobs']))
    def test_v1_and_v2_packet_loaders_reject_each_others_inputs(self):
        with self.assertRaises(ValueError):v1.load_prepared(PACKET)
        with self.assertRaises(ValueError):v2.load_prepared(OLD)
    def test_packet_tamper_cannot_relax_limits_even_with_updated_local_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for p in PACKET.iterdir():
                if p.is_file():(root/p.name).write_bytes(p.read_bytes())
            plan=json.loads((root/'PLAN.json').read_text());plan['budgets']['max_client_inflight']=64
            (root/'PLAN.json').write_text(json.dumps(plan))
            manifest=json.loads((root/'artifact_manifest.json').read_text());manifest['files']['PLAN.json']=hashlib.sha256((root/'PLAN.json').read_bytes()).hexdigest()
            (root/'artifact_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):v2.load_prepared(root)
    def test_relabeling_original_failed_inputs_is_rejected(self):
        raws={k:(PACKET/(k+'.json')).read_bytes() for k in v2.INPUTS}
        d=json.loads(raws['development_result_input']);d['status']='engineering_collection_complete'
        raws['development_result_input']=json.dumps(d).encode()
        with self.assertRaises(ValueError):v2.compile_inputs(raws)
    def test_original_failed_work_and_original_offered_bytes_still_fail_v1(self):
        _,bank=v1.load_prepared(OLD);playback=json.loads((BASE/'challenges_001/rate_ladder-b0-off/playback.json').read_text())
        rows=[json.loads(line) for line in (BASE/'challenges_001/rate_ladder-b0-off/requests/receipts.jsonl').read_text().splitlines()]
        rows=[{k:r[k] for k in ('request_id','admitted_at_ns','completed_at_ns','http_status','error','prompt_tokens','output_tokens')}
            for r in rows if r['request_id']!='challenge-warmup']
        binding=ServingBinding(**json.loads((BASE/'challenges_001/rate_ladder-b0-off/binding.json').read_text()))
        result=v1.select_pressure([],binding,case_start_ns=playback['start_ns'],request_rows=rows,schedule=bank['rate_ladder'],job=v1.job_design()[0])
        self.assertEqual(result['status'],'incomplete_work');self.assertIsNone(result['selected_rate_rps'])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.binding=ServingBinding('fixture',0,43,'GPU-fixture','model','0','host');self.schedule=v2.make_schedule('rate_ladder','prompt','model')
        self.rows=work(self.schedule);self.job=v1.job_design()[0]
    def receipts(self,positive=()):
        rows=[]
        for i in range(80):
            t=v2.NS+i*v2.NS//2+1
            rows.append(MetricReceipt(str(i),self.binding,t,t+1,200,metric_text(model='model',waiting=int(i//16 in positive)),None))
        return rows
    def select(self,receipts=None,rows=None,schedule=None,job=None):
        return v2.select_pressure(self.receipts() if receipts is None else receipts,self.binding,case_start_ns=v2.NS,
            request_rows=self.rows if rows is None else rows,schedule=self.schedule if schedule is None else schedule,job=self.job if job is None else job)
    def test_lowest_qualifying_rate_can_be_new_3rps(self):
        r=self.select(self.receipts((3,4)));self.assertEqual(r['selected_rate_rps'],3)
        self.assertEqual(r['status'],'engineering_candidate')
    def test_highest_qualifying_rate_can_be_4rps_only_with_fresh_complete_evidence(self):
        self.assertEqual(self.select(self.receipts((4,)))['selected_rate_rps'],4)
    def test_zero_queue_and_single_spike_never_select(self):
        self.assertEqual(self.select()['status'],'no_sampled_pressure_candidate')
        rows=self.receipts();rows[65]=self.receipts((4,))[65]
        self.assertEqual(self.select(rows)['status'],'no_sampled_pressure_candidate')
    def test_any_missing_or_late_work_still_invalidates_whole_ladder(self):
        self.assertEqual(self.select(rows=self.rows[:-1])['status'],'incomplete_work')
        rows=copy.deepcopy(self.rows);rows[0]['admitted_at_ns']+=51_000_000
        self.assertEqual(self.select(rows=rows)['status'],'incomplete_work')
    def test_incomplete_metrics_still_prevent_selection_despite_positive_queues(self):
        rows=self.receipts((3,4));rows.pop(15)
        self.assertEqual(self.select(rows)['status'],'incomplete_evidence')
    def test_foreign_source_duplicate_and_on_role_are_rejected(self):
        rows=self.receipts((4,))
        for bad in ([rows[0],*rows],[replace(rows[0],binding=replace(self.binding,generation=1)),*rows[1:]]):
            with self.assertRaises(ValueError):self.select(bad)
        with self.assertRaises(ValueError):self.select(job=self.job|dict(event_instrumentation=True))
    def test_old_and_new_ladders_cannot_be_cross_selected(self):
        old=v1.make_schedule('rate_ladder','prompt','model')
        with self.assertRaises(ValueError):self.select(schedule=old,rows=work(old))
        with self.assertRaises(ValueError):v1.select_pressure([],self.binding,case_start_ns=v2.NS,request_rows=self.rows,schedule=self.schedule,job=self.job)


class CampaignTests(unittest.IsolatedAsyncioTestCase):
    async def campaign(self,selection):
        calls=[]
        async def episode(target,clock,job,entry,schedule,output,budget,generation,**kwargs):
            self.assertIs(kwargs['selection_fn'],v2.select_pressure)
            budget.reserve(job['job_id'],len(schedule.requests)+1);budget.charge(job['job_id'])
            calls.append((job['job_id'],entry['rate_rps'],len(schedule.requests)))
            result=dict(job_id=job['job_id'],schedule_sha256=schedule.file_sha256,case_start_ns=v2.NS,requests=work(schedule))
            if job['job_id']=='rate_ladder-b0-off':result['selection']=selection
            return result
        with tempfile.TemporaryDirectory() as tmp,patch('revision.feasibility.challenge_runner.run_episode',side_effect=episode):
            root=Path(tmp)/'campaign';target=type('SyntheticTarget',(),dict(live=False))()
            success=await run_campaign(target,MonotonicClock(),PACKET,root,loader=v2.load_prepared,selection_fn=v2.select_pressure)
            return success,calls,json.loads((root/'RESULT.json').read_text()),json.loads((root/'request_budget.json').read_text()),json.loads((root/'jobs.json').read_text())
    async def test_no_candidate_runs_four_ladders_and_skips_twelve_jobs(self):
        ok,calls,result,budget,jobs=await self.campaign(dict(status='no_sampled_pressure_candidate',selected_rate_rps=None))
        self.assertTrue(ok);self.assertEqual(len(calls),4);self.assertEqual(sum(j['status']=='skipped_no_eligible_rate' for j in jobs),12)
        self.assertEqual(budget['max_total'],1932);self.assertEqual(result['protocol_version'],v2.VERSION)
    async def test_v2_candidate_uses_exact_versioned_bank_without_exceeding_total_reservation(self):
        ok,calls,result,budget,jobs=await self.campaign(dict(status='engineering_candidate',selected_rate_rps=3))
        self.assertTrue(ok);self.assertEqual(len(calls),16);self.assertTrue(all(r==3 for _,r,_ in calls[4:]))
        self.assertEqual(sum(budget['reserved'].values()),1552)
        self.assertFalse(result['study_ready']);self.assertFalse(result['protocol_frozen'])


if __name__=='__main__':unittest.main()
