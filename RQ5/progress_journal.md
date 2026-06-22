# RQ5 Progress Journal

RQ5 asks:

> Which runtime signals are most useful for deciding when to stop heavy GPU tracing?

RQ5 studies the stopping signals used by the controller. The goal is to identify which cheap runtime signals and diagnosis-evidence signals are useful for deciding that additional heavy GPU tracing is no longer worth its cost.

Candidate stopping signals from the project plan:

- Stable bottleneck class.
- Stable root-cause ranking.
- No diagnosis change after a new profiler burst.
- Request latency recovery.
- Queueing delay recovery.
- GPU utilization recovery.
- GPU memory utilization recovery.
- Kernel duration stability.

## Step 1: Start RQ5 From Existing RQ4/RQ1/RQ2 Artifacts

- Created `RQ5/progress_journal.md`.
- Reused the existing L4 vLLM automatic-mode window evidence:
  - `RQ1/runs/vllm_rq2_multiclass_long`
- Reused the RQ4 controlled ambiguity stress dataset:
  - `RQ4/datasets/policy_stress_l4_vllm`
- Reused the RQ4 policy conclusions:
  - `hybrid_stop` and `counter_recovery_stop` are safety-first.
  - `stability_stop` and `marginal_utility_stop` are budget-aware.
  - `fixed_burst` is brittle when the first heavy-tracing window is ambiguous.

First RQ5 framing:

- Treat every suspicious vLLM window as a possible stopping point.
- Label a stopping point as correct if its diagnosis label matches the expected scenario label.
- Label a stopping point as ambiguous if the diagnosis is unknown or empty.
- Score runtime signals by how well they identify correct stopping points and ambiguous stopping points.

Important limitation:

- This first RQ5 pass uses existing window CSVs, not new live instrumentation.
- Some recovery-oriented columns are sparse or zero-filled in the existing vLLM window outputs.
- Therefore, boolean recovery flags are useful for screening but should not be overinterpreted until richer queueing/latency-baseline fields are available.

## Step 2: Add Initial Stop-Signal Analyzer

- Added `RQ5/scripts/analyze_stop_signals.py`.
- The analyzer reads automatic-mode suspicious windows and computes signal rows for:
  - `diagnosis_stable_2`
  - `diagnosis_changed_from_previous`
  - `latency_recovered`
  - `gpu_util_recovered`
  - `memory_pressure_low`
  - `throughput_recovered`
  - `queue_pressure_low`
- It reports:
  - Precision, recall, and F1 for predicting correct stopping points.
  - Precision, recall, and F1 for predicting ambiguous stopping points.
  - Numeric correlations for latency, throughput, GPU utilization, memory usage, and queue-pressure proxy.

Stable replay command:

```bash
python RQ5/scripts/analyze_stop_signals.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_long \
  --output-dir RQ5/analysis/stop_signals_stable_l4_vllm
```

Stable replay outputs:

- `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_detail_1781806897.csv`
- `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781806897.csv`
- `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781806897.md`
- `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_numeric_signal_summary_1781806897.csv`
- `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781806897.json`

Stress replay command:

```bash
python RQ5/scripts/analyze_stop_signals.py \
  --input-root RQ4/datasets/policy_stress_l4_vllm \
  --output-dir RQ5/analysis/stop_signals_stress_l4_vllm
```

Stress replay outputs:

- `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_detail_1781806897.csv`
- `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781806897.csv`
- `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781806897.md`
- `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_numeric_signal_summary_1781806897.csv`
- `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781806897.json`

Stable replay signal ranking:

| Rank | Signal | Correct precision | Correct recall | Correct F1 |
| ---: | --- | ---: | ---: | ---: |
| 1 | `latency_recovered` | 1.000 | 1.000 | 1.000 |
| 2 | `queue_pressure_low` | 1.000 | 1.000 | 1.000 |
| 3 | `throughput_recovered` | 1.000 | 0.783 | 0.878 |
| 4 | `diagnosis_stable_2` | 1.000 | 0.739 | 0.850 |
| 5 | `diagnosis_changed_from_previous` | 0.000 | 0.000 | 0.000 |
| 6 | `gpu_util_recovered` | 0.000 | 0.000 | 0.000 |
| 7 | `memory_pressure_low` | 0.000 | 0.000 | 0.000 |

