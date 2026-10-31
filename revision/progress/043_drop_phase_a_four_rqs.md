# Step 043: Drop Phase A; four empirical RQs

Date: 2026-10-28.

## Decision

The author decided to drop Phase A (systematic issue mining).

Reasons:
- **Time:** the author has limited time for it.
- **No second human coder,** so a reliable taxonomy is not possible.
- **Off-topic:** the pilot showed that general LLM-serving performance issues rarely involve GPU profiling (profiler evidence in 4 of 20 included issues). A full taxonomy would mostly not be about GPU profiling.

## What changed

[EMPIRICAL_STUDY_PROPOSAL.md](../protocol/EMPIRICAL_STUDY_PROPOSAL.md) has been rewritten. The step-038 version is preserved as `EMPIRICAL_STUDY_PROPOSAL_step038.md`.

- **Four RQs, ordered as a funnel:**
  1. when cheap telemetry is enough;
  2. how much heavy profiling is enough;
  3. whether adaptive stopping rules find that amount, and when they fail;
  4. whether the findings hold across thresholds, held-out workloads and a second GPU.
- **Empirical framing kept throughout:**
  - the tracer is the instrument, and the stopping rules are the treatments;
  - each RQ maps to possible findings and the implication each informs (§3.2);
  - the "solution" is evidence-based guidance derived from the findings (§8). The tracer is configured from that guidance on calibration cases and evaluated once on held-out cases, as a demonstration, not as a novel controller.
- **Cases:** GitHub issues are still the source of reproducible cases. They are screened for reproducibility only, with no taxonomy coding; vllm#6240 is the first candidate.
- **Motivation:** comes from published issue studies (Liu et al., Cao et al.) instead of our own mining.
- **Blinded assessor:** made optional, because none is available. References rest on upstream-confirmed causes and external analysis tools.
- **Comparators:** repetition-sampling (ICS '22) and retroactive-window comparators added to the arms table.
- **Phase A pilot:** archived (§12) and not cited as a result.

## Scope of this step

Planning only. No GPU use, paper, bib or source changes.

## Next

Case screen (§10 step 2): check vllm#6240 for reproduction on an L4, then run targeted searches for further candidates with merged fix PRs.
