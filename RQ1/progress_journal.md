# RQ1 Progress Journal

## Research Question

Can an adaptive GPU tracing controller determine when heavy GPU tracing has collected sufficient diagnostic evidence?

## Current Scope

- Phase 0 local development on RTX 4060 Ti 8GB.
- Start with controlled CUDA/PyTorch microbenchmarks.
- Build and validate the controller loop before running vLLM workloads.

## Completed Steps

### Step 1:

- Created `RQ1/` workspace.
- Created this progress journal.
- Added Phase 0 local development plan to `plan.md`.

### Step 2:

- Selected the first GPU-heavy workload scope:
  - Kernel launch frequency workload.
  - Mixed compute and memory workload.
  - Compute-bound GEMM loop.
- Kept the 15 cheap metrics listed below as the first always-on metric set.
- Created a local conda environment at `RQ1/.conda`.
- Installed PyTorch with CUDA support in `RQ1/.conda`.
- Installed CUDA compiler/profiling support in `RQ1/.conda`:
  - `cuda-nvcc`.
  - `cuda-cupti`.
  - `cuda-nvtx`.
- Installed Python metric/logging support:
  - `nvidia-ml-py`.
  - `psutil`.
  - `pandas`.
- Installed Nsight Systems CLI locally under `RQ1/tools/nsight-systems`.
- Added an `nsys` wrapper in `RQ1/.conda/bin/nsys`.
- Verified PyTorch GPU execution on the local RTX 4060 Ti.
- Verified CUDA compiler availability with `nvcc --version`.
- Verified NVML access for cheap GPU metrics.

Step 2 verification results:

- PyTorch version: `2.5.1`.
- PyTorch CUDA version: `12.4`.
- CUDA available in PyTorch: `True`.
- GPU detected by PyTorch: `NVIDIA GeForce RTX 4060 Ti`.
- CUDA compiler: `nvcc 12.4.131`.
- Nsight Systems CLI: `2026.1.3.243`.
- NVML metrics available through `nvidia-ml-py`.

Step 2 limitation:

- DCGM tooling is not installed yet.
- On this Arch system, `dcgmi` and `nv-hostengine` are not present, the normal Arch package search did not expose a DCGM package, and Docker GPU passthrough is not configured.
- For Phase 0, use NVML/`nvidia-smi` for the cheap metrics first. Revisit DCGM when running on a supported cloud Linux image or after installing system-level NVIDIA container/DCGM packages with root access.

### Step 3:

- Implemented the first microbenchmark runner at `RQ1/scripts/run_microbenchmarks.py`.
- Added the three selected workloads:
  - `launch_overhead_or_small_kernel`.
  - `mixed`.
  - `compute_bound`.
- Added windowed CSV logging under `RQ1/runs/`.
- Added one JSON summary file per run.
- Added background NVML sampling so cheap GPU metrics are collected during workload execution instead of only after synchronized iterations.
- Added workload labels to each logged window.
- Added the first suspicious-window trigger rule:
  - Trigger on high mean GPU utilization.
  - Trigger on high memory use.
  - Trigger on latency regression relative to the first window baseline.
  - Trigger on high launch rate for the kernel launch frequency workload.
- Verified the runner with reduced-size smoke tests.
- Verified the runner with short default-size tests.

Step 3 verification results:

- Reduced-size smoke run output: `RQ1/runs/smoke2/`.
- Short default-size run output: `RQ1/runs/short_default2/`.
- Launch-trigger validation output: `RQ1/runs/launch_trigger_check/`.
- `mixed` and `compute_bound` triggered suspicious windows through `high_gpu_util`.
- `launch_overhead_or_small_kernel` triggered suspicious windows through `high_launch_rate`.
- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py`.

### Step 4:

- Added optional Nsight Systems burst collection when a suspicious window fires.
- Added `--enable-nsys-bursts` to turn profiler bursts on explicitly.
- Added `--nsys-burst-seconds` to control burst duration.
- Added profiler output fields to each CSV row:
  - `profiler_mode`.
  - `profiler_output_prefix`.
  - `profiler_report_paths`.
  - `profiler_status`.
  - `profiler_returncode`.
  - `profiler_duration_s`.
- Stored profiler output paths in each run summary.
- Added first-pass diagnosis labels from cheap metrics and profiler evidence:
  - `compute_bound`.
  - `mixed`.
  - `launch_overhead_or_small_kernel`.
  - `mixed_compute_memory_pressure`.
  - `latency_regression_unknown_gpu_cause`.
  - `healthy_or_not_suspicious`.
- Added `fixed_window` mode as the first manual-style baseline.
- Added `compare` mode to run automatic and fixed-window modes into sibling output folders and write one comparison JSON.

Step 4 verification results:

- Automatic profiler-burst check output: `RQ1/runs/step4_auto_check2/`.
- Fixed-window baseline check output: `RQ1/runs/step4_fixed_check/`.
- Automatic versus fixed-window comparison output: `RQ1/runs/step4_compare_check/`.
- Automatic mode collected an Nsight report at `RQ1/runs/step4_compare_check/automatic/profiles/compute_bound_window0_automatic_trigger_1781548075.nsys-rep`.
- Fixed-window mode collected an Nsight report at `RQ1/runs/step4_compare_check/fixed_window/profiles/compute_bound_window0_fixed_window_1781548080.nsys-rep`.
- Comparison summary written at `RQ1/runs/step4_compare_check/comparison_1781548084.json`.
- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py`.

### Step 5:

- Ran comparison mode across all three selected workloads with longer windows.
- Added lightweight profiler feature extraction from Nsight outputs using `nsys stats --report cuda_gpu_kern_sum`.
- Added per-burst kernel summary files next to each `.nsys-rep`.
- Added profiler feature fields to CSV rows and summaries:
  - Kernel count.
  - Kernel instances.
  - Total kernel time.
  - Average kernel duration.
  - Top kernel name.
  - Kernel summary path.
- Added a diagnosis-stability stopping policy for automatic mode:
  - Once the same suspicious diagnosis appears for `--stability-stop-windows`, automatic mode records `stable_diagnosis:<label>:<N>_windows`.
  - Further automatic profiler bursts are skipped after that stop reason appears.
- Added an RQ1 summary table for automatic versus fixed-window comparison.
- Corrected run timing so profiler burst wall time does not consume the intended workload window duration.

Step 5 verification results:

- Full all-workload comparison output: `RQ1/runs/step5_all_workloads_compare_v2/`.
- Comparison summary: `RQ1/runs/step5_all_workloads_compare_v2/comparison_1781549876.json`.
- RQ1 summary table: `RQ1/runs/step5_all_workloads_compare_v2/rq1_summary_table_1781549876.csv`.
- Automatic mode collected one Nsight burst per selected workload and then stopped further bursts after diagnosis stability.
- Fixed-window mode collected one fixed-window Nsight burst per selected workload.
- Kernel-summary JSON files were generated for all six Nsight reports.
- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py`.

### Step 6:

- Added a local RQ1 run guide at `RQ1/README.md`.
- Documented how to:
  - Activate the local conda environment.
  - Run a smoke test without Nsight.
  - Run automatic mode against the fixed-window baseline.
  - Run multiple repetitions.
  - Aggregate repetition results.
- Added a richer fixed-window baseline by separating profiler duration settings:
  - Automatic mode uses `--nsys-burst-seconds`.
  - Fixed-window mode uses `--fixed-window-nsys-seconds`.
  - Default fixed-window profiler duration is now longer than automatic mode.
- Added the first repetition aggregation script at `RQ1/scripts/analyze_repetitions.py`.
- The aggregation script reads `comparison_*.json` files and writes:
  - One aggregate CSV row per workload.
  - Mean and standard deviation for windows, suspicious windows, profiler bursts, profiler durations, kernel instances, and kernel time.
  - Mean profiler duration saved by automatic mode relative to fixed-window mode.
  - Total diagnosis-label counts across repetitions.
- Fixed final-window profiler accounting so a burst collected in the final partial window increments the local burst counter.

Step 6 verification results:

- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py RQ1/scripts/analyze_repetitions.py`.
- CLI check confirmed `--fixed-window-nsys-seconds` is available.
- Fixed-window duration check output: `RQ1/runs/step6_fixed_window_duration_check/`.
- Step 6 comparison summary: `RQ1/runs/step6_fixed_window_duration_check/comparison_1781551115.json`.
- Automatic profiler duration in the Step 6 check was shorter than fixed-window profiler duration.
- Repetition aggregate CSV: `RQ1/analysis/aggregate_1781551123.csv`.
- Repetition aggregate JSON: `RQ1/analysis/aggregate_1781551123.json`.

