# Paired evidence assessment and scope — step 026

The step-025 paired pilot validates collection but is insufficient for calibration or causal reference labels. This CPU-only workflow audits the saved bytes, documents gaps, proposes a narrower research scope and validates reviewer input for gap tracking. It does not modify the classifier or create/lock references.

## Verified observations and limits

The saved audit verifies the source manifest and all 472 recorded artifact entries before reading the packet. It rechecks exact offered files, response bytes/usage, request IDs, worker/session/generation/clock scope of raw metrics and both trace databases. Optional `--expected-manifest-sha256` binds the audit to a separately retained manifest digest; otherwise integrity is conditional on the supplied manifest, not protection against an actor changing data and manifest together. Evidence paths reject traversal/symlinks and bound file size.

- All 64 sampled waiting gauges are zero, but these are receipt-assigned point samples. The largest gaps, including horizon edges, are roughly 0.50–0.52 seconds. This does not rule out queues between scrapes or certify healthy behavior.
- Every two-second window lacks a valid request p95: at most one request completes per window, below the existing two-completion development guard. Choosing a longer window after seeing the data would be a retrospective change, not prospective validation or evidence of percentile precision.
- Matched request IDs and actual token counts agree within pairs. The audit computes request-ID-aligned latency differences/ratios from raw receipt times rather than trusting precomputed packet latencies. With two requests per role and no prospectively specified tolerances, no run-equivalence verdict is justified.
- Both full traces reparse with expected worker/device coverage, and their control acknowledgements bracket playback. This does not create same-execution truth for the feature run, a per-request GPU/host clock map, losslessness guarantees or active capture boundaries.
- GPU utilization was not collected in this pilot. Finished-request wait histograms and request phase durations still do not supply admission-window waits or exclusive GPU phase fractions.

These are **retrospective evidence-gap findings**, not adjudicated causes, healthy references, contradiction labels or calibrated thresholds. The offline audit creates no new feature windows or online decisions.

## Draft scope and rubric

[RUBRIC_DRAFT.json](../examples/evidence_assessment/paired_001/RUBRIC_DRAFT.json) proposes evaluating **queue pressure only** initially; prefill diagnosis is deferred until exclusive phase attribution exists. Candidate features are request p95, completed requests/s and sampled queue depth, with actual token counts as workload context. GPU utilization is optional context pending collection validation; unsupported wait/phase values must never be substituted.

This is a proposal, not a new classifier version. The current classifier still abstains and its required-input contract is unchanged. A narrower classifier profile needs separate versioning, a frozen feature/coverage specification, independent references, calibration and held-out validation.

The rubric requests evidence for realized queue pressure and reversal using same-run independently clock-bound server admission/wait events, latency/throughput context and alternatives. Planned arrival rate or prompt band is not a cause label. Negative/healthy assertions require explicit cause scope and adequate observation coverage; zero gauge samples or HTTP success alone are insufficient. Separate full traces require actual work/mismatch assessment rather than assumed equivalence.

Prospective numerical limits remain **null**: maximum receipt gap, minimum completions per latency window, work/latency mismatch tolerances and independent repetitions. Set and justify them before the relevant collection/freeze, based on measurement semantics and a defensible precision target. Fitting numbers to these already observed small differences would not validate them. The rubric exports no reference and enables no threshold fitting.

## Review workflow

1. Generate a new audit, draft rubric and blank worksheet from the source packet:

```bash
python3 -m experiments.scripts.assess_paired_evidence --output /tmp/new_evidence_assessment
```

2. Review the audit, original raw artifacts and clock/cohort limits. `REVIEW_TEMPLATE.json` deliberately leaves assessor identity, actual blinding statement, outcomes and rationales blank. It records canonical JSON hashes of the audit and rubric; retain these versions together. No assessor action is inferred from opening/generating a worksheet.
3. For a completed **gap review**, supply assessor identity, an actual boolean blinding statement, single-assessor/unblinded limitations, and one response per pair. Each response links unique known artifacts from that pair and explains work mismatch, latency mismatch, negative-evidence limits, clock/cohort limits and additional evidence needed. Outcomes in this incomplete pilot are only `unresolved` or `needs_more_evidence`.
4. Validate a filled worksheet into a new directory:

```bash
python3 -m experiments.scripts.assess_paired_evidence --review /path/to/filled_review.json --output /tmp/new_gap_review_validation
```

The validator rejects blank identities/rationales, stale audit/rubric hashes, wrong/duplicate pair IDs, unknown/wrong-pair artifact links, extra truth fields and healthy/supported assertions. Acceptance confirms structure and binding only. It does not authenticate identity, prove actual blinding, assess rationale quality or create a `ReferenceRecord`.

5. Address evidence gaps with additional validated collection. Actual future cause adjudication must satisfy the existing reference contracts and criteria-linked corroboration, mismatch/blinding/limitations declarations, then lock through the reference store before scoring. This gap-review workflow intentionally has no reference-export shortcut.

The saved worksheet is blank; no human review or reference lock has occurred. [Saved report](../examples/evidence_assessment/REPORT.md).

## Subsequent instrumentation preparation and next step

Step 027 provides [opt-in pinned scheduler hooks and prospective engineering rules](SERVER_EVENT_INSTRUMENTATION.md). CPU checks cover bounded history, fresh source probes and delay uncertainty, but actual GPU startup and engine/client correlation remain unvalidated. First CPU scheduling is not GPU execution start; the existing wait/phase fields stay unavailable.

Next step 028 wires owned startup and commissions at most eight L4 requests before any challenging cases. Validate effective cache settings and real source/clock/ID mapping, then resolve observer controls, exact pressure selection/arrival files and scientific limits before further collection, adjudication or fitting. The earlier sparse pilot remains retrospectively insufficient for calibration.
