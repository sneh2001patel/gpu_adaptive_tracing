# Research Gaps: Budget-Aware Adaptive GPU Tracing

## Core Gap Statement

The literature has mature work on adaptive distributed tracing, mature tools for GPU profiling and instrumentation, and strong systems work on GPU-heavy LLM serving. However, these areas are mostly separate.

Adaptive tracing papers decide which request traces or spans to collect, but they rarely treat GPU counters, GPU runtime events, kernel traces, or profiler captures as tiered evidence sources with explicit cost. GPU profiling papers expose rich accelerator evidence, but they usually assume the profiler is manually invoked or used during offline optimization rather than controlled by an adaptive tracing policy. LLM serving papers explain realistic GPU bottlenecks, but they generally do not study when to activate, stop, or budget GPU tracing during live diagnosis.

The research opportunity is a controller that continuously collects cheap request and GPU utilization evidence, selectively escalates to richer GPU evidence under a tracing budget, and de-escalates once additional GPU tracing no longer improves diagnosis.

## What the 20 Papers Cover

| Literature cluster | Representative papers | What they contribute | What they leave open |
|---|---|---|---|
| Distributed tracing infrastructure | Dapper, X-Trace, Canopy | End-to-end request visibility, causal context propagation, production-scale trace processing | GPU execution is not treated as a first-class tracing target |
| Dynamic and adaptive tracing | Pivot Tracing, Hindsight, Sifter, TraStrainer, TraceMesh, Astraea | Runtime instrumentation, adaptive sampling, suspicious trace selection, budget-aware span utility | Adaptation is mostly at request/span level, not GPU evidence-tier level |
| Trace cost reduction | Mint, Tracezip, 3MileBeach | Trace compression, lower trace volume, lower instrumentation overhead, fault-injection support | Cost reduction is not connected to GPU profiler escalation and de-escalation |
| GPU tracing and profiling | NVBit, Low-Overhead GPU Trace Collection, HPCToolkit, DrGPU | GPU instrumentation, kernel tracing, counters, PC sampling, CPU-GPU attribution | Tools expose evidence, but do not decide when evidence should be collected |
| GPU-heavy LLM serving | vLLM/PagedAttention, Orca, SARATHI | Realistic GPU bottlenecks: KV cache pressure, batching, prefill/decode imbalance, utilization changes | Diagnosis and observability are not framed as adaptive tracing lifecycle problems |

## Gap 1: GPU Evidence Is Not Modeled as a Tiered Tracing Budget

Existing adaptive tracing work usually models cost in terms of request traces, spans, instrumentation points, storage, or network volume. GPU observability has a different cost structure. Cheap GPU utilization counters are very different from per-process metrics, kernel traces, CUPTI activity records, or Nsight-style profiler captures.

What is missing:

- A GPU-specific evidence hierarchy.
- A cost model for each GPU evidence tier.
- A policy that decides whether the next GPU tracing action is worth the remaining budget.
- A way to compare diagnostic utility per unit tracing cost.

Possible contribution:

> Define a budget-aware GPU evidence model with tiers such as request metrics, GPU utilization counters, detailed device metrics, runtime events, kernel traces, and profiler bursts.

Possible RQ:

> How should an adaptive tracing controller allocate a limited GPU tracing budget across cheap counters, detailed GPU metrics, and heavy profiler captures?

## Gap 2: GPU Profiling Tools Are Rich but Not Adaptive

GPU profiling tools can expose kernel timing, memory transfers, occupancy, stalls, GPU memory behavior, and CPU-GPU attribution. However, these tools are typically used manually, offline, or for fixed profiling windows. They do not usually answer when profiling should start, how long it should continue, or when the collected evidence is enough.

What is missing:

- A control policy around profiler activation.
- Short-burst GPU tracing policies.
- A stopping rule for profiler captures.
- A way to avoid profiling during windows where cheap evidence is sufficient.

Possible contribution:

> Convert GPU profiling from a manual diagnostic action into an adaptive evidence acquisition action controlled by runtime suspicion, uncertainty, and budget.

Possible RQ:

> Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

### Focused Project Version of Gap 2

This is the strongest main direction for a new paper:

> Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

The key novelty is an automatic controller around GPU tracing. Instead of a human deciding when to start Nsight/CUPTI/kernel tracing, how long to run it, and when to stop, the system makes those decisions at runtime from cheap signals and short bursts of heavy evidence.