Stress replay signal ranking:

| Rank | Signal | Correct precision | Correct recall | Correct F1 | Ambiguous precision | Ambiguous recall | Ambiguous F1 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `latency_recovered` | 0.739 | 1.000 | 0.850 | 0.261 | 1.000 | 0.414 |
| 2 | `queue_pressure_low` | 0.739 | 1.000 | 0.850 | 0.261 | 1.000 | 0.414 |
| 3 | `throughput_recovered` | 0.778 | 0.824 | 0.800 | 0.222 | 0.667 | 0.333 |
| 4 | `diagnosis_stable_2` | 1.000 | 0.647 | 0.786 | 0.000 | 0.000 | 0.000 |
| 5 | `diagnosis_changed_from_previous` | 1.000 | 0.353 | 0.522 | 0.000 | 0.000 | 0.000 |
| 6 | `gpu_util_recovered` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 7 | `memory_pressure_low` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

Stress replay numeric-signal summary:

| Numeric signal | Correlation with correct stop | Mean when correct | Mean when not correct |
| --- | ---: | ---: | ---: |
| `gpu_util_percent_mean` | 0.967 | 98.084 | 94.325 |
| `request_throughput_rps` | 0.185 | 1.244 | 0.767 |
| `throughput_ratio_vs_baseline` | 0.170 | 0.865 | 0.633 |
| `latency_ratio_vs_baseline` | -0.065 | 0.117 | 0.167 |
| `gpu_memory_used_percent_mean` | -0.002 | 98.464 | 98.465 |
| `queue_pressure_proxy` | 0.000 | 0.000 | 0.000 |

Step 2 interpretation:

- Diagnosis-evidence signals are the most defensible first RQ5 stopping signals:
  - `diagnosis_stable_2` has perfect precision and useful recall on the stress replay.
  - `diagnosis_changed_from_previous` has perfect precision but low recall, making it useful as a conservative continuation signal rather than a stop signal.
- Cheap recovery flags need better instrumentation before they can be trusted as paper-level stopping signals:
  - `latency_recovered` and `queue_pressure_low` rank high, but this is partly because `latency_ratio_vs_baseline` and `queue_pressure_proxy` are sparse or zero in the existing outputs.
  - `gpu_util_recovered` and `memory_pressure_low` are not useful as binary recovery flags under the current thresholds because vLLM scenarios stay highly utilized.
- Numeric GPU utilization is surprisingly informative in the stress replay:
  - Correlation with correct stop: 0.967.
  - This likely reflects the controlled ambiguity transform and scenario dynamics, so it should be treated as a useful candidate signal, not as a final standalone rule.
- First RQ5 claim:
  - Diagnosis stability is the strongest robust stopping signal available in the current artifacts.
  - Throughput recovery and numeric GPU utilization are useful supporting signals.
  - Latency/queue recovery need richer non-sparse baselines before they can be paper-grade stopping signals.

Verification:

```bash
python -m py_compile RQ5/scripts/analyze_stop_signals.py
```

## Next Steps

### Step 3: Add RQ5 Paper Tables

- Added `RQ5/scripts/make_paper_tables.py`.
- The script combines the stable replay signal summary and the stress replay signal summary into compact paper-table outputs.
- It also writes a numeric-signal correlation table using the stress replay.
- Paper-ready signal criteria:
  - Precision floor across stable and stress replay at least 0.90.
  - Stress correct-stop F1 at least 0.70.
  - Stress ambiguous-stop F1 at most 0.10.
- These criteria intentionally penalize signals that also fire on ambiguous stopping points.

Current command:

```bash
python RQ5/scripts/make_paper_tables.py \
  --stable-summary RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781808022.json \
  --stress-summary RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781808022.json \
  --output-dir RQ5/analysis/paper_tables
```

Output files:

- `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.csv`
- `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.md`
- `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.tex`
- `RQ5/analysis/paper_tables/rq5_numeric_signal_table_1781808029.csv`
- `RQ5/analysis/paper_tables/rq5_numeric_signal_table_1781808029.md`
- `RQ5/analysis/paper_tables/rq5_signal_tables_1781808029.json`

