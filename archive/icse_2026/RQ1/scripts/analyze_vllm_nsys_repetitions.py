#!/usr/bin/env python3
"""Aggregate vLLM Nsight comparison JSON files across repetitions."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


NUMERIC_FIELDS = (
    "profiler_duration_saved_s",
    "profiler_duration_saved_percent",
    "automatic_duration_s",
    "fixed_window_duration_s",
    "automatic_kernel_instances",
    "fixed_window_kernel_instances",
    "automatic_kernel_total_time_ns",
    "fixed_window_kernel_total_time_ns",
    "automatic_kernel_avg_duration_ns",
    "fixed_window_kernel_avg_duration_ns",
    "automatic_smoke_success_rate",
    "fixed_window_smoke_success_rate",
    "automatic_smoke_requests",
    "fixed_window_smoke_requests",
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


def ci95_half_width(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * stdev(values) / (len(values) ** 0.5)


def find_comparison_files(input_root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in input_root.rglob(pattern) if path.is_file())


def load_smoke_summary(paths: list[str], scenario: str) -> dict[str, float]:
    if not paths:
        return {"smoke_requests": 0.0, "smoke_success_rate": 0.0}
    path = Path(paths[-1])
    if not path.exists():
        return {"smoke_requests": 0.0, "smoke_success_rate": 0.0}
    data = json.loads(path.read_text(encoding="utf-8"))
    scenario_summary = data.get("scenarios", {}).get(scenario, {})
    return {
        "smoke_requests": as_float(scenario_summary.get("request_count")),
        "smoke_success_rate": as_float(scenario_summary.get("success_rate")),
    }


def flatten_mode(mode_name: str, mode: dict[str, Any], scenario: str) -> dict[str, Any]:
    kernel = mode.get("kernel_summary", {}) if isinstance(mode.get("kernel_summary"), dict) else {}
    smoke = load_smoke_summary(mode.get("smoke_summary_paths", []), scenario)
    return {
        f"{mode_name}_status": mode.get("status", ""),
        f"{mode_name}_duration_s": as_float(mode.get("duration_s")),
        f"{mode_name}_kernel_instances": as_float(kernel.get("kernel_instances")),
        f"{mode_name}_kernel_total_time_ns": as_float(kernel.get("kernel_total_time_ns")),
        f"{mode_name}_kernel_avg_duration_ns": as_float(kernel.get("kernel_avg_duration_ns")),
        f"{mode_name}_top_kernel_name": kernel.get("top_kernel_name", ""),
        f"{mode_name}_report_paths": "|".join(str(path) for path in mode.get("report_paths", [])),
        f"{mode_name}_smoke_requests": smoke["smoke_requests"],
        f"{mode_name}_smoke_success_rate": smoke["smoke_success_rate"],
    }


def load_records(comparison_files: list[Path]) -> list[dict[str, Any]]:
    records = []
    for path in comparison_files:
        comparison = json.loads(path.read_text(encoding="utf-8"))
        scenario = str(comparison.get("scenario", ""))
        record = {
            "comparison_path": str(path),
            "run_dir": str(path.parent),
            "created_at": comparison.get("created_at", ""),
            "model": comparison.get("model", ""),
            "scenario": scenario,
            "seed": comparison.get("seed", ""),
            "profiler_duration_saved_s": as_float(comparison.get("profiler_duration_saved_s")),
            "profiler_duration_saved_percent": as_float(comparison.get("profiler_duration_saved_percent")),
        }
        record.update(flatten_mode("automatic", comparison.get("automatic", {}), scenario))
        record.update(flatten_mode("fixed_window", comparison.get("fixed_window", {}), scenario))
        records.append(record)
    return records


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_scenario[str(record["scenario"])].append(record)

    rows = []
    for scenario, scenario_records in sorted(by_scenario.items()):
        row: dict[str, Any] = {
            "scenario": scenario,
            "model": scenario_records[0].get("model", ""),
            "repetitions": len(scenario_records),
            "seeds": "|".join(str(record.get("seed", "")) for record in scenario_records),
            "comparison_files": "|".join(str(record["comparison_path"]) for record in scenario_records),
            "all_modes_ok": int(
                all(
                    record.get("automatic_status") == "ok" and record.get("fixed_window_status") == "ok"
                    for record in scenario_records
                )
            ),
        }
        for field in NUMERIC_FIELDS:
            values = [as_float(record.get(field)) for record in scenario_records]
            row[f"{field}_mean"] = mean(values)
            row[f"{field}_stdev"] = stdev(values)
            row[f"{field}_min"] = min(values) if values else 0.0
            row[f"{field}_max"] = max(values) if values else 0.0
            row[f"{field}_ci95_half_width"] = ci95_half_width(values)
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, Any]], records: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = output_dir / f"vllm_nsys_aggregate_{timestamp}.csv"
    json_path = output_dir / f"vllm_nsys_aggregate_{timestamp}.json"

    fieldnames = list(rows[0].keys()) if rows else ["scenario", "repetitions"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "aggregate_csv": str(csv_path),
        "records": records,
        "scenarios": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("RQ1/runs"))
    parser.add_argument("--pattern", default="vllm_l4_nsys_queue_pressure_rep*/vllm_nsys_comparison_*.json")
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis/vllm_l4_nsys_queue_pressure"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison_files = find_comparison_files(args.input_root, args.pattern)
    if not comparison_files:
        raise SystemExit(f"No vLLM comparison files found under {args.input_root} with pattern {args.pattern}")
    records = load_records(comparison_files)
    rows = aggregate(records)
    csv_path, json_path = write_outputs(rows, records, args.output_dir)
    print(f"loaded_comparison_files={len(comparison_files)}")
    print(f"loaded_records={len(records)}")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
