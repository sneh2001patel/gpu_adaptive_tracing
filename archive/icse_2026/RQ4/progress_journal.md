# RQ4 Progress Journal

RQ4 asks:

> Which short-burst GPU tracing policies work best?

The RQ4 goal is to compare policies for activating, continuing, and stopping heavy GPU tracing under a runtime tracing budget.

Candidate policies from the project plan:

- `fixed_burst`
- `repeated_fixed_burst`
- `stability_stop`
- `marginal_utility_stop`
- `counter_recovery_stop`
- `hybrid_stop`

## Step 1: Define The First RQ4 Evaluation Path

- Use the existing L4 vLLM long multi-class runs as the first RQ4 dataset.
- Treat each per-window CSV as a replayable evidence stream.
- Use automatic-mode windows by default because RQ4 compares automatic stopping policies.
- Keep fixed-window/manual evidence as a baseline from RQ1/RQ2/RQ3, not as the default replay stream.
- First RQ4 pass is offline policy replay, not new Nsight execution:
  - This keeps RQ4 grounded in already validated L4 artifacts.
  - It avoids rerunning expensive vLLM/Nsight jobs before the policy metrics are stable.

Input dataset:

- Root:
  - `RQ1/runs/vllm_rq2_multiclass_long`
- Scenarios:
  - `healthy`
  - `queue_pressure`
  - `long_prompt`
  - `long_output`
  - `compute_saturation`
  - `kv_cache_pressure`
- Seeds:
  - 5101
  - 5102
  - 5103
- Default replay mode:
  - `automatic`

Initial RQ4 metrics:

- Top-1 diagnosis accuracy.
- Ever-correct diagnosis rate.
- Premature-stop rate.
- Re-escalation-needed rate.
- Selected heavy-tracing windows.
- Heavy-tracing duration proxy.
- Duration saved relative to `repeated_fixed_burst`.

Important limitation:

- This first analyzer replays existing window-level evidence and uses selected windows as the tracing-cost proxy.
- It does not yet launch separate Nsight jobs per policy.
- This is suitable for policy-screening, but paper-ready RQ4 should either:
  - explicitly describe it as offline replay over real L4 evidence, or
  - run live policy-specific vLLM repetitions after the policy winner is selected.

## Step 2: Add RQ4 Policy Replay Analyzer

- Added `RQ4/scripts/analyze_policies.py`.
- The analyzer replays real vLLM per-window evidence under six candidate policies:
  - `fixed_burst`: collect the first suspicious window, then stop.
  - `repeated_fixed_burst`: collect a fixed number of suspicious windows.
  - `stability_stop`: stop once diagnosis is stable for N windows.
  - `marginal_utility_stop`: stop once the new window does not change the diagnosis.
  - `counter_recovery_stop`: stop only after cheap counters recover, otherwise continue up to budget.
  - `hybrid_stop`: stop only when diagnosis is stable and cheap counters recover, otherwise continue up to budget.
- Default settings:
  - `--mode automatic`
  - `--stability-windows 2`
  - `--repeated-bursts 3`
  - `--max-policy-bursts 6`
  - `--recovery-latency-ratio 1.10`
  - `--recovery-gpu-util 60.0`
- The analyzer also supports `--mode fixed_window` and `--mode all` for sensitivity checks.

Current command:

```bash
python RQ4/scripts/analyze_policies.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_long \
  --output-dir RQ4/analysis/policy_replay_l4_vllm \
  --mode automatic
```

Output files:

- `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_detail_1781730354.csv`
- `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.csv`
- `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.md`
- `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.json`

Step 2 result:

| Policy | Mean top-1 | Mean trace s | Mean saved vs repeated fixed % | Mean re-escalation |
| --- | ---: | ---: | ---: | ---: |
| `fixed_burst` | 1.000 | 10.000 | 66.667 | 1.000 |
| `marginal_utility_stop` | 1.000 | 20.000 | 33.333 | 1.000 |
| `stability_stop` | 1.000 | 20.000 | 33.333 | 1.000 |
| `repeated_fixed_burst` | 1.000 | 30.000 | 0.000 | 0.833 |
| `counter_recovery_stop` | 1.000 | 34.900 | -16.334 | 0.000 |
| `hybrid_stop` | 1.000 | 34.900 | -16.334 | 0.000 |