Step 3 signal-ranking result:

| Rank | Signal | Stable F1 | Stress F1 | Stress ambiguous F1 | Precision floor | Score | Paper-ready |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `diagnosis_stable_2` | 0.850 | 0.786 | 0.000 | 1.000 | 0.851 | yes |
| 2 | `latency_recovered` | 1.000 | 0.850 | 0.414 | 0.739 | 0.777 | no |
| 3 | `queue_delay_recovered` | 1.000 | 0.850 | 0.414 | 0.739 | 0.777 | no |
| 4 | `queue_pressure_low` | 1.000 | 0.850 | 0.414 | 0.739 | 0.777 | no |
| 5 | `throughput_recovered` | 0.878 | 0.800 | 0.333 | 0.778 | 0.740 | no |
| 6 | `diagnosis_changed_from_previous` | 0.000 | 0.522 | 0.000 | 0.000 | 0.235 | no |
| 7 | `diagnosis_confident` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | no |
| 8 | `diagnosis_margin_clear` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | no |
| 9 | `gpu_util_recovered` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | no |
| 10 | `kernel_duration_stable` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | no |
| 11 | `memory_pressure_low` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | no |

Step 3 numeric-signal result:

| Numeric signal | Correlation with correct stop | Mean when correct | Mean when not correct |
| --- | ---: | ---: | ---: |
| `gpu_util_percent_mean` | 0.967 | 98.084 | 94.325 |
| `request_throughput_rps` | 0.185 | 1.244 | 0.767 |
| `throughput_ratio_vs_baseline` | 0.170 | 0.865 | 0.633 |
| `latency_ratio_vs_baseline` | -0.065 | 0.117 | 0.167 |
| `gpu_memory_used_percent_mean` | -0.002 | 98.464 | 98.465 |
| `queue_delay_proxy_p95_ms` | 0.000 | 0.000 | 0.000 |
| `queue_pressure_score` | 0.000 | 0.000 | 0.000 |
| `diagnosis_confidence` | 0.000 | 0.000 | 0.000 |
| `diagnosis_rank_margin` | 0.000 | 0.000 | 0.000 |
| `kernel_duration_cv` | 0.000 | 0.000 | 0.000 |
| `kernel_duration_stability_delta_percent` | 0.000 | 0.000 | 0.000 |

Step 3 interpretation:

- `diagnosis_stable_2` is the only paper-ready signal under the current criteria.
- Recovery-style signals rank high by F1 but fail paper-ready criteria because they also fire on ambiguous stress windows.
- Newly added future-instrumentation fields appear in the table but score 0.000 on existing artifacts because the historical CSVs do not contain those fields.
- This supports the Step 4 decision that more instrumentation is needed for a stronger RQ5 result.

### Step 4: Decide Whether RQ5 Needs More Instrumentation

- Decision: existing RQ1/RQ2 window fields are not enough for a strong first L4 RQ5 result.
- Reason:
  - Existing `latency_ratio_vs_baseline` and `queue_pressure_proxy` fields are sparse or zero-filled in many vLLM windows.
  - Existing windows do not include explicit queue-delay estimates.
  - Existing windows do not include recovery streak counters.
  - Existing windows do not include diagnosis confidence or rank margin.
  - Existing windows do not include kernel-duration stability fields from Nsight summaries.
- Implemented richer future vLLM window instrumentation in `RQ1/scripts/run_vllm_smoke.py`.
- Added explicit queue-delay proxy fields:
  - `queue_delay_proxy_mean_ms`
  - `queue_delay_proxy_p95_ms`
  - `queue_pressure_score`
- Added nonzero baseline and ratio fields:
  - `latency_baseline_mean_ms`
  - `latency_baseline_p50_ms`
  - `latency_ratio_vs_baseline`
  - `latency_ratio_vs_initial_window`
  - `request_throughput_baseline_rps`
  - `request_throughput_ratio_vs_baseline`
- Added recovery streak counters:
  - `latency_recovery_streak`
  - `gpu_util_recovery_streak`
  - `throughput_recovery_streak`
  - `queue_delay_recovery_streak`