The project should not try to trace every possible GPU signal. GPUs expose many possible evidence sources, and using all of them would make the study too broad. A stronger first paper should focus on one or two GPU trace targets where the diagnosis problem is clear.

Recommended trace targets:

1. GPU utilization and memory utilization counters.
2. Kernel execution timing from short profiler bursts.

These two are a good starting point because they create a clean evidence ladder:

| Evidence | Cost | Role |
|---|---:|---|
| Request latency and queueing delay | Very low | Detect suspicious serving windows |
| GPU utilization and memory utilization | Low | Decide whether the symptom is likely GPU-related |
| Short kernel-timing burst | High | Resolve ambiguity only when counters are insufficient |

This keeps the scope narrow enough to evaluate rigorously. The controller does not need to diagnose every possible GPU fault. It can focus on a small set of bottleneck classes:

- Normal or recovered behavior.
- GPU compute saturation.
- GPU memory pressure.
- Queueing or batching pressure that raises latency without proportional GPU execution slowdown.
- Ambiguous case requiring heavy trace evidence.

This also gives a clean automatic-versus-manual comparison. The manual baseline is a human-style fixed profiler workflow: start profiling after detecting an anomaly, collect a fixed-duration profiler window, inspect the evidence, and stop after the fixed window. The automatic controller instead starts and stops heavy tracing based on diagnosis stability and marginal evidence gain.

Additional research questions:

> How accurate is the automatic controller compared with a manual fixed-window GPU tracing approach?

This asks whether automatic start/stop decisions preserve the same diagnosis quality as a manual profiler workflow. The comparison should report diagnosis accuracy, unresolved rate, premature-stop rate, and time-to-diagnosis.

> Does automatic GPU tracing introduce overhead compared with the manual approach, and if so is the overhead negligible?

This asks whether the controller itself and its short profiler bursts perturb the workload. The comparison should report p50/p95 latency, throughput, profiler duration, trace volume, CPU overhead, GPU overhead if measurable, and total budget used.

> Which short-burst GPU tracing policies work best?

This asks how the controller should use heavy GPU tracing once it is activated. The policies should vary burst length, stopping condition, cooldown, and evidence-stability rule.

Candidate short-burst policies:

- Fixed Burst: collect one fixed-duration profiler burst after anomaly detection.
- Repeated Fixed Burst: collect repeated bursts until a maximum budget is reached.
- Stability Stop: stop after the bottleneck class is unchanged for several windows.
- Marginal Utility Stop: stop when the next burst does not change the diagnosis score or root-cause ranking.
- Counter-Recovery Stop: stop when request latency and GPU counters both return to baseline.
- Hybrid Stop: stop only when diagnosis is stable and cheap counters show sustained recovery.

The expected best policy is likely a hybrid policy. A pure fixed burst may waste budget, while a pure counter-recovery policy may stop too early during temporary symptom reduction.

## Gap 3: Adaptive Tracing Does Not Distinguish GPU Recovery From Temporary Symptom Reduction

Many adaptive tracing and sampling systems focus on selecting interesting traces during anomalous behavior. Less attention is given to the end of the tracing episode. This matters for GPUs because utilization, memory pressure, queueing delay, and latency can fluctuate rapidly under batching and mixed workloads.

A temporary drop in GPU utilization or request latency may not mean the fault is gone. It may only reflect a short workload lull, a different prompt mix, a transient batch shape, or a momentary reduction in queue pressure.

What is missing:

- Recovery criteria specific to GPU symptoms.
- Multi-window stability checks before de-escalation.
- Distinction between true recovery and temporary reduction in latency or utilization.
- Metrics for premature GPU trace stopping.

Possible contribution:

> Define evidence-stability policies for GPU trace de-escalation that require agreement between request-level recovery and GPU-level recovery across multiple windows.

Possible RQ:

> Can adaptive GPU trace de-escalation distinguish between true fault recovery and temporary symptom reduction?

## Gap 4: It Is Unclear Which GPU Runtime Signals Are Best for De-escalation

The literature gives many possible GPU signals: utilization, memory utilization, memory bandwidth, kernel duration, occupancy, stall cycles, power, temperature, runtime calls, synchronization, queueing delay, prefill/decode timing, and KV-cache pressure. But it is not clear which of these are most useful for deciding when to stop heavy tracing.

This is different from detecting that something is wrong. A signal that is useful for escalation may not be useful for de-escalation. For example, high GPU utilization may indicate suspicion, but stable utilization alone may not prove that the diagnosis is stable.

