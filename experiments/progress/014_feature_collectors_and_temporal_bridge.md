# Step 014 — Request/server feature collection and temporal joins

Date: 2026-10-27. Status: complete for the implemented CPU collection scope. Queue-depth gauge and actual response usage collection are implemented; interval wait/prefill statistics, live GPU wiring and calibration remain pending. No GPU or SSH access used.

## Completed

- [x] Add bounded async HTTP receipt/body collection, actual response-token extraction, typed successful/failed completions, and explicit missing usage. Do not use requested token budgets as measured input.
- [x] Add an exact-series server queue-gauge collector with explicit metric-type validation, null/error outcomes for unsupported/missing/malformed data and parent request/receipt timestamps.
- [x] Add raw completion/server/GPU feature windows with counts, grace/receipt audit, final-boundary handling, immutable closure and an explicit development sparse-latency guard.
- [x] Keep wait p95 and prefill fraction explicitly unavailable rather than infer them from queue depth or cumulative counters.
- [x] Join closed metric windows to newly parsed kernel evidence by interval/domain/readiness/provenance, verifying configured worker/device identity and extracting measured fields only.
- [x] Route typed bundles into the uncalibrated adapter. Future evidence waits without mutation; adjacent-window evidence and duplicate identities are rejected. Diagnoses remain unknown.
- [x] Exercise complete/missing/sparse/transition scenarios using real loopback HTTP plus delayed fake-profiler parsing; preserve raw fixture records and timing/audit artifacts.
- [x] Update the contract guide, README, progress tracker and CAIN revision plan.

## Files and validation

- [Collectors](../tracing/feature_collection.py) and [temporal bridge](../tracing/feature_bridge.py).
- [Guide](../protocol/FEATURE_COLLECTION.md), [demo](../scripts/demo_feature_bridge.py), [tests](../tests/test_feature_collectors.py).
- [Complete fixture](../examples/feature_bridge_demo/complete.json), [missing queue](../examples/feature_bridge_demo/missing_queue.json), [missing usage](../examples/feature_bridge_demo/missing_usage.json), [sparse completions](../examples/feature_bridge_demo/sparse.json) and [transition](../examples/feature_bridge_demo/transition.json).

All **240 CPU-only tests pass**, including 23 new collection/bridge checks. All five saved loopback/fake-profiler scenarios complete with six unknown predictions in total; synthetic queue samples transition from 8 to 0 without creating a concrete diagnosis. `git diff --check` passes. The new tests cover actual response usage, errors/timeouts/cancellation/body limits, exact gauge selection, unsupported/missing/duplicate/nonfinite data, sparse/partial/zero semantics, receipt/closure/boundary rules, delayed readiness, mismatched intervals/worker/device/domain/provenance, duplicate evidence and exclusion of foreign metadata. The HTTP-transition integration checks the whole fixture → collectors → closed windows → delayed fake parse → typed adapter path.

## Limits

No GPU endpoint names or semantics have been validated. Queue sample means are not time-weighted queue averages. Reported token usage is from the response, not independently recomputed tokenization. Missing wait/prefill measurements still prevent those mechanisms from being calibrated. Complete acquisition accounting does not prove sufficient samples or absence of skipped scheduled polls.

The old activation/recovery aggregator and L4 pilot remain unchanged; the richer bridge is separately CPU-tested and is not yet the live evidence-gate callback. Production collection needs a serialized producer/arm runner and explicit host acquisition alignment; an interval mismatch cannot be hidden by a latest-window join. Durable blinded reference storage, phase attribution, actual calibration and frozen confirmation remain unfinished. Synthetic GPU/kernel values are not measurements.

## Next step — 015 (CPU-only)

1. Define and hash exact offered-arrival files with timestamps, unique IDs and actual request payloads; keep case/phase/reference metadata in a separate driver/evaluator artifact.
2. Implement bounded asynchronous playback with the same offered schedule across arms, explicit admission/skips/errors, response usage, outstanding requests, timeouts and drain/censoring records.
3. Serialize request/server/GPU receipts into feature windows while delayed evidence is being serviced. Test queue backpressure, sparse completions, transitions and horizon boundaries using local fixtures.
4. Next implement distinct unprofiled/cheap-only/reference arm lifecycles and reset checks, then durable reference locking/scoring. GPU rental remains unnecessary for this driver preparation.
