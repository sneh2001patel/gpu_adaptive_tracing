# Experiment Setup Plan: Automatic Short-Burst GPU Tracing

## Summary
Build a single-GPU experimental study that tests whether an automatic GPU tracing controller can decide when to start and stop heavy GPU profiling without manual intervention. The study will run in two stages: controlled CUDA/PyTorch microbenchmarks first, then a realistic vLLM serving workload. The controller will use cheap GPU utilization and memory utilization signals continuously, then activate short Nsight/CUPTI-style kernel-timing bursts only when cheap evidence is insufficient.

Primary RQ:

> Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

Supporting RQs:

- How accurate is automatic tracing compared with a manual fixed-window profiling approach?
- How much overhead does automatic tracing add, and is it negligible compared with manual profiling?
- Which short-burst GPU tracing policy works best?
- Which runtime signals are most useful for deciding when to stop heavy GPU tracing?

## GPU Systems To Test
Use cloud GPUs, one GPU per run, for the final evaluation. Keep the first paper single-GPU.

Phase 0 local development system:

| GPU | Why include it | Role |
|---|---|---|
| RTX 4060 Ti, 8GB | Locally available GPU for immediate development | Prototype controller logic, validate microbenchmarks, test profiler bursts, and run scaled-down vLLM smoke tests |

Use the 4060 Ti as a development and feasibility platform, not as a replacement for the final cloud GPU set. Its 8GB memory is enough for CUDA/PyTorch microbenchmarks and controller development, but the vLLM workload should use a smaller or quantized model, reduced context length, and low concurrency.

Recommended core set:

| GPU | Why include it | Role |
|---|---|---|
| NVIDIA L4, 24GB | Low-power inference GPU with 24GB memory | Cost-efficient inference baseline |
| NVIDIA A10, 24GB | Common midrange datacenter GPU with higher bandwidth than L4 | Mid-tier comparison |
| NVIDIA A100 40GB or 80GB | Widely used datacenter training/inference GPU | Strong datacenter baseline |
| NVIDIA H100 80GB | Modern high-end GPU | Optional high-end validation if budget allows |

Optional external-validity system:

| GPU | Why optional |
|---|---|
| RTX 4090, 24GB | Useful if locally available or cheap in cloud, but less datacenter-representative |

Default minimum publishable setup: L4 + A10 + A100. Add H100 only if cost allows.

Use NVIDIA tooling because the experiment depends on standard GPU telemetry and profiler access: DCGM/DCGM Exporter for cheap GPU metrics, Nsight Systems CLI for short profiler bursts, and CUPTI only if Nsight export is not enough for kernel timing. Relevant docs: NVIDIA DCGM Exporter, Nsight Systems CLI, CUPTI tracing docs, and vLLM GPU support docs.

## Experiment Design
Phase 0: Local development on RTX 4060 Ti

- Purpose: build and debug the controller before paying for cloud GPUs.
- Run the Stage 1 microbenchmarks locally first.
- Verify cheap GPU metric collection, suspicious-window detection, trace triggering, trace stopping, and profiler-output parsing.
- Run a scaled-down vLLM smoke test only after the controller works on microbenchmarks.
- Use a small or quantized model that fits in 8GB VRAM, with reduced context length and low request concurrency.
- Treat Phase 0 results as engineering validation, not as the final cross-GPU evaluation.

Stage 1: Controlled microbenchmarks

- Purpose: validate controller behavior under known bottlenecks before using vLLM.
- Workloads:
  - Compute-bound kernel loop.
  - Memory-bandwidth-bound tensor operation.
  - Mixed compute/memory workload.
  - Intermittent anomaly workload that alternates normal and degraded phases.
- Ground truth:
  - Label each window as healthy, compute-bound, memory-bound, mixed, or recovered.
- Use this stage to tune burst duration, stability windows, and diagnostic thresholds.

Stage 2: vLLM serving workload

