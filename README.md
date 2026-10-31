# Adaptive GPU Profiling for LLM Serving

Empirical study of when to stop detailed GPU profiling (Nsight Systems captures) during latency incidents in LLM serving.

## Layout

| Path | Contents |
|---|---|
| `experiments/` | Study instrument and evidence: episode controller (`tracing/`), stopping policies, case reproductions (`cases/`), calibration and evaluation sessions, analysis scripts and tests. See `experiments/README.md`, `experiments/PLAN.md` and `experiments/PROGRESS.md`. |
| `litterature_review/` | Literature review notes (paper PDFs are not redistributed). |
| `archive/icse_2026/` | Previous study (RQ1-RQ5 experiments, ICSE paper and reviewer feedback). Kept for provenance; not part of the current results. |

## Tests

```bash
python3 -m unittest discover -s experiments/tests
```

## Reproducing the analysis

```bash
cd experiments/cases/checks
python3 analyze_evaluation.py evaluation_hosts --out evaluation_analysis   # needs scipy
```

Session records were written while this folder was named `revision/`, so paths stored inside them start with `revision/`; they refer to the same files under `experiments/`.
