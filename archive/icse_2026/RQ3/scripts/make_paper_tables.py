#!/usr/bin/env python3
"""Create compact paper-table outputs for RQ3 overhead summaries."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any


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


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [dict(row) for row in payload.get("rows", [])]
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_runtime_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [dict(row) for row in payload.get("aggregate", [])]
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def p95_regression_percent(row: dict[str, Any]) -> float:
    automatic = as_float(row.get("p95_latency_ms_automatic"))
    fixed = as_float(row.get("p95_latency_ms_fixed_window"))
    if automatic <= 0 or fixed <= 0:
        return 0.0
    return safe_percent(automatic - fixed, fixed)


def has_request_latency(row: dict[str, Any]) -> bool:
    return as_float(row.get("p95_latency_ms_automatic")) > 0 and as_float(row.get("p95_latency_ms_fixed_window")) > 0


def build_rows(rows: list[dict[str, Any]], min_match_rate: float, max_p95_regression_percent: float) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        trace_saved = as_float(row.get("trace_saved_s"))
        kernel_avoided = as_float(row.get("kernel_instances_avoided"))
        match_rate = as_float(row.get("automatic_success_or_match_rate"))
        fixed_match_rate = as_float(row.get("fixed_window_success_or_match_rate"))
        p95_regression = p95_regression_percent(row)
        request_latency_available = has_request_latency(row)
        trace_pass = trace_saved > 0
        kernel_pass = kernel_avoided > 0
        match_pass = min(match_rate, fixed_match_rate) >= min_match_rate
        p95_pass = (not request_latency_available) or p95_regression <= max_p95_regression_percent
        output.append(
            {
                "source": row.get("source", ""),
                "workload": row.get("workload", ""),
                "repetitions": as_int(row.get("repetitions")),
                "automatic_trace_s": round(as_float(row.get("automatic_trace_s")), 3),
                "fixed_window_trace_s": round(as_float(row.get("fixed_window_trace_s")), 3),
                "trace_saved_s": round(trace_saved, 3),
                "trace_saved_percent": round(as_float(row.get("trace_saved_percent")), 3),
                "automatic_kernel_instances": round(as_float(row.get("automatic_kernel_instances")), 3),
                "fixed_window_kernel_instances": round(as_float(row.get("fixed_window_kernel_instances")), 3),
                "kernel_instances_avoided": round(kernel_avoided, 3),
                "kernel_instances_avoided_percent": round(as_float(row.get("kernel_instances_avoided_percent")), 3),
                "automatic_success_or_match_rate": round(match_rate, 3),
                "fixed_window_success_or_match_rate": round(fixed_match_rate, 3),
                "p95_latency_ms_automatic": round(as_float(row.get("p95_latency_ms_automatic")), 3),
                "p95_latency_ms_fixed_window": round(as_float(row.get("p95_latency_ms_fixed_window")), 3),
                "p95_latency_regression_percent": round(p95_regression, 3),
                "throughput_rps_automatic": round(as_float(row.get("throughput_rps_automatic")), 3),
                "throughput_rps_fixed_window": round(as_float(row.get("throughput_rps_fixed_window")), 3),
                "trace_savings_pass": trace_pass,
                "kernel_savings_pass": kernel_pass,
                "match_rate_pass": match_pass,
                "p95_latency_pass": p95_pass,
                "overall_pass": trace_pass and kernel_pass and match_pass and p95_pass,
            }
        )
    return output


def build_runtime_rows(
    rows: list[dict[str, Any]],
    max_p95_regression_percent: float,
    min_success_rate: float,
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        p95_regression = as_float(row.get("p95_latency_regression_percent_mean"))
        success_rate = as_float(row.get("cheap_metrics_success_rate_mean"))
        p95_pass = p95_regression <= max_p95_regression_percent
        success_pass = success_rate >= min_success_rate
        output.append(
            {
                "scenario": row.get("scenario", ""),
                "repetitions": as_int(row.get("repetitions")),
                "mode_orders": row.get("mode_orders", ""),
                "no_profiler_p95_latency_ms": round(as_float(row.get("no_profiler_p95_latency_ms_mean")), 3),
                "cheap_metrics_p95_latency_ms": round(as_float(row.get("cheap_metrics_p95_latency_ms_mean")), 3),
                "p95_latency_regression_percent": round(p95_regression, 3),
                "no_profiler_throughput_rps": round(as_float(row.get("no_profiler_throughput_rps_mean")), 3),
                "cheap_metrics_throughput_rps": round(as_float(row.get("cheap_metrics_throughput_rps_mean")), 3),
                "throughput_change_percent": round(as_float(row.get("throughput_change_percent_mean")), 3),
                "cheap_metrics_success_rate": round(success_rate, 3),
                "p95_latency_pass": p95_pass,
                "success_rate_pass": success_pass,
                "overall_pass": p95_pass and success_pass,
            }
        )
    return output


def write_csv(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq3_paper_table_{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_runtime_csv(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path | None:
    if not rows:
        return None
    path = output_dir / f"rq3_runtime_table_{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_markdown(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq3_paper_table_{timestamp}.md"
    headers = [
        "Source",
        "Workload",
        "Reps",
        "Saved %",
        "Kernel avoided %",
        "Match",
        "Auto p95 ms",
        "Fixed p95 ms",
        "p95 regress %",
        "Pass",
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
                    str(row["trace_saved_percent"]),
                    str(row["kernel_instances_avoided_percent"]),
                    str(row["automatic_success_or_match_rate"]),
                    str(row["p95_latency_ms_automatic"]),
                    str(row["p95_latency_ms_fixed_window"]),
                    str(row["p95_latency_regression_percent"]),
                    "yes" if row["overall_pass"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_runtime_markdown(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path | None:
    if not rows:
        return None
    path = output_dir / f"rq3_runtime_table_{timestamp}.md"
    headers = [
        "Scenario",
        "Reps",
        "Orders",
        "No-prof p95 ms",
        "Cheap p95 ms",
        "p95 regress %",
        "No-prof rps",
        "Cheap rps",
        "Throughput change %",
        "Success",
        "Pass",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["repetitions"]),
                    markdown_cell(row["mode_orders"]),
                    str(row["no_profiler_p95_latency_ms"]),
                    str(row["cheap_metrics_p95_latency_ms"]),
                    str(row["p95_latency_regression_percent"]),
                    str(row["no_profiler_throughput_rps"]),
                    str(row["cheap_metrics_throughput_rps"]),
                    str(row["throughput_change_percent"]),
                    str(row["cheap_metrics_success_rate"]),
                    "yes" if row["overall_pass"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_latex(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq3_paper_table_{timestamp}.tex"
    lines = [
        "\\begin{tabular}{llrrrrrrr}",
        "\\hline",
        "Source & Workload & Reps & Saved \\% & Kernel avoided \\% & Match & Auto p95 ms & Fixed p95 ms & p95 regress \\% \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(
            f"{row['source']} & {row['workload']} & {row['repetitions']} & "
            f"{row['trace_saved_percent']} & {row['kernel_instances_avoided_percent']} & "
            f"{row['automatic_success_or_match_rate']} & "
            f"{row['p95_latency_ms_automatic']} & {row['p95_latency_ms_fixed_window']} & "
            f"{row['p95_latency_regression_percent']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_runtime_latex(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path | None:
    if not rows:
        return None
    path = output_dir / f"rq3_runtime_table_{timestamp}.tex"
    lines = [
        "\\begin{tabular}{lrrrrrr}",
        "\\hline",
        "Scenario & Reps & No-prof p95 ms & Cheap p95 ms & p95 regress \\% & Throughput change \\% & Success \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(
            f"{row['scenario']} & {row['repetitions']} & "
            f"{row['no_profiler_p95_latency_ms']} & {row['cheap_metrics_p95_latency_ms']} & "
            f"{row['p95_latency_regression_percent']} & {row['throughput_change_percent']} & "
            f"{row['cheap_metrics_success_rate']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_success_criteria(
    rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
    output_dir: Path,
    timestamp: int,
    min_match_rate: float,
    max_p95_regression_percent: float,
    min_runtime_success_rate: float,
) -> Path:
    path = output_dir / f"rq3_success_criteria_{timestamp}.json"
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "criteria": {
            "trace_duration_saved_s_must_be_positive": True,
            "kernel_instances_avoided_must_be_positive": True,
            "minimum_success_or_match_rate": min_match_rate,
            "maximum_p95_latency_regression_percent_when_available": max_p95_regression_percent,
            "runtime_maximum_p95_latency_regression_percent": max_p95_regression_percent,
            "runtime_minimum_request_success_rate": min_runtime_success_rate,
            "runtime_throughput_change_is_reported_not_pass_fail": True,
        },
        "results": rows,
        "runtime_results": runtime_rows,
        "overall_pass": all(row["overall_pass"] for row in rows) and all(row["overall_pass"] for row in runtime_rows),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--runtime-overhead", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ3/analysis/l4_overhead/paper_tables"))
    parser.add_argument("--min-match-rate", type=float, default=0.95)
    parser.add_argument("--max-p95-regression-percent", type=float, default=5.0)
    parser.add_argument("--min-runtime-success-rate", type=float, default=100.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(load_rows(args.summary), args.min_match_rate, args.max_p95_regression_percent)
    runtime_rows = build_runtime_rows(
        load_runtime_rows(args.runtime_overhead),
        args.max_p95_regression_percent,
        args.min_runtime_success_rate,
    )
    if not rows:
        raise SystemExit("No RQ3 overhead rows found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = write_csv(rows, args.output_dir, timestamp)
    markdown_path = write_markdown(rows, args.output_dir, timestamp)
    latex_path = write_latex(rows, args.output_dir, timestamp)
    runtime_csv_path = write_runtime_csv(runtime_rows, args.output_dir, timestamp)
    runtime_markdown_path = write_runtime_markdown(runtime_rows, args.output_dir, timestamp)
    runtime_latex_path = write_runtime_latex(runtime_rows, args.output_dir, timestamp)
    criteria_path = write_success_criteria(
        rows,
        runtime_rows,
        args.output_dir,
        timestamp,
        args.min_match_rate,
        args.max_p95_regression_percent,
        args.min_runtime_success_rate,
    )
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {latex_path}")
    if runtime_csv_path:
        print(f"wrote {runtime_csv_path}")
    if runtime_markdown_path:
        print(f"wrote {runtime_markdown_path}")
    if runtime_latex_path:
        print(f"wrote {runtime_latex_path}")
    print(f"wrote {criteria_path}")


if __name__ == "__main__":
    main()
