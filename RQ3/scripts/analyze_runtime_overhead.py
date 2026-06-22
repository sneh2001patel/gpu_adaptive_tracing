#!/usr/bin/env python3
"""Aggregate dedicated vLLM runtime-overhead repetitions."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any


NUMERIC_FIELDS = (
    "no_profiler_request_count",
    "cheap_metrics_request_count",
    "no_profiler_p50_latency_ms",
    "cheap_metrics_p50_latency_ms",
    "no_profiler_p95_latency_ms",
    "cheap_metrics_p95_latency_ms",
    "no_profiler_throughput_rps",
    "cheap_metrics_throughput_rps",
    "no_profiler_success_rate",
    "cheap_metrics_success_rate",
    "p95_latency_delta_ms",
    "p95_latency_regression_percent",
    "throughput_delta_rps",
    "throughput_change_percent",
)


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def ci95(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * stdev(values) / (len(values) ** 0.5)


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for record in payload.get("records", []):
        no_profiler = record.get("no_profiler", {})
        cheap = record.get("cheap_metrics_only", {})
        comparison = record.get("comparison", {})
        records.append(
            {
                "summary_path": str(path),
                "comparison_path": record.get("comparison_path", ""),
                "model": record.get("model", payload.get("model", "")),
                "scenario": record.get("scenario", payload.get("scenario", "")),
                "seed": record.get("seed", ""),
                "mode_order": "|".join(str(mode) for mode in record.get("mode_order", [])),
                "no_profiler_request_count": as_float(no_profiler.get("request_count")),
                "cheap_metrics_request_count": as_float(cheap.get("request_count")),
                "no_profiler_p50_latency_ms": as_float(no_profiler.get("p50_latency_ms")),
                "cheap_metrics_p50_latency_ms": as_float(cheap.get("p50_latency_ms")),
                "no_profiler_p95_latency_ms": as_float(no_profiler.get("p95_latency_ms")),
                "cheap_metrics_p95_latency_ms": as_float(cheap.get("p95_latency_ms")),
                "no_profiler_throughput_rps": as_float(no_profiler.get("throughput_rps")),
                "cheap_metrics_throughput_rps": as_float(cheap.get("throughput_rps")),
                "no_profiler_success_rate": as_float(no_profiler.get("success_rate")),
                "cheap_metrics_success_rate": as_float(cheap.get("success_rate")),
                "p95_latency_delta_ms": as_float(comparison.get("p95_latency_delta_ms")),
                "p95_latency_regression_percent": as_float(comparison.get("p95_latency_regression_percent")),
                "throughput_delta_rps": as_float(comparison.get("throughput_delta_rps")),
                "throughput_change_percent": as_float(comparison.get("throughput_change_percent")),
            }
        )
    return records


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    row: dict[str, Any] = {
        "scenario": records[0].get("scenario", ""),
        "model": records[0].get("model", ""),
        "repetitions": len(records),
        "seeds": "|".join(str(record.get("seed", "")) for record in records),
        "mode_orders": ";".join(str(record.get("mode_order", "")) for record in records),
    }
    for field in NUMERIC_FIELDS:
        values = [as_float(record.get(field)) for record in records]
        row[f"{field}_mean"] = mean(values)
        row[f"{field}_stdev"] = stdev(values)
        row[f"{field}_ci95_half_width"] = ci95(values)
    return [row]


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
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
                    str(row["no_profiler_p95_latency_ms_mean"]),
                    str(row["cheap_metrics_p95_latency_ms_mean"]),
                    str(row["p95_latency_regression_percent_mean"]),
                    str(row["no_profiler_throughput_rps_mean"]),
                    str(row["cheap_metrics_throughput_rps_mean"]),
                    str(row["throughput_change_percent_mean"]),
                    str(row["cheap_metrics_success_rate_mean"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ3/analysis/vllm_runtime_overhead"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.summary)
    rows = [rounded(row) for row in aggregate(records)]
    if not rows:
        raise SystemExit("No runtime-overhead records found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = args.output_dir / f"runtime_overhead_aggregate_{timestamp}.csv"
    md_path = args.output_dir / f"runtime_overhead_aggregate_{timestamp}.md"
    json_path = args.output_dir / f"runtime_overhead_aggregate_{timestamp}.json"
    write_csv(csv_path, rows)
    write_markdown(md_path, rows)
    json_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "summary": str(args.summary),
                "records": records,
                "aggregate": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"loaded_records={len(records)}")
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
