# RQ2 Progress Journal

## Research Question

RQ2 asks:

> How accurate is automatic GPU tracing compared with a manual profiling approach?

The manual baseline is modeled as fixed-window profiling:

1. Detect an anomaly.
2. Start a profiler window using a fixed operational rule.
3. Collect a fixed-duration heavy trace.
4. Diagnose from the collected profiler output.
5. Stop when the fixed window ends.

The automatic controller is evaluated against that baseline using diagnosis agreement and accuracy-oriented metrics.

## Current Scope

The current RQ2 implementation reuses RQ1 per-window outputs rather than launching separate RQ2 experiments.

This is intentional for the first pass:

- RQ1 already produces paired `automatic` and `fixed_window` outputs.
- The controlled microbenchmark workloads have known expected labels.
- The per-window CSVs contain `diagnosis_label`, `trigger_trace`, `window_id`, and workload identity.

The current controlled labels are:

- `compute_bound`
- `launch_overhead_or_small_kernel`
- `mixed`

The current RQ2 script is:

- `RQ2/scripts/analyze_accuracy.py`

The current planning file is:

- `RQ2/planning.md`

## Metrics

The current RQ2 script computes:

- Expected-label match rate on suspicious windows, falling back to all windows if no suspicious windows exist.
- Ambiguous or unknown diagnosis rate.
- First correct diagnosis window.
- Confusion rows by mode, workload, expected label, and diagnosis label.
- Automatic versus fixed-window disagreement rate across paired windows.

Candidate metrics still to add:

- Top-k diagnosis accuracy once diagnoses become ranked rather than single-label.
- Time-to-diagnosis in seconds, not only first correct window index.
- Premature-stop rate.
- Output-size and profiler-cost columns to connect RQ2 with RQ3.
- vLLM-specific serving diagnosis labels.

## Completed Work

### Step 1: RQ2 Planning

- Created `RQ2/planning.md`.
- Defined the first RQ2 comparison as automatic mode versus fixed-window mode using RQ1 microbenchmark outputs.
- Selected the first accuracy metrics:
  - Top-1 expected-label match rate.
  - Ambiguous or unknown rate.
  - First correct diagnosis window.
  - Confusion table.
  - Automatic versus fixed-window disagreement rate.
- Decided that a separate RQ2 run layout is not needed until vLLM-specific workload labels are added.

### Step 2: Accuracy Analyzer

- Added `RQ2/scripts/analyze_accuracy.py`.
- The script loads paired RQ1 run directories with this layout:
  - `<run>/automatic/*.csv`
  - `<run>/fixed_window/*.csv`
- The script writes:
  - Accuracy summary CSV.
  - Confusion CSV.
  - Disagreement CSV.
  - JSON report.

### Step 3: Phase 0 Accuracy Snapshot

- Ran RQ2 accuracy analysis on the earlier 5-repetition microbenchmark snapshot.
- Output directory:
  - `RQ2/analysis/step9_accuracy/`
- Output files:
  - `RQ2/analysis/step9_accuracy/rq2_accuracy_1781553587.json`
  - `RQ2/analysis/step9_accuracy/rq2_accuracy_summary_1781553587.csv`
  - `RQ2/analysis/step9_accuracy/rq2_confusion_1781553587.csv`
  - `RQ2/analysis/step9_accuracy/rq2_disagreement_1781553587.csv`

Step 3 result:

- `compute_bound`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic versus fixed-window disagreement rate: 0.25.
- `launch_overhead_or_small_kernel`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic versus fixed-window disagreement rate: 0.0286.
- `mixed`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic versus fixed-window disagreement rate: 0.2121.

Interpretation:

- The first Phase 0 result shows that automatic tracing matched the expected controlled labels on suspicious windows.
- The fixed-window baseline also matched the expected controlled labels.
- Disagreement still appears across paired windows because automatic and fixed-window modes do not always produce identical per-window diagnosis sequences or run lengths.
- This is feasibility evidence, not the final RQ2 claim.

## Current Status

RQ1 is now complete for the current L4 scope.

New RQ1 outputs now available for RQ2 follow-up:

