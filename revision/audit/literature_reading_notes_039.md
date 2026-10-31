# Reading notes for steps 039–040 (full-text reads)

Working notes taken while reading each PDF in [litterature_review/papers/](../../litterature_review/papers/). Section references point into those PDFs. Condensed into [the related-work matrix](../related_work_matrix.md).

## StriaTrace — Wu et al., OSDI '26 (read pp.1–20 incl. appendix)
- Target: online LLM inference (vLLM), production Alibaba; H20 x8 testbed, Qwen3-Coder-30B FP8, PD disaggregated TP=8 (§6.1).
- Collection unit: CPU spans at sync barriers (O(10) sites, Table 2/5) + py-spy 10 ms sampling (§5.2.2) + GPU kernel/memcpy start/end via CUPTI only, no API tracing (§5.3.1).
- Activation: ALWAYS-ON lightweight tracing; "detailed tracing only during abnormalities" is implemented as anomaly-driven RETENTION: kernel traces for normal steps discarded, full-fidelity persisted only when step flagged outlier by roofline (§5.3.2); retention ≈1.6% of raw stream.
- Anomaly detection: empirical roofline = P99 linear regression latency vs #tokens per step (RANSAC), bootstrapped then periodically retrained (§5.4.1). R²=0.983.
- Stopping rule: none in our sense — no decision about when enough evidence has been collected; per-step retain/discard.
- Diagnosis: correlation: dominant span + py-spy stack + GIL state + kernel outliers (§5.4.2). Explicitly "not designed as a fully automated, end-to-end root-cause oracle ... rapid triage mechanism" (§6.4).
- Evaluation: overhead vs NSys/TProf/Scalene (Fig 9): NSys +34.3% median TPOT, +32.0% P99 at concurrency 8 on decode; TTFT NSys +4.7% median/+6.3% P99; TProf ~3x TTFT. Data rates Table 3 (NSys decode 1003.2 GiB/h).
- Detection eval: fault injection (SIGSTOP host stall; Numba SM-saturating kernels), 100% recall on injected faults (§6.3). No precision reported for that experiment; production ~7% false positives (§6.4).
- Production: 6 months, >1,700 instances, >180M req/day; 19 root causes Table 4 (hardware/config/code).
- Limitation stated: sustained degradations (e.g., CUDA Graph disabled, Case 8) evade roofline because baseline built on degraded state (§6.4). Low-frequency sampling may miss micro-stalls for sustained issues (§8).
- Relevance to us: (a) closest LLM-inference tracing system; establishes anomaly-triggered detailed evidence retention for vLLM -> we cannot claim novelty for anomaly-triggered GPU tracing; (b) quantifies Nsight overhead on vLLM -> supports why capture budget matters; (c) does NOT study stopping/sufficiency of captures, nor compare stopping rules; (d) workflow framing: SRE triage, reduce search space — good precedent for operator-workflow section; (e) their sustained-degradation limitation = our "persistent incident" case.
- Artifact availability: not stated in the paper text I read (no repo link found). Mark unknown.

## BPW "Diagnose Before You Compress" — Liu et al., arXiv 2608.00423 (Aug 2026, read all 14 pp)
- Problem: selecting a compact replay suite of workloads (from BurstGPT, ServeGen, Mooncake traces) that still provides bottleneck evidence for scheduler/prefill/decode/KV components. NOT runtime profiling.
- Key methodological points directly relevant to our circularity critique: "using predicted bottlenecks as target truth creates circular evaluation" (abstract); target truth defined ONLY from direct target-system measurements relative to a neutral anchor, threshold fixed before target evaluation (§4 Bottleneck Truth Verification, Eq.4–5); majority over 3 chronological restarts.
- Stopping: earliest prefix satisfying a quality gate (Macro-F1 ≥ ηM, worst-dim recall ≥ ηR, ≥2 direct witnesses per component across restarts, restart stability ≥ ηA) (Eq.6–7). This IS a stopping rule over evidence sufficiency — but over workload selection, not profiler captures.
- Non-compensatory evidence: evidence for one component cannot compensate for another (§1, §3).
- Setup: V100S 32GB, Qwen2-1.5B-Instruct, vLLM 0.6.6.post1, 2 configs, 24 requests/cell, 3 restarts (§5).
- Baselines: 16 "inspired" policies (response-blind ranking adaptations, not author code) (§5).
- Results: Table 2; +2.3% mean prefix Macro-F1, +16.3% WBRC-AUC on avg. Without direct verification 23.3/40.0/36.4% candidates had incorrect component incidences (Fig 4).
- Limitations noted by authors: stage interventions on fixed matrices = contribution analysis not causal (§5). No statistical tests reported in what I read; no CIs.
- Code: https://github.com/llmllmllm/BPW (abstract).
- Relevance: precedent for (1) prediction-independent reference labels from direct measurements, (2) non-compensatory per-component sufficiency (maps to overlapping causes), (3) "two-witness" requirement ~ our SS(K=2) idea but applied to evidence counts. Different problem (offline replay-suite selection), so complementary not competing.

