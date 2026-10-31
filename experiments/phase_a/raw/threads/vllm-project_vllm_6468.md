# vllm-project/vllm#6468: [Performance]: [Speculative Decoding] Measurement of Cost Coefficient through vLLM
state=closed reason=completed created=2024-07-16T08:53:51Z closed=2024-07-17T00:42:05Z labels=['performance']
cross-referenced PRs: none

## body (@bong-furiosa)
### Proposal to improve performance

Recently, vLLM has been conducting a lot of work related to Speculative Decoding, and we often see remarkable achievements.

For the Speculative Decoding algorithm to achieve maximum efficiency, it is important to consider not only the performance of the draft and target models but also the **speed of each model**.

According to the Definition 3.7 from [original Speculative Decoding paper](https://arxiv.org/pdf/2211.17192), the latency ratio between the target model  and the draft model is referred to as the Cost Coefficient `c`. And it is assumed that the `c` value is very small.

🤔 **However, when I examined the vLLM github repo as far as I can, I could not find any information related to the Cost Coefficient.**

I have attempted various methods to obtain the Cost Coefficient value for each model on my own. For example:
```
VLLM_ATTENTION_BACKEND=FLASH_ATTN nsys profile -t cuda,nvtx,osrt,cudnn,cublas -o llama_7b_nsight_report ./venv/bin/python3 ./benchmarks/benchmark_latency.py --model NousResearch/Llama-2-7b-hf --enforce-eager --input-len 128 --output-len 2 --batch-size 1 --num-iters-warmup 5 --num-iters 5
VLLM_ATTENTION_BACKEND=FLASH_ATTN nsys profile -t cuda,nvtx,osrt,cudnn,cublas -o llama_1.1b_nsight_report ./venv/bin/python3 ./benchmarks/benchmark_latency.py --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --enforce-eager  --input-len 128 --output-len 2 --batch-size 1 --num-iters-warmup 5 --num-iters 5
VLLM_ATTENTION_BACKEND=FLASH_ATTN nsys profile -t cuda,nvtx,osrt,cudnn,cublas -o llama_160m_nsight_report ./venv/bin/python3 ./benchmarks/benchmark_latency.py --model JackFram/llama-160m --enforce-eager  --input-len 128 --output-len 2 --batch-size 1 --num-iters-warmup 5 --num-iters 5
VLLM_ATTENTION_BACKEND=FLASH_ATTN nsys profile -t cuda,nvtx,osrt,cudnn,cublas -o llama_68m_nsight_report ./venv/bin/python3 ./benchmarks/benchmark_latency.py --model JackFram/llama-68m --enforce-eager  --input-len 128 --output-len 2 --batch-size 1 --num-iters-warmup 5 --num-iters 5
```
Additionally, I used `NVTX` to mark the model running part. Below is the modified part of `model_runner.py`
```
torch.cuda.nvtx.range_push("model_executable()")
hidden_or_intermediate_states = model_executable(
    input_ids=model_input.input_tokens,
    positions=model_input.input_positions,
    kv_caches=kv_caches,
    attn_metadata=model_input.attn_metadata,
    intermediate_tensors=intermediate_tensors,
    **multi_modal_kwargs,
    **seqlen_agnostic_kwargs)
torch.cuda.nvtx.range_pop()
```
(I will upload the profile image for LLaMA-68 only.)
![image](https://github.com/user-attachments/assets/0b9bf096-536d-4831-93ed-1206c5f4a2f7)

🤔 Here is the profile results obtained using Nsight System.
| Model     | Profiled Time (ms) | Cost Coefficient |
|-----------|---------------------------|--------------|
| LLaMA 7B  | 16.607                      | 1.00 |
| LLaMA 1.1B| 11.427                       | 0.68 |
| LLaMA 160M| 5.635                       | 0.33 |
| LLaMA 68M | 1.099                       | 0.06 |

**One of the most notable point here is that, when comparing LLaMA-7B and LLaMA-160m, the Cost Coefficient was measured to be 0.33.** I assume that this result suggests that when applying Speculative Decoding with the combination of these two models, the efficient range of `num_speculative_tokens` is constrained to approximately 3 or 4.

In the original Speculative Decoding paper and the recently published paper ([Online Speculaitve Decoding](https://arxiv.org/pdf/2310.07177)), the Cost Coefficient is used at a much smaller value, around 0.05 or 0.13.

**Therefore, I am curious if vLLM has considered such Cost Coefficients when implementing Speculative Decoding, or if it is something that can be disregarded during the vLLM Speculative Decoding serving. Additionally, I would kike to know if the measurement process I did was correct!** 🙏 

### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


## comment @keyboardAnt 2024-07-16T17:09:04Z
Speculative decoding [might](https://arxiv.org/pdf/2405.14105) be slower than non-speculative if the drafter model is too slow or inaccurate. Using a simple simulation, we get the following heatmap:
![image](https://github.com/user-attachments/assets/2414efa1-b354-4bc4-8723-66dd9c7a3c07)
(SI over non-SI. Pink marks slowdowns)

The [distributed](https://arxiv.org/pdf/2405.14105) variation of the algorithm avoids slowdowns. It is always faster than the non-distributed version:
![image](https://github.com/user-attachments/assets/541997f3-ea83-4f17-bcc9-b8df432644d6)
(DSI speedups over SI)

For a drafter latency of 68% (as you mentioned for LLaMa 1.1B), DSI offers up to 1.8x speedup compared to SI. The heatmap also shows that DSI’s speedup increases as the acceptance rate decreases.

DSI is not yet supported in vLLM though. 🥲

## comment @comaniac 2024-07-16T19:11:13Z
@bong-furiosa the cost coefficient is more like a configuration by users, meaning that you could refer to this criteria when selecting the draft model. vLLM just executes whatever you configured, because it cannot select the draft model for you, after all.

For your measurement, although this doesn't include other system overheads such as scheduling and sampling, I'd say it's generally ok, because @cadedaniel is leading community efforts to resolve such overheads as possible. Please keep an eye on related updates on issues and PRs and you would see obvious improvements over time.

## comment @bong-furiosa 2024-07-17T00:42:06Z
Hello @keyboardAnt ! I have read your DSI paper before (also DISCO, recently). At that time, I didn't pay close attention to it because I wasn't considering Specuding Decoding. It's happy to be reminded of your paper and to meet the author.
The table you provided from the paper seems like it will be a great reference when using Speculative Decoding in vLLM!

@comaniac, Thank you for understanding my interest in the Cost Coefficient values for Speculative Decoding in vLLM!
Indeed, through PRs and ISSUEs, I have observed that many experts, including @cadedaniel, are making efforts to reduce serving overhead during Speculative Decoding. I will keep looking forward to seeing further improvements in vLLM.

Since I received excellent response to this ISSUE, I will close it.

## comment @cadedaniel 2024-07-17T20:45:54Z
By the way, it would be great to measure the cost coefficient in vLLM and report it in the metrics. I can direct you to the relevant code sections if that interests you.

## comment @bong-furiosa 2024-07-18T02:13:39Z
Hello @cadedaniel !
Thank you for understanding my interest in the Cost Coefficient impact on the vLLM serving system. 🙇 
I have reached out to you via email regarding this concern.
I would appreciate it if you could check it.
