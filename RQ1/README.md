# RQ1 Run Guide

This directory contains the RQ1 GPU tracing experiments. The current active target is the NVIDIA L4 24GB host.

## Environment

Use the active L4 conda environment:

```bash
conda activate /venv/main
```

Quick checks:

```bash
python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
PY

nsys --version
```

DCGM is not required for Phase 0. The current runner uses NVML through `nvidia-ml-py` for cheap GPU metrics.

The current L4 snapshot used:

- PyTorch `2.5.1`.
- PyTorch CUDA `12.4`.
- Nsight Systems `2024.6.2.225-246235244400v0`.
- GPU `NVIDIA L4`.

## Smoke Run Without Nsight

Use this first when checking that CUDA, PyTorch, and NVML are working:

```bash
python RQ1/scripts/run_microbenchmarks.py \
  --mode automatic \
  --workload all \
  --duration-seconds 6 \
  --window-seconds 2 \
  --output-dir RQ1/runs/smoke_local
```

## Automatic Versus Fixed-Window Run

This runs the three RQ1 workloads in automatic mode and fixed-window baseline mode:

```bash
python RQ1/scripts/run_microbenchmarks.py \
  --mode compare \
  --workload all \
  --duration-seconds 20 \
  --window-seconds 5 \
  --enable-nsys-bursts \
  --nsys-burst-seconds 2 \
  --fixed-window-nsys-seconds 8 \
  --max-nsys-bursts-per-workload 1 \
  --fixed-window-bursts-per-workload 1 \
  --stability-stop-windows 2 \
  --output-dir RQ1/runs/rq1_compare_rep1
```

The fixed-window baseline should use a longer profiler duration than automatic mode. In the command above, automatic mode traces 2 seconds per burst and fixed-window mode traces 8 seconds per burst.

## Repetitions

Run several repetitions with different output directories:

```bash
for rep in 1 2 3 4 5; do
  python RQ1/scripts/run_microbenchmarks.py \
    --mode compare \
    --workload all \
    --duration-seconds 20 \
    --window-seconds 5 \
    --enable-nsys-bursts \
    --nsys-burst-seconds 2 \
    --fixed-window-nsys-seconds 8 \
    --max-nsys-bursts-per-workload 1 \
    --fixed-window-bursts-per-workload 1 \
    --stability-stop-windows 2 \
    --output-dir "RQ1/runs/rq1_l4_compare_rep${rep}"
done
```

Then aggregate all comparison summaries:

```bash
python RQ1/scripts/analyze_repetitions.py \
  --input-root RQ1/runs \
  --output-dir RQ1/analysis
```

To aggregate only the fresh repetition directories:

```bash
python RQ1/scripts/analyze_repetitions.py \
  --input-root RQ1/runs \
  --pattern 'rq1_l4_compare_rep*/comparison_*.json' \
  --output-dir RQ1/analysis/l4_5rep_snapshot
```

Generate compact paper-table outputs and first-pass success checks:

```bash
python RQ1/scripts/make_paper_tables.py \
  --aggregate RQ1/analysis/l4_5rep_snapshot/aggregate_1781639990.json \
  --output-dir RQ1/analysis/l4_5rep_snapshot/paper_tables
```

The initial RQ1 success checks are:

- Automatic mode saves at least 25% profiler duration compared with fixed-window mode.
- The expected diagnosis label appears in at least 95% of suspicious automatic windows.
- Automatic profiler burst count is stable across repetitions, with burst-count standard deviation at most 0.25.

## Outputs

Each run directory contains:

- Per-window CSV files under `automatic/` and `fixed_window/`.
- Per-mode `summary_*.json` files.
- Optional Nsight Systems reports under `profiles/`.
- Optional kernel summary JSON files generated from `nsys stats`.
- A top-level `comparison_*.json`.
- A top-level `rq1_summary_table_*.csv`.

The repetition analysis writes:

- `aggregate_<timestamp>.csv`.
- `aggregate_<timestamp>.json`.

The paper-table script writes:

- `paper_table_<timestamp>.csv`.
- `paper_table_<timestamp>.md`.
- `paper_table_<timestamp>.tex`.
- `success_criteria_<timestamp>.json`.

The figure script writes SVG files for draft figures:

```bash
python RQ1/scripts/make_paper_figures.py \
  --aggregate RQ1/analysis/step8_enhanced_reps/aggregate_1781552692.json \
  --output-dir RQ1/analysis/step8_enhanced_reps/figures
```

The manifest script records the command settings and local environment for each repetition:

```bash
python RQ1/scripts/write_experiment_manifest.py \
  --run-dir RQ1/runs/rq1_l4_compare_rep1 \
  --run-dir RQ1/runs/rq1_l4_compare_rep2 \
  --run-dir RQ1/runs/rq1_l4_compare_rep3 \
  --run-dir RQ1/runs/rq1_l4_compare_rep4 \
  --run-dir RQ1/runs/rq1_l4_compare_rep5
```

For Phase 0, keep using 3 repetitions while tuning the controller. Use 5 repetitions for the first internal result snapshot.

The current L4 5-repetition snapshot is stored under:

- `RQ1/analysis/l4_5rep_snapshot/aggregate_1781639990.csv`
- `RQ1/analysis/l4_5rep_snapshot/paper_tables/paper_table_1781640003.md`
- `RQ1/analysis/l4_5rep_snapshot/figures/trace_time_saved_percent_1781640003.svg`
- `RQ1/analysis/l4_5rep_snapshot/figures/diagnosis_match_rate_1781640003.svg`

The original local 5-repetition snapshot is stored under:

