# Pinned-stack feasibility gates — step 020

Prepared and tested on CPU on 2026-10-28. No GPU/SSH access used. The executable live adapter performs read-only discovery on an already running local serving stack. It does not launch a server, submit workload, restart workers, start capture or kill processes. The remaining activity gates have explicit receipt contracts and CPU fixtures; a real owned activity adapter remains necessary.

## Reviewed metric semantics

The selected profile is **vLLM 0.10.2, V1, one model/engine**. In the pinned [metrics logger](https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/v1/metrics/loggers.py), queue, prefill and decode histograms are observed inside the finished-request loop. Thus changes between scrapes describe newly reported finished requests. They are not the admission-time cohort measured by the CPU history source. Under backlog, unfinished requests may contribute no such observations. Presence of the histogram does not establish the requested window coverage or online availability.

The pinned [request statistics](https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/v1/metrics/stats.py) distinguish frontend wall-clock timestamps from engine-core monotonic timestamps. A metric receipt time does not automatically map either source clock to the controller. Request phase durations also do not establish exclusive GPU service attribution under concurrent requests. This harness therefore blocks automatic mappings into admission-window wait and `prefill_service_fraction`; it does not rename those measurements to satisfy the existing classifier contract.

[Reviewed source snapshots and hashes](sources/vllm_0_10_2/SOURCE_MANIFEST.json) retain the tagged files, original headers and Apache license. This source review is a capability hypothesis for the pinned stack, not confirmation of the installed rental environment.

## Scoped metric inspection

[The inspector](../feasibility/metrics.py) selects exact `model_name` and `engine` label values independent of label order, without aggregating other engines/models. It inspects waiting/running gauges and queue/prefill/decode classic histogram components. Selected duplicate series/labels/types, unexpected labels, nonfinite values, malformed buckets/counts/sums and unsupported explicit timestamps/exemplars are rejected. Missing components remain unavailable. This is a scoped parser, not general OpenMetrics support.

Saved sequences retain invalid snapshots, histogram schema changes, decreases/resets, inconsistent deltas and newly reported finished-request counts. Those counts are inventory only: no quantiles, calibrated diagnoses, phase fractions or controller features are generated. Hidden resets and exporter atomicity still need actual source validation. Zero queue/running gauges alone cannot establish worker/device quiescence.

## Gate order and bounded execution

[Configuration](../configs/l4_feasibility_v1.json) pins the previous vLLM 0.10.2/Nsight 2026.3.1/Qwen model revision, one selected L4 and engine 0. The current device UUID is supplied for each deployment. There is one prospective capture attempt; main matrix and calibration execution are disabled. Every adapter operation has a deadline; a failed/unavailable gate skips dependent activity. Synchronous validation uses a 64 MiB per-artifact size bound rather than a hard parser wall-time deadline. Cleanup is attempted even on cancellation and failures, and interrupted results are retained.

| Gate | Required evidence | What discovery can establish |
|---|---|---|
| Inventory | Pinned versions, selected device UUID/name, one live compute PID matching a worker record, local model-config and source hashes | Read-only candidate identity checks; not proof of loaded weight bytes or worker clock mapping |
| Metrics | Hashed raw HTTP snapshots, ordered parent request/receipt times, exact selected gauge series and capability inspection | Which scoped series are exposed; incompatible mappings remain unsupported |
| Quiet/reset | Repeated zero queue/running observations plus fresh worker barrier tokens, quiet hold, acknowledged fresh-worker restart and next generation | Unavailable in the read-only adapter; gauges cannot substitute |
| Capture | Post-reset start/stop acknowledgements, report/parse readiness before decision, hashed SQLite with exact worker/device kernels and serving continuation | Unavailable in the read-only adapter; earlier pilot reports cannot satisfy a fresh gate |
| Cleanup | Confirmed absence of all pilot-owned groups after activity | Read-only adapter owns no processes and makes no global cleanup claim |

