# Step 003 — Historical claim, artifact, and timing audit

Date: 2026-10-27. Status: completed as a local read-only audit. This does not establish independent diagnosis accuracy or replace missing GPU captures.

## Completed work

- [x] Registered 40 claim groups covering the submitted PDF's implementation, setup, Tables I–VIII/Fig.1, five RQs, interpretation, reproducibility, and scope. Each entry records analysis/raw artifacts, source scripts, finding, and disposition. Literature novelty is explicitly marked for external primary-source comparison rather than purportedly established from experiment files.
- [x] Added `experiments/scripts/audit_artifacts.py`, a CPU-only reproducible audit that writes exclusively within `experiments/`. It reads original artifacts and emits audit products instead of regenerating paper tables.
- [x] Indexed 405 historical timing records across serving, microbenchmark, and replay-selected live-capture families. Preserved profile wall time separately from request span and summed kernel execution; unavailable capture/startup/export/lifecycle durations remain unknown.
- [x] Verified that 817 local profiler files are LFS pointers (409 reports, 408 SQLite paths), recorded their original object IDs/sizes, and avoided treating file presence as binary availability.
- [x] Reconciled the six Table VI scenario totals against 18 saved comparison JSONs. Times match rounded paper values but use the wrong clock for active-capture claims; all scenario kernel pairs disagree with the PDF.
- [x] Counted 201 canonical multiclass window records, and verified that all 402 saved CSV representations collapse to 201 unique window identities. The later deduplicated analysis also reports 201.
- [x] Verified L4 microbenchmark manifests specify 5 s windows and 2/8 s automatic/fixed workload segments; the larger paper durations are subprocess wall times.
- [x] Identified Table VIII's 0.635 F1 as the confidence signal's result, not the diagnosis-change signal's archived result (0.000).
- [x] Recomputed all eight dedicated polling-overhead repetitions from raw per-request CSVs. Queue-pressure mean p95 change is −3.555926% (5 runs); healthy is +0.645937% (3 runs). Differences from saved per-run calculations are below 1e-13 percentage points.
- [x] Wrote a timing contract for the next implementation step, including separate control-window, capture-active, startup, profile-wall, report-finalization, stats-command, parse, evidence-ready, and lifecycle measurements.
- [x] Fingerprinted 1,554 inputs and checked they remained unchanged during the audit. Recorded source PDF hash and repository HEAD, with the limitation that per-run source commits are absent.
- [x] Added five CPU-only audit tests and updated the main plan and cumulative tracker.

## Files produced

- [Claim audit and reuse decisions](../audit/CLAIM_AUDIT.md).
- [Timing definitions, historical boundaries, and future contract](../audit/TIMING_AUDIT.md).
- [Editable claim registry](../audit/claim_registry.json).
- Generated audit products in `experiments/audit/generated/`: `artifact_audit.csv`, `artifact_checks.csv`, `profiler_availability.csv`, `timing_audit.csv`, `table_vi_reconciliation.csv`, `raw_request_overhead_checks.csv`, `input_fingerprints.csv`, and `audit_summary.json`.

## Validation

```bash
python3 experiments/scripts/audit_artifacts.py
python3 -m unittest discover -s experiments/tests -q
python3 -m py_compile experiments/scripts/audit_artifacts.py experiments/tests/test_artifact_audit.py
git diff --check
```

The audit resolves every registered artifact pattern. The full CPU suite has 40 passing tests. New checks verify LFS detection, preservation of unknown phase times, rejection of empty latency data, output-directory restrictions, and read-only input handling. No GPU tools are required or invoked.

## Interpretation and remaining limits

The 18.9–48.5% duration-saving arithmetic is historical profile-command wall time under differing workload durations, not measured active-capture efficiency. Startup/export phase values cannot be recovered by subtracting request span or summing kernel durations. Full lifecycle time also includes untimed work outside the profile-command timer.

Existing LFS objects may permit further forensic capture-boundary analysis if retrieved; this needs storage/network/tool access, not necessarily a new GPU run. No LFS download occurred. Untimestamped capture messages and summary kernel counts cannot replace profiler metadata.

Historical accuracy, policy rankings, and signal safety results need independent evidence and corrected semantics. Cheap-polling perturbation results remain narrowly reusable; they do not measure concurrent aggregation or full adaptive-controller overhead. Exact historical executable identity is not independently proven because run-level source hashes are absent.

Original raw artifacts, historical analyses, and paper tables were not changed. The 405 timing entries include archive/diagnostic runs and must not be presented as independent experimental repetitions.

## Next step

**Step 004: monotonic timing/event recorder and fake profiler backend.** Implement the contract from the timing audit and test phase ordering, unavailable real capture intervals, failed-start behavior, and evidence-readiness constraints on CPU. Then use those interfaces for the streaming episode controller before GPU capture integration. Record the work in a new numbered report and update `experiments/PROGRESS.md` and `experiments/PLAN.md`.