## LatencyPrism — Du et al., arXiv 2601.09258v2 (Jan 2026), Alibaba Cloud (read all 15 pp)
- Target: production LLM inference, multi-XPU; eval on A100 + SGLang v0.5.4 + Qwen3-32B (§5.1); cross-stack check on vLLM v0.10.0 DeepSeek-R1-Distill-Llama-70B TP=4 (§5.2).
- Collection: ptrace-based Python frame hooks, NVTX insertion, eBPF, CUPTI/ROCm, NVML/SMI telemetry (§4.1.1). Non-intrusive (no restart).
- ACTIVATION = closest analogue to our two-tier design: "Sentinel Mode" (always-on, <0.5% CPU overhead, workload metadata + key events) and "Deep-Dive Mode" (~7% overhead) automatically triggered when residual exceeds a dynamic control limit; "dynamically triggers comprehensive collection (e.g., enabling Python Probes or GPU kernel Traces)" based on user-configured policies (§3.2.3).
- Trigger: GBDT baseline Latency=f(workload) on decode batches; Positive Prediction Error, moving average window W, UCL = min(mu+3sigma, theta_max) (§4.2.3, Eq.1).
- STOPPING of deep-dive: NOT specified in the paper — no rule for when to end comprehensive collection or how much to collect. (Searched full text; only "according to user configuration".)
- Detection eval: injected faults (CPU AVX-512, DVFS, GPU GEMM contention, clock lock, memory thrash, NVLink saturation, PCIe P2P disabled) (§4.2.3 list); Table 5: Dynamic-Window P=0.971 R=0.999 F1=0.985 FPR 0.59%; 20 trials heatmap (Fig 6).
- Diagnosis: exploratory downstream script, suspicion score |Δβ|×(|Zβ|+|Zlogμ|), adapted from PerfTracker (§5.3); Table 6 four faults. Authors say it is NOT a core built-in component.
- Limitation (§7): relies on historical normal data; "Pre-existing persistent performance issues may not trigger alerts due to the lack of a valid normal reference" — same failure as StriaTrace's sustained degradation.
- Artifact: https://github.com/kunluninsight/LatencyPrism (core logic, anomaly injection scripts, results).
- Relevance: (a) directly implements anomaly-triggered escalation from cheap to deep tracing for LLM serving -> our "two-tier escalation" is NOT novel; (b) leaves open how long/how much deep tracing is needed — the stopping question we study; (c) its anomaly-injection suite is a candidate source of controlled cases / comparator; (d) reports detection evaluation with injected faults whose labels = injection (same circularity class as ours, but for detection not diagnosis).

