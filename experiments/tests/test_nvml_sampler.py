"""CPU-only fake bindings/workers; never import or initialize real NVML."""
import asyncio
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from experiments.scripts.preflight_gpu import preflight, probe
from experiments.tracing.nvml_sampler import NvmlConfig, NvmlSampler, NvmlSession, SamplingError
from experiments.tracing.timing import MonotonicClock


class NotSupported(Exception):
    pass


class FakeNvml:
    NVMLError_NotSupported = NotSupported

    def __init__(self, uuid='GPU-test', value=0, mig=0):
        self.uuid, self.value, self.mig = uuid, value, mig
        self.inits = self.shutdowns = 0

    def nvmlInit(self):
        self.inits += 1

    def nvmlShutdown(self):
        self.shutdowns += 1

    def nvmlDeviceGetHandleByUUID(self, uuid):
        self.requested_uuid = uuid
        return 'handle'

    def nvmlDeviceGetUUID(self, handle):
        return self.uuid.encode()

    def nvmlDeviceGetMigMode(self, handle):
        if self.mig is None:
            raise NotSupported()
        return self.mig, self.mig

    def nvmlDeviceGetName(self, handle):
        return b'fake device'

    def nvmlSystemGetDriverVersion(self):
        return b'fake driver'

    def nvmlDeviceGetUtilizationRates(self, handle):
        return SimpleNamespace(gpu=self.value)


def fake_worker(connection, uuid):
    """Spawn-safe native-worker stand-in; fake modes encoded only in test UUIDs."""
    try:
        if uuid == 'GPU-start-hang':
            time.sleep(60)
        if uuid == 'GPU-start-error':
            connection.send(dict(kind='startup_error', error_type='FakeNoDriver'))
            return
        connection.send(dict(kind='ready', metadata=dict(device_uuid='GPU-wrong' if uuid == 'GPU-wrong-id' else uuid,
                                                         mig_enabled=False, source='fake_worker')))
        index = 0
        while True:
            command = connection.recv()
            if command['kind'] == 'close':
                if uuid == 'GPU-close-hang':
                    time.sleep(60)
                connection.send(dict(kind='closed'))
                return
            if uuid in ('GPU-read-hang', 'GPU-cancel'):
                time.sleep(60)
            if uuid == 'GPU-read-error' and index == 0:
                connection.send(dict(kind='error', request_id=command['request_id'], error_type='FakeUnavailable'))
            else:
                connection.send(dict(kind='reading', request_id=command['request_id'] + (uuid == 'GPU-bad-reply'),
                                     gpu_util=float('nan') if uuid == 'GPU-invalid' else 0.0))
            index += 1
    finally:
        connection.close()


