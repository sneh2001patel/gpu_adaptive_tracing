## Single-valued fields
| Field | n | % agree | Cohen's κ |
|---|---|---|---|
| include (all 30) | 30 | 83% | 0.63 |
| symptom_primary (both included) | 17 | 71% | 0.62 |
| baseline_primary (both included) | 17 | 88% | 0.84 |
| multi_gpu (both included) | 17 | 100% | 1.00 |
| profiler_by (both included) | 17 | 88% | 0.55 |
| profiler_role (both included) | 17 | 88% | 0.56 |
| cause_category_primary (both included) | 17 | 71% | 0.64 |
| cause_confirmed_by (both included) | 17 | 100% | 1.00 |
| resolution (both included) | 17 | 94% | 0.91 |
| repro_candidate (both included) | 17 | 76% | 0.55 |

## Multi-valued fields (both included)
| Field | n | exact-set agree | mean Jaccard | per-label κ |
|---|---|---|---|---|
| symptom | 17 | 8/17 | 0.64 | e2e_latency 0.61, itl_tpot 0.00, memory_capacity 1.00, other 0.00, stall_hang 0.00, startup_time 1.00, throughput 0.76, ttft 0.45 |
| baseline | 17 | 11/17 | 0.75 | expectation 0.60, not_stated 0.00, other_config 0.53, other_engine 1.00, prev_version 0.87 |
| evidence | 17 | 10/17 | 0.73 | benchmark_numbers 0.68, bisect 0.56, code_reading 1.00, gpu_counters 1.00, host_counters 1.00, llm_assistant 1.00, none 0.00, other -0.09, per_step_microbenchmark 1.00, python_profiler 1.00, server_logs_metrics 0.77, torch_profiler 0.00, trace_unspecified 1.00 |
| cause_category | 17 | 10/17 | 0.68 | communication_parallelism 0.45, cpu_overhead 0.45, decode_attention_kernel 0.00, kernel_backend_selection 0.45, memory_management 0.64, model_or_algorithm_implementation 1.00, other 0.00, prefill_heavy_input 0.00, unknown 0.88, user_config_or_expectation 1.00 |
| evidence_requested | 17 | 14/17 | 0.82 | none 0.48, profile 0.00, repro_script 0.77, version_info 0.64 |

Both included: 17; coder1 included 20, coder2 19

### Disagreements: include (5)
- https://github.com/vllm-project/vllm/issues/23739 | yes |  | no | usage_question
- https://github.com/vllm-project/vllm/issues/44858 | yes |  | no | feature_request
- https://github.com/vllm-project/vllm/issues/5274 | yes |  | no | not_performance
- https://github.com/vllm-project/vllm/issues/7518 | no | usage_question | yes | 
- https://github.com/vllm-project/vllm/issues/8457 | no | feature_request | yes | 

### Disagreements: cause_category (7)
- https://github.com/sgl-project/sglang/issues/14665 | cpu_overhead;kernel_backend_selection | decode_attention_kernel
- https://github.com/sgl-project/sglang/issues/922 | prefill_heavy_input | other
- https://github.com/vllm-project/vllm/issues/11192 | communication_parallelism | unknown
- https://github.com/vllm-project/vllm/issues/2150 | communication_parallelism;memory_management | memory_management
- https://github.com/vllm-project/vllm/issues/31961 | user_config_or_expectation;cpu_overhead | user_config_or_expectation
- https://github.com/vllm-project/vllm/issues/4917 | user_config_or_expectation;kernel_backend_selection | user_config_or_expectation
- https://github.com/vllm-project/vllm/issues/7619 | memory_management | other

### Disagreements: resolution (1)
- https://github.com/vllm-project/vllm/issues/9565 | fixed_pr | fixed_pr_stale_closed

### Disagreements: repro_candidate (4)
- https://github.com/vllm-project/vllm/issues/10031 | no | maybe
- https://github.com/vllm-project/vllm/issues/4917 | maybe | yes
- https://github.com/vllm-project/vllm/issues/7619 | maybe | yes
- https://github.com/vllm-project/vllm/issues/9565 | maybe | no

### Disagreements: profiler_role (2)
- https://github.com/sgl-project/sglang/issues/14665 | decisive | supporting
- https://github.com/vllm-project/vllm/issues/2150 | decisive | none

### Disagreements: evidence (7)
- https://github.com/vllm-project/vllm/issues/10031 | benchmark_numbers;server_logs_metrics | benchmark_numbers
- https://github.com/vllm-project/vllm/issues/11192 | other | none
- https://github.com/vllm-project/vllm/issues/20316 | other;code_reading | code_reading;benchmark_numbers
- https://github.com/vllm-project/vllm/issues/2150 | torch_profiler | other
- https://github.com/vllm-project/vllm/issues/36943 | host_counters | host_counters;bisect
- https://github.com/vllm-project/vllm/issues/5523 | server_logs_metrics;gpu_counters | server_logs_metrics;gpu_counters;benchmark_numbers;bisect
- https://github.com/vllm-project/vllm/issues/9413 | benchmark_numbers | benchmark_numbers;bisect

### Disagreements: multi_gpu (0)
