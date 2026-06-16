#!/usr/bin/env python3
"""Create simple SVG figures for RQ1 paper drafts from aggregate output."""

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


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [dict(row) for row in payload.get("workloads", [])]
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_counts(raw_counts: Any) -> dict[str, int]:
    if isinstance(raw_counts, dict):
        return {str(key): int(value) for key, value in raw_counts.items()}
    if isinstance(raw_counts, str) and raw_counts:
        parsed = json.loads(raw_counts)
        return {str(key): int(value) for key, value in parsed.items()}
    return {}


def label(text: str) -> str:
    return text.replace("_or_", "/").replace("_", " ")


def values_for_figures(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    savings = []
    matches = []
    for row in rows:
        workload = str(row["workload"])
        reps = int(as_float(row.get("repetitions")))
        fixed_duration = as_float(row.get("fixed_window_profiler_duration_s_mean"))
        saved = as_float(row.get("profiler_duration_saved_s_mean"))
        saved_pct = (saved / fixed_duration) * 100 if fixed_duration else 0.0
        saved_ci = as_float(row.get("profiler_duration_saved_s_ci95_half_width"))
        saved_pct_ci = (saved_ci / fixed_duration) * 100 if fixed_duration else 0.0

        suspicious_total = as_float(row.get("automatic_suspicious_windows_mean")) * reps
        expected = EXPECTED_LABELS.get(workload, workload)
        counts = parse_counts(row.get("automatic_diagnosis_counts_total"))
        match_rate = counts.get(expected, 0) / suspicious_total if suspicious_total else 0.0

        savings.append({"workload": workload, "value": saved_pct, "ci": saved_pct_ci})
        matches.append({"workload": workload, "value": match_rate * 100, "ci": 0.0})
    return savings, matches


def write_bar_svg(
    rows: list[dict[str, Any]],
    path: Path,
    title: str,
    y_label: str,
    y_max: float,
    threshold: float | None = None,
) -> None:
    width = 820
    height = 430
    left = 90
    right = 40
    top = 55
    bottom = 105
    plot_w = width - left - right
    plot_h = height - top - bottom
    bar_w = 88
    gap = (plot_w - len(rows) * bar_w) / max(len(rows), 1)

    def y_pos(value: float) -> float:
        return top + plot_h - (min(value, y_max) / y_max) * plot_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">{title}</text>',
        f'<text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14">{y_label}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#222" stroke-width="1.3"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#222" stroke-width="1.3"/>',
    ]
    for tick in range(0, int(y_max) + 1, 20):
        y = y_pos(tick)
        lines.append(f'<line x1="{left - 5}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#d8d8d8" stroke-width="0.8"/>')
        lines.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{tick}</text>')
    if threshold is not None:
        y = y_pos(threshold)
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#8b1e3f" stroke-width="1.5" stroke-dasharray="5 4"/>')
        lines.append(f'<text x="{left + plot_w - 4}" y="{y - 7:.1f}" text-anchor="end" font-family="Arial" font-size="12" fill="#8b1e3f">threshold {threshold:g}%</text>')

    for idx, row in enumerate(rows):
        x = left + gap / 2 + idx * (bar_w + gap)
        y = y_pos(row["value"])
        h = top + plot_h - y
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="#2f6f73"/>')
        lines.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-family="Arial" font-size="13">{row["value"]:.1f}</text>')
        if row.get("ci", 0) > 0:
            y_hi = y_pos(row["value"] + row["ci"])
            y_lo = y_pos(max(row["value"] - row["ci"], 0))
            cx = x + bar_w / 2
            lines.append(f'<line x1="{cx:.1f}" y1="{y_hi:.1f}" x2="{cx:.1f}" y2="{y_lo:.1f}" stroke="#222" stroke-width="1.3"/>')
            lines.append(f'<line x1="{cx - 8:.1f}" y1="{y_hi:.1f}" x2="{cx + 8:.1f}" y2="{y_hi:.1f}" stroke="#222" stroke-width="1.3"/>')
            lines.append(f'<line x1="{cx - 8:.1f}" y1="{y_lo:.1f}" x2="{cx + 8:.1f}" y2="{y_lo:.1f}" stroke="#222" stroke-width="1.3"/>')
        label_lines = label(str(row["workload"])).split("/")
        for line_idx, label_part in enumerate(label_lines):
            lines.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 28 + line_idx * 16}" '
                f'text-anchor="middle" font-family="Arial" font-size="12">{label_part}</text>'
            )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis/figures"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.aggregate)
    savings, matches = values_for_figures(rows)
    timestamp = int(time.time())
    savings_path = args.output_dir / f"trace_time_saved_percent_{timestamp}.svg"
    matches_path = args.output_dir / f"diagnosis_match_rate_{timestamp}.svg"
    write_bar_svg(savings, savings_path, "Automatic tracing reduces profiler duration", "Profiler time saved (%)", 100.0, threshold=25.0)
    write_bar_svg(matches, matches_path, "Automatic diagnosis matches controlled workload", "Expected-label match rate (%)", 100.0, threshold=95.0)
    print(f"wrote {savings_path}")
    print(f"wrote {matches_path}")


if __name__ == "__main__":
    main()
