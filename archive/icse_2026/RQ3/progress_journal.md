# RQ3 Progress Journal

## Research Question

RQ3 asks:

> Does automatic GPU tracing introduce overhead compared with manual profiling, and is the overhead negligible?

For the current L4 scope, RQ3 should focus on tracing cost and workload perturbation evidence that can be computed from the existing RQ1 and RQ2 outputs before launching new experiments.

## Current Scope

RQ3 should use two existing evidence streams:

1. RQ1 profiler-savings outputs.
2. RQ2 cost-augmented vLLM accuracy tables.

This keeps the first RQ3 pass grounded in already validated L4 runs:

- RQ1 shows whether automatic tracing uses less profiler time than the fixed-window baseline.
- RQ2 shows whether those cost reductions preserve diagnosis accuracy for vLLM serving labels.

## Step 1: Define RQ3 Overhead Analysis Inputs

Use the RQ1 profiler-savings outputs as the primary tracing-cost evidence.

Primary RQ1 microbenchmark input:

- `RQ1/analysis/l4_5rep_snapshot/paper_tables/paper_table_1781640003.md`
- `RQ1/analysis/l4_5rep_snapshot/aggregate_1781639990.json`

Current L4 microbenchmark profiler-savings result:

| Workload | Reps | Automatic trace s | Fixed-window trace s | Saved % | Match rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `compute_bound` | 5 | 12.412 | 18.134 | 31.6 | 1.0 |
| `launch_overhead_or_small_kernel` | 5 | 12.994 | 23.993 | 45.8 | 1.0 |
| `mixed` | 5 | 11.964 | 18.533 | 35.4 | 1.0 |

Primary RQ1 vLLM profiler-savings input:

- `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/paper_tables/vllm_paper_table_1781646125.md`
- `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json`

Current L4 vLLM queue-pressure profiler-savings result:

| Scenario | Reps | Automatic trace s | Fixed-window trace s | Saved % | Success % |
| --- | ---: | ---: | ---: | ---: | ---: |
| `queue_pressure` | 3 | 104.561 | 133.545 | 21.7 | 100.0 |

Use the RQ2 cost-augmented vLLM tables as the accuracy-preserving serving-cost evidence.

Primary RQ2 vLLM cost-augmented input:

- `RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables/rq2_paper_table_1781706568.md`
- `RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_1781706527.json`

Current L4 vLLM multiclass cost result:

- Expected-label match rate: 1.0 for all six serving workloads and both modes.
- Ambiguous or unknown rate: 0.0 for all six serving workloads and both modes.
- Total automatic trace duration across all vLLM rows: 1858.481 s.
- Total fixed-window trace duration across all vLLM rows: 2437.733 s.
- Total trace duration saved: 579.252 s.
- Total trace duration saved percent: 23.8%.
- Total automatic kernel instances: 1460211.
- Total fixed-window kernel instances: 2759441.
- Total kernel instances avoided: 1299230.
- Total kernel instances avoided percent: 47.1%.

## RQ3 Metric Definition

The first RQ3 analysis should report:

- Automatic trace duration.
- Fixed-window trace duration.
- Trace duration saved.
- Trace duration saved percent.
- Automatic kernel instances.
- Fixed-window kernel instances.
- Kernel instances avoided.
- Kernel instances avoided percent.
- Profiler report count.
- Diagnosis success or expected-label match rate.

For vLLM serving, RQ3 should additionally carry request-level overhead metrics when available:

- p50 request latency.
- p95 request latency.
- Throughput.
- Queueing delay if available.
- Prompt and output token counts.

The current Step 1 definition is enough to begin RQ3 with tracing-cost overhead. Request-level latency and throughput overhead can be added in a later step from vLLM smoke summaries.

## Interpretation Plan

RQ3 should distinguish two claims:

1. Tracing-cost reduction:
   - Automatic tracing should use less profiler duration and fewer kernel-profiled instances than fixed-window profiling.
