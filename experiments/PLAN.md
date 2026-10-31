# Study plan: checklist and implementation plan

Status: step 043 drops Phase A issue mining and rewrites the [proposal](protocol/EMPIRICAL_STUDY_PROPOSAL.md) around four empirical RQs (when cheap telemetry is enough; how much heavy profiling is enough; adaptive stopping cost and failure conditions; robustness), with evidence-based guidance as the paper's practical outcome. The [Phase A pilot](phase_a/PILOT_REPORT.md) is archived as a source of reproduction candidates only. Step 040's [related-work matrix](related_work_matrix.md) covers 16 papers. Step 044's [case screen](cases/SCREENING.md) found 7 reproduction candidates and 2 possible ones; steps 045–046 [reproduced](cases/REPRODUCTION.md) 5 cases on the L4 (#6240, #7619, #3087, #25418, #19732), with #7592 pending and #6923/#49013 failed. No GPU collection, labels or scientific results are claimed. See [progress](PROGRESS.md) and [step 046](progress/046_case_reproduction_round2.md).

## Objective and execution order

Develop a defensible empirical study of GPU profiling stopping decisions for LLM-serving performance diagnosis. The controller is the experimental instrument; the contribution is evidence about cost, diagnostic sufficiency, and failure conditions.

Execution order: **audit → define policies and metrics → implement independent evidence collection and online control → pilot → freeze protocol → collect held-out results → write findings and operator workflow**. Paper drafting and literature review can proceed alongside implementation.

The highest priority is validity, rather than adding more policies or a learned model. An honest negative result or narrower conclusion is acceptable.

## 0. Prerequisite: reconcile claims with the implementation

- [x] Create an artifact-to-claim inventory before reusing old results (step 003: 40 claim groups, with sources, findings, and dispositions).
- [x] Separate workload truth from classifier inputs and prediction outputs in the vLLM and microbenchmark runners (step 001). Expected labels remain evaluation metadata; classifier validity/calibration is still pending.
- [x] Merge the SS(K=2)/MU duplicate and define shared policy semantics (step 002).
- [x] Fix unknown/cached evidence, missing recovery metrics, and hard burst limits in the shared engine and replay adapter (step 002).
- [x] Audit which experiments made online decisions versus fixed-duration captures or replay (step 003; full T2-based serving control remains unvalidated).
- [x] Distinguish historical profile-process wall time from active capture and unmeasured startup/export phases (step 003).
- [x] Instrument explicit monotonic timing events and evidence-readiness gating with a fake backend before GPU integration (step 004).
- [x] Connect chronological cheap windows, asynchronous captures, and episode/recovery transitions in a CPU-only streaming controller (step 005).
- [x] Implement a truth-free streaming adapter from request completions/GPU samples to closed windows (step 006).
- [x] Connect request/sample producers through a serialized queue and validate a CPU HTTP/sampler dry run (step 007).
- [x] Add an optional isolated NVML sampler and deployment preflight (step 008; fake bindings/workers and passive inventory only).
- [x] Implement the profiler command/lifecycle harness with fake-executable CPU tests (step 009; synthetic acknowledgements/reports only).
- [x] Implement and smoke-test a pinned single-worker L4/Nsight/vLLM capture path (step 010; synchronous report flush, measured worker/device coverage).
- [x] Complete/audit the engineering pilot (step 011, corrected `pilot_002`); preserve abstention, missing active-capture measurements and the telemetry-deficient first matrix.
- [ ] Recover a paper source that matches the submitted PDF before editing it.

### Instructions

1. Preserve the submitted PDF, existing result directories, and current scripts as the original study. Use new revision output directories and record the code commit and configuration for every new run. Do not silently regenerate old tables with changed semantics.
2. Trace each paper result to its script, raw inputs, metric formula, and evidence mode. Suggested output: `experiments/artifact_audit.csv`, with columns `claim, table, runner, raw_paths, evidence_mode, validity_issue, disposition`.
3. Address these observed issues first:

| Observed code behavior | Location | Required action |
|---|---|---|
| Suspicious windows received `scenario["label"]` as their diagnosis | Original `RQ1/scripts/run_vllm_smoke.py:451` | Code fixed in step 001; regeneration of affected diagnosis results remains pending. |
| Diagnosis scores explicitly boosted the configured expected label | Original `RQ1/scripts/run_vllm_smoke.py:246` | Boost removed in step 001; margins remain uncalibrated heuristic scores. |
| Microbenchmark diagnosis/trigger branches used workload names | Original `run_microbenchmarks.py:260` and `:363` | Removed in step 001; high utilization alone now abstains on the compute/mixed distinction. Kernel-backed diagnosis remains pending. |
| Window aggregation occurs after `run_scenario` completes | `RQ1/scripts/run_vllm_smoke.py:605` | Add streaming window closure for online decisions; retrospective aggregation is not online control. |
| Automatic and fixed modes use predefined workload durations | `RQ1/scripts/run_vllm_nsys_compare.py:81` | Hold the request schedule and observation horizon constant; vary capture decisions instead. |
| Reported `duration_s` times the entire `nsys` subprocess, including startup/shutdown | `RQ1/scripts/run_vllm_nsys_compare.py:220` | Record active capture intervals, export/parse time, server startup, and total wall time separately. Audit old “profiler duration” claims. |
| “Live policy validation” reads replay-selected durations and runs a fixed capture | `RQ4/scripts/run_live_policy_validation.py:89` and `:278` | Describe as live capture at a replay-selected duration; implement an online decision loop for actual live policy validation. |
| SS at K=2 and MU used equivalent label-repeat conditions | Original `RQ4/scripts/analyze_policies.py:113` | Fixed in step 002: five distinct default policies; MU remains an SS(K=2) compatibility alias. |
| Repeated unknown labels could satisfy stability | Same original function | Fixed in step 002: unknown, missing, provisional, healthy, and cached observations reset concrete-label streaks. |
| Policy loops could select a stop beyond the six-burst cap | Same original function | Fixed in step 002: incremental engine enforces a hard attempt cap and explicit exhaustion. |
| Missing telemetry became zero and could count as recovery | Original `RQ4/scripts/analyze_policies.py:96` | Fixed in step 002: both valid counters and observed absence of suspicion are required, over a configurable recovery streak (default 2). |
| Replay prefiltered suspicious windows; `premature_stop` meant never correct, and later suspicion meant re-escalation needed | Original `RQ4/scripts/analyze_policies.py:163` and `:226` | Step 002 preserves the first-episode timeline and scores intentional stops at their final label. Later suspicion is explicitly a proxy; actual retrigger integration and independent references remain pending. |

4. Microbenchmark truth-dependent classification and triggering were audited and corrected in step 001. Other microbenchmark control and profiling paths still require audit.
5. Add meaningful regression checks for the validity fixes: identical telemetry with different scenario names must yield identical predictions; unknown/unknown must not imply sufficiency; missing counters must not imply recovery; six bursts must remain a hard cap; online and replay decisions must agree on the same valid prefix.

Audit evidence: SS(K=2) and MU chose identical stops on all 21,844 enumerated label sequences of lengths 1–7 over four values (empty, A, B, unknown). Small probes also reproduced unknown-label stopping, stopping after the cap, and recovery with absent telemetry. These are code checks, not workload experiments.

