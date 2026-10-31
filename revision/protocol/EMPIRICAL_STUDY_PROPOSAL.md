# Empirical study proposal: when is GPU profiling enough?

Date: 2026-10-28; case section revised 2026-10-29. Status: proposed research design (step 043, case gate revised in step 047), not a frozen protocol or an executed study.

**Step 047 decisions (case benchmark):**
1. Stop searching for real cases at 5 accepted reproductions (§4.1).
2. Confirm or reject vllm#7592 with repeat runs (§4.1, §10 step 2b).
3. The gate is now ≥ 5 reproduced real issues plus the controlled cases, with ≥ 4 cause types overall. The limitation is stated in threats to validity (§13).
4. The next main work is the feasibility pilot (§10 step 5): checking that the stopping rules make different online decisions at all is now the larger risk to the study. All counts, thresholds and budgets below are planning values for author review, not approved scientific criteria. Existing blank criteria and assessor records remain untouched.

Previous versions are preserved unchanged:
- [EMPIRICAL_STUDY_PROPOSAL_step038.md](EMPIRICAL_STUDY_PROPOSAL_step038.md): five RQs, with Phase A issue mining;
- [EMPIRICAL_STUDY_PROPOSAL_step037.md](EMPIRICAL_STUDY_PROPOSAL_step037.md): three RQs.

**What changed from step 038:**
- **Phase A (systematic issue mining) is dropped**, together with its practice RQ.
  - The pilot is archived as an internal record; see [phase_a/](../phase_a/) and section 12.
  - The reason is scope and resources. The pilot showed that general performance issues rarely contain profiler evidence (4 of 20 included issues), so a full taxonomy would mostly not be about GPU profiling. A reliable taxonomy also needs a second human coder, and none is available.
- GitHub issues remain a **source of reproducible cases** (section 4.1), screened but not coded for a taxonomy.
- The four RQs are reordered as a funnel:
  1. is heavy profiling needed at all;
  2. if so, how much;
  3. can stopping rules find that amount, and where do they fail;
  4. do the answers hold up.
- Every RQ is stated as a question about stopping heavy GPU tracing, and each is planned to end in a **finding and its practical implication** (section 3.2). The paper's "solution" is the evidence-based guidance that comes out of those findings (section 8), not a new controller.

## 1. Contribution and framing

Working title: *When Is Profiling Enough? An Empirical Study of Stopping Heavy GPU Tracing for Performance Diagnosis in LLM Serving.*

This is an empirical study:
- **The object of study** is the decision of when to start and stop heavy GPU tracing (Nsight Systems bursts) while diagnosing a slowdown in a live LLM server.
- **The adaptive tracer from the earlier draft is the experimental instrument.** It runs every arm the same way and records the evidence. It is not the contribution, and the paper does not claim it is novel.
- **The stopping rules are the treatments:** no heavy tracing, fixed budgets, stability, recovery and hybrid.
- **The contribution is evidence and the guidance derived from it.**

Planned contributions, each conditional on the study producing it:
1. Measurements of when cheap telemetry is enough to diagnose a GPU-serving slowdown, and when heavy profiling is required (RQ1).
2. Diagnosis-quality-versus-capture-cost curves for heavy profiling, scored against independent reference diagnoses, by case type (RQ2).
3. The cost and the failure conditions of adaptive stopping rules compared with fixed budgets (RQ3), and whether they hold across thresholds, workloads and GPUs (RQ4).
4. Evidence-based guidance for operators and tool builders on when to profile and when to stop, applied to the instrument and checked on held-out cases (section 8).
5. A benchmark of reproduced and controlled cases with reference diagnoses, released as a replication package.

A shorter capture costing less is not a finding. The study is only worth publishing if it shows something non-obvious, for example:
- cheap telemetry is already enough for some causes;
- apparent stability comes before a wrong or incomplete diagnosis;
- rule rankings reverse across settings.

