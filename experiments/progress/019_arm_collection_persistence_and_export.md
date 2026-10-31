# Step 019 — CPU collection binding, persistence and arm export

Date: 2026-10-27. Status: complete for CPU source/arm integration and validation. No GPU or SSH access used.

## Completed

- [x] Bind an owned CPU source's monotonic acquisition clock to a parent request/receipt bracket and source/reset identity.
- [x] Record actual queue-entry/service-admission waits in bounded optional target history; expose exact half-open as-of histogram prefixes.
- [x] Keep this additional recording disabled in the unprofiled arm; enable it consistently in the seven cheap-sampling arms.
- [x] Collect interval receipts asynchronously through a bounded queue owned by the serialized playback loop; preserve raw hashes, errors, late rejection and cancellation.
- [x] Persist cheap and capture observations separately, without inventing matching intervals or phase attribution.
- [x] Route ready capture observations through the uncalibrated measured classifier, retaining missingness and abstention.
- [x] Automatically export initial stops for finalized policy arms; mark controls/reference inapplicable and fail explicit persistence errors.
- [x] Fix the real-clock activation stamp discrepancy exposed by strict export; retain development failure logs.
- [x] Save a matrix/fault demonstration, final artifact fingerprints and a passive server-metric snapshot probe for later feasibility checks.
- [x] Update the guide, progress tracker and CAIN revision plan.

## Validation

All **349 CPU-only tests pass**, including **17 new source/arm integration checks**. Coverage includes actual admission waits, empty cohorts, source clock/identity/generation validation, raw hashes, reset-invalidated bindings, history epoch/future rejection, full arm export, no-profiler instrumentation exclusion, continuous reference applicability, missing/reset/clock/generation/overflow/late/timeout behavior, cancellation and persistence failure with owned cleanup. The passive probe verifies raw bytes/type hints without claiming interval features.

[Saved report](../examples/arm_collection_export_demo/REPORT.md) and [summary](../examples/arm_collection_export_demo/SUMMARY.json): eight comparable CPU arms and six source fault cases, with raw receipts, original observations, policy initial-stop exports, manifests and closed owned groups/tasks. The [artifact audit](../examples/arm_collection_export_demo/VALIDATION.json) verifies 206 saved artifact hashes, 104 raw interval hashes, 20 ready synthetic reports and 11 initial policy stops. All owned groups are absent and interval/sampler/request tasks are closed. A separate saved CPU endpoint probe retains raw responses. Documentation links and whitespace checks pass.

An initial integration run rejected policy exports because the episode start and activation event used separate real clock reads. The controller now takes its authoritative start from the activation event. Earlier deterministic tests saw identical manual-clock values. [Initial failed check logs](../examples/arm_collection_export_demo/development_failures/initial_real_clock_export_checks.log) are retained; final source hashes identify the corrected implementation. [Final test output](../examples/arm_collection_export_demo/TEST_RESULTS.txt) records the passing focused/full suite.

[CPU source binding](../tracing/cpu_interval_collection.py), [owned target](../scripts/fake_serving_target.py), [playback](../tracing/schedule_playback.py), [arm runner](../tracing/experiment_arms.py), [capture backend](../tracing/target_capture.py), [tests](../tests/test_arm_collection_export.py), [demo](../scripts/demo_arm_collection_export.py), [passive probe](../scripts/snapshot_server_metrics.py), [guide](../protocol/ARM_COLLECTION_AND_EXPORT.md).

## Limits

The source's history-prefix endpoint is a CPU fixture facility, not a capability established on vLLM. Its same-host clock probe does not map remote/GPU timestamps. Admission-cohort waits exclude requests still queued; bucket p95 remains estimated. Source history is bounded, and overflow remains unavailable. Phase attribution is not instrumented. Kernel/device reports are synthetic.

Cheap and capture observations have separate acquisition intervals. Capture classification therefore still has missing request/server features and abstains. No calibrated joint diagnosis, causal reference adjudication, actual GPU reset/metrics, capture-active savings, operator benefit or empirical stopping contribution is established. Persistence hashes are integrity checks, not reference truth or administrator-proof storage. Historical outputs are preserved.

## Next step — 020 (CPU preparation, then hardware feasibility)

1. Prepare a gated live-feasibility harness for the previously pinned L4/vLLM 0.10.2 stack; preserve exact source/package/model/worker/device identities.
2. Inventory actual server metric capabilities and define explicit availability/clock/cohort gates; reject unsupported wait/prefill attribution rather than infer it from names.
3. Prepare a small pilot that checks server/worker quiet/reset, capture readiness and temporal scope before any main matrix or diagnosis calibration.
4. Request GPU access when executing that live pilot is the next dependency. Harness preparation can continue without renting hardware; the protocol remains unfrozen.
