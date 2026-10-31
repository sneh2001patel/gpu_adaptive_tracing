# sgl-project/sglang#19380: [Tracking] GLM-5 (G)B200 Functional Support and Optimizations
state=closed reason=completed created=2026-02-26T01:39:00Z closed=2026-07-27T09:17:52Z labels=['feature', 'performance', 'new-model', 'nvidia']
cross-referenced PRs: ['https://github.com/SemiAnalysisAI/InferenceX-app/pull/386']

## body (@nvpohanh)
## GLM-5 (G)B200 Functional Support and Optimizations

Tracking issue for GLM-5 support in SGLang on (G)B200.

---

### Progress Tracker

#### no-MTP+Agg

| Category | Precision | Item | Status |
|---|---|---|---|
| Functional | FP8 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | FP8 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | FP8 | TP (low-latency) works functionally | ✅ DONE |
| Functional | FP8 | TP (low-latency) has good accuracy | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) works functionally | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) has good accuracy | ✅ DONE |
| Baseline Perf | FP8 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | FP8 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Cookbook | (all) | Update SGLang cookbook | 🔄 IN PROGRESS |
| Perf Analysis | FP8 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Analysis | NVFP4 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Optimization | FP8 | Round 1 perf optimizations | 🔄 IN PROGRESS |
| Perf Optimization | NVFP4 | Round 1 perf optimizations | 🔄 IN PROGRESS |

#### MTP+Agg

| Category | Precision | Item | Status |
|---|---|---|---|
| Functional | FP8 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | FP8 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | FP8 | TP (low-latency) works functionally | ✅ DONE |
| Functional | FP8 | TP (low-latency) has good accuracy | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) works functionally | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) has good accuracy | ✅ DONE |
| Baseline Perf | FP8 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | FP8 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Cookbook | (all) | Update SGLang cookbook | 🔄 IN PROGRESS |
| Perf Analysis | FP8 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Analysis | NVFP4 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Optimization | FP8 | Round 1 perf optimizations | 🔄 IN PROGRESS |
| Perf Optimization | NVFP4 | Round 1 perf optimizations | 🔄 IN PROGRESS |

#### no-MTP+Disagg

| Category | Precision | Item | Status |
|---|---|---|---|
| Functional | FP8 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | FP8 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | FP8 | TP (low-latency) works functionally | ✅ DONE |
| Functional | FP8 | TP (low-latency) has good accuracy | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) works functionally | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) has good accuracy | ✅ DONE |
| Baseline Perf | FP8 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | FP8 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Cookbook | (all) | Update SGLang cookbook | 🔄 IN PROGRESS |
| Perf Analysis | FP8 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Analysis | NVFP4 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Optimization | FP8 | Round 1 perf optimizations | 🔄 IN PROGRESS |
| Perf Optimization | NVFP4 | Round 1 perf optimizations | 🔄 IN PROGRESS |

#### MTP+Disagg

| Category | Precision | Item | Status |
|---|---|---|---|
| Functional | FP8 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | FP8 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | FP8 | TP (low-latency) works functionally | ✅ DONE |
| Functional | FP8 | TP (low-latency) has good accuracy | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) works functionally | ✅ DONE |
| Functional | NVFP4 | DEP (high-throughput) has good accuracy | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) works functionally | ✅ DONE |
| Functional | NVFP4 | TP (low-latency) has good accuracy | ✅ DONE |
| Baseline Perf | FP8 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | FP8 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | DEP (high-throughput) uses correct backends/kernels | ✅ DONE |
| Baseline Perf | NVFP4 | TP (low-latency) uses correct backends/kernels | ✅ DONE |
| Cookbook | (all) | Update SGLang cookbook | 🔄 IN PROGRESS |
| Perf Analysis | FP8 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Analysis | NVFP4 | Round 1 perf analysis | 🔄 IN PROGRESS |
| Perf Optimization | FP8 | Round 1 perf optimizations | 🔄 IN PROGRESS |
| Perf Optimization | NVFP4 | Round 1 perf optimizations | 🔄 IN PROGRESS |

---

### Weekly Progress

#### 2026-05-28

- Piecewise CUDA graph support for NSA has landed; batch CUDA graph follow-up is next.
- GB300 FP4 disaggregated no-MTP configs were submitted, and FP8 disaggregated configs are ready and being submitted.
- GB300 FP4 MTP and GB200 configs remain in progress; the team is also addressing a WideEP memory-use issue.
- For high-throughput runs, a DP load-balancing fix is under review; round-robin routing is the current workaround.

#### 2026-05-15

- FP8 B200 disaggregated 8k/1k and 1k/1k no-MTP submissions and FP4 GB300 disaggregated 8k/1k and 1k/1k no-MTP submissions are ongoing.
- FP8 GB300 disaggregated no-MTP and FP4 GB300 disaggregated MTP work remain in progress.
- #23351 is in review for piecewise CUDA graph support, targeting B200/B300 aggregate max-throughput.
- #25235 is in review for high-throughput DP load balancing, targeting GB300 disaggregated max-throughput.

#### 2026-05-08

