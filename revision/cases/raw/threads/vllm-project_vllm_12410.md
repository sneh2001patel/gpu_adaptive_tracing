# vllm-project/vllm#12410: [Bug]: Performance regression when use PyTorch regional compilation
state=closed reason=completed created=2025-01-24T15:10:46Z closed=2025-02-05T21:24:27Z labels=['bug']
cross-referenced PRs: ['https://github.com/HabanaAI/vllm-fork/pull/740', 'https://github.com/HabanaAI/vllm-fork/pull/745', 'https://github.com/vllm-project/vllm/pull/12536']

## body (@anko-intel)
### Your current environment

<details>
<summary>Run on hpu backend  on version from  https://github.com/HabanaAI/vllm-fork </summary>

```text
INFO 01-24 15:38:37 __init__.py:188] Automatically detected platform hpu.
Collecting environment information...
PyTorch version: 2.5.1a0+git354fc07
Is debug build: False
CUDA used to build PyTorch: None
ROCM used to build PyTorch: N/A

OS: Ubuntu 22.04.5 LTS (x86_64)
GCC version: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0
Clang version: Could not collect
CMake version: version 3.22.1
[... 80 lines truncated ...]

```

</details>


### Model Input Dumps

_No response_

### 🐛 Describe the bug

Performance regression occurs when use regional compilation after https://github.com/vllm-project/vllm/pull/11967

When run :
```
 python -u benchmarks/benchmark_throughput.py \
                                --model /path_to_model/Llama-2-7b-hf \
                                --device hpu \
                                --seed 2024 \
                                --backend vllm \
                                --dataset /path_to_dataset/ShareGPT_V3_unfiltered_cleaned_split.json \
                                --num-prompts 1000 \
                                --dtype bfloat16 \
                                --max-model-len 4096 \
                                --max-num-batched-tokens 8192 \
                                --max-num-seqs 128 \
                                --use-padding-aware-scheduling
```

The [regional compilation](https://pytorch.org/tutorials/recipes/regional_compilation.html) is used in [the code](https://github.com/HabanaAI/vllm-fork/blob/1b8b69e7b302857549ee95d34c0593bd675a71fd/vllm/worker/hpu_model_runner.py#L227C2-L258C37)  I observe big throughput degradation due to recompilation happened  due to indexing in attention layer:

```
torch/_dynamo/guards.py:2813] [1/4] [__recompiles] Recompiling function forward in /software/users/akotlowski/vllm-fork/vllm/model_executor/models/llama.py:267
torch/_dynamo/guards.py:2813] [1/4] [__recompiles]     triggered by the following guard failure(s):
torch/_dynamo/guards.py:2813] [1/4] [__recompiles]     - 1/3: L['self']._modules['self_attn']._modules['attn'].layer_name == 'model.layers.3.self_attn.attn'  # self = forward_context.attn_layers[layer_name]  # oftware/users/akotlowski/vllm-fork/vllm/attention/layer.py:244 in unified_attention
torch/_dynamo/guards.py:2813] [1/4] [__recompiles]     - 1/2: L['self']._modules['self_attn']._modules['attn'].layer_name == 'model.layers.2.self_attn.attn'  # self = forward_context.attn_layers[layer_name]  # oftware/users/akotlowski/vllm-fork/vllm/attention/layer.py:244 in unified_attention
torch/_dynamo/guards.py:2813] [1/4] [__recompiles]     - 1/1: L['self']._modules['self_attn']._modules['attn'].layer_name == 'model.layers.1.self_attn.attn'  # self = forward_context.attn_layers[layer_name]  # oftware/users/akotlowski/vllm-fork/vllm/attention/layer.py:244 in unified_attention
torch/_dynamo/guards.py:2813] [1/4] [__recompiles]     - 1/0: L['self']._modules['self_attn']._modules['attn'].layer_name == 'model.layers.0.self_attn.attn'  # self = forward_context.attn_layers[layer_name]  # oftware/users/akotlowski/vllm-fork/vllm/attention/layer.py:244 in unified_attention
```
https://github.com/vllm-project/vllm/blob/e784c6b9984e8f8116f74000b863d941495acb0b/vllm/attention/layer.py#L268

When we partially revert  the change https://github.com/vllm-project/vllm/pull/11967, dynamo compilation treats  layers as the same, which originally bring performance boost and reduce time of compilation.

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @bsochack 2025-01-28T14:00:59Z
It looks like TorchDynamo is guarding on the layer name. I assume it has performance impact on torch.compile with regional compilation but it can also impact performance of the whole model compilation.
@heheda12345 would you be able to advice how to resolve this issue correctly?