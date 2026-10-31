"""Synthetic CPU histories test cohorts/intervals/readiness, not diagnostic truth."""
import copy,json,tempfile,unittest
from dataclasses import asdict
from pathlib import Path
from experiments.evaluation.scheduler_bound_audit import audit_window,boundary_state,cohort,distribution,audit_campaign,sha
from experiments.feasibility.challenge_protocol import event_window
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.server_events import EventJournal,validate_snapshot
from experiments.scripts.audit_scheduler_bounds import audit

MS=1_000_000


class BoundAuditTests(unittest.TestCase):
    def setUp(self):
        self.binding=ServingBinding('fixture',1,43,'GPU-fixture','model','0','fixture-clock')
        self.now=0;self.journal=EventJournal(self.binding,lambda:self.now)
        self.event('engine_admitted',10,20)
        self.event('first_positive_schedule',100,110)
        self.event('scheduler_finished',200,210,'FINISHED_LENGTH_CAPPED')
        self.now=300*MS;cmd=dict(token='a'*32,binding=asdict(self.binding),requested_at_ns=290*MS)
        self.receipt=dict(command=cmd,received_at_ns=310*MS,data=self.journal.probe(cmd))
        self.states=validate_snapshot(self.receipt['data'],cmd,self.binding,310*MS)
        self.requests=[dict(request_id='r1',admitted_at_ns=0,completed_at_ns=250*MS)]

    def event(self,kind,start,end,status=None):
        self.now=end*MS;self.journal.record(kind,'cmpl-r1-0',start*MS,end*MS,terminal_status=status)

    def window(self,start=50,end=150,*,probes=None,withheld=None,late=False):
        probes=[('probe.json',self.receipt)] if probes is None else probes
        w=dict(start_ns=start*MS,end_ns=end*MS,decision_ns=end*MS+750*MS,
            owner_observed_at_ns=end*MS+750*MS+(51*MS if late else 1*MS),owner_late=late)
        available=[r for _,r in probes if r['received_at_ns']<=w['decision_ns']]
        gate=event_window(available[-1] if available else None,self.binding,start_ns=w['start_ns'],end_ns=w['end_ns'],decision_ns=w['decision_ns'],withheld_interval=withheld)
        if late:gate=dict(status='unresolved',reason='owner_decision_deadline_missed',bounds=None,diagnosis=None)
        return w|gate,probes

    def test_interval_width_and_cohort_difference_are_explicit(self):
        w,probes=self.window();r=audit_window(probes,self.binding,w,self.states,self.requests)
        self.assertEqual(r['descriptive_proxy_p95_bounds']['lower_ms'],80)
        self.assertEqual(r['descriptive_proxy_p95_bounds']['upper_ms'],100)
        self.assertEqual(r['client_admission_count'],0);self.assertEqual(r['client_completion_count'],0)
        self.assertEqual(r['schedule_cohort_not_client_admission_ids'],['cmpl-r1-0'])
        self.assertEqual(r['client_pending_at_window_end'],1)
        self.assertFalse(r['existing_request_wait_p95_mapping_supported']);self.assertIsNone(r['diagnosis'])

    def test_boundary_crossing_is_not_assigned_a_point_wait(self):
        w,probes=self.window(end=105);r=audit_window(probes,self.binding,w,self.states,self.requests)
        self.assertEqual(r['raw_source_at_deadline']['observations'],[])
        self.assertEqual(r['raw_source_at_deadline']['boundary_ambiguous_request_ids'],['cmpl-r1-0'])
        self.assertIsNone(r['descriptive_proxy_p95_bounds']['lower_ms'])
        self.assertEqual(r['retrospective_source_state_at_window_end']['unscheduled_boundary_ambiguous'],1)

    def test_half_open_end_and_uncertain_left_edge_are_separate(self):
        observations,ambiguous=cohort(self.states,110*MS,150*MS)
        self.assertEqual(observations,[]);self.assertEqual(ambiguous,['cmpl-r1-0'])
        observations,ambiguous=cohort(self.states,0,100*MS)
        self.assertEqual((observations,ambiguous),([],[]))

    def test_late_receipt_cannot_retrofill_even_with_complete_final_history(self):
        late=copy.deepcopy(self.receipt);late['received_at_ns']=901*MS
        w,probes=self.window(probes=[('late.json',late)])
        r=audit_window(probes,self.binding,w,self.states,self.requests)
        self.assertEqual(r['consumer_reason'],'missing_event_receipt');self.assertIsNone(r['selected_probe'])
        self.assertIsNone(r['raw_source_at_deadline']);self.assertEqual(r['consumer_usable_bound_observations'],0)
        self.assertEqual(r['retrospective_final_cohort_count'],1)

    def test_withheld_raw_bounds_are_offline_only(self):
        masked=(0,200*MS);w,probes=self.window(withheld=masked)
        r=audit_window(probes,self.binding,w,self.states,self.requests,masked)
        self.assertEqual(len(r['raw_source_at_deadline']['observations']),1)
        self.assertEqual(r['consumer_usable_bound_observations'],0)
        self.assertEqual(r['consumer_reason'],'deliberately_withheld_consumer_event_evidence')

    def test_owner_missed_deadline_does_not_accept_ready_bounds(self):
        w,probes=self.window(late=True);r=audit_window(probes,self.binding,w,self.states,self.requests)
        self.assertTrue(r['owner_late']);self.assertEqual(r['consumer_usable_bound_observations'],0)

    def test_probe_pending_and_historical_pending_are_not_interchangeable(self):
        w,probes=self.window(end=90);r=audit_window(probes,self.binding,w,self.states,self.requests)
        self.assertEqual(r['raw_source_at_deadline']['still_unscheduled_at_probe'],0)
        self.assertEqual(r['retrospective_source_state_at_window_end']['unscheduled_definite'],1)
        self.assertEqual(r['window_end_only_unscheduled_ids'],['cmpl-r1-0'])
        self.assertFalse(r['retrospective_state_is_online_feature'])

    def test_unscheduled_and_aborted_without_schedule_are_not_zero_waits(self):
        for finished in (False,True):
            states=copy.deepcopy(self.states);states['cmpl-r1-0']['scheduled']=None
            if not finished:states['cmpl-r1-0']['finished']=None
            observations,ambiguous=cohort(states,0,250*MS)
            self.assertEqual(observations,[]);self.assertEqual(ambiguous,[])
            end=boundary_state(states,250*MS)
            self.assertEqual(end['unscheduled_definite'],1)
            self.assertEqual(end['unfinished_definite'],0 if finished else 1)

    def test_overlapping_hooks_clip_lower_bound_but_retain_uncertainty(self):
        states=copy.deepcopy(self.states);states['cmpl-r1-0']['admission']['hook_return_ns']=105*MS
        observations,_=cohort(states,50*MS,150*MS)
        self.assertEqual(observations[0]['wait_lower_ms'],0)
        self.assertEqual(observations[0]['wait_upper_ms'],100)

    def test_recorded_gate_and_fixed_deadline_cannot_be_rewritten(self):
        w,probes=self.window();w['status']='unresolved'
        with self.assertRaisesRegex(ValueError,'Recorded consumer'):audit_window(probes,self.binding,w,self.states,self.requests)
        w,probes=self.window();w['decision_ns']+=1
        with self.assertRaisesRegex(ValueError,'Changed consumer deadline'):audit_window(probes,self.binding,w,self.states,self.requests)

    def test_foreign_source_binding_is_rejected(self):
        w,probes=self.window();bad=copy.deepcopy(self.receipt);bad['data']['binding']['generation']=2
        with self.assertRaises(ValueError):audit_window([('bad.json',bad)],self.binding,w,self.states,self.requests)

    def test_empty_statistics_are_unavailable_and_rank_is_nearest_rank(self):
        self.assertEqual(distribution([]),dict(n=0,min=None,median=None,p95=None,max=None))
        self.assertEqual(distribution(list(range(1,21)))['p95'],19)

    def test_manifest_pin_and_output_isolation_fail_before_processing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'artifact_manifest.json').write_text(json.dumps(dict(files={})))
            with self.assertRaisesRegex(ValueError,'retained digest'):audit_campaign(root,'f'*64)
            with self.assertRaisesRegex(ValueError,'outside'):audit(root,root/'audit','f'*64)
            outside=root.parent/root.name;self.assertTrue(outside.exists())
            with self.assertRaises(FileExistsError):audit(root,root.parent,'f'*64)

    def test_pinned_manifest_does_not_allow_changed_bytes_or_escaping_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'data.json').write_bytes(b'changed')
            for files,reason in [({'data.json':sha(b'original')},'hash mismatch'),({'../outside':'f'*64},'Unsafe campaign')]:
                raw=json.dumps(dict(files=files)).encode();(root/'artifact_manifest.json').write_bytes(raw)
                with self.assertRaisesRegex(ValueError,reason):audit_campaign(root,sha(raw))
