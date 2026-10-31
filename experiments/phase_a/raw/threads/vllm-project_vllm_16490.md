# vllm-project/vllm#16490: [Performance]: fp8 Online Quantization
state=closed reason=not_planned created=2025-04-11T14:53:02Z closed=2025-08-12T02:25:16Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@diggle001)
### Proposal to improve performance

hello, I saw the following sentence in the official documentation：
```
https://docs.vllm.ai/en/latest/features/quantization/fp8.html
vLLM supports FP8 (8-bit floating point) weight and activation quantization using hardware acceleration on GPUs such as Nvidia H100 and AMD MI300x. Currently, only Hopper and Ada Lovelace GPUs are officially supported for W8A8. Ampere GPUs are supported for W8A16 (weight-only FP8) utilizing Marlin kernels. Quantization of models with FP8 allows for a 2x reduction in model memory requirements and up to a 1.6x improvement in throughput with minimal impact on accuracy.
```
After using fp8 quantization, the throughput becomes 2.6 times that of using bf16？
What model did you test on, what GPU and num did you use, what concurrency was used, and what was the input and output length to achieve this effect? can you give the detail information?



## comment @ghost 2025-04-12T13:38:52Z
it says 1.6x not 2.6x?

## comment @github-actions[bot] 2025-07-13T02:13:40Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-08-12T02:25:16Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!