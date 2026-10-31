# Study instrument and experiments

No CUDA, vLLM, NVML, Nsight, or third-party Python packages are needed for the CPU demos, tests, or passive preflight. The active NVML probe and live serving pilot require a target NVIDIA environment; CPU demos/tests remain available without it. Virtual-clock examples are synthetic; the HTTP dry run measures actual local request receipt timings with fake GPU samples and profiler evidence.

## CPU simulation versus experimental baselines

The CPU is the development/test execution environment, **not a hardware baseline** for the paper. The eventual experimental comparisons run alternative profiling strategies (fixed short/long windows, repeated bursts, SS, CR, HS) on the same GPU serving workload. CPU simulation cannot establish GPU savings, serving overhead, or diagnostic accuracy.

`HealthyBaseline` has a different meaning: it is the detector's explicit latency calibration reference (for example, healthy p95 request latency), independent of which profiling strategy is selected. In these demos it is synthetic. For real experiments it must come from a separately documented healthy calibration run; the controller does not automatically treat its first window as healthy or verify calibration validity.

## Streaming episode demo

The controller can now also be driven by raw arrivals through the adapter below.

```bash
python3 experiments/scripts/demo_streaming_controller.py --scenario stable
python3 experiments/scripts/demo_streaming_controller.py --scenario changing
python3 experiments/scripts/demo_streaming_controller.py --scenario ambiguous_first
```

Available fixtures: `healthy`, `stable`, `ambiguous_first`, `changing`, `unknown`, `timeout`. `--policy` selects one of the five distinct strategies. These exercise behavior, not a performance ranking. Outputs under `experiments/examples/streaming/<fixture>/<policy>/` include input windows, controller events, timing events, and results. They carry explicit synthetic provenance and CPU-role metadata.

`StreamingController.on_window()` accepts chronological, already aggregated cheap windows; it does not consume a completed experiment or workload truth. `tick()` services asynchronous captures, and `next_wakeup_ns()` lets a scheduler wake for stage completion, capture stop, or timeout without busy waiting. The demo delivers cheap-window arrivals before backend service at equal timestamps.

The controller keeps an incident open after tracing stops, closes it on sustained observed recovery, and suppresses recapture for unchanged suspicion. Optional reactivation requires a measured change after cooldown, or explicitly enabled unresolved-diagnosis retry. All capture rounds share the incident's original attempt cap. A new incident receives a new budget only after the previous incident has recovered. Startup/evidence timeout or end-of-stream cancellation closes pending fake-backend phases and does not publish late evidence.

Recovery consumes each cheap window once, even if multiple capture decisions share it. All intervening cheap windows are processed, so a recovery gap cannot disappear between capture decisions. Diagnosis stability consumes fresh parsed summaries separately. The shared engine is now `stopping_v3`; the new recovery identity field preserves the earlier default behavior for legacy replay calls.

These are explicit, uncalibrated controller semantics. A symptom change is a reason to seek evidence, not proof of a changed root cause. The raw-event adapter is implemented; the HTTP/sampler bridge is implemented; real GPU capture coverage/cleanup, signal calibration, and independent diagnoses remain outstanding.

## Raw request/sample streaming

```bash
python3 experiments/scripts/demo_raw_stream.py --scenario stable
python3 experiments/scripts/demo_raw_stream.py --scenario late
python3 experiments/scripts/demo_raw_stream.py --scenario late --allowed-lateness 0.5 \
  --output-dir experiments/examples/raw_stream/late_with_grace
python3 experiments/scripts/demo_raw_stream.py --scenario drain
```

Available fixtures are `stable`, `missing`, `errors`, `late`, and `drain`. The pipeline is raw start/completion/sample arrivals → `StreamingWindowAdapter` → `CheapWindow` → streaming controller → fake captures → parsed evidence → policy decisions. No completed-run aggregation or expected labels are used. All fixtures are synthetic.

`experiments/tracing/aggregation.py` provides:

- `RequestStarted`: optional admission/start observation; needed to count known outstanding requests. `require_request_starts=True` enforces matching starts for supplied completions.
- `RequestCompletion`: client-observed terminal outcome, with positive start/end lifetime, explicit arrival availability, and success/error metadata.
- `GpuSample`: a timestamped utilization reading; `None` is an unavailable reading, while zero is an observed value.
- `WindowConfig`: fixed observation origin/horizon, width, and arrival grace.
- `StreamingWindowAdapter`: receive events, call `advance()` to close due windows, and use `next_wakeup_ns()` to schedule closures even when no requests complete. The `on_window` callback feeds the controller immediately.

Definitions and boundary rules:

| Quantity/rule | Meaning |
|---|---|
| Window latency p95 | Linear-interpolated p95 of all observed completions in that window, including errors; `None` when no completions exist. |
| `throughput_rps` | Successful completions per second (goodput). Reports separately include total completed throughput and error counts. |
| GPU utilization | Arithmetic mean of actual valid samples in the window, without carrying old samples across missing windows. Irregular samples are not time-weighted. |
| Regular boundary | Windows are `[start, end)`; an event at a regular boundary goes to the next window. |
| Final boundary | The predeclared final horizon is included in the final window once, avoiding a silently lost terminal completion/sample. |
| Partial final window | Uses its actual width as the rate denominator. |
| Arrival grace | A window closes at end + allowance. Ingest all arrivals at that timestamp before calling `advance()`. |
| Late data | Recorded in the ledger, excluded from already closed control windows. Earlier producer timestamps cannot hide actual late ingestion. |
| Window availability | Actual closure/emission time, including arrival grace or delayed servicing; it is never backdated. |
| Drain | Completions after the observation horizon are counted separately and resolve tracked outstanding requests; they do not rewrite observation windows. |
| Censoring | Unfinished requests remain explicit for observed start records. Missing start records cannot establish total offered load or global censoring. |

`finish()` requires the horizon and arrival grace to have elapsed. It closes remaining windows and seals ingestion; ingest any allowed drain completions before calling it. Missing/empty windows still emit with null latency/GPU values. A failed consumer callback is logged and halts further delivery rather than silently dropping or replaying a window.

Raw request errors now trigger suspicion even if fast failures have low latency. Ages of observed pending requests can also trigger suspicion; elevated pending ages cannot establish healthy recovery. These are explicit uncalibrated rules, not verified root-cause diagnoses. The controller is version `streaming_v2`; legacy manually constructed `CheapWindow` inputs can leave the new count fields unavailable.

The adapter accepts one monotonic clock domain and is single-threaded; production callbacks must be serialized through a queue. Existing historical `time.time()` CSV timestamps must not simply be relabeled as current monotonic time. The adapter leaves the supplied healthy calibration unchanged and has no calibration/expected-label input shortcut.

