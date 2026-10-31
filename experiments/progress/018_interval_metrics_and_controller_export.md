# Step 018 — Interval metric adapters and controller initial-stop export

Date: 2026-10-27. Status: complete for CPU adapters/export contracts and fixture validation. No GPU or SSH access used.

## Completed

- [x] Add typed cumulative wait-histogram snapshots and interval p95 estimation, with explicit cohort, units, source/generation identity and acquisition/availability.
- [x] Reject malformed/future/unmapped input; mark resets, incompatible deltas/schema, no observations and infinite-bucket quantiles unavailable.
- [x] Add explicit exclusive phase-duration counter fractions and an unsupported-phase representation; infer no phase dominance from gauges or workload names.
- [x] Accept measured interval statistics into exactly matching open feature windows, preserving missingness and rejecting late/duplicate/misaligned inputs.
- [x] Export one initial stop per activated episode from actual finalized CPU controller snapshots, preserving first stops across reactivation.
- [x] Verify original measured observations for ready decisions; retain null evidence acquisition for failed/censored stops, alongside distinct policy reasons and execution statuses.
- [x] Add a separate offline export CLI with saved source/input hashes, controller snapshot and audit. Keep reference locking and scoring separate.
- [x] Extend scoring to v2 for absent acquisitions and independent failure/policy outcomes; preserve historical v1 saved scores.
- [x] Save fixtures and update guide, progress tracker and CAIN plan.

## Validation

All **332 CPU-only tests pass**, including **27 new interval/export tests**. Checks cover histogram delta quantiles, minimum-event guards, infinite buckets, reset/source/schema changes, malformed/missing/future data, exclusive phase partitions, exact-window acceptance, timeout/failure/censor preservation, first-stop selection after reactivation, observation identity/readiness and scoring joins against locked synthetic references.

[Saved example](../examples/interval_export_demo/SUMMARY.json): eight independent CPU cases, seven initial stops, zero activated healthy episodes. Unknown/budget rows have measured fixture acquisition intervals; launch/diagnosis/timeout/horizon failures have no invented acquisition. A reactivated episode still exports its first stop only. The offline CLI round trip, raw counter fixtures, saved source/input hashes, documentation links and whitespace checks pass.

[Adapters](../tracing/interval_metrics.py), [feature windows](../tracing/feature_collection.py), [exporter](../evaluation/controller_export.py), [CLI](../scripts/export_initial_stops.py), [v2 scorer](../evaluation/scoring.py), [demo](../scripts/demo_interval_export.py), [tests](../tests/test_interval_metrics_and_export.py), [guide](../protocol/INTERVAL_METRICS_AND_EXPORT.md).

## Limits

Typed snapshots do not establish atomic collection, correct host clock mapping, independent causal evidence or reset-generation authority. Between-sample resets can be hidden by catch-up. Histogram p95 is a bucket-interpolated estimate for admission-time observations; it excludes requests still queued. Phase fraction requires genuinely instrumented, exclusive attributed service durations; real availability remains unknown. The supplied minimum count is a development guard, not a calibrated sufficiency threshold.

The exporter leaves cause sets empty and the deployed classifier still abstains. It does not supply a full incident census or detection recall. Actual acquisition/receipt collection and arm-runner persistence still need binding; no live vLLM metric support, calibrated diagnosis, GPU cost, independent adjudication, operator benefit or stopping safety is claimed. Historical paper/L4 artifacts and step-017 v1 scores are preserved.

## Next step — 019 (CPU preparation)

1. Bind acquisition and receipt contracts to a CPU collection source, saving raw snapshots and identity/generation/availability evidence.
2. Wire interval metrics and measured observation persistence into the CPU arm-runner export path, keeping unsupported attribution explicit.
3. Validate missing/reset/late data end to end and prepare an executable pinned-server metric/GPU feasibility check.
4. Request GPU access when real metric semantics, worker/reset readiness and calibration collection need hardware validation; do not freeze the study beforehand.
