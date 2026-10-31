# Step 041: Phase A issue-mining pilot

Date: 2026-10-28.

## What was done

- Checked the vLLM and SGLang labels; both have `performance`.
- Retrieved the closed `performance`-labelled frames: 480 vLLM issues and 43 SGLang issues.
- Extracted the Liu et al. "Abnormal Performance" subset: 53 rows, 16 of them vLLM.
- Wrote codebook v0.
- Drew a seeded, stratified sample of 30 issues and fetched each full thread.
- Coded all 30 as a single coder.
- Reported feasibility signals and codebook v1 changes.
- Everything is in [experiments/phase_a/](../phase_a/); see the [pilot report](../phase_a/PILOT_REPORT.md).

## Feasibility signals

These are from a single coder and 30 issues; they are not results.

- **Noisy labels:** 20 of 30 issues included.
- **Stale closures:** about two-thirds of vLLM performance issues are stale-closed (322 of 480 carry `stale`).
- **Disjoint frames:** the Liu et al. performance subset does not overlap the `performance` frame at all (0 of 16).
- **Profiler evidence is rare:** present in 4 of 20 included issues and decisive in 2. Benchmarks, bisecting, logs and code reading dominate.
- **Confirmed causes:** 11 of 20 have one.
- **Multi-GPU settings:** 11 of 20.
- **Phase B candidates:** 1 clear (vllm#6240, FP8 on Ada, single GPU, version toggle) and 5 maybes. Reproduction needs targeted screening.

## Scope of this step

CPU and GitHub API only. No GPU use. No change to the paper, bib, source code or tests. Issue text was treated as untrusted data; one spam comment was ignored.

## Next

- Second coder on the same 30 with codebook v1, then κ.
- Extend the frame with performance-keyword `bug` issues.
- Run a targeted Phase B screen starting from vllm#6240.
