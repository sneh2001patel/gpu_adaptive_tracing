# Adaptive GPU Profiling for LLM Serving

Empirical study of when to stop detailed GPU profiling (Nsight Systems captures) during latency incidents in LLM serving.

## Layout

| Path | Contents |
|---|---|
| `revision/` | Study instrument and evidence: episode controller, stopping policies, case reproductions, calibration, evaluation sessions, analysis scripts and tests. See `revision/README.md` and `revision/PROGRESS.md`. |
| `CAIN_REVISION_PLAN.md` | Revision checklist and step log. |
| `litterature_review/` | Literature review notes (paper PDFs are not redistributed). |
| `archive/icse_2026/` | Previous study (RQ1-RQ5 experiments, ICSE paper and reviewer feedback). Kept for provenance; not part of the CAIN results. |

## Tests

```bash
python3 -m unittest discover -s revision/tests
```
