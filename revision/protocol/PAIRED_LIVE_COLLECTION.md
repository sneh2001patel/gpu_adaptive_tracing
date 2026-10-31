# Owned paired live collection — step 025

This bounded pilot executes the four candidate jobs materialized in step 024. It verifies exact-arrival collection across separate fresh serving runs and assembles evidence for later assessment. It does not create adjudicated references, fit a classifier or execute the main study.

## Input and lifecycle

`load_pairs` requires the original unfrozen, unexecuted candidate manifest, exactly two roles per short/long pair, distinct integer order positions, fresh-restart requirements and matching offered-file SHA-256 values. Paths remain bounded to the input directory. Each schedule lasts eight seconds, contains at most twelve requests and requests exactly 32 output tokens with EOS suppression. The saved candidates have two arrivals each at offsets zero and four seconds.

Run all four jobs in their previously seeded order: short feature collection, short matched full trace, long matched full trace, long feature collection. Each job owns a fresh engine/worker, session nonce, generation and reset token. Validate pinned inventory and quiet barriers; submit the same declared first-request warmup outside the measured range; repeat quiet checks. Prefix caching remains enabled as in step 024. Fresh engine/KV state is created per job; model/OS page cache is reused.

Both roles run the existing `SchedulePlayback` driver against **identical offered bytes within a pair**. Its optional window factory and completion collector retain the original defaults for previous callers. The new collector stores raw HTTP bytes/status/usage/errors and client timestamps. Bound raw metric receipts map to server samples backed by the same validated session scope; the window rejects a sample that differs from its raw receipt. Each two-second measured window persists independently after a 0.25-second grace. Actual prompt/output usage is retained; missing interval/phase/GPU-utilization features stay unavailable.

Playback allows at most four in-flight requests, a 12-second HTTP deadline, 15-second drain, 0.25-second admission lateness and 0.5-second metric cadence. Skips, errors, censoring, telemetry drops and outstanding tasks remain in the ledger. This plumbing pilot passes only when every offered request is admitted/completed and the request/sampling lifecycle checks pass. A failed run is retained, not retried silently.

## Full-trace role

Only a matched-full-trace job launches its fresh server under Nsight. Exactly one attempted range is allowed per such job, two attempts total across the pilot. Wait for both the real CUDA-worker start acknowledgement and Nsight callback before starting playback. Stop after playback and its admitted requests/drain finish; require report export, SQLite parsing and exact worker/device coverage before proceeding. Save control timestamps and verify that they bracket playback. Each report is obtained while serving remains alive, followed by post-work quiet checks and owned shutdown.

Control bracketing and valid kernels do not independently prove zero event loss, complete per-request CUDA attribution or active capture boundaries. `capture_active_s` remains null. Warmup/startup are outside the requested control range. The full trace belongs to a **separate execution**, not the feature run's ground truth. No classifier or stopping policy consumes the trace in this step.

The pilot work deadline is 480 seconds, with separate bounded cleanup. Supervisor manages the top-level job; all serving groups and backend helper processes are owned. Preserve source/input archives, worker/reset records, raw responses/metrics, playback ledgers/windows, backend/timing events, reports/SQLite and independent cleanup checks off-host.

## Assessment packet

`ADJUDICATION_PACKET.json` links request/server diagnostics and full-trace artifacts by relative paths and hashes. The entire run's artifact manifest also binds linked raw records. For each pair, display both realized completion counts and per-request client latencies; do not assume identical realized behavior from identical offered schedules.

Its role is `artifact_packet_not_adjudicated_reference`; status is `awaiting_blinded_assessment`. It creates/locks zero references and computes no predictions. The assessor must supply identity, rationale, alternative-cause checks, source/clock/cohort coverage, trace limitations and matched-run mismatch assessment. Intended prompt bands do not establish queue pressure or prefill-dominated service. Sparse low-rate cases cannot establish healthy reference coverage merely because no request failed.

The packet contains no policy predictions; no assessor blinding is claimed to have occurred. Reference locking must use the existing reference store after actual assessment, before scoring. Metrics and request channels are independent of classifier output but are not independent proof of causality.

## Invocation and tests

Run in the pinned GPU environment under the one-shot supervisor wrapper, using a fresh output directory:

```bash
python -m revision.scripts.run_l4_pairs --output /workspace/results/pairs_new --pairs /path/to/paired_schedules --model-path /path/to/pinned/model --device-uuid GPU-UUID
```

```bash
python3 -m unittest revision.tests.test_paired_collection -v
```

Original candidate manifests stay immutable; execution records are written to the new pilot directory. Passing this low-rate two-prompt engineering pilot does not complete the eighteen-job calibration proposal or establish maximum capacity, challenging-case diagnosis, threshold sensitivity or main-study readiness.

## Subsequent assessment and next step

Step 026 adds [the retrospective gap audit, draft rubric and reviewer workflow](EVIDENCE_ASSESSMENT.md). It identifies sparse latency windows, point-sampled zero queues, missing event/phase mapping and unset prospective mismatch tolerances. The blank worksheet does not create a reference; actual adjudication/locking remains pending.

Next step 027 prepares clock-bound server event instrumentation and prospective coverage/sample-volume/mismatch/challenge rules on CPU before further bounded GPU validation. Do not manufacture labels or fit thresholds from intended interventions or these sparse low-rate observations.
