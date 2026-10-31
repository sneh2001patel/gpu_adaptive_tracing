# vllm-project/vllm#5523: [Bug]: The speed of loading the qwen2 72b model, glm-4-9b-chat-1m model in v0.5.0 is much lower than that in v0.4.2.
state=closed reason=completed created=2024-06-14T02:50:55Z closed=2024-06-14T21:47:46Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/5528']

## body (@majestichou)
### Your current environment

I run python3 collect_env.py in the docker container started by vllm:0.5.0, and the output is as follows:
```
Collecting environment information...
PyTorch version: 2.3.0+cu121
Is debug build: False
CUDA used to build PyTorch: 12.1
ROCM used to build PyTorch: N/A

OS: Ubuntu 22.04.4 LTS (x86_64)
GCC version: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0
Clang version: Could not collect
CMake version: version 3.29.5
Libc version: glibc-2.35
[... 88 lines truncated ...]
  NV#  = Connection traversing a bonded set of # NVLinks
```



### 🐛 Describe the bug

I use vLLM (v0.5.0 docker image) to load Qwen/Qwen2-72B-Instruct model. I download the model weights to a local directory named /serving/data/models/. Run the following command to start the Docker container:

`docker run --gpus 8 -p 8080:8000 --ipc=host -v /serving/data/models/:/data/models/ --env "TRANSFORMERS_OFFLINE=1" --env "HF_DATASET_OFFLINE=1" vllm/vllm-openai:v0.5.0 --model "/data/models/Qwen2-72B-Instruct/" --tensor-parallel-size 8`

