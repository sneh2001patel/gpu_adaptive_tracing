# Case reproduction log (proposal §4.1)

Host: vast.ai container with one NVIDIA L4 (SM89, 23 GB), driver 615.71.09, 40 vCPUs, Ubuntu 24.04. Date: 2026-10-28.

These are **feasibility checks: single runs that show whether the reported symptom appears and whether the documented fix removes it.** They are not study measurements. Benchmark-grade runs with repeated blocks come later (proposal §7).

Scripts are in [checks/](checks/); raw outputs (`*.json`, `*.out`, `*.err`) sit next to them. Environments are rebuilt with [checks/setup_case_env.sh](checks/setup_case_env.sh).

## Host constraints found

- **Unprivileged container:** no Docker, and `kernel.perf_event_paranoid = 4`.
  - Nsight Systems on this host gets no CPU sampling; it can still trace CUDA, NVTX and OS runtime calls.
  - For host-side cases, the GPU-side trace shows idle gaps, not the responsible Python code.
- **Storage:** about 23 GB free on `/` and 17 GB in `/dev/shm`. Each old vLLM stack takes 5–7 GB, so environments are built one or two at a time and removed after use. `/workspace` is not a persistent volume, so results are copied back after every check.
- **Driver:** supports CUDA 13. vllm#49013, previously marked driver-blocked, is feasible on this host.
- **Dependencies:** old releases resolve against present-day packages unless they are pinned. Every environment uses `uv pip install --exclude-newer <release date>`.
  - Exception: `pyairports` was removed from PyPI and replaced by an empty placeholder. It is exempted from the cutoff and stubbed with an empty `AIRPORT_LIST`; `outlines` uses it only for an airport-code type.
