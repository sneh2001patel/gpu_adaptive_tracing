# Scheduler criteria and evaluator worksheet workflow — step 036

This workflow checks declarations, scope and evidence binding. It does not judge scientific adequacy, authenticate people, prove blinding or create/lock a reference. The classifier and calibration remain disabled. [Generated packet](../hardware/l4_20261028/scheduler_assessment_036/PACKET.json), [blank criteria](../hardware/l4_20261028/scheduler_assessment_036/CRITERIA.json), [blank worksheet](../hardware/l4_20261028/scheduler_assessment_036/REVIEW_TEMPLATE.json), [measurement limits](SCHEDULER_BOUND_ASSESSMENT.md).

## Prepared material

The packet is tied to the independently retained campaign and step-035 audit manifest digests. Both bundles are verified before preparation: 6,142 original campaign artifacts and three audit artifacts. Ninety-six cases identify the original ten-second consumer windows. The 3,932 catalog records identify exact bytes, source channels, evidence families and acquisition scope using the existing `ReferenceArtifact` and `Acquisition` contracts.

Evidence per case includes its recorded consumer gate, whole-job request receipts, wholly contained queue-metric acquisition brackets and the selected source probe where present. It does not synthesize a missing trace or intervention record. Raw evidence from a deliberately withheld window is evaluator-only context; it does not change the recorded consumer decision.

**Availability has two distinct meanings here.** Case intervals retain the original recorded consumer window and observation time. Catalog files receive a conservative availability bound at the original job's completed cleanup checkpoint. Their bytes were saved before cleanup, but some files contain full job history or wrappers written after a receipt. The worksheet therefore does not claim that complete files existed at earlier consumer deadlines. Actual receipt readiness remains in the unchanged step-035 audit and original metadata. Raw gate files have a whole-job acquisition interval; `gate_json_pointer` selects the relevant row for each case.

The packet depends on access to the original campaign/audit roots. It is not a self-contained blinded archive. Job names, roles and raw request IDs may reveal workload or policy information. Case IDs are stable worksheet handles, not a claim of anonymization. Assessor identity and actual blinding are left blank; any later declaration remains unauthenticated by this validator.

## 1. Complete a scientific-criteria proposal

Copy `CRITERIA.json` to a new proposal file. Keep its audit/campaign identities and the supported host scheduling measurand/cohort intact. Each of the fourteen choices needs:

- `value`: a finite numeric/count choice or a definition for normalization/reference agreement;
- `unit`: the explicitly declared unit in the template;
- `definition`: population/cohort, denominator, normalizer or statistical method as applicable;
- `rationale`: why that choice answers the intended research question.

Time/absolute precision entries use milliseconds; relative mismatch entries use their named fractions; boundary/work fractions lie in [0,1]; confidence lies in (0,1); counts must be positive integers. These are type/unit checks, not a judgment that any particular value is scientifically adequate. The percentile-precision entry uses an absolute millisecond target; a different statistical target or measurand needs a separately versioned contract rather than a silent unit change.

Fill `decision_provenance` with the actual decision author, UTC declaration ending in `Z`, rationale and a boolean statement of whether development data informed it. Existing development observations cannot become held-out confirmation by changing a status or declaration date. `confirmation_scope` remains `future_disjoint_collection_only`. The validator checks syntax/declarations, not their truth or whether a decision predated collection.

Declare classifier-input and independent-reference evidence families and explain their separation. An empty classifier-family list can explicitly describe a measurement-only proposal; it does not create a classifier. Reference planning must include a non-intervention channel. The same evidence family cannot serve as both input and independent reference. These family checks are necessary structural safeguards, not proof of causal independence or that future evidence exists.

All actual choices remain null in the saved step-036 criteria. The example numerical values in the synthetic contract fixture are arbitrary test inputs and must not be copied as study decisions.

## 2. Validate into a fresh directory

Use separately retained manifest digests and a new output path outside both input bundles:

```bash
python3 -m revision.scripts.prepare_scheduler_assessment \
  --campaign revision/hardware/l4_20261028/challenges_v2_001 \
  --audit revision/hardware/l4_20261028/scheduler_bounds_035 \
  --expected-campaign-manifest-sha256 d7243e5159c79fc0e704dcf693453a44af0393e25cda924cedb6d40f37f121db \
  --expected-audit-manifest-sha256 264f2d82a58bb0ac374b4c60277e377d423023cd9e3aeac27a5af304c72be7f2 \
  --criteria /path/to/criteria_proposal.json \
  --output /tmp/new_scheduler_criteria_validation
```

Omit `--criteria` to generate a blank proposal. Null entries produce `blocked_incomplete_criteria`; malformed values, wrong units, stale identities, extra fields and overlapping input/reference families are rejected. A complete declaration produces `complete_declarations_only_not_scientific_acceptance`. No threshold is applied to the existing campaign and no confirmation/refit is performed.

This also regenerates `REVIEW_TEMPLATE.json` against the exact proposal hash. Changing criteria invalidates an earlier worksheet; regenerate before assessing that new version. Preserve each proposal/output rather than overwriting its predecessors.

## 3. Fill the evaluator-only gap worksheet

Keep all 96 case rows. Partial work may retain null answers in unfinished rows; it remains blocked. For each reviewed case, record one allowed gap outcome (`unresolved` or `needs_more_evidence`), the six requested rationales, and unique allowed artifact IDs with purpose `context`, `limitation` or `candidate_reference`.

A candidate-reference link must belong to the declared independent reference family and channel, not an input family or a consumer-decision record. Whole-job files are permissible offline context; do not reinterpret their later data as earlier online evidence. Wrong-window artifacts, unknown IDs and repeated links/cases are rejected. References to shared whole-job files are scoped by their declared acquisition and explicit per-case selection.

Record the actual assessor identity, boolean blinding declaration, scope of that declaration, independence statement and limitations. Unblinded or single-assessor work must be described honestly. The software cannot verify those statements. Workload names, arrival rates, case phases, successful requests and zero queue points do not become labels.

Validate a supplied worksheet with `--review /path/to/worksheet.json` and the same `--criteria` into another fresh output. Missing criteria keep the workflow blocked even if all gap-review fields are filled. Completed structure produces `gap_review_structure_complete_not_adjudication`; supported/healthy/cause labels and truth-field injection remain prohibited. Original bytes and both input bundles are checked again.

## 4. Follow-up scientific decisions

The next task is to prepare a concrete, justified criteria proposal and prospective disjoint confirmation design for review, with explicit development-data influence. Do not invent an author's approval or an assessor's judgments. Independent adjudication must later satisfy the existing reference contracts and reference-store locking rules before scoring/calibration; this gap workflow has no reference-export shortcut.

The generated actual packet remains blocked for fourteen unset choices and missing assessor entries. No GPU is needed to prepare/review the proposal. Future changed-source live work still requires a new engineering snapshot; no hardware claim is created here.
