# vllm-project/vllm PR #44490: [Bugfix][Core] Fix host memory leak from undrained new_block_ids
merged_at=2026-07-07T07:32:55Z merge_commit=b4cfbc24d33ca17bc764a75ffe749654654521c1 author=@Sunt-ing
files: vllm/v1/core/kv_cache_coordinator.py, vllm/v1/core/sched/scheduler.py, vllm/v1/core/single_type_kv_cache_manager.py

## body

## Purpose

Fixes #44175 

Under sustained `max_tokens=1` load, host RSS grows linearly with no plateau. The reporter saw ~6.0 → 6.57 GiB over a 12h run with Gemma-3-1b and prefix caching.

**Who is affected:** any V1 model with a full-attention or MLA KV-cache layer and **no Mamba layers** — i.e. essentially all standard attention models (Llama, Qwen, GPT/OPT, Gemma-2/3, DeepSeek-MLA). Mamba / hybrid-Mamba models are unaffected.

**Root cause:** #35219 added `SingleTypeKVCacheManager.new_block_ids`, appended on every full-attention/MLA block allocation but drained only when `needs_kv_cache_zeroing` (which equals `has_mamba_layers`):

- Recording is gated on the **spec type** (`FullAttentionSpec`/`TQFullAttentionSpec`/`MLAAttentionSpec`); draining is gated on **having Mamba layers**.
- So a non-Mamba model records on every block allocation but **never drains** → the list grows without bound (one `int` per allocated block per request).
- `gc.freeze()` at `EngineCore` startup hides the list from `gc.get_objects()`/`tracemalloc`, which is why it looks like allocator fragmentation.
- #35219 itself states "non-hybrid (pure attention) models are completely unaffected" — this fix makes that true.

**Fix** (consumer side, one file): drain `take_new_block_ids()` **unconditionally** every scheduler step, and only use the result when zeroing is enabled.

- The drained ids are consumed only by the zeroing path (`take_new_block_ids()` → `SchedulerOutput.new_block_ids_to_zero` → `gpu_model_runner._zero_block_ids()`), so unconditional draining is safe for all models.
- For Mamba models the drain already happened in that branch, so their behavior is byte-for-byte unchanged.
- I avoided gating the *recording* behind a new manager constructor flag: a default-`False` flag for a correctness feature (KV zeroing) would silently disable zeroing on any construction path that forgot to pass it.

## Test Plan

Reproduced on current `main` and verified the fix on the same runs. Hardware: NVIDIA RTX PRO 6000 (Blackwell, sm120), CUDA 13.0, PyTorch 2.11, Python 3.12 — the leak is host-side and GPU-independent.

Common settings: V1, `enable_prefix_caching=True`, `max_tokens=1`, unique ~500-token prompts, MIG-like `gpu_memory_utilization=0.10`, `enforce_eager`, `VLLM_USE_FLASHINFER_SAMPLER=0` (sm120). In-process runs set `VLLM_ENABLE_V1_MULTIPROCESSING=0` to sample the `EngineCore`'s `VmRSS` and `new_block_ids` length directly. This is the reporter's model on the same code path, not their exact MIG/container/12h run.

<details><summary>Reproduction script (in-process soak)</summary>

```python
import os, random
os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"  # EngineCore in-process: /proc/self is the scheduler process
from vllm import LLM, SamplingParams

llm = LLM(model="google/gemma-3-1b-it", enforce_eager=True, gpu_memory_utilization=0.10,
          max_model_len=2048, enable_prefix_caching=True)  # or model="facebook/opt-125m"
sched = llm.llm_engine.engine_core.engine_core.scheduler            # in-process V1 EngineCore
mgrs = sched.kv_cache_manager.coordinator.single_type_managers      # only FullAttentionSpec managers record
new_block_ids = lambda: sum(len(m.new_block_ids) for m in mgrs)

def vmrss_mb():
[... 7 lines truncated ...]
        print(f"req={i} VmRSS_MB={vmrss_mb():.1f} new_block_ids={new_block_ids()}")
```
</details>

