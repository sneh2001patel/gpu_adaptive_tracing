# Step 026 — evidence assessment, draft rubric and narrower scope

Completed: 2026-10-28. CPU-only retrospective inspection and workflow implementation; no SSH or new GPU activity.

## Completed checklist

- [x] Verify the step-025 packet and all 472 source artifact hashes, with bounded paths/files and optional separately retained manifest identity.
- [x] Recompute request-ID-aligned actual work/latency comparisons from raw responses and receipts, without trusting precomputed packet latencies.
- [x] Audit all 64 raw metric receipts, clock/session/worker scope, 16 typed windows, point-sample gaps and missing metrics.
- [x] Reparse both SQLite traces and check playback control bracketing while retaining missing per-request GPU clock mapping and active capture time.
- [x] Draft explicit queue-support, negative/healthy, matched-trace, phase-claim and assessor/rationale criteria; leave prospective numerical limits unset.
- [x] Propose a separately versioned queue-pressure-only candidate feature profile, deferring prefill claims and leaving the current classifier unchanged.
- [x] Implement hash-bound blank gap-review templates and validation that cannot create healthy/supported labels, reference records or locks.
- [x] Pass 467 CPU tests, including 16 new integrity, sparse evidence, trace/mismatch, reviewer binding and anti-promotion checks.
- [x] Save the audit/rubric/worksheet and update progress and the CAIN revision plan.

## Implementation and artifacts

[Assessment module](../evaluation/evidence_assessment.py), [CLI](../scripts/assess_paired_evidence.py), [operating instructions](../protocol/EVIDENCE_ASSESSMENT.md), [saved report](../examples/evidence_assessment/REPORT.md), [audit](../examples/evidence_assessment/paired_001/AUDIT.json), [draft rubric](../examples/evidence_assessment/paired_001/RUBRIC_DRAFT.json), [blank worksheet](../examples/evidence_assessment/paired_001/REVIEW_TEMPLATE.json).

The audit independently verifies existing bytes, joins requests by ID, checks actual response usage and computes trace-minus-feature latency differences. For short prompts those differences are 11.110084 and 2.948201 ms; for long prompts, 6.240873 and 8.212704 ms. There are only two observations per role and no prospectively specified tolerance/repetition rule, so **no run-equivalence or perturbation verdict is issued**. Actual IDs/token work agree, but equal offered/completed work is not equal execution behavior.

All 64 sampled waiting gauges are zero; maximum receipt gaps including horizon edges are approximately 518.416/503.957/503.425/503.001 ms across jobs 0–3. These are point samples without server-event clock mapping. **No continuous absence of queues or healthy reference is inferred.** All 16 windows lack valid request p95 because they have fewer than two successful completions. GPU utilization, admission-window wait and exclusive GPU phase features also remain unavailable. Both traces reparse at 21,308/23,044 kernels on the expected workers/GPU, but cannot supply same-execution truth for their paired feature runs.

The proposed initial scope is queue pressure only, with request p95, completed requests/s and sampled queue depth as candidate features and actual token counts as context. This proposal is not a new classifier or a calibrated input contract. Prefill diagnosis is deferred pending exclusive phase attribution. The current classifier remains uncalibrated/unchanged. No default numeric mismatch, cadence or sample-precision tolerance is fitted to already observed data.

The worksheet binds canonical audit/rubric digests but leaves identity, actual blinding statement and review outcomes blank. A filled gap review must provide pair-specific artifact links and all rationales/limitations. Only unresolved/needs-more-evidence outcomes are accepted for this incomplete pilot. Validation checks structure/binding, not identity authenticity, actual blinding or scientific rationale quality. **Zero references are created/locked; reference export, calibration and freeze remain disabled.**

## Validation and limits

All **467 CPU tests pass**, including **16 new checks**. The tests cover manifest/tampering/path/symlink rejection, raw evidence inspection and trace reparsing, no healthy/equivalence inference, unset rubric limits, unstarted worksheets, stale versions, missing identities/blinding/rationales, wrong-pair/duplicate artifact links and rejection of fabricated cause assertions. Synthetic completed forms exist only in tests; no completed human review is saved.

The saved output manifest binds the audit, rubric, worksheet and source snapshot. Original hardware artifacts/source archives are unchanged; this step adds no measurements, feature windows or online decisions. Hash checks are conditional on the retained source manifest, not administrator-proof provenance. The collection pilot is retrospective and lacks challenging incidents/recovery, independent event attribution, prospective scientific tolerances, adequate latency samples and actual reference adjudication. No diagnostic accuracy, stopping effectiveness, savings or operator benefit is claimed.

## Next step — 027

1. Prepare and CPU-test pinned-stack server admission/first-service/completion event instrumentation, with explicit event IDs, instance/generation/clock binding and dropped-event accounting.
2. Specify prospective coverage/window/sample-volume/mismatch rules and bounded offered-rate ramp/removal/recovery, temporary lull/recurrence and unresolved controls, with actual corpus hashes and cache policy.
3. Validate source mapping and realized challenging cases in a subsequent bounded L4 pilot before adjudication/locking or fitting. Do not substitute finished-request histograms for admission windows or start the main study.

CPU implementation can proceed next. No GPU job or rental-state change was made in this step; the rental was left running after step 025.
