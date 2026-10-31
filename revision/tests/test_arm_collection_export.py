"""Owned CPU collection/persistence/export checks; never accesses a GPU."""
import asyncio,copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from revision.tracing.arm_session import CpuTargetSession,SessionConfig
from revision.tracing.cpu_interval_collection import CpuIntervalCollector
from revision.tracing.experiment_arms import CpuArmRunner,require_comparable
from revision.tracing.feature_collection import collect_completion
from revision.tracing.timing import MonotonicClock
from revision.tracing.schedule_playback import PlaybackConfig
from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.evaluation.scoring import InitialStopPrediction
from revision.tracing.measured_evidence import MeasuredObservation


def offered(duration=.35):
    return ArrivalSchedule.from_bytes(json.dumps(dict(version='offered_arrivals_v1',duration_ns=round(duration*1e9),requests=[
        dict(request_id=f'opaque-{i}',offset_ns=i*10_000_000,payload=dict(model='fixture',prompt='fixture',max_tokens=32,stream=False))
        for i in range(int(duration/.01)-3)])).encode())


def config(**changes):
    return PlaybackConfig(**(dict(window_s=.05,grace_s=.015,min_latency_samples=1,request_timeout_s=1,drain_s=.08,
        max_admission_lateness_s=.1,sample_interval_s=.01,sample_timeout_s=.15)|changes))


class SourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    async def start(self,**changes):
        session=CpuTargetSession(self.root/'target',MonotonicClock(),'disabled',config=SessionConfig(work_s=.04),interval_recording=True,**changes)
        await session.start();await session.reset();collector=CpuIntervalCollector(session);await collector.bind()
        return session,collector

    async def test_actual_queue_wait_admissions_and_raw_hash(self):
        session,collector=await self.start()
        try:
            start=session.clock.now_ns()
            await asyncio.gather(*(collect_completion(session.clock,str(i),session.endpoint+'/v1/completions',dict(max_tokens=32)) for i in range(4)))
            end=session.clock.now_ns();receipt=await collector.collect(session.clock,'w',start,end)
            wait,phase=receipt.metrics
            self.assertIsNone(receipt.error);self.assertEqual(wait.valid_samples,4);self.assertGreater(wait.value,1)
            self.assertIsNone(phase.value);self.assertEqual(phase.missing_reason,'phase_attribution_not_instrumented')
            saved=collector.receipts[-1];self.assertEqual(hashlib.sha256(saved['raw'].encode()).hexdigest(),saved['raw_sha256'])
            raw=json.loads(saved['raw']);self.assertEqual(raw['previous']['sampled_at_ns'],start);self.assertEqual(raw['current']['sampled_at_ns'],end)
            self.assertLessEqual(raw['collected_at_ns'],saved['received_at_ns'])
        finally:await session.aclose()

    async def test_passive_metric_probe_retains_raw_bytes_without_feature_claims(self):
        from revision.scripts.snapshot_server_metrics import snapshot
        session,collector=await self.start()
        try:
            output=self.root/'probe'
            result=await snapshot(session.endpoint+'/metrics',output,samples=2,interval_s=0)
            self.assertFalse(result['interval_features_validated']);self.assertFalse(result['server_clock_mapping'])
            self.assertEqual(len(result['snapshots']),2)
            for row in result['snapshots']:
                self.assertIsNone(row['error']);self.assertEqual(hashlib.sha256((output/row['path']).read_bytes()).hexdigest(),row['sha256'])
                self.assertIn(dict(name='fixture_queue',declared_type='gauge'),row['declared_type_lines'])
            with self.assertRaises(FileExistsError):await snapshot(session.endpoint+'/metrics',output,samples=1)
        finally:await session.aclose()

    async def test_empty_histogram_is_unavailable_not_zero(self):
        session,collector=await self.start()
        try:
            start=session.clock.now_ns();await asyncio.sleep(.001);end=session.clock.now_ns()
            receipt=await collector.collect(session.clock,'w',start,end)
            self.assertEqual(receipt.metrics[0].missing_reason,'insufficient_interval_observations')
        finally:await session.aclose()

    async def test_binding_rejects_foreign_domain_and_probe(self):
        session,collector=await self.start()
        try:
            reply=collector.binding['source']
            for changed in (reply|dict(clock_domain='foreign'),reply|dict(probe_ns=0)):
                with patch.object(session,'command',return_value=changed),self.assertRaises(ValueError):await CpuIntervalCollector(session).bind()
        finally:await session.aclose()

    async def test_reset_invalidates_binding_without_silent_reuse(self):
        session,collector=await self.start()
        try:
            await session.reset();start=session.clock.now_ns();await asyncio.sleep(.001)
            receipt=await collector.collect(session.clock,'w',start,session.clock.now_ns())
            self.assertIsNone(receipt.metrics[0].value);self.assertIn('predates reset',receipt.error)
            await collector.bind();again=await collector.collect(session.clock,'w2',start,session.clock.now_ns())
            self.assertIsNone(again.error)
        finally:await session.aclose()

    async def test_future_interval_and_history_before_reset_are_rejected(self):
        session,collector=await self.start()
        try:
            for start,end in ((0,1),(session.clock.now_ns(),session.clock.now_ns()+10_000_000_000)):
                # Future acquisition cannot be represented as an available metric.
                if end>session.clock.now_ns():
                    with self.assertRaises(ValueError):await collector.collect(session.clock,'future',start,end)
                else:
                    receipt=await collector.collect(session.clock,'old',start,end)
                    self.assertIsNone(receipt.metrics[0].value);self.assertIsNotNone(receipt.error)
        finally:await session.aclose()

    async def test_parser_rejects_foreign_incomplete_or_bad_source_data(self):
        session,collector=await self.start()
        try:
            start=session.clock.now_ns();await asyncio.sleep(.001);end=session.clock.now_ns()
            receipt=await collector.collect(session.clock,'w',start,end);data=json.loads(collector.receipts[-1]['raw'])
            changes=[dict(nonce='foreign'),dict(history_complete=False),dict(semantics='request_duration'),
                dict(collected_at_ns=receipt.received_at_ns+1),dict(phase_attribution='inferred_from_prompt'),dict(clock_domain='foreign')]
            for changeset in changes:
                with self.subTest(changes=changeset),self.assertRaises(ValueError):collector.parse(data|changeset,start,end,receipt.received_at_ns,'x')
            for key,value in (('sampled_at_ns',start+1),('generation','foreign'),('count',1)):
                broken=copy.deepcopy(data);broken['previous'][key]=value
                with self.assertRaises(ValueError):collector.parse(broken,start,end,receipt.received_at_ns,'x')
        finally:await session.aclose()


class CollectionArmTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def runner(self,name='fixed_burst',fault='normal',**playback):
        return CpuArmRunner(self.root/(name+'-'+fault),name,offered(),playback_config=config(**playback),
            session_config=SessionConfig(work_s=.05),target_fault=fault)

    def verify_manifest(self,runner):
        manifest=json.loads((runner.output/'artifact_manifest.json').read_text())
        self.assertTrue(manifest['files'])
        for name,expected in manifest['files'].items():self.assertEqual(hashlib.sha256((runner.output/name).read_bytes()).hexdigest(),expected,name)

    async def test_normal_policy_persists_original_observations_and_scoring_exports(self):
        # This test needs an actual ready capture and an accepted interval,
        # rather than testing sub-15ms loopback scheduling on a busy host.
        runner=CpuArmRunner(self.root/'normal-persistence','fixed_burst',offered(1),
            playback_config=config(window_s=.1,grace_s=.1,drain_s=.3,sample_timeout_s=.3),
            session_config=SessionConfig(work_s=.05))
        result=await runner.run();self.verify_manifest(runner)
        self.assertEqual(result['status'],'completed');self.assertGreater(result['cheap_observation_count'],0)
        self.assertGreater(result['measured_observation_count'],0)
        observations=json.loads((runner.output/'measured_observations.json').read_text())
        rows=json.loads((runner.output/'evaluation/predictions.json').read_text())
        self.assertEqual(len(rows),len(result['controller']['episodes']))
        for row in rows:
            typed=InitialStopPrediction.from_dict(row);self.assertEqual(typed.cause_set,())
            if typed.decision_status=='ok':
                observation=MeasuredObservation.from_dict(observations[typed.evidence_id]);self.assertEqual(typed.evidence_interval,observation.acquisition)
                self.assertEqual(observation.metrics,());self.assertIsNotNone(observation.kernel)
        self.assertTrue(all(p['policy_label'] is None and 'calibration_unavailable' in p['reasons'] for p in json.loads((runner.output/'measured_predictions.json').read_text())))
        intervals=result['playback']['interval_records'];self.assertTrue(any(r['accepted'] and r['metric']['value'] is not None for r in intervals))
        self.assertEqual(result['playback']['live_interval_tasks'],0)

    async def test_no_profiler_opens_no_interval_source_or_export_controller(self):
        runner=self.runner('no_profiler');result=await runner.run();self.verify_manifest(runner)
        self.assertFalse(runner.session.interval_recording)
        self.assertIsNone(result['interval_source']);self.assertEqual(result['playback']['interval_records'],[])
        self.assertFalse(result['evaluation_export']['applicable']);self.assertFalse((runner.output/'evaluation/predictions.json').exists())

    async def test_cheap_control_persists_metrics_without_policy_or_capture(self):
        runner=self.runner('cheap_only');result=await runner.run();self.verify_manifest(runner)
        self.assertGreater(result['cheap_observation_count'],0);self.assertEqual(result['measured_observation_count'],0)
        self.assertFalse(result['evaluation_export']['applicable']);self.assertIsNone(result['capture_backend'])
        for row in result['playback']['interval_records']:
            if row['metric']['name']=='prefill_service_fraction':self.assertIsNone(row['metric']['value'])

    async def test_reference_retains_report_observation_without_policy_prediction(self):
        runner=self.runner('full_horizon_reference');result=await runner.run();self.verify_manifest(runner)
        self.assertEqual(result['measured_observation_count'],1);self.assertFalse(result['evaluation_export']['applicable'])
        self.assertIsNone(result['controller']);self.assertEqual(result['capture_backend']['attempts']['full-reference']['state'],'ready')

    async def test_reset_deltas_stay_unavailable_end_to_end(self):
        runner=self.runner(fault='interval_reset');result=await runner.run();self.verify_manifest(runner)
        waits=[r for r in result['playback']['interval_records'] if r['metric']['name']=='request_wait_p95_ms']
        self.assertTrue(waits);self.assertTrue(all(r['metric']['value'] is None for r in waits))
        self.assertTrue(any(r['metric']['missing_reason']=='counter_reset_or_decrease' for r in waits))
        self.assertTrue(result['evaluation_export']['applicable'])

    async def test_missing_generation_clock_and_overflow_do_not_become_zero(self):
        for fault in ('interval_missing','interval_generation','interval_clock','interval_overflow'):
            with self.subTest(fault=fault):
                runner=self.runner('cheap_only',fault);result=await runner.run();self.verify_manifest(runner)
                waits=[r for r in result['playback']['interval_records'] if r['metric']['name']=='request_wait_p95_ms']
                self.assertTrue(waits);self.assertTrue(all(r['metric']['value'] is None and r['collection_error'] for r in waits))
                self.assertTrue(all(r['raw'] is not None for r in result['interval_source']['receipts']))

    async def test_late_receipts_preserved_but_never_rewrite_closed_windows(self):
        runner=self.runner('cheap_only','interval_late',grace_s=.003);result=await runner.run();self.verify_manifest(runner)
        rows=result['playback']['interval_records'];self.assertTrue(rows);self.assertTrue(all(not r['accepted'] for r in rows))
        for window in result['playback']['feature_windows']:
            waits=[m for m in window['metrics'] if m['name']=='request_wait_p95_ms'];self.assertIsNone(waits[0]['value'])
        self.assertFalse(result['session']['cleanup']['group_alive']);self.assertEqual(result['playback']['live_interval_tasks'],0)

    async def test_interval_timeout_is_retained_and_cleanup_is_bounded(self):
        runner=self.runner('cheap_only','interval_late',sample_timeout_s=.005);result=await runner.run();self.verify_manifest(runner)
        self.assertGreater(result['playback']['interval_collection_errors'],0);self.assertEqual(result['playback']['live_interval_tasks'],0)
        self.assertTrue(any(r['error']=='cancelled' for r in result['interval_source']['receipts']))

    async def test_persistence_failure_is_a_failed_arm_with_cleanup_and_raw_results(self):
        runner=self.runner()
        with patch.object(runner,'persist_evaluation',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):await runner.run()
        saved=json.loads((runner.output/'results.json').read_text());self.assertEqual(saved['status'],'failed')
        self.assertTrue(any(e['phase']=='evaluation_persistence' for e in saved['errors']))
        self.assertFalse(saved['session']['cleanup']['group_alive']);self.verify_manifest(runner)

    async def test_cancellation_closes_interval_work_and_keeps_aborted_outputs(self):
        runner=self.runner('cheap_only','interval_late');task=asyncio.create_task(runner.run())
        while runner.driver is None:await asyncio.sleep(.001)
        await asyncio.sleep(.06);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        saved=json.loads((runner.output/'results.json').read_text());self.assertEqual(saved['status'],'aborted')
        self.assertEqual(saved['playback']['live_interval_tasks'],0);self.assertFalse(saved['session']['cleanup']['group_alive'])
        self.verify_manifest(runner)
