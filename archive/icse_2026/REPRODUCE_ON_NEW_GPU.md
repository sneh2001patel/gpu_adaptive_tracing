# Reproducing RQ1-RQ5 On A New GPU

This guide describes the order used for the current NVIDIA L4 results and how to rerun the same experiment chain on another GPU. The important dependency is:

```text
RQ1 runs -> RQ2 accuracy -> RQ3 overhead -> RQ4 policies -> RQ5 stop signals
```

The existing output directories often contain `l4` in their names because the first full result was run on an NVIDIA L4. For a new GPU, use a new tag such as `a100`, `h100`, `rtx4090`, or `l40s` and keep the old L4 artifacts untouched.

## 0. Environment

Use two Python environments if possible:

- Main/controller environment: PyTorch, `pynvml`, `psutil`, analysis scripts.
- vLLM serving environment: vLLM and its serving dependencies.

The L4 run used paths like these:

```bash
export MAIN_PY=/venv/main/bin/python
export VLLM_PY=/venv/vllm/bin/python
export NSYS=/opt/nvidia/nsight-systems/2024.6.2/bin/nsys
export MODEL=Qwen/Qwen2.5-7B-Instruct
export GPU_TAG=newgpu
```

On a new host, verify the basics first:

```bash
$MAIN_PY - <<'PY'
import torch, pynvml, psutil
print("torch", torch.__version__)
print("cuda", torch.version.cuda)
print("cuda_available", torch.cuda.is_available())
print("gpu", torch.cuda.get_device_name(0))
pynvml.nvmlInit()
print("driver", pynvml.nvmlSystemGetDriverVersion())
pynvml.nvmlShutdown()
PY

$NSYS --version
$VLLM_PY - <<'PY'
import vllm, torch
print("vllm", vllm.__version__)
print("torch", torch.__version__)
PY
```

If vLLM is missing, install it into the serving environment:

```bash
$VLLM_PY -m pip install 'vllm==0.10.2'
$VLLM_PY -m pip install \
  'transformers==4.56.2' \
  'tokenizers==0.22.1' \
  'fastapi==0.115.14' \
  'starlette==0.46.2' \
  'prometheus-fastapi-instrumentator==7.1.0' \
  'uvicorn==0.34.3'
```

For smaller GPUs, adjust `--gpu-memory-utilization`, `--max-model-len`, `--max-num-seqs`, or choose a smaller model. Keep those changes in the directory names and notes because results will not be directly comparable otherwise.

## 1. RQ1: Adaptive Tracing Saves Profiler Time

RQ1 has two evidence streams:

- Microbenchmarks with automatic versus fixed-window tracing.
- vLLM `queue_pressure` Nsight comparison.

### 1.1 Microbenchmark Full Run

Run five repetitions:

```bash
for rep in 1 2 3 4 5; do
  $MAIN_PY RQ1/scripts/run_microbenchmarks.py \
    --mode compare \
    --workload all \
    --duration-seconds 20 \
    --window-seconds 5 \
    --enable-nsys-bursts \
    --nsys-path "$NSYS" \
    --nsys-burst-seconds 2 \
    --fixed-window-nsys-seconds 8 \
    --max-nsys-bursts-per-workload 1 \
    --fixed-window-bursts-per-workload 1 \
    --stability-stop-windows 2 \
    --output-dir "RQ1/runs/rq1_${GPU_TAG}_compare_rep${rep}"
done
```

Aggregate and generate tables:

```bash
$MAIN_PY RQ1/scripts/analyze_repetitions.py \
  --input-root RQ1/runs \
  --pattern "rq1_${GPU_TAG}_compare_rep*/comparison_*.json" \
  --output-dir "RQ1/analysis/${GPU_TAG}_5rep_snapshot"

RQ1_MICRO_AGG=$(ls -t RQ1/analysis/${GPU_TAG}_5rep_snapshot/aggregate_*.json | head -1)

$MAIN_PY RQ1/scripts/make_paper_tables.py \
  --aggregate "$RQ1_MICRO_AGG" \
  --output-dir "RQ1/analysis/${GPU_TAG}_5rep_snapshot/paper_tables"

$MAIN_PY RQ1/scripts/make_paper_figures.py \
  --aggregate "$RQ1_MICRO_AGG" \
  --output-dir "RQ1/analysis/${GPU_TAG}_5rep_snapshot/figures"
```

Expected full-run shape:

- 5 comparison directories.
- Each comparison has `automatic`, `fixed_window`, `profiles`, kernel summaries, and `comparison_*.json`.
- Paper success JSON should report overall pass.

