# Empirical study proposal: when is GPU profiling enough?

Date: 2026-10-28. Status: proposed research design (step 038), not a frozen protocol or an executed study. It replaces the step-037 version, which is preserved unchanged as [EMPIRICAL_STUDY_PROPOSAL_step037.md](EMPIRICAL_STUDY_PROPOSAL_step037.md). All counts, thresholds and budgets below are planning values for author review, not approved scientific criteria. Existing blank criteria and assessor records remain untouched.

**What changed from step 037:** the study now has an issue-mining phase that grounds workload cases and reference diagnoses in real, independently resolved performance issues. This addresses the reviewers' realism and circularity objections directly rather than through narrower synthetic cases. The single-cause queue-pressure scope becomes the feasibility pilot, not the whole study. The measurement, missing-data and proceed/revise/stop rules from step 037 are retained.

## 1. Contribution and framing

Working title: *When Is Profiling Enough? An Empirical Study of Stopping Decisions for GPU Performance Diagnosis in LLM Serving.*

The paper no longer claims a novel controller. The controller is the experimental instrument; the stopping rules are treatments; the contribution is evidence. Planned contributions, each conditional on the study producing it:

1. A characterization of real LLM-serving performance issues and how practitioners collect profiling evidence for them (from mined issue reports).
2. A benchmark of reproduced cases with independently established reference diagnoses, plus controlled cases for failure modes that mined issues rarely isolate.
3. Measured cost-versus-evidence trade-offs of fixed, stability-based, recovery-gated and hybrid stopping under the same offered workload.
4. Observed failure conditions of each stopping rule, and how their ranking changes with thresholds, workloads and hardware.
5. An operator workflow and episode report built from logged evidence, framed as supporting inspection, not as demonstrated debugging-time savings.

A shorter capture costing less is not a finding. The study is only worth publishing if it shows something non-obvious: for example, where apparent stability precedes a wrong or incomplete diagnosis, where cheap telemetry is already sufficient, or where rankings reverse across settings. A negative or narrower result is acceptable and should be reported as such.

## 2. Review concerns and design responses

| Concern (reviewer) | Design response | Section |
|---|---|---|
| Limited novelty of a hand-tuned controller (B, C, meta) | Reframe as an empirical study; contribution is evidence, not the algorithm | 1 |
| Artificial workloads; unclear realism (A, B, meta) | Cases derived from mined, reproduced real issues | 4, 5 |
| Accuracy is agreement with self-defined labels (C, meta) | Reference diagnoses from upstream resolution, external analysis tools and blinded assessment; never from the scenario definition | 5.3 |
| Uniformly perfect results; easy workloads (C) | Include changing, overlapping, lull/recurrence and incomplete-evidence cases; report failures and distributions | 5.2, 7 |
| Only six scenarios (B, meta) | Target 8–15 reproduced issues plus controlled cases | 5 |
| Hand-tuned thresholds, optimality, sensitivity (A, B, C Q1) | Calibration/evaluation split, frozen configuration, one-factor sweeps plus a small interaction grid, full grid reported | 6.4 |
| No statistical tests; 3–5 repetitions (A) | At least 10 independent blocks per main cell, sized from pilot variance; paired effects with bootstrap intervals | 8 |
| Arbitrary success thresholds and weighted composite score (A) | Removed; Pareto plots and quality–cost curves instead | 7, 8 |
| No formal definitions of patterns/policies (A) | Formal stopping rules parameterized by thresholds | 6.2 |
| SS vs MU unclear (A) | MU dropped as the SS(K=2) alias identified in step 002 | 6.2 |
| Replay dataset validity (A) | Every result labelled by provenance; offline replay never used for live cost or perturbation claims | 6.3 |
| Weak SE connection (A, B) | Practitioner-practice findings and operator workflow | 4, 9 |
| Existing adaptive profilers not compared (B) | Primary-source comparison with Zhou et al. (ICS '22) and StriaTrace (OSDI '26); executable comparator where feasible | 10 |
| Multiple bottlenecks; multi-GPU (C Q4, Q5) | Overlapping-cause cases in scope; multi-GPU stated as out of scope | 5.2, 11 |

## 3. Research questions

- **RQ1 (practice):** What performance problems are reported for LLM serving systems, what evidence do practitioners collect to diagnose them, and how is collection started and stopped?
- **RQ2 (sufficiency):** How much heavy-profiling evidence is needed to reach the reference diagnosis, and how does agreement with the reference change as capture budget grows?
- **RQ3 (failure conditions):** Under which conditions does each stopping rule stop with a wrong, incomplete or unresolved diagnosis, or stop before an incident recurs?
- **RQ4 (robustness):** Do the cost–evidence trade-offs and rankings of stopping rules hold across threshold settings, held-out workloads and a second GPU?
- **RQ5 (cheap evidence):** When does cheap telemetry alone support the same diagnosis as heavy profiling?

