# sgl-project/sglang#14665: [Bug] Llama4 on DGXH100 has regressed by 14.23%
state=closed reason=completed created=2025-12-08T19:29:46Z closed=2025-12-13T03:11:10Z labels=['bug', 'performance', 'nvidia', 'hopper']
cross-referenced PRs: ['https://github.com/sgl-project/sglang/pull/15009']

## body (@leejnau)
### Checklist

- [ ] I searched related issues but found no solution.
- [ ] The bug persists in the latest version.
- [ ] Issues without environment info and a minimal reproducible demo are hard to resolve and may receive no feedback.
- [ ] If this is not a bug report but a general question, please start a discussion at https://github.com/sgl-project/sglang/discussions. Otherwise, it will be closed.
- [ ] Please use English. Otherwise, it will be closed.

### Describe the bug

The Llama4 model performance has regressed 14%+ on the 8-GPU (DGX) H100 system (with concurrency 128 the drop is even bigger than 14%).  This issue may be reproduced either on a DGXH100 or any system with 8 H100 GPUs on the same node.

- Downgrading the FlashInfer version did not result in any performance difference so is likely not the cause.  

- The most likely culprit is the PyTorch version, since its version changed between the containers: 

```
last_good=lmsysorg/sglang:nightly-dev-20251124-4683e244
first_bad=lmsysorg/sglang:nightly-dev-20251127-b087ef8b
```

### Reproduction

Below are the commands to reproduce:

```
# Setup: 8xH100 gpus.

last_good=lmsysorg/sglang:nightly-dev-20251124-4683e244
first_bad=lmsysorg/sglang:nightly-dev-20251127-b087ef8b

docker run -it --rm --gpus all --ipc=host --network=host --ulimit memlock=-1 --ulimit stack=67108864 --entrypoint /bin/bash $last_good # or first_bad

model_path=meta-llama/Llama-4-Scout-17B-16E # Note that this is a gated model, so you need to be logged in to a HF account and have access to it.

pip install aiperf

[... 21 lines truncated ...]
  --artifact-dir "aiperf_results_1000_1000_128"
```

Below are the results for both the last good config and the first bad config:

```
# Results:
# ------- last good
                                                NVIDIA AIPerf | LLM Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃                               Metric ┃       avg ┃       min ┃       max ┃       p99 ┃       p90 ┃       p50 ┃      std ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│             Time to First Token (ms) │  1,661.47 │    432.92 │  5,899.66 │  5,481.33 │  3,085.93 │  1,495.17 │ 1,035.62 │
│            Time to Second Token (ms) │  1,196.70 │     17.73 │  3,787.02 │  3,668.10 │  2,813.26 │    989.37 │   948.32 │
│                 Request Latency (ms) │ 24,830.33 │ 23,946.02 │ 27,859.63 │ 27,859.14 │ 27,854.22 │ 24,075.01 │ 1,513.40 │
│             Inter Token Latency (ms) │     22.68 │     21.12 │     25.27 │     25.07 │     24.12 │     22.51 │     0.93 │
│     Output Token Throughput Per User │     44.17 │     39.57 │     47.34 │     46.87 │     46.24 │     44.42 │     1.75 │
[... 30 lines truncated ...]
5,250.25 vs 486.20 token throughput (90% regression)
```

### Environment

Below is the last good environment:

```
# last_good lmsysorg/sglang:nightly-dev-20251124-4683e244 
 
root@4u8g-gen-0078:/sgl-workspace/sglang# python -m sglang.check_env 
Python: 3.12.12 (main, Oct 10 2025, 08:52:57) [GCC 11.4.0] 
CUDA available: True 
GPU 0,1,2,3,4,5,6,7: NVIDIA H100 NVL 
GPU 0,1,2,3,4,5,6,7 Compute Capability: 9.0 
CUDA_HOME: /usr/local/cuda 
NVCC: Cuda compilation tools, release 12.9, V12.9.86 
CUDA Driver Version: 550.127.05 
PyTorch: 2.8.0+cu129 
[... 59 lines truncated ...]
ulimit soft: 1048576 
```

Below is the first bad environment:
 
 ```
# first_bad lmsysorg/sglang:nightly-dev-20251127-b087ef8b 
 
root@4u8g-gen-0078:/sgl-workspace/sglang# python -m sglang.check_env 
Python: 3.12.12 (main, Oct 10 2025, 08:52:57) [GCC 11.4.0] 
CUDA available: True 
GPU 0,1,2,3,4,5,6,7: NVIDIA H100 NVL 
GPU 0,1,2,3,4,5,6,7 Compute Capability: 9.0 
CUDA_HOME: /usr/local/cuda 
NVCC: Cuda compilation tools, release 12.9, V12.9.86 
CUDA Driver Version: 550.127.05 
PyTorch: 2.9.1+cu129 
[... 59 lines truncated ...]
ulimit soft: 1048576
```

## comment @b8zhong 2025-12-08T19:41:29Z
Hi, can you try adding the following for both? Also this is for the BF16 checkpoint right?

`--kv-cache-dtype bfloat16`

