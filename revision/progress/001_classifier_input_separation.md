# Step 001 — Separate expected labels from classifier inputs

Date: 2026-10-27. Status: completed for the serving and microbenchmark prediction paths inspected in this step.

## Problem

The serving runner assigned the configured expected label to suspicious windows and boosted its score. The microbenchmark runner used workload identity in both the suspicion trigger and diagnosis branches. Consequently, the original perfect label agreement cannot establish independent diagnostic accuracy.

## Completed work

- [x] Added `RQ1/scripts/evidence_classifier.py`, a standard-library-only module that accepts measured evidence and has no access to workload configurations or expected-label mappings.
- [x] Added the frozen `ServingObservation` interface: latency ratio, GPU utilization, memory-used percentage, observed prompt/output lengths, throughput ratio, and observed mean in-flight requests. No scenario name, expected label, or configured concurrency is accepted.
- [x] Moved intended serving labels to `RQ1/scripts/vllm_expected_labels.py`. Workload configurations no longer contain labels. Expected labels remain in request/window metadata and run summaries for evaluation compatibility; they are never passed into prediction.
- [x] Removed the expected-label score floor. Suspicious serving windows now use the highest-scoring cheap-evidence candidate, with abstention for missing/invalid features, tied candidates, or a healthy candidate that does not explain the anomaly. Existing heuristic weights were retained; this step does not calibrate them.
- [x] Replaced configured concurrency in scoring with time-weighted observed request overlap. Configured values remain metadata/load-generation inputs only.
- [x] Removed microbenchmark workload-name conditions. High operation rate can suggest possible launch overhead, but is no longer reported as measured GPU launch rate. High utilization alone cannot distinguish compute-bound from mixed and now returns unknown rather than reading the workload name.
- [x] Added classifier version, evidence tier, and heuristic-score provenance. The legacy `diagnosis_confidence` field is explicitly identified as `heuristic_not_probability`, not a calibrated confidence estimate.
- [x] Fixed a final-window boundary defect found during testing: a request finishing exactly at the final observation timestamp was previously omitted. It is now included in the final window.
- [x] Added CPU-only independence and integration tests, and updated the main revision plan and cumulative progress index.

## Validation

Run from the repository root:

```bash
python3 -m unittest discover -s revision/tests -v
python3 -m py_compile RQ1/scripts/evidence_classifier.py RQ1/scripts/vllm_expected_labels.py RQ1/scripts/run_vllm_smoke.py RQ1/scripts/run_microbenchmarks.py revision/tests/test_classifier_independence.py
git diff --check
```

The suite contains 10 tests, including:

- Rejecting truth fields at the classifier interface and checking the classifier does not import workload/expected-label modules.
- Running actual serving aggregation with identical observations but renamed scenarios, altered expected labels, and different configured concurrency/token limits; all diagnosis fields and trigger results must remain identical.
- Running actual microbenchmark classification with identical telemetry/operation counts and different workload identities; predictions and triggers must remain identical.
- Confirming that changed measured evidence can change the provisional serving prediction.
- Abstention for each missing, non-finite, or negative feature; preservation of a zero throughput ratio.
- Observed-concurrency calculation and final-completion inclusion.

Runner tests replace only hardware/process dependency imports with minimal stand-ins; they execute the real aggregation/classifier functions. No CUDA kernels, vLLM server, NVML device calls, or Nsight captures are tested.

## Behavior and compatibility changes

New predictions can disagree with expected labels or remain unknown. Historical accuracy and stopping results must not be reused as revised results. Existing data, profiler outputs, and paper tables were not regenerated or edited.

Existing CLI flags remain available. CSVs retain the legacy evaluation metadata and diagnosis fields, with additional provenance and observed-concurrency fields. `SCENARIOS` no longer exposes a `label` key; in-repository callers were checked. New imports resolve alongside the existing script entry points.

## Remaining limitations

- Serving scores are provisional heuristics; allocated VRAM and estimated token counts do not establish a root cause. T2 kernel evidence is not yet integrated into prediction.
- Serving aggregation is still retrospective. Baseline definitions, threshold selection, streaming control, and capture timing remain separate work.
- Policy code still needs concrete-label/missing-evidence semantics and cap enforcement. An unknown result must not be interpreted as a sufficient diagnosis merely because it repeats.
- Some analyzers still derive expected labels from scenario names for scoring. That is evaluator behavior, not classifier input, but new independently verified reference events are still required.
- Full artifact auditing, including classifier-sensitive stopping/signal tables and any other derived datasets, is pending.

## Next step

**Step 002: resolve shared policy semantics.** Merge the current MU alias with SS(K=2), implement explicit concrete-label streaks and missingness handling, enforce the budget for every policy, distinguish stop reasons, and add CPU-only edge-case tests. Record that work in a new numbered report and update `revision/PROGRESS.md` and `CAIN_REVISION_PLAN.md`.
