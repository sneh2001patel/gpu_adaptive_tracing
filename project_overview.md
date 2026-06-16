# Automatic Short-Burst GPU Tracing: Project Overview

## Overview

GPU profiling tools can expose detailed evidence about kernel execution, memory behavior, and accelerator utilization. However, these tools are usually used manually or through fixed profiling windows. A developer or operator decides when to start profiling, how long to collect traces, and when enough evidence has been gathered.

This project studies a different approach: an adaptive GPU tracing controller that automatically decides when to activate heavy GPU tracing and when to stop it. The controller uses cheap always-on signals, such as request latency, queueing delay, GPU utilization, and GPU memory utilization, to detect suspicious windows. When those signals are not enough to explain the problem, the controller activates a short burst of heavier GPU tracing, such as kernel execution timing. It then stops heavy tracing once the collected evidence is sufficient for diagnosis.

The main research question is:

> Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

The project focuses on a narrow, practical tracing surface instead of trying to trace every GPU signal. The first version should use:

1. GPU utilization and GPU memory utilization as cheap low-cost evidence.
2. Kernel execution timing from short profiler bursts as high-cost evidence.

This creates a clean tracing ladder: cheap signals run continuously, while heavy GPU tracing is activated only when needed and stopped as soon as it stops improving diagnosis.

## Motivation

GPU-heavy systems, especially LLM serving systems, can experience performance problems for many reasons. Request latency may increase because of queueing, batching, GPU compute saturation, GPU memory pressure, long inputs, long outputs, or temporary workload changes. Cheap signals can show that something is wrong, but they may not explain why.

Manual GPU profiling is useful, but it has practical limitations:

- It requires human intervention.
- It often uses fixed profiling windows.
- It may collect more evidence than needed.
- It may start too late after the important behavior has passed.
- It may perturb the workload or generate large profiler outputs.
- It does not answer when profiling should stop.

An automatic tracing controller could make GPU profiling more usable in live systems. Instead of profiling continuously or relying on manual decisions, the controller would collect cheap evidence all the time and use heavy tracing only when the expected diagnostic value is high.

The motivation is not simply to reduce trace volume. The deeper problem is diagnostic sufficiency:

> When has the system seen enough GPU evidence to make a diagnosis, and when is more heavy tracing no longer worth the cost?

## Research Gap

Existing work leaves a clear gap between adaptive tracing and GPU profiling.

Adaptive distributed tracing systems study how to sample request traces, select interesting spans, reduce trace volume, or add instrumentation dynamically. These systems are useful, but they usually operate at the request or service level. They do not deeply study GPU-specific evidence tiers such as utilization counters, memory utilization, kernel execution timing, or profiler bursts.

GPU profiling tools provide rich low-level evidence. They can show kernel timing, memory transfers, occupancy, stalls, and CPU-GPU interactions. However, they are mostly used as manual tools or fixed-window profiling mechanisms. They expose evidence, but they do not decide when the evidence should be collected or when it is sufficient.

LLM serving systems create realistic GPU diagnosis problems. Systems such as vLLM, Orca, and SARATHI show that GPU utilization, batching, prefill, decode, queueing, and memory pressure interact in complex ways. However, this work generally does not study tracing lifecycle control.

The missing research problem is:

> How can a runtime controller automatically manage heavy GPU tracing so that it collects enough evidence for diagnosis without relying on manual profiling windows?

This gap has three parts:

1. Activation: deciding when cheap evidence is insufficient and heavy GPU tracing should start.
2. Evidence sufficiency: deciding when the heavy trace has collected enough diagnostic evidence.
3. De-escalation: stopping heavy GPU tracing before it wastes budget or perturbs the workload.

## Proposed Research Direction

This project proposes an automatic short-burst GPU tracing controller.

The controller starts with cheap always-on evidence:

- Request latency.
- Request throughput.
- Queueing delay.
- GPU utilization.
- GPU memory utilization.

When cheap evidence indicates a suspicious window but cannot explain the likely cause, the controller activates a short heavy-tracing burst:

- Kernel execution timing.
- Kernel duration distribution.
- Kernel launch frequency.
- Optional memory-related profiler evidence if available.

After each burst, the controller asks whether the new evidence changed the diagnosis. If the bottleneck class is stable, if additional bursts no longer change the root-cause ranking, or if cheap signals show sustained recovery, the controller stops heavy tracing.

The controller can compare several short-burst policies:

- Fixed Burst: collect one fixed-duration profiler burst after anomaly detection.
- Repeated Fixed Burst: collect repeated bursts until a maximum tracing budget is reached.
- Stability Stop: stop after the bottleneck class remains unchanged for several windows.
- Marginal Utility Stop: stop when a new burst does not change the diagnosis score or root-cause ranking.
- Counter-Recovery Stop: stop when request latency and cheap GPU counters both return to baseline.
- Hybrid Stop: stop only when diagnosis is stable and cheap counters show sustained recovery.

