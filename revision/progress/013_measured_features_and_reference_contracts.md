# Step 013 — Measured features and independent reference contracts

Date: 2026-10-27. Status: complete for CPU interface implementation. No GPU or SSH access used. The experimental protocol remains unfrozen and live classification still abstains.

## Completed

- [x] Add immutable request/server/GPU/kernel observation contracts with exact input field sets, acquisition/availability timestamps, clock domains, identities and provenance.
- [x] Validate units/ranges, sample accounting and complete/partial/unavailable coverage. Keep observed zero distinct from missing evidence.
- [x] Reject future/unmapped evidence, premature bundle readiness, misaligned metrics, unsupported worker coverage and arbitrary nested input fields.
- [x] Implement an explicitly uncalibrated classifier adapter: measured-only input, null diagnosis/cause set and missing/partial/calibration reasons. Declare queue vocabulary correspondence and unresolved prefill mapping.
- [x] Add evaluator-only reference/artifact/criterion contracts, supported/healthy/unresolved outcomes, cause completeness, alternative explanations and assessor/blinding limitations.
- [x] Require criterion-linked corroborating channel declarations beyond injection logs; validate artifact hashes/paths/content, evidence/adjudication/declared-lock ordering and run/provenance joins. Matched traces identify a separate run and mismatch assessment.
- [x] Update the empty reference template and add a runnable synthetic CPU example. The classifier never receives its separate synthetic reference.
- [x] Add regression checks and update the contract guide, README, progress index and main revision plan.

## Implementation and validation

- [Measured contracts](../tracing/measured_evidence.py).
- [Uncalibrated adapter](../tracing/diagnosis.py).
- [Evaluator references](../evaluation/references.py).
- [Contract guide](../protocol/MEASURED_EVIDENCE_CONTRACT.md).
- [Tests](../tests/test_measured_contracts.py) and [synthetic demo](../scripts/demo_measured_evidence.py).
- [Saved synthetic prediction](../examples/measured_contract_demo/prediction.json) and [separate fixture reference](../examples/measured_contract_demo/evaluator_reference.json).

All **217 CPU-only tests pass**, including 22 new contract tests. The synthetic demo runs successfully and saved artifact content/record roundtrips verify. `git diff --check` passes. These tests demonstrate code invariants, not diagnosis correctness, reference quality or GPU timing validity. The unchanged shared policy engine reaches hard exhaustion rather than stability when unknown predictions persist across the synthetic queue change.

## Limits

No server endpoint, metric collector, input-token collector, timestamp-domain mapping, richer live-gate join, fitted classifier or new GPU result is implemented here. Acquisition coverage is distinct from sample adequacy. Report/device coverage, corroboration, blinding and lock metadata are declared inputs, not independently proven by a dataclass validator. Actual artifact bytes require explicit content verification. Durable reference locking and scored joins are not yet implemented. Synthetic references are intentionally labeled as fixtures.

The existing live runner remains an abstaining kernel-summary path. The new adapter needs measured request/server data aligned with kernel acquisition and actual availability before integration. Do not translate long input or kernel names into an unvalidated prefill/root-cause diagnosis.

## Next step — 014 (CPU-only)

1. Add measured request-token/completion feature extraction and a configured server-metric collector that reports unavailable/unsupported metrics explicitly. Validate against synthetic HTTP metric fixtures before GPU endpoint verification.
2. Align raw metrics and ready kernel evidence by acquisition interval/domain, honoring receipt/availability and missing data. Route only the typed measured bundle to the adapter; keep evaluator state separate.
3. Exercise the richer bridge with synthetic HTTP/server/profiler fixtures, including delayed reports, transitions, missing queue/prefill data and sparse completions.
4. Then add exact offered arrival files, unprofiled/cheap-only/reference arm ownership and reset checks, plus durable reference locking/scoring. Revisit GPU rental only after those collection paths are executable.