- **Install checks (dry-run resolution):** all candidate releases resolve, except v0.8.0/v0.8.1 (vllm#15105). Those pin `xgrammar==0.1.16`, which is no longer on PyPI.
  - vLLM 0.9.2 pins `xgrammar==0.1.19`, so the vllm#19732 toggle (0.1.19 → 0.1.21) requires overriding that pin.

## vllm#6240: FP8 CUTLASS GEMM on Ada. **Reproduced.**

**Finding 1: the PyPI wheel cannot reproduce it.**
- The vLLM 0.5.1 PyPI wheel is built with CUDA 12.1. It reports `cutlass_scaled_mm_supports_fp8(89) = False`, so vLLM falls back to `torch._scaled_mm`.
- Calling its CUTLASS kernel directly fails with "not implemented" device errors.
- This matches the maintainer who could not reproduce the issue on an L40.
- Raw output: `6240_v051.*`.

**Environment:**
- The reporter used the `vllm/vllm-openai:v0.5.1` image, built with CUDA 12.4.
- Docker is unavailable here, so the `vllm` package (`0.5.1+cu124`) was extracted from layer 8 of that image through the registry API.
- It was swapped into the pip environment, which uses the same `torch==2.3.0` as the image. The PyPI copy is kept alongside for comparison.

**Kernel level** (`check_6240_kernels.py`; raw output `6240_v051_image.json`):
- The image build selects CUTLASS on SM89 (`cutlass_fp8_supported() = True`).
- CUTLASS FP8 GEMM is **1.7–5.2× slower** than `torch._scaled_mm` at every Llama-3-8B linear shape (qkv, o, gate_up, down) and M ∈ {1, 16, 64, 256}.

**Serving level** (`check_6240_serving.py`; raw output `6240_serving_{on,off}.json`):
- Model: `neuralmagic/Meta-Llama-3-8B-Instruct-FP8`, the reporter's model; offline greedy decode, 256 tokens, `ignore_eos`.
- Toggle: `--cutlass off` forces `cutlass_fp8_supported()` to `False`. That is what fix PR #6384 does on Ada; the build and everything else are unchanged.

| Batch | CUTLASS on (bug) | CUTLASS off (fix effect) | Slowdown |
|---|---|---|---|
| 1 | 14.58 tok/s | 25.97 tok/s | 1.78× |
| 8 | 115.07 tok/s | 200.12 tok/s | 1.74× |
| 32 | 417.76 tok/s | 713.29 tok/s | 1.71× |

The reporter saw 25.36 vs 56.28 tok/s (2.2×) on an L20, a faster card of the same architecture.

**v0.5.2 release check** (`check_6240_serving_v052.py`, which only adapts the import path; raw output `6240_serving_v052.*`):
- `cutlass_fp8_supported() = False`.
- Throughput: 25.86 / 198.63 / 702.18 tok/s at batch 1 / 8 / 32, the same as the CUTLASS-off toggle.
- **Caveat:** the v0.5.2 PyPI wheel is also a CUDA 12.1 build, so it would avoid CUTLASS on SM89 even without the fix. This confirms the fixed release's performance, not that the fix is the reason.
- The decisive comparison remains the toggle within the 0.5.1 image build above. A full release confirmation needs the `vllm/vllm-openai:v0.5.2` image build.

## vllm#7619: block manager v2 prefix-cache warm-up. **Reproduced and fix confirmed.**

**Setup:**
- The reporter's command on the reporter's GPU type (L4): `benchmarks/benchmark_prefix_caching.py` at tag v0.5.4, which is the script whose output format the issue shows.
- `--model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 --output-len 200 --enable-prefix-caching`, with and without `--use-v2-block-manager`.
- Raw output: `7619_v055_{v1,v2}.out`, `7619_v060_v2.out`.

| Release | Block manager | Warm-up batch | Second batch | Reporter (L4) |
|---|---|---|---|---|
| v0.5.5 | v1 | 15.61 s | 14.39 s | 14.58 / 13.35 s |
| v0.5.5 | v2 | **24.16 s** | 14.10 s | **24.06** / 13.42 s |
| v0.6.0 (fix #7822) | v2 | 15.21 s | 14.17 s | — |

**Accepted as a case:**
- the symptom reproduces at the reported size;
- the fixed release removes it;
- there is a same-release configuration toggle (v1 vs v2).

## vllm#7592: chunked-prefill scheduler regression. **Accepted after 5 paired blocks (step 050).**

**Setup:**
- The reporter's engine-loop benchmark from the issue body ([checks/check_7592_chunked.py](checks/check_7592_chunked.py)): 1000 prompts of `"hi" * 511`, 512 output tokens, `ignore_eos`, temperature 1.0, `enforce_eager`, chunked prefill with `max_num_batched_tokens = max_num_seqs = 256`. That value is the reporter's largest gap: 5.59 → 4.91 req/s on an RTX 4090.
- **Deviation:** Qwen2.5-7B-Instruct, the cached model, instead of Qwen2-7B-Instruct (same architecture and size).
- Raw output: `7592_v055.*`, `7592_v060.*`.

| Release | req/s | Time per output token | Preemptions logged (lower bound) |
|---|---|---|---|
| v0.5.5 (bug, after #6867) | 1.397 | 130.0 ms | ≥ 251 |
| v0.6.0 (fix #7874) | 1.539 | 109.6 ms | ≥ 151 |

**Reading:**
- The fixed release is about 10% faster (reporter: 14%).
- The L4 leaves about 4.7k KV blocks after 14.2 GB of weights, so both releases preempt continually. The difference in preemption count is consistent with the fix's stated mechanism: sorting the running queue so that decodes are prioritized, which reduces thrashing.
- The preemption counter is cheap telemetry that tracks the cause (relevant to RQ1).
- **Not yet accepted:** a single 10% difference needs repeated blocks to separate it from run-to-run variation.
- **Cost:** each run takes about 11–12 minutes, which matters for the GPU budget. A smaller `num_prompts` should be checked for whether it preserves the effect.

## vllm#6923: prefix-caching evictor overhead. **Not reproduced (two attempts). Recorded as a failed reproduction.**

**Setup:**
- [checks/check_6923_prefix_ttft.py](checks/check_6923_prefix_ttft.py): closed loop with N clients in place of llmperf; 512-token shared prefix + 1024 random tokens, 512 output tokens.
- Llama-3-8B FP8 (deviation from bf16 Llama-3-8B on an A100); 32 clients; 256 requests.
- Raw output: `6923_*`.

| Release | Prefix caching | TTFT mean | TTFT p95 | Elapsed |
|---|---|---|---|---|
| v0.6.4.post1 | off | 4812 ms | 8778 ms | 365 s |
| v0.6.4.post1 | on | 3377 ms | 6020 ms | 318 s |
| v0.6.5 (fix #7209) | on | 3443 ms | 6028 ms | 316 s |

**Reading:**
- Prefix caching helps here, and the fix changes nothing. The reported 2–5× TTFT inflation does not appear.
- **Likely reason:** fix PR #7209 measured about 7 ms per eviction on an A100, because the evictor's lookup scans the free table, whose size grows with the number of KV blocks. With an 8B model, the L4 holds only a fraction of an A100-80GB's blocks, so the scan stays cheap.
- **Attempt 2 tested that hypothesis.**
  - Setup: Qwen2.5-1.5B-Instruct (35,648 KV blocks, about 7× more), 64 clients, 512 requests on v0.6.4.post1. Raw output: `6923s_*`.
  - Prefix caching off: TTFT mean 3090 ms, p95 5694 ms.
  - Prefix caching on: TTFT mean 2448 ms, p95 4923 ms.
  - Still no slowdown. An 8B bf16 model on an A100-80GB leaves a block count of the same order, so cache size alone does not explain the gap.
- **Untested differences:**
  - the reporter's host CPU (the evictor runs on the CPU);
  - llmperf's open HTTP clients versus the in-engine closed loop;
  - block-manager defaults in the reporter's build.
- **Decision:** stop here to save GPU time. Keep the case as a failed attempt in the reproduction count.

## vllm#25418: per-request `mm_processor_kwargs` re-create the HF processor. **Reproduced (35×). Fixed release ineffective on this stack (root cause found).**

**Setup:**
- [checks/check_25418_mm_kwargs.py](checks/check_25418_mm_kwargs.py): offline engine; 100 requests, each with one synthetic 448×448 image; 112 output tokens.
- Mode `per_request` gives every request `mm_processor_kwargs={"fps": U(1.9, 2.1)}`, the same as the reporter's patch.
- **Deviations:** Qwen2.5-VL-3B instead of 7B; synthetic images instead of VisionArena; offline engine instead of `vllm bench serve`.
- Raw output: `25418_*`. Run partly through the detached queue ([checks/queue_round2.sh](checks/queue_round2.sh), log `queue_round2.log`).

| Release | Per-request kwargs | req/s | output tok/s |
|---|---|---|---|
| v0.11.0 | none | 6.867 | 769.1 |
| v0.11.0 | per request | **0.194** | 21.7 |
| v0.11.1 (fix #26483) | none | 7.275 | 814.8 |
| v0.11.1 (fix #26483) | per request | **0.177** | 19.9 |

The reporter saw 7.28 → 0.32 req/s on an L40S (23×).

**Why the fixed release is still slow:**
- Fix #26483 removes per-call processor options from the processor cache key. It finds those options by reading the type hints of the processor's `__call__` kwargs.
- With the release-date `transformers==4.57.1` (Python 3.10), `get_type_hints(Qwen2_5_VLProcessorKwargs)` raises `NameError: name 'PILImageResampling' is not defined`, a forward reference that is never imported at runtime.
- `get_processor_kwargs_from_processor` catches every exception and returns an empty set. So no option counts as per-call, `fps` stays in the cache key, and the processor is still rebuilt for every request.
- The fix is therefore silently inactive in this environment. The PR's own verification (0.30 → 9.01 req/s) must have used a different `transformers`.

**As a benchmark case:**
- Use the **workload toggle**: same release, with or without per-request kwargs.
- The release toggle is invalid on this stack, and is recorded as such.
- Cause is per-request HF processor construction (host CPU). It is confirmed by the PR's description and by the mechanism above; the processor-cache miss itself has not yet been instrumented directly.

## vllm#19732: xgrammar on nested length-constrained lists. **Direction reproduced (2.1×); magnitude not comparable.**

**Setup:**
- [checks/check_19732_xgrammar.py](checks/check_19732_xgrammar.py): vLLM 0.9.2, one environment, xgrammar swapped in place (0.1.19 is vLLM's pin; 0.1.21 is fix #20992).
- The issue's exact schema; Qwen2.5-1.5B-Instruct (the issue states no model); 8 batched requests; 512 max tokens; greedy.
- The backend is set at engine init, because 0.9.x rejects per-request backend selection. The first attempt failed on that and is kept in `19732_*.err` history.

| xgrammar | Elapsed | Output tok/s | Valid JSON |
|---|---|---|---|
| 0.1.19 | 6.56 s | 204.96 | 8/8 |
| 0.1.21 | 3.15 s | 426.05 | 8/8 |

**Reading:**
- Identical outputs (1344 tokens each) at twice the speed: the cost is in the grammar engine's per-token mask computation on the host.
- The reporter's "< 3 tok/s" cannot be compared: model, batch size and hardware are not stated.
- **Accepted** with a clean single-component toggle. The cause is only stated as "xgrammar performance improvements" (xgrammar PR #308), so the reference diagnosis is "grammar mask generation on the host", not a specific function.

## vllm#3087: logits processors deep-copied per request. **Reproduced (7.5×), fix confirmed.**

**Setup:**
- [checks/check_3087_logits_copy.py](checks/check_3087_logits_copy.py): the issue's example verbatim (outlines `JSONLogitsProcessor`, the issue's schema and prompt, 256 copies, `max_tokens=128`, greedy), timed, plus peak process RSS.
- Packages as of the issue date: outlines 0.0.33, pydantic 2.6.3, transformers 4.38.1, torch 2.1.2.
- **Deviation:** TinyLlama-1.1B (32k Llama vocabulary) instead of Mistral-7B-v0.1. The copied object is the outlines FSM, which depends on the schema and vocabulary, not on model size.
- Raw output: `3087_*`.

| Release | Elapsed | Peak host RSS | Reporter (Mistral-7B) |
|---|---|---|---|
| v0.3.3 (fix #3099) | 46.17 s | 7.40 GB | 58 s, ~6 GB |
| v0.3.2 (bug, #2881) | **344.71 s** | **19.75 GB** | 418 s, ~18 GB |

**Accepted:**
- the ratio (7.5× vs the reporter's 7.2×) and the host-memory growth both match on a model 7× smaller, which is consistent with the stated cause;
- the fixed release removes it.

The cost is entirely on the host: `deepcopy` of `SamplingParams`, including the FSM, per request, before any GPU work, while the GPU sits idle. For the diagnosis study, this is the clearest "GPU idle, host busy" case.

## vllm#49013: structured-output decode regression from CPU thread contention. **Not reproduced (two attempts).**

**Setup:**
- [checks/check_49013_structured.py](checks/check_49013_structured.py): vLLM 0.26.0 (torch 2.11.0+cu130; runs on this CUDA 13 driver).
- `unsloth/gemma-3-1b-it`: an ungated mirror of Gemma 3 1B with a 262k vocabulary. No HF token is configured on the host. Gemma licence terms apply.
- 256 chat requests, all using one JSON schema; `max_num_seqs = 64`; up to 128 tokens.
- The host has a cgroup CPU quota of 19.2 CPUs with 40 visible: the condition that the second reproducer found made the regression worse.
- Raw output: `49013_*`.

| Engine mode | Decoding | OMP_NUM_THREADS | Output tok/s |
|---|---|---|---|
| multiprocess (default) | plain | unset | 5019.6 |
| multiprocess (default) | guided JSON | unset | 4172.6 |
| multiprocess (default) | guided JSON | 1 | 4199.1 |
| in-process (`VLLM_ENABLE_V1_MULTIPROCESSING=0`) | guided JSON | unset | 4127.6 |
| in-process | guided JSON | 1 | 4122.8 |
| in-process | plain | unset | 5013.8 |

**Reading:**
- The workaround (`OMP_NUM_THREADS=1`) changes nothing, so the regression is not present in this configuration. The regressing commit (#45424) is in v0.26.0, and none of the alternative fix PRs (#49150, #49168, #49780) were merged.
- The engine logged "Using V2 Model Runner"; per the second reproducer, that path regresses through a different file (`buffer_utils.py`).
- **Untested differences:**
  - long prompts (about 5.9k input tokens) and outputs (about 110 tokens) versus about 35 output tokens here;
  - 26–31B models;
  - different host CPU topologies.
- **Decision:** stop (time-box) and keep it as a failed attempt. The v0.28.0 comparison was not run, because there was no symptom to compare.

## Tally after round 2

| Case | Where the cost shows | Outcome | Toggle to use |
|---|---|---|---|
| #6240 | GPU kernel (FP8 GEMM) | **Accepted** | CUTLASS support check on/off in the 0.5.1 image build |
| #7619 | Redundant GPU prefill | **Accepted** | Block manager v1/v2 (v0.5.5); fix release v0.6.0 |
| #3087 | Host CPU + host memory (deepcopy) | **Accepted** | v0.3.2 vs v0.3.3 |
| #25418 | Host CPU (HF processor rebuilds) | **Accepted** (workload toggle) | Per-request kwargs on/off; the release toggle is invalid on this stack |
| #19732 | Host CPU (grammar masks) | **Accepted** | xgrammar 0.1.19 vs 0.1.21 under vLLM 0.9.2 |
| #7592 | Scheduling / preemption | **Accepted** (5 blocks, +10.6%, CI excludes 0) | v0.5.5 vs v0.6.0 |
| #6923 | Host CPU (evictor) | Failed (2 attempts) | — |
| #49013 | Host CPU (thread contention) | Failed (2 attempts) | — |
| #15105 | Host memory / CPU | Not attempted: v0.8.x cannot install (`xgrammar==0.1.16` gone) | — |

**Count (after step 050):** 6 accepted out of 8 attempted (75% yield). That is above the roughly 50% expected from the literature.

**Mix:** 2 GPU-side (kernel, redundant compute), 3 host-side, plus 1 scheduling case pending. The proposal's gate is ≥ 8 cases across ≥ 4 types. That still needs about 3 more accepted cases, either from a second search frame or from the controlled cases (§4.2: queue pressure, KV-cache pressure).

## vllm#7592 confirmation blocks (step 050)

**Setup:**
- [checks/queue_7592_blocks.sh](checks/queue_7592_blocks.sh): 5 blocks in counterbalanced order (ab, ba, ab, ba, ab), with a fresh engine process per run. The round-1 benchmark is unchanged.
- A first queue start drew "ba" for all five blocks from its seed. It was stopped before any block completed and restarted counterbalanced; the log is kept as `queue_7592_blocks_aborted_ba.log`.
- Analysis: [checks/analyze_7592_blocks.py](checks/analyze_7592_blocks.py). Raw output and `analysis.json`: [checks/blocks_7592/](checks/blocks_7592/).

**Result:**

| Measure | Value |
|---|---|
| Mean paired difference (v0.6.0 − v0.5.5) | +0.1472 req/s (+10.6%) |
| SD | 0.0041 |
| 95% CI, t | [0.1414, 0.1531] |
| 95% CI, bootstrap | [0.1442, 0.1508] |
| Blocks favouring the fix | 5/5 |

**Accepted:** both intervals exclude zero. Run-to-run variation is small (v0.5.5: 1.3845–1.391 req/s; v0.6.0: about 1.537–1.538).

## Serving check under the external instrument (step 055)

This is proposal §10 step 6: each accepted case as an open-loop serving workload, fixed side vs bug side at the same arrival times. It used a pre-declared criterion: bug p50 latency at least 1.1× the fixed side's, or throughput at most 0.9×. Details are in [CALIBRATION_PLAN.md §2.1](../protocol/CALIBRATION_PLAN.md).

| Case | Offline result (above) | Serving result |
|---|---|---|
| #6240 | 1.71–1.78× decode slowdown | p50 1.84× — **shown** |
| #7619 | 24.2 vs 15.6 s warm-up batch | p50 2.29×, throughput 0.81× — **shown** |
| #3087 | 7.5× | p50 133×, throughput 0.49× — **shown** |
| #25418 | 35× | p50 45×, only 39 of 115 requests completed — **shown** |
| #7592 | +10.6% throughput for the fix | throughput 0.90×, p50 1.14× at 3 req/s (not at 1.45 req/s) — **shown** |
| #19732 | 2.1× | no difference at 1.5 or 4 req/s, grammar active on both sides — **not reproduced under serving** |

**#19732 status:**
- It stays an accepted offline reproduction.
- It is excluded from the serving study.

**Final serving set:** 5 cases across 4 cause types.