RQ5 may produce the most practically useful finding; it must not be dropped if the answer weakens the case for heavy profiling.

## 4. Phase A — issue mining (RQ1)

### 4.1 Sources and selection

- Repositories: `vllm-project/vllm` (primary), `sgl-project/sglang`, and optionally `huggingface/text-generation-inference`. Pinning the vLLM release for reproduction (Phase B) is separate from mining across releases.
- Candidate query: closed issues and linked pull requests that mention latency, throughput, regression, slow, OOM or preemption, together with profiling terms (`nsys`, `Nsight`, `torch.profiler`, `VLLM_TORCH_PROFILER_DIR`, `kernel`, `trace`). Check the actual label names (for example a `performance` label) on each repository before freezing the query.
- Inclusion: a performance symptom in serving or inference; enough detail to identify the configuration; a stated or linked resolution (fix commit, configuration change, or a maintainer-confirmed cause).
- Exclusion: feature requests, build/install failures, correctness bugs without a performance symptom, and duplicates (keep the canonical issue).
- Record the query text, date, tool version and raw result set so the sample is reproducible.

### 4.2 Coding protocol

- Pilot-code about 30 issues to draft a codebook. Planned dimensions:
  - symptom (TTFT, inter-token latency, throughput, OOM, preemption);
  - root-cause category (scheduling/queueing, prefill-heavy input, decode-heavy output, KV-cache capacity/preemption, kernel or backend choice, CPU-side overhead, configuration);
  - evidence used (metrics, logs, torch profiler, Nsight, none);
  - who collected it and how long the capture ran, when stated;
  - resolution type.
- Code the main sample with two coders. Report Cohen's kappa per dimension and resolve disagreements by discussion, keeping a log. If no second coder is available, state this as a threat and code a random 20% subset twice with a gap of at least two weeks.
- Sample size: target 150–300 included issues, or saturation, whichever comes first. Report the funnel (retrieved → screened → included).

### 4.3 Outputs

- A taxonomy with frequencies, and the practices practitioners actually report.
- A candidate list for reproduction: issues with a confirmed cause, a reproducible configuration on available hardware, and a resolution that can be toggled (pre-fix vs post-fix version, or configuration A vs B).

## 5. Phase B — case benchmark

### 5.1 Reproduced cases

- Target 8–15 reproduced issues spanning at least four root-cause categories from Phase A. Prefer issues whose fix or configuration change can be toggled, so that symptom reversal can be verified.
- Reproduction is accepted only if the reported symptom appears under the pinned stack and is reduced by the documented fix or change. Failed reproduction attempts are kept and counted, not discarded.
- Use model sizes that fit the available GPU. Document every deviation from the original report (model, GPU, version).

### 5.2 Controlled cases

These isolate failure modes that real issues rarely present cleanly. They are documented as laboratory interventions.

| Case | Intervention | Question |
|---|---|---|
| Persistent incident | Hold arrivals above measured service capacity | Does recovery gating spend extra tracing after a correct diagnosis? |
| Changing bottleneck | Shift from short-request overload to a prefill-heavy mix; vary the shift relative to burst boundaries | Can early stability hide a later change? |
| Lull and recurrence | Briefly reduce arrivals during an incident, then restore them | Does a recovery-based stop mistake temporary relief for resolution? |
| Overlapping causes | Combine overload with long contexts or outputs; include each cause alone as a control | Does a stable single label omit an active cause? |
| Healthy control | No perturbation | False activations |
| Incomplete evidence | Withhold specified observations from the decision consumer while retaining raw data | Does missing evidence create false sufficiency? |

The step-037 queue-pressure patterns (sustained pressure, reduced load, lull with recurrence) become the feasibility pilot for this table (section 11).

### 5.3 Reference diagnoses

The reference must not come from the scenario definition or from the classifier under test.

1. **Reproduced cases:** the upstream-confirmed cause, corroborated by symptom reversal under the fix.
2. **External analysis:** a tool not written for this study, such as the Nsight Systems `nsys analyze` expert-system rules, or Holistic Trace Analysis on a torch-profiler trace from a separate matched reference session. Check which tool supports the pinned stack before committing to it.
3. **Blinded assessment:** for the prefix captured at each stop, a second researcher records a diagnosis without seeing the policy, its prediction or the case name. They record their reasoning, their uncertainty, and "unresolved" where the evidence does not support a diagnosis.
4. **Overlapping cases:** the reference is a set of active causes. Score per-cause coverage; a single scenario name does not count as a complete diagnosis.

