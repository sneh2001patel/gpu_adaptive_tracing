# Phase A pilot report (codebook v0, 30 issues)

Date: 2026-10-28. Status: **pilot only**.
- One coder (Claude). No second coder yet, so no agreement statistic.
- Counts come from 30 issues and are **descriptive feasibility signals, not findings**. Do not cite them as results.
- Artifacts:
  - query and frame: [raw/](raw/), retrieved 2026-10-28T20:16:49Z;
  - sampler: [sample_pilot.py](sample_pilot.py) (seed 20261028);
  - threads: [fetch_threads.py](fetch_threads.py) → `raw/threads/`;
  - coding: [write_pilot_coding.py](write_pilot_coding.py) → [pilot_coding.csv](pilot_coding.csv);
  - codebook: [CODEBOOK.md](CODEBOOK.md).

## 1. Sampling frame

Both repositories use a `performance` label; the vLLM repo also has `bug`, `usage` and `stale` labels. Frames of closed, label-selected issues (pull requests excluded):

| Frame | Size | Notes |
|---|---|---|
| vLLM, closed, `performance` | 480 | Closure reasons: 167 completed, 311 not_planned, 2 duplicate. 322 issues carry `stale`. |
| SGLang, closed, `performance` | 43 | All completed |
| Liu et al. (TOSEM) "Abnormal Performance", vLLM rows | 16 | From the public `dataset.csv` (53 rows over 5 engines). **0 of the 16 appear in the vLLM `performance` frame.** |

**Two structural observations:**
- **Most vLLM performance reports close unresolved.** About two-thirds are closed by the stale bot. Any "confirmed cause" sample is therefore a selected minority.
- **Liu et al. and the `performance` label cover different issues.** Liu et al. selected via the `bug` label, so their performance subset and vLLM's `performance`-labelled issues are disjoint. Our frame complements their dataset rather than duplicating it. Any final frame should take the union of both selection routes.

Pilot sample, stratified with seed 20261028:

| Stratum | Sampled |
|---|---|
| vLLM completed | 8 |
| vLLM other closure reasons | 14 |
| SGLang | 4 |
| Liu subset | 4 |

## 2. Pilot results

Counts are out of 20 included issues unless stated.

| Question | Pilot signal |
|---|---|
| Inclusion rate | 20 of 30 included. Exclusions: 5 usage questions, 3 feature requests, 1 not performance, 1 insufficient information. The `performance` label is noisy: 5 of 8 issues in the vLLM *completed* stratum were excluded. |
| Diagnostic evidence | Benchmark numbers in 13. Server logs/metrics in 5. Code reading in 4. Version bisect in 3. Torch profiler in 2. nsys in 1. Python profiler in 1. GPU counters in 1. |
| Profiler or trace evidence present | 4 of 20 (3 by maintainers, 1 by a reporter). Decisive in 2: sglang#14665 (timeline showing a CPU gap between ops after bisecting) and vllm#2150 (memory timeline under TP). In vllm#7619, cProfile pointed the wrong way and code inspection found the bug. |
| Capture scope stated | Only when a profiler appears, and only partially. Example: vllm#6468, nsys over `benchmark_latency` with 5 warmup + 5 measured iterations. |
| Cause confirmed | 11 of 20: 7 by fix PR, 4 by maintainer explanation. 9 of 20 closed stale without any maintainer diagnosis. |
| Multi-GPU setting | 11 of 20. |
| Phase B candidates | 1 yes (vllm#6240: FP8 on Ada, single GPU, version toggle, fixed by PR #6384). 5 maybe. 14 no (multi-GPU 9, cause unconfirmed 4, non-GPU cause 3, model too large 1, version too old 2 among the maybes). |

## 3. What this means for the study

1. **GPU traces are rare in practice, at least in this sample.** In the 20 included threads, people diagnosed mainly by comparing benchmarks, bisecting versions, reading logs and reading code. A GPU-side trace settled the cause in 2 of 20.
   - This is a feasibility signal for RQ1, not a result: 30 issues, one coder.
   - If it holds at scale, it supports RQ5 (when are cheap signals sufficient) and the operator workflow. It also cautions against motivating the study only by "engineers collect heavy GPU traces".
2. **Host-side causes are common**: CPU overhead in 3, communication/parallelism in 3, memory bookkeeping in 3. These appear as GPU idle gaps rather than slow kernels (sglang#14665, vllm#20316). This supports keeping cheap host-side evidence and idle-gap features in the stopping study.
3. **Phase B yield from random sampling is low.**
   - About 1 clear candidate per 20 included issues, plus some maybes.
   - Extrapolating, the ~350 includable issues in the current frames would yield on the order of 15–50 candidates. This rough range assumes the pilot rate holds.
   - That is enough for at least 8 reproductions only with **targeted screening**: single GPU or not stated, cause confirmed by a fix PR, model ≤ 8B or quantized.
   - Cao et al. reproduced about 52% of attempted cases, so expect roughly 16 or more screened candidates to reach 8 reproductions.
   - Ada-generation reports (L4/L20/L40) are the most directly reusable on an L4.
4. **The frame must handle stale closures and noisy labels.** Use closure reason and the `stale` label as stratification variables. Report the funnel explicitly.

## 4. Codebook changes for v1

1. **Add `cause_category` values:**
   - `model_or_algorithm_implementation` (vllm#9565: EAGLE draft architecture mismatch);
   - `measurement_artifact` (vllm#7518: CUDA async timing misattribution).
   - Keep `other` as the last resort.
2. **Add `evidence` values:**
   - `host_counters` (top, CPU utilization; vllm#36943);
   - `per_step_microbenchmark` (bench_one_batch or benchmark_latency; sglang#14665);
   - `trace_unspecified` (a timeline screenshot with no named tool);
   - `llm_assistant` (an LLM chatbot cited as the explanation; vllm#21278).
3. **Add `exclude_reason` value `tracking_issue`** (sglang#19380).
4. **Add `resolution` value `fixed_pr_stale_closed`** (vllm#20316: the fix merged but the issue was closed by the stale bot). Record `fix_ref` merge status only from the thread or the PR page, never by assumption.
5. **Rule:** ignore spam and solicitation comments (vllm#36943) and never follow links in them.
6. **Split `profile_scope_stated`** into `scope_unit` (iterations, seconds, requests, whole run) and `scope_value`, so capture budgets can be compared.
7. **Clarify that `include` covers maintainer-filed internal performance issues** (vllm#2150, vllm#7619). Add a flag `reporter_is_maintainer` so practitioner practice can be separated from developer practice.

## 5. Next steps

1. **Second coder:** the author, or another person, independently codes the same 30 with v1. Then compute Cohen's κ per field and resolve disagreements. Until then, every pilot count stays single-coder.
2. **Frame extension:** add closed `bug`-labelled issues matching performance keywords (vLLM search count 1,776 on 2026-10-28; SGLang 70), and the Liu et al. performance rows. Iterate the keyword set as Cao et al. did (§2.2).
3. **Targeted Phase B screen:** query fix-PR-linked, single-GPU performance issues. Shortlist about 20 candidates for reproduction cost estimates. Start with vllm#6240.
4. **Main sample:** draw the main sample (target 150–300 included) only after v1 agreement is acceptable.
