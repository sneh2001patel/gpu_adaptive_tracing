# Step 015 — Exact offered arrivals and bounded playback

Date: 2026-10-27. Status: complete for CPU driver preparation. No GPU or SSH access used; no calibration, new diagnosis or experimental arm comparison claimed.

## Completed

- [x] Implement strict offered-arrival files with unique IDs, ordered relative timestamps, actual immutable request payloads, exact-file/canonical-content hashes and duplicate/foreign metadata rejection.
- [x] Implement bounded async playback with absolute due times, explicit admission tolerance, capacity/scheduler/horizon skips, actual response usage and per-ID accounting.
- [x] Record timeouts/errors, observed/reconstructed horizon pending state, real post-horizon completion, drain censoring, abort outcomes and task cleanup separately.
- [x] Reserve terminal receipt capacity and separately bound telemetry; retain overflow records and sampling skips/failures/cancellation rather than silently claim complete coverage.
- [x] Serialize raw receipts into measured feature windows while servicing delayed evidence; keep offered payload/evaluator data out of typed classifier observations.
- [x] Add CLI artifact persistence and six loopback workload fixtures reusing one exact offered file, including delayed fake-profiler evidence during continued HTTP playback.
- [x] Fix an older contract demo's host-load-sensitive interval construction without relaxing production interval checks or the new driver's predeclared horizon.
- [x] Update the guide, README, progress tracker and CAIN plan.

## Files and validation

- [Schedule contract](../tracing/arrival_schedule.py), [playback](../tracing/schedule_playback.py), [CLI](../scripts/play_arrivals.py).
- [CPU demo](../scripts/demo_schedule_playback.py), [tests](../tests/test_schedule_playback.py), [guide](../protocol/OFFERED_WORKLOAD_PLAYBACK.md).
- [Offered file](../examples/schedule_playback_demo/offered_arrivals.json), [normal run](../examples/schedule_playback_demo/normal.json), [capacity](../examples/schedule_playback_demo/capacity.json), [timeout](../examples/schedule_playback_demo/timeout.json), [drain](../examples/schedule_playback_demo/drain.json), [transition](../examples/schedule_playback_demo/transition.json), [delayed evidence](../examples/schedule_playback_demo/delayed_evidence.json).

All **262 CPU-only tests pass**, including 22 new schedule/playback checks. The older corrected fixture and the new tests also pass in a focused 23-test run. All six final demo runs share the same exact offered-file hash, conserve offered/admitted outcomes, retain unknown predictions and finish with zero live driver request/sample tasks. Saved source fingerprints, typed observation roundtrips and documentation links are verified; `git diff --check` passes. New checks cover exact hash preservation/immutability, rejected truth fields/duplicate keys, capacity/scheduler/horizon misses, identical offered files with different realized work, HTTP failures, bounded drain/censoring, telemetry overflow/missingness, cancellation/consumer failure, CLI output and end-to-end fake evidence during local playback. The initial full-suite failure identified the older synthetic demo timing assumption; it is corrected and retained in this step's validation history.

## Limits

These are mechanics checks. Short timing/default settings are development guards, not fitted GPU thresholds. Some fixture runs can have logged sampling skips; those remain explicit and must not be interpreted as complete telemetry coverage. Endpoint/tokenizer feasibility, wait/prefill interval evidence, live-controller wiring, distinct arm/reset ownership, immutable reference storage and confirmation remain pending.

Local client cleanup cannot prove cancellation or quiescence of server/GPU work. Response censoring is not a measured successful latency. Retrospective horizon reconstruction uses later receipts and must remain evaluator-only. Source/receipt logs are research instrumentation, not bounded total memory or a performance guarantee.

## Next step — 016 (CPU-only)

1. Define distinct no-profiler, cheap-only, bounded policy and full-reference arm plans. Require the same offered file/hash and declared horizon/configuration across comparable arms.
2. Implement owned target/process lifecycles with per-arm fresh sampling sessions and explicit stop/cleanup independent of policy capture stops.
3. Validate reset/quiescence and failure behavior using fake executable/HTTP targets; do not infer server idleness from empty client task sets.
4. Preserve arm/run manifests, startup/warmup/observation/drain/export/cleanup scopes and failures. Then implement durable blinded reference locking/scoring and additional interval instrumentation before renting GPU capacity for calibration.
