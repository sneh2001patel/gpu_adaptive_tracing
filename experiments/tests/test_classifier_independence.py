"""CPU-only boundary and integration tests; no GPU dependencies required."""

import ast
import dataclasses
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / "archive" / "icse_2026" / "RQ1" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from evidence_classifier import (  # noqa: E402
    UNKNOWN, ServingObservation, classify_serving, diagnosis_scores,
)


class FakeProcess:
    def cpu_percent(self, interval=None):
        return 0.0

    def memory_info(self):
        return types.SimpleNamespace(rss=0)


class FakeSampler:
    def samples_between(self, start, end):
        return [{"gpu_util_percent": 95.0, "gpu_memory_used_percent": 40.0}]


def load_runners():
    # Replace hardware/process dependencies only during runner import. No GPU
    # calls are exercised; real aggregation and classifier code run unchanged.
    dependencies = {name: types.ModuleType(name) for name in ("psutil", "pynvml", "torch")}
    dependencies["psutil"].Process = FakeProcess
    with patch.dict(sys.modules, dependencies):
        return (importlib.import_module("run_vllm_smoke"),
                importlib.import_module("run_microbenchmarks"))


class ClassifierBoundaryTests(unittest.TestCase):
    def observation(self, **changes):
        return dataclasses.replace(ServingObservation(1.5, 95.0, 40.0, 100.0, 60.0, 1.0, 1.0), **changes)

    def test_interface_rejects_expected_label_and_scenario(self):
        for forbidden in ("expected_label", "scenario_name", "workload", "configured_concurrency"):
            with self.subTest(field=forbidden), self.assertRaises(TypeError):
                ServingObservation(**{**vars(self.observation()), forbidden: "compute_bound"})

    def test_classifier_has_no_truth_or_workload_import(self):
        tree = ast.parse((SCRIPTS / "evidence_classifier.py").read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(set(imports) & {"vllm_expected_labels", "run_vllm_smoke", "run_microbenchmarks"})
        self.assertFalse(any(isinstance(node, ast.Name) and node.id in {"EXPECTED_LABELS", "SCENARIOS"}
                             for node in ast.walk(tree)))

    def test_observed_evidence_changes_prediction(self):
        compute = classify_serving(self.observation(), suspicious=True)
        prompt = classify_serving(self.observation(gpu_util_mean=30, prompt_tokens_mean=2400), suspicious=True)
        self.assertEqual(compute["diagnosis_label"], "vllm_compute_saturation")
        self.assertEqual(prompt["diagnosis_label"], "vllm_long_prompt")
        self.assertEqual(compute["diagnosis_score_kind"], "heuristic_not_probability")

    def test_missing_and_invalid_features_abstain(self):
        for field in dataclasses.fields(ServingObservation):
            for value in (None, float("nan"), float("inf"), -1.0):
                with self.subTest(field=field.name, value=value):
                    result = classify_serving(self.observation(**{field.name: value}), suspicious=True)
                    self.assertEqual(result["diagnosis_label"], UNKNOWN)
                    self.assertEqual(result["diagnosis_confidence"], 0.0)

    def test_zero_throughput_is_not_replaced_with_baseline(self):
        baseline = diagnosis_scores(self.observation(throughput_ratio=1.0))
        stalled = diagnosis_scores(self.observation(throughput_ratio=0.0))
        self.assertGreater(stalled["vllm_queue_pressure"], baseline["vllm_queue_pressure"])


class RunnerIndependenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke, cls.micro = load_runners()

    def record(self, **changes):
        record = self.smoke.RequestRecord(
            0, "queue_pressure", "vllm_queue_pressure", 100.0, 101.0, 1000.0,
            1, 200, "", 100, 64, 60, 160,
        )
        return dataclasses.replace(record, **changes)

    def aggregate(self, records, name, config):
        args = types.SimpleNamespace(
            window_seconds=10.0, suspicious_latency_ratio=1.5, suspicious_gpu_util=60,
            queue_pressure_latency_ratio=1.25, queue_delay_pressure_ms=250,
            recovery_latency_ratio=1.1, recovery_gpu_util=60,
            throughput_recovery_ratio=0.95, queue_delay_recovery_ms=100,
        )
        return self.smoke.aggregate_windows(records, FakeSampler(), name, config, args)[0]

    def test_serving_predictions_ignore_truth_names_and_configuration(self):
        reference = self.aggregate([self.record()], "queue_pressure", self.smoke.SCENARIOS["queue_pressure"])
        other_record = self.record(scenario="renamed", workload_phase_label="deliberately_wrong")
        with patch.dict(self.smoke.EXPECTED_LABELS, {"renamed": "deliberately_wrong"}):
            changed = self.aggregate([other_record], "renamed", {
                "label": "another_wrong_label", "concurrency": 999, "max_tokens": 999,
            })
        self.assertNotEqual(reference["expected_label"], changed["expected_label"])
        self.assertEqual(reference["diagnosis_label"], "vllm_compute_saturation")
        for key in reference:
            if key.startswith("diagnosis_") or key in {"trigger_trace", "suspicion_reasons", "observed_concurrency_mean"}:
                self.assertEqual(reference[key], changed[key], key)

    def test_workload_configurations_no_longer_contain_expected_labels(self):
        self.assertTrue(all("label" not in config for config in self.smoke.SCENARIOS.values()))

    def test_final_completion_is_not_dropped(self):
        row = self.aggregate([self.record()], "queue_pressure", self.smoke.SCENARIOS["queue_pressure"])
        self.assertEqual(row["request_count"], 1)
        self.assertEqual(row["request_latency_mean_ms"], 1000.0)

    def test_concurrency_uses_observed_overlap(self):
        records = [self.record(start_ts=0, end_ts=2), self.record(start_ts=1, end_ts=3)]
        self.assertAlmostEqual(self.smoke.observed_concurrency_mean(records, 0, 3), 4 / 3)
        self.assertEqual(self.smoke.observed_concurrency_mean(records, 1, 2), 2)

    def test_microbenchmark_predictions_and_triggers_ignore_workload_names(self):
        args = types.SimpleNamespace(
            suspicious_gpu_util=60, suspicious_mem_percent=80,
            suspicious_launch_ops_per_s=100, suspicious_latency_ratio=1.5, suspicious_score=0.4,
        )
        for operations in (1, 200):
            rows = []
            for name in ("compute_bound", "mixed", "launch_overhead_or_small_kernel", "renamed"):
                window = self.micro.Window(0, 0, 1, name, "truth_" + name,
                                           [100.0], operations,
                                           [{"gpu_util_percent": 95, "gpu_memory_used_percent": 40}])
                rows.append(self.micro.classify_window(window, FakeProcess(), 100.0, args))
            for row in rows[1:]:
                for key in ("diagnosis_label", "diagnosis_confidence", "diagnosis_evidence",
                            "suspicion_score", "suspicion_reasons", "trigger_trace"):
                    self.assertEqual(rows[0][key], row[key], key)
            if operations == 1:
                self.assertEqual(rows[0]["diagnosis_label"], "latency_regression_unknown_gpu_cause")

    def test_microbenchmark_unknown_and_idle_reset_stability(self):
        args = types.SimpleNamespace(stability_stop_windows=2)
        for row in ({"trigger_trace": 1, "diagnosis_label": "latency_regression_unknown_gpu_cause"},
                    {"trigger_trace": 0, "diagnosis_label": "compute_bound"}):
            self.assertEqual(self.micro.update_stability_stop(row, "compute_bound", 1, "", args),
                             (None, 0, ""))

    def test_serving_unknown_evidence_does_not_start_stability_streak(self):
        class MissingSampler:
            def samples_between(self, start, end):
                return []
        with patch.object(FakeSampler, "samples_between", MissingSampler.samples_between):
            row = self.aggregate([self.record()], "queue_pressure", self.smoke.SCENARIOS["queue_pressure"])
        self.assertEqual(row["diagnosis_stability_streak"], 0)


if __name__ == "__main__":
    unittest.main()
