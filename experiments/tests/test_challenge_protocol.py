"""Synthetic CPU checks: exact phases/budgets, scoped selection and receipt gaps."""
import copy,hashlib,json,math,tempfile,unittest
from dataclasses import asdict,replace
from pathlib import Path
from experiments.feasibility.challenge_protocol import NS,RATES,make_schedule,phases,wire_payload,materialize,load_prepared,select_pressure,event_window
from experiments.tracing.arrival_schedule import ArrivalSchedule,canonical
from experiments.tracing.live_features import ServingBinding,MetricReceipt
from experiments.tracing.server_events import EventJournal
from experiments.scripts.demo_live_feasibility import metric_text

BASE=Path('experiments/hardware/l4_20261028')
def inputs():
    return dict(corpus_raw=(BASE/'capacity_001/corpus.json').read_bytes(),
        spec_raw=Path('experiments/examples/server_events/prospective_001/SPECIFICATION.json').read_bytes(),
        commission_raw=(BASE/'events_001/RESULT.json').read_bytes(),validation_raw=(BASE/'EVENTS_VALIDATION.json').read_bytes())


class PlanTests(unittest.TestCase):
    def test_phase_counts_boundaries_and_warmup_budgets(self):
        self.assertEqual(len(make_schedule('rate_ladder','prompt','model').requests),124)
        for case in ('pressure_then_removal','lull_then_recurrence','unresolved_source_gap_control'):
            for rate in RATES:
                schedule=make_schedule(case,'prompt','model',rate)
                self.assertLessEqual(len(schedule.requests)+1,512)
                for name,start,end,rps in phases(case,rate):
                    offered=[r for r in schedule.requests if start*NS<=r.offset_ns<end*NS]
                    self.assertEqual(len(offered),math.ceil((end-start)*rps))
        self.assertEqual(len(make_schedule('lull_then_recurrence','prompt','model',8).requests),285)
    def test_wire_ids_are_deterministic_and_do_not_mutate_legacy_payload(self):
        offered=make_schedule('rate_ladder','prompt','model').requests[0]
        self.assertEqual(wire_payload(offered)['request_id'],offered.request_id)
        self.assertEqual(wire_payload(offered)['n'],1);self.assertNotIn('request_id',offered.payload)
    def test_materialized_plan_exact_bank_hashes_order_and_independent_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'packet';plan=materialize(root,**inputs());loaded,bank=load_prepared(root)
            self.assertEqual(loaded,plan);self.assertEqual(len(bank),16)
            self.assertEqual(plan['budgets']['max_total_requests_including_warmups'],3612)
            for case in ('rate_ladder','pressure_then_removal','lull_then_recurrence'):
                jobs=[j for j in plan['jobs'] if j['case_id']==case]
                self.assertEqual([j['role'] for j in jobs],['off','on','on','off'])
                self.assertTrue(all(j['prefix_caching'] is False for j in jobs))
            self.assertTrue(all(j['event_instrumentation'] for j in plan['jobs'] if j['case_id']=='unresolved_source_gap_control'))
            self.assertFalse(plan['launch_supported']);self.assertFalse(plan['reference_export_enabled'])
    def test_tampered_corpus_or_failed_commission_cannot_prepare(self):
        for key in ('corpus_raw','commission_raw'):
            kw=inputs();data=json.loads(kw[key])
            if key=='corpus_raw':data['prompts'][0]['prompt']='tampered'
            else:data['commission_passed']=False
            kw[key]=json.dumps(data).encode()
            with tempfile.TemporaryDirectory() as temp,self.assertRaises(ValueError):materialize(Path(temp)/'packet',**kw)
    def test_schedule_tamper_and_unsafe_paths_fail_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'packet';materialize(root,**inputs())
            path=root/'rate_ladder.json';path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(ValueError):load_prepared(root)
            manifest=json.loads((root/'artifact_manifest.json').read_text());manifest['files']['../escape']='a'*64
            (root/'artifact_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):load_prepared(root)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.binding=ServingBinding('fixture',0,43,'GPU-test','fixture-model','0','fixture-clock')
        self.schedule=make_schedule('rate_ladder','prompt','fixture-model');self.start=NS
        self.job=dict(job_id='rate_ladder-b0-off',event_instrumentation=False,prefix_caching=False)
        self.work=[dict(request_id=r.request_id,admitted_at_ns=self.start+r.offset_ns,
            completed_at_ns=self.start+r.offset_ns+1,http_status=200,error=None,prompt_tokens=1072,output_tokens=32) for r in self.schedule.requests]
    def receipts(self,positive_levels=()):
        result=[]
        for i in range(80):
            t=self.start+i*NS//2+1
            raw=metric_text(model='fixture-model',waiting=1 if i//16 in positive_levels else 0)
            result.append(MetricReceipt(str(i),self.binding,t,t+1,200,raw,None))
        return result
    def select(self,receipts=None,work=None,job=None):
        return select_pressure(self.receipts() if receipts is None else receipts,self.binding,case_start_ns=self.start,
            request_rows=self.work if work is None else work,schedule=self.schedule,job=self.job if job is None else job)
    def test_selects_lowest_qualifying_level_without_classifier(self):
        result=self.select(self.receipts((2,4)))
        self.assertEqual(result['status'],'engineering_candidate');self.assertEqual(result['selected_rate_rps'],2)
    def test_all_zero_and_isolated_spikes_do_not_select(self):
        self.assertEqual(self.select()['status'],'no_sampled_pressure_candidate')
        rows=self.receipts();rows[33]=self.receipts((2,))[33]
        self.assertEqual(self.select(rows)['status'],'no_sampled_pressure_candidate')
    def test_gap_or_missing_http_evidence_prevents_selection(self):
        rows=self.receipts((2,));rows.pop(60)
        self.assertEqual(self.select(rows)['status'],'incomplete_evidence')
        rows=self.receipts((2,));rows[10]=replace(rows[10],http_status=503,raw=None,error='http_503')
        self.assertEqual(self.select(rows)['status'],'incomplete_evidence')
    def test_skips_errors_token_mismatch_and_lateness_prevent_selection(self):
        self.assertEqual(self.select(work=self.work[:-1])['status'],'incomplete_work')
        for change in (dict(error='timeout'),dict(output_tokens=31),dict(admitted_at_ns=self.start+51_000_000)):
            work=copy.deepcopy(self.work);work[0].update(change)
            self.assertEqual(self.select(work=work)['status'],'incomplete_work')
    def test_foreign_duplicate_reverse_and_on_role_are_rejected(self):
        rows=self.receipts()
        for bad in ([replace(rows[0],binding=replace(self.binding,generation=1)),*rows[1:]],[rows[0],*rows],list(reversed(rows))):
            with self.assertRaises(ValueError):self.select(bad)
        with self.assertRaises(ValueError):self.select(job=self.job|dict(event_instrumentation=True))
    def test_altered_ladder_is_rejected(self):
        data=self.schedule.as_dict();data['requests'][0]['offset_ns']=1
        self.schedule=ArrivalSchedule.from_bytes(canonical(data))
        with self.assertRaises(ValueError):self.select()


class EventWindowTests(unittest.TestCase):
    def setUp(self):
        self.binding=ServingBinding('fixture',0,43,'GPU-test','model','0','host')
        journal=EventJournal(self.binding,lambda:0);journal.now_ns=lambda:60*NS
        command=dict(token='a'*32,binding=asdict(self.binding),requested_at_ns=59*NS)
        self.receipt=dict(command=command,data=journal.probe(command),received_at_ns=61*NS)
    def gate(self,start,end,**kwargs):
        return event_window(self.receipt,self.binding,start_ns=start*NS,end_ns=end*NS,decision_ns=62*NS,**kwargs)
    def test_withheld_windows_are_unresolved_without_changing_raw_receipt(self):
        original=canonical(self.receipt)
        for start,end in ((10,20),(9,11),(30,40)):
            result=self.gate(start,end,withheld_interval=(10*NS,40*NS))
            self.assertEqual(result['status'],'unresolved');self.assertIsNone(result['bounds']);self.assertIsNone(result['diagnosis'])
        self.assertEqual(canonical(self.receipt),original)
    def test_touching_boundaries_do_not_withhold_unrelated_windows(self):
        for start,end in ((0,10),(40,50)):
            self.assertEqual(self.gate(start,end,withheld_interval=(10*NS,40*NS))['status'],'bounds_available')
    def test_future_missing_or_foreign_receipt_remains_unresolved(self):
        self.assertEqual(event_window(None,self.binding,start_ns=0,end_ns=10*NS,decision_ns=11*NS)['status'],'unresolved')
        self.assertEqual(event_window(self.receipt,self.binding,start_ns=0,end_ns=10*NS,decision_ns=11*NS)['reason'],'event_receipt_not_ready_at_decision')
        self.receipt['data']['binding']['worker_pid']=99
        self.assertEqual(self.gate(0,10)['status'],'unresolved')
    def test_reversed_gap_or_window_is_rejected(self):
        with self.assertRaises(ValueError):self.gate(0,10,withheld_interval=(40*NS,10*NS))
        with self.assertRaises(ValueError):self.gate(10,0)


if __name__=='__main__':unittest.main()
