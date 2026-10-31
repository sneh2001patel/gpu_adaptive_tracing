# Case screen: reproducible vLLM slowdowns (proposal §4.1)

Date: 2026-10-28. Status: first screening round, from GitHub threads and fix PRs only. **Nothing has been reproduced yet.**

## Method

1. **Search frame:** [search_candidates.py](search_candidates.py).
   - Five GitHub searches over closed `vllm-project/vllm` issues that have a linked PR: the `performance` label, plus "slow", "regression", "throughput" and "latency" in the title.
   - Kept only issues that GitHub lists as closed by a **merged** PR (`closedByPullRequestsReferences`).
   - Result: 81 issues ([raw/candidates.jsonl](raw/candidates.jsonl); retrieval time in [raw/retrieved_at.txt](raw/retrieved_at.txt)).
   - This misses fixes linked only in comments, so it is a reproducible frame, not a complete one.
2. **Title screen:** 60 excluded, for example benchmark tooling, functional bugs, multi-GPU, non-NVIDIA or unavailable GPUs, CPU backend, or startup-only effects.
3. **Thread screen:** 21 threads and their fix PRs fetched ([fetch_cases.py](fetch_cases.py), [raw/threads/](raw/threads/)) and read in full.
4. **Toggle versions:** for each fix, the last release before it and the first release containing it ([fix_releases.py](fix_releases.py)).

Every decision and its reason is in [screening.csv](screening.csv), written by [write_screening.py](write_screening.py).

**Acceptance criteria for a case:**
- a confirmed cause;
- a toggle: a fix release or a configuration or workload switch;
- a single-GPU setting that fits an L4 (24 GB, Ada SM89), or can be scaled down to one;
- enough workload detail to rerun it;
- a sustained effect that a tracing episode can observe.

**L4 host constraints**, from the [RQ1 journal](../../RQ1/progress_journal.md) step 12:
- the driver runs CUDA 12.8 builds (vLLM 0.10.2, torch 2.8.0+cu128);
- CUDA 13-era vLLM failed against this driver;
- Docker GPU passthrough is not configured.

## Result: 7 candidates, 2 possible

