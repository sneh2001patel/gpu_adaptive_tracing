"""Actual loopback HTTP/queue integration; no GPU dependencies."""
import asyncio
import unittest

from revision.scripts.demo_http_stream import LocalService, run_demo
from revision.tracing.aggregation import StreamingWindowAdapter, WindowConfig
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.producers import ProducerBridge, ProducerConfig, http_post
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import MonotonicClock, TimingRecorder, seconds_to_ns
from revision.tracing.windows import HealthyBaseline


def make_bridge(endpoint, sampler=None, duration=.16, **kwargs):
    clock = MonotonicClock()
    backend = FakeProfilerBackend(TimingRecorder(clock, provenance='synthetic_simulation'))
    baseline = HealthyBaseline(20, 'external-fixture-reference')
    controller = StreamingController(backend, baseline, lambda _: None,
        lambda identity, window: backend.start(identity, FakeCapturePlan(startup_s=.001)),
        ControllerConfig(burst_s=.01))
    start = clock.now_ns()
    adapter = StreamingWindowAdapter(clock, WindowConfig(start, start + seconds_to_ns(duration),
        window_s=.05, allowed_lateness_s=.015, require_request_starts=True),
        controller.on_window, provenance='cpu_http_dry_run')
    async def fake_sample():
        return 0.0
    defaults = dict(rate_rps=60, max_inflight=2, request_timeout_s=.2, drain_s=.02, sample_interval_s=.01)
    defaults.update(kwargs)
    return ProducerBridge(adapter, controller, ProducerConfig(endpoint, **defaults), {}, sampler or fake_sample)


