# vllm-project/vllm#6240: [Bug]: Performance : slow inference for FP8 on L20 with 0.5.1(v0.5.0.post1 was fine)
state=closed reason=completed created=2024-07-09T03:50:20Z closed=2024-07-15T16:57:10Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/6384']

## body (@garycaokai)
### Your current environment


```text
Collecting environment information...
PyTorch version: 2.3.0+cu121
Is debug build: False
CUDA used to build PyTorch: 12.1
ROCM used to build PyTorch: N/A

OS: Ubuntu 22.04.4 LTS (x86_64)
GCC version: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0
Clang version: Could not collect
CMake version: version 3.30.0
Libc version: glibc-2.35
[... 59 lines truncated ...]
  NIC0: mlx5_bond_0
```


### 🐛 Describe the bug

The inference speed of vllm0.5.1 with fp8 quantization on L20 is even slower than fp16.

qwen2-7b @ L20*1:
| vllm version | quant | speed | 
|:-----:|:-----:|:-----:| 
| 0.5.0 | fp8 | 59.41 token/s | 
| 0.5.0 | fp16 | 44.05 token/s | 
| 0.5.1 | fp8 | **26.50** token/s | 
| 0.5.1 | fp16 | 43.60 token/s | 



## comment @garycaokai 2024-07-09T06:38:24Z
llama3 8b
vllm version | quant | speed
-- | -- | --
0.5.0 | fp8 | 56.28 token/s
0.5.0 | fp16 | 41.72 token/s
0.5.1 | fp8 | **25.36** token/s
0.5.1 | fp16 | 41.38 token/s



## comment @youkaichao 2024-07-09T06:44:19Z
cc @robertgshaw2-neuralmagic 

## comment @garycaokai 2024-07-09T09:15:38Z
qwen2-7b fp8 marlin kernel seems better on vllm v0.5.1

| gpu | speed | 
|:-----:|:-----:| 
| A30 | 70.09 token/s | 
| L20 | 68.81 token/s | 

## comment @tlrmchlsmth 2024-07-09T18:06:20Z
Hi @garycaokai, I'm trying to reproduce the issue on an L40, but no luck so far. Could you share the exact script and model you are using to run these benchmarks?

## comment @garycaokai 2024-07-10T03:52:46Z
> Hi @garycaokai, I'm trying to reproduce the issue on an L40, but no luck so far. Could you share the exact script and model you are using to run these benchmarks?

```console
python3 -m vllm.entrypoints.openai.api_server \
    --served-model-name llama \
    --model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 \
    --trust-remote-code \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --max-num-batched-tokens 32000 \
    --host 0.0.0.0 \
    --use-v2-block-manager \
    --port 8360

client use postman
```

## comment @tlrmchlsmth 2024-07-10T13:21:23Z
Thanks, could you also share how the client is querying the server? If you could reproduce the problem using `benchmarks/benchmark_serving.py`, that would be very helpful.

Also, did you build from source or install from pypi? If you built from source, could you share the version of `nvcc` that you built with? vLLM uses different FP8 kernels for Ada Lovelace on 12.4 and later.

## comment @garycaokai 2024-07-11T07:06:01Z
> Thanks, could you also share how the client is querying the server? If you could reproduce the problem using `benchmarks/benchmark_serving.py`, that would be very helpful.
> 
> Also, did you build from source or install from pypi? If you built from source, could you share the version of `nvcc` that you built with? vLLM uses different FP8 kernels for Ada Lovelace on 12.4 and later.

I downloaded the docker image from https://hub.docker.com/r/vllm/vllm-openai, found the cuda version is 12.1, 
```console
$ docker pull vllm/vllm-openai:v0.5.1
 
$ nvidia-smi 
Thu Jul 11 06:56:21 2024       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.54.15              Driver Version: 550.54.15      CUDA Version: 12.4     |

$ python3
>>> import torch
>>> print(torch.version.cuda)
12.1
[... 74 lines truncated ...]
==================================================
 ```

## comment @tlrmchlsmth 2024-07-11T13:32:42Z
Thank you. I think I see what's happening. 

Actually the relevant CUDA version for this particular issue is not the version that torch is compiled with (`torch.version.cuda`), but rather the CUDA version that vLLM's custom kernels were compiled with, which looks to be 12.4, seen here:
>| NVIDIA-SMI 550.54.15              Driver Version: 550.54.15      CUDA Version: 12.4     |

I'll try to reproduce the problem and update here.

## comment @garycaokai 2024-07-11T14:38:36Z
> ```
> vllm 0.5.1 fp8 benchmark
> ```

add the vllm 0.5.1 marlin kernel, and vllm 0.5.1 fp8 kernel performance data

## comment @garycaokai 2024-07-15T04:01:21Z
> Thank you. I think I see what's happening.
> 
> Actually the relevant CUDA version for this particular issue is not the version that torch is compiled with (`torch.version.cuda`), but rather the CUDA version that vLLM's custom kernels were compiled with, which looks to be 12.4, seen here:
> 
> > | NVIDIA-SMI 550.54.15              Driver Version: 550.54.15      CUDA Version: 12.4     |
> 
> I'll try to reproduce the problem and update here.



> Thank you. I think I see what's happening.
> 
> Actually the relevant CUDA version for this particular issue is not the version that torch is compiled with (`torch.version.cuda`), but rather the CUDA version that vLLM's custom kernels were compiled with, which looks to be 12.4, seen here:
> 
> > | NVIDIA-SMI 550.54.15              Driver Version: 550.54.15      CUDA Version: 12.4     |
> 
> I'll try to reproduce the problem and update here.

your new version works fine~
```console
vllm 0.5.1.0715
Traffic request rate: 20.0
100%|██████████| 300/300 [00:55<00:00,  5.43it/s]
============ Serving Benchmark Result ============
Successful requests:                     300       
Benchmark duration (s):                  55.28     
Total input tokens:                      62238     
Total generated tokens:                  60431     
Request throughput (req/s):              5.43      
Input token throughput (tok/s):          1125.84   
Output token throughput (tok/s):         1093.15   
[... 11 lines truncated ...]
==================================================
```

## comment @mgoin 2024-07-15T16:57:10Z
Resolved by https://github.com/vllm-project/vllm/pull/6384