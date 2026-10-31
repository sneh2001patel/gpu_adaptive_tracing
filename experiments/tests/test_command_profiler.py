"""Owned CPU subprocesses and fake reports; no Nsight/GPU interaction."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

from experiments.scripts.demo_command_profiler import fixture_plan
from experiments.tracing.command_profiler import CommandProfilerBackend
from experiments.tracing.evidence_gate import EvidenceDecisionGate
from experiments.tracing.policies import PolicyConfig, StoppingPolicy
from experiments.tracing.profiler import CaptureFailed, EvidenceNotReady
from experiments.tracing.timing import MonotonicClock, TimingRecorder


@unittest.skipUnless(os.name == 'posix', 'POSIX process-group implementation')
class CommandBackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='profiler-command-test-')
        self.clock = MonotonicClock()
        self.recorder = TimingRecorder(self.clock, provenance='synthetic_simulation')
        self.backend = CommandProfilerBackend(self.recorder, Path(self.temp.name))

    async def asyncTearDown(self):
        try:
            await self.backend.aclose()
        finally:
            self.temp.cleanup()

    def plan(self, mode='ok', **changes):
        return fixture_plan(mode, **(dict(startup_s=1, stop_s=1, finalization_s=1, export_s=1,
                                         parse_s=1, cleanup_grace_s=.03) | changes))

    async def until(self, states, identity='c', timeout=5):
        limit = asyncio.get_running_loop().time() + timeout
        while self.backend.state(identity) not in states:
            self.backend.poll(identity)
            if asyncio.get_running_loop().time() > limit:
                self.fail(f'Timed out in {self.backend.state(identity)}')
            await asyncio.sleep(.005)
        return self.backend.state(identity)

    async def run_capture(self, mode='ok', identity='c', **changes):
        self.backend.start(identity, self.plan(mode, **changes))
        state = await self.until({'capturing', 'failed'}, identity)
        if state == 'capturing':
            self.backend.stop(identity)
            state = await self.until({'ready', 'failed'}, identity)
        return state

    async def test_plan_rejects_ambiguous_configuration(self):
        for changes in (dict(collect='shell command'), dict(stop=()), dict(driver_version=''),
                        dict(worker_pids=(True,)), dict(worker_pids=(1, 1)), dict(parse_s=0),
                        dict(device_uuid='0'), dict(max_artifact_bytes=0)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan(**changes)
        with self.assertRaises(ValueError):
            CommandProfilerBackend(TimingRecorder(self.clock, provenance='live_online'), Path(self.temp.name))

    async def test_end_to_end_readiness_hashes_and_timing(self):
        self.assertEqual(await self.run_capture(), 'ready')
        evidence = self.backend.evidence('c')
        self.assertEqual(evidence.payload['top_kernel_name'], 'fixture_gemm')
        self.assertEqual(len(evidence.payload['artifact_hashes']), 3)
        self.assertLessEqual(evidence.ready_at_ns, self.clock.now_ns())
        metrics = self.recorder.metrics('c')
        self.assertIsNone(metrics['capture_active_s'])
        self.assertIsNone(metrics['server_startup_s'])
        self.assertIsNone(metrics['lifecycle_total_s'])
        self.assertGreater(metrics['profile_process_wall_s'], metrics['capture_control_window_s'])
        self.assertGreater(metrics['evidence_collection_s'], metrics['profile_process_wall_s'])
        await self.backend.aclose()
        self.assertTrue(self.backend.snapshot()['attempts']['c']['cleanup_complete'])
        self.assertEqual(self.backend.snapshot()['attempts']['c']['groups_alive'], [])
        self.assertTrue(all(p['returncode'] == 0 for p in self.backend.snapshot()['attempts']['c']['commands'].values()))
        evidence.payload['kernels'].clear()
        self.assertTrue(self.backend.evidence('c').payload['kernels'])

    async def test_ack_required_and_stop_validated(self):
        self.backend.start('c', self.plan('no-start-ack', startup_s=.15))
        with self.assertRaises(ValueError):
            self.backend.stop('c')
        await asyncio.sleep(.03)
        self.backend.poll('c')
        self.assertEqual(self.backend.state('c'), 'starting')
        self.assertEqual(await self.until({'failed'}), 'failed')
        self.assertIsNone(self.recorder.duration('capture_control_window', 'c'))

    async def test_gate_never_classifies_before_parse(self):
        classifier = Mock(return_value='compute_bound')
        gate = EvidenceDecisionGate(self.backend, StoppingPolicy('stability_stop', PolicyConfig()), classifier)
        gate.start_capture('c', lambda:self.backend.start('c', self.plan()))
        with self.assertRaises(EvidenceNotReady):
            gate.evaluate('early')
        classifier.assert_not_called()
        await self.until({'capturing'})
        self.backend.stop('c')
        with self.assertRaises(EvidenceNotReady):
            gate.evaluate('still-early')
        await self.until({'ready', 'failed'})
        decision = gate.evaluate('ready')
        self.assertEqual(decision.status, 'ok')
        self.assertEqual(classifier.call_count, 1)
        self.assertGreaterEqual(decision.decision_ready_at_ns, decision.evidence_ready_at_ns)

    async def test_collector_wall_time_excludes_lingering_stop_helper(self):
        self.backend.start('c', self.plan('stop-helper-hold'))
        await self.until({'capturing'})
        self.backend.stop('c')
        deadline = asyncio.get_running_loop().time() + 3
        while not self.backend.attempts['c'].report_ready:
            self.backend.poll('c')
            self.assertNotEqual(self.backend.state('c'), 'failed')
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        self.assertIsNotNone(self.recorder.duration('profile_process_wall', 'c'))
        self.assertIsNotNone(self.recorder.duration('report_finalization', 'c'))
        self.assertIsNone(self.recorder.duration('stop_command', 'c'))
        (self.backend.attempts['c'].directory / 'allow-stop-exit').touch()
        self.assertEqual(await self.until({'ready', 'failed'}), 'ready')

    async def test_collection_exit_is_not_capture_ack(self):
        self.assertEqual(await self.run_capture('collect-exit'), 'failed')
        self.assertIn('collect_exit:7', self.backend.attempts['c'].failure)

    async def test_stop_success_is_not_stop_ack(self):
        self.assertEqual(await self.run_capture('no-stop-ack'), 'failed')
        self.assertIn('without stop acknowledgement', self.backend.attempts['c'].failure)

    async def test_bad_start_ack_rejected(self):
        self.assertEqual(await self.run_capture('wrong-start-ack'), 'failed')
        self.assertIn('identity', self.backend.attempts['c'].failure)

    async def test_nonzero_export_and_parse(self):
        for index, mode in enumerate(('stop-exit', 'export-exit', 'parse-exit')):
            identity = f'c{index}'
            self.assertEqual(await self.run_capture(mode, identity), 'failed')
            self.assertIn('exit:7', self.backend.attempts[identity].failure)
            await self.backend.aclose()

    async def test_missing_report_and_lfs_rejected(self):
        for index, mode in enumerate(('missing-report', 'lfs-report')):
            identity = f'c{index}'
            self.assertEqual(await self.run_capture(mode, identity), 'failed')
            await self.backend.aclose()

    async def test_export_integrity_and_json_checked(self):
        for index, mode in enumerate(('export-invalid', 'export-wrong-hash')):
            identity = f'c{index}'
            self.assertEqual(await self.run_capture(mode, identity), 'failed')
            await self.backend.aclose()

    async def test_summary_identity_units_coverage_and_truth_fields(self):
        for index, mode in enumerate(('empty-summary', 'wrong-device', 'wrong-workers', 'unknown-coverage',
                                     'truth-summary', 'wrong-units', 'wrong-summary-id', 'wrong-summary-hash')):
            identity = f'c{index}'
            self.assertEqual(await self.run_capture(mode, identity), 'failed', mode)
            with self.assertRaises(CaptureFailed):
                self.backend.evidence(identity)
            await self.backend.aclose()

    async def test_all_external_stage_timeouts(self):
        for index, (mode, deadlines) in enumerate((
            ('collect-hang', dict(startup_s=.15)), ('stop-hang', dict(stop_s=.15)),
            ('finalization-hang', dict(finalization_s=.15)),
            ('export-hang', dict(export_s=.15)), ('parse-hang', dict(parse_s=.15)))):
            identity = f'c{index}'
            self.assertEqual(await self.run_capture(mode, identity, **deadlines), 'failed')
            self.assertIn('timeout', self.backend.attempts[identity].failure)
            await self.backend.aclose()
            self.assertTrue(self.backend.attempts[identity].cleanup_complete)

    async def test_cancel_during_capture_prevents_late_evidence(self):
        self.backend.start('c', self.plan())
        await self.until({'capturing'})
        self.backend.cancel('c', 'horizon_ended')
        self.backend.cancel('c', 'second_cancel')
        self.assertEqual(self.backend.attempts['c'].failure, 'horizon_ended')
        with self.assertRaises(CaptureFailed):
            self.backend.evidence('c')
        await self.backend.aclose()
        self.assertTrue(self.backend.attempts['c'].cleanup_complete)
        self.assertEqual(self.recorder.metrics('c')['phase_status']['capture_control_window'], 'cancelled')

    async def test_kill_escalation_for_ignoring_owned_process(self):
        self.backend.start('c', self.plan('collect-hang', startup_s=3))
        attempt = self.backend.attempts['c']
        deadline = asyncio.get_running_loop().time() + 3
        while not (attempt.directory / 'command-hanging').exists():
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        self.backend.cancel('c', 'test_termination')
        await self.backend.aclose()
        self.assertTrue(self.backend.attempts['c'].kill_sent)
        self.assertTrue(all(p.poll() is not None for p in self.backend.attempts['c'].processes.values()))

    async def test_cancellation_during_final_cleanup_waits_for_owned_exit(self):
        self.backend.start('c', self.plan('collect-hang', cleanup_grace_s=.1))
        attempt = self.backend.attempts['c']
        deadline = asyncio.get_running_loop().time() + 3
        while not (attempt.directory / 'command-hanging').exists():
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        closing = asyncio.create_task(self.backend.aclose())
        await asyncio.sleep(.01)
        closing.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertTrue(attempt.cleanup_complete)
        self.assertTrue(attempt.kill_sent)
        self.assertFalse(self.backend._groups_alive(attempt))

    async def test_unrelated_process_survives_cleanup(self):
        import subprocess
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], start_new_session=True)
        try:
            self.backend.start('c', self.plan('no-start-ack', startup_s=.15))
            await self.until({'failed'})
            await self.backend.aclose()
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=2)

    async def test_launch_error_charges_budget(self):
        plan = self.plan(collect=('/nonexistent-profiler-command',))
        gate = EvidenceDecisionGate(self.backend, StoppingPolicy('stability_stop', PolicyConfig(max_bursts=1)), lambda _:None)
        gate.start_capture('c', lambda:self.backend.start('c', plan))
        result = gate.evaluate('w')
        self.assertEqual(result.status, 'capture_failed')
        self.assertEqual(result.decision.reason, 'budget_exhausted')

    async def test_fresh_directories_and_duplicate_ids(self):
        self.assertEqual(await self.run_capture(), 'ready')
        await self.backend.aclose()
        with self.assertRaises(ValueError):
            self.backend.start('c', self.plan())
        self.assertEqual(await self.run_capture(identity='other'), 'ready')
        self.assertNotEqual(self.backend.attempts['c'].directory, self.backend.attempts['other'].directory)
        self.assertNotEqual(self.backend.attempts['c'].token, self.backend.attempts['other'].token)

    async def test_symlink_artifact_rejected(self):
        self.backend.start('c', self.plan())
        a = self.backend.attempts['c']
        (a.directory / 'test').symlink_to(a.directory / 'plan.json')
        with self.assertRaises(ValueError):
            self.backend._bytes(a, 'test')

    async def test_controller_waits_for_cleanup_without_spending_attempt(self):
        # Kill escalation may outlive the failure decision; the next capture
        # must wait instead of being counted as a failed launch during cleanup.
        from experiments.tracing.controller import ControllerConfig, StreamingController
        from experiments.tracing.windows import CheapWindow, HealthyBaseline
        controller = StreamingController(self.backend, HealthyBaseline(100, 'fixture'), lambda _:None,
            lambda identity, window:self.backend.start(identity, self.plan('collect-hang', startup_s=.15)),
            ControllerConfig(policy_config=PolicyConfig(max_bursts=2), startup_timeout_s=1, evidence_timeout_s=2))
        start = self.clock.now_ns()
        await asyncio.sleep(.001)
        now = self.clock.now_ns()
        controller.on_window(CheapWindow('w', start, now, now, self.clock.domain, 200, 95, 1))
        deadline = asyncio.get_running_loop().time() + 4
        while controller.state != 'monitoring':
            controller.tick()
            if controller.state == 'suspicious' and controller.gate.pending is None:
                self.assertIsNotNone(controller.next_wakeup_ns())
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        controller.finish()
        self.assertEqual(len(self.backend.attempts), 2)
        self.assertEqual(len(controller.episodes[0].attempts), 2)
        self.assertFalse(any(e.name == 'attempt_start_failed' for e in self.recorder.events))


if __name__ == '__main__':
    unittest.main()