### 1.2 vLLM Queue-Pressure Nsight Full Run

Run three longer seeded repetitions:

```bash
for item in "1 1111 8021" "2 2222 8022" "3 3333 8023"; do
  set -- $item
  rep=$1
  seed=$2
  port=$3
  $MAIN_PY RQ1/scripts/run_vllm_nsys_compare.py \
    --model "$MODEL" \
    --scenario queue_pressure \
    --port "$port" \
    --vllm-python "$VLLM_PY" \
    --client-python "$MAIN_PY" \
    --nsys-path "$NSYS" \
    --seed "$seed" \
    --automatic-smoke-seconds 30 \
    --fixed-window-smoke-seconds 60 \
    --window-seconds 10 \
    --request-timeout-seconds 240 \
    --output-dir "RQ1/runs/vllm_${GPU_TAG}_nsys_queue_pressure_long_rep${rep}"
done
```

Aggregate and generate vLLM tables/figures:

```bash
$MAIN_PY RQ1/scripts/analyze_vllm_nsys_repetitions.py \
  --input-root RQ1/runs \
  --pattern "vllm_${GPU_TAG}_nsys_queue_pressure_long_rep*/vllm_nsys_comparison_*.json" \
  --output-dir "RQ1/analysis/vllm_${GPU_TAG}_nsys_queue_pressure_long"

RQ1_VLLM_AGG=$(ls -t RQ1/analysis/vllm_${GPU_TAG}_nsys_queue_pressure_long/vllm_nsys_aggregate_*.json | head -1)

$MAIN_PY RQ1/scripts/make_vllm_paper_tables.py \
  --aggregate "$RQ1_VLLM_AGG" \
  --output-dir "RQ1/analysis/vllm_${GPU_TAG}_nsys_queue_pressure_long/paper_tables"

$MAIN_PY RQ1/scripts/make_vllm_paper_figures.py \
  --aggregate "$RQ1_VLLM_AGG" \
  --output-dir "RQ1/analysis/vllm_${GPU_TAG}_nsys_queue_pressure_long/figures"
```

Expected full-run shape:

- 3 vLLM comparison directories.
- Each has automatic and fixed-window smoke outputs plus `.nsys-rep` and kernel summary JSON.
- Aggregate should include 3 reps and 100% request success.

## 2. RQ2: Diagnosis Accuracy

RQ2 reuses RQ1 outputs. Run both the microbenchmark analysis and the vLLM multiclass analysis.

### 2.1 Microbenchmark Accuracy

```bash
$MAIN_PY RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs \
  --run-pattern "rq1_${GPU_TAG}_compare_rep*" \
  --output-dir "RQ2/analysis/${GPU_TAG}_microbenchmark_accuracy"

RQ2_MICRO=$(ls -t RQ2/analysis/${GPU_TAG}_microbenchmark_accuracy/rq2_accuracy_*.json | head -1)

$MAIN_PY RQ2/scripts/make_paper_tables.py \
  --report "$RQ2_MICRO" \
  --output-dir "RQ2/analysis/${GPU_TAG}_microbenchmark_accuracy/paper_tables" \
  --min-match-rate 0.95 \
  --max-ambiguous-rate 0.05
```

### 2.2 vLLM Multiclass Full Run

This is the core RQ2 serving experiment: six scenarios, three seeds, automatic 30s and fixed-window 60s per scenario/seed.

```bash
SCENARIOS="healthy queue_pressure long_prompt long_output compute_saturation kv_cache_pressure"
SEEDS="5101 5102 5103"
base_port=8050
i=0

for scenario in $SCENARIOS; do
  for seed in $SEEDS; do
    port=$((base_port + i))
    i=$((i + 1))
    $MAIN_PY RQ1/scripts/run_vllm_nsys_compare.py \
      --model "$MODEL" \
      --scenario "$scenario" \
      --port "$port" \
      --vllm-python "$VLLM_PY" \
      --client-python "$MAIN_PY" \
      --nsys-path "$NSYS" \
      --seed "$seed" \
      --automatic-smoke-seconds 30 \
      --fixed-window-smoke-seconds 60 \
      --window-seconds 10 \
      --request-timeout-seconds 240 \
      --output-dir "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}/${scenario}_seed${seed}"
  done
done
```

Analyze and table it:

```bash
$MAIN_PY RQ2/scripts/analyze_accuracy.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --run-pattern "*" \
  --output-dir "RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy"

RQ2_VLLM=$(ls -t RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy/rq2_accuracy_*.json | head -1)

$MAIN_PY RQ2/scripts/make_paper_tables.py \
  --report "$RQ2_VLLM" \
  --output-dir "RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy/paper_tables" \
  --min-match-rate 0.95 \
  --max-ambiguous-rate 0.05
```

