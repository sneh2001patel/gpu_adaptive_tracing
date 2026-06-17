#!/usr/bin/env python3
"""Create simple SVG figures for vLLM RQ1 aggregate results."""

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
        return [dict(row) for row in payload.get("scenarios", [])]
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def label(text: str) -> str:
    return text.replace("_", " ")


def write_bar_svg(
    rows: list[dict[str, Any]],
    path: Path,
    title: str,
    y_label: str,
    y_max: float,
    value_key: str,
    ci_key: str | None = None,
    threshold: float | None = None,
) -> None:
    width = 720
    height = 400
    left = 90
    right = 40
    top = 55
    bottom = 95
    plot_w = width - left - right
    plot_h = height - top - bottom
    bar_w = 110
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
    for tick in range(0, int(y_max) + 1, max(int(y_max // 5), 1)):
        y = y_pos(tick)
        lines.append(f'<line x1="{left - 5}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#d8d8d8" stroke-width="0.8"/>')
        lines.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{tick}</text>')
    if threshold is not None:
        y = y_pos(threshold)
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#8b1e3f" stroke-width="1.5" stroke-dasharray="5 4"/>')
        lines.append(f'<text x="{left + plot_w - 4}" y="{y - 7:.1f}" text-anchor="end" font-family="Arial" font-size="12" fill="#8b1e3f">threshold {threshold:g}</text>')

    for idx, row in enumerate(rows):
        value = as_float(row.get(value_key))
        ci = as_float(row.get(ci_key)) if ci_key else 0.0
        x = left + gap / 2 + idx * (bar_w + gap)
        y = y_pos(value)
        h = top + plot_h - y
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="#2f6f73"/>')
        lines.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-family="Arial" font-size="13">{value:.1f}</text>')
        if ci > 0:
            y_hi = y_pos(value + ci)
            y_lo = y_pos(max(value - ci, 0))
            cx = x + bar_w / 2
            lines.append(f'<line x1="{cx:.1f}" y1="{y_hi:.1f}" x2="{cx:.1f}" y2="{y_lo:.1f}" stroke="#222" stroke-width="1.3"/>')
            lines.append(f'<line x1="{cx - 8:.1f}" y1="{y_hi:.1f}" x2="{cx + 8:.1f}" y2="{y_hi:.1f}" stroke="#222" stroke-width="1.3"/>')
            lines.append(f'<line x1="{cx - 8:.1f}" y1="{y_lo:.1f}" x2="{cx + 8:.1f}" y2="{y_lo:.1f}" stroke="#222" stroke-width="1.3"/>')
        lines.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 30}" '
            f'text-anchor="middle" font-family="Arial" font-size="12">{label(str(row.get("scenario", "")))}</text>'
        )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/analysis/vllm_figures"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.aggregate)
    if not rows:
        raise SystemExit("No rows found in vLLM aggregate input")
    timestamp = int(time.time())
    savings_path = args.output_dir / f"vllm_trace_time_saved_percent_{timestamp}.svg"
    kernels_path = args.output_dir / f"vllm_kernel_instances_{timestamp}.svg"
    write_bar_svg(
        rows,
        savings_path,
        "vLLM automatic tracing reduces profiler duration",
        "Profiler time saved (%)",
        40.0,
        "profiler_duration_saved_percent_mean",
        "profiler_duration_saved_percent_ci95_half_width",
        threshold=15.0,
    )
    write_bar_svg(
        rows,
        kernels_path,
        "vLLM automatic tracing collects fewer kernel instances",
        "Automatic kernel instances",
        max(as_float(row.get("fixed_window_kernel_instances_mean")) for row in rows) * 1.1,
        "automatic_kernel_instances_mean",
        "automatic_kernel_instances_ci95_half_width",
    )
    print(f"wrote {savings_path}")
    print(f"wrote {kernels_path}")


if __name__ == "__main__":
    main()
