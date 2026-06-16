#!/usr/bin/env python3
"""Analyze RQ2 diagnosis accuracy from per-window RQ1 CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_LABELS = {
    "compute_bound": "compute_bound",
    "launch_overhead_or_small_kernel": "launch_overhead_or_small_kernel",
    "mixed": "mixed",
}

AMBIGUOUS_LABELS = {
    "healthy_or_not_suspicious",
    "latency_regression_unknown_gpu_cause",
    "possible_launch_overhead_or_small_kernel",
    "possible_memory_pressure",
}

MODES = ("automatic", "fixed_window")


def as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def run_dirs(input_root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in input_root.glob(pattern) if path.is_dir())


def load_windows(run_dir: Path) -> list[dict[str, Any]]:
    records = []
    for mode in MODES:
        for csv_path in sorted((run_dir / mode).glob("*.csv")):
            with csv_path.open("r", newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    workload = row.get("workload", "")
                    records.append(
                        {
                            "run_dir": str(run_dir),
                            "mode": mode,
                            "workload": workload,
                            "expected_label": EXPECTED_LABELS.get(workload, workload),
                            "window_id": as_int(row.get("window_id")),
                            "diagnosis_label": row.get("diagnosis_label", ""),
                            "trigger_trace": as_int(row.get("trigger_trace")),
                            "csv": str(csv_path),
                        }
                    )
    return records


def first_correct_window(records: list[dict[str, Any]]) -> int | None:
    correct = [
        as_int(record["window_id"])
        for record in records
        if record["diagnosis_label"] == record["expected_label"]
    ]
    return min(correct) if correct else None


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(str(record["workload"]), str(record["mode"]))].append(record)

    rows = []
    for (workload, mode), group in sorted(groups.items()):
        expected = EXPECTED_LABELS.get(workload, workload)
        suspicious = [record for record in group if as_int(record["trigger_trace"]) == 1]
        denominator = suspicious or group
        correct = [record for record in denominator if record["diagnosis_label"] == expected]
        ambiguous = [record for record in denominator if record["diagnosis_label"] in AMBIGUOUS_LABELS]
        first_windows_by_run = []
        for run_dir in sorted({str(record["run_dir"]) for record in group}):
            run_group = [record for record in group if record["run_dir"] == run_dir]
            first = first_correct_window(run_group)
            if first is not None:
                first_windows_by_run.append(float(first))
        rows.append(
            {
                "workload": workload,
                "mode": mode,
                "expected_label": expected,
                "runs": len({str(record["run_dir"]) for record in group}),
                "windows": len(group),
                "suspicious_windows": len(suspicious),
                "match_rate_on_suspicious_or_all": len(correct) / len(denominator) if denominator else 0.0,
                "ambiguous_or_unknown_rate": len(ambiguous) / len(denominator) if denominator else 0.0,
                "first_correct_window_mean": mean(first_windows_by_run),
                "first_correct_window_stdev": stdev(first_windows_by_run),
                "first_correct_window_missing_runs": len({str(record["run_dir"]) for record in group}) - len(first_windows_by_run),
            }
        )
    return rows


def confusion_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str, str]] = Counter()
    for record in records:
        if as_int(record["trigger_trace"]) != 1:
            continue
        key = (
            str(record["mode"]),
            str(record["workload"]),
            str(record["expected_label"]),
            str(record["diagnosis_label"]),
        )
        counts[key] += 1
    return [
        {
            "mode": mode,
            "workload": workload,
            "expected_label": expected,
            "diagnosis_label": diagnosis,
            "count": count,
        }
        for (mode, workload, expected, diagnosis), count in sorted(counts.items())
    ]


def disagreement_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, int], dict[str, str]] = defaultdict(dict)
    for record in records:
        key = (str(record["run_dir"]), str(record["workload"]), as_int(record["window_id"]))
        by_key[key][str(record["mode"])] = str(record["diagnosis_label"])

    grouped: dict[str, list[int]] = defaultdict(list)
    for (_run_dir, workload, _window_id), modes in by_key.items():
        if all(mode in modes for mode in MODES):
            grouped[workload].append(int(modes["automatic"] != modes["fixed_window"]))

    return [
        {
            "workload": workload,
            "paired_windows": len(values),
            "disagreement_rate": mean([float(value) for value in values]),
        }
        for workload, values in sorted(grouped.items())
    ]


def write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fieldnames = list(rows[0].keys()) if rows else fallback_fields
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("RQ1/runs"))
    parser.add_argument("--run-pattern", default="rq1_compare_rep*")
    parser.add_argument("--output-dir", type=Path, default=Path("RQ2/analysis/step9_accuracy"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs = run_dirs(args.input_root, args.run_pattern)
    if not runs:
        raise SystemExit(f"No run directories found under {args.input_root} with pattern {args.run_pattern}")

    records = []
    for run_dir in runs:
        records.extend(load_windows(run_dir))
    if not records:
        raise SystemExit("No per-window CSV records were loaded")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    summary = summarize(records)
    confusion = confusion_rows(records)
    disagreement = disagreement_rows(records)

    summary_path = args.output_dir / f"rq2_accuracy_summary_{timestamp}.csv"
    confusion_path = args.output_dir / f"rq2_confusion_{timestamp}.csv"
    disagreement_path = args.output_dir / f"rq2_disagreement_{timestamp}.csv"
    json_path = args.output_dir / f"rq2_accuracy_{timestamp}.json"

    write_csv(summary_path, summary, ["workload", "mode"])
    write_csv(confusion_path, confusion, ["mode", "workload", "expected_label", "diagnosis_label", "count"])
    write_csv(disagreement_path, disagreement, ["workload", "paired_windows", "disagreement_rate"])
    json_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "run_dirs": [str(path) for path in runs],
                "summary_csv": str(summary_path),
                "confusion_csv": str(confusion_path),
                "disagreement_csv": str(disagreement_path),
                "summary": summary,
                "confusion": confusion,
                "disagreement": disagreement,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"loaded_run_dirs={len(runs)}")
    print(f"loaded_window_records={len(records)}")
    print(f"wrote {summary_path}")
    print(f"wrote {confusion_path}")
    print(f"wrote {disagreement_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
