# RQ2 Planning

## Research Question

How accurate is automatic GPU tracing compared with a manual profiling approach?

## Phase 0 Starting Point

Use the RQ1 local microbenchmark infrastructure before moving to vLLM. The current controlled workload labels are:

1. `compute_bound`
2. `launch_overhead_or_small_kernel`
3. `mixed`

The first manual baseline is `fixed_window` mode from `RQ1/scripts/run_microbenchmarks.py`.

## First RQ2 Comparison

Compare automatic mode against fixed-window mode using the same fresh repetition layout:

- `RQ1/runs/rq1_compare_rep1/`
- `RQ1/runs/rq1_compare_rep2/`
- `RQ1/runs/rq1_compare_rep3/`
- `RQ1/runs/rq1_compare_rep4/`
- `RQ1/runs/rq1_compare_rep5/`

Initial accuracy signal:

- Automatic expected-label match rate was 1.0 for all three controlled workloads in the 5-repetition Step 9 snapshot.
- Fixed-window expected-label match rate was also 1.0 for all three controlled workloads in the 5-repetition Step 9 snapshot.
- Treat this as Phase 0 feasibility evidence, not a final accuracy claim.

## Candidate RQ2 Metrics

1. Top-1 diagnosis accuracy.
2. Expected-label match rate on suspicious windows.
3. Unknown or ambiguous diagnosis rate.
4. Time-to-first-correct-diagnosis window.
5. Premature-stop rate.
6. Automatic versus fixed-window disagreement rate.
7. Per-workload confusion table.

## Next Implementation Tasks

1. Extend the RQ2 script with top-k support once diagnoses become ranked rather than single-label.
2. Add output-size and time-to-diagnosis columns to connect RQ2 accuracy with RQ3 overhead.
3. Add vLLM-specific labels before using RQ2 for serving experiments.
4. Re-run RQ2 after the scaled-down vLLM smoke workload exists.

## Phase 0 Decision

Use 3 repetitions for fast local iteration. Use 5 repetitions for the first internal result snapshot.

For Phase 0, RQ2 should reuse the RQ1 microbenchmark outputs because the existing runs already contain both automatic and fixed-window per-window CSVs with controlled labels. A separate RQ2 run layout is not needed until vLLM-specific workload phases are added.

## Step 9 Outputs

- RQ2 accuracy summary: `RQ2/analysis/step9_accuracy/rq2_accuracy_summary_1781553587.csv`.
- RQ2 confusion table: `RQ2/analysis/step9_accuracy/rq2_confusion_1781553587.csv`.
- RQ2 disagreement table: `RQ2/analysis/step9_accuracy/rq2_disagreement_1781553587.csv`.
- RQ2 JSON report: `RQ2/analysis/step9_accuracy/rq2_accuracy_1781553587.json`.

Step 9 result:

- Automatic expected-label match rate on suspicious windows: 1.0 for `compute_bound`, `launch_overhead_or_small_kernel`, and `mixed`.
- Fixed-window expected-label match rate on suspicious windows: 1.0 for `compute_bound`, `launch_overhead_or_small_kernel`, and `mixed`.
- Automatic versus fixed-window disagreement rate across paired windows:
  - `compute_bound`: 0.25.
  - `launch_overhead_or_small_kernel`: 0.0286.
  - `mixed`: 0.2121.

