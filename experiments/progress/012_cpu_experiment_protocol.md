# Step 012 — Prepare the next L4 protocol without a GPU

Date: 2026-10-27. Status: complete for CPU protocol preparation. No SSH connection or GPU workload was used in this step. The protocol remains a draft; actual calibration/reference collection and confirmation remain pending.

## Completed

- [x] Define empirical questions about stable-but-unsupported diagnoses, diagnosis versus recovery, changes/lulls/overlap, sensitivity and measured collection cost.
- [x] Separate driver intervention schedules, controller-visible measurements, blinded reference adjudication and offline scoring. Define strict future input allowlists rather than trusting filenames.
- [x] Specify conservative queue/prefill mechanism rubrics, same-run independent reference channels, uncertainty and single-intervention controls. Distinguish intended intervention from realized diagnosis and matched reference runs from ground truth.
- [x] Specify calibration/development/confirmation separation, corpus/arrival hashes, abstaining candidate selection and a complete freeze manifest. No classifier thresholds were fitted or declared validated.
- [x] Draft six cases and eight arms: five distinct policies plus no-profiler, cheap-only and full-horizon reference. Keep MU an alias, shared incident budgets and explicit reactivation.
- [x] Define initial-stop diagnosis outcomes, unknown/failure/censoring denominators, telemetry integrity, performance/skips/drain, timing uncertainty and sensitivity limits.
- [x] Implement deterministic CPU design compilation with phase, split, arm and budget validation; emit controller jobs separately from evaluator/driver metadata. Compiler cannot launch GPU work or certify a frozen study.
- [x] Compile the proposed development matrix and estimate observation/drain bounds. Confirmation jobs deliberately remain ungenerated.
- [x] Update the README, progress index and main revision plan.

## Files and reproduction

- [Protocol](../protocol/L4_EXPERIMENT_PROTOCOL.md): step-by-step instructions, reference rubric, cases/arms, analysis and freeze gates.
- [Draft configuration](../configs/l4_protocol_draft.json): provisional settings and explicit unresolved prerequisites.
- [Reference-record template](../protocol/reference_record.template.json): empty evaluator record, explicitly not an observation or scoring truth.
- [CPU compiler](../scripts/prepare_protocol.py) and [regression checks](../tests/test_protocol_preparation.py).
- [Generated design](../protocol/draft_design_v1/planning_summary.json), [controller jobs](../protocol/draft_design_v1/controller_jobs.json), [evaluator schedule](../protocol/draft_design_v1/evaluator_schedule.json), [hash manifest](../protocol/draft_design_v1/manifest.json).

From the repository root, target a new directory:

```bash
python3 -m experiments.scripts.prepare_protocol --output experiments/protocol/another_draft_design
python3 -m unittest discover -s experiments/tests
```

## Validation

All **195 CPU-only tests pass**, including nine new checks for complete case/seed/arm pairing, deterministic generation, no intervention metadata in controller jobs, phase gaps/overlaps, seed/corpus split overlap, MU duplication, impossible budgets and false freeze certification. `git diff --check` passes. The exact generated config/compiler fingerprints are saved; generation does not modify its configuration.

Draft scale: six cases × eight arms × three development repetition labels = 144 runs across 18 blocks. Observation alone is 4.8 hours; observation plus maximum drain is 6.6 hours. Those bounds exclude startup/warmup, capacity/calibration, additional export, retries, sensitivity, confirmation and the GPU feasibility pilot. Start with one feasibility block and measure actual cycle time before scaling. No rental is requested now.

## Known gaps

Existing live classification still abstains. The current kernel-only classifier input cannot support independent queue/prefill diagnoses; metric collection, measured-feature aggregation and label mapping must be implemented and calibrated. The expanded arrival/arm/reset runner, blinded reference locking/scoring and full-horizon reference arm are specified, not implemented by the draft compiler. Nominal corpus names/seeds do not prove disjoint real content until files are constructed and hashed.

All phase lengths/rates/token bands remain proposals. The hardware pilot must verify actual queue/prefill effects, temporary relief, removal, drain/reset and available metrics. Active capture time remains unavailable unless valid boundaries are demonstrated; otherwise remove active-time savings from the confirmatory endpoints. A single-author adjudication or perturbed matched reference remains an explicit limitation.

## Next step — 013 (CPU-only)

1. Define typed request/server/kernel observations with acquisition and availability timestamps, coverage/counts, missingness and clock domains; allow measured fields only.
2. Validate independent reference records, rubric/version and artifact identities; keep reference cause sets and intervention schedules out of classifier inputs.
3. Add a conservative classifier adapter that abstains until required metrics/calibration exist. Make mapping to concrete policy labels explicit; do not infer a cause from kernel names.
4. Use synthetic fixtures to check timestamp availability, reference leakage, missing metrics, transitions and unknown handling. Synthetic fixtures are code validation, not diagnosis evidence.
5. Then implement workload/arm/reset collection and reference/scoring tools before the next GPU feasibility/calibration session.