- Added diagnosis confidence and margin fields:
  - `diagnosis_top_candidate`
  - `diagnosis_runner_up`
  - `diagnosis_confidence`
  - `diagnosis_rank_margin`
  - `diagnosis_stability_streak`
  - `diagnosis_changed_from_previous`
- Added kernel-duration stability placeholder fields for future Nsight-enriched windows:
  - `kernel_duration_mean_ns`
  - `kernel_duration_cv`
  - `kernel_duration_stability_delta_percent`
  - `kernel_duration_stable`
  - `kernel_summary_source`
- Added new vLLM smoke CLI thresholds:
  - `--queue-delay-pressure-ms`
  - `--queue-delay-recovery-ms`
  - `--recovery-latency-ratio`
  - `--recovery-gpu-util`
  - `--throughput-recovery-ratio`
- Updated `RQ5/scripts/analyze_stop_signals.py` so it can consume these richer future fields while remaining backward-compatible with existing historical CSVs.
- Newly supported RQ5 analyzer signals:
  - `diagnosis_confident`
  - `diagnosis_margin_clear`
  - `queue_delay_recovered`
  - `kernel_duration_stable`
- Newly supported numeric fields:
  - `queue_delay_proxy_p95_ms`
  - `queue_pressure_score`
  - `diagnosis_confidence`
  - `diagnosis_rank_margin`
  - `kernel_duration_cv`
  - `kernel_duration_stability_delta_percent`

Schema check:

```bash
python - <<'PY'
import argparse, time, sys
sys.path.insert(0, 'RQ1/scripts')
import run_vllm_smoke as s

now = time.time()
records = [
    s.RequestRecord(i, 'queue_pressure', 'vllm_queue_pressure', now, now+0.2+i*0.05, 200+i*50, 1, 200, '', 100, 96, 30, 130)
    for i in range(4)
]
...
PY
```

Schema-check result:

```text
{
  'queue_delay_proxy_p95_ms': 44.99999999999999,
  'latency_baseline_p50_ms': 250,
  'latency_ratio_vs_initial_window': 1.0,
  'request_throughput_ratio_vs_baseline': 1.0,
  'diagnosis_confidence': 0.55,
  'diagnosis_rank_margin': 0.25,
  'latency_recovery_streak': 1,
  'kernel_duration_stable': ''
}
```

Verification:

```bash
python -m py_compile \
  RQ1/scripts/run_vllm_smoke.py \
  RQ5/scripts/analyze_stop_signals.py \
  RQ5/scripts/make_paper_tables.py
```

## Real Enriched RQ5 Runs

The Step 5 smoke check confirmed that the enriched schema worked, but it was not enough to support the enriched-signal part of RQ5 by itself. A real enriched RQ5 run set was added after that check.

### Step 7: Run Real Enriched L4 vLLM Signal Runs

- Ran the enriched vLLM window schema across all six concrete vLLM scenarios.
- Model:
  - `Qwen/Qwen2.5-7B-Instruct`
- GPU:
  - NVIDIA L4 24GB.
- Scenario set:
  - `healthy`
  - `queue_pressure`
  - `long_prompt`
  - `long_output`
  - `compute_saturation`
  - `kv_cache_pressure`
- Seeds:
  - 9201
  - 9202
  - 9203
- Duration:
  - 60 s per scenario/seed.
- Window size:
  - 10 s.
- Output root:
  - `RQ5/runs/enriched_real_l4_vllm`
- Server log:
  - `RQ5/runs/enriched_real_l4_vllm/server/vllm_server.log`

Run pattern:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --endpoint http://127.0.0.1:8102/v1/completions \
  --scenario <scenario> \
  --duration-seconds 60 \
  --window-seconds 10 \
  --request-timeout-seconds 240 \
  --seed <seed> \
  --output-dir RQ5/runs/enriched_real_l4_vllm/<scenario>_seed<seed>/automatic/smoke
