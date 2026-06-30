#!/usr/bin/env python3
"""Build a baseline-comparison table from existing vLLM tracing artifacts.

This script combines two sources:
1. live automatic/fixed-window Nsight comparison JSON files from RQ1/RQ2 runs;
2. offline stopping-policy replay from RQ4's per-window CSV replay logic.

Replay rows should be described as replay in the paper; they do not create new
Nsight reports or new kernel-instance counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_EXPERIMENT_DIR = SCRIPT_DIR.parents[1]
RQ4_SCRIPTS = REPO_EXPERIMENT_DIR / "RQ4" / "scripts"
sys.path.insert(0, str(RQ4_SCRIPTS))

import analyze_policies  # type: ignore  # noqa: E402


EXPECTED_LABELS = analyze_policies.EXPECTED_LABELS
LIVE_MODES = {
    "automatic": "Adaptive live",
    "fixed_window": "Manual long fixed-window live",
}
REPLAY_BASELINES = {
    "fixed_burst": "Equal-duration fixed burst replay",
    "repeated_fixed_burst": "Repeated fixed burst N=3 replay",
    "stability_stop": "Stability Stop K=2 replay",
    "hybrid_stop": "Hybrid Stop replay",
    "counter_recovery_stop": "Counter-Recovery Stop replay",
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


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def safe_percent(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator * 100.0


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def read_windows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def scenario_seed_from_run_dir(run_dir: Path) -> tuple[str, str]:
    name = run_dir.name
    if "_seed" in name:
        scenario, seed = name.rsplit("_seed", 1)
        return scenario, seed
    return name, ""


def live_mode_accuracy(run_dir: Path, mode: str, scenario: str) -> tuple[float, float]:
    expected = EXPECTED_LABELS.get(scenario, f"vllm_{scenario}")
    window_files = [
        path
        for path in sorted((run_dir / mode).rglob("*_windows_*.csv"))
        if not path.name.startswith("all_windows_")
    ]
    rows: list[dict[str, str]] = []
    for path in window_files:
        rows.extend(read_windows(path))
    suspicious = [
        row
        for row in rows
        if as_int(row.get("trigger_trace")) == 1 or str(row.get("controller_state", "")) == "suspicious"
    ]
    denominator = suspicious or rows
    if not denominator:
        return 0.0, 0.0
    correct = [row for row in denominator if row.get("diagnosis_label") == expected]
    ambiguous = [
        row
        for row in denominator
        if row.get("diagnosis_label", "").endswith("unknown_gpu_cause")
        or row.get("diagnosis_label", "") in {"healthy_or_not_suspicious", "possible_memory_pressure"}
    ]
    return len(correct) / len(denominator), len(ambiguous) / len(denominator)


def collect_live_rows(input_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comparison_path in sorted(input_root.rglob("vllm_nsys_comparison_*.json")):
        payload = json.loads(comparison_path.read_text(encoding="utf-8"))
        run_dir = comparison_path.parent
        scenario = str(payload.get("scenario") or scenario_seed_from_run_dir(run_dir)[0])
        seed = str(payload.get("seed") or scenario_seed_from_run_dir(run_dir)[1])
        for mode, label in LIVE_MODES.items():
            mode_payload = payload.get(mode) or {}
            kernel_summary = mode_payload.get("kernel_summary") or {}
            match_rate, ambiguous_rate = live_mode_accuracy(run_dir, mode, scenario)
            rows.append(
                {
                    "baseline": label,
                    "source": "live",
                    "scenario": scenario,
                    "seed": seed,
                    "streams": 1,
                    "top1_accuracy": match_rate,
                    "ambiguous_rate": ambiguous_rate,
                    "premature_stop_rate": 0.0 if match_rate > 0 else 1.0,
                    "re_escalation_rate": "",
                    "profiler_duration_s": as_float(mode_payload.get("duration_s")),
                    "kernel_instances": as_float(kernel_summary.get("kernel_instances")),
                    "trace_windows": "",
                }
            )
    return rows


def collect_replay_rows(input_root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    policy_rows = analyze_policies.analyze(input_root, args)
    rows: list[dict[str, Any]] = []
    for row in policy_rows:
        policy = str(row.get("policy", ""))
        if policy not in REPLAY_BASELINES:
            continue
        rows.append(
            {
                "baseline": REPLAY_BASELINES[policy],
                "source": "offline replay",
                "scenario": row.get("scenario", ""),
                "seed": row.get("seed", ""),
                "streams": 1,
                "top1_accuracy": as_float(row.get("top1_correct")),
                "ambiguous_rate": "",
                "premature_stop_rate": as_float(row.get("premature_stop")),
                "re_escalation_rate": as_float(row.get("re_escalation_needed")),
                "profiler_duration_s": as_float(row.get("heavy_trace_duration_s")),
                "kernel_instances": "",
                "trace_windows": as_float(row.get("selected_windows")),
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["baseline"])].append(row)
    live_fixed_total = sum(
        as_float(row.get("profiler_duration_s"))
        for row in rows
        if row.get("baseline") == LIVE_MODES["fixed_window"]
    )
    output: list[dict[str, Any]] = []
    for baseline, group in sorted(grouped.items()):
        duration_total = sum(as_float(row.get("profiler_duration_s")) for row in group)
        kernel_values = [as_float(row.get("kernel_instances")) for row in group if row.get("kernel_instances") != ""]
        re_esc_values = [as_float(row.get("re_escalation_rate")) for row in group if row.get("re_escalation_rate") != ""]
        ambiguous_values = [as_float(row.get("ambiguous_rate")) for row in group if row.get("ambiguous_rate") != ""]
        trace_window_values = [as_float(row.get("trace_windows")) for row in group if row.get("trace_windows") != ""]
        output.append(
            rounded(
                {
                    "baseline": baseline,
                    "source": group[0]["source"],
                    "streams": len(group),
                    "top1_accuracy_mean": mean([as_float(row.get("top1_accuracy")) for row in group]),
                    "ambiguous_rate_mean": mean(ambiguous_values) if ambiguous_values else "",
                    "premature_stop_rate_mean": mean([as_float(row.get("premature_stop_rate")) for row in group]),
                    "re_escalation_rate_mean": mean(re_esc_values) if re_esc_values else "",
                    "profiler_duration_s_total": duration_total,
                    "profiler_duration_s_mean": mean([as_float(row.get("profiler_duration_s")) for row in group]),
                    "duration_saved_vs_manual_long_percent": safe_percent(live_fixed_total - duration_total, live_fixed_total)
                    if live_fixed_total
                    else "",
                    "kernel_instances_total": sum(kernel_values) if kernel_values else "",
                    "kernel_instances_mean": mean(kernel_values) if kernel_values else "",
                    "trace_windows_mean": mean(trace_window_values) if trace_window_values else "",
                }
            )
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Baseline",
        "Source",
        "Streams",
        "Top-1",
        "Premature",
        "Re-esc.",
        "Trace total s",
        "Saved vs manual %",
        "Kernels total",
        "Trace windows",
    ]
    fields = [
        "baseline",
        "source",
        "streams",
        "top1_accuracy_mean",
        "premature_stop_rate_mean",
        "re_escalation_rate_mean",
        "profiler_duration_s_total",
        "duration_saved_vs_manual_long_percent",
        "kernel_instances_total",
        "trace_windows_mean",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("experiment/RQ1/runs/vllm_rq2_multiclass_long"))
    parser.add_argument("--output-dir", type=Path, default=Path("experiment/RQ2/analysis/baseline_comparison"))
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
    live_rows = collect_live_rows(args.input_root)
    replay_rows = collect_replay_rows(args.input_root, args)
    detail_rows = [rounded(row) for row in live_rows + replay_rows]
    summary_rows = aggregate(detail_rows)
    if not detail_rows:
        raise SystemExit(f"No baseline rows found under {args.input_root}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    detail_csv = args.output_dir / f"baseline_comparison_detail_{timestamp}.csv"
    summary_csv = args.output_dir / f"baseline_comparison_summary_{timestamp}.csv"
    summary_md = args.output_dir / f"baseline_comparison_summary_{timestamp}.md"
    summary_json = args.output_dir / f"baseline_comparison_summary_{timestamp}.json"
    write_csv(detail_csv, detail_rows)
    write_csv(summary_csv, summary_rows)
    write_markdown(summary_md, summary_rows)
    summary_json.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "input_root": str(args.input_root),
                "note": "Rows marked offline replay reuse existing per-window evidence and do not include new Nsight kernel counts.",
                "summary": summary_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"live_rows={len(live_rows)} replay_rows={len(replay_rows)}")
    print(f"wrote {detail_csv}")
    print(f"wrote {summary_csv}")
    print(f"wrote {summary_md}")
    print(f"wrote {summary_json}")


if __name__ == "__main__":
    main()
