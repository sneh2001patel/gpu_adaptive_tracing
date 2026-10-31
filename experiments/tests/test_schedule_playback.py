"""Exact offered-workload invariants and real loopback playback, no GPU."""
import asyncio
import copy
import json
import time
import unittest

from experiments.tests.test_feature_collectors import HttpFixture
from experiments.tracing.arrival_schedule import ArrivalSchedule
from experiments.tracing.schedule_playback import SchedulePlayback, PlaybackConfig
from experiments.tracing.feature_collection import QueueGaugeCollector
from experiments.tracing.feature_bridge import FeatureClassifierBridge
from experiments.tracing.timing import MonotonicClock


def schedule(offsets=(0,.025,.05),duration=.12):
    data=dict(version='offered_arrivals_v1',duration_ns=round(duration*1e9),requests=[
        dict(request_id=f'opaque-{i}',offset_ns=round(offset*1e9),payload=dict(
            model='fixture',prompt='actual fixture prompt',max_tokens=99,stream=False,temperature=0,seed=i))
        for i,offset in enumerate(offsets)])
    return ArrivalSchedule.from_bytes(json.dumps(data).encode())


def config(**changes):
    return PlaybackConfig(**(dict(max_inflight=8,window_s=.04,grace_s=.005,drain_s=.1,
        request_timeout_s=.3,max_admission_lateness_s=.2,sample_interval_s=.005,tick_s=.001)|changes))


