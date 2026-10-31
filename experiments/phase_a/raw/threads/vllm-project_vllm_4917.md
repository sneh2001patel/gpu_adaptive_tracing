# vllm-project/vllm#4917: [Performance]: Automatic Prefix Caching in multi-turn conversations
state=closed reason=completed created=2024-05-20T10:52:38Z closed=2024-05-23T18:09:28Z labels=['performance']
cross-referenced PRs: none

## body (@hmellor)
I'm interested in the automatic prefix caching feature for multi-turn conversations but I can't seem to observe a performance improvement when prefix caching is enabled. [This tweet](https://x.com/vllm_project/status/1776283245665304929/photo/1) from @vllm_project indicates that automatic prefix caching should benefit this use case.

I am using the following commands to start the vLLM server:

```console
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf --port 7001 --gpu-memory-utilization 0.5 --disable-log-requests --enforce-eager

python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf --port 7001 --gpu-memory-utilization 0.5 --disable-log-requests --enforce-eager --enable-prefix-caching
```

And the following script to simulate a multi turn conversation from a user:

```python
import time
from openai import OpenAI

user_messages = [
    "Tell me your ten favourite films",
    "Who directed each of these films?",
    "Which director has the most experience?",
    "What other films has this director directed?",
    "Do these films have anything in common?",
    "Which of those films is the oldest?",
    "How old was the director when this was released?",
[... 17 lines truncated ...]
print(f"{stop - start = }")
```

With automatic prefix caching disabled I see:

```console
$ python test.py 
CompletionUsage(completion_tokens=598, prompt_tokens=16, total_tokens=614)
CompletionUsage(completion_tokens=238, prompt_tokens=629, total_tokens=867)
CompletionUsage(completion_tokens=321, prompt_tokens=882, total_tokens=1203)
CompletionUsage(completion_tokens=465, prompt_tokens=1219, total_tokens=1684)
CompletionUsage(completion_tokens=446, prompt_tokens=1700, total_tokens=2146)
CompletionUsage(completion_tokens=212, prompt_tokens=2162, total_tokens=2374)
CompletionUsage(completion_tokens=58, prompt_tokens=2393, total_tokens=2451)
stop - start = 35.292656753677875
```

And with automatic prefix caching enabled I see:

```console
$ python test.py 
CompletionUsage(completion_tokens=598, prompt_tokens=16, total_tokens=614)
CompletionUsage(completion_tokens=238, prompt_tokens=629, total_tokens=867)
CompletionUsage(completion_tokens=321, prompt_tokens=882, total_tokens=1203)
CompletionUsage(completion_tokens=468, prompt_tokens=1219, total_tokens=1687)
CompletionUsage(completion_tokens=459, prompt_tokens=1703, total_tokens=2162)
CompletionUsage(completion_tokens=197, prompt_tokens=2178, total_tokens=2375)
CompletionUsage(completion_tokens=60, prompt_tokens=2394, total_tokens=2454)
stop - start = 35.605276009999216
```

Is this expected?

## comment @hmellor 2024-05-20T10:53:51Z
CC @robertgshaw2-neuralmagic (the tweet said the feature was added by Neural Magic, so you might have some insight into this feature)

## comment @robertgshaw2-redhat 2024-05-20T14:00:59Z
Will take a look at this case

## comment @comaniac 2024-05-20T20:31:47Z
I'm also interested in this issue so I benchmarked today using the latest main branch, which already uses flash-attn kernel for prefix caching. But even I've verified cache hit in prefix cache, I also found no speedup by running the above script. I'll also investigate a bit.

## comment @robertgshaw2-redhat 2024-05-20T20:37:05Z
cc @SageMoore fyi

## comment @robertgshaw2-redhat 2024-05-20T21:01:20Z
I am not sure what GPU this is, but on an A100, we can do ~15000 prefill tokens/sec at fp16. So even a 2000 token prefill should only take 0.13 seconds to process. Since APC skips prefill computation, there are only 0.5s worth of time that can be optimized in this case. As a result, I would not really expect to see a speedup in this case (+ in fact there is some overhead associated with managing another layer of indirection)

APC really is useful for cases with long shared prefills and short decodes, such as:
  - Shared system prompt
  - Few shot prompting



## comment @comaniac 2024-05-20T21:41:00Z
Thanks for the good hint. I instead let the script report the latency of every request instead of the total time, and here are the results on L4 GPU:

w/o APC
```
stop - start = 28.363408592998894
CompletionUsage(completion_tokens=453, prompt_tokens=16, total_tokens=469)
stop - start = 13.253794727999775
CompletionUsage(completion_tokens=211, prompt_tokens=485, total_tokens=696)
stop - start = 15.47434264399999
CompletionUsage(completion_tokens=245, prompt_tokens=712, total_tokens=957)
stop - start = 22.77607062900279
CompletionUsage(completion_tokens=357, prompt_tokens=974, total_tokens=1331)
stop - start = 25.096272947001125
CompletionUsage(completion_tokens=392, prompt_tokens=1348, total_tokens=1740)
stop - start = 2.3558405980002135
[... 1 lines truncated ...]
CompletionUsage(completion_tokens=37, prompt_tokens=1806, total_tokens=1843)
```

w. APC
```
stop - start = 28.40403065999999
CompletionUsage(completion_tokens=453, prompt_tokens=16, total_tokens=469)
stop - start = 13.463971014996787
CompletionUsage(completion_tokens=211, prompt_tokens=485, total_tokens=696)
stop - start = 15.43624263699894
CompletionUsage(completion_tokens=245, prompt_tokens=712, total_tokens=957)
stop - start = 22.343338724000205
CompletionUsage(completion_tokens=355, prompt_tokens=974, total_tokens=1329)
stop - start = 25.549687523998728
CompletionUsage(completion_tokens=403, prompt_tokens=1346, total_tokens=1749)
stop - start = 1.933658195001044
[... 1 lines truncated ...]
CompletionUsage(completion_tokens=37, prompt_tokens=1815, total_tokens=1852)
```

It seems align to what you analyzed.


## comment @hmellor 2024-05-20T22:17:40Z
> I am not sure what GPU this is

My results came from A100 40GB with `--gpu-memory-utilization 0.5` and `--enforce-eager` (both of which would make my experiments slower).

> there are only 0.5s worth of time that can be optimized in this case

Ok, so it's simply a case of my test not being suitable. If I was running a model with a more expensive prefill (i.e. bigger than 7B) and with longer prompts, I'd start to be able to observe the difference in a single conversation (albeit a subtle difference). 

Presumably there is also a concurrency benefit too, because the slot that would have been scheduled to execute the cached prefill can be used to process the prefill (or decoding) of a different request?


## comment @KuntaiDu 2024-05-21T00:09:39Z
The key thing for automatic prefix caching to have a sizable improvement is that the ratio between input token length and output token length should be VERY VERY large (ideally more than 100x difference).

This is a very strong workload requirement, and such type of workload only commonly occurs in specific applications (e.g. asking questions to a very long software manual).

## comment @hmellor 2024-05-23T17:51:33Z
I ran a better test and have an interesting graph:

![image](https://github.com/vllm-project/vllm/assets/19981378/da750d6a-4311-4205-9e61-a1936cf72fff)

Regardless of first prompt size, there seems to be a large fixed cost on turn 1 (i.e. the second turn), but not the subsequent turns. 

@SageMoore:
- Have you seen this while developing the feature?
- Do you know where in the `PrefixCachingBlockAllocator` this comes from?


## comment @robertgshaw2-redhat 2024-05-23T17:54:21Z
@hmellor - this is caused by Triton jitting. The first time the server runs the context_fwd_attention, Triton jits which slows us down. Have been meaning to finish off a PR that runs the JITing durin profiling, but has become lower priority since if you use latest main with flash attention this issue is resolved b/c it uses the flash attn kernels rather than triton for context_fwd_attn

## comment @robertgshaw2-redhat 2024-05-23T17:56:53Z
note: this will happen once per instantiation of the server

## comment @hmellor 2024-05-23T18:05:42Z
> if you use latest main with flash attention this issue is resolved

Is that the flash attention from the "`pip install vllm-flash-attn` for better performance." info log I've seen?

## comment @comaniac 2024-05-23T18:08:02Z
Yes. You can just pip install vllm-flash-attn and make sure seeing the log `Using FlashAttention-2` when launching the server.

## comment @robertgshaw2-redhat 2024-05-23T18:08:03Z
I think its now installed automatically

https://github.com/vllm-project/vllm/blob/main/setup.py#L356

## comment @hmellor 2024-05-23T18:09:28Z
Ok, thanks for clearing that up for me!

## comment @whr819987540 2024-12-03T03:44:54Z
How should we enable APC in the offline chat?

## comment @renjie0 2025-01-04T00:33:20Z
> I'm also interested in this issue so I benchmarked today using the latest main branch, which already uses flash-attn kernel for prefix caching. But even I've verified cache hit in prefix cache, I also found no speedup by running the above script. I'll also investigate a bit.

How do you verify? Is there any stats by default