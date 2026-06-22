#!/usr/bin/env python3
"""Replay vLLM window evidence under candidate RQ4 tracing policies."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


POLICIES = (
    "fixed_burst",
    "repeated_fixed_burst",
    "stability_stop",
    "marginal_utility_stop",
    "counter_recovery_stop",
    "hybrid_stop",
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
    return as_int(row.get("trigger_trace")) == 1 or str(row.get("controller_state", "")) == "suspicious"


def diagnosis(row: dict[str, Any]) -> str:
    return str(row.get("diagnosis_label", ""))


def recovered(row: dict[str, Any], args: argparse.Namespace) -> bool:
    latency_ratio = as_float(row.get("latency_ratio_vs_baseline"))
    gpu_util = as_float(row.get("gpu_util_percent_mean"))
    state = str(row.get("controller_state", ""))
    no_trigger = as_int(row.get("trigger_trace")) == 0
    latency_ok = latency_ratio == 0.0 or latency_ratio <= args.recovery_latency_ratio
    gpu_ok = gpu_util == 0.0 or gpu_util <= args.recovery_gpu_util
    return state != "suspicious" and no_trigger and latency_ok and gpu_ok


def first_correct_window(rows: list[dict[str, Any]], expected_label: str) -> int | None:
    for row in rows:
        if diagnosis(row) == expected_label:
            return as_int(row.get("window_id"))
    return None


def stop_index_for_policy(rows: list[dict[str, Any]], policy: str, args: argparse.Namespace) -> int:
    if not rows:
        return -1

    if policy == "fixed_burst":
        return 0

    if policy == "repeated_fixed_burst":
        return min(len(rows), args.repeated_bursts) - 1

    if policy == "stability_stop":
        streak = 0
        previous = ""
        for index, row in enumerate(rows):
            current = diagnosis(row)
            streak = streak + 1 if current and current == previous else 1
            previous = current
            if streak >= args.stability_windows:
                return index
        return min(len(rows), args.max_policy_bursts) - 1

    if policy == "marginal_utility_stop":
        previous = ""
        for index, row in enumerate(rows):
            current = diagnosis(row)
            if index > 0 and current and current == previous:
                return index
            previous = current
        return min(len(rows), args.max_policy_bursts) - 1

    if policy == "counter_recovery_stop":
        for index, row in enumerate(rows):
            if index > 0 and recovered(row, args):
                return index
        return min(len(rows), args.max_policy_bursts) - 1

    if policy == "hybrid_stop":
        streak = 0
        previous = ""
        for index, row in enumerate(rows):
            current = diagnosis(row)
            streak = streak + 1 if current and current == previous else 1
            previous = current
            if streak >= args.stability_windows and recovered(row, args):
                return index
        return min(len(rows), args.max_policy_bursts) - 1

    raise ValueError(f"Unsupported policy: {policy}")


def run_policy(
    rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    policy: str,
    scenario: str,
    seed: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    expected_label = EXPECTED_LABELS.get(scenario, f"vllm_{scenario}")
    stop_index = stop_index_for_policy(selected_rows, policy, args)
    traced = selected_rows[: stop_index + 1] if stop_index >= 0 else []
    labels = [diagnosis(row) for row in traced]
    correct_windows = [row for row in traced if diagnosis(row) == expected_label]
    first_correct = first_correct_window(traced, expected_label)
    stop_window = as_int(traced[-1].get("window_id")) if traced else None
    later_suspicious = [
        row for row in rows if stop_window is not None and as_int(row.get("window_id")) > stop_window and is_suspicious(row)
    ]
    window_seconds = mean([as_float(row.get("duration_s")) for row in traced]) or args.default_window_seconds
    return {
        "scenario": scenario,
        "seed": seed,
        "policy": policy,
        "expected_label": expected_label,
        "selected_windows": len(traced),
        "heavy_trace_duration_s": len(traced) * window_seconds,
        "trace_volume_proxy_windows": len(traced),
        "top1_correct": int(bool(traced) and labels[-1] == expected_label),
        "ever_correct": int(bool(correct_windows)),
        "first_correct_window": first_correct if first_correct is not None else "",
        "stop_window": stop_window if stop_window is not None else "",
        "premature_stop": int(not correct_windows),
        "re_escalation_needed": int(bool(later_suspicious)),
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
        selected_rows = [row for row in rows if is_suspicious(row)] or rows
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
        "Ever correct",
        "Premature",
        "Re-escalation",
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
    parser.add_argument("--output-dir", type=Path, default=Path("RQ4/analysis/policy_replay_l4_vllm"))
    parser.add_argument("--mode", choices=("automatic", "fixed_window", "all"), default="automatic")
    parser.add_argument("--stability-windows", type=int, default=2)
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
                "settings": {
                    "stability_windows": args.stability_windows,
                    "repeated_bursts": args.repeated_bursts,
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
