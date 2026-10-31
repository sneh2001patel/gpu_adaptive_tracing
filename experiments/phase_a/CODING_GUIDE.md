# How to fill in `second_coder_sheet.csv` — plain-English guide with worked examples

The two worked examples are real vLLM issues that are **not** among your 30. Their saved threads are in [examples/](examples/). [CODEBOOK.md](CODEBOOK.md) remains the authoritative list of allowed values; this guide explains what each column is for.

## What each column asks

Work left to right. Each column answers one question about the issue thread.

| Column | The question you are answering | Typical answer |
|---|---|---|
| `include` | Is this someone reporting that serving or inference is **slow, uses too much memory, or stalls**? | `yes` / `no` |
| `exclude_reason` | Only if `no`: why not? (It's just a how-to question, a feature idea, a tracker, a crash, …) | `usage_question` |
| `reporter_is_maintainer` | Did a vLLM/SGLang team member open the issue, or an outside user? | `no` |
| `symptom` | **What** is slow or bad? | `throughput` (tokens/s), `ttft` (time to first token), `itl_tpot` (time between tokens), `e2e_latency` (whole request), `memory_capacity`, `startup_time`, … |
| `baseline` | Slow **compared to what**? | `prev_version` (an older vLLM was faster), `other_config` (a different flag or model), `other_engine`, `expectation` (a paper or blog said it should be faster) |
| `multi_gpu` | Does the report use more than one GPU? | `yes` / `no` / `not_stated` |
| `evidence` | What did people **actually show** to investigate? List everything shown. | `benchmark_numbers`, `bisect` (comparing versions), `nsys`, `torch_profiler`, `code_reading`, … |
| `profiler_by` | If a profiler or trace appears: who ran it? | `reporter` / `maintainer` / `none` |
| `scope_unit` | If a profiler appears: what was its capture measured in? | `iterations` / `seconds` / `not_stated` (blank if no profiler) |
| `scope_value` | The stated amount, copied from the thread | `5 warmup + 5 iters` (blank if none) |
| `profiler_role` | Did the profiler evidence lead to the answer? | `decisive` / `supporting` / `present_unused` / `none` |
| `evidence_requested` | Did a responder ask the reporter for something? | `repro_script`, `version_info`, `profile`, `logs`, `none` |
| `cause_category` | **Why** was it slow, according to the thread? | Pick the closest category; `unknown` if nobody said |
| `cause_confirmed_by` | Who or what established that cause? | `fix_pr`, `maintainer_explanation`, `reporter_resolved`, `none` |
| `resolution` | How did the issue end? | `fixed_pr`, `expected_behavior`, `stale_unresolved` (bot closed it), `unclear`, … |
| `fix_ref` | PR number mentioned as the fix (add `merged` if you checked) | `#21194` |
| `repro_candidate` | Could we rerun this on **one L4 GPU** with a known cause and a before/after toggle? | `yes` / `maybe` / `no` |
| `repro_blocker` | If not `yes`: what stops it? | `multi_gpu`, `cause_unconfirmed`, `model_too_large_for_L4`, … |
| `confidence` | How sure are you of this row overall? | `high` / `medium` / `low` |
| `notes` | Why you made any judgement call | One or two sentences |
| `coder` | Your initials | `SP` |

**Two rules that matter most:**
- Code only what the thread says, not what you know about vLLM.
- When nothing fits exactly, choose the closest value, lower `confidence`, and explain in `notes`.

## Worked example 1: a report where nobody explained the cause

**Issue:** [vllm#30043](https://github.com/vllm-project/vllm/issues/30043), "big perf loss between 0.11.2 and 0.12.0 on rms_norm". Saved copy: [examples/vllm-project_vllm_30043.md](examples/vllm-project_vllm_30043.md).

**What the thread says:**
- The reporter says DeepSeek-OCR got slower after upgrading.
- A maintainer asks which model.
- Later the reporter narrows it down to the `RMSNorm` layer and posts a benchmark script: 10 warmup + 1,000 iterations of that layer alone. Mean time rises from 0.0199 ms (0.11.2) to 0.0755 ms (0.12.0).
- The issue is then closed as "completed" with no explanation and no fix linked.

| Column | Value | Why |
|---|---|---|
| `include` | `yes` | A measured slowdown in inference |
| `exclude_reason` | *(blank)* | Included |
| `reporter_is_maintainer` | `no` | An outside user opened it |
| `symptom` | `other` | The numbers are per-layer kernel time, not throughput or request latency. None of the listed symptoms fits exactly. |
| `baseline` | `prev_version` | 0.11.2 vs 0.12.0 |
| `multi_gpu` | `not_stated` | GPU count never mentioned |
| `evidence` | `per_step_microbenchmark;bisect` | A script timing one layer over iterations, plus comparing two versions |
| `profiler_by` | `none` | No profiler or trace tool was used; a timing script is not a profiler |
| `scope_unit` | *(blank)* | Only for profiler evidence |
| `scope_value` | *(blank)* | |
| `profiler_role` | `none` | |
| `evidence_requested` | `none` | The maintainer asked "which model?". That isn't any of the listed requests, so record it in notes. |
| `cause_category` | `unknown` | The thread locates *where* (RMSNorm) but never says *why* |
| `cause_confirmed_by` | `none` | |
| `resolution` | `unclear` | Closed as "completed" with no fix or explanation in the thread |
| `fix_ref` | *(blank)* | |
| `repro_candidate` | `maybe` | Single layer, versions known, easy to rerun; but there is no confirmed cause |
| `repro_blocker` | `cause_unconfirmed` | |
| `confidence` | `medium` | The `symptom` choice was a judgement call |
| `notes` | `Layer-level regression localised to RMSNorm via reporter's benchmark (0.0199→0.0755 ms); maintainer only asked for the model; closed completed without explanation or PR.` | |
| `coder` | `SP` | |

## Worked example 2: a maintainer explains the cause

**Issue:** [vllm#21029](https://github.com/vllm-project/vllm/issues/21029), "Why the support for Mamba2 in vLLM v1 appears to be less optimized than in v0". Saved copy: [examples/vllm-project_vllm_21029.md](examples/vllm-project_vllm_21029.md).

**What the thread says:**
- The reporter posts tokens/s: v0 gives 2209.8 and v1 gives 1104.7.
- A maintainer replies: "It's because we don't yet have CUDA graphs working for mamba in V1."
- Two days later the maintainer links PR #21194, which removes the need for eager mode.

| Column | Value | Why |
|---|---|---|
| `include` | `yes` | The title is phrased as a "why" question, but it reports a measured 2× slowdown. A **measured shortfall makes it a report, not a usage question.** |
| `exclude_reason` | *(blank)* | |
| `reporter_is_maintainer` | `no` | |
| `symptom` | `throughput` | Tokens per second |
| `baseline` | `other_config` | v0 vs v1 are two engines inside the same vLLM version, not two releases. `prev_version` would also be defensible, so note it. |
| `multi_gpu` | `not_stated` | |
| `evidence` | `benchmark_numbers` | Only throughput numbers were shown |
| `profiler_by` | `none` | |
| `scope_unit` / `scope_value` | *(blank)* | |
| `profiler_role` | `none` | The maintainer knew the cause without any trace |
| `evidence_requested` | `none` | |
| `cause_category` | `other` | "CUDA graphs not yet supported" is an execution-mode gap. It isn't clearly one of the listed categories, so use `other` and explain. |
| `cause_confirmed_by` | `maintainer_explanation` | The PR came later and the thread doesn't show it fixing the slowdown, so the explanation is the confirmation. |
| `resolution` | `expected_behavior` | Known limitation at the time; the PR was linked after closing |
| `fix_ref` | `#21194` | Mentioned in the thread; merge status not checked |
| `repro_candidate` | `maybe` | Cause and toggle (eager vs CUDA graphs) are clear; model size and GPU not stated |
| `repro_blocker` | `no_config` | Model and workload are missing |
| `confidence` | `medium` | `cause_category` and `baseline` were judgement calls |
| `notes` | `Mamba2 v1 2x slower than v0; maintainer: no CUDA graph support for mamba in V1 yet; PR #21194 linked after close. Cause category 'other' (execution mode); could argue cpu_overhead (launch overhead) but thread doesn't say so.` | |
| `coder` | `SP` | |

## Example 3: an excluded issue

This one is illustrative, not a real issue.

> "Does vLLM support FlashAttention on V100?" No numbers, no slowdown reported.

| `include` | `exclude_reason` | `confidence` | `notes` |
|---|---|---|---|
| `no` | `usage_question` | `high` | `Asks about support; no measured problem.` |

Leave every other column blank.

## Order to work in each row

1. Read the whole thread once without coding.
2. Decide `include`. If `no`, fill 4 cells and move on.
3. Fill `symptom`, `baseline` and `multi_gpu`: what is slow, compared to what, on what hardware.
4. Fill the evidence columns: what was shown, by whom, and whether it led to the answer.
5. Fill the cause and resolution columns: why, how that's known, how it ended.
6. Fill the reproduction screen, `confidence` and `notes`.
