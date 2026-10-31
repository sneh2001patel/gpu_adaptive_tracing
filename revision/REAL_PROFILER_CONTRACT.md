# Real profiler integration contract (single-worker L4 path validated)

This is the acceptance contract for replacing `FakeProfilerBackend` with validated GPU collection. Step 009 implements a CPU command/lifecycle harness; step 010 adds the first hardware-tested single-worker L4/Nsight/vLLM path. Broader target support and research validation remain pending. CPU tests and a successful NVML read cannot establish CUDA tracing or diagnostic correctness.

## Deployment and device identity

1. Record the exact code revision/dirty-tree state, configuration, Python/binding/driver/Nsight versions, serving command, model revision, device UUIDs, and serving worker PIDs. Set the observation horizon and admission schedule before observation begins.
2. Supply a separately documented healthy calibration with raw requests, matching model/device/load conditions, and its source ID. Preflight validates syntax only; it cannot establish healthy behavior or hold-out independence.
3. Verify the physical GPU UUID against every CUDA-serving worker, including child processes. NVML device indices and CUDA ordinals are not assumed equivalent. `CUDA_VISIBLE_DEVICES` is recorded as context, not proof of mapping. One physical-device-wide utilization reading does not attribute load to a process; unrelated GPU activity remains a confounder.
4. This first telemetry adapter accepts physical `GPU-...` UUIDs only, checks the returned UUID, and rejects MIG-enabled devices. Unsupported queries produce errors/missing readings, never zero. Support for MIG or distributed/multi-GPU aggregation requires a separate design and validation.

