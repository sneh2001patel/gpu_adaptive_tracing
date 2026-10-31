# Owned L4 paired collection pilot — step 025

Completed 2026-10-28. [Result](pairs_001/RESULT.json): four jobs pass with eight successful scheduled requests, four successful warmups and two parsed full-range traces. This is a low-rate engineering collection pilot. It creates no adjudicated reference or calibrated diagnosis.

## Source, input and ownership

The pinned L4 UUID, Qwen2.5-7B-Instruct revision, vLLM 0.10.2 and Nsight 2026.3.1 match the earlier [capacity/corpus pilot](CAPACITY_REPORT.md). Exact source and immutable paired inputs were archived before the one-shot supervisor launch: [deployment record](pairs_025_deployment/source_archive.json). No driver/management services were changed.

The [original candidate pair manifest](capacity_001/paired_schedules/PAIRS.json) remains unchanged. Each pair uses identical offered bytes/hash: two requests at offsets zero and four seconds over an eight-second horizon, each requesting 32 output tokens. Actual prompt counts are 17 and 1,072 tokens. Each job owns a fresh worker, nonce, generation and reset acknowledgement; model/OS cache is reused. The same declared first-request warmup precedes collection in both roles. Prefix caching remains enabled, and repeated prompts can benefit from it.

## Executed jobs

[Job records](pairs_001/jobs.json); all latencies below are end-to-end client observations in milliseconds. These are two observations per role, not inferential comparisons.

| Job | Pair | Role | Worker | Completed/offered | Observed request latencies (ms) | Parsed kernels |
|---|---|---|---:|---:|---|---:|
| job-0 | Short | Feature collection | 4974 | 2/2 | 1887.67, 1887.73 | No profiler |
| job-1 | Short | Matched full trace | 5432 | 2/2 | 1898.78, 1890.68 | 21,308 |
| job-2 | Long | Matched full trace | 5969 | 2/2 | 1918.08, 1919.44 | 23,044 |
| job-3 | Long | Feature collection | 6439 | 2/2 | 1911.84, 1911.23 | No profiler |

All requests were admitted/completed, with no request failures, skips, censoring, sampling errors/skips or telemetry overflows. Actual usage matched the expected prompt counts and 32 output tokens for every scheduled request and warmup. Sixteen live two-second windows persist measured client completions/usage and **64 raw metric receipts**. Wait/phase/GPU-utilization measurements remain unavailable. Sparse windows do not meet the two-completion minimum for latency p95; missingness remains explicit.

Only the two full-trace roles invoke Nsight. Each uses one attempted range, waiting for CUDA-worker acknowledgement plus the actual Nsight start callback before playback. Stop acknowledgement follows complete playback/drain; reports export and parse while serving remains alive. [Short trace receipt](pairs_001/job-1/trace_receipt.json), [long trace receipt](pairs_001/job-2/trace_receipt.json). Both SQLite files independently reparse with exact single-worker/GPU coverage. Backend helpers report clean shutdown. Start/stop control acknowledgement bracketing is not an independent measurement of active capture duration or proof of zero event loss/per-request CUDA attribution. `capture_active_s` remains null.

## Assessment packet and scientific limits

[ADJUDICATION_PACKET.json](pairs_001/ADJUDICATION_PACKET.json) links **ten request/server/full-trace artifacts** by path/hash, records both roles' realized counts and per-request latencies, and requests explicit mismatch, coverage, alternatives and unresolved/negative-evidence assessments. The root artifact manifest also binds linked raw responses/metrics and logs.

The packet is `artifact_packet_not_adjudicated_reference`, awaiting blinded assessment. **Zero references are created or locked; no classifier/policy runs.** No assessor blinding or human adjudication is claimed to have occurred. Raw channels are independent of classifier output, but do not by themselves prove causality. Identical offered schedules do not establish realized-run equivalence or make the separate full trace the feature run's ground truth.

Two low-rate requests over repeated prompts are collection plumbing, not challenging incidents, healthy-reference adjudication, capacity measurement, overhead estimation, calibrated threshold sensitivity or evidence about stopping effectiveness. The original eighteen-job calibration proposal is still incomplete. A long prompt does not establish prefill-dominated GPU service. No diagnostic accuracy, capture-active savings, operator benefit or main-study readiness is claimed.

## Integrity and cleanup

All **451 CPU tests pass**, including **12 new checks**. [Full suite](pairs_025_deployment/cpu_suite.log), [focused tests](pairs_025_deployment/cpu_focused.log). Existing playback defaults remain exercised by the broader suite.

[Saved backup audit](PAIRS_VALIDATION.json) verifies **472 artifact hashes**, **360 source fingerprint entries** across five manifests (72 source files per manifest), all exact paired hashes, request/warmup usage, 64 raw metrics, 16 measured windows, **24 fresh barrier receipts**, both SQLite traces and zero fabricated/locked references. [Audit script](pairs_025_deployment/validate_backup.py).

[Independent cleanup checks](pairs_post_cleanup_checks.json) confirm all four serving parents/groups/workers absent, empty compute inventory and **0 MiB GPU memory**. Raw outputs, reports/databases, source/inputs, supervisor files and logs are backed up locally. Owned jobs are stopped; **the rental instance remains running**.

Next: inspect the evidence and establish an explicit assessment/rubric workflow and coverage/mismatch limits. Identify additional instrumentation/challenging cases needed for a defensible narrower feature profile before reference locking or fitting. The main protocol remains unfrozen.
