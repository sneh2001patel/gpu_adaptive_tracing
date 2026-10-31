# Step 044: Case screen (first round)

Date: 2026-10-28.

## What was done

- Searched closed vLLM issues closed by a merged PR; 81 issues ([search_candidates.py](../cases/search_candidates.py)).
- Screened titles (60 excluded), then read 21 threads and their fix PRs in full.
- Found the before/after release for each fix.
- Recorded every decision in [screening.csv](../cases/screening.csv). Write-up: [SCREENING.md](../cases/SCREENING.md).

## Result

**7 candidates:** vllm#6240, #7619, #6923, #7592, #25418, #19732, #3087.

**2 possible:** #49013, which is blocked by the L4 driver (CUDA 13), and #15105, which was reported on 2 GPUs but may scale down.

## Observations

- **Decision gate (≥ 8 viable cases across ≥ 4 cause types):** borderline. More candidates are needed, because only about half are expected to reproduce.
- **Most candidates are host-side:** the cost is on the CPU (scheduler, preprocessing, grammar) rather than in GPU kernels. The diagnosis rules and references must therefore handle GPU idle gaps, not only kernel-time shifts.
- **L4 host constraints:** CUDA 12.8 driver, no Docker GPU passthrough. #6240 may need the official image's kernels.

## Scope of this step

GitHub API reads only. No GPU use, installs, or paper/bib/source changes.

## Next

1. On the L4 host: install checks and short before/after symptom checks for each candidate.
2. A second search frame (fix PR linked only in comments) to add candidates.
