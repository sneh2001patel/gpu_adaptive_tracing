# Locked-reference initial-stop scoring

Provenance: `synthetic_simulation`. Offline agreement with declared locked adjudications; not diagnosis validation or stopping safety.

Reference lock: `eacf48b4da8dca15724cf1a90bf3bd4a910ffe90fa0c9c52114da1f5c7b38af2`.

| Diagnosis outcome | Initial stops |
|---|---:|
| supported_complete | 1 |
| supported_partial | 1 |
| unsupported_concrete | 2 |
| unresolved | 3 |
| reference_unavailable | 5 |

All logged activated episodes: 12; adjudicable references: 7; unavailable: 5.
Stable unsupported: 2; stable incomplete: 1; stable unadjudicable: 3.

Failures, budget exhaustion, recovery and horizon censoring retain distinct reason/status counts in SCORE.json. An unresolved/unavailable result is never silently counted as a correct healthy diagnosis. A generic mixed label supplies no cause coverage.

The denominator is conditional on the supplied hashed activation snapshot. Missed incident detection, false activations against a full incident census, human benefit, profiler cost and empirical classifier calibration are not established.
