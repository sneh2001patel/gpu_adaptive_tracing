"""Inter-coder agreement for the Phase A pilot: coder 1 (pilot_coding.csv, codebook v0) vs coder 2 (coder_sheet_ans.csv, v1).

Usage: python agreement.py [coder2.csv]
Default is coder_sheet_ans.csv, coder 2's own independent coding. second_coder_sheet.csv is a later copy in which
an AI model rewrote the notes and also changed 109 code cells; it is archived and is not an independent coding.

Coder 1's v0 codes are mapped to v1 by the fixed rules in V0_TO_V1 below. Each rule only re-expresses
information already written in coder 1's own v0 note for that issue; coder 2's answers are never consulted.
Fields new in v1 (reporter_is_maintainer, scope_unit) have no coder-1 value and are excluded.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
V = "https://github.com/vllm-project/vllm/issues/"
S = "https://github.com/sgl-project/sglang/issues/"

# url -> {field: v1 value}; justification is coder 1's own v0 note (quoted in AGREEMENT.md).
V0_TO_V1 = {
    V + "9565": {"cause_category": "model_or_algorithm_implementation"},
    V + "36943": {"evidence": "host_counters"},
    S + "14665": {"evidence": "benchmark_numbers;bisect;per_step_microbenchmark;trace_unspecified"},
    V + "21278": {"evidence": "benchmark_numbers;llm_assistant"},
    V + "20316": {"resolution": "fixed_pr_stale_closed"},
}

# Coder 2 wrote a few values outside the v1 vocabulary; these map each one to the v1 value it unambiguously names.
# memory_profile (vllm#2150) has no unambiguous v1 equivalent and is left as written.
C2_NORMALIZE = {
    "evidence": {"cprofile": "python_profiler", "logs": "server_logs_metrics"},
    "symptom": {"stall": "stall_hang"},
    "exclude_reason": {"tracker": "tracking_issue", "crash": "not_performance"},
}

SINGLE = ["symptom_primary", "baseline_primary", "multi_gpu", "profiler_by", "profiler_role",
          "cause_category_primary", "cause_confirmed_by", "resolution", "repro_candidate"]
MULTI = ["symptom", "baseline", "evidence", "cause_category", "evidence_requested"]


def load(name):
    with open(HERE / name, encoding="utf-8-sig") as f:
        return {r["url"]: r for r in csv.DictReader(f)}


def labels(value):
    return frozenset(v.strip() for v in (value or "").split(";") if v.strip())


def normalize(row):
    out = dict(row)
    for field, table in C2_NORMALIZE.items():
        out[field] = ";".join(table.get(v.strip(), v.strip()) for v in (row[field] or "").split(";") if v.strip())
    return out


def kappa(pairs):
    """Cohen's kappa for a list of (a, b) nominal codes."""
    n = len(pairs)
    if n == 0:
        return float("nan"), 0.0, 0
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (1.0 if pe == 1 else (po - pe) / (1 - pe)), po, n


def primary(value):
    """First listed value, used where one coder gave a multi-value answer to a mostly single-valued field."""
    vals = [v.strip() for v in (value or "").split(";") if v.strip()]
    return vals[0] if vals else ""


def main():
    c2_file = sys.argv[1] if len(sys.argv) > 1 else "coder_sheet_ans.csv"
    c1 = load("pilot_coding.csv")
    c2 = {u: normalize(r) for u, r in load(c2_file).items()}
    assert set(c1) == set(c2), "coders must cover the same issues"
    for url, changes in V0_TO_V1.items():
        c1[url] = {**c1[url], **changes}
    urls = sorted(c1)

    out = []
    inc = [(c1[u]["include"], c2[u]["include"]) for u in urls]
    k, po, n = kappa(inc)
    out.append(("include (all 30)", k, po, n))

    both = [u for u in urls if c1[u]["include"] == "yes" and c2[u]["include"] == "yes"]
    for field in SINGLE:
        src = field.replace("_primary", "")
        get = primary if field.endswith("_primary") else (lambda v: (v or "").strip())
        pairs = [(get(c1[u][src]), get(c2[u][src])) for u in both]
        out.append((f"{field} (both included)", *kappa(pairs)))

    multi = []
    for field in MULTI:
        jac = [len(labels(c1[u][field]) & labels(c2[u][field])) / len(labels(c1[u][field]) | labels(c2[u][field]) or {1})
               for u in both]
        exact = sum(labels(c1[u][field]) == labels(c2[u][field]) for u in both)
        vocab = sorted(set().union(*(labels(c1[u][field]) | labels(c2[u][field]) for u in both)))
        per_label = {lab: kappa([(lab in labels(c1[u][field]), lab in labels(c2[u][field])) for u in both])[0]
                     for lab in vocab}
        multi.append((field, sum(jac) / len(jac), exact, len(both), per_label))

    disagreements = {
        "include": [(u, c1[u]["include"], c1[u]["exclude_reason"], c2[u]["include"], c2[u]["exclude_reason"])
                    for u in urls if c1[u]["include"] != c2[u]["include"]],
    }
    for field in ["cause_category", "resolution", "repro_candidate", "profiler_role", "evidence", "multi_gpu"]:
        disagreements[field] = [(u, c1[u][field], c2[u][field]) for u in both
                                if labels(c1[u][field]) != labels(c2[u][field])]

    print("## Single-valued fields")
    print("| Field | n | % agree | Cohen's κ |\n|---|---|---|---|")
    for name, k, po, n in out:
        print(f"| {name} | {n} | {po:.0%} | {k:.2f} |")
    print("\n## Multi-valued fields (both included)")
    print("| Field | n | exact-set agree | mean Jaccard | per-label κ |\n|---|---|---|---|---|")
    for field, jac, exact, n, per in multi:
        per_s = ", ".join(f"{lab} {k:.2f}" for lab, k in per.items())
        print(f"| {field} | {n} | {exact}/{n} | {jac:.2f} | {per_s} |")
    print(f"\nBoth included: {len(both)}; coder1 included {sum(a == 'yes' for a, _ in inc)}, coder2 {sum(b == 'yes' for _, b in inc)}")
    for field, rows in disagreements.items():
        print(f"\n### Disagreements: {field} ({len(rows)})")
        for r in rows:
            print("- " + " | ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