Expected full-run shape:

- 18 scenario/seed directories.
- Each directory has both `automatic/smoke` and `fixed_window/smoke`.
- RQ2 summary should cover all six vLLM labels in both modes.
- Success criteria should pass overall.

## 3. RQ3: Overhead

RQ3 has two pieces:

- Artifact-based profiler-cost overhead using RQ1/RQ2 outputs.
- Dedicated runtime overhead comparing `no_profiler` versus `cheap_metrics_only`.

### 3.1 Artifact-Based Overhead

```bash
$MAIN_PY RQ3/scripts/analyze_overhead.py \
  --rq1-micro-aggregate "$RQ1_MICRO_AGG" \
  --rq1-vllm-aggregate "$RQ1_VLLM_AGG" \
  --rq2-vllm-accuracy "$RQ2_VLLM" \
  --vllm-run-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --output-dir "RQ3/analysis/${GPU_TAG}_overhead"

RQ3_OVERHEAD=$(ls -t RQ3/analysis/${GPU_TAG}_overhead/rq3_overhead_*.json | head -1)
```

### 3.2 Dedicated Runtime Overhead

Run the paper-minimum randomized `queue_pressure` runtime overhead:

```bash
$MAIN_PY RQ3/scripts/run_vllm_runtime_overhead.py \
  --model "$MODEL" \
  --scenario queue_pressure \
  --seeds 6201 6202 6203 \
  --base-port 8071 \
  --vllm-python "$VLLM_PY" \
  --duration-seconds 30 \
  --window-seconds 10 \
  --request-timeout-seconds 240 \
  --mode-order randomized \
  --output-dir "RQ3/runs/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized"

RQ3_RUNTIME_SUMMARY=$(ls -t RQ3/runs/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized/runtime_overhead_summary_*.json | head -1)

$MAIN_PY RQ3/scripts/analyze_runtime_overhead.py \
  --summary "$RQ3_RUNTIME_SUMMARY" \
  --output-dir "RQ3/analysis/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized"

RQ3_RUNTIME_AGG=$(ls -t RQ3/analysis/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized/runtime_overhead_aggregate_*.json | head -1)
```

Optional strengthening, matching the later L4 support runs:

```bash
$MAIN_PY RQ3/scripts/run_vllm_runtime_overhead.py \
  --model "$MODEL" \
  --scenario healthy \
  --seeds 6301 6302 6303 \
  --base-port 8091 \
  --vllm-python "$VLLM_PY" \
  --duration-seconds 30 \
  --window-seconds 10 \
  --request-timeout-seconds 240 \
  --mode-order randomized \
  --output-dir "RQ3/runs/vllm_runtime_overhead_${GPU_TAG}_healthy_randomized"
```

Generate RQ3 paper tables:

```bash
$MAIN_PY RQ3/scripts/make_paper_tables.py \
  --summary "$RQ3_OVERHEAD" \
  --runtime-overhead "$RQ3_RUNTIME_AGG" \
  --output-dir "RQ3/analysis/${GPU_TAG}_overhead/paper_tables" \
  --min-match-rate 0.95 \
  --max-p95-regression-percent 5.0 \
  --min-runtime-success-rate 100.0
```

Expected full-run shape:

- Artifact table includes RQ1 microbenchmark rows, RQ1 vLLM row, and all six RQ2 vLLM rows.
- Runtime table includes at least `queue_pressure` with 3 randomized reps.
- Success JSON should report `overall_pass: true`.

## 4. RQ4: Policy Comparison

RQ4 starts with offline replay over the RQ2 vLLM multiclass windows, then creates a controlled ambiguity stress dataset. We also now have an optional full live policy-specific validation path.

### 4.1 Stable Policy Replay

```bash
$MAIN_PY RQ4/scripts/analyze_policies.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --output-dir "RQ4/analysis/policy_replay_${GPU_TAG}_vllm" \
  --mode automatic

RQ4_STABLE=$(ls -t RQ4/analysis/policy_replay_${GPU_TAG}_vllm/rq4_policy_summary_*.json | head -1)

$MAIN_PY RQ4/scripts/make_paper_tables.py \
  --summary "$RQ4_STABLE" \
  --output-dir "RQ4/analysis/policy_replay_${GPU_TAG}_vllm/paper_tables"
```

### 4.2 Stress Dataset And Stress Replay

