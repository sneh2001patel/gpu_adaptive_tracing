# vllm-project/vllm PR #49919: [Core] Explicitly manage torch CPU threads in workers
merged_at=2026-08-04T17:06:38Z merge_commit=7635a9002baecca64909dbcf8b1d461d26fb879d author=@njhill
files: tests/utils_/test_torch_utils.py, vllm/utils/torch_utils.py, vllm/v1/executor/multiproc_executor.py, vllm/v1/worker/gpu_worker.py

## body
Clamp for startup, single thread for serving.

torch defaults its intra-op thread pool to the host core count, ignoring process affinity, cgroup CPU quotas, and co-located worker processes. Any torch CPU op above the parallel_for grain size (32k elements) fans out across that pool, and the OpenMP workers then spin-wait after every parallel region - stealing cycles from the engine loop's serial code and, in containers, burning the CFS quota so that the entire process is throttled for the rest of the quota period. This is the root cause of the 2-6x structured-output decode throughput regression reported in #49013 (per-step pinning/fill of the ~12.6MB grammar bitmask on the hot path).

Previously only the multiproc executor mitigated this, by exporting `OMP_NUM_THREADS=1` before spawning workers - which also pinned model loading to a single thread, and never covered the uniproc (TP=1), Ray, or external-launcher paths. All #49013 reproductions are TP=1.

Manage torch threads explicitly in the workers instead:

- `Worker.init_device()`: set torch threads to available_cpus divided by the workers on this node, where available_cpus honors both scheduling affinity and the effective cgroup CPU quota (resolved from `/proc/self/cgroup`, v1 and v2). This keeps weight loading parallel but bounded - multiproc workers previously loaded single-threaded.
- After warmup completes in `compile_or_warm_up_model()`: set torch threads to 1. No steady-state CPU op benefits from intra-op parallelism; it only creates spin-wait contention and quota burn.
- The multiproc executor no longer exports `OMP_NUM_THREADS=1` to workers; the parent engine-core process still caps itself to 1 thread since the scheduler gains nothing from intra-op parallelism.

An externally-set `OMP_NUM_THREADS` is always respected; a value > 1 now logs a warning at the serving transition explaining the potential impact.

----

### Weight-loading time improvements

Qwen3-235B-A22B-Thinking-2507-FP8 (221 GiB), TP=4, enforce_eager=True, max_model_len=4096, gpu_memory_utilization=0.85, 4×GB200 / 144 CPU cores

**Warm cache** (4 back-to-back repeats per variant, ±1% spread):

| variant | weight load | total `LLM()` init | load as % of init |
|---|---|---|---|
| before | 37.52 s | 81.79 s | 45.9% |
| **after** | **31.60 s** | **76.06 s** | 41.5% |
| | **−15.8%** | **−7.0%** | |

**Cold cache** (~220 GiB evicted before each run; prefetch 14.2 s cold vs 0.8 s warm):

| variant | weight load | total init |
|---|---|---|
| before | 49.82 s | 95.88 s |
| **after** | **42.21 s** | **85.94 s** |
| | −15.3% | −10.4% |

----

Also [confirmed](https://github.com/vllm-project/vllm/pull/49168#issuecomment-5119258579) to have resolved the TP=1 stuctured output runtime performance regression:

Fixes #49013