- L4 microbenchmark comparison repetitions:
  - `RQ1/runs/rq1_l4_compare_rep1/`
  - `RQ1/runs/rq1_l4_compare_rep2/`
  - `RQ1/runs/rq1_l4_compare_rep3/`
  - `RQ1/runs/rq1_l4_compare_rep4/`
  - `RQ1/runs/rq1_l4_compare_rep5/`
- L4 vLLM queue-pressure comparison repetitions:
  - Short-window aggregate: `RQ1/analysis/vllm_l4_nsys_queue_pressure/vllm_nsys_aggregate_1781644983.json`
  - Longer-window aggregate: `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json`

RQ2 has now been rerun on the L4 microbenchmark outputs.

RQ2 now defines the vLLM serving label set, but it does not yet include a full vLLM serving accuracy analyzer because the current vLLM RQ1 comparison is mainly a profiler-duration comparison for a fixed serving workload, not a multi-class diagnosis accuracy study.

### Step 4: Re-run RQ2 on L4 Microbenchmark Outputs

- Re-ran RQ2 accuracy analysis on the 5 L4 microbenchmark comparison repetitions:
  - `RQ1/runs/rq1_l4_compare_rep1/`
  - `RQ1/runs/rq1_l4_compare_rep2/`
  - `RQ1/runs/rq1_l4_compare_rep3/`
  - `RQ1/runs/rq1_l4_compare_rep4/`
  - `RQ1/runs/rq1_l4_compare_rep5/`
- Command:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs \
  --run-pattern 'rq1_l4_compare_rep*' \
  --output-dir RQ2/analysis/l4_microbenchmark_accuracy
```

- Output files:
  - `RQ2/analysis/l4_microbenchmark_accuracy/rq2_accuracy_1781646495.json`
  - `RQ2/analysis/l4_microbenchmark_accuracy/rq2_accuracy_summary_1781646495.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy/rq2_confusion_1781646495.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy/rq2_disagreement_1781646495.csv`

Step 4 result:

- Loaded 5 L4 run directories.
- Loaded 230 per-window records.
- `compute_bound`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic ambiguous or unknown rate: 0.0.
  - Fixed-window ambiguous or unknown rate: 0.0.
  - Automatic versus fixed-window disagreement rate: 0.2.
- `launch_overhead_or_small_kernel`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic ambiguous or unknown rate: 0.0.
  - Fixed-window ambiguous or unknown rate: 0.0.
  - Automatic versus fixed-window disagreement rate: 0.4857.
- `mixed`:
  - Automatic expected-label match rate: 1.0.
  - Fixed-window expected-label match rate: 1.0.
  - Automatic ambiguous or unknown rate: 0.0.
  - Fixed-window ambiguous or unknown rate: 0.0.
  - Automatic versus fixed-window disagreement rate: 0.1714.

Interpretation:

- Automatic and fixed-window both preserved controlled-label accuracy on the L4 microbenchmark snapshot.
- The higher disagreement rate for `launch_overhead_or_small_kernel` should be interpreted as sequence/window disagreement, not an accuracy failure, because both modes still match the expected label on suspicious windows.

### Step 5: Add Paper-Ready RQ2 Tables

- Added `RQ2/scripts/make_paper_tables.py`.
- The script reports:
  - Workload.
  - Mode.
  - Expected-label match rate.
  - Ambiguous or unknown rate.
  - First correct diagnosis window.
  - Automatic versus fixed-window disagreement rate.
  - Profiler duration.
  - Kernel instances.
  - Kernel total time.
  - Profiler report count.
  - Pass/fail against accuracy criteria.
- Current criteria:
  - Expected-label match rate at least 0.95.
  - Ambiguous or unknown rate at most 0.05.
  - No missing first-correct-diagnosis runs.
- Command:

```bash
python RQ2/scripts/make_paper_tables.py \
  --report RQ2/analysis/l4_microbenchmark_accuracy/rq2_accuracy_1781646495.json \
  --output-dir RQ2/analysis/l4_microbenchmark_accuracy/paper_tables \
  --min-match-rate 0.95 \
  --max-ambiguous-rate 0.05