A configured intervention establishes what was done, not the realized bottleneck. Use the existing reference contracts (`MEASURED_EVIDENCE_CONTRACT.md`, `LOCKED_REFERENCE_SCORING.md`) and lock references before reading predictions.

## 6. Phase C — stopping experiments (RQ2–RQ5)

### 6.1 Arms

| Arm | Role |
|---|---|
| NT — cheap telemetry only | Answers RQ5: is heavy evidence needed at all? |
| FIX(n), n ∈ {1, 2, 3, 6} bursts | Fixed-budget sweep; FIX(1) is the former FB, FIX(3) the former RFB |
| SS(K) | Stability stop |
| CR | Recovery-gated stop |
| HS(K) | Stability and recovery |
| REF — full-horizon capture | Reference instrument in a separate matched session; not same-execution truth |
| Unprofiled | Measures perturbation from cheap metrics and the profiler |

### 6.2 Formal policy definitions

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

### 6.3 Evidence provenance

Label every result `live_online`, `live_fixed_duration`, `offline_replay` or `synthetic_replay`. Planned cost saving: derive FIX(n) prefixes offline from the REF session's continuous capture, labelled `offline_replay`. Run NT, SS, CR, HS and FIX(1) live to measure actual cost and perturbation. Offline prefixes cannot estimate perturbation or evidence that a different capture schedule would have produced.

### 6.4 Threshold sensitivity (RQ4)

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

## 7. Measurements

- **Cost:**
  - profiler-process wall time, startup, export/parse and evidence-ready delay, recorded separately;
  - capture-active seconds only where validated start/end events establish them, otherwise unknown;
  - captured kernel instances and report bytes.
- **Evidence:** agreement with the reference, broken down as supported, incorrect, unresolved and stable-but-wrong, plus per-cause coverage for overlapping cases. Missing evidence is never scored as healthy or correct.
- **Timing:** time from incident onset, and from first capture, to an evidence-supported diagnosis.
- **Detection (reported separately):** missed episodes, false activations, activation delay.
- **Serving impact:** p95 latency, throughput, failures, and offered vs realized work, for every arm including unprofiled.
- **Reporting:** use explicit episode- and run-level denominators. Show distributions and failures, not only means.

## 8. Statistical analysis plan

- The unit of analysis is the independent block (a fresh server and its offered schedule). Windows and requests are not independent repetitions.
- Each block runs all arms on the same exact offered schedule, in randomized order, with a verified reset between arms.
- Choose the number of blocks per main cell from pilot variance and a stated precision target. The planning floor is 10, which is not a power guarantee: zero failures in 10 runs still allows a failure rate of about 30% at 95% confidence.
- For primary comparisons (SS, CR and HS each against FIX(3)), report paired differences with cluster-bootstrap 95% CIs and Wilcoxon signed-rank tests with Holm correction, plus Cliff's δ or Vargha–Delaney A12 as effect sizes. For agreement proportions, report Wilson intervals.
- Pre-declare the primary comparisons before confirmation. Label everything else exploratory.
- Present results as Pareto plots and quality–cost curves. No weighted composite score, no required savings percentage.

## 9. Operator workflow (SE relevance)

- Map the Phase A practice findings to a workflow: incident → cheap evidence → capture decisions → episode report → the operator's next verification step.
- Render episode reports from logged evidence only, covering:
  - symptom and cohort;
  - baseline and current statistics with sample counts;
  - candidate and alternative explanations;
  - captures and their artifacts;
  - stop reason and the conditions actually met;
  - budget spent;
  - the recommended verification step.
- Walk through at least one correct case and one failure or unresolved case from real runs.
- A small blinded task study (fixed-window vs adaptive-prefix reports) is optional. Without one, claim that the report supports inspection, not that it saves engineering time.

## 10. Related work to establish before claiming a gap

Step 039 status: see [related_work_matrix.md](../related_work_matrix.md). 13 of the sources below are read in full; Zhou et al. (ICS '22), Darvishi et al. (ICSE-NIER '24) and Darche & Dagenais remain unread. The matrix's design implications (BPW-style references, retroactive-window comparator, LatencyPrism injection suite, Liu et al. dataset as Phase A seed, ~50% reproduction yield) supersede conflicting details below.

Build `revision/related_work_matrix.md` from primary sources. Mark cells as unknown rather than inferring absence from abstracts. Columns: collection unit, activation rule, stopping rule, budget, diagnostic target, validation setting and artifacts.

