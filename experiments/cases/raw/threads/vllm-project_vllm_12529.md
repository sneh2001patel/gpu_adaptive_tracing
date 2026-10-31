# vllm-project/vllm#12529: [Performance]: V1 higher memory usage
state=closed reason=completed created=2025-01-28T22:23:50Z closed=2025-03-14T03:40:24Z labels=['performance', 'v1']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/13776', 'https://github.com/vllm-project/vllm/pull/14728']

## body (@wedobetter)
### Proposal to improve performance

_No response_

### Report of performance regression

*Hardware:* 4x RTX 3070 = 32GB VRAM

*Issue:* I was able to run `Qwen/Qwen2.5-Coder-32B-Instruct-GPTQ-Int4` with 12K context length with 0.6.x, now with `0.7.0 + VLLM_USE_V1=1` I cannot push the context length higher than 3K or encountering a CUDA OOM error. 
Of course, I can reconfigure it to avoid OOM, my question is: *Is V1 expected to consume more memory?*


Some of the libraries:
```
flashinfer==0.1.6+cu124torch2.4
torch==2.5.1
transformers==4.48.1
vllm==0.7.0
```

*VLLM command*
```
        - vllm
        - serve
        - Qwen/Qwen2.5-Coder-32B-Instruct-GPTQ-Int4
        - --gpu-memory-utilization=1
        - --tensor-parallel-size=4
        - --load-format=auto
        - --enforce-eager
        - --swap-space=0
        - --max-model-len=12K
        - --max-num-batched-tokens=12K
        - --disable-fastapi-docs
[... 1 lines truncated ...]
        - --tool-call-parser=hermes
```

Thanks

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @WoosukKwon 2025-01-28T22:43:29Z
Hi @wedobetter thanks for reporting the issue. We will take a look at the memory profiling part of V1. Meanwhile, could you please try lower `pu-memory-utilization` like 0.95 or 0.9? Generally, We don't recommend 1.0 because our memory profiling is not 100% accurate (since we do dynamic memory allocation during run time).

## comment @mgoin 2025-01-29T00:58:38Z
I think you could also try reducing `--max-num-batched-tokens=12K`, this could be much smaller like 2k and might reduce peak activations for memory and from torch.compile compilation

