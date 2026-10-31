# vllm-project/vllm#21029: [Performance]: Why the support for Mamba2 in vLLM v1 appears to be less optimized than in v0, leading to a obvious performance drop?
state=closed reason=completed created=2025-07-16T03:21:02Z closed=2025-07-16T07:15:08Z labels=['performance']
cross-referenced PRs: none

## body (@NhStudy2025)
### Proposal to improve performance

_No response_

### Report of performance regression




### Misc discussion on performance

V0:
Total runtime: 29.66 seconds
Total tokens (input + output): 65543
Batches completed: 10
TPS (Tokens per second): 2209.84

V1:
Total runtime: 59.68 seconds
Total tokens (input + output): 65934
Batches completed: 10
TPS (Tokens per second): 1104.71

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @DarkLight1337 2025-07-16T04:16:49Z
cc @tdoublep @tlrmchlsmth 

## comment @tdoublep 2025-07-16T04:34:09Z
It's because we don't yet have CUDA graphs working for mamba in V1 yet. I am working on this at the moment. It is high priority for us. 

## comment @NhStudy2025 2025-07-16T07:12:00Z
Got it, thanks!

## comment @tdoublep 2025-07-18T19:54:42Z
@NhStudy2025 PR is up now which removes the requirement to use eager mode: https://github.com/vllm-project/vllm/pull/21194