Outputs under `experiments/examples/raw_stream/<fixture>/` contain window reports, aggregation events (including raw records and accepted/late/drain status), controller/timing events, and results. The audit ledger is retained in memory in this research harness; its production memory/perturbation cost has not been measured. Observed-completion p95 is not a censoring-corrected serving SLO estimate.

## Capture/readiness demo

```bash
python3 -m unittest discover -s experiments/tests -q
python3 experiments/scripts/demo_fake_profiler.py
```

The demo writes [events.jsonl](examples/fake_profiler/events.jsonl) and [results.json](examples/fake_profiler/results.json). It simulates two capture attempts and feeds their parsed summaries to the shared SS(K=2) policy only when evidence is ready. Its tiny illustrative classifier checks a synthetic GEMM name; it is not the research classifier and establishes no diagnosis accuracy.

Default simulated stages per capture:

| Quantity | Simulated seconds |
|---|---:|
| Startup | 1 |
| Capture control window | 10 |
| Report finalization | 2 |
| Profile process wall span, including startup/control/finalization | 13 |
| Stats/export command | 3 |
| Summary parse | 0.5 |
| Evidence collection, attempt start to parsed evidence ready | 16.5 |
| Capture-active interval | Unknown |
| Full persisted lifecycle | Unknown |

Startup/finalization are nested inside the profile-process span; do not add them to 13 again. The recorder exposes `evidence_collection_s` separately from `lifecycle_total_s`, because this harness does not measure complete output persistence or workload drain. Phase status distinguishes failed attempts from successful completion, even when failure costs are measured.

To exercise synthetic interval confirmation, without claiming actual GPU coverage:

```bash
python3 experiments/scripts/demo_fake_profiler.py \
  --confirm-synthetic-capture \
  --output-dir experiments/examples/fake_profiler_confirmed
```

Every event/result includes a clock domain and `synthetic_simulation` provenance. The optional interval is still synthetic. The CLI restricts output to `experiments/`, and writes to its selected example directory on reruns.

## Components

- `tracing/timing.py`: real monotonic and manual simulation clocks; scoped phases; event JSONL; capture-interval union; null measurements; failure statuses.
- `tracing/nsys_backend.py`: live single-worker Nsight/vLLM capture RPC, acknowledgement, SQLite export/readiness, UUID/PID coverage and artifact hashing; pinned hardware-pilot scope.
- `tracing/vllm_cuda_worker.py`: GPU-only vLLM 0.10.2 worker subclass issuing CUDA profiler calls in the CUDA owner.
- `tracing/command_profiler.py`: owned subprocess command lifecycle, explicit acknowledgement inputs, report/export/parse integrity checks, stage deadlines and nonblocking cleanup; CPU-contract-only.
- `tracing/profiler.py`: readiness interface and asynchronous fake startup/capture/finalization/export/parse pipeline. `poll()` never sleeps and never backdates stage completion.
- `tracing/evidence_gate.py`: single-pending-attempt harness that gates classification and policy updates on parsed evidence. Rejects future/foreign-clock evidence and duplicate consumption; failures consume budget without extending diagnosis stability.
- `tracing/policies.py`: shared five-policy stopping engine, with distinct cheap-recovery evidence identities.
- `tracing/windows.py`: immutable observed-window and healthy-calibration interfaces; no expected labels.
- `tracing/controller.py`: event-driven episodes, anomaly triggers, capture scheduling, recovery, cooldown, reactivation, and budget accounting.
- `tracing/nvml_sampler.py`: lazy optional NVML session in a spawned worker, explicit UUID/MIG contracts, async receipt audit, read failures and bounded cleanup.
- `scripts/preflight_gpu.py`: passive deployment inventory and syntax checks, with an opt-in isolated hardware probe.
- `tracing/producers.py`: actual async HTTP admission/receipt records and a serialized sampler bridge, fixed horizon, concurrency limits, skipped slots, bounded drain, and receipt ledger.
- `tracing/aggregation.py`: online raw-event windows, lateness/drop ledger, error/goodput counts, tracked pending requests, and drain accounting.
- `scripts/audit_artifacts.py`: read-only historical artifact audit. Its snapshot products are distinct from the synthetic examples.

Use `EvidenceDecisionGate.start_capture(id, start_attempt_callback)` to reserve a pending attempt before starting a backend. Advance/poll the fake backend, stop only after its capture-start acknowledgement, and call `evaluate(window_id, ...)` only when evidence is ready or the attempt has failed. An early call raises `EvidenceNotReady` without classifying or changing policy state. A failed launch/capture/classification is an explicit outcome and consumes its attempt budget; it must not be interpreted as successful evidence sufficiency.

The readiness interface is not a security boundary against a dishonest backend: a real backend must establish actual capture provenance, worker coverage, clock mapping, and report/parse readiness. The CPU pipeline handles raw-event aggregation, episode transitions, and fake cancellation/timeouts; the HTTP/sampler bridge is implemented; the optional isolated NVML adapter is implemented; the pinned L4/Nsight/vLLM serving path below is hardware-tested. Broader worker coverage, active-capture boundaries, independent classification and target-specific failure validation remain subsequent work.

See [PROGRESS.md](PROGRESS.md) and [the timing contract](audit/TIMING_AUDIT.md).

## HTTP producer dry run (no GPU)

```bash
python3 experiments/scripts/demo_http_stream.py --scenario slow
python3 experiments/scripts/demo_http_stream.py --scenario errors
python3 experiments/scripts/demo_http_stream.py --scenario missing
python3 experiments/scripts/demo_http_stream.py --scenario drain
```

The local fixture binds an ephemeral loopback port and sends actual JSON HTTP POST requests. Request starts, terminal receipts, and fake utilization samples enter `ProducerBridge`'s queue; its single consumer feeds the adapter and controller while servicing window/backend deadlines. The fixture cleans up HTTP connections and server tasks. It does not need NVML, CUDA, a serving installation, or network access beyond loopback.

`ProducerBridge(adapter, controller, ProducerConfig(endpoint, ...), payload, sampler)` is reusable with a supplied HTTP endpoint and async utilization callback returning a percentage or `None`. Use the same `MonotonicClock` object throughout. Construct `WindowConfig` with a fixed observation horizon, and supply `HealthyBaseline(p95_latency_ms, source_id)` from a separate documented healthy reference. The demo's 20 ms reference is an explicit fixture value, not an experimental calibration.

The producer bounds in-flight requests and skips admission slots when capacity or scheduler time is unavailable. Each admitted request emits one start and one terminal completion; timeout, HTTP errors, and drain cancellation remain visible. After the fixed horizon, new admissions stop. Outstanding HTTP tasks receive the configured drain interval, then cancellation. The controller finishes at the final window closure (including arrival grace); the adapter remains open for drain records until producer cleanup completes. This preserves the final window's pending count while recording later terminal outcomes separately.

