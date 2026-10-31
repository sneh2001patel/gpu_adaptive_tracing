"""Policy mechanics and replay integration tests without GPU dependencies."""

import argparse
import csv
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "archive" / "icse_2026" / "RQ4" / "scripts"))
import analyze_policies as replay
from experiments.tracing.policies import POLICIES, PolicyConfig, PolicyEvidence, StoppingPolicy

LABEL = "compute_bound"
OTHER = "mixed"


def evidence(index, label=LABEL, **changes):
    return replace(PolicyEvidence(str(index), label, f"capture-{index}", f"evidence-{index}",
                                  1.0, 20.0, False), **changes)


def args(**changes):
    values = dict(stability_windows=2, repeated_bursts=3, max_policy_bursts=6,
                  recovery_windows=2, recovery_latency_ratio=1.1, recovery_gpu_util=60,
                  default_window_seconds=10, mode="automatic")
    return argparse.Namespace(**{**values, **changes})


class PolicyTests(unittest.TestCase):
    def test_only_five_distinct_policies(self):
        self.assertEqual(len(POLICIES), 5)
        self.assertNotIn("marginal_utility_stop", POLICIES)

    def test_mu_is_ss_two_even_when_general_ss_uses_three(self):
        mu = StoppingPolicy("marginal_utility_stop", PolicyConfig(stability_windows=3))
        ss = StoppingPolicy("stability_stop", PolicyConfig(stability_windows=2))
        for i in range(2):
            self.assertEqual(mu.observe(evidence(i)), ss.observe(evidence(i)))
        self.assertEqual(mu.terminal.reason, "diagnosis_stable")

    def test_mu_alias_matches_ss_on_label_sequences(self):
        for seq in itertools.product((LABEL, OTHER, None, "unknown_gpu_cause"), repeat=4):
            engines = [StoppingPolicy(name, PolicyConfig()) for name in ("marginal_utility_stop", "stability_stop")]
            for index, label in enumerate(seq):
                self.assertEqual(engines[0].observe(evidence(index, label)), engines[1].observe(evidence(index, label)))

    def test_nonconcrete_labels_never_satisfy_stability(self):
        for label in (None, "", "unknown_gpu_cause", "vllm_latency_regression_unknown_gpu_cause",
                      "healthy_or_not_suspicious", "vllm_healthy", "possible_memory_pressure", "invented"):
            engine = StoppingPolicy("stability_stop", PolicyConfig())
            for i in range(2):
                decision = engine.observe(evidence(i, label))
                self.assertFalse(decision.stop)
                self.assertEqual(decision.diagnosis_streak, 0)

    def test_unknown_resets_consecutive_streak(self):
        engine = StoppingPolicy("stability_stop", PolicyConfig())
        for i, label in enumerate((LABEL, None, LABEL)):
            self.assertFalse(engine.observe(evidence(i, label)).stop)
        self.assertEqual(engine.observe(evidence(3)).reason, "diagnosis_stable")

    def test_cached_evidence_does_not_increment_streak(self):
        engine = StoppingPolicy("stability_stop", PolicyConfig())
        engine.observe(evidence(0))
        decision = engine.observe(evidence(1, diagnosis_evidence_id="evidence-0"))
        self.assertFalse(decision.stop)
        self.assertEqual(decision.diagnosis_streak, 0)
        self.assertFalse(engine.observe(evidence(2)).stop)

    def test_missing_new_diagnosis_resets_streak(self):
        engine = StoppingPolicy("stability_stop", PolicyConfig())
        engine.observe(evidence(0))
        self.assertEqual(engine.observe(evidence(1, diagnosis_evidence_id=None)).diagnosis_streak, 0)

    def test_recovery_requires_valid_observed_metrics(self):
        for field, values in (("latency_ratio", (None, 0, -1, float("nan"), float("inf"))),
                              ("gpu_util", (None, -1, 101, float("nan"))),
                              ("suspicious", (None, True))):
            for value in values:
                with self.subTest(field=field, value=value):
                    engine = StoppingPolicy("counter_recovery_stop", PolicyConfig())
                    for i in range(2):
                        self.assertFalse(engine.observe(evidence(i, **{field: value})).stop)

    def test_zero_gpu_is_valid_recovery_and_requires_two_windows(self):
        engine = StoppingPolicy("counter_recovery_stop", PolicyConfig())
        self.assertFalse(engine.observe(evidence(0, gpu_util=0)).stop)
        self.assertEqual(engine.observe(evidence(1, gpu_util=0)).reason, "counters_recovered")

    def test_recovery_gap_resets_streak(self):
        engine = StoppingPolicy("counter_recovery_stop", PolicyConfig())
        for i, gpu in enumerate((20, None, 20)):
            self.assertFalse(engine.observe(evidence(i, gpu_util=gpu)).stop)
        self.assertTrue(engine.observe(evidence(3)).stop)

    def test_hybrid_needs_both_stability_and_recovery(self):
        engine = StoppingPolicy("hybrid_stop", PolicyConfig())
        engine.observe(evidence(0, gpu_util=90))
        self.assertFalse(engine.observe(evidence(1, gpu_util=90)).stop)
        self.assertFalse(engine.observe(evidence(2)).stop)
        self.assertEqual(engine.observe(evidence(3)).reason, "stable_and_recovered")

    def test_every_policy_obeys_budget_even_when_target_is_later(self):
        for name in POLICIES:
            engine = StoppingPolicy(name, PolicyConfig(max_bursts=2, repeated_bursts=8, stability_windows=3))
            for i in range(10):
                decision = engine.observe(evidence(i, None, gpu_util=None))
                self.assertLessEqual(decision.bursts, 2)
            if name != "fixed_burst":
                self.assertEqual(decision.reason, "budget_exhausted")
                self.assertFalse(decision.policy_condition_met)
            self.assertFalse(engine.can_capture)

    def test_condition_on_last_allowed_burst_is_valid(self):
        engine = StoppingPolicy("stability_stop", PolicyConfig(max_bursts=2))
        engine.observe(evidence(0))
        self.assertEqual(engine.observe(evidence(1)).reason, "diagnosis_stable")

    def test_cheap_windows_and_duplicate_capture_ids_do_not_spend_budget(self):
        engine = StoppingPolicy("repeated_fixed_burst", PolicyConfig())
        self.assertEqual(engine.observe(evidence(0, capture_id=None)).bursts, 0)
        self.assertEqual(engine.observe(evidence(1)).bursts, 1)
        self.assertEqual(engine.observe(evidence(2, capture_id="capture-1")).bursts, 1)

    def test_duplicate_window_cannot_fake_sustained_recovery(self):
        engine = StoppingPolicy("counter_recovery_stop", PolicyConfig())
        engine.observe(evidence(0))
        with self.assertRaises(ValueError):
            engine.observe(evidence(0))

    def test_horizon_and_budget_are_not_successful_conditions(self):
        engine = StoppingPolicy("stability_stop", PolicyConfig())
        engine.observe(evidence(0))
        self.assertEqual(engine.finish().reason, "horizon_ended")
        self.assertFalse(engine.finish().policy_condition_met)
        self.assertEqual(StoppingPolicy("stability_stop", PolicyConfig()).finish().bursts, 0)

    def test_invalid_configs_fail_before_running(self):
        for change in ({"max_bursts": 0}, {"stability_windows": 1}, {"recovery_windows": -1},
                       {"repeated_bursts": 2.5}, {"recovery_gpu_util": 101},
                       {"recovery_latency_ratio": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                PolicyConfig(**change)


class ReplayTests(unittest.TestCase):
    def row(self, i, label="vllm_queue_pressure", **changes):
        return {"window_id": i, "diagnosis_label": label, "trigger_trace": 1,
                "controller_state": "suspicious", "duration_s": 10,
                "latency_ratio_vs_baseline": 1.0, "gpu_util_percent_mean": 20, **changes}

    def test_missing_or_malformed_metrics_do_not_imply_recovery(self):
        for row in ({}, {"trigger_trace": 0}, {"trigger_trace": 0, "latency_ratio_vs_baseline": "bad",
                    "gpu_util_percent_mean": ""}):
            self.assertFalse(replay.recovered(row, args()))

    def test_full_timeline_preserves_unknown_gap(self):
        rows = [self.row(0), self.row(1, "unknown_gpu_cause", trigger_trace=0, controller_state="idle"), self.row(2)]
        result = replay.run_policy(rows, [rows[0], rows[2]], "stability_stop", "queue_pressure", "0", args())
        self.assertEqual(result["stop_reason"], "horizon_ended")
        self.assertEqual(result["diagnosis_streak_at_stop"], 1)
        self.assertEqual(result["successful_stop"], 0)

    def test_correct_then_wrong_stop_is_premature(self):
        rows = [self.row(0), self.row(1, "vllm_long_prompt"), self.row(2, "vllm_long_prompt")]
        result = replay.run_policy(rows, rows, "stability_stop", "queue_pressure", "0", args())
        self.assertEqual(result["ever_correct"], 1)
        self.assertEqual(result["premature_stop"], 1)

    def test_healthy_stream_never_activates(self):
        rows = [self.row(0, trigger_trace=0, controller_state="idle")]
        result = replay.run_policy(rows, rows, "fixed_burst", "healthy", "0", args())
        self.assertEqual(result["selected_windows"], 0)
        self.assertEqual(result["stop_reason"], "no_anomaly")

    def test_replay_matches_incremental_engine(self):
        rows = [self.row(i, label) for i, label in enumerate(("unknown_gpu_cause", LABEL, LABEL))]
        index, decision = replay.replay_policy(rows, "stability_stop", args())
        engine = StoppingPolicy("stability_stop", replay.config_from_args(args()))
        for i, row in enumerate(rows[:index + 1]):
            live_decision = engine.observe(replay.evidence_from_row(row, i))
        self.assertEqual(decision, live_decision)

    def test_cli_outputs_only_distinct_policies_and_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "queue_pressure_seed0" / "automatic"
            source.mkdir(parents=True)
            rows = [self.row(i, "unknown_gpu_cause") for i in range(8)]
            with (source / "queue_pressure_windows_1.csv").open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            completed = subprocess.run([sys.executable, str(ROOT / "archive/icse_2026/RQ4/scripts/analyze_policies.py"),
                "--input-root", str(root), "--output-dir", str(root / "out"), "--max-policy-bursts", "2"],
                text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(next((root / "out").glob("*.json")).read_text())
            self.assertEqual(len(payload["policies"]), 5)
            with next((root / "out").glob("*detail*.csv")).open() as handle:
                details = list(csv.DictReader(handle))
            self.assertTrue(all(int(row["selected_windows"]) <= 2 for row in details))
            self.assertTrue(all(row["successful_stop"] == "0" for row in details))


if __name__ == "__main__":
    unittest.main()
