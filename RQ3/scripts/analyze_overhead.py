#!/usr/bin/env python3
"""Build RQ3 overhead summaries from RQ1/RQ2 aggregate artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


MODES = ("automatic", "fixed_window")
AMBIGUOUS_OR_NON_DIAGNOSIS = {
    "healthy_or_not_suspicious",
    "latency_regression_unknown_gpu_cause",
    "vllm_latency_regression_unknown_gpu_cause",
    "possible_launch_overhead_or_small_kernel",
    "possible_memory_pressure",
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
    return 0.0 if denominator <= 0 else (numerator / denominator) * 100.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (rank - low)


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def diagnosis_match_rate(row: dict[str, Any], mode: str, expected_label: str) -> float:
    counts_raw = row.get(f"{mode}_diagnosis_counts_total", "{}")
    try:
        counts = json.loads(counts_raw) if isinstance(counts_raw, str) else dict(counts_raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        counts = {}
    correct = as_float(counts.get(expected_label))
    diagnostic_total = sum(
        as_float(count)
        for label, count in counts.items()
        if str(label) not in AMBIGUOUS_OR_NON_DIAGNOSIS
    )
    if diagnostic_total <= 0:
        suspicious_total = as_float(row.get(f"{mode}_suspicious_windows_mean")) * as_float(row.get("repetitions"))
        diagnostic_total = suspicious_total
    return correct / diagnostic_total if diagnostic_total > 0 else 0.0


def build_cost_row(
    source: str,
    workload: str,
    repetitions: int,
    automatic_trace_s: float,
    fixed_window_trace_s: float,
    automatic_kernel_instances: float,
    fixed_window_kernel_instances: float,
    automatic_report_count: float,
    fixed_window_report_count: float,
    automatic_success_rate: float,
    fixed_window_success_rate: float,
    automatic_request_metrics: dict[str, float] | None = None,
    fixed_window_request_metrics: dict[str, float] | None = None,
) -> dict[str, Any]:
    trace_saved_s = fixed_window_trace_s - automatic_trace_s
    kernel_instances_avoided = fixed_window_kernel_instances - automatic_kernel_instances
    automatic_request_metrics = automatic_request_metrics or {}
    fixed_window_request_metrics = fixed_window_request_metrics or {}
    return {
        "source": source,
        "workload": workload,
        "repetitions": repetitions,
        "automatic_trace_s": automatic_trace_s,
        "fixed_window_trace_s": fixed_window_trace_s,
        "trace_saved_s": trace_saved_s,
        "trace_saved_percent": safe_percent(trace_saved_s, fixed_window_trace_s),
        "automatic_kernel_instances": automatic_kernel_instances,
        "fixed_window_kernel_instances": fixed_window_kernel_instances,
        "kernel_instances_avoided": kernel_instances_avoided,
        "kernel_instances_avoided_percent": safe_percent(kernel_instances_avoided, fixed_window_kernel_instances),
        "automatic_profiler_report_count": automatic_report_count,
        "fixed_window_profiler_report_count": fixed_window_report_count,
        "automatic_success_or_match_rate": automatic_success_rate,
        "fixed_window_success_or_match_rate": fixed_window_success_rate,
        "request_count_automatic": automatic_request_metrics.get("request_count", 0.0),
        "request_count_fixed_window": fixed_window_request_metrics.get("request_count", 0.0),
        "p50_latency_ms_automatic": automatic_request_metrics.get("p50_latency_ms", 0.0),
        "p50_latency_ms_fixed_window": fixed_window_request_metrics.get("p50_latency_ms", 0.0),
        "p95_latency_ms_automatic": automatic_request_metrics.get("p95_latency_ms", 0.0),
        "p95_latency_ms_fixed_window": fixed_window_request_metrics.get("p95_latency_ms", 0.0),
        "throughput_rps_automatic": automatic_request_metrics.get("throughput_rps", 0.0),
        "throughput_rps_fixed_window": fixed_window_request_metrics.get("throughput_rps", 0.0),
        "success_rate_automatic": automatic_request_metrics.get("success_rate", 0.0),
        "success_rate_fixed_window": fixed_window_request_metrics.get("success_rate", 0.0),
        "prompt_tokens_mean_automatic": automatic_request_metrics.get("prompt_tokens_mean", 0.0),
        "prompt_tokens_mean_fixed_window": fixed_window_request_metrics.get("prompt_tokens_mean", 0.0),
        "output_tokens_mean_automatic": automatic_request_metrics.get("output_tokens_mean", 0.0),
        "output_tokens_mean_fixed_window": fixed_window_request_metrics.get("output_tokens_mean", 0.0),
    }


def rq1_microbenchmark_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    rows = []
    for workload in payload.get("workloads", []):
        name = str(workload.get("workload", ""))
        repetitions = as_int(workload.get("repetitions"))
        automatic_trace_s = as_float(workload.get("automatic_profiler_duration_s_mean"))
        fixed_trace_s = as_float(workload.get("fixed_window_profiler_duration_s_mean"))
        rows.append(
            build_cost_row(
                source="rq1_microbenchmark",
                workload=name,
                repetitions=repetitions,
                automatic_trace_s=automatic_trace_s,
                fixed_window_trace_s=fixed_trace_s,
                automatic_kernel_instances=as_float(workload.get("automatic_profiler_kernel_instances_mean")),
                fixed_window_kernel_instances=as_float(workload.get("fixed_window_profiler_kernel_instances_mean")),
                automatic_report_count=as_float(workload.get("automatic_profiler_bursts_mean")),
                fixed_window_report_count=as_float(workload.get("fixed_window_profiler_bursts_mean")),
                automatic_success_rate=diagnosis_match_rate(workload, "automatic", name),
                fixed_window_success_rate=diagnosis_match_rate(workload, "fixed_window", name),
            )
        )
    return rows


def rq1_vllm_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    rows = []
    for scenario in payload.get("scenarios", []):
        automatic_trace_s = as_float(scenario.get("automatic_duration_s_mean"))
        fixed_trace_s = as_float(scenario.get("fixed_window_duration_s_mean"))
        rows.append(
            build_cost_row(
                source="rq1_vllm_profiler_savings",
                workload=str(scenario.get("scenario", "")),
                repetitions=as_int(scenario.get("repetitions")),
                automatic_trace_s=automatic_trace_s,
                fixed_window_trace_s=fixed_trace_s,
                automatic_kernel_instances=as_float(scenario.get("automatic_kernel_instances_mean")),
                fixed_window_kernel_instances=as_float(scenario.get("fixed_window_kernel_instances_mean")),
                automatic_report_count=1.0,
                fixed_window_report_count=1.0,
                automatic_success_rate=as_float(scenario.get("automatic_smoke_success_rate_mean")) / 100.0,
                fixed_window_success_rate=as_float(scenario.get("fixed_window_smoke_success_rate_mean")) / 100.0,
            )
        )
    return rows


def request_metrics_for_file(path: Path) -> dict[str, float]:
    rows = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    latencies = [as_float(row.get("request_latency_ms")) for row in rows if as_float(row.get("request_latency_ms")) > 0]
    starts = [as_float(row.get("request_start_ts")) for row in rows if as_float(row.get("request_start_ts")) > 0]
    ends = [as_float(row.get("request_end_ts")) for row in rows if as_float(row.get("request_end_ts")) > 0]
    duration = max(ends) - min(starts) if starts and ends and max(ends) > min(starts) else 0.0
    return {
        "request_count": float(len(rows)),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "throughput_rps": len(rows) / duration if duration > 0 else 0.0,
        "success_rate": mean([as_float(row.get("success")) for row in rows]),
        "prompt_tokens_mean": mean([as_float(row.get("prompt_tokens_estimate")) for row in rows]),
        "output_tokens_mean": mean([as_float(row.get("output_tokens_estimate")) for row in rows]),
    }


def combine_request_metrics(metrics: list[dict[str, float]]) -> dict[str, float]:
    if not metrics:
        return {}
    weighted_fields = (
        "p50_latency_ms",
        "p95_latency_ms",
        "throughput_rps",
        "success_rate",
        "prompt_tokens_mean",
        "output_tokens_mean",
    )
    total_requests = sum(metric.get("request_count", 0.0) for metric in metrics)
    combined = {"request_count": total_requests}
    for field in weighted_fields:
        if total_requests > 0:
            combined[field] = sum(metric.get(field, 0.0) * metric.get("request_count", 0.0) for metric in metrics) / total_requests
        else:
            combined[field] = mean([metric.get(field, 0.0) for metric in metrics])
    return combined


def vllm_request_metrics(run_root: Path) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)
    if not run_root.exists():
        return {}
    for path in sorted(run_root.glob("*/**/smoke/*_requests_*.csv")):
        if path.name.startswith("all_requests_"):
            continue
        mode = ""
        for part in path.parts:
            if part in MODES:
                mode = part
                break
        if not mode:
            continue
        scenario = path.name.split("_requests_", 1)[0]
        grouped[(scenario, mode)].append(request_metrics_for_file(path))
    return {key: combine_request_metrics(value) for key, value in grouped.items()}


def rq2_vllm_rows(path: Path, request_metrics: dict[tuple[str, str], dict[str, float]]) -> list[dict[str, Any]]:
    payload = load_json(path)
    by_workload: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in payload.get("summary", []):
        by_workload[str(row.get("workload", ""))][str(row.get("mode", ""))] = row

    rows = []
    for workload, modes in sorted(by_workload.items()):
        if not all(mode in modes for mode in MODES):
            continue
        automatic = modes["automatic"]
        fixed = modes["fixed_window"]
        rows.append(
            build_cost_row(
                source="rq2_vllm_multiclass",
                workload=workload,
                repetitions=as_int(automatic.get("runs")),
                automatic_trace_s=as_float(automatic.get("profiler_duration_s_total")),
                fixed_window_trace_s=as_float(fixed.get("profiler_duration_s_total")),
                automatic_kernel_instances=as_float(automatic.get("profiler_kernel_instances_total")),
                fixed_window_kernel_instances=as_float(fixed.get("profiler_kernel_instances_total")),
                automatic_report_count=as_float(automatic.get("profiler_report_count_total")),
                fixed_window_report_count=as_float(fixed.get("profiler_report_count_total")),
                automatic_success_rate=as_float(automatic.get("match_rate_on_suspicious_or_all")),
                fixed_window_success_rate=as_float(fixed.get("match_rate_on_suspicious_or_all")),
                automatic_request_metrics=request_metrics.get((workload, "automatic"), {}),
                fixed_window_request_metrics=request_metrics.get((workload, "fixed_window"), {}),
            )
        )
    return rows


def totals_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    vllm_rows = [row for row in rows if row["source"] == "rq2_vllm_multiclass"]
    automatic_request_metrics = combine_request_metrics(
        [
            {
                "request_count": as_float(row.get("request_count_automatic")),
                "p50_latency_ms": as_float(row.get("p50_latency_ms_automatic")),
                "p95_latency_ms": as_float(row.get("p95_latency_ms_automatic")),
                "throughput_rps": as_float(row.get("throughput_rps_automatic")),
                "success_rate": as_float(row.get("success_rate_automatic")),
                "prompt_tokens_mean": as_float(row.get("prompt_tokens_mean_automatic")),
                "output_tokens_mean": as_float(row.get("output_tokens_mean_automatic")),
            }
            for row in vllm_rows
        ]
    )
    fixed_window_request_metrics = combine_request_metrics(
        [
            {
                "request_count": as_float(row.get("request_count_fixed_window")),
                "p50_latency_ms": as_float(row.get("p50_latency_ms_fixed_window")),
                "p95_latency_ms": as_float(row.get("p95_latency_ms_fixed_window")),
                "throughput_rps": as_float(row.get("throughput_rps_fixed_window")),
                "success_rate": as_float(row.get("success_rate_fixed_window")),
                "prompt_tokens_mean": as_float(row.get("prompt_tokens_mean_fixed_window")),
                "output_tokens_mean": as_float(row.get("output_tokens_mean_fixed_window")),
            }
            for row in vllm_rows
        ]
    )
    return build_cost_row(
        source="rq2_vllm_multiclass_total",
        workload="all_vllm_scenarios",
        repetitions=sum(as_int(row.get("repetitions")) for row in vllm_rows),
        automatic_trace_s=sum(as_float(row.get("automatic_trace_s")) for row in vllm_rows),
        fixed_window_trace_s=sum(as_float(row.get("fixed_window_trace_s")) for row in vllm_rows),
        automatic_kernel_instances=sum(as_float(row.get("automatic_kernel_instances")) for row in vllm_rows),
        fixed_window_kernel_instances=sum(as_float(row.get("fixed_window_kernel_instances")) for row in vllm_rows),
        automatic_report_count=sum(as_float(row.get("automatic_profiler_report_count")) for row in vllm_rows),
        fixed_window_report_count=sum(as_float(row.get("fixed_window_profiler_report_count")) for row in vllm_rows),
        automatic_success_rate=mean([as_float(row.get("automatic_success_or_match_rate")) for row in vllm_rows]),
        fixed_window_success_rate=mean([as_float(row.get("fixed_window_success_or_match_rate")) for row in vllm_rows]),
        automatic_request_metrics=automatic_request_metrics,
        fixed_window_request_metrics=fixed_window_request_metrics,
    )


def round_row(row: dict[str, Any]) -> dict[str, Any]:
    rounded = {}
    for key, value in row.items():
        rounded[key] = round(value, 3) if isinstance(value, float) else value
    return rounded


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Source",
        "Workload",
        "Reps",
        "Auto trace s",
        "Fixed trace s",
        "Saved %",
        "Auto kernels",
        "Fixed kernels",
        "Avoided %",
        "Auto p95 ms",
        "Fixed p95 ms",
        "Auto rps",
        "Fixed rps",
        "Match",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["source"]),
                    str(row["workload"]),
                    str(row["repetitions"]),
                    str(row["automatic_trace_s"]),
                    str(row["fixed_window_trace_s"]),
                    str(row["trace_saved_percent"]),
                    str(row["automatic_kernel_instances"]),
                    str(row["fixed_window_kernel_instances"]),
                    str(row["kernel_instances_avoided_percent"]),
                    str(row["p95_latency_ms_automatic"]),
                    str(row["p95_latency_ms_fixed_window"]),
                    str(row["throughput_rps_automatic"]),
                    str(row["throughput_rps_fixed_window"]),
                    str(row["automatic_success_or_match_rate"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rq1-micro-aggregate", type=Path, required=True)
    parser.add_argument("--rq1-vllm-aggregate", type=Path, required=True)
    parser.add_argument("--rq2-vllm-accuracy", type=Path, required=True)
    parser.add_argument("--vllm-run-root", type=Path, default=Path("RQ1/runs/vllm_rq2_multiclass_long"))
    parser.add_argument("--output-dir", type=Path, default=Path("RQ3/analysis/l4_overhead"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request_metrics = vllm_request_metrics(args.vllm_run_root)
    rows = []
    rows.extend(rq1_microbenchmark_rows(args.rq1_micro_aggregate))
    rows.extend(rq1_vllm_rows(args.rq1_vllm_aggregate))
    rows.extend(rq2_vllm_rows(args.rq2_vllm_accuracy, request_metrics))
    rows.append(totals_row(rows))
    rounded_rows = [round_row(row) for row in rows]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = args.output_dir / f"rq3_overhead_summary_{timestamp}.csv"
    json_path = args.output_dir / f"rq3_overhead_{timestamp}.json"
    markdown_path = args.output_dir / f"rq3_overhead_summary_{timestamp}.md"

    write_csv(csv_path, rounded_rows)
    write_markdown(markdown_path, rounded_rows)
    json_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "rq1_micro_aggregate": str(args.rq1_micro_aggregate),
                "rq1_vllm_aggregate": str(args.rq1_vllm_aggregate),
                "rq2_vllm_accuracy": str(args.rq2_vllm_accuracy),
                "vllm_run_root": str(args.vllm_run_root),
                "summary_csv": str(csv_path),
                "summary_markdown": str(markdown_path),
                "rows": rounded_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"loaded_request_metric_groups={len(request_metrics)}")
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
