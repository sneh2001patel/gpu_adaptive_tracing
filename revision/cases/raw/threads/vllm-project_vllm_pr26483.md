# vllm-project/vllm PR #26483: Speed up mm processor kwargs per request by spliting dynamic and static kwargs
merged_at=2025-11-06T23:51:28Z merge_commit=59b453eaa2b5434c62cf954e75937cd930cbdc13 author=@LJH-LBJ
files: tests/transformers_utils/test_get_processor_kwargs_from_processor.py, vllm/transformers_utils/processor.py

## body
<small>

## Purpose  
fix https://github.com/vllm-project/vllm/issues/25418

## Test Plan  
<pre style="white-space:pre-wrap; font-size:smaller;">
vllm serve \
    /workspace/models/Qwen2.5-VL-7B-Instruct \
    --port 5580 --host 0.0.0.0 \
    --max-num-seqs 128 --dtype bfloat16 --max-model-len=8192  \
    --no-enable-prefix-caching --trust-remote-code -tp 1\
    --gpu-memory-utilization=0.93
</pre>

<pre style="white-space:pre-wrap; font-size:smaller;">
vllm bench serve \
--backend openai-chat \
--port 5580 \
--host 127.0.0.1 \
--endpoint /v1/chat/completions \
--model /workspace/models/Qwen2.5-VL-7B-Instruct \
--dataset-name hf \
--dataset-path lmarena-ai/VisionArena-Chat \
--hf-split train \
--num-prompts 100
</pre>

Add verification
<pre style="white-space:pre-wrap; font-size:smaller;">
diff --git a/vllm/benchmarks/serve.py b/vllm/benchmarks/serve.py
index c3c45f05f..91cbd3e75 100644
--- a/vllm/benchmarks/serve.py
+++ b/vllm/benchmarks/serve.py
@@ -670,7 +670,7 @@ async def benchmark(
             multi_modal_content=mm_content,
             ignore_eos=ignore_eos,
             extra_headers=extra_headers,
-            extra_body=extra_body,
+            extra_body={**extra_body, "mm_processor_kwargs": {"fps": random.uniform(1.9, 2.1)}},
             request_id=request_id,
         )
         tasks.append(
diff --git a/vllm/multimodal/processing.py b/vllm/multimodal/processing.py
index a2d3db75d..7e1ce3a5c 100644
--- a/vllm/multimodal/processing.py
+++ b/vllm/multimodal/processing.py
@@ -1815,7 +1815,7 @@ class BaseMultiModalProcessor(ABC, Generic[_I]):
         caching the results and reusing cached results.
         """
         cache = self.cache
-
+        logger.warning(f"MM_HASH_KWARGS={hf_processor_mm_kwargs},mm_uuids={mm_uuids}")
         _, passthrough_data = self._get_hf_mm_data(mm_data_items)
         if cache is None or passthrough_data:
             return self._apply_hf_processor(

</pre>
## Test Result

<pre style="white-space:pre-wrap; font-size:smaller;">
Before:
============ Serving Benchmark Result ============
Successful requests:                     10        
Benchmark duration (s):                  33.42     
Total input tokens:                      313       
Total generated tokens:                  1148      
Request throughput (req/s):              0.30      
Output token throughput (tok/s):         34.35     
Peak output token throughput (tok/s):    90.00     
Peak concurrent requests:                10.00     
Total Token throughput (tok/s):          43.71     
---------------Time to First Token----------------
Mean TTFT (ms):                          28827.40  
Median TTFT (ms):                        28462.53  
P99 TTFT (ms):                           31998.74  
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          1.10      
Median TPOT (ms):                        0.00      
P99 TPOT (ms):                           10.04     
---------------Inter-token Latency----------------
Mean ITL (ms):                           10.23     
Median ITL (ms):                         11.00     
P99 ITL (ms):                            12.08     
==================================================

</pre>

<pre style="white-space:pre-wrap; font-size:smaller;">
After：
============ Serving Benchmark Result ============
Successful requests:                     100       
Benchmark duration (s):                  11.10     
Total input tokens:                      5280      
Total generated tokens:                  11098     
Request throughput (req/s):              9.01      
Output token throughput (tok/s):         999.75    
Peak output token throughput (tok/s):    4554.00   
Peak concurrent requests:                100.00    
Total Token throughput (tok/s):          1475.40   
---------------Time to First Token----------------
Mean TTFT (ms):                          4109.83   
Median TTFT (ms):                        3925.76   
P99 TTFT (ms):                           8649.84   
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          68.15     
Median TPOT (ms):                        61.41     
P99 TPOT (ms):                           248.57    
---------------Inter-token Latency----------------
Mean ITL (ms):                           56.21     
Median ITL (ms):                         20.05     
P99 ITL (ms):                            283.84    
==================================================
</pre>

![Snipaste_2025-10-10_12-11-29](https://github.com/user-attachments/assets/6f22ed2b-866b-4970-b215-0f0ab7b75274)

---

<details>
<summary> Essential Elements of an Effective PR Description Checklist </summary>
<small>
- [ ] The purpose of the PR, such as "Fix some issue (link existing issues this PR will resolve)".
- [ ] The test plan, such as providing test command.
- [ ] The test results, such as pasting the results comparison before and after, or e2e results
- [ ] (Optional) The necessary documentation update, such as updating `supported_models.md` and `examples` for a new model.
- [ ] (Optional) Release notes update. If your change is user facing, please update the release notes draft in the [Google Doc](https://docs.google.com/document/d/1YyVqrgX4gHTtrstbq8oWUImOyPCKSGnJ7xtTpmXzlRs/edit?tab=t.0).
</small>
</details>

