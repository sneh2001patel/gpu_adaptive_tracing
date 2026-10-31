# Prospective event challenges — step 029

This is CPU preparation for a bounded engineering pilot. [The packet](../examples/event_challenges/prepared_001/PLAN.json) contains exact offered schedules, prospective controls and budgets; **none of its GPU jobs has run**. The main study is not frozen, no scientific threshold is fitted, and no diagnostic reference is created. [Step 028](../hardware/l4_20261028/EVENTS_REPORT.md) commissioned eight sequential L4 requests only.

## Exact workload and cases

All cases use the pinned Qwen2.5-7B-Instruct long prompt (1,072 actual prompt tokens in step 028), request 32 output tokens with `ignore_eos=true`, and have a 60-second horizon plus at most 30 seconds of drain. Prefix caching must be explicitly disabled and its actual setting verified in every role. Each fresh session has one declared long-prompt/32-token warmup outside the case, ID `challenge-warmup`. There are no inference-based probe triggers or retries.

| Case | Offered schedule | Scheduled requests |
|---|---|---|
| Ladder | 0.5/1/2/4/8 requests/s for eight seconds each; no arrivals at 40–60s | 124 |
| Pressure/removal | 0.5 requests/s at 0–10s; selected rate at 10–40s; none at 40–60s | 20/35/65/125/245 |
| Lull/recurrence | 0.5 requests/s at 0–10s; selected rate at 10–25s; none at 25–30s; selected rate at 30–50s; none at 50–60s | 23/40/75/145/285 |
| Consumer evidence gap | Same offers as pressure/removal; event evidence withheld from the consumer over 10–40s | 20/35/65/125/245 |

Each phase starts an arrival at its left boundary and excludes its right boundary. Consequently 15 seconds at 0.5 requests/s offers eight requests, rather than rounding down 7.5. Each candidate selected rate has its own saved file; no rate/file is generated after inspecting outcomes. Sixteen files cover the ladder plus five candidates for each dependent case. The `phase_table`, offered SHA-256 and wire-content SHA-256 identify each one.

The legacy immutable arrival format is preserved. The future challenge completion adapter must add exactly `n=1` and `request_id=offered_request_id` to the payload, identically in both roles; [the CPU helper](../feasibility/challenge_protocol.py) hashes this exact wire transformation. This uses the restricted commissioned `B → cmpl-B → cmpl-B-0` join. Identical IDs may recur only in separate fresh sessions. Actual response IDs and token work must be checked from raw response bytes; the plan and CPU fixtures do not prove future delivery.

## Engineering pressure selection

Only `rate_ladder-b0-off`, the first uninstrumented/cache-off ladder, may select the rate. Collector-on results, predictions, stop decisions and later cases cannot influence selection.

1. Require exactly the 124 offered IDs with successful HTTP responses, 1,072 prompt/32 output tokens, no skips/censors/errors and admissions within 50 ms of their offered time. All completions must arrive by the 90-second case/drain deadline. Retain actual raw artifacts; normalized work rows are not independent evidence by themselves.
2. Require serialized, unique, exact-session/worker/model/engine queue receipts across all five eight-second levels. Each level needs at least twelve valid receipts. Acquisition width, successive receipt gaps and leading/trailing uncovered edges must each be at most 0.75 seconds. Only receipt brackets wholly inside the level count. The planned scrape cadence is 0.5 seconds; missing/failed/foreign evidence cannot become zero queue.
3. A level qualifies when at least three consecutive receipts show positive waiting queue, spanning at least one second. Select the lowest qualifying offered rate. This establishes sampled backlog evidence only; it does not measure continuous queue duration, maximum capacity or a causal diagnosis.
4. With complete evidence but no qualifying level, record `no_sampled_pressure_candidate` and skip all dependent cases. Incomplete delivery/coverage also stops dependent cases. Do not increase rates or lower guards after seeing outcomes. Run the four predeclared ladder controls before dependent cases; a failed job is retained without retry.

The selector rejects other job identities and collector-on/cache-on inputs. The future runner must also bind the declared job identity to its owned session and raw receipt files; the pure helper cannot authenticate a caller's provenance.

## Matched observer controls

For ladder, pressure/removal and lull/recurrence, use two order blocks: **off, on; on, off**. Each job starts a fresh owned engine/worker/KV cache and uses the identical schedule bytes and wire transformation within the case. This is an engineering order control, not an independently powered repetition design. Both roles share client limit 32, server sequence cap 16, cache off, model/configuration, warmup, raw metric cadence, four surrounding quiet barriers and completion/drain accounting.

Only the on role enables the scheduler hooks and fixed event RPC. Both roles collect HTTP queue metrics and raw client responses. The off role records no-op markers at planned event probe offsets without invoking an unavailable event method. Snapshot serialization, hook bookkeeping and command-file reads are part of the observer difference. No profiler or GPU sampler is introduced in this pilot, so the comparison concerns this incremental event collector, not the complete adaptive tracing system.

Probes occur before the case after warmup, at the union of ten-second boundaries and phase boundaries, and after drain: at most twelve in a ladder session, nine in a lull session and eight in the other cases. The last probe must include all terminal/aborted requests or explicitly fail coverage. The initial snapshot is expected to include the declared warmup, rather than the empty history required by step 028's no-warmup commissioning.

Before interpreting paired latency, verify offered/wire hashes, actual IDs/tokens, all terminal outcomes and admission lateness. Retain failed/mismatched pairs as ineligible and report all skips, errors and drain censoring. The implementation contract for step 030 assigns requests to fixed ten-second **offered-arrival** cohorts so both roles compare identical IDs, including complete latencies delivered in drain. A cohort needs twenty successful matched requests for p95 review. Use nearest-rank p95 (`ceil(0.95*n)`); flag a symmetric on/off p95 ratio greater than 1.25 for engineering review. Zero/missing denominators and low counts are unavailable. The flag is not a scientific equivalence test, and an unflagged pair does not establish negligible overhead. Queue trajectories and outstanding work still need review, especially during no-arrival removal windows.

`OwnedLiveActivity.start(prefix_caching=False, event_instrumentation=...)` now expresses independent cache policy. Existing ordinary and commissioning defaults are preserved. CPU tests verify the actual launch arguments for both cache values with hooks on/off. **An effective cache-setting receipt from the uninstrumented live worker is still required**; argv tests alone do not establish that setting on hardware.

## Incomplete-evidence control

Use the pressure/removal schedule with hooks enabled in all four jobs, ordered **complete, withheld; withheld, complete**. The only intended difference is consumer visibility of event evidence. Keep collecting and preserving raw event receipts. For a consumer window intersecting the half-open interval `[case_start+10s, case_start+40s)`, return unresolved with `bounds=null` and `diagnosis=null`; save the injection record separately. Do not edit source events, fabricate drops, block the scheduler, or alter client/queue evidence.

The [consumer gate](../feasibility/challenge_protocol.py) also rejects missing, invalid, foreign or not-yet-ready event receipts. A later complete receipt cannot backfill an earlier online decision; the gate uses that decision's fixed time. Outside the injection interval, bounds are available only if the source history/clock checks pass. Availability alone makes no diagnosis. This is a **consumer evidence-withholding control**, not proof of physical source loss, profiler failure or actual controller behavior. Step 030 still needs to connect and test it in the owned runner. Three masked fixture windows demonstrate the gate only; the fixtures explicitly evaluate offline at 62 seconds.

## Budgets, launch gates and evidence status

There are at most sixteen planned fresh jobs and 3,612 total inference requests including all warmups, if every case runs at the highest candidate rate. The largest session offers 285 requests plus one warmup (at most 858 normal lifecycle events), below the 512-request/4,096-event journal limits. There are at most 32 probe tokens/session; no extra warmup/control requests may be added outside the budget. Each job has a 240-second work deadline and 45-second cleanup deadline. A 50 ms admission limit does not guarantee a rented host will achieve it; misses invalidate eligibility rather than permitting compressed catch-up bursts.

The packet has `launch_supported=false`. Before a GPU challenge, step 030 must implement owned concurrent playback, raw response/receipt adapters and actual off-role cache verification; enforce selection identity, total budgets, cleanup and fixed probe/withholding clocks; then test failure/cancellation/skip paths on CPU and freeze the deployed source/packet hashes. No live challenge or paper claim is authorized by passing fixtures alone. Scientific precision, mismatch tolerances, independent reference repetitions, adjudication/blinding and calibration remain unresolved.

Reproduce CPU preparation into **new** output directories:

```bash
python3 -m revision.scripts.prepare_event_challenges --output /tmp/new_challenge_packet
python3 -m revision.scripts.demo_event_challenges --output /tmp/new_challenge_fixtures
python3 -m unittest revision.tests.test_challenge_protocol revision.tests.test_owned_live_activity
```
