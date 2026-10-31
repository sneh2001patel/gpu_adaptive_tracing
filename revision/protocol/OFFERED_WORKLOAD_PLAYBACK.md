# Exact offered-workload playback — step 015

Implemented and tested on CPU with local HTTP fixtures. No GPU/SSH access, server launch, experimental arm comparison or fitted diagnosis is performed. This driver is a component for the next experiment runner, not the final study runner.

## 1. Save the offered requests before running an arm

[arrival_schedule.py](../tracing/arrival_schedule.py) loads exact UTF-8 JSON bytes using `ArrivalSchedule.load(path)` or `from_bytes(raw)`. The strict schema is:

```json
{
  "version": "offered_arrivals_v1",
  "duration_ns": 250000000,
  "requests": [
    {"request_id": "opaque-0", "offset_ns": 0,
     "payload": {"model": "fixture", "prompt": "Actual request text", "max_tokens": 99, "stream": false}}
  ]
}
```

Use unique opaque request IDs and nondecreasing integer offsets in `[0, duration_ns)`. Equal offsets are allowed to represent explicitly planned bursts. Prompt text and model/output settings are actual driver inputs, not diagnosis features. Allowed optional request fields are temperature, seed and ignore_eos. Expected labels, scenario/phase metadata, unknown request fields, duplicate JSON keys, invalid values, duplicate IDs and out-of-horizon arrivals are rejected. Evaluator interventions and references remain separate sidecars.

Each payload is stored as immutable canonical JSON and decoded afresh for a request. The schedule records both the exact input-file SHA-256 and a canonical-content SHA-256; whitespace-only edits change the first, while request/time/prompt changes also change the second. Reuse the same file across matched arms. These checks establish what was offered, not equal admitted or completed work. They do not establish corpus disjointness, tokenizer/context compatibility or model feasibility; calibration/freeze must still verify those.

## 2. Run against an existing HTTP service

[schedule_playback.py](../tracing/schedule_playback.py) implements `SchedulePlayback`; [play_arrivals.py](../scripts/play_arrivals.py) supplies a CLI. It preserves exact schedule bytes and source hashes in a new output directory, then saves raw receipts, request ledger, window audits/metrics, typed observations and unknown predictions. Failures after driver start retain a partial snapshot and propagate the exception.

For an existing service, supply its URL, a schedule with the matching served model and a new output directory:

```bash
python3 -m revision.scripts.play_arrivals \
  --schedule "$ARRIVAL_OFFERED_FILE" \
  --endpoint "$ARRIVAL_COMPLETIONS_URL" \
  --provenance synthetic_simulation \
  --output /tmp/my_arrival_playback
```

Set `live_online` only for actual live measurement, never to promote a fixture into GPU evidence. The CLI does not launch a GPU sampler/profiler or initialize a serving target. An existing remote inference endpoint may itself use a GPU; all validation in this step uses loopback CPU fixtures only. Queue endpoint/series options are optional and must be supplied together. The short default windows/lateness/drain settings are development settings, not a calibrated GPU protocol.

Playback derives absolute due times from one monotonic start plus saved offsets. A single owner decides admissions, consumes receipts, routes metrics, closes windows, calls the window callback and services the optional evidence hook. HTTP/sample tasks publish results without modifying classifier/policy/window state.

- At capacity, retain the offered ID as `skipped_capacity`; do not retry or shift its due time.
- Past the explicit admission-lateness tolerance, record `skipped_scheduler`. Unprocessed offers after the fixed horizon become `skipped_horizon`.
- Offers still within tolerance may be admitted together after a scheduling delay. The declared tolerance is therefore part of the protocol; there is no claim of zero arrival jitter or that all late offers are skipped.
- Record due, actual admission/dispatch and HTTP receipt/start times separately. Local task scheduling can separate admission from HTTP start; admission is not proof of server receipt or queue entry.
- Bound admitted in-flight IDs until their terminal receipts are consumed. A terminal queue reserves one slot per admitted request so telemetry cannot displace response outcomes.
- Bound telemetry publication separately. Full telemetry queues retain dropped records in an explicit overflow journal and flag receipt coverage. Sampling scheduler skips, failures and horizon cancellation are distinct. Do not present a flagged run as complete metric coverage.

A sampler callback is optional and must be cooperative on cancellation; callback deadlines and cleanup belong to its implementation. The optional NVML adapter must still be freshly owned per episode/run. This driver does not open or reuse NVML sessions by itself. Raw journals/schedules remain in memory until saved: bounded concurrency and transport queues are not bounded total artifact memory or a throughput guarantee.

