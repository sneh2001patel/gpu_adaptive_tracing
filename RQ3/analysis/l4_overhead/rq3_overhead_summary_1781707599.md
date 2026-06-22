| Source | Workload | Reps | Auto trace s | Fixed trace s | Saved % | Auto kernels | Fixed kernels | Avoided % | Auto p95 ms | Fixed p95 ms | Auto rps | Fixed rps | Match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rq1_microbenchmark | compute_bound | 5 | 12.412 | 18.134 | 31.556 | 332.4 | 1305.2 | 74.533 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_microbenchmark | launch_overhead_or_small_kernel | 5 | 12.994 | 23.993 | 45.842 | 124877.8 | 477389.8 | 73.842 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_microbenchmark | mixed | 5 | 11.964 | 18.533 | 35.444 | 1293.0 | 5928.0 | 78.188 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_vllm_profiler_savings | queue_pressure | 3 | 104.561 | 133.545 | 21.703 | 97382.0 | 175338.0 | 44.46 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq2_vllm_multiclass | compute_saturation | 3 | 336.771 | 415.072 | 18.864 | 264744.0 | 463302.0 | 42.857 | 9812.146 | 9817.126 | 2.441 | 2.441 | 1.0 |
| rq2_vllm_multiclass | healthy | 3 | 301.255 | 391.865 | 23.123 | 189945.0 | 344715.0 | 44.898 | 3766.836 | 3806.311 | 0.267 | 0.266 | 1.0 |
| rq2_vllm_multiclass | kv_cache_pressure | 3 | 329.383 | 449.337 | 26.696 | 247290.0 | 494580.0 | 50.0 | 19804.966 | 19816.853 | 0.404 | 0.404 | 1.0 |
| rq2_vllm_multiclass | long_output | 3 | 291.005 | 397.137 | 26.724 | 293334.0 | 586477.0 | 49.984 | 30909.277 | 30943.009 | 0.129 | 0.129 | 1.0 |
| rq2_vllm_multiclass | long_prompt | 3 | 290.366 | 380.965 | 23.781 | 172668.0 | 345336.0 | 50.0 | 7510.034 | 7537.282 | 0.533 | 0.532 | 1.0 |
| rq2_vllm_multiclass | queue_pressure | 3 | 309.702 | 403.356 | 23.219 | 292230.0 | 525031.0 | 44.34 | 7150.489 | 7261.554 | 2.235 | 2.231 | 1.0 |
| rq2_vllm_multiclass_total | all_vllm_scenarios | 18 | 1858.482 | 2437.731 | 23.762 | 1460211.0 | 2759441.0 | 47.083 | 9541.103 | 9691.891 | 1.95 | 1.915 | 1.0 |