2. Accuracy-preserving overhead reduction:
   - Automatic tracing should preserve RQ2 diagnosis accuracy while reducing profiler cost.

The current L4 evidence supports both as a first-pass analysis:

- Microbenchmarks show 31.6% to 45.8% trace-duration savings with match rate 1.0.
- vLLM queue-pressure RQ1 shows 21.7% trace-duration savings with success 100.0%.
- vLLM multiclass RQ2 shows all labels pass while automatic mode uses less trace duration and fewer kernel instances than fixed-window mode.

### Step 2: Add RQ3 Aggregation Script

- Added `RQ3/scripts/analyze_overhead.py`.
- The script reads:
  - RQ1 microbenchmark aggregate JSON.
  - RQ1 vLLM aggregate JSON.
  - RQ2 vLLM accuracy JSON.
- It produces one RQ3 overhead summary table with tracing-cost and accuracy columns.
- It also reads vLLM request CSVs under the selected vLLM run root so request-level metrics can be joined into RQ3 rows.
- Current command:

```bash
python RQ3/scripts/analyze_overhead.py \
  --rq1-micro-aggregate RQ1/analysis/l4_5rep_snapshot/aggregate_1781639990.json \
  --rq1-vllm-aggregate RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json \
  --rq2-vllm-accuracy RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_1781706527.json \
  --vllm-run-root RQ1/runs/vllm_rq2_multiclass_long \
  --output-dir RQ3/analysis/l4_overhead
```

- Output files:
  - `RQ3/analysis/l4_overhead/rq3_overhead_1781707599.json`
  - `RQ3/analysis/l4_overhead/rq3_overhead_summary_1781707599.csv`
  - `RQ3/analysis/l4_overhead/rq3_overhead_summary_1781707599.md`

Step 2 result:

- Loaded request metrics for 12 vLLM scenario/mode groups.
- Produced a combined RQ3 table with:
  - RQ1 L4 microbenchmark rows.
  - RQ1 L4 vLLM queue-pressure profiler-savings row.
  - RQ2 L4 vLLM multiclass rows.
  - One total row for all RQ2 vLLM multiclass scenarios.
- Syntax check passed:

```bash
python -m py_compile RQ3/scripts/analyze_overhead.py
```

### Step 3: Add Request-Level vLLM Overhead

- Extended the RQ3 table with request-level vLLM metrics from the existing vLLM smoke request CSV files:
  - Request count.
  - p50 request latency.
  - p95 request latency.
  - Throughput in requests per second.
  - Request success rate.
  - Mean prompt token estimate.
  - Mean output token estimate.
- Request-level metrics are currently available for the RQ2 vLLM multiclass long runs.
- The RQ1 vLLM queue-pressure aggregate row currently reports tracing-cost metrics but not request latency/throughput because its aggregate JSON only carries smoke request counts and success rates.

Step 3 result:

| Workload | Auto trace s | Fixed trace s | Saved % | Auto p95 ms | Fixed p95 ms | Auto rps | Fixed rps | Match |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `compute_saturation` | 336.771 | 415.072 | 18.864 | 9812.146 | 9817.126 | 2.441 | 2.441 | 1.0 |
| `healthy` | 301.255 | 391.865 | 23.123 | 3766.836 | 3806.311 | 0.267 | 0.266 | 1.0 |
| `kv_cache_pressure` | 329.383 | 449.337 | 26.696 | 19804.966 | 19816.853 | 0.404 | 0.404 | 1.0 |
| `long_output` | 291.005 | 397.137 | 26.724 | 30909.277 | 30943.009 | 0.129 | 0.129 | 1.0 |
| `long_prompt` | 290.366 | 380.965 | 23.781 | 7510.034 | 7537.282 | 0.533 | 0.532 | 1.0 |
| `queue_pressure` | 309.702 | 403.356 | 23.219 | 7150.489 | 7261.554 | 2.235 | 2.231 | 1.0 |
| `all_vllm_scenarios` | 1858.482 | 2437.731 | 23.762 | 9541.103 | 9691.891 | 1.950 | 1.915 | 1.0 |

