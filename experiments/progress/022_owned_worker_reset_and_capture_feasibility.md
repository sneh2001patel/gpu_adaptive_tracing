# Step 022 — owned worker barrier, reset and live capture feasibility

Completed: 2026-10-28.

## Completed checklist

- [x] Add a fixed loopback barrier RPC into the actual CUDA owner, with fresh tokens, session/generation identity, CUDA synchronization and bracketed monotonic acknowledgements.
- [x] Require repeated zero queue/running observations before/after barriers and no outstanding owned client tasks; persist the raw evidence.
- [x] Close the original owned process group and verify absence before a fresh engine/worker with new PID, nonce, generation and startup reset acknowledgement.
- [x] Implement a bounded one-attempt activity adapter/CLI; preserve unavailable metric mappings and disable calibration/main matrix.
- [x] CPU-test barrier rejection, stale/foreign evidence, busy/pending work, failed request persistence, attempt budgets, cleanup and callback-path ownership.
- [x] Run the L4 pilot, retain the initial callback-path failure, correct absolute paths and validate a separately recorded invocation.
- [x] Verify live report readiness, SQLite PID/GPU coverage, post-parse serving continuation and owned cleanup.
- [x] Back up and audit both invocations, exact source archives, raw responses, timing events and supervisor configuration.
- [x] Update progress and the CAIN revision plan.

## Outcome and evidence

[Hardware report](../hardware/l4_20261028/ACTIVITY_REPORT.md), [validation](../hardware/l4_20261028/ACTIVITY_VALIDATION.json), [successful gates](../hardware/l4_20261028/activity_002/RESULT.json), [retained failed gates](../hardware/l4_20261028/activity_001/RESULT.json), [operating contract](../protocol/OWNED_LIVE_ACTIVITY.md).

Corrected invocation: all five live feasibility gates pass. Fresh restart moves from worker 2764 to 3215; six distinct quiet barriers pass. One bounded capture contains 5,992 measured kernels on the expected worker/GPU. Both the 32-output-token request submitted during capture and the 16-output-token post-readiness continuation request succeed. The former extends beyond the range, so complete-request trace coverage is not claimed.

Initial invocation: capture startup times out because Nsight runs a relative callback from another working directory. CUDA acknowledgement alone does not pass the gate; no controlled request is submitted. That invocation remains failed with zero successful validated captures, even though Nsight emits a report during shutdown. Absolute callback/session/output paths and a CPU regression guard fix the cause for the separate corrective invocation. Both source versions and output directories are retained.

All **399 CPU-only tests pass**, including **19 new checks**. The local backup audit verifies **110 artifact hash entries**, **128 archived source fingerprint entries**, 10 fresh barrier receipts, actual response usage, capture ordering and SQLite coverage. The owned processes/groups/workers are absent and GPU memory is 0 MiB. No driver or management service changes were made; the rental instance remains running.

## Limits

This validates engineering feasibility for one pinned single-worker L4 stack. Synchronization covers prior-issued configured-worker CUDA work, not future arrivals or global GPU idleness. Restart creates new engine/KV state while reusing model files and OS page cache. Active-capture time remains unknown; CUDA acknowledgement spacing and kernel sum/envelope are not substitutes. The readiness-only marker is not a policy/classifier diagnosis. Finished-request histograms still cannot populate admission-window waits or exclusive GPU phase fractions. No calibration, main matrix, diagnostic accuracy, sensitivity or operator benefit is established; protocol freeze remains false.

## Next step — 023

1. Define and CPU-test an explicit live measured-feature cohort/availability contract using the discovered metric semantics; keep unsupported admission-window/phase fields unavailable.
2. Wire only validated observations into persisted feature windows without using expected causes or reference labels.
3. Prepare an independent reference/calibration pilot with explicit coverage and abstention checks. Use GPU time only after its collection and scoring path is executable; do not launch the main study yet.

The next implementation preparation can proceed on CPU. Fresh hardware validation/calibration will need the L4 again.
