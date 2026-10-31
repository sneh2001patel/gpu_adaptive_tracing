# L4 experiment protocol — draft v1

Prepared 2026-10-27, step 012. **CPU preparation complete; protocol not frozen and no new GPU experiment run.** The configuration is [l4_protocol_draft.json](../configs/l4_protocol_draft.json). Draft compilation validates a design; it does not implement the missing collectors, workload runner or diagnosis model. Step-011 artifacts are engineering/development data and cannot become confirmation data.

## Questions and permissible conclusions

1. When a concrete diagnosis repeats, how often is it supported, contradicted or incomplete according to independent reference evidence? A stable label can still be wrong.
2. On a persistent incident with a supported diagnosis, what additional collection does recovery gating incur? A correct diagnosis and service recovery are different outcomes.
3. Under changing conditions, a lull, or overlapping effects, when do stopping and reactivation miss information? Later suspicion alone does not prove that another capture was necessary.
4. Do conclusions survive trigger, stability and workload changes? Report abstention, failures, missingness and ranking reversals.

These questions address empirical stopping behavior. This protocol does not establish novelty relative to prior work; a primary-source related-work comparison remains a separate prerequisite for paper claims.

## 1. Separate the information paths before collecting labels

| Consumer | May receive | Must not receive |
|---|---|---|
| Workload driver | Timestamped offered arrivals, actual prompts/token budgets, evaluator schedule | Policy predictions as feedback to alter the schedule |
| Controller/classifier | Received completions, measured request features, server/NVML samples, newly ready kernel evidence, frozen calibration | Case name, configured phase, intended cause, reference labels, future samples or future reports |
| Reference adjudicator | Independent server diagnostics, intervention/removal record, matched reference runs and quality flags | Policy name, predicted labels, stop decisions; adjudicate first |
| Offline scorer | Frozen predictions plus locked reference records and join keys | Permission to change calibration or reference labels after seeing scores |

Opaque run IDs are logging keys, never model features. A private driver must not import its intervention metadata into classifier observations. `controller_jobs.json` deliberately omits case/phase/prompt schedules; `evaluator_schedule.json` is a separate evaluator/driver artifact. Filenames are not a security boundary: enforce typed input allowlists and tests at the actual adapter. Measured prompt lengths and actual pending requests can be features; configured arrival rates and injected cause names cannot.

Existing live classifier signature takes a parsed kernel summary only and returns `None`. Existing kernel name/count/time aggregates alone cannot identify queueing, KV pressure or a prefill bottleneck. Step 013 implements the richer typed measured-observation contract and an abstaining adapter; step 014 adds response-usage/queue-gauge collection and temporal joining. Wait/prefill interval instrumentation and live runner integration still need implementation and validation. Do not replace abstention with keyword matches in kernel names.

## 2. Define the diagnosis target and independent reference

Initial targets are **observed mechanisms**: `queue_pressure` and `prefill_dominated_service`. Before live integration, explicitly map these reference terms to the existing policy vocabulary (`vllm_queue_pressure`, and a justified interpretation of `vllm_long_prompt`) or version the vocabulary; do not silently change which strings count as concrete. A long-prompt workload label must not substitute for a supported prefill mechanism. Do not claim compute-bound, memory-bandwidth-bound or KV-cache-pressure diagnoses without the additional instrumentation needed to distinguish them. Long input by itself describes request mix, not a bottleneck. Kernel-time sum can overlap across streams and is not device busy time or capture-active time.

| Reference mechanism | Required evidence | Contradictions / insufficient evidence |
|---|---|---|
| Queue pressure | Sustained server waiting/queue measurements plus arrival/service and request-wait evidence; compare overload-alone control and removal | High client in-flight count, slow completions or GPU utilization alone; absent server queue evidence |
| Prefill-dominated service | Actual input-token mix plus measured prefill service contribution/latency and corroborating annotated activity or server timings; compare long-input-alone control and removal | A long prompt, kernel name, or slower request alone; unavailable phase attribution |
| Overlap | Both mechanism rubrics supported in the same interval, with individual controls and uncertainty recorded | Combined intervention name alone; queueing may be a downstream mediator of changed service demand, not an independent root cause |

During calibration, set numerical persistence/effect criteria using baseline variation and measurements. Save candidate rules, selected thresholds and rejected alternatives. None is established by the intervention schedule. Freeze criteria before development scoring and re-freeze before confirmation if development changes the design.

Reference records are interval-specific, including neutral/missing/ambiguous intervals. Use `reference_record.template.json` as a schema example, not an experimental observation. Each reference stores artifact hashes, observed/available times, evidence channels, criterion results, alternative explanations, assessor identities and rubric version. `supported_causes=[]` with `status=unresolved` is valid. Absence of evidence is not a healthy label. A verified healthy interval is separately adjudicated.

