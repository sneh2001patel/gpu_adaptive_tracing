# CPU arm collection, persistence and export — step 019

Implemented on owned CPU subprocess/HTTP fixtures only. This binds step-018 interval contracts to a concrete acquisition source and the arm runner. It does not bind to vLLM, NVML or a GPU clock; synthetic kernel/device reports remain synthetic.

## Source acquisition and receipt

The fake target optionally records actual queue-entry and service-admission timestamps around its semaphore. Queue wait is the difference in `time.monotonic_ns()` on that target. Its bounded history stores at most 10,000 admission observations per reset generation; overflow makes interval history unavailable. Reset clears history and advances its epoch/generation only after the independent quiet/reset protocol succeeds.

Only cheap-sampling arms enable this additional event recording. `no_profiler` neither records this history nor opens a collector/sampler/capture backend. The other seven arms use the same recording contract. These are CPU instrumentation distinctions, not measured GPU profiling overhead baselines.

[The collector](../tracing/cpu_interval_collection.py) is restricted to an owned CPU target. Before collection, it checks a target clock probe against the parent's request/receipt bracket, declared clock implementation/domain, instance/PID/nonce and generation. This is a bounded same-host process binding for the fixture. It is not a remote clock synchronization protocol or proof of GPU timestamps. A reset invalidates the binding until it is renewed.

After each window ends, the collector requests **as-of** cumulative histograms at the exact start/end boundaries. The target reconstructs them from its admission history, using `admitted_at < boundary`, so differencing gives the half-open admission cohort. These are historical prefix queries made online after the interval, not instantaneous HTTP scrapes relabeled with convenient timestamps. A normal Prometheus endpoint cannot be assumed to support this interface. Queries before the generation epoch, beyond source time, or with incomplete history fail explicitly.

The response retains boundary times, epoch, source collection time, cumulative counts, bucket schema, generation, clock identity and explicit lack of phase instrumentation. The parent saves raw response bytes as text, their SHA-256, request/receipt times and errors. Result availability is after parsing. Malformed/missing, foreign-clock/generation and overflow responses produce unavailable wait metrics; counter decreases produce the step-018 reset outcome. None becomes a healthy zero. Phase attribution is always unavailable in this fixture.

## Serialized window integration

`SchedulePlayback` optionally owns one sequential interval-collection task and a bounded receipt queue. Network work yields to request admission/controller servicing. The serialized owner consumes interval receipts before closing windows. Only exact-domain, exact-interval, already available metrics received before the closure deadline enter a feature window.

Late/rejected/timeout receipts remain in `playback.interval_records`; the source retains its raw receipt audit as well. They cannot rewrite closed windows. The final interval may finish during the window's grace/drain period, but the policy controller still ends at its observation horizon. Cancellation drains/cancels the owned task and preserves aborted results. Collection timeout, task counts and source errors are explicit. Source waits exclude requests still queued, and complete histogram cohort counts do not establish completeness of all offered requests.

## Measured observations and initial stops

[The runner](../tracing/experiment_arms.py) persists closed cheap observations separately from ready capture observations. A triggering cheap window can end before a capture begins. The runner therefore never reassigns that window's measurements to the capture's interval. Capture observations currently contain the synthetic kernel fixture and its explicit host acquisition range, with no matched request/server feature metrics. The uncalibrated measured classifier reports missing metrics/calibration and abstains. Full combined T2 classification remains pending.

Capture acquisition begins after the start acknowledgement and ends after the stop/report reply. It includes control/report time and is not GPU capture-active time. Device/worker identity, ready time and original observation identity are checked before classification and export. Continuous reference captures produce measured fixture observations without policy predictions.

Each finalized policy arm automatically exports one initial stop per activated episode via the offline evaluator export interface. Controls/reference arms save `applicable: false`; their absence of a policy controller is not a fabricated zero-episode policy result. References and expected labels are never passed to the classifier. An export/persistence error fails the arm while retaining cleanup/raw results; it is not silently accepted.

Real-clock integration exposed separate episode/event activation reads. The controller now uses the event's timestamp as the authoritative episode start, preserving strict export equality. Synthetic/manual-clock checks had not exposed the nanosecond discrepancy. Development failure logs are retained beside final validation artifacts.

## Saved outputs and checks

Each arm saves:

- `interval_source.json`: bound source, raw replies/hashes, request/receipt times and errors (only instrumented arms).
- `cheap_observations.json`, `measured_observations.json`, `measured_predictions.json`: separate acquisition scopes and abstention reasons.
- `evaluation/`: initial stops, wrapped controller snapshot and audit for policy arms; explicit applicability status for all arms.
- `results.json`, timing events, source fingerprints and a final `artifact_manifest.json` of saved file hashes after owned-target cleanup.

The manifest detects changes relative to its retained digest declarations; it is not administrator-proof storage or an adjudicated reference lock. Active GPU and fully persisted lifecycle durations remain unknown. Historical paper/L4 outputs and earlier saved demonstrations are preserved.

```bash
python3 -m experiments.scripts.demo_arm_collection_export --output /tmp/new_cpu_arm_collection_demo
python3 -m unittest experiments.tests.test_arm_collection_export -v
python3 -m experiments.scripts.snapshot_server_metrics --help
```

[The saved report](../examples/arm_collection_export_demo/REPORT.md) covers all eight arms under the same offered/comparison contract and six source fault cases. Saved source and artifact hashes, ownership cleanup, unavailable phases and initial-stop counts are audited.

## Next feasibility work

A read-only executable probe is ready for a later pinned server:

```bash
python3 -m experiments.scripts.snapshot_server_metrics \
  --endpoint http://127.0.0.1:8080/metrics \
  --output /tmp/new_server_metric_snapshots --samples 3 --interval-s 1
```

It saves bounded raw HTTP responses, status, hashes, parent timestamps and declared TYPE-line inventory. It performs no clock mapping, interval-feature derivation, phase inference or diagnosis. The saved CPU probe sees only the fixture queue gauge; TYPE declarations are hints, not validated semantics. Pair later hardware probes with exact package/model/device/worker identity records. The earlier L4 stack pinned vLLM 0.10.2; reproducing it still requires checking the actual rental environment.

Step 020 adds [gated feasibility contracts and scoped discovery](LIVE_FEASIBILITY.md). Next step 021 runs read-only capability discovery on a fresh L4. GPU access is required to execute the eventual metric/worker/reset/readiness pilot and collect calibration; it is not needed to prepare the harness. Do not treat the old engineering pilot runner as the complete revised experiment runner, or freeze the protocol before these checks succeed.
