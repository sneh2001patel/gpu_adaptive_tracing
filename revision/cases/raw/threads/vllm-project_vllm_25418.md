# vllm-project/vllm#25418: [Performance][Multimodal]: Per-request `mm_processor_kwargs` are very slow
state=closed reason=completed created=2025-09-22T20:01:15Z closed=2025-11-06T23:51:29Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/25941', 'https://github.com/vllm-project/vllm/pull/26483']

## body (@lgeiger)
### Proposal to improve performance

Passing per-request `mm_processor_kwargs` like FPS as added in #13533 greatly reduces performance.

### Report of performance regression

I tested this on latest `main` (239ef0c1ac0dfe68d8d2e28c54ecf9aa9bcd945b):

```shell
vllm serve Qwen/Qwen2.5-VL-7B-Instruct

vllm bench serve --backend openai-chat --endpoint-type openai-chat --model Qwen/Qwen2.5-VL-7B-Instruct --endpoint /v1/chat/completions --dataset-name hf --dataset-path lmarena-ai/VisionArena-Chat --hf-split train --num-prompts 100
```

Baseline performance on a single L40s GPU
```
============ Serving Benchmark Result ============
Successful requests:                     100
Benchmark duration (s):                  13.73
Total input tokens:                      5280
Total generated tokens:                  11260
Request throughput (req/s):              7.28
Output token throughput (tok/s):         819.84
Peak output token throughput (tok/s):    2509.00
Peak concurrent requests:                100.00
Total Token throughput (tok/s):          1204.27
---------------Time to First Token----------------
[... 10 lines truncated ...]
==================================================
```

With the following patch applied to simulate different `mm_processor_kwargs` per request, performance is greatly reduced.

```diff
diff --git a/vllm/benchmarks/serve.py b/vllm/benchmarks/serve.py
index 7382782f1..2916f57af 100644
--- a/vllm/benchmarks/serve.py
+++ b/vllm/benchmarks/serve.py
@@ -647,7 +647,7 @@ async def benchmark(
             multi_modal_content=mm_content,
             ignore_eos=ignore_eos,
             extra_headers=extra_headers,
-            extra_body=extra_body,
+            extra_body={**extra_body, "mm_processor_kwargs": {"fps": random.uniform(1.9, 2.1)}},
             request_id=request_id,
         )
         tasks.append(
```
```
============ Serving Benchmark Result ============
Successful requests:                     100
Benchmark duration (s):                  311.55
Total input tokens:                      5280
Total generated tokens:                  11180
Request throughput (req/s):              0.32
Output token throughput (tok/s):         35.89
Peak output token throughput (tok/s):    61.00
Peak concurrent requests:                100.00
Total Token throughput (tok/s):          52.83
---------------Time to First Token----------------
[... 10 lines truncated ...]
==================================================
```

### Misc discussion on performance

I assume this is caused by the huggingface preprocessor being re-created on every request since the `mm_processor_kwargs` are part of the cache key https://github.com/vllm-project/vllm/blob/8db29392899b12843787b0a03880f70a6e6ac88e/vllm/transformers_utils/processor.py#L135-L149

I'm not sure whether this could be avoided, but in its current state this introduces a huge performance bottleneck.

## comment @DarkLight1337 2025-09-23T00:25:45Z
I think we can set a flag per-model that indicates which arguments affect the hash during processor initialization.

## comment @LJH-LBJ 2025-09-23T02:08:01Z
Hello, can I take this one?

## comment @DarkLight1337 2025-09-23T04:54:29Z
Sure!

## comment @DarkLight1337 2025-09-25T09:46:46Z
When will you be able to open the PR?

## comment @LJH-LBJ 2025-09-30T02:42:54Z
Sorry, something else came up and delayed me, I will open the PR today.