## comment @wenscarl 2025-12-10T22:04:34Z
In the good container:
With b087ef8b4b802d055610c492e54a22673de96a8b (first bad commit), forcing sgl_kernel unchanged:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
┃                               Metric ┃       avg ┃       min ┃       max ┃       p99 ┃       p90 ┃       p50 ┃    std ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
│             Time to First Token (ms) │  1,435.85 │    107.95 │  4,542.14 │  4,262.72 │  2,297.43 │  1,402.43 │ 778.41 │
│            Time to Second Token (ms) │  1,112.50 │      0.17 │  3,234.74 │  3,164.31 │  2,310.45 │  1,024.06 │ 800.21 │
│                 Request Latency (ms) │ 24,083.21 │ 23,426.47 │ 26,046.04 │ 26,045.39 │ 26,041.71 │ 23,545.55 │ 988.41 │
│             Inter Token Latency (ms) │     22.16 │     20.50 │     24.49 │     24.11 │     23.27 │     22.12 │   0.81 │
│     Output Token Throughput Per User │     45.18 │     40.83 │     48.78 │     47.98 │     47.22 │     45.21 │   1.62 │
│                    (tokens/sec/user) │           │           │           │           │           │           │        │
│      Output Sequence Length (tokens) │  1,023.01 │    999.00 │  1,055.00 │  1,041.61 │  1,033.00 │  1,022.00 │   7.61 │
│       Input Sequence Length (tokens) │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │   0.00 │
[... 2 lines truncated ...]

```
with 4683e244fe62db8b116a4c37e12409bf9964b5b6 (last good commit)
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
┃                               Metric ┃       avg ┃       min ┃       max ┃       p99 ┃       p90 ┃       p50 ┃    std ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
│             Time to First Token (ms) │  1,173.79 │    273.51 │  2,157.10 │  2,088.21 │  1,886.63 │  1,177.92 │ 537.90 │
│            Time to Second Token (ms) │    862.31 │     18.54 │  1,883.60 │  1,833.02 │  1,621.48 │    895.16 │ 553.65 │
│                 Request Latency (ms) │ 23,475.60 │ 23,323.91 │ 23,575.59 │ 23,575.33 │ 23,571.83 │ 23,477.00 │  62.44 │
│             Inter Token Latency (ms) │     21.82 │     20.69 │     22.97 │     22.83 │     22.59 │     21.81 │   0.57 │
│     Output Token Throughput Per User │     45.86 │     43.53 │     48.34 │     48.04 │     47.50 │     45.84 │   1.20 │
│                    (tokens/sec/user) │           │           │           │           │           │           │        │
│      Output Sequence Length (tokens) │  1,023.08 │    999.00 │  1,047.00 │  1,042.61 │  1,033.00 │  1,023.00 │   7.82 │
│       Input Sequence Length (tokens) │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │  1,000.00 │   0.00 │
[... 1 lines truncated ...]
│             Request Count (requests) │    640.00 │       N/A │       N/A │       N/A │       N/A │       N/A │    N/A │
```

## comment @wenscarl 2025-12-11T02:30:21Z
The big gap comes from the fa3. Running bench_one_batch:
```
python3 -m sglang.bench_one_batch \
    --model-path meta-llama/Llama-4-Scout-17B-16E \
    --disable-radix-cache \
    --context-length 2048 \
    --attention-backend fa3 \
    --load-format dummy \
    --batch-size 128 \
    --tp-size 8 \
    --input-len 1000 \
    --output-len 1000
```
got:
in bad container: 
```
Benchmark ...
Prefill. latency: 1.88961 s, throughput:  67738.75 token/s
Decode 0. Batch size: 128, latency: 0.18360 s, throughput:    697.16 token/s
Decode 1. Batch size: 128, latency: 0.18259 s, throughput:    701.01 token/s
Decode 2. Batch size: 128, latency: 0.17793 s, throughput:    719.40 token/s
Decode 3. Batch size: 128, latency: 0.18186 s, throughput:    703.83 token/s
Decode 4. Batch size: 128, latency: 0.18281 s, throughput:    700.19 token/s
```

in good container:
```
Prefill. latency: 1.73583 s, throughput:  73740.04 token/s
Decode 0. Batch size: 128, latency: 0.03107 s, throughput:   4119.41 token/s
Decode 1. Batch size: 128, latency: 0.01935 s, throughput:   6615.37 token/s
Decode 2. Batch size: 128, latency: 0.01881 s, throughput:   6806.59 token/s
Decode 3. Batch size: 128, latency: 0.01916 s, throughput:   6679.67 token/s
Decode 4. Batch size: 128, latency: 0.01909 s, throughput:   6705.10 token/s
```
Switching to triton backend, both containers reaches similar decode throughput > 7k token/s. 
Both containers have similar cuda kernel time but in the bad one, there is big cpu gap b/w the following 2 ops.

<img width="1027" height="797" alt="Image" src="https://github.com/user-attachments/assets/bb5ea89f-781b-4566-b947-8ecfdb7edf81" />

As compare, the good one looks like:

<img width="1634" height="814" alt="Image" src="https://github.com/user-attachments/assets/2953dea7-24b7-4e46-b9cf-e01a4a6a1c51" />

very likely a torch issue brought by upgrade.

## comment @wenscarl 2025-12-12T19:39:24Z
Fixed by https://github.com/sgl-project/sglang/pull/15009