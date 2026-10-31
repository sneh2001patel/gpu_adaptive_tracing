# Step 011 — First live L4 engineering pilot

Date: 2026-10-27. Status: complete for engineering validation. The corrected matrix is `pilot_002`; diagnostic effectiveness remains unvalidated.

## Frozen pilot configuration

- One persistent Qwen2.5-7B-Instruct server on the L4 stack validated in step 010.
- Separate warmup (3 requests) and healthy latency calibration (12 sequential requests); the same frozen reference is used for the matrix.
- Three healthy controls plus five policies × three repetition/seed labels: 18 intended runs. Persistent-load policy order is shuffled with seed `20261027`; controls precede them.
- Each observation horizon is 24 s, windows 2 s, arrival grace 0.1 s, requested capture span 1 s, hard incident cap 3 attempts. Reactivation is disabled for this comparison.
- Healthy arm: 0.5 requests/s, 32 output tokens. Persistent-load arm: 8 offered requests/s, 128 output tokens, at most 16 in flight. Capacity/scheduler skips, failures, outstanding requests and post-horizon drain are recorded.
- The classifier deliberately abstains pending independent T2 diagnosis/calibration. Unknown evidence cannot establish diagnosis stability. These runs do not estimate diagnostic quality.
- Greedy generation with three seed labels does not prove statistical independence. All arms share a persistent server/cache state and one calibration cohort. No confidence-interval or significance claims are planned.

## Artifacts and implementation

- Runner: `experiments/scripts/run_l4_pilot.py`.
- Analysis: `experiments/scripts/analyze_l4_pilot.py`.
- Rerun directory: `experiments/hardware/l4_20261027/pilot_002/`; the telemetry-deficient first matrix remains in `pilot_001/`.
- Exact source hashes, base Git commit/dirty state, package freeze, model revision, schedule, launch command, baseline requests and control settings are saved.
- Every run saves raw producer receipt records, windows, controller/timing decisions, capture failures and parsed summaries. Actual Nsight reports and SQLite exports remain linked by artifact hashes.

## First-matrix telemetry defect and correction

The first matrix completed 18 runs and produced 39 valid captures, but its final audit found 1,560 sampling errors and 156 missing GPU windows across 13 later runs. Cancelling a sampler read at an episode horizon closes its NVML session; the runner incorrectly reused that sampler in later episodes. Capture readiness alone did not catch the missing telemetry. `pilot_001` is retained and explicitly marked telemetry-incomplete, rather than used as a clean policy comparison.

The runner now owns a fresh sampler for each episode, initializes it before the observation horizon, saves per-episode sampler lifecycle records, and rejects episodes with sampling errors or missing GPU windows. A CPU regression reproduces the closed-sampler boundary and verifies distinct ownership. All **186 CPU-only tests pass**. The unchanged matrix completed as `pilot_002`; its exact 27 executed source files have been hash-verified and archived. The analyzer also audits telemetry coverage and checks archived executed source separately from later working-tree edits.

## Completion checks

- [x] All intended runs complete, with failures retained if any.
- [x] Verify parsed evidence exists before every successful policy decision.
- [x] Verify later admissions/completions establish continued serving after decisions.
- [x] Check captured worker/device identity and report/SQLite hashes after session shutdown.
- [x] Record unknown stops, request errors, late data, skips, drain and cleanup honestly.
- [x] Copy the raw artifacts off the rental and generate the pilot report/CSV.
- [x] Update the progress tracker and main CAIN plan.

## Audited rerun results

- All 18 scheduled runs completed: three healthy controls (zero captures) and five policies × three repetitions (39 captures total).
- 756 admitted requests completed, with zero request errors. There were 2,160 capacity skips, zero scheduler skips, 240 completions during post-horizon drain, and zero late completions/GPU samples. Equal offered schedules therefore do not establish equal realized work.
- Zero sampling errors and zero missing GPU windows across all 216 windows. All 18 per-episode samplers ended with no surviving worker.
- All 39 successful decisions used parsed evidence available before the decision and occurred before the horizon; each was followed by both new admissions and completions.
- 301,283 captured kernel instances parsed from the configured worker/device. All 78 report/database hashes and 27 archived executed-source fingerprints match.
- FB used one capture/run; RFB, SS, CR and HS used three/run. Every diagnosis remained unresolved by design. This demonstrates budget/unknown handling, not diagnosis sufficiency or policy superiority.
- Owned serving session exited with status 0; CUDA worker absent, no Nsight sessions or GPU compute processes, GPU memory 0 MiB at cleanup check. The rental itself remains running and billable.
- Raw reports, databases, request/sample streams, source archive and cleanup records are backed up locally under `experiments/hardware/l4_20261027/pilot_002/`.

See [generated report](../hardware/l4_20261027/pilot_002/analysis/PILOT_REPORT.md), [audit checks](../hardware/l4_20261027/pilot_002/analysis/validity_checks.json), [run metrics](../hardware/l4_20261027/pilot_002/analysis/run_metrics.csv) and [cleanup](../hardware/l4_20261027/pilot_002/cleanup_verified.json).

## Limits and next work

Synchronous report flush can pause the GPU worker. Capture-control/RPC/export/parse costs are observed; GPU capture-active time stays unavailable. No GPU savings, diagnosis accuracy, stable-label safety, independent root-cause reference, operator benefit or generalization is established. These are laboratory serving interventions and engineering checks.

Next step 012: independent reference evidence and T2 classification/calibration; evolving/lull/overlap cases; matched no-profiler and cheap-only controls; active-capture boundary validation; then a frozen held-out experiment protocol. A100 replication follows a validated L4 protocol rather than mixing old and revised results.
