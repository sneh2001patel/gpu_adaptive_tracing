# Empirical study proposal: stopping profiling during LLM serving

Date: 2026-10-28. Status: proposed research design, not a frozen protocol or executed study. This document supersedes the execution priority of adding general assessment infrastructure. Existing scientific criteria and assessor records remain blank; the values below are planning choices, not author-approved acceptance thresholds.

## Contribution and scope

Study the trade-off between profiling cost and retained actionable evidence under different stopping rules. The controller is an instrument, not the claimed algorithmic novelty. A publishable contribution requires findings beyond the unsurprising observation that shorter captures cost less: for example, when apparent stability precedes recurrence, when missing observations create false sufficiency, or when cheap evidence provides the same useful conclusion as heavy tracing. These are questions, not results.

Begin with one L4, pinned vLLM/model configuration, and queue-pressure investigations. Do not promise general GPU bottleneck diagnosis, exclusive GPU phase attribution, production representativeness, optimality, or cross-device generality. Add A100 only after the L4 pilot demonstrates a useful measurable comparison and the cost of replication is justified.

## Research questions

1. What cost/evidence trade-offs do fixed-budget, stability-based and hybrid stopping rules exhibit under the same offered workload and horizon?
2. How do recurrence, incomplete evidence and parameter changes affect premature stopping, abstention and later reactivation?
3. What evidence does each strategy provide for an operator's next diagnostic action, and what remains unresolved?

The empirical novelty must be checked against primary-source related work before making a novelty claim. Inspect the works identified in the reviews and other directly relevant adaptive/sampled GPU and LLM tracing studies. Record which question, setting or failure mechanism they already establish; adopt an applicable published comparator or explain a concrete incompatibility. Do not claim a literature gap from the reviews alone.

## Bounded first pilot: 30 proposed serving sessions

Three workload patterns: sustained pressure, pressure followed by reduced offered load, and pressure with a lull followed by recurrence. Phase names describe interventions; reduced load and lulls do not automatically establish recovery. Include enough initial baseline observation to estimate normal behavior without fitting on held-out outcomes.

Four strategy roles:

| Role | Purpose |
|---|---|
| Cheap telemetry only | Establish whether expensive traces add useful evidence at all; not a CPU hardware baseline |
| Fixed profiling budget | Practical cost/evidence comparator with a predeclared capture schedule |
| Stability stop | Stop after fresh supported observations agree; unknowns cannot establish stability |
| Hybrid stop | Compare the existing combined rule against stability alone; retain its explicit distinct semantics |

Use two independently reset blocks per pattern: 3 patterns × 4 roles × 2 blocks = 24 serving sessions. Add one separate reference session per pattern/block: 6 additional sessions, 30 total. Two blocks are a feasibility pilot, not an inferential sample-size justification. Pair exact offered schedules within blocks and randomize strategy order. Hold triggers, per-burst limits, incident caps, configuration and observation horizons constant where applicable. State all deliberate differences for the cheap and reference roles. A reference session may have a different capture schedule and associated perturbation; it is not same-execution truth.

The current classifier abstains, so stability and hybrid are not yet scientifically executable comparisons. Before this pilot, define one narrow measured conclusion with a transparent rule and independent assessment, calibrate it on development data, and freeze its inputs and thresholds. Do not manufacture diagnoses from workload names or simply rename the host scheduling proxy as a GPU diagnosis. If no defensible narrow conclusion is possible, revise the question before spending on the matrix.

Reference construction must use evidence withheld from the online decision inputs, with explicit scope, uncertainty, assessor reasoning and possible unresolved outcomes. Intervention schedules and full traces alone do not establish a bottleneck. Scheduler event history may corroborate queueing only if it is not also an input to the tested decision. Verify the existing reference contracts can represent the chosen target; do not bypass them or create labels to satisfy the matrix.

Before deployment, perform one targeted end-to-end commissioning run that checks policy-specific capture decisions and timing availability. Count and report it separately from the 30 sessions. The existing broad CPU regression remains unresolved and requires clearance before deploying changed source; investigate the specific failures, without another general framework expansion.

## Measurements and missing-data handling

- Record profiler-process wall time, startup, export/parse, evidence-ready delay and total runtime separately. Claim capture-active savings only if validated start/end events establish active intervals; otherwise retain unknown and report the measured clocks.
- Record completed requests, failures, offered/realized token work, latency and throughput. Equal offered schedules do not guarantee equal realized work. Investigate differences and retain failed runs rather than silently excluding them.
- Compare evidence-supported conclusions against independent references. Report supported, incorrect and unresolved outcomes, premature-stop events and recurrence handling with explicit denominators. Never score missing evidence as healthy or correct.
- Produce an episode timeline containing the evidence actually available at each decision, the reason to stop/continue/abstain, and the operator's next justified check. This is an evidence/workflow demonstration, not proof of human debugging-time improvement without a human study.

For missing-evidence sensitivity, retain complete raw data but withhold specified observations from the decision consumer. Offline application to a complete history is replay and cannot establish live capture cost or observations a different capture schedule would have produced. Include a live withheld-evidence case in the later confirmation study if the pilot is viable.

## Pilot decision and full-study design

Proceed only if all of the following can be demonstrated: independent assessments are possible for at least a useful subset of cases; stopping strategies actually take different online decisions; the timing metrics are valid for the claims; and the resulting evidence differences can inform an operator action. Report unresolved cases and reference disagreements. If the target remains unassessable, revise or drop it. If cheap telemetry provides the same useful evidence as tracing, report that finding and reassess the need for heavy profiling; do not force a positive adaptive-tracing result.

Use pilot variance and a practically meaningful precision target to determine the independent block count for the main study. Do not fix statistical power from the current two-block pilot or count requests/windows as independent repetitions. Compare paired block effects with appropriate uncertainty intervals, show cost versus retained evidence directly, and avoid the original arbitrary weighted utility score or required savings percentage.

Freeze the main protocol before fresh confirmation collection. Keep development schedules/data separate from confirmation schedules/data. Add unseen request mixes, recurrence and an incomplete-evidence condition; include a small justified threshold grid. Parameters chosen after observing development results are development-informed. Report the full grid, not only the best setting. The 16 existing v2 engineering jobs support feasibility and protocol development, not independent held-out confirmation or validated diagnosis accuracy.

## Paper changes and immediate execution order

1. Rewrite the introduction and contributions around the three empirical questions; create a primary-source related-work comparison.
2. Specify the narrow conclusion/reference rule and measurable cost endpoint. Demonstrate it on a small development episode before committing to 30 sessions.
3. Clear deployment regression failures, complete targeted commissioning, then run the bounded pilot. No unrelated infrastructure additions.
4. Make an explicit proceed/revise/stop decision from pilot results. Only then freeze a feasible confirmation matrix and collection budget.
5. Analyze fresh results and rewrite methodology, evaluation, operator workflow, threats, discussion and conclusion. Withdraw or regenerate historical label-dependent accuracy/stopping claims. Keep original artifacts intact.

Possible working title: “When Is Profiling Enough? An Empirical Study of Stopping Decisions in LLM Serving.” Title and claims must be narrowed further if the validated endpoint is queue-pressure evidence rather than GPU diagnosis.
