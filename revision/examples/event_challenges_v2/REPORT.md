# V2 development protocol — CPU preparation

[Protocol](../../protocol/EVENT_CHALLENGE_PROTOCOL_V2.md), [prepared packet](prepared_001/PLAN.json), [step report](../../progress/032_development_informed_v2_protocol.md). The new fixed ladder is 0.5/1/2/3/4 requests/s, with 84 offers plus warmup. Sixteen exact files and sixteen planned jobs retain the original strict eligibility/control limits. Maximum total work drops to 1,932 attempts; all jobs remain unexecuted.

[Synthetic cases](fixture_001/RESULT.json) cover zero queue, isolated spike, lowest qualifying 3 requests/s, qualifying 4 requests/s, metric gap and missing work. Each has raw hand-authored receipt/work JSON and a saved gate result. `GPU_used=false` and `live_validation=false`; these fixtures are not model measurements or diagnostic labels.

All **549 CPU tests pass** (eighteen new); [full log](validation/cpu_suite.log), [52 focused checks](validation/focused.log). The [initial failed full log](validation/cpu_suite_initial_failed.log) and [two passing isolated timing diagnostics](validation/timing_diagnostic.log) are preserved. Two old CPU fixture timing windows were extended, retaining their assertions and every GPU protocol guard.

The [new source snapshot](snapshot_001/FREEZE.json) binds 184 entries and twelve carried-forward installed source pins. The [preservation audit](validation/AUDIT.json) verifies 25 packet and nineteen fixture artifact hashes, the entire new archive and all 171 original archived entries/362 original failed artifacts/21 original packet artifacts. The original failed run, v1 descriptor/archive and backup are unchanged; no retrospective rate is selected. [Audit script](validation/audit_preservation.py), [document/check fingerprints](validation/CHECKS.json).

No SSH/GPU workload, new reference/calibration or scientific protocol freeze occurs. Next step 033 validates the separately frozen v2 packet fresh on the L4; pressure and complete delivery are not guaranteed by the new ceiling.
