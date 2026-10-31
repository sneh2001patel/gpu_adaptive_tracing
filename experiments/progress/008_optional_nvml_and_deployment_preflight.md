# Step 008 — Optional NVML sampler and deployment preflight

Date: 2026-10-27. Status: completed for CPU-testable telemetry preparation and passive environment inventory. No real NVML initialization/query, CUDA capture, GPU installation, or paper experiment was performed.

## Completed work

- [x] Added `experiments/tracing/nvml_sampler.py`, with lazy optional `pynvml` import confined to a separately spawned process. CPU demos/tests do not require NVIDIA packages.
- [x] Added explicit physical-device UUID selection and returned-UUID verification. Device indices, MIG UUIDs, and MIG-enabled devices are rejected for this first adapter. Device-wide utilization is not claimed to attribute serving-worker activity.
- [x] Preserved valid zero utilization while rejecting invalid/nonfinite readings. Completed query errors raise an exception for the bridge to record as missing/error; the next query can retry without reusing a cached reading.
- [x] Added startup/read/shutdown deadlines, cooperative shutdown acknowledgement, termination/kill fallback, cancellation propagation, and cleanup diagnostics. A stalled native call cannot hold the controller's asyncio loop. The sampler is single-use after timeout/protocol failure/cancellation.
- [x] Logged query request and parent receipt timestamps in the supplied controller clock domain. The device averaging interval stays unknown; receipt timestamps are not relabeled as instantaneous GPU event times.
- [x] Added passive `preflight_gpu.py`: platform/Python, optional binding/module, `nsys` path, and CUDA visibility inventory. Optional endpoint/calibration inputs receive syntax checks only, with no server connection.
- [x] Added an explicit `--probe-nvml --device-uuid GPU-...` path for later hardware use. Even a successful read cannot set `live_experiment_ready=true` while worker mapping and real profiler coverage/readiness remain unverified.
- [x] Created `REAL_PROFILER_CONTRACT.md` with version-specific launch/session requirements, capture acknowledgement, worker/device coverage, clock/cost boundaries, artifact/parse readiness, independent evidence, and owned-process cleanup acceptance checks.
- [x] Added 23 CPU-only tests, saved a passive local inventory, and updated the README, progress index, and CAIN plan.

## Validation

```bash
python3 -m unittest discover -s experiments/tests -q
python3 experiments/scripts/preflight_gpu.py
python3 -m py_compile experiments/tracing/nvml_sampler.py experiments/scripts/preflight_gpu.py experiments/tests/test_nvml_sampler.py
git diff --check
```

The full suite passes **149 CPU-only tests** (126 previous, 23 added). New tests exercise binding lifecycle, UUID/MIG checks, zero/invalid/error utilization, lazy imports in a fresh interpreter, spawned-worker startup/read/shutdown failures and stalls, event-loop heartbeat during a stalled native call, cancellation cleanup, retries, stale/malformed response rejection, sampler-to-HTTP-bridge integration, passive inventory, supplied configuration checks, and preflight failure/readiness semantics. All native interactions in tests use fake bindings/workers.

The saved local passive report identifies Darwin/Python 3.13.7, no `pynvml` module, and no `nsys` executable. NVML remains `not_checked`; GPU/capture readiness is false. This is an inventory, not a failed GPU experiment or a hardware baseline. No optional dependency was installed.

## Remaining limits

- Real binding/driver behavior, utilization under load, worker-to-device mapping, actual sampler perturbation, and cleanup on the target OS remain unvalidated. Device-wide utilization can include unrelated processes and the underlying device averaging interval is unknown.
- The spawn-worker transport and retained audit events are research instrumentation with unmeasured IPC, throughput, and memory cost. A process in an OS-level unkillable state cannot be guaranteed to exit; cleanup checks report and raise if the worker survives bounded termination/kill polling.
- The existing profiler remains fake. The contract does not implement arbitrary process attachment, Nsight sessions, CUDA acknowledgements, artifact parsing, or measured capture coverage. Binary/package discovery and NVML success cannot imply those capabilities.
- Hardware smoke probes should be run on a target NVIDIA machine only after explicitly configuring its physical UUID. Sample initialization must finish before constructing the observation horizon; keep sampler ownership outside the bridge's context so drain/cancellation cleanup is explicit.
- Existing artifacts, experiments, paper tables, and submitted PDF are unchanged. No new empirical claims are supported by this step.

## Next step

**Step 009: real profiler command/lifecycle harness, exercised with a fake executable on CPU.** Implement version/configuration-specific command plans, owned subprocess/session lifecycle, acknowledgement inputs, report/export/parse readiness checks, and bounded cleanup behind the existing backend interface. Do not equate command success with capture acknowledgement or fill unknown capture boundaries. Real Nsight invocation and coverage validation remain gated on an NVIDIA target and installed-version capability checks.

**GPU notice:** the preparation above can continue without hardware. Actual NVML/device smoke tests, serving-worker mapping, and Nsight capture/readiness/coverage validation now require NVIDIA GPU access. Notify the user before that hardware milestone; do not substitute fake results for it.
