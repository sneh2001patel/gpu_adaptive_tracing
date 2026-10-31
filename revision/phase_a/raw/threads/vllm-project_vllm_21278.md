# vllm-project/vllm#21278: [Performance]: Speculative decoding doesn't seem to speed up inference?
state=closed reason=not_planned created=2025-07-21T03:53:40Z closed=2026-03-15T02:18:54Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@la1ty)
### Proposal to improve performance

I want to improve the inference speed of Qwen3-32B-FP8 on NVIDIA L20. Currently, the inference speed is as follows:

- Single card: 13-14 tokens/s
- Dual cards: 20-21 tokens/s

So I try VLLM's speculative decoding with Qwen3's small sized models, executing a command like this:

```
python -m vllm.entrypoints.openai.api_server   --host 0.0.0.0     --port 9997     --model "/path/to/Qwen3-32B-FP8/" --served-model-name qwen3  --seed 42     --max-model-len 10240     -tp 2     --speculative_config '{"model": "/path/to/Qwen3-4B-FP8/", "max_model_len": 10240, "num_speculative_tokens": 3}' 
```

But it turns out that it leads to a slower inference speed (around 10-11 tokens/s). I don't know if it's normal.

By the way, I would appreciate it if you have any other suggestions for improving this model's inference speed...

### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
==============================
        System Info
==============================
OS                           : Ubuntu 24.04.2 LTS (x86_64)
GCC version                  : (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0
Clang version                : Could not collect
CMake version                : Could not collect
Libc version                 : glibc-2.39

==============================
       PyTorch Info
[... 175 lines truncated ...]
CUDA_MODULE_LOADING=LAZY
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @LiYomi 2025-07-21T07:10:07Z
Same question here—I also didn’t see any performance improvement using n-gram-based speculative decoding.

## comment @fangpin 2025-07-21T07:32:15Z
have you ever tried other value except 3 for 'num_speculative_tokens', maybe there's better value. And you can also try the AWQ version model.

## comment @la1ty 2025-07-21T08:20:26Z
> have you ever tried other value except 3 for 'num_speculative_tokens', maybe there's better value. And you can also try the AWQ version model.

I've tested it with a few combinations of draft models and `num_speculative_tokens`. However, none of them show any acceleration:

| Draft Model | num_speculative_tokens | Inference Speed |
| ------------ | --------------------------- | ------------------- |
| Qwen3-4B | 3 | 10-11 tokens/s |
| Qwen3-4B | 5 | 8-9 tokens/s |
| Qwen3-4B | 10 | 4-5 tokens/s |
| Qwen3-1.7B | 3 | 11-12 tokens/s |
| Qwen3-1.7B | 5 | 9-10 tokens/s |
| Qwen3-1.7B | 10 | 7-8 tokens/s |
| Qwen3-0.6B | 3 | 12-13 tokens/s |
| Qwen3-0.6B | 5 | 11-12 tokens/s |
| Qwen3-0.6B | 10 | 9-10 tokens/s |

## comment @gerayking 2025-07-21T09:42:19Z
Meet the same problem on qwen3 models， GPU H20.

## comment @la1ty 2025-07-21T12:28:25Z
Probably bad news: I also tried SGLang's Eagle-3 speculative decoding with [AngelSlim/Qwen3-32B_eagle3](https://huggingface.co/AngelSlim/Qwen3-32B_eagle3), still without any acceleration (18-19 tokens/s). 

## comment @gerayking 2025-07-21T13:07:50Z
> Probably bad news: I also tried SGLang's Eagle-3 speculative decoding with [AngelSlim/Qwen3-32B_eagle3](https://huggingface.co/AngelSlim/Qwen3-32B_eagle3), still without any acceleration (18-19 tokens/s).

Are you using Chinese datasets? Perhaps their acceptance rate is not very good.

## comment @gerayking 2025-07-22T03:46:50Z
> > have you ever tried other value except 3 for 'num_speculative_tokens', maybe there's better value. And you can also try the AWQ version model.
> 
> I've tested it with a few combinations of draft models and `num_speculative_tokens`. However, none of them show any acceleration:
> 
> Draft Model	num_speculative_tokens	Inference Speed
> Qwen3-4B	3	10-11 tokens/s
> Qwen3-4B	5	8-9 tokens/s
> Qwen3-4B	10	4-5 tokens/s
> Qwen3-1.7B	3	11-12 tokens/s
> Qwen3-1.7B	5	9-10 tokens/s
> Qwen3-1.7B	10	7-8 tokens/s
> Qwen3-0.6B	3	12-13 tokens/s
> Qwen3-0.6B	5	11-12 tokens/s
> Qwen3-0.6B	10	9-10 tokens/s

I found that v1 does not support speculative decoding. Therefore, the code used with speculative decoding is vllm-v0. It is possible that this is the reason why there is no performance gain. I recommend using the vllm-v0 version as the baseline.

## comment @la1ty 2025-07-22T03:51:11Z
> Are you using Chinese datasets? Perhaps their acceptance rate is not very good.

Yes.

I asked Deepseek why speculative decoding is slower than normal inference, and DeepSeek said that the inference time for speculative decoding consists of four parts: the sampling time of the draft model, the transfer time of the sampling results of the draft model to the main model, the verification time of the main model, and the calculation time of resampling. 

I suspect the transfer time is the culprit, which may require optimization at the hardware level and beyond my capabilities. 

## comment @la1ty 2025-07-22T05:30:28Z
> I found that v1 does not support speculative decoding. Therefore, the code used with speculative decoding is vllm-v0. It is possible that this is the reason why there is no performance gain. I recommend using the vllm-v0 version as the baseline.

The baseline performance using vllm-v0 is similar:

- Single card: 13-14 tokens/s
- Dual cards: 18-19 tokens/s (slower than v1)

## comment @la1ty 2025-07-22T06:30:22Z
I noticed that the metric in #13933 used a low temperature (0/0.1). When I tried setting the temperature to 0.001 with SGLang Eagle3 speculative decoding, it did achieve a small improvement in inference speed...

Alright, I give up. 😿 

## comment @GGKOP 2025-07-22T06:45:42Z
same problem

## comment @hongyanz 2025-07-27T15:35:35Z
You can turn on the draft tree to increase the acceptance rate. According to https://huggingface.co/AngelSlim/Qwen3-32B_eagle3, there should have been 2.63x speedup for T=0.

## comment @gerayking 2025-07-27T17:43:44Z
> You can turn on the draft tree to increase the acceptance rate. According to https://huggingface.co/AngelSlim/Qwen3-32B_eagle3, there should have been 2.63x speedup for T=0.

Currently, vLLM Qwen3 does not support Eagle3. Do you have any solutions for this?

## comment @wenqf11 2025-08-25T10:57:38Z
> You can turn on the draft tree to increase the acceptance rate. According to https://huggingface.co/AngelSlim/Qwen3-32B_eagle3, there should have been 2.63x speedup for T=0.

@hongyanz so how to turn on this draft tree? 

## comment @Zengwh02 2025-11-14T08:49:34Z
same problem

## comment @github-actions[bot] 2026-02-13T02:17:44Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2026-03-15T02:18:54Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!