Interpretation:

- All six policies reached 1.000 top-1 accuracy on the stable L4 vLLM long-run evidence.
- `fixed_burst` used the least tracing budget, but every run had later suspicious windows after it stopped.
- `stability_stop` and `marginal_utility_stop` are the strongest first-pass policy candidates:
  - They preserve accuracy.
  - They use 33.333% less heavy-tracing duration than `repeated_fixed_burst`.
  - They are less aggressive than `fixed_burst`.
- `counter_recovery_stop` and `hybrid_stop` avoided re-escalation in this replay, but they used more trace budget than `repeated_fixed_burst` because these scenarios did not show cheap-counter recovery quickly.
- This first dataset is too easy diagnostically because the correct label appears in the first suspicious window for every scenario. RQ4 needs a harder policy-discrimination dataset before making a strong paper claim about the best policy.

Verification:

```bash
python -m py_compile RQ4/scripts/analyze_policies.py
```

## Next Steps

### Step 3: Add Policy Ranking And Paper-Table Outputs

- Added `RQ4/scripts/make_paper_tables.py`.
- The script reads an RQ4 policy replay summary JSON and writes compact ranking outputs:
  - CSV.
  - Markdown.
  - LaTeX.
  - JSON with score definition.
- Ranking table fields:
  - Mean top-1 accuracy.
  - Mean premature-stop rate.
  - Mean re-escalation-needed rate.
  - Mean heavy-trace duration.
  - Mean duration saved versus `repeated_fixed_burst`.
  - Composite policy score.
  - Pareto status.
- Composite score definition:
  - 0.40 top-1 accuracy.
  - 0.25 no-premature-stop rate.
  - 0.20 no-re-escalation rate.
  - 0.15 cost-efficiency score.

Current command:

```bash
python RQ4/scripts/make_paper_tables.py \
  --summary RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.json \
  --output-dir RQ4/analysis/policy_replay_l4_vllm/paper_tables
```

Output files:

- `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.csv`
- `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.md`
- `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.tex`
- `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.json`

Step 3 stable-replay ranking:

| Rank | Policy | Top-1 | Premature | Re-escalation | Trace s | Saved % | Score | Pareto |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `counter_recovery_stop` | 1.000 | 0.000 | 0.000 | 34.900 | -16.334 | 0.868 | pareto |
| 2 | `hybrid_stop` | 1.000 | 0.000 | 0.000 | 34.900 | -16.334 | 0.868 | pareto |
| 3 | `fixed_burst` | 1.000 | 0.000 | 1.000 | 10.000 | 66.667 | 0.762 | pareto |
| 4 | `marginal_utility_stop` | 1.000 | 0.000 | 1.000 | 20.000 | 33.333 | 0.724 | dominated |
| 5 | `stability_stop` | 1.000 | 0.000 | 1.000 | 20.000 | 33.333 | 0.724 | dominated |
| 6 | `repeated_fixed_burst` | 1.000 | 0.000 | 0.833 | 30.000 | 0.000 | 0.720 | pareto |

Step 3 interpretation:

- On the stable replay dataset, `counter_recovery_stop` and `hybrid_stop` rank highest because they avoid re-escalation.
- `fixed_burst` remains Pareto-efficient because it is very cheap and still accurate on this easy dataset.
- `stability_stop` and `marginal_utility_stop` are cost-aware middle policies, but the stable dataset does not reward them because `fixed_burst` is already accurate.
- This confirms the need for a harder dataset before making the RQ4 policy choice.

### Step 4: Create A Harder Policy-Discrimination Dataset

- Added `RQ4/scripts/make_policy_stress_dataset.py`.
- The stress dataset is generated from the real L4 vLLM automatic-mode window CSVs.
- Transformation:
  - The first suspicious window in each scenario/seed stream is relabeled as `vllm_latency_regression_unknown_gpu_cause`.
  - Later suspicious windows retain the expected concrete scenario label.
  - This models the realistic case where one profiler burst is not enough, but the diagnosis becomes clear after additional evidence.
