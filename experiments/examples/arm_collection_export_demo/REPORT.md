# CPU arm collection and export checks

Real CPU HTTP admission waits; synthetic kernel/device reports. Phase attribution unavailable. Classifier abstains. No GPU metrics/cost/diagnosis validation.

| Arm | Valid wait intervals | Measured capture observations | Initial stops | Owned group absent |
|---|---:|---:|---:|---|
| no_profiler | 0 | 0 | not applicable | True |
| cheap_only | 8 | 0 | not applicable | True |
| fixed_burst | 8 | 1 | 1 | True |
| repeated_fixed_burst | 8 | 3 | 1 | True |
| stability_stop | 8 | 3 | 1 | True |
| counter_recovery_stop | 5 | 3 | 1 | True |
| hybrid_stop | 8 | 3 | 1 | True |
| full_horizon_reference | 8 | 1 | not applicable | True |

Six fault cases retain missing/reset/generation/clock/history-overflow/late source evidence. Late receipts do not rewrite closed windows.

Policy export uses original capture observations with null cause assertions; cheap windows remain separate intervals. Independent references and calibrated diagnosis remain pending.