Use same-run independent server/request channels to establish realized behavior. Collect full-horizon Nsight reference captures in **separate matched runs** because tracing perturbs serving; compare response trajectories and record mismatch. Do not transplant reference-run timestamps or labels onto a policy run merely because the injection schedule matches. A separate reference capture is corroboration, not automatic ground truth. Do not let a policy's own short capture be the sole basis of its reference label.

Have a second researcher adjudicate without predictions when available. Lock reference artifacts/hashes before joining predictions. If one author performs both tasks, record that limitation, hide predictions until the reference is saved, and claim a controlled intervention study rather than independent human validation. Do not invent reviewer agreement or operator benefit.

## 3. Calibration and data splits

1. Preserve step-011 code/data as development history. Retain `pilot_001` as telemetry-incomplete and `pilot_002` as an abstaining engineering pilot.
2. On the next rental, reproduce device/worker identity, readiness and cleanup checks on the pinned L4 stack. Validate server metric names and timing semantics from actual endpoint output; they are not implemented by this document.
3. Measure sustainable unprofiled service capacity using a fixed short-prompt, 32-output-token mix. Record queue slope, completions, errors and offered/admitted work at each tested rate; define the sustainable-rate rule before selecting capacity. Do not derive it from the maximum latency observed under overload.
4. Create disjoint prompt corpora and save content hashes/tokenizer revision/actual token counts. Draft short and long bands are not yet tokenized; select bands within the pinned model's 2,048-token context including output headroom. Freeze exact arrival files, request IDs, prompts, seeds and lengths before policy runs.
5. Collect separate healthy baseline requests and choose window length/sample requirements using observed completion density. Current 2 s windows are provisional: do not present sparse-window p95 as precise. Record counts and uncertainty; define which insufficient windows cannot trigger/recover before freezing. Implement that rule in the adapter.
6. Fit transparent, abstaining candidate diagnosis rules on calibration-only measurements. Use measured queue/wait/token/service features and valid T2 corroboration. Preserve candidate scores and report false-concrete rate versus coverage on a disjoint calibration-validation subset. Select conservatively by supported correctness first, then coverage, with deterministic tie-breaking; if every candidate abstains, the diagnosis gate remains failed. No numerical accuracy target is justified yet. Any target used for confirmation must be motivated and specified before viewing confirmation results.
7. Development covers transitions/lulls/overlap and is allowed to expose defects. Change protocol versions when fixing defects. Confirmation uses disjoint prompts, arrivals, onset/duration shapes and seeds; a new seed alone does not establish workload transfer. The compiled schedule is **development only**; confirmation remains ungenerated until freeze.

Freeze manifest: source archive/hash, hardware/software/model/tokenizer revisions, corpus/arrival hashes, server settings, calibration cohort/hash, classifier feature/rule hash, reference rubric hash, policies, outcome definitions, randomization/reset rule, repetitions/precision rationale, all timing scopes, missingness/exclusion rules, and analysis version. No timestamped freeze is claimed now.

## 4. Challenge cases and phase feasibility

All provisional cases have a 120 s horizon, 2 s windows, up to 45 s drain and 32 output tokens. Capacity ratios refer to the short-input capacity measured in calibration and are offered-load settings, not diagnosis features.

| Case | Draft offered workload | Test |
|---|---|---|
| Healthy | Short inputs, 0.35 × capacity throughout | False activations and control overhead |
| Persistent / overload alone | Healthy 0–20 s; short-input 1.25 × capacity 20–100 s; healthy 100–120 s | Diagnosis versus recovery; single-intervention control |
| Prefill alone | Healthy 0–20 s; long inputs at unchanged 0.35 × short-input capacity 20–100 s; healthy afterward | Measured effect of input mix; queueing may also arise |
| Changing | Short-input overload 20–60 s, then long inputs at 0.35 × capacity 60–100 s | Changed evidence, coverage and reactivation |
| Temporary lull | Short-input overload 20–55 s, 0.1 × capacity 55–65 s, overload 65–100 s | Whether actual queue relief occurs and collection resumes when warranted |
| Overlap | Long inputs at 1.25 × short-input capacity 20–100 s | Both effects versus individual interventions |

Warmup and calibration precede every measured session. Changing and lull phases may be too short given queue backlog, request service and synchronous flush. The next GPU feasibility pilot must verify realized phases and adjust durations **before** freezing; a lull that fails to relieve the queue is an unsuccessful intervention, not manufactured recovery. Verify removal actually reverses the symptom; record carryover if it does not. Do not rescale phases after inspecting confirmation outcomes.

