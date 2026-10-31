# Step 006 — Raw request completions and GPU samples to online controller windows

Date: 2026-10-27. Status: completed for the CPU-only adapter and fake-backend integration. No live HTTP service, NVML device, CUDA profiler, or historical experiment was run.

## Completed work

- [x] Added `experiments/tracing/aggregation.py` with immutable, truth-free `RequestStarted`, `RequestCompletion`, `GpuSample`, and `WindowConfig` interfaces. Records carry event/availability timestamps and a shared monotonic clock domain; expected labels and workload names are not accepted.
- [x] Implemented `StreamingWindowAdapter` to accept events as they arrive, close windows on scheduled deadlines, and immediately deliver each `CheapWindow` to the controller. It does not wait for the entire run to finish.
- [x] Defined an explicit fixed observation horizon, regular half-open windows, an inclusive final boundary, and correct partial-window denominators. A completion/sample exactly at the final horizon is included once.
- [x] Added configurable arrival grace. Data arriving before closure can contribute even when event times arrive out of order; data arriving after closure is recorded as late and cannot rewrite earlier windows. Actual ingestion time controls lateness, not a producer's earlier claimed availability.
- [x] Preserved unknown GPU data and empty-window latencies as null, while distinguishing real zero GPU utilization. GPU means use valid samples only and do not reuse old readings.
- [x] Defined p95 over all observed terminal request outcomes, including errors. Window throughput is successful completions per second; separate window reports retain total completion rate and error/success counts.
- [x] Extended `CheapWindow` with explicit completion/error/GPU-sample counts and observed pending-request information. Added controller suspicion for request errors and long pending requests so fast failures or censored slow requests cannot silently establish health. Controller version is now `streaming_v2`.
- [x] Added optional start tracking, request identity/lifetime checks, explicit unfinished/censored tracked requests, and separate post-horizon drain accounting. Drain and late completions resolve tracked outstanding requests without rewriting closed control metrics.
- [x] Added conservative interface validation for duplicates, future/unmapped clocks, invalid timestamps/metrics, premature finish, and a failing window consumer. Consumer failure is logged and stops further ingestion/delivery.
- [x] Added `demo_raw_stream.py`, connecting raw events → online windows → controller → fake profiler → parsed evidence → policy decisions. Saved stable, late, and drain examples with synthetic provenance.
- [x] Added 25 tests, exercised all five raw-stream scenarios and a grace variant, and updated README, tracker, and main plan.

## Important semantics

An observation window closes at its end plus configured arrival grace. Its `available_at_ns` is the actual emission time, including any scheduler delay. Ingest all raw arrivals at an equal timestamp before calling `advance()`; the demo then services backend deadlines. The caller must service both adapter and controller wakeups even when no requests complete.

Request latency is attributed by completion time. A regular boundary belongs to the following window; the predeclared final horizon belongs to the last window. Rates use each window's actual duration. Events after that horizon remain visible as drain/outside records rather than being silently mixed into the final window.

`sample_count` counts observed completions, including failures. `throughput_rps` counts successes only, while `completed_throughput_rps` in reports counts all outcomes. GPU sample counts distinguish absent readings from valid zeros. Unfinished-request counts/ages cover observed start records only; enforcing start/completion pairs cannot prove that a producer supplied every real admission. Completion-conditioned latency p95 does not estimate censored request latency or a complete SLO distribution.

The controller's baseline remains an explicit external healthy-calibration reference. These demos use a separate synthetic reference; the first raw window does not overwrite it. CPU simulation is not a hardware baseline and establishes no GPU savings, runtime overhead, or diagnosis accuracy.

## Validation

```bash
python3 -m unittest discover -s experiments/tests -q
python3 experiments/scripts/demo_raw_stream.py --scenario stable
python3 experiments/scripts/demo_raw_stream.py --scenario late
python3 experiments/scripts/demo_raw_stream.py --scenario drain
python3 -m py_compile experiments/tracing/aggregation.py experiments/tracing/windows.py experiments/tracing/controller.py experiments/scripts/demo_raw_stream.py experiments/tests/test_streaming_aggregation.py
git diff --check
```

The full suite passes **114 CPU-only tests** (89 previous, 25 added). New coverage includes p95/rate/sample aggregation, regular/final boundaries, partial windows, missing versus zero GPU samples, grace, actual late ingestion, immutable closed windows, out-of-order event times, duplicate/future/foreign inputs, start pairing, drain/censoring, failures/goodput, finish semantics, callback failure, nonzero origins, truth-free inputs, error/pending-trigger integration, and the raw-stream CLI.

All five synthetic fixtures (`stable`, `missing`, `errors`, `late`, `drain`) emitted 20 windows and completed without a scheduler deadlock. The late fixture recorded one late completion with zero grace and none with 0.5 s grace. The drain fixture recorded one post-horizon completion and no unfinished tracked requests at finalization. These are behavior checks, not empirical performance results.

## Remaining limits

- The adapter accepts serialized raw callbacks; actual load-client and NVML producers are not wired to it yet. No old wall-clock records are relabeled as monotonic observations.
- Observation horizon, arrival allowance, anomaly thresholds, and pending-age thresholds are explicit uncalibrated settings.
- The research harness retains its audit ledger/window reports in memory; production throughput, memory, and perturbation costs remain unmeasured.
- Real GPU profiler readiness, worker coverage, process cleanup, independent diagnostic references, classifier calibration, and live overhead experiments remain pending.
- Historical raw artifacts, analyses, paper tables, and earlier audit snapshots are unchanged.

## Next step

**Step 007: real producer integration with a CPU dry run.** Wire a serving-load client to emit monotonic start/completion records and a serialized GPU-sample producer interface. Exercise the bridge against a local fake HTTP service and fake GPU sampler; keep NVML optional until GPU access exists. Ensure thread/queue ordering, bounded admission/drain, explicit arrival timestamps, and supplied healthy calibration. Then validate actual NVML and profiler integration on NVIDIA hardware. Create a new step report and update the tracker and plan.
