# Live feature mapping and calibration preparation

Step 023 maps raw metric receipts from the pinned vLLM 0.10.2 V1 stack into the measured window interface. It does not calibrate a classifier or launch GPU work.

## Supported contract

`ServingBinding` identifies the independently verified owned worker: session nonce, generation, PID, GPU UUID, model, engine and monotonic clock domain. `LiveMetricCollector` reads a bounded loopback endpoint and returns actual HTTP status, raw bytes, acquisition brackets and errors. Its caller must close/rebind it on restart. The HTTP bytes do not authenticate worker identity or prove that a restart did not occur; owned lifecycle management remains required.

`map_receipt` rejects foreign bindings and future receipts, inspects the exact-model/engine exposition and maps only the waiting gauge to `ServerSample`. A missing/invalid gauge or failed HTTP receipt becomes an explicitly missing sample, never zero. Raw metric hashes and inspection details accompany every mapping. Malformed selected histogram data causes the scrape to fail closed. Running gauges and finished-request histograms remain diagnostic sidecars.

| Feature | Source and cohort | Limit |
|---|---|---|
| Request p95 and completed requests/s | Existing successful client completions assigned by completion time | Sparse/error/pending accounting remains explicit; not admission-window latency |
| Prompt/output token means | Actual successful response usage | Configured lengths and intended prompts are not substituted |
| Queue depth mean | Exact selected waiting gauge assigned by parent receipt time | Unweighted sample mean; not a time-weighted mean or a source event timestamp |
| GPU utilization mean | Existing validated sampler receipts | NVML averaging intervals are not inferred from parent acquisition times |
| Admission-window request-wait p95 | Unavailable | Finished-request logger histograms have a different cohort and no validated admission-window clock mapping |
| Exclusive GPU prefill-service fraction | Unavailable | Request phase durations do not partition exclusive GPU service time |

`LiveFeatureWindow` accepts bound raw scrapes plus existing typed completions/GPU samples. It preserves half-open windows, deadline/late/outside auditing and per-record accounting. Direct unbound server samples and interval-statistic injection are rejected. Histogram changes cannot change measured features. Closing a window retains explicit unsupported reasons for both interval fields. `persist` writes an exclusive output directory with measured observation, raw receipts, audit and artifact hashes.

The existing classifier bridge accepts these windows, checks their worker/device/provenance against its target, and retains the uncalibrated classifier's abstention. Cheap-only observations have no kernel evidence. The existing parsed-kernel temporal join still requires exact acquisition/availability and expected worker/device; this step does not create a new GPU-to-host timestamp mapping.

`complete` coverage means all accepted attempted records supplied that statistic. It does **not** establish a planned sampling cadence, continuous time coverage, source-cohort completeness or statistical adequacy. Dropped/skipped request admissions remain the workload driver's responsibility.

## CPU usage

```python
collector = LiveMetricCollector("http://127.0.0.1:8012/metrics", verified_binding)
receipt = await collector.sample(clock, "sample-1")
window.on_scrape(receipt)  # also feed actual client completions and sampler receipts
# After the window and grace deadline:
window.persist(new_output_directory, "window-1")
bridge.register("window-1", window)
prediction = bridge.classify("window-1")  # uncalibrated: abstains
```

The collector is ready for owned lifecycle integration, not automatically started by the experiment-arm runner. Reusing a collector across workers is invalid. Neither this code nor a caller-declared binding replaces startup inventory/reset checks.

## Offline saved-byte audit

```bash
python3 -m experiments.scripts.audit_saved_live_features --output /tmp/new_saved_mapping_audit
```

[Saved audit](../examples/live_feature_mapping/saved_l4_audit/AUDIT.json) checks 12 existing step-022 raw metric receipts, their hashes and worker/generation scope. This is offline mapping of previously collected live bytes: no new GPU activity, reconstructed windows, online decisions or calibration data. The original hardware outputs remain unchanged. Parent acquisition brackets are reused for receipt validation only.

## Independent calibration preparation

```bash
python3 -m experiments.scripts.prepare_live_calibration --output /tmp/new_calibration_preparation
```

[Saved packet](../examples/live_feature_mapping/calibration_preparation/PREPARATION.json) lists 18 planned jobs: feature and matched-full-trace pairs for healthy control, arrival-pressure-only and long-prompt-only collection instructions across three calibration seeds. Schedules and counterbalanced order are unresolved; this is a non-executable collection plan. Intended interventions live in evaluator-only metadata, are not classifier inputs and never become reference labels automatically.

An optional `--entries` JSON list can inventory already collected calibration observations, with each entry containing exactly `run_id`, `split: "calibration"`, and relative `observation_path`. `--artifact-root` bounds these files. The inventory validates strict measured records, hashes bytes, preserves null/partial/sample counts and rejects held-out/development entries or mixed synthetic/live inventories. Split declarations do not prove corpus/seed independence; the separate protocol and eventual collection manifest must establish it. The saved empty packet contains no calibration observations or reference labels.

Before fitting: pin actual prompt bytes/token bands; measure capacity; materialize exact offered files and paired fresh resets; resolve collection order; collect independent server/request/full-trace evidence; adjudicate ambiguity/alternatives and matched-run mismatch while blinded to policy predictions; lock references through the existing reference store before scoring. A preparation packet is not a lock. Human adjudication remains required, including for a single-author study, with assessor identity and limits recorded.

The current required classifier metrics include unsupported fields. A narrower candidate feature profile requires a separately versioned contract and independent calibration; deleting missingness or renaming finished-request p95 is not validation. Queue-pressure and prefill claims must be evaluated separately. No thresholds, calibrated labels, accuracy estimates or study readiness are produced here.

## Subsequent validation and next step

Step 024 implements [the bounded throughput/corpus pilot](CAPACITY_AND_CORPUS_PILOT.md) and validates six live client/queue windows on the L4. Actual token usage and 96 raw metric receipts pass checks; unsupported fields remain null. Four candidate paired jobs are materialized but not executed. This does not establish maximum capacity or calibrated diagnosis.

Step 025 now passes owned exact-arrival paired collection, two full traces and a ten-artifact assessment packet. Next step 026 establishes evidence assessment/rubric and coverage/mismatch limits, with feature/challenging-case gaps. Actual reference adjudication/locking, fitting and protocol freeze remain pending.
