# vllm-project/vllm#24169: [Performance]: MoE FP8 and Gemm FP8 for CPU
state=closed reason=not_planned created=2025-09-03T10:20:55Z closed=2026-01-03T02:13:58Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@duanzhui)
### Proposal to improve performance

_No response_

### Report of performance regression

We implemented a single-node vllm inference solution for the DeepSeek-R1 671B model based on a hybrid CPU-GPU architecture, handling some of the expert MoE computation tasks on Xeon Sapphirerapids processors. Since x86 processors do not support FP8 native floating-point computation, we leveraged the ktransformers MoE operator framework to extend the functionality of online conversion of DeepSeek-R1's FP8 weights to BF16 format, seamlessly providing support for the DeepSeek-R1 671B model on Sapphirerapids processors. In July, we discovered that the new version of VLLM also added support for Moe FP8 and Gemm FP8  for cpu. We tested the torch.ops._C.fused_experts_cpu operator based on the DeepSeek-R1 671B model. The test results showed that for input data batch sizes of 1/2/4/8, the average Moe computational latency amortized to per expert and per input tensor for a single model layer was about 45% higher than our implementation. Does anyone know the main reason for the higher computational latency in the Moe FP8 and Gemm FP8 for cpu of the VLLM version?

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @github-actions[bot] 2025-12-04T02:11:54Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2026-01-03T02:13:57Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!