### Step 7:

- Ran 3 fresh comparison repetitions using the Step 6 command shape.
- Kept the output directories separate:
  - `RQ1/runs/rq1_compare_rep1/`.
  - `RQ1/runs/rq1_compare_rep2/`.
  - `RQ1/runs/rq1_compare_rep3/`.
- Re-ran `RQ1/scripts/analyze_repetitions.py` against only the fresh repetition directories.
- Added a paper-table and success-check script at `RQ1/scripts/make_paper_tables.py`.
- Generated compact table outputs for Step 7:
  - CSV table.
  - Markdown table.
  - LaTeX table.
  - JSON success criteria report.
- Decided the first RQ1 success criteria:
  - Automatic mode should save at least 25% profiler duration compared with fixed-window mode.
  - The expected diagnosis label should appear in at least 95% of suspicious automatic windows.
  - Automatic profiler burst count should be stable across repetitions, with burst-count standard deviation at most 0.25.

Step 7 verification results:

- Fresh comparison summaries:
  - `RQ1/runs/rq1_compare_rep1/comparison_1781551889.json`.
  - `RQ1/runs/rq1_compare_rep2/comparison_1781552090.json`.
  - `RQ1/runs/rq1_compare_rep3/comparison_1781552292.json`.
- Fresh repetition aggregate CSV: `RQ1/analysis/step7_fresh_reps/aggregate_1781552298.csv`.
- Fresh repetition aggregate JSON: `RQ1/analysis/step7_fresh_reps/aggregate_1781552298.json`.
- Paper-ready Markdown table: `RQ1/analysis/step7_fresh_reps/paper_tables/paper_table_1781552366.md`.
- Paper-ready LaTeX table: `RQ1/analysis/step7_fresh_reps/paper_tables/paper_table_1781552366.tex`.
- Success criteria report: `RQ1/analysis/step7_fresh_reps/paper_tables/success_criteria_1781552366.json`.
- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py RQ1/scripts/analyze_repetitions.py RQ1/scripts/make_paper_tables.py`.
- Initial Step 7 result:
  - `compute_bound`: automatic trace mean 7.004s, fixed-window trace mean 13.048s, saved 46.3%, expected-label match rate 1.0.
  - `launch_overhead_or_small_kernel`: automatic trace mean 11.926s, fixed-window trace mean 22.745s, saved 47.6%, expected-label match rate 1.0.
  - `mixed`: automatic trace mean 9.865s, fixed-window trace mean 17.447s, saved 43.5%, expected-label match rate 1.0.
- All three workloads passed the first RQ1 success criteria.

### Step 8:

- Enhanced `RQ1/scripts/analyze_repetitions.py` with:
  - Minimum and maximum columns for each numeric aggregate.
  - 95% confidence interval half-width columns for each numeric aggregate.
  - Minimum, maximum, and 95% confidence interval half-width for profiler duration saved.
- Added `RQ1/scripts/write_experiment_manifest.py`.
- Wrote reproducibility manifests for each fresh repetition:
  - `RQ1/runs/rq1_compare_rep1/experiment_manifest.json`.
  - `RQ1/runs/rq1_compare_rep2/experiment_manifest.json`.
  - `RQ1/runs/rq1_compare_rep3/experiment_manifest.json`.
- Each manifest records:
  - Command settings.
  - GPU name.
  - NVIDIA driver version from `nvidia-smi`.
  - PyTorch version.
  - PyTorch CUDA version.
  - Nsight Systems version.
  - Key output artifacts.
- Added `RQ1/scripts/make_paper_figures.py`.
- Generated paper-ready SVG plots for:
  - Trace-time savings.
  - Diagnosis match rate.
- Regenerated paper tables and success criteria from the enhanced aggregate.
- Decided the repetition policy:
  - Keep using 3 repetitions for fast Phase 0 iteration.
  - Move to 5 repetitions for the first internal result snapshot because the current data is stable but still small.
- Started RQ2 planning in `RQ2/planning.md`.

Step 8 verification results:

- Enhanced aggregate CSV: `RQ1/analysis/step8_enhanced_reps/aggregate_1781552692.csv`.
- Enhanced aggregate JSON: `RQ1/analysis/step8_enhanced_reps/aggregate_1781552692.json`.
- Trace-time savings figure: `RQ1/analysis/step8_enhanced_reps/figures/trace_time_saved_percent_1781552702.svg`.
- Diagnosis match-rate figure: `RQ1/analysis/step8_enhanced_reps/figures/diagnosis_match_rate_1781552702.svg`.
- Paper-ready Markdown table: `RQ1/analysis/step8_enhanced_reps/paper_tables/paper_table_1781552702.md`.
- Paper-ready LaTeX table: `RQ1/analysis/step8_enhanced_reps/paper_tables/paper_table_1781552702.tex`.
- Success criteria report: `RQ1/analysis/step8_enhanced_reps/paper_tables/success_criteria_1781552702.json`.
- Syntax check passed with `python -m py_compile RQ1/scripts/run_microbenchmarks.py RQ1/scripts/analyze_repetitions.py RQ1/scripts/make_paper_tables.py RQ1/scripts/make_paper_figures.py RQ1/scripts/write_experiment_manifest.py`.

### Step 9:

- Ran two more fresh repetitions for the first internal 5-repetition snapshot:
  - `RQ1/runs/rq1_compare_rep4/`.
  - `RQ1/runs/rq1_compare_rep5/`.
- Wrote reproducibility manifests for the new repetitions:
  - `RQ1/runs/rq1_compare_rep4/experiment_manifest.json`.
  - `RQ1/runs/rq1_compare_rep5/experiment_manifest.json`.
- Re-ran the enhanced RQ1 aggregate across all 5 repetitions.
- Regenerated RQ1 paper tables, success checks, and SVG figures across all 5 repetitions.
- Added the first RQ2 per-window accuracy script at `RQ2/scripts/analyze_accuracy.py`.
- Ran RQ2 analysis over the automatic and fixed-window per-window CSV files from all 5 RQ1 repetitions.
- RQ2 Phase 0 decision:
  - Reuse the RQ1 microbenchmark outputs for Phase 0 RQ2 analysis.
  - A separate RQ2 run layout is not needed until vLLM-specific workload phases are added.
- Updated `RQ2/planning.md` with the Step 9 RQ2 result and next tasks.

Step 9 verification results:

- New comparison summaries:
  - `RQ1/runs/rq1_compare_rep4/comparison_1781553313.json`.
  - `RQ1/runs/rq1_compare_rep5/comparison_1781553508.json`.
- Five-repetition RQ1 aggregate CSV: `RQ1/analysis/step9_5rep_snapshot/aggregate_1781553516.csv`.
- Five-repetition RQ1 aggregate JSON: `RQ1/analysis/step9_5rep_snapshot/aggregate_1781553516.json`.
- Five-repetition paper-ready Markdown table: `RQ1/analysis/step9_5rep_snapshot/paper_tables/paper_table_1781553526.md`.
- Five-repetition paper-ready LaTeX table: `RQ1/analysis/step9_5rep_snapshot/paper_tables/paper_table_1781553526.tex`.
- Five-repetition success criteria report: `RQ1/analysis/step9_5rep_snapshot/paper_tables/success_criteria_1781553526.json`.
- Five-repetition trace-time savings figure: `RQ1/analysis/step9_5rep_snapshot/figures/trace_time_saved_percent_1781553526.svg`.
- Five-repetition diagnosis match-rate figure: `RQ1/analysis/step9_5rep_snapshot/figures/diagnosis_match_rate_1781553526.svg`.
- RQ2 accuracy summary: `RQ2/analysis/step9_accuracy/rq2_accuracy_summary_1781553587.csv`.
- RQ2 confusion table: `RQ2/analysis/step9_accuracy/rq2_confusion_1781553587.csv`.
- RQ2 disagreement table: `RQ2/analysis/step9_accuracy/rq2_disagreement_1781553587.csv`.
- RQ2 JSON report: `RQ2/analysis/step9_accuracy/rq2_accuracy_1781553587.json`.
- Five-repetition RQ1 result:
  - `compute_bound`: automatic trace mean 7.422s, fixed-window trace mean 12.313s, saved 39.7%, expected-label match rate 1.0.
  - `launch_overhead_or_small_kernel`: automatic trace mean 12.109s, fixed-window trace mean 21.445s, saved 43.5%, expected-label match rate 1.0.
  - `mixed`: automatic trace mean 9.306s, fixed-window trace mean 17.487s, saved 46.8%, expected-label match rate 1.0.
- RQ2 result:
  - Automatic expected-label match rate on suspicious windows was 1.0 for all three workloads.
  - Fixed-window expected-label match rate on suspicious windows was 1.0 for all three workloads.
  - Automatic versus fixed-window disagreement rate was 0.25 for `compute_bound`, 0.0286 for `launch_overhead_or_small_kernel`, and 0.2121 for `mixed`.

## Next Steps

### Step 10:

- Add a scaled-down vLLM smoke plan for the RTX 4060 Ti 8GB.
- Select a small or quantized model that fits in 8GB VRAM.
- Define vLLM smoke scenarios:
  - Healthy low-concurrency serving.
  - Queue pressure.
  - Long prompt or long output pressure.
  - GPU compute saturation if feasible.
- Decide the minimal request-level metrics to add before vLLM:
  - Request latency.
  - Throughput.
  - Queueing delay if available.
  - Prompt and output token counts.
- Extend the controller schema so RQ1/RQ2 tables can include vLLM labels after the microbenchmark phase.

Selected GPU-heavy microbenchmark workload set:

1. Kernel launch frequency workload
   - Run many small GPU operations in a tight loop.
   - Expected label: `launch_overhead_or_small_kernel`.
   - Goal: create behavior where GPU utilization may look uneven and heavy tracing can reveal many short kernels.

2. Mixed compute and memory workload
   - Alternate matrix multiplication with large tensor transforms.
   - Expected label: `mixed`.
   - Goal: create a diagnosis case where cheap metrics may be less clear.

3. Compute-bound GEMM loop
   - Repeated large matrix multiplications using `torch.matmul`.
   - Expected label: `compute_bound`.
   - Goal: drive high SM/GPU utilization with relatively stable memory use.

Deferred workload candidates:

1. Memory-bandwidth tensor streaming
   - Repeated large tensor reads/writes, copies, elementwise ops, and reductions.
   - Expected label: `memory_bound`.
   - Goal: stress GPU memory bandwidth more than CPU scheduling.

2. GPU memory pressure workload
   - Allocate and hold large tensors near a safe fraction of 8GB VRAM, then run smaller kernels.
   - Expected label: `memory_pressure`.
   - Goal: test whether memory utilization and free-memory signals help explain slowdown.

3. Intermittent anomaly workload
   - Alternate healthy periods with compute-bound, memory-bound, or memory-pressure periods.
   - Expected labels: `healthy`, then bottleneck label, then `recovered`.
   - Goal: test start/stop behavior and avoid tracing after recovery.

4. Contention-style workload
   - Run a background GPU load while the foreground benchmark measures latency.
   - Expected label: `gpu_contention`.
   - Goal: simulate external interference or noisy co-location on a single local GPU.

Research-question focus:

- Use the three selected workloads as the first experimental scope for all five research questions.
- Treat the deferred workloads as later extensions only after the controller, cheap metrics, and tracing workflow work reliably.

Cheap metrics to collect continuously:

1. Timestamp and window ID.
2. Workload phase label: `healthy`, `compute_bound`, `memory_bound`, `mixed`, `memory_pressure`, `launch_overhead_or_small_kernel`, `gpu_contention`, or `recovered`.
3. GPU utilization percent.
4. GPU memory used, free, and total.
5. GPU memory utilization percent.
6. GPU temperature.
7. GPU power draw and power limit.
8. SM clock and memory clock.
9. PCIe transmit and receive throughput if available.
10. Per-process GPU memory usage if available.
11. Benchmark iteration latency or operation time.
12. Benchmark throughput, such as operations per second or tokens/requests later for vLLM.
13. Controller CPU utilization and memory usage.
14. Suspicion score for the current window.
15. Controller state: `idle`, `suspicious`, `tracing`, `stopping`, or `recovered`.

## Notes

- The RTX 4060 Ti 8GB should be treated as a development GPU only.
- Final publishable cross-GPU claims should use the planned cloud GPU set.
