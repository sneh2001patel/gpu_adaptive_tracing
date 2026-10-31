# Evaluation results (blocks 201, 202, 203)

273 sessions. Units: 25418, 3087, 6240, 7592, 7619, ctl_engine_stall, ctl_kv, ctl_lull, ctl_overlap, ctl_overload, ctl_persistent, ctl_shift, ctl_withhold.

## Primary: each policy against FIX3 (paired by block and unit)

Negative difference = policy lower than FIX3. `supported` and time to a supported stop use the adjudicable units only (#6240 and #7619 excluded); time is from the episode trigger to a supported stop, censored at 240 s (the schedule length) when the stop is not supported.

With three blocks the block bootstrap has at most 10 distinct resamples, so its intervals are narrow and coarse; read them with the per-unit tables. Lower/equal/higher counts the pairs where the policy is below, equal to or above FIX3 (for `supported`, higher is better).

| Measure | Policy | Pairs | Policy mean | FIX3 mean | Mean diff | 95% CI (block bootstrap) | Wilcoxon p | Holm p | A12 | Lower/equal/higher |
|---|---|---|---|---|---|---|---|---|---|---|
| bursts | SS | 39 | 3.59 | 2.974 | 0.615 | [0.615, 0.615] | 0.12 | 0.12 | 0.418 | 22/2/15 |
| bursts | CR | 39 | 5.974 | 2.974 | 3.0 | [2.923, 3.077] | 1e-09 | 2.1e-09 | 1.0 | 0/0/39 |
| bursts | HS | 39 | 6.0 | 2.974 | 3.026 | [3.0, 3.077] | 6.7e-10 | 2e-09 | 1.0 | 0/0/39 |
| profiler_wall_s | SS | 39 | 37.345 | 37.986 | -0.641 | [-18.544, 8.381] | 0.84 | 0.84 | 0.357 | 25/0/14 |
| profiler_wall_s | CR | 39 | 69.065 | 37.986 | 31.079 | [1.953, 60.392] | 1.4e-06 | 4.2e-06 | 0.884 | 2/0/37 |
| profiler_wall_s | HS | 39 | 57.664 | 37.986 | 19.679 | [1.72, 30.361] | 2.1e-06 | 4.2e-06 | 0.878 | 2/0/37 |
| supported | SS | 33 | 0.727 | 0.636 | 0.091 | [0.091, 0.091] | 0.25 | 0.25 | 0.545 | 0/30/3 |
| supported | CR | 33 | 0.0 | 0.636 | -0.636 | [-0.636, -0.636] | 4.6e-06 | 1.4e-05 | 0.182 | 21/12/0 |
| supported | HS | 33 | 0.0 | 0.636 | -0.636 | [-0.636, -0.636] | 4.6e-06 | 1.4e-05 | 0.182 | 21/12/0 |
| t_supported_stop_s | SS | 33 | 78.462 | 104.003 | -25.54 | [-26.09, -24.727] | 1.8e-05 | 1.8e-05 | 0.245 | 24/9/0 |
| t_supported_stop_s | CR | 33 | 240.0 | 104.003 | 135.997 | [133.997, 137.18] | 9.5e-07 | 2.9e-06 | 0.818 | 0/12/21 |
| t_supported_stop_s | HS | 33 | 240.0 | 104.003 | 135.997 | [133.997, 137.18] | 9.5e-07 | 2.9e-06 | 0.818 | 0/12/21 |

## Diagnosis outcome at the initial stop (adjudicable units)

| Arm | n | Complete | Partial | Unsupported | Unresolved | Ref. unavailable | Supported rate | Wilson 95% |
|---|---|---|---|---|---|---|---|---|
| NT | 33 | 0 | 0 | 0 | 33 | 0 | 0.0 | [0.0, 0.104] |
| FIX1 | 33 | 17 | 3 | 1 | 12 | 0 | 0.606 | [0.437, 0.753] |
| FIX3 | 33 | 18 | 3 | 0 | 12 | 0 | 0.636 | [0.466, 0.778] |
| SS | 33 | 21 | 3 | 0 | 9 | 0 | 0.727 | [0.558, 0.849] |
| CR | 33 | 0 | 0 | 2 | 29 | 2 | 0.0 | [0.0, 0.104] |
| HS | 33 | 0 | 0 | 1 | 29 | 3 | 0.0 | [0.0, 0.104] |

NT has no heavy evidence and stops at the horizon, so its stop is never scored as supported; its cheap label at the trigger is scored in the RQ1 table.

## RQ1: NT cheap label at the trigger against FIX1 (adjudicable units)

Primary: the frozen rule in its in-episode mode on the trigger window (as every burst is scored). In brackets: the label the window classifier logged online, which gates on theta_L = 1.95 > trigger 1.5.

| | FIX1 supported | FIX1 not |
|---|---|---|
| NT supported | 15 (0) | 6 (3) |
| NT not | 5 (20) | 7 (10) |

| Block | Unit | Reference | NT rule label | NT first-10-windows label | FIX1 label |
|---|---|---|---|---|---|
| 201 | 25418 | host_bound | None (unresolved) | None | None (unresolved) |
| 201 | 3087 | host_bound | host_bound (complete) | host_bound | None (unresolved) |
| 201 | 6240 | kernel_hotspot:gemm | None (ref. unavailable) | None | None (ref. unavailable) |
| 201 | 7592 | kv_pressure | kv_pressure (complete) | kv_pressure | kv_pressure (complete) |
| 201 | 7619 | vocabulary_gap:redundant_prefill | host_bound (ref. unavailable) | queue_pressure | host_bound (ref. unavailable) |
| 201 | ctl_engine_stall | host_bound | host_bound (complete) | host_bound | host_bound (complete) |
| 201 | ctl_kv | kv_pressure | None (unresolved) | None | None (unresolved) |
| 201 | ctl_lull | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 201 | ctl_overlap | queue_pressure+kv_pressure | queue_pressure (partial) | queue_pressure | queue_pressure (partial) |
| 201 | ctl_overload | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 201 | ctl_persistent | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 201 | ctl_shift | queue_pressure->prefill_heavy | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 201 | ctl_withhold | queue_pressure | queue_pressure (complete) | queue_pressure | None (unresolved) |
| 202 | 25418 | host_bound | None (unresolved) | None | None (unresolved) |
| 202 | 3087 | host_bound | host_bound (complete) | None | None (unresolved) |
| 202 | 6240 | kernel_hotspot:gemm | None (ref. unavailable) | None | None (ref. unavailable) |
| 202 | 7592 | kv_pressure | kv_pressure (complete) | kv_pressure | host_bound+kv_pressure (unsupported) |
| 202 | 7619 | vocabulary_gap:redundant_prefill | host_bound (ref. unavailable) | host_bound | host_bound (ref. unavailable) |
| 202 | ctl_engine_stall | host_bound | host_bound (complete) | host_bound | host_bound (complete) |
| 202 | ctl_kv | kv_pressure | None (unresolved) | None | None (unresolved) |
| 202 | ctl_lull | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 202 | ctl_overlap | queue_pressure+kv_pressure | queue_pressure (partial) | queue_pressure | queue_pressure (partial) |
| 202 | ctl_overload | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 202 | ctl_persistent | queue_pressure | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 202 | ctl_shift | queue_pressure->prefill_heavy | queue_pressure (complete) | queue_pressure | queue_pressure (complete) |
| 202 | ctl_withhold | queue_pressure | queue_pressure (complete) | queue_pressure | None (unresolved) |
| 203 | 25418 | host_bound | None (unresolved) | None | None (unresolved) |
| 203 | 3087 | host_bound | host_bound (complete) | host_bound | None (unresolved) |
| 203 | 6240 | kernel_hotspot:gemm | None (ref. unavailable) | None | None (ref. unavailable) |
| 203 | 7592 | kv_pressure | kv_pressure (complete) | kv_pressure | kv_pressure (complete) |
| 203 | 7619 | vocabulary_gap:redundant_prefill | host_bound (ref. unavailable) | None | None (ref. unavailable) |
| 203 | ctl_engine_stall | host_bound | host_bound (complete) | host_bound | host_bound (complete) |
| 203 | ctl_kv | kv_pressure | None (unresolved) | None | None (unresolved) |
| 203 | ctl_lull | queue_pressure | None (unresolved) | queue_pressure | queue_pressure (complete) |
| 203 | ctl_overlap | queue_pressure+kv_pressure | None (unresolved) | queue_pressure | queue_pressure (partial) |
| 203 | ctl_overload | queue_pressure | None (unresolved) | queue_pressure | queue_pressure (complete) |
| 203 | ctl_persistent | queue_pressure | None (unresolved) | queue_pressure | queue_pressure (complete) |
| 203 | ctl_shift | queue_pressure->prefill_heavy | None (unresolved) | queue_pressure | queue_pressure (complete) |
| 203 | ctl_withhold | queue_pressure | None (unresolved) | queue_pressure | None (unresolved) |

## RQ2: outcome of the k-th burst (all profiled arms, adjudicable units)

| Burst | n | Supported | Unsupported | Unresolved | Ref. unavailable | Supported rate | Wilson 95% |
|---|---|---|---|---|---|---|---|
| 1 | 165 | 107 | 2 | 56 | 0 | 0.648 | [0.573, 0.717] |
| 2 | 132 | 90 | 3 | 39 | 0 | 0.682 | [0.598, 0.755] |
| 3 | 110 | 67 | 0 | 43 | 0 | 0.609 | [0.516, 0.695] |
| 4 | 75 | 44 | 0 | 31 | 0 | 0.587 | [0.474, 0.691] |
| 5 | 75 | 43 | 0 | 30 | 2 | 0.573 | [0.461, 0.679] |
| 6 | 74 | 36 | 3 | 30 | 5 | 0.486 | [0.376, 0.598] |

## Serving impact against U (paired by block and unit)

The load generator falls behind under overload in every arm, U included: `lateness` is the median over sessions of each session's median send delay, and `unsent` counts scheduled requests never sent before the horizon. The offered load is therefore not identical across arms.

| Arm | Pairs | Median p95 ratio | p95 ratio range | Completed diff (median / mean) | Worst pair | Censored diff (mean) | Unsent | Lateness (s) |
|---|---|---|---|---|---|---|---|---|
| NT | 39 | 1.004 | [0.835, 1.103] | 0 / -1.67 | ('202', 'ctl_persistent', -37) | 1.67 | 3810 | 0.0 |
| FIX1 | 39 | 1.003 | [0.781, 1.094] | 0 / 0.31 | ('201', '7592', -11) | -0.31 | 3733 | 0.0 |
| FIX3 | 39 | 1.006 | [0.803, 1.075] | 0 / -0.67 | ('203', 'ctl_persistent', -16) | 0.67 | 3771 | 0.0 |
| SS | 39 | 1.006 | [0.948, 1.408] | 0 / -1.74 | ('202', 'ctl_persistent', -55) | 1.74 | 3813 | 0.0 |
| CR | 39 | 1.006 | [0.985, 1.55] | 0 / -1.33 | ('202', 'ctl_persistent', -31) | 1.33 | 3797 | 0.0 |
| HS | 39 | 1.006 | [0.805, 1.106] | 0 / -10.1 | ('203', 'ctl_withhold', -324) | 10.1 | 4139 | 0.0 |
| U (reference) | 39 | | | | | | 3745 | 0.0 |

## Why the rule abstained (bursts with no label, reasons per unit)

| Unit | Reasons |
|---|---|
| 25418 | elevated_latency_without_firing_condition (15), unknown:kernel_time_per_token (15), unknown:kv_pressure (15), unknown:queue_pressure (15) |
| 3087 | elevated_latency_without_firing_condition (14), idle_without_pending_work (14), capture_failure:analysis_failed: OperationalError: no such table: CUPTI_ACTIVITY_KIND_KERNEL (1) |
| 6240 | elevated_latency_without_firing_condition (15), capture_failure:analysis_failed: OperationalError: no such table: CUPTI_ACTIVITY_KIND_KERNEL (1), idle_without_pending_work (1) |
| 7592 | capture_failure:analysis_failed: OperationalError: no such table: CUPTI_ACTIVITY_KIND_KERNEL (2) |
| 7619 | elevated_latency_without_firing_condition (11), capture_failure:analysis_failed: OperationalError: no such table: CUPTI_ACTIVITY_KIND_KERNEL (10), idle_without_pending_work (9) |
| ctl_engine_stall |  |
| ctl_kv | elevated_latency_without_firing_condition (15) |
| ctl_lull |  |
| ctl_overlap |  |
| ctl_overload |  |
| ctl_persistent |  |
| ctl_shift |  |
| ctl_withhold | capture_failure:withheld (15) |

## Per unit: stop reason, label and bursts per block

### 25418 (reference `host_bound`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 192.92 s | p95 170.53 s | p95 184.01 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved |
| FIX3 | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved |
| SS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| CR | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| HS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |

### 3087 (reference `host_bound`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 73.35 s | p95 92.98 s | p95 135.64 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved |
| FIX3 | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved |
| SS | diagnosis_stable · host_bound · 3b · complete | diagnosis_stable · host_bound · 3b · complete | diagnosis_stable · host_bound · 2b · complete |
| CR | budget_exhausted · host_bound · 6b · unresolved | horizon_ended · — · 5b · unresolved | budget_exhausted · host_bound · 6b · unresolved |
| HS | budget_exhausted · host_bound · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · host_bound · 6b · unresolved |

### 6240 (reference `kernel_hotspot:gemm`, unreachable by the frozen rule)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 22.99 s | p95 23.52 s | p95 22.79 s |
| NT | horizon_ended · — · 0b · ref. unavailable | horizon_ended · — · 0b · ref. unavailable | horizon_ended · — · 0b · ref. unavailable |
| FIX1 | fixed_burst_complete · — · 1b · ref. unavailable | fixed_burst_complete · — · 1b · ref. unavailable | fixed_burst_complete · — · 1b · ref. unavailable |
| FIX3 | repeated_bursts_complete · — · 3b · ref. unavailable | repeated_bursts_complete · — · 3b · ref. unavailable | repeated_bursts_complete · — · 3b · ref. unavailable |
| SS | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |
| CR | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |
| HS | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |

### 7592 (reference `kv_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 159.96 s | p95 154.03 s | p95 148.31 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · kv_pressure · 1b · complete | fixed_burst_complete · host_bound+kv_pressure · 1b · unsupported | fixed_burst_complete · kv_pressure · 1b · complete |
| FIX3 | repeated_bursts_complete · kv_pressure · 3b · complete | repeated_bursts_complete · kv_pressure · 3b · complete | repeated_bursts_complete · kv_pressure · 3b · complete |
| SS | diagnosis_stable · kv_pressure · 2b · complete | diagnosis_stable · kv_pressure · 2b · complete | diagnosis_stable · kv_pressure · 2b · complete |
| CR | budget_exhausted · — · 6b · unresolved | budget_exhausted · kv_pressure · 6b · unresolved | budget_exhausted · host_bound+kv_pressure · 6b · unsupported |
| HS | budget_exhausted · — · 6b · unresolved | budget_exhausted · kv_pressure · 6b · unresolved | budget_exhausted · host_bound+kv_pressure · 6b · unsupported |

### 7619 (reference `vocabulary_gap:redundant_prefill`, unreachable by the frozen rule)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 80.88 s | p95 52.02 s | p95 44.49 s |
| NT | horizon_ended · — · 0b · ref. unavailable | horizon_ended · — · 0b · ref. unavailable | horizon_ended · — · 0b · ref. unavailable |
| FIX1 | fixed_burst_complete · host_bound · 1b · ref. unavailable | fixed_burst_complete · host_bound · 1b · ref. unavailable | fixed_burst_complete · — · 1b · ref. unavailable |
| FIX3 | repeated_bursts_complete · host_bound · 3b · ref. unavailable | repeated_bursts_complete · — · 3b · ref. unavailable | horizon_ended · — · 2b · ref. unavailable |
| SS | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |
| CR | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |
| HS | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable | budget_exhausted · — · 6b · ref. unavailable |

### ctl_engine_stall (reference `host_bound`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 14.13 s | p95 13.98 s | p95 13.81 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · host_bound · 1b · complete | fixed_burst_complete · host_bound · 1b · complete | fixed_burst_complete · host_bound · 1b · complete |
| FIX3 | repeated_bursts_complete · host_bound · 3b · complete | repeated_bursts_complete · host_bound · 3b · complete | repeated_bursts_complete · host_bound · 3b · complete |
| SS | diagnosis_stable · host_bound · 2b · complete | diagnosis_stable · host_bound · 2b · complete | diagnosis_stable · host_bound · 2b · complete |
| CR | budget_exhausted · host_bound · 6b · unresolved | budget_exhausted · host_bound · 6b · unresolved | budget_exhausted · host_bound · 6b · unresolved |
| HS | budget_exhausted · host_bound · 6b · unresolved | budget_exhausted · host_bound · 6b · unresolved | budget_exhausted · host_bound · 6b · unresolved |

### ctl_kv (reference `kv_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 185.77 s | p95 187.62 s | p95 180.62 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved |
| FIX3 | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved |
| SS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| CR | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| HS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |

### ctl_lull (reference `queue_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 41.06 s | p95 42.33 s | p95 40.96 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete |
| FIX3 | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete |
| SS | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete |
| CR | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |
| HS | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |

### ctl_overlap (reference `queue_pressure+kv_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 39.5 s | p95 38.81 s | p95 39.16 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · queue_pressure · 1b · partial | fixed_burst_complete · queue_pressure · 1b · partial | fixed_burst_complete · queue_pressure · 1b · partial |
| FIX3 | repeated_bursts_complete · queue_pressure · 3b · partial | repeated_bursts_complete · queue_pressure · 3b · partial | repeated_bursts_complete · queue_pressure · 3b · partial |
| SS | diagnosis_stable · queue_pressure · 2b · partial | diagnosis_stable · queue_pressure · 2b · partial | diagnosis_stable · queue_pressure · 2b · partial |
| CR | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |
| HS | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |

### ctl_overload (reference `queue_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 41.07 s | p95 42.45 s | p95 41.39 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete |
| FIX3 | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete |
| SS | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete |
| CR | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · host_bound · 6b · unsupported |
| HS | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |

### ctl_persistent (reference `queue_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 41.34 s | p95 41.37 s | p95 42.86 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete |
| FIX3 | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete |
| SS | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete |
| CR | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |
| HS | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved | budget_exhausted · queue_pressure · 6b · unresolved |

### ctl_shift (reference `queue_pressure->prefill_heavy`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 49.33 s | p95 45.47 s | p95 49.32 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete | fixed_burst_complete · queue_pressure · 1b · complete |
| FIX3 | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete | repeated_bursts_complete · queue_pressure · 3b · complete |
| SS | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete | diagnosis_stable · queue_pressure · 2b · complete |
| CR | budget_exhausted · queue_pressure · 6b · ref. unavailable | budget_exhausted · queue_pressure · 6b · ref. unavailable | budget_exhausted · queue_pressure · 6b · unresolved |
| HS | budget_exhausted · queue_pressure · 6b · ref. unavailable | budget_exhausted · queue_pressure · 6b · ref. unavailable | budget_exhausted · queue_pressure · 6b · ref. unavailable |

### ctl_withhold (reference `queue_pressure`)

| Arm | 201 | 202 | 203 |
|---|---|---|---|
| U | p95 41.35 s | p95 41.25 s | p95 41.76 s |
| NT | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved | horizon_ended · — · 0b · unresolved |
| FIX1 | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved | fixed_burst_complete · — · 1b · unresolved |
| FIX3 | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved | repeated_bursts_complete · — · 3b · unresolved |
| SS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| CR | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
| HS | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved | budget_exhausted · — · 6b · unresolved |
