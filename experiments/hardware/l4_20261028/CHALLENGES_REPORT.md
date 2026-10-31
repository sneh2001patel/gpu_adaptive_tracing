# Frozen L4 challenge campaign — step 031

Executed 2026-10-28 on NVIDIA L4 `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb`. **The campaign failed its first job's offered-work completeness check and stopped without retry.** Cleanup and the independent artifact audit pass. This is a development engineering outcome, not a successful sixteen-job experiment or a diagnostic reference.

## What ran

The exact step-030 archive and freeze descriptor were deployed to a fresh `/workspace/gpu_adaptive_tracing_step031` checkout through one-shot supervisor service `revision-l4-challenges-031`. Restart was disabled. Before startup, the preflight verified all eleven cached model/tokenizer/configuration files against the earlier full hashes, 171 frozen source/input entries and twelve installed vLLM source pins; the GPU was idle at 0 MiB.

Only `rate_ladder-b0-off` started. Parent 7707 and worker 7911 were independently mapped to the pinned model/session/GPU. The new fixed configuration RPC returned actual prefix caching false, synchronous scheduling, sixteen server sequences and single-worker parallel settings. One declared warmup preceded the sixty-second ladder. No scheduler collector, source event probe, profiler or classifier was enabled in this off role.

The client offered all 124 scheduled arrivals. Its existing 32-request in-flight cap admitted ninety and skipped thirty-four. All ninety admitted requests and the warmup succeeded with exact response IDs/model and 1,072 prompt/32 output tokens each. There were zero HTTP failures, censored requests, late-dispatch skips or horizon skips. The admission cap was preserved; no guard, rate or threshold changed during the run.

| Offered phase | Offered | Admitted/completed | Capacity-skipped | Positive queue samples / samples | Maximum sampled queue |
|---|---:|---:|---:|---:|---:|
| 0–8s, 0.5 requests/s | 4 | 4 | 0 | 0 / 16 | 0 |
| 8–16s, 1 request/s | 8 | 8 | 0 | 0 / 16 | 0 |
| 16–24s, 2 requests/s | 16 | 16 | 0 | 0 / 16 | 0 |
| 24–32s, 4 requests/s | 32 | 32 | 0 | 9 / 16 | 7 |
| 32–40s, 8 requests/s | 64 | 30 | 34 | 16 / 16 | 16 |
| 40–60s, no arrivals | 0 | — | 0 | 12 / 40 | 16 |

Completion counts in the table follow offered-arrival cohorts, including responses delivered after their phase. The 120 raw queue receipts have no sampling errors/skips or telemetry overflows; the largest receipt gap is about 0.514 seconds. Thirty-seven receipts show a positive waiting queue. These are point samples, not proof of continuous queue duration or a causal GPU diagnosis. No requests remain pending at the horizon and none complete after it. Successful scheduled-request latencies range from approximately 2.33 to 11.62 seconds; these are the **admitted cohort**, which excludes the thirty-four skipped offers.

The frozen rule requires all offered work to succeed before selection. The 4 requests/s phase's complete work and positive queue samples do **not** retrospectively authorize selecting 4 requests/s: no rate was selected, and eligibility remains failed. All fifteen later jobs are uncompleted; no collector-on/off comparison, recurrence test or evidence-withholding run exists from this campaign. The six consumer windows are unresolved because this is the collector-off role, as expected.

## Cleanup, backup and audit

The runner retained the failure and closed its owned process group. Independent checks find parent 7707, worker 7911 and the group absent, empty GPU compute process list, 0 MiB GPU memory and the supervised service EXITED. Two pre-case CUDA quiet barriers verify; the failure stops before post-case quiet/source collection. Final cleanup is not a measured healthy-recovery reference. Management services, prior workspaces and frozen archives remain intact; the rental itself is still running.

The off-host result archive SHA-256 is `8686b5b489dc6edb350a08a929a4845bacd2155f9bb0e29f2e204c7eaa14d40e`. The independent audit verifies 362 root artifact hashes, 171 frozen entries, ninety runtime source entries, eleven model files and twelve installed source pins. Installed service files match the saved wrapper/configuration. All previously passing 531 CPU tests remain the source snapshot's code checks; this step changes no runtime code or prepared schedule and adds no code-test claim.

- [Raw campaign failure](challenges_001/RESULT.json), [all job statuses](challenges_001/jobs.json), [charged budget](challenges_001/request_budget.json).
- [First job failure/cleanup](challenges_001/rate_ladder-b0-off/RESULT.json), [complete playback ledger](challenges_001/rate_ladder-b0-off/playback.json), [raw response receipts](challenges_001/rate_ladder-b0-off/requests/receipts.jsonl).
- [Actual configuration receipt](challenges_001/rate_ladder-b0-off/effective_configuration.json), [preflight hashes](challenges_031_deployment/preflight.json), [independent final process/GPU checks](challenges_031_deployment/post_cleanup_checks.json).
- [Independent validation](CHALLENGES_VALIDATION.json), [descriptive phase analysis](CHALLENGES_FAILURE_ANALYSIS.json), [auditor](challenges_031_deployment/validate_backup.py), [analysis script](challenges_031_deployment/analyze_failure.py), [backed-up result archive](challenges_031_deployment/results_backup.tar.gz).

## Next engineering decision

Step 032 should prepare a new, explicitly development-informed protocol version on CPU. A concrete candidate is a finite ladder capped at 4 requests/s while retaining the current client/journal/time budgets, followed by fresh validation. Another option is a separately justified bounded client-admission design; simply raising limits or relaxing completeness after these observations would not repair the frozen run. Predeclare offered versus admitted eligibility, exact new files and selection/failure behavior, test the revised design, and save a new source/packet snapshot before any further GPU requests. Do not overwrite or merge this failed attempt with future results.

The under-load source collector, matched observer effects and dependent cases remain unvalidated. No capture, diagnostic label/reference, calibration or main-study result is produced; scientific limits and protocol freeze remain unresolved.
