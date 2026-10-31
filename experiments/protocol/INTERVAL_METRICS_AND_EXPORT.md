# Interval statistics and initial-stop export — step 018

Implemented and checked on CPU. Counter inputs are hand-authored instrumented snapshots; exported stops come from actual executions of the existing CPU streaming controller with its fake backend. No GPU, calibrated classifier, real server histogram binding or phase instrumentation is added.

## Interval statistics

[The adapter](../tracing/interval_metrics.py) requires immutable typed snapshots with explicit sample, source instance, reset generation, series identity, observation/availability timestamps and mapped host clock domain. These are instrumented acquisition times, not HTTP receipt times relabeled as server timestamps. A real source adapter must establish this binding before use. This module is not a general Prometheus parser or an adapter to the pinned vLLM endpoint.

Wait snapshots declare cumulative classic histogram buckets in seconds, ending in +Inf with a matching total count. The adapter subtracts corresponding bucket counts for one source/generation and unchanged bucket schema, then estimates interval p95 using linear interpolation inside the selected finite bucket. The minimum-event setting is an explicit development guard (fixture default 1), not a calibrated statistical sufficiency threshold. The result is an estimate with bucket-resolution error, not an exact per-request percentile.

This follows the cumulative bucket model and interpolation convention described by [Prometheus metric types](https://prometheus.io/docs/concepts/metric_types/) and [histogram query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/). Unlike PromQL rate extrapolation/reset correction, this adapter directly differences two validated snapshots and rejects detected resets or incompatible intervals. If p95 falls in +Inf it returns unavailable, rather than manufacturing a finite bound.

A decreased counter, changed source/generation/schema, inconsistent cumulative deltas or insufficient interval observations returns an explicit unavailable metric. Repeated/out-of-order samples, invalid histograms, future availability or clock mismatch reject the input. A reset that catches up between samples cannot always be detected from counts; a trustworthy generation binding and endpoint validation remain necessary. Atomic/coherent source snapshots, correct metric semantics and observation completeness are source responsibilities, not proven by these dataclasses.

The observation cohort is queue-wait values recorded at **service admission between snapshots**. It is not all requests arriving during that interval, all completed requests, or requests still waiting. Pending waits can therefore be absent precisely during a backlog. The valid/attempted counts describe the supplied histogram cohort, not completeness against the request driver. This bias must remain visible during calibration and reference adjudication.

Prefill fraction requires explicit cumulative prefill/decode/other durations that partition attributed service time. No duration may decrease; zero attributed duration remains unavailable. Its denominator is summed attributed service duration, not GPU utilization or automatically device wall time. The source must validate exclusivity, phase ownership and flush timing. Gauges, prompt lengths, request duration and kernel names do not supply this attribution. `phase_unavailable` records the unsupported case explicitly.

`FeatureWindow.on_interval_metric` accepts only the two supported interval statistics, with an exact matching acquisition interval/domain and actual availability before window closure/deadline. Adjacent/misaligned/future/late/duplicate inputs fail; it never spreads histogram mass across arbitrary cheap windows. Without a matching supplied metric, the existing queue collector leaves it unavailable. No forward fill or post-closure feature rewrite is introduced.

## Initial-stop export

[The exporter](../evaluation/controller_export.py) accepts a finished controller snapshot, evidence-ID keyed measured observations and an explicit classifier version. It accepts no reference or expected-label input. Activation events must agree with the episode list and start timestamps. Every activated episode yields one initial stop; later reactivation decisions do not replace it. Open/incomplete episodes fail export.

A ready decision requires its original typed measured observation, matching capture/evidence identity, provenance, clock, readiness and decision visibility. Acquisition comes from that observation, not profiler-process duration. Concrete labels are retained as unmapped labels with an empty cause assertion set; this code does not validate or infer a cause mapping. Failure/censored stops retain an explicit null acquisition/evidence identity and cannot assert a diagnosis. The v2 scorer accepts this absence and reports reference-unavailable (`no_acquired_evidence`); it never invents an interval to obtain a favorable join.

Policy terminal reason and execution status remain separate. For example, a fixed-burst stop can coexist with capture failure, or budget exhaustion with timeout. Cancellation events identify startup/evidence timeout and horizon censoring; the export audit retains the original decision status and source capture. The saved controller snapshot retains all attempts, nonterminal failures and later reactivations, while the prediction file intentionally scores initial stops only. No detection recall or full incident census is established.

The offline CLI validates before creating a new output directory, saves predictions, wrapped controller snapshot, export audit and source/input hashes:

```bash
python3 -m experiments.scripts.export_initial_stops --help
python3 -m experiments.scripts.demo_interval_export --output /tmp/new_interval_export_demo
python3 -m unittest experiments.tests.test_interval_metrics_and_export -v
```

For an existing run, supply `--controller-snapshot` (the raw finished snapshot), `--observations` (JSON object keyed by evidence ID), `--run-id`, `--classifier-version` and a new `--output`. Reference locking/scoring remains a separate [evaluator workflow](LOCKED_REFERENCE_SCORING.md). The CLI does not retrieve measurements or validate a live host clock binding on behalf of the producer.

## Saved checks and next work

[The saved example](../examples/interval_export_demo/SUMMARY.json) covers unknown, budget exhaustion, launch failure, diagnosis failure, timeout, horizon cancellation, reactivation and healthy/no-activation. Seven initial stops across eight separate CPU cases are retained. Counter fixtures preserve raw inputs and illustrate valid wait estimation, reset/generation rejection, no observations, explicitly unavailable phases and an explicitly attributed synthetic phase fraction. None establishes a real prefill diagnosis or classifier effectiveness.

Step 019 implements [CPU source binding and arm persistence/export](ARM_COLLECTION_AND_EXPORT.md). Step 020 prepares [pinned-stack feasibility gates and read-only discovery](LIVE_FEASIBILITY.md). Next step 021 needs fresh L4 capability discovery; no automatic finished-request/admission or phase mapping is accepted. Keep absent phase attribution explicit. Then validate actual pinned-server metrics, source/reset semantics and per-range readiness on a GPU before calibration. The experiment protocol remains unfrozen.