The transport supports finite nonstreaming HTTP(S) responses with Content-Length or connection-close framing. Chunked/SSE responses are rejected, including any endpoint accidentally configured for token streaming. A full HTTP 2xx receipt is transport success only. Request lifetimes include client scheduling, connection setup, and response receipt; they do not measure GPU execution. Authentication, retries, TTFT/token metrics, semantic output validation, and production serving-client compatibility remain unimplemented.

Sample callbacks must be asynchronous and cancellation-cooperative. Exceptions or invalid readings become missing samples and increment a failure count. A stuck cooperative callback is cancelled at the horizon. Blocking native sampling calls need isolation before integration. The unbounded queue and retained ledgers are development instrumentation with unmeasured memory/perturbation cost; actual receipt time, including queue delay, governs late-data handling.

Outputs under `experiments/examples/http_stream/<scenario>/` include results, raw producer/receipt records, windows, aggregation, controller, and timing events. `cpu_http_dry_run` identifies the local HTTP source; separate fields identify fake GPU samples and the fake profiler, whose internal timing retains `synthetic_simulation`. The demo classifier always abstains. These fixtures establish no GPU savings or diagnostic accuracy.

Step 008 adds the optional NVML adapter and passive preflight below. Real NVML telemetry and Nsight capture validation still require NVIDIA GPU access.

## Optional NVML adapter and passive preflight

Run the inventory without GPU access or optional packages:

```bash
python3 experiments/scripts/preflight_gpu.py
```

This writes `experiments/examples/preflight/environment.json`. It discovers the platform/Python, binding/module and `nsys` path without importing NVML, initializing CUDA, launching Nsight or contacting a serving endpoint. `live_experiment_ready` remains false. Optional `--endpoint`, `--healthy-p95-ms`, and `--calibration-source` must be supplied together and validate syntax only; they do not verify healthy calibration or endpoint compatibility.

On a future NVIDIA target, install the optional `nvidia-ml-py` distribution in the experiment environment and record its exact installed version. Its module name is `pynvml`. Only the spawned worker imports it; CPU workflows remain standard-library only. A hardware probe must explicitly select a physical device UUID:

```bash
# NVIDIA hardware required; this command was NOT run during CPU development.
python3 experiments/scripts/preflight_gpu.py \
  --probe-nvml --device-uuid GPU-YOUR-EXACT-DEVICE-UUID \
  --output experiments/examples/preflight/target_gpu.json
```

A failed active probe exits with status 2 and retains an error report. A successful read reports device identity/driver/binding metadata and cleanup diagnostics but still does not establish serving-worker attribution or profiler readiness. NVIDIA's [NVML reference](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html) documents the utilization query's MIG restriction; this adapter rejects MIG UUIDs and enabled MIG mode.

`NvmlSampler(NvmlConfig(device_uuid), clock)` is an async callback compatible with `ProducerBridge`. Own it with `async with`, initialize it before constructing the observation horizon, and pass the same clock object to sampler/adapter/controller. Launch spawn-based programs under an `if __name__ == '__main__':` entry point. Persist sampler `metadata` and `events` alongside bridge records to retain device identity, failures, receipt semantics, and forced-cleanup status.

The worker makes one query per callback. Valid zero readings remain zero; errors are raised so the bridge records missing data. Startup/read/protocol failure or cancellation closes the session; a completed native query error may retry on the next poll. Native calls run outside asyncio with deadlines and termination/kill cleanup. A worker that survives cleanup is explicitly reported as a failure. Shutdown acknowledgement is separate from forced termination.

Read timestamps are parent receipts, not the device sampling interval or a process-specific activity timeline. Device utilization is shared across workloads. IPC overhead, target-driver behavior, real process cleanup and measurement perturbation remain unmeasured. See [the real profiler contract](REAL_PROFILER_CONTRACT.md) for hardware acceptance requirements and [step 008](progress/008_optional_nvml_and_deployment_preflight.md) for completed CPU checks. Step 009 adds the command/lifecycle harness below; actual telemetry/capture validation still needs NVIDIA hardware.

## Profiler command/lifecycle harness (no GPU)

```bash
python3 experiments/scripts/demo_command_profiler.py --mode ok
python3 experiments/scripts/demo_command_profiler.py --mode empty-summary
python3 experiments/scripts/demo_command_profiler.py --mode no-start-ack
```

These commands run real CPU subprocesses through `CommandProfilerBackend` and the existing controller. `fake_profiler_command.py` writes synthetic acknowledgements, a fake binary report, an export and a kernel-summary fixture. No Nsight executable, GPU package or CUDA target is involved. The demo classifier always abstains, so even the valid-report fixture reaches its six-attempt budget rather than claiming diagnostic sufficiency.

`CommandPlan` requires explicit driver/version, expected device UUID/workers, four argv tuples (`collect`, `stop`, `export`, `parse`), external-stage deadlines and artifact limits. Recognized whole-argument placeholders are `{directory}`, `{capture_id}`, `{token}`, `{device_uuid}`, and `{worker_pids}`. Commands are launched with `shell=False` in fresh attempt directories and owned POSIX sessions. Literal shell syntax remains an argv value. This harness currently supports POSIX only.

The file protocol is `capture_command_v1`. Every control/JSON artifact matches protocol, capture ID, random attempt token and fake source. `start_ack.json` and `stop_ack.json` additionally require their expected acknowledgement kind and a synthetic fixture basis. A successful stop command cannot substitute for a collector stop acknowledgement. Collector success and a valid report precede export; export must match the report hash. Parser success precedes strict kernel-summary validation, expected device/worker coverage, units and export/report hash checks. Empty evidence, unknown fields (including truth labels), wrong identities, symlinks, LFS reports and unsupported schemas are rejected. Only then can the evidence gate classify or advance the policy.

Evidence-ready timestamps reflect validated parse availability. The capture-control span covers receipt of the fixture start/stop acknowledgements; it does not establish active GPU collection. `capture_active_s`, actual serving startup and full persisted lifecycle remain unknown. Additional capture-startup/stop-command/owned-cleanup durations are available in backend snapshots without changing the timing-v1 metric schema.

Service `backend.service_cleanup()` while running, and always `await backend.aclose()` in a `finally` block. Cancellation marks evidence failed immediately, then cleans up owned command groups with TERM/KILL escalation and direct-child reaping. The controller (`streaming_v3`) waits for optional backend cleanup readiness before spending another attempt. Its observation horizon can end while process cleanup is still pending; final cleanup is a separate requirement. A surviving group causes an explicit error. Descendants that escape their owned session require additional target-specific tracking; a real persistent serving target must have separate ownership so stopping an attempt cannot terminate serving.