```

- Output files:
  - `RQ2/analysis/l4_microbenchmark_accuracy/paper_tables/rq2_paper_table_1781646586.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy/paper_tables/rq2_paper_table_1781646586.md`
  - `RQ2/analysis/l4_microbenchmark_accuracy/paper_tables/rq2_paper_table_1781646586.tex`
  - `RQ2/analysis/l4_microbenchmark_accuracy/paper_tables/rq2_success_criteria_1781646586.json`

Step 5 verification results:

- Syntax check passed with `python -m py_compile RQ2/scripts/analyze_accuracy.py RQ2/scripts/make_paper_tables.py`.
- All workloads and modes passed the RQ2 paper-table criteria.
- Overall success criteria result: `true`.

### Step 6: Decide vLLM RQ2 Scope

- Decided to use all concrete candidate vLLM serving labels as valid expected labels:
  - `vllm_healthy`
  - `vllm_queue_pressure`
  - `vllm_long_prompt`
  - `vllm_long_output`
  - `vllm_compute_saturation`
  - `vllm_kv_cache_pressure`
- Decided to treat the fallback label as ambiguous or unknown rather than as a normal expected workload label:
  - `vllm_latency_regression_unknown_gpu_cause`
- Updated `RQ2/scripts/analyze_accuracy.py` with the vLLM label mapping:
  - `healthy` -> `vllm_healthy`
  - `queue_pressure` -> `vllm_queue_pressure`
  - `long_prompt` -> `vllm_long_prompt`
  - `long_output` -> `vllm_long_output`
  - `compute_saturation` -> `vllm_compute_saturation`
  - `kv_cache_pressure` -> `vllm_kv_cache_pressure`
- Also allowed already-prefixed vLLM workload names such as `vllm_queue_pressure`.
- Added `vllm_latency_regression_unknown_gpu_cause` to the ambiguous label set.

Step 6 interpretation:

- The six concrete vLLM labels can be used for scenario accuracy.
- The unknown-cause label is useful, but it should count toward ambiguous or unknown rate.
- The current vLLM RQ1 result uses `queue_pressure` as the selected serving workload. That is enough for tracing-duration RQ1, but it is not enough for a full multi-class vLLM RQ2 accuracy claim.
- For a vLLM RQ2 accuracy study, run multiple serving scenarios with expected labels and compare automatic versus fixed-window diagnosis outputs.

### Step 7: Add Accuracy/Cost Bridge Columns

- Extended `RQ2/scripts/analyze_accuracy.py` to carry profiler-cost columns from the RQ1 per-window CSVs into the RQ2 summary:
  - `profiler_burst_count`
  - `profiler_duration_s_total`
  - `profiler_duration_s_mean`
  - `profiler_kernel_instances_total`
  - `profiler_kernel_instances_mean`
  - `profiler_kernel_total_time_ns_total`
  - `profiler_kernel_total_time_ns_mean`
  - `profiler_report_count_total`
- Extended `RQ2/scripts/make_paper_tables.py` so the paper table includes total trace seconds.
- Re-ran the L4 microbenchmark accuracy analysis with cost bridge columns.
- Output files:
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/rq2_accuracy_1781646884.json`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/rq2_accuracy_summary_1781646884.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/rq2_confusion_1781646884.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/rq2_disagreement_1781646884.csv`
- Generated updated paper-table outputs:
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/paper_tables/rq2_paper_table_1781646890.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/paper_tables/rq2_paper_table_1781646890.md`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/paper_tables/rq2_paper_table_1781646890.tex`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_cost/paper_tables/rq2_success_criteria_1781646890.json`

Step 7 verification results:

- Syntax check passed with `python -m py_compile RQ2/scripts/analyze_accuracy.py RQ2/scripts/make_paper_tables.py`.
- Accuracy results remained unchanged:
  - Expected-label match rate: 1.0 for all workloads and modes.
  - Ambiguous or unknown rate: 0.0 for all workloads and modes.
  - Success criteria overall result: `true`.
- Cost bridge result:
  - `compute_bound`: automatic trace total 62.060 s, fixed-window trace total 90.672 s.
  - `launch_overhead_or_small_kernel`: automatic trace total 64.970 s, fixed-window trace total 119.965 s.
  - `mixed`: automatic trace total 59.822 s, fixed-window trace total 92.666 s.

### Step 8: Plan vLLM Multi-Class RQ2 Accuracy Runs

- Created `RQ2/vllm_multiclass_plan.md`.
- Decided to create vLLM automatic/fixed-window comparison outputs for all six concrete serving labels:
  - `vllm_healthy`
  - `vllm_queue_pressure`
  - `vllm_long_prompt`
  - `vllm_long_output`
  - `vllm_compute_saturation`
  - `vllm_kv_cache_pressure`