**Done when:** every retained claim has traceable inputs and accurately named measurements; the new classifier cannot access expected labels; affected old accuracy and stopping claims are marked for replacement or withdrawal. Old raw telemetry may still be reusable, but reconstructing valid classifications requires the actual evidence available at each decision point.

Step 001 note: `RQ1/scripts/evidence_classifier.py` defines an explicit measured-feature interface and has no expected-label/workload imports. `vllm_expected_labels.py` holds intended labels for metadata only. New rows/summaries identify `cheap_evidence_v2` and T0/T1 provenance. Existing accuracy, signal-ranking, and stopping results are historical and must not be reused as evidence for the revised classifier. See the progress files for tests and remaining limits.

Step 002 note: `experiments/tracing/policies.py` provides the CPU-only incremental engine. RQ4 replay uses this engine; both RQ1 runners use its concrete-label stability helper. Explicit capture/evidence IDs support cached-evidence detection and budget accounting. Legacy replay rows without IDs use a documented hypothetical-burst assumption. See [step 002](progress/002_stopping_policy_semantics.md). Full online capture integration is not implemented yet.

Step 003 note: [the claim inventory](audit/generated/artifact_audit.csv) and [timing audit](audit/TIMING_AUDIT.md) distinguish reusable observations from claims needing replacement. Findings include 201 unique multiclass windows versus 402 duplicate representations; Table VI kernel-count mismatches; a Table VIII signal/F1 mismatch; 5 s windows and 2/8 s workload segments in L4 microbenchmark manifests; and 817 local profiler files that are LFS pointers. Historical savings use profile-process wall time. The cheap-polling p95 results reproduce from raw requests, but do not measure full streaming-controller overhead. Original artifacts and paper tables remain unchanged.

Step 004 note: `experiments/tracing/timing.py`, `profiler.py`, and `evidence_gate.py` implement explicit monotonic event scopes, a nonblocking fake pipeline, and a readiness gate before classification/policy updates. Failed attempts consume budget without incrementing stability. Capture-active time stays unknown unless synthetic interval confirmation is explicitly enabled; full persisted lifecycle time stays unknown. The [runnable demo](README.md) and its outputs are synthetic, not empirical results. See [step 004](progress/004_timing_events_and_fake_backend.md).

Step 005 note: `experiments/tracing/controller.py` consumes chronological `CheapWindow` observations, activates captures, services parsed-evidence decisions, monitors ongoing incidents after tracing stops, and closes on sustained recovery. Reactivation shares the original episode cap. Startup/evidence timeouts and horizon cancellation are tested with the fake backend. `stopping_v3` distinguishes cheap-recovery identities from fresh diagnosis identities. The legacy serving runner is not yet connected; raw streaming aggregation is next. `HealthyBaseline` is calibration data, while experimental baseline strategies will run on the same GPU workload. See [step 005](progress/005_streaming_episode_controller.md).

Step 006 note: `experiments/tracing/aggregation.py` now emits controller windows from timestamped request completions and GPU samples as time advances. It enforces a fixed horizon and arrival allowance, preserves missing data, records late/drain events separately, and includes final-boundary events once. Request failures and known slow pending requests cannot establish healthy recovery; count metadata enters `streaming_v2`. The supplied healthy calibration is not derived from the first window. Raw-event integration demos remain synthetic. Actual serving/NVML producer wiring is step 007. See [step 006](progress/006_raw_request_and_gpu_sample_streaming.md).

Step 007 note: `experiments/tracing/producers.py` connects real nonstreaming HTTP request lifetimes and async sample callbacks through a serialized queue to the window adapter/controller. Admission is paced and concurrency-limited, with explicit missed slots, request timeouts, bounded drain, errors/cancellation, monotonic receipt records, and unchanged supplied calibration. Four local fake-service fixtures exercise the bridge; samples/profiler evidence remain synthetic and diagnoses abstain. This is CPU development, not live GPU evidence. See [step 007](progress/007_http_producers_and_serialized_bridge.md). Step 008 prepares optional NVML sampling and deployment checks without a GPU; actual NVML/Nsight validation requires NVIDIA hardware.

Step 008 note: `experiments/tracing/nvml_sampler.py` isolates optional native NVML calls in a spawned worker, verifies a configured physical GPU UUID, rejects MIG/invalid readings, and bounds startup/read/shutdown/cancellation. Parent receipt timestamps do not establish the GPU sampling interval. `preflight_gpu.py` defaults to passive inventory and syntax-only endpoint/calibration checks; opt-in hardware probes never imply capture readiness. [The profiler contract](REAL_PROFILER_CONTRACT.md) defines remaining acknowledgement, coverage, clock, readiness and cleanup requirements. All telemetry tests use fake bindings/workers; no GPU was queried and the real backend remains pending. See [step 008](progress/008_optional_nvml_and_deployment_preflight.md).

Step 009 note: `experiments/tracing/command_profiler.py` implements owned POSIX command groups, explicit synthetic start/stop acknowledgements, stage deadlines, report/export/parse validation, artifact hashes and bounded cleanup. `streaming_v3` waits for backend cleanup before spending the next capture attempt. The fake executable exercises real subprocess behavior but produces no GPU evidence; the harness accepts synthetic provenance only. Captured-active time, serving startup and total lifecycle are not inferred from command wall time. See [step 009](progress/009_profiler_command_lifecycle_harness.md). A target-specific Nsight driver plus NVIDIA hardware checks are next; operator reporting/protocol work can continue on CPU while hardware is unavailable.

Step 010 note: live NVML, native CUDA capture, and persistent Qwen2.5-7B/vLLM worker capture passed on the provided L4. The pinned backend uses actual CUDA-worker and Nsight-start acknowledgements plus synchronous range flushing and validated SQLite export/parse. The asynchronous/deferred path failed its readiness gate and is retained as a failure. `streaming_v4` adds an explicit reactivation switch; the pilot prospectively disables it for policy comparisons. The classifier abstains and active capture stays unknown. See [step 010](progress/010_l4_hardware_capture_integration.md). The first matrix exposed cross-episode NVML sampler reuse (13 runs with missing telemetry); it is preserved as telemetry-incomplete. Fresh per-episode sampler ownership and a regression check are implemented, and the 18-run rerun completed with 39 captures, zero request/sampling errors, no missing GPU windows, matching artifact/source hashes and verified cleanup ([step 011](progress/011_l4_live_engineering_pilot.md)); it cannot replace independent diagnosis/reference validation. Steps 012–020 prepare CPU contracts, playback/arm/reference lifecycles and pinned feasibility gates. Steps 021–025 validate bounded live discovery, owned barriers/reset/capture, receipt mapping, corpus probes and paired collection. Step 026 audits the evidence gaps; step 027 prepares pinned scheduler hooks and prospective engineering rules. Step 028 commissions the event collector with eight L4 requests and exact source/clock/ID/cache checks. Next step 029 prepares exact prospective challenge files and observer controls before bounded challenge execution, calibration or the main study.

## 1. Make the empirical contribution explicit

- [ ] Write a contribution statement centered on evidence, rather than policy complexity.
- [x] Build a current related-work comparison from primary sources (steps 039–040; 16 papers read).
- [ ] Turn broad claims into falsifiable questions.
- [ ] Tie each eventual finding to a specific experiment and its limitations.