Outputs under `experiments/examples/command_profiler/<mode>/` include controller/timing/results records and per-attempt plans, command stdout/stderr, acknowledgements and artifacts. Everything remains `synthetic_simulation`. This first harness rejects live recorder provenance and fake protocol fields must be replaced by validated target evidence before any GPU claim. Artifact checks run synchronously within configured size bounds; logs/ledgers and process/IPC cost have not been evaluated for production overhead.

Next is the target-specific Nsight driver and its installed-version/device/worker/capture validation. **The actual hardware checks require an NVIDIA GPU.** The initial L4 checks are now recorded in step 010. While hardware is unavailable, operator evidence reports, protocol/manifests, sensitivity tooling, and paper revision remain possible CPU tasks. See [step 009](progress/009_profiler_command_lifecycle_harness.md).

## Real L4 serving integration and engineering pilot

The first hardware path is validated on one NVIDIA L4 with Nsight Systems 2026.3.1.0, vLLM 0.10.2, torch 2.8.0+cu128 and Transformers 4.55.2. Exact packages/source fingerprints are in `experiments/hardware/l4_20261027/`. The model is Qwen2.5-7B-Instruct at revision `a09a35458c702b33eeacc393d103063234e8bc28`; weights are outside the artifact tree in the rental's RAM-backed cache. Raw reports are copied back locally. See [step 010](progress/010_l4_hardware_capture_integration.md).

`serve_vllm_cuda.py` registers vLLM's gated profile routes during API import, then removes the Torch profiler setting before engine creation. `CudaCaptureWorker.profile()` executes actual `cudaProfilerStart`/`cudaProfilerStop` calls and writes UUID/PID/clock acknowledgements. The backend additionally requires the Nsight collection-start callback, then uses synchronous per-range flush and successful export/parse for readiness. No simultaneous Torch/Kineto trace is collected. The successful serving smoke continued accepting/completing requests after live evidence decisions.

The tested range mode is `repeat:120:sync`; it pauses the CUDA worker to finalize a report. That pause is part of observed RPC/control/evidence latency, not free collection. The earlier async/deferred attempt failed to satisfy report readiness before its horizon and remains in the failure artifacts. CPU perf sampling is disabled in this unprivileged container; CUDA activity tracing works. No host driver, kernel settings or management services were changed.

For the pinned target only, the foreground runner can be invoked as follows (the rental uses supervisor to own it):

```bash
/workspace/envs/vllm/bin/python experiments/scripts/run_l4_pilot.py \
  --output experiments/hardware/l4_20261027/pilot_new \
  --device-uuid GPU-YOUR-DEVICE-UUID \
  --model-path /path/to/pinned/local/Qwen2.5-7B-Instruct \
  --healthy-controls
```

The output directory must be new. The runner starts one owned persistent Nsight/vLLM session on `127.0.0.1:8010`, verifies a single worker/device, warms up, freezes a separate calibration reference, then streams HTTP requests and real NVML samples into the controller. It retains source hashes, package freeze, configuration, randomized order, admissions/skips/drain, raw observations, capture RPCs, reports/exports and decisions. Final cleanup stops its own serving session. The rental remains a separate resource; destroying/recycling it or losing its RAM filesystem removes the model cache.

This first matrix is engineering validation: five policies × three repetition labels and three healthy controls. It uses 24 s horizons, 2 s windows, a 1 s requested capture span, a three-attempt cap, and prospectively disabled reactivation (`streaming_v4`). Deployment defaults retain changed-evidence reactivation. The classifier intentionally abstains pending independent T2 calibration, so unknown labels cannot satisfy SS/HS. Fixed-budget completion is separate from diagnosis sufficiency. Shared server/cache state and greedy decoding do not establish independent statistical repetitions, and in-flight limits can skip nominal arrivals. Do not treat these data as an equal-realized-workload quality comparison.

After copying the complete output locally, audit it with:

```bash
python3 experiments/scripts/analyze_l4_pilot.py \
  --run-dir experiments/hardware/l4_20261027/pilot_002
```

Analysis writes `analysis/run_metrics.csv`, `validity_checks.json` and `PILOT_REPORT.md`, checking evidence-before-decision, continued serving, measured kernel coverage, immutable report/database hashes and source fingerprints. Capture-active time, diagnosis accuracy and stopping-safety/savings remain unestablished. Pure server startup, per-range finalization and full persisted lifecycle are not inferred from unrelated timing spans. See [step 011](progress/011_l4_live_engineering_pilot.md) for the live matrix status and remaining research work.

The live runner creates and closes a separate NVML sampler per episode; cancellation at a horizon must not carry a closed sampler into the next episode. Runs with sampler errors or missing GPU windows fail the engineering gate. `pilot_001` is retained as telemetry-incomplete; `pilot_002` repeats the matrix after the ownership fix. The analyzer verifies telemetry coverage and the exact executed-source archive.

## Prepare the next experiment protocol on CPU (step 012)

Read [the draft protocol](protocol/L4_EXPERIMENT_PROTOCOL.md) for independent reference rules, calibration/held-out separation, six workload cases, controls, timing/outcome definitions, sensitivity and the freeze checklist. The [configuration](configs/l4_protocol_draft.json) contains provisional parameters, not fitted thresholds or a runnable GPU matrix.

From the repository root, compile into a **new** directory:

```bash
python3 -m experiments.scripts.prepare_protocol --output experiments/protocol/my_draft_design
```

The compiler never connects to a GPU or launches experiments. It validates splits, phases, arms and budgets, then emits controller jobs, a separate evaluator/driver intervention schedule, a planning summary and source/configuration fingerprints. The checked-in [draft design](protocol/draft_design_v1/planning_summary.json) contains 144 proposed development runs (4.8 observation hours; up to 6.6 hours including drain, excluding other costs). It generates no confirmation runs and cannot certify a frozen protocol. Workload metadata must also be kept outside actual classifier inputs by the future typed adapter.

Step 013 implements measured-evidence/reference interfaces; step 014 adds response-usage/queue-gauge collection and temporal joins; step 015 adds exact offered-arrival playback/accounting, and step 016 adds owned CPU arm lifecycles and independent reset checks; next is durable reference locking/scoring (017). Actual capacity, metric availability, references, classifier calibration and phase/reset feasibility still require GPU collection. See [step 012](progress/012_cpu_experiment_protocol.md).

## Measured features and evaluator reference contracts (step 013)