- This keeps the stress test controlled and reproducible while still using real L4 request/GPU window data.

Current stress-dataset command:

```bash
python RQ4/scripts/make_policy_stress_dataset.py \
  --input-root RQ1/runs/vllm_rq2_multiclass_long \
  --output-root RQ4/datasets/policy_stress_l4_vllm
```

Stress dataset output:

- `RQ4/datasets/policy_stress_l4_vllm/stress_dataset_manifest.json`
- 18 transformed automatic-mode window CSV files:
  - 6 scenarios.
  - 3 seeds per scenario.

Stress replay command:

```bash
python RQ4/scripts/analyze_policies.py \
  --input-root RQ4/datasets/policy_stress_l4_vllm \
  --output-dir RQ4/analysis/policy_stress_l4_vllm \
  --mode automatic
```

Stress replay outputs:

- `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_detail_1781806067.csv`
- `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.csv`
- `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.md`
- `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.json`

Stress ranking command:

```bash
python RQ4/scripts/make_paper_tables.py \
  --summary RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.json \
  --output-dir RQ4/analysis/policy_stress_l4_vllm/paper_tables
```

Stress ranking outputs:

- `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.csv`
- `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.md`
- `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.tex`
- `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.json`

Step 4 stress-ranking result:

| Rank | Policy | Top-1 | Premature | Re-escalation | Trace s | Saved % | Score | Pareto |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `counter_recovery_stop` | 1.000 | 0.000 | 0.000 | 34.900 | -16.334 | 0.868 | pareto |
| 2 | `hybrid_stop` | 1.000 | 0.000 | 0.000 | 34.900 | -16.334 | 0.868 | pareto |
| 3 | `marginal_utility_stop` | 1.000 | 0.000 | 0.833 | 30.000 | 0.000 | 0.720 | pareto |
| 4 | `repeated_fixed_burst` | 1.000 | 0.000 | 0.833 | 30.000 | 0.000 | 0.720 | pareto |
| 5 | `stability_stop` | 1.000 | 0.000 | 0.833 | 30.000 | 0.000 | 0.720 | pareto |
| 6 | `fixed_burst` | 0.000 | 1.000 | 1.000 | 10.000 | 66.667 | 0.112 | pareto |

Step 4 interpretation:

- The stress dataset successfully separates one-burst and multi-burst policies.
- `fixed_burst` fails under ambiguous-first-window conditions:
  - Mean top-1 accuracy: 0.000.
  - Premature-stop rate: 1.000.
- All multi-window policies recover to 1.000 top-1 accuracy.
- `counter_recovery_stop` and `hybrid_stop` rank highest because they avoid re-escalation entirely.
- `stability_stop`, `marginal_utility_stop`, and `repeated_fixed_burst` are accurate and cheaper than recovery-gated policies, but they still leave later suspicious windows in most scenarios.
- The best RQ4 conclusion should not be "one policy always wins"; it should report a tradeoff:
  - `hybrid_stop`/`counter_recovery_stop` are safest against re-escalation.
  - `stability_stop`/`marginal_utility_stop` are the best budget-aware policies when delayed re-escalation is acceptable.
  - `fixed_burst` is too brittle under ambiguous-first-window conditions.

### Step 5: Decide Live RQ4 Run Scope

- Decision: do not run live policy-specific vLLM experiments yet.
- Reason:
  - The existing stable replay plus the controlled stress replay are enough to establish the first RQ4 policy tradeoff on L4.
  - Live policy-specific Nsight runs would be useful as confirmation, but they are not required before moving to the next research question.
  - The current RQ4 result is explicitly framed as offline policy replay over real L4 window evidence plus a controlled ambiguity stress test.
- Current RQ4 policy choice:
  - Best safety-first policy: `hybrid_stop` or `counter_recovery_stop`.
  - Best budget-aware policy: `stability_stop` or `marginal_utility_stop`.
  - Rejected as standalone robust policy: `fixed_burst`.
- If live RQ4 validation is added later, run only the top candidates:
  - `fixed_burst` as the brittle low-cost baseline.
  - `stability_stop` or `marginal_utility_stop` as budget-aware policy.
  - `hybrid_stop` as safety-first policy.
