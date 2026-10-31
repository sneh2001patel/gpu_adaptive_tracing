# Criterion and assessment worksheet contracts — step 036

Completed 2026-10-28 on CPU. [Workflow instructions](../../protocol/SCHEDULER_ASSESSMENT_WORKFLOW.md), [actual criteria](../../hardware/l4_20261028/scheduler_assessment_036/CRITERIA.json), [criteria status](../../hardware/l4_20261028/scheduler_assessment_036/CRITERIA_VALIDATION.json), [worksheet](../../hardware/l4_20261028/scheduler_assessment_036/REVIEW_TEMPLATE.json), [review status](../../hardware/l4_20261028/scheduler_assessment_036/REVIEW_VALIDATION.json).

## Delivered

- A strict declaration contract for fourteen scientific choices, with explicit units, definitions, rationale, author/time/development-data provenance and input/reference-family separation.
- A deterministic evaluator-only packet for **96 windows**, with **3,932 typed artifact records**, after verifying **6,142 campaign artifacts and three audit artifacts** against retained manifest digests.
- Blank actual criteria and worksheet, validation results, fresh-output CLI and an explicitly synthetic contract fixture. The real criteria have fourteen null values and **49 missing completion fields** including definitions, rationales and provenance. The blank worksheet has **773 pending fields** across its 96 cases and assessor declarations.
- Structural checks for scope/version/hash changes, type/unit errors, nonfinite/boolean values, unknown/duplicate/wrong-window links, reference/input reuse, undeclared reference channels and attempted supported/healthy/cause labels.
- Reuse of existing `Bundle`, `Acquisition`, `ReferenceArtifact` and independent-channel contracts. No `ReferenceRecord`, store lock, scoring input, classifier profile or calibration is produced.

Both actual gates remain blocked. Complete synthetic declarations demonstrate only schema validation; they do not make numerical limits adequate, authenticate provenance, prove assessor blinding, validate a causal reference or confirm the observed campaign. All actual assessor entries remain null. The arbitrary values in [CONTRACT_FIXTURE.json](CONTRACT_FIXTURE.json) are test data, not scientific proposals.

## Evidence scope and availability

The packet discloses job/policy/workload metadata and requires access to original source roots. It is not a blinded or self-contained evidence export. Its stable window IDs do not establish anonymization. Whole-job request and gate files, raw queue receipts and selected source probes are explicitly offline assessment material.

Catalog availability is conservatively bounded by each original job's completed cleanup checkpoint, rather than backdating full file availability to an earlier logical observation. Case intervals separately preserve the recorded window/owner observation; original receipt readiness remains in the step-035 audit. Whole-job file intervals and the gate-row selector make future-in-file context visible. Withheld evidence remains absent from the original consumer decision even when an assessor can inspect it offline.

## Verification

New synthetic tests exercise blank and complete declarations, invalid units/numbers/provenance, input/reference overlap, intervention-only references, stale packet/criteria hashes, partial assessments, case/link scope, prohibited labels, conservative saved-file availability and fresh output. Complete worksheets remain gap records with all authentication/scientific/export flags false. Existing paired gap-review checks also run. Full test counts and original-data preservation fingerprints are recorded in [validation/CHECKS.json](validation/CHECKS.json).

All **34 focused tests pass**, including **eighteen new tests**, which also pass in both full runs. Full-suite clearance remains unresolved: the first 597-test run has five failures/one error in older timing-based checks; those six checks pass in isolation. The retry runs 597 tests with twelve failures/two errors in older timing-based checks. Host load averages rise from above sixteen to about eighty-nine, and loop scheduling warnings show substantial delays. These observations support a timing sensitivity concern; they do not establish that every broader-suite failure is harmless. Both full logs, the isolated checks and host-load evidence are retained. All 136 previously recorded source/configuration files remain unchanged; no existing runtime, test or GPU guard is edited. A clean broad regression run is required before creating a new deployment snapshot.

No runtime policy, GPU setting or existing source artifact is edited. No SSH/GPU activity or rental-state recheck occurs. The original successful development campaign, failed v1 attempt, snapshots/backups, prior provenance index and step-035 audit remain unchanged. Hardware confirmation of the earlier quiet-log fix remains pending; no new engineering snapshot is created.

## Next — step 037, CPU-only scientific proposal

Prepare a concrete criteria proposal with justified precision/coverage, statistical sampling, observer/work mismatch and repetition choices, plus a prospective disjoint confirmation design. Declare the influence of development observations and distinguish proposed decisions from actual author/assessor input. Use the new validator to make missing decisions reviewable. Keep the original criteria/worksheet blank and preserve them as the step-036 starting point; do not invent approval, adjudication or reference labels. No GPU is needed to prepare that proposal.

Recheck the full CPU suite on a responsive host before any new engineering freeze. The focused workflow validation and preserved artifacts do not replace that outstanding regression gate.