## Test Result

The leak reproduces on the reporter's exact model in the reporter's exact deployment (`vllm serve`), and the fix flattens the host RSS. Each row is the same run before/after the fix:

| Model (KV-cache class) | Engine / setting | Reqs | Host-RSS growth: **before → after fix** |
|---|---|---|---|
| **gemma-3-1b-it** — reporter's model (hybrid SWA + global, no Mamba) | **real `vllm serve`**, 64-concurrent | 400k | container RSS **+163.8 MiB, no plateau → +1.5 MiB, flat** |
| gemma-3-1b-it (same) | in-process | 100k | EngineCore VmRSS **+91.5 MiB → +1.2 MiB**; list 6.8M → **0** |
| opt-125m (pure full-attention) | in-process | 300k | EngineCore VmRSS **+167.4 MiB → +4.2 MiB**; list 19.85M → **0** |
| Qwen3-0.6B (pure full-attention) | in-process | 20k | `new_block_ids` **→ 1.37M, linear** (leaks) |
| **Qwen3.5-4B** — hybrid **Mamba/SSM** (`needs_kv_cache_zeroing=True`) | in-process | 18k | `new_block_ids` **stays 0 — no leak** |

- **In-use leak, not fragmentation:** every before-fix run's final `gc.collect()` frees **0 MB** (`malloc_trim` does not return it).
- **Magnitude matches the report:** opt-125m converges to **8.84 B per leaked entry** = a CPython list pointer ≈ the reporter's ~90 B/req (~0.57 GiB over ~6.5M reqs at 150 RPS × 12h).
- **Negative control:** the hybrid-Mamba family #35219 was built for (Qwen3.5-4B) does **not** leak — it drains every step. For `needs_kv_cache_zeroing=True` models the fix is a no-op, so it cannot affect the Mamba zeroing feature.
- **MLA** is covered by the same code, not a separate run: `spec_manager_map[MLAAttentionSpec]` is `FullAttentionManager` (the same class and recording line as the tested dense models) and MLA models have no Mamba layers.

<details><summary>Full VmRSS curves (before / after)</summary>

```
# REAL vllm serve (multiprocess), google/gemma-3-1b-it, container/tree RSS, 400k requests @ 363 rps
NO-FIX   done=400000 container_rss 4360.9 -> 4524.7 MiB  (+163.8, monotonic, no plateau)
WITHFIX  done=400000 container_rss 4271.5 -> 4273.0 MiB  (+1.5, flat)

# in-process engine, google/gemma-3-1b-it (reporter's model), 100k requests
NO-FIX   req=20064  dMB=2.3   list=1374362
NO-FIX   req=60192  dMB=23.2  list=4106748
NO-FIX   req=100000 dMB=91.5  list=6817315   gc_collect_freed=0.0MB
WITHFIX  req=40128  dMB=0.8   list=0
WITHFIX  req=100000 dMB=1.2   list=0          gc_collect_freed=0.0MB

[... 2 lines truncated ...]
WITHFIX  req=300032 dMB=4.2   list=0          gc_collect_freed=0.0MB
```
</details>

**Tests / lint:** behavior is verified by the before/after `vllm serve` and in-process soak runs above; the leak is a runtime accumulation a unit test can't faithfully express, so none is added. `test_scheduler.py` and `test_single_type_kv_cache_manager.py` pass unchanged on this branch. `ruff` / `ruff-format` / `typos` / SPDX-header all clean.

**Not reproduced (out of scope here):** the report also notes a CPU decline and a latency step-up at ~7h. These did not reproduce in this environment (no cgroup limits like the reporter's `cpu: "2"` container, and far more host RAM, so RSS never approaches a reclaim threshold) and are most likely downstream of the memory growth. @ashgold — could you confirm they clear once this fix is applied on your setup?

AI assistance was used to prepare this PR.
