# Step 035 — scheduler-bound precision and cohort audit

Completed 2026-10-28. CPU-only. [Report](../examples/scheduler_bound_audit/REPORT.md), [assessment plan](../protocol/SCHEDULER_BOUND_ASSESSMENT.md), [live-data audit](../hardware/l4_20261028/scheduler_bounds_035/AUDIT.json).

## Completed checklist

- [x] Verify the retained manifest digest and all original artifact hashes before interpreting source receipts.
- [x] Recheck raw snapshot bytes, source scopes/history prefixes and exact final client-ID/clock joins.
- [x] Independently reconstruct host scheduling intervals, explicit boundary ambiguity and request counts.
- [x] Compare scheduling, client-admission and client-completion cohorts without treating them as interchangeable.
- [x] Audit actual receipt readiness, deliberate withholding and owner deadlines; preserve original consumer outcomes.
- [x] Separate probe-time pending state from retrospective window-end reconstruction and eventual completion.
- [x] Publish explicit feature-admissibility limits and fourteen unset scientific choices with independent-assessment instructions.
- [x] Add synthetic CPU regressions, run focused/full tests and preserve original live/source artifacts; update progress and plan.

## Results and limits

The audit verifies 6,142 hashes, ninety source probes and 958 complete scheduled case lifecycles across ten source-enabled jobs. Fifty-four accepted windows contain 798 observations; six withheld windows contain 160 additional raw observations used only offline. Thirty-six source-disabled windows remain unresolved. All recorded consumer decisions reproduce.

Wait-bound widths have median 0.2362 ms, sample p95 0.3252 ms and maximum 0.7692 ms; scientific precision acceptance remains unset. All sixty source-enabled windows have a ready raw receipt by the original deadline, with maximum window-end receipt delay 316.594 ms and minimum remaining margin 433.406 ms. No owner is late. Probe latency is not observer overhead.

Scheduling cohorts differ from client admission in 40/60 windows and completion in 52/60. Thirty-two raw cohorts have fewer than twenty requests and eight are empty; the accepted 54 windows include those same 32 small/eight empty cohorts. Zero boundary ambiguities occur in this run, but the code retains them. The 147 probe-time unscheduled occurrences differ from 148 reconstructed window-end occurrences in one window. There are 622 definitely unfinished source occurrences at window ends; final source case lifecycles are complete. Intermediate counts are occurrences, not final failures or censors.

The existing wait feature remains unsupported by this different proxy/cohort, and GPU phase fields remain unavailable. No classifier activation, reference label, scientific threshold fit, calibration, online replay or new engineering snapshot occurs. No SSH/GPU use or rental-state recheck occurs. Hardware confirmation of changed runtime source remains pending.

All **579 CPU tests pass**, including fourteen new checks; the focused audit/event group passes 31. Two older CPU fixtures exposed short timing assumptions: the persistence/export case now has a one-second observation horizon with 100 ms window/grace, and the busy-reset case keeps fake work alive for one second while retaining its 30 ms rejection deadline and adding a busy-state assertion. Original assertions and GPU guards are retained. Both failed full logs, isolated diagnostics/corrected checks and the final passing log are saved.

## Next step — 036, CPU-only

1. Implement a criterion-completion contract with required measurand/cohort, precision/coverage, sample precision, observer/work mismatch, independent repetitions and reference-agreement choices, including rationale and decision provenance.
2. Keep unset entries blocked. Record whether criteria were informed by this development data; do not present them as held-out confirmation thresholds.
3. Generate an evaluator-only worksheet bound to the audited artifacts and completed criteria. Keep assessor identity, actual blinding, outcomes and rationale blank until provided; record competing explanations and feature/reference separation.
4. Validate structure, evidence scope, hashes and unresolved decisions using synthetic cases, reusing existing reference contracts. Do not automatically export labels, lock references or enable calibration.
5. Save the report and next task. No GPU is needed for this workflow; independent adjudication and future confirmation remain separate required work.
