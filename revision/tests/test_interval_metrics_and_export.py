"""CPU contract checks for interval statistics and real controller exports."""
from dataclasses import asdict,replace
import copy,json,math,tempfile,unittest
from pathlib import Path
from revision.tracing.interval_metrics import CounterStamp,WaitHistogram,PhaseCounters,wait_p95,prefill_fraction,phase_unavailable
from revision.tracing.measured_evidence import Acquisition,MeasuredObservation
from revision.tracing.feature_collection import FeatureWindow
from revision.tracing.timing import ManualClock
from revision.evaluation.controller_export import export_initial_stops
from revision.evaluation.scoring import InitialStopPrediction,evaluate
from revision.evaluation.reference_store import ReferenceStore
from revision.scripts.demo_interval_export import controller_case
from revision.scripts.demo_reference_scoring import make_references


class IntervalTests(unittest.TestCase):
    def setUp(self):
        self.a=CounterStamp('a','server','g0','wait',0,0,'test-clock')
        self.b=replace(self.a,sample_id='b',sampled_at_ns=100,available_at_ns=110)
        self.first=WaitHistogram(self.a,(.01,.1,1.,math.inf),(10,20,30,30),30)
        self.last=WaitHistogram(self.b,self.first.upper_seconds,(12,30,50,50),50)
        self.options=dict(now_ns=110,clock_domain='test-clock')

    def wait(self,**changes):return wait_p95(self.first,replace(self.last,**changes),**self.options)

    def test_delta_quantile_uses_interval_counts_not_lifetime(self):
        value=self.wait();self.assertAlmostEqual(value.value,910.)
        self.assertEqual((value.valid_samples,value.attempted_samples),(20,20))
        self.assertEqual(value.acquisition,Acquisition(0,100,110,'test-clock'))

    def test_zero_events_is_missing_not_zero_wait(self):
        result=self.wait(cumulative_counts=self.first.cumulative_counts,count=self.first.count)
        self.assertIsNone(result.value);self.assertEqual(result.missing_reason,'insufficient_interval_observations')

    def test_minimum_events_guard(self):
        self.assertIsNone(wait_p95(self.first,self.last,min_events=21,**self.options).value)
        with self.assertRaises(ValueError):wait_p95(self.first,self.last,min_events=0,**self.options)

    def test_infinite_quantile_is_missing(self):
        self.assertEqual(self.wait(cumulative_counts=(10,20,30,50)).missing_reason,'quantile_in_infinite_bucket')

    def test_counter_reset_is_missing(self):
        self.assertEqual(self.wait(cumulative_counts=(0,0,0,0),count=0).missing_reason,'counter_reset_or_decrease')

    def test_inconsistent_interval_buckets_are_missing(self):
        self.assertEqual(self.wait(cumulative_counts=(20,21,50,50)).missing_reason,'inconsistent_bucket_deltas')

    def test_identity_changes_fail_closed(self):
        for changes in ({'generation':'g1'},{'instance_id':'another-server'},{'series':'other-wait'}):
            with self.subTest(changes=changes):self.assertIsNone(self.wait(stamp=replace(self.b,**changes)).value)

    def test_schema_change_is_missing(self):
        self.assertEqual(self.wait(upper_seconds=(.02,.1,1.,math.inf)).missing_reason,'histogram_schema_changed')

    def test_future_or_unmapped_clock_rejected(self):
        for options in (dict(now_ns=109,clock_domain='test-clock'),dict(now_ns=110,clock_domain='other')):
            with self.assertRaises(ValueError):wait_p95(self.first,self.last,**options)

    def test_duplicate_out_of_order_snapshots_rejected(self):
        for stamp in (replace(self.b,sample_id='a'),replace(self.b,sampled_at_ns=0)):
            with self.assertRaises(ValueError):self.wait(stamp=stamp)

    def test_histogram_shape_count_nonfinite_or_wrong_semantics_rejected(self):
        for changes in (dict(upper_seconds=(.1,.01,1.,math.inf)),dict(count=51),dict(cumulative_counts=(10,9,50,50)),
                        dict(cumulative_counts=(True,30,50,50)),dict(upper_seconds=(.01,.1,float('nan'),math.inf)),
                        dict(semantics='request_duration'),dict(upper_seconds=(.01,.1,1.,2.))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(self.last,**changes)

    def test_exclusive_phase_fraction_and_idle(self):
        a=PhaseCounters(self.a,100,100,100,300);b=PhaseCounters(self.b,160,130,110,400)
        self.assertAlmostEqual(prefill_fraction(a,b,**self.options).value,.6)
        self.assertEqual(prefill_fraction(a,replace(a,stamp=self.b),**self.options).missing_reason,'no_attributed_service_time')

    def test_phase_partition_and_reset(self):
        with self.assertRaises(ValueError):PhaseCounters(self.a,5,5,5,14)
        a=PhaseCounters(self.a,100,100,100,300);b=PhaseCounters(self.b,1,2,3,6)
        self.assertIsNone(prefill_fraction(a,b,**self.options).value)
        self.assertIsNone(prefill_fraction(a,replace(a,stamp=replace(self.b,generation='new')),**self.options).value)

    def test_phase_unavailable_requires_no_proxy(self):
        result=phase_unavailable(Acquisition(0,100,110,'test-clock'))
        self.assertIsNone(result.value);self.assertEqual(result.missing_reason,'phase_attribution_not_instrumented')

    def test_exact_window_integration_and_original_availability(self):
        clock=ManualClock(110);clock.domain='test-clock'
        window=FeatureWindow(clock,0,100,min_latency_samples=1,grace_ns=10)
        window.on_interval_metric(self.wait());window.on_interval_metric(phase_unavailable(Acquisition(0,100,110,clock.domain)))
        metrics={m.name:m for m in window.close()}
        self.assertAlmostEqual(metrics['request_wait_p95_ms'].value,910.)
        self.assertIsNone(metrics['prefill_service_fraction'].value)

    def test_misaligned_future_late_duplicate_window_metrics_rejected(self):
        clock=ManualClock(110);clock.domain='test-clock'
        w=FeatureWindow(clock,0,100,min_latency_samples=1,grace_ns=10)
        for acquisition in (Acquisition(1,100,110,clock.domain),Acquisition(0,100,111,clock.domain),Acquisition(0,100,110,'foreign')):
            with self.assertRaises(ValueError):w.on_interval_metric(replace(self.wait(),acquisition=acquisition))
        w.on_interval_metric(self.wait())
        with self.assertRaises(ValueError):w.on_interval_metric(self.wait())
        w.close()
        with self.assertRaises(ValueError):w.on_interval_metric(phase_unavailable(Acquisition(0,100,110,clock.domain)))
        late=FeatureWindow(clock,0,100,min_latency_samples=1)
        with self.assertRaises(ValueError):late.on_interval_metric(self.wait())


class ExportTests(unittest.TestCase):
    def case(self,mode='unknown'):return controller_case(mode)
    def export(self,wrapper,observations):
        return export_initial_stops(wrapper['run_id'],wrapper['controller'],observations,classifier_version='fixture-test')

    def test_actual_unknown_stop_keeps_acquisition_and_no_cause_mapping(self):
        result,observations=self.case();row=InitialStopPrediction.from_dict(result['predictions'][0])
        self.assertEqual(row.terminal_reason,'fixed_burst_complete');self.assertIsNone(row.policy_label)
        self.assertEqual(row.cause_set,());self.assertIsNotNone(row.evidence_interval)
        self.assertIn(row.evidence_id,observations)

    def test_budget_unknown_preserved(self):
        result,_=self.case('budget');row=result['predictions'][0]
        self.assertEqual(row['terminal_reason'],'budget_exhausted');self.assertEqual(row['decision_status'],'ok')

    def test_launch_diagnosis_timeout_horizon_retained_without_invented_interval(self):
        for mode,status in [('launch_failure','capture_failed'),('diagnosis_failure','diagnosis_failed'),('timeout','timeout'),('horizon','horizon_censored')]:
            with self.subTest(mode=mode):
                result,_=self.case(mode);row=InitialStopPrediction.from_dict(result['predictions'][0])
                self.assertEqual(row.decision_status,status);self.assertIsNone(row.evidence_interval)
                self.assertEqual(row.cause_set,());self.assertIsNone(row.evidence_id)

    def test_reactivation_does_not_replace_first_stop(self):
        result,_=self.case('reactivated');source=result['controller_snapshot']['controller']['episodes'][0]
        self.assertEqual(source['reactivation_attempts'],1);self.assertEqual(len(result['predictions']),1)
        self.assertEqual(result['predictions'][0]['decision_at_ns'],source['decisions'][0]['decision_ready_at_ns'])

    def test_healthy_zero_activation_is_zero_stops(self):
        result,_=self.case('healthy');self.assertEqual(result['predictions'],[])

    def test_unfinished_snapshot_or_activation_timestamp_mismatch_rejected(self):
        result,observations=self.case();wrapper=result['controller_snapshot']
        for change in ('finished','start'):
            broken=copy.deepcopy(wrapper)
            if change=='finished':broken['controller']['finished']=False
            else:broken['controller']['episodes'][0]['started_at_ns']+=1
            with self.assertRaises(ValueError):self.export(broken,observations)

    def test_missing_ready_observation_rejected(self):
        result,_=self.case()
        with self.assertRaises(ValueError):self.export(result['controller_snapshot'],{})

    def test_wrong_observation_identity_domain_or_visibility_rejected(self):
        result,observations=self.case();eid=next(iter(observations));obs=observations[eid]
        for changed in (replace(obs,provenance='live_online'),replace(obs,kernel=replace(obs.kernel,capture_id='other')),
                        replace(obs,acquisition=replace(obs.acquisition,available_at_ns=50_000_000_000))):
            with self.assertRaises(ValueError):self.export(result['controller_snapshot'],{eid:changed})

    def test_incomplete_episode_and_duplicate_activation_rejected(self):
        result,observations=self.case();wrapper=result['controller_snapshot'];broken=copy.deepcopy(wrapper)
        episode=broken['controller']['episodes'][0];episode['decisions']=[];episode['ended_at_ns']=None
        with self.assertRaises(ValueError):self.export(broken,observations)
        broken=copy.deepcopy(wrapper);broken['controller']['events'].append(next(e for e in broken['controller']['events'] if e['event']=='episode_started'))
        with self.assertRaises(ValueError):self.export(broken,observations)

    def test_null_interval_cannot_assert_diagnosis(self):
        result,_=self.case('launch_failure');row=result['predictions'][0]
        with self.assertRaises(ValueError):InitialStopPrediction.from_dict(row|dict(policy_label='vllm_queue_pressure'))

    def test_exported_controller_rows_join_locked_references(self):
        for mode in ('unknown','budget','launch_failure','diagnosis_failure','timeout','horizon','reactivated','healthy'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);result,_=self.case(mode);wrapper=result['controller_snapshot'];domain=wrapper['controller']['clock_domain']
                records=make_references(root/'adjudication')
                record=replace(records[0],run_id=wrapper['run_id'],interval=Acquisition(0,50_000_000_000,50_000_000_000,domain),
                    adjudicated_at_ns=50_000_000_000,artifacts=tuple(replace(a,acquisition=replace(a.acquisition,clock_domain=domain)) for a in records[0].artifacts))
                clock=ManualClock(55_000_000_000);clock.domain=domain
                store=ReferenceStore(root/'store');anchor=store.lock([record],root/'adjudication',root/'adjudication/rubric.json',clock=clock)
                clock.advance_to(60_000_000_000)
                score=evaluate(store,anchor,json.dumps(result['predictions']).encode(),json.dumps(wrapper).encode(),clock=clock)
                expected=0 if mode=='healthy' else 1
                self.assertEqual(score['denominators']['all_initial_stops'],expected)
                self.assertEqual(sum(score['outcomes'].values()),expected)
                self.assertEqual(score['outcomes']['supported_complete'],0)
                if mode in ('launch_failure','diagnosis_failure','timeout','horizon'):
                    self.assertEqual(score['outcomes']['reference_unavailable'],1)
