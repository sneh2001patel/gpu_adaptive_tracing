# Measured evidence and evaluator references — step 013

Version: `measured_evidence_v1`. These CPU contracts are implemented. Step 014 adds [response-usage/queue-gauge collectors, feature aggregation and temporal joins](FEATURE_COLLECTION.md), tested on local fixtures. Interval wait/prefill instrumentation, calibrated diagnoses and live-controller integration remain pending. No new GPU measurements were collected.

## Controller-visible observations

[measured_evidence.py](../tracing/measured_evidence.py) provides immutable `Acquisition`, `MeasuredMetric`, `KernelObservation` and `MeasuredObservation` records. JSON parsing accepts exact field sets at every level: unknown fields, including scenario/reference labels and intervention schedules, are rejected rather than forwarded.

Each acquisition includes `start_ns`, `end_ns`, `available_at_ns` and `clock_domain`. Acquisition must precede availability. Classification must occur at or after bundle availability in the same clock domain. Bundle availability must include all its metric/kernel availability times. Host acquisition intervals are not device capture-active intervals; do not subtract timestamps from a different device/profiler domain without an independently validated mapping.

| Measured field | Source | Unit |
|---|---|---|
| `request_p95_ms` | Request observations | ms |
| `completed_rps` | Request observations | requests/s |
| `prompt_tokens_mean`, `output_tokens_mean` | Actual observed request tokens | tokens |
| `queue_depth_mean` | Server diagnostics | requests |
| `request_wait_p95_ms` | Server diagnostics | ms |
| `prefill_service_fraction` | Server phase attribution | fraction |
| `gpu_util_mean` | GPU telemetry | percent |

The metric/source/unit combinations are fixed. A metric includes valid and attempted sample counts, coverage (`complete`, `partial`, `unavailable`) and an explicit missing reason for null values. Missing measurements cannot claim valid samples; measured zero remains distinct from missing. Complete coverage describes acquisition accounting, not statistical precision or independent samples. Minimum counts and adequacy thresholds must be calibrated separately. No sparse-window p95 rule is silently added to the existing aggregator.

All scalar metrics belong to the same acquisition interval/domain; kernel acquisition must lie within it. Joining adjacent windows, stale values or a delayed kernel to unrelated measurements is rejected. A future collector must aggregate the intended common interval or report missing evidence; these classes do not automatically align streams. Explicit availability may be later than acquisition end because parsing/export takes time.

Kernel records require a capture/evidence ID, physical GPU UUID, one worker PID, positive actual kernel count/time sum and the existing verified single-worker coverage designation. Coverage is a producer assertion until validated against the actual report; the schema does not inspect a GPU. Kernel names are not classifier features. Overlapping kernel-time sums are not capture-active time or device busy fraction.

Use `MeasuredObservation.from_dict(...)` at the input boundary. Direct typed construction also validates invariants. Both a raw dictionary and an evaluator `ReferenceRecord` are rejected by the classifier adapter. Opaque observation/evidence IDs serve audit identity only and do not enter a fitted model here.

## Deliberately uncalibrated classifier

[diagnosis.py](../tracing/diagnosis.py) implements `UncalibratedClassifier.classify(observation, now_ns=..., clock_domain=...)`. It checks evidence visibility and emits a `DiagnosisResult` containing audit identities, provenance, availability/decision times, null policy label, an empty cause set and explicit reasons.

It **always abstains**, including for complete synthetic input. Missing and partial metrics/kernel evidence are listed; no confidence score or threshold is invented. `queue_pressure` has an explicit vocabulary correspondence to `vllm_queue_pressure`, without automatically emitting that label. `prefill_dominated_service` has no validated policy mapping; a long prompt alone cannot justify one. A future calibrated adapter must version its feature requirements, thresholds and vocabulary mapping.

This adapter does not yet replace the live runner's `lambda summary: None`. The current evidence gate consumes kernel-summary dictionaries; integrating the richer observations requires measured request/server collectors and an explicit interval/availability join. No existing GPU pilot is reinterpreted as using this new adapter.

## Evaluator-only reference records

[references.py](../evaluation/references.py) is separate from classifier code. It defines `ReferenceArtifact`, `ReferenceCriterion` and `ReferenceRecord`. The classifier does not import it. JSON fields are strict and immutable after typed construction.

- Templates/injection schedules cannot be scoring records. Accepted records explicitly identify adjudication role, run, rubric version, provenance and interval.
- Causes are sets of supported/contradicted queue/prefill mechanisms, with explicit completeness. Healthy, supported and unresolved are distinct; unresolved does not claim complete cause coverage.
- Assertions require linked criteria and at least two corroborating channel declarations beyond the intervention log. A policy's short capture is not an allowed independent reference channel. This structural rule is a conservative collection requirement, not proof of causal independence or a scientifically sufficient rubric.
- Artifacts carry relative paths, SHA-256 hashes, channel and acquisition/availability times. `verify_content(root)` checks actual bytes and rejects traversal/symlink escape. Parsing alone validates declared identity format, not file contents; collection/scoring tools must explicitly verify every artifact before use.
- Reference evidence must be available before adjudication. All compared timestamps must share the declared host domain; a matched run with another domain needs an explicit mapped representation. No automatic clock conversion exists.
- Matched full-trace evidence requires a separate run ID and a mismatch assessment. Reference-run labels/times cannot be copied onto policy runs as automatic truth. Alternative explanations and limitations remain explicit.
- Assessor identities and declared blinding are required. Single-assessor/unblinded records require stated limitations. The validator cannot prove blinding or evidence quality.
- `require_joinable(...)` rejects wrong run/provenance/domain, an absent lock, or a declared lock later than prediction join. Step 017 adds [durable snapshots/lock manifests, verified bytes and a scoring CLI](LOCKED_REFERENCE_SCORING.md). Clock authority and human blinding remain external responsibilities; the CLI accepts synthetic clocks only. A synthetic reference cannot be joined as live evidence.

The [empty template](reference_record.template.json) deliberately fails validation until placeholders are replaced by a real adjudication. No synthetic example is experiment ground truth.

## CPU example and checks

From the repository root, use a new output directory:

```bash
python3 -m revision.scripts.demo_measured_evidence --output /tmp/my_measured_contract_demo
python3 -m unittest revision.tests.test_measured_contracts -v
```

The [saved example](../examples/measured_contract_demo/prediction.json) is synthetic. It includes complete measured inputs and a separately asserted synthetic reference, but the classifier receives only measurements and still returns null. Its generated artifact files are fixture declarations, not real server measurements. The tests check future evidence, unmapped clocks, missingness/zero/partial coverage, reference leakage, unknown stability across a change, artifact integrity, matched-reference identity and locking order.

Step 015 implements exact offered-arrival playback/accounting. Step 016 adds owned CPU arm/session/reset handling. Step 017 adds durable evaluator reference locking and scoring. Next is interval instrumentation/export preparation (018), followed by real GPU validation. GPU capacity/diagnosis calibration and the step-012 freeze checklist remain pending.