**It took 40 minutes to start the model with vllm version 0.5.0((v0.5.0 docker image)**. During the boot process, I use nvitop to check the gpu memory usage of the machine. The usage of the display memory stays at 5.4% for a long time. The GPU memory usage stays at 5.4% for a long time, sometimes increases to 5.6%, and then decreases to 5.4%. `Sometimes, the message "zombile process" is displayed on the screen of the nvitop.`
I used the https://docs.vllm.ai/en/stable/getting_started/debugging.html link to troubleshoot, everthing is ok, I didn't find any strange problems.

The docker log is as follows:
```
INFO 06-14 10:21:15 api_server.py:177] vLLM API server version 0.5.0
INFO 06-14 10:21:15 api_server.py:178] args: Namespace(host=None, port=8000, uvicorn_log_level='info', allow_credentials=False, allowed_origins=['*'], allowed_methods=['*'], allowed_headers=['*'], api_key=None, lora_modules=None, chat_template=None, response_role='assistant', ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, ssl_cert_reqs=0, root_path=None, middleware=[], model='/data/models/Qwen2-72B-Instruct/', tokenizer=None, skip_tokenizer_init=False, revision=None, code_revision=None, tokenizer_revision=None, tokenizer_mode='auto', trust_remote_code=False, download_dir=None, load_format='auto', dtype='auto', kv_cache_dtype='auto', quantization_param_path=None, max_model_len=None, guided_decoding_backend='outlines', distributed_executor_backend=None, worker_use_ray=False, pipeline_parallel_size=1, tensor_parallel_size=8, max_parallel_loading_workers=None, ray_workers_use_nsight=False, block_size=16, enable_prefix_caching=False, disable_sliding_window=False, use_v2_block_manager=False, num_lookahead_slots=0, seed=0, swap_space=4, gpu_memory_utilization=0.9, num_gpu_blocks_override=None, max_num_batched_tokens=None, max_num_seqs=256, max_logprobs=20, disable_log_stats=False, quantization=None, rope_scaling=None, rope_theta=None, enforce_eager=False, max_context_len_to_capture=None, max_seq_len_to_capture=8192, disable_custom_all_reduce=False, tokenizer_pool_size=0, tokenizer_pool_type='ray', tokenizer_pool_extra_config=None, enable_lora=False, max_loras=1, max_lora_rank=16, lora_extra_vocab_size=256, lora_dtype='auto', long_lora_scaling_factors=None, max_cpu_loras=None, fully_sharded_loras=False, device='auto', image_input_type=None, image_token_id=None, image_input_shape=None, image_feature_size=None, image_processor=None, image_processor_revision=None, disable_image_processor=False, scheduler_delay_factor=0.0, enable_chunked_prefill=False, speculative_model=None, num_speculative_tokens=None, speculative_max_model_len=None, speculative_disable_by_batch_size=None, ngram_prompt_lookup_max=None, ngram_prompt_lookup_min=None, model_loader_extra_config=None, preemption_mode=None, served_model_name=None, qlora_adapter_name_or_path=None, engine_use_ray=False, disable_log_requests=False, max_log_len=None)
2024-06-14 10:21:19,072 INFO worker.py:1753 -- Started a local Ray instance.
INFO 06-14 10:21:29 config.py:623] Defaulting to use mp for distributed inference
INFO 06-14 10:21:29 llm_engine.py:161] Initializing an LLM engine (v0.5.0) with config: model='/data/models/Qwen2-72B-Instruct/', speculative_config=None, tokenizer='/data/models/Qwen2-72B-Instruct/', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.bfloat16, max_seq_len=32768, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=8, disable_custom_all_reduce=False, quantization=None, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), seed=0, served_model_name=/data/models/Qwen2-72B-Instruct/)
Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained.
INFO 06-14 10:21:30 selector.py:50] Using XFormers backend.
(VllmWorkerProcess pid=10874) INFO 06-14 10:21:45 selector.py:50] Using XFormers backend.
(VllmWorkerProcess pid=10872) INFO 06-14 10:21:45 selector.py:50] Using XFormers backend.
(VllmWorkerProcess pid=10873) INFO 06-14 10:21:45 selector.py:50] Using XFormers backend.
(VllmWorkerProcess pid=10870) INFO 06-14 10:21:45 selector.py:50] Using XFormers backend.
[... 53 lines truncated ...]
INFO 06-14 10:21:58 custom_all_reduce_utils.py:169] generating GPU P2P access cache in /root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json
```
The docker logs are not updated for a long time.

Then I booted the model on the same machine with vllm version 0.4.2.
` docker run --gpus 8 -p 8080:8000 --ipc=host -v /serving/data/models/:/data/models/ --env "TRANSFORMERS_OFFLINE=1" --env "HF_DATASET_OFFLINE=1" vllm/vllm-openai:v0.4.2 --model "/data/models/Qwen2-72B-Instruct/" --tensor-parallel-size 8`
**It took 20 minutes to start the model with vllm version 0.4.2((v0.4.2 docker image).**

**The speed of loading the qwen2 72b model in v0.5.0 is much lower than that in v0.4.2.**

I repeated the above process many times, with the same conclusion.




## comment @NiuBlibing 2024-06-14T02:54:55Z
same issue. The "generating GPU P2P access cache" progress is very slow.

## comment @majestichou 2024-06-14T03:08:16Z
I also tested the loading of the glm-4-9b-chat-1m model. The speed of loading the glm-4-9b-chat-1m model in v0.5.0 is also much lower than that in v0.4.2. The "generating GPU P2P access cache" progress is very slow.

## comment @NiuBlibing 2024-06-14T03:14:21Z
The first "generating GPU P2P access cache" is very slow which is not related with specify models I think, if the file exists, it will reading from the file directly.

## comment @youkaichao 2024-06-14T03:50:21Z
I understand "generating GPU P2P access cache" can be slow, because it needs to test the p2p of each gpu pair. I don't think it can take 20 minutes though. In my experience that's kind of 1~2 minutes.

## comment @majestichou 2024-06-14T03:52:55Z
> I understand "generating GPU P2P access cache" can be slow, because it needs to test the p2p of each gpu pair. I don't think it can take 20 minutes though. In my experience that's kind of 1~2 minutes.

can you reproduce my step? And you will see what i said.

## comment @youkaichao 2024-06-14T04:47:13Z
Can you try https://github.com/vllm-project/vllm/pull/5528 and give some feedback? I think that should solve this issue.

## comment @majestichou 2024-06-14T09:37:44Z
> Can you try #5528 and give some feedback? I think that should solve this issue.

What should I try? I use a docker image to start the service instead of compiling the source code. 
Should I modify the code in the docker container of vllm version 0.5.0 as the PR #5528 ?
Then restart the container.
Or should I pull the latest v0.5.0.post1 docker image and load the model with the latest image?


## comment @NiuBlibing 2024-06-14T10:46:14Z
> > Can you try #5528 and give some feedback? I think that should solve this issue.
> 
> What should I try? I use a docker image to start the service instead of compiling the source code. Should I modify the code in the docker container of vllm version 0.5.0 as the PR #5528 ? Then restart the container. Or should I pull the latest v0.5.0.post1 docker image and load the model with the latest image?

@youkaichao Maybe we need a ci to build nightly package for pr? Locally build and install is too boring and slow.

This is my test results:

v0.5.0: 8min50s
```
INFO 06-14 14:22:10 custom_all_reduce_utils.py:169] generating GPU P2P access cache in /root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json
INFO 06-14 14:31:00 custom_all_reduce_utils.py:179] reading GPU P2P access cache from /root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json
```

pr #5528 (I just remove the vllm config `/root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json`):  44s
```
INFO 06-14 18:44:29 custom_all_reduce_utils.py:184] generating GPU P2P access cache in /root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json
INFO 06-14 18:45:13 custom_all_reduce_utils.py:199] reading GPU P2P access cache from /root/.config/vllm/gpu_p2p_access_cache_for_0,1,2,3,4,5,6,7.json
``` 

## comment @Elissa0723 2024-06-14T10:48:38Z

I try to load qwen2_57b_a14b_instruct and met the same issue.
I had already updated to the latest code and used `os.environ['NCCL_IGNORE_DISABLED_P2P']` = '1'`

## comment @youkaichao 2024-06-14T16:40:16Z
@NiuBlibing glad it helps, the PR should be merged recently.

> Maybe we need a ci to build nightly package for pr?

It's ongoing. Since most PR only touches Python files, you can also manually replace these files to test.