# Scheduler-bound feature and reference assessment — step 035

This is an offline assessment plan for the unchanged step-033 development campaign. It defines measurement scope and unresolved decisions. It creates no reference labels, accepted classifier feature profile, calibration data or main-study freeze. [Audit](../hardware/l4_20261028/scheduler_bounds_035/AUDIT.json), [summary](../hardware/l4_20261028/scheduler_bounds_035/SUMMARY.json), [unfilled scientific criteria](../hardware/l4_20261028/scheduler_bounds_035/CRITERIA_DRAFT.json).

## Measurement and cohort

The pinned source brackets `Scheduler.add_request` and the first `Scheduler.schedule` result assigning positive tokens to a request. For admission bracket `[a0,a1]` and first-positive scheduling bracket `[s0,s1]`, the elapsed host scheduling proxy lies in `[max(0,s0−a1), s1−a0]`. Only scheduling brackets wholly inside `[window_start, window_end)` enter that window's proxy cohort; brackets crossing a boundary stay ambiguous. Unscheduled or finished-without-schedule requests never receive a zero wait.

This measures host scheduling decisions. It does not locate CUDA kernel execution start, partition exclusive GPU service phases, supply prefill service fractions or automatically implement the existing `request_wait_p95_ms` field. HTTP dispatch/admission, engine admission, first positive scheduling and HTTP completion use different event definitions. The exact request-ID join does not make their window cohorts interchangeable.

The audit derives a descriptive sample p95 interval by taking the nearest-rank p95 separately over lower and upper request bounds. It is an order-statistic bound for the observed proxy cohort. It is not a population confidence interval, an accuracy guarantee, or an accepted mapping to another metric. Empty cohorts return null bounds. The twenty-request count is reported as existing engineering context, not adopted as scientific percentile precision.

## Observed limits in the development data

All 6,142 original artifact hashes verify against the manifest digest retained in step 034. Ninety source probes cover ten source-enabled jobs and 958 scheduled case requests, excluding ten warmups. All final source/client lifecycles pass, with no final incomplete source case lifecycle. These denominators do not include the six source-disabled jobs as zero waits.

- Of sixty source-enabled ten-second windows, all sixty have raw evidence by the recorded deadline. The actual consumer accepts bounds in 54, while six deliberately withheld windows stay unresolved. The accepted windows contain 798 proxy observations; the withheld windows contain 160 additional offline-only observations. The 36 source-disabled windows remain unresolved for missing receipts. The audit never retrofills a recorded consumer decision.
- No scheduling-bracket boundary ambiguity is observed in these sixty windows. The implementation and synthetic tests still preserve that category; zero observed ambiguity does not justify deleting it from future denominators.
- Wait-bound widths across the 958 case requests have median **0.2362 ms**, sample p95 **0.3252 ms** and maximum **0.7692 ms**. These describe bracketing uncertainty, not measurement accuracy or the magnitude of request waits. No scientific width/error criterion has been justified.
- Source-probe command/receipt round trips range from **8.070 to 314.876 ms**. Window-end-to-receipt delay ranges from **11.100 to 316.594 ms**; all have at least **433.406 ms** remaining before the engineering 750 ms decision deadline. There are zero late owner decisions. These delays do not estimate serving observer overhead or establish a future scientific readiness tolerance.
- Scheduling cohorts differ from HTTP client admission cohorts in **40/60 windows**, and from HTTP completion cohorts in **52/60**. These comparisons include the six withheld windows solely as offline diagnostics.
- **32/60 raw source cohorts contain fewer than twenty requests; eight are empty.** Among the 54 consumer-accepted windows, 32 are below twenty and eight are empty. Thus engineering `bounds_available` can describe a valid empty history, and it does not imply an available or statistically precise percentile.
- There are **147 unscheduled-at-probe request occurrences**, versus **148 definitely unscheduled-at-window-end occurrences** reconstructed from final history. One request in the first withheld control was scheduled after its thirty-second boundary and before the source probe. There are **622 definitely unfinished source occurrences at window ends** despite all case requests eventually completing. These are sums across windows, not counts of unique failed/censored requests. Final-history reconstruction is explicitly retrospective and cannot become an online feature at an earlier deadline.

