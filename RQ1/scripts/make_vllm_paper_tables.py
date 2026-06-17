#!/usr/bin/env python3
"""Create compact paper-table outputs for vLLM RQ1 aggregate results."""

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


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("scenarios", [])
        if not isinstance(rows, list):
            raise SystemExit(f"Aggregate JSON does not contain a scenario list: {path}")
        return [dict(row) for row in rows]
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_rows(rows: list[dict[str, Any]], min_saved_percent: float, min_success_rate: float) -> list[dict[str, Any]]:
    table_rows = []
    for row in rows:
        saved_percent = as_float(row.get("profiler_duration_saved_percent_mean"))
        auto_success = as_float(row.get("automatic_smoke_success_rate_mean"))
        fixed_success = as_float(row.get("fixed_window_smoke_success_rate_mean"))
        all_modes_ok = int(as_float(row.get("all_modes_ok")))
        duration_pass = saved_percent >= min_saved_percent
        success_pass = auto_success >= min_success_rate and fixed_success >= min_success_rate and all_modes_ok == 1
        table_rows.append(
            {
                "scenario": row.get("scenario", ""),
                "model": row.get("model", ""),
                "repetitions": int(as_float(row.get("repetitions"))),
                "seeds": row.get("seeds", ""),
                "automatic_trace_s_mean": round(as_float(row.get("automatic_duration_s_mean")), 3),
                "fixed_window_trace_s_mean": round(as_float(row.get("fixed_window_duration_s_mean")), 3),
                "trace_time_saved_s_mean": round(as_float(row.get("profiler_duration_saved_s_mean")), 3),
                "trace_time_saved_percent_mean": round(saved_percent, 1),
                "trace_time_saved_percent_ci95": round(as_float(row.get("profiler_duration_saved_percent_ci95_half_width")), 2),
                "automatic_kernel_instances_mean": round(as_float(row.get("automatic_kernel_instances_mean")), 3),
                "fixed_window_kernel_instances_mean": round(as_float(row.get("fixed_window_kernel_instances_mean")), 3),
                "automatic_smoke_success_rate_mean": round(auto_success, 3),
                "fixed_window_smoke_success_rate_mean": round(fixed_success, 3),
                "duration_saved_pass": duration_pass,
                "success_rate_pass": success_pass,
                "overall_pass": duration_pass and success_pass,
            }
        )
    return table_rows


def write_csv(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"vllm_paper_table_{timestamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_markdown(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"vllm_paper_table_{timestamp}.md"
    headers = ["Scenario", "Reps", "Auto trace s", "Fixed trace s", "Saved %", "Success %", "Pass"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        success = min(row["automatic_smoke_success_rate_mean"], row["fixed_window_smoke_success_rate_mean"])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    str(row["repetitions"]),
                    str(row["automatic_trace_s_mean"]),
                    str(row["fixed_window_trace_s_mean"]),
                    str(row["trace_time_saved_percent_mean"]),
                    str(success),
                    "yes" if row["overall_pass"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_latex(rows: list[dict[str, Any]], output_dir: Path, timestamp: int) -> Path:
    path = output_dir / f"vllm_paper_table_{timestamp}.tex"
    lines = [
        "\\begin{tabular}{lrrrrr}",
        "\\hline",
        "Scenario & Reps & Auto trace s & Fixed trace s & Saved \\% & Success \\% \\\\",
        "\\hline",
    ]
    for row in rows:
        success = min(row["automatic_smoke_success_rate_mean"], row["fixed_window_smoke_success_rate_mean"])
        lines.append(
            f"{row['scenario']} & {row['repetitions']} & "
            f"{row['automatic_trace_s_mean']} & {row['fixed_window_trace_s_mean']} & "
            f"{row['trace_time_saved_percent_mean']} & {success} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_success_criteria(
    rows: list[dict[str, Any]],
    output_dir: Path,
    timestamp: int,
    min_saved_percent: float,
    min_success_rate: float,
) -> Path:
    path = output_dir / f"vllm_success_criteria_{timestamp}.json"
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "criteria": {
            "minimum_trace_time_saved_percent": min_saved_percent,
            "minimum_smoke_success_rate": min_success_rate,
        },
        "results": rows,
        "overall_pass": all(row["overall_pass"] for row in rows),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis/vllm_paper_tables"))
    parser.add_argument("--min-saved-percent", type=float, default=15.0)
    parser.add_argument("--min-success-rate", type=float, default=99.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(load_rows(args.aggregate), args.min_saved_percent, args.min_success_rate)
    if not rows:
        raise SystemExit("No rows found in vLLM aggregate input")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = write_csv(rows, args.output_dir, timestamp)
    markdown_path = write_markdown(rows, args.output_dir, timestamp)
    latex_path = write_latex(rows, args.output_dir, timestamp)
    criteria_path = write_success_criteria(rows, args.output_dir, timestamp, args.min_saved_percent, args.min_success_rate)
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {latex_path}")
    print(f"wrote {criteria_path}")


if __name__ == "__main__":
    main()
