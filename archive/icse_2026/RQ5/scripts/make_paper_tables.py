#!/usr/bin/env python3
"""Create compact RQ5 signal-ranking paper tables."""

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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def row_by_signal(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("signal")): dict(row) for row in rows}


def build_signal_rows(stable: dict[str, Any], stress: dict[str, Any]) -> list[dict[str, Any]]:
    stable_by_signal = row_by_signal(stable.get("summary", []))
    stress_by_signal = row_by_signal(stress.get("summary", []))
    rows = []
    for signal in sorted(set(stable_by_signal) | set(stress_by_signal)):
        stable_row = stable_by_signal.get(signal, {})
        stress_row = stress_by_signal.get(signal, {})
        stable_f1 = as_float(stable_row.get("correct_stop_f1"))
        stress_f1 = as_float(stress_row.get("correct_stop_f1"))
        stress_ambiguous_f1 = as_float(stress_row.get("ambiguous_stop_f1"))
        precision_floor = min(
            as_float(stable_row.get("correct_stop_precision")),
            as_float(stress_row.get("correct_stop_precision")),
        )
        score = 0.35 * stable_f1 + 0.45 * stress_f1 + 0.20 * precision_floor - 0.25 * stress_ambiguous_f1
        rows.append(
            {
                "signal": signal,
                "stable_correct_f1": stable_f1,
                "stress_correct_f1": stress_f1,
                "stress_ambiguous_f1": stress_ambiguous_f1,
                "precision_floor": precision_floor,
                "paper_signal_score": score,
                "paper_ready": (
                    precision_floor >= 0.90
                    and stress_f1 >= 0.70
                    and stress_ambiguous_f1 <= 0.10
                ),
            }
        )
    rows.sort(key=lambda row: (-as_float(row["paper_signal_score"]), row["signal"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_numeric_rows(stress: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in stress.get("numeric_summary", []):
        rows.append(
            {
                "signal": row.get("signal", ""),
                "correlation_with_correct_stop": as_float(row.get("correlation_with_correct_stop")),
                "correlation_with_ambiguous_stop": as_float(row.get("correlation_with_ambiguous_stop")),
                "mean_when_correct_stop": as_float(row.get("mean_when_correct_stop")),
                "mean_when_not_correct_stop": as_float(row.get("mean_when_not_correct_stop")),
            }
        )
    rows.sort(key=lambda row: -abs(as_float(row["correlation_with_correct_stop"])))
    return rows


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_signal_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Rank",
        "Signal",
        "Stable F1",
        "Stress F1",
        "Stress ambig F1",
        "Precision floor",
        "Score",
        "Paper-ready",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["signal"]),
                    str(row["stable_correct_f1"]),
                    str(row["stress_correct_f1"]),
                    str(row["stress_ambiguous_f1"]),
                    str(row["precision_floor"]),
                    str(row["paper_signal_score"]),
                    "yes" if row["paper_ready"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_numeric_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = ["Signal", "Corr correct", "Corr ambiguous", "Mean correct", "Mean not correct"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["signal"]),
                    str(row["correlation_with_correct_stop"]),
                    str(row["correlation_with_ambiguous_stop"]),
                    str(row["mean_when_correct_stop"]),
                    str(row["mean_when_not_correct_stop"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "\\begin{tabular}{rlrrrrr}",
        "\\hline",
        "Rank & Signal & Stable F1 & Stress F1 & Ambig. F1 & Score & Ready \\\\",
        "\\hline",
    ]
    for row in rows:
        ready = "yes" if row["paper_ready"] else "no"
        lines.append(
            f"{row['rank']} & {row['signal']} & {row['stable_correct_f1']} & "
            f"{row['stress_correct_f1']} & {row['stress_ambiguous_f1']} & "
            f"{row['paper_signal_score']} & {ready} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-summary", type=Path, required=True)
    parser.add_argument("--stress-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ5/analysis/paper_tables"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stable = load_json(args.stable_summary)
    stress = load_json(args.stress_summary)
    signal_rows = [rounded(row) for row in build_signal_rows(stable, stress)]
    numeric_rows = [rounded(row) for row in build_numeric_rows(stress)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    signal_csv = args.output_dir / f"rq5_signal_ranking_{timestamp}.csv"
    signal_md = args.output_dir / f"rq5_signal_ranking_{timestamp}.md"
    signal_tex = args.output_dir / f"rq5_signal_ranking_{timestamp}.tex"
    numeric_csv = args.output_dir / f"rq5_numeric_signal_table_{timestamp}.csv"
    numeric_md = args.output_dir / f"rq5_numeric_signal_table_{timestamp}.md"
    output_json = args.output_dir / f"rq5_signal_tables_{timestamp}.json"
    write_csv(signal_csv, signal_rows)
    write_signal_markdown(signal_md, signal_rows)
    write_latex(signal_tex, signal_rows)
    write_csv(numeric_csv, numeric_rows)
    write_numeric_markdown(numeric_md, numeric_rows)
    output_json.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "stable_summary": str(args.stable_summary),
                "stress_summary": str(args.stress_summary),
                "criteria": {
                    "paper_ready_precision_floor": 0.90,
                    "paper_ready_stress_correct_f1": 0.70,
                    "paper_ready_max_stress_ambiguous_f1": 0.10,
                },
                "signal_rows": signal_rows,
                "numeric_rows": numeric_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {signal_csv}")
    print(f"wrote {signal_md}")
    print(f"wrote {signal_tex}")
    print(f"wrote {numeric_csv}")
    print(f"wrote {numeric_md}")
    print(f"wrote {output_json}")


if __name__ == "__main__":
    main()
