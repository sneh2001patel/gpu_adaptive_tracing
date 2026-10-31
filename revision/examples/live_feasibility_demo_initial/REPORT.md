# Live-feasibility gate checks on CPU

Hand-authored gate receipts and synthetic SQLite kernels; not hardware/reset/capture validation.

| Case | Gate mechanics passed | Live feasibility passed | Study ready |
|---|---|---|---|
| positive | True | False | False |
| wrong_pin | False | False | False |
| bad_hash | False | False | False |
| busy | False | False | False |
| stale_reset | False | False | False |
| future_parse | False | False | False |
| cleanup_failure | False | False | False |
| discovery_only | False | False | False |

Positive fixture receipts exercise ordered gates, including synthetic worker barriers and SQLite kernels. They do not validate those operations on hardware.

Discovery-only stops before capture when owned activity evidence is unavailable. Receipt validation and cleanup mechanics do not establish causal truth or calibration. The real read-only adapter never restarts or profiles a server.