- Reused the Step 6 label policy:
  - Concrete labels count toward expected-label accuracy.
  - `vllm_latency_regression_unknown_gpu_cause` counts as ambiguous or unknown.
- Chose a two-stage vLLM RQ2 run strategy:
  - Stage A: short validation runs for all six concrete labels.
  - Stage B: longer paper-ready seeded repetitions after Stage A passes.
- Proposed short validation settings:
  - Automatic smoke duration: 12 s.
  - Fixed-window smoke duration: 24 s.
  - Window size: 6 s.
  - One seed per scenario.
- Proposed longer paper-ready settings:
  - Automatic smoke duration: 30 s.
  - Fixed-window smoke duration: 60 s.
  - Window size: 10 s.
  - Three seeds per scenario.
- Updated `RQ2/scripts/analyze_accuracy.py` so it can read future vLLM comparison layouts:
  - Recursively reads CSV files under `automatic/` and `fixed_window/`.
  - Uses `workload`, `scenario`, or `workload_phase_label` as the workload identity.
  - Skips request-level CSV rows that do not contain window-level diagnosis fields.

Step 8 result:

- vLLM RQ2 should use short multi-class validation runs first.
- Only after the six-label validation passes should we spend time on longer paper-ready vLLM repetitions.
- The current analyzer is ready to consume the nested vLLM `automatic/smoke/*_windows_*.csv` layout produced by `RQ1/scripts/run_vllm_nsys_compare.py`.

### Step 9: Add Time-to-Diagnosis Seconds

- Extended `RQ2/scripts/analyze_accuracy.py` to compute first-correct diagnosis time in seconds.
  - Uses `timestamp_end - run_start` because the diagnosis is available after a completed evidence window.
  - Keeps the existing first-correct window index.
- Added summary columns:
  - `first_correct_seconds_mean`
  - `first_correct_seconds_stdev`
  - `first_correct_seconds_missing_runs`
- Extended `RQ2/scripts/make_paper_tables.py` so paper tables report:
  - First correct window.
  - First correct seconds.
- Re-ran the L4 microbenchmark RQ2 analysis with both cost bridge and time-to-diagnosis columns.
- Output files:
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/rq2_accuracy_1781647103.json`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/rq2_accuracy_summary_1781647103.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/rq2_confusion_1781647103.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/rq2_disagreement_1781647103.csv`
- Generated updated paper-table outputs:
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/paper_tables/rq2_paper_table_1781647109.csv`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/paper_tables/rq2_paper_table_1781647109.md`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/paper_tables/rq2_paper_table_1781647109.tex`
  - `RQ2/analysis/l4_microbenchmark_accuracy_with_time/paper_tables/rq2_success_criteria_1781647109.json`

Step 9 verification results:

- Syntax check passed with `python -m py_compile RQ2/scripts/analyze_accuracy.py RQ2/scripts/make_paper_tables.py`.
- Accuracy results remained unchanged:
  - Expected-label match rate: 1.0 for all workloads and modes.
  - Ambiguous or unknown rate: 0.0 for all workloads and modes.
  - Success criteria overall result: `true`.
- First-correct diagnosis time:
  - `compute_bound`: automatic 5.004 s, fixed-window 5.005 s.
  - `launch_overhead_or_small_kernel`: automatic 6.002 s, fixed-window 5.001 s.
  - `mixed`: automatic 5.005 s, fixed-window 5.003 s.

### Step 10: Run vLLM Multi-Class Short Validation

- Ran one short automatic/fixed-window vLLM comparison for each concrete serving label using the Stage A settings from `RQ2/vllm_multiclass_plan.md`.
- Stage A settings:
  - Automatic smoke duration: 12 s.
  - Fixed-window smoke duration: 24 s.
  - Window size: 6 s.
  - One seed per scenario.
- Run outputs:
  - `RQ1/runs/vllm_rq2_multiclass_short/healthy/`
  - `RQ1/runs/vllm_rq2_multiclass_short/queue_pressure/`
  - `RQ1/runs/vllm_rq2_multiclass_short/long_prompt/`
  - `RQ1/runs/vllm_rq2_multiclass_short/long_output/`
  - `RQ1/runs/vllm_rq2_multiclass_short/compute_saturation/`
  - `RQ1/runs/vllm_rq2_multiclass_short/kv_cache_pressure/`
- Ran the RQ2 analyzer:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_short \
  --run-pattern '*' \
  --output-dir RQ2/analysis/vllm_multiclass_short_accuracy
```

