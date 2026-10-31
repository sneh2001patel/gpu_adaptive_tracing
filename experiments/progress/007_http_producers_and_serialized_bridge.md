# Step 007 — HTTP producers and serialized sampler bridge

Date: 2026-10-27. Status: completed for CPU HTTP integration. No GPU, NVML, CUDA profiler, or production serving experiment was run.

## Completed work

- [x] Added `experiments/tracing/producers.py`: asynchronous nonstreaming JSON HTTP POST producer, sampler callback interface, and one serialized event queue feeding the raw-window adapter and controller.
- [x] Used one process monotonic clock for admission, response completion, sample availability, queue receipt, windows, and controller timing. Queue delays and raw records are retained in a separate producer ledger; the adapter still uses actual ingestion time for lateness.
- [x] Added a fixed observation horizon, paced admission, bounded concurrency, explicit capacity/scheduler skips, and no catch-up admission bursts. Starts are published before network work and before their matching terminal records.
- [x] Added per-request timeout, bounded post-horizon drain, cancellation records, terminal HTTP/transport errors, sampler failure/missing readings, and cleanup on cancellation/consumer failure.
- [x] Kept controller observation closure separate from request drain: controller finalizes after the last window and its grace, while the adapter can still record drain completions without changing previous windows.
- [x] Kept healthy calibration explicit and unchanged. No expected labels, workload-name diagnosis rules, or inferred root causes enter the producer interface.
- [x] Added `demo_http_stream.py`, a local fake HTTP service with slow/error/missing/drain scenarios, fake utilization samples, and the existing fake profiler. Unlike the earlier virtual-clock demo, these request lifetimes include actual local network receipt time.
- [x] Saved example outputs, added 12 producer/configuration/integration tests, and updated README, tracker, and revision plan.

## Validation

```bash
python3 -m unittest discover -s experiments/tests -q
python3 experiments/scripts/demo_http_stream.py --scenario slow
python3 experiments/scripts/demo_http_stream.py --scenario errors
python3 experiments/scripts/demo_http_stream.py --scenario missing
python3 experiments/scripts/demo_http_stream.py --scenario drain
python3 -m py_compile experiments/tracing/producers.py experiments/scripts/demo_http_stream.py experiments/tests/test_producers.py
git diff --check
```

The full suite passes **126 CPU-only tests** (114 previous, 12 added). New coverage includes configuration, actual HTTP receipt/order, unchanged calibration, concurrency and bounded drain, timeout/error propagation, missing/failed/hung samplers, single-use bridge, skipped admission slots after a blocked event loop, consumer-failure cleanup, oversized/truncated/chunked response rejection, and explicit demo provenance/unknown diagnosis.

Saved examples each emit eight observation windows. The error example records HTTP 503 failures; missing readings remain null; the drain example records three cancellations after the horizon, resolves all three tracked requests, and preserves the pending count in the final observation window. Counts and wall times depend on local scheduling; they are behavioral fixtures, not paper results. Testing exposed a fake-server shutdown-order issue, corrected by cancelling handlers before waiting for the server to close.

## Scope and limits

- CPU is the development environment, not an experimental hardware baseline. This work establishes no GPU savings, serving perturbation, classifier accuracy, or profiler coverage.
- Generic HTTP POST transport supports finite nonstreaming responses with Content-Length or connection-close framing. It rejects chunked transfer and SSE. It does not implement streaming tokens/TTFT, retries, authentication, production response-schema validation, redirects, pooling, or multi-process clock mapping. HTTP 2xx plus complete body is transport success, not semantic model-output correctness.
- Admission is paced with skipped slots under saturation, not a validated reproduction of the old workload generator. HTTP producer timings include client scheduling, connection setup and response receipt; they are not GPU kernel/service times.
- Sampler callbacks must cooperate with asyncio cancellation. Blocking native calls need separate isolation before use. Failures yield missing data; readings are never carried forward.
- The queue and audit ledgers are in memory and unbounded. This research bridge has no measured production throughput, memory, or perturbation guarantees. Window lateness can expose slow service but cannot recover dropped control evidence.
- The controller still uses a synthetic profiler and abstains on diagnosis in this demo. No original runner, experiment, paper table, or historical artifact was regenerated.

## Next step

**Step 008: GPU telemetry adapter and deployment preflight.** Implement an optional NVML sampler with CPU-testable device/error/clock contracts and a clear environment/configuration check; avoid importing GPU packages for CPU workflows. Specify the real profiler backend's attachment, capture acknowledgement, report-readiness, worker-coverage, and cleanup requirements before live integration. These preparations can continue without a GPU. **Actual NVML sampling and Nsight capture validation require access to an NVIDIA GPU**; notify the user before that validation milestone. Create a numbered report and update both tracking files.
