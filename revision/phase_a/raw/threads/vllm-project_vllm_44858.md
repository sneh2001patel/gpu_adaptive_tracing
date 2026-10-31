# vllm-project/vllm#44858: [Performance]: After enabling MTP on the Qwen3.5-27B model, the number of hit blocks for the prefix cache is one less compared to the scenario with MTP disabled. This is the current implementation. Can we optimize this behavior?
state=closed reason=not_planned created=2026-06-08T09:32:07Z closed=2026-10-07T01:57:09Z labels=['performance', 'stale']
cross-referenced PRs: ['https://github.com/ai-dynamo/dynamo/pull/11558', 'https://github.com/vllm-project/vllm/pull/44986']

## body (@fanshuxue-hw)
### Proposal to improve performance

1. Environment：
vLLM version：0.19.1
Model：Qwen3.5/3.6-27B

2. Test case：
input 2000 tokens（prefix repeated 80%），output 500 tokens

3. Test result：
xxx（TP = 4） attention block size 1536    prefix cache 0%

4.Optimization Proposals
(1). MTP runs primarily in the decode phase rather than the prefill phase. Given this, why does the prefix cache still need to reserve an extra block for MTP?
(2). Could we add a new parameter to the invocation of find_longest_cache_hit() in kv_cache_manager.py? When a request is in the prefill phase, skip popping the last block to retain full prefix cache hits.

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

## comment @github-actions[bot] 2026-09-07T01:46:16Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2026-10-07T01:57:08Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!