```

Completed 18 real enriched scenario/seed runs:

- 6 scenarios x 3 seeds.
- Every run wrote enriched request, window, and summary files.
- Example window outputs:
  - `RQ5/runs/enriched_real_l4_vllm/healthy_seed9201/automatic/smoke/healthy_windows_1781808838.csv`
  - `RQ5/runs/enriched_real_l4_vllm/queue_pressure_seed9201/automatic/smoke/queue_pressure_windows_1781808903.csv`
  - `RQ5/runs/enriched_real_l4_vllm/long_prompt_seed9201/automatic/smoke/long_prompt_windows_1781808971.csv`
  - `RQ5/runs/enriched_real_l4_vllm/long_output_seed9201/automatic/smoke/long_output_windows_1781809034.csv`
  - `RQ5/runs/enriched_real_l4_vllm/compute_saturation_seed9201/automatic/smoke/compute_saturation_windows_1781809102.csv`
  - `RQ5/runs/enriched_real_l4_vllm/kv_cache_pressure_seed9201/automatic/smoke/kv_cache_pressure_windows_1781809182.csv`

Analyzed the real enriched run set:

```bash
python RQ5/scripts/analyze_stop_signals.py \
  --input-root RQ5/runs/enriched_real_l4_vllm \
  --output-dir RQ5/analysis/stop_signals_enriched_real_l4_vllm
```

Real enriched analysis outputs:

- `RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_detail_1781810012.csv`
- `RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_summary_1781810012.csv`
- `RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_summary_1781810012.md`
- `RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_numeric_signal_summary_1781810012.csv`
- `RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_summary_1781810012.json`

Real enriched signal ranking:

| Rank | Signal | Correct precision | Correct recall | Correct F1 |
| ---: | --- | ---: | ---: | ---: |
| 1 | `latency_recovered` | 1.000 | 1.000 | 1.000 |
| 2 | `throughput_recovered` | 1.000 | 0.884 | 0.938 |
| 3 | `diagnosis_stable_2` | 1.000 | 0.860 | 0.925 |
| 4 | `diagnosis_margin_clear` | 1.000 | 0.744 | 0.853 |
| 5 | `queue_delay_recovered` | 1.000 | 0.659 | 0.794 |
| 6 | `diagnosis_confident` | 1.000 | 0.465 | 0.635 |
| 7 | `queue_pressure_low` | 1.000 | 0.434 | 0.605 |

Generated updated paper tables using real enriched results as the stable input and the ambiguity stress replay as the stress input:

```bash
python RQ5/scripts/make_paper_tables.py \
  --stable-summary RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_summary_1781810012.json \
  --stress-summary RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781808022.json \
  --output-dir RQ5/analysis/paper_tables_enriched_real
```

Updated real-enriched paper-table outputs:

- `RQ5/analysis/paper_tables_enriched_real/rq5_signal_ranking_1781810018.csv`
- `RQ5/analysis/paper_tables_enriched_real/rq5_signal_ranking_1781810018.md`
- `RQ5/analysis/paper_tables_enriched_real/rq5_signal_ranking_1781810018.tex`
- `RQ5/analysis/paper_tables_enriched_real/rq5_numeric_signal_table_1781810018.csv`
- `RQ5/analysis/paper_tables_enriched_real/rq5_numeric_signal_table_1781810018.md`
- `RQ5/analysis/paper_tables_enriched_real/rq5_signal_tables_1781810018.json`

Updated real-enriched paper ranking:

| Rank | Signal | Real enriched F1 | Stress F1 | Stress ambiguous F1 | Precision floor | Paper-ready |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `diagnosis_stable_2` | 0.925 | 0.786 | 0.000 | 1.000 | yes |
| 2 | `latency_recovered` | 1.000 | 0.850 | 0.414 | 0.739 | no |
| 3 | `throughput_recovered` | 0.938 | 0.800 | 0.333 | 0.778 | no |
| 4 | `queue_delay_recovered` | 0.794 | 0.850 | 0.414 | 0.739 | no |
| 5 | `queue_pressure_low` | 0.605 | 0.850 | 0.414 | 0.739 | no |
| 6 | `diagnosis_margin_clear` | 0.853 | 0.000 | 0.000 | 0.000 | no |

Step 7 interpretation:

- The real enriched runs address the smoke-only limitation.
- `diagnosis_stable_2` remains the only signal that passes the combined paper-ready criteria.
- `latency_recovered` and `throughput_recovered` look strong on real enriched runs, but they still fail the ambiguity stress criterion because they can fire on ambiguous first-window cases.
- `diagnosis_margin_clear` is promising on real enriched runs, but it does not exist in the historical stress replay, so it cannot yet be promoted to the main paper-ready signal.

### Step 8: Updated RQ5 Completion Decision

- RQ5 is complete for the first L4 result with the real enriched run set included.
- Final paper-ready stopping signal:
  - `diagnosis_stable_2`
- Supporting signals from real enriched runs:
  - `latency_recovered`
  - `throughput_recovered`
  - `diagnosis_margin_clear`
  - `queue_delay_recovered`
- Final paper caveat:
  - Recovery and confidence/margin signals are now instrumented and validated on real enriched L4 runs.
  - Only diagnosis stability currently survives both real enriched runs and the ambiguity stress replay.

Verification:

```bash
python -m py_compile \
  RQ1/scripts/run_vllm_smoke.py \
  RQ5/scripts/analyze_stop_signals.py \
  RQ5/scripts/make_paper_tables.py