Primary paired comparisons use the same precomputed offered request file and horizon, with a reset and fresh baseline state per arm; implementation/cost must be validated. Randomize blocks and arm order, save both. The old persistent-cache pilot cannot establish reset independence. Load errors, admission skips, unfinished requests and drain are retained: equal offered load is not equal realized work. Prefer a load generator whose admission limit does not become the experimental bottleneck; if backpressure/capacity drops occur, report offered/admitted/completed distributions and a separate matched-completed-work sensitivity where feasible.

## 5. Arms, budgets and cost

Five policies use the shared engine: FB(1), RFB(3), SS(K=2), CR(2 consecutive valid recovery windows), HS(SS and CR). MU remains an SS(K=2) alias, never a sixth arm. Draft incident cap is six attempts, including failures and reactivation; all capture lengths are requested 1 s. Enable the existing changed-evidence reactivation rule for every policy; freeze thresholds/cooldown and distinguish initial stop from later monitoring/reactivation. Include a no-reactivation ablation only as a separate declared analysis. Missing/cached/unknown evidence cannot establish stability or recovery.

Additional arms:

- `no_profiler`: same client measurement and offered workload, without controller/NVML/Nsight; any reference-only server instrumentation common to arms is declared.
- `cheap_only`: same measurement + NVML/controller monitoring, heavy capture disabled and no diagnosis-sufficiency claim.
- `full_horizon_reference`: continuous reference collection, separately matched; workload horizon continues regardless of report availability. Do not feed post-horizon reports into online decisions.

Their implementations are pending; the existing pilot runner is **not** an executor for this matrix. In particular, omitting profiler RPCs while still launching the server under Nsight is not an unprofiled baseline.

Record actual capture kernel instances/report bytes; start RPC, control span (including synchronous flush), readiness wait, export, parse and decision latency; serving initialization, warmup, observation, drain and total persisted lifecycle separately. Do not add overlapping phases. Capture-active seconds remain null until domain-mapped boundaries are validated; otherwise withdraw active-time savings as a primary endpoint. Timing unavailable does not make the other cost observations invalid.

Draft development scale: six cases × eight arms × three repetition labels = **144 runs**, 4.8 observation hours; observation plus maximum drain alone is 6.6 hours. Startup, warmup, capacity/calibration, export, retries, sensitivity and confirmation are additional. This is a planning bound, not a rental recommendation or measured bill. Begin with a single feasibility block and instrument the actual cycle time before committing to the matrix. Confirmation repetition count requires observed block variance and a justified precision/effect target; three labels are engineering planning only.

## 6. Analysis and exclusions

Primary diagnosis outcome at each policy's initial stop: supported-complete, supported-partial, unsupported-concrete, unresolved, or reference-unavailable. Complete means the predicted cause set matches all supported mechanisms without unsupported additions. A generic `mixed` label does not establish complete coverage. The current single-string policy interface cannot represent cause sets: retain a concrete primary label for mechanics and store separately scored cause sets only after implementing and testing the mapping. Until then, report overlap omissions and partial coverage; never turn `mixed` into automatic correctness.

Report all activated episodes as the main denominator, including unknowns/budget exhaustion/failures; also report conditional results for adjudicable reference intervals, with their coverage. Report false activations/missed incidents and activation delay over all independently realized incidents. Do not omit failures from cost/latency accounting. Stable-but-unsupported counts require a concrete stability stop and adjudicable reference; missing reference is a separate category. Associate prediction with evidence acquisition interval and decision availability; flag captures crossing a reference transition instead of choosing whichever label scores best.

Separate terminal reasons: policy condition, fixed budget completion, hard exhaustion, timeout, capture failure, evidence missing, observation-horizon censoring, and recovery. Recovery is not diagnosis correctness. Report time to first supported diagnosis, later disagreement/change detection, reactivation count/delay and unresolved alternatives. Do not use future evidence as a controller feature.

For performance, report offered/admitted/completed rates, errors/timeouts, post-horizon completions, unresolved requests and completion p95 with denominators. Completion-only p95 can omit the slowest requests; show timeout/censoring alongside it rather than imputing success latency. Report paired effects versus unprofiled and cheap-only arms. Use independent session/block as the resampling unit after reset feasibility is established; windows/captures are correlated, not independent trials. Pilot repetitions have descriptive summaries only. Freeze confirmation comparisons and interval method before analysis; report all policies without a weighted winner score.

Exclude corrupted timing/device/report data only under predefined integrity checks; retain failed runs and exclusion reasons. A failed reference is not a negative diagnosis. Unexpected background activity, missing metrics, clock mismatch and sampler shutdown failures are explicit validity flags. Never repeat only an unfavorable arm until a favorable run appears; log retries and distinguish infrastructure failures from workload outcomes.