## 3. Keep horizon, drain and censoring distinct

Every offered ID receives a ledger state. Top-level `admitted` counts all admissions; `counts.admitted` is the remaining pending state. End states distinguish successful `completed`, terminal `failed`, `censored`, capacity/scheduler/horizon skips, and offers not dispatched because the run aborted. Conservation checks verify all offered IDs, admitted outcomes and concurrency limits.

HTTP timeout/error is a failed terminal, not a success. At the fixed request horizon, admissions stop while outstanding requests may drain. A response during drain remains a real completion with its actual timestamps and token usage; it does not rewrite earlier closed windows. At the drain cutoff, unfinished client requests are cancelled and marked `drain_cancelled`/censored. Client cancellation duration is not an observed successful response latency. External cancellation or callback failure aborts the run, retains accounting and closes client tasks; unstarted task cancellation is also accounted for.

`observed_horizon` records the owner's first horizon observation and its then-visible pending IDs, including its actual timestamp. `pending_at_horizon_reconstructed` uses later terminal timestamps to reconstruct pending admissions at the horizon; it is evaluator-only and cannot enter the online classifier. It stays null if an aborted run never observed the horizon. The two views must not be conflated when receipt processing is delayed. Post-horizon terminal counts distinguish real successes/failures from censored outcomes through the ledger/counts; no latency is imputed for missing responses.

Closing a client connection does **not** prove cancellation of server/GPU work. The next arm/reset implementation must independently establish queue/worker quiescence or restart the owned target before comparison. Local `live_request_tasks=0` only describes this driver's tasks.

## 4. Connect to measured feature windows and evidence

One owner routes completions by completion time and server/GPU samples by parent receipt to the original half-open acquisition window; the final endpoint belongs to the last window. Actual owner receipt time determines grace/late acceptance. In-flight/pending and censoring records are retained in the ledger rather than supplied as invented completed latency. Missing/unsupported wait/prefill features remain null.

`on_window(window_id, window)` receives only a closed measured feature object. It can register that object with `FeatureClassifierBridge`; no offered payload, phase or expected label is forwarded. `service_evidence()` can poll readiness during HTTP playback/drain. Both callbacks are synchronous and must stay brief: their runtime is part of actual scheduling/receipt delay. The driver does not backdate delayed closure or manufacture unavailable evidence.

Evidence still needs the strict interval/domain/provenance/worker/device checks from [step 014](FEATURE_COLLECTION.md). The driver does not automatically wait indefinitely for an unresolved backend after its configured workload/drain/grace lifetime. The callback owner must retain pending/horizon-censored evidence and clean up the backend separately. This is not yet integration with the legacy live policy controller, experimental arm ownership or an incident reactivation study.

## 5. Reproduce the CPU checks

```bash
python3 -m revision.scripts.demo_schedule_playback --output /tmp/my_schedule_playback_demo
python3 -m unittest revision.tests.test_schedule_playback -v
```

The demo writes one [exact offered file](../examples/schedule_playback_demo/offered_arrivals.json) and reuses its hash across six fixture runs: [normal](../examples/schedule_playback_demo/normal.json), [capacity](../examples/schedule_playback_demo/capacity.json), [timeout](../examples/schedule_playback_demo/timeout.json), [drain](../examples/schedule_playback_demo/drain.json), [transition](../examples/schedule_playback_demo/transition.json), and [delayed evidence](../examples/schedule_playback_demo/delayed_evidence.json). They save raw receipt/overflow logs, per-ID outcomes, windows, predictions and synthetic profiler events. Source hashes are saved alongside them. All queue/token/GPU/kernel values are fixtures; loopback durations are CPU execution observations, not an experimental hardware baseline or GPU cost.

During validation, the full suite exposed an older step-014 demo's 200 ms fixed fixture interval being exceeded by host scheduling delay. That contract demo now constructs its example interval after HTTP acquisition, retaining the strict bridge bounds. This changes only synthetic fixture setup: the exact-arrival driver and proposed GPU protocol retain predeclared horizons.

Step 016 implements [distinct owned CPU arm lifecycles and independent quiet/reset gates](EXPERIMENT_ARM_LIFECYCLE.md). Step 017 implements [durable reference locking/scoring](LOCKED_REFERENCE_SCORING.md). Next is interval instrumentation/export preparation (018), followed by actual GPU lifecycle/calibration validation.
