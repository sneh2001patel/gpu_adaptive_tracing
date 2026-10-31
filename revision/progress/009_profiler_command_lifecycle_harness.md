# Step 009 — Profiler command/lifecycle harness with a fake executable

Date: 2026-10-27. Status: completed for the CPU subprocess contract and controller integration. No Nsight command, CUDA capture, real NVML query, serving attachment, or GPU experiment was run.

## Completed work

- [x] Added `revision/tracing/command_profiler.py`, implementing the existing backend interface through owned POSIX subprocess groups. Versioned command plans record driver identity/version, expected device/workers, argv, stage deadlines and artifact limits. Commands run without a shell.
- [x] Added fresh per-attempt directories/tokens and a versioned file protocol. Capture-start and capture-stop acknowledgements must match the attempt identity/token/source; command success or a file's mere existence cannot substitute for them.
- [x] Added collection, stop, finalization, export and parse lifecycle handling, stage deadlines, command stdout/stderr, return-code records and launch failure outcomes.
- [x] Required nonempty, bounded, non-symlink artifacts; rejected LFS pointer reports, malformed/foreign records, unknown schemas/units, missing expected workers/device coverage, empty kernels, and truth fields. Bound export to report and summary to export with SHA-256 checks; published evidence only after parse exit and validation.
- [x] Timestamped evidence availability at actual validated receipt, retained unique evidence IDs, and left capture-active time and total persisted lifecycle unknown. Capture startup is distinct from serving startup; additional command/cleanup durations are exposed in the backend snapshot.
- [x] Added cancellation and nonblocking cleanup service: TERM only owned process groups, escalate to KILL after a grace interval, reap direct children, retain cleanup state, and report groups that survive bounded final cleanup. A separate unrelated-process test verifies that cleanup does not kill it.
- [x] Updated the controller to `streaming_v3`: optionally service backend cleanup and wait for capture readiness before spending another attempt. Failed attempts remain charged, while cleanup waiting cannot create artificial launch failures.
- [x] Added `fake_profiler_command.py` and a runnable controller demo using actual CPU subprocesses and fake acknowledgements/reports. Saved valid, empty-summary and missing-start-ack examples. The demo classifier abstains; successful evidence collection does not imply a correct diagnosis or a stability stop.
- [x] Fixed an NVML cleanup cancellation race exposed by the full suite: shield one shared cleanup task through TERM/KILL polling, then propagate cancellation after cleanup. Added a deterministic cancellation-at-termination regression.
- [x] Added 21 subprocess/configuration/controller tests plus one NVML cancellation regression and updated progress, README, contract, and main revision plan.

## Validation

```bash
python3 -m unittest discover -s revision/tests -q
python3 revision/scripts/demo_command_profiler.py --mode ok
python3 revision/scripts/demo_command_profiler.py --mode empty-summary
python3 revision/scripts/demo_command_profiler.py --mode no-start-ack
python3 -m py_compile revision/tracing/command_profiler.py revision/scripts/fake_profiler_command.py revision/scripts/demo_command_profiler.py revision/tests/test_command_profiler.py revision/tracing/controller.py
git diff --check
```

The full suite passes **171 CPU-only tests** (149 previous, 22 added). New coverage includes valid readiness/hash/timing behavior, no classification before parse, acknowledgement requirements, nonzero command exits, missing/LFS reports, malformed or mismatched export, empty/foreign/truth-bearing summaries, all five external-stage timeouts, cancellation, kill escalation, unrelated-process survival, failed-launch budget charging, unique directories/tokens, symlink rejection, cleanup waiting without extra attempts, and collector wall/finalization time ending independently of a lingering stop helper.

Each saved fixture runs to the six-attempt cap because its classifier always abstains. The valid fixture produces parsed evidence but no concrete diagnosis; empty summaries and missing acknowledgements produce explicit capture failures. Counts demonstrate policy/failure behavior only. CPU subprocess timings are development measurements, not GPU capture cost or paper experimental results.

## Scope and limits

- This is a command harness, not a working Nsight integration. It accepts only `synthetic_simulation` recorder provenance and the fake executable's protocol/source/acknowledgement basis. Enabling real evidence requires a separately validated target-specific driver and protocol changes; changing a provenance string is insufficient.
- GPU physical UUIDs and worker PIDs in fixtures are synthetic identity/coverage expectations, not observed hardware/process mappings. A fixture acknowledgement does not prove actual target-side CUDA collection.
- Owned commands may be terminated on failure/final cleanup. A future persistent serving target must have separate ownership/lifetime; do not place it in an attempt-owned group and then assume cleanup preserves serving. Arbitrary already-running CUDA process attachment is not implemented.
- POSIX process-group cleanup cannot prove that a child has not escaped into another session. An OS-uninterruptible process/group may survive kill; final cleanup raises and retains that state. Direct children are reaped, and known owned groups are checked; real worker/session cleanup requires target validation.
- Callers must service backend cleanup while running and await `backend.aclose()` in `finally` after controller completion/failure. `failed` prevents late evidence consumption but does not itself mean process cleanup has completed.
- Artifact reads/hashing and process launch are synchronous and bounded in size, not hard real-time or perturbation-free. Command logs and audit ledgers have unmeasured disk/memory cost. There is no production performance claim.
- Existing historical results, audit snapshots, paper tables and submitted PDF remain unchanged. Real sampler/capture coverage, independent classification, calibration and experimental results remain pending.

## Next step

**Step 010: target-specific Nsight driver and hardware smoke validation.** Collect the target machine's installed Nsight version/help/capabilities, select a supported persistent serving-session and bounded capture mechanism, implement its acknowledgement/export/parser adapter, and validate device/worker coverage and failure cleanup with known CUDA activity. Keep the same serving/load horizon when stopping captures. Actual telemetry, capture acknowledgement, report readiness and coverage checks require an NVIDIA GPU.

**GPU notice:** the CPU command harness is ready for integration work. The next hardware validation milestone requires NVIDIA GPU access; tell the user before attempting it. If hardware is unavailable, independent CPU tasks remain available: operator evidence reports, experiment manifests/protocol, threshold-sensitivity tooling, and contribution/related-work revision. Those do not substitute for live validation.
