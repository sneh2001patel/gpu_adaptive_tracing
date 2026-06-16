# Literature Review: Adaptive Tracing, GPU Tracing, and Budget-Aware GPU Observability

## Scope

This review collects 20 research papers that can support a new direction on budget-aware adaptive GPU tracing. The exact topic "adaptive tracing on GPUs" appears to be underexplored as a single established area, so the papers are grouped into three connected bodies of work:

1. Adaptive and cost-aware distributed tracing.
2. GPU tracing, profiling, and low-overhead instrumentation.
3. GPU-heavy LLM serving systems where utilization, memory, queueing, and profiling evidence matter.

The research gap is to combine these areas: use cheap GPU resource signals continuously, selectively escalate to richer GPU traces under a tracing budget, and de-escalate when enough diagnostic evidence has been collected.

## Candidate Research Questions

- RQ1: Can low-cost GPU utilization signals determine when richer GPU tracing is necessary?
- RQ2: Can an adaptive GPU tracing controller determine when heavy tracing has collected sufficient diagnostic evidence?
- RQ3: Can adaptive GPU trace de-escalation distinguish between true fault recovery and temporary symptom reduction?
- RQ4: Which runtime signals are most useful for deciding when to de-escalate heavy GPU tracing?
- RQ5: How should a limited GPU tracing budget be allocated across counters, per-process metrics, kernel traces, and profiler bursts?

## Paper List

### 1. Dapper, a Large-Scale Distributed Systems Tracing Infrastructure

- Authors: Benjamin H. Sigelman, Luiz A. Barroso, Mike Burrows, Pat Stephenson, Manoj Plakal, Donald Beaver, Saul Jaspan, Chandan Shanbhag.
- Year: 2010.
- Link: [Google Research](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)
- Category: General distributed tracing.
- Main idea: Dapper introduced a production-scale tracing infrastructure for large distributed systems with low overhead and broad deployment.
- Relevance: Provides the baseline motivation for tracing as always-on production observability. For GPU tracing, it motivates keeping low-cost evidence always available while avoiding full heavy tracing by default.

### 2. X-Trace: A Pervasive Network Tracing Framework

