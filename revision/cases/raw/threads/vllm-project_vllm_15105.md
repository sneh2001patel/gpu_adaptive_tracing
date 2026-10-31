# vllm-project/vllm#15105: [Bug]: Extremely slow inference + big waste of memory on 0.8.0
state=closed reason=completed created=2025-03-19T07:36:31Z closed=2025-03-19T08:21:23Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/15114']

## body (@SlerpE)
### Your current environment


2xRTX3090 32GB RAM
Driver Version: 570.124.04
nvcc --version:
```
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2024 NVIDIA Corporation
Built on Thu_Mar_28_02:18:24_PDT_2024
Cuda compilation tools, release 12.4, V12.4.131
Build cuda_12.4.r12.4/compiler.34097967_0
```



### 🐛 Describe the bug

Hello! I've encountered an unpleasant bug: When I run Qwen QwQ in AWQ or GPTQ 4-bit quantization on version 0.8.0, the text generation speed is only 7 tokens per second, whereas on version 0.7.3 it was consistently 45 tokens per second. Additionally, memory consumption has sharply increased—while using the same context window that I used with 0.7.3, Qwen now throws a "CUDA out of memory" error. The issue was only resolved by adding the parameter `--disable-mm-preprocessor-cache`, which allowed Qwen AWQ to barely fit into two 3090 GPUs, consuming exactly 24068 MiB on each. On version 0.7.3, this number was only 19-20 GB. Please help me, I would be very grateful!

The command I use to run both versions 0.8.0 and 0.7.3 is the same (except for the --disable-mm-preprocessor-cache option):
```bash
CUDA_VISIBLE_DEVICES=0,1 CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_LAUNCH_BLOCKING=1 vllm serve OPEA_QwQ-32B-int4-AutoRound-gptq-sym   --dtype auto   --api-key token-abc123   --host 0.0.0.0   --port 8000   --tensor-parallel-size 2 --gpu-memory-utilization 0.95   --max-model-len 30000   --cpu-offload-gb 0      --device cuda   --disable-custom-all-reduce   --enable-reasoning --reasoning-parser deepseek_r1 --served-model-name AlexBefest/Qwen_QwQ-32B-AWQ --block-size 32 --max-seq-len-to-capture 30000  --disable-mm-preprocessor-cache
```
### Logs

Using --disable-mm-preprocessor-cache:

```bash
(base) root@287aa8679d31:/workdir# CUDA_VISIBLE_DEVICES=0,1 CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_LAUNCH_BLOCKING=1 vllm serve Qwen_QwQ-32B-AWQ   --dtype auto   --api-key token-abc123   --host 0.0.0.0   --port
 8000   --tensor-parallel-size 2 --gpu-memory-utilization 0.9  --max-model-len 30000   --cpu-offload-gb 0      --device cuda   --disable-custom-all-reduce   --enable-reasoning --reasoning-parser deepseek_r
1 --served-model-name AlexBefest/Qwen_QwQ-32B-AWQ --max-seq-len-to-capture 30000  --disable-mm-preprocessor-cache
INFO 03-19 07:08:38 [__init__.py:256] Automatically detected platform cuda.
INFO 03-19 07:08:38 [api_server.py:977] vLLM API server version 0.8.0
INFO 03-19 07:08:38 [api_server.py:978] args: Namespace(subparser='serve', model_tag='Qwen_QwQ-32B-AWQ', config='', host='0.0.0.0', port=8000, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key='token-abc123', lora_modules=None, prompt_adapters=None, chat_template=None, chat_template_content_format='auto', response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, enable_ssl_refresh=False, ssl_cert_reqs=0, root_path=None, middleware=[], return_tokens_as_token_ids=False, disable_frontend_multiprocessing=False, enable_request_id_headers=False, enable_auto_tool_choice=False, tool_call_parser=None, tool_parser_plugin='', model='Qwen_QwQ-32B-AWQ', task='auto', tokenizer=None, hf_config_path=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, allowed_local_media_path=None, download_dir=None, load_format='auto', config_format=<ConfigFormat.AUTO: 'auto'>, dtype='auto', kv_cache_dtype='auto', max_model_len=30000, guided_decoding_backend='xgrammar', logits_processor_pattern=None, model_impl='auto', distributed_executor_backend=None, pipeline_parallel_size=1, tensor_parallel_size=2, enable_expert_parallel=False, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=None, enable_prefix_caching=None, disable_sliding_window=False, use_v2_block_manager=True, num_lookahead_slots=0, seed=None, swap_space=4, cpu_offload_gb=0.0, gpu_memory_utilization=0.9, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_partial_prefills=1, max_long_partial_prefills=1, long_prefill_token_threshold=0, max_num_seqs=None, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, hf_overrides=None, enforce_eager=False, max_seq_len_to_capture=30000, disable_custom_all_reduce=True, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, limit_mm_per_prompt=None, mm_processor_kwargs=None, disable_mm_preprocessor_cache=True, enable_lora=False, enable_lora_bias=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, enable_prompt_adapter=False, max_prompt_adapters=1, max_prompt_adapter_token=0, device='cuda', num_scheduler_steps=1, use_tqdm_on_load=True, multi_step_stream_outputs=True, scheduler_delay_factor=0.0, enable_chunked_prefill=None, speculative_model=None, speculative_model_quantization=None, num_speculative_tokens=None, speculative_disable_mqa_scorer=False, speculative_draft_tensor_parallel_size=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, spec_decoding_acceptance_method='rejection_sampler', typical_acceptance_sampler_posterior_threshold=None, typical_acceptance_sampler_posterior_alpha=None, disable_logprobs_during_spec_decoding=None, model_loader_extra_config=None, ignore_patterns=[], preemption_mode=None, served_model_name=['AlexBefest/Qwen_QwQ-32B-AWQ'], qlora_adapter_name_or_path=None, show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, disable_async_output_proc=False, scheduling_policy='fcfs', scheduler_cls='vllm.core.scheduler.Scheduler', override_neuron_config=None, override_pooler_config=None, compilation_config=None, kv_transfer_config=None, worker_cls='auto', worker_extension_cls='', generation_config='auto', override_generation_config=None, enable_sleep_mode=False, calculate_kv_scales=False, additional_config=None, enable_reasoning=True, reasoning_parser='deepseek_r1', disable_log_requests=False, max_log_len=None, disable_fastapi_docs=False, enable_prompt_tokens_details=False, enable_server_load_tracking=False, dispatch_function=<function ServeSubcommand.cmd at 0x7bec2da64680>)
INFO 03-19 07:08:42 [config.py:583] This model supports multiple tasks: {'embed', 'classify', 'reward', 'score', 'generate'}. Defaulting to 'generate'.
INFO 03-19 07:08:42 [awq_marlin.py:114] The model is convertible to awq_marlin during runtime. Using awq_marlin kernel.
INFO 03-19 07:08:43 [config.py:1515] Defaulting to use mp for distributed inference
INFO 03-19 07:08:43 [config.py:1693] Chunked prefill is enabled with max_num_batched_tokens=2048.
INFO 03-19 07:08:45 [__init__.py:256] Automatically detected platform cuda.
[... 79 lines truncated ...]
INFO:     Application startup complete.
```