## 7. Sensitivity without fabricated evidence

Candidate calibration grids: latency trigger {1.25, 1.5, 2.0}, GPU trigger {80, 85, 95}, SS K {2, 3, 4}; later recovery-latency {1.05, 1.10, 1.20} and recovery GPU {60, 80, 95}. Values are proposals, not fitted defaults. Use one-factor sweeps first, then a small trigger × K grid chosen before confirmation.

Replay K only on complete, independently collected evidence with real availability and charged attempts; retain prefix identity and horizon censoring. An uncollected burst has no kernel evidence. Altered triggers, capture lengths, and reactivation times need live confirmation: they change what evidence exists and profiler perturbation. Replay results are conditional policy mechanics, not measured capture cost or equivalent live outcomes. Validate selected default and failure-prone settings live.

## 8. Freeze and next-rental checklist

- [x] CPU: implement typed measured-evidence/reference contracts and strict abstaining classifier input boundary (step 013).
- [x] CPU: collect actual response usage and exact queue gauges, and join ready kernel evidence with original-window availability (step 014; local fixtures).
- [x] CPU: implement typed interval wait/phase adapters, exact-window acceptance and controller initial-stop export (step 018; snapshots/fixtures only).
- [x] Bind collection/persistence/export to the CPU arm runner (step 019; custom CPU admission-history source).
- [x] Prepare pinned-stack feasibility gates, scoped metric inspection and read-only discovery (step 020; CPU fixtures).
- [x] Run fresh L4 discovery and two bounded serving probes (step 021; inventory/metric gates pass, no new captures).
- [x] Implement/test owned worker/reset/activity and validate one bounded capture (step 022; corrected invocation passes; initial failure retained).
- [x] Implement honest live feature cohort/availability mapping and independent reference/calibration preparation (step 023; CPU/offline checks, full live integration pending).
- [x] Implement bounded capacity/corpus probes and exact paired schedules; validate six cells on the L4 (step 024; maximum sustainable capacity still unestablished).
- [x] Bind candidate paired jobs to owned collection and assemble diagnostic artifact packets (step 025; actual adjudication/locking pending).
- [x] Implement retrospective evidence-gap audit/draft rubric and expose unset scientific coverage/mismatch limits (step 026).
- [x] Prepare pinned scheduler hooks/probes and prospective engineering-pilot rules; CPU-test (step 027; GPU/source-client mapping/scientific criteria pending).
- [ ] Wire owned startup and commission at most eight L4 requests before challenging cases (step 028). Finished-request histograms cannot automatically supply admission-window waits or exclusive GPU phase attribution.
- [x] CPU: implement feature/reference record validators and an abstaining interface; synthetic fixtures test mechanics only (step 013).
- [x] CPU: implement exact arrival-file driver, admission/skip/error records, bounded drain/censoring and serialized collection (step 015; local fixtures).
- [x] CPU: implement distinct capture-disabled/bounded/reference arm/session ownership and repeated server quiet/reset gates (step 016; bundled CPU targets only).
- [ ] GPU: validate corresponding real target/device quiescence, worker identity, capture mode, cache reset and cleanup semantics.
- [x] CPU: implement evaluator-only reference snapshots/locking, rubric/content hashes and offline initial-stop scoring (step 017; synthetic fixtures).
- [ ] Complete study freeze manifest, actual independent/blinded reference assessment and operator episode report with unresolved alternatives.
- [ ] GPU: verify metric availability/phase attribution; collect capacity, healthy and single-intervention reference/calibration data.
- [ ] GPU: show intended phase effects, drain/reset feasibility, per-range evidence readiness and valid cost scopes; confirm references are adjudicable.
- [ ] Freeze feature/rule/rubric/configuration versions; set confirmation repetitions/precision and blinded analysis procedure. If criteria fail, narrow diagnosis claims or remain explicitly unresolved.
- [ ] GPU: run randomized development blocks, resolve defects, then separately freeze and run held-out confirmation and selected sensitivity checks.

**Next action:** step 028 wires the opt-in scheduler into owned startup and commissions at most eight L4 requests with exact source/process/session/clock/ID/cache checks. Step 027 provides [bounded scheduler history/probes and prospective engineering rules](SERVER_EVENT_INSTRUMENTATION.md), checked on CPU only. Its first scheduling decision is not GPU start, and delay bounds cannot populate the existing wait/phase features. Challenging cases, observer perturbation, exact pressure selection/offered files and scientific coverage/mismatch/precision limits remain unresolved. Stop before challenges if commissioning fails. No reference adjudication/lock, calibrated diagnosis or main-study freeze is established.
