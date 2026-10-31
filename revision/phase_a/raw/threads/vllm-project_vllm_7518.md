# vllm-project/vllm#7518: [Performance]: How to measure and understand the performance benefit of prefix caching
state=closed reason=completed created=2024-08-14T13:12:51Z closed=2024-11-14T08:52:08Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@PanJason)
### Proposal to improve performance

_No response_

### Report of performance regression

_No response_

### Misc discussion on performance

I am trying to understand how prefix caching helps with prompts of different lengths, so I ran the [benchmark_prefix_caching.py](https://github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_prefix_caching.py) with different prompt lengths (basically `PROMPT * n` in the code). I also changed the `num_prompts` to 1 and set the output_len to 1. 
I also changed the [`model_runner.py`](https://github.com/vllm-project/vllm/blob/main/vllm/worker/model_runner.py) to understand where the benefit comes from. IMO, the benefit should come from model execution because prefix caching reduces the complexity of attention of `O(n^2)` to `O(n)`. I added the following timestamps for my understanding:
```diff
diff --git a/vllm/worker/model_runner.py b/vllm/worker/model_runner.py
index f9c26e0c..fdac9af4 100644
--- a/vllm/worker/model_runner.py
+++ b/vllm/worker/model_runner.py
@@ -1360,6 +1360,7 @@ class ModelRunner(GPUModelRunnerBase[ModelInputForGPUWithSamplingMetadata]):
             "finished_requests_ids": model_input.finished_requests_ids,
             "request_ids_to_seq_ids": model_input.request_ids_to_seq_ids,
         } if self.has_seqlen_agnostic else {}
+        t0 = time.perf_counter()
         hidden_or_intermediate_states = model_executable(
             input_ids=model_input.input_tokens,
[... 31 lines truncated ...]
         return [output]
```
Basically, to get the time spent on model execution, logit computation, and sampling, respectively.

I set `n=40` (prompt len = 30121) and tested a llama-7b variant which supports a long context window. The commands I ran are as follows:
```bash
python3 benchmarks/benchmark_prefix_caching.py --model=togethercomputer/Llama-2-7B-32K-Instruct  --output-len=1 --enable-prefix-caching
python3 benchmarks/benchmark_prefix_caching.py --model=togethercomputer/Llama-2-7B-32K-Instruct  --output-len=1
```

The result I got when I enabled prefix caching is:
```bash
execute time: 0.011940602911636233
compute logits time: 6.694509647786617e-05
sample time: 0.022152308141812682
cost time 0.16930818557739258
```
Without prefix caching, it is:
```bash
execute time: 0.01532919192686677
compute logits time: 9.334413334727287e-05
sample time: 2.9377362160012126
cost time 2.982032060623169
```

I wonder why the sample time is decreased dramatically rather than the time when the `model_executable` is invoked. I further identified the place in `sampler.py` which costs the most time. By default, vllm uses the greedy sampler and the following [place](https://github.com/vllm-project/vllm/blob/d3d9cb6e4b8185b4e56e1dda92c6fc31cdc05de1/vllm/model_executor/layers/sampler.py#L337) in `greedy_sampler` is the most expensive:
```c
    samples_lst = samples.tolist()
```
This is very different from what I thought. One reason I can think of is that there is a future which is only invoked when `tolist()` is called and the model executable is not really executing the cuda kernel synchronously. I guess this may relate to cuda graph but I saw the above result both with cuda graph enabled and disabled. 

I also tried different models (llama-2-7b, llama-2-13b) with different prompt lengths. I saw similar issues happening where the most time reduction comes from sampling rather than `model_executable` so I am really confused now.
Is there anyone who has looked into the execution with prefix caching in detail? Thanks a lot!

### Your current environment (if you think it is necessary)

```text
Collecting environment information...                                                                                                                                                                                                                                                                               [43/60927]
PyTorch version: 2.4.0+cu121
Is debug build: False
CUDA used to build PyTorch: 12.1
ROCM used to build PyTorch: N/A

OS: Ubuntu 20.04.5 LTS (x86_64)                                                                                                                                                                                                                                                                                               GCC version: (Ubuntu 9.4.0-1ubuntu1~20.04.1) 9.4.0                                                                                                                                                                                                                                                                            Clang version: Could not collect                                                                                                                                                                                                                                                                                              CMake version: version 3.30.2
Libc version: glibc-2.31

Python version: 3.10.14 (main, Apr  6 2024, 18:45:05) [GCC 9.4.0] (64-bit runtime)
Python platform: Linux-6.2.0-39-generic-x86_64-with-glibc2.31
[... 100 lines truncated ...]
  NIC0: mlx5_bond_0
```


## comment @PanJason 2024-08-14T14:00:10Z
We also ran llava2 on A20 and saw a similar case

## comment @PanJason 2024-08-14T15:12:30Z
I think we have found the reason. This is because all the pytorch cuda operations are asynchronous which means the torch functions are just wrappers to launch the kernel and torch ensures the correct order with synchronization. See more details in [Asynchronous execution](https://github.com/user-attachments/assets/bda6df09-486b-4d0a-adfd-86320aee6aa1) in pytorch documentation.
This teach us a lesson: for all torch cuda related operations, use `torch.cuda.event` to measure time and one should never use `time.perf_counter()` which is only for end2end measurement

## comment @github-actions[bot] 2024-11-14T01:59:22Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!