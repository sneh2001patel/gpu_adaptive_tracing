#!/usr/bin/env python3
"""Create compact RQ1 tables and first-pass success checks from aggregate output."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any


EXPECTED_LABELS = {
    "compute_bound": "compute_bound",
    "launch_overhead_or_small_kernel": "launch_overhead_or_small_kernel",
    "mixed": "mixed",
}


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_aggregate(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        workloads = payload.get("workloads", [])
        if not isinstance(workloads, list):
            raise SystemExit(f"Aggregate JSON does not contain a workload list: {path}")
        return [dict(row) for row in workloads]

    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_counts(raw_counts: Any) -> dict[str, int]:
    if isinstance(raw_counts, dict):
        return {str(key): int(value) for key, value in raw_counts.items()}
    if isinstance(raw_counts, str) and raw_counts:
        parsed = json.loads(raw_counts)
        return {str(key): int(value) for key, value in parsed.items()}
    return {}


def build_rows(rows: list[dict[str, Any]], min_saved_percent: float, min_match_rate: float) -> list[dict[str, Any]]:
    table_rows = []
    for row in rows:
        workload = str(row["workload"])
        reps = int(as_float(row.get("repetitions")))
        auto_duration = as_float(row.get("automatic_profiler_duration_s_mean"))
        fixed_duration = as_float(row.get("fixed_window_profiler_duration_s_mean"))
        saved = as_float(row.get("profiler_duration_saved_s_mean"))
        saved_percent = (saved / fixed_duration) * 100 if fixed_duration else 0.0

        suspicious_total = as_float(row.get("automatic_suspicious_windows_mean")) * reps
        expected_label = EXPECTED_LABELS.get(workload, workload)
        diagnosis_counts = parse_counts(row.get("automatic_diagnosis_counts_total"))
        expected_count = diagnosis_counts.get(expected_label, 0)
        match_rate = expected_count / suspicious_total if suspicious_total else 0.0
        burst_stdev = as_float(row.get("automatic_profiler_bursts_stdev"))

        duration_pass = saved_percent >= min_saved_percent
        diagnosis_pass = match_rate >= min_match_rate
        burst_stability_pass = burst_stdev <= 0.25
        overall_pass = duration_pass and diagnosis_pass and burst_stability_pass

        table_rows.append(
            {
                "workload": workload,
                "repetitions": reps,
                "automatic_trace_s_mean": round(auto_duration, 3),
                "fixed_window_trace_s_mean": round(fixed_duration, 3),
                "trace_time_saved_s_mean": round(saved, 3),
                "trace_time_saved_percent": round(saved_percent, 1),
                "automatic_bursts_mean": round(as_float(row.get("automatic_profiler_bursts_mean")), 3),
                "automatic_bursts_stdev": round(burst_stdev, 3),
                "expected_diagnosis_label": expected_label,
                "expected_label_match_rate": round(match_rate, 3),
                "duration_saved_pass": duration_pass,
                "diagnosis_match_pass": diagnosis_pass,
                "burst_stability_pass": burst_stability_pass,
                "overall_pass": overall_pass,
            }
        )
    return table_rows


def write_csv(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"paper_table_{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_markdown(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"paper_table_{timestamp}.md"
    headers = [
        "Workload",
        "Reps",
        "Auto trace s",
        "Fixed trace s",
        "Saved %",
        "Match rate",
        "Pass",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["workload"]),
                    str(row["repetitions"]),
                    str(row["automatic_trace_s_mean"]),
                    str(row["fixed_window_trace_s_mean"]),
                    str(row["trace_time_saved_percent"]),
                    str(row["expected_label_match_rate"]),
                    "yes" if row["overall_pass"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_latex(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"paper_table_{timestamp}.tex"
    lines = [
        "\\begin{tabular}{lrrrrr}",
        "\\hline",
        "Workload & Reps & Auto trace s & Fixed trace s & Saved \\% & Match rate \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(
            f"{row['workload']} & {row['repetitions']} & "
            f"{row['automatic_trace_s_mean']} & {row['fixed_window_trace_s_mean']} & "
            f"{row['trace_time_saved_percent']} & {row['expected_label_match_rate']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_success_criteria(
    rows: list[dict[str, Any]],
    output_dir: Path,
    timestamp: int,
    min_saved_percent: float,
    min_match_rate: float,
) -> Path:
    path = output_dir / f"success_criteria_{timestamp}.json"
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "criteria": {
            "minimum_trace_time_saved_percent": min_saved_percent,
            "minimum_expected_label_match_rate": min_match_rate,
            "maximum_automatic_profiler_burst_stdev": 0.25,
        },
        "results": rows,
        "overall_pass": all(row["overall_pass"] for row in rows),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis/paper_tables"))
    parser.add_argument("--min-saved-percent", type=float, default=25.0)
    parser.add_argument("--min-match-rate", type=float, default=0.95)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_aggregate(args.aggregate)
    table_rows = build_rows(rows, args.min_saved_percent, args.min_match_rate)
    if not table_rows:
        raise SystemExit("No rows found in aggregate input")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = write_csv(table_rows, args.output_dir, timestamp)
    markdown_path = write_markdown(table_rows, args.output_dir, timestamp)
    latex_path = write_latex(table_rows, args.output_dir, timestamp)
    criteria_path = write_success_criteria(
        table_rows,
        args.output_dir,
        timestamp,
        args.min_saved_percent,
        args.min_match_rate,
    )

    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {latex_path}")
    print(f"wrote {criteria_path}")


if __name__ == "__main__":
    main()
