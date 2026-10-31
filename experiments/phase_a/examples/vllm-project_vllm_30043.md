# vllm-project/vllm#30043: [Performance]: big perf loss between 0.11.2 and 0.12.0 on rms_norm
state=closed reason=completed created=2025-12-04T09:34:14Z closed=2025-12-25T13:35:31Z labels=['performance']
cross-referenced PRs: none

## body (@vince62s)
### Proposal to improve performance

_No response_

### Report of performance regression

With this function
from vllm.model_executor.layers.layernorm import RMSNorm

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @robertgshaw2-redhat 2025-12-04T14:42:06Z
Is there a particular model you are looking at?

## comment @vince62s 2025-12-04T14:44:01Z
yes deepseek-ocr

## comment @vince62s 2025-12-23T16:38:09Z
FYI 0.13 did not recover the perf loss. Saw some other similar post with MoE models.

## comment @vince62s 2025-12-23T17:11:09Z
ok my bad, it was not coming from moe but from rms_norm.

Here is a test script:
```
import torch
import time
import numpy as np
from vllm.model_executor.layers.layernorm import RMSNorm

def benchmark_rmsnorm(hidden_size, batch_size, seq_len, num_warmup=10, num_iterations=1000):
    """Benchmark RMSNorm layer performance."""
    
    # Initialize RMSNorm layer
    rms_norm = RMSNorm(hidden_size).cuda()
    rms_norm = rms_norm.half()  # Convert weights to fp16
[... 82 lines truncated ...]
    main()
```

Results with vllm=0.11.2

```
============================================================
vLLM RMSNorm Performance Benchmark
============================================================

Configuration: {'hidden_size': 4096, 'batch_size': 1, 'seq_len': 128}
------------------------------------------------------------
WARNING 12-23 18:06:42 [vllm.py:1135] Current vLLM config is not set.
INFO 12-23 18:06:42 [scheduler.py:216] Chunked prefill is enabled with max_num_batched_tokens=2048.
Running 10 warmup iterations...
Running 1000 benchmark iterations...
Mean:   0.0199 ms
[... 63 lines truncated ...]
BS=8, SL=512, HS=8192          0.1032       0.1074      
```


results with vllm=0.12.0
```
============================================================
vLLM RMSNorm Performance Benchmark
============================================================

Configuration: {'hidden_size': 4096, 'batch_size': 1, 'seq_len': 128}
------------------------------------------------------------
WARNING 12-23 18:08:34 [vllm.py:1322] Current vLLM config is not set.
INFO 12-23 18:08:35 [scheduler.py:228] Chunked prefill is enabled with max_num_batched_tokens=2048.
Running 10 warmup iterations...
Running 1000 benchmark iterations...
Mean:   0.0755 ms
[... 63 lines truncated ...]
BS=8, SL=512, HS=8192          0.7606       0.7767     
```

big big gap.