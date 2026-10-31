# L4 live engineering pilot

GPU telemetry coverage checks passed for these completed runs.

These are actual vLLM/NVML/Nsight observations. The classifier deliberately abstains; no diagnosis accuracy, stopping safety, human benefit, or GPU capture-active savings is established. Synchronous report flushing can pause the CUDA worker and is part of the measured control/evidence latency.

| Case | Policy | Runs | Valid captures | Failures | Request errors | Mean capture-control seconds/run |
|---|---|---:|---:|---:|---:|---:|
| healthy | fixed_burst | 3 | 0 | 0 | 0 | 0.000 |
| persistent_load | counter_recovery_stop | 3 | 9 | 0 | 0 | 5.609 |
| persistent_load | fixed_burst | 3 | 3 | 0 | 0 | 1.966 |
| persistent_load | hybrid_stop | 3 | 9 | 0 | 0 | 5.820 |
| persistent_load | repeated_fixed_burst | 3 | 9 | 0 | 0 | 5.806 |
| persistent_load | stability_stop | 3 | 9 | 0 | 0 | 5.690 |

Capture-control seconds include control/RPC/flush latency; they are not GPU capture-active seconds. Kernel counts are actual captured instances, not estimates of all workload kernels. Report/export/parse delays are recorded separately; overlapping timing scopes must not be added.

Telemetry: 0 sampling errors; 0 missing GPU windows across 0 runs.
Integrity: 78 artifact hashes checked; 0 mismatches.
Readiness: 39/39 decisions had parsed evidence available.
Continuation: 39/39 decisions were followed by new admissions; 39/39 by completions.

The three repetition/seed labels do not establish statistical independence: arms share a persistent server, greedy generation, cache state and one calibration cohort. Offered arrival slots can be skipped at the in-flight cap; consult admissions/skips/drain before claiming equal realized workloads. No confidence intervals or effect-significance claims are made.

Next: independent reference evidence and T2 classification/calibration; changed/lull/overlap cases; matched no-profiler and cheap-only controls; active-capture boundary validation; then a frozen held-out protocol.