The likely strongest policy is the hybrid policy because it uses both diagnosis stability and recovery evidence. A pure fixed-burst policy may waste tracing budget, while a pure counter-recovery policy may stop too early during temporary symptom reduction.

## Research Questions

### RQ1: Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

This is the main research question. It asks whether the controller can stop heavy tracing automatically once additional kernel-timing evidence no longer changes the diagnosis.

This RQ should evaluate:

- Whether the controller stops earlier than fixed manual profiler windows.
- Whether it avoids premature stopping.
- Whether it preserves diagnosis quality while reducing heavy-tracing duration.

### RQ2: How accurate is automatic GPU tracing compared with a manual profiling approach?

This RQ compares the automatic controller against a manual-style baseline.

The manual baseline can be modeled as:

1. Detect an anomaly.
2. Start a profiler window using a fixed rule.
3. Collect a fixed-duration heavy trace.
4. Diagnose from the collected profiler output.
5. Stop when the fixed window ends.

The automatic controller should be evaluated against this baseline using:

- Top-1 diagnosis accuracy.
- Top-k diagnosis accuracy.
- Unresolved or ambiguous rate.
- Time-to-diagnosis.
- Premature-stop rate.

### RQ3: Does automatic GPU tracing introduce overhead compared with manual profiling, and is the overhead negligible?

This RQ measures whether the controller and short-burst tracing perturb the workload.

Relevant overhead metrics include:

- p50 request latency.
- p95 request latency.
- Throughput.
- Heavy-tracing duration.
- Profiler output size.
- Controller CPU overhead.
- GPU overhead if measurable.
- Total tracing budget used.

The expected result is that controller overhead should be small, and automatic tracing should reduce profiler duration and profiler output size compared with fixed-window manual profiling.

### RQ4: Which short-burst GPU tracing policies work best?

This RQ compares different policies for activating and stopping heavy GPU tracing.

Candidate policies include:

- Fixed Burst.
- Repeated Fixed Burst.
- Stability Stop.
- Marginal Utility Stop.
- Counter-Recovery Stop.
- Hybrid Stop.

The comparison should evaluate:

- Diagnosis accuracy.
- Heavy-tracing duration.
- Trace volume.
- Premature-stop rate.
- Re-escalation rate.
- Diagnosis quality per unit tracing cost.

### RQ5: Which runtime signals are most useful for deciding when to stop heavy GPU tracing?

This RQ studies the stopping signals used by the controller.

Candidate signals include:

- Stable bottleneck class.
- Stable root-cause ranking.
- No diagnosis change after a new profiler burst.
- Request latency recovery.
- Queueing delay recovery.
- GPU utilization recovery.
- GPU memory utilization recovery.
- Kernel duration stability.

This RQ is important because the best signal for starting heavy tracing may not be the best signal for stopping it.

## Expected Contributions

This project can contribute:

1. A formulation of automatic GPU trace de-escalation as a runtime control problem.
2. A short-burst GPU tracing controller that starts and stops heavy tracing without manual intervention.
3. A focused GPU evidence model using cheap utilization counters and high-cost kernel timing bursts.
4. A set of short-burst tracing policies for deciding when to continue or stop heavy GPU tracing.
5. An evaluation against a manual fixed-window profiling baseline.
6. Evidence about the accuracy, overhead, and tracing-budget tradeoffs of automatic GPU tracing.
7. A signal analysis showing which runtime signals are most useful for deciding when enough GPU evidence has been collected.

## Possible Evaluation Setup

A first evaluation can use a single-GPU LLM serving system such as vLLM.

Possible scenarios:

- Healthy service.
- Queue pressure.
- GPU compute saturation.
- GPU memory pressure.
- Long input workload.
- Long output workload.
- Mixed cases.
- Temporary recovery or intermittent anomaly cases.

Evidence tiers:

| Tier | Evidence | Cost role |
|---|---|---|
| T0 | Request latency, throughput, queueing delay | Always-on cheap evidence |
| T1 | GPU utilization and GPU memory utilization | Cheap GPU evidence |
| T2 | Short kernel execution timing burst | Heavy GPU evidence |

Baselines:

- No heavy tracing.
- Manual fixed-window profiling.
- Always-profile during anomaly.
- Fixed Burst.
- Repeated Fixed Burst.
- Oracle Stop.

Metrics:

- Diagnosis accuracy.
- Time-to-diagnosis.
- Heavy-tracing duration.
- Profiler output size.
- Budget used.
- p50 and p95 latency overhead.
- Throughput overhead.
- Premature-stop rate.
- Re-escalation rate.
- Diagnosis quality per unit cost.

## Summary

The main idea is to make GPU profiling automatic and evidence-aware. Instead of relying on manual profiler windows, the system uses cheap request and GPU utilization signals to decide when heavy GPU tracing is needed, collects short bursts of kernel-level evidence, and stops when additional tracing no longer improves diagnosis.

The central contribution is not a new GPU profiler. The contribution is the controller around profiling: deciding when to trace, when to continue, and when to stop under a runtime tracing budget.
