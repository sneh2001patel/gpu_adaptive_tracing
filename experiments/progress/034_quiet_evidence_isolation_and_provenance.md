# Step 034 — quiet-evidence isolation and immutable provenance

Completed 2026-10-28. CPU-only. [Implementation/validation report](../examples/quiet_evidence_isolation/REPORT.md), [live-data index](../hardware/l4_20261028/challenges_v2_quiet_provenance_034/INDEX.json), [preservation checks](../examples/quiet_evidence_isolation/validation/PRESERVATION.json).

## Completed checklist

- [x] Isolate working-source quiet persistence by resolved episode output; keep same-output multi-phase/reset history.
- [x] Reject unsafe labels, unrelated session output, duplicate raw filenames and replacing another activity's saved log before issuing a barrier RPC.
- [x] Add meaningful multi-job, reset, partial-failure and overwrite regressions; retain existing cleanup-failure coverage.
- [x] Reproduce the leak against the exact archived implementation: second job saves eight rows instead of four.
- [x] Build a separate hash-bound index of original jobs/bindings/raw files and every historical quiet-row occurrence.
- [x] Pass 33 focused and all 565 CPU tests, including sixteen new tests.
- [x] Reproduce the original step-033 audit without writing its report; verify both original archives, descriptors, backups and the failed v1 artifacts unchanged.
- [x] Record the new working-source fingerprints without creating a new deployment snapshot or hardware claim; update the plan/progress.

## Outcome and limits

New job output files contain only their own episode's evidence. Deliberate restarts in one output retain both generations, with distinct labels protecting raw files. The separate historical index verifies 6,142 campaign hashes and maps 544 observed rows to 64 original barriers, including 480 historical copies; it does not rewrite or reinterpret the original files as self-contained jobs.

The frozen regression proof has one expected old-code assertion failure. An initial reproduction-harness mock-routing error is separately retained and corrected; the current 565-test suite passes. The archived step-033 audit reproduces its existing report exactly. Both snapshots verify 171/184 entries, and 362 original failed-run artifacts remain failed and unchanged. The previous successful engineering campaign remains development evidence.

Working source now differs from the v2 snapshot, and the old freeze correctly rejects it. No new snapshot, live rerun, GPU measurement, reference, diagnosis or classifier calibration occurs. CPU fixtures establish persistence/audit behavior, not a paper baseline or hardware performance. No SSH or rental-state check is performed; the last GPU cleanup/rental observation remains step 033.

## Next step — 035, CPU-only

1. Use the unchanged step-033 bytes and their existing source/clock/ID bindings to audit scheduler wait-bound precision, window boundaries and cohort inclusion.
2. Tabulate acquisition bracket widths, boundary ambiguities, incomplete/censored lifecycles, deadline readiness and usable request counts, retaining absent/ambiguous evidence explicitly.
3. Decide which fields are admissible as measured features and keep CPU scheduler waits separate from exclusive GPU phase claims. Do not activate classification based solely on engineering checks.
4. Expose scientific tolerances and independent assessment criteria that remain unset. Prepare an assessment plan without manufacturing reference labels, retrospectively confirming thresholds or fitting calibration.
5. Save the offline audit/report, tests where needed and the next-step status. Future changed-source hardware validation needs a new engineering snapshot; no GPU is required for step 035.
