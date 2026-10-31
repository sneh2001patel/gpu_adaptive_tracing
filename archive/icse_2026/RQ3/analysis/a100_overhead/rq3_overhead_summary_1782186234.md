| Source | Workload | Reps | Auto trace s | Fixed trace s | Saved % | Auto kernels | Fixed kernels | Avoided % | Auto p95 ms | Fixed p95 ms | Auto rps | Fixed rps | Match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rq1_microbenchmark | compute_bound | 5 | 10.397 | 16.67 | 37.631 | 454.4 | 1910.8 | 76.219 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_microbenchmark | launch_overhead_or_small_kernel | 5 | 11.917 | 23.162 | 48.549 | 154829.8 | 596429.8 | 74.041 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_microbenchmark | mixed | 5 | 10.224 | 16.807 | 39.166 | 2344.0 | 10008.0 | 76.579 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq1_vllm_profiler_savings | queue_pressure | 3 | 103.314 | 135.069 | 23.51 | 330831.333 | 661779.667 | 50.009 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rq2_vllm_multiclass | compute_saturation | 3 | 282.862 | 401.714 | 29.586 | 996920.0 | 1993846.0 | 50.0 | 2402.667 | 2365.749 | 10.154 | 10.164 | 1.0 |
| rq2_vllm_multiclass | healthy | 3 | 285.276 | 400.111 | 28.701 | 717570.0 | 1421070.0 | 49.505 | 910.879 | 918.982 | 1.118 | 1.116 | 1.0 |
| rq2_vllm_multiclass | kv_cache_pressure | 3 | 278.21 | 385.865 | 27.9 | 741870.0 | 1483740.0 | 50.0 | 5117.857 | 5109.373 | 1.566 | 1.566 | 1.0 |
| rq2_vllm_multiclass | long_output | 3 | 306.51 | 415.477 | 26.227 | 1466922.0 | 2639708.0 | 44.429 | 7199.396 | 7206.735 | 0.561 | 0.562 | 1.0 |
| rq2_vllm_multiclass | long_prompt | 3 | 282.216 | 385.721 | 26.834 | 690672.0 | 1323788.0 | 47.826 | 2004.252 | 2005.546 | 2.003 | 2.001 | 1.0 |
| rq2_vllm_multiclass | queue_pressure | 3 | 283.368 | 396.469 | 28.527 | 993217.0 | 1986434.0 | 50.0 | 1827.059 | 1799.226 | 8.934 | 8.935 | 1.0 |
| rq2_vllm_multiclass_total | all_vllm_scenarios | 18 | 1718.442 | 2385.357 | 27.959 | 5607171.0 | 10848586.0 | 48.314 | 2393.972 | 2357.611 | 7.801 | 7.849 | 1.0 |