- `RQ1/analysis/step9_5rep_snapshot/aggregate_1781553516.csv`
- `RQ1/analysis/step9_5rep_snapshot/paper_tables/paper_table_1781553526.md`
- `RQ1/analysis/step9_5rep_snapshot/figures/trace_time_saved_percent_1781553526.svg`
- `RQ1/analysis/step9_5rep_snapshot/figures/diagnosis_match_rate_1781553526.svg`

## L4 vLLM Smoke

Step 11 adds a first vLLM smoke plan and harness for the L4:

- Plan: `RQ1/vllm_smoke_plan.md`
- Harness: `RQ1/scripts/run_vllm_smoke.py`
- Nsight compare harness: `RQ1/scripts/run_vllm_nsys_compare.py`

Default model:

- `Qwen/Qwen2.5-7B-Instruct`

Use a separate vLLM environment so `/venv/main` remains the validated microbenchmark environment:

```bash
/venv/vllm/bin/python -m pip install 'vllm==0.10.2'
/venv/vllm/bin/python -m pip install \
  'transformers==4.56.2' \
  'tokenizers==0.22.1' \
  'fastapi==0.115.14' \
  'starlette==0.46.2' \
  'prometheus-fastapi-instrumentator==7.1.0' \
  'uvicorn==0.34.3'
```

Start a vLLM OpenAI-compatible server:

```bash
HF_HOME=/dev/shm/hf-cache /venv/vllm/bin/vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.82 \
  --max-model-len 4096 \
  --max-num-seqs 32
```

Run a quick healthy scenario:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario healthy \
  --duration-seconds 20 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_smoke_quick
```

Run all smoke scenarios:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario all \
  --duration-seconds 60 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_smoke
```

Run a short automatic versus fixed-window Nsight comparison around a vLLM smoke workload:

```bash
python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8010 \
  --automatic-smoke-seconds 12 \
  --fixed-window-smoke-seconds 24 \
  --window-seconds 6 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure
```

Run 3 seeded repetitions for the selected `queue_pressure` serving workload:

```bash
python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8011 \
  --seed 101 \
  --automatic-smoke-seconds 12 \
  --fixed-window-smoke-seconds 24 \
  --window-seconds 6 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_rep1

python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8012 \
  --seed 202 \
  --automatic-smoke-seconds 12 \
  --fixed-window-smoke-seconds 24 \
  --window-seconds 6 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_rep2

python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8013 \
  --seed 303 \
  --automatic-smoke-seconds 12 \
  --fixed-window-smoke-seconds 24 \
  --window-seconds 6 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_rep3
```

Aggregate the seeded vLLM repetitions:

```bash
python RQ1/scripts/analyze_vllm_nsys_repetitions.py \
  --input-root RQ1/runs \
  --pattern 'vllm_l4_nsys_queue_pressure_rep*/vllm_nsys_comparison_*.json' \
  --output-dir RQ1/analysis/vllm_l4_nsys_queue_pressure
```

Run longer vLLM repetitions for the paper-ready serving result:

```bash
python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8021 \
  --seed 1111 \
  --automatic-smoke-seconds 30 \
  --fixed-window-smoke-seconds 60 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_long_rep1

python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8022 \
  --seed 2222 \
  --automatic-smoke-seconds 30 \
  --fixed-window-smoke-seconds 60 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_long_rep2

python RQ1/scripts/run_vllm_nsys_compare.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario queue_pressure \
  --port 8023 \
  --seed 3333 \
  --automatic-smoke-seconds 30 \
  --fixed-window-smoke-seconds 60 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_nsys_queue_pressure_long_rep3
```

Aggregate the longer vLLM repetitions and generate paper outputs:

```bash
python RQ1/scripts/analyze_vllm_nsys_repetitions.py \
  --input-root RQ1/runs \
  --pattern 'vllm_l4_nsys_queue_pressure_long_rep*/vllm_nsys_comparison_*.json' \
  --output-dir RQ1/analysis/vllm_l4_nsys_queue_pressure_long

python RQ1/scripts/make_vllm_paper_tables.py \
  --aggregate RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json \
  --output-dir RQ1/analysis/vllm_l4_nsys_queue_pressure_long/paper_tables

python RQ1/scripts/make_vllm_paper_figures.py \
  --aggregate RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json \
  --output-dir RQ1/analysis/vllm_l4_nsys_queue_pressure_long/figures
```

The first L4 vLLM smoke artifacts are:

- Quick healthy smoke: `RQ1/runs/vllm_l4_smoke_quick_fixed/`
- Full smoke sweep: `RQ1/runs/vllm_l4_smoke_full/`
- Corrected long-prompt smoke: `RQ1/runs/vllm_l4_smoke_long_prompt_fixed/`
- Corrected KV-cache smoke: `RQ1/runs/vllm_l4_smoke_kv_fixed/`
- Nsight comparison: `RQ1/runs/vllm_l4_nsys_queue_pressure/vllm_nsys_comparison_1781642848.json`
- Seeded Nsight aggregate: `RQ1/analysis/vllm_l4_nsys_queue_pressure/vllm_nsys_aggregate_1781644983.json`
- Longer-window seeded Nsight aggregate: `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/vllm_nsys_aggregate_1781646112.json`
- Longer-window vLLM paper table: `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/paper_tables/vllm_paper_table_1781646125.md`
- Longer-window vLLM figures:
  - `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/figures/vllm_trace_time_saved_percent_1781646125.svg`
  - `RQ1/analysis/vllm_l4_nsys_queue_pressure_long/figures/vllm_kernel_instances_1781646125.svg`

RQ2 now reuses the same RQ1 microbenchmark outputs for Phase 0 accuracy analysis:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs \
  --run-pattern 'rq1_l4_compare_rep*' \
  --output-dir RQ2/analysis/step9_accuracy
```