Sources:
- Zhou et al., ICS '22: adaptive epoch profiling.
- Wu et al., StriaTrace, OSDI '26.
- Astraea, TraStrainer, Hindsight, Pivot Tracing, HPCToolkit, NVBit.
- LLM-serving performance and characterization studies.
- Empirical studies of performance bugs in ML/DL systems. This method precedent should be cited in Phase A.

For each closest work, decide whether a faithful executable comparator is feasible; otherwise document the concrete incompatibility.

## 11. Execution order and decision gates

| Step | Work | Needs GPU | Gate |
|---|---|---|---|
| 1 | Related-work matrix; contribution statement | No | Empirical gap stated against primary sources |
| 2 | Phase A query, codebook pilot (~30 issues) | No | Codebook stable; agreement on the pilot reported |
| 3 | Phase A main coding; reproduction candidate list | No | ≥ 8 viable candidates across ≥ 4 categories, or narrow the scope |
| 4 | Reference method chosen and demonstrated on existing development captures | No | Reference produced without access to predictions or case names |
| 5 | Clear the step-036 CPU regression | No | Clean full suite before changed source is deployed |
| 6 | Feasibility pilot: step-037 queue-pressure patterns × {NT, FIX(3), SS, HS} × 2 blocks + 6 reference sessions (30 sessions), plus one commissioning run counted separately | L4 | Proceed / revise / stop (below) |
| 7 | Reproduce candidates (Phase B) | L4 | Accepted cases ≥ 8, or report a narrower benchmark |
| 8 | Calibration, then freeze the confirmation protocol | L4 | Frozen configuration and pre-declared comparisons |
| 9 | Confirmation runs; A100 transfer on a subset if affordable | L4 (+A100) | Planned blocks completed, failures retained |
| 10 | Analysis and paper rewrite | No | Every claim traceable to a run, script and provenance label |

**Pilot proceed criteria (from step 037):**
- independent references are possible for a useful subset;
- the policies actually make different online decisions;
- the timing metrics are valid for the claims;
- the evidence differences inform an operator action.

If cheap telemetry already gives the same useful evidence, report that and reassess the role of heavy profiling.

**Planning budget (to be replaced with pilot measurements):**
- Sessions = cases × live arms × blocks.
- Example: 15 cases × 6 live arms × 10 blocks = 900 sessions, plus 150 REF sessions. At an assumed 5 min per session including startup and export, that is about 90 L4 GPU-hours before calibration and sweeps.
- Measure the actual per-session time in the pilot before committing.

## 12. Disposition of existing results

| Result | Disposition |
|---|---|
| RQ2 match/ambiguity rates; RQ1 match rates | Withdraw. Label-dependent diagnosis (step 001 audit). |
| RQ4 ambiguity-stress replay and composite ranking | Withdraw. Relabelled windows, arbitrary weights. |
| RQ5 signal F1 table | Withdraw. Table/F1 mismatch (step 003) and label-dependent inputs. |
| Profiler-duration savings (18.9–48.5%) | Withdraw as stated. Measured whole `nsys` process wall time. Regenerate with separated clocks. |
| Cheap-metric p95 overhead (old RQ3) | Reusable as historical context after the step-003 recomputation. Re-measure for the full controller. |
| Infrastructure in `revision/tracing/` and the L4 v2 campaign | Reuse as instrument and feasibility evidence. Not held-out confirmation. |

## 13. Proposed paper structure

1. Introduction: the stopping question, RQs, contributions as study outputs.
2. Background and related work: the comparison matrix.
3. Study design: Phases A–C, arms, formal rules, references, statistics.
4. RQ1 results: taxonomy and practice.
5. RQ2–RQ5 results: trade-off curves, failure conditions, sensitivity, cheap-only sufficiency.
6. Operator workflow and episode walkthroughs.
7. Discussion: implications for tool builders and operators.
8. Threats to validity: construct (reference quality), internal (perturbation, replay), external (one serving stack, single GPU per session, mined-sample bias).
9. Conclusion and replication package, including mined data, codebook and raw traces where storage permits.

## 14. Open decisions for the author

- Is a second coder and blinded assessor available? If not, the design keeps working, but the threats section must say so and agreement statistics become self-consistency.
- What is the GPU budget? It sets the number of reproduced cases and blocks.
- Which venue? CAIN suits the SE-for-AI framing. ICSE requires the Phase A practice results and the workflow to be strong.
- Is SGLang included in Phase A only, or also reproduced in Phase B? Including it widens external validity but adds a second serving stack to maintain.
