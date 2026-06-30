# Adaptive GPU Tracing: Knowing When to Stop

GPU profiling tools (Nsight Systems, CUPTI, NVBit, etc.) expose rich kernel-level
evidence for diagnosing performance anomalies in GPU-heavy serving systems, but
they are typically invoked manually with a fixed profiling window that neither
adapts to evidence quality nor decides when enough evidence has been collected.

This repository implements and evaluates an **adaptive GPU tracing controller**
that manages heavy GPU profiling automatically using a two-tier evidence model:
cheap always-on signals (request latency, throughput, GPU utilization, GPU
memory utilization) run continuously, while short Nsight Systems kernel-timing
bursts are activated only when cheap evidence is insufficient to explain an
anomaly, and stopped automatically once the diagnosis has stabilized.

The study is organized into five research questions (RQ1-RQ5), each with its
own experiment scripts, raw run artifacts, analysis, and paper tables/figures:

| RQ | Question | Directory |
|----|----------|-----------|
| RQ1 | Does the adaptive controller save profiler time and diagnose correctly versus a fixed-window baseline? | [`RQ1/`](RQ1/) |
| RQ2 | How accurate is automatic GPU tracing compared with manual fixed-window profiling? | [`RQ2/`](RQ2/) |
| RQ3 | Does automatic GPU tracing introduce measurable overhead, and is it negligible? | [`RQ3/`](RQ3/) |
| RQ4 | Which short-burst stopping policy works best (Fixed Burst, Repeated Fixed Burst, Stability Stop, Marginal Utility Stop, Counter-Recovery Stop, Hybrid Stop)? | [`RQ4/`](RQ4/) |
| RQ5 | Which runtime signals are most useful for deciding when to stop heavy GPU tracing? | [`RQ5/`](RQ5/) |

The experiments target NVIDIA L4 and A100 GPUs running vLLM serving
`Qwen/Qwen2.5-7B-Instruct`, plus standalone CUDA/PyTorch microbenchmarks for
RQ1's controlled comparison.

## Repository Layout

```text
RQ1/ .. RQ5/        Experiment scripts, raw run outputs, and analysis per RQ
  scripts/            Python entry points (runners + analyzers + table/figure generators)
  runs/               Raw per-run artifacts (window CSVs, summaries, Nsight reports)
  analysis/           Aggregated results, paper tables, and (RQ1) draft figures
  datasets/           Derived/replay datasets (RQ4 stress dataset)
  progress_journal.md Running log of what was tried and why, per RQ
litterature_review/  Related-work source material (20-paper survey, gap analysis)
paper/                IEEE-format paper source (LaTeX), figures, and bibliography
project_overview.md   Project motivation, gap statement, and RQ design rationale
plan.md               Original experiment design plan (GPUs, phases, workloads)
REPRODUCE_ON_NEW_GPU.md  Step-by-step commands to rerun RQ1-RQ5 end-to-end on a new GPU
requirements.txt       Python deps for the controller/analysis environment
requirements-vllm.txt  Python deps for the separate vLLM serving environment
```

## Requirements

### Hardware and system tools

