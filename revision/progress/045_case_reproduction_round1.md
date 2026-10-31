# Step 045: Case reproduction, round 1 (L4 feasibility checks)

Date: 2026-10-28. Host: vast.ai L4 container (details in [REPRODUCTION.md](../cases/REPRODUCTION.md)).

## Results

These are single runs; they are feasibility checks, not measurements.

| Case | Outcome |
|---|---|
| vllm#6240 FP8 CUTLASS on Ada | **Reproduced.** Kernel 1.7–5.2× slower; decode 1.71–1.78× slower. Needs the official image's CUDA 12.4 vLLM build, extracted from the registry; the PyPI wheel cannot reproduce it. |
| vllm#7619 block manager v2 prefix warm-up | **Reproduced, fix confirmed.** 24.16 s vs 15.61 s (reporter: 24.06 vs 14.58 on L4); v0.6.0: 15.21 s. |
| vllm#7592 chunked-prefill scheduler | **Direction reproduced.** v0.6.0 is about 10% faster (reporter: 14%), with fewer preemptions. Needs repeat runs. |
| vllm#6923 prefix-cache evictor | **Not reproduced** in two attempts (8B FP8 model; then a 1.5B model with 7× the KV blocks). Kept as a failed attempt. |

## Host findings

- **No Docker** inside the container.
- **`perf_event_paranoid = 4`:** Nsight Systems cannot do CPU sampling here, which affects the host-side cases.
- **Storage:** about 23 GB of disk and no persistent volume; results are copied back after each check.
- **Driver:** supports CUDA 13, so vllm#49013 is feasible on this host.
- **Dependencies:** every environment is pinned to its release date with `uv --exclude-newer`. `pyairports` is stubbed. v0.8.x cannot install (missing `xgrammar==0.1.16`).
- **Rebuilding:** [setup_case_env.sh](../cases/checks/setup_case_env.sh) recreates each environment.

## Scope of this step

About 1.5 L4 GPU-hours. No changes to the study instrument environment (`/workspace/envs/vllm`), the paper, the bib or the source.

## Next

1. Remaining candidates: #25418, #19732, #3087, #49013.
2. v0.5.2 confirmation for #6240.
3. Repeat runs for #7592.