The optional Python binding is distributed as `nvidia-ml-py` and imported as `pynvml`. See the [binding's publisher documentation](https://pypi.org/project/nvidia-ml-py/). NVIDIA documents device UUID queries and the MIG restriction for utilization in the [NVML device-query reference](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html). Consulted 2026-10-27.

## Profiler ownership and capture acknowledgement

1. Choose and demonstrate a supported launch/session mechanism for the installed Nsight version. Do not assume that launching `nsys` later can trace arbitrary already-running CUDA workers. An initial design may launch the server under a profiler-controlled session before admitting requests, then control capture ranges while serving continues.
2. Preserve the same serving/request observation horizon across policies. Stopping a capture must not terminate/restart the server or truncate the load stream. Document collection control and target-process lifetime separately. NVIDIA describes interactive sessions and target termination behavior in the [Nsight Systems user guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html); installed-version CLI help and a hardware smoke test must establish the actual commands. The pinned step-010 implementation records its actual launch command and uses CUDA-worker APIs with synchronous per-range report flushing.
3. Implement `start`, `poll`, `stop`, `cancel`, `next_deadline_ns`, and `evidence` behind the existing backend interface. Each attempt gets unique capture/evidence IDs and a unique output directory. Reserve the attempt budget before launch, including failed launches.
4. Report `capturing` only after a target-side acknowledgement or demonstrated profiler/session event establishes capture start. A process spawning, a timer expiring, or report-file creation is insufficient. Bound startup, stop, finalization, export and parse phases; each failure is explicit and charged.
5. Establish coverage for each relevant process, CUDA context and device, using controlled test kernels/markers and the captured report. A kernel observed in one worker does not establish all-worker coverage. Coverage gaps make the result unresolved/limited and are retained in the operator evidence.

## Clock and cost contract

- The controller's monotonic domain times command requests, acknowledgements, parsed evidence arrival, decisions and queue receipts. Device/profiler timestamps remain in their own domains until an explicit mapping with uncertainty is demonstrated. Never subtract unrelated timestamps.
- Keep server startup, target initialization, capture-control span, profiler-process wall time, report finalization, stats/export, parse, diagnosis, workload/drain and total persisted lifecycle distinct. Overlapping spans are not additive.
- Active capture is the union of established capture intervals in a valid clock domain. A requested burst duration, process wall span, first/last kernel envelope or NVML utilization percentage is not a capture-active measurement. Leave active time null when boundaries are unavailable.
- NVML read timestamps mark parent receipt of a completed query. The device's averaging interval is unknown here, so repeated polls are not independent instantaneous GPU measurements. Retain request/receipt audit timestamps and sampling errors; quantify polling/IPC/controller perturbation later on the target system.

## Evidence readiness and integrity

1. A stop acknowledgement ends collection only. Wait for the report writer to finish successfully, verify that the report is a real readable artifact (not an LFS pointer), and complete a version-compatible stats/export command and parser before declaring evidence ready.
2. Validate the summary schema, units, worker/device provenance, capture identity, and coverage. Hash produced artifacts and retain their paths and command return codes. Empty captures, unsupported schemas, parse failures and missing coverage are explicit unresolved outcomes; they do not inherit the previous label.
3. Timestamp `evidence_ready` when the validated parsed summary is available to the controller. Never backdate it to capture end. Keep evaluator-only expected labels outside parser/classifier inputs.
4. Feed each new evidence ID to the shared policy once. Cached summaries cannot extend stability. Stable labels establish repeatability only; independent references determine whether the explanation is correct.

## Cleanup and failure contract

- Own subprocesses/session IDs explicitly and retain their exit statuses. Stop only owned captures/process groups; never use broad machine-wide kill commands. Preserve the serving target when the experimental protocol requires it to continue.
- Cancellation/timeouts close pending timing phases, consume attempted budget, prevent late evidence consumption and report whether descendants/report writers are still alive. Preserve partial reports with failed status.
- A native NVML call runs in a separately spawned worker. Cooperative shutdown is attempted, then termination/kill with bounded polling. Record forced termination and whether the worker remained alive; forced cleanup does not establish an NVML shutdown acknowledgement.
- The sampler remains inside an async context outside `ProducerBridge.run()` so startup precedes observation and final cleanup follows sampling cancellation. Initialize the real observation horizon after sampler/server preparation; do not consume the observation budget during setup.

## Hardware acceptance sequence

| Check | Required observation | Current status |
|---|---|---|
| Passive preflight | Inventory without initializing CUDA/NVML or contacting serving endpoint | CPU implementation/tests complete |
| NVML device smoke | Explicit UUID matches, finite utilization under idle/load, failures preserved, clean worker exit | Real L4 identity/read and isolated-worker cleanup passed; target errors additionally CPU-tested |
| Worker mapping | Serving workers shown to use the selected UUID(s) | One actual vLLM CUDA worker/L4 UUID mapped and verified against captured kernels |
| Capture smoke | Known CUDA activity appears in intended process/device/range | Native CUDA probe and vLLM kernel/device/PID coverage passed on the pinned L4 stack; exact active boundaries still unknown |
| Readiness smoke | Final report → export → validated parse → decision while serving continues | Single-worker L4 serving smoke passed with synchronous flush and abstaining classifier; report hashes checked after shutdown |
| Failure smoke | Startup/export/parse timeout and cancellation leave no owned processes behind | Fake pipeline and owned CPU subprocess groups tested; actual Nsight/session validation pending |
| Pilot experiment | Same horizon/load across policies, independent diagnoses, full cost scopes and run provenance | Step-011 corrected matrix complete: 18 runs/39 captures with telemetry/readiness/integrity/cleanup checks passed; independent diagnoses, matched perturbation controls and full costs remain pending |

**GPU boundary:** NVML/profiler adapter preparation can proceed on CPU, but the device/coverage/readiness acceptance checks require an NVIDIA GPU. Passing preflight or mocked tests is not permission to report live adaptive-stopping results.

## Implemented CPU command harness boundary (step 009)

`CommandProfilerBackend` now implements the backend lifecycle with versioned argv plans, per-attempt tokens/directories, explicit start/stop acknowledgement inputs, report/export/summary integrity checks, external-stage deadlines, and owned POSIX process-group cleanup. The controller waits for cleanup before launching another attempt. See [step 009](progress/009_profiler_command_lifecycle_harness.md) and the [usage guide](README.md).

The current protocol accepts `source=fake_executable`, `ack_basis=synthetic_fixture`, `coverage=fixture_verified`, and `synthetic_simulation` recorder provenance only. It intentionally cannot certify a live Nsight session. A real driver must replace and validate these sources/contracts and preserve the serving process independently of attempt-owned commands. Code tests do not establish arbitrary attachment support, CUDA capture boundaries, GPU/worker coverage, installed-version compatibility, or serving perturbation. Those remain the hardware acceptance criteria above.

## Hardware-tested pilot boundary (step 010)

The separate `NsightServingBackend` accepts actual `live_online` observations from the pinned L4/Nsight 2026.3.1/vLLM 0.10.2 stack. CUDA-owner acknowledgements include the configured device UUID and worker PID. A Nsight start callback corroborates collection start. The tested stop path uses synchronous per-range flush followed by successful export and strict SQLite parse/coverage checks; it does not depend on an unobserved report-ready callback or relabel mere file existence as readiness. The CPU fake-command protocol remains synthetic and is not switched to live provenance.

The tested synchronous flush can block the worker and must be included when studying perturbation. The earlier asynchronous/deferred serving attempt failed its online gate and remains failed. API/control spans are available; GPU capture-active time and pure finalization boundaries remain unknown. Read-only kernel parsing verifies this configured single worker and device; it is not a distributed-coverage claim or a calibrated root-cause classifier.

The supervised pilot owns the persistent serving-session lifetime separately from capture RPC/export helpers. Session teardown is checked independently of policy stop, and source/package/configuration/observations are retained. The matrix currently freezes reactivation off to compare stop rules; deployment defaults remain unchanged. See [step 010](progress/010_l4_hardware_capture_integration.md) and [step 011](progress/011_l4_live_engineering_pilot.md).

The live runner must own a distinct NVML sampler per observation episode. Cancellation of an in-flight native read closes that sampler and must not affect the next episode. Step 011 found this reuse defect in `pilot_001`; the retained matrix has missing telemetry. The corrected runner records per-episode sampler cleanup and fails on sampling errors or windows without GPU readings. The matrix rerun is `pilot_002`.

The corrected `pilot_002` completed 18 runs and 39 captures with zero sampling errors or missing GPU windows. All 39 decisions had parsed evidence before decision and serving continued afterward; 78 artifact hashes matched. Owned serving/sampler workers exited and no GPU compute process remained. Independent diagnosis and capture-active measurement remain pending.
