"""Provisional cheap-evidence classifiers with no workload-truth inputs.

These heuristic scores are not probabilities or validated root-cause diagnoses.
Keep scenario names, expected labels, and workload configurations out of this
module. T2 classification and independent calibration remain revision work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


UNKNOWN = "vllm_latency_regression_unknown_gpu_cause"
CLASSIFIER_VERSION = "cheap_evidence_v2"


@dataclass(frozen=True)
class ServingObservation:
    latency_ratio: float | None
    gpu_util_mean: float | None
    memory_used_percent: float | None
    prompt_tokens_mean: float | None
    output_tokens_mean: float | None
    throughput_ratio: float | None
    observed_concurrency_mean: float | None


def diagnosis_scores(observation: ServingObservation) -> dict[str, float]:
    """Retain the existing heuristic weights, without truth-dependent boosts.

    Missing/invalid evidence abstains instead of becoming a healthy zero.
    Concurrency is measured from request lifetimes, not workload configuration.
    """
    values = tuple(vars(observation).values())
    if any(value is None or not math.isfinite(value) or value < 0 for value in values):
        return {}

    def clamp(value: float) -> float:
        return min(max(value, 0.0), 1.0)

    latency = clamp(observation.latency_ratio / 2.0)
    gpu = clamp(observation.gpu_util_mean / 100.0)
    memory = clamp((observation.memory_used_percent - 80.0) / 20.0)
    prompt = clamp((observation.prompt_tokens_mean - 800.0) / 1000.0)
    output = clamp((observation.output_tokens_mean - 120.0) / 400.0)
    concurrency = clamp((observation.observed_concurrency_mean - 1.0) / 23.0)
    throughput_drop = clamp(1.0 - observation.throughput_ratio)
    return {
        "vllm_healthy": max(0.0, 1.0 - max(latency, gpu, memory, throughput_drop)),
        "vllm_queue_pressure": 0.45 * concurrency + 0.35 * latency + 0.20 * throughput_drop,
        "vllm_long_prompt": 0.70 * prompt + 0.30 * latency,
        "vllm_long_output": 0.70 * output + 0.30 * latency,
        "vllm_compute_saturation": 0.75 * gpu + 0.25 * latency,
        "vllm_kv_cache_pressure": 0.45 * prompt + 0.35 * memory + 0.20 * latency,
    }


def classify_serving(observation: ServingObservation, *, suspicious: bool) -> dict[str, str | float]:
    scores = diagnosis_scores(observation)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_label, top_score = ordered[0] if ordered else ("", 0.0)
    runner_label, runner_score = ordered[1] if len(ordered) > 1 else ("", 0.0)
    ambiguity = ""
    if not ordered:
        label, ambiguity = UNKNOWN, "missing_or_invalid_cheap_evidence"
    elif not suspicious:
        label = "healthy_or_not_suspicious"
    elif top_label == "vllm_healthy" or math.isclose(top_score, runner_score):
        label, ambiguity = UNKNOWN, "cheap_evidence_does_not_resolve_anomaly"
    else:
        label = top_label
    return {
        "diagnosis_label": label,
        "diagnosis_top_candidate": top_label,
        "diagnosis_runner_up": runner_label,
        "diagnosis_confidence": scores.get(label, 0.0),
        "diagnosis_rank_margin": max(top_score - runner_score, 0.0),
        "diagnosis_ambiguity_reason": ambiguity,
        "diagnosis_source": CLASSIFIER_VERSION,
        "diagnosis_evidence_tier": "T0_T1",
        "diagnosis_score_kind": "heuristic_not_probability",
    }


def diagnose_microbenchmark(
    *, reasons: list[str], gpu_util_mean: float | None, mem_used_percent_mean: float | None,
) -> tuple[str, float, str]:
    """Cheap evidence cannot identify a GEMM/mixed workload by its name."""
    evidence = "|".join(reasons)
    if "high_operation_rate" in reasons:
        return "possible_launch_overhead_or_small_kernel", 0.35, evidence
    if "high_memory_use" in reasons and gpu_util_mean is not None and gpu_util_mean >= 60:
        return "mixed_compute_memory_pressure", 0.65, evidence
    if "high_gpu_util" in reasons or "latency_regression" in reasons:
        return "latency_regression_unknown_gpu_cause", 0.0, evidence
    if mem_used_percent_mean is not None and mem_used_percent_mean >= 50:
        return "possible_memory_pressure", 0.35, "moderate_memory_use"
    return "healthy_or_not_suspicious", 0.0, "no_trigger"
