# RQ2 vLLM Multi-Class Accuracy Plan

## Purpose

Use vLLM serving scenarios to evaluate whether automatic tracing preserves diagnosis accuracy compared with the fixed-window manual baseline.

This is separate from the RQ1 vLLM `queue_pressure` result, which mainly measures automatic versus fixed-window profiler-duration savings for one selected serving workload.

## Label Policy

Concrete expected labels:

- `vllm_healthy`
- `vllm_queue_pressure`
- `vllm_long_prompt`
- `vllm_long_output`
- `vllm_compute_saturation`
- `vllm_kv_cache_pressure`

Ambiguous or unknown label:

- `vllm_latency_regression_unknown_gpu_cause`

The unknown-cause label should not be treated as a correct expected label for a known serving scenario. It should count toward the ambiguous or unknown rate.

## Run Strategy

Use a two-stage vLLM RQ2 workflow.

### Stage A: Short Validation Runs

Run one short automatic/fixed-window comparison for each concrete serving label.

Purpose:

- Validate that every scenario can run through the comparison harness.
- Confirm the analyzer can read nested vLLM smoke window CSVs.
- Check expected-label match rate and ambiguous rate before spending time on longer repetitions.

Suggested settings:

- Automatic smoke duration: 12 s.
- Fixed-window smoke duration: 24 s.
- Window size: 6 s.
- One seed per scenario.

Suggested run directories:

- `RQ1/runs/vllm_rq2_multiclass_short/healthy/`
- `RQ1/runs/vllm_rq2_multiclass_short/queue_pressure/`
- `RQ1/runs/vllm_rq2_multiclass_short/long_prompt/`
- `RQ1/runs/vllm_rq2_multiclass_short/long_output/`
- `RQ1/runs/vllm_rq2_multiclass_short/compute_saturation/`
- `RQ1/runs/vllm_rq2_multiclass_short/kv_cache_pressure/`

The RQ2 analyzer expects each run directory to contain:

- `automatic/**/*.csv`
- `fixed_window/**/*.csv`

The existing `RQ1/scripts/run_vllm_nsys_compare.py` already writes this layout.

### Stage B: Longer Paper-Ready Runs

After Stage A passes, run 3 seeded repetitions for each concrete serving label.

Suggested settings:

- Automatic smoke duration: 30 s.
- Fixed-window smoke duration: 60 s.
- Window size: 10 s.
- Three seeds per scenario.

Purpose:

- Produce a more stable RQ2 serving accuracy result.
- Preserve a bridge to RQ3 by also reporting profiler duration and kernel counts.

## Analysis Commands

Short validation analysis:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_short \
  --run-pattern '*' \
  --output-dir RQ2/analysis/vllm_multiclass_short_accuracy

python RQ2/scripts/make_paper_tables.py \
  --report RQ2/analysis/vllm_multiclass_short_accuracy/rq2_accuracy_<timestamp>.json \
  --output-dir RQ2/analysis/vllm_multiclass_short_accuracy/paper_tables \
  --min-match-rate 0.95 \
  --max-ambiguous-rate 0.05
```

Longer paper-ready analysis:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_long \
  --run-pattern '*' \
  --output-dir RQ2/analysis/vllm_multiclass_long_accuracy

python RQ2/scripts/make_paper_tables.py \
  --report RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_<timestamp>.json \
  --output-dir RQ2/analysis/vllm_multiclass_long_accuracy/paper_tables \
  --min-match-rate 0.95 \
  --max-ambiguous-rate 0.05
```

## Acceptance Criteria

For each concrete vLLM scenario and each mode:

- Expected-label match rate should be at least 0.95.
- Ambiguous or unknown rate should be at most 0.05.
- Missing first-correct-diagnosis runs should be 0.

Additional diagnostics:

- Report automatic versus fixed-window disagreement rate.
- Report first-correct diagnosis time in seconds.
- Report profiler duration, kernel instances, kernel time, and profiler report count.
