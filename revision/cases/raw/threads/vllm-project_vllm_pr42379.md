# vllm-project/vllm PR #42379: [Bugfix] Fix RMSNorm kernels to multiply in weight's native dtype
merged_at=2026-05-30T06:16:53Z merge_commit=124fac10cb0ea83aee2ffeabac0b413d6b759b26 author=@liulanze
files: csrc/libtorch_stable/layernorm_kernels.cu, csrc/libtorch_stable/layernorm_quant_kernels.cu

## body
## Purpose

Fix a regression introduced by #40860 (DeepSeek V4 support) where `csrc/layernorm_kernels.cu` was changed to always upcast the RMSNorm weight to `float32` before the final multiplication. The correct behaviour, per the Python spec in `vllm/ir/ops/layernorm.py:20`, is to multiply in the weight's native dtype (BF16/FP16):

```python
x = x.to(weight.dtype) * weight  # multiply in weight.dtype
```

The FP32 weight path introduces ~0.03 per-element error per layer. For models with many Q/K RMSNorm layers (e.g. LLaDA-2, DeepSeek with Q/K norm) this compounds catastrophically — 20-layer cumulative divergence exceeds 100, and only ~2% of output tokens match the reference.

The bug was reproduced locally on an A100-SXM4-40GB before implementing the fix, confirming the reported max diff of ~3e-02. The fix was built from source and verified on the same hardware.

Fixes #42325

## Changes

**`csrc/layernorm_kernels.cu`** — 3 locations:
- `rms_norm_kernel` vectorized path
- `fused_add_rms_norm_kernel` FP16/BF16 optimised path
- `fused_add_rms_norm_kernel` generic scalar fallback

Pattern in each location:
```cpp
// Before (regressed in #40860):
float w = static_cast<float>(weight_elem);
out = static_cast<scalar_t>(x * s_variance * w);

// After (restores v0.19.1 behaviour):
out = static_cast<scalar_t>(x * s_variance) * weight_elem;
```

**`csrc/layernorm_quant_kernels.cu`** — 3 matching locations:
The FP8 quant kernels contain an explicit comment explaining they were designed to match the non-fused composite path (`rms_norm` output → `static_scaled_fp8_quant`). After fixing the non-fused path, the quant kernels require the same update to stay consistent. Without it, `test_fused_rms_norm_quant` fails because the two paths diverge.

## Test Plan

```bash
pytest tests/kernels/core/test_layernorm.py -x -q
pytest tests/kernels/ir/test_layernorm.py -x -q
```

Regression repro script (shows `FIXED` after patch):

```python
import torch
from vllm import _custom_ops as ops

x = torch.randn(48, 128, dtype=torch.bfloat16, device='cuda')
weight = torch.randn(128, dtype=torch.bfloat16, device='cuda')
out = torch.empty_like(x)
ops.rms_norm(out, x, weight, 1e-6)

x_fp32 = x.to(torch.float32)
variance = x_fp32.pow(2).mean(-1, keepdim=True)
x_normed = x_fp32 * torch.rsqrt(variance + 1e-6)
[... 3 lines truncated ...]
print("FIXED" if diff < 0.001 else "BUG CONFIRMED")
```

## Test Result

Reproduced the bug and verified the fix locally on an A100-SXM4-40GB, building vllm from source on this branch:

| | Before (bug reproduced) | After (fix verified) |
|---|---|---|
| `rms_norm` max diff (BF16) | `3.125e-02` ✗ | `0.000e+00` ✓ |
| `fused_add_rms_norm` max diff (BF16) | `3.125e-02` ✗ | `0.000e+00` ✓ |

```
tests/kernels/core/test_layernorm.py: 865 passed
tests/kernels/ir/test_layernorm.py:   1442 passed, 361 skipped
```

---
<details>
<summary> Essential Elements of an Effective PR Description Checklist </summary>

- [x] The purpose of the PR, such as "Fix some issue (link existing issues this PR will resolve)".
- [x] The test plan, such as providing test command.
- [x] The test results, such as pasting the results comparison before and after, or e2e results
- [ ] (Optional) The necessary documentation update, such as updating `supported_models.md` and `examples` for a new model.
</details>

Note summary:

DeepSeek V4 support accidentally changed 6 CUDA kernel sites to upcast weights to float32 before multiplying, deviating from the spec (multiply in weight's native BF16 dtype); tiny per-layer rounding errors compounded across 20+ norm layers until the model output was nearly completely wrong — fixed by restoring the correct cast-then-multiply order.

