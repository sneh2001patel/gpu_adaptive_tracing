# Step 020 — Feasibility harness and pinned metric capability gates

Date: 2026-10-28. Status: complete for CPU-tested gate contracts, scoped metric inspection and executable read-only live discovery. No GPU or SSH access used. Real owned reset/capture execution remains pending.

## Completed

- [x] Review/tag/archive the vLLM 0.10.2 V1 metric logger/statistics sources and record the finished-request cohort/clock distinctions.
- [x] Add scoped exact-model/engine metric inspection with duplicate/type/bucket/count/timestamp checks and retained reset/schema/missingness diagnostics.
- [x] Block unsupported admission-window wait and exclusive prefill-service mappings; do not supply concrete classifier labels or new feature values.
- [x] Define pinned inventory → metrics → independent quiet/reset → capture readiness/coverage → cleanup gates, with explicit receipts and dependent-stage blocking.
- [x] Add bounded adapter operations, shielded cleanup and retained interruption/failure results.
- [x] Implement a read-only local-host discovery adapter checking package/tool versions, selected device/compute PID, worker record, local revision config/hash, model label and raw endpoint samples.
- [x] Keep owned restart/barrier/capture operations unavailable in discovery. Separate discovery, synthetic gate mechanics, live feasibility and study readiness.
- [x] Save eight synthetic gate cases and test actual loopback discovery with mocked hardware inventory.
- [x] Update guide, progress tracker and CAIN revision plan; identify the next GPU dependency.

## Validation

All **375 CPU-only tests pass**, including **26 new checks**. Coverage includes scoped labels/engines, malformed/duplicate data, exact bounded counters, histogram resets/schema/missingness, hashes/path escapes, ordered worker reset/capture readiness, busy/cached barriers, pin/device/PID mismatch, deadline/cancellation cleanup, output preservation, confined model-config symlinks and local read-only HTTP discovery. No NVIDIA commands or GPU libraries are executed by the CPU tests; hardware inventory is mocked.

[Saved report](../examples/live_feasibility_demo/REPORT.md) and [summary](../examples/live_feasibility_demo/SUMMARY.json): eight synthetic cases. Only the positive case passes mechanics; every case keeps live feasibility and study readiness false. Discovery-only skips capture after unavailable activity evidence. The [saved audit](../examples/live_feasibility_demo/VALIDATION.json) verifies 87 artifact hashes and 540 source fingerprints, reviews 21 raw metric artifacts (including the deliberately bad digest case), and confirms cleanup was attempted in all cases. Primary-source snapshots, gate-call order and documentation links verify. CLI help and whitespace checks pass. The initial fixture demonstration is preserved separately; the final fixture also enforces the requested minimum host control-range duration, without treating it as GPU-active time.

[Inspector](../feasibility/metrics.py), [gate harness](../feasibility/harness.py), [read-only adapter](../feasibility/discovery.py), [CLI](../scripts/live_feasibility.py), [configuration](../configs/l4_feasibility_v1.json), [fixtures](../scripts/demo_live_feasibility.py), [tests](../tests/test_live_feasibility.py), [guide](../protocol/LIVE_FEASIBILITY.md), [reviewed primary sources](../protocol/sources/vllm_0_10_2/SOURCE_MANIFEST.json).

A subsequent full-suite run exposed an existing normal-exit sampler test using a 50 ms shutdown allowance. Its no-escalation assertion depended on host scheduling under load. That one success-path test now uses the production 500 ms default; production cleanup and the deliberate hung-worker deadlines are unchanged. The [failed-suite log](../examples/live_feasibility_demo/development_checks/sampler_50ms_timing_failure.log) is retained with [final test output](../examples/live_feasibility_demo/TEST_RESULTS.txt) and test-source fingerprints.

## Limits

The live discovery adapter assumes an already running local pinned server; it does not launch, own, restart or profile that server. Real worker barrier/reset/capture adapters still need implementation/validation. Local model-config hashes and served labels do not prove loaded weight identity. Worker/PID inventory does not establish source clock mapping, worker quiescence or causal evidence. Receipt verification is conditional on adapter observations and cannot prove hardware execution against fabricated records.

The pinned histograms describe finished-request observations, not the CPU fixture's admission cohort. Their presence cannot supply the existing wait/phase classifier contract. No new joint classifier, independent reference adjudication, GPU-active savings, operator benefit or empirical stopping result is established. The protocol remains unfrozen and historical artifacts are preserved.

## Next step — 021 (hardware discovery)

1. Obtain fresh L4 access and start/reproduce the pinned serving stack with explicit worker/device/model/source records.
2. Run the new read-only discovery command; retain raw metrics and all failed/unsupported gates.
3. Use actual capabilities to choose an honest cohort/clock mapping or narrow the diagnosis scope. Keep unsupported phase attribution unavailable.
4. Implement/validate the owned worker barrier/restart/activity adapter before one bounded live capture and serving-continuation check. Only afterward consider calibration and the revised matrix.

GPU access is now needed for the live discovery portion. Adapter preparation can continue on CPU while hardware is unavailable; no new GPU run is claimed here.
