# Step 053: Rule v2 (author-approved fixes) and re-commissioning

Date: 2026-10-29.

## Author decisions

1. **Latency:** use the in-flight request age as the latency signal, *and* require pending work before `host_bound`.
2. **Kernels:** compare per-token GPU time by kernel family against the baseline.

## Implemented

- **`rule_diagnosis.py` v2:**
  - `kernel_time_ratio` (θ_r) replaces `kernel_share_increase`;
  - `HeavyBurst` carries `family_ns_per_token` and `family_top_kernel`;
  - pending-work guard for `host_bound`;
  - `kernel_family`, `family_time_per_token`.
- **`external_instrument.ExternalBursts.capture`:** `on_started` / `before_stop` callbacks bracket the capture window.
- **`run_episode.py`:**
  - in-flight p95 age as `L`; completed p95 kept for reporting;
  - running requests passed to the rule;
  - token counters read over the capture;
  - baseline records the median in-flight p95 and per-token family time.
- **Tests:** 656 OK in a full run.

## Re-commissioning on the L4

- Flaw 1 is fixed.
- Flaw 2 is fixed for GEMM. A residual false `kernel_hotspot:attention` remains at the provisional θ_r = 1.3: overload raises per-token attention time 1.5–2.3×.
- This sets a constraint on calibrating θ_r; the fallback is per-family thresholds or load-matched baselines.
- SS now stops after 2 bursts. HS exhausts its budget (no recovery within 6 bursts).
- Details: design doc §8.

## Scope of this step

About 0.5 L4 GPU-hours. Development data only.

## Next

Calibration sessions:
1. the healthy baseline per case configuration;
2. controlled overload, KV-pressure and lull cases;
3. each real case's toggle-off configuration at its incident load.

Then derive θ, author review, freeze.