- Authors: Rodrigo Fonseca, George Porter, Randy H. Katz, Scott Shenker, Ion Stoica.
- Year: 2007.
- Link: [USENIX](https://www.usenix.org/conference/nsdi-07/x-trace-pervasive-network-tracing-framework)
- Category: End-to-end tracing.
- Main idea: X-Trace propagates tracing metadata across layers to reconstruct a comprehensive view of distributed service behavior.
- Relevance: Useful for GPU-aware distributed tracing because GPU spans must be connected back to request paths, not interpreted as isolated device-level events.

### 3. Pivot Tracing: Dynamic Causal Monitoring for Distributed Systems

- Authors: Jonathan Mace, Ryan Roelke, Rodrigo Fonseca.
- Year: 2015.
- Link: [USENIX](https://www.usenix.org/conference/atc16/technical-sessions/presentation/mace)
- Category: Dynamic instrumentation and causal monitoring.
- Main idea: Pivot Tracing lets operators install runtime monitoring queries and correlate events across distributed components using happened-before relationships.
- Relevance: Strong conceptual precedent for adaptive GPU tracing: richer instrumentation can be installed dynamically when cheap evidence is insufficient.

### 4. Canopy: An End-to-End Performance Tracing and Analysis System

- Authors: Jonathan Kaldor, Jonathan Mace, Michael Bejda, Edison Gao, Joe O'Neill, Kian Win Ong, Bill Schaller, Pingjia Shan, Brendan Viscomi, Vinod Venkataraman, Kaushik Veeraraghavan, Yee Jiun Song.
- Year: 2017.
- Link: [Facebook Research](https://research.facebook.com/publications/canopy-end-to-end-performance-tracing-at-scale/)
- Category: Production tracing infrastructure.
- Main idea: Canopy records causally related performance data across client, mobile, web, and backend services at Facebook scale.
- Relevance: Shows how tracing infrastructure can serve many performance questions. A GPU extension would need similar cross-layer aggregation from request to accelerator.

### 5. The Benefit of Hindsight: Tracing Edge-Cases in Distributed Systems

- Authors: Lei Zhang, Zhiqiang Xie, Vaastav Anand, Ymir Vigfusson, Jonathan Mace.
- Year: 2023.
- Link: [USENIX NSDI](https://www.usenix.org/conference/nsdi23/presentation/zhang-lei)
- Category: Retroactive and adaptive tracing.
- Main idea: Hindsight lazily retrieves trace data after symptoms such as high tail latency, errors, or bottlenecked queues are detected.
- Relevance: Directly supports budget-aware escalation. GPU tracing could similarly buffer or retain cheap GPU evidence and only retrieve richer evidence after suspicious symptoms appear.

### 6. Sifter: Scalable Sampling for Distributed Traces, without Feature Engineering

- Authors: Pedro Las-Casas, Giorgi Papakerashvili, Vaastav Anand, Jonathan Mace.
- Year: 2019.
- Link: [Microsoft Research](https://www.microsoft.com/en-us/research/publication/sifter-scalable-sampling-for-distributed-traces-without-feature-engineering/)
- Category: Biased trace sampling.
- Main idea: Sifter biases sampling toward unusual traces, infrequent request types, and anomalous executions using an online model of common behavior.
- Relevance: Useful for deciding which GPU-affected requests deserve richer traces. The GPU version could bias profiling toward unusual utilization or memory-pressure windows.

### 7. TraStrainer: Adaptive Sampling for Distributed Traces with System Runtime State

- Authors: Haiyu Huang, Xiaoyu Zhang, Pengfei Chen, Zilong He, Zhiming Chen, Guangba Yu, Hongyang Chen, Chen Sun.
- Year: 2024.
- Link: [ESEC/FSE 2024](https://2024.esec-fse.org/details/fse-2024-research-papers/48/TraStrainer-Adaptive-Sampling-for-Distributed-Traces-with-System-Runtime-State)
- Category: Adaptive trace sampling.
- Main idea: TraStrainer combines trace diversity with system runtime state to improve online sampling decisions.
- Relevance: Very close to the proposed direction. For GPUs, runtime state could include utilization, memory pressure, power, queueing delay, and thermal signals.

### 8. TraceMesh: Scalable and Streaming Sampling for Distributed Traces

- Authors: Zhuangbin Chen, Zhihan Jiang, Yuxin Su, Michael R. Lyu, Zibin Zheng.
- Year: 2024.
- Link: [arXiv](https://arxiv.org/abs/2406.06975)
- Category: Streaming trace sampling.
- Main idea: TraceMesh uses locality-sensitive hashing and evolving clustering to sample high-dimensional trace streams efficiently.
- Relevance: GPU-aware traces may add high-dimensional features. TraceMesh suggests methods for keeping sampling practical when traces include GPU counters and profiler-derived features.

### 9. An Online Probabilistic Distributed Tracing System

- Authors: M. Toslali, S. Qasim, S. Parthasarathy, F. A. Oliveira, H. Huang, G. Stringhini, Z. Liu, A. K. Coskun.
- Year: 2024.
- Link: [arXiv](https://arxiv.org/abs/2405.15645)
- Category: Cost-aware probabilistic tracing.
- Main idea: Astraea uses online Bayesian learning and multi-armed bandits to steer tracing toward useful instrumentation under cost constraints.
- Relevance: This is one of the strongest budget models for the new topic. GPU tracing actions can be treated as arms with different costs and diagnostic utilities.

### 10. Mint: Cost-Efficient Tracing with All Requests Collection via Commonality and Variability Analysis

- Authors: Haiyu Huang, Cheng Chen, Kunyi Chen, Pengfei Chen, Guangba Yu, Zilong He, Yilun Wang, Huxing Zhang, Qi Zhou.
- Year: 2024.
- Link: [arXiv](https://arxiv.org/abs/2411.04605)
- Category: Cost-efficient tracing.
- Main idea: Mint reduces trace storage and network overhead by separating common trace patterns from variable request-specific data.
- Relevance: Provides an alternative to pure sampling. GPU traces may also contain repeated common patterns where only variable GPU counters or kernel features need to be retained.

### 11. Tracezip: Efficient Distributed Tracing via Trace Compression

- Authors: Zhuangbin Chen, Junsong Pu, Zibin Zheng.
- Year: 2025.
- Link: [arXiv](https://arxiv.org/abs/2502.06318)
- Category: Trace compression.
- Main idea: Tracezip reduces distributed tracing overhead by exploiting redundancy in trace spans and reconstructing full traces from compressed forms.
- Relevance: Relevant to GPU tracing because profiler and kernel traces can be large. Compression can be part of the tracing budget model alongside sampling and de-escalation.

### 12. 3MileBeach: A Tracer with Teeth

- Authors: Jun Zhang, Robert Ferydouni, Aldrin Montana, Daniel Bittman, Peter Alvaro.
- Year: 2021.
- Link: [ACM Digital Library](https://dl.acm.org/doi/10.1145/3472883.3486986)
- Category: Low-overhead tracing and fault injection.
- Main idea: 3MileBeach provides message-level distributed tracing and fault injection for microservices with reduced overhead.
- Relevance: Useful for experiment design. GPU tracing research may need controlled fault injection or workload perturbation to evaluate whether adaptive tracing finds the right bottleneck.

### 13. NVBit: A Dynamic Binary Instrumentation Framework for NVIDIA GPUs

- Authors: Oreste Villa, Mark Stephenson, David Nellans, Stephen W. Keckler.
- Year: 2019.
- Link: [NVIDIA Research](https://research.nvidia.com/publication/2019-10_nvbit-dynamic-binary-instrumentation-framework-nvidia-gpus)
- Category: GPU dynamic instrumentation.
- Main idea: NVBit enables dynamic binary instrumentation for NVIDIA GPU binaries and libraries.
- Relevance: Key GPU-side mechanism for heavy tracing. It motivates a high-cost tracing tier for instruction, memory, or kernel-level evidence.

### 14. Low-Overhead Trace Collection and Profiling on GPU Compute Kernels

- Authors: Sebastien Darche, Michel R. Dagenais.
- Year: 2024.
- Link: [ACM Digital Library](https://dl.acm.org/doi/10.1145/3649510)
- Category: GPU tracing overhead reduction.
- Main idea: The paper proposes a lower-overhead method for collecting traces while GPU compute kernels execute.
- Relevance: Directly relevant to budget-aware GPU tracing because it studies the cost of collecting GPU traces and how to reduce tracing overhead.

### 15. Measurement and Analysis of GPU-accelerated Applications with HPCToolkit

- Authors: Keren Zhou, Laksono Adhianto, Jonathon Anderson, Aaron Cherian, Dejan Grubisic, Mark Krentel, Yumeng Liu, Xiaozhu Meng, John Mellor-Crummey.
- Year: 2021.
- Link: [arXiv](https://arxiv.org/abs/2109.06931)
- Category: GPU performance measurement.
- Main idea: HPCToolkit attributes CPU and GPU performance measurements to calling contexts and supports profiling, tracing, PC sampling, and hardware counters.
- Relevance: Gives a practical map of GPU evidence tiers: counters, kernel timing, PC sampling, traces, and source-level attribution.

### 16. Tools for Top-Down Performance Analysis of GPU-Accelerated Applications

- Authors: Keren Zhou, Mark W. Krentel, John Mellor-Crummey.
- Year: 2020.
- Link: [ACM Digital Library](https://dl.acm.org/doi/10.1145/3392717.3392752)
- Category: GPU performance analysis.
- Main idea: Extends HPCToolkit for top-down performance analysis of GPU-accelerated applications.
- Relevance: Useful for identifying which runtime signals are diagnostic: CPU-GPU calling context, kernel behavior, memory behavior, and hierarchical execution dynamics.

### 17. DrGPU: A Top-Down Profiler for GPU

- Authors: Yueming Hao, Neha Jain, Rob F. Van der Wijngaart, Nitin Saxena, Yifan Fan, Xipeng Liu.
- Year: 2023.
- Link: [SPEC ICPE Proceedings PDF](https://research.spec.org/icpe_proceedings/2023/proceedings/p43.pdf)
- Category: GPU profiling.
- Main idea: DrGPU applies top-down performance analysis ideas to GPU profiling.
- Relevance: Helps define possible diagnosis categories for GPU utilization tracing, such as compute saturation, memory stalls, synchronization, and underutilization.

### 18. Efficient Memory Management for Large Language Model Serving with PagedAttention

- Authors: Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph E. Gonzalez, Hao Zhang, Ion Stoica.
- Year: 2023.
- Link: [arXiv](https://arxiv.org/abs/2309.06180)
- Category: GPU-heavy LLM serving.
- Main idea: vLLM uses PagedAttention to reduce KV-cache memory waste and improve LLM serving throughput.
- Relevance: Provides a concrete target workload where GPU memory utilization, KV-cache pressure, and request latency interact. This is a strong benchmark candidate for adaptive GPU tracing.

### 19. Orca: A Distributed Serving System for Transformer-Based Generative Models

- Authors: Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, Byung-Gon Chun.
- Year: 2022.
- Link: [USENIX OSDI](https://www.usenix.org/conference/osdi22/presentation/yu)
- Category: LLM serving scheduling.
- Main idea: Orca proposes iteration-level scheduling and selective batching for transformer-based generative model serving.
- Relevance: GPU utilization symptoms in LLM serving often arise from batching and scheduling decisions. This paper helps connect request-level tracing to GPU execution behavior.

### 20. SARATHI: Efficient LLM Inference by Piggybacking Decodes with Chunked Prefills

- Authors: Amey Agrawal, Ashish Panwar, Jayashree Mohan, Nipun Kwatra, Bhargav S. Gulavani, Ramachandran Ramjee.
- Year: 2023.
- Link: [arXiv](https://arxiv.org/abs/2308.16369)
- Category: LLM inference scheduling and GPU utilization.
- Main idea: SARATHI improves inference efficiency by chunking prefills and piggybacking decode requests to improve GPU utilization.
- Relevance: Useful for studying whether GPU utilization changes represent true recovery, temporary workload-shape changes, or scheduling effects.

## Synthesis for a New Paper Direction

The literature suggests a clear opening:

- Distributed tracing work has strong methods for sampling, retroactive tracing, dynamic instrumentation, cost control, and trace compression.
- GPU profiling work has strong mechanisms for measuring utilization, memory behavior, kernel behavior, and CPU-GPU attribution.
- LLM serving work has realistic GPU bottlenecks involving queueing, batching, prefill, decode, KV cache pressure, and utilization instability.

What is missing is a controller that joins these ideas into one budget-aware GPU tracing lifecycle:

1. Always collect cheap request and GPU utilization evidence.
2. Escalate to richer GPU metrics only when cheap evidence cannot support a diagnosis.
3. Spend profiler budget only on ambiguous or high-risk windows.
4. Stop heavy GPU tracing when diagnosis confidence stabilizes or marginal utility drops.
5. Avoid premature stopping by checking whether recovery is stable across multiple windows.

## Most Relevant Papers for Immediate Reading

Start with these five:

1. TraStrainer.
2. Hindsight.
3. Astraea.
4. NVBit.
5. vLLM/PagedAttention.

Together they cover adaptive sampling, retroactive evidence acquisition, budget-aware instrumentation, GPU tracing mechanisms, and a realistic GPU-heavy target system.
