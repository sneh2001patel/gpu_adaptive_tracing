#!/usr/bin/env python3
"""Aggregate RQ1 comparison summaries across repeated runs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NUMERIC_FIELDS = (
    "automatic_windows",
    "fixed_window_windows",
    "automatic_suspicious_windows",
    "fixed_window_suspicious_windows",
    "automatic_profiler_bursts",
    "fixed_window_profiler_bursts",
    "automatic_profiler_duration_s",
    "fixed_window_profiler_duration_s",
    "automatic_profiler_kernel_instances",
    "fixed_window_profiler_kernel_instances",
    "automatic_profiler_kernel_total_time_ns",
    "fixed_window_profiler_kernel_total_time_ns",
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


def load_records(comparison_files: list[Path]) -> list[dict[str, Any]]:
    records = []
    for path in comparison_files:
        comparison = json.loads(path.read_text(encoding="utf-8"))
        workloads = comparison.get("workloads", {})
        if not isinstance(workloads, dict):
            continue
        for workload, result in workloads.items():
            if not isinstance(result, dict):
                continue
            record = {
                "comparison_path": str(path),
                "run_dir": str(path.parent),
                "workload": workload,
            }
            record.update(result)
            records.append(record)
    return records


def count_diagnoses(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        value = record.get(field, {})
        if isinstance(value, dict):
            counts.update({str(label): int(count) for label, count in value.items()})
    return dict(sorted(counts.items()))


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_workload: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_workload[str(record["workload"])].append(record)

    rows = []
    for workload, workload_records in sorted(by_workload.items()):
        row: dict[str, Any] = {
            "workload": workload,
            "repetitions": len(workload_records),
            "comparison_files": "|".join(sorted({str(record["comparison_path"]) for record in workload_records})),
        }
        for field in NUMERIC_FIELDS:
            values = [as_float(record.get(field)) for record in workload_records]
            row[f"{field}_mean"] = mean(values)
            row[f"{field}_stdev"] = stdev(values)
            row[f"{field}_min"] = min(values) if values else 0.0
            row[f"{field}_max"] = max(values) if values else 0.0
            row[f"{field}_ci95_half_width"] = ci95_half_width(values)

        auto_duration = [as_float(record.get("automatic_profiler_duration_s")) for record in workload_records]
        fixed_duration = [as_float(record.get("fixed_window_profiler_duration_s")) for record in workload_records]
        saved = [fixed - auto for auto, fixed in zip(auto_duration, fixed_duration, strict=True)]
        row["profiler_duration_saved_s_mean"] = mean(saved)
        row["profiler_duration_saved_s_stdev"] = stdev(saved)
        row["profiler_duration_saved_s_min"] = min(saved) if saved else 0.0
        row["profiler_duration_saved_s_max"] = max(saved) if saved else 0.0
        row["profiler_duration_saved_s_ci95_half_width"] = ci95_half_width(saved)
        row["automatic_diagnosis_counts_total"] = json.dumps(
            count_diagnoses(workload_records, "automatic_diagnosis_counts"),
            sort_keys=True,
        )
        row["fixed_window_diagnosis_counts_total"] = json.dumps(
            count_diagnoses(workload_records, "fixed_window_diagnosis_counts"),
            sort_keys=True,
        )
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, Any]], records: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = output_dir / f"aggregate_{timestamp}.csv"
    json_path = output_dir / f"aggregate_{timestamp}.json"

    fieldnames = list(rows[0].keys()) if rows else ["workload", "repetitions"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "aggregate_csv": str(csv_path),
        "records": records,
        "workloads": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("RQ1/runs"))
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis"))
    parser.add_argument("--pattern", default="comparison_*.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison_files = find_comparison_files(args.input_root, args.pattern)
    if not comparison_files:
        raise SystemExit(f"No comparison files found under {args.input_root} with pattern {args.pattern}")

    records = load_records(comparison_files)
    if not records:
        raise SystemExit("Comparison files were found, but no workload records were loaded")

    rows = aggregate(records)
    csv_path, json_path = write_outputs(rows, records, args.output_dir)
    print(f"loaded_comparison_files={len(comparison_files)}")
    print(f"loaded_workload_records={len(records)}")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
