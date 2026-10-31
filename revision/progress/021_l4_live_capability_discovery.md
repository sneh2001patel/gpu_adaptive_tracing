# Step 021 — Live L4 capability discovery and bounded serving probe

Date: 2026-10-28. Status: complete for hardware discovery and two short serving probes. Actual worker barrier/reset and new capture feasibility remain pending. GPU access used through the user-provided SSH connection; no main experiment matrix run.

## Completed

- [x] Read the instance operating guide and inspect the actual L4/tool/environment state without changing management services.
- [x] Deploy an isolated source snapshot and one-shot supervisor service, preserving the earlier pilot workspace/results.
- [x] Restore the exact Qwen2.5 model revision into shared-memory cache and record SHA-256 values for all 11 model files.
- [x] Start the pinned single-worker serving stack; validate UUID/device name, vLLM/Nsight/model identity and live compute PID.
- [x] Run the step-020 inventory/metric discovery gates against actual endpoint data; retain unavailable quiet/reset and skipped capture states.
- [x] Submit two declared short completion probes and preserve actual response usage, timings and before/after raw metric snapshots.
- [x] Shut down the owned serving process group; independently verify parent/worker absence, empty compute inventory and 0 MiB GPU memory.
- [x] Back up the raw results, source archive, model hashes, service configuration and cleanup records into the local workspace; verify artifact integrity.
- [x] Test wrapper ownership/persistence and fix transient local process-group visibility handling without treating uncertainty as absence.
- [x] Update progress and the CAIN revision plan.

## Evidence and validation

[Hardware report](../hardware/l4_20261028/REPORT.md), [summary](../hardware/l4_20261028/SUMMARY.json), [discovery gates](../hardware/l4_20261028/discovery_001/discovery/RESULT.json), [raw probe records](../hardware/l4_20261028/discovery_001/probe_requests.json), [metric inspection](../hardware/l4_20261028/discovery_001/probe_capabilities.json), [cleanup proof](../hardware/l4_20261028/post_cleanup_checks.json).

The actual L4/vLLM 0.10.2/Nsight 2026.3.1 stack passed inventory and scoped metric checks. The model revision matches the earlier pilot. Worker PID 1196 matched the selected GPU compute inventory. Both short requests succeeded, each reporting 12 prompt tokens and 16 output tokens. Queue/prefill/decode histogram counts advanced 0 → 1 → 2. This is consistent with source-reviewed finished-request reporting, not evidence that an admission-window or exclusive GPU-service mapping is valid.

Quiet/reset remains unavailable and capture skipped; there are **zero new captures**, no calibration and no main matrix. The owned serving parent and worker are absent, with no escalation and 0 MiB GPU memory after cleanup. The rental instance itself was not stopped.

All **380 CPU-only tests pass**, including **five new wrapper checks**. The [saved integrity audit](../hardware/l4_20261028/VALIDATION.json) verifies all **34 recorded artifact hash entries** after local backup and **122 deployed source fingerprints** against the exact source archive. Model weight/config hashes are recorded from the remote files; weights are not copied locally or rehashed from local bytes. The [wrapper](../scripts/run_l4_discovery.py) and [tests](../tests/test_l4_discovery_wrapper.py) retain ownership/persistence behavior.

An initial local cleanup test encountered transient process-group visibility denial. The current launcher treats denial as unknown and retries within its deadline. This guard was added after the Linux deployment; the hardware run retains its original source archive/fingerprint. Core discovery/serving sources are identical. Initial failed logs and final passing tests are saved in the hardware directory. Historical step-011 and paper outputs are preserved.

## Limits

Two sequential short completions are feasibility probes, not accuracy, calibration, statistical precision, perturbation or workload-transfer evidence. The histograms cover reported finished requests and have no validated source-clock/window mapping to the existing admission-cohort adapter. Phase durations do not establish exclusive GPU phase service. No concrete diagnosis, causal reference, operator benefit, capture-active savings or empirical stopping contribution is claimed. The study protocol remains unfrozen.

## Next step — 022

1. Implement an owned worker barrier with fresh request/acknowledgement tokens and same-host clock identity; do not equate zero gauges with worker/GPU idle.
2. Implement fresh owned-session restart/reset with independently observed quiet states before/after, new worker identity and explicit cache/state semantics.
3. Use actual metric capabilities to implement an honest cohort/availability mapping or retain the unsupported fields; do not copy finished-request values into admission windows.
4. CPU-test that adapter, then run one bounded live Nsight capture with verified report readiness, worker/device coverage, serving continuation and owned cleanup before calibration or the study matrix.

The serving job is stopped and artifacts are backed up locally. GPU access remains useful for the next adapter validation; implementation preparation can proceed on CPU. The rental itself remains running.