```

Final GPU/server state:

- Temporary vLLM server was stopped.
- `nvidia-smi` showed no active GPU processes after the run.

## Next Steps

### Step 5: Run A Fresh RQ5-Instrumented vLLM Smoke Check

- Ran a fresh enriched vLLM smoke check using `Qwen/Qwen2.5-7B-Instruct` on the L4.
- Kept the run separate from prior RQ1/RQ2/RQ4 artifacts:
  - `RQ5/runs/enriched_smoke_check`
- Started a temporary vLLM server:
  - Host: `127.0.0.1`
  - Port: `8101`
  - Model: `Qwen/Qwen2.5-7B-Instruct`
  - Server log:
    - `RQ5/runs/enriched_smoke_check/server/vllm_server.log`
- Ran the low-pressure scenario:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --endpoint http://127.0.0.1:8101/v1/completions \
  --scenario healthy \
  --duration-seconds 20 \
  --window-seconds 5 \
  --request-timeout-seconds 180 \
  --seed 9101 \
  --output-dir RQ5/runs/enriched_smoke_check/automatic/smoke
```

- Healthy outputs:
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/healthy_requests_1781808526.csv`
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/healthy_windows_1781808526.csv`
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/vllm_smoke_summary_1781808526.json`
- Ran the loaded serving scenario:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --endpoint http://127.0.0.1:8101/v1/completions \
  --scenario queue_pressure \
  --duration-seconds 20 \
  --window-seconds 5 \
  --request-timeout-seconds 180 \
  --seed 9102 \
  --output-dir RQ5/runs/enriched_smoke_check/automatic/smoke
```

- Queue-pressure outputs:
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/queue_pressure_requests_1781808553.csv`
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/queue_pressure_windows_1781808553.csv`
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/vllm_smoke_summary_1781808553.json`
- Confirmed the enriched real vLLM window schema includes:
  - `request_throughput_baseline_rps`
  - `request_throughput_ratio_vs_baseline`
  - `queue_delay_proxy_mean_ms`
  - `queue_delay_proxy_p95_ms`
  - `queue_pressure_score`
  - `latency_baseline_mean_ms`
  - `latency_baseline_p50_ms`
  - `latency_ratio_vs_initial_window`
  - `diagnosis_stability_streak`
  - `diagnosis_top_candidate`
  - `diagnosis_runner_up`
  - `diagnosis_confidence`
  - `diagnosis_rank_margin`
  - `latency_recovery_streak`
  - `gpu_util_recovery_streak`
  - `throughput_recovery_streak`
  - `queue_delay_recovery_streak`
  - Kernel-duration stability placeholder fields.
- Example populated enriched fields from the real smoke CSV:

```text
queue_delay_proxy_p95_ms: 0.0
latency_baseline_p50_ms: 4297.080755233765
latency_ratio_vs_initial_window: 1.0
request_throughput_ratio_vs_baseline: 1.0
diagnosis_confidence: 0.55
diagnosis_rank_margin: 0.22206896551724142
latency_recovery_streak: 1
queue_delay_recovery_streak: 1
```

- Ran RQ5 signal analysis on the fresh enriched smoke output:

```bash
python RQ5/scripts/analyze_stop_signals.py \
  --input-root RQ5/runs/enriched_smoke_check \
  --output-dir RQ5/analysis/stop_signals_enriched_smoke_check
