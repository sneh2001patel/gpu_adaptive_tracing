# L4 owned reset and capture feasibility — step 022

Date: 2026-10-28. This report supplements the earlier [discovery report](REPORT.md); historical results are preserved.

The corrected [activity_002 result](activity_002/RESULT.json) passes inventory, metrics, quiet/reset, capture and cleanup. Study readiness, diagnosis readiness and protocol freeze remain false. This is one bounded single-worker feasibility case, not the revised experiment matrix.

## Implementation and deployment

[Owned activity adapter](../../feasibility/activity.py), [CLI](../../scripts/run_l4_activity.py), [barrier helper](../../tracing/worker_barrier.py), [CUDA worker](../../tracing/vllm_cuda_worker.py) and [operating contract](../../protocol/OWNED_LIVE_ACTIVITY.md).

The supplied host ran NVIDIA L4 UUID `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb`, vLLM 0.10.2, Nsight 2026.3.1 and the pinned Qwen2.5-7B-Instruct model revision `a09a35458c702b33eeacc393d103063234e8bc28`. Model files/hashes from step 021 were reused. The one-shot supervisor service owned all serving/profiling activity. No management services or drivers were changed; no main matrix/calibration was enabled.

Each invocation allowed one attempted capture. Exact initial and corrected source archives plus service configuration are retained in [the deployment folder](activity_022_deployment/source_archive_fix.json). The corrected source uses absolute callback/session/output paths because Nsight changes the callback working directory.

## Initial failed invocation — retained

[activity_001](activity_001/RESULT.json) passes inventory, metrics, quiet/reset and cleanup, but fails capture with `starting_timeout`. CUDA start returned success; Nsight could not execute the relative callback path (`callback_start.sh: not found` in the server log). No controlled request was submitted because the backend required both acknowledgements first. A report emitted during shutdown is retained but supplies **zero valid successful captures** for this invocation. Its source, raw logs and four fresh barrier receipts are preserved. The original and restarted workers were 1785 and 2236.

The path fix received a CPU regression check before a separate corrective invocation. It did not refund the failed invocation's attempt or overwrite its outputs.

## Corrected invocation

[Quiet/reset receipt](activity_002/quiet_reset_receipt.json) and [six raw barrier observations](activity_002/quiet_evidence.json): original worker 2764 was removed with its owned group; fresh worker 3215 acknowledged a new session nonce, generation and reset token. Before reset, after reset and after capture, two distinct worker barriers were bracketed by zero queue/running gauges. Synchronization covers prior-issued configured-device work; it does not guarantee future admissions or unrelated GPU work. Model/OS page cache was reused; engine/KV state was fresh.

[Capture receipt](activity_002/capture_receipt.json), [backend](activity_002/backend_final.json), [timing events](activity_002/timing_events.jsonl), [requests](activity_002/requests.json), and [validated SQLite](activity_002/validated_capture.sqlite):

- One one-second requested range passed CUDA-start plus Nsight-start notification, stop acknowledgement, report readiness, SQLite export and parse gates.
- Parsed evidence contains **5,992 kernels**, exclusively mapped to worker 3215 and the configured GPU. Kernel sum is 1.016357856 s; envelope is 1.115275741 s. Neither quantity measures active capture duration.
- Start/stop acknowledgement spacing is **1.896336451 s**. Evidence became parsed-ready **0.200605226 s after stop acknowledgement**. These are observed lifecycle intervals for this invocation, not general overhead/savings estimates.
- The request submitted during the range succeeded with 32 output tokens. It continued beyond the range; this is not a complete-request trace guarantee. A separate request submitted after the readiness-only decision marker succeeded with 16 output tokens. Both returned HTTP 200.
- No classifier, diagnostic stop or causal reference was evaluated. `capture_active_s` remains null.

## Backup, integrity and cleanup

[Saved audit](ACTIVITY_VALIDATION.json) verifies **110 recorded artifact hashes** and **128 source fingerprint entries** across both invocations against their respective frozen archives. It rechecks gate receipts, 10 unique barrier tokens/raw gauge hashes, successful request usage, SQLite worker/device coverage and lifecycle order. [Audit script](activity_022_deployment/validate_backup.py); [CPU suite](activity_022_deployment/cpu_suite.log); [focused tests](activity_022_deployment/cpu_focused.log). All **399 CPU tests pass**, including **19 new checks**, separate from GPU evidence.

The [independent cleanup check](activity_post_cleanup_checks.json) confirms all four session parents/groups/workers absent, no compute processes and 0 MiB GPU memory. Raw outputs, source archives, supervisor configuration and logs are backed up locally. The serving job is stopped. **The rental instance remains running.**

## Remaining work

Finished-request histograms still do not supply admission-window waits or exclusive prefill GPU service fractions. Step 023 must implement an explicit measured-feature cohort/availability mapping and prepare independent reference/calibration collection. Calibration, held-out stopping/accuracy results, sensitivity, operator benefit and capture-active savings remain unvalidated; the main-study protocol is unfrozen.
