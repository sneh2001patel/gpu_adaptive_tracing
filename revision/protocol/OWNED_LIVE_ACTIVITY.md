# Owned worker reset and capture feasibility

Step 022 adds an activity adapter for one local, single-worker L4 serving process. It runs the existing ordered inventory → metrics → quiet/reset → capture → cleanup gates. Passing these gates establishes bounded engineering feasibility, with study, diagnosis and protocol-freeze flags still false.

## Worker barrier and quiet observations

The fixed loopback `POST /revision/barrier` route invokes only `revision_barrier` in the CUDA worker. The parent writes a fresh command token, session nonce, generation and same-host monotonic clock domain. The worker rejects consumed or malformed tokens, foreign scope and an active capture, synchronizes CUDA, and atomically writes a PID/device-bound acknowledgement. Failed synchronization cannot produce a successful receipt.

The adapter requires no outstanding owned client task, exact-model/engine waiting/running gauges equal to zero before and after the RPC, and a receipt bracketed by parent request/receipt times. Two observations use different tokens, separated by a minimum 10 ms hold. Raw metric bytes, fingerprints, command and acknowledgement remain available for audit.

Synchronization covers prior-issued work on the configured worker device. It cannot rule out future admissions, unrelated device work or another client. The serving endpoint is loopback-only, the process is owned by this pilot, and no competing workload is deliberately submitted. Zero gauges alone do not establish GPU quiescence.

## Fresh reset

The original owned process group is closed and worker absence verified before a fresh server starts under Nsight. The new worker must have a different PID, new session nonce, incremented generation, expected UUID and the reset token from its fresh startup record. Inventory is checked again. New-engine/KV state is fresh; downloaded model files and OS page cache are reused. This is not a cold-storage/cache experiment. Quiet observations are repeated after restart and after capture.

## Exactly one attempted range per invocation

The configuration prohibits the main matrix/calibration and permits one capture attempt. The capture-used flag is set before starting; failure does not refund the attempt. Nsight's pinned synchronous repeated-range mode provides per-range reports while preserving serving; the adapter issues only one range. A corrected invocation receives a new output directory, retains the failed invocation and records its changed source snapshot.

The backend requires both a CUDA-worker acknowledgement and the actual Nsight collection callback before submitting the 32-output-token feasibility request. After the requested one-second range, it requires stop acknowledgement, report notification, SQLite export and parsing for the expected fresh PID/UUID. A readiness-only decision marker precedes a separate 16-output-token serving-continuation request. No classifier or stopping-policy decision is run. Active capture duration remains null: acknowledgement spacing is a control interval, not an independently observed active boundary.

Callbacks, session paths and Nsight output paths are absolute because Nsight can execute callbacks outside the launch working directory. Cleanup cancels/awaits clients, closes backend helpers and all owned sessions, and requires process-group/worker absence even after a failed stage. Unexpected failures are persisted rather than promoted to successful captures.

## Invocation and checks

Run only in the pinned GPU environment, from a one-shot supervisor service using the instance operating guide. Use an unused output directory and the selected device UUID:

```bash
python -m revision.scripts.run_l4_activity --output /workspace/results/activity_new --model-path /path/to/pinned/model --device-uuid GPU-UUID
```

Read `RESULT.json`, stage receipts, `quiet_evidence.json`, request responses, backend/timing events and cleanup records. Preserve the deployed source archive and off-host backup. The CLI returns nonzero unless all live feasibility gates pass. CPU verification:

```bash
python3 -m unittest revision.tests.test_worker_barrier revision.tests.test_owned_live_activity -v
```

These tests inject CUDA synchronization and subprocess behavior. They establish rejection/ownership logic without GPU execution; hardware receipts provide the separate live evidence.

## Feature and study limits

Pinned vLLM queue/prefill/decode histograms describe reported finished requests. They have no validated mapping to admission-window waits or exclusive GPU prefill service fractions. This adapter retains both unsupported fields and does not calibrate a classifier. Step 023 adds [the explicit cohort/availability contract and independent calibration preparation](LIVE_FEATURE_MAPPING.md), checked on CPU and saved bytes. Full live collection, capacity/corpus measurements and independent reference adjudication still precede calibration or main-study freeze. A single capture does not establish diagnostic accuracy, savings, perturbation or operator benefit.
