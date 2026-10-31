# Step 030 — owned concurrent challenge runner

Completed 2026-10-28. CPU implementation/tests, explicit synthetic episodes and an immutable engineering source snapshot. Read-only SSH retrieved three installed worker source files; no serving restart, inference or GPU profiling workload ran. [Execution contract](../protocol/CHALLENGE_EXECUTION.md).

## Completed checklist

- [x] Implement exact-bank campaign orchestration, fresh owned target lifecycles, charged request/session/campaign budgets and fail-stop/no-retry behavior.
- [x] Connect concurrent exact-arrival playback to raw response ID/model/token checks and scoped raw queue receipts.
- [x] Add a fixed actual-worker configuration RPC with bounded fresh tokens, exact identity/clock/type/configuration checks and no CUDA synchronization.
- [x] Read and fingerprint installed worker/base source inheritance; bind its hashes with the earlier source pins.
- [x] Add asynchronous fixed-offset event probes/no-op controls, warmup-inclusive final source joins and deadline-based consumer withholding without retroactive filling.
- [x] Add offered-cohort nearest-rank p95 review with twenty-matched-request floor, ineligibility on work/admission mismatch and unavailable zero denominators.
- [x] CPU-test cancellation, drain censoring, capacity skips, slow probes, failed metrics, bad response IDs, configuration mismatch and unconfirmed cleanup.
- [x] Verify no-pressure campaigns run four ladder controls then skip twelve dependent jobs; failed episodes stop without retry.
- [x] Save two successful and one expected-failure synthetic episodes; close all fake targets with no active requests.
- [x] Freeze exact source/packet/protocol/test-log hashes and source archive before any live challenge; update the revision plan and progress index.

## Validation and saved evidence

All **531 CPU tests pass**, including **twenty new tests**. The focused group passes 51 tests. [Three scaled CPU episodes](../examples/challenge_runner/fixture_001/RESULT.json) use the actual asynchronous episode code with the explicit test transport. The collector-on/off episodes each charge one warmup plus four offered requests; the failed-ID episode preserves its failed work and cleanup. These are `synthetic_simulation` with `live_validation=false`, not GPU results. Event masking preserves the backing source history; a delayed/invalid receipt or missed owner deadline remains unresolved.

The engineering [snapshot](../examples/challenge_runner/snapshot_001/FREEZE.json) binds **171 entries** and **12 installed source pins**, including the three newly reviewed worker files. Archive SHA-256: `c4bc872cb5eb0fe583e29ab94bef6c7afd466f482a80dd77b1a93bb0b18fa747`. Independent audit verifies every archive/input/source entry and all **91 fixture artifact hashes**, plus change-rejection guards. The launcher validates source/packet and installed bytes before starting serving. Historical archives, step-029 prepared bytes and existing unrelated edits are preserved.

The supplementary engineering rules are explicit before live execution: consumer deadlines are window end plus 750 ms; owner lateness beyond 50 ms is unresolved; half-second queue sampling ends at the horizon rather than providing a continuous drain trajectory. Quiet receipts and complete work/drain accounting remain available. These choices and the original packet are frozen together in this engineering snapshot; no scientific/main-study protocol is frozen.

## Limits

The new configuration RPC, under-load probe latency, exact concurrent live ID joins, realized pressure/lull/removal, and paired observer effects remain unvalidated on hardware. Pure helpers cannot authenticate arbitrary caller-provided provenance; the owned runner binds job/session/raw files. The complete/withheld pair tests consumer availability, not actual journal loss or profiler failure. Availability results do not invoke a classifier or produce references. Diagnostic accuracy, exclusive GPU phases, existing interval wait metrics, capture-active savings and main-study results remain unresolved.

No new GPU request/capture/reference/calibration or rental-state change occurs. The rental was last checked running after step 028; this step makes no new GPU-memory claim.

## Next step — 031

1. Recheck the authorized L4, pinned local model cache, idle compute state and instance guide. Deploy the exact engineering archive to a fresh workspace through a one-shot supervised service; retain local/remote archive hashes and service files.
2. Run the bounded campaign with original guards, at most sixteen jobs/3,612 warmup-inclusive attempts. Stop on failed ownership/configuration/source/coverage/work gates; keep no-pressure and failed outcomes without retries or added rates.
3. Independently audit raw responses/IDs/tokens, actual cache settings in both roles, source and queue receipt coverage, consumer deadlines/injection, offered versus actual accounting and matched-cohort review.
4. Verify serving PID/group absence and GPU memory after cleanup, copy all outputs off-host and update progress before reference assessment or scientific calibration.

The next execution needs the L4. Do not infer diagnosis, negligible observer cost, physical source loss or capture-active savings from passing this CPU implementation.
