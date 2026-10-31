# sgl-project/sglang#922: TTFT latency for long context (16K) is very high around 15 seconds for llama3.1 70b model. (same or worse than vLLM)
state=closed reason=completed created=2024-08-04T23:14:23Z closed=2024-10-09T01:10:58Z labels=['high priority', 'performance']
cross-referenced PRs: none

## body (@gkiri)
### Checklist

- [X] 1. I have searched related issues but cannot get the expected help.
- [X] 2. The bug has not been fixed in the latest version.
- [ ] 3. Please note that if the bug-related issue you submitted lacks corresponding environment info and a minimal reproducible demo, it will be challenging for us to reproduce and resolve the issue, reducing the likelihood of receiving feedback.

### Describe the bug

I am experimenting with SGLang and vLLM for long context(16K) RAG application which requires real time responses.
I am using single Nvidia A6000 48GB GPU and llaam3.1 70b awq 4 bit model.

Currently I am seeing Time for first token latency is around 15 seconds which is very high.
Experimented with parameters like --chunked-prefill-size , --mem-frac etc

can you please suggest what are the parameters I need to mainly focus on to get the optimal TTFT for long context ?

### Reproduction

na

### Environment

```Shell
na
```


## comment @Ying1123 2024-08-05T03:47:27Z
SGLang currently mostly accelerates the decoding, so what you observed is expected. We are working on multiple optimizations that can accelerate prefill for long context workloads. Some of them should be ready soon. We will let you know when it is ready!

## comment @zhyncs 2024-08-05T04:35:04Z
Hi @gkiri May you provide a script for me to reproduce the situation you mentioned? Thanks.

## comment @gkiri 2024-08-05T13:11:18Z
 python3 -m sglang.launch_server --model-path hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4 --dtype half --trust-remote-code --quantization marlin  --enable-p2p-check --efficient-weight-load --host 0.0.0.0 --mem-fraction-static 0.875 --disable-cuda-graph --max-running-requests 5 --port 30000 --context-length 16000

## comment @gkiri 2024-08-05T13:15:38Z
Please provide Input query length >10K tokens to observe high TTFT latency

## comment @zhyncs 2024-08-05T17:57:30Z
@gkiri Thanks! May you provide a simple client demo?

## comment @min-xu-et 2024-08-05T19:14:46Z
@gkiri can you also provide the vllm command line for your test?

## comment @gkiri 2024-08-06T12:04:19Z
python -m vllm.entrypoints.openai.api_server --model hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4 --max_model_len 16000 --gpu-memory-utilization 0.98 --dtype=half  --enforce-eager --quantization awq --swap-space 4 --disable-log-requests --trust-remote-code --enable-prefix-caching --use-v2-block-manager

## comment @jon-chuang 2024-08-08T08:27:51Z
> We are working on multiple optimizations that can accelerate prefill for long context workloads. 

@Ying1123 could you share a bit on how you intend to improve the prefill or even chunked prefill performance?

Is one for instance by using FA3?

## comment @zhyncs 2024-08-08T08:32:59Z
We will not share many details for now. I suggest you switch the LLM inference engine to SGLang and stay tuned.

## comment @mory91 2024-08-10T00:03:58Z
> SGLang currently mostly accelerates the decoding, so what you observed is expected. We are working on multiple optimizations that can accelerate prefill for long context workloads. Some of them should be ready soon. We will let you know when it is ready!

I was reading the paper and wanted to dig deeper to the roots of performance superiority of SGLang to vLLM. The paper (In section 6.2) mentions that the prefill time is expected to improve. Or maybe I'm missing something here. Could you please elaborate a little bit?


## comment @github-actions[bot] 2024-10-09T01:10:59Z
This issue has been automatically closed due to inactivity. Please feel free to reopen it if needed.

## comment @rj-linqingxu 2024-11-07T06:35:31Z
TTFT latency for long context(10k) ,batch_size=8, mean TTFT: 3496.12ms；
sglang 0.3.5 GPU is Radeon RX 7900xtx
![image](https://github.com/user-attachments/assets/73911ba4-6e82-4ebc-b902-6c4185f988b1)
batch_size=16， mean TTFT: 12495.6ms
![image](https://github.com/user-attachments/assets/c63e0a6a-d011-4535-809c-6c35769b3bc0)

