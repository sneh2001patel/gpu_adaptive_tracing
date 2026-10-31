# Event challenge protocol v2 — development revision, step 032

This is a **new, CPU-prepared development protocol**, not a repair or rerun of the failed frozen v1 attempt. [The original outcome](../hardware/l4_20261028/CHALLENGES_REPORT.md) remains failed: 124 offers, ninety admitted completions, thirty-four client-capacity skips, zero eligible jobs and no selected rate. Its data informed this revision and is not independent confirmation, a diagnostic reference or a healthy baseline.

## Prospective change and unchanged gates

The new ladder offers **0.5, 1, 2, 3 and 4 requests/s**, each for eight seconds, followed by twenty seconds with no arrivals. It has **84 offers plus one warmup**, replacing v1's 124 offers plus one warmup. The 8 requests/s level is removed; 3 requests/s fills the gap below the new ceiling. In the development run, the 4 requests/s phase delivered all thirty-two offers and had nine positive queue samples, whereas the 8 requests/s phase hit the client cap. This motivates a candidate ceiling; it does not guarantee complete delivery or pressure in a fresh run, particularly with the new preceding 3 requests/s phase.

Client concurrency stays **32**, server sequence cap **16**, per-session journal limits **512 requests/4,096 events**, horizon/drain **60/30 seconds**, request timeout **30 seconds**, admission lateness **50 ms**, and source-probe budget **32**. All sixteen prospective fresh-session jobs retain their two reversed-order blocks, cache-off settings, shared corpus and exact wire overlays. Source probe offsets, ten-second windows, 750 ms consumer decision grace, twenty-completion p95 floor, 0.75-second queue receipt gap guard and 1.25 paired-latency review flag are unchanged. No classifier, profiler or reference export is enabled.

Only total offered work and the rate grid change; the strict eligibility requirements do not. All scheduled offers must be admitted in time and return successful exact-ID/model/token responses. Every offer, skip, error and censor remains in the ledger denominator. Require complete queue coverage across all five levels before the first collector-off ladder may select the lowest level with three consecutive positive receipts spanning at least one second. Missing work or coverage cannot be interpreted as zero queue or be dropped from selection. No candidate stops dependent cases; a failed job stops the campaign without retry or automatic guard/rate adjustment.

## Exact arrivals and budget

The compiler treats a rate as an exact rational `p/q`. A phase of duration `D` seconds offers `ceil(D*p/q)` requests at independent offsets `floor(i*1e9*q/p)`. Each phase includes its left boundary and excludes its right boundary. This avoids an extra near-boundary arrival caused by repeatedly adding a rounded 333,333,333 ns period at 3 requests/s. The three-per-second eight-second level has exactly twenty-four offers. Every v2 request ID has a `v2-` prefix; v1 and v2 canonical ladders are rejected by each other's selector/loader.

| Case | Candidate rates | Maximum scheduled offers | With warmup |
|---|---|---:|---:|
| Ladder | Fixed five-level grid | 84 | 85 |
| Pressure/removal | 0.5, 1, 2, 3, 4 requests/s | 125 | 126 |
| Lull/recurrence | Same grid | 145 | 146 |
| Consumer evidence withholding | Same grid, same pressure/removal offers | 125 | 126 |

Four jobs per case give a **maximum of 1,932 inference attempts including warmups**. The largest session is 146 requests, at most 438 ordinary lifecycle events. No per-session client, journal, timeout or drain allowance is raised. The runner now obtains the campaign total from the validated packet, so v2 cannot silently inherit the old 3,612-request allowance. A mock CPU campaign selecting 3 requests/s reserves 1,552 attempts; this is control-flow validation only, not executed serving work.

## Data separation and input integrity

The [new packet](../examples/event_challenges_v2/prepared_001/PLAN.json) records version `event_challenge_preparation_v2`, exact rate/phase tables, offered/wire hashes, immutable copied parent/development inputs and explicit `development_tuning_not_independent_confirmation` scope. Its parent manifest is pinned to the original v1 packet SHA-256 `e7b6bac5ec791f7ba3892be6031421fa6f5d1f857ad1382164f8142a4fafd8aa`. The builder checks every original failed-run artifact against its manifest before creating a new output directory. The copied result/playback hashes, all 124 original IDs/offsets, ninety complete/thirty-four skipped outcomes and null original selection remain mandatory.

The v2 loader verifies all packet hashes and regenerates the entire expected plan and exact offered bytes. Rewriting a local manifest to accept changed client limits, incomplete-work rules, masking controls or rate files does not make those changes valid. Original run artifacts, backup, v1 packet and engineering snapshot are never rewritten. Runtime helpers are refactored with explicit version-specific loader/selector injection and v1 defaults retained. Changed working source correctly fails the old freeze's source guard; the original code remains reproducible from its untouched archive.

V1 and v2 remain separately named packets and entrypoints. The v2 live launcher requires a new engineering freeze descriptor bound to the v2 version, source/input hashes and 1,932-request total. Freeze records are engineering source snapshots; `hardware_validated`, `study_ready` and scientific `protocol_frozen` remain false. A passing CPU log and new source archive are prerequisites to fresh GPU execution, not proof of eligibility or diagnostic correctness.

## CPU validation and fresh-run requirement

Tests cover exact rational offsets/counts, unchanged budgets/gates/order, model/corpus and failed-data bindings, version rejection, manifest tampering, missing/late work, queue gaps/foreign scope and no-candidate skips. Six hand-authored evidence fixtures remain `synthetic_simulation`, with `live_validation=false`: zero queue, isolated spike, lowest qualifying 3 requests/s, qualifying 4 requests/s, metric gap and missing work. The original ninety-row admitted cohort still returns `incomplete_work` under v1; it never becomes a v2 rate selection.

The first full CPU suite exposed two older wall-clock fixture assumptions (150 ms server work and a 300 ms capture/workload horizon); both passed in isolation. Their test-only work/quiescence/horizon windows are extended while retaining the same assertions. Initial failures and isolated diagnostics are preserved alongside the final log in the new engineering snapshot. No GPU deadline, capacity or eligibility guard is relaxed by those fixture changes.

The final full suite passes **549 tests**, including eighteen new v2 checks. [Saved packet, fixture and preservation audits](../examples/event_challenges_v2/REPORT.md) distinguish these CPU results from future live validation. No SSH or GPU workload is used in step 032.

Next step 033 deploys the separately frozen v2 archive to a fresh supervised workspace and validates the bounded campaign. Retain failures or no-pressure outcomes, actual-versus-offered accounting, configuration/source/queue coverage and final cleanup. Under-load event collection, paired observer cost and removal/lull/withholding behavior are still unvalidated. Any further rate/eligibility revision must be a new documented development version with fresh validation. Scientific precision, reference mismatch limits, independent repetitions, adjudication/blinding and diagnosis calibration remain unresolved; development-informed results cannot serve as untouched confirmatory results.

```bash
python3 -m revision.scripts.prepare_event_challenges_v2 --output /tmp/new_v2_packet
python3 -m revision.scripts.demo_event_challenges_v2 --output /tmp/new_v2_fixtures
python3 -m revision.scripts.run_l4_challenges_v2 --help
```
