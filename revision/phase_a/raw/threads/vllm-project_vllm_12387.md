# vllm-project/vllm#12387: [Performance]: Details about the performance of vLLM on `reasoning models`
state=closed reason=completed created=2025-01-24T05:09:40Z closed=2025-02-01T01:36:20Z labels=['performance']
cross-referenced PRs: none

## body (@shaoyuyoung)
### Proposal to improve performance

just curiously, for open-source reasoning models (e.g., deepseek-r1), does vLLM have a specific part for recording its performance?

In short summary, I mean where can I know the performance of vLLM on reasoning models? Because I think reasoning model will take more time to think step by step. But how much it will take on vLLM?

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

## comment @gaocegege 2025-01-29T04:09:30Z
I believe there is no difference compared to DeepSeek v3. The parameter size remains the same; it simply outputs `<think>...</think>` before the content. The kvcache may impact performance, as each response will first drop the reasoning content and then add it to the prefix text.



## comment @shaoyuyoung 2025-01-29T10:08:16Z
> it simply outputs `<think>...</think>` before the content. The kvcache may impact performance, as each response will first drop the reasoning content and then add it to the prefix text.

That's true in theory, but it would be nice if any experimental results could support this. :)

## comment @hmellor 2025-02-01T01:36:20Z
You can check out our benchmarks here: https://github.com/vllm-project/vllm/tree/main/benchmarks