- Purpose: test the controller in a realistic GPU-heavy system.
- Model:
  - Use one 7B/8B-class open model that fits on 24GB GPUs, with the same model across all GPUs.
- Scenarios:
  - Healthy service.
  - Queue pressure.
  - Long input workload.
  - Long output workload.
  - GPU compute saturation.
  - GPU memory pressure or KV-cache pressure.
  - Mixed queueing plus GPU pressure.
  - Temporary recovery or intermittent anomaly.
- Evidence tiers:
  - T0: request latency, throughput, queueing delay.
  - T1: GPU utilization and GPU memory utilization.
  - T2: short kernel-timing profiler burst.
- Windowing:
  - Aggregate evidence over fixed windows, e.g. 10s or 30s.
  - A suspicious window triggers the controller.
  - A heavy trace burst lasts a short fixed unit, e.g. 2s, 5s, or 10s depending on profiling feasibility.

## Controller And Baselines
Automatic controller behavior:

- Continuously collect T0/T1 evidence.
- Trigger a short T2 burst when latency is suspicious and cheap evidence is ambiguous.
- After each burst, classify the bottleneck state.
- Continue tracing only if the diagnosis remains unstable or ambiguous.
- Stop tracing when evidence is sufficient, budget is exhausted, or sustained recovery is observed.

Short-burst policies to compare:

| Policy | Behavior |
|---|---|
| Fixed Burst | One profiler burst after anomaly detection, then stop |
| Repeated Fixed Burst | Repeat bursts until max budget is reached |
| Stability Stop | Stop after bottleneck class is stable for N windows |
| Marginal Utility Stop | Stop when a new burst does not change diagnosis/ranking |
| Counter-Recovery Stop | Stop when latency and GPU counters return to baseline |
| Hybrid Stop | Stop only when diagnosis is stable and cheap counters show sustained recovery |

Baselines:

- No heavy tracing: cheap metrics only.
- Manual fixed-window profiling: start profiling after anomaly detection and collect a fixed duration.
- Always-profile during anomaly: heavy tracing remains active while anomaly persists.
- Oracle stop: offline ideal that stops when enough evidence for the correct label has appeared.

Manual baseline definition:

- Manual does not mean a real human must inspect every run.
- Model it as a fixed operational workflow: anomaly detected, fixed profiler window starts, diagnosis is made from that fixed window, then profiling stops.

## Metrics And Acceptance Criteria
Diagnosis metrics:

- Top-1 diagnosis accuracy.
- Top-k diagnosis accuracy.
- Unknown or ambiguous rate.
- Time-to-diagnosis.
- Premature-stop rate.
- Re-escalation rate.

Cost and overhead metrics:

- Heavy tracing duration.
- Profiler output size.
- Total tracing budget used.
- p50 and p95 request latency.
- Throughput.
- Controller CPU overhead.
- GPU utilization perturbation if measurable.

Policy success criteria:

- Automatic tracing should approach manual fixed-window diagnosis accuracy.
- Automatic tracing should reduce heavy tracing duration and profiler output size.
- Controller overhead should be small compared with fixed-window profiling.
- Hybrid Stop and Marginal Utility Stop should be the main expected winners.
- The study should report when automatic tracing fails, especially temporary recovery and ambiguous mixed cases.

## Assumptions
- Cloud GPU access is needed for the final evaluation, but local development can begin on the RTX 4060 Ti 8GB.
- The first paper stays single-GPU.
- The study uses both stages: microbenchmarks first, vLLM second.
- The focused trace targets are GPU utilization/memory utilization plus kernel execution timing.
- H100 is optional; L4, A10, and A100 are the recommended core systems.
- The 4060 Ti is a Phase 0 development system only; final paper claims should rely on the recommended cloud GPU set.
- The implementation should prefer Nsight Systems CLI for short profiler bursts, DCGM/DCGM Exporter for cheap metrics, and CUPTI only if finer kernel-timing control is needed.
