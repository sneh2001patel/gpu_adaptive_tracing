# vllm-project/vllm#23739: [Performance]: The full cudagraph seems not work.
state=closed reason=completed created=2025-08-27T11:16:05Z closed=2026-01-05T17:34:28Z labels=['performance', 'stale']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/16072']

## body (@xsank)
### Proposal to improve performance

_No response_

### Report of performance regression


command:
```shell
env VLLM_FLASH_ATTN_VERSION=3 VLLM_ATTENTION_BACKEND=FLASH_ATTN  CUDA_VISIBLE_DEVICES=5  vllm serve Qwen/Qwen3-Reranker-0.6B --task=score --port 12346 --data-parallel-size=1 --gpu-memory-utilization=0.6 --max-num-seqs=45 --quantization='fp8' --compilation-config '{"full_cuda_graph": true}' 
```

### Misc discussion on performance

<img width="2076" height="1052" alt="Image" src="https://github.com/user-attachments/assets/72ae7ea5-e3ee-41d5-af48-ce323ca6ea00" />

<img width="1904" height="700" alt="Image" src="https://github.com/user-attachments/assets/64a999ef-34e7-4249-8ae4-fbf056e2046e" />

### Your current environment (if you think it is necessary)

```shell
==============================
        System Info
==============================
OS                           : CentOS Linux Server 7.2 (Paladin) (x86_64)
GCC version                  : (GCC) 10.2.1 20200825 (Alibaba 10.2.1-3 2.17)
Clang version                : Could not collect
CMake version                : Could not collect
Libc version                 : glibc-2.32

==============================
       PyTorch Info
[... 160 lines truncated ...]
CUDA_MODULE_LOADING=LAZY
```

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @ProExpertProg 2025-09-05T21:49:48Z
What's the actual perf regression here?

## comment @xsank 2025-09-07T08:57:28Z
Use full cuda graph, the profiler maybe only could see the cuda graph launch rather than the separated node launch?

## comment @ProExpertProg 2025-09-08T17:31:56Z
Could you post the output of the logs with VLLM_LOGGING_LEVEL=DEBUG for the `vllm serve` command?

## comment @xsank 2025-09-09T07:36:45Z
@ProExpertProg 
```shell
env VLLM_LOGGING_LEVEL=DEBUG VLLM_TEST_DYNAMO_FULLGRAPH_CAPTURE=1 VLLM_ATTENTION_BACKEND=FLASH_ATTN VLLM_TORCH_PROFILER_DIR=/root/profile CUDA_VISIBLE_DEVICES=5 nsys launch --session-new=vllm_profile --trace-fork-before-exec=true --cuda-graph-trace=node  --trace=cublas,cuda,cudnn,nvtx vllm serve Qwen/Qwen3-Reranker-0.6B --task=score --port 12346 --data-parallel-size=1 --gpu-memory-utilization=0.2 --max-num-seqs=200 --quantization='fp8' --compilation-config '{"full_cuda_graph": true, "cudagraph_num_of_warmups": 200}' -O3 --disable-log-requests
DEBUG 09-09 15:32:49 [__init__.py:30] No plugins for group vllm.platform_plugins found.
DEBUG 09-09 15:32:49 [__init__.py:35] Checking if TPU platform is available.
DEBUG 09-09 15:32:49 [__init__.py:45] TPU platform is not available because: No module named 'libtpu'
DEBUG 09-09 15:32:49 [__init__.py:52] Checking if CUDA platform is available.
DEBUG 09-09 15:32:49 [__init__.py:72] Confirmed CUDA platform is available.
DEBUG 09-09 15:32:49 [__init__.py:100] Checking if ROCm platform is available.
DEBUG 09-09 15:32:49 [__init__.py:114] ROCm platform is not available because: No module named 'amdsmi'
DEBUG 09-09 15:32:49 [__init__.py:121] Checking if XPU platform is available.
DEBUG 09-09 15:32:49 [__init__.py:140] XPU platform is not available because: No module named 'intel_extension_for_pytorch'
DEBUG 09-09 15:32:49 [__init__.py:147] Checking if CPU platform is available.
[... 314 lines truncated ...]
INFO:     Application startup complete.
```
the debug log is the same with the profiler result. the graph is separated to many pieces.

## comment @ProExpertProg 2025-09-09T20:36:22Z
It appears using an old version of vLLM, can you try with a more recent version?

## comment @xsank 2025-09-10T01:56:51Z
> It appears using an old version of vLLM, can you try with a more recent version?

But he full cudagraph feature is already merged into the version 0.10.0, you mean the latest version 0.10.1 works well?

## comment @ProExpertProg 2025-09-25T00:15:43Z
@xsank a lot has changed around cudagraphs recently, that's why I mention it

## comment @xsank 2025-09-29T12:10:06Z
> [@xsank](https://github.com/xsank) a lot has changed around cudagraphs recently, that's why I mention it

ok, i will try the latest version recently.

## comment @github-actions[bot] 2025-12-30T02:29:42Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @ProExpertProg 2026-01-05T17:34:28Z
Closing for now, please open new issue if there are problems with full cudagraphs