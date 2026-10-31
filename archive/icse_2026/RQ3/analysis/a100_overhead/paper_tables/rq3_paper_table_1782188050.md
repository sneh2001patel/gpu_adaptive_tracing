| Source | Workload | Reps | Saved % | Kernel avoided % | Match | Auto p95 ms | Fixed p95 ms | p95 regress % | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rq1_microbenchmark | compute_bound | 5 | 37.631 | 76.219 | 1.0 | 0.0 | 0.0 | 0.0 | yes |
| rq1_microbenchmark | launch_overhead_or_small_kernel | 5 | 48.549 | 74.041 | 1.0 | 0.0 | 0.0 | 0.0 | yes |
| rq1_microbenchmark | mixed | 5 | 39.166 | 76.579 | 1.0 | 0.0 | 0.0 | 0.0 | yes |
| rq1_vllm_profiler_savings | queue_pressure | 3 | 23.51 | 50.009 | 1.0 | 0.0 | 0.0 | 0.0 | yes |
| rq2_vllm_multiclass | compute_saturation | 3 | 29.586 | 50.0 | 1.0 | 2402.667 | 2365.749 | 1.561 | yes |
| rq2_vllm_multiclass | healthy | 3 | 28.701 | 49.505 | 1.0 | 910.879 | 918.982 | -0.882 | yes |
| rq2_vllm_multiclass | kv_cache_pressure | 3 | 27.9 | 50.0 | 1.0 | 5117.857 | 5109.373 | 0.166 | yes |
| rq2_vllm_multiclass | long_output | 3 | 26.227 | 44.429 | 1.0 | 7199.396 | 7206.735 | -0.102 | yes |
| rq2_vllm_multiclass | long_prompt | 3 | 26.834 | 47.826 | 1.0 | 2004.252 | 2005.546 | -0.065 | yes |
| rq2_vllm_multiclass | queue_pressure | 3 | 28.527 | 50.0 | 1.0 | 1827.059 | 1799.226 | 1.547 | yes |
| rq2_vllm_multiclass_total | all_vllm_scenarios | 18 | 27.959 | 48.314 | 1.0 | 2393.972 | 2357.611 | 1.542 | yes |
