#!/usr/bin/env python3
"""Render the RQ2 vLLM multiclass accuracy table as a two-panel bar chart.

Preview-only script: generates the figure for review but does not modify
the paper. Source data is the already-published per-scenario mean values
from the RQ2 vLLM multiclass table (3 seeds per scenario, L4); this script
does not recompute anything.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

# (scenario_label, auto_trace_s, fixed_trace_s, auto_kernels_k, fixed_kernels_k)
ROWS = [
    ("healthy", 301.3, 391.9, 730, 1380),
    ("queue_pressure", 309.7, 403.4, 748, 1380),
    ("long_prompt", 290.4, 381.0, 732, 1380),
    ("long_output", 291.0, 397.1, 729, 1380),
    ("compute_saturation", 336.8, 415.1, 757, 1380),
    ("kv_cache_pressure", 329.4, 449.3, 731, 1380),
]

OUTPUT_DIR = Path(__file__).resolve().parents[2].parent / "figures"


def grouped_bars(ax, auto_vals, fixed_vals, labels, ylabel, value_fmt):
    n = len(labels)
    x = list(range(n))
    bar_width = 0.35

    ax.bar(
        [i - bar_width / 2 for i in x],
        auto_vals,
        width=bar_width,
        label="Automatic",
        color="#2c7fb8",
    )
    ax.bar(
        [i + bar_width / 2 for i in x],
        fixed_vals,
        width=bar_width,
        label="Fixed-window",
        color="#bdbdbd",
    )

    for i, (a, f) in enumerate(zip(auto_vals, fixed_vals)):
        saved_pct = (f - a) / f * 100.0
        top = max(a, f)
        ax.annotate(
            f"-{saved_pct:.0f}%",
            xy=(i, top + top * 0.02),
            ha="center",
            va="bottom",
            fontsize=7.5,
            color="#222222",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7.5)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(fixed_vals) * 1.18)


def main() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    fig, (ax_trace, ax_kernels) = plt.subplots(1, 2, figsize=(7.0, 3.2))

    labels = [row[0] for row in ROWS]
    auto_trace = [row[1] for row in ROWS]
    fixed_trace = [row[2] for row in ROWS]
    auto_kernels = [row[3] for row in ROWS]
    fixed_kernels = [row[4] for row in ROWS]

    grouped_bars(ax_trace, auto_trace, fixed_trace, labels, "Total profiler duration (s)", "{:.0f}")
    grouped_bars(ax_kernels, auto_kernels, fixed_kernels, labels, "Kernel instances (K)", "{:.0f}")

    handles, legend_labels = ax_trace.get_legend_handles_labels()
    fig.legend(
        handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=2,
        frameon=False,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT_DIR / "rq2_vllm_accuracy_PREVIEW.pdf"
    png_path = OUTPUT_DIR / "rq2_vllm_accuracy_PREVIEW.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    print(f"wrote {pdf_path}")
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
