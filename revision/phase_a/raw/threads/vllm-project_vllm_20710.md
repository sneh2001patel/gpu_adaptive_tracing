# vllm-project/vllm#20710: [Performance]: Unexpected Inference Speed Gain at Concurrency 16 vs 1 on Llama-3.3-70B (FP8, B200, vLLM v0.9.0)
state=closed reason=not_planned created=2025-07-09T21:31:21Z closed=2025-11-07T02:10:00Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@Juno13340)
### Proposal to improve performance

Observed an unexpected inference speed gain when running LLaMA-3.3-70B (FP8, B200) with vLLM v0.9.0 under concurrency 16 compared to concurrency 1.

Goal is to understand whether this is a known scheduling/dispatch behavior or something that can be optimized or improved under low concurrency (e.g., concurrency=1).


### Report of performance regression

### Summary
While benchmarking the LLaMA-3.3-70B-Instruct model (FP8 quantized) on vLLM v0.9.0 with 2xB200 GPUs, I observed significantly higher output inference speed at concurrency 16 than at concurrency 1.

### Steps Taken
- ✅ Re-ran genai-bench at concurrency=1 and concurrency=16 → speed gain confirmed
- ✅ Verified e2e_latency and TTFT → e2e_latency is **lower** at concurrency=16
- ✅ Used benchmark_serving.py → concurrency=16 yields higher token throughput despite higher TTFT
- ✅ Confirmed token count output is consistent

### Example Results (Fusion task, 512 in / 512 out)
| Concurrency | TTFT | e2e_latency | Output Speed (tok/s) |
|-------------|------|-------------|------------------------|
| 1           | 0.05 | 8.29        | 35.04                  |
| 16          | 0.07 | 5.99        | 49.97                  |

### Hypothesis
Possibly related to internal batching, token dispatch, or scheduling behavior being more optimized under higher concurrency. Could also involve KV cache behavior with FP8 or memory layout.

### Ask
Is this speed gain at concurrency 16 expected? Should concurrency=1 path be optimized, or is this considered normal behavior under FP8 B200?

Happy to share logs or full benchmark trace if helpful.


### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
vLLM version: v0.9.0  
CUDA version: 12.1  
GPU: 2x NVIDIA B200 (FP8)  
Container: vllm/vllm-openai:v0.9.0  
Model: LLaMA-3.3-70B-Instruct  
Benchmarking tool: genai-bench 0.1.132  
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @github-actions[bot] 2025-10-08T02:02:04Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-11-07T02:09:59Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!