```

- Enriched smoke analysis outputs:
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_signal_detail_1781808579.csv`
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_signal_summary_1781808579.csv`
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_signal_summary_1781808579.md`
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_numeric_signal_summary_1781808579.csv`
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_signal_summary_1781808579.json`

Enriched smoke signal ranking:

| Rank | Signal | Correct precision | Correct recall | Correct F1 |
| ---: | --- | ---: | ---: | ---: |
| 1 | `diagnosis_margin_clear` | 1.000 | 1.000 | 1.000 |
| 2 | `latency_recovered` | 1.000 | 1.000 | 1.000 |
| 3 | `diagnosis_stable_2` | 1.000 | 0.800 | 0.889 |
| 4 | `queue_delay_recovered` | 1.000 | 0.800 | 0.889 |
| 5 | `queue_pressure_low` | 1.000 | 0.700 | 0.824 |
| 6 | `throughput_recovered` | 1.000 | 0.700 | 0.824 |

Step 5 interpretation:

- The enriched schema is now present in real vLLM output, not only a synthetic check.
- The RQ5 analyzer consumes the enriched output successfully.
- The fresh smoke check is intentionally short and should be used as an instrumentation validation, not as a replacement for the stable/stress paper tables.
- `diagnosis_stable_2` remains consistent on the enriched smoke output.
- `diagnosis_margin_clear` now appears as a promising future signal because the enriched schema provides diagnosis margin values.
- Recovery signals are now measurable, but need longer fresh runs before they should replace the current paper-ready diagnosis-stability claim.

### Step 6: Decide RQ5 Completion Scope

- Decision: RQ5 is complete for the first L4 result.
- Completion scope:
  - Paper-ready current signal: `diagnosis_stable_2`.
  - Supporting candidate signals: `throughput_recovered`, numeric `gpu_util_percent_mean`, and enriched `diagnosis_margin_clear`.
  - Recovery-signal instrumentation has been added for future stronger runs.
- The first L4 RQ5 result should be framed as:
  - Existing L4 artifacts support diagnosis stability as the robust stopping signal.
  - Recovery-style signals need enriched instrumentation and longer fresh runs before they become paper-grade.
  - The enriched smoke check confirms the new instrumentation is available for future RQ5 refinement.
- No additional RQ5 run is required before moving on.

Final RQ5 evidence set:

- Stable signal analysis:
  - `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781808022.json`
  - `RQ5/analysis/stop_signals_stable_l4_vllm/rq5_signal_summary_1781808022.md`
- Stress signal analysis:
  - `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781808022.json`
  - `RQ5/analysis/stop_signals_stress_l4_vllm/rq5_signal_summary_1781808022.md`
- RQ5 paper tables:
  - `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.csv`
  - `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.md`
  - `RQ5/analysis/paper_tables/rq5_signal_ranking_1781808029.tex`
  - `RQ5/analysis/paper_tables/rq5_numeric_signal_table_1781808029.csv`
  - `RQ5/analysis/paper_tables/rq5_numeric_signal_table_1781808029.md`
  - `RQ5/analysis/paper_tables/rq5_signal_tables_1781808029.json`
- Enriched smoke instrumentation check:
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/healthy_windows_1781808526.csv`
  - `RQ5/runs/enriched_smoke_check/automatic/smoke/queue_pressure_windows_1781808553.csv`
  - `RQ5/analysis/stop_signals_enriched_smoke_check/rq5_signal_summary_1781808579.md`

Final RQ5 result statement:

- `diagnosis_stable_2` is the only signal that passes the current paper-ready criteria across stable and stress replay:
  - Stable correct-stop F1: 0.850.
  - Stress correct-stop F1: 0.786.
  - Stress ambiguous-stop F1: 0.000.
  - Precision floor: 1.000.
- Recovery-style signals are promising but not yet paper-ready:
  - They fire on ambiguous stress windows in the current historical artifacts.
  - Future enriched runs can evaluate them more fairly because queue delay, throughput ratio, recovery streaks, and diagnosis margins are now logged.

Verification:

```bash
python -m py_compile \
  RQ1/scripts/run_vllm_smoke.py \
  RQ5/scripts/analyze_stop_signals.py \
  RQ5/scripts/make_paper_tables.py
```