Without --disable-mm-preprocessor-cache:
```bash
(base) root@287aa8679d31:/workdir# CUDA_VISIBLE_DEVICES=0,1 CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_LAUNCH_BLOCKING=1 vllm serve Qwen_QwQ-32B-AWQ   --dtype auto   --api-key token-abc123   --host 0.0.0.0   --port
 8000   --tensor-parallel-size 2 --gpu-memory-utilization 0.95   --max-model-len 30000   --cpu-offload-gb 0      --device cuda   --disable-custom-all-reduce   --enable-reasoning --reasoning-parser deepseek
_r1 --served-model-name AlexBefest/Qwen_QwQ-32B-AWQ --block-size 32 --max-seq-len-to-capture 30000
INFO 03-19 07:26:21 [__init__.py:256] Automatically detected platform cuda.
INFO 03-19 07:26:22 [api_server.py:977] vLLM API server version 0.8.0
INFO 03-19 07:26:22 [api_server.py:978] args: Namespace(subparser='serve', model_tag='Qwen_QwQ-32B-AWQ', config='', host='0.0.0.0', port=8000, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key='token-abc123', lora_modules=None, prompt_adapters=None, chat_template=None, chat_template_content_format='auto', response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, enable_ssl_refresh=False, ssl_cert_reqs=0, root_path=None, middleware=[], return_tokens_as_token_ids=False, disable_frontend_multiprocessing=False, enable_request_id_headers=False, enable_auto_tool_choice=False, tool_call_parser=None, tool_parser_plugin='', model='Qwen_QwQ-32B-AWQ', task='auto', tokenizer=None, hf_config_path=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, allowed_local_media_path=None, download_dir=None, load_format='auto', config_format=<ConfigFormat.AUTO: 'auto'>, dtype='auto', kv_cache_dtype='auto', max_model_len=30000, guided_decoding_backend='xgrammar', logits_processor_pattern=None, model_impl='auto', distributed_executor_backend=None, pipeline_parallel_size=1, tensor_parallel_size=2, enable_expert_parallel=False, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=32, enable_prefix_caching=None, disable_sliding_window=False, use_v2_block_manager=True, num_lookahead_slots=0, seed=None, swap_space=4, cpu_offload_gb=0.0, gpu_memory_utilization=0.95, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_partial_prefills=1, max_long_partial_prefills=1, long_prefill_token_threshold=0, max_num_seqs=None, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, hf_overrides=None, enforce_eager=False, max_seq_len_to_capture=30000, disable_custom_all_reduce=True, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, limit_mm_per_prompt=None, mm_processor_kwargs=None, disable_mm_preprocessor_cache=False, enable_lora=False, enable_lora_bias=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, enable_prompt_adapter=False, max_prompt_adapters=1, max_prompt_adapter_token=0, device='cuda', num_scheduler_steps=1, use_tqdm_on_load=True, multi_step_stream_outputs=True, scheduler_delay_factor=0.0, enable_chunked_prefill=None, speculative_model=None, speculative_model_quantization=None, num_speculative_tokens=None, speculative_disable_mqa_scorer=False, speculative_draft_tensor_parallel_size=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, spec_decoding_acceptance_method='rejection_sampler', typical_acceptance_sampler_posterior_threshold=None, typical_acceptance_sampler_posterior_alpha=None, disable_logprobs_during_spec_decoding=None, model_loader_extra_config=None, ignore_patterns=[], preemption_mode=None, served_model_name=['AlexBefest/Qwen_QwQ-32B-AWQ'], qlora_adapter_name_or_path=None, show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, disable_async_output_proc=False, scheduling_policy='fcfs', scheduler_cls='vllm.core.scheduler.Scheduler', override_neuron_config=None, override_pooler_config=None, compilation_config=None, kv_transfer_config=None, worker_cls='auto', worker_extension_cls='', generation_config='auto', override_generation_config=None, enable_sleep_mode=False, calculate_kv_scales=False, additional_config=None, enable_reasoning=True, reasoning_parser='deepseek_r1', disable_log_requests=False, max_log_len=None, disable_fastapi_docs=False, enable_prompt_tokens_details=False, enable_server_load_tracking=False, dispatch_function=<function ServeSubcommand.cmd at 0x70a528e44680>)
INFO 03-19 07:26:25 [config.py:583] This model supports multiple tasks: {'embed', 'classify', 'reward', 'generate', 'score'}. Defaulting to 'generate'.
INFO 03-19 07:26:26 [awq_marlin.py:114] The model is convertible to awq_marlin during runtime. Using awq_marlin kernel.
INFO 03-19 07:26:26 [config.py:1515] Defaulting to use mp for distributed inference
INFO 03-19 07:26:26 [config.py:1693] Chunked prefill is enabled with max_num_batched_tokens=2048.
INFO 03-19 07:26:28 [__init__.py:256] Automatically detected platform cuda.
[... 164 lines truncated ...]
Killed
```

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @DarkLight1337 2025-03-19T07:44:46Z
Can you try setting `VLLM_USE_V1=0` (without `--disable-mm-preprocessor-cache`) and see if the memory leak still occurs?

## comment @DarkLight1337 2025-03-19T07:47:09Z
Also, you have set `--block-size 32` in the command without `--disable-mm-preprocessor-cache`. Can you see if removing `--block-size 32` alone solves the problem in V1?

## comment @SlerpE 2025-03-19T08:02:51Z
`VLLM_USE_V1=0` solved the problem, thanks! Removing `--block-size 32` in V1 did not solve the problem. 

## comment @akai-shuuichi 2025-03-19T08:42:15Z
The same problem occurs when 32B-AWQ is run at 3090 tp=2. OOM appears, and it is normal after switching to V0. I hope V1 can be used normally

## comment @DarkLight1337 2025-03-19T09:05:24Z
I have opened a PR to fix this problem on V1: https://github.com/vllm-project/vllm/pull/15114 can you try it?