## Field admissibility

| Field | Permitted use now | Unresolved acceptance |
|---|---|---|
| Raw request-ID-bound host admission/scheduling brackets | Scoped descriptive measurements and explicit interval uncertainty | Scientific precision, coverage, observer mismatch and repetition targets |
| First-positive-schedule proxy per-window bounds | Descriptive proxy with its own cohort/version and request count | Separate feature specification and calibration; existing wait-field mapping remains unsupported |
| Probe-time unscheduled/finished-without-schedule counts | State at that source probe, with its actual receipt readiness | Historical window-end state and current classifier mapping |
| Window-end state reconstructed from final history | Offline evidence audit with retrospective flag | Online availability is never inferred from it |
| Client response latency and admission/completion cohorts | Explicitly named client measurements; retain their own denominators | Scientific percentile precision and any different-cohort mapping |
| Source collection off, deliberately withheld or late evidence | Preserve unresolved consumer result | No zero imputation or retrospective fill |
| GPU execution start, exclusive phase fractions, prefill fraction | Unavailable | Further instrumentation/clock attribution required |
| Diagnostic/healthy/cause reference | No automatic label | Independent evidence and documented adjudication required |

The runtime classifier remains unchanged and uncalibrated. Engineering source validation does not activate a host-scheduler feature profile or establish causal diagnosis.

## Complete criteria before confirmation

The draft deliberately leaves fourteen scientific choices null: absolute hook/bracket and wait-bound width limits; relative uncertainty normalization/limit; boundary-ambiguity fraction; minimum proxy cohort size; percentile precision/confidence targets; readiness and source-gap limits; paired work/latency mismatch limits; independent repetitions; and reference agreement. The relative normalizer itself is unset because near-zero waits make an arbitrary ratio misleading.

1. Declare the intended research claim and measurand: a host scheduling proxy, realized queue-pressure evidence, or another construct. Specify which fields are classifier inputs and which evidence is evaluator-only before fitting or adjudication.
2. Justify measurement precision, missingness/coverage, sample precision, independence/repetition and matched-work tolerances. Record their rationale and decision provenance. Observed maxima and small pair differences above cannot supply held-out confirmation of thresholds fitted to them.
3. Freeze a separately versioned feature/criteria specification and held-out collection/split design. Keep this development campaign in development; changed runtime source needs a new engineering snapshot before any further live validation.
4. Prepare an evaluator-only assessment worksheet bound to audited artifact and criteria hashes. Record assessor identity and actual blinding status, competing explanations, evidence scope, clock/cohort limits and pair mismatch. Case names, offered rates, successful HTTP responses and zero point samples are not reference labels.
5. Avoid using the same scheduling proxy as both classifier input and independent causal reference. For separate traces, assess actual matched work, clocks, observer effects and permitted source scope; do not assume same-execution ground truth. Require explicit coverage and cause scope for healthy/recovery assertions.
6. Retain unresolved disagreements and missing criteria. Perform independent adjudication and the existing reference-store lock before scoring or calibration. A structurally complete worksheet alone does not authenticate an assessor, prove blinding, settle causal truth or create a reference.

Step 036 [implements the criterion/worksheet workflow](SCHEDULER_ASSESSMENT_WORKFLOW.md), with actual choices and assessor fields still blank. The separate packet preserves evidence scope, conservative file availability and blocked scientific/reference gates. Focused checks pass; broad regression clearance remains unresolved under host timing pressure and must be cleared before another engineering freeze. Next step 037 prepares justified scientific choices and a prospective disjoint confirmation proposal for review. No GPU is needed for that proposal; actual adjudication, confirmation and calibration remain subsequent work.
