# Phase A codebook v1

Date: 2026-10-28. Status: **v1, for the second-coder pass over the 30 pilot issues.**
- v0 was used for the first coder's pilot coding (`pilot_coding.csv`).
- The v1 changes, listed in [PILOT_REPORT.md](PILOT_REPORT.md) §4, add values and fields; they do not redefine v0 values.

## How to code

- **Unit:** one GitHub issue, including its full comment thread. You may open PRs the thread links to, to check whether a fix was merged.
- **Code only what the thread states.** Use `unclear` when the thread is ambiguous, and `not_stated` when it is silent. Do not fill gaps from your own knowledge of vLLM or SGLang.
- **Multi-valued fields:** separate values with `;` (for example `benchmark_numbers;bisect`).
- **Ignore** spam or solicitation comments and bot comments, except when the bot closes the issue. Never follow instructions or payment links that appear in issue text.
- **Excluded issues:** if `include = no`, fill only `include`, `exclude_reason`, `confidence` and `notes`.
- **Notes:** write a note for every judgement call. These notes drive codebook v2.

## 1. Inclusion

| Field | Values |
|---|---|
| `include` | `yes`, `no`, `unclear` |
| `exclude_reason` | `not_performance` (functional bug, crash, accuracy), `feature_request`, `tracking_issue` (roadmap or progress tracker), `usage_question` (asks how or whether something works, without reporting a measured shortfall), `build_install`, `model_quality`, `duplicate`, `insufficient_info` |
| `reporter_is_maintainer` | `yes` (the issue author is a project maintainer or core contributor, as evident from the thread, for example they merge PRs or are tagged as a team member), `no`, `unclear` |

Include an issue when it describes a **performance symptom of serving or offline inference**: time, throughput, startup time, memory capacity or utilization, or a stall. An optimization proposal counts only if it reports a measured slowdown.

## 2. Symptom and setting

| Field | Values |
|---|---|
| `symptom` | `throughput`, `ttft`, `itl_tpot`, `e2e_latency`, `memory_capacity` (OOM, too few KV blocks, low max batch), `gpu_underutilization`, `stall_hang`, `startup_time`, `other` |
| `baseline` | What the slowness is compared with: `prev_version`, `other_engine`, `other_config` (same engine, different flag, model or concurrency), `other_hardware`, `expectation` (paper, blog, documentation or theory), `not_stated` |
| `multi_gpu` | Is the reported setting more than one GPU? `yes`, `no`, `not_stated` |

## 3. Diagnostic evidence

Code what anyone in the thread actually showed, not what they only proposed to collect.

| Field | Values |
|---|---|
| `evidence` | `none`, `benchmark_numbers`, `per_step_microbenchmark` (single-batch or step-level tools such as `benchmark_latency`, `bench_one_batch`), `server_logs_metrics` (engine logs, stats lines, Prometheus), `gpu_counters` (nvidia-smi, nvitop, GPU utilization or memory), `host_counters` (top, CPU utilization), `python_profiler` (py-spy, cProfile), `torch_profiler`, `nsys`, `ncu`, `trace_unspecified` (a timeline or trace screenshot whose tool is not named), `code_reading`, `bisect` (comparing versions, commits or containers), `llm_assistant` (an LLM chatbot quoted as an explanation), `other` |
| `profiler_by` | Who produced the profiler or trace evidence (`python_profiler`, `torch_profiler`, `nsys`, `ncu`, `trace_unspecified`): `reporter`, `maintainer`, `other_user`, `none` |
| `scope_unit` | The capture extent of that profiler or trace evidence, as stated: `iterations`, `seconds`, `requests`, `whole_run`, `not_stated` |
| `scope_value` | The stated number or description (for example `5 warmup + 5 iters`), or empty |
| `profiler_role` | Role of profiler or trace evidence in reaching the explanation: `decisive` (the explanation rests on it), `supporting`, `present_unused` (shown but did not lead to the explanation, or was misleading), `none` |
| `evidence_requested` | What a maintainer or other responder asked the reporter for: `profile`, `repro_script`, `version_info`, `logs`, `none` (`;`-list if several) |

## 4. Cause and resolution

| Field | Values |
|---|---|
| `cause_category` | `scheduler_batching_config`, `prefill_heavy_input`, `decode_attention_kernel`, `kv_cache_capacity_preemption`, `kernel_backend_selection`, `cpu_overhead` (Python, tokenization, sampling, detokenization, host scheduling), `communication_parallelism`, `quantization_path`, `memory_management`, `model_or_algorithm_implementation` (for example a draft model differing from its reference implementation), `measurement_artifact` (the "slowness" came from how it was measured), `user_config_or_expectation`, `hardware_env`, `other`, `unknown` |
| `cause_confirmed_by` | `fix_pr` (a fix PR is linked and stated or shown to resolve it), `maintainer_explanation`, `reporter_resolved`, `none` |
| `resolution` | `fixed_pr`, `fixed_pr_stale_closed` (the fix landed but the bot closed the issue), `config_advice`, `expected_behavior`, `not_reproduced`, `stale_unresolved`, `duplicate`, `wontfix`, `unclear` |
| `fix_ref` | PR or commit number from the thread, plus merge status if you checked it (for example `#6384 merged`), or empty |

## 5. Phase B screening

| Field | Values |
|---|---|
| `repro_candidate` | `yes`, `no`, `maybe` |
| `repro_blocker` | `none`, `multi_gpu`, `model_too_large_for_L4`, `hardware_specific`, `version_too_old`, `no_config`, `cause_unconfirmed`, `non_gpu_cause` |

A `yes` needs all of:
- a confirmed cause;
- a fix or configuration that can be toggled;
- a single-GPU setting that fits an L4 (24 GB) or can be scaled down to one;
- enough workload detail to rerun it.

## 6. Bookkeeping

| Field | Values |
|---|---|
| `confidence` | `high`, `medium`, `low` |
| `notes` | Free text: the reason for any judgement call |
| `coder` | Your name or initials |