What is missing:

- Signal ranking for GPU trace stopping.
- Ablation study of GPU de-escalation signals.
- Comparison between request-level signals and GPU-level signals.
- Evidence of which signals prevent premature stopping.

Possible contribution:

> Evaluate candidate de-escalation signals and identify which ones best preserve diagnosis quality while reducing heavy tracing duration.

Possible RQ:

> Which runtime signals are most useful for deciding when to de-escalate heavy GPU tracing?

## Gap 5: Request Traces and GPU Traces Are Not Integrated Into One Diagnosis Path

Distributed tracing papers follow requests across services. GPU profiling papers follow kernels, runtime calls, and device-level activity. LLM serving systems sit across both worlds: a user request becomes queueing, batching, prefill, decode, memory pressure, and GPU kernel execution. The diagnosis needs both request context and GPU context.

What is missing:

- A request-to-GPU trace model.
- A way to attach GPU evidence to suspicious request cohorts.
- A mapping from request symptoms to GPU evidence tiers.
- A diagnosis model that can say whether the bottleneck is request queueing, batching, memory pressure, GPU compute saturation, host-side overhead, or temporary workload shape.

Possible contribution:

> Build a GPU-aware tracing lifecycle where request-level suspicion controls GPU-level evidence acquisition.

Possible RQ:

> Can request-level symptoms and cheap GPU utilization signals jointly decide which request cohorts deserve GPU-level tracing?

## Gap 6: LLM Serving Work Explains GPU Bottlenecks but Not Observability Control

vLLM, Orca, and SARATHI explain how LLM serving performance depends on batching, KV-cache memory, prefill, decode, and scheduling. These systems make GPU utilization behavior more understandable, but they do not focus on tracing budget or evidence lifecycle.

For adaptive GPU tracing, LLM serving is valuable because it creates realistic ambiguity:

- Queue pressure and long prompts can both raise latency.
- Decode-heavy workloads may underutilize compute while still creating latency.
- KV-cache pressure can look like memory or scheduling trouble.
- A short recovery window may reflect a temporary workload change rather than fault recovery.

What is missing:

- An observability controller for LLM serving.
- A study of which GPU evidence tiers resolve which LLM serving pathologies.
- A benchmark that measures diagnosis quality per unit GPU tracing cost.
- A stopping policy for profiler bursts during LLM inference anomalies.

Possible contribution:

> Use LLM serving as the concrete testbed for budget-aware adaptive GPU tracing, with controlled pathologies and measured GPU evidence tiers.

Possible RQ:

> Which GPU evidence tiers are necessary to diagnose LLM serving bottlenecks under a fixed tracing budget?

## Gap 7: Existing Work Optimizes Collection but Not Diagnostic Sufficiency

Sampling, compression, and low-overhead instrumentation reduce tracing cost. But lower cost is not the same as knowing when the evidence is sufficient for diagnosis. A system can collect less data and still stop too early, or collect compressed data that does not resolve the important ambiguity.

What is missing:

- A diagnostic sufficiency criterion for GPU tracing.
- A marginal utility measure for additional GPU evidence.
- A policy that stops because the diagnosis is stable, not because a fixed window expired.
- Metrics that jointly report cost saved and diagnosis preserved.

Possible contribution:

> Define diagnostic sufficiency as the point where additional GPU evidence no longer changes the root-cause ranking or verdict precision.

Possible RQ:

> Can marginal diagnostic utility determine when heavy GPU tracing should stop?

## Refined Research Direction

A sharper project framing is:

> Budget-aware adaptive GPU tracing studies whether an automatic controller can decide when to start heavy GPU tracing, when to stop it, and whether it can match manual profiling accuracy with lower or negligible overhead.

This framing has three parts:

1. Activation: decide when cheap request and GPU utilization signals justify a short heavy-tracing burst.
2. Evidence sufficiency: decide whether the burst has collected enough diagnostic evidence.
3. De-escalation: stop heavy GPU tracing when diagnosis is stable, without requiring manual intervention.

## Proposed Main Research Questions

### RQ1: Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

This is the main research question. It asks whether the controller can stop heavy tracing automatically once additional kernel-timing or GPU utilization evidence no longer changes the diagnosis.

Expected result:

- The controller should stop earlier than a fixed manual profiler window when evidence stabilizes.
- It should avoid stopping too early when the diagnosis remains ambiguous.
- It should reduce heavy-tracing duration while preserving diagnosis quality.