The [contract guide](protocol/MEASURED_EVIDENCE_CONTRACT.md) documents immutable measured observations, strict JSON fields, availability/clock checks, missing/partial/complete acquisition coverage, and separate evaluator references with linked artifact identities and declared lock ordering. The new classifier adapter accepts only measured observations and always abstains until calibration/mapping are implemented. This does not yet replace the live runner's kernel-summary callback.

Run a synthetic example into a new directory:

```bash
python3 -m experiments.scripts.demo_measured_evidence --output /tmp/my_measured_evidence_demo
python3 -m unittest experiments.tests.test_measured_contracts -v
```

The [saved prediction](examples/measured_contract_demo/prediction.json) is null even though the fixture has complete inputs and a separately declared synthetic reference. No reference is passed into classification. Actual collectors, live interval joins, calibration, durable reference locking and scoring remain pending. See [step 013](progress/013_measured_features_and_reference_contracts.md) and the step-014 collection implementation below.

## Response/server feature collection and temporal joining (step 014)

[The collection guide](protocol/FEATURE_COLLECTION.md) covers bounded HTTP response usage, an explicitly configured exact queue-gauge series, sparse/partial/missing features, raw receipt/closure audits and joining parsed evidence to its original acquisition interval. Wait p95/prefill fraction remain unsupported; classification still abstains and the old GPU runner is unchanged.

```bash
python3 -m experiments.scripts.demo_feature_bridge --output /tmp/my_feature_bridge_demo
python3 -m unittest experiments.tests.test_feature_collectors -v
```

The output directory must be new. Five [saved fixture scenarios](examples/feature_bridge_demo/complete.json) use real loopback HTTP with synthetic server/GPU/kernel values and delayed fake-profiler parsing. They validate mechanics, not diagnosis quality, workload effects or GPU costs. See [step 014](progress/014_feature_collectors_and_temporal_bridge.md). Step 015 adds exact offered-arrival playback and admission/timeout/drain/censoring accounting; step 016 adds distinct owned CPU arm lifecycles and independent quiet/reset checks; step 017 adds durable reference locking/scoring; step 018 implements interval/export contracts; step 019 binds collection/persistence/export; step 020 adds feasibility gates/read-only discovery; next is L4 capability discovery (021), still without a GPU.

## Exact offered requests and bounded playback (step 015)

[The workload driver guide](protocol/OFFERED_WORKLOAD_PLAYBACK.md) specifies immutable saved request schedules, file/content hashes, admission tolerance/skips, actual completions, pending-state reconstruction, timeouts, drain censoring, bounded terminal/telemetry queues and explicit coverage flags. It preserves equal offered files without assuming equal realized work. This is not yet the experimental arm/session runner.

```bash
python3 -m experiments.scripts.demo_schedule_playback --output /tmp/my_schedule_playback_demo
python3 -m unittest experiments.tests.test_schedule_playback -v
```

The output directory must be new. Six saved [fixture runs](examples/schedule_playback_demo/normal.json) reuse one [offered file](examples/schedule_playback_demo/offered_arrivals.json); source hashes, raw receipts, per-ID outcomes, windows and unknown predictions are saved. `python3 -m experiments.scripts.play_arrivals --help` documents playback against an existing HTTP endpoint. Local request cleanup does not prove server/GPU quiescence. See [step 015](progress/015_exact_offered_arrival_playback.md); step 016 implements CPU arm/reset lifecycles; step 017 adds durable reference locking/scoring; step 018 implements interval/export contracts; step 019 binds collection/persistence/export; step 020 adds feasibility gates/read-only discovery; next is L4 capability discovery (021), without GPU use.

## Distinct arm/session lifecycles and quiet/reset gates (step 016)

[The lifecycle guide](protocol/EXPERIMENT_ARM_LIFECYCLE.md) documents eight validated arm plans, fresh owned target processes/samplers, capture-disabled controls, bounded policy/reference capture, repeated server quiet checks, token/generation reset acknowledgements and cancellation-safe TERM/KILL/reaping. Client task cleanup never substitutes for server work clearance. This adapter accepts only the bundled CPU fake target; actual GPU/worker/cache reset validation remains pending.

```bash
python3 -m experiments.scripts.demo_arm_lifecycles --output /tmp/my_cpu_arm_lifecycles
python3 -m unittest experiments.tests.test_arm_lifecycles -v
```

Use a new output directory. The [saved report](examples/arm_lifecycle_demo/REPORT.md) covers eight fresh target instances, seven closed sampler sessions, 14 synthetic reports and four retained injected failures. Source/report hashes and server/reset/cleanup evidence are retained. No GPU costs or diagnosis effectiveness are established. See [step 016](progress/016_arm_lifecycles_and_reset_quiescence.md); step 017 adds durable evaluator reference storage and offline scoring; step 018 implements interval/export contracts; step 019 binds collection/persistence/export; step 020 adds feasibility gates/read-only discovery; next is L4 capability discovery (021), CPU-only.

## Locked references and offline scoring (step 017)

[The scoring guide](protocol/LOCKED_REFERENCE_SCORING.md) describes separate reference locking and prediction reading, verified content-addressed snapshots, retained external digest anchors, interval joins and complete logged-activation denominators. It distinguishes complete/partial/unsupported/unresolved/unavailable diagnoses and retains failure/budget/censoring statuses.

```bash
python3 -m experiments.scripts.demo_reference_scoring --output /tmp/my_reference_scoring_demo
python3 -m experiments.scripts.reference_eval --help
python3 -m unittest experiments.tests.test_locked_reference_scoring -v
```

Use a new output directory. The [saved report](examples/reference_scoring_demo/REPORT.md) contains 12 hand-authored synthetic stops, not deployed classifier results. Hashes cannot establish human blinding or causal truth. The CLI accepts synthetic clocks only; actual run clock binding and initial-stop export remain pending. See [step 017](progress/017_locked_references_and_offline_scoring.md). Step 018 implements these contracts; step 019 binds collection/persistence/export; step 020 adds feasibility gates/read-only discovery; next is L4 capability discovery (021); GPU calibration is still required later.

## Interval metric adapters and initial-stop export (step 018)

[The guide](protocol/INTERVAL_METRICS_AND_EXPORT.md) covers typed admission-cohort wait histograms, explicit phase counters or unavailability, exact-window matching and export from finalized controller snapshots. The v2 scorer preserves absent acquisition rather than inventing failure intervals. First stops survive reactivation; no cause mapping is inferred.

```bash
python3 -m experiments.scripts.demo_interval_export --output /tmp/my_interval_export_demo
python3 -m experiments.scripts.export_initial_stops --help
python3 -m unittest experiments.tests.test_interval_metrics_and_export -v
```