class ProducerConfigTests(unittest.TestCase):
    def test_invalid_configuration(self):
        for change in ({'endpoint': 'file:///tmp/a'}, {'endpoint': 'http://user:password@localhost'},
                       {'rate_rps': float('nan')}, {'rate_rps': 0}, {'rate_rps': 1e10},
                       {'max_inflight': True}, {'max_response_bytes': 0}, {'drain_s': -1},
                       {'sample_interval_s': 0}, {'request_timeout_s': 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ProducerConfig(**({'endpoint': 'http://localhost/'} | change))


class ProducerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_receipt_order_and_calibration(self):
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint, request_timeout_s=2, drain_s=1)
            baseline = bridge.controller.baseline
            result = await bridge.run()
        self.assertGreater(result['admitted'], 0)
        self.assertEqual(result['admitted'], result['completed'])
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['baseline']['source_id'], 'external-fixture-reference')
        self.assertIs(bridge.controller.baseline, baseline)
        self.assertEqual(bridge.adapter.summary()['outstanding_tracked_requests'], [])
        self.assertEqual(bridge.adapter.summary()['untracked_completions'], 0)
        starts = {}
        receipts = []
        for event in bridge.events:
            record = event['record']
            receipts.append(event['received_at_ns'])
            self.assertGreaterEqual(event['queue_delay_ns'], 0)
            self.assertEqual(record['clock_domain'], bridge.clock.domain)
            if event['type'] == 'RequestStarted':
                starts[record['request_id']] = record['start_ns']
                self.assertLess(record['start_ns'], bridge.adapter.config.horizon_ns)
            elif event['type'] == 'RequestCompletion':
                self.assertEqual(starts[record['request_id']], record['start_ns'])
                self.assertGreater(record['end_ns'], record['start_ns'])
        self.assertEqual(receipts, sorted(receipts))
        self.assertTrue(bridge.adapter.finished and bridge.controller.finished)

    async def test_capacity_and_bounded_drain(self):
        async with LocalService('drain') as service:
            bridge = make_bridge(service.endpoint, max_inflight=1)
            result = await bridge.run()
        self.assertEqual(result['peak_inflight'], 1)
        self.assertEqual(result['admitted'], 1)
        self.assertGreater(result['skipped_capacity'], 0)
        self.assertEqual(result['drain_cancelled'], 1)
        self.assertEqual(result['completed'], 1)
        self.assertEqual(bridge.adapter.drain_completions, 1)
        final = next(e for e in bridge.events if e['type'] == 'RequestCompletion')
        self.assertEqual(final['record']['error_kind'], 'drain_cancelled')
        self.assertEqual(bridge.adapter.summary()['outstanding_tracked_requests'], [])
        # The final window still records the outstanding request at observation end.
        self.assertEqual(bridge.adapter.reports[-1]['window']['outstanding_request_count'], 1)

    async def test_request_timeout_is_terminal_error(self):
        async with LocalService('drain') as service:
            bridge = make_bridge(service.endpoint, duration=.12, request_timeout_s=.02)
            result = await bridge.run()
        self.assertEqual(result['completed'], result['admitted'])
        self.assertGreater(result['errors'], 0)
        errors = [e['record']['error_kind'] for e in bridge.events if e['type'] == 'RequestCompletion']
        self.assertIn('TimeoutError', errors)

    async def test_http_errors_reach_windows(self):
        async with LocalService('errors') as service:
            bridge = make_bridge(service.endpoint)
            result = await bridge.run()
        self.assertGreater(result['errors'], 0)
        self.assertTrue(any(e['record'].get('error_kind') == 'http_503' for e in bridge.events))
        self.assertTrue(any(r['window']['request_error_count'] for r in bridge.adapter.reports))
        self.assertTrue(any('request_errors' in e.get('suspicion_reasons', []) for e in bridge.controller.events))

    async def test_sampler_failure_becomes_missing_not_zero(self):
        async def failing():
            raise RuntimeError('unavailable')
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint, sampler=failing)
            result = await bridge.run()
        self.assertGreater(result['sampler_errors'], 0)
        self.assertTrue(all(r['window']['gpu_util'] is None for r in bridge.adapter.reports))
        self.assertTrue(all(r['window']['gpu_sample_count'] == 0 for r in bridge.adapter.reports))

    async def test_stuck_sampler_cancelled_at_horizon(self):
        stopped = asyncio.Event()
        async def hanging():
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint, sampler=hanging)
            await asyncio.wait_for(bridge.run(), 2)
        self.assertTrue(stopped.is_set())
        self.assertTrue(all(r['window']['gpu_util'] is None for r in bridge.adapter.reports))

    async def test_bridge_single_use(self):
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint)
            await bridge.run()
            with self.assertRaises(RuntimeError):
                await bridge.run()

    async def test_no_catchup_burst_after_event_loop_delay(self):
        # Controlled sleep in the sampler stands for an uncooperative callback.
        import time
        first = True
        async def slow():
            nonlocal first
            if first:
                first = False
                time.sleep(.055)
            return None
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint, sampler=slow)
            result = await bridge.run()
        self.assertGreater(result['skipped_scheduler'], 0)
        self.assertGreaterEqual(bridge.adapter.reports[0]['window']['available_at_ns'],
                                bridge.adapter.reports[0]['window']['end_ns'])

    async def test_consumer_failure_stops_controller_and_producers(self):
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint)
            def failing(window):
                raise RuntimeError('delivery failed')
            bridge.adapter.on_window = failing
            with self.assertRaisesRegex(RuntimeError, 'delivery failed'):
                await bridge.run()
        self.assertTrue(bridge.adapter.delivery_failed)
        self.assertTrue(bridge.controller.finished)

    async def test_protocol_failures_are_reported(self):
        for response in (b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n',
                         b'HTTP/1.1 200 OK\r\nContent-Length: 10000000\r\n\r\n',
                         b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}'):
            async def serve(reader, writer):
                try:
                    await reader.readuntil(b'\r\n\r\n')
                    writer.write(response)
                    await writer.drain()
                finally:
                    writer.close()
            server = await asyncio.start_server(serve, '127.0.0.1', 0)
            async with server:
                endpoint = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}/'
                with self.assertRaises((ValueError, asyncio.IncompleteReadError)):
                    await http_post(ProducerConfig(endpoint), b'{}')

    async def test_demo_provenance_and_unknown_diagnosis(self):
        result, bridge = await run_demo('slow', .3)
        self.assertFalse(result['gpu_used'])
        self.assertEqual(result['provenance'], 'cpu_http_dry_run')
        self.assertEqual(result['profiler_source'], 'fake_profiler')
        self.assertGreater(len(bridge.controller.episodes), 0)
        self.assertTrue(all(e.last_diagnosis is None for e in bridge.controller.episodes))


if __name__ == '__main__':
    unittest.main()