### Instructions

1. Use this provisional framing:

   > We investigate when short GPU profiler captures provide sufficient evidence for LLM-serving performance triage, comparing fixed-cost, diagnosis-stability, and recovery-gated stopping under changing and overlapping workload conditions.

2. Read the closest work before claiming an unstudied gap. Start with the two papers named by Reviewer B:
   - [Zhou et al., ICS 2022](https://www.jokeren.tech/publication/zhou-2022-low/): the author abstract explicitly describes adaptive epoch profiling. The earlier blanket statement that GPU tools are not adaptive needs correction.
   - [StriaTrace, OSDI 2026](https://www.usenix.org/conference/osdi26/presentation/wu-haonan): the official abstract describes detailed tracing during abnormalities and production diagnosis. Anomaly-triggered detailed tracing alone cannot carry the novelty claim.
   - Recheck Astraea, TraStrainer, and relevant profiler capture/sampling mechanisms already cited in the paper.

3. Create `experiments/related_work_matrix.md`. For each source, record the exact section supporting its collection unit, activation rule, stopping rule, budget, diagnostic target, validation setting, artifact availability, and limitations. Mark unanswered cells as unknown rather than inferring absence from an abstract. Decide whether a faithful executable baseline is feasible; otherwise document the conceptual comparison.
4. Investigate these candidate contributions:

| Question | How to establish it | What would falsify or narrow it? |
|---|---|---|
| Does a stable label imply sufficient evidence? | Measure stable-but-wrong stops against independent evidence, including overlapping causes. | Persistent wrong labels despite stability. |
| Is diagnosis completion different from incident recovery? | Compare diagnosis-based and recovery-gated policies on persistent, correctly diagnosed incidents. | Extra recovery-gated cost without better diagnosis; this is still a useful result. |
| Can cheap recovery safely replace diagnostic evidence? | Test actual temporary lulls and unresolved incidents without editing labels. | Recovery signals fire before evidence supports a diagnosis. |
| Do policy rankings survive threshold and workload changes? | Freeze calibration, evaluate held-out workload shapes, and report sensitivity. | Rankings change substantially or only one narrow setting works. |

5. Draft contributions as study outputs: an explicit stopping model, a reproducible benchmark/protocol, measured cost–diagnosis tradeoffs, and observed failure conditions. Only claim a new algorithm if there is an actual differentiated algorithmic advance.
6. Replace “safest stopping signal” with a conditional finding unless independently validated results support the stronger statement. Separate policy consistency from correctness: a rule designed around label repetition cannot be validated solely by labels being repeated.

**Done when:** the introduction states what knowledge the study adds, why the closest work does not already establish it, and exactly which evidence supports each conclusion. A simple controller can remain if the empirical findings are substantive.

## 2. Strengthen evidence with live cases and threshold sensitivity

- [x] Implement the initial persistent-serving online capture/readiness loop (step 010; one worker/L4, synchronous flush). Diagnosis-based sufficiency still needs independent calibration/validation.
- [ ] Add evolving, intermittent, and overlapping live cases.
- [ ] Establish reference diagnoses independently of controller output.
- [ ] Freeze calibration before held-out evaluation.
- [ ] Measure full-controller perturbation and equal-workload baselines.
- [ ] Report uncertainty and failure cases without arbitrary pass scores.

### Protocol prepared on CPU (step 012)

- [x] Specify separate controller, workload-driver, blinded-reference and scoring paths.
- [x] Draft reference rubrics, calibration/development/confirmation separation, six workload cases, five policies and three controls/reference arms.
- [x] Specify cost/missingness/outcome definitions, sensitivity limits, reset/randomization requirements and freeze blockers.
- [x] Compile a deterministic draft development design with phase/split/budget checks and separate evaluator metadata.
- [x] Implement measured request/server/kernel and evaluator reference-record contracts plus an abstaining adapter (step 013; CPU-only).
- [x] Implement actual response-usage and exact queue-gauge collectors with interval/availability joins (step 014; local HTTP/synthetic profiler only).
- [x] Implement exact offered-arrival playback, admission/outstanding/drain/censoring accounting and serialized collection (step 015; CPU fixtures).
- [x] Implement distinct unprofiled/cheap-only/policy/reference session ownership and independent reset/quiescence checks (step 016; CPU fixtures).
- [x] Implement durable evaluator reference storage/locking, artifact verification and explicit scoring (step 017; synthetic fixtures).
- [x] Implement initial-stop export and interval wait/phase-attribution adapters (step 018; CPU snapshots/contracts).
- [x] Bind collection, measured-observation persistence and export to the CPU arm runner (step 019; owned CPU history source).
- [x] Prepare gated pinned-stack feasibility contracts, scoped metric inspection and executable read-only discovery (step 020; CPU fixtures).
- [x] Run fresh L4 capability discovery and two bounded serving probes (step 021; inventory/metrics pass, owned activity gates pending).
- [x] Implement/test owned worker barrier/reset/activity and validate one bounded capture/readiness/serving-continuation pilot (step 022; corrected invocation passes; failed invocation retained).
- [x] Implement honest live measured-feature cohort/availability mapping and prepare independent reference/calibration collection (step 023; CPU/offline checked, live integration pending).
- [x] Implement bounded capacity/corpus probes and paired exact offered files; CPU-test and validate six L4 cells (step 024; maximum capacity not established).
- [x] Bind candidate jobs to owned live collection and assemble independent diagnostic artifact packets (step 025; four jobs pass; adjudication/locking pending).
- [x] Implement retrospective assessment/draft rubric and expose unset coverage/mismatch limits and feature/challenging-case gaps (step 026; no prospective thresholds/adjudication).
- [x] Prepare pinned scheduler admission/first-decision/terminal hooks and prospective engineering coverage/challenge rules; CPU-test (step 027; live validation/scientific criteria pending).
- [x] Wire owned startup and commission at most eight L4 requests with real clock/ID/cache checks before challenges (step 028; all eight responses/24 events pass).
- [x] Prepare exact challenge schedules, deterministic pressure selection and independent observer/cache/incomplete-evidence controls (step 029; CPU packet and fixtures, no new GPU work).
- [x] Implement/test the owned concurrent challenge runner and actual cache/ID/receipt/probe/injection integration (step 030; CPU checks, engineering source snapshot).
- [x] Deploy/execute/audit the frozen bounded L4 attempt and verify actual configuration/work/coverage/cleanup (step 031; first offered-work check fails, fifteen later jobs uncompleted).
- [x] Prepare a separate development-informed protocol/packet on CPU (step 032; v2 capped grid, exact rational arrivals and unchanged completeness/coverage guards).
- [x] Deploy/execute/audit the exact v2 L4 snapshot (step 033; all sixteen jobs pass; development provenance, raw bytes and quiet-log persistence limitation retained).
- [x] Isolate quiet-evidence persistence by episode and add a multi-job CPU regression/provenance index (step 034; 565 passing CPU tests and preserved live re-audit).
- [x] Audit scheduler wait-bound precision/cohort semantics and expose scientific feature/reference criteria (step 035, CPU-only).
- [x] Implement criterion-completion/validation and evaluator-only assessment worksheets (step 036, CPU-only); keep unset scientific decisions blocked and no automatic reference export.
- [ ] Clear broad CPU regression before another engineering freeze; step-036 full suite remains unresolved under host timing pressure.
- [ ] Prepare justified scientific-criteria proposals and a prospective disjoint confirmation design for review (step 037, CPU-only).
- [ ] Establish actual independent reference diagnoses and assessor/blinding procedure on collected evidence.
- [ ] Validate real GPU target/worker quiet/reset and profiler/session behavior before confirmation.
- [ ] Supply validated interval wait/prefill statistics; these remain explicitly unsupported by the queue collector.
- [ ] Fit/validate diagnosis criteria and verify phase/arm feasibility on GPU; freeze a confirmation protocol afterward.

See [the protocol](protocol/L4_EXPERIMENT_PROTOCOL.md), [draft configuration](configs/l4_protocol_draft.json) and [step 012](progress/012_cpu_experiment_protocol.md). The proposed 144-run development matrix needs 4.8 observation hours, up to 6.6 including maximum drain, plus unmeasured setup/calibration costs; start with one feasibility block. No new GPU use, fitted classifier, independent reference or held-out result is claimed. Do not run the old pilot runner as though it implemented these additional arms.

Step 013 adds strict [measured and reference contracts](protocol/MEASURED_EVIDENCE_CONTRACT.md), rejecting unknown input fields, future/unmapped evidence, invalid coverage and mismatched reference joins. The adapter still abstains; reference validation checks declarations and content identities, not causal truth, blinding or actual durable locking. [Step report](progress/013_measured_features_and_reference_contracts.md). No new GPU collection or fitted diagnosis is claimed.

Step 014 adds [feature collection and temporal joining](protocol/FEATURE_COLLECTION.md): actual response token usage, exact declared queue gauges, sparse/partial/missing semantics, original-window joins to parsed evidence, and delayed fake-profiler/HTTP fixtures. Wait p95/prefill fraction remain unsupported; the legacy live runner is unchanged and classification abstains. [Step report](progress/014_feature_collectors_and_temporal_bridge.md).

Step 015 implements [exact offered workload playback](protocol/OFFERED_WORKLOAD_PLAYBACK.md): immutable request files, exact/canonical hashes, explicit admission/skips/errors, horizon/drain/censoring records, bounded receipt queues and serialized feature/evidence service. Six loopback fixtures conserve IDs while exhibiting different realized work under the same offered file. Local client cleanup does not establish server/GPU quiescence; distinct arm/reset management is next. [Step report](progress/015_exact_offered_arrival_playback.md).

Step 016 adds [distinct owned arm/session lifecycles and reset gates](protocol/EXPERIMENT_ARM_LIFECYCLE.md). Eight CPU arms reuse the same offered/configuration contract while controlling capture capability, opening seven fresh cheap samplers and independently observing server queue/running/report/capture clearance before token/generation-acknowledged resets. Client cleanup is explicitly insufficient. Four injected failures and an initial development cleanup-visibility failure are retained. No GPU quiescence, baseline cost or diagnosis validation is claimed. [Step report](progress/016_arm_lifecycles_and_reset_quiescence.md).

Step 017 adds [durable reference locking and offline scoring](protocol/LOCKED_REFERENCE_SCORING.md): content-addressed evidence/rubric snapshots, external lock anchors, byte verification before prediction reads, complete logged-episode denominators and explicit partial/unsupported/unresolved outcomes. The 12 saved predictions are hand-authored synthetic counterexamples; blinding, causal truth and deployed diagnosis are not established. [Step report](progress/017_locked_references_and_offline_scoring.md). Step 018 implements these CPU adapter/export contracts; real GPU calibration remains pending.

Step 018 adds [interval statistics and initial-stop export](protocol/INTERVAL_METRICS_AND_EXPORT.md): admission-cohort wait histogram deltas, explicit phase attribution or unavailability, exact-window acceptance and exported initial stops from actual CPU controller cases. Failures retain null acquisitions; scorer v2 keeps policy reasons and execution statuses separate. No cause mapping or fitted diagnosis is introduced. [Step report](progress/018_interval_metrics_and_controller_export.md). Step 019 implements CPU collection/persistence/export; actual GPU metric/reset feasibility and calibration remain pending.

Step 019 adds [CPU source binding and automatic arm exports](protocol/ARM_COLLECTION_AND_EXPORT.md): actual admission-cohort waits, checked acquisition/receipt/source identity, bounded interval queues, raw fingerprints, measured observations and exported initial policy stops. Cheap/capture intervals remain separate; phase attribution and joint calibrated diagnosis are unavailable. The unprofiled arm does not enable the additional interval event history. [Step report](progress/019_arm_collection_persistence_and_export.md). Step 020 prepares these gates/read-only discovery; fresh L4 discovery is next (021), before activity validation, calibration or freeze.

Step 020 adds [pinned-stack feasibility gates and read-only discovery](protocol/LIVE_FEASIBILITY.md). Source review identifies finished-request histograms, which are incompatible with automatically supplying the CPU admission cohort or exclusive GPU phase fractions. Exact-model/engine inspection retains unsupported mappings. Ordered inventory/metric/reset/capture/cleanup contracts pass CPU fixtures; the real adapter performs discovery only and cannot pass owned activity gates. [Step report](progress/020_live_feasibility_harness_and_capability_gates.md). Step 021 completes fresh L4 discovery; step 022 validates owned activity and one bounded capture. Step 023 implements that mapping/preparation; step 024 validates bounded throughput/corpus collection. Next is paired collection/reference preparation (025).

Step 021 completes [fresh L4 capability discovery](hardware/l4_20261028/REPORT.md) on the supplied host: pinned inventory/metrics passed, two 16-output-token probes succeeded, and queue/prefill/decode histogram counts advanced 0→1→2. These are feasibility observations, not calibrated diagnoses or a valid admission-window/phase mapping. Quiet/reset remains unavailable, capture skipped and zero new captures were taken. Exact deployed source/model hashes and raw results are backed up; serving parent/worker are absent and GPU memory is 0 MiB. [Step report](progress/021_l4_live_capability_discovery.md). Step 022 subsequently validates owned activity and one capture; the rental itself remains running.

Step 022 completes [owned worker/reset/capture feasibility](hardware/l4_20261028/ACTIVITY_REPORT.md). Fresh session/generation/token-bound CUDA barriers and repeated quiet observations pass around a verified worker restart. One corrected bounded capture contains 5,992 kernels on the expected worker/GPU; both serving requests succeed and all owned processes are removed. The initial callback-path timeout remains failed; absolute paths and a CPU regression test fix its cause. All 399 CPU tests pass; both source snapshots and 110 artifact hash entries are audited. Active capture remains unknown, the classifier is not run, and study/diagnosis/freeze flags remain false. [Step report](progress/022_owned_worker_reset_and_capture_feasibility.md). Step 023 implements that mapping/preparation on CPU; step 024 validates the bounded L4 probes and candidate schedules. Next is paired collection/reference preparation (025).

Step 023 implements [live feature mapping and calibration preparation](protocol/LIVE_FEATURE_MAPPING.md). Raw metric receipts carry independently verified session/generation/PID/UUID/series/clock scope; exact queue samples enter measured windows with client/GPU inputs, persisted raw hashes and bridge target checks. Finished-request histograms remain diagnostic sidecars and cannot supply unsupported interval/phase statistics. All 427 CPU tests pass (28 new); 12 saved L4 receipts map offline without inventing windows or decisions. The preparation packet lists 18 planned collection jobs and zero calibration observations, with evaluator-only interventions rather than fabricated reference labels. No GPU activity, fitting, calibration, study or freeze is enabled. [Step report](progress/023_live_feature_mapping_and_calibration_preparation.md). Step 024 subsequently implements this bounded pilot and candidate paired files; see below for current next steps.

Step 024 completes [the bounded throughput/corpus pilot](hardware/l4_20261028/CAPACITY_REPORT.md). Two fresh workers run six eight-second closed-loop cells at concurrency 1/2/4 over pinned 17-token and 1,072-token prompts. All 68 probe requests and two warmups succeed; 54 completions fall in horizon and 14 in drain. Six windows retain 96 real metric receipts and explicit unsupported fields. All 439 CPU tests pass (12 new), and 379 artifact hashes/70 source entries verify. Four paired jobs share exact offered bytes but are not executed. Increasing rates through concurrency 4, prefix caching/repeated prompts and short fixed-order probes do not establish maximum capacity or diagnosis. Owned workers are absent and memory is 0 MiB; the rental remains running. [Step report](progress/024_bounded_capacity_and_corpus_pilot.md). Step 025 subsequently validates paired collection and produces an assessment packet; next is assessment/rubric and coverage/mismatch limits (026), before fitting or the main study.

Step 025 completes [owned L4 paired collection](hardware/l4_20261028/PAIRS_REPORT.md): four fresh workers run the same offered bytes within each pair; all eight scheduled requests and four warmups succeed. Sixteen windows retain 64 raw metrics; two full traces parse with 21,308/23,044 kernels on expected workers/GPU. The ten-artifact packet records realized-run differences and awaits blinded assessment; zero references are created/locked and no classifier/policy runs. All 451 CPU tests pass (12 new); 472 artifact hashes/360 archived source entries verify, and all owned workers are absent with 0 MiB memory. This low-rate pilot does not establish challenging-case diagnosis, same-execution truth, capture-active savings or calibration. [Step report](progress/025_owned_paired_collection_and_assessment_packet.md). Step 026 subsequently audits those gaps and proposes a draft queue-pressure scope; next is clock-bound event instrumentation and prospective coverage/challenge rules (027). The rental remains running.

Step 026 completes [retrospective evidence assessment and draft scope](protocol/EVIDENCE_ASSESSMENT.md). All 472 source artifact hashes verify; raw request-ID comparisons show equal observed token work but only two latencies per role and no prospective mismatch tolerance. All 64 sampled queues are zero, point-sample gaps reach about 518 ms and all 16 windows lack valid request p95. Both traces reparse, without same-execution GPU clock attribution. The draft proposes queue-pressure-only features and defers prefill claims; limits remain null, current classification stays unchanged, and a blank hash-bound worksheet can record unresolved evidence only. All 467 CPU tests pass (16 new); zero references are created/locked and no GPU activity is launched. [Step report](progress/026_evidence_assessment_rubric_and_scope.md). Step 027 subsequently prepares pinned scheduler hooks and prospective engineering-pilot rules; next is bounded live commissioning (028), before challenges, adjudication or fitting.

Step 027 completes [scheduler-event preparation and prospective engineering rules](protocol/SERVER_EVENT_INSTRUMENTATION.md). Five installed vLLM source files are preserved read-only. An opt-in exact-source/version/synchronous-single-worker subclass records engine admission, first positive CPU scheduling and terminal brackets, with bounded history, explicit drops/faults and fresh same-host file probes. Delay bounds retain uncertain boundaries, pending/aborted requests and missing GPU/client clock attribution; they do not populate existing wait/phase metrics. All 484 CPU tests pass at that step (17 new); five saved cases are explicitly synthetic and no GPU workload/package/default change is launched. Prospective engineering guards and rate/removal/lull/unresolved templates remain non-executable; scientific limits remain unset. [Step report](progress/027_scheduler_events_and_prospective_pilot_rules.md). Subsequent live commissioning is recorded below.

Step 028 completes [owned scheduler-event commissioning](hardware/l4_20261028/EVENTS_REPORT.md). One fresh L4 worker completes eight sequential requests, with 24 complete events, zero drops/faults, exact source-pinned client/engine ID joins and actual prompt/output token checks. Two fixed idle RPC probes add no inference requests; actual cache configuration is disabled and PID/session/clock checks pass. Four quiet barriers and independent process/group/0 MiB checks pass after cleanup. All 494 CPU tests pass (ten new); off-host backup verifies 46 artifact hashes, 142 archive entries, 81 runtime source entries and eight installed ID/CLI pins. Zero captures, challenges or references are added; wait/phase mapping, observer effects, scientific tolerances, calibration and main-study freeze remain unresolved. [Step report](progress/028_owned_scheduler_event_commissioning.md). Next step 029 prepares exact challenge files, pressure selection and observer/cache/incomplete-evidence controls on CPU before bounded GPU validation. The rental remains running.

Step 029 completes [exact challenge/observer-control preparation](protocol/EVENT_CHALLENGE_PROTOCOL.md) on CPU. Sixteen offered files and sixteen prospective jobs bind the pinned corpus to the commissioned stack. First collector-off ladder selection requires exact successful work, complete scoped queue coverage and a sustained sampled-positive streak; no candidate/incomplete evidence stops dependent cases. Reversed-order controls share exact wire work and independently specified cache-off settings. A consumer-only withholding gate preserves raw receipts and returns unresolved for missing/late/foreign evidence. All 511 CPU tests pass (17 new), and forty-two prepared/fixture hashes verify. Six saved cases remain synthetic; no GPU jobs, references or calibration are created. [Step report](progress/029_exact_challenges_and_observer_controls.md). Next step 030 implements/tests the owned concurrent runner and effective off-role cache/raw ID/probe/injection integration before bounded GPU validation. Scientific limits and main-study freeze remain pending.

Step 030 completes [owned concurrent challenge execution infrastructure](protocol/CHALLENGE_EXECUTION.md): actual-worker configuration RPCs, raw concurrent ID/model/token checks, scoped queue/event collection, fixed asynchronous probes, deadline-based consumer withholding, matched offered-cohort review and charged fail-stop lifecycles. All 531 CPU tests pass (twenty new); three synthetic episodes verify expected success/failure and cleanup. Ninety-one fixture artifact hashes and 171 frozen source/input entries verify, with twelve installed source pins. The engineering source snapshot is immutable; hardware validation and main-study freeze remain false. Read-only SSH retrieves worker inheritance sources but runs no GPU workload. [Step report](progress/030_owned_concurrent_challenge_runner.md). Next step 031 deploys the exact archive and audits the bounded L4 campaign, preserving failures/no-pressure outcomes before scientific calibration or adjudication.

Step 031 [executes and audits the frozen L4 attempt](hardware/l4_20261028/CHALLENGES_REPORT.md). The first collector-off ladder admits/completes ninety of 124 offers and skips thirty-four at the 32-client cap, all in the 8 requests/s phase; the warmup also succeeds. There are zero request errors, censors or late/horizon skips. The offered-work guard fails, no rate is selected, no retry occurs and fifteen later jobs remain uncompleted. Actual configuration, 120 queue receipts, 362 artifact hashes, 171 frozen entries, ninety runtime source entries and all model/installed pins verify; owned cleanup returns to 0 MiB. Descriptive positive queue samples in the 4 requests/s phase do not retrospectively repair eligibility. [Step report](progress/031_frozen_l4_campaign_and_capacity_failure.md). Next step 032 prepares a separate development-informed protocol version on CPU, with a finite ladder capped at 4 requests/s as one concrete candidate, then validates fresh after new tests/source/packet hashes. The rental remains running; no diagnostic reference, capture, calibration or main-study result is produced.

Step 032 completes [a separate v2 development protocol](protocol/EVENT_CHALLENGE_PROTOCOL_V2.md). The fixed 0.5/1/2/3/4 requests/s ladder has 84 offers; exact rational offsets avoid an extra 3 requests/s boundary arrival. All client/session/journal/time/coverage/completeness gates and reversed controls remain unchanged; maximum campaign work falls to 1,932 warmup-inclusive attempts. Version-specific runner/selector/loader/freeze integration rejects cross-version data and altered guards. All 549 CPU tests pass (eighteen new); two older CPU timing fixtures gain observation margin without changing GPU guards, and failed/diagnostic logs are retained. The new archive binds 184 entries and twelve source pins; 44 packet/fixture hashes plus 171 original archive entries/362 failed-run artifacts verify unchanged. All sixteen v2 jobs remain unexecuted; no SSH/GPU workload occurs. [Step report](progress/032_development_informed_v2_protocol.md). Next step 033 validates fresh from the new snapshot; the v1 failure is never retrospectively repaired or used as independent confirmation.

Step 033 [validates the unchanged v2 snapshot fresh on the L4](hardware/l4_20261028/CHALLENGES_V2_REPORT.md). All sixteen jobs pass: 1,536 offers plus sixteen warmups complete, with zero skips/errors/censors and a first-off selection of 3 requests/s. The 1,920 queue receipts, ninety real source probes and 6,142 artifact hashes verify; six deliberately withheld consumer windows stay unresolved. Eight paired reviews have no flags across 22 evaluable windows, without establishing equivalence. Source/model pins, 64 unique quiet barriers, off-host backup and independent cleanup to 0 MiB pass. A cumulative quiet-log persistence defect retains 480 historical duplicate rows with original-job-relative paths; the whole-campaign audit resolves their original bindings/files without rewriting data. Next step 034 fixes per-job isolation and adds a multi-job regression/provenance index on CPU. Scientific feature/reference acceptance and calibration remain pending; the rental remains running. [Step report](progress/033_fresh_v2_l4_validation.md).

Step 034 [fixes working-source quiet persistence and indexes historical provenance](examples/quiet_evidence_isolation/REPORT.md). Per-output logs preserve same-episode reset generations while rejecting overwritten files or inherited logs. All 565 CPU tests pass (sixteen new); an archived-code reproduction fails with eight rows instead of four in the second job. The separate index maps 544 saved rows to 64 original barriers, including 480 historical duplicates, and verifies all 6,142 live artifacts. The original live audit reproduces exactly without writing its report; both archives/descriptors/backups and all 362 failed-v1 artifacts remain unchanged. Old frozen source correctly rejects the revised working tree; no new freeze or live validation occurs. Next step 035 audits bound precision/cohort semantics and scientific feature/reference criteria on CPU. [Step report](progress/034_quiet_evidence_isolation_and_provenance.md).

Step 035 [audits scheduler-bound precision and cohort semantics offline](examples/scheduler_bound_audit/REPORT.md). All 6,142 original artifact hashes verify, with 958 complete source-observed case requests and exact reproduction of 96 consumer gates. The consumer retains 798 observations while 160 withheld observations remain offline-only. Scheduling versus client admission/completion differs in 40/60 and 52/60 source windows; 32 raw cohorts are below twenty requests and eight are empty. Median/sample-p95/max bound widths are 0.2362/0.3252/0.7692 ms; no scientific precision criterion is fitted. Probe-time versus historical pending counts differ in one window. All 579 CPU tests pass (fourteen new); two older CPU timing fixtures are stabilized with failure logs retained, without relaxing GPU guards. Original data/archives/prior audit remain unchanged. The assessment plan keeps fourteen scientific choices null and existing wait/phase mappings unsupported. Next step 036 builds a criterion-completion and independent-assessment worksheet contract on CPU before scientific adjudication/calibration. [Step report](progress/035_scheduler_bound_precision_and_cohort_audit.md).

Step 036 [implements the scientific-criteria and evaluator worksheet workflow](examples/scheduler_assessment/REPORT.md). It verifies the original campaign/audit bundles and provides 96 cases with 3,932 typed artifact records, conservative post-job file availability and explicit metadata disclosure. Fourteen numerical/definitional choices and actual assessor entries remain blank. Complete structural declarations cannot authenticate decision provenance, establish scientific adequacy, produce labels or lock references. All 34 focused tests pass (eighteen new), with all new tests passing in both broad runs. Full regression clearance remains open: the 597-test retry has twelve failures/two errors in older timing checks under heavy host load; failed/isolated logs are retained, and all 136 prior source files are unchanged. Next step 037 prepares a concrete justified criteria proposal and prospective disjoint confirmation design on CPU, while a clean full suite remains required before freezing changed source. [Step report](progress/036_scientific_criteria_and_assessment_workflow.md).

### 2A. Implement the experimental foundation

1. Proposed new structure, keeping old scripts reproducible:

   ```text
   experiments/
     configs/                  # frozen experiment and threshold configurations
     tracing/evidence.py       # typed observations, missingness, capture provenance
     tracing/classifier.py     # receives visible evidence only
     tracing/policies.py       # shared incremental rules for live and replay modes
     tracing/controller.py     # episode state, budget, retrigger, cooldown
     tracing/profiler.py       # capture start/stop, readiness, export and parse
     scripts/run_episode.py    # persistent server and streaming decision loop
     scripts/run_matrix.py     # randomized blocked runs and manifests
     scripts/analyze_runs.py    # independent reference join and metrics
     scripts/sweep_thresholds.py
     scripts/render_episode.py
     tests/
     runs/                     # new runs only; large raw captures handled separately
   ```

2. Give each component a narrow interface:
   - `classify(observation, optional_kernel_summary) -> diagnosis, supporting_features, ambiguity_reasons`.
   - `policy.update(evidence, state) -> continue | sufficient | recovered | budget_exhausted | inconclusive`.
   - Keep run/scenario IDs only as logging metadata. Injection schedules and reference labels are evaluator-only data. Observed prompt length or live concurrency may be valid inputs; configured scenario truth is not.
3. Warm up the server and collect a separate healthy baseline. Freeze that baseline for an episode. Define latency ratios consistently using the same statistic, preferably current p95 / baseline p95, and record sample counts. Do not derive a “healthy” baseline from the first anomalous window.
4. Stream request and GPU observations into windows while requests continue. At a suspicious window, capture a bounded GPU interval, parse its evidence when available, classify, and decide whether to request another burst. Stop heavy collection without ending the request workload.
5. Prototype capture integration on the pinned GPU/vLLM/Nsight stack first. Confirm that boundaries control capture in the process actually executing GPU kernels. A CUDA profiler call in an unrelated wrapper process is not sufficient proof; inspect kernel timestamps and worker coverage.
6. Verify whether the pinned profiler supports exporting each bounded interval soon enough to inform the next decision. Include export/parse delays and gaps in logs. If it does not, implement and validate an appropriate evidence backend or narrow the claim to offline policy replay; do not claim online kernel-evidence stopping based on a report only available after the final decision.
7. Record monotonic timestamps for window close, evidence availability, capture start/end, decision, and report readiness. Never use evidence before its availability timestamp. Healthy streams should remain cheap-only in deployment-mode experiments.
8. Use the same precomputed arrival schedule, request mix, seed, warmup, observation horizon, and server settings across policy arms. Prefer an open-loop arrival schedule for queue-pressure comparisons; record offered load, completions, failures, and unfinished requests rather than dropping slow requests from p95 calculations.

**Gate:** a smoke run demonstrates a stopping decision based on newly available kernel evidence, with workload continuing after capture stops. Replay of the recorded evidence prefix produces the same decision.

### 2B. Add four small but discriminating live cases

Use controlled live perturbations with a documented operational rationale. These remain laboratory incidents unless real production data are obtained. Establish durations in a pilot so phases contain enough windows and completed requests; freeze them afterward.

| Case | Implementation | Evidence to collect | Main comparison |
|---|---|---|---|
| Stable persistent incident | Increase arrival rate above measured service capacity and hold it while diagnosis becomes clear. | Queue depth/waiting metrics, request latency, throughput, GPU/kernel evidence. | Does recovery gating spend additional tracing after correct diagnosis? |
| Changing bottleneck | Transition from short-request overload to a prefill-heavy mix; vary transition position relative to burst boundaries. | Time-varying request mix, server queue metrics, prefill/decode kernel summaries. | Can early label stability hide a later change, and does change-triggered reactivation work? |
| Temporary lull | During a long anomaly, briefly reduce arrivals, then restore them. | Unedited latency/utilization/recovery signals and independent incident timeline. | Does a recovery-based stop mistake temporary symptom relief for resolution? |
| Overlapping causes | Combine increased arrivals with long contexts or long outputs; include each perturbation alone as a control. | Queue and KV-cache/preemption metrics where available, request mix, kernel evidence. | Does a stable single-label diagnosis omit an active cause? |

For a genuinely healthy negative control, reuse the same infrastructure with no perturbation. Report false activations. Do not use high allocated VRAM alone as proof of KV-cache pressure; verify actual cache occupancy, preemption, queueing, or other relevant server evidence.

### 2C. Establish diagnosis and sufficiency independently

1. Store the perturbation schedule in evaluator-only `reference_events.json`. A configured injection establishes an intervention, not automatically the system's realized bottleneck.
2. Verify that the intended effect occurred using independent server metrics, a full-horizon reference capture in a separate matched run, and single-perturbation controls. Include removal/rollback of the perturbation when feasible to verify symptom reversal.
3. Have reference diagnoses adjudicated without seeing policy decisions or predicted labels when a second researcher is available. Record the evidence, uncertainty, and disagreements. Without that independence, describe the result as a controlled intervention study with explicit limitations.
4. Separate scoring layers: synthetic state-machine traces test policy mechanics; frozen independent evidence streams compare stopping rules conditional on a classifier; live episodes measure end-to-end behavior.
5. For stop-time evidence sufficiency, present only the captured prefix to a blinded assessor where feasible. A later full trace can help construct a reference, but future evidence must never enter the controller. Without a human assessment, use a transparent independent reference rubric and avoid claims of demonstrated operator benefit.
6. Use a set of active causes for overlapping cases. Measure per-cause coverage and unsupported causes, or report “mixed/unresolved” as an honest abstention. Do not score a single expected scenario name as a complete diagnosis.
7. Evaluate anomaly detection separately: missed episodes, false activations, and activation delay. Report both conditional-on-activation stopping performance and end-to-end results.

### 2D. Correct metrics and baselines

1. Primary metrics: valid-stop agreement with the independent reference; unknown/unresolved stops; stable-but-wrong stops; capture-active seconds; actual captured kernel instances and report bytes; time from anomaly onset and from first capture to an evidence-supported diagnosis; measured later capture activations; p95 latency, throughput, and failures.
2. Track diagnosis completion separately from recovery. Continuing suspicion after a correct diagnosis is not automatically a premature stop or a need to reactivate. Reactivation requires a predefined changed-evidence/uncertainty trigger. Report the existing “later suspicious windows” metric as a proxy only if retained.
3. Record budget exhaustion, profiler failure, missing evidence, timeout, and observation-horizon censoring as distinct outcomes. None establishes successful sufficiency. Report episode- and run-level denominators explicitly.
4. Compare these arms on the same request horizon: fixed short burst; repeated fixed N=3; SS; CR; HS. Add a fixed-duration sweep (for example one, two, three, and six burst-length equivalents) to expose quality–cost tradeoffs. Retain the long fixed manual-style window as an operational comparator, not the only baseline.
5. Add an optional full-horizon reference-capture arm. Its higher perturbation means it is a reference instrument, not unquestionable ground truth. Show matched no-profiler and cheap-only arms to distinguish cheap-metric cost from full-controller/profiler perturbation.
6. Start with three pilot seeds for engineering validation, not publication claims. Four challenge cases × five distinct policies × three pilot seeds is 60 runs, before negative controls and reference/overhead arms. Estimate GPU time from measured run duration plus startup/export overhead before scaling.
7. Select confirmation repetitions prospectively from pilot variance, the smallest useful effect, and desired interval width. Ten independent runs per main cell is a possible initial planning target, not a power guarantee. Zero failures in ten runs does not prove safety; the rough 95% upper failure bound is still about 30%.
8. Randomize policy order within seed/workload blocks. Report paired effect sizes and run-level confidence intervals; bootstrap independent runs/blocks rather than treating correlated windows as independent samples. If using hypothesis tests, predefine primary comparisons and account for multiplicity. Plot failures and distributions, not just averages.
9. Remove arbitrary 25% savings gates and the weighted composite ranking as the main conclusion. Present quality–cost curves and Pareto tradeoffs. Any operator-specified acceptance constraint must be justified and fixed before confirmation runs.

### 2E. Sensitivity and transfer

1. Use a small calibration-only workload subset to establish baseline thresholds. Save a frozen configuration before evaluating held-out arrival schedules, prompt/output mixes, onset times, and seeds. A new seed alone does not demonstrate transfer to a different workload distribution.
2. Proposed initial sweep: latency trigger `{1.25, 1.5, 2.0}`; stability K `{2, 3, 4}`; GPU suspicion threshold `{80, 85, 95}` percent. Values are experimental settings, not validated defaults. Later vary latency recovery `{1.05, 1.10, 1.20}` and GPU recovery `{60, 80, 95}` only as justified by the recovery definition.
3. Sweep stopping thresholds offline only where a complete, independently collected evidence stream supports all decisions. Sweep anomaly-trigger thresholds live, or on continuous reference observations with explicit counterfactual limitations: changing activation time changes which T2 evidence exists. Never fabricate kernel summaries for untraced windows.
4. Begin with one-factor sweeps and add a small trigger × K interaction grid. Do not run an expensive full factorial before checking the pilot.
5. Confirm default, best, and failure-prone settings live. Report threshold-selection rules, calibration/evaluation separation, ranking reversals, and where a threshold makes the policy effectively always trace or never recover.
6. Test transfer to the second GPU only if available and affordable; otherwise narrow hardware claims. Changes to the model or serving framework are optional extensions, not prerequisites for an honest single-stack study.

**Done when:** main results include naturally produced ambiguity or documented failure to produce it, valid independent references, equal-workload baselines, sensitivity, and uncertainty. If all revised cases remain easy, report that limitation instead of relabeling windows to manufacture the main finding.

## 3. Clarify the engineering workflow

- [ ] Specify the operator's trigger, output, decision, and next action.
- [ ] Produce an episode report from actual logged observations.
- [ ] Walk through at least one correct case and one inconclusive/failure case.
- [ ] Distinguish a usable interface from demonstrated human benefit.

### Instructions

1. Describe the workflow concretely: an operator observes a latency incident; the controller identifies affected intervals and captures evidence; the report explains the candidate diagnosis and why collection stopped; the operator inspects the linked capture and selects a verification or mitigation step.
2. Implement `render_episode.py` to read `episode.json`, `windows.csv`, and `decisions.jsonl`, and emit a portable Markdown report plus a timeline figure. No dashboard is required.
3. Include: incident onset and request cohort; baseline and current statistics with sample counts; telemetry availability; candidate labels and supporting/contradicting features; capture timestamps and report paths; stability/recovery streaks; stop reason; budget spent; unresolved alternatives; recommended verification step.
4. Suggested report structure:

   ```text
   Episode: <id>; outcome: <sufficient / recovered / inconclusive / budget exhausted>
   Symptom: <observed latency/throughput change and interval>
   Candidate explanation: <label or cause set, with supporting evidence>
   Alternative explanation: <what remains unresolved>
   Captures: <timestamps, active seconds, kernel summary, artifact links>
   Stop decision: <policy, conditions actually satisfied, missing evidence>
   Next verification: <operator action tied to this explanation>
   ```

5. For queue pressure, a verification might compare offered load, queue depth, and service rate before adjusting admission or batching. For a prefill-heavy mix, inspect input-length distribution and prefill timing before changing serving configuration. Treat actions as suggestions requiring validation, not automated fixes.
6. Document that stopping capture does not mean the service recovered. An ongoing incident with a concrete diagnosis remains visibly open under cheap monitoring. Budget exhaustion must prominently state that evidence may be insufficient.
7. Use actual successful and unsuccessful revised runs in the paper walkthrough. Mark any mock report as illustrative and exclude its numbers from evaluation.
8. If time allows, conduct a small blinded task study comparing fixed-window reports and adaptive-prefix reports. Otherwise claim that the report supports inspection, not that it reduces engineers' debugging time.

**Done when:** a reader can follow a real incident from symptom to captured evidence to stop decision to an operator's next verification, including what happens when the controller cannot diagnose it.

## 4. Resolve policies and baseline ambiguities

- [ ] Use one policy implementation for replay and live control.
- [x] Merge SS(K=2) and the current MU alias (step 002).
- [x] Define concrete-label eligibility, streak resets, sustained recovery, and attempt budgets in a shared engine (step 002).
- [ ] Integrate episode resets/reactivation, real capture provenance, and evidence-availability timestamps into the online controller.
- [ ] Label measured, replayed, and synthetic results consistently.

### Instructions

1. Define evidence `E_t`, concrete label `d_t`, suspicion `A_t`, recovery `R_t`, capture count `b_t`, and budget `B`. Unknown, missing, healthy/no-incident, and mixed outputs need explicit vocabulary and semantics.
2. Recommended stable-label rule: `s_t = 0` for non-concrete or unavailable new evidence; otherwise `s_t = s_(t-1)+1` if the preceding eligible evidence window had the same concrete label, and `1` otherwise. A cached label repeated without new evidence must not count as another diagnostic observation.
3. To simplify the revised study, use T2-backed windows for SS's primary streak. If cheap-label confirmation is retained as an ablation, describe exactly when cheap evidence may seed one observation and ensure no double-counting. This changes the original one-burst behavior and requires regenerated results.
4. Use these distinct policies:

| Policy | Stop rule |
|---|---|
| FB | One valid bounded capture, then stop; possibly unresolved. |
| RFB(N) | N bounded captures, independent of diagnosis; possibly unresolved. |
| SS(K) | At least K consecutive eligible evidence windows with the same concrete label. |
| CR | Recovery predicate holds for a documented number of consecutive cheap windows; report diagnosis status separately. |
| HS | Both SS and sustained recovery hold. |

5. Drop the current MU as a separate policy and explain that it is the SS(K=2) special case in the inspected replay code. A future utility-based policy would need an actual measure of incremental evidence/diagnosis improvement and its own justification; renaming a label-repeat rule does not create a different method.
6. Apply the cap to all policies before launching another burst. `budget_exhausted` and `horizon_ended` must remain distinguishable from a policy's successful stop. Define resets, cooldown, and reactivation when a previous explanation becomes uncertain or changes.
7. Represent evidence provenance explicitly as `live_online`, `live_fixed_duration`, `offline_replay`, or `synthetic_replay`. Use these values in result schemas and table captions.
8. For replay, use full chronological streams with original timestamps, evidence availability, and decision boundaries. A post-policy-stop T2 summary can be used by an offline evaluator/reference, never by the simulated controller without charging a new capture. State that replay cannot estimate a policy's actual kernel counts or runtime perturbation.
9. Define whether “equal budget” means equal burst length, equal maximum captures, or equal total active seconds. Equal burst length does not imply equal total cost. Plot a budget sweep rather than conflating these quantities.
10. Add edge-case tests for: repeated unknowns; concrete→unknown→same concrete; stable wrong labels (policy may stop, evaluator must mark wrong); missing counters; delayed reports; budget limits; evidence ending early; changed causes; and replay/live agreement. Remove claims that stability mathematically guarantees correctness.

**Done when:** each policy has an unambiguous rule, every cost has a defined clock, every table identifies evidence provenance, and SS/MU duplication cannot inflate the apparent breadth of comparison.

## Milestones and submission decision

| Priority | Deliverable | Acceptance condition |
|---|---|---|
| P0 | Artifact audit and validity fixes | Truth-independent predictions; correct missingness, clocks, budgets, and policy semantics. |
| P0 | Working online smoke episode | A decision uses newly available T2 evidence while workload continues; logs prove capture coverage. |
| P1 | Frozen protocol and live pilot | Cases produce verifiable behavior; independent references and practical run cost established. |
| P1 | Main results and sensitivity | Held-out findings with uncertainty, failures, and accurate provenance. |
| P1 | Contribution and workflow rewrite | Claims match evidence; closest work compared; operator report included. |
| P2 | Extra GPU/model or human task study | Useful extension if core evidence is already sound. |

If online capture or independent classification is not ready, a smaller explicitly offline empirical study may be defensible, but it must not retain live adaptive-stopping claims. If the study cannot support its main contribution in time, do not treat a venue change or a shorter format as a substitute for validity.

Start implementation with **0 → 4 → 2A**. These determine whether new experiments would answer the intended research question. Then run the pilot before committing to a large GPU matrix.