Interpretation:

- Automatic mode reduced vLLM multiclass profiler duration by 23.762% overall.
- Automatic mode avoided 47.083% of profiled kernel instances overall.
- RQ2 diagnosis match rate remained 1.0.
- Request-level p95 latency and throughput are very close between automatic and fixed-window modes for every vLLM scenario, which supports the first-pass claim that the controller/profiling choice reduces profiler cost without obvious serving-level degradation in these runs.

### Step 4: Add RQ3 Paper Tables

- Added `RQ3/scripts/make_paper_tables.py`.
- Converted the RQ3 overhead summary into compact paper-table outputs:
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781707839.csv`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781707839.md`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781707839.tex`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_success_criteria_1781707839.json`
- Current command:

```bash
python RQ3/scripts/make_paper_tables.py \
  --summary RQ3/analysis/l4_overhead/rq3_overhead_1781707599.json \
  --output-dir RQ3/analysis/l4_overhead/paper_tables \
  --min-match-rate 0.95 \
  --max-p95-regression-percent 5.0
```

- Added success criteria for overhead:
  - Positive trace-duration savings.
  - Positive kernel-instance savings.
  - Diagnosis success or match rate remains at least 0.95.
  - Request-level p95 latency regression stays within 5.0% where request metrics are available.

Step 4 result:

| Workload | Saved % | Kernel avoided % | Match | p95 regress % | Pass |
| --- | ---: | ---: | ---: | ---: | --- |
| `compute_bound` | 31.556 | 74.533 | 1.0 | 0.0 | yes |
| `launch_overhead_or_small_kernel` | 45.842 | 73.842 | 1.0 | 0.0 | yes |
| `mixed` | 35.444 | 78.188 | 1.0 | 0.0 | yes |
| `queue_pressure` RQ1 vLLM | 21.703 | 44.460 | 1.0 | 0.0 | yes |
| `compute_saturation` | 18.864 | 42.857 | 1.0 | -0.051 | yes |
| `healthy` | 23.123 | 44.898 | 1.0 | -1.037 | yes |
| `kv_cache_pressure` | 26.696 | 50.000 | 1.0 | -0.060 | yes |
| `long_output` | 26.724 | 49.984 | 1.0 | -0.109 | yes |
| `long_prompt` | 23.781 | 50.000 | 1.0 | -0.362 | yes |
| `queue_pressure` RQ2 vLLM | 23.219 | 44.340 | 1.0 | -1.529 | yes |
| `all_vllm_scenarios` | 23.762 | 47.083 | 1.0 | -1.556 | yes |

Step 4 verification:

- Syntax check passed:

```bash
python -m py_compile RQ3/scripts/analyze_overhead.py RQ3/scripts/make_paper_tables.py
```

- Overall success criteria result: `true`.
- All rows passed trace-duration savings, kernel-instance savings, match-rate, and p95-regression criteria.

### Step 5: Decide Whether RQ3 Needs Dedicated Runtime Runs

- Decided that the current artifact-based RQ3 analysis is useful but not enough for the paper's first L4 result.
- Decided that more direct runtime-overhead evidence is needed.
- Added `RQ3/scripts/run_vllm_runtime_overhead.py`.
- Added `RQ3/scripts/analyze_runtime_overhead.py`.
- Ran dedicated vLLM runtime-overhead repetitions using:
  - Scenario: `queue_pressure`.
  - Model: `Qwen/Qwen2.5-7B-Instruct`.
  - Seeds: 6101, 6102, 6103.
  - No Nsight profiler.
  - Mode 1: `no_profiler`.
  - Mode 2: `cheap_metrics_only`, using the NVML/window controller path.
  - Duration: 30 s per mode.
  - Window size for cheap metrics: 10 s.
- Current command:

```bash
python RQ3/scripts/run_vllm_runtime_overhead.py \
  --scenario queue_pressure \
  --seeds 6101 6102 6103 \
  --base-port 8061 \
  --duration-seconds 30 \
  --window-seconds 10 \
  --output-dir RQ3/runs/vllm_runtime_overhead_queue_pressure
```