```bash
$MAIN_PY RQ4/scripts/make_policy_stress_dataset.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --output-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm"

$MAIN_PY RQ4/scripts/analyze_policies.py \
  --input-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm" \
  --output-dir "RQ4/analysis/policy_stress_${GPU_TAG}_vllm" \
  --mode automatic

RQ4_STRESS=$(ls -t RQ4/analysis/policy_stress_${GPU_TAG}_vllm/rq4_policy_summary_*.json | head -1)

$MAIN_PY RQ4/scripts/make_paper_tables.py \
  --summary "$RQ4_STRESS" \
  --output-dir "RQ4/analysis/policy_stress_${GPU_TAG}_vllm/paper_tables"
```

Expected full-run shape:

- Stress dataset manifest exists.
- 18 transformed automatic-mode window CSVs.
- Replay detail has 108 rows: 6 scenarios x 3 seeds x 6 policies.
- Stress ranking should show `fixed_burst` failing under ambiguous-first-window conditions and multi-window policies recovering.

### 4.3 Full Live Policy-Specific Validation

If you want live policy-specific experiments, run the full 108-job validation from the stress replay detail CSV:

```bash
RQ4_STRESS_DETAIL=$(ls -t RQ4/analysis/policy_stress_${GPU_TAG}_vllm/rq4_policy_detail_*.csv | head -1)

$MAIN_PY RQ4/scripts/run_live_policy_validation.py \
  --policy-detail "$RQ4_STRESS_DETAIL" \
  --output-dir "RQ4/runs/live_policy_validation_${GPU_TAG}_vllm" \
  --model "$MODEL" \
  --vllm-python "$VLLM_PY" \
  --client-python "$MAIN_PY" \
  --nsys-path "$NSYS" \
  --base-port 8101 \
  --request-timeout-seconds 240
```

Expected full live-run shape:

- 108 `live_policy_result.json` files.
- 108 `.nsys-rep` files.
- 108 `.kernel_summary.json` files.
- Final `live_policy_summary_*.json` with `job_count: 108` and `ok_count: 108`.

For a quick pilot before the full live matrix:

```bash
$MAIN_PY RQ4/scripts/run_live_policy_validation.py \
  --policy-detail "$RQ4_STRESS_DETAIL" \
  --output-dir "RQ4/runs/live_policy_validation_${GPU_TAG}_pilot" \
  --model "$MODEL" \
  --vllm-python "$VLLM_PY" \
  --client-python "$MAIN_PY" \
  --nsys-path "$NSYS" \
  --scenarios queue_pressure \
  --seeds 5101 \
  --policies fixed_burst \
  --limit 1
```

## 5. RQ5: Stop-Signal Analysis

RQ5 uses RQ4 stress replay plus enriched real vLLM runs.

### 5.1 Stable And Stress Signal Analysis

```bash
$MAIN_PY RQ5/scripts/analyze_stop_signals.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --output-dir "RQ5/analysis/stop_signals_stable_${GPU_TAG}_vllm"

$MAIN_PY RQ5/scripts/analyze_stop_signals.py \
  --input-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm" \
  --output-dir "RQ5/analysis/stop_signals_stress_${GPU_TAG}_vllm"
```

### 5.2 Real Enriched vLLM Signal Runs

Start one vLLM server for these runs:

```bash
mkdir -p "RQ5/runs/enriched_real_${GPU_TAG}_vllm/server"
HF_HOME=/dev/shm/hf-cache "$VLLM_PY" -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --host 127.0.0.1 \
  --port 8102 \
  --dtype auto \
  --gpu-memory-utilization 0.82 \
  --max-model-len 4096 \
  --max-num-seqs 32 \
  > "RQ5/runs/enriched_real_${GPU_TAG}_vllm/server/vllm_server.log" 2>&1 &
echo $! > "RQ5/runs/enriched_real_${GPU_TAG}_vllm/server/vllm_server.pid"
```

Wait until `http://127.0.0.1:8102/v1/models` responds, then run the 18 real enriched scenario/seed jobs:

```bash
SCENARIOS="healthy queue_pressure long_prompt long_output compute_saturation kv_cache_pressure"
SEEDS="9201 9202 9203"

for scenario in $SCENARIOS; do
  for seed in $SEEDS; do
    $MAIN_PY RQ1/scripts/run_vllm_smoke.py \
      --model "$MODEL" \
      --endpoint http://127.0.0.1:8102/v1/completions \
      --scenario "$scenario" \
      --duration-seconds 60 \
      --window-seconds 10 \
      --request-timeout-seconds 240 \
      --seed "$seed" \
      --output-dir "RQ5/runs/enriched_real_${GPU_TAG}_vllm/${scenario}_seed${seed}/automatic/smoke"
  done
done
```

