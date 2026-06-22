| Scenario | Reps | Orders | No-prof p95 ms | Cheap p95 ms | p95 regress % | No-prof rps | Cheap rps | Throughput change % | Success | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| queue_pressure | 5 | no_profiler\|cheap_metrics_only;cheap_metrics_only\|no_profiler;cheap_metrics_only\|no_profiler;cheap_metrics_only\|no_profiler;no_profiler\|cheap_metrics_only | 7142.66 | 6886.169 | -3.556 | 2.448 | 2.398 | -0.982 | 100.0 | yes |
| healthy | 3 | cheap_metrics_only\|no_profiler;cheap_metrics_only\|no_profiler;no_profiler\|cheap_metrics_only | 3698.749 | 3722.236 | 0.646 | 0.271 | 0.27 | -0.475 | 100.0 | yes |
