# Step 023 — live cohort mapping and independent calibration preparation

Completed: 2026-10-28. CPU-only implementation and offline audit; no SSH, GPU activity or new live experiment.

## Completed checklist

- [x] Define typed session/generation/PID/GPU/model/engine/clock bindings and bounded raw HTTP metric receipts.
- [x] Implement a loopback collector and exact selected-gauge mapping, rejecting foreign/future receipts and preserving failures as missing samples.
- [x] Keep finished-request histograms in diagnostic sidecars; prohibit their use as admission-window waits or exclusive GPU phase service.
- [x] Connect mapped receipts to the measured window interface alongside actual client usage and sampler inputs; retain late/outside/duplicate and partial accounting.
- [x] Persist observations, raw metric bytes, receipts, audit and hashes in exclusive output directories.
- [x] Connect the window subclass to the existing classifier bridge with worker/device/provenance checks and unchanged abstention.
- [x] Audit 12 saved step-022 raw receipts offline without inventing historical online windows or calibration data.
- [x] Prepare evaluator-only independent calibration pairs, availability inventory and explicit collection/freeze blockers; fit no thresholds or reference labels.
- [x] Test the mapping, persistence, local HTTP path, missingness, histogram independence, bridge boundaries and preparation rejection rules.
- [x] Update progress and the CAIN revision plan.

## Implementation

[Mapping and collector](../tracing/live_features.py), [classifier bridge](../tracing/feature_bridge.py), [preparation](../evaluation/calibration_preparation.py), [CLI](../scripts/prepare_live_calibration.py), [saved-byte audit](../scripts/audit_saved_live_features.py), [contract and instructions](../protocol/LIVE_FEATURE_MAPPING.md).

Queue depth uses the exact-model/engine waiting gauge assigned by parent receipt time; the mean is unweighted. Actual client completions/token usage and validated GPU samples retain existing semantics. Both unsupported fields remain null with explicit cohort/attribution reasons, even when histograms exist. Direct interval injection is rejected. Changing histogram counts leaves measured features unchanged. The collector must be closed/rebound around independently verified owned restarts; HTTP metric bytes cannot authenticate a worker or detect every restart.

The preparation packet plans nine independent feature/full-trace pairs (18 jobs) across three calibration seeds and three collection instructions. Intended interventions stay evaluator-only and are not adjudicated causes. Optional availability inventory accepts strict calibration observations only, preserves sample counts/nulls and rejects development/confirmation data or mixed synthetic/live provenance. Split declarations alone do not establish corpus independence. Collection schedules/order, actual corpus hashes/capacity, reference collection/locking, candidate feature profile, fitting and held-out checks remain unresolved. Launch/fitting/calibration/study/freeze flags stay false.

## Validation and evidence

All **427 CPU tests pass**, including **28 new tests**. They exercise a real local HTTP response, typed measured client usage and GPU sample plumbing, stale/foreign scope, future clocks, cancellation/failure handling, raw hash tampering and exclusive persistence, late/outside/duplicate samples, unsupported interval injection, histogram-feature independence, bridge target checks and preparation boundaries. Synthetic test inputs remain synthetic. [Saved test logs and audit](../examples/live_feature_mapping/REPORT.md).

The [saved-byte audit](../examples/live_feature_mapping/saved_l4_audit/AUDIT.json) maps **12 existing L4 metric receipts** with original raw hashes and verified saved worker identity. All waiting gauges are zero in these quiet observations. This is offline mapping only: no newly closed feature windows, online decisions, diagnostic findings or calibration data are inferred. Original step-022 artifacts/source archives are preserved.

The [saved preparation packet](../examples/live_feature_mapping/calibration_preparation/PREPARATION.json) contains **18 planned jobs and zero observed calibration windows**. Its artifact hashes and those of the mapping audit are verified locally. No GPU time is used.

## Limits

Sample completeness is not temporal coverage or planned-cadence completeness. Pending/skipped/censored admissions still need workload-driver records. Raw metric identity is conditional on trusted owned lifecycle binding. The new collector is not automatically launched by the eight-arm runner. The full live measured-feature pipeline and its instrumentation perturbation still need GPU validation. The current required classifier contract includes unsupported fields; any narrower calibrated profile needs separate versioning and independent validation. No concrete diagnosis, calibrated threshold, reference lock, stopping-effectiveness result, active-capture saving or operator benefit is established.

## Next step — 024

1. Implement the bounded capacity/prompt-corpus collection runner with actual prompt bytes/hashes and observed token usage.
2. Materialize deterministic paired offered schedules and collection manifests, with explicit fresh owned resets, bounded drain/cleanup and source provenance.
3. CPU-test the runner before a bounded L4 capacity/corpus pilot. Do not launch the main matrix or treat intended interventions as reference labels.

CPU preparation can proceed next. Capacity measurement and full live mapping validation will require the GPU; no new GPU activity was launched in this step.
