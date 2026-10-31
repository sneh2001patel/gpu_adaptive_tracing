# vllm-project/vllm#11192: [Performance]: Online serving with Pipeline Parallel
state=closed reason=not_planned created=2024-12-14T02:31:13Z closed=2025-04-14T02:08:46Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@Ltryxcy)
### Proposal to improve performance

_No response_

### Report of performance regression

_No response_

### Misc discussion on performance

Hi, when I run ./benchmarks/benchmark_serving.py on the vLLM backend with the llama-2-7b model on two A40 GPUs connected via an NVLink bridge, using pipeline parallelism, I noticed that the data transfer between the two GPUs doesn't seem to go through NVLink, and the inference throughput significantly drops 
vLLM version:0.6.3.post1

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @github-actions[bot] 2025-03-15T02:00:54Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-04-14T02:08:46Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!