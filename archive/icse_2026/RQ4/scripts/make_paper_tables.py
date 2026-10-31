#!/usr/bin/env python3
"""Create compact RQ4 policy ranking tables from replay summaries."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def load_summary(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(row) for row in payload.get("summary", [])]


def dominated(candidate: dict[str, Any], other: dict[str, Any]) -> bool:
    no_worse = (
        as_float(other["top1_accuracy_mean"]) >= as_float(candidate["top1_accuracy_mean"])
        and as_float(other["premature_stop_rate_mean"]) <= as_float(candidate["premature_stop_rate_mean"])
        and as_float(other["re_escalation_rate_mean"]) <= as_float(candidate["re_escalation_rate_mean"])
        and as_float(other["heavy_trace_duration_s_mean"]) <= as_float(candidate["heavy_trace_duration_s_mean"])
    )
    strictly_better = (
        as_float(other["top1_accuracy_mean"]) > as_float(candidate["top1_accuracy_mean"])
        or as_float(other["premature_stop_rate_mean"]) < as_float(candidate["premature_stop_rate_mean"])
        or as_float(other["re_escalation_rate_mean"]) < as_float(candidate["re_escalation_rate_mean"])
        or as_float(other["heavy_trace_duration_s_mean"]) < as_float(candidate["heavy_trace_duration_s_mean"])
    )
    return no_worse and strictly_better


def build_policy_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summary_rows:
        grouped[str(row["policy"])].append(row)

    max_trace = max((as_float(row.get("heavy_trace_duration_s_mean")) for row in summary_rows), default=0.0)
    output = []
    for policy, rows in sorted(grouped.items()):
        trace_mean = mean([as_float(row.get("heavy_trace_duration_s_mean")) for row in rows])
        top1 = mean([as_float(row.get("top1_accuracy")) for row in rows])
        premature = mean([as_float(row.get("premature_stop_rate")) for row in rows])
        re_escalation = mean([as_float(row.get("re_escalation_rate")) for row in rows])
        saved = mean([as_float(row.get("duration_saved_vs_repeated_fixed_percent")) for row in rows])
        cost_efficiency = 0.0 if max_trace <= 0 else 1.0 - trace_mean / max_trace
        composite = (
            0.40 * top1
            + 0.25 * (1.0 - premature)
            + 0.20 * (1.0 - re_escalation)
            + 0.15 * cost_efficiency
        )
        output.append(
            {
                "policy": policy,
                "scenario_count": len(rows),
                "top1_accuracy_mean": top1,
                "premature_stop_rate_mean": premature,
                "re_escalation_rate_mean": re_escalation,
                "heavy_trace_duration_s_mean": trace_mean,
                "selected_windows_mean": mean([as_float(row.get("selected_windows_mean")) for row in rows]),
                "duration_saved_vs_repeated_fixed_percent_mean": saved,
                "cost_efficiency_score": cost_efficiency,
                "composite_score": composite,
            }
        )

    for row in output:
        row["pareto_status"] = "dominated" if any(dominated(row, other) for other in output if other is not row) else "pareto"

    output.sort(
        key=lambda row: (
            -as_float(row["composite_score"]),
            as_float(row["premature_stop_rate_mean"]),
            -as_float(row["top1_accuracy_mean"]),
            as_float(row["heavy_trace_duration_s_mean"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Rank",
        "Policy",
        "Top-1",
        "Premature",
        "Re-escalation",
        "Trace s",
        "Saved %",
        "Score",
        "Pareto",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["policy"]),
                    str(row["top1_accuracy_mean"]),
                    str(row["premature_stop_rate_mean"]),
                    str(row["re_escalation_rate_mean"]),
                    str(row["heavy_trace_duration_s_mean"]),
                    str(row["duration_saved_vs_repeated_fixed_percent_mean"]),
                    str(row["composite_score"]),
                    str(row["pareto_status"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "\\begin{tabular}{rlrrrrrl}",
        "\\hline",
        "Rank & Policy & Top-1 & Premature & Re-esc. & Trace s & Saved \\% & Pareto \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(
            f"{row['rank']} & {row['policy']} & {row['top1_accuracy_mean']} & "
            f"{row['premature_stop_rate_mean']} & {row['re_escalation_rate_mean']} & "
            f"{row['heavy_trace_duration_s_mean']} & "
            f"{row['duration_saved_vs_repeated_fixed_percent_mean']} & {row['pareto_status']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ4/analysis/paper_tables"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [rounded(row) for row in build_policy_rows(load_summary(args.summary))]
    if not rows:
        raise SystemExit("No RQ4 summary rows found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    csv_path = args.output_dir / f"rq4_policy_ranking_{timestamp}.csv"
    md_path = args.output_dir / f"rq4_policy_ranking_{timestamp}.md"
    tex_path = args.output_dir / f"rq4_policy_ranking_{timestamp}.tex"
    json_path = args.output_dir / f"rq4_policy_ranking_{timestamp}.json"
    write_csv(csv_path, rows)
    write_markdown(md_path, rows)
    write_latex(tex_path, rows)
    json_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "summary": str(args.summary),
                "score_definition": {
                    "top1_accuracy_weight": 0.40,
                    "no_premature_stop_weight": 0.25,
                    "no_re_escalation_weight": 0.20,
                    "cost_efficiency_weight": 0.15,
                },
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")
    print(f"wrote {tex_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