- Output files:
  - `RQ2/analysis/vllm_multiclass_short_accuracy/rq2_accuracy_1781648429.json`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/rq2_accuracy_summary_1781648429.csv`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/rq2_confusion_1781648429.csv`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/rq2_disagreement_1781648429.csv`
- Generated paper-table outputs:
  - `RQ2/analysis/vllm_multiclass_short_accuracy/paper_tables/rq2_paper_table_1781648434.csv`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/paper_tables/rq2_paper_table_1781648434.md`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/paper_tables/rq2_paper_table_1781648434.tex`
  - `RQ2/analysis/vllm_multiclass_short_accuracy/paper_tables/rq2_success_criteria_1781648434.json`

Step 10 result:

- Loaded 6 short vLLM run directories.
- Loaded 114 window records.
- All six concrete vLLM labels passed in both automatic and fixed-window mode.
- Expected-label match rate: 1.0 for every workload and mode.
- Ambiguous or unknown rate: 0.0 for every workload and mode.
- First correct diagnosis time: first 6-second window for every workload and mode.

### Step 11: Decide Whether vLLM RQ2 Needs Longer Runs

- Step 10 passed all labels, so no vLLM diagnosis mapping fix was needed before longer experiments.
- Ran Stage B longer seeded repetitions for all six concrete vLLM labels.
- Stage B settings:
  - Automatic smoke duration: 30 s.
  - Fixed-window smoke duration: 60 s.
  - Window size: 10 s.
  - Three seeds per scenario: 5101, 5102, 5103.
- Run output root:
  - `RQ1/runs/vllm_rq2_multiclass_long/`
- Ran the RQ2 analyzer:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_long \
  --run-pattern '*' \
  --output-dir RQ2/analysis/vllm_multiclass_long_accuracy
```

- Output files:
  - `RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_1781652858.json`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_summary_1781652858.csv`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/rq2_confusion_1781652858.csv`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/rq2_disagreement_1781652858.csv`
- Generated paper-table outputs:
  - `RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables/rq2_paper_table_1781652863.csv`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables/rq2_paper_table_1781652863.md`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables/rq2_paper_table_1781652863.tex`
  - `RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables/rq2_success_criteria_1781652863.json`

Step 11 result:

- Loaded 18 long vLLM run directories.
- Loaded 402 window records.
- All six concrete vLLM labels passed in both automatic and fixed-window mode.
- Expected-label match rate: 1.0 for every workload and mode.
- Ambiguous or unknown rate: 0.0 for every workload and mode.
- First correct diagnosis time: first 10-second window for every workload and mode.
- Automatic versus fixed-window disagreement rate:
  - 0.0 for all workloads except `long_prompt`.
  - 0.25 for `long_prompt`.
- The `long_prompt` disagreement is not an accuracy failure because both modes still matched the expected label and passed the ambiguity criteria.
- Current vLLM paper tables show profiler bridge columns as 0.0. The vLLM accuracy result is complete, but the profiler-cost bridge should be tightened later if the vLLM RQ2 table needs to report trace duration and kernel-count columns directly.

## Next Steps

### Step 12: Tighten vLLM Cost Bridge If Needed

- Decide whether RQ2 vLLM paper tables need profiler-duration and kernel-count columns, or whether those should stay in RQ1/RQ3 tables.
- If they should appear in RQ2 vLLM tables, extend the analyzer to read profiler-cost fields from the vLLM comparison JSON files in addition to per-window CSV rows.

## Notes

- The existing `RQ2/analysis/step9_accuracy/` result came from the earlier local/Phase 0-style RQ1 run names, not the latest L4 run names.
- The L4 microbenchmark RQ2 analysis now exists in original, cost-augmented, and time-to-diagnosis forms.
- The L4 vLLM multiclass accuracy analysis now exists in short-validation and long seeded forms.
- `healthy_light` from RQ1 Step 14 should only be added later if RQ2/RQ3 need a low-utilization serving baseline.