| Issue | Cause (from thread/PR) | Where the cost shows | Toggle | Before → after release | L4 notes |
|---|---|---|---|---|---|
| [#6240](https://github.com/vllm-project/vllm/issues/6240) | Untuned CUTLASS FP8 GEMM selected on Ada | GPU kernel | release | v0.5.1 → v0.5.2 (#6384) | Same architecture as the report. Needs CUDA ≥ 12.4-built kernels, which the official image has and the PyPI wheel may not. |
| [#7619](https://github.com/vllm-project/vllm/issues/7619) | Prefix-cache blocks not marked computed, so prefill is recomputed | Redundant GPU work | block manager v1/v2; release | v0.5.5 → v0.6.0 (#7822) | Reported on an L4 with Llama-3-8B FP8 |
| [#6923](https://github.com/vllm-project/vllm/issues/6923) | O(n) evictor lookup when prefix caching is on; TTFT up to 5× | Host CPU in the scheduler | prefix caching on/off; release | v0.6.4.post1 → v0.6.5 (#7209) | 8B bf16 is tight on 24 GB; use FP8 or a smaller model |
| [#7592](https://github.com/vllm-project/vllm/issues/7592) | Scheduler change prioritizes prefill and causes preemption thrashing; ~15% lower throughput | Scheduling policy | chunked prefill on/off; release | v0.5.5 → v0.6.0 (#7874) | RTX 4090 (Ada). Smallest effect of the set. |
| [#25418](https://github.com/vllm-project/vllm/issues/25418) | HF processor re-created for per-request `mm_processor_kwargs`; 7.28 → 0.32 req/s | Host CPU in preprocessing | workload (kwargs or not); release | v0.11.0 → v0.11.1 (#26483) | Single L40S with a 7B VL model; a 3B VL model may be needed for KV room |
| [#19732](https://github.com/vllm-project/vllm/issues/19732) | Slow xgrammar handling of nested length-constrained lists; < 3 tok/s | Host CPU in grammar masking | xgrammar version | xgrammar 0.1.19 → 0.1.21 (#20992; vLLM v0.9.2 → v0.10.0) | Model unstated. The cause is only "xgrammar performance improvements", so the reference is weaker. |
| [#3087](https://github.com/vllm-project/vllm/issues/3087) | Logits processors deep-copied per request: 58 s → 418 s, plus host RAM growth | Host CPU and host memory | release | v0.3.2 → v0.3.3 (#3099) | Old stack (torch 2.1, outlines); installability unchecked |
| [#49013](https://github.com/vllm-project/vllm/issues/49013) *(maybe)* | torch CPU thread pool spin-waits on a per-step 12.6 MB bitmask; 2–5× slower structured decode | Host CPU contention | `OMP_NUM_THREADS=1`; release | v0.26.0 → v0.28.0 (#49919) | Affected releases use CUDA 13-era PyTorch, which is **blocked by the L4 driver**. Needs a 262k-vocabulary model that fits. |
| [#15105](https://github.com/vllm-project/vllm/issues/15105) *(maybe)* | Multimodal processing cache sized as ~0 bytes, so it grows without bound; 45 → 7 tok/s | Host memory and CPU | release | v0.8.0 → v0.8.1 (#15114) | Reported on 2 GPUs, but the cause is not multi-GPU; may scale down to one L4 |

The pilot's vllm#20316 (beam-search candidate concatenation on the host CPU, PR #19347 merged) is a further possible case outside this frame.

## What the screen shows

1. **The decision gate (≥ 8 viable cases across ≥ 4 cause types) is borderline.**
   - Counting the 7 candidates, the gate is short by one. Counting the 2 possible cases, there are 9.
   - By where the cost shows, there are four types: GPU kernel (1), redundant GPU work (1), scheduling policy (1), and host CPU or memory (4, or 6 with the possible cases).
   - Expect roughly half to reproduce (related-work matrix §5), so more candidates are needed. Next sources:
     - a second search frame: issues whose fix PR is linked only in comments;
     - the controlled cases in §4.2 (queue and KV-cache pressure);
     - SGLang.
2. **Most real cases are host-side, not GPU-kernel.** 4 of 7 candidates, and 6 of 9 including the possible ones, have their cause on the CPU (scheduler, preprocessing, grammar, Python copies). This matters for the RQs:
   - RQ1: cheap signals such as GPU utilization dropping while latency rises may point to "host-bound" without any profiler, but not to which host component is responsible.
   - RQ2–RQ3: Nsight Systems shows host-side causes as GPU idle gaps and CPU samples, not as slow kernels. The diagnosis rules and references must cover that, not only kernel-time shifts.
   - This is an observation about the screened sample, not a study result.
3. **Toggles are mostly release pairs.** A release pair changes other code too. Where the thread offers a narrower switch (block manager, prefix caching, chunked prefill, workload, `OMP_NUM_THREADS`, xgrammar version), use it as the primary toggle and the release pair as confirmation.

## Before any GPU time: feasibility checks on the L4 host

All of these need the L4 machine but little GPU time:

1. **Install check:** can each before/after release be installed in its own venv with a CUDA 12.x PyTorch that the driver accepts?
   - The oldest stacks are v0.3.x (#3087) and v0.5.x (#6240, #7619, #7592).
   - The newest blocked one is #49013.
2. **#6240 kernels:** do the PyPI v0.5.1 wheels contain the SM89 CUTLASS FP8 path? If not, either enable Docker GPU passthrough (nvidia-container-toolkit) or extract the environment from the `vllm/vllm-openai:v0.5.1` image.
3. **Symptom check per case:** a short before/after run that shows the reported direction and rough size of the effect. Only cases that pass become benchmark cases (§4.1 acceptance rule). Failed attempts are recorded, not discarded.
