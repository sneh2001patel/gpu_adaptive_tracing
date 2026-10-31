# Step 025 — owned paired collection and assessment packet

Completed: 2026-10-28. CPU implementation/tests followed by a four-job supervised L4 pilot.

## Completed checklist

- [x] Validate immutable paired schedules, shared hashes, role/order/reset requirements and bounded request/output counts.
- [x] Add optional window/completion hooks to the existing exact-arrival playback driver, preserving original defaults.
- [x] Bind raw scoped metrics to measured live windows; preserve actual raw HTTP responses/status/usage/errors and conserved admission/completion ledgers.
- [x] Execute four fresh owned servers with identical within-pair offered bytes, declared warmups and repeated quiet checks.
- [x] Execute exactly two Nsight range attempts, require control bracketing/report export/parse and exact worker/GPU coverage, then close helpers/servers.
- [x] Assemble hashed request/server/full-trace packets and descriptive mismatch data without fabricating reference labels, assessor decisions or locks.
- [x] Pass 451 CPU tests, including 12 new checks, and archive the tested source plus inputs before launch.
- [x] Independently verify owned cleanup, back up/audit all artifacts and update the progress tracker/revision plan.

## Implementation and evidence

[Collection helpers](../feasibility/paired_collection.py), [CLI](../scripts/run_l4_pairs.py), [playback hooks](../tracing/schedule_playback.py), [protocol](../protocol/PAIRED_LIVE_COLLECTION.md), [hardware report](../hardware/l4_20261028/PAIRS_REPORT.md), [validation](../hardware/l4_20261028/PAIRS_VALIDATION.json), [raw result](../hardware/l4_20261028/pairs_001/RESULT.json).

The two exact offered files from step 024 each run twice, in their pre-existing seeded order. **All eight scheduled requests and four warmups succeed**, with expected 17/1,072 input-token counts and 32 output tokens. No skips, request errors, censoring, sampling errors/skips or telemetry overflows occur. Four different workers/nonces/generations are verified. Sixteen live windows retain actual usage/completion statistics and **64 raw metric receipts**; unsupported wait/phase/GPU-utilization metrics remain null.

The two full-trace jobs yield **21,308 and 23,044 kernels** on their expected workers/GPU. Acknowledged start/callback precede playback, stop follows complete playback/drain, and SQLite parse/coverage gates pass. Each backend helper is closed; active capture duration remains unknown. Feature-only jobs produce no traces. Neither a classifier nor a stopping policy runs.

The [assessment packet](../hardware/l4_20261028/pairs_001/ADJUDICATION_PACKET.json) binds **ten diagnostic artifacts** and lists realized request counts/latencies and required mismatch/coverage/alternative-cause assessments. It is an artifact packet awaiting blinded assessment, not an adjudicated reference. **Zero references are created/locked.** Intended prompt bands and successful requests do not establish cause labels or healthy references.

The saved audit checks **472 artifact hashes**, **360 archived source fingerprint entries** (five manifests of 72 files), all exact offered hashes, response usage, both traces, 24 fresh worker barriers and lifecycle/cleanup records. All four owned groups/workers are absent and GPU memory is 0 MiB. Off-host backup is complete. The rental itself remains running.

## Limits

This is a low-rate two-prompt collection pilot, not the eighteen-job calibration study or challenging-case evaluation. Prefix caching/repeated prompts, one run per role and two requests per job preclude generality or reliable perturbation/precision conclusions. The trace is from a separate execution; equal offered load does not prove realized equivalence. Trace control bracketing and parsed kernels do not prove lossless per-request attribution or active-time boundaries. Human assessment/blinding is not asserted. No calibrated thresholds, diagnostic accuracy, active-capture savings, stopping effectiveness or operator benefit is established; protocol freeze remains false.

## Next step — 026

1. Inspect the paired evidence and implement an assessment/rubric workflow with explicit clock/cohort/coverage and matched-run mismatch limits.
2. Record unresolved/negative evidence and assess whether existing channels support a narrower candidate feature profile; identify additional instrumentation/challenging cases where they do not.
3. Prepare the next bounded collection checks without manufacturing labels from intended interventions. Actual adjudication must precede reference locking and fitting.

CPU preparation can proceed next. Further instrumentation/challenging-case validation will need GPU access. Owned jobs are stopped; the rental remains running.
