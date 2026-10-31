# Step 010 — L4 hardware capture and persistent vLLM integration

Date: 2026-10-27. Status: completed for one NVIDIA L4, one CUDA-owning vLLM worker, and the pinned pilot stack. This is an engineering validation, not confirmation of diagnostic accuracy, capture-active savings, or general multi-worker support.

## Completed work

- [x] Connected to the user-provided rental, read its full `/etc/vast-agents-guide.md`, and confirmed an NVIDIA L4 with UUID `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb`. Preserved the instance's management services and host-injected driver.
- [x] Recorded the environment and successfully queried the physical device through the isolated NVML adapter. The container blocks CPU perf sampling; CUDA activity tracing works with `--sample=none --cpuctxsw=none`.
- [x] Compiled and ran `experiments/native/capture_probe.cu` in the actual GPU-owning process. Two real Nsight reports were observed before the target finished, with continued post-capture CUDA work. Exported SQLite verified actual kernel records, device UUID and target PID.
- [x] Installed a separate vLLM environment and pinned its compatible Transformers release. Downloaded the public Qwen2.5-7B-Instruct model at revision `a09a35458c702b33eeacc393d103063234e8bc28`. Stored weights in `/dev/shm/hf-cache` because the instance has a 32 GiB writable container filesystem, rather than the previously suggested disk allocation.
- [x] Added `CudaCaptureWorker`, executing start/stop profiler APIs inside the vLLM worker and writing identity/UUID/clock/API-return acknowledgements. The parent controller does not issue unrelated CUDA profiler calls and assume worker coverage.
- [x] Added a pinned vLLM entry point that registers the profiling routes but removes the Torch profiler setting before frontend/worker construction. Nsight CUDA capture runs without simultaneous Torch/Kineto profiling; the successful smoke produced zero Torch trace artifacts.
- [x] Added `NsightServingBackend` with worker and Nsight-start acknowledgements, bounded local capture RPC helpers, report/export/parser readiness, strict single-device/worker SQLite coverage, artifact hashes, and fresh evidence IDs. Failed or uncertain captures poison the session rather than allowing unsafe retries.
- [x] Validated synchronous per-range report flushing (`repeat:120:sync`) while keeping the serving process alive. Report readiness requires worker stop acknowledgement and successful SQLite export/validation; file existence alone is not evidence readiness. Capture-active time stays null.
- [x] Added an explicit `reactivation_enabled` controller setting (`streaming_v4`) so policy-comparison runs can hold reactivation off without changing deployment defaults. The initial successful smoke exercised two changed-evidence reactivations; the subsequent matrix disables reactivation prospectively.
- [x] Added 13 parser/backend protocol tests and one controller regression. Full suite: **185 CPU-only tests pass** (171 previous, 14 added). Actual hardware checks are separate from that test count.

## Validated stack

| Component | Observed configuration |
|---|---|
| GPU | NVIDIA L4, 23034 MiB reported by `nvidia-smi` |
| Host driver | 615.71.09 |
| Nsight Systems | 2026.3.1.0 |
| CUDA compiler | 13.4; native probe compiled for `sm_89` |
| Serving Python | 3.12.15 |
| PyTorch | 2.8.0+cu128 |
| vLLM | 0.10.2 |
| Transformers | 4.55.2 |
| NVML binding | nvidia-ml-py 13.615.71 |
| Serving | One GPU/worker, FP16, eager execution, context 2048, max 16 sequences |

Exact package versions and source fingerprints are stored with the hardware/pilot artifacts. The working tree is uncommitted; file hashes identify the executed revision rather than pretending the base Git commit includes these changes.

## Hardware evidence and failures retained

Artifacts: `experiments/hardware/l4_20261027/`.

- `capture_smoke/`: native source build/output, real reports/SQLite, commands and target progress.
- `nvml_preflight.json`: real device read and sampler cleanup diagnostics. Successful telemetry alone does not establish live-experiment readiness.
- `smoke_001/` and `smoke_002/`: command/callback argument handling failures, before serving started. Corrected by using executable callback wrappers and `--option=value` for optional Nsight callback arguments.
- `smoke_003/`: actual serving requests completed, but the profiling RPC was disabled (HTTP 404); capture was retained as failed.
- `smoke_004/`: start/stop acknowledgements succeeded, but the deferred/asynchronous report-ready path did not satisfy the online gate before the horizon. It remains a failed/censored capture, not a successful online experiment.
- `smoke_005/`: successful persistent-serving smoke, three valid captures within one incident through two reactivations, zero request errors, and zero late request/GPU observations. Report parsing and policy decisions occurred while serving continued. The classifier abstained throughout, so these are fixed-burst mechanics, not correct diagnoses.

The supported engineering path now uses synchronous range flushing. It pauses the CUDA worker during flush and this cost enters measured control/RPC/evidence latency. The earlier asynchronous attempt must not be presented as validated for vLLM. This restriction matters for eventual profiling overhead claims.

## Timing and scope

CUDA API request/return times and callback receipts use the same host `CLOCK_MONOTONIC`, explicitly passed as the session clock domain. Nsight kernel timestamps remain in the profiler domain; they are not subtracted from controller times. Kernel counts, duration sums and envelopes are measured separately and never relabeled capture-active seconds.

The capture-control span includes acknowledgement/stop-RPC/flush latency. Report-readiness waiting is separately logged; successful export/parse gate evidence availability. Pure finalization, capture-active time, per-attempt whole-profiler-process time (the profiler session spans all captures), and total persisted lifecycle are not inferred where they cannot be isolated. Source manifests, package freezes, calibration requests, per-command logs and run configuration are retained.

Only the configured single worker/device is validated. Distributed serving, additional GPUs, A100 transfer, calibrated diagnoses, full-controller perturbation, active-capture boundary measurement and independent references remain pending. The default cheap classifier is not substituted for validated T2 diagnosis.

## Next step

**Step 011: small prospective live engineering matrix.** Use a frozen separate healthy reference, the five distinct policies, three repetition labels and healthy controls on this L4. Keep a fixed observation horizon, log admission skips/drain, disable reactivation explicitly, and audit every decision against real readiness and continued serving. Keep unknown diagnoses and scope results as engineering evidence; do not regenerate paper accuracy/savings tables. Create its step report, analysis and plan update after the matrix finishes.