### RQ2: How accurate is the automatic controller compared with a manual GPU tracing approach?

This RQ compares automatic tracing against a manual-style fixed-window workflow.

Manual baseline:

- Detect anomaly.
- Start profiler manually or by a fixed rule.
- Collect a fixed-duration heavy trace.
- Diagnose from the collected trace.
- Stop after the fixed window.

Expected result:

- Automatic tracing should approach manual diagnosis accuracy.
- Automatic tracing should reduce unnecessary profiler time.
- Automatic tracing should have fewer wasted tracing windows when cheap evidence is already sufficient.

### RQ3: Does automatic GPU tracing introduce overhead compared with the manual approach?

This RQ measures whether the controller and its short bursts perturb the workload.

Overhead metrics:

- p50 and p95 request latency.
- Throughput.
- Heavy-tracing duration.
- Profiler output volume.
- CPU overhead from the controller.
- GPU overhead if measurable.
- Total tracing budget used.

Expected result:

- Controller overhead should be negligible relative to manual heavy tracing.
- Automatic tracing should reduce profiler duration and trace volume compared with fixed-window manual profiling.

### RQ4: Which short-burst GPU tracing policies work best?

This RQ compares policies for how the controller uses heavy tracing once activated.

Candidate policies:

- Fixed Burst.
- Repeated Fixed Burst.
- Stability Stop.
- Marginal Utility Stop.
- Counter-Recovery Stop.
- Hybrid Stop.

Expected result:

- Hybrid or marginal-utility policies should perform better than fixed bursts.
- Pure recovery-based stopping may be vulnerable to temporary symptom reduction.

### RQ5: Which runtime signals are most useful for stopping heavy GPU tracing?

This RQ ranks candidate signals for de-escalation.

Possible stopping signals:

- Stable root-cause ranking.
- Stable GPU bottleneck class.
- No change after additional profiler samples.
- Repeated agreement between request symptoms and GPU counters.
- Low marginal diagnostic utility.
- Request latency.
- Throughput.
- Queueing delay.
- GPU utilization.
- Memory utilization.
- Kernel duration.

Expected result:

- The strongest stopping signals may differ from the strongest escalation signals.

## Possible Experimental Setup

Target system:

- vLLM or another LLM serving stack on one GPU first.
- Optional later extension to multi-GPU or microservice deployment.

Evidence tiers:

| Tier | Evidence | Cost role |
|---|---|---|
| T0 | Request latency, throughput, queueing delay | Always on |
| T1 | GPU utilization, memory utilization, power, temperature | Cheap GPU evidence |
| T2 | SM occupancy, memory bandwidth, per-process GPU metrics | Medium-cost evidence |
| T3 | Runtime/kernel/profiler burst | Heavy evidence |

Pathologies:

- Queue pressure.
- Long input.
- Long output.
- KV-cache pressure.
- Host-side tokenization or launch overhead.
- GPU memory pressure.
- Thermal or power throttling if feasible.
- Mixed cases.
- Intermittent faults and temporary recovery cases.

Baselines:

- Fixed heavy-tracing window.
- Always-profile during anomaly.
- Budget-exhaustion tracing.
- Utilization-threshold only.
- Request-latency threshold only.
- Oracle stop.

Metrics:

- Top-1 diagnosis accuracy.
- Top-k diagnosis accuracy.
- Unknown or unresolved rate.
- Time-to-diagnosis.
- Heavy GPU tracing duration.
- Profiler volume.
- Budget used.
- Cost saved versus fixed-window tracing.
- Premature-stop rate.
- Re-escalation rate.
- Controller oscillation rate.
- Diagnosis quality per unit tracing cost.

## Most Defensible Novelty Claim

The strongest novelty claim is not "we invented GPU profiling" or "we invented adaptive tracing." The defensible claim is:

> Existing adaptive tracing systems decide which distributed traces to collect, and existing GPU profilers expose rich accelerator evidence. This work studies the missing control problem between them: how to allocate and stop costly GPU tracing actions under a runtime observability budget while preserving diagnosis quality.

## Suggested Paper Title Directions

- Budget-Aware Adaptive GPU Tracing for LLM Serving Diagnosis
- Knowing When to Stop GPU Tracing
- Evidence-Aware De-escalation for GPU Observability
- Adaptive GPU Tracing Under Observability Budgets
- Runtime Control of GPU Profiling for Cost-Aware Diagnosis