- An NVIDIA GPU with a recent driver (the reference runs used L4 and A100).
- [NVIDIA Nsight Systems CLI](https://developer.nvidia.com/nsight-systems) (`nsys`) on `PATH` or pointed to via `--nsys-path` — required for RQ1, RQ2, and the live-validation paths of RQ4/RQ5.
- [Git LFS](https://git-lfs.com/) — `*.sqlite` and `*.nsys-rep` profiler artifacts are tracked via LFS (see `.gitattributes`). Run `git lfs pull` after cloning if you need the raw profiler outputs.
- (Optional, paper only) A LaTeX toolchain (`pdflatex`, `bibtex`) to build `paper/main.pdf`.

### Python environments

Requires **Python 3.9-3.13** (the pinned `torch==2.5.1` in `requirements.txt`
does not publish wheels for 3.14+; `python3.11` or `python3.12` is a safe
choice). Use **two separate Python environments**, matching the project's
existing practice — vLLM pulls in a pinned torch/transformers stack that
conflicts with the controller/analysis environment's own torch pin:

```bash
# 1. Main/controller environment: runs the controller, microbenchmarks,
#    analysis, table/figure generation (RQ1-RQ5 scripts + paper figures).
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. vLLM serving environment: only needed for the vLLM-based experiments
#    (RQ1 vLLM smoke/Nsight runs, RQ2-RQ5 serving workloads).
python3.11 -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install -r requirements-vllm.txt
```

Verify the environments before running anything:

```bash
.venv/bin/python - <<'PY'
import torch, pynvml
print("torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.is_available())
pynvml.nvmlInit()
print("driver", pynvml.nvmlSystemGetDriverVersion())
PY

nsys --version

.venv-vllm/bin/python - <<'PY'
import vllm, torch
print("vllm", vllm.__version__, "torch", torch.__version__)
PY
```

`torch==2.5.1` in `requirements.txt` is pinned to the version validated
against the reference GPUs (CUDA 12.4). If that wheel doesn't match your
driver, install torch separately from the matching
[PyTorch index](https://pytorch.org/get-started/locally/) before installing
the rest of `requirements.txt`.

## Quick Start

A fast smoke test that only needs the main environment and exercises CUDA,
PyTorch, and NVML (no Nsight, no vLLM):

```bash
.venv/bin/python RQ1/scripts/run_microbenchmarks.py \
  --mode automatic \
  --workload all \
  --duration-seconds 6 \
  --window-seconds 2 \
  --output-dir RQ1/runs/smoke_local
```

## Running The Experiments

Each RQ directory's `progress_journal.md` documents what was tried and why;
[`RQ1/README.md`](RQ1/README.md) has the most detailed single-RQ run guide.
**[`REPRODUCE_ON_NEW_GPU.md`](REPRODUCE_ON_NEW_GPU.md) is the authoritative,
copy-pasteable, end-to-end guide** — it runs RQ1 through RQ5 in dependency
order on a fresh GPU and lists expected artifact counts at each step. The
summary below is a condensed entry point into that guide.

The RQs have a strict dependency order — later RQs reuse earlier RQs' raw
run outputs instead of re-running vLLM:

```text
RQ1 (controller runs) -> RQ2 (accuracy) -> RQ3 (overhead) -> RQ4 (policies) -> RQ5 (stop signals)
```

Set up shared variables once per shell session (adjust paths/tag for your host):

```bash
export MAIN_PY=.venv/bin/python
export VLLM_PY=.venv-vllm/bin/python
export NSYS=$(command -v nsys)
export MODEL=Qwen/Qwen2.5-7B-Instruct
export GPU_TAG=mygpu   # tags output directories, e.g. l4, a100, h100
```

### RQ1 — Controller vs. fixed-window baseline

Microbenchmark comparison (no vLLM needed):

```bash
for rep in 1 2 3 4 5; do
  $MAIN_PY RQ1/scripts/run_microbenchmarks.py \
    --mode compare --workload all \
    --duration-seconds 20 --window-seconds 5 \
    --enable-nsys-bursts --nsys-path "$NSYS" \
    --nsys-burst-seconds 2 --fixed-window-nsys-seconds 8 \
    --max-nsys-bursts-per-workload 1 --fixed-window-bursts-per-workload 1 \
    --stability-stop-windows 2 \
    --output-dir "RQ1/runs/rq1_${GPU_TAG}_compare_rep${rep}"
done

$MAIN_PY RQ1/scripts/analyze_repetitions.py \
  --input-root RQ1/runs \
  --pattern "rq1_${GPU_TAG}_compare_rep*/comparison_*.json" \
  --output-dir "RQ1/analysis/${GPU_TAG}_5rep_snapshot"

$MAIN_PY RQ1/scripts/make_paper_tables.py \
  --aggregate "$(ls -t RQ1/analysis/${GPU_TAG}_5rep_snapshot/aggregate_*.json | head -1)" \
  --output-dir "RQ1/analysis/${GPU_TAG}_5rep_snapshot/paper_tables"
```

vLLM `queue_pressure` Nsight comparison (needs `$VLLM_PY` and a running
vLLM server — see [`RQ1/README.md`](RQ1/README.md) for the full server
startup command and three-seed repetition loop). Full RQ1 commands,
including the vLLM path, are in [`REPRODUCE_ON_NEW_GPU.md` §1](REPRODUCE_ON_NEW_GPU.md#1-rq1-adaptive-tracing-saves-profiler-time).

### RQ2 — Diagnosis accuracy

Reuses RQ1 outputs; the core result is the six-scenario, three-seed vLLM
multiclass run (18 scenario/seed jobs) analyzed for diagnosis match rate:

```bash
$MAIN_PY RQ2/scripts/analyze_accuracy.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --run-pattern "*" \
  --output-dir "RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy"

$MAIN_PY RQ2/scripts/make_paper_tables.py \
  --report "$(ls -t RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy/rq2_accuracy_*.json | head -1)" \
  --output-dir "RQ2/analysis/vllm_multiclass_${GPU_TAG}_accuracy/paper_tables" \
  --min-match-rate 0.95 --max-ambiguous-rate 0.05
```

Full RQ2 commands (including the 18-job generation loop) are in
[`REPRODUCE_ON_NEW_GPU.md` §2](REPRODUCE_ON_NEW_GPU.md#2-rq2-diagnosis-accuracy).

### RQ3 — Overhead

Artifact-based overhead reuses RQ1/RQ2 outputs; a dedicated runtime-overhead
run compares `no_profiler` vs. `cheap_metrics_only` directly:

```bash
$MAIN_PY RQ3/scripts/run_vllm_runtime_overhead.py \
  --model "$MODEL" --scenario queue_pressure \
  --seeds 6201 6202 6203 --base-port 8071 \
  --vllm-python "$VLLM_PY" \
  --duration-seconds 30 --window-seconds 10 --request-timeout-seconds 240 \
  --mode-order randomized \
  --output-dir "RQ3/runs/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized"

$MAIN_PY RQ3/scripts/analyze_runtime_overhead.py \
  --summary "$(ls -t RQ3/runs/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized/runtime_overhead_summary_*.json | head -1)" \
  --output-dir "RQ3/analysis/vllm_runtime_overhead_${GPU_TAG}_queue_pressure_randomized"
```

Full RQ3 commands (artifact-based overhead + paper tables) are in
[`REPRODUCE_ON_NEW_GPU.md` §3](REPRODUCE_ON_NEW_GPU.md#3-rq3-overhead).

### RQ4 — Stopping-policy comparison

Offline replay over RQ2's vLLM windows, plus a controlled ambiguity-stress
dataset (first suspicious window relabeled "unknown") that separates
single-burst from multi-burst policies:

```bash
$MAIN_PY RQ4/scripts/make_policy_stress_dataset.py \
  --input-root "RQ1/runs/vllm_rq2_multiclass_${GPU_TAG}" \
  --output-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm"

$MAIN_PY RQ4/scripts/analyze_policies.py \
  --input-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm" \
  --output-dir "RQ4/analysis/policy_stress_${GPU_TAG}_vllm" \
  --mode automatic

$MAIN_PY RQ4/scripts/make_paper_tables.py \
  --summary "$(ls -t RQ4/analysis/policy_stress_${GPU_TAG}_vllm/rq4_policy_summary_*.json | head -1)" \
  --output-dir "RQ4/analysis/policy_stress_${GPU_TAG}_vllm/paper_tables"
```

An optional full live-validation path (108 real Nsight jobs: 6 scenarios x 3
seeds x 6 policies) is also available via `run_live_policy_validation.py` —
see [`REPRODUCE_ON_NEW_GPU.md` §4](REPRODUCE_ON_NEW_GPU.md#4-rq4-policy-comparison).

### RQ5 — Stop-signal analysis

Combines the RQ4 stress replay with a dedicated enriched real-run signal
dataset (18 scenario/seed jobs against a single long-lived vLLM server) to
rank candidate stopping signals:

```bash
$MAIN_PY RQ5/scripts/analyze_stop_signals.py \
  --input-root "RQ4/datasets/policy_stress_${GPU_TAG}_vllm" \
  --output-dir "RQ5/analysis/stop_signals_stress_${GPU_TAG}_vllm"

$MAIN_PY RQ5/scripts/make_paper_tables.py \
  --stable-summary "$(ls -t RQ5/analysis/stop_signals_enriched_real_${GPU_TAG}_vllm/rq5_signal_summary_*.json | head -1)" \
  --stress-summary "$(ls -t RQ5/analysis/stop_signals_stress_${GPU_TAG}_vllm/rq5_signal_summary_*.json | head -1)" \
  --output-dir "RQ5/analysis/paper_tables_enriched_real_${GPU_TAG}"
```

Full RQ5 commands (including starting the long-lived vLLM server for the
enriched real-run signal jobs) are in
[`REPRODUCE_ON_NEW_GPU.md` §5](REPRODUCE_ON_NEW_GPU.md#5-rq5-stop-signal-analysis).

### Sanity-checking a new GPU run

`REPRODUCE_ON_NEW_GPU.md` §6 has `py_compile` checks and expected
artifact-count checks (e.g. 18 RQ2 vLLM comparisons, 18 RQ4 stress window
files, 108 live RQ4 validation jobs) to confirm a full run completed
correctly before comparing results across GPUs.

## Building The Paper

The paper source lives in [`paper/`](paper/) (IEEE conference format,
`main.tex` -> `01_introduction.tex` ... `05_conclusion.tex`,
`references.bib`). It has its own self-contained venv (`paper/.venv`, not
tracked in git) for figure regeneration:

```bash
cd paper
python3 -m venv .venv          # skip if paper/.venv already exists
.venv/bin/pip install matplotlib
.venv/bin/python scripts/make_rq4_tradeoff_figure.py   # regenerates figures/rq4_tradeoff.pdf

pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Note: `paper/02_related_works.tex` (included by `main.tex`) is currently a
placeholder — populate it from `paper/related_works.tex` /
`paper/references.bib`, which already contain a drafted Related Work section
and bibliography sourced from `litterature_review/`.

## Background Reading

- [`project_overview.md`](project_overview.md) — project motivation, the
  research gap this work targets, and why the RQs are scoped the way they are.
- [`plan.md`](plan.md) — original experiment design plan (GPU tiers, phases, workloads).
- [`litterature_review/`](litterature_review/) — the 20-paper related-work
  survey and gap analysis that motivated this direction; drafted into
  `paper/related_works.tex` and `paper/references.bib` (not yet merged into
  `paper/02_related_works.tex`, see note above).