[Saved fixtures](examples/interval_export_demo/SUMMARY.json) cover eight CPU controller cases and seven initial stops. These adapters still need collection-source and arm-runner binding; actual server metric support and GPU phase instrumentation remain unvalidated. See [step 018](progress/018_interval_metrics_and_controller_export.md). Step 019 implements CPU collection/persistence/export; step 020 adds feasibility gates/read-only discovery; next is L4 capability discovery (021), then hardware feasibility and calibration.

## CPU source collection and automatic arm exports (step 019)

[The guide](protocol/ARM_COLLECTION_AND_EXPORT.md) covers actual admission waits in an owned CPU source, checked same-host acquisition/receipt binding, bounded interval queues, late/missing/reset outcomes and persisted observations/initial stops. Cheap and capture scopes remain separate, and the classifier abstains. The unprofiled arm does not record additional interval history.

```bash
python3 -m experiments.scripts.demo_arm_collection_export --output /tmp/my_arm_collection_demo
python3 -m experiments.scripts.snapshot_server_metrics --help
python3 -m unittest experiments.tests.test_arm_collection_export -v
```

[Saved report](examples/arm_collection_export_demo/REPORT.md): eight CPU arms and six source fault cases, with raw/source/artifact hashes and owned cleanup. The passive probe saves endpoint bytes/type hints without establishing live metric semantics. See [step 019](progress/019_arm_collection_persistence_and_export.md). Step 020 prepares feasibility gates/read-only discovery; next is actual L4 capability discovery (021), before owned activity validation, calibration or protocol freeze.

## Pinned-stack feasibility gates and read-only discovery (step 020)

[The guide](protocol/LIVE_FEASIBILITY.md) documents exact-model/engine metric inspection, the finished-request cohort mismatch, ordered inventory/metric/quiet-reset/capture/cleanup gates and a read-only local-server adapter. Discovery cannot pass unavailable owned activity gates or enable the main matrix.

```bash
python3 -m experiments.scripts.demo_live_feasibility --output /tmp/my_feasibility_gate_demo
python3 -m experiments.scripts.live_feasibility --help
python3 -m unittest experiments.tests.test_live_feasibility -v
```

[Saved report](examples/live_feasibility_demo/REPORT.md): eight explicitly synthetic cases; even positive mechanics keep live feasibility/study readiness false. See [step 020](progress/020_live_feasibility_harness_and_capability_gates.md). Step 021 completes fresh L4 discovery; step 022 adds a separately owned worker/reset/capture adapter and passes one bounded corrected invocation. See the activity section below; the read-only adapter remains discovery-only.

## Live L4 capability discovery (step 021)

[The hardware report](hardware/l4_20261028/REPORT.md) records fresh pinned-stack discovery and two short successful serving probes. Histogram counts advanced 0→1→2, consistent with the reviewed finished-request cohort. This does not validate admission-window waits, phase attribution, calibration or diagnosis. Quiet/reset remains unavailable and no capture/main matrix was run.

Raw metric/request bytes, model/source fingerprints, exact deployed archive and cleanup checks are backed up locally. The owned server/worker are absent and GPU memory returned to 0 MiB; the rental itself remains running. See [step 021](progress/021_l4_live_capability_discovery.md) for that discovery snapshot; subsequent activity is recorded separately below.

## Owned live activity (step 022)

[The contract](protocol/OWNED_LIVE_ACTIVITY.md) describes fixed worker-barrier RPCs, fresh token/session/generation acknowledgements, repeated zero-gauge observations, verified restart, one-attempt capture readiness and cleanup. [The hardware report](hardware/l4_20261028/ACTIVITY_REPORT.md) preserves an initial callback-path timeout and a separate corrected invocation passing all five gates: one validated capture/5,992 kernels, two successful requests and all owned processes removed. Serving is stopped; the rental remains running.

All 399 CPU tests pass. Artifacts and both source snapshots are backed up and audited. This is feasibility, with classifier, active-capture measurement, study/calibration and protocol freeze still unavailable. See [step 022](progress/022_owned_worker_reset_and_capture_feasibility.md). Step 023 subsequently implements mapping/preparation on CPU; see below for current next steps.

## Live metric/window mapping and calibration preparation (step 023)

[The mapping contract](protocol/LIVE_FEATURE_MAPPING.md) connects session-bound raw endpoint receipts to measured queue windows, actual client usage and GPU samples. Histograms remain diagnostic sidecars; unsupported wait/phase fields remain null. Raw receipts, observations and audits persist with hashes. The classifier bridge checks worker/device/provenance and continues to abstain.

[Saved checks](examples/live_feature_mapping/REPORT.md): all 427 CPU tests pass; 12 prior L4 receipts map offline, without new windows or online decisions. The independent calibration preparation packet lists 18 planned collection jobs, zero observed calibration windows and explicit blockers; launch/fitting/calibration/freeze remain false. No new GPU activity is launched. See [step 023](progress/023_live_feature_mapping_and_calibration_preparation.md). Step 024 subsequently validates the bounded throughput/corpus pilot described below.

## Bounded L4 throughput/corpus pilot (step 024)

[Protocol and invocation](protocol/CAPACITY_AND_CORPUS_PILOT.md), [hardware report](hardware/l4_20261028/CAPACITY_REPORT.md), [step report](progress/024_bounded_capacity_and_corpus_pilot.md). The supervised two-worker pilot completes six eight-second cells, 68 probe requests plus two warmups, and six persisted live windows/96 raw metric receipts with zero errors. Actual prompt tokenization is 17/1,072 tokens; every response reports the matching input count and 32 output tokens. Four paired jobs share exact offered bytes but remain unexecuted.

All 439 CPU tests pass (12 new), with 379 artifact hashes and 70 source fingerprints verified after local backup. Increasing rates through concurrency 4 and repeated cached prompts do not establish saturation capacity or diagnostic outcomes. Owned jobs are stopped, GPU memory is 0 MiB and the rental remains running. Step 025 subsequently passes that paired pilot and assembles an assessment packet, as described below. Calibration/freeze remain pending.

## Owned paired L4 collection (step 025)

[Protocol/invocation](protocol/PAIRED_LIVE_COLLECTION.md), [hardware report](hardware/l4_20261028/PAIRS_REPORT.md), [step report](progress/025_owned_paired_collection_and_assessment_packet.md). Four fresh-server jobs replay identical offered files within each pair. All eight scheduled requests and four warmups succeed; sixteen measured windows retain 64 raw metrics. The two full traces parse with 21,308 and 23,044 kernels on their expected workers/GPU. Active capture duration stays unknown, and classifier/policies are not run.

The ten-artifact packet awaits assessment and records matched-run differences; zero references are created/locked. All 451 CPU tests pass, with 472 artifact hashes/360 archived source entries verified. All owned workers are absent and GPU memory is 0 MiB; the rental remains running. Step 026 subsequently implements that retrospective gap assessment and draft rubric, as described below. Actual assessment still precedes reference locking and fitting.

