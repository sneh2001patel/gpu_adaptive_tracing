#!/usr/bin/env python3
"""Create compact paper-table outputs for RQ2 accuracy reports."""

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


def load_report(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [dict(row) for row in payload.get("summary", [])], [dict(row) for row in payload.get("disagreement", [])]

    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)], []


def disagreement_by_workload(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {str(row.get("workload", "")): as_float(row.get("disagreement_rate")) for row in rows}


def build_rows(
    summary_rows: list[dict[str, Any]],
    disagreement_rows: list[dict[str, Any]],
    min_match_rate: float,
    max_ambiguous_rate: float,
) -> list[dict[str, Any]]:
    disagreement = disagreement_by_workload(disagreement_rows)
    rows = []
    for row in summary_rows:
        match_rate = as_float(row.get("match_rate_on_suspicious_or_all"))
        ambiguous_rate = as_float(row.get("ambiguous_or_unknown_rate"))
        missing_runs = int(as_float(row.get("first_correct_window_missing_runs")))
        match_pass = match_rate >= min_match_rate
        ambiguous_pass = ambiguous_rate <= max_ambiguous_rate
        first_correct_pass = missing_runs == 0
        rows.append(
            {
                "workload": row.get("workload", ""),
                "mode": row.get("mode", ""),
                "expected_label": row.get("expected_label", ""),
                "runs": int(as_float(row.get("runs"))),
                "windows": int(as_float(row.get("windows"))),
                "suspicious_windows": int(as_float(row.get("suspicious_windows"))),
                "expected_label_match_rate": round(match_rate, 3),
                "ambiguous_or_unknown_rate": round(ambiguous_rate, 3),
                "first_correct_window_mean": round(as_float(row.get("first_correct_window_mean")), 3),
                "first_correct_window_stdev": round(as_float(row.get("first_correct_window_stdev")), 3),
                "first_correct_window_missing_runs": missing_runs,
                "first_correct_seconds_mean": round(as_float(row.get("first_correct_seconds_mean")), 3),
                "first_correct_seconds_stdev": round(as_float(row.get("first_correct_seconds_stdev")), 3),
                "first_correct_seconds_missing_runs": int(as_float(row.get("first_correct_seconds_missing_runs"))),
                "auto_fixed_disagreement_rate": round(disagreement.get(str(row.get("workload", "")), 0.0), 3),
                "profiler_burst_count": int(as_float(row.get("profiler_burst_count"))),
                "profiler_duration_s_total": round(as_float(row.get("profiler_duration_s_total")), 3),
                "profiler_duration_s_mean": round(as_float(row.get("profiler_duration_s_mean")), 3),
                "profiler_kernel_instances_total": round(as_float(row.get("profiler_kernel_instances_total")), 3),
                "profiler_kernel_instances_mean": round(as_float(row.get("profiler_kernel_instances_mean")), 3),
                "profiler_kernel_total_time_ns_total": round(as_float(row.get("profiler_kernel_total_time_ns_total")), 3),
                "profiler_report_count_total": int(as_float(row.get("profiler_report_count_total"))),
                "match_rate_pass": match_pass,
                "ambiguous_rate_pass": ambiguous_pass,
                "first_correct_pass": first_correct_pass,
                "overall_pass": match_pass and ambiguous_pass and first_correct_pass,
            }
        )
    return rows


def write_csv(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq2_paper_table_{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_markdown(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq2_paper_table_{timestamp}.md"
    headers = [
        "Workload",
        "Mode",
        "Match rate",
        "Ambiguous rate",
        "First correct window",
        "First correct s",
        "Disagree rate",
        "Trace s",
        "Kernel instances",
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
                    str(row["mode"]),
                    str(row["expected_label_match_rate"]),
                    str(row["ambiguous_or_unknown_rate"]),
                    str(row["first_correct_window_mean"]),
                    str(row["first_correct_seconds_mean"]),
                    str(row["auto_fixed_disagreement_rate"]),
                    str(row["profiler_duration_s_total"]),
                    str(row["profiler_kernel_instances_total"]),
                    "yes" if row["overall_pass"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_latex(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"rq2_paper_table_{timestamp}.tex"
    lines = [
        "\\begin{tabular}{llrrrrrrr}",
        "\\hline",
        "Workload & Mode & Match rate & Ambiguous rate & First correct & First correct s & Disagree rate & Trace s & Kernel instances \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(
            f"{row['workload']} & {row['mode']} & "
            f"{row['expected_label_match_rate']} & {row['ambiguous_or_unknown_rate']} & "
            f"{row['first_correct_window_mean']} & {row['first_correct_seconds_mean']} & "
            f"{row['auto_fixed_disagreement_rate']} & "
            f"{row['profiler_duration_s_total']} & {row['profiler_kernel_instances_total']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_success_criteria(
    rows: list[dict[str, Any]],
    output_dir: Path,
    timestamp: int,
    min_match_rate: float,
    max_ambiguous_rate: float,
) -> Path:
    path = output_dir / f"rq2_success_criteria_{timestamp}.json"
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "criteria": {
            "minimum_expected_label_match_rate": min_match_rate,
            "maximum_ambiguous_or_unknown_rate": max_ambiguous_rate,
            "maximum_first_correct_window_missing_runs": 0,
        },
        "results": rows,
        "overall_pass": all(row["overall_pass"] for row in rows),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ2/analysis/paper_tables"))
    parser.add_argument("--min-match-rate", type=float, default=0.95)
    parser.add_argument("--max-ambiguous-rate", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_rows, disagreement_rows = load_report(args.report)
    rows = build_rows(summary_rows, disagreement_rows, args.min_match_rate, args.max_ambiguous_rate)
    if not rows:
        raise SystemExit("No RQ2 summary rows found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = write_csv(rows, args.output_dir, timestamp)
    markdown_path = write_markdown(rows, args.output_dir, timestamp)
    latex_path = write_latex(rows, args.output_dir, timestamp)
    criteria_path = write_success_criteria(rows, args.output_dir, timestamp, args.min_match_rate, args.max_ambiguous_rate)
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {latex_path}")
    print(f"wrote {criteria_path}")


if __name__ == "__main__":
    main()