class ScheduleTests(unittest.TestCase):
    def test_raw_and_semantic_hashes_distinguish_formatting_and_payload_changes(self):
        original=schedule();formatted=json.dumps(original.as_dict(),indent=4).encode()
        other=ArrivalSchedule.from_bytes(formatted)
        self.assertNotEqual(original.file_sha256,other.file_sha256)
        self.assertEqual(original.content_sha256,other.content_sha256)
        data=other.as_dict();data['requests'][0]['payload']['prompt']='different'
        self.assertNotEqual(original.content_sha256,ArrivalSchedule.from_bytes(json.dumps(data).encode()).content_sha256)

    def test_payload_copy_cannot_mutate_frozen_offered_work(self):
        original=schedule();payload=original.requests[0].payload;payload['max_tokens']=1
        self.assertEqual(original.requests[0].payload['max_tokens'],99)

    def test_duplicate_ids_unordered_offsets_and_horizon_boundary_are_rejected(self):
        base=schedule().as_dict()
        for mode in ('duplicate','order','boundary','negative'):
            data=copy.deepcopy(base)
            if mode=='duplicate':data['requests'][1]['request_id']=data['requests'][0]['request_id']
            elif mode=='order':data['requests'][1]['offset_ns']=data['requests'][2]['offset_ns']+1
            elif mode=='boundary':data['requests'][-1]['offset_ns']=data['duration_ns']
            else:data['requests'][0]['offset_ns']=-1
            with self.subTest(mode=mode),self.assertRaises(ValueError):ArrivalSchedule.from_bytes(json.dumps(data).encode())

    def test_truth_metadata_and_invalid_payloads_do_not_enter_schedule(self):
        for key,value in [('expected_label','queue'),('stream',True),('max_tokens',True),('temperature',float('nan'))]:
            data=schedule().as_dict();data['requests'][0]['payload'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):ArrivalSchedule.from_bytes(json.dumps(data).encode())
        data=schedule().as_dict();data['scenario']='overload'
        with self.assertRaises(ValueError):ArrivalSchedule.from_bytes(json.dumps(data).encode())

    def test_duplicate_json_keys_and_unknown_row_fields_are_rejected(self):
        with self.assertRaises(ValueError):ArrivalSchedule.from_bytes(b'{"version":"a","version":"b"}')
        data=schedule().as_dict();data['requests'][0]['reference_label']='queue'
        with self.assertRaises(ValueError):ArrivalSchedule.from_bytes(json.dumps(data).encode())

    def test_configuration_rejects_unbounded_or_impossible_options(self):
        for options in ({'max_inflight':0},{'drain_s':-1},{'request_timeout_s':0},{'telemetry_queue_size':True},
                        {'min_latency_samples':0},{'tick_s':float('nan')},{'sample_timeout_s':False}):
            with self.subTest(options=options),self.assertRaises(ValueError):config(**options)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_conserves_ids_usage_and_fixed_schedule(self):
        arrivals=schedule()
        async with HttpFixture(b'{"usage":{"prompt_tokens":7,"completion_tokens":3}}') as server:
            playback=SchedulePlayback(arrivals,MonotonicClock(),server.endpoint,provenance='synthetic_simulation',config=config())
            result=await playback.run()
        self.assertEqual((result['offered'],result['admitted'],result['counts']['completed']),(3,3,3))
        self.assertEqual(result['schedule_file_sha256'],arrivals.file_sha256)
        self.assertEqual([r['request_id'] for r in result['ledger']],[r.request_id for r in arrivals.requests])
        for row in result['ledger']:
            self.assertGreaterEqual(row['admitted_at_ns'],row['due_at_ns'])
            self.assertEqual(row['terminal']['output_tokens'],3)
        self.assertEqual(result['live_request_tasks'],0);self.assertEqual(result['live_sampling_tasks'],0)
        with self.assertRaises(RuntimeError):await playback.run()

    async def test_capacity_skips_retain_offered_ids_without_retiming(self):
        arrivals=schedule((0,0,0),.06)
        async with HttpFixture(b'{}',delay=.04) as server:
            result=await SchedulePlayback(arrivals,MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(max_inflight=1)).run()
        self.assertEqual(result['admitted'],1)
        self.assertEqual(result['counts']['skipped_capacity'],2)
        self.assertEqual({r['offset_ns'] for r in result['ledger']},{0})

    async def test_scheduler_delay_skips_expired_offers_without_catch_up_burst(self):
        blocked=False
        def service():
            nonlocal blocked
            if not blocked:blocked=True;time.sleep(.035)
        async with HttpFixture(b'{}') as server:
            result=await SchedulePlayback(schedule((0,.01,.02,.09)),MonotonicClock(),server.endpoint,
                provenance='synthetic_simulation',config=config(max_admission_lateness_s=.008),service_evidence=service).run()
        self.assertGreaterEqual(result['counts']['skipped_scheduler'],3)
        self.assertLessEqual(result['admitted'],1)

    async def test_entirely_missed_horizon_retains_every_offer_as_skipped(self):
        blocked=False
        def service():
            nonlocal blocked
            if not blocked:blocked=True;time.sleep(.07)
        async with HttpFixture() as server:
            result=await SchedulePlayback(schedule((0,.01),.04),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(),service_evidence=service).run()
        self.assertEqual(result['counts']['skipped_horizon'],2)
        self.assertEqual(result['admitted'],0)
        self.assertTrue(all(result['accounting_checks'].values()))

    async def test_timeout_is_failed_terminal_not_censored_success(self):
        async with HttpFixture(b'{}',delay=.1) as server:
            result=await SchedulePlayback(schedule((0,),.06),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(request_timeout_s=.015)).run()
        self.assertEqual(result['counts']['failed'],1)
        self.assertEqual(result['counts']['censored'],0)
        self.assertEqual(result['ledger'][0]['terminal']['completion']['error_kind'],'TimeoutError')

    async def test_horizon_pending_then_natural_drain_completion_is_preserved(self):
        async with HttpFixture(b'{"usage":{"prompt_tokens":7,"completion_tokens":3}}',delay=.07) as server:
            result=await SchedulePlayback(schedule((0,),.035),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(drain_s=.2)).run()
        self.assertEqual(result['counts']['completed'],1)
        self.assertEqual(result['pending_at_horizon_reconstructed'],['opaque-0'])
        self.assertEqual(result['post_horizon_terminals'],1)
        self.assertTrue(all(w['audit']['completion_count']==0 for w in result['feature_windows']))

    async def test_drain_cutoff_censors_request_without_imputing_response_latency(self):
        async with HttpFixture(b'{}',delay=.2) as server:
            result=await SchedulePlayback(schedule((0,),.03),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(drain_s=.01)).run()
        self.assertEqual(result['counts']['censored'],1)
        row=result['ledger'][0]
        self.assertEqual(row['terminal']['completion']['error_kind'],'drain_cancelled')
        self.assertEqual(result['counts']['completed'],0)
        self.assertEqual(result['live_request_tasks'],0)

    async def test_same_file_can_have_different_realized_work_across_concurrency_limits(self):
        arrivals=schedule((0,0,0),.06);results=[]
        async with HttpFixture(b'{}',delay=.02) as server:
            for limit in (1,3):
                results.append(await SchedulePlayback(arrivals,MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                    config=config(max_inflight=limit)).run())
        self.assertEqual(results[0]['schedule_file_sha256'],results[1]['schedule_file_sha256'])
        self.assertEqual([r['admitted'] for r in results],[1,3])

    async def test_bounded_telemetry_overflow_is_explicit_and_flagged(self):
        async def sample():return 90
        async with HttpFixture() as server:
            result=await SchedulePlayback(schedule((),.06),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(tick_s=.02,sample_interval_s=.0001,telemetry_queue_size=1),gpu_sampler=sample).run()
        self.assertGreater(result['telemetry_overflows'],0)
        self.assertFalse(result['receipt_coverage_clean'])
        self.assertEqual(len(result['telemetry_drops']),result['telemetry_overflows'])

    async def test_failed_gpu_callback_remains_missing_and_counted(self):
        async def sample():raise RuntimeError('fixture sampler unavailable')
        async with HttpFixture() as server:
            result=await SchedulePlayback(schedule((),.05),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(),gpu_sampler=sample).run()
        self.assertGreater(result['sampling_errors']['gpu'],0)
        self.assertTrue(all(m['value'] is None for w in result['feature_windows'] for m in w['metrics'] if m['name']=='gpu_util_mean'))

    async def test_saved_cli_preserves_schedule_bytes_and_partial_statistics(self):
        from argparse import Namespace
        from contextlib import redirect_stdout
        import io
        from pathlib import Path
        import tempfile
        from experiments.scripts.play_arrivals import main_async
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'offered.json';raw=json.dumps(schedule((0,),.05).as_dict(),indent=3).encode()
            source.write_bytes(raw)
            async with HttpFixture(b'{"usage":{"prompt_tokens":7,"completion_tokens":3}}') as server:
                args=Namespace(schedule=source,endpoint=server.endpoint,output=root/'result',provenance='synthetic_simulation',
                    queue_endpoint=None,queue_series=None,max_inflight=2,request_timeout=.2,drain=.1,max_lateness=.1,
                    window=.025,grace=.005,min_latency_samples=2)
                with redirect_stdout(io.StringIO()):await main_async(args)
            self.assertEqual((args.output/'offered_arrivals.json').read_bytes(),raw)
            data=json.loads((args.output/'results.json').read_text())
            self.assertEqual(data['counts']['completed'],1)
            self.assertTrue(all(p['policy_label'] is None for p in data['predictions']))
            self.assertTrue((args.output/'source_manifest.json').is_file())

    async def test_delayed_fake_profiler_is_serviced_during_exact_http_playback(self):
        from experiments.scripts.demo_schedule_playback import run_case,offered_bytes
        result=await run_case('delayed_evidence',ArrivalSchedule.from_bytes(offered_bytes()))
        self.assertTrue(result['fake_capture']['classified'])
        self.assertFalse(result['gpu_used'])
        self.assertTrue(all(result['accounting_checks'].values()))
        kernel_prediction=next(p for p in result['predictions'] if p['evidence_id'] is not None)
        self.assertGreaterEqual(kernel_prediction['decision_at_ns'],kernel_prediction['available_at_ns'])
        self.assertTrue(any(r['terminal'] is not None and r['terminal']['completion']['end_ns']>kernel_prediction['decision_at_ns'] for r in result['ledger']))

    async def test_http_sampling_and_closed_windows_feed_only_typed_observations(self):
        clock=MonotonicClock();bridge=FeatureClassifierBridge(clock,provenance='synthetic_simulation',device_uuid='GPU-fixture',worker_pid=1)
        async def sample():return 90
        def on_window(identity,window):bridge.register(identity,window);bridge.classify(identity)
        async with HttpFixture(b'# TYPE queue gauge\nqueue 0') as server:
            playback=SchedulePlayback(schedule((),.06),clock,server.endpoint,provenance='synthetic_simulation',config=config(),
                server_collector=QueueGaugeCollector(server.endpoint,'queue'),gpu_sampler=sample,on_window=on_window)
            result=await playback.run()
        self.assertEqual(len(bridge.predictions),2)
        self.assertTrue(all(p.policy_label is None for p in bridge.predictions))
        self.assertTrue(any(m.name=='queue_depth_mean' and m.value==0 for o in bridge.observations for m in o.metrics))
        self.assertEqual(result['sampling_errors'],{'server':0,'gpu':0})

    async def test_run_cancellation_cleans_requests_and_keeps_partial_accounting(self):
        async with HttpFixture(b'{}',delay=.3) as server:
            playback=SchedulePlayback(schedule((0,.1),.2),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',config=config())
            task=asyncio.create_task(playback.run());await asyncio.sleep(.015);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        result=playback.snapshot()
        self.assertEqual(result['status'],'aborted')
        self.assertEqual(result['live_request_tasks'],0)
        self.assertEqual(result['counts']['censored'],1)
        self.assertEqual(result['counts']['not_dispatched_run_abort'],1)
        self.assertIsNone(result['pending_at_horizon_reconstructed'])

    async def test_consumer_failure_cleans_up_and_surfaces_error(self):
        def fail(*args):raise RuntimeError('fixture consumer failed')
        async with HttpFixture(b'{}',delay=.3) as server:
            playback=SchedulePlayback(schedule((0,),.15),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(window_s=.02),on_window=fail)
            with self.assertRaisesRegex(RuntimeError,'consumer failed'):await playback.run()
        result=playback.snapshot()
        self.assertEqual(result['status'],'aborted')
        self.assertEqual(result['live_request_tasks'],0)

    async def test_service_hook_keeps_running_while_requests_are_pending(self):
        calls=0
        def service():
            nonlocal calls
            calls+=1
        async with HttpFixture(b'{}',delay=.04) as server:
            result=await SchedulePlayback(schedule((0,),.06),MonotonicClock(),server.endpoint,provenance='synthetic_simulation',
                config=config(),service_evidence=service).run()
        self.assertGreater(calls,5)
        self.assertEqual(result['counts']['completed'],1)


if __name__=='__main__':unittest.main()
