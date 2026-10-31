# Step 031 — frozen L4 campaign and capacity failure

Completed 2026-10-28: deploy, execute the bounded attempt, preserve the first-job failure, independently audit and back up, and verify cleanup. **The campaign does not pass.** [Hardware report](../hardware/l4_20261028/CHALLENGES_REPORT.md).

## Completed checklist

- [x] Verify idle L4/model cache, all eleven model-file hashes, 171 frozen source/input entries and twelve installed source pins.
- [x] Deploy the exact step-030 snapshot and freeze descriptor to a fresh supervised workspace, with no automatic retry/restart.
- [x] Verify actual collector-off worker configuration through the new fixed RPC before warmup/workload.
- [x] Execute the first ladder with the frozen offered files, request/clock/concurrency guards and declared warmup.
- [x] Stop the campaign on its offered-work failure; preserve all skipped offers and leave the fifteen later jobs uncompleted.
- [x] Audit raw IDs/model/token work, request/queue/consumer ledgers, exact source hashes, charged attempts and quiet/cleanup receipts.
- [x] Verify independent parent/worker/group absence and 0 MiB GPU state; copy raw results, logs and service files off-host.
- [x] Record descriptive queue/phase evidence without retrospectively selecting a rate or relabeling the run eligible.
- [x] Update the plan and progress with the failure and the next prospective design task.

## Observed outcome

The collector-off first job offers 124 arrivals and admits ninety. All ninety admitted requests plus one warmup succeed with the expected IDs, model, 1,072 prompt tokens and 32 output tokens. The 32-client in-flight cap skips thirty-four offers, all in the 8 requests/s level. There are zero request errors, censored requests or late/horizon skips. The final offered-work guard correctly rejects the job; selection never runs, and zero jobs are eligible/completed in the campaign result. No thresholds, budgets, rates or code are changed during execution, and no retry is made.

All 120 queue receipts are available, without sampling errors/skips or telemetry overflows. The 4 requests/s phase has thirty-two complete offers and nine positive queue samples; the 8 requests/s phase has thirty complete and thirty-four capacity-skipped offers, with sixteen positive queue samples. Maximum sampled waiting queue is sixteen; the largest receipt gap is about 0.514 seconds. This is descriptive development evidence of sampled backlog and client admission saturation, not a valid selected rate, continuous pressure duration, causal diagnosis or maximum-capacity estimate.

The new actual-worker configuration RPC is validated for this collector-off session: cache false, synchronous scheduling, sequence cap sixteen and parallel sizes one. Paired on/off settings and under-load source probing remain unvalidated because the campaign stops before any collector-on job. Six off-role consumer windows remain unresolved as expected; no missing-source control or reference assessment is run.

## Validation and limits

The independent audit verifies **362 artifact hashes**, **171 frozen entries**, **ninety runtime source entries**, **eleven model files** and **twelve installed source pins**. All ninety-one charged request attempts have successful raw response receipts; two pre-case quiet barriers verify. Parent 7707, worker 7911 and their process group are absent, compute process list empty and GPU memory 0 MiB. Service files and backup archive hashes match; the rental remains running. Prior deployments/artifacts and source snapshots are preserved.

All 531 CPU tests remain the frozen snapshot's previously passing checks. This step adds deployment/audit scripts, not runtime changes or new diagnostic tests. No captures, references, calibration, matched observer comparison or main-study results are produced. The audit passes; the experiment eligibility fails. Fifteen later jobs remain uncompleted rather than being treated as negative results or successful no-pressure cases.

## Next step — 032

1. Use this development outcome to prepare a separate protocol version on CPU. A finite ladder capped at 4 requests/s is a concrete candidate with unchanged client/journal/time budgets; predeclare the new exact rate bank and no-candidate/failure behavior.
2. Explicitly separate the fixed offered-work target, realized admissions and source/queue eligibility. Keep every skipped/censored offer in denominators. Do not retrospectively select 4 requests/s from the failed frozen attempt or silently relax completeness.
3. Test the revised prospective schedule/selection/control logic and save new code/packet hashes while preserving this attempt and step-030 freeze unchanged.
4. Validate fresh on the L4, retaining new failures/no-pressure outcomes. Confirm source collection/observer effects and dependent removal/lull/withholding cases before scientific calibration or adjudication.

The next protocol revision is CPU-only; the subsequent validation requires the GPU. No further GPU job is needed to finish step 031's audit.
