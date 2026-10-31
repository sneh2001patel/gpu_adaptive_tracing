# Step 028 — owned scheduler-event commissioning

Completed 2026-10-28. CPU implementation and one bounded supervised L4 run; all eight requests pass. [Hardware report](../hardware/l4_20261028/EVENTS_REPORT.md).

## Completed checklist

- [x] Add explicit owned-startup opt-in for the pinned scheduler, event route and disabled prefix cache; save effective config.
- [x] Add a fixed idle worker RPC accessing the scheduler journal in the same process/interpreter, with session/clock/UUID/PID checks and capture exclusion.
- [x] Make hook/RPC observation of an unchanged consumed command idempotent without refreshing the saved timestamp; reject changed commands and preserve the journal's anti-replay contract.
- [x] Review and pin installed completion/processor/async/CLI sources; implement the exact restricted single-prompt, single-choice request-ID join.
- [x] CPU-test opt-in/default isolation, no CUDA synchronization in the idle RPC, foreign identity/missing registry/capture rejection, replay handling, exact joins, budgets, token work and clock brackets.
- [x] Freeze the source archive and eight-request plan before execution; deploy to a fresh owned workspace/service and run zero additional inference triggers/warmups.
- [x] Validate all eight live client/engine IDs, actual token work, 24 lifecycle events, two fresh same-host idle probes and four quiet barriers.
- [x] Close owned jobs, independently verify PID/group absence and 0 MiB, copy evidence off-host and audit hashes/source/service files.
- [x] Update the progress index, revision plan and instrumentation contract.

## Implementation and evidence

`OwnedLiveActivity.start(event_instrumentation=True)` sets the event flag and exact scheduler/cache arguments. Default launches clear an inherited event flag. The source registry fails if the scheduler and CUDA worker do not share the expected interpreter/PID. The fixed RPC takes a CPU journal snapshot without an inference request or CUDA synchronization; quiet CUDA barriers remain a separate check.

The [runner](../scripts/run_l4_events.py) saves eight charged attempts before sending, uses concurrency one, and stops on failure without retries or challenges. A 240-second work deadline and 45-second cleanup deadline bound execution. Its final snapshot includes every request's terminal event, avoiding the earlier admission-triggered-probe completeness problem.

The restricted installed-source mapping is payload `request_id=B`, response `cmpl-B`, engine `cmpl-B-0`. This scope requires a single string prompt, `n=1`, nonstreaming output, no beam/best-of or overriding header. Every live response matches exactly; no arbitrary suffix stripping is used. Four prompts contain 17 tokens and four contain 1,072; all responses report 32 output tokens. Raw source snapshots retain conservative ID-mapping metadata, while separate commissioning receipts establish this restricted join.

Actual worker 7200 matches the scheduler binding and selected L4 UUID; prefix caching is false, sequence cap 16 and async scheduling false. Initial history is empty; final history has eight admissions, eight first CPU scheduling decisions and eight length-capped terminal events, with zero drops/faults. All source probe and per-request lifecycle brackets pass. No p95, GPU execution/phase mapping or existing wait metric is populated.

## Validation and limits

All **494 CPU tests pass** (ten new). The independent off-host audit verifies **46 artifact hashes**, **142 archived entries**, **81 runtime source entries** and **eight installed ID/CLI pins**. The actual installed service files match the saved copies. Parent 6983, worker 7200 and their process group are absent; compute process list is empty, GPU memory 0 MiB and the one-shot service exited. The rental remains running; management services and prior artifacts are preserved.

This validates instrumentation feasibility for eight sequential requests on this pinned stack. It does not measure observer effects or validate pressure, short lulls, recovery, aborts/concurrency, percentile precision, scientific thresholds, references or diagnosis. Host first-scheduling delay excludes frontend time, later preemption and GPU execution. Zero captures/references/calibration/challenges are created; the main study is not frozen.

## Next step — 029

1. Materialize exact offered files and freeze a deterministic pressure-selection rule with an explicit no-pressure outcome. Keep all request/drain/probe budgets prospective.
2. Define paired observer-on/off controls with the same effective cache/serving settings and actual ID/token accounting. The current commissioning opt-in couples cache disabling to instrumentation, so controlled challenge runners must set cache policy independently for both roles.
3. Define incomplete-evidence injection and expected abstention/coverage checks without fabricated diagnostic labels. Add CPU playback/budget checks and document prospective selection/mismatch criteria.
4. After those files and rules are saved, run the bounded L4 ladder/removal/lull/unresolved cases, auditing realized pressure and observer differences before reference assessment or fitting.

The next protocol/schedule preparation can run without a GPU. The subsequent live challenges require the L4. Scientific precision/repetition/equivalence criteria remain a separate prerequisite for confirmation.