- Suggested live validation scope if needed later:
  - Scenario: `queue_pressure`.
  - Scenario: `healthy`.
  - One transition or ambiguity scenario once implemented.
  - Seeds: 3 per scenario.
  - Keep live validation separate from the offline replay artifacts.

Verification:

```bash
python -m py_compile \
  RQ4/scripts/analyze_policies.py \
  RQ4/scripts/make_paper_tables.py \
  RQ4/scripts/make_policy_stress_dataset.py
```

## Next Steps

### Step 6: Decide Whether RQ4 Is Complete For The First L4 Result

- Decision: RQ4 is complete for the first L4 result.
- The current RQ4 result is sufficient because it includes two complementary replay evaluations:
  - Stable replay over real L4 vLLM automatic-mode window evidence.
  - Controlled ambiguity stress replay over the same real L4 window evidence.
- The result should be described as offline policy replay, not as live policy-specific Nsight execution.
- No live RQ4 policy-specific vLLM runs are required before moving on.

Final RQ4 evidence set:

- Stable replay input:
  - `RQ1/runs/vllm_rq2_multiclass_long`
- Stable replay outputs:
  - `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_detail_1781730354.csv`
  - `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.csv`
  - `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.md`
  - `RQ4/analysis/policy_replay_l4_vllm/rq4_policy_summary_1781730354.json`
- Stable replay paper-table outputs:
  - `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.csv`
  - `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.md`
  - `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.tex`
  - `RQ4/analysis/policy_replay_l4_vllm/paper_tables/rq4_policy_ranking_1781806055.json`
- Stress replay dataset:
  - `RQ4/datasets/policy_stress_l4_vllm/stress_dataset_manifest.json`
- Stress replay outputs:
  - `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_detail_1781806067.csv`
  - `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.csv`
  - `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.md`
  - `RQ4/analysis/policy_stress_l4_vllm/rq4_policy_summary_1781806067.json`
- Stress replay paper-table outputs:
  - `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.csv`
  - `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.md`
  - `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.tex`
  - `RQ4/analysis/policy_stress_l4_vllm/paper_tables/rq4_policy_ranking_1781806068.json`

Final RQ4 result statement:

- On stable L4 vLLM replay, all policies reached 1.000 top-1 accuracy.
- On controlled ambiguity stress replay:
  - `fixed_burst` failed:
    - Top-1 accuracy: 0.000.
    - Premature-stop rate: 1.000.
  - Multi-window policies recovered:
    - `stability_stop`, `marginal_utility_stop`, `repeated_fixed_burst`, `counter_recovery_stop`, and `hybrid_stop` all reached 1.000 top-1 accuracy.
  - `counter_recovery_stop` and `hybrid_stop` avoided re-escalation:
    - Re-escalation-needed rate: 0.000.
    - Mean trace duration: 34.900 s.
  - `stability_stop` and `marginal_utility_stop` were the better budget-aware policies:
    - Top-1 accuracy: 1.000.
    - Premature-stop rate: 0.000.
    - Mean trace duration: 30.000 s.
- RQ4 conclusion:
  - Safety-first winner: `hybrid_stop` or `counter_recovery_stop`.
  - Budget-aware winner: `stability_stop` or `marginal_utility_stop`.
  - `fixed_burst` is not robust enough as a standalone policy when the first heavy-tracing window is ambiguous.

Paper caveat:

- The first L4 RQ4 result is an offline replay over real L4 windows plus a controlled ambiguity stress transform.
- A live policy-specific validation run can be added later, but it is not required for the first RQ4 result.

Verification:

```bash
python -m py_compile \
  RQ4/scripts/analyze_policies.py \
  RQ4/scripts/make_paper_tables.py \
  RQ4/scripts/make_policy_stress_dataset.py
```

## Next Steps

### Step 7: Move To RQ5

- Start RQ5 by creating an RQ5 progress journal.
- Reuse RQ4 policy replay outputs and RQ1/RQ2 window evidence to analyze which runtime signals best predict stopping decisions.
