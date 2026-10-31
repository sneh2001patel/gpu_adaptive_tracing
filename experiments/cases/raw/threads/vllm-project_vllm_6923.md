# vllm-project/vllm#6923: [Bug]: Prefix Caching in BlockSpaceManagerV1 and BlockSpaceManagerV2 Increases Time to First Token(TTFT) and Slows Down System
state=closed reason=completed created=2024-07-30T00:50:20Z closed=2024-12-06T02:07:18Z labels=['bug', 'stale']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/7209']

## body (@llsj14)
### Your current environment

```text
PyTorch version: 2.3.1+cu121
Is debug build: False
CUDA used to build PyTorch: 12.1
ROCM used to build PyTorch: N/A

OS: Ubuntu 22.04.3 LTS (x86_64)
GCC version: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0
Clang version: Could not collect
CMake version: version 3.27.6
Libc version: glibc-2.35

[... 36 lines truncated ...]
CUDA Archs: 5.2 6.0 6.1 7.0 7.2 7.5 8.0 8.6 8.7 9.0+PTX; ROCm: Disabled; Neuron: Disabled
```


### 🐛 Describe the bug

When enabling prefix caching in BlockSpaceManagerV2, the system experiences a slowdown, particularly with an increased time to first token(ttft). The following are the results of my experiments with the Llama3 8B and 70B models.
Initially, I suspected the tensor parallel logic, but since the 8B model, which I ran on a single GPU, also showed a slowdown, I believe the cause lies elsewhere.
(By the way, prefix caching in BlockSpaceManagerV1 showed a 1.3-1.5x speedup in the time to first token metric with the same experiment settings.)

### Experiment Settings
- I tested with [llmperf](https://github.com/ray-project/llmperf), which can vary the number of clients, affecting the maximum batch size in the vLLM worker.
- The total input length was set to 1536, with a prefix prompt length of 512.

### Llama 70B result
Model | Num GPUs | Num Clients | Block Manager | Prefix Caching | TTFT (mean)
-- | -- | -- | -- | -- | --
Llama3-70B | 4 | 16 | v2 | X | 2415 ms
Llama3-70B | 4 | 32 | v2 | X | 4179 ms
Llama3-70B | 4 | 64 | v2 | X | 7670 ms
Llama3-70B | 4 | 128 | v2 | X | 12883 ms
Llama3-70B | 4 | 16 | v2 | O | 2755 ms
Llama3-70B | 4 | 32 | v2 | O | 4652 ms
Llama3-70B | 4 | 64 | v2 | O | 14344 ms
Llama3-70B | 4 | 128 | v2 | O | 25500 ms

### Llama 8B result
Model | Num GPUs | Num Clients | Block Manager | Prefix Caching | TTFT (mean)
-- | -- | -- | -- | -- | --
Llama3-8B | 1 | 16 | v2 | X | 841 ms
Llama3-8B | 1 | 32 | v2 | X | 1441 ms
Llama3-8B | 1 | 64 | v2 | X | 2619 ms
Llama3-8B | 1 | 128 | v2 | X | 4729 ms
Llama3-8B | 1 | 16 | v2 | O | 1962 ms
Llama3-8B | 1 | 32 | v2 | O | 8382 ms
Llama3-8B | 1 | 64 | v2 | O | 12665 ms
Llama3-8B | 1 | 128 | v2 | O | 22439 ms





## comment @Ximingwang-09 2024-07-31T07:53:44Z
I meet the problem when enabling prefix caching in BlockSpaceManagerV2 ...

## comment @github-actions[bot] 2024-11-06T01:58:31Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2024-12-06T02:07:18Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!