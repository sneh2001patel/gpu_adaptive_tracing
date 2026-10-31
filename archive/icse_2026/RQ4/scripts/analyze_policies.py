#!/usr/bin/env python3
"""Replay vLLM window evidence under candidate RQ4 tracing policies."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


# Resolve the shared engine from both direct-script and imported entry points.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from revision.tracing.policies import (  # noqa: E402
    POLICIES, POLICY_VERSION, PolicyConfig, PolicyEvidence, StoppingPolicy,
    is_concrete_label, recovery_observed,
)


EXPECTED_LABELS = {
    "healthy": "vllm_healthy",
    "queue_pressure": "vllm_queue_pressure",
    "long_prompt": "vllm_long_prompt",
    "long_output": "vllm_long_output",
    "compute_saturation": "vllm_compute_saturation",
    "kv_cache_pressure": "vllm_kv_cache_pressure",
}


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def safe_percent(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator * 100.0


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def ci95(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * stdev(values) / (len(values) ** 0.5)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def load_windows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows.sort(key=lambda row: as_int(row.get("window_id")))
    return rows


def is_suspicious(row: dict[str, Any]) -> bool:
    return suspicion_observed(row) is True


def diagnosis(row: dict[str, Any]) -> str:
    return str(row.get("diagnosis_label", ""))


def optional_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def config_from_args(args: argparse.Namespace) -> PolicyConfig:
    return PolicyConfig(
        stability_windows=args.stability_windows, repeated_bursts=args.repeated_bursts,
        max_bursts=args.max_policy_bursts, recovery_windows=getattr(args, "recovery_windows", 2),
        recovery_latency_ratio=args.recovery_latency_ratio, recovery_gpu_util=args.recovery_gpu_util,
    )


def suspicion_observed(row: dict[str, Any]) -> bool | None:
    if str(row.get("controller_state", "")).strip() == "suspicious":
        return True
    trigger = optional_number(row.get("trigger_trace"))
    if trigger in (0.0, 1.0):
        return bool(trigger)
    return None


def evidence_from_row(row: dict[str, Any], index: int) -> PolicyEvidence:
    # Historical CSVs lack per-burst IDs. Those rows are hypothetical captures,
    # not measured capture activity. Explicit blank IDs mean no new evidence.
    capture = row.get("capture_id", f"replay-burst-{index}")
    evidence_id = row.get("diagnosis_evidence_id", capture)
    if str(row.get("diagnosis_is_new", "1")).strip().lower() in {"0", "false", "no"}:
        evidence_id = None
    return PolicyEvidence(
        window_id=f"replay-window-{index}",
        diagnosis_label=diagnosis(row).strip(),
        capture_id=str(capture) if capture else None,
        diagnosis_evidence_id=str(evidence_id) if evidence_id else None,
        latency_ratio=optional_number(row.get("latency_ratio_vs_baseline")),
        gpu_util=optional_number(row.get("gpu_util_percent_mean")),
        suspicious=suspicion_observed(row),
    )


def recovered(row: dict[str, Any], args: argparse.Namespace) -> bool:
    """One observed recovery window; the engine requires a sustained streak."""
    return recovery_observed(evidence_from_row(row, 0), config_from_args(args))


def first_correct_window(rows: list[dict[str, Any]], expected_label: str) -> int | None:
    for row in rows:
        if diagnosis(row) == expected_label:
            return as_int(row.get("window_id"))
    return None


def replay_policy(rows: list[dict[str, Any]], policy: str, args: argparse.Namespace):
    engine = StoppingPolicy(policy, config_from_args(args))
    decision = None
    for index, row in enumerate(rows):
        decision = engine.observe(evidence_from_row(row, index))
        if decision.stop:
            return index, decision
    return len(rows) - 1, engine.finish()


def stop_index_for_policy(rows: list[dict[str, Any]], policy: str, args: argparse.Namespace) -> int:
    """Compatibility wrapper; new consumers should also retain the stop reason."""
    return replay_policy(rows, policy, args)[0]


def run_policy(
    rows: list[dict[str, Any]], selected_rows: list[dict[str, Any]], policy: str,
    scenario: str, seed: str, args: argparse.Namespace,
) -> dict[str, Any]:
    # selected_rows is retained for caller compatibility. It must not filter out
    # intervening unknown or recovery windows in the original timeline.
    expected_label = EXPECTED_LABELS.get(scenario, f"vllm_{scenario}")
    first = next((i for i, row in enumerate(rows) if is_suspicious(row)), None)
    episode = rows[first:] if first is not None else []
    stop_index, decision = replay_policy(episode, policy, args)
    observed = episode[:stop_index + 1] if stop_index >= 0 else []
    charged = []
    seen = set()
    for index, row in enumerate(observed):
        capture_id = evidence_from_row(row, index).capture_id
        if capture_id and capture_id not in seen:
            seen.add(capture_id)
            charged.append(row)
    labels = [diagnosis(row) for row in observed]
    correct = bool(labels) and labels[-1] == expected_label
    first_correct = first_correct_window(observed, expected_label)
    stop_window = as_int(observed[-1].get("window_id")) if observed else None
    later_suspicious = bool(observed) and any(is_suspicious(row) for row in episode[stop_index + 1:])
    reason = decision.reason if first is not None else "no_anomaly"
    return {
        "scenario": scenario, "seed": seed, "policy": decision.policy,
        "requested_policy": policy, "policy_version": POLICY_VERSION,
        "stability_windows": 2 if policy == "marginal_utility_stop" else args.stability_windows,
        "expected_label": expected_label,
        "evidence_mode": "offline_replay",
        "capture_cost_basis": "hypothetical_window_budget",
        "stop_reason": reason,
        "policy_condition_met": int(decision.policy_condition_met),
        "successful_stop": int(correct and decision.policy_condition_met and is_concrete_label(decision.diagnosis_label)),
        "budget_exhausted": int(reason == "budget_exhausted"),
        "horizon_ended": int(reason == "horizon_ended"),
        "unresolved_at_stop": int(not is_concrete_label(decision.diagnosis_label)),
        "diagnosis_streak_at_stop": decision.diagnosis_streak,
        "recovery_streak_at_stop": decision.recovery_streak,
        "selected_windows": len(charged),
        "observed_windows": len(observed),
        "heavy_trace_duration_s": sum(
            value if (value := optional_number(row.get("duration_s"))) is not None and value > 0
            else args.default_window_seconds for row in charged
        ),
        "trace_volume_proxy_windows": len(charged),
        "top1_correct": int(correct), "ever_correct": int(first_correct is not None),
        "first_correct_window": first_correct if first_correct is not None else "",
        "stop_window": stop_window if stop_window is not None else "",
        "premature_stop": int(decision.policy_condition_met and not correct),
        # Legacy name preserved for downstream compatibility: this is NOT an
        # actual reactivation measurement, only suspicion after the chosen stop.
        "re_escalation_needed": int(later_suspicious),
        "later_suspicion_proxy": int(later_suspicious),
        "diagnosis_sequence": "|".join(labels),
    }


def scenario_seed_from_path(path: Path) -> tuple[str, str]:
    scenario = path.name.split("_windows_")[0]
    seed = ""
    for part in path.parts:
        if "_seed" in part:
            seed = part.rsplit("_seed", 1)[-1]
    return scenario, seed


def path_mode(path: Path) -> str:
    if "automatic" in path.parts:
        return "automatic"
    if "fixed_window" in path.parts:
        return "fixed_window"
    return "unknown"


def iter_window_files(input_root: Path, mode: str) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*_windows_*.csv")
        if path.name != "all_windows_*.csv" and not path.name.startswith("all_windows_")
        and (mode == "all" or path_mode(path) == mode)
    )


def analyze(input_root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    results = []
    for path in iter_window_files(input_root, args.mode):
        scenario, seed = scenario_seed_from_path(path)
        if scenario not in EXPECTED_LABELS:
            continue
        rows = load_windows(path)
        selected_rows = rows
        for policy in POLICIES:
            results.append(run_policy(rows, selected_rows, policy, scenario, seed, args))
    return results


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["scenario"]), str(row["policy"]))].append(row)

    output = []
    for (scenario, policy), group in sorted(grouped.items()):
        reps = len(group)
        trace_values = [as_float(row.get("heavy_trace_duration_s")) for row in group]
        selected_values = [as_float(row.get("selected_windows")) for row in group]
        output.append(
            {
                "scenario": scenario,
                "policy": policy,
                "repetitions": reps,
                "successful_stop_rate": mean([as_float(row.get("successful_stop")) for row in group]),
                "budget_exhausted_rate": mean([as_float(row.get("budget_exhausted")) for row in group]),
                "horizon_ended_rate": mean([as_float(row.get("horizon_ended")) for row in group]),
                "top1_accuracy": mean([as_float(row.get("top1_correct")) for row in group]),
                "ever_correct_rate": mean([as_float(row.get("ever_correct")) for row in group]),
                "premature_stop_rate": mean([as_float(row.get("premature_stop")) for row in group]),
                "re_escalation_rate": mean([as_float(row.get("re_escalation_needed")) for row in group]),
                "heavy_trace_duration_s_mean": mean(trace_values),
                "heavy_trace_duration_s_ci95_half_width": ci95(trace_values),
                "selected_windows_mean": mean(selected_values),
                "selected_windows_ci95_half_width": ci95(selected_values),
            }
        )
    return output


def add_relative_costs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scenario: dict[str, float] = {}
    for row in rows:
        if row["policy"] == "repeated_fixed_burst":
            by_scenario[str(row["scenario"])] = as_float(row["heavy_trace_duration_s_mean"])
    for row in rows:
        baseline = by_scenario.get(str(row["scenario"]), 0.0)
        row["duration_saved_vs_repeated_fixed_percent"] = safe_percent(
            baseline - as_float(row["heavy_trace_duration_s_mean"]),
            baseline,
        )
    return rows


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Scenario",
        "Policy",
        "Reps",
        "Top-1",
        "Successful stop",
        "Budget exhausted",
        "Horizon ended",
        "Ever correct",
        "Premature",
        "Later suspicion (proxy)",
        "Trace s",
        "Selected windows",
        "Saved vs repeated %",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["policy"]),
                    str(row["repetitions"]),
                    str(row["top1_accuracy"]),
                    str(row["successful_stop_rate"]),
                    str(row["budget_exhausted_rate"]),
                    str(row["horizon_ended_rate"]),
                    str(row["ever_correct_rate"]),
                    str(row["premature_stop_rate"]),
                    str(row["re_escalation_rate"]),
                    str(row["heavy_trace_duration_s_mean"]),
                    str(row["selected_windows_mean"]),
                    str(row["duration_saved_vs_repeated_fixed_percent"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("RQ1/runs/vllm_rq2_multiclass_long"))
    parser.add_argument("--output-dir", type=Path, default=Path("revision/analysis/policy_replay_v2"))
    parser.add_argument("--mode", choices=("automatic", "fixed_window", "all"), default="automatic")
    parser.add_argument("--stability-windows", type=int, default=2)
    parser.add_argument("--recovery-windows", type=int, default=2)
    parser.add_argument("--repeated-bursts", type=int, default=3)
    parser.add_argument("--max-policy-bursts", type=int, default=6)
    parser.add_argument("--recovery-latency-ratio", type=float, default=1.10)
    parser.add_argument("--recovery-gpu-util", type=float, default=60.0)
    parser.add_argument("--default-window-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [rounded(row) for row in analyze(args.input_root, args)]
    aggregate_rows = [rounded(row) for row in add_relative_costs(aggregate(rows))]
    if not rows or not aggregate_rows:
        raise SystemExit("No policy rows found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    detail_csv = args.output_dir / f"rq4_policy_detail_{timestamp}.csv"
    summary_csv = args.output_dir / f"rq4_policy_summary_{timestamp}.csv"
    summary_md = args.output_dir / f"rq4_policy_summary_{timestamp}.md"
    summary_json = args.output_dir / f"rq4_policy_summary_{timestamp}.json"
    write_csv(detail_csv, rows)
    write_csv(summary_csv, aggregate_rows)
    write_markdown(summary_md, aggregate_rows)
    summary_json.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "input_root": str(args.input_root),
                "mode": args.mode,
                "policies": POLICIES,
                "policy_version": POLICY_VERSION,
                "note": "Offline hypothetical-window replay; historical labels may contain workload truth. No new measured profiler cost or reactivation events.",
                "settings": {
                    "stability_windows": args.stability_windows,
                    "repeated_bursts": args.repeated_bursts,
                    "recovery_windows": args.recovery_windows,
                    "max_policy_bursts": args.max_policy_bursts,
                    "recovery_latency_ratio": args.recovery_latency_ratio,
                    "recovery_gpu_util": args.recovery_gpu_util,
                },
                "summary": aggregate_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"loaded_policy_rows={len(rows)}")
    print(f"wrote {detail_csv}")
    print(f"wrote {summary_csv}")
    print(f"wrote {summary_md}")
    print(f"wrote {summary_json}")


if __name__ == "__main__":
    main()
