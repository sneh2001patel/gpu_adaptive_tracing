# Step 016 — Distinct arm lifecycles and independent reset/quiescence

Date: 2026-10-27. Status: complete for CPU fixture implementation/validation. No GPU or SSH access used. The adapter launches only the bundled fake target and cannot certify a real GPU baseline or reset.

## Completed

- [x] Define eight distinct arm plans: capture-disabled unprofiled/cheap-only controls, five bounded policy arms, and a continuous reference arm. Reject mislabeled instrumentation and MU as a separate arm.
- [x] Preserve the same offered file, horizon, playback/warmup/service settings and shared budget contract across arms. Verify contract hashes and fresh target/sampler identities.
- [x] Own a fresh target subprocess/group per arm; validate readiness/HTTP status against its PID, nonce, instance, capture mode and reset generation.
- [x] Implement acknowledged capture control in that same CPU serving fixture, parsed/persisted synthetic reports and independent capture/serving lifetimes.
- [x] Gate resets on repeated server quiet observations over a hold interval, then a fresh token/next-generation acknowledgement and another quiet gate. Missing/stale/busy status fails instead of becoming healthy zero.
- [x] Demonstrate residual server work after client timeout/censoring. Wait for actual queue/running/report/capture clearance before reset, independently of the driver's empty task set.
- [x] Close fresh per-arm sampler sessions and shield bounded TERM/KILL/reaping of owned groups, retaining failures and timing scopes.
- [x] Run and save an eight-arm CPU matrix, four injected failures, report/source fingerprints and cleanup checks. Preserve the initial development cleanup visibility failure and its follow-up.
- [x] Update the guide, progress tracker and CAIN revision plan.

## Files and validation

- [Arm runner/plans](../tracing/experiment_arms.py), [owned session](../tracing/arm_session.py), [capture control](../tracing/target_capture.py).
- [Fake serving target](../scripts/fake_serving_target.py), [matrix demo](../scripts/demo_arm_lifecycles.py), [tests](../tests/test_arm_lifecycles.py).
- [Lifecycle guide](../protocol/EXPERIMENT_ARM_LIFECYCLE.md), [saved report](../examples/arm_lifecycle_demo/REPORT.md), [summary](../examples/arm_lifecycle_demo/SUMMARY.json), [plan](../examples/arm_lifecycle_demo/matrix_plan.json).

All **282 CPU-only tests pass**, including 20 new lifecycle checks. The focused 20-test run also passes. Tests cover mode validation, missing/stale counters/identity/reset, residual server work after client timeout, capture stop without target stop, pending report clearance, hard budgets/abstention, sampler reuse, owned process escalation, cleanup cancellation and comparison integrity.

Final saved matrix: eight completed arms with matching exact offered-file/comparison contracts, eight distinct target instances, seven closed distinct sampler sessions and eight successful final quiet/reset gates. There are 14 synthetic reports (FB 1; RFB/SS/CR/HS 3 each; reference 1), whose 14 hashes match. All 13 policy decisions remain unresolved and use ready evidence. Four injected failures reject their gate and retain cleanup; all owned target groups/PIDs are absent. Source fingerprints and documentation links verify; `git diff --check` passes.

An initial development run exposed a permission-denied group visibility/signal check during cleanup. That failed result is retained separately. The corrected handler treats denied visibility as unknown, retries within a deadline and requires confirmed absence; a regression forces this case. A follow-up confirms the original PID is absent. No unverified cleanup is promoted into a successful arm result.

## Limits

CPU target counters/generations do not prove actual CUDA worker idleness, KV/cache reset, multi-worker coverage, profiler overhead or statistical independence. Policy classification still abstains, using the existing streaming controller; calibrated richer T2 classification is not integrated by this step. Two warmup timings are a synthetic activation reference, not the planned GPU calibration cohort. Cheap-only monitoring here exercises sample/window lifecycle, not an operator diagnosis workflow.

Active GPU time, pure Nsight export and fully persisted lifecycle time remain unmeasured. Client cancellation does not establish backend work cancellation. Real GPU session/metric/reset validation and independent references remain necessary before confirmation. The old L4 pilot and submitted-paper artifacts are unchanged.

## Next step — 017 (CPU-only)

1. Add durable evaluator-only reference storage with artifact/content hashes, explicit rubric/provenance/assessor metadata, and an immutable lock manifest before prediction joins.
2. Verify real artifact bytes and reject stale/tampered/cross-run or synthetic/live joins. Keep references/interventions out of controller inputs.
3. Implement explicit supported/partial/unsupported/unresolved/reference-unavailable scoring with complete denominators, interval-transition handling, and separate budget/failure/censoring outcomes.
4. Validate on synthetic fixture references and predictions only. Then finish interval wait/prefill instrumentation and the GPU calibration/feasibility checklist before renting hardware.