## TELLER — Xu, Li, Chen, Xie, ASE '26 (arXiv 2608.01975v1; DOI 10.1145/3832783.3837440) (read all 12 pp)
- SE venue (ASE '26) precedent: LLM-inference RCA framed as automated SE debugging (§1).
- Collection: NVTX hooks via import-time wrapping + CUPTI runtime/driver/kernel activity + stdout/stderr logs; launched through tracing wrapper (§3.2). Full collection during run; overhead +9.8% wall time, +8.8% CPU (Table 10).
- No activation/stopping policy: tracing runs for the collected request traces; compression (TPE) is post hoc for the RCA model (§3.5). Not adaptive collection.
- Diagnosis: GMM candidate localization + causal-context slice + TPE tokenizer + multimodal (trace+log) LM; outputs fault type, explanation, operator set (§3.4–3.7).
- Evaluation: 300 request traces, 5 settings (SGLang, Torch FSDP, vLLM v0, v1 offline/online), 2 nodes x 3 A40, Qwen3-8B (§4.1–4.2, Table 1). Faults INJECTED in 5 categories; labels = injection metadata (is_fault, fault_type) (§4.2).
- Validity statements worth citing: splits request-disjoint but run/injection can cross splits => "in-distribution estimates", run-disjoint eval future work (§4.2, §7); explanation audit "not independent, blinded expert validation" (§7); injected vs real faults threat (§7).
- Case study: real vLLM failure reported by AI21 Labs (Mamba SSM state contamination) (§6).
- Artifact: figshare doi:10.6084/m9.figshare.33142493.v1.
- Relevance: (a) SE-venue precedent that LLM-inference diagnosis is in scope for SE (answers reviewer B venue concern); (b) shows field norm — injected-fault labels with explicit threats; our design should do better (independent references) or at least match their threat disclosure; (c) not about collection cost/stopping; (d) compression–accuracy trade-off (Table 3) is analogous to our cost–evidence trade-off but over representation, not capture duration.

## ARGUS — Zhou et al. (Tencent), arXiv 2606.20374v2 (Jul 2026) (read all 17 pp incl. appendices)
- Target: LLM TRAINING at 10,000+ GPU scale (not serving); plans to generalize to inference serving (§10).
- Collection: ALWAYS-ON py-spy streaming stacks + CUDA-event framework semantics + CUPTI kernel activity; <2% overhead (§4, §8.2). KDE-clustered kernel summaries (count,p50,p99) compress 10 MB -> 2.7 KB per rank per step (~3,700x) (§5.2, Table 4).
- Explicit design position AGAINST triggered profiling: EROICA "triggers kernel-level profiling only after detecting anomalies, potentially missing critical windows of sporadic events" (§2.2); "fail-slow events are intermittent and unpredictable, requiring the system to operate always-on rather than relying on manual triggering or short-window sampling" (§2.1). => an argument our study must address: triggered capture can miss transient events.
- Diagnosis: L1 iteration jitter/change-point; L2 CV/z-score per parallel group; L3 Wasserstein-1 over reconstructed kernel CDFs + IQR fence; L4/L5 manual Perfetto/CPU-stack deep dive (§6, Table 2).
- Evaluation: overhead on 8-/32-GPU HunYuan-V3 Preview MoE training, 1,000 iterations: PyTorch Profiler +20–44% and OOM; nsys always-on failed (NaN at iter 10 on 8-GPU; hang in AllToAll on 32-GPU) (§8.2). Data volumes Table 4 (nsys 63.56 MB/rank/step).
- Fault diagnosis: 5 production case studies (§9); capability table (App. D) — no quantitative detection accuracy. Case 3: no automatic level alerted (manual Grafana inspection found it) — honest negative.
- Artifact: not stated in text read. Mark unknown.
- Relevance: (a) training not serving -> different workload regularity; (b) provides the counter-position (always-on summaries vs triggered heavy capture) that a stopping/triggering study must discuss; (c) evidence that nsys always-on is infeasible at scale (motivation for bounded capture).

## Beyond Microservices — Scheinert et al., arXiv 2603.02057v1 (Mar 2026) (read all 13 pp)
- EMPIRICAL STUDY precedent (not a new tool): evaluates 24 existing RCA methods (20 metric, 2 trace, 2 multi-source) on an LLM inference stack (K3s + Ray + vLLM, 8 VMs w/ A100 80GB; Falcon-H1-7B, DP=4) (§4.1, §4.3, §5.2).
- Fault injection: CPU hog, memory leak, network latency (ChaosMesh), GPU throttling (power 300->150W); single fault at a time; 10 injections per worker pod x 3 pods = 30/fault, 120 total (§4.3, §5.2). Load: Locust 5 QPS, 360 s, 512 prompt/256 output tokens.
- Metrics AC@k, Avg@k with random baseline AC@1≈1/6 (§5.1). Table 1.
- Findings: multi-source best; trace-based largely fail (misattribute to NGINX gateway); GPU throttling not visible in GPU utilization/memory metrics due to static allocations (§5.4) — relevant: cheap GPU counters can be uninformative (our RQ5/NT arm).
- Threats (§5.4): single faults only; excludes bugs/misconfigurations; fixed load pattern.
- Artifact: https://github.com/exalsius/rca-llm.
- Relevance: (a) methodological template for an EMPIRICAL study at an SE/systems boundary: compare many existing methods on controlled injections, report misattribution patterns, derive guidelines; (b) shows label = injection target is accepted when the question is localization of an injected component — but our diagnosis-class labels need stronger grounding; (c) supports our hypothesis that cheap GPU telemetry may miss some causes.

## Liu et al., "A First Look at Bugs in LLM Inference Engines", arXiv 2506.09713v2 (Jan 2026) (read all 34 pp)
- Empirical SE study, mines 5 engines (Llama.cpp, vLLM, DeepSpeed, Mlc-llm, TensorRT-llm) as of Dec 1, 2024 (§3).
- Selection: repository 'label:bug' (DeepSpeed: bug+inference), CLOSED issues only; then random sample per engine at 95% confidence / 5% interval (vLLM: 1200 potential -> 292 sampled -> 290 kept) (§3.2). => issues labelled only as performance/usage, not 'bug', are excluded by construction.
- Coding: open coding; pilot on 50% (465), reliability on remaining 464; Cohen's kappa 0.927 symptoms, 0.873 root causes, 0.8179 fix strategies; arbitrator; >500 person-hours (§3.3).
- Results relevant to us: 6 symptoms; Abnormal Performance (S4) = 53 bugs (~6%), all in inference/serving phase (Table 3); S4 has highest mean fix time 58.2 days, median 18.0 days (Table 6). Abnormal performance mainly due to Functionality and Configuration (Finding 14, Table 5). 28 root causes / 5 categories (Fig. 5).
- Threats (§10.4): 5 engines; GitHub-reported issues bias; manual coding bias; closed issues only.
- Dataset: https://github.com/infbug/bugs-in-LLM-inference-engines.
- Relevance: (a) direct method template for our Phase A (sampling, open coding, kappa, closed issues); (b) DIRECT OVERLAP RISK: a general taxonomy of LLM inference-engine bugs exists; our Phase A must not re-do it. Gap it leaves: performance issues are a small slice (53) selected via 'bug' label; it does not study what profiling evidence developers collected, how long, or whether captures were sufficient. Our Phase A should be scoped to performance issues + diagnostic-evidence practice, and can reuse/extend their public dataset for the S4 subset.

## Cao et al., "Understanding Performance Problems in Deep Learning Systems", ESEC/FSE '22 (arXiv 2112.01771v2) (read all 13 pp)
- Empirical SE study of 224 performance problems (PPs) from 210 StackOverflow posts (TensorFlow/Keras, posts from 2018-01-01 to 2021-03-01) (§2.2).
- Keyword derivation by iterative sampling of 'performance'-tagged posts until no new keyword (300 posts) (§2.2 Step 2); manual PP identification kappa 0.813; labeling kappas 0.906/0.772/0.847/0.928; ~6 person-months (§2.2–2.3).
- BENCHMARK BY REPRODUCTION (§2.4): sampled 112 PPs (50% per root-cause x symptom stratum), reproduced 58 (52%) with buggy AND fixed versions in Docker, ~4 person-months; failures due to incomplete snippets and hardware differences.
- RQ4 (§3.4, Table 1): TensorFlow Profiler applicable to only 15/58 (25.9%) PPs; of those, OOM during profiling for 9, no/false warning for 4, partially solved 2. => empirical precedent that profilers have limited capability in tackling real PPs.
- Root cause "established" from the fixed code in the accepted answer (§2.3) — i.e., reference = resolution, as in our plan.
- Threats (§4.3): TF/Keras only; StackOverflow only (GitHub suggested as future source); manual bias; small benchmark.
- Artifact: Zenodo doi:10.5281/zenodo.7060209.
- Relevance: (a) closest SE template for Phase A + Phase B combined (mine -> taxonomy -> reproduce buggy/fixed -> assess tools); (b) gives a realistic reproduction yield (~52%) and cost (4 person-months for 58) for planning Phase B; (c) "fixed version" as independent reference supports our reference design.

## Astraea — Toslali et al., "An Online Probabilistic Distributed Tracing System", arXiv 2405.15645v1 (May 2024) (read all 11 pp)
- Venue: the v1 text I read does not state a venue (search results say IC2E 2024; NOT verified from the PDF). Cite as arXiv v1 unless the IC2E version is obtained.
- Collection unit: span-level sampling probabilities on top of request-based sampling (microservices: Social network, Media, Train ticket; Jaeger) (§III, §IV-A).
- Formulation: cost-vs-utility trade-off as EXPLORATION vs EXPLOITATION; Bayesian beta beliefs per span; utility = latency variance (chosen empirically, Fig. 6); Approximate Bayesian Sampling (probability matching) with percentile threshold P (default 75th) and epsilon-exploration (default 5%) (§III-A,B).
- NOTE for our old paper: our ICSE related-work said Astraea "formalizes tracing as a cost-constrained online learning problem under a budget". The paper does not define an explicit budget constraint; it is an exploration/exploitation formulation with knobs (P, epsilon). The budget wording must be corrected. (Log2 baseline is the one with a budget parameter, §IV-C.)
- Stopping: no stopping rule; continuous online adaptation; reports samples to reach 90% confidence (~200–700 samples, Table I).
- Evaluation: injected delays (sleep in code) and Pumba CPU/memory stress; oracle = faulty spans capturing injected anomalies (§IV-A); 20 runs/app; Top-5 accuracy 92%, ~24.7% instrumentation (§IV-B); vs Log2 and VAIF (§IV-C); sensitivity analysis on P, epsilon, sampling rate (§IV-D, Fig. 11); 8 case studies, 7 naturally present, 1 injected (§V, Table I).
- Relevance: (a) closest in-spirit precedent for a cost/utility learning approach to evidence collection — reviewer C asked "why not learned/adaptive stopping"; (b) includes sensitivity analysis of its knobs (model for our RQ4); (c) not GPU, not stopping of heavy captures.

## TraStrainer — Huang et al., Proc. ACM Softw. Eng. 1(FSE), Article 22, 2024, doi:10.1145/3643748 (read all 21 pp)
- Online TAIL-BASED biased trace sampler for microservices combining system-runtime-state bias (DLinear forecast of each metric -> anomaly degree -> preference vector) and diversity bias (clustering in a look-back window) via a dynamic AND/OR voting mechanism that tracks an explicit BUDGET sampling rate β (§2.3 Eq.1, §4.2–4.5, Fig. 7).
- NOTE for our old paper: our ICSE text said TraStrainer uses "CPU and memory pressure" as runtime state. The paper uses general system metrics (121 metrics in dataset A, 32 in B; CPU usage, SQL connection time etc. as examples) (Table 1, §4.1). Wording should be "system runtime metrics". Also: the explicit budget formalism is in TraStrainer (β), not Astraea.
- Evaluation: Dataset A = 13 Huawei production microservice systems, 62 incidents Apr–Aug 2023, 909,797 traces, labels by SREs/experts (2.5% label rate); Dataset B = OnlineBoutique + TrainTicket with 56 Chaosblade-injected faults, labels from injection positions (Table 1, §5.1). Baselines Random, HC, Sifter, Sieve (§5.2). Downstream RCA (TraceAnomaly, TraceRCA, MicroRank) A@1/A@3/MRR at budgets 0.1/1/2.5% (Table 3). Ablations w/oM, w/oD (§5.6).
- Threats (§7): baseline reimplementations (HC, Sifter); 10% warm-up; only 7 fault types.
- Artifact: https://github.com/IntelligentDDS/TraStrainer.
- Relevance: (a) shows SE-venue (FSE) acceptance of evidence-collection policy evaluated by DOWNSTREAM diagnosis quality — the right evaluation lens for our study (judge a stopping rule by what the downstream diagnosis can conclude from the retained evidence); (b) mixes expert-labelled production incidents with injected benchmark faults — a model for our reproduced-issue + controlled-case design; (c) budget-sweep evaluation (0.1–10%) = analogue of our FIX(n) sweep.

## Hindsight — Zhang, Xie, Anand, Vigfusson, Mace, "The Benefit of Hindsight: Tracing Edge-Cases in Distributed Systems", arXiv 2202.05769 (read all 18 pp)
- Venue: the arXiv PDF does not print a venue; TraStrainer's reference list (which I read) cites it as NSDI '23, pp. 321–339. Our bib entry (year 2021, DOI 10.1145/3472883.3486986) is inconsistent with that and must be fixed; Tprof (SoCC '21) has DOI 10.1145/3472883.3486994 per TraStrainer refs, so 3472883.* is a SoCC '21 DOI prefix — our DOI is very likely a wrong SoCC paper.
- Mechanism: RETROACTIVE SAMPLING — generate all trace data into local memory buffers on every node, ingest lazily only when a programmatic trigger fires (error, percentile latency, rare category, queue latency + lateral traces); breadcrumbs reconstruct the request path (§3–§5). "Event horizon" = time before local data is overwritten (§3, §6.2, §7.3): e.g., 10 MB pool: 500 ms trigger delay -> 58% coherent; default 1 GB ≈ 1 minute horizon.
- Key insight relevant to us (§3): "once we observe symptoms, it is too late to just enable tracing from that point on, as we have already missed the events that led to the anomaly" — the classic argument against triggered (start-after-symptom) capture. Our design captures AFTER suspicion; we must state that pre-onset evidence is unavailable unless a ring buffer is kept, and that this limits diagnosis of transient causes.
- Evaluation: Alibaba-derived 93-service MicroBricks topology, DSB social network, HDFS; head vs tail vs Hindsight; edge-case capture 99–100%, <3.5% throughput impact (§6.1, Fig. 3); use cases UC1–UC3 (§6.3).
- Scope: application-level distributed tracing; cross-layer/GPU not addressed (§7.2).
- Relevance: (a) principal counter-design to "start heavy capture on suspicion": always-generate + retroactive retrieval. For GPU, the analogue would be a continuous ring-buffer of kernel events (cf. ARGUS/StriaTrace always-on CUPTI). Our study should include or at least discuss a "retroactive window" comparator; (b) old ICSE paper cited Hindsight as "runtime-adaptive evidence escalation" — accurate only loosely; it is retroactive retrieval triggered by symptoms, not escalation of collection detail.

## Pivot Tracing — Mace, Roelke, Fonseca, SOSP '15 (author PDF, cs.brown.edu) (read main text pp.1–13 in full; reference list pp.13–16 skimmed)
- Venue confirmed from PDF: SOSP'15, October 4–7, 2015, Monterey, CA (p.1). Our bib entry's URL points to an ATC'16 presentation page — should be fixed to the SOSP'15 paper (DOI printed on p.1 is garbled in extraction; obtain from ACM).
- Mechanism: dynamic instrumentation (runtime-installed tracepoints/advice, zero cost when inactive) + causal metadata propagation ("baggage") enabling the happened-before join across process/machine boundaries; LINQ-like queries (§2–§5).
- Adaptivity = OPERATOR-DRIVEN: users install/uninstall queries at runtime; no automatic activation or stopping policy. Authors leave "automatic problem detection and exploration" to future work (§8).
- Evaluation: Hadoop stack (HDFS, HBase, MapReduce, YARN) on 8-node cluster; case studies: HDFS replica-selection bug (HDFS-6268), network limplock, GC, NameNode lock (§6.1–6.2); overhead ≤0.3% enabled, up to 15.9% when propagating 60 tuples for short CPU-bound Open (Table 5).
- Relevance: (a) precedent that the INFORMATION to collect should be chosen at runtime rather than a priori (the "recall vs overhead" trade-off, §2.3); (b) our old paper cited it as "runtime-adaptive evidence escalation" — fair only in the sense of runtime-chosen instrumentation; it does not automate escalation/de-escalation; (c) diagnosis via iterative operator queries = a human-in-the-loop workflow model for our operator section.

## Zhou, Anderson, Meng, Mellor-Crummey, "Low Overhead and Context Sensitive Profiling of GPU-accelerated Applications", ICS '22, doi:10.1145/3524059.3532388 (read all 13 pp) — named by Reviewer B
- Problem: overhead of attributing GPU metrics (coarse-grained ops; fine-grained PC/instruction samples) to full CPU+GPU calling contexts (§1–3). Tool = HPCToolkit-E.
- Two mechanisms: (1) call-path MEMOIZATION keyed on ⟨stack height, binary id, function id, previous-op trace⟩ with stochastic backoff unwinding U (default 1/4) (§4); (2) EPOCH-BASED PC-sample collection: fixed epochs (N kernels) or ADAPTIVE epochs that end when a kernel is launched from a conflicting call path (§5.2–5.3).
- "Adaptive epoch sampling" (§5.3): because "GPU kernels are often repeatedly launched with similar or patterned behaviors", already-seen kernel sequences (tracked in a call-path trie, §5.4) are profiled only with random enabling rate E (6% "high", 0.8% "low"); samples are scaled by sampled/total invocation ratios (§5.5). New sequences always start profiling.
- Accuracy reference = serialized full profiling (HPCToolkit) via sum of attribution-percentage differences (Eq. 1); call-path ground truth = full unwind at every op (§6.1). Results: coarse overhead 1.42x vs 2.08x HPCToolkit / 2.76x Nsight Systems (Fig 11); fine-grained 4.61x vs 27.51x serialized, accuracy 96.16% (Table 2, §6.2). Nsight Compute 14400x on Laghos (§6.2).
- Workloads: 9 HPC/ML apps incl. PyTorch ResNet-50 and PyG on one A100 (§6). Whole-run offline profiling; no anomaly trigger, no diagnosis target, no serving workload.
- Limitations (§8): accuracy/overhead trade-off can't always be had; CUPTI continuous PC-sampling issues (buffer overflow; forced sync every 512 kernels for LAMMPS).
- Relevance / overlap assessment:
  (a) It is "adaptive" in WHEN TO SYNCHRONIZE/FLUSH and in SKIPPING REPEATED KERNEL SEQUENCES with probabilistic re-enabling — conceptually close to our premise that repeated evidence adds little (our SS stop on repetition). Must cite as prior art for "repetition ⇒ reduce collection" in GPU profiling.
  (b) It does NOT: trigger on anomalies, decide that evidence is sufficient for a DIAGNOSIS, stop a capture session, evaluate against diagnosis references, or target LLM serving. Its correctness criterion is profile-attribution fidelity vs a full serialized profile — a useful precedent for our "full-horizon reference capture" comparator and for measuring retained-evidence fidelity as % deviation from the full profile.
  (c) Reviewer B's suggestion stands: it is a GPU-profiling cost-reduction strategy that must be discussed and, ideally, its "skip repeated sequences with rate E" policy treated as a comparator (e.g., a capture policy that samples repeated windows probabilistically rather than stopping).

## Darvishi, Noferesti, Ezzati-Jivan, "Toward Adaptive Tracing: Efficient System Behavior Analysis using Language Models", ICSE-NIER '24, pp. 62–66, doi:10.1145/3639476.3639778 (read all 5 pp)
- SE VENUE (ICSE NIER) precedent for "adaptive tracing": trace a limited event set normally; when a "significant behavioral shift" is detected, enable detailed/focused tracing around the potential root cause and store it for later manual analysis (§3, Fig 1).
- Detection: LSTM/BERT multi-task LM over LTTng kernel system-call sequences + binned durations; cross-entropy loss rescaled by MAD as change score (§3.1–3.4). RCA: cosine similarity of error vectors to pre-clustered tagged centroids (§3.5).
- Stopping rule: NOT specified (when detailed tracing ends is not defined in the paper). Budget: not defined; cites Pythia's instrumentation budget [1] (§2).
- Evaluation (preliminary, §4): Apache2 web server traces from Fournier et al. [8] + their own bandwidth-limited "duration" noise set; 7 noise categories; scenarios 0–50% noisy events. 77.1% fewer recorded events, 5.8% miss rate of change-related events; noise-type (root cause) identification 91.3%, up to 20.9% better than event-sequence-only model; detection latency 106 ms (LSTM) / 151 ms (BERT) on V100. Labels = injected noise categories.
- NOTE: search-result summaries quoted 92.7% and 20.4%; the PDF says 91.3% and 20.9%. Use the PDF numbers.
- Future work (§5): recurring abnormalities should be learned as normal, else tracing cost approaches always-on — the recurrence problem our study's lull/recurrence case targets.
- Artifact: zenodo.org/records/10437041.
- Relevance: (a) an ICSE paper already proposes "adaptive tracing = cheap normally, detailed on change" — further confirms the escalation mechanism is not novel, and shows the SE community accepts this problem; (b) it evaluates reduction (77.1%) and miss rate (5.8%) — i.e., cost vs evidence retained — but with injected-noise labels and no stopping rule; (c) its open problem (recurring abnormalities; how long to trace) aligns with our RQ3.
- New leads from its §2: Pythia (Ates et al., SoCC '19) "instrumentation budget"; Zhang et al. 2020 adaptive instrumentation (ICCCI). Not read.

## Darche & Dagenais, "Low-Overhead Trace Collection and Profiling on GPU Compute Kernels", ACM Trans. Parallel Comput. 11(2), Article 9, June 2024, doi:10.1145/3649510 (read all 24 pp incl. appendices)
- VENUE CORRECTION: ACM Transactions on Parallel Computing (TOPC), not TACO (p.1 reference format). Our bib `darche2024lowoverhead` says "ACM Transactions on Architecture and Code Optimization" — wrong.
- What it is: DEVICE-SIDE instrumentation of GPU compute kernels (LLVM IR pass, HIP/AMD MI100, ROCm 5.6) to trace events INSIDE kernels (basic-block timestamps, wavefront state/EXEC mask, memory addresses) (§3, Table 1). Two-pass method: a counters run records per-thread basic-block counts so the tracing run can pre-allocate exact per-producer buffers without atomics (§3.2–3.3, Eq. 1–2). "Replayer" mode for non-copyable state (§4.6).
- Results: Rodinia kernels — tracing kernel overhead mean 1.50x / median 1.29x with GCN-asm events (Table 2); whole-app mean 1.60x vs CUDA-Flux numbers reported in its paper (Table 3; authors note cross-device comparison caveat §4.2); large memory overhead (Table 4); case studies hash table, Quicksilver (§4.5–4.6).
- Target use: "short, self-contained programs designed to fine-tune the behavior of compute kernels" (§4.3); "does not scale as well as lighter PC-sampling approaches ... preferably focused on the tuning process of the kernel in a rather small program" (§5.1). No activation/stopping policy; not for production/serving; no anomaly detection.
- Future work: circular-buffer GPU tracing (§5.2).
- Artifact: github.com/dorsal-lab/hip-analyzer (+ TraceCompassGpu plugin).
- NOTE for our old paper: 03_methodology says nsys is "the same class of low-overhead GPU kernel tracing studied by Darche and Dagenais". Inaccurate: Darche instruments kernel internals on AMD devices via a compiler pass; nsys records kernel-level activity via CUPTI on NVIDIA. Different collection unit and platform. Either drop the citation or cite it only as an example of the fine-grained/heavy end of the GPU evidence spectrum and of instrumentation-noise concerns (§1, §5.1).
- Relevance to the stopping question: none directly (no collection policy). Useful only for the "observer effect / instrumentation noise" argument (§1 "Reducing the runtime overhead is of high interest to mitigate measurement noise").
