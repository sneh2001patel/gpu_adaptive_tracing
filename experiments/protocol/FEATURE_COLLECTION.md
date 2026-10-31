# Feature collection and evidence joining — step 014

CPU implementation and loopback/fake-profiler checks only. No GPU, SSH connection, production metric endpoint or fitted classifier is used. The old L4 pilot is unchanged.

## Implemented collection paths

[feature_collection.py](../tracing/feature_collection.py) provides bounded async HTTP transport, `collect_completion`, `QueueGaugeCollector`, `ObservedCompletion`, `ServerSample` and `FeatureWindow`.

- HTTP uses a whole-operation deadline and a body-size limit. It supports finite Content-Length or connection-close responses; chunked/streaming/SSE responses are rejected. Cancellation propagates and closes the client connection. There is no retry or token streaming.
- Request records measure start through full response receipt. Token features use actual response `usage.prompt_tokens` and `usage.completion_tokens`. Configured prompt/output budgets never substitute for response usage. Successful HTTP with missing/malformed usage retains latency but makes tokens unavailable; failed/time-out requests retain a terminal error and no successful usage. Arbitrary response fields are not forwarded.
- Queue collection requires an explicitly configured exact metric/label series and one `# TYPE <name> gauge` declaration. It rejects counters, duplicate series, nonfinite/negative values and explicit remote timestamps. Missing series, errors and timeouts produce null plus a reason, not zero. Exact labels/order must match; this is deliberately a subset parser, not a general Prometheus/OpenMetrics client. There is no automatically chosen vLLM metric name or worker aggregation.
- Queue point time is parent HTTP receipt; request/receipt bracketing is saved. It is not a server event timestamp or an established averaging interval. Window queue/GPU means are sample means, not time-weighted means.
- `request_wait_p95_ms` and `prefill_service_fraction` remain explicitly unsupported by this collector. Queue gauges and cumulative counters do not establish these interval statistics. They need validated histogram deltas/phase attribution or another measured source before diagnosis calibration. Endpoint names and metric semantics must be validated on the next GPU deployment.

## Window and missing-data behavior

A `FeatureWindow` handles one half-open acquisition interval, with an explicit grace period. Completion time assigns request cohorts; parent receipt assigns server samples. The final horizon endpoint is included only when `include_end=True`, matching the existing raw-window adapter. It checks current receipt time, timestamp/domain, duplicate identities and actual availability; supplying an old availability timestamp cannot hide late receipt. Outside/late records remain in an audit ledger but do not rewrite closed metrics.

Call `close()` only after its deadline. It creates immutable typed metric records; repeated closure returns the same tuple. Metric availability is actual closure time, including grace/service delay. Minimum latency count is an explicitly supplied **development guard**, not a calibrated threshold. Sparse completions produce null p95 with an insufficient-count reason; actual success/error counts remain in the audit. This rule belongs to the new feature collector and does not silently modify the old cheap activation/recovery window implementation.

`completed_rps` counts successful observed completions divided by window duration. It uses one closed-window counter observation, so a genuinely observed empty completion stream records zero rate while latency stays null. Its sample count is a counter observation count, not the number of completed requests. Other aggregate counts refer to delivered eligible raw records; acquisition coverage does not prove adequate sample density, that every scheduled poll occurred, or that observations are independent. Scheduler skips/censoring must be recorded by the future workload driver.

Failed request records contribute to p95 attempted-sample accounting but not successful latency values. Token means use successful responses with valid reported usage. Missing usage or failed GPU/queue polls produce partial/unavailable metrics. No absent queue/prefill metric is interpreted as healthy. The collector's audit distinguishes request errors, usage missingness, accepted/outside/late records and threshold role. It does not invent pending admissions or end-to-end overhead results.

All `on_*` calls belong to a single serialized owner, as in the existing producer bridge. Concurrent callback wiring and the full admission/drain driver are not implemented by a one-window object. The caller must retain raw records in addition to the audit; the demo saves them explicitly.

## Join to the classifier

[feature_bridge.py](../tracing/feature_bridge.py) implements `kernel_from_ready` and `FeatureClassifierBridge`:

1. Register a closed window using the exact same clock object as the bridge.
2. Obtain actual `ReadyEvidence` from a backend, retaining capture/evidence ID, ready time, domain and provenance. Provide its host acquisition interval separately. This interval is not a certified GPU capture-active interval.
3. Validate source, single-worker/device identities, coverage and readiness. Live source is `nsys_sqlite`; synthetic source is `synthetic_fixture`. Extract only measured kernel count/time/identity fields; raw kernel names and any foreign payload metadata are excluded from classifier input.
4. Wait until both feature closure and parsed evidence are available. Future evidence raises `EvidenceNotReady` without consuming an identity or emitting a prediction. Preserve each metric's original closure availability; the bundle's availability is the latest prerequisite.
5. Require kernel acquisition to lie inside the original window/domain. An adjacent-window report is an error; there is no fallback to latest measurements and no automatic stale-value reuse. A production integration may need a wider explicitly aggregated acquisition window if export/control spans exceed the cheap-window width.
6. Pass the strict typed observation to `UncalibratedClassifier`. Duplicate evidence IDs cannot produce another classification, including across windows. Cheap-only classification has no capture identity and remains unknown.

Coverage/provenance declarations do not independently prove a real GPU report. The live Nsight parser remains responsible for actual report/device/worker verification. The new measured bridge is not yet wired into the legacy GPU runner or its evidence gate; it is a tested collection/join component for the forthcoming workload/arm runner. No old pilot result is reclassified.

## Reproduction and reviewable outputs

From the repository root, use a new directory:

```bash
python3 -m experiments.scripts.demo_feature_bridge --output /tmp/my_feature_bridge_demo
python3 -m unittest experiments.tests.test_feature_collectors -v
```

The demo uses real loopback HTTP requests and a delayed `FakeProfilerBackend` on a host monotonic clock. Server queues, response usage, GPU utilization and kernels are fixture values. Five saved scenarios cover [complete](../examples/feature_bridge_demo/complete.json), [missing queue](../examples/feature_bridge_demo/missing_queue.json), [missing usage](../examples/feature_bridge_demo/missing_usage.json), [sparse completions](../examples/feature_bridge_demo/sparse.json) and [queue transition](../examples/feature_bridge_demo/transition.json). They contain raw request/server records, closure/late audits, typed observations, predictions and profiler timing events. Every prediction remains null; even the complete scenario lacks calibrated wait/prefill evidence. These are mechanics checks, not workload diagnoses or GPU measurements.

Step 015 adds [exact offered-arrival validation/playback, admission/drain/censoring accounting and a serialized collector owner](OFFERED_WORKLOAD_PLAYBACK.md). Step 016 adds CPU arm lifecycles and independent server quiet/reset checks. Step 017 adds durable evaluator reference storage/scoring. Step 018 adds [typed interval adapters and initial-stop export](INTERVAL_METRICS_AND_EXPORT.md), without validating a live metric endpoint. Step 019 adds [CPU collection/arm-runner binding](ARM_COLLECTION_AND_EXPORT.md). Step 020 adds [feasibility gates and scoped read-only discovery](LIVE_FEASIBILITY.md). Next is fresh L4 capability discovery (021), followed by owned activity/instrumentation validation and calibration.