The quiet/reset contract currently supports a fresh owned worker restart, not an unvalidated cache-clearing shortcut. The capture gate rejects an acknowledged control range shorter than the requested duration; this is a host control-range check, not a GPU-active measurement. The capture parser checks actual SQLite bytes and worker/device coverage. Host acknowledgement/report scopes remain distinct from GPU capture-active intervals, which stay unknown. Producer clock authority and truthfulness of operation receipts are adapter responsibilities; a schema/hash does not prove hardware execution or resist fabricated evidence.

A positive synthetic fixture may pass gate mechanics. It always keeps `live_feasibility_passed`, `diagnosis_ready`, `study_ready` and `protocol_frozen` false. A live read-only discovery result also leaves activity feasibility false because it cannot supply owned quiet/reset/capture receipts. No report promotes discovery into main-study readiness.

## Read-only command for the next L4 session

Run this **on the GPU host**, against a separately started pinned serving stack with its worker identity directory. The command is ready, but was not executed on a GPU in this step:

```bash
python3 -m experiments.scripts.live_feasibility \
  --config experiments/configs/l4_feasibility_v1.json \
  --output experiments/hardware/NEW_SESSION/feasibility_discovery \
  --device-uuid GPU-ACTUAL-UUID \
  --endpoint http://127.0.0.1:8010 \
  --model-path /ACTUAL/CACHE/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 \
  --session-directory /ACTUAL/OWNED/SESSION
```

Use a new output directory. Model config links may resolve within the configured model/cache root; escapes fail. The adapter records the served model label and hashes local revision config; those checks do not prove which weight bytes the running server loaded. Worker records are cross-checked against live selected-device compute PIDs, but still need an owned session/clock binding for activity. No GPU libraries are imported in CPU test discovery.

The CLI exit code reports discovery success only. Inspect `RESULT.json`: `discovery_passed` and `live_feasibility_passed` are separate. On success the live read-only adapter explicitly stops at unavailable quiet/reset and skips capture. Missing tools, wrong pins, ambiguous workers or malformed metric data retain failure reports rather than enabling activity.

Outputs include source/configuration fingerprints, raw metric bytes, stage receipts, per-gate status, capability diagnostics, final result and artifact hashes. Inventory does not dump the environment or credentials. The command uses only local HTTP endpoints and fixed read-only inventory commands.

## CPU verification and next step

```bash
python3 -m experiments.scripts.demo_live_feasibility --output /tmp/new_feasibility_gate_demo
python3 -m unittest experiments.tests.test_live_feasibility -v
python3 -m experiments.scripts.live_feasibility --help
```

[The saved report](../examples/live_feasibility_demo/REPORT.md) covers positive synthetic mechanics, wrong pins, hash failure, busy worker, stale reset, future parse, cleanup failure and discovery-only cases. All are explicitly synthetic, including SQLite kernels and worker barrier receipts.

**Steps 021–022 completed:** [fresh discovery](../hardware/l4_20261028/REPORT.md) passed inventory/metrics and two bounded probes; [owned activity](../hardware/l4_20261028/ACTIVITY_REPORT.md) now passes all live gates for one corrected capture invocation. The failed initial callback-path invocation remains preserved. See [the owned activity contract](OWNED_LIVE_ACTIVITY.md). This adds a separate owned adapter; the read-only discovery adapter still cannot pass activity gates. **Step 023 completed:** [live feature mapping/preparation](LIVE_FEATURE_MAPPING.md) passes CPU/offline checks; full owned live integration is pending. **Step 024 completed:** [six L4 throughput/corpus cells](../hardware/l4_20261028/CAPACITY_REPORT.md) validate scoped client/queue window collection and materialize candidate pairs, without establishing maximum capacity or calibration. **Step 025 completed:** [four owned paired jobs](../hardware/l4_20261028/PAIRS_REPORT.md) pass with two valid traces and an assessment packet, but zero adjudicated/locked references. **Next step 026:** evidence assessment/rubric and coverage/mismatch limits. Do not treat finished-request histograms as admission windows or exclusive GPU phase service, calibrate from this feasibility report, or launch the revised main matrix. Preparation can proceed on CPU; later validation needs the GPU.
