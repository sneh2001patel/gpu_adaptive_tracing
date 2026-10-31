# vllm-project/vllm#14450: [Performance]: LoRA is not taken into account when determining the number of KV cache blocks
state=closed reason=completed created=2025-03-07T17:57:20Z closed=2025-03-08T06:10:39Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/14469']

## body (@chenhongyu2048)
### Proposal to improve performance

I noticed that when LLMengine calls the determine_KV_cache_blocks function, only the GPU memory occupied by the model weight and activation is considered. But when LoRA is enabled, LoRA will also occupy a part of the memory.
In my experiment, using different LoRa Rank and Max LoRas did not affect the number of kv cache blocks which is decided in the profiling, this resullt supported my suspicions.
I'd like to know the reason behind this design, it's a bug? Or does vLLM really not want to take it into account at the moment to avoid wasting memory?

### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @jeejeelee 2025-03-08T02:47:51Z
This is a bug, V1 LoRA should not have this issue.

## comment @chenhongyu2048 2025-03-08T06:10:39Z
Thanks for your contribution!