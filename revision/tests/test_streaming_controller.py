"""Chronological, CPU-only episode tests; no expected labels enter the controller."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.policies import PolicyConfig
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import ManualClock, TimingRecorder
from revision.tracing.windows import CheapWindow, HealthyBaseline


class Harness:
    def __init__(self, *, config=None, summaries=None, plan_changes=None, launch_fails=False):
        self.clock = ManualClock()
        self.recorder = TimingRecorder(self.clock, provenance="synthetic_simulation")
        self.backend = FakeProfilerBackend(self.recorder)
        self.calls = 0

        def start(capture_id, window):
            index = self.calls
            self.calls += 1
            if launch_fails:
                raise OSError("synthetic launch failure")
            summary = summaries[min(index, len(summaries) - 1)] if summaries else {"top_kernel_name": "gemm"}
            self.backend.start(capture_id, FakeCapturePlan(startup_s=0.1, finalization_s=0.1,
                stats_s=0.1, parse_s=0.1, kernel_summary=summary, **(plan_changes or {})))

        def classify(summary):
            name = summary.get("top_kernel_name")
            return {"gemm": "compute_bound", "prefill": "vllm_long_prompt"}.get(name)

        self.controller = StreamingController(self.backend, HealthyBaseline(100, "synthetic-healthy-calibration"),
                                               classify, start, config or ControllerConfig(burst_s=0.5, cooldown_s=0))

    def advance(self, target, *, include_equal=True):
        target_ns = round(target * 1e9)
        for _ in range(1000):
            wake = self.controller.next_wakeup_ns()
            if wake is None or wake > target_ns or (not include_equal and wake == target_ns):
                self.clock.advance_to(target_ns)
                return
            self.clock.advance_to(wake)
            self.controller.tick()
        raise AssertionError("Controller failed to make scheduled progress")

    def send(self, end, latency=200, gpu=95, throughput=1):
        self.advance(end, include_equal=False)
        previous = self.controller.latest
        window = CheapWindow(f"w{len(self.controller._window_ids)}", previous.end_ns if previous else 0,
                             round(end * 1e9), round(end * 1e9), self.clock.domain,
                             latency, gpu, 10 if latency is not None else 0, throughput)
        self.controller.on_window(window)


class StreamingTests(unittest.TestCase):
    def test_cpu_simulation_is_not_a_hardware_baseline(self):
        h = Harness()
        self.assertEqual(h.controller.snapshot()["evidence_mode"], "synthetic_simulation")
        self.assertEqual(h.controller.baseline.p95_latency_ms, 100)
        self.assertEqual(h.calls, 0)

    def test_healthy_stream_never_launches_profiler(self):
        h = Harness()
        for i in range(1, 4):
            h.send(i, latency=100, gpu=20)
        h.controller.finish()
        self.assertEqual(h.calls, 0)
        self.assertEqual(h.controller.episodes, [])

    def test_missing_metrics_do_not_establish_health_or_recovery(self):
        h = Harness()
        h.send(1, latency=None, gpu=None)
        self.assertIsNone(h.controller.suspicious)
        h.send(2)
        h.advance(5)
        h.send(6, latency=None, gpu=None)
        self.assertEqual(h.controller.episodes[0].recovery_streak, 0)
        self.assertIsNone(h.controller.episodes[0].ended_at_ns)

    def test_sustained_gpu_trigger_requires_elevated_latency(self):
        h = Harness()
        h.send(1, latency=120)
        self.assertEqual(h.calls, 0)
        h.send(2, latency=120)
        self.assertEqual(h.calls, 1)

    def test_stable_diagnosis_stops_capture_before_workload_recovers(self):
        h = Harness()
        h.send(1)
        h.advance(4)
        episode = h.controller.episodes[0]
        self.assertEqual(len(episode.attempts), 2)
        self.assertEqual(episode.stop_reason, "diagnosis_stable")
        self.assertEqual(h.controller.state, "monitoring")
        self.assertIsNone(episode.ended_at_ns)
        h.send(5, latency=100, gpu=20)
        h.send(6, latency=100, gpu=20)
        self.assertEqual(episode.end_reason, "workload_recovered")
        self.assertEqual(h.controller.state, "idle")

    def test_unknown_first_capture_requires_two_subsequent_concrete_observations(self):
        h = Harness(summaries=[{}, {"top_kernel_name": "gemm"}])
        h.send(1)
        h.advance(5)
        episode = h.controller.episodes[0]
        self.assertEqual(len(episode.attempts), 3)
        self.assertEqual([d.decision.diagnosis_streak for d in episode.decisions], [0, 1, 2])

    def test_changing_kernel_evidence_resets_stability(self):
        h = Harness(summaries=[{"top_kernel_name": "gemm"}, {"top_kernel_name": "prefill"}])
        h.send(1)
        h.advance(5)
        episode = h.controller.episodes[0]
        self.assertEqual(len(episode.attempts), 3)
        self.assertEqual(episode.last_diagnosis, "vllm_long_prompt")

    def test_unknown_only_stream_exhausts_budget_inconclusively(self):
        h = Harness(config=ControllerConfig(burst_s=0.5, policy_config=PolicyConfig(max_bursts=2)), summaries=[{}])
        h.send(1)
        h.advance(5)
        episode = h.controller.episodes[0]
        self.assertEqual(episode.stop_reason, "budget_exhausted")
        self.assertIsNone(episode.last_diagnosis)
        self.assertFalse(episode.decisions[-1].decision.policy_condition_met)

    def test_cheap_windows_continue_arriving_while_parsing(self):
        h = Harness()
        h.send(1)
        h.send(1.75, latency=100, gpu=20)
        self.assertEqual(h.controller.state, "evaluating")
        self.assertEqual(len(h.controller.episodes[0].decisions), 0)
        self.assertEqual(h.controller.latest.window_id, "w1")
        h.advance(2)
        self.assertEqual(len(h.controller.episodes[0].decisions), 1)

    def test_recovery_counts_unique_cheap_windows_not_capture_decisions(self):
        h = Harness(config=ControllerConfig(policy="counter_recovery_stop", burst_s=0.5,
                    cooldown_s=0, policy_config=PolicyConfig(max_bursts=10)))
        h.send(1)
        h.send(1.2, latency=100, gpu=20)
        h.advance(4)
        episode = h.controller.episodes[0]
        self.assertTrue(all(d.decision.recovery_streak == 1 for d in episode.decisions))
        self.assertIsNone(episode.stop_reason)
        h.send(4.1, latency=100, gpu=20)
        h.advance(5)
        self.assertEqual(episode.stop_reason, "counters_recovered")
        self.assertEqual(episode.end_reason, "workload_recovered")

    def test_recovery_gap_between_captures_is_not_skipped(self):
        h = Harness(config=ControllerConfig(policy="counter_recovery_stop", burst_s=0.5, cooldown_s=0))
        h.send(1)
        h.send(1.1, latency=100, gpu=20)
        h.send(1.2)
        h.send(1.3, latency=100, gpu=20)
        h.advance(2)
        self.assertEqual(h.controller.episodes[0].decisions[0].decision.recovery_streak, 1)
        self.assertIsNone(h.controller.episodes[0].stop_reason)

    def test_persistent_unchanged_suspicion_does_not_reactivate(self):
        h = Harness()
        h.send(1)
        h.advance(4)
        h.send(5)
        h.send(6)
        self.assertEqual(h.calls, 2)
        self.assertEqual(h.controller.episodes[0].reactivation_attempts, 0)

    def test_reactivation_can_be_disabled_for_fixed_cost_policy_comparison(self):
        h = Harness(config=ControllerConfig(policy="fixed_burst", burst_s=0.5,
            cooldown_s=0, reactivation_enabled=False))
        h.send(1)
        h.advance(3)
        self.assertEqual(h.calls, 1)
        h.send(4, latency=500, gpu=50, throughput=10)
        h.advance(7)
        self.assertEqual(h.calls, 1)
        self.assertEqual(h.controller.episodes[0].reactivation_attempts, 0)
        self.assertEqual(h.controller.state, "monitoring")

    def test_changed_evidence_reactivates_within_same_episode_and_budget(self):
        h = Harness(config=ControllerConfig(burst_s=0.5, cooldown_s=0.5,
                    policy_config=PolicyConfig(max_bursts=4)))
        h.send(1)
        h.advance(4)
        h.send(5, latency=400)
        h.advance(8)
        h.send(9, latency=800)
        h.advance(12)
        self.assertEqual(len(h.controller.episodes), 1)
        self.assertEqual(h.controller.episodes[0].reactivation_attempts, 1)
        self.assertEqual(h.calls, 4)

    def test_new_episode_resets_budget_only_after_recovery(self):
        h = Harness()
        h.send(1)
        h.advance(4)
        h.send(5, latency=100, gpu=20)
        h.send(6, latency=100, gpu=20)
        h.send(7)
        h.advance(10)
        self.assertEqual([len(e.attempts) for e in h.controller.episodes], [2, 2])

    def test_reactivation_respects_cooldown(self):
        h = Harness(config=ControllerConfig(burst_s=0.5, cooldown_s=10))
        h.send(1)
        h.advance(4)
        h.send(5, latency=400)
        self.assertEqual(h.calls, 2)

    def test_launch_failures_spend_budget_without_deadlock(self):
        h = Harness(launch_fails=True, config=ControllerConfig(policy_config=PolicyConfig(max_bursts=2)))
        h.send(1)
        h.advance(2)
        self.assertEqual(h.calls, 2)
        self.assertEqual(h.controller.episodes[0].stop_reason, "budget_exhausted")

    def test_startup_timeout_cancels_without_ready_evidence(self):
        h = Harness(config=ControllerConfig(startup_timeout_s=0.05,
                    policy_config=PolicyConfig(max_bursts=2)))
        h.send(1)
        h.advance(2)
        episode = h.controller.episodes[0]
        self.assertEqual(episode.stop_reason, "budget_exhausted")
        self.assertTrue(all(d.evidence_ready_at_ns is None for d in episode.decisions))
        self.assertTrue(all("startup_timeout" in d.error for d in episode.decisions))

    def test_total_evidence_timeout_cancels_slow_export(self):
        h = Harness(config=ControllerConfig(burst_s=0.5, evidence_timeout_s=0.75,
                    policy_config=PolicyConfig(max_bursts=1)))
        h.send(1)
        h.advance(3)
        result = h.controller.episodes[0].decisions[0]
        self.assertIn("evidence_timeout", result.error)
        self.assertEqual(result.status, "capture_failed")

    def test_stream_end_cancels_pending_capture_and_closes_episode(self):
        h = Harness()
        h.send(1)
        h.advance(1.2)
        capture_id = h.controller.gate.pending
        h.controller.finish()
        self.assertEqual(h.backend.state(capture_id), "failed")
        self.assertEqual(h.controller.episodes[0].end_reason, "horizon_ended")
        self.assertEqual(h.calls, 1)
        self.assertTrue(h.controller.finished)
        h.controller.finish()
        with self.assertRaises(RuntimeError):
            h.send(2)

    def test_out_of_order_duplicate_future_and_foreign_windows_are_rejected(self):
        h = Harness()
        h.send(1, latency=100, gpu=20)
        original = h.controller.latest
        with self.assertRaises(ValueError):
            h.controller.on_window(original)
        for change in ({"clock_domain": "foreign"}, {"available_at_ns": 2_000_000_000}):
            from dataclasses import replace
            window = replace(original, window_id="next", **change)
            with self.assertRaises(ValueError):
                h.controller.on_window(window)
        self.assertEqual(h.calls, 0)

    def test_expected_labels_are_not_inputs(self):
        with self.assertRaises(TypeError):
            CheapWindow("w", 0, 1, 1, "domain", 100, 20, 1, expected_label="compute_bound")
        with self.assertRaises(ValueError):
            HealthyBaseline(0, "")

    def test_decisions_and_json_output_have_available_evidence_only(self):
        h = Harness()
        h.send(1)
        h.advance(4)
        h.controller.finish()
        payload = json.loads(json.dumps(h.controller.snapshot(), allow_nan=False))
        for episode in payload["episodes"]:
            for result in episode["decisions"]:
                self.assertLessEqual(result["evidence_ready_at_ns"], result["decision_ready_at_ns"])
        self.assertTrue(all(m["capture_active_s"] is None for m in payload["capture_timings"].values()))
        self.assertEqual(len(h.controller.jsonl().splitlines()), len(h.controller.events))

    def test_streaming_demo_cli_is_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "revision") as temp:
            result = subprocess.run([sys.executable, str(ROOT / "revision/scripts/demo_streaming_controller.py"),
                                     "--scenario", "ambiguous_first", "--output-dir", temp],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((Path(temp) / "results.json").read_text())
            self.assertFalse(payload["gpu_used"])
            self.assertEqual(payload["cpu_role"], "simulation_execution_not_experimental_baseline")
            self.assertEqual(len(payload["episodes"][0]["attempts"]), 3)
            self.assertEqual(payload["episodes"][0]["stop_reason"], "diagnosis_stable")
            self.assertEqual(payload["episodes"][0]["end_reason"], "workload_recovered")


if __name__ == "__main__":
    unittest.main()
