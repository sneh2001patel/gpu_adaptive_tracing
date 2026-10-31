# Step 038 — Issue-grounded empirical study design

Date: 2026-10-28.

Completed: revised the [empirical study proposal](../protocol/EMPIRICAL_STUDY_PROPOSAL.md) at the author's request. The step-037 version is preserved unchanged as [EMPIRICAL_STUDY_PROPOSAL_step037.md](../protocol/EMPIRICAL_STUDY_PROPOSAL_step037.md).

Main changes:
- **Issue mining (Phase A, RQ1).** Added a phase that mines vLLM/SGLang performance issues to characterize real problems and profiling practice, and to select reproducible cases with upstream-confirmed causes.
- **Case benchmark (Phase B).** Combines reproduced issues with controlled failure-mode cases: changing, overlapping, lull/recurrence, healthy, and incomplete evidence.
- **Independent reference diagnoses.** Built from upstream resolution, external analysis tools and blinded assessment, never from scenario definitions or the classifier under test.
- **Formal policy definitions.** Every threshold is a named parameter. MU is dropped as the SS(K=2) alias.
- **Statistics and sensitivity.** The analysis plan uses paired blocks, cluster-bootstrap intervals, Holm-corrected Wilcoxon tests and effect sizes. Threshold sensitivity uses a calibration/evaluation split. The composite score and savings thresholds are removed.
- **Review mapping and disposition.** Each review concern is mapped to a design response, and each existing paper result is given a disposition.
- **Pilot status.** The step-037 queue-pressure pilot and its proceed/revise/stop criteria are retained as the feasibility gate.

Documentation only. No issues mined, no scientific results, no GPU use, no source or test changes. All counts, thresholds and budgets are planning values for author review.

Next: build the primary-source related-work matrix, then the Phase A query and codebook pilot (~30 issues). Both are CPU-only. The step-036 regression still must be cleared before changed source is deployed.
