#!/usr/bin/env python3
"""Generate the RQ4 cost-safety tradeoff figure (fig:rq4-tradeoff in 04_RQ4.tex)
from the L4 ambiguity-stress replay ranking table.

Usage:
    paper/.venv/bin/python paper/scripts/make_rq4_tradeoff_figure.py
"""
import csv
from pathlib import Path

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_CSV = (
    REPO_ROOT
    / "RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.csv"
)
OUT_DIR = REPO_ROOT / "paper/figures"
OUT_PDF = OUT_DIR / "rq4_tradeoff.pdf"
OUT_PNG = OUT_DIR / "rq4_tradeoff.png"

POLICY_LABELS = {
    "fixed_burst": ("FB", "Fixed Burst"),
    "repeated_fixed_burst": ("RFB", "Repeated Fixed Burst"),
    "stability_stop": ("SS", "Stability Stop"),
    "marginal_utility_stop": ("MU", "Marginal Utility Stop"),
    "counter_recovery_stop": ("CR", "Counter-Recovery Stop"),
    "hybrid_stop": ("HS", "Hybrid Stop"),
}

# Fixed plotting order so policies that share identical (x, y) coordinates
# get a small, deterministic horizontal jitter and don't render on top of
# each other.
PLOT_ORDER = [
    "fixed_burst",
    "stability_stop",
    "marginal_utility_stop",
    "repeated_fixed_burst",
    "counter_recovery_stop",
    "hybrid_stop",
]

MARKERS = ["o", "o", "o", "o", "o", "o"]
COLORS = ["#d62728", "#9467bd", "#8c564b", "#2ca02c", "#1f77b4", "#ff7f0e"]


def load_rows():
    with open(DATA_CSV, newline="") as f:
        rows = {r["policy"]: r for r in csv.DictReader(f)}
    return rows


def jittered_x(rows):
    """Group policies by (duration, re-escalation) and spread ties along x."""
    groups = {}
    for policy in PLOT_ORDER:
        key = (
            rows[policy]["heavy_trace_duration_s_mean"],
            rows[policy]["re_escalation_rate_mean"],
        )
        groups.setdefault(key, []).append(policy)

    jitter = {}
    spread = 2.6
    for members in groups.values():
        n = len(members)
        offsets = [(-spread * (n - 1) / 2) + spread * i for i in range(n)]
        for policy, dx in zip(members, offsets):
            jitter[policy] = dx
    return jitter


def main():
    rows = load_rows()
    dx = jittered_x(rows)

    fig, ax = plt.subplots(figsize=(5.2, 3.8))

    for marker, color, policy in zip(MARKERS, COLORS, PLOT_ORDER):
        row = rows[policy]
        abbrev, full_name = POLICY_LABELS[policy]
        x = float(row["heavy_trace_duration_s_mean"]) + dx[policy]
        y = float(row["re_escalation_rate_mean"])
        ax.scatter(
            x,
            y,
            marker=marker,
            color=color,
            s=90,
            edgecolor="black",
            linewidth=0.6,
            zorder=3,
            label=f"{abbrev} — {full_name}",
        )
        ax.annotate(
            abbrev,
            (x, y),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=8.5,
        )

    ax.set_xlabel("Mean heavy-tracing duration per episode (s)")
    ax.set_ylabel("Re-escalation rate (lower = safer)")
    ax.set_title("RQ4: cost–safety tradeoff, ambiguity stress replay (L4)")
    ax.set_ylim(-0.08, 1.12)
    ax.set_xlim(5, 42)
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.6, zorder=0)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        fontsize=7.5,
        frameon=False,
    )

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