- Runtime output files:
  - `RQ3/runs/vllm_runtime_overhead_queue_pressure/runtime_overhead_summary_1781708664.json`
  - `RQ3/runs/vllm_runtime_overhead_queue_pressure/queue_pressure_seed6101/runtime_overhead_comparison_1781708408.json`
  - `RQ3/runs/vllm_runtime_overhead_queue_pressure/queue_pressure_seed6102/runtime_overhead_comparison_1781708538.json`
  - `RQ3/runs/vllm_runtime_overhead_queue_pressure/queue_pressure_seed6103/runtime_overhead_comparison_1781708664.json`
- Aggregate command:

```bash
python RQ3/scripts/analyze_runtime_overhead.py \
  --summary RQ3/runs/vllm_runtime_overhead_queue_pressure/runtime_overhead_summary_1781708664.json \
  --output-dir RQ3/analysis/vllm_runtime_overhead_queue_pressure
```

- Aggregate output files:
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure/runtime_overhead_aggregate_1781708713.csv`
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure/runtime_overhead_aggregate_1781708713.md`
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure/runtime_overhead_aggregate_1781708713.json`

Step 5 result:

| Scenario | Reps | No-profiler p95 ms | Cheap-metrics p95 ms | p95 regression % | No-profiler rps | Cheap-metrics rps | Throughput change % | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `queue_pressure` | 3 | 7228.844 | 6714.840 | -7.147 | 2.238 | 2.614 | 16.824 | 100.0 |

Interpretation:

- Dedicated runtime runs show no request-latency regression from cheap metrics on the L4 `queue_pressure` workload.
- Cheap metrics had lower mean p95 latency than no-profiler mode in this run set.
- Cheap metrics had higher mean throughput than no-profiler mode in this run set.
- Both modes had 100.0% request success.
- This supports the RQ3 claim that cheap controller metrics do not introduce obvious runtime degradation for the selected L4 serving workload.

Caveat:

- The current dedicated runtime runner executes `no_profiler` first and `cheap_metrics_only` second within each repetition.
- This is useful first evidence, but the paper-ready runtime overhead claim should be strengthened with a reverse-order or randomized-order run to reduce warmup/order effects.

Verification:

```bash
python -m py_compile RQ3/scripts/run_vllm_runtime_overhead.py RQ3/scripts/analyze_runtime_overhead.py
```

## Next Steps

### Step 6: Add Randomized-Order Runtime Overhead Runs

- Extended `RQ3/scripts/run_vllm_runtime_overhead.py` with `--mode-order`.
- Supported mode orders:
  - `no_profiler_first`
  - `cheap_metrics_first`
  - `randomized`
- The randomized order is deterministic by seed so the experiment is reproducible.
- Extended `RQ3/scripts/analyze_runtime_overhead.py` so the aggregate records per-repetition mode order.
- Ran the same `queue_pressure` dedicated runtime experiment with randomized order:
  - Scenario: `queue_pressure`.
  - Model: `Qwen/Qwen2.5-7B-Instruct`.
  - Seeds: 6201, 6202, 6203.
  - Ports: 8071, 8072, 8073.
  - Mode order:
    - Seed 6201: `no_profiler` then `cheap_metrics_only`.
    - Seed 6202: `cheap_metrics_only` then `no_profiler`.
    - Seed 6203: `cheap_metrics_only` then `no_profiler`.
  - Duration: 30 s per mode.
  - Window size for cheap metrics: 10 s.
- Current command:

```bash
python RQ3/scripts/run_vllm_runtime_overhead.py \
  --scenario queue_pressure \
  --seeds 6201 6202 6203 \
  --base-port 8071 \
  --duration-seconds 30 \
  --window-seconds 10 \
  --mode-order randomized \
  --output-dir RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized
```

- Runtime output file:
  - `RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_summary_1781709476.json`
- Aggregate command:

```bash
python RQ3/scripts/analyze_runtime_overhead.py \
  --summary RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_summary_1781709476.json \
  --output-dir RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized
```

- Aggregate output files:
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_aggregate_1781709485.csv`
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_aggregate_1781709485.md`
  - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_aggregate_1781709485.json`

Step 6 result:

| Scenario | Reps | Orders | No-profiler p95 ms | Cheap-metrics p95 ms | p95 regression % | No-profiler rps | Cheap-metrics rps | Throughput change % | Success |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `queue_pressure` | 3 | mixed | 7081.815 | 6757.630 | -4.553 | 2.475 | 2.384 | -2.704 | 100.0 |

Per-seed randomized-order result:

| Seed | Order | p95 regression % | Throughput change % |
| ---: | --- | ---: | ---: |
| 6201 | `no_profiler` then `cheap_metrics_only` | -15.457 | 18.648 |
| 6202 | `cheap_metrics_only` then `no_profiler` | 0.669 | -13.250 |
| 6203 | `cheap_metrics_only` then `no_profiler` | 1.128 | -13.509 |

Interpretation:

- The randomized-order run confirms that cheap metrics did not cause meaningful p95 latency regression for `queue_pressure`.
- The aggregate p95 regression remained negative at -4.553%.
- In the two cheap-metrics-first repetitions, p95 regression was positive but small: 0.669% and 1.128%, both within the 5% tolerance used in Step 4.
- The throughput improvement observed in Step 5 was order-sensitive. In the randomized run, throughput change averaged -2.704%, and the cheap-metrics-first repetitions showed about -13% throughput change.
- Therefore, the stronger paper-ready RQ3 claim should be:
  - Cheap metrics do not show meaningful p95 latency regression on the L4 `queue_pressure` workload.
  - Throughput perturbation is small on average in the randomized aggregate, but less stable than p95 and should be reported with the order-effect caveat.

Verification:

```bash
python -m py_compile RQ3/scripts/run_vllm_runtime_overhead.py RQ3/scripts/analyze_runtime_overhead.py
```

## Next Steps

### Step 7: Fold Dedicated Runtime Runs Into RQ3 Paper Tables

- Extended `RQ3/scripts/make_paper_tables.py` to accept a dedicated runtime-overhead aggregate with `--runtime-overhead`.
- Added a separate dedicated runtime-overhead table alongside the existing profiler-cost table.
- Added dedicated runtime success criteria:
  - Mean p95 latency regression must be at most 5%.
  - Cheap-metrics request success must remain 100%.
  - Throughput change is reported but not treated as a hard pass/fail until additional randomized repetitions are available.
- The success-criteria JSON now includes both profiler-cost rows and dedicated runtime-overhead rows.
- Overall RQ3 pass now requires:
  - Positive trace-duration savings.
  - Positive kernel-count reduction.
  - Accuracy or match rate at least 0.95.
  - p95 latency regression at most 5% when request latency is available.
  - Dedicated runtime p95 latency regression at most 5%.
  - Dedicated runtime request success at least 100%.

Current command:

```bash
python RQ3/scripts/make_paper_tables.py \
  --summary RQ3/analysis/l4_overhead/rq3_overhead_1781707599.json \
  --runtime-overhead RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_aggregate_1781709485.json \
  --output-dir RQ3/analysis/l4_overhead/paper_tables \
  --min-match-rate 0.95 \
  --max-p95-regression-percent 5.0 \
  --min-runtime-success-rate 100.0
```

Output files:

