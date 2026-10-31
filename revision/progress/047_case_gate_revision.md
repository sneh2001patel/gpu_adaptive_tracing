# Step 047: Case gate revised; real-case search stopped

Date: 2026-10-29. Author decision after step 046 (5 accepted cases).

## Changes to [EMPIRICAL_STUDY_PROPOSAL.md](../protocol/EMPIRICAL_STUDY_PROPOSAL.md)

1. **Stop at 5 real cases** (§4.1): vllm#6240, #7619, #3087, #25418, #19732. No further search frames.
2. **vllm#7592:** confirm with ≥ 5 blocks per release (v0.5.5 vs v0.6.0). Accept it if the paired 95% CI excludes zero; otherwise record it as failed (§10 step 2b).
3. **Gate revised** from "≥ 8 reproduced across ≥ 4 types" to "≥ 5 reproduced real issues plus the §4.2 controlled cases, ≥ 4 cause types overall".
   - Rationale: the case count serves realism and cause-type coverage; statistical precision comes from repeated blocks.
   - The threats section now states the limitation: one kernel-level case, per-case reporting, deviations, and the inert fix in vllm#25418.
4. **Next main work:** the feasibility pilot (§10 step 5).
   - §10 step 6 is now "integrate the accepted cases into the instrument's workload driver".
   - The §2 review-response row is updated to "5 (6) real + 6 controlled cases".

## Scope of this step

Proposal text only. No GPU use, paper, bib or source changes.