## Evidence-gap assessment and draft scope (step 026)

[Instructions](protocol/EVIDENCE_ASSESSMENT.md), [saved audit/rubric/blank worksheet](examples/evidence_assessment/REPORT.md), [step report](progress/026_evidence_assessment_rubric_and_scope.md). All 472 source artifacts verify; the offline audit recomputes raw request-ID differences, inspects 64 raw queue receipts and reparses both traces. Every sampled queue is zero and every latency p95 window is unavailable. Two requests per role and no prospective mismatch tolerances cannot establish equivalence or reference validity.

The rubric proposes queue-pressure-only scope and leaves numerical coverage/mismatch/precision limits unset; prefill diagnosis is deferred. Gap-review validation binds audit/rubric hashes and accepts only unresolved/needs-more-evidence outcomes. It creates no reference or lock and does not authenticate assessor identity/blinding. The saved worksheet is blank, the classifier unchanged, and all 467 CPU tests pass (16 new). No GPU activity or rental-state change occurs. Step 027 subsequently prepares that instrumentation and engineering plan, described below.

## Scheduler hooks and prospective instrumentation pilot (step 027)

[Operating contract](protocol/SERVER_EVENT_INSTRUMENTATION.md), [source fingerprints](protocol/sources/vllm_0_10_2/events/SOURCE_MANIFEST.json), [saved CPU fixtures/plan](examples/server_events/REPORT.md), [step report](progress/027_scheduler_events_and_prospective_pilot_rules.md). The opt-in pinned scheduler subclass records engine admission, first positive CPU scheduling and terminal brackets. Bounded history/drop accounting and parent-bracketed nonce/generation/PID/UUID probes reject incomplete or foreign evidence. Delay bounds retain ambiguous windows and unscheduled/aborted requests; no GPU execution, client delivery or phase attribution is inferred.

All 484 CPU tests pass at step 027 (17 new). Five demos remain synthetic; that source-retrieval step launches no GPU workload or package/service change. Existing measured wait/phase fields and the classifier remain unchanged. The prospective specification sets engineering-only budgets/guards and bounded rate/removal/lull/unresolved templates; launch/fitting/reference export/freeze remain false. Subsequent live commissioning is recorded below.

## Owned scheduler-event commissioning (step 028)

[Hardware report](hardware/l4_20261028/EVENTS_REPORT.md), [raw receipts](hardware/l4_20261028/events_001/RESULT.json), [backup audit](hardware/l4_20261028/EVENTS_VALIDATION.json), [step report](progress/028_owned_scheduler_event_commissioning.md). One fresh supervisor-owned L4 server completes eight sequential requests with 24 complete lifecycle events and exact client/engine ID joins. Two fixed idle RPC probes need no additional inference requests. Worker/scheduler PID, UUID, nonce, generation and clock agree; actual prefix caching is disabled. Four quiet barriers and final independent process/group/GPU checks pass.

All 494 CPU tests pass (ten added). Local backup verifies 46 artifact hashes, 142 frozen archive entries, 81 runtime source entries and eight installed ID/CLI pins. Owned serving is stopped and GPU memory is 0 MiB; the rental remains running. This validates the restricted nonstreaming single-prompt/single-choice collector path only. No challenges, references, calibration or new captures are executed; host first-scheduling bounds do not become GPU timing or the existing wait/phase metrics.

Step 029 subsequently prepares exact offered files and controls, described below. Scientific limits and main-study freeze remain pending.

## Exact event challenges and observer controls (step 029)

[Protocol](protocol/EVENT_CHALLENGE_PROTOCOL.md), [prepared packet](examples/event_challenges/prepared_001/PLAN.json), [CPU fixture report](examples/event_challenges/REPORT.md), [step report](progress/029_exact_challenges_and_observer_controls.md). Sixteen exact schedules cover the rate ladder and five candidate rates for each dependent removal/lull/evidence-gap case. The first collector-off ladder selects the lowest qualifying sampled queue rate only after exact work and receipt-coverage checks. No candidate or incomplete evidence stops dependent cases. Two reversed-order blocks share cache-off settings and wire payloads; explicit cache policy is now independent of hooks.

All 511 CPU tests pass at step 029 (17 new); forty-two packet/fixture hashes verify. Six synthetic cases and a consumer-only evidence-withholding gate demonstrate selection rejection and unresolved missing evidence without changing raw receipts or the classifier. That step uses no SSH/GPU/rental change. Subsequent runner implementation is recorded below.

## Owned concurrent challenge runner (step 030)

[Execution contract](protocol/CHALLENGE_EXECUTION.md), [CPU artifacts](examples/challenge_runner/REPORT.md), [engineering snapshot](examples/challenge_runner/snapshot_001/FREEZE.json), [step report](progress/030_owned_concurrent_challenge_runner.md). The owned runner adds fixed actual-worker configuration receipts, exact concurrent HTTP work/raw queue collection, asynchronous probe offsets, decision-time consumer withholding, warmup-inclusive final source joins and matched-cohort latency review. Request/session/campaign charges, no-pressure skips, fail-stop handling, cancellation/drain accounting and verified owned cleanup are explicit.

All 531 CPU tests pass at step 030 (twenty new). Three saved episodes remain synthetic; 91 fixture artifact hashes and 171 archived source/input entries verify, with twelve installed vLLM pins. That implementation step retrieves worker source read-only and runs no GPU workload. Subsequent live execution is recorded below. Classifier/calibration/reference/main-study freeze remain unavailable.

## Frozen L4 campaign attempt (step 031)

[Hardware report](hardware/l4_20261028/CHALLENGES_REPORT.md), [raw failure](hardware/l4_20261028/challenges_001/RESULT.json), [independent audit](hardware/l4_20261028/CHALLENGES_VALIDATION.json), [descriptive phase analysis](hardware/l4_20261028/CHALLENGES_FAILURE_ANALYSIS.json), [step report](progress/031_frozen_l4_campaign_and_capacity_failure.md). The campaign stops on its first collector-off ladder: all ninety admitted arrivals plus the warmup succeed, but the fixed 32-client cap skips thirty-four of 124 offers in the 8 requests/s phase. No rate is selected, no retry occurs and fifteen later jobs remain uncompleted. Real queue receipts show sampled backlog, including nine positive samples in the completely delivered 4 requests/s phase; this does not retrospectively make that rate eligible under the frozen rule.