Stop the server:

```bash
kill -INT "$(cat RQ5/runs/enriched_real_${GPU_TAG}_vllm/server/vllm_server.pid)"
```

Analyze and generate final RQ5 tables:

```bash
$MAIN_PY RQ5/scripts/analyze_stop_signals.py \
  --input-root "RQ5/runs/enriched_real_${GPU_TAG}_vllm" \
  --output-dir "RQ5/analysis/stop_signals_enriched_real_${GPU_TAG}_vllm"

RQ5_REAL=$(ls -t RQ5/analysis/stop_signals_enriched_real_${GPU_TAG}_vllm/rq5_signal_summary_*.json | head -1)
RQ5_STRESS=$(ls -t RQ5/analysis/stop_signals_stress_${GPU_TAG}_vllm/rq5_signal_summary_*.json | head -1)

$MAIN_PY RQ5/scripts/make_paper_tables.py \
  --stable-summary "$RQ5_REAL" \
  --stress-summary "$RQ5_STRESS" \
  --output-dir "RQ5/analysis/paper_tables_enriched_real_${GPU_TAG}"
```

Expected full-run shape:

- 18 enriched real run directories.
- 18 scenario-specific request CSVs and 18 scenario-specific window CSVs.
- Signal detail covers all six scenarios and all three seeds.
- Final table should identify which signals are paper-ready under stable plus stress criteria.

## 6. Sanity Checks After A Full New-GPU Run

Run these checks before comparing results to the L4 artifacts:

```bash
$MAIN_PY -m py_compile \
  RQ1/scripts/run_microbenchmarks.py \
  RQ1/scripts/run_vllm_smoke.py \
  RQ1/scripts/run_vllm_nsys_compare.py \
  RQ1/scripts/analyze_repetitions.py \
  RQ1/scripts/analyze_vllm_nsys_repetitions.py \
  RQ2/scripts/analyze_accuracy.py \
  RQ2/scripts/make_paper_tables.py \
  RQ3/scripts/analyze_overhead.py \
  RQ3/scripts/run_vllm_runtime_overhead.py \
  RQ3/scripts/analyze_runtime_overhead.py \
  RQ3/scripts/make_paper_tables.py \
  RQ4/scripts/analyze_policies.py \
  RQ4/scripts/make_policy_stress_dataset.py \
  RQ4/scripts/make_paper_tables.py \
  RQ4/scripts/run_live_policy_validation.py \
  RQ5/scripts/analyze_stop_signals.py \
  RQ5/scripts/make_paper_tables.py
```

Artifact-count checks:

```bash
find "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" -name 'vllm_nsys_comparison_*.json' | wc -l
find "RQ4/datasets/policy_stress_${GPU_TAG}_vllm" -name '*_windows_*.csv' ! -name 'all_windows_*' | wc -l
find "RQ5/runs/enriched_real_${GPU_TAG}_vllm" -name 'vllm_smoke_summary_*.json' | wc -l
```

Expected counts:

- RQ2 vLLM comparisons: `18`.
- RQ4 stress scenario window files: `18`.
- RQ5 enriched real summaries: `18`.

For live RQ4 validation, if run:

```bash
find "RQ4/runs/live_policy_validation_${GPU_TAG}_vllm" -name 'live_policy_result.json' | wc -l
find "RQ4/runs/live_policy_validation_${GPU_TAG}_vllm" -name '*.nsys-rep' | wc -l
find "RQ4/runs/live_policy_validation_${GPU_TAG}_vllm" -name '*.kernel_summary.json' | wc -l
```

Expected live RQ4 counts:

- Result JSONs: `108`.
- Nsight reports: `108`.
- Kernel summaries: `108`.

## 7. Notes For Comparing GPUs

Keep these constant when possible:

- Model: `Qwen/Qwen2.5-7B-Instruct`.
- Scenario set and seeds.
- Automatic/fixed-window durations.
- Window size.
- Nsight trace settings.
- vLLM `max-model-len`, `max-num-seqs`, and GPU memory utilization.

If a GPU cannot support the same model/settings, record the changed model or serving parameters in the output directory name and in the writeup. Treat those results as a new configuration, not a strict apples-to-apples GPU comparison.

The scripts write timestamped outputs. In follow-on commands, prefer selecting the latest JSON/CSV in the newly created directory, as shown above, instead of editing commands with old L4 timestamps.
