# Step 029 — exact challenges and observer controls

Completed 2026-10-28. CPU preparation only; no SSH connection, serving restart or GPU workload. [Operating protocol](../protocol/EVENT_CHALLENGE_PROTOCOL.md).

## Completed checklist

- [x] Generate sixteen exact offered files: one ladder and five rate candidates for each removal, lull/recurrence and consumer-gap case.
- [x] Preserve the legacy arrival schema and hash the declared wire overlay supplying exact commissioned request IDs and `n=1`.
- [x] Define first collector-off ladder selection, exact work/coverage gates and explicit no-candidate/incomplete outcomes.
- [x] Predeclare two reversed-order blocks with fresh sessions, common raw collection/cache/work settings and bounded probes.
- [x] Separate explicit prefix-cache policy from scheduler opt-in; test on/off combinations while retaining prior defaults.
- [x] Implement a consumer-only missing-evidence gate that preserves raw receipts and returns unresolved for masked/invalid/late evidence.
- [x] Bound every schedule and overall job/request/warmup/probe/drain budget; reject tampered files and foreign/duplicate/reversed receipts.
- [x] Save six explicit synthetic selection cases and the event-withholding fixture, with no live-validation/diagnostic claims.
- [x] Update progress, revision plan and current instrumentation documentation.

## Results

All **511 CPU tests pass**, including **17 new tests** (15 challenge tests and two owned-startup tests). The [prepared packet](../examples/event_challenges/prepared_001/PLAN.json) has sixteen schedules and sixteen planned jobs, all unexecuted. Twenty-one prepared artifact hashes and twenty-one fixture hashes are verified separately; validation also regenerates phase/wire hashes. The worst-case inference budget is 3,612 requests across all jobs including warmups; the largest single session has 286. No GPU source deployment or rental-state change occurs here.

The ladder offers 124 requests over five eight-second levels followed by twenty seconds without arrivals. A candidate requires exact successful work and complete raw queue coverage across all levels, then three consecutive positive queue receipts spanning at least one second. Only the first collector-off job may select the lowest qualifying rate. The six saved cases distinguish zero queues, isolated spikes, lowest qualifying 2 requests/s, a missing metric receipt, missing work and foreign scope. All are hand-authored CPU fixtures, not observations of GPU pressure.

Collector-on/off jobs share exact offered bytes and wire IDs; cache policy can now be explicitly false independently of hooks. Complete/withheld control jobs all enable hooks and differ only in consumer event visibility at 10–40 seconds. Masked windows retain unavailable bounds/diagnosis; raw source evidence is unchanged. Future receipts cannot repair earlier decision-time availability. The existing classifier and interval wait/phase metrics remain unchanged.

## Limits and decisions

This prepares contracts and arithmetic schedule playback checks, not an owned concurrent GPU runner. The off-role effective cache receipt, complete raw response joins under concurrency, fixed-time probe/injection integration, realized pressure/removal/lull behavior and observer comparison still need implementation/live validation. The source helper relies on a future owned runner to bind the named primary job to raw receipts; its arguments are not authentication. Engineering sampling/latency-review guards are prospective choices, not calibrated diagnoses, scientific equivalence or a power guarantee. No references/locks/fits or main-study freeze are created. Historical frozen archives and pilots are preserved.

## Next step — 030

1. Implement the bounded owned challenge runner using these exact bank files, the declared wire overlay and independent cache policy. Persist actual effective cache settings in both roles before sending workload.
2. Connect raw HTTP responses and session-bound queue/event receipts to exact request-ID/token accounting. Enforce primary-job selection, no-candidate skips, total request/probe budgets and fixed clocks for consumer withholding.
3. CPU-test concurrency/backpressure, slow probes, missing receipts, cancellation/drain and owned cleanup. Implement the predeclared matched-cohort latency review without lowering sample floors.
4. After CPU checks, freeze source and packet hashes before a supervised bounded L4 run; audit all raw artifacts and realized behavior. Preserve failures/no-pressure outcomes without adding rates or retries.

Runner implementation/testing is CPU-only. The subsequent live run requires the L4. No further GPU access was needed for step 029.