## comment @DarkLight1337 2025-01-29T03:56:24Z
I have noticed similar issues for VLMs as well. See [Slack thread](https://vllm-dev.slack.com/archives/C07QCGVDNUF/p1735656611474479?thread_ts=1735568905.344979&cid=C07QCGVDNUF). cc @ywang96 

## comment @wedobetter 2025-01-29T06:42:58Z
> I think you could also try reducing `--max-num-batched-tokens=12K`, this could be much smaller like 2k and might reduce peak activations for memory and from torch.compile compilation

As I stated, I know how to reconfigure the execution parameters, my observation was OOM encountered just by upgrading from latest 0.6.x to 0.7.0 VLLM and enabling V1, while keeping all the runtime parameters the same 

## comment @wedobetter 2025-01-29T06:46:10Z
> Hi [@wedobetter](https://github.com/wedobetter) thanks for reporting the issue. We will take a look at the memory profiling part of V1. Meanwhile, could you please try lower `pu-memory-utilization` like 0.95 or 0.9? Generally, We don't recommend 1.0 because our memory profiling is not 100% accurate (since we do dynamic memory allocation during run time).

Thanks for your input. I generally set that to 1, fearing that CPU offloading can significantly affect performance but I have probably confused gpu-memory-utilization with cpu_offload_gb options. 

## comment @robertgshaw2-redhat 2025-01-30T17:35:19Z
Thanks for the feedback. Note for contributors -- another place to look is torch.compile and the number of cudagraphs we use

## comment @Leon-Sander 2025-01-30T20:05:25Z
> (since we do dynamic memory allocation during run time).

Can you elaborate a bit more on what exactly is dynamic?

## comment @focuzz8 2025-01-31T23:50:20Z
I can confirm increased memory consumption with **Qwen/Qwen2.5-32B-Instruct-AWQ**
_Hardware: 2x RTX 4070 Ti = 32GB VRAM_
I suspect that @robertgshaw2-redhat is correct and problem is related to the torch.compile.

## comment @chelseaztq 2025-02-07T11:56:25Z
I have the same issue. When deploying the DeepSeek R1 32B distilled model, the GPU memory usage under the v1 engine is higher than under v0. This causes the v1 engine to run out of memory (OOM) under the same configuration, while v0 does not.
 


## comment @rohan-uiuc 2025-02-13T17:50:36Z
I have the same issue, blocking me to use V1 arch. I tried using the same configuration as with V0, also tried reducing gpu memory utilization from 0.95 to 0.8 but to no luck always resulting in an OOM on startup. 

Also, it takes extremely long for the server to warmup as compared to V0. 

## comment @JaheimLee 2025-02-20T09:29:42Z
same issue

## comment @fahadh4ilyas 2025-03-10T04:51:36Z
Same issue but only on llama3.1 #14286 

## comment @ywang96 2025-03-10T07:08:43Z
https://github.com/vllm-project/vllm/pull/14508 should fix this

## comment @ywang96 2025-03-11T16:46:47Z
Now that #14508 is merged, can you try the nightly build and see if the issue is still there? Thanks!

## comment @fahadh4ilyas 2025-03-12T08:00:30Z
I still got the error. Here is the log

<details>

<summary>Log vllm v0</summary>

```
INFO 03-12 14:55:20 [__init__.py:256] Automatically detected platform cuda.
INFO 03-12 14:55:20 [api_server.py:912] vLLM API server version 0.7.4.dev390+gdebd6bbf
INFO 03-12 14:55:20 [api_server.py:913] args: Namespace(subparser='serve', model_tag='models/llama3.1-8B-INT8', config='', host='0.0.0.0', port=8000, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key=None, lora_modules=None, prompt_adapters=None, chat_template=None, chat_template_content_format='auto', response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, enable_ssl_refresh=False, ssl_cert_reqs=0, root_path=None, middleware=[], return_tokens_as_token_ids=False, disable_frontend_multiprocessing=False, enable_request_id_headers=False, enable_auto_tool_choice=True, tool_call_parser='llama3_json', tool_parser_plugin='', model='models/llama3.1-8B-INT8', task='auto', tokenizer=None, hf_config_path=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, allowed_local_media_path=None, download_dir=None, load_format='auto', config_format=<ConfigFormat.AUTO: 'auto'>, dtype='auto', kv_cache_dtype='auto', max_model_len=65536, guided_decoding_backend='xgrammar', logits_processor_pattern=None, model_impl='auto', distributed_executor_backend=None, pipeline_parallel_size=1, tensor_parallel_size=1, enable_expert_parallel=False, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=None, enable_prefix_caching=None, disable_sliding_window=False, use_v2_block_manager=True, num_lookahead_slots=0, seed=None, swap_space=4, cpu_offload_gb=0, gpu_memory_utilization=0.9, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_partial_prefills=1, max_long_partial_prefills=1, long_prefill_token_threshold=0, max_num_seqs=None, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, hf_overrides=None, enforce_eager=False, max_seq_len_to_capture=8192, disable_custom_all_reduce=False, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, limit_mm_per_prompt=None, mm_processor_kwargs=None, disable_mm_preprocessor_cache=False, enable_lora=False, enable_lora_bias=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, enable_prompt_adapter=False, max_prompt_adapters=1, max_prompt_adapter_token=0, device='auto', num_scheduler_steps=1, use_tqdm_on_load=True, multi_step_stream_outputs=True, scheduler_delay_factor=0.0, enable_chunked_prefill=None, speculative_model=None, speculative_model_quantization=None, num_speculative_tokens=None, speculative_disable_mqa_scorer=False, speculative_draft_tensor_parallel_size=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, spec_decoding_acceptance_method='rejection_sampler', typical_acceptance_sampler_posterior_threshold=None, typical_acceptance_sampler_posterior_alpha=None, disable_logprobs_during_spec_decoding=None, model_loader_extra_config=None, ignore_patterns=[], preemption_mode=None, served_model_name=['llama3.1-8B', 'llama3.1-8B-Int8'], qlora_adapter_name_or_path=None, show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, disable_async_output_proc=False, scheduling_policy='fcfs', scheduler_cls='vllm.core.scheduler.Scheduler', override_neuron_config=None, override_pooler_config=None, compilation_config=None, kv_transfer_config=None, worker_cls='auto', worker_extension_cls='', generation_config='auto', override_generation_config=None, enable_sleep_mode=False, calculate_kv_scales=False, additional_config=None, enable_reasoning=False, reasoning_parser=None, disable_log_requests=False, max_log_len=None, disable_fastapi_docs=False, enable_prompt_tokens_details=False, dispatch_function=<function ServeSubcommand.cmd at 0x7f0f49c4fd80>)
INFO 03-12 14:55:20 [api_server.py:209] Started engine process with PID 17986
INFO 03-12 14:55:22 [__init__.py:256] Automatically detected platform cuda.
INFO 03-12 14:55:24 [config.py:576] This model supports multiple tasks: {'generate', 'classify', 'embed', 'score', 'reward'}. Defaulting to 'generate'.
WARNING 03-12 14:55:25 [arg_utils.py:1266] Chunked prefill is enabled by default for models with max_model_len > 32K. Currently, chunked prefill might not work with some features or models. If you encounter any issues, please disable chunked prefill by setting --enable-chunked-prefill=False.
INFO 03-12 14:55:25 [config.py:1666] Chunked prefill is enabled with max_num_batched_tokens=2048.
INFO 03-12 14:55:26 [config.py:576] This model supports multiple tasks: {'embed', 'reward', 'classify', 'generate', 'score'}. Defaulting to 'generate'.
WARNING 03-12 14:55:27 [arg_utils.py:1266] Chunked prefill is enabled by default for models with max_model_len > 32K. Currently, chunked prefill might not work with some features or models. If you encounter any issues, please disable chunked prefill by setting --enable-chunked-prefill=False.
INFO 03-12 14:55:27 [config.py:1666] Chunked prefill is enabled with max_num_batched_tokens=2048.
[... 48 lines truncated ...]
INFO:     Application startup complete.
```

</details>

<details>

<summary>Log vllm v1</summary>

```
INFO 03-12 14:57:29 [__init__.py:256] Automatically detected platform cuda.
INFO 03-12 14:57:31 [api_server.py:912] vLLM API server version 0.7.4.dev390+gdebd6bbf
INFO 03-12 14:57:31 [api_server.py:913] args: Namespace(subparser='serve', model_tag='models/llama3.1-8B-INT8', config='', host='0.0.0.0', port=8000, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key=None, lora_modules=None, prompt_adapters=None, chat_template=None, chat_template_content_format='auto', response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, enable_ssl_refresh=False, ssl_cert_reqs=0, root_path=None, middleware=[], return_tokens_as_token_ids=False, disable_frontend_multiprocessing=False, enable_request_id_headers=False, enable_auto_tool_choice=True, tool_call_parser='llama3_json', tool_parser_plugin='', model='models/llama3.1-8B-INT8', task='auto', tokenizer=None, hf_config_path=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, allowed_local_media_path=None, download_dir=None, load_format='auto', config_format=<ConfigFormat.AUTO: 'auto'>, dtype='auto', kv_cache_dtype='auto', max_model_len=65536, guided_decoding_backend='xgrammar', logits_processor_pattern=None, model_impl='auto', distributed_executor_backend=None, pipeline_parallel_size=1, tensor_parallel_size=1, enable_expert_parallel=False, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=None, enable_prefix_caching=None, disable_sliding_window=False, use_v2_block_manager=True, num_lookahead_slots=0, seed=None, swap_space=4, cpu_offload_gb=0, gpu_memory_utilization=0.9, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_partial_prefills=1, max_long_partial_prefills=1, long_prefill_token_threshold=0, max_num_seqs=None, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, hf_overrides=None, enforce_eager=False, max_seq_len_to_capture=8192, disable_custom_all_reduce=False, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, limit_mm_per_prompt=None, mm_processor_kwargs=None, disable_mm_preprocessor_cache=False, enable_lora=False, enable_lora_bias=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, enable_prompt_adapter=False, max_prompt_adapters=1, max_prompt_adapter_token=0, device='auto', num_scheduler_steps=1, use_tqdm_on_load=True, multi_step_stream_outputs=True, scheduler_delay_factor=0.0, enable_chunked_prefill=None, speculative_model=None, speculative_model_quantization=None, num_speculative_tokens=None, speculative_disable_mqa_scorer=False, speculative_draft_tensor_parallel_size=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, spec_decoding_acceptance_method='rejection_sampler', typical_acceptance_sampler_posterior_threshold=None, typical_acceptance_sampler_posterior_alpha=None, disable_logprobs_during_spec_decoding=None, model_loader_extra_config=None, ignore_patterns=[], preemption_mode=None, served_model_name=['llama3.1-8B', 'llama3.1-8B-Int8'], qlora_adapter_name_or_path=None, show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, disable_async_output_proc=False, scheduling_policy='fcfs', scheduler_cls='vllm.core.scheduler.Scheduler', override_neuron_config=None, override_pooler_config=None, compilation_config=None, kv_transfer_config=None, worker_cls='auto', worker_extension_cls='', generation_config='auto', override_generation_config=None, enable_sleep_mode=False, calculate_kv_scales=False, additional_config=None, enable_reasoning=False, reasoning_parser=None, disable_log_requests=False, max_log_len=None, disable_fastapi_docs=False, enable_prompt_tokens_details=False, dispatch_function=<function ServeSubcommand.cmd at 0x7ecb3b7ca5c0>)
WARNING 03-12 14:57:31 [arg_utils.py:1478] Setting max_num_batched_tokens to 2048 for OPENAI_API_SERVER usage context.
INFO 03-12 14:57:34 [config.py:576] This model supports multiple tasks: {'score', 'generate', 'classify', 'embed', 'reward'}. Defaulting to 'generate'.
INFO 03-12 14:57:34 [config.py:1666] Chunked prefill is enabled with max_num_batched_tokens=2048.
INFO 03-12 14:57:36 [__init__.py:256] Automatically detected platform cuda.
INFO 03-12 14:57:37 [core.py:52] Initializing a V1 LLM engine (v0.7.4.dev390+gdebd6bbf) with config: model='models/llama3.1-8B-INT8', speculative_config=None, tokenizer='models/llama3.1-8B-INT8', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, override_neuron_config=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.bfloat16, max_seq_len=65536, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=compressed-tensors, enforce_eager=False, kv_cache_dtype=auto,  device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='xgrammar', reasoning_backend=None), observability_config=ObservabilityConfig(show_hidden_metrics=False, otlp_traces_endpoint=None, collect_model_forward_time=False, collect_model_execute_time=False), seed=None, served_model_name=llama3.1-8B, num_scheduler_steps=1, multi_step_stream_outputs=True, enable_prefix_caching=True, chunked_prefill_enabled=True, use_async_output_proc=True, disable_mm_preprocessor_cache=False, mm_processor_kwargs=None, pooler_config=None, compilation_config={"level":3,"custom_ops":["none"],"splitting_ops":["vllm.unified_attention","vllm.unified_attention_with_output"],"use_inductor":true,"compile_sizes":[],"use_cudagraph":true,"cudagraph_num_of_warmups":1,"cudagraph_capture_sizes":[512,504,496,488,480,472,464,456,448,440,432,424,416,408,400,392,384,376,368,360,352,344,336,328,320,312,304,296,288,280,272,264,256,248,240,232,224,216,208,200,192,184,176,168,160,152,144,136,128,120,112,104,96,88,80,72,64,56,48,40,32,24,16,8,4,2,1],"max_capture_size":512}
WARNING 03-12 14:57:38 [utils.py:2304] Methods determine_num_available_blocks,device_config,get_cache_block_size_bytes,initialize_cache not implemented in <vllm.v1.worker.gpu_worker.Worker object at 0x70f697f98110>
INFO 03-12 14:57:38 [parallel_state.py:948] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, TP rank 0
INFO 03-12 14:57:38 [cuda.py:215] Using Flash Attention backend on V1 engine.
[... 33 lines truncated ...]
Killed
```

</details>

## comment @gaocegege 2025-03-13T01:02:00Z
Still get the OOM error. Running a 1.5B model on an 8GB NV GPU. Here are the debug logs:

<details>
<summary><code>VLLM_USE_V1=0 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --max-model-len 2000 --gpu_memory_utilization=0.9</code></summary>
<br>

```
DEBUG 03-13 08:56:28 [__init__.py:28] No plugins for group vllm.platform_plugins found.
DEBUG 03-13 08:56:28 [__init__.py:35] Checking if TPU platform is available.
DEBUG 03-13 08:56:28 [__init__.py:45] TPU platform is not available because: No module named 'libtpu'
DEBUG 03-13 08:56:28 [__init__.py:53] Checking if CUDA platform is available.
DEBUG 03-13 08:56:28 [__init__.py:73] Confirmed CUDA platform is available.
DEBUG 03-13 08:56:28 [__init__.py:101] Checking if ROCm platform is available.
DEBUG 03-13 08:56:28 [__init__.py:115] ROCm platform is not available because: No module named 'amdsmi'
DEBUG 03-13 08:56:28 [__init__.py:123] Checking if HPU platform is available.
DEBUG 03-13 08:56:28 [__init__.py:130] HPU platform is not available because habana_frameworks is not found.
DEBUG 03-13 08:56:28 [__init__.py:141] Checking if XPU platform is available.
DEBUG 03-13 08:56:28 [__init__.py:151] XPU platform is not available because: No module named 'intel_extension_for_pytorch'
[... 97 lines truncated ...]
INFO:     Application startup complete.
```

</details>

<details>
<summary><code>VLLM_USE_V1=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --max-model-len 2000 --gpu_memory_utilization=0.9</code></summary>
<br>

```
DEBUG 03-13 09:00:22 [__init__.py:28] No plugins for group vllm.platform_plugins found.
DEBUG 03-13 09:00:22 [__init__.py:35] Checking if TPU platform is available.
DEBUG 03-13 09:00:22 [__init__.py:45] TPU platform is not available because: No module named 'libtpu'
DEBUG 03-13 09:00:22 [__init__.py:53] Checking if CUDA platform is available.
DEBUG 03-13 09:00:22 [__init__.py:73] Confirmed CUDA platform is available.
DEBUG 03-13 09:00:22 [__init__.py:101] Checking if ROCm platform is available.
DEBUG 03-13 09:00:22 [__init__.py:115] ROCm platform is not available because: No module named 'amdsmi'
DEBUG 03-13 09:00:22 [__init__.py:123] Checking if HPU platform is available.
DEBUG 03-13 09:00:22 [__init__.py:130] HPU platform is not available because habana_frameworks is not found.
DEBUG 03-13 09:00:22 [__init__.py:141] Checking if XPU platform is available.
DEBUG 03-13 09:00:22 [__init__.py:151] XPU platform is not available because: No module named 'intel_extension_for_pytorch'
[... 169 lines truncated ...]
CRITICAL 03-13 09:00:43 [core_client.py:260] Got fatal signal from worker processes, shutting down. See stack trace above for root cause issue.
```

</details>

Not sure if it is related to flashinfer. I did not install it in the set up. And the error is from `/home/gaocegege/code/vllm/vllm/v1/sample/sampler.py` `self.topk_topp_sampler`

Update: Get a different error after installing flashinfer:

```
ERROR 03-13 09:07:24 [core.py:330] EngineCore hit an exception: Traceback (most recent call last):
ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 322, in run_engine_core
ERROR 03-13 09:07:24 [core.py:330]     engine_core = EngineCoreProc(*args, **kwargs)
ERROR 03-13 09:07:24 [core.py:330]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 277, in __init__
ERROR 03-13 09:07:24 [core.py:330]     super().__init__(vllm_config, executor_class, log_stats)
ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 61, in __init__
ERROR 03-13 09:07:24 [core.py:330]     num_gpu_blocks, num_cpu_blocks = self._initialize_kv_caches(
ERROR 03-13 09:07:24 [core.py:330]                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 114, in _initialize_kv_caches
ERROR 03-13 09:07:24 [core.py:330]     available_gpu_memory = self.model_executor.determine_available_memory()
[... 50 lines truncated ...]
ERROR 03-13 09:07:24 [core.py:330] ValueError: too many values to unpack (expected 2)
```

## comment @ywang96 2025-03-13T03:27:01Z
> Still get the OOM error. Running a 1.5B model on an 8GB NV GPU. Here are the debug logs:
> 
> `VLLM_USE_V1=0 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --max-model-len 2000 --gpu_memory_utilization=0.9`
> `VLLM_USE_V1=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --max-model-len 2000 --gpu_memory_utilization=0.9`
> 
> ```
> DEBUG 03-13 09:00:22 [__init__.py:28] No plugins for group vllm.platform_plugins found.
> DEBUG 03-13 09:00:22 [__init__.py:35] Checking if TPU platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:45] TPU platform is not available because: No module named 'libtpu'
> DEBUG 03-13 09:00:22 [__init__.py:53] Checking if CUDA platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:73] Confirmed CUDA platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:101] Checking if ROCm platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:115] ROCm platform is not available because: No module named 'amdsmi'
> DEBUG 03-13 09:00:22 [__init__.py:123] Checking if HPU platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:130] HPU platform is not available because habana_frameworks is not found.
> DEBUG 03-13 09:00:22 [__init__.py:141] Checking if XPU platform is available.
> DEBUG 03-13 09:00:22 [__init__.py:151] XPU platform is not available because: No module named 'intel_extension_for_pytorch'
[... 169 lines truncated ...]
> CRITICAL 03-13 09:00:43 [core_client.py:260] Got fatal signal from worker processes, shutting down. See stack trace above for root cause issue.
> ```
> 
> Not sure if it is related to flashinfer. I did not install it in the set up. And the error is from `/home/gaocegege/code/vllm/vllm/v1/sample/sampler.py` `self.topk_topp_sampler`
> 
> Update: Get a different error after installing flashinfer:
> 
> ```
> ERROR 03-13 09:07:24 [core.py:330] EngineCore hit an exception: Traceback (most recent call last):
> ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 322, in run_engine_core
> ERROR 03-13 09:07:24 [core.py:330]     engine_core = EngineCoreProc(*args, **kwargs)
> ERROR 03-13 09:07:24 [core.py:330]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
> ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 277, in __init__
> ERROR 03-13 09:07:24 [core.py:330]     super().__init__(vllm_config, executor_class, log_stats)
> ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 61, in __init__
> ERROR 03-13 09:07:24 [core.py:330]     num_gpu_blocks, num_cpu_blocks = self._initialize_kv_caches(
> ERROR 03-13 09:07:24 [core.py:330]                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
> ERROR 03-13 09:07:24 [core.py:330]   File "/home/gaocegege/code/vllm/vllm/v1/engine/core.py", line 114, in _initialize_kv_caches
> ERROR 03-13 09:07:24 [core.py:330]     available_gpu_memory = self.model_executor.determine_available_memory()
[... 50 lines truncated ...]
> ERROR 03-13 09:07:24 [core.py:330] ValueError: too many values to unpack (expected 2)
> ```

@gaocegege Can you try lowering the `--gpu_memory_utilization` with V1 to something like 0.8? I should have also moved this check into `_dummy_sampler_run` so let me just make a PR for that...
https://github.com/vllm-project/vllm/blob/a94a699c3ff9bfc23a35f147150a826b753bbf6a/vllm/v1/worker/gpu_worker.py#L231-L238

## comment @gaocegege 2025-03-13T04:48:09Z
```
VLLM_USE_V1=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B --max-model-len 2000 --enable-reasoning --reasoning-parser deepseek_r1 --gpu_memory_utilization=0.8 --max_num_batched_tokens=64 --max_num_seqs=64
```

This command works, but `--max_num_batched_tokens=256 --max_num_seqs=256` does not work. Just FYI.

## comment @rstanislav 2025-03-19T21:40:54Z
With v0.8 its the same.. and this starts to look very strange, V1 cant load 70b q4 model on quad 24g GPU's, where V0 had no problem with that at full (128k) context.

## comment @ywang96 2025-03-19T23:44:03Z
> With v0.8 its the same.. and this starts to look very strange, V1 cant load 70b q4 model on quad 24g GPU's, where V0 had no problem with that at full (128k) context.

@rstanislav Can you try lowering `--max-num-seqs`? This value is 256 by default on V0 but 1024 on V1, and this difference contributes a lot to the memory usage.

## comment @rstanislav 2025-03-20T02:39:27Z
Thanks for help 🤗! Tried many different settings, got success with --max-num-seqs 64 --max_num_batched_tokens=256, without --max_num_batched_tokens=256 it was crashing even with --max-num-seqs 2 (only way to load it was --max-num-seqs 1).

## comment @DarkLight1337 2025-04-07T06:18:33Z
Sorry for the delay, I have opened https://github.com/vllm-project/vllm/pull/16158 to revert `max_num_seqs` for most hardware to avoid OOM when switching from V0 to V1 Engine.

## comment @activlayer-team 2026-07-23T18:20:45Z
This illustrates why checkpoint size alone is not enough: KV cache, activation peaks and runtime workspaces must all be considered. CommNet measures those components and selects cache tiers and execution plans under a fixed peak-VRAM limit. I can try reproducing this model and publish a memory breakdown comparing the configurations.