- Piecewise CUDA graph support is in review in #23351. A follow-up PR, #24276, expands CUDA graph coverage to more ops and needs additional work.
- Dense MLA prefill support has landed in FlashInfer via flashinfer-ai/flashinfer#3064; the next step is to pick up the next FlashInfer update in SGLang.
- GB300 disaggregated configurations are in progress.
#### 2026-04-17

- **Key issue: B200 FP8 Agg prefill host-boundness** — prefill stage is host-bound, limiting Agg throughput on B200. Multiple mitigations in progress:
  - Piecewise CUDA graph for prefill: debugging segfault issues (draft #18094)
  - `torch.compile()` kernel fusion to fuse tiny kernels causing host overhead — [dev branch](https://github.com/mattteochen/sglang/tree/torch-compile-indexer) available, exploring integration with piecewise CUDA graph
  - Disagg configs: current disagg results look promising, gathering more configs


#### 2026-04-08

- SGLang upgraded to FlashInfer v0.6.7.post2 and released v0.5.10 — all Functional and Baseline Perf now DONE for all variants and precisions
- All Cookbook, Perf Analysis, and Perf Optimization tasks now IN PROGRESS
- Cookbook update planned: trtllm-gen attn backend, NVFP4 instruction, B300 instruction, MTPv2
- Known perf issue: prefill stage is host-bound when ISL is small; ongoing work to enable piecewise cuda graph (draft PR: #18094)

#### 2026-04-07
- stable version v0.5.10 released, on which GLM-5 can directly run
- Flashinfer trtllm sparse mla kernels set by default on sm100/sm103 (#21783)
- IndexCache supported (#21405)
- no-MTP + Agg NVFP4: accuracy verified on both TP and DEP


#### 2026-03-30

- no-MTP+Agg & MTP+Agg FP8 Functional: ✅ DONE (with #17784 merged)
- no-MTP+Agg & MTP+Agg NVFP4 Functional: pending FlashInfer v0.6.7 upgrade (#21422 in review)
- no-MTP+Agg & MTP+Agg Baseline Perf (FP8 + NVFP4): pending FlashInfer v0.6.7 upgrade (#21422 in review)
- no-MTP+Agg & MTP+Agg Cookbook: in progress
- no-MTP+Disagg & MTP+Disagg Functional: all in progress
- no-MTP+Disagg & MTP+Disagg Baseline Perf: all in progress
- FlashInfer PR flashinfer-ai/flashinfer#2836 (included in v0.6.7) merged to improve trtllm-gen sparse MLA perf

#### 2026-03-17

- no-MTP+Agg FP8 Functional: in review — blocked on HF transformers upgrade PR (#17784)
- no-MTP+Agg NVFP4 Functional: in progress — waiting for FlashInfer v0.6.7 upgrade (fix PR merged: flashinfer-ai/flashinfer#2726)
- no-MTP+Agg Baseline Perf (FP8+NVFP4): in progress — working on trtllm-gen for prefill+decode, FP8 kv-cache (#20163)
- Added "Baseline Perf" stage between Functional and Cookbook
- NVIDIA released GLM-5 NVFP4 model: https://huggingface.co/nvidia/GLM-5-NVFP4

#### 2026-03-12

- NVFP4 intermittent IMA (#19081) root-caused; FlashInfer fix PR in review: flashinfer-ai/flashinfer#2726 (targeting v0.6.6.post1)
- Both FP8 and NVFP4 now work functionally with flashmla sparse mla (prefill) + trtllm (decode) using BF16 kv-cache
- Working on using trtllm for both prefill and decode to enable FP8 kv-cache: #20163

#### 2026-03-06 (update)

- no-MTP+Agg FP8 and NVFP4 functional support: IN PROGRESS
- FP8 DEP/TP and NVFP4 DEP/TP functionality and accuracy confirmed (GSM8K: FP8=0.950, NVFP4=0.960)
- Blocker: NVFP4 intermittent IMA with trtllm attention backend (#19081)
- Other variants (MTP+Agg, no-MTP+Disagg, MTP+Disagg) not started yet

#### 2026-03-06

- Created and initialized all tasks

---

### Related GitHub Issues

- #25142 - High-throughput DP load balancing issue
- #25235 - DP load balancing fix (in review)
- #23351 - Piecewise CUDA graph support (in review)
- #24276 - Additional CUDA graph coverage follow-up (in progress)
- flashinfer-ai/flashinfer#3064 - Dense MLA prefill support (merged)
- @Fridge003 's optimization tracker: https://github.com/sgl-project/sglang/issues/15025
- @Fridge003 's bug tracker: https://github.com/sgl-project/sglang/issues/14511
- #17784 - HF transformers version upgrade (merged)
- #18094 - Piecewise CUDA graph for prefill (draft)
- #19081 - NVFP4 intermittent illegal memory access issue
- #20163 - Use trtllm attention for both prefill and decode (FP8 kv-cache)
- #21422 - FlashInfer v0.6.7 upgrade
- #21405 - IndexCache support
- #21783 - Flashinfer trtllm sparse MLA kernels default on sm100/sm103
- flashinfer-ai/flashinfer#2726 - Fix for IMA issue (merged)
- flashinfer-ai/flashinfer#2836 - Improve trtllm-gen sparse MLA perf (merged, included in v0.6.7)
- #22467 - Set sgl_per_token_group_quant_8bit_v2 as default choice