class SessionTests(unittest.TestCase):
    def test_configuration(self):
        for uuid in ('', '0', 'MIG-123', 'GPU-', None):
            with self.subTest(uuid=uuid), self.assertRaises(ValueError):
                NvmlConfig(uuid)
        with self.assertRaises(ValueError):
            NvmlConfig('GPU-test', read_timeout_s=0)

    def test_identity_zero_and_shutdown(self):
        module = FakeNvml()
        session = NvmlSession(module, 'GPU-test')
        self.assertEqual(module.requested_uuid, 'GPU-test')
        self.assertEqual(session.read(), 0)
        self.assertEqual(session.metadata['scope'], 'device_wide_not_process_attributed')
        session.close()
        session.close()
        self.assertEqual((module.inits, module.shutdowns), (1, 1))

    def test_uuid_mismatch_cleans_up(self):
        module = FakeNvml(uuid='GPU-other')
        with self.assertRaises(SamplingError):
            NvmlSession(module, 'GPU-test')
        self.assertEqual(module.shutdowns, 1)

    def test_mig_enabled_rejected(self):
        module = FakeNvml(mig=1)
        with self.assertRaises(SamplingError):
            NvmlSession(module, 'GPU-test')
        self.assertEqual(module.shutdowns, 1)

    def test_non_mig_device_support(self):
        session = NvmlSession(FakeNvml(mig=None), 'GPU-test')
        self.assertFalse(session.metadata['mig_enabled'])
        session.close()

    def test_invalid_utilization(self):
        for value in (None, True, float('nan'), float('inf'), -1, 101):
            with self.subTest(value=value):
                session = NvmlSession(FakeNvml(value=value), 'GPU-test')
                with self.assertRaises(SamplingError):
                    session.read()
                session.close()

    def test_query_error_never_becomes_zero(self):
        module = FakeNvml()
        def fail(handle):
            raise RuntimeError('not available')
        module.nvmlDeviceGetUtilizationRates = fail
        session = NvmlSession(module, 'GPU-test')
        with self.assertRaises(RuntimeError):
            session.read()
        session.close()

    def test_lazy_import_in_fresh_process(self):
        result = subprocess.run([sys.executable, '-c',
            'import sys; import experiments.tracing.nvml_sampler; import experiments.scripts.preflight_gpu; '
            'assert "pynvml" not in sys.modules; assert "torch" not in sys.modules'], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


class SamplerTests(unittest.IsolatedAsyncioTestCase):
    def sampler(self, uuid='GPU-test', **kwargs):
        values = dict(startup_timeout_s=3, read_timeout_s=.1, shutdown_timeout_s=.05)
        values.update(kwargs)
        return NvmlSampler(NvmlConfig(uuid, **values), MonotonicClock(), _worker_target=fake_worker)

    async def test_spawn_read_receipt_and_cleanup(self):
        # Verify normal handshake correctness using the production grace; the
        # 50 ms fault-test default also measures host scheduling under load.
        sampler = self.sampler(shutdown_timeout_s=NvmlConfig('GPU-test').shutdown_timeout_s)
        async with sampler:
            self.assertEqual(await sampler(), 0.0)
            self.assertEqual(sampler.metadata['source'], 'fake_worker')
        self.assertFalse(sampler.process.is_alive())
        self.assertFalse(sampler.forced_termination)
        receipt = next(e for e in sampler.events if e['event'] == 'nvml_read_received')
        request = next(e for e in sampler.events if e['event'] == 'nvml_read_requested')
        self.assertGreaterEqual(receipt['timestamp_ns'], request['timestamp_ns'])
        self.assertEqual(receipt['clock_domain'], sampler.clock.domain)
        self.assertEqual(receipt['sampling_interval'], 'unknown')
        self.assertTrue(sampler.events[-1]['shutdown_acknowledged'])
        await sampler.aclose()

    async def test_session_not_reusable(self):
        sampler = self.sampler()
        with self.assertRaises(SamplingError):
            await sampler()
        async with sampler:
            pass
        with self.assertRaises(SamplingError):
            await sampler.open()

    async def test_startup_error_cleans_up(self):
        sampler = self.sampler('GPU-start-error')
        with self.assertRaisesRegex(SamplingError, 'FakeNoDriver'):
            await sampler.open()
        self.assertTrue(sampler.closed)
        self.assertFalse(sampler.process.is_alive())

    async def test_native_startup_hang_terminated(self):
        sampler = self.sampler('GPU-start-hang', startup_timeout_s=.1)
        with self.assertRaisesRegex(SamplingError, 'deadline'):
            await sampler.open()
        self.assertTrue(sampler.forced_termination)
        self.assertFalse(sampler.process.is_alive())

    async def test_native_read_hang_does_not_block_event_loop(self):
        sampler = self.sampler('GPU-read-hang')
        async with sampler:
            ticks = 0
            async def heartbeat():
                nonlocal ticks
                for _ in range(10):
                    ticks += 1
                    await asyncio.sleep(.002)
            heart = asyncio.create_task(heartbeat())
            with self.assertRaisesRegex(SamplingError, 'deadline'):
                await sampler()
            await heart
        self.assertEqual(ticks, 10)
        self.assertTrue(sampler.forced_termination)
        self.assertFalse(sampler.process.is_alive())

    async def test_cancelled_read_closes_worker(self):
        sampler = self.sampler('GPU-cancel', read_timeout_s=2)
        async with sampler:
            pending = asyncio.create_task(sampler())
            await asyncio.sleep(.02)
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        self.assertTrue(sampler.closed)
        self.assertFalse(sampler.process.is_alive())

    async def test_cancelled_shutdown_preserves_cancellation_and_kills_worker(self):
        sampler = self.sampler('GPU-close-hang', shutdown_timeout_s=.1)
        await sampler.open()
        closing = asyncio.create_task(sampler.aclose())
        await asyncio.sleep(.02)
        closing.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertFalse(sampler.process.is_alive())
        self.assertTrue(sampler.forced_termination)

    async def test_cancellation_during_termination_still_waits_for_cleanup(self):
        sampler = self.sampler('GPU-close-hang', shutdown_timeout_s=.05)
        await sampler.open()
        terminate = sampler.process.terminate
        closing = None
        def cancel_at_termination():
            terminate()
            asyncio.get_running_loop().call_soon(closing.cancel)
        sampler.process.terminate = cancel_at_termination
        closing = asyncio.create_task(sampler.aclose())
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertFalse(sampler.process.is_alive())
        self.assertTrue(sampler.closed)
        self.assertEqual(sampler.events[-1]['event'], 'nvml_closed')

    async def test_worker_identity_and_values_validated(self):
        for uuid in ('GPU-bad-reply', 'GPU-invalid', 'GPU-wrong-id'):
            sampler = self.sampler(uuid)
            with self.subTest(uuid=uuid), self.assertRaises(SamplingError):
                async with sampler:
                    await sampler()
            self.assertTrue(sampler.closed)
            self.assertFalse(sampler.process.is_alive())

    async def test_completed_error_can_retry_without_stale_value(self):
        sampler = self.sampler('GPU-read-error')
        async with sampler:
            with self.assertRaisesRegex(SamplingError, 'FakeUnavailable'):
                await sampler()
            self.assertFalse(sampler.closed)
            self.assertEqual(await sampler(), 0)
        self.assertEqual(len([e for e in sampler.events if e['event'] == 'nvml_read_received']), 1)

    async def test_bridge_accepts_sampler_callback(self):
        from experiments.tests.test_producers import make_bridge, LocalService
        async with LocalService('missing') as service:
            bridge = make_bridge(service.endpoint, duration=.2, drain_s=1, request_timeout_s=2)
            sampler = NvmlSampler(NvmlConfig('GPU-test'), bridge.clock, _worker_target=fake_worker)
            bridge.sampler = sampler
            # Open first, then set a fresh observation horizon after worker startup.
            async with sampler:
                from experiments.tracing.aggregation import StreamingWindowAdapter, WindowConfig
                start = bridge.clock.now_ns()
                bridge.adapter = StreamingWindowAdapter(bridge.clock,
                    WindowConfig(start, start + 200_000_000, window_s=.05,
                        allowed_lateness_s=.015, require_request_starts=True),
                    bridge.controller.on_window, provenance='cpu_fake_nvml_integration')
                result = await bridge.run()
        self.assertEqual(result['sampler_errors'], 0)
        self.assertTrue(any(r['window']['gpu_util'] == 0 for r in bridge.adapter.reports))
        self.assertFalse(sampler.process.is_alive())


class PreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_passive_does_not_probe(self):
        with patch('experiments.scripts.preflight_gpu.probe', side_effect=AssertionError('probe called')):
            result = await preflight()
        self.assertEqual(result['mode'], 'passive_inventory')
        self.assertEqual(result['telemetry']['status'], 'not_checked')
        self.assertFalse(result['live_experiment_ready'])

    async def test_explicit_configuration_is_only_syntax_validation(self):
        result = await preflight(endpoint='http://127.0.0.1:1/generate', healthy_p95_ms=10,
                                 calibration_source='separate-calibration.json')
        self.assertEqual(result['configuration']['status'], 'syntax_valid_only')
        self.assertFalse(result['configuration']['endpoint_contacted'])
        self.assertFalse(result['live_experiment_ready'])

    async def test_incomplete_or_invalid_config_rejected(self):
        for arguments in (dict(endpoint='http://localhost'), dict(device_uuid='0'),
                          dict(probe_nvml=True), dict(endpoint='file:///a', healthy_p95_ms=10, calibration_source='x')):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                await preflight(**arguments)

    async def test_successful_probe_does_not_imply_capture_ready(self):
        with patch('experiments.scripts.preflight_gpu.probe', return_value=dict(status='sample_received', gpu_util=0)):
            result = await preflight(device_uuid='GPU-test', probe_nvml=True)
        self.assertEqual(result['telemetry']['status'], 'sample_received')
        self.assertFalse(result['live_experiment_ready'])
        self.assertEqual(result['capture_coverage'], 'unverified')

    async def test_failed_probe_report(self):
        class FailingSampler:
            def __init__(self, *args):
                pass
            async def __aenter__(self):
                raise SamplingError('fake absent driver')
            async def __aexit__(self, *args):
                pass
        result = await probe(NvmlConfig('GPU-test'), sampler_factory=FailingSampler)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_type'], 'SamplingError')


if __name__ == '__main__':
    unittest.main()
