# Step 017 — Locked references and offline initial-stop scoring

Date: 2026-10-27. Status: complete for CPU fixture implementation/validation. No GPU or SSH access used.

## Completed

- [x] Separate reference-only locking from prediction reading and offline joins.
- [x] Verify and snapshot evidence bytes, rubric and adjudicated records into content-addressed storage; commit an exclusive durable lock manifest last.
- [x] Preserve an external digest anchor, read-only objects and old versions; reverify every hash on load and reject mismatched run/provenance/clock joins.
- [x] Support bounded-memory raw evidence copying, with explicit file-size limits.
- [x] Require exactly one initial-stop record per logged activated episode, retaining unknown/failure/budget/censoring outcomes.
- [x] Score supported complete/partial, unsupported, unresolved and unavailable separately, including transition/gap and incomplete-reference counterexamples.
- [x] Retain input/scorer hashes, explicit cause assertions and classifier/mapping versions without adding reference data to classifier inputs.
- [x] Save synthetic example, tests, guide and updated progress/CAIN plan.

## Files and validation

[Reference store](../evaluation/reference_store.py), [scorer](../evaluation/scoring.py), [separate lock/score CLI](../scripts/reference_eval.py), [fixture generator](../scripts/demo_reference_scoring.py), [tests](../tests/test_locked_reference_scoring.py), [guide](../protocol/LOCKED_REFERENCE_SCORING.md).

All **305 CPU-only tests pass**, including **23 new checks**. Coverage includes hash tampering/missing objects/symlinks, concurrent object publication, source changes, preserved correction versions, a raw artifact above the metadata size limit, invalid clocks/rubrics/intervals, validation before prediction file opening, strict prediction schema, episode denominator conservation, reference incompleteness and separate CLI phases.

The [saved report](../examples/reference_scoring_demo/REPORT.md) and [score](../examples/reference_scoring_demo/SCORE.json) retain 12 hand-authored stops against synthetic references: 1 supported complete, 1 partial, 2 unsupported, 3 unresolved and 5 unavailable. Seven are reference-adjudicable. Stable-stop counterexamples include 2 unsupported, 1 incomplete and 3 unadjudicable cases. These are scorer checks, not measurements of a deployed diagnosis. Source fingerprints, stored hashes, score inputs and documentation links are verified; `git diff --check` passes.

## Limits

A retained anchor detects altered content but is not administrator-proof storage. Assessor identities, blinding and evidence independence remain declarations; durable snapshots do not establish causal truth. The demo explicitly declares synthetic unblinded assessment. The CLI accepts synthetic clocks only; a real evaluator must validate the run's monotonic clock/domain binding. Matching the hashed activation snapshot does not establish a full incident census or detection recall.

The deployed classifier still abstains. Actual initial-stop export from the streaming controller, validated policy-label/cause mapping, interval wait/prefill instrumentation, GPU reset/metric feasibility and independent adjudication remain pending. No new GPU costs, safety, operator benefit, classifier accuracy or empirical contribution is claimed. Historical paper and L4 results are preserved.

## Next step — 018 (CPU-only)

1. Add interval wait-histogram delta adapters with coverage, reset, missingness and evidence-availability checks using saved CPU fixtures.
2. Represent phase-attribution availability explicitly; do not infer prefill/decode dominance from queue gauges or prompt names.
3. Connect initial-stop/controller export to the evaluator schema without introducing reference inputs or dropping failures.
4. Validate the adapter/export contracts on CPU, then list the actual pinned-server metric and GPU calibration checks still required before renting again.
