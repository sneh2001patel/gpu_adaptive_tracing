# Step 056: Calibration on the L4 and threshold freeze

Date: 2026-10-29. Host: the same L4 (vast.ai host 506934, `185.101.222.15:17499`). The main run took 15:42–20:55 UTC; the #7619 seed-101 baseline rerun took 20:55–21:02. About 5.5 L4 hours, plus the seed-100 pre-run.

## Sessions

- **Seeds 101–103:** 51 sessions, all complete.
  - Controlled: healthy plus six conditions, × 3 = 21 sessions.
  - Five real cases, fixed side: baseline plus incident, × 3 = 30 sessions.
- **Seed 100 pre-run:** kept in `cases/checks/calibration_prerun/` and never used for θ.
- **Data:** `cases/checks/calibration/`, with the derivation report in `calibration/derive_report.json`. Raw `.nsys-rep` files stayed on the host; the exported SQLite files were copied.

## Deviations from CALIBRATION_PLAN.md (recorded before the freeze)

1. **Calibration bursts replace FIX(4).** Every incident and condition session was arm NT with four bursts scheduled at 75, 105, 135 and 165 s; these never reached the controller. FIX(4) triggers on an uncalibrated θ.
2. **Host stall moved into the engine loop** (`engine_stall_v1:40`). The front-end stall did not idle the GPU under the V1 engine, and was removed at the author's request.
3. **KV pressure at 3 req/s; #3087 uses `min_latency_samples=1`.** Both were set on seed 100.
4. **#7619 seed-101 baseline rerun.** The first capture fell in an idle gap between request groups: it had no CUDA activity and crashed the analysis thread. The runner now records `analysis_failed`. The original is kept as `calibration/101/7619/baseline_idle_capture*`. Every L is recomputed from the raw in-flight age and the final baseline.
5. **All #7619 baselines censor 32 requests.** This is the last request group still in flight at the horizon, by the case's group-arrival design.

## Faults found in the derivation (fixed before any θ was shown as final)

- `baseline_idle_capture/` was loaded as a fourth #7619 incident session.
- The load-matched option paired bursts by list position. A burst with no activity is dropped, so pairing is now by capture id.
- Leave-one-out contained a spurious "without healthy" run.

Regression tests were added; `tests/test_derive_thresholds.py` passes 9/9. The full suite passes 675 tests (log: `validation/step056_full_suite/full_run1.log`).

## Result (§4 rules)

| θ | Value | Margin |
|---|---|---|
| θ_L | 1.95 | overload median L 4.24 ÷ 1.95 = 2.17 |
| θ_w | 1 | overload median 252 waiting |
| θ_u | 0.5768 | healthy p99 0.19, KV median 0.96 |
| θ_p | 0.5 (floor) | **0**: KV pressure never preempts (vLLM 0.11 queues instead) |
| θ_g | 0.769 | engine stall 0.60 vs overload 0.94 (gap 0.33) |
| θ_b | 0.7373 | engine stall 0.57 vs overload 0.90 (gap 0.33) |
| θ_r | **not separable** | option 1 max ratio 89×, option 2 92×, per-family max 20–114× |

**Leave-one-out ranges:**
- θ_L 1.70–2.00, moved by #7619 and #3087;
- θ_u 0.49–0.58, moved by #7592;
- all others constant.

### θ_r is not separable

Tokens in a burst come from the `/metrics` counters. Over a 2 s capture they are lumpy whenever prompt work dominates. Two #7619 bursts with the GPU 87% busy counted 78 and 28,512 tokens.

The capture window (2.13 s) and the token window (2.02 s) agree in every burst checked, so this is not a timing fault.

Ratios also exceed the 2.0 ceiling in units without the lumpy effect: #25418 reaches 3.1 and overlap 2.3.

### θ_L is set by group-arrival cases

Healthy p99 L is 2.08 for #7619 and 2.24 for #3087; every other unit is 1.13–1.28. The engine-stall condition has median L 1.81, so only 1% of its windows pass θ_L.

## Author decisions at the freeze

1. θ_r: accept "not separable". There is no kernel-hotspot label, and this is reported as a finding. Frozen as θ_r = ∞, so the check stays defined and the configuration counts as complete.
2. θ_L: keep the pooled 1.95.
3. θ_p: accept the zero margin.

**Frozen:**
- `cases/checks/thresholds_study_rule_v2_calibrated_2026-10-29.json`
- SHA-256 `6cd8becf0bc9f45330875cd5dc523252d0794edb1613f90263d3d01f443f961a`, equal to `RuleThresholds.digest()`
- written by `derive_thresholds.py calibration --out … --version study_rule_v2_calibrated_2026-10-29`

## Evaluation started

The evaluation plan is pre-declared in [EVALUATION_PLAN.md](../protocol/EVALUATION_PLAN.md):
- units: 5 bug-side cases plus 8 controlled conditions, two of them evaluation-only (`ctl_persistent`, `ctl_withhold`);
- arms: U, NT, FIX1, FIX3, SS, CR, HS;
- blocks: 201–203, started 21:33 UTC with `queue_evaluation.sh`.
