# vllm-project/vllm#49013: [Perf] ~2x decode throughput regression for structured outputs since #45424: apply_grammar_bitmask staging rewrite (bisected to commit, file, and hunk)
state=closed reason=completed created=2026-07-18T04:46:01Z closed=2026-08-04T17:06:39Z labels=[]
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/49150', 'https://github.com/vllm-project/vllm/pull/49168', 'https://github.com/vllm-project/vllm/pull/49780', 'https://github.com/vllm-project/vllm/pull/49919']

## body (@romancomplexio)


## Summary

End-to-end decode throughput for guided-JSON (xgrammar) workloads drops ~2x
between v0.23.0 and v0.24.0 (also v0.25.1). Bisected to commit
**7df3d7dada840c68b85b26b79de7f59f676d58e3** "[Core] Ensure memory is pinned
prior to async h2d copy" (#45424), then within the commit to a single file:
**vllm/v1/structured_output/utils.py — `apply_grammar_bitmask`**.

Evidence chain (identical harness, deterministic to ±1s per 2,000-request
drain; A100 80GB, Gemma-4-26B-A4B-IT bf16, max_num_seqs=64, ngram spec decode
k=5, CUDA graphs, EVERY request uses output_format json_schema → xgrammar):

| build | drain time | rate |
|---|---|---|
| 8dd1b702f (parent commit) | 513 s | 233 req/min |
| 7df3d7dad (culprit) | 985 s | 121 req/min |
| 7df3d7dad + ALL 29 v1/* files reverted to parent | 534 s | 224 req/min |
| 7df3d7dad + ONLY structured_output/utils.py reverted | 534 s | 224 req/min |
| 7df3d7dad + worker files (gpu_model_runner/gpu_input_batch) reverted | 1006 s | 119 req/min |
| 7df3d7dad + PIN_MEMORY forced False (torch_utils) | 985 s | 121 req/min |
| v0.24.0 release | 7581 s vs 3810 s on 15k corpus | 2.0x slower |

Note the PIN_MEMORY=False row: forcing the new global pin flag off does NOT
recover throughput, so the cost is in the staging rewrite itself, not merely
the pinned allocation flag.
Hunk-level split: restoring ONLY the staging block below (keeping the
commit's other change in the same function — index_tensor via
async_tensor_h2d) fully recovers baseline: **514 s / 233 req/min**. The
staging rewrite is the entire regression.

## The suspect code

#45424 changed the per-step bitmask staging in `apply_grammar_bitmask` from:

```python
sorted_bitmask = np.full(
    shape=(logits.shape[0], grammar_bitmask.shape[1]), fill_value=-1,
    dtype=grammar_bitmask.dtype,
)
...  # reorder loop fills rows
grammar_bitmask = torch.from_numpy(sorted_bitmask).to(logits.device, non_blocking=True)
```

to:

```python
sorted_bitmask_tensor = torch.full(
    (logits.shape[0], grammar_bitmask.shape[1]), -1,
    dtype=torch.from_numpy(grammar_bitmask[:0]).dtype,
    pin_memory=PIN_MEMORY,
)
sorted_bitmask = sorted_bitmask_tensor.numpy()
...  # same reorder loop, now writing into the (pinned) tensor's numpy view
grammar_bitmask = sorted_bitmask_tensor.to(logits.device, non_blocking=True)
```

For a 262k-vocab model at max_num_seqs=64 with k=5 ngram speculation this is a
~(384 x 8192) int32 = ~12.6 MB freshly allocated (normally pinned) host tensor
per engine step, plus the reorder loop writing through the numpy view of that
pinned buffer, freed again at the end of the step. This path runs every step
for every batch containing structured-output requests.

## Setup detail

- A100 80GB PCIe, torch 2.11.0 (cu13), python 3.12, offline LLM engine
  (in-process), xgrammar backend, chunked prefill 8192, TRITON_ATTN
  (forced by Gemma4 hetero head dims), async scheduling disabled (ngram).
- Symptom profile: engine steps uniformly ~2x slower at identical batch
  occupancy, acceptance rates, KV/prefix-cache hit, GPU clocks; CUDA graphs
  on/off preserves the gap; regression also present WITHOUT spec decode
  (0.25.1 no-ngram run degraded >2x as well). All requests guided-JSON.
- Release-level numbers (14,985-request production-derived corpus):
  v0.21.0 3810 s makespan / 531 accepted tok/s → v0.24.0 7581 s / 266,
  v0.25.1 7590 s / 265.

## Suggested fix

Restore the numpy staging (or keep a cached, reused pinned staging buffer
sized to (max_logits_rows, bitmask_width) instead of a fresh per-step
allocation).

Possibly related: #47047 (Gemma-4-26B-A4B on SM120/NVFP4, 0.21→0.23 slowdown
at low concurrency, unresolved — different window but same model family and
also structured-output-heavy workloads).

Full bisect logs (9 commit-level probes via per-commit wheels + 8 file/hunk-level
image probes) available on request.


## comment @anencore94 2026-07-25T03:31:12Z

Independent reproduction, plus a finding on **why the magnitude varies so much**: in a
container with a CPU quota, the same commit costs **5.4x**, not 2x — and the whole
regression disappears by setting `OMP_NUM_THREADS`.

## Reproduction (independent of the reporter's harness)

- vLLM v0.23.0 vs v0.25.1, identical args, KServe pods, 1×B300, TP=1
- Workload: real production traffic — 300 Korean VOC classification requests,
  ~5.9K prompt tokens, ~110 output tokens, single JSON schema, `temperature=0`
- Measured both `bf16` (google/gemma-4-31B-it) and `NVFP4` (nvidia/Gemma-4-31B-IT-NVFP4)

| build | free p50 | guided p50 | guided out-tok/s |
|---|---|---|---|
| v0.23.0 + NVFP4 | 1.52s | 1.42s | — |
| v0.25.1 + NVFP4 | 1.35s | **7.30s** | 664 → **120** |
| v0.25.1 + bf16 | 2.04s | **6.10s** | 427 → **117** |

Quality was unaffected (300/300 valid JSON, zero `finish_reason=length`) — timing only.
Rolling the image back to v0.23.0 (args unchanged) restored guided to 1.66s immediately.

Two things worth noting, both consistent with the staging rewrite being the cause:
- **Concurrency-gated**: at concurrency 1, guided ≈ free (0.93s vs 0.99s). The collapse
  only appears at concurrency 8+.
- **Not grammar compilation**: a second run against a warm grammar cache is equally slow,
  so this is per-step, not admission-time.

## The V2 runner path has the same rewrite — and it is not covered by either open PR

Both open PRs (#49150, #49168) change only `vllm/v1/structured_output/utils.py`, i.e. the
**V1** runner. Dense models on v0.25.1 take the **V2** runner
(`VllmConfig` dropped the `is_quantized` term from the V2 eligibility check, so e.g.
`google/gemma-4-31B-it` moves V1 → V2 between v0.23.0 and v0.25.1), and that path regresses
through a different file with the same change — `vllm/v1/worker/gpu/buffer_utils.py`:

```python
# v0.23.0
#   Copy directly to GPU — explicit pin_memory() causes sporadic stalls
#   under high concurrency due to CUDA driver contention. The driver
#   handles the transfer efficiently without manual pinning.
return out.copy_(x, non_blocking=True)

# v0.25.1 (#45424)
# pin_memory() is no-op if the memory is already pinned.
pinned = x.pin_memory()
return out.copy_(pinned, non_blocking=True)
```

Worth flagging: that comment came from **#37006 ("[V1] Remove pin_memory() in
async_copy_to_gpu to fix sporadic stalls", merged 2026-03-14)**, whose whole purpose was to
remove this `pin_memory()` call. #45424 reinstated it, so on the V2 path this is a silent
regression of a previously merged fix rather than a new trade-off.

The "no-op if already pinned" assumption does not hold on this path: `grammar_bitmask` is a
fresh `np.ndarray` built by the scheduler every step, so `pin_memory()` is a real allocation
plus copy on every decode step. The call is guided-only — `apply_grammar_bitmask()` returns
early on `if not grammar_req_ids` — which is why free decoding is unaffected.
`StructuredOutputsWorker.apply_grammar_bitmask` also allocates a second pinned tensor per
step for the bitmask→logits mapping (`torch.tensor(mapping, ..., pin_memory=True)`).

## Why some deployments see 2x and we saw 5.4x

`torch.get_num_threads()` is derived from **host** core count and ignores the cgroup CPU
quota. On our node that is 172 threads against a 12-CPU quota (`cpu.max = 1200000 100000`)
— 14.3x oversubscription. The per-step pinned memcpy fans out across those threads and
sustains CFS throttling.

Controlled experiment (v0.25.1, `google/gemma-4-12B-it` bf16, same args, same `cpu limit: 12`,
same 80-request conc-8 workload), **varying only the host core count of the node**:

| host cores | torch threads | free p50 | guided p50 | guided out-tok/s |
|---|---|---|---|---|
| 40 | 40 | 1.41s | 2.18s (+55%) | 384 |
| 172 | 172 | 1.12s | **7.49s (+569%)** | 115 |
| 172 | **12** (`OMP_NUM_THREADS=12`) | 1.11s | **1.07s** | **738** |

So `OMP_NUM_THREADS` matching the cgroup quota **fully eliminates the regression** without
reverting anything — guided returns to parity with free (1.07s vs 1.11s), 6.4x more decode
throughput. This is a usable workaround for anyone hitting this in Kubernetes today, and it
suggests the severity reported here scales with (host cores ÷ CPU quota) rather than being
a fixed 2x.

Confirmed on the production serving too: setting `OMP_NUM_THREADS=12` on the v0.25.1 bf16
gemma-4-31B deployment (nothing else changed) took guided p50 from 6.10s to **1.72s** and
decode throughput from 117 to 398 tok/s, with guided again slightly ahead of unguided.

Happy to test a patch on this workload if that's useful. I've opened a PR for the V2 path
that stages both per-step copies through preallocated `CpuGpuBuffer`s, which keeps #45424's
"source must be pinned" property while removing the per-step allocation — it is complementary
to #49150 / #49168 rather than overlapping with them.


## comment @njhill 2026-07-27T00:22:40Z
Should hopefully be fixed by https://github.com/vllm-project/vllm/pull/49919.

## comment @njhill 2026-07-30T17:01:16Z
@romancomplexio would be great if you could confirm that #49919 restores the performance in your case.

## comment @njhill 2026-08-04T17:07:18Z
@romancomplexio feel free to reopen if the problem was not fixed by https://github.com/vllm-project/vllm/pull/49919, thanks!

## comment @romancomplexio 2026-09-11T14:18:00Z
Hi @njhill, I appreciate a ton the help here and my apologies for coming back late.

I've finally tested the throughput on the newer version and, unfortunately, this hasn't fixed the performance regression.

In my understanding the problem for us has been the added allocation of a 12MB tensor per every structured decode step. The thread oversubscription was a much smaller problem.

Here are the numbers on our workloads:
```
v0.21.0 (pre-regression control)   515s  233 req/min
v0.24.0 + OMP_NUM_THREADS=4        997s  120 req/min
v0.28.0 stock                      987s  121 req/min
v0.28.0 + patch                    495s  242 req/min
```

The mentioned patch is the reversal of the change on this file [here](https://github.com/vllm-project/vllm/commit/7df3d7dada840c68b85b26b79de7f59f676d58e3#diff-c8a54e6226d416ba544652f3f956b2c78fbbb5719d2e6ba2e3c97fd8f987c04aL126).