A negative or narrower result is acceptable and must be reported as such.

## 2. Review concerns and design responses

| Concern (reviewer) | Design response | Section |
|---|---|---|
| Limited novelty of a hand-tuned controller (B, C, meta) | Reframed as an empirical study. The controller is the instrument; the contribution is evidence and guidance. | 1, 8 |
| Artificial workloads; unclear realism (A, B, meta) | Cases reproduced from real, upstream-resolved GitHub issues, plus controlled cases documented as interventions | 4 |
| Accuracy is agreement with self-defined labels (C, meta) | Reference diagnoses from upstream resolution and external analysis tools, never from the scenario definition | 4.3 |
| Uniformly perfect results; easy workloads (C) | Changing, overlapping, lull/recurrence and incomplete-evidence cases; failures and distributions reported | 4.2, 6 |
| Only six scenarios (B, meta) | 5 reproduced real issues (6 if vllm#7592 is confirmed) plus 6 controlled cases | 4 |
| Hand-tuned thresholds, optimality, sensitivity (A, B, C Q1) | Calibration/evaluation split, frozen configuration, sweeps, full grid reported (RQ4) | 5.4 |
| No statistical tests; 3–5 repetitions (A) | At least 10 independent blocks per main cell, sized from pilot variance; paired effects with bootstrap intervals | 7 |
| Arbitrary success thresholds and weighted composite score (A) | Removed; Pareto plots and quality–cost curves instead | 6, 7 |
| No formal definitions of patterns/policies (A) | Formal stopping rules parameterized by thresholds | 5.2 |
| SS vs MU unclear (A) | MU dropped as the SS(K=2) alias identified in step 002 | 5.2 |
| Replay dataset validity (A) | Every result labelled by provenance; offline replay never used for live cost or perturbation claims | 5.3 |
| Weak SE connection (A, B) | Evidence-based guidance for operators and tool builders, and an episode report that supports inspection | 8 |
| Existing adaptive profilers not compared (B) | Primary-source comparison; repetition-sampling (Zhou et al., ICS '22) and retroactive-window comparators where feasible | 5.1, 9 |
| Multiple bottlenecks; multi-GPU (C Q4, Q5) | Overlapping-cause cases in scope; multi-GPU stated as out of scope | 4.2, 10 |

## 3. Research questions

### 3.1 Questions

**RQ1: When is cheap telemetry enough?**
In which GPU-serving slowdowns do request metrics and NVML counters alone support the same diagnosis as heavy GPU profiling, and in which do they not?
- **Arms:** NT (cheap telemetry only) and REF (full-horizon Nsight capture), each scored against the reference diagnosis. The unprofiled arm gives profiling overhead as context.
- **Measures:**
  - agreement with the reference, per case and per cause type;
  - which causes cheap telemetry confuses or cannot separate;
  - overhead of cheap metrics and of heavy capture on p95 latency and throughput.

**RQ2: How much heavy profiling is enough?**
When heavy profiling is needed, how many Nsight bursts does it take to reach the reference diagnosis, and how does agreement change as the capture budget grows?
- **Arms:** FIX(n) for n ∈ {1, 2, 3, 6}, and REF.
- **Measures:**
  - agreement-versus-cost curves, by case type;
  - the smallest budget at which agreement stops improving, with uncertainty.

**RQ3: Do adaptive stopping rules find that amount, and when do they fail?**
Compared with fixed budgets, how much profiling do stability, recovery and hybrid stopping rules use, and under what conditions do they stop with a wrong, incomplete or unresolved diagnosis, or before the incident recurs?
- **Arms:** SS(K), CR and HS(K) against FIX(3) as the primary comparison, and against the full FIX(n) curve from RQ2.
- **Measures:**
  - paired cost and diagnosis-quality differences, shown as Pareto plots;
  - each failure tied to a case condition: stable but wrong, changing cause, overlapping causes, lull then recurrence, missing evidence.

**RQ4: Do the findings hold up?**
Do the trade-offs and rankings from RQ1–RQ3 hold when thresholds change, on held-out workloads, and on a second GPU?
- **Method:**
  - thresholds tuned on a calibration set, then frozen;
  - one-factor sweeps and a small interaction grid;
  - held-out cases;
  - L4 vs A100 on a subset.
- **Measures:** ranking reversals, and settings where a rule always traces or never stops.

### 3.2 From each question to a finding and an implication

Each RQ is designed so that either answer is informative. The table lists the possible outcomes, not expected results.

| RQ | Possible findings | Implication it informs |
|---|---|---|
| RQ1 | Cheap telemetry matches the reference for some cause types (for example queue pressure) but not others (for example kernel or backend choice) | Which slowdowns operators can diagnose without starting a profiler; when a profiler should be triggered |
| RQ2 | Agreement saturates after a small number of bursts for steady causes but keeps improving for changing or overlapping ones | A default capture budget per situation, instead of one fixed window |
| RQ3 | Adaptive rules match fixed budgets at lower cost in steady cases but stop wrongly under specific conditions | When an adaptive stop can be trusted, and which safeguard (for example a recovery check) prevents each failure |
| RQ4 | Rankings are stable, or reverse at named thresholds or on another GPU | Which guidance transfers, and which settings must be re-calibrated per deployment |

## 4. Case benchmark

### 4.1 Reproduced cases

- **Source:** closed vLLM GitHub issues with a confirmed cause and a fix or configuration change that can be toggled, so that the symptom can be shown before and after.
  - Issues are screened for reproducibility only; there is no taxonomy coding.
  - Screen record per issue: confirmed cause, toggle, single-GPU fit for an L4 (24 GB), workload detail.
  - Candidates came from one search frame: closed vLLM issues closed by a merged PR. See [SCREENING.md](../cases/SCREENING.md) for the queries, dates and decisions.
- **Target (revised in step 047):** at least 5 reproduced real issues, plus the controlled cases in §4.2, covering at least 4 cause types across the two sets.
  - The earlier target of 8–15 was a planning value.
  - What the case count must achieve is realism and cause-type coverage. Statistical precision comes from repeated blocks per case (§7), not from the number of cases.
- **Status ([REPRODUCTION.md](../cases/REPRODUCTION.md)):** 8 attempted.
  - 5 accepted:

    | Issue | Cause |
    |---|---|
    | vllm#6240 | GPU kernel selection |
    | vllm#7619 | Redundant GPU prefill |
    | vllm#3087 | Host deepcopy |
    | vllm#25418 | Host processor rebuilds |
    | vllm#19732 | Host grammar masks |

  - 1 pending: vllm#7592 (scheduling/preemption). The direction is reproduced, but the effect is about 10%.
  - 2 failed: vllm#6923, #49013.
  - 1 not installable: vllm#15105.
- **Search stopped (step 047).** No further search frames are planned.
  - Real-issue cause coverage is GPU kernel, GPU redundant work and host CPU. Scheduling is added if vllm#7592 is confirmed.
  - The controlled cases add queue overload, changing and overlapping causes, recurrence and missing evidence.
  - With one kernel-level case, the paper reports results per case and makes no general claim about GPU-kernel causes (§13, threats).
- **vllm#7592 confirmation:** repeat runs of both releases (v0.5.5 vs v0.6.0), at least 5 blocks each.
  - Accept it if the paired difference has a 95% CI that excludes zero.
  - Otherwise report it as a failed reproduction.
- **Acceptance:** a reproduction is accepted only if the reported symptom appears under the pinned stack and is reduced by the documented fix or change. Failed reproduction attempts are kept and counted, not discarded.
- **Deviations:** use model sizes that fit the available GPU, and document every deviation from the original report (model, GPU, version).

### 4.2 Controlled cases

These isolate failure modes that real issues rarely present cleanly. They are documented as laboratory interventions.

| Case | Intervention | Question |
|---|---|---|
| Persistent incident | Hold arrivals above measured service capacity | Does recovery gating spend extra tracing after a correct diagnosis? |
| Changing bottleneck | Shift from short-request overload to a prefill-heavy mix; vary the shift relative to burst boundaries | Can early stability hide a later change? |
| Lull and recurrence | Briefly reduce arrivals during an incident, then restore them | Does a recovery-based stop mistake temporary relief for resolution? |
| Overlapping causes | Combine overload with long contexts or outputs; include each cause alone as a control | Does a stable single label omit an active cause? |
| Healthy control | No perturbation | False activations |
| Incomplete evidence | Withhold specified observations from the decision consumer while retaining raw data | Does missing evidence create false sufficiency? |

The step-037 queue-pressure patterns (sustained pressure, reduced load, lull with recurrence) become the feasibility pilot for this table (section 10).

### 4.3 Reference diagnoses

The reference must not come from the scenario definition or from the classifier under test.

1. **Reproduced cases:** the upstream-confirmed cause, corroborated by symptom reversal under the fix.
2. **External analysis:** a tool not written for this study, such as the Nsight Systems `nsys analyze` expert-system rules, or Holistic Trace Analysis on a torch-profiler trace from a separate matched reference session. Check which tool supports the pinned stack before committing to it.
3. **Blinded assessment (optional):** for the prefix captured at each stop, a second researcher records a diagnosis without seeing the policy, its prediction or the case name, with reasoning, uncertainty, and "unresolved" where the evidence does not support a diagnosis. No second researcher is currently available. Without one, references rest on methods 1 and 2, and the threats section says so.
4. **Overlapping cases:** the reference is a set of active causes. Score per-cause coverage; a single scenario name does not count as a complete diagnosis.

A configured intervention establishes what was done, not the realized bottleneck. Use the existing reference contracts (`MEASURED_EVIDENCE_CONTRACT.md`, `LOCKED_REFERENCE_SCORING.md`) and lock references before reading predictions.

## 5. Stopping experiments (RQ1–RQ4)

### 5.1 Arms

| Arm | Role | RQ |
|---|---|---|
| NT: cheap telemetry only | Is heavy evidence needed at all? | 1 |
| FIX(n), n ∈ {1, 2, 3, 6} bursts | Fixed-budget sweep; FIX(1) is the former FB, FIX(3) the former RFB | 2, 3 |
| SS(K) | Stability stop | 3 |
| CR | Recovery-gated stop | 3 |
| HS(K) | Stability and recovery | 3 |
| Repetition sampling (after Zhou et al., ICS '22) | Comparator from prior adaptive profiling, if a faithful adaptation is feasible | 3 |
| Retroactive window (after Hindsight / ARGUS) | Comparator that keeps recent evidence and captures on demand, if feasible | 3 |
| REF: full-horizon capture | Reference instrument in a separate matched session; not same-execution truth | 1, 2 |
| Unprofiled | Measures perturbation from cheap metrics and the profiler | 1 |

### 5.2 Formal policy definitions

Notation for the evidence window `t`:

| Symbol | Meaning |
|---|---|
| `E_t` | Fresh T2 evidence; ⊥ if absent, failed or cached |
| `d_t ∈ L ∪ {unknown, mixed}` | Diagnosis |
| `R_t` | Recovery predicate on cheap signals |
| `b_t` | Captures used |
| `B` | Per-episode cap |

- **Stability streak:** `s_t = 0` if `E_t = ⊥` or `d_t ∉ L`; otherwise `s_t = s_{t-1} + 1` if `d_t = d_{t'}` for the previous eligible window `t'`, else `1`.
- **Recovery streak:** `r_t = r_{t-1} + 1` if `R_t` holds with valid telemetry and no suspicion, else `0`. Missing telemetry never satisfies `R_t`.
- **R_t:** `p95_t / p95_base ≤ θ_lat` and, where applicable, `util_t ≤ θ_util`. `p95_base` comes from a separate healthy calibration session, never from the first anomalous window.
- **Stop rules:** FIX(n) stops at `b_t = n`; SS(K) stops at `s_t ≥ K`; CR stops at `r_t ≥ M`; HS(K) stops at `s_t ≥ K ∧ r_t ≥ M`. All rules stop at `b_t = B` with the distinct outcome `budget_exhausted`.
- **Outcomes kept distinct:** `sufficient`, `recovered`, `budget_exhausted`, `horizon_ended`, `profiler_failed`, `evidence_missing`. None but the first two counts as a successful stop.
- **Diagnosis mapping (Table III):** state each class as an explicit predicate over named features with named thresholds, so that every tunable value appears in the configuration and in the paper.

These match the semantics implemented in step 002 (`revision/tracing/policies.py`).

### 5.3 Evidence provenance

Label every result `live_online`, `live_fixed_duration`, `offline_replay` or `synthetic_replay`.
- **Planned cost saving:** derive FIX(n) prefixes offline from the REF session's continuous capture, labelled `offline_replay`.
- **Live arms:** run NT, SS, CR, HS and FIX(1) live to measure actual cost and perturbation.
- **Limit of offline prefixes:** they cannot estimate perturbation, or evidence that a different capture schedule would have produced.

### 5.4 Threshold sensitivity (RQ4)

- **Calibration subset:** a disjoint set of cases and seeds. Freeze the configuration before evaluating held-out cases.
- **One-factor sweeps:**
  - latency trigger {1.25, 1.5, 2.0};
  - K {2, 3, 4};
  - GPU suspicion {80, 85, 95}%;
  - latency recovery {1.05, 1.10, 1.20};
  - recovery streak M {1, 2, 3}.
- **Interaction grid:** latency trigger × K.
- Sweep stopping thresholds offline only over complete independently collected streams. Sweep trigger thresholds live, because changing activation time changes which evidence exists.
- Report the full grid, any ranking reversals, and settings where a policy always traces or never recovers.

## 6. Measurements

- **Cost:**
  - profiler-process wall time, startup, export/parse and evidence-ready delay, recorded separately;
  - capture-active seconds only where validated start/end events establish them, otherwise unknown;
  - captured kernel instances and report bytes.
- **Evidence:** agreement with the reference, broken down as supported, incorrect, unresolved and stable-but-wrong, plus per-cause coverage for overlapping cases. Missing evidence is never scored as healthy or correct.
- **Timing:** time from incident onset, and from first capture, to an evidence-supported diagnosis.
- **Detection (reported separately):** missed episodes, false activations, activation delay.
- **Serving impact:** p95 latency, throughput, failures, and offered vs realized work, for every arm including unprofiled.
- **Reporting:** use explicit episode- and run-level denominators. Show distributions and failures, not only means.

## 7. Statistical analysis plan

- The unit of analysis is the independent block (a fresh server and its offered schedule). Windows and requests are not independent repetitions.
- Each block runs all arms on the same exact offered schedule, in randomized order, with a verified reset between arms.
- Choose the number of blocks per main cell from pilot variance and a stated precision target. The planning floor is 10, which is not a power guarantee: zero failures in 10 runs still allows a failure rate of about 30% at 95% confidence.
- For primary comparisons (SS, CR and HS each against FIX(3)), report paired differences with cluster-bootstrap 95% CIs and Wilcoxon signed-rank tests with Holm correction, plus Cliff's δ or Vargha–Delaney A12 as effect sizes. For agreement proportions, report Wilson intervals.
- Pre-declare the primary comparisons before confirmation. Label everything else exploratory.
- Present results as Pareto plots and quality–cost curves. No weighted composite score, no required savings percentage.

## 8. From findings to guidance

This section is the study's answer to "so what should practitioners do?". The guidance is derived from the findings and is not designed in advance.

- **Guidance statements.** Each finding in section 3.2 is turned into a short, conditional recommendation that cites the RQ result behind it. Illustrative form, not a result: "for slowdowns that cheap metrics attribute to queue pressure, heavy capture added no diagnostic agreement (RQ1); trigger a profiler only when …". Each statement is labelled with the cases and GPU it was observed on.
- **Applying the guidance to the instrument.** The adaptive tracer is configured from the guidance using calibration cases only: trigger conditions, default budget and stopping safeguard.
  - That configuration is evaluated once on held-out cases as part of RQ4.
  - It is reported as a demonstration that the guidance can be put into practice, not as a new or optimal controller.
- **Operator view.** An episode report rendered from logged evidence only, covering:
  - symptom and baseline statistics with sample counts;
  - candidate and alternative explanations;
  - captures and their artifacts;
  - stop reason and the conditions actually met;
  - budget spent;
  - the recommended next verification step.
  - Walk through at least one correct case and one failure or unresolved case from real runs.
  - Without a user study, claim only that the report supports inspection, not that it saves engineering time.
- **Implications for tool builders.** What the failure conditions in RQ3 imply for profiler and observability tools, for example keeping recent evidence available instead of stopping on stability alone.

## 9. Related work

See [related_work_matrix.md](../related_work_matrix.md); 16 sources are read in full. Its design implications supersede conflicting details here:
- BPW-style references;
- a retroactive-window comparator;
- the LatencyPrism injection suite;
- a reproduction yield of about 50%.

The matrix's Phase A design implication (the Liu et al. dataset as a seed) no longer applies.

- **Motivation:** cite published characterizations of LLM-serving and deep-learning performance issues (Liu et al., Cao et al.) for how often such problems occur and how they are diagnosed. This study does not repeat that characterization.
- **Gap:** stated conditionally, as in the matrix §3: diagnosis-sufficiency stopping of bounded captures in live LLM serving. No "no prior work" phrasing.
- **Comparators:** for each closest work, decide whether a faithful executable comparator is feasible; otherwise document the concrete incompatibility.

## 10. Execution order and decision gates

| Step | Work | Needs GPU | Gate |
|---|---|---|---|
| 1 | Related-work matrix; contribution statement | No | Done (step 039–040) |
| 2 | Case screen and reproduction (moved before the pilot) | No / L4 | Done (steps 044–046): 5 accepted. Gate revised in step 047 to ≥ 5 reproduced plus controlled cases, ≥ 4 cause types overall |
| 2b | vllm#7592 repeat runs (≥ 5 blocks per release) | L4 | Paired 95% CI excludes zero, or the case is recorded as failed |
| 3 | Reference method chosen and demonstrated on existing development captures | No | Reference produced without access to predictions or case names |
| 4 | Clear the step-036 CPU regression | No | Clean full suite before changed source is deployed |
| 5 | Feasibility pilot: step-037 queue-pressure patterns × {NT, FIX(3), SS, HS} × 2 blocks + 6 reference sessions (30 sessions), plus one commissioning run counted separately | L4 | Proceed / revise / stop (below) |
| 6 | Integrate accepted cases into the instrument's workload driver, with toggles and references | L4 | Each case shows its symptom under the instrument with its toggle. **Passed for 5 of 6 cases (step 055)**; #19732 not reproduced under serving and excluded ([CALIBRATION_PLAN.md](CALIBRATION_PLAN.md) §2.1) |
| 7 | Calibration, then freeze the confirmation protocol | L4 | Frozen configuration and pre-declared comparisons. Sessions and θ rules pre-declared in [CALIBRATION_PLAN.md](CALIBRATION_PLAN.md) §3–4 (about 9 L4 h); approved by the author (step 054). **Done (step 056)**: thresholds frozen as `study_rule_v2_calibrated_2026-10-29`; θ_r not separable; [EVALUATION_PLAN.md](EVALUATION_PLAN.md) |
| 8 | Confirmation runs; A100 transfer on a subset if affordable | L4 (+A100) | Planned blocks completed, failures retained |
| 9 | Analysis, guidance (section 8), and paper rewrite | No | Every claim traceable to a run, script and provenance label |

**Pilot proceed criteria (from step 037):**
- independent references are possible for a useful subset;
- the policies actually make different online decisions;
- the timing metrics are valid for the claims;
- the evidence differences inform an operator action.

If cheap telemetry already gives the same useful evidence, report that as an RQ1 finding and reassess the role of heavy profiling.

**Planning budget (to be replaced with pilot measurements):**
- Sessions = cases × live arms × blocks.
- Example: 15 cases × 6 live arms × 10 blocks = 900 sessions, plus 150 REF sessions. At an assumed 5 min per session including startup and export, that is about 90 L4 GPU-hours before calibration and sweeps.
- Measure the actual per-session time in the pilot before committing.

## 11. Disposition of existing results

| Result | Disposition |
|---|---|
| RQ2 match/ambiguity rates; RQ1 match rates | Withdraw. Label-dependent diagnosis (step 001 audit). |
| RQ4 ambiguity-stress replay and composite ranking | Withdraw. Relabelled windows, arbitrary weights. |
| RQ5 signal F1 table | Withdraw. Table/F1 mismatch (step 003) and label-dependent inputs. |
| Profiler-duration savings (18.9–48.5%) | Withdraw as stated. Measured whole `nsys` process wall time. Regenerate with separated clocks. |
| Cheap-metric p95 overhead (old RQ3) | Reusable as historical context after the step-003 recomputation. Re-measure for the full controller (RQ1 context). |
| Infrastructure in `revision/tracing/` and the L4 v2 campaign | Reuse as instrument and feasibility evidence. Not held-out confirmation. |

## 12. Archived: Phase A pilot

- Kept in [phase_a/](../phase_a/) as an internal record: 30 issues, codebook v1, and a human-vs-LLM agreement analysis.
- Not cited as a result. It lacks a human–human reliability check, and the main sample was never coded.
- It is used only as the starting list of reproduction candidates (section 4.1).

## 13. Proposed paper structure

1. **Introduction:** the stopping question, the four RQs, contributions as study outputs.
2. **Background and related work:** published issue characterizations as motivation; the comparison matrix.
3. **Study design:** instrument, cases, arms, formal rules, references, statistics.
4. **RQ1 results:** when cheap telemetry is enough.
5. **RQ2 results:** how much heavy profiling is enough.
6. **RQ3 results:** adaptive stopping costs and failure conditions.
7. **RQ4 results:** sensitivity, held-out cases, second GPU.
8. **Guidance and its application:** guidance statements, the tracer configured from them on held-out cases, episode walkthroughs.
9. **Discussion:** implications for operators and tool builders.
10. **Threats to validity:**
    - construct: reference quality; no blinded assessor;
    - internal: perturbation, replay;
    - external:
      - one serving stack and a single GPU per session;
      - case selection from one GitHub search frame;
      - only 5 (or 6) reproduced real issues, one of them kernel-level, so results are reported per case and no general claim is made about GPU-kernel causes;
      - several deviations from the original reports (smaller models, synthetic inputs), listed per case;
      - one fixed release found inert on its release-date dependencies (vllm#25418).
11. **Conclusion and replication package:** cases, scripts, references and raw traces where storage permits.

## 14. Open decisions for the author

- **GPU budget:** sets the number of reproduced cases and blocks.
- **Venue:** CAIN suits the SE-for-AI framing. ICSE needs the guidance and the operator view to be strong.
- **Blinded assessor:** none is available now. If one becomes available later, add method 3 in section 4.3 on a subset.
- **Comparators:** whether the repetition-sampling and retroactive-window comparators can be implemented faithfully within budget.