## comment @akai-shuuichi 2025-03-20T02:50:00Z
> I have opened a PR to fix this problem on V1: [#15114](https://github.com/vllm-project/vllm/pull/15114) can you try it?
```
INFO 03-20 02:23:32 [__init__.py:256] Automatically detected platform cuda.
INFO 03-20 02:23:35 [api_server.py:977] vLLM API server version 0.8.1
INFO 03-20 02:23:35 [api_server.py:978] args: Namespace(subparser='serve', model_tag='/mnt/llm/Qwen2.5-32B-Instruct-AWQ', config='', host=None, port=9001, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key=None, lora_modules=None, prompt_adapters=None, chat_template=None, chat_template_content_format='auto', response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, enable_ssl_refresh=False, ssl_cert_reqs=0, root_path=None, middleware=[], return_tokens_as_token_ids=False, disable_frontend_multiprocessing=False, enable_request_id_headers=False, enable_auto_tool_choice=False, tool_call_parser=None, tool_parser_plugin='', model='/mnt/llm/Qwen2.5-32B-Instruct-AWQ', task='auto', tokenizer=None, hf_config_path=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, allowed_local_media_path=None, download_dir=None, load_format='auto', config_format=<ConfigFormat.AUTO: 'auto'>, dtype='auto', kv_cache_dtype='auto', max_model_len=15000, guided_decoding_backend='xgrammar', logits_processor_pattern=None, model_impl='auto', distributed_executor_backend=None, pipeline_parallel_size=1, tensor_parallel_size=2, enable_expert_parallel=False, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=None, enable_prefix_caching=True, disable_sliding_window=False, use_v2_block_manager=True, num_lookahead_slots=0, seed=None, swap_space=4.0, cpu_offload_gb=0, gpu_memory_utilization=0.78, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_partial_prefills=1, max_long_partial_prefills=1, long_prefill_token_threshold=0, max_num_seqs=None, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, hf_overrides=None, enforce_eager=False, max_seq_len_to_capture=8192, disable_custom_all_reduce=False, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, limit_mm_per_prompt=None, mm_processor_kwargs=None, disable_mm_preprocessor_cache=False, enable_lora=False, enable_lora_bias=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, enable_prompt_adapter=False, max_prompt_adapters=1, max_prompt_adapter_token=0, device='auto', num_scheduler_steps=1, use_tqdm_on_load=True, multi_step_stream_outputs=True, scheduler_delay_factor=0.0, enable_chunked_prefill=True, speculative_model=None, speculative_model_quantization=None, num_speculative_tokens=None, speculative_disable_mqa_scorer=False, speculative_draft_tensor_parallel_size=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, spec_decoding_acceptance_method='rejection_sampler', typical_acceptance_sampler_posterior_threshold=None, typical_acceptance_sampler_posterior_alpha=None, disable_logprobs_during_spec_decoding=None, model_loader_extra_config=None, ignore_patterns=[], preemption_mode=None, served_model_name=['Qwen2.5-32B-Instruct'], qlora_adapter_name_or_path=None, show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, disable_async_output_proc=False, scheduling_policy='fcfs', scheduler_cls='vllm.core.scheduler.Scheduler', override_neuron_config=None, override_pooler_config=None, compilation_config=None, kv_transfer_config=None, worker_cls='auto', worker_extension_cls='', generation_config='auto', override_generation_config=None, enable_sleep_mode=False, calculate_kv_scales=False, additional_config=None, enable_reasoning=False, reasoning_parser=None, disable_log_requests=False, max_log_len=None, disable_fastapi_docs=False, enable_prompt_tokens_details=False, enable_server_load_tracking=False, dispatch_function=<function ServeSubcommand.cmd at 0x7fbfd47fd240>)
INFO 03-20 02:23:43 [config.py:583] This model supports multiple tasks: {'score', 'classify', 'embed', 'reward', 'generate'}. Defaulting to 'generate'.
INFO 03-20 02:23:43 [awq_marlin.py:114] The model is convertible to awq_marlin during runtime. Using awq_marlin kernel.
INFO 03-20 02:23:44 [config.py:1515] Defaulting to use mp for distributed inference
INFO 03-20 02:23:44 [config.py:1693] Chunked prefill is enabled with max_num_batched_tokens=2048.
INFO 03-20 02:23:48 [__init__.py:256] Automatically detected platform cuda.
INFO 03-20 02:23:52 [core.py:53] Initializing a V1 LLM engine (v0.8.1) with config: model='/mnt/llm/Qwen2.5-32B-Instruct-AWQ', speculative_config=None, tokenizer='/mnt/llm/Qwen2.5-32B-Instruct-AWQ', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, override_neuron_config=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=15000, download_dir=None, load_format=auto, tensor_parallel_size=2, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=awq_marlin, enforce_eager=False, kv_cache_dtype=auto,  device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='xgrammar', reasoning_backend=None), observability_config=ObservabilityConfig(show_hidden_metrics=False, otlp_traces_endpoint=None, collect_model_forward_time=False, collect_model_execute_time=False), seed=None, served_model_name=Qwen2.5-32B-Instruct, num_scheduler_steps=1, multi_step_stream_outputs=True, enable_prefix_caching=True, chunked_prefill_enabled=True, use_async_output_proc=True, disable_mm_preprocessor_cache=False, mm_processor_kwargs=None, pooler_config=None, compilation_config={"level":3,"custom_ops":["none"],"splitting_ops":["vllm.unified_attention","vllm.unified_attention_with_output"],"use_inductor":true,"compile_sizes":[],"use_cudagraph":true,"cudagraph_num_of_warmups":1,"cudagraph_capture_sizes":[512,504,496,488,480,472,464,456,448,440,432,424,416,408,400,392,384,376,368,360,352,344,336,328,320,312,304,296,288,280,272,264,256,248,240,232,224,216,208,200,192,184,176,168,160,152,144,136,128,120,112,104,96,88,80,72,64,56,48,40,32,24,16,8,4,2,1],"max_capture_size":512}
WARNING 03-20 02:23:52 [multiproc_worker_utils.py:306] Reducing Torch parallelism from 36 threads to 1 to avoid unnecessary CPU contention. Set OMP_NUM_THREADS in the external environment to tune this value as needed.
INFO 03-20 02:23:52 [shm_broadcast.py:258] vLLM message queue communication handle: Handle(local_reader_ranks=[0, 1], buffer_handle=(2, 10485760, 10, 'psm_794aca41'), local_subscribe_addr='ipc:///tmp/d3e54754-045a-4dc1-9af1-bee60ddd10c4', remote_subscribe_addr=None, remote_addr_ipv6=False)
[... 147 lines truncated ...]
CRITICAL 03-20 02:29:07 [core_client.py:269] Got fatal signal from worker processes, shutting down. See stack trace above for root cause issue.
```
I tried 0.8.1 and it still works. Launch command:
```
vllm serve /mnt/llm/Qwen2.5-32B-Instruct-AWQ --enable-prefix-caching --port 9001 --served-model-name Qwen2.5-32B-Instruct -tp 2 --max-model-len 15000 --gpu-memory-utilization 0.78 --enable-chunked-prefill --swap-space 4
```


## comment @DarkLight1337 2025-03-20T03:00:51Z
So, is your issue solved or not?

## comment @akai-shuuichi 2025-03-20T03:17:16Z
> So, is your issue solved or not?

No, this doesn't solve my problem

## comment @ywang96 2025-03-20T03:39:18Z
> > So, is your issue solved or not?
> 
> No, this doesn't solve my problem

Can you try lowering the max-num-seqs to a lower number? (say 64?). It actually says in the error message
```
ERROR 03-20 02:29:07 [core.py:340] RuntimeError: CUDA out of memory occurred when warming up sampler with 1024 dummy requests. Please try lowering `max_num_seqs` or `gpu_memory_utilization` when initializing the engine.
```

## comment @akai-shuuichi 2025-03-20T03:56:16Z
> > > 那么，您的问题解决了吗？
> > 
> > 
> > 不，这不能解决我的问题
> 
> 您能否尝试将 max-num-seqs 降低到更低的数字？（比如说 64？）。错误消息中实际上说
> 
> ```
> ERROR 03-20 02:29:07 [core.py:340] RuntimeError: CUDA out of memory occurred when warming up sampler with 1024 dummy requests. Please try lowering `max_num_seqs` or `gpu_memory_utilization` when initializing the engine.
> ```

Thank you, it works by setting lower levels ofgpu-memory-utilization (0.78->0.7) and max_num_seqs (128->10) and max_model_len (16000->10000)