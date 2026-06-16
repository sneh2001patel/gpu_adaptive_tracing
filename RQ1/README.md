# RQ1 Local Run Guide

This directory contains the Phase 0 local GPU experiment for RQ1 on the RTX 4060 Ti 8GB.

## Environment

Use the local conda environment that was created for RQ1:

```bash
conda activate /home/snehpatel/research/adaptive_tracing_when_to_stop/gpu_adaptive_tracing/RQ1/.conda
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
for rep in 1 2 3; do
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
    --output-dir "RQ1/runs/rq1_compare_rep${rep}"
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
  --pattern 'rq1_compare_rep*/comparison_*.json' \
  --output-dir RQ1/analysis/step7_fresh_reps
```

Generate compact paper-table outputs and first-pass success checks:

```bash
python RQ1/scripts/make_paper_tables.py \
  --aggregate RQ1/analysis/step7_fresh_reps/aggregate_1781552298.json \
  --output-dir RQ1/analysis/step7_fresh_reps/paper_tables
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
  --run-dir RQ1/runs/rq1_compare_rep1 \
  --run-dir RQ1/runs/rq1_compare_rep2 \
  --run-dir RQ1/runs/rq1_compare_rep3
```

For Phase 0, keep using 3 repetitions while tuning the controller. Use 5 repetitions for the first internal result snapshot.

The first 5-repetition snapshot is stored under:

- `RQ1/analysis/step9_5rep_snapshot/aggregate_1781553516.csv`
- `RQ1/analysis/step9_5rep_snapshot/paper_tables/paper_table_1781553526.md`
- `RQ1/analysis/step9_5rep_snapshot/figures/trace_time_saved_percent_1781553526.svg`
- `RQ1/analysis/step9_5rep_snapshot/figures/diagnosis_match_rate_1781553526.svg`

RQ2 now reuses the same RQ1 microbenchmark outputs for Phase 0 accuracy analysis:

```bash
python RQ2/scripts/analyze_accuracy.py \
  --input-root RQ1/runs \
  --run-pattern 'rq1_compare_rep*' \
  --output-dir RQ2/analysis/step9_accuracy
```
