"""Timing, failure, and evidence-readiness behavior using virtual time only."""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.tracing.evidence_gate import EvidenceDecisionGate
from experiments.tracing.policies import PolicyConfig, StoppingPolicy
from experiments.tracing.profiler import CaptureFailed, EvidenceNotReady, FakeCapturePlan, FakeProfilerBackend
from experiments.tracing.timing import ManualClock, MonotonicClock, TimingRecorder


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.recorder = TimingRecorder(self.clock, provenance="synthetic_simulation")

    def test_real_clock_is_monotonic_and_domains_are_unique(self):
        clock = MonotonicClock()
        self.assertLessEqual(clock.now_ns(), clock.now_ns())
        self.assertNotEqual(clock.domain, MonotonicClock().domain)

    def test_manual_clock_rejects_backward_and_invalid_time(self):
        self.clock.advance(2)
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.clock.advance(value)
        with self.assertRaises(ValueError):
            self.clock.advance_to(1)

    def test_missing_and_unfinished_phases_remain_unknown(self):
        self.recorder.begin("stats_command", "c")
        self.clock.advance(2)
        metrics = self.recorder.metrics("c")
        self.assertIsNone(metrics["stats_command_s"])
        self.assertIsNone(metrics["capture_active_s"])
        self.assertIsNone(metrics["lifecycle_total_s"])

    def test_phase_order_and_duplicates_are_rejected(self):
        with self.assertRaises(ValueError):
            self.recorder.end("summary_parse", "c")
        self.recorder.begin("summary_parse", "c")
        with self.assertRaises(ValueError):
            self.recorder.begin("summary_parse", "c")
        self.recorder.end("summary_parse", "c")
        with self.assertRaises(ValueError):
            self.recorder.end("summary_parse", "c")

    def test_failed_phase_has_cost_but_explicit_failure_status(self):
        self.recorder.begin("server_startup", "c")
        self.clock.advance(2)
        self.recorder.end("server_startup", "c", status="failed")
        metrics = self.recorder.metrics("c")
        self.assertEqual(metrics["server_startup_s"], 2)
        self.assertEqual(metrics["phase_status"]["server_startup"], "failed")

    def test_capture_duration_uses_interval_union(self):
        self.clock.advance(10)
        for start, end in ((0, 4), (2, 6), (8, 9)):
            self.recorder.confirm_capture_interval("c", start * 10**9, end * 10**9,
                                                   clock_domain=self.clock.domain)
        self.assertEqual(self.recorder.metrics("c")["capture_active_s"], 7)

    def test_cross_domain_and_future_capture_boundaries_are_rejected(self):
        for domain, end in (("other-process", 0), (self.clock.domain, 1)):
            with self.assertRaises(ValueError):
                self.recorder.confirm_capture_interval("c", 0, end, clock_domain=domain)

    def test_jsonl_preserves_nulls_and_monotonic_event_order(self):
        self.recorder.begin("stats_command", "c")
        self.clock.advance(1)
        self.recorder.end("stats_command", "c")
        events = [json.loads(line) for line in self.recorder.jsonl().splitlines()]
        self.assertEqual([e["sequence"] for e in events], [0, 1])
        self.assertLess(events[0]["timestamp_ns"], events[1]["timestamp_ns"])
        self.assertIsNone(events[0]["status"])


class FakeProfilerTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.recorder = TimingRecorder(self.clock, provenance="synthetic_simulation")
        self.backend = FakeProfilerBackend(self.recorder)
        self.classifier = Mock(return_value="compute_bound")
        self.policy = StoppingPolicy("stability_stop", PolicyConfig(max_bursts=2))
        self.gate = EvidenceDecisionGate(self.backend, self.policy, self.classifier)

    def start(self, capture_id="c", **changes):
        plan = FakeCapturePlan(**changes)
        self.gate.start_capture(capture_id, lambda: self.backend.start(capture_id, plan))

    def due(self, capture_id="c"):
        self.clock.advance_to(self.backend.next_deadline_ns(capture_id))
        return self.backend.poll(capture_id)

    def ready(self, capture_id="c", **changes):
        self.start(capture_id, **changes)
        self.due(capture_id)
        self.clock.advance(10)
        self.backend.stop(capture_id)
        while self.backend.state(capture_id) not in {"ready", "failed"}:
            self.due(capture_id)

    def assert_not_ready(self, state):
        self.assertEqual(self.backend.state("c"), state)
        with self.assertRaises(EvidenceNotReady):
            self.gate.evaluate("window")
        self.classifier.assert_not_called()
        self.assertEqual(len(self.policy.capture_ids), 0)
        self.assertEqual(self.policy.window_ids, set())

    def test_every_preparse_stage_withholds_evidence_and_policy_mutation(self):
        self.start()
        self.assert_not_ready("starting")
        self.due()
        self.assert_not_ready("capturing")
        self.backend.stop("c")
        self.assert_not_ready("finalizing")
        self.due()
        self.assert_not_ready("exporting")
        self.due()
        self.assert_not_ready("parsing")
        self.due()
        self.assertEqual(self.gate.evaluate("window").status, "ok")
        self.classifier.assert_called_once()

    def test_phase_costs_are_separate_without_double_counting(self):
        self.ready()
        metrics = self.recorder.metrics("c")
        self.assertEqual(metrics["server_startup_s"], 1)
        self.assertEqual(metrics["capture_control_window_s"], 10)
        self.assertEqual(metrics["report_finalization_s"], 2)
        self.assertEqual(metrics["profile_process_wall_s"], 13)
        self.assertEqual(metrics["stats_command_s"], 3)
        self.assertEqual(metrics["summary_parse_s"], 0.5)
        self.assertEqual(metrics["evidence_collection_s"], 16.5)
        self.assertIsNone(metrics["capture_active_s"])
        self.assertIsNone(metrics["lifecycle_total_s"])

    def test_capture_boundaries_are_only_synthetic_if_opted_in(self):
        self.ready(confirm_capture=True)
        metrics = self.recorder.metrics("c")
        self.assertEqual(metrics["capture_active_s"], 10)
        self.assertEqual(metrics["timing_provenance"], "synthetic_simulation")

    def test_late_poll_never_backdates_evidence_availability(self):
        self.start()
        self.clock.advance(50)
        self.backend.poll("c")
        self.backend.stop("c")
        for _ in range(3):
            self.clock.advance(50)
            self.backend.poll("c")
        self.assertEqual(self.backend.evidence("c").ready_at_ns, self.clock.now_ns())
        self.assertEqual(self.recorder.metrics("c")["server_startup_s"], 50)

    def test_classifier_and_decision_follow_evidence_ready(self):
        self.ready()
        evidence_ready = self.backend.evidence("c").ready_at_ns
        self.classifier.side_effect = lambda payload: (self.clock.advance(0.25), "compute_bound")[1]
        result = self.gate.evaluate("w")
        self.assertEqual(result.evidence_ready_at_ns, evidence_ready)
        self.assertEqual(result.decision_ready_at_ns, evidence_ready + 250_000_000)
        self.assertEqual(self.recorder.metrics("c")["diagnosis_compute_s"], 0.25)
        self.assertEqual(self.policy.diagnosis_streak, 1)

    def test_pipeline_failures_never_produce_ready_evidence(self):
        for stage in ("startup", "stop", "finalization", "stats", "parse"):
            with self.subTest(stage=stage):
                clock = ManualClock()
                recorder = TimingRecorder(clock, provenance="synthetic_simulation")
                backend = FakeProfilerBackend(recorder)
                backend.start("failure", FakeCapturePlan(fail_at=stage))
                while backend.state("failure") not in {"ready", "failed"}:
                    if backend.state("failure") == "capturing":
                        backend.stop("failure")
                    else:
                        clock.advance_to(backend.next_deadline_ns("failure"))
                        backend.poll("failure")
                with self.assertRaises(CaptureFailed):
                    backend.evidence("failure")
                self.assertIsNone(recorder.metrics("failure")["evidence_ready_at_ns"])

    def test_failed_attempts_consume_budget_and_cannot_stabilize(self):
        for index in range(2):
            capture_id = str(index)
            self.start(capture_id, fail_at="startup")
            self.due(capture_id)
            result = self.gate.evaluate(f"w{index}")
            self.assertEqual(result.status, "capture_failed")
            self.assertEqual(result.decision.bursts, index + 1)
            self.assertEqual(result.decision.diagnosis_streak, 0)
        self.assertEqual(result.decision.reason, "budget_exhausted")
        with self.assertRaises(RuntimeError):
            self.start("third")
        self.classifier.assert_not_called()

    def test_launch_exception_is_an_explicit_charged_failure(self):
        def fail():
            raise OSError("simulated launch failure")
        self.gate.start_capture("launch", fail)
        result = self.gate.evaluate("w")
        self.assertEqual(result.status, "capture_failed")
        self.assertEqual(result.decision.bursts, 1)

    def test_classifier_failure_is_inconclusive_and_charged(self):
        self.ready()
        self.classifier.side_effect = ValueError("simulated classifier failure")
        result = self.gate.evaluate("w")
        self.assertEqual(result.status, "diagnosis_failed")
        self.assertIsNone(result.evidence_id)
        self.assertEqual(result.decision.bursts, 1)
        self.assertEqual(result.decision.diagnosis_streak, 0)

    def test_pending_and_consumed_attempts_cannot_be_reused(self):
        self.start()
        with self.assertRaises(RuntimeError):
            self.start("second")
        self.due()
        self.backend.stop("c")
        for _ in range(3):
            self.due()
        self.gate.evaluate("w")
        with self.assertRaises(RuntimeError):
            self.gate.evaluate("w2")
        with self.assertRaises(ValueError):
            self.start()

    def test_payload_mutation_cannot_rewrite_backend_evidence(self):
        self.ready(kernel_summary={"kernels": [1, 2]})
        copy = self.backend.evidence("c")
        copy.payload["kernels"].clear()
        self.assertEqual(self.backend.evidence("c").payload["kernels"], [1, 2])

    def test_future_and_foreign_clock_evidence_is_rejected(self):
        self.ready()
        original = self.backend.evidence("c")
        for change, error in (({"ready_at_ns": self.clock.now_ns() + 1}, EvidenceNotReady),
                              ({"clock_domain": "foreign"}, ValueError),
                              ({"provenance": "live"}, ValueError),
                              ({"capture_id": "other"}, ValueError)):
            with self.subTest(change=change):
                provider = Mock(wraps=self.backend)
                provider.recorder = self.recorder
                provider.evidence.return_value = replace(original, **change)
                gate = EvidenceDecisionGate(provider, self.policy, self.classifier)
                gate.start_capture("c", lambda: None)
                with self.assertRaises(error):
                    gate.evaluate("w")
        self.classifier.assert_not_called()

    def test_stop_before_start_ack_is_rejected(self):
        self.start()
        with self.assertRaises(ValueError):
            self.backend.stop("c")

    def test_fake_backend_cannot_be_labeled_live(self):
        with self.assertRaises(ValueError):
            FakeProfilerBackend(TimingRecorder(self.clock, provenance="live"))

    def test_zero_delay_stages_still_require_explicit_ordered_polls(self):
        self.start(startup_s=0, finalization_s=0, stats_s=0, parse_s=0)
        self.due()
        self.backend.stop("c")
        for state in ("exporting", "parsing", "ready"):
            self.assertEqual(self.backend.poll("c"), state)

    def test_two_ready_captures_reach_stability_and_stop_launches(self):
        for index in range(2):
            self.ready(str(index))
            result = self.gate.evaluate(str(index))
        self.assertEqual(result.decision.reason, "diagnosis_stable")
        with self.assertRaises(RuntimeError):
            self.start("third")

    def test_demo_cli_writes_synthetic_artifacts_with_null_capture_time(self):
        # Output remains inside experiments/; the temporary directory cleans itself.
        with tempfile.TemporaryDirectory(dir=ROOT / "experiments") as temp:
            result = subprocess.run([sys.executable, str(ROOT / "experiments/scripts/demo_fake_profiler.py"),
                                     "--output-dir", temp], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((Path(temp) / "results.json").read_text())
            self.assertFalse(payload["gpu_used"])
            self.assertEqual(payload["evidence_mode"], "synthetic_simulation")
            self.assertEqual(payload["decisions"][-1]["decision"]["reason"], "diagnosis_stable")
            self.assertTrue(all(row["capture_active_s"] is None for row in payload["timings"].values()))

    def test_cancellation_closes_each_pending_phase_without_late_evidence(self):
        for target in ("starting", "capturing", "finalizing", "exporting", "parsing"):
            with self.subTest(target=target):
                clock = ManualClock()
                recorder = TimingRecorder(clock, provenance="synthetic_simulation")
                backend = FakeProfilerBackend(recorder)
                backend.start("c", FakeCapturePlan())
                while backend.state("c") != target:
                    if backend.state("c") == "capturing":
                        backend.stop("c")
                    else:
                        clock.advance_to(backend.next_deadline_ns("c"))
                        backend.poll("c")
                backend.cancel("c", "synthetic_timeout")
                clock.advance(100)
                self.assertEqual(backend.poll("c"), "failed")
                with self.assertRaises(CaptureFailed):
                    backend.evidence("c")
                self.assertIsNone(recorder.metrics("c")["evidence_ready_at_ns"])


if __name__ == "__main__":
    unittest.main()
