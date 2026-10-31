# Timing definitions and historical measurement audit

## What was measured

| Collector | Saved field | Timer boundary | Included | Excluded |
|---|---|---|---|---|
| `RQ1/scripts/run_vllm_nsys_compare.py`, `run_nsys_mode` | `duration_s` | Before `subprocess.run(nsys profile ...)` to its return | Profiler launch, wrapper/server/model startup, client work, server shutdown, report finalization during profile command | Subsequent `nsys stats`, Python parsing, summary writing; individual included phases are not separately timed. |
| `RQ1/scripts/run_microbenchmarks.py`, `collect_nsys_burst` | `duration_s` → CSV `profiler_duration_s` | Before profile subprocess to its return | Child Python/torch/CUDA/workload initialization, bounded reproduction workload, shutdown, profile report finalization | Subsequent kernel-summary stats extraction and parent analysis. |
| `RQ4/scripts/run_live_policy_validation.py`, `run_live_job` | `wall_duration_s` | Before profile subprocess to its return | Startup, serving segment selected by replay, shutdown, profile report finalization | Subsequent stats extraction, smoke-metric loading, JSON writing. |
| RQ4 historical policy replay | `heavy_trace_duration_s` | Selected rows × mean window duration | Hypothetical trace-window budget | No actual profiler execution, startup, export, or perturbation measurement. |
| `RQ3/scripts/run_vllm_runtime_overhead.py`, `request_metrics` | `duration_s` | Earliest request start to latest request end | Observed request workload span, including drain | Server startup, post-request aggregation, profiler phases. |
| `RQ2/scripts/analyze_accuracy.py`, `first_correct_seconds` | `first_correct_seconds_mean` | Labelled window end minus first window start | Position of the first matching window in the request timeline | Classifier execution/aggregation delay, profiler export/parse delay, actual diagnosis availability. |

The three profile collectors use `time.time()` differences, not a monotonic duration clock. The recorded scalars do not separate startup from capture or export. `nsys stats` may itself export intermediate data; it is a distinct, untimed command after the profile-process timer has ended.

## What the audit can and cannot recover

[timing_audit.csv](generated/timing_audit.csv) preserves the historical profile wall scalar and, where available, computes the observed request span from timestamped request CSVs. It stores capture-active, startup, shutdown, report-finalization, stats-export/parse, and total-lifecycle durations as **unknown**, serialized as empty CSV cells. Unknown is not zero.

For example, a saved compute-saturation seed has approximately 105.794 s of automatic profile-process wall time, 39.330 s of observed request span, and 8.992 s of summed kernel execution. These three quantities describe different intervals or accumulations. None establishes the duration of active capture. Subtracting the request span from process wall time would combine startup, shutdown, client overhead, and report finalization; it does not isolate any one phase.

Summed kernel execution is a sum of device-operation durations, not an elapsed capture clock. Concurrent kernels can overlap; idle time and capture startup are absent. A first-to-last-kernel envelope would also not establish exact capture boundaries.

The paper's 18.9–48.5% savings therefore cannot currently be interpreted as active-capture savings. The numbers can be described as historical profile-command wall-time differences under differing configured workload lengths. They also do not by themselves isolate the benefit of adaptive stopping.

All 817 local profiler files are LFS pointers. If original SQLite/report blobs are retrieved, inspect recorded capture-range metadata and its process/worker coverage. Untimestamped “capture range started/ended” console messages prove neither exact elapsed intervals nor correct GPU-worker coverage. Raw reports may help reconstruct capture intervals; they will not necessarily recover server startup or external `nsys stats` duration. Those remain unknown unless independently timestamped logs exist, or new instrumented runs are performed.

## Timing contract for the next implementation step

Record these separately using monotonic timestamps within a named clock domain. Use wall-clock timestamps only for human correlation. Do not subtract timestamps across unrelated processes without a verified common clock/mapping.

| Field | Definition | Evidence required |
|---|---|---|
| `server_startup_s` | Server process launch to verified readiness | Launcher and readiness events in the same clock domain. |
| `workload_span_s` | First scheduled/observed request to final completed/failed request, with offered-load and drain policy recorded | Request events; report outstanding/censored requests too. |
| `capture_control_window_s` | Successful start-control acknowledgement to stop-control acknowledgement | Backend control events; explicitly a control-window proxy. |
| `capture_active_s` | Union of profiler-confirmed active-capture intervals for the intended GPU workers | Profiler/backend evidence of actual boundaries and coverage. Leave unknown if only wrapper control calls exist. |
| `profile_process_wall_s` | Profile command launch to command return | Parent monotonic clock; includes nested phases. |
| `report_finalization_s` | Backend's capture/report-close event to report-ready event | Defined backend events; do not infer from process-wall residuals. |
| `stats_command_s` | Launch to return of the stats/export command | Parent monotonic clock. |
| `summary_parse_s` | Start to completion of Python summary parsing | Parent monotonic clock. |
| `diagnosis_compute_s` | Classification start to prediction produced | Actual classifier execution events. |
| `evidence_ready_at` | Timestamp when parsed evidence is available for a decision | Parse completion event; cannot precede actual availability. |
| `decision_ready_at` | Timestamp when controller emits its stop/continue decision | Controller event after evidence readiness. |
| `lifecycle_total_s` | Defined collector lifecycle start to persisted result-ready event | End-to-end monotonic boundary, with lifecycle definition recorded. |

For repeated/overlapping ranges, sum only disjoint intervals or compute their union. For the same process lifecycle, profile wall time already contains startup and finalization: adding those nested phases to profile wall time double-counts them. A full collector lifecycle may exceed profile wall time because stats extraction and parsing follow it. Keep requested burst/workload seconds alongside measured fields as configuration, never as a substitute measurement.

## Acceptance criteria for instrumented timing

- [x] CPU-only fake-backend tests prove ordering, unknown-value preservation, failed-start handling, and evidence-ready gating (step 004).
- [x] Fake collector output uses explicit timing fields and synthetic provenance (step 004); historical GPU runners remain unchanged.
- [ ] Request schedules and observation horizons match across profiling policies.
- [ ] On GPU, inspect actual kernel/worker coverage and profiler-confirmed capture boundaries.
- [ ] Report startup, active-capture, export/parse, and total-runtime costs separately, with missing phases left unknown.
- [ ] Recompute savings only between like-for-like timing quantities; do not merge replay-window cost with measured process/capture time.

Step 003 defined this contract and audited historical measurements. Step 004 implements a recorder and fake-backend readiness harness; see [its report](../progress/004_timing_events_and_fake_backend.md). The harness reports `evidence_collection_s` from attempt start to parsed evidence readiness, while leaving the full persisted `lifecycle_total_s` unknown. It does not instrument the GPU runners or claim that real capture-active time has been measured.