The actual cache-off configuration RPC, 120 raw queue receipts, exact raw IDs/tokens and owned cleanup verify. Independent backup audit checks 362 artifact hashes, 171 frozen entries and ninety runtime source entries; parent/worker/group are absent and GPU memory is 0 MiB at that check. The rental remains running at step 031. No collector-on comparison, source under load, diagnostic reference, calibration or new capture is produced. Subsequent v2 preparation is recorded below; the failed attempt and original artifacts are preserved.

## Development-informed v2 protocol (step 032)

[Protocol](protocol/EVENT_CHALLENGE_PROTOCOL_V2.md), [packet](examples/event_challenges_v2/prepared_001/PLAN.json), [engineering snapshot](examples/event_challenges_v2/snapshot_001/FREEZE.json), [CPU audit](examples/event_challenges_v2/validation/AUDIT.json), [step report](progress/032_development_informed_v2_protocol.md). A separate 0.5/1/2/3/4 requests/s ladder offers 84 requests plus warmup; exact rational offsets preserve counts at 3 requests/s. The sixteen-job worst case is 1,932 attempts. Client/server/journal/time/completeness/coverage limits are unchanged. Strict v1/v2 loaders/selectors and frozen version tags prevent reinterpretation of the failed run.

All 549 CPU tests pass (eighteen new). Two earlier CPU timing fixtures were given more observation time; initial failure/isolated logs remain preserved and GPU guards are untouched. Six saved cases remain synthetic. The new archive verifies 184 entries, 25 packet/nineteen fixture hashes and all original failed/archive data unchanged. No SSH or GPU workload occurs in step 032. Subsequent fresh validation is recorded below; the new ceiling itself does not establish complete delivery or scientific validity.

## Fresh v2 L4 validation (step 033)

[Live report](hardware/l4_20261028/CHALLENGES_V2_REPORT.md), [summary](hardware/l4_20261028/CHALLENGES_V2_SUMMARY.json), [audit](hardware/l4_20261028/CHALLENGES_V2_VALIDATION.json), [step report](progress/033_fresh_v2_l4_validation.md). The unchanged engineering snapshot passes all sixteen fresh L4 jobs: 1,536 scheduled offers and sixteen warmups complete, with zero skips/errors/censors. The first-off rule selects 3 requests/s. There are 1,920 queue receipts, ninety source probes and 2,904 final-history events. All six deliberately withheld consumer windows remain unresolved. No paired review flag fires among 22 evaluable windows; statistical equivalence and diagnostic accuracy remain unestablished.

The off-host backup verifies 6,142 artifact hashes, 184 frozen entries, model/installed pins and 64 unique quiet barriers. Independent cleanup confirms all sixteen owned process groups absent and 0 MiB; the rental remains running. A persistence defect remains explicit: later quiet-evidence files include 480 historical duplicate rows with original-job-relative filenames. The whole campaign resolves and verifies them using original session provenance; individual later jobs are not self-contained for those rows. Next step 034 isolates per-job persistence and adds a multi-job regression/provenance index on CPU. Frozen results/source stay unchanged; no GPU is needed for that fix.


## Quiet-evidence isolation and historical provenance (step 034)

[Report](examples/quiet_evidence_isolation/REPORT.md), [step report](progress/034_quiet_evidence_isolation_and_provenance.md), [immutable live-data index](hardware/l4_20261028/challenges_v2_quiet_provenance_034/INDEX.json). Working quiet logs are now scoped by resolved output directory. Different jobs may reuse filenames safely; deliberate reset generations within one episode remain available. Existing logs, duplicate raw filenames and invalid destinations/labels fail before overwrite or RPC.

All 565 CPU tests pass (sixteen new), with 33 focused checks. The multi-job regression reproduces the original eight-versus-four-row bug in archived source. The separate historical index verifies 6,142 result hashes and resolves 544 rows to 64 originals/480 historical copies without changing saved data. The step-033 audit reproduces its existing report exactly, and both snapshots/backups and the failed v1 artifacts remain unchanged. The current source correctly fails the old freeze; no new engineering archive or live-validation claim is created. Step 034 uses no SSH/GPU. Next step 035 audits scheduler-bound precision/cohort semantics and scientific feature/reference criteria offline; no GPU is needed.

## Scheduler-bound precision and cohort audit (step 035)

[Report](examples/scheduler_bound_audit/REPORT.md), [assessment plan](protocol/SCHEDULER_BOUND_ASSESSMENT.md), [summary](hardware/l4_20261028/scheduler_bounds_035/SUMMARY.json), [step report](progress/035_scheduler_bound_precision_and_cohort_audit.md). The offline audit verifies 6,142 unchanged artifacts, ninety probes and 958 source case lifecycles. All 96 recorded gates reproduce; 798 observations remain consumer-accepted and 160 withheld observations stay offline-only. Scheduling differs from admission/completion cohorts in 40/60 and 52/60 source windows. Thirty-two source cohorts are below twenty requests and eight are empty. Bound-width median/sample p95/max are 0.2362/0.3252/0.7692 ms; scientific acceptance remains unset.

All 579 CPU tests pass (fourteen new); two older CPU timing fixtures gain observation margin with initial failures retained and GPU guards untouched. Original live results, archives/backups and prior audits are preserved. The existing wait metric and GPU phase fields remain unsupported by these host hooks. No SSH/GPU, labels, classifier activation or calibration occurs. Next step 036 prepares a criterion-completion/validation contract and evaluator-only assessment worksheet on CPU; actual scientific decisions and assessor entries remain pending.

## Scientific criteria and evaluator worksheet (step 036)

[Report](examples/scheduler_assessment/REPORT.md), [instructions](protocol/SCHEDULER_ASSESSMENT_WORKFLOW.md), [actual blank criteria](hardware/l4_20261028/scheduler_assessment_036/CRITERIA.json), [worksheet](hardware/l4_20261028/scheduler_assessment_036/REVIEW_TEMPLATE.json), [step report](progress/036_scientific_criteria_and_assessment_workflow.md). The packet verifies 6,142 campaign artifacts and three audit files, then provides 96 cases/3,932 typed artifact records with conservative post-job availability. It discloses workload/policy metadata and makes no blinding claim. Fourteen scientific choices and assessor judgments remain blank; missing criteria, wrong-scope links, feature/reference reuse and supported/healthy labels cannot bypass the gap-review gate.

All 34 focused tests pass (eighteen new), and all new tests pass in both full runs. Broad clearance is unresolved: the 597-test retry has twelve failures/two errors in older timing tests under heavy host load; the first six affected checks pass in isolation. Existing source/deadlines remain unchanged and all failure logs are retained. No references, locks, calibration, SSH/GPU work or new snapshot occurs. Next step 037 prepares justified criteria and a prospective confirmation proposal on CPU; obtain a clean broad regression before a new engineering freeze.
