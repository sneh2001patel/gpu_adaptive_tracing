# Related-work matrix (primary sources)

Date: 2026-10-28. Status: steps 039–040, CPU-only literature steps. Every entry below comes from reading the full text of the paper's PDF, stored in [litterature_review/papers/](../litterature_review/papers/). [Sources](../litterature_review/papers/README.md) lists the provenance of each PDF. Sections are cited as they appear in the PDF read. Where a paper does not state something, the cell says "not stated" rather than inferring absence. Abstracts, search snippets and secondary summaries were used only to locate PDFs, never as evidence.

Step 040 added the three ACM papers the author supplied: Zhou et al. ICS '22, Darvishi et al. ICSE-NIER '24 and Darche & Dagenais TOPC '24. 16 papers are now read in full.

**Not yet read — no claims made about these:**

| Paper | Reason |
|---|---|
| NVBit (Villa et al., MICRO '19), DrGPU, top-down GPU analysis (Zhou et al., ICS '20), Dapper, X-Trace, Canopy, Sifter, Sieve, vLLM, Orca, Sarathi (all cited in the draft) | Lower priority for the stopping question |
| Pythia (Ates et al., SoCC '19; "instrumentation budget") and Zhang et al. 2020 (ICCCI; adaptive instrumentation) | New leads cited in Darvishi et al. §2; not yet obtained |

## 1. Matrix

Notation: "LLM inf." = LLM inference serving.

| Work (venue as verified) | Domain | Collection unit | Activation rule | Stopping / retention rule | Budget | Diagnostic target | Validation and reference | Artifact |
|---|---|---|---|---|---|---|---|---|
| **StriaTrace** (OSDI '26) | LLM inf. (vLLM, production) | CPU spans at sync barriers; py-spy 10 ms; CUPTI kernel and memcpy intervals only (§5.2–5.3) | Always-on lightweight tracing | Per-step retain/discard: full kernel traces kept only for roofline outliers, ≈1.6% of raw stream (§5.3.2); no capture-sufficiency rule | Not stated as a parameter | Long-tail step latency; triage to rank, phase, code (§5.4.2, §6.4) | Overhead vs NSys/TProf/Scalene (Fig 9, Table 3); injected SIGSTOP and SM-contention faults, 100% recall (§6.3); 19 production root causes (Table 4); ≈7% false positives in production (§6.4) | Not stated |
| **LatencyPrism** (arXiv 2601.09258v2) | LLM inf. (SGLang; vLLM check) | ptrace Python hooks, NVTX, eBPF, CUPTI, NVML (§4.1) | Sentinel mode always-on; deep-dive tracing triggered when residual > dynamic UCL (§3.2.3, §4.2.3) | Not stated (deep-dive per "user-configured policies") | Overhead: sentinel <0.5% CPU, deep ≈7% (§1) | Decode-step latency anomalies; exploratory RCA script (§5.3) | Injected faults (CPU, GPU contention or clock lock, memory, NVLink, PCIe); P 0.971, R 0.999 (Table 5) | github.com/kunluninsight/LatencyPrism |
| **TELLER** (ASE '26; arXiv 2608.01975v1) | LLM inf. (vLLM, SGLang, FSDP) | NVTX + CUPTI runtime/driver/kernel + logs (§3.2) | Tracing during the runs collected | None (post-hoc compression, TPE) | None | Abnormal step, operator set, explanation (§2.3) | 300 request traces, injected faults in 5 categories; labels = injection metadata (§4.2); in-distribution splits acknowledged (§7) | figshare 10.6084/m9.figshare.33142493.v1 |
| **ARGUS** (arXiv 2606.20374v2) | LLM *training*, 10k+ GPUs | py-spy, CUDA-event phases, CUPTI kernels; KDE summaries (§4–5) | Always-on; argues against post-anomaly triggering (§2.1–2.2) | Tiered: summaries online, full Perfetto to object storage (§5.1) | <2% overhead target (§8.2) | Fail-slow stragglers and kernels (§6) | Overhead on 8/32 GPU (nsys always-on failed, §8.2); 5 production case studies (§9) | Not stated |
| **BPW** "Diagnose Before You Compress" (arXiv 2608.00423) | LLM serving *replay-suite selection* (offline) | Workload replays on vLLM | n/a | Earliest prefix meeting a quality gate: ≥2 direct witnesses per component across restarts, Macro-F1 and worst-recall thresholds (Eq. 6–7) | Replay GPU seconds, compared only among feasible prefixes (§3–4) | Scheduler, prefill, decode, KV bottleneck evidence | Prediction-independent labels from direct target measurements vs a neutral anchor, thresholds fixed before evaluation (§4, Eq. 4–5); 16 adapted baselines (§5) | github.com/llmllmllm/BPW |
| **Beyond Microservices** (arXiv 2603.02057v1) | LLM inf. on K8s + Ray + vLLM | Prometheus, logs, DeepFlow eBPF traces (§4.2) | n/a (evaluation study) | n/a | n/a | Root-cause pod among 6 | Empirical study of 24 RCA methods; 120 single-fault injections; AC@k (§5); GPU throttling invisible to utilization metrics (§5.4) | github.com/exalsius/rca-llm |
| **Liu et al.**, bugs in LLM inference engines (arXiv 2506.09713v2) | 5 inference engines | GitHub issues labelled "bug", closed only, sampled 95%/5% (§3.2) | n/a | n/a | n/a | Symptom and root-cause taxonomy | Open coding; κ 0.927 / 0.873 / 0.8179 (§3.3); Abnormal Performance = 53 bugs (Table 3), mean fix 58.2 days (Table 6) | github.com/infbug/bugs-in-LLM-inference-engines |
| **Cao et al.**, DL performance problems (ESEC/FSE '22) | TensorFlow/Keras apps | 224 PPs from StackOverflow (§2.2) | n/a | n/a | n/a | PP symptoms, root causes, stages | κ 0.772–0.928 (§2.3); 58 of 112 sampled PPs reproduced with buggy and fixed versions (§2.4); TF Profiler applicable to 15/58, partially solved 2 (§3.4) | Zenodo 10.5281/zenodo.7060209 |
| **TraStrainer** (Proc. ACM SE 1(FSE), 2024) | Microservice traces | Whole traces (tail-based) | Online sampler; bias from runtime-metric anomaly degree + diversity (§4) | Per-trace keep/drop under budget rate β, AND/OR voting (§4.5) | Explicit β (§2.3) | Downstream RCA A@1/A@3/MRR (Table 3) | 62 Huawei production incidents labelled by SREs + 56 Chaosblade injections (Table 1) | github.com/IntelligentDDS/TraStrainer |
| **Astraea** (arXiv 2405.15645v1; venue not printed) | Microservice traces | Span-level sampling probability (§III) | Online Bayesian belief per span; probability matching with ε-exploration (§III-B) | None; continuous adaptation | No explicit budget; knobs P and ε (§IV-D) | Spans explaining latency variance | Injected delays/stress, oracle = faulty spans (§IV-A); 92% top-5, ≈25% instrumentation (§IV-B); sensitivity analysis (Fig 11) | Not stated |
| **Hindsight** (arXiv 2202.05769; NSDI '23 per TraStrainer refs) | Distributed traces | All trace data written to local ring buffers (§4–5) | Programmatic symptom triggers (percentile, category, exception, lateral) (§5.2, Table 2) | Lazy retrieval of past data within an "event horizon" (§6.2, §7.3) | Buffer pool size; rate limits | Edge-case traces | Coherent edge-case capture vs head/tail sampling (§6.1); UC1–UC3 (§6.3) | Not stated |
| **Pivot Tracing** (SOSP '15) | Java distributed systems | Runtime-installed tracepoint queries + baggage (§3–5) | Operator installs queries at runtime | Operator removes queries; no automatic policy (§8) | n/a | Cross-component causal queries | Hadoop stack case studies (§6.1–6.2); overhead ≤0.3% enabled (Table 5) | Not stated |
| **Zhou et al.**, context-sensitive GPU profiling (ICS '22) — named by Reviewer B | HPC/ML apps incl. PyTorch ResNet-50, PyG (offline, one A100) | CUPTI coarse metrics + PC samples attributed to CPU/GPU calling contexts (§3) | Whole-run profiling; new kernel sequences always profiled | *Adaptive epochs* end when a kernel launches from a conflicting call path; already-seen sequences are re-profiled only at random enabling rate E (6% / 0.8%) and samples are scaled (§5.3–5.5) | Overhead vs serialized mode; no explicit budget | Attribution of metrics to calling contexts | Reference = full serialized profile (Eq. 1) and full unwinding (§6.1); 4.61× vs 27.51× overhead at 96.16% accuracy (Table 2) | HPCToolkit-E (integrated in HPCToolkit; separate repo not stated) |
| **Darvishi et al.**, "Toward Adaptive Tracing" (ICSE-NIER '24) | Linux kernel traces (LTTng), Apache2 | System-call sequences and durations (§3.2–3.3) | Limited event set normally; detailed, focused tracing when an LM loss-based change score flags a "significant behavioral shift" (§3, §3.4) | Not stated | Not defined (cites Pythia's budget, §2) | Noise-type / root-cause identification (§3.5) | Injected noise categories on Apache2 traces; 77.1% fewer events, 5.8% miss rate; 91.3% noise-type accuracy (§4) | zenodo.org/records/10437041 |
| **Darche & Dagenais**, device-side GPU kernel tracing (ACM TOPC 11(2), 2024) | GPU compute kernels (HIP, AMD MI100) | Device-side basic-block / wavefront events via LLVM IR instrumentation; two-pass counters then tracing (§3) | Developer-chosen tracepoints | None | n/a | Kernel tuning (control flow, divergence, timing) | Rodinia overhead: tracing kernel mean 1.50×, median 1.29× (Table 2) | github.com/dorsal-lab/hip-analyzer |
| **HPCToolkit GPU** (Parallel Computing 2021; arXiv 2109.06931v1) | HPC GPU apps | Call-path profiles, traces, PC sampling, counters (§4) | User chooses measurement per run; recommends separate runs to limit distortion (§4.7) | User-defined | n/a | Heterogeneous calling contexts, GPU idleness blame (§7.2) | ECP case studies; overhead 1.42–2.24× (§8.1) | Not stated in text read |

## 2. What the literature already establishes

These points cannot be claimed as new contributions.

1. **Anomaly-triggered detailed collection for LLM inference exists.**
   - LatencyPrism escalates from an always-on sentinel to deep GPU/Python tracing on a residual alarm (§3.2.3).
   - StriaTrace keeps full-fidelity kernel traces only for outlier steps (§5.3.2).
   - Our ICSE contribution 1 ("formulation of automatic GPU trace stopping as a runtime control problem") and the two-tier escalation design are therefore not novel as a mechanism.
2. **Heavy profilers perturb LLM serving measurably.**
   - StriaTrace: NSys +34.3% median TPOT at concurrency 8 (§6.2).
   - ARGUS: nsys always-on broke training runs (§8.2).
   - This motivates bounded capture. It should be cited, not re-measured as a contribution.
3. **Circular evaluation is a recognized flaw, and there is a published remedy.** BPW states that "using predicted bottlenecks as target truth creates circular evaluation" and defines prediction-independent labels from direct target measurements with pre-fixed thresholds (§1, §4). This is the same flaw Reviewer C identified in our paper. Our reference design should cite and adapt it, not re-invent it.
4. **Empirical studies of LLM-inference diagnosis are publishable.**
   - Beyond Microservices is a pure evaluation of existing methods with guidelines (§5).
   - TELLER appeared at an SE venue (ASE '26) for LLM-inference RCA.
   - Both support the reframing and answer Reviewer B's venue concern. Neither studies how much heavy evidence to collect.
5. **A general bug taxonomy for LLM inference engines exists.** Liu et al. cover 929 bugs; performance bugs are 53, selected via the `bug` label (§3.2, Table 3). Phase A must not present a general taxonomy as new.
6. **Triggered capture misses pre-onset evidence.** Hindsight (§3) and ARGUS (§2.1–2.2) both argue that enabling detailed collection only after a symptom loses the events that led to it. Any finding about stopping must be conditional on this. Retroactive or ring-buffer collection is a credible alternative design.
7. **"Adaptive tracing" (cheap normally, detailed on a behavioral shift) is already an SE-venue idea.** Darvishi et al. (ICSE-NIER '24, §3) reports cost reduction (77.1% fewer events) against evidence lost (5.8% miss) (§4). It does not define when detailed tracing ends, and its own future work names recurring abnormalities as the open problem (§5).
8. **GPU profiling already reduces collection when kernel behavior repeats.** Zhou et al. (ICS '22, §5.3) re-profile already-seen kernel sequences only at a random enabling rate E, because "GPU kernels are often repeatedly launched with similar or patterned behaviors", and scale the samples. This is the closest prior art to our premise that repeated evidence adds little. It differs in purpose and test, though: it preserves profile attribution fidelity against a full serialized profile (Eq. 1), and it does not decide when a diagnosis is supported or stop a capture session.

## 3. Candidate gap (after reading all three ACM papers)

None of the 16 papers read defines or evaluates a rule for **when a bounded heavy GPU capture has collected enough evidence to support a diagnosis**, compared across stopping rules against independent references.

- LatencyPrism leaves deep-dive duration to user policy.
- Darvishi et al. do not state when detailed tracing ends.
- StriaTrace retains per step and has no sufficiency notion.
- Zhou et al. (ICS '22) sample repeated kernel sequences to keep profile attribution accurate, not to establish diagnostic sufficiency.
- BPW has a sufficiency gate, but for offline workload selection, not runtime captures.
- Astraea and TraStrainer adapt sampling continuously in microservices.

Two further gaps also remain among the papers read:
- none studies **what profiling evidence developers actually collect for LLM-serving performance issues**;
- none compares cheap-only, fixed, stability, recovery and probabilistic re-sampling stopping on the same serving workload.

Allowed phrasing: "To our knowledge, among [cited works], none evaluates…". "No prior work" is not allowed: the Pythia and Zhang 2020 leads are unread, and the search was not systematic.

What answers Reviewer B's question about ICS '22: it adapts *when samples are synchronized* and *how often repeated work is re-profiled*, for attribution accuracy in offline HPC/ML profiling. Our study asks *when capture during a live serving incident can stop* without losing the evidence a diagnosis needs. Its random re-enabling policy should be included as a comparator arm (§5), not only cited.

## 4. Corrections required in the ICSE draft and bibliography

| Location | Current text or field | Correction (source) |
|---|---|---|
| `02_related_works.tex`, Astraea | "formalizes tracing as a cost-constrained online learning problem under a budget" | Astraea frames it as exploration vs exploitation with knobs P and ε; it states no budget constraint (Astraea §III). The budget formalism is TraStrainer's β (TraStrainer §2.3). |
| `02_related_works.tex`, TraStrainer | Runtime state described as "CPU and memory pressure" | It uses general system runtime metrics (121 in dataset A) with an explicit budget rate (TraStrainer §4.1, Table 1). |
| `02_related_works.tex`, closing paragraph | "no prior work studies the runtime control problem of automatically starting, continuing, and stopping costly GPU tracing" | Contradicted for starting/escalation by LatencyPrism §3.2.3 and StriaTrace §5.3.2. Withdraw; replace with the conditional gap in §3. |
| `01_introduction.tex` | "building on runtime-adaptive evidence escalation [Pivot, Hindsight]" | Pivot Tracing is operator-driven runtime instrumentation (§8). Hindsight is retroactive retrieval on symptoms (§3). Neither automates escalation; describe each accurately. |
| `references.bib` `zhang2023hindsight` | year 2021, DOI 10.1145/3472883.3486986 | NSDI '23, pp. 321–339 (as cited in TraStrainer refs [52]). The 10.1145/3472883.* prefix is a SoCC '21 DOI (TraStrainer refs cite Tprof as 10.1145/3472883.3486994), so this DOI likely points to a different paper. |
| `references.bib` `mace2015pivot` | URL points to an ATC '16 page | SOSP '15, October 4–7, 2015, Monterey, CA (paper p. 1). Use the SOSP DOI from ACM. |
| `references.bib` `zhou2021hpctoolkit` | `@misc` arXiv | Published in Parallel Computing (2021), doi:10.1016/j.parco.2021.102837 (arXiv v1 p. 1 footnote). |
| `references.bib` `toslali2024astraea` | — | The arXiv v1 text does not print a venue. Cite arXiv v1, or obtain and read the IC2E version before citing IC2E. |
| `references.bib` `darche2024lowoverhead` | journal "ACM Transactions on Architecture and Code Optimization" | ACM Transactions on Parallel Computing 11(2), Article 9, June 2024 (paper p. 1). |
| `03_methodology.tex` l. 269 | nsys is "the same class of low-overhead GPU kernel tracing studied by Darche and Dagenais" | Wrong characterization: Darche & Dagenais instrument kernel internals on AMD GPUs through an LLVM IR pass, for kernel tuning in small programs (§3, §4.3, §5.1). nsys records kernel-level activity via CUPTI. Drop the citation here, or cite it only for instrumentation noise and the fine-grained end of the evidence spectrum. |
| `02_related_works.tex` (new) | Zhou et al. ICS '22 and Darvishi et al. ICSE-NIER '24 not cited | Add both. Position ICS '22 as repetition-aware sampling for attribution fidelity, and Darvishi et al. as SE-venue adaptive tracing without a stopping rule (§2 items 7–8). |

## 5. Implications for the study design

These update [EMPIRICAL_STUDY_PROPOSAL.md](protocol/EMPIRICAL_STUDY_PROPOSAL.md).

- **References (§5.3 of the proposal):**
  - Adopt BPW's principle explicitly: labels come only from direct measurements relative to a neutral anchor, with thresholds fixed before evaluation and agreement required across restarts.
  - Our "two-witness" stability rule SS(K=2) is close to BPW's two-witness gate. Cite this and discuss the difference: ours is a runtime stop, theirs an offline evidence gate.
- **Arms:**
  - Add a *retroactive-window* comparator inspired by Hindsight and ARGUS: a continuous low-cost kernel ring buffer, retrieved on trigger.
  - Alternatively, state explicitly that pre-onset evidence is out of scope and quantify what it misses.
- **Repetition-sampling arm (from ICS '22):**
  - Add an arm that, after the first capture, re-captures repeated suspicious windows only with probability E (for example 0.06) instead of stopping. This mirrors Zhou et al.'s random epoch re-enabling (§5.3).
  - Also borrow their fidelity metric: percentage deviation of the retained profile from the full-horizon reference capture (Eq. 1). Use it as a cost-independent measure of retained evidence, alongside diagnosis agreement.
- **Controlled cases:** LatencyPrism publishes an anomaly-injection suite (GPU contention, clock lock, PCIe, NVLink, memory). Evaluate it for reuse before writing our own injections.
- **Phase A scope:**
  - Narrow to *performance* issues and *diagnostic-evidence practice*.
  - Reuse the Liu et al. public dataset as a seed (their S4 subset) rather than re-deriving a general taxonomy.
  - Follow their method (closed issues, open coding, κ, arbitrator) and Cao et al.'s keyword-derivation loop (Cao §2.2).
- **Phase B feasibility:** Cao et al. reproduced 58 of 112 sampled performance problems (≈52%) in about four person-months (§2.4). Plan Phase B for roughly half of the candidates failing to reproduce.
- **Evaluation lens:** TraStrainer judges sampling by downstream RCA quality under a budget sweep (Table 3). Our cost–evidence curves should likewise score what a downstream diagnosis can conclude from the retained evidence.
- **Threats precedent:** TELLER §7 and Beyond Microservices §5.4 disclose injected-vs-real, single-fault and in-distribution-split threats. Our threats section should be at least as explicit.

## 6. Next reading

1. Done in step 040: ICS '22, ICSE-NIER '24 and Darche TOPC '24 are read, and §2–§5 are updated.
2. Obtain and read Pythia (Ates et al., SoCC '19) and Zhang et al. 2020 (adaptive instrumentation), the leads from Darvishi et al. §2.
3. Read NVBit, the top-down GPU analysis papers (ICS '20, DrGPU) and Sifter/Sieve only if they are kept as citations.
4. Look for any 2025–2026 work on capture-duration or sufficiency for GPU profilers (search terms: "profiling budget", "sampling duration", "when to stop profiling"), and add whatever is found under the same full-read rule.
