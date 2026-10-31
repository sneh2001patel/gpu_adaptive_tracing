# Step 046: Case reproduction, round 2

Date: 2026-10-28/29. Host: same vast.ai L4.

## Results

These are single feasibility runs. Details are in [REPRODUCTION.md](../cases/REPRODUCTION.md).

| Case | Outcome |
|---|---|
| vllm#25418 | **Reproduced, 35×** (6.87 → 0.19 req/s). Fixed release v0.11.1 is still slow. Root cause: the fix's `get_type_hints` raises `NameError` (`PILImageResampling`) under transformers 4.57.1, and the error is swallowed, so the fix is inactive. Use the workload toggle. |
| vllm#19732 | **Reproduced, 2.1×** (205 → 426 tok/s) by swapping xgrammar 0.1.19 → 0.1.21 under vLLM 0.9.2. |
| vllm#3087 | **Reproduced, 7.5×** (344.7 vs 46.2 s; host RSS 19.8 vs 7.4 GB). Reporter: 7.2×. Fix confirmed. |
| vllm#49013 | **Not reproduced** in two attempts (multiprocess and in-process engine; OMP_NUM_THREADS had no effect). |
| vllm#6240 | v0.5.2 release runs at fix-level speed. Weak confirmation: the PyPI wheel lacks SM89 CUTLASS anyway. |

**Tally:** 5 accepted, 1 pending (#7592), 2 failed, 1 not installable. The gate (≥ 8 across ≥ 4 types) is not yet met.

## Process notes

- A detached queue ([queue_round2.sh](../cases/checks/queue_round2.sh)) ran checks while the laptop slept.
- Each CUDA 12.8/13 environment takes 7.5–13 GB, so environments are built and removed per case.
- The HF xet chunk cache filled `/dev/shm` once; it is now disabled with `HF_XET_CHUNK_CACHE_SIZE_BYTES=0`.
- The host has a 19.2-CPU cgroup quota with 40 visible cores.

## Scope of this step

About 2 L4 GPU-hours. The study instrument environment was not touched. No paper, bib or source changes.

## Next

1. Find about 3 more accepted cases: a second GitHub search frame, or the controlled cases in §4.2.
2. Repeat runs for #7592.
3. Then the feasibility pilot (proposal §10, step 5).