- `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.csv`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.md`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.tex`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.csv`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.md`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.tex`
- `RQ3/analysis/l4_overhead/paper_tables/rq3_success_criteria_1781711077.json`

Dedicated runtime-overhead table:

| Scenario | Reps | Orders | No-profiler p95 ms | Cheap-metrics p95 ms | p95 regression % | No-profiler rps | Cheap-metrics rps | Throughput change % | Success | Pass |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `queue_pressure` | 3 | mixed randomized | 7081.815 | 6757.630 | -4.553 | 2.475 | 2.384 | -2.704 | 100.0 | yes |

Step 7 result:

- Dedicated runtime p95 criterion passed: -4.553% mean p95 latency regression, under the 5% maximum.
- Dedicated runtime success criterion passed: cheap-metrics request success remained 100.0%.
- Throughput change was -2.704% and is reported as context, not used as pass/fail.
- Combined RQ3 success criteria passed with `overall_pass: true`.

Verification:

```bash
python -m py_compile RQ3/scripts/make_paper_tables.py
```

## Next Steps

### Step 8: Decide Whether RQ3 Is Complete For The First L4 Paper Result

- Decision: RQ3 is complete for the first L4 paper result.
- The current evidence is sufficient because it covers both sides of the RQ3 claim:
  - Profiler-cost overhead: automatic tracing reduces profiler duration and kernel count versus fixed-window tracing.
  - Runtime perturbation: cheap controller metrics do not introduce meaningful request-latency regression on the selected L4 serving workload.
- The final RQ3 evidence set is:
  - RQ1 microbenchmark profiler-cost rows:
    - `compute_bound`
    - `launch_overhead_or_small_kernel`
    - `mixed`
  - RQ1 vLLM profiler-savings row:
    - `queue_pressure`
  - RQ2 vLLM multi-class profiler-cost rows:
    - `healthy`
    - `queue_pressure`
    - `long_prompt`
    - `long_output`
    - `compute_saturation`
    - `kv_cache_pressure`
  - RQ3 dedicated randomized runtime-overhead row:
    - `queue_pressure`
- Final paper-table artifacts:
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.csv`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.md`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_paper_table_1781711077.tex`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.csv`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.md`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.tex`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_success_criteria_1781711077.json`
- Final RQ3 success status:
  - `overall_pass: true`.
  - All profiler-cost rows passed trace-duration, kernel-count, match-rate, and request-latency criteria.
  - Dedicated runtime-overhead row passed p95 latency and request-success criteria.
- Main RQ3 result statement for the first L4 paper result:
  - Automatic tracing reduced profiler duration by 18.864% to 45.842% across the individual RQ1/RQ2 workloads.
  - Automatic tracing reduced captured kernel instances by 42.857% to 78.188% across the individual RQ1/RQ2 workloads.
  - Across all RQ2 vLLM scenarios, automatic tracing reduced profiler duration by 23.762% and captured kernel instances by 47.083%.
  - For the randomized dedicated `queue_pressure` runtime-overhead run, cheap metrics showed -4.553% mean p95 latency regression with 100.0% request success.
- Caveat to carry into the paper:
  - Throughput perturbation is reported but not used as a hard pass/fail criterion in the current RQ3 result.
  - The randomized `queue_pressure` aggregate showed -2.704% throughput change, while per-seed throughput changes were more order-sensitive than p95 latency.

No additional RQ3 runs are required before moving on.

Optional paper-strengthening work, if time allows:

- Run two more randomized `queue_pressure` repetitions to increase the dedicated runtime-overhead sample from 3 to 5.
- Add a second dedicated runtime-overhead workload, preferably `healthy` for a low-pressure baseline or `long_output` for a generation-heavy serving case.
- Keep these optional runs separate from the current first L4 RQ3 result so the existing result remains reproducible.

### Optional Runtime-Overhead Strengthening Runs

- Kept the first L4 RQ3 result artifacts unchanged:
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_success_criteria_1781711077.json`
  - `RQ3/analysis/l4_overhead/paper_tables/rq3_runtime_table_1781711077.*`
- Ran two additional randomized `queue_pressure` runtime-overhead repetitions:
  - Seeds: 6204, 6205.
  - Ports: 8081, 8082.
  - Duration: 30 s per mode.
  - Window size for cheap metrics: 10 s.
  - Output summary:
    - `RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized_plus2/runtime_overhead_summary_1781728539.json`
- Created a separate combined 5-repetition `queue_pressure` summary without modifying the original 3-repetition summary:
  - Source summaries:
    - `RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized/runtime_overhead_summary_1781709476.json`
    - `RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized_plus2/runtime_overhead_summary_1781728539.json`
  - Combined summary:
    - `RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized_5rep/runtime_overhead_summary_1781728923.json`
- Added a second dedicated runtime-overhead workload:
  - Scenario: `healthy`.
  - Purpose: low-pressure serving baseline.
  - Seeds: 6301, 6302, 6303.
  - Ports: 8091, 8092, 8093.
  - Duration: 30 s per mode.
  - Window size for cheap metrics: 10 s.
  - Output summary:
    - `RQ3/runs/vllm_runtime_overhead_healthy_randomized/runtime_overhead_summary_1781728906.json`
- Aggregated optional runtime-overhead outputs:
  - Extra two `queue_pressure` repetitions:
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_plus2/runtime_overhead_aggregate_1781728956.csv`
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_plus2/runtime_overhead_aggregate_1781728956.md`
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_plus2/runtime_overhead_aggregate_1781728956.json`
  - Combined five `queue_pressure` repetitions:
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_5rep/runtime_overhead_aggregate_1781728956.csv`
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_5rep/runtime_overhead_aggregate_1781728956.md`
    - `RQ3/analysis/vllm_runtime_overhead_queue_pressure_randomized_5rep/runtime_overhead_aggregate_1781728956.json`
  - New `healthy` repetitions:
    - `RQ3/analysis/vllm_runtime_overhead_healthy_randomized/runtime_overhead_aggregate_1781728956.csv`
    - `RQ3/analysis/vllm_runtime_overhead_healthy_randomized/runtime_overhead_aggregate_1781728956.md`
    - `RQ3/analysis/vllm_runtime_overhead_healthy_randomized/runtime_overhead_aggregate_1781728956.json`
- Created a separate optional-strengthening paper-table directory:
  - Combined optional runtime aggregate:
    - `RQ3/analysis/vllm_runtime_overhead_optional_strengthening/runtime_overhead_aggregate_1781728995.json`
  - Optional-strengthening paper tables:
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_paper_table_1781729000.csv`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_paper_table_1781729000.md`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_paper_table_1781729000.tex`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_runtime_table_1781729000.csv`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_runtime_table_1781729000.md`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_runtime_table_1781729000.tex`
    - `RQ3/analysis/l4_overhead/paper_tables_optional_runtime_strengthening/rq3_success_criteria_1781729000.json`

Optional-strengthening runtime table:

| Scenario | Reps | Orders | No-profiler p95 ms | Cheap-metrics p95 ms | p95 regression % | No-profiler rps | Cheap-metrics rps | Throughput change % | Success | Pass |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `queue_pressure` | 5 | mixed randomized | 7142.660 | 6886.169 | -3.556 | 2.448 | 2.398 | -0.982 | 100.0 | yes |
| `healthy` | 3 | mixed randomized | 3698.749 | 3722.236 | 0.646 | 0.271 | 0.270 | -0.475 | 100.0 | yes |

Optional-strengthening interpretation:

- The five-repetition `queue_pressure` result strengthens the original three-repetition result:
  - p95 latency regression stayed negative at -3.556%.
  - Request success remained 100.0%.
  - Throughput change moved closer to neutral at -0.982%.
- The second workload, `healthy`, gives a low-pressure baseline:
  - p95 latency regression was 0.646%, well under the 5% threshold.
  - Request success remained 100.0%.
  - Throughput change was -0.475%.
- Optional-strengthening success criteria passed with `overall_pass: true`.
- These optional results can be cited as stronger supporting evidence, while the original first L4 RQ3 result remains separately reproducible.

Verification:

```bash
python -m py_compile RQ3/scripts/run_vllm_runtime_overhead.py RQ3/scripts/analyze_runtime_overhead.py RQ3/scripts/make_paper_tables.py
```
