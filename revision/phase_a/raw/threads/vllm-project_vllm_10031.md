# vllm-project/vllm#10031: [Performance]: latency of medusa is longer than naive inferece even the concurreny =2
state=closed reason=not_planned created=2024-11-05T08:27:03Z closed=2025-03-06T02:02:28Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@IvanDeng0)
### Proposal to improve performance

_No response_

### Report of performance regression

I compared the performance of the Medusa method and the naive method on a dataset containing 100 prompts and found that even when the concurrency was set to 2, the performance of the Medusa method was worse than that of naive inference. 

The detailed results (average) are shown in below, the draft acceptance rate is around 50% (reported by the vllm log), I understand that Medusa's performance may be affected when the concurrency is high, however, the performance drop is too significant.

hardware: single A100 40GB
model: Qwen2-1.5B
deploy script:
`export CUDA_VISIBLE_DEVICES=0
vllm serve /mnt/model/Qwen2-1.5B-Instruct \
    --host 0.0.0.0 \
    --trust-remote-code \
    --max-model-len 32768 \
    --port=7802 \
    --disable-log-requests \
    --tensor-parallel-size 1 \
    --speculative-model /mnt/model/exp2_Qwen2_Medusa_3_head_32_weight_2_4096/_medusa_mlp_Qwen2-1.5B-Instruct_medusa_3_lr_0.0001_layers_2/converted \
    --speculative-draft-tensor-parallel-size 1 \
    --num-speculative-tokens 1 \
    --use-v2-block-manager \`

| Concurrency | Naive(s) | Medusa(s) |
|----------|----------|----------|
| 1  | 785  | 577  |
| 2  | 335  | 367  |
| 3  | 268  | 291  |
| 4  | 226  | 263  |
| 5  | 220  | 268  |

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

vllm 0.5.4


### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @github-actions[bot] 2025-02-04T01:57:34Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-03-06T02:02:28Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!