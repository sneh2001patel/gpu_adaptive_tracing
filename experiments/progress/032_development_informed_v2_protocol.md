# Step 032 — development-informed v2 protocol

Completed 2026-10-28. CPU-only new protocol, exact schedule bank, version-aware runner/selection/freeze integration, tests and immutable engineering snapshot. No SSH, serving restart, inference or GPU profiling workload. [Protocol](../protocol/EVENT_CHALLENGE_PROTOCOL_V2.md).

## Completed checklist

- [x] Keep the original step-031 attempt failed, with null selection and all 124 offers/ninety completions/thirty-four skips intact.
- [x] Prepare a separately named v2 ladder at 0.5/1/2/3/4 requests/s, capped at four and explicitly informed by development data.
- [x] Compile exact rational arrival offsets so 3 requests/s creates the intended count without a rounded-period boundary arrival.
- [x] Generate sixteen exact v2 files and bind copied parent/development evidence, offered bytes, wire IDs and phase/probe tables.
- [x] Retain client/server/journal/time/coverage/completeness/control settings; reduce maximum campaign work to 1,932 warmup-inclusive attempts.
- [x] Integrate explicit version-specific loaders/selectors and packet-derived total reservation with the existing owned runner; retain v1 defaults.
- [x] Reject cross-version packets/ladders, tampered guards, missing work and incomplete/foreign queue evidence; test no-candidate skips and exact candidate-bank control flow.
- [x] Save six explicitly synthetic evidence fixtures; retain the initial CPU timing failures and their isolated diagnostics, then stabilize only the older CPU fixture timing windows.
- [x] Pass the full suite and freeze a new engineering source/packet snapshot before future live execution.
- [x] Independently audit original artifact preservation and update progress/revision plan.

## Results

V2 offers **84 ladder requests plus one warmup**, compared with v1's 124 plus one. Dependent cases keep their original phase lengths and choose only from the new fixed rate grid. The maximum is **1,932 total requests across sixteen jobs**, down from 3,612; the largest session has 145 offers plus one warmup. Client cap 32, server cap 16, journal/request/probe limits, 60/30-second horizon/drain, 30-second HTTP timeout, 50 ms lateness and strict whole-ladder completeness remain unchanged. Complete delivery or positive pressure at the new ceiling is not guaranteed; the preceding 3 requests/s phase differs from the development run's 2 requests/s phase.

The [packet](../examples/event_challenges_v2/prepared_001/PLAN.json) explicitly records development tuning, original failed status/null selection and no retrospective eligibility repair. Every request ID has a version-specific prefix. V1 still rejects the original ninety-row cohort as incomplete; v1/v2 loaders and selectors reject each other's files. No legacy artifact is edited or reinterpreted as confirmation.

All **549 CPU tests pass**, including **eighteen new v2 checks**; the focused group passes 52. The first full suite had two older real-time CPU fixture failures; both passed in isolation. The server-work fixture now uses one second of work with three-second quiet allowance, and the fixed-burst fixture uses a one-second workload horizon. Assertions are retained, initial failed/diagnostic logs are preserved, and no GPU guard is relaxed. The [six saved cases](../examples/event_challenges_v2/fixture_001/RESULT.json) are hand-authored `synthetic_simulation`, not model outputs or live observations.

The [new engineering snapshot](../examples/event_challenges_v2/snapshot_001/FREEZE.json) binds **184 entries** and twelve carried-forward installed source pins. Archive SHA-256: `a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51`. Independent audit verifies 25 new packet hashes, nineteen fixture hashes, 184 archive entries, 171 original archived entries, 362 original failed-run artifacts and 21 original packet artifacts. The original archive/descriptor/backup hashes match exactly. New source/packet/version guard rejection is checked. The old freeze correctly rejects changed working source; its untouched archived source remains reproducible.

## Limits

All sixteen v2 jobs remain unexecuted. Source pins are carried forward from the previously reviewed installation; actual installed bytes/model/GPU state must be checked again before live execution. An eight-second development phase does not establish thirty-second sustained capacity; dependent cases can still fail the unchanged work-completeness guard. Fresh work delivery, rate eligibility, under-load source history, matched observer differences and removal/lull/withholding behavior remain unvalidated. This is development-informed design, not independent confirmation, calibration, a healthy baseline or diagnostic truth. The main study is not frozen; no references, classifier fit or capture-active claims are created. Rental state was not rechecked or changed in this CPU-only step.

## Next step — 033

1. Recheck the authorized L4/instance guide, model cache and installed source hashes. Deploy the exact v2 archive/descriptor to a new supervised workspace and preserve their hashes/service files.
2. Run the v2 entrypoint with the frozen 1,932-request total and unchanged client/session/evidence guards. Preserve failure/no-pressure outcomes without automatic retries, new rates or relaxed completeness.
3. Audit offered/admitted/completed/skipped/censored work, actual cache settings, queue/source/consumer coverage and matched-cohort review. Fresh results must stay explicitly development evidence unless a separate independent confirmation design is established.
4. Verify all owned processes and GPU cleanup, back up raw data off-host and update progress before scientific reference assessment/calibration.

The next execution requires the L4. No new GPU activity was needed for this protocol revision.
