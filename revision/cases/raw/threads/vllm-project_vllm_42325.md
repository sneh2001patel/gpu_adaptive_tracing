# vllm-project/vllm#42325: [Bug]: RMSNorm kernel ignores weight dtype, always uses FP32 (regression in v0.20.0)
state=closed reason=completed created=2026-05-11T15:14:53Z closed=2026-05-30T06:16:55Z labels=[]
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/42379']

## body (@AlonKellner-RedHat)
### Your current environment

This is a kernel implementation bug affecting all platforms with CUDA. Environment details are not relevant as the issue is in the source code itself (`csrc/layernorm_kernels.cu`).

**Affected versions:** v0.20.0, v0.20.1, v0.20.2, and current main branch  
**Last working version:** v0.19.1

### 🐛 Describe the bug

## Summary

vLLM's RMSNorm CUDA kernel (`csrc/layernorm_kernels.cu`) ignores the weight dtype and always multiplies in FP32, violating the Python reference specification in `vllm/ir/ops/layernorm.py`. This regression was introduced in v0.20.0 (commit 4d51588e23, PR #40860) and affects all subsequent versions including the current main branch.

## Actual Behavior (v0.20.0+)

The kernel casts weight to FP32 and performs multiplication in FP32:

```cpp
// csrc/layernorm_kernels.cu (lines 77-82, v0.20.0+)
#pragma unroll
for (int j = 0; j < VEC_SIZE; j++) {
  float x = static_cast<float>(src1.val[j]);
  float w = static_cast<float>(src2.val[j]);  // ❌ Always FP32
  dst.val[j] = static_cast<scalar_t>(x * s_variance * w);
}
```

## Expected Behavior (Specification)

The Python reference in `vllm/ir/ops/layernorm.py` specifies that multiplication should happen in **weight dtype**, not FP32:

```python
# vllm/ir/ops/layernorm.py (lines 19-21)
if weight is not None:
    x = x.to(weight.dtype) * weight  # ← Multiply in weight.dtype
return x.to(orig_dtype)
```

v0.19.1 and earlier correctly respected the weight dtype:

```cpp
// csrc/layernorm_kernels.cu (lines 77-82, v0.19.1)
#pragma unroll
for (int j = 0; j < VEC_SIZE; j++) {
  float x = static_cast<float>(src1.val[j]);
  dst.val[j] = ((scalar_t)(x * s_variance)) * src2.val[j];  // ✅ Respects weight dtype
}
```

## Version Timeline

| Version | Release Date | Status | Behavior |
|---------|--------------|--------|----------|
| v0.19.1 | April 15, 2026 | ✅ Correct | Respects weight dtype |
| v0.20.0 | April 27, 2026 | ❌ Bug | Always uses FP32 |
| v0.20.1 | May 4, 2026 | ❌ Bug | Always uses FP32 |
| v0.20.2 | May 5, 2026 | ❌ Bug | Always uses FP32 |
| main | Current | ❌ Bug | Always uses FP32 |

## Root Cause

The bug was introduced in commit 4d51588e23 (DeepSeek V4 feature PR #40860, April 26, 2026). This PR added FP8 quantization support and modified both the FP8 quantization kernels and the regular RMSNorm kernels.

**In the FP8 quantization context**, the FP32 multiplication is actually **correct** because the fused kernel must match the precision of the unfused composite operation (RMSNorm → BF16 cast → FP8 quant).

**However**, the same pattern was applied to the **regular RMSNorm kernel** where it's **incorrect** because it violates the specification that multiplication should happen in weight dtype.

This appears to be an unintended side effect rather than a deliberate design change.

## Impact

### Precision Mismatch

When using BF16 weights (the common case for modern LLMs), the kernel:

- **Expected behavior**: Convert normalized values to BF16, multiply in BF16
- **Actual behavior**: Multiply in FP32, then convert to BF16

This causes measurable numerical divergence:

```
Max divergence from reference: ~0.03 to 0.06
```

### Cumulative Effects

For models with RMSNorm in multiple layers (e.g., attention Q/K normalization), the error compounds:

- Single layer: divergence = 0.03
- 20 layers: divergence = 124 (exponential growth)
- Final output match rate: ~2%

This can significantly affect model accuracy, especially for models that rely on precise normalization (e.g., LLaDA2 with Q/K normalization).

## Reproduction

```python
import torch
from vllm import _custom_ops as ops

def reference_rmsnorm(x, weight, eps=1e-6):
    """Reference matching vLLM IR ops spec."""
    orig_dtype = x.dtype
    x_fp32 = x.to(torch.float32)
    variance = x_fp32.pow(2).mean(-1, keepdim=True)
    x_normed = x_fp32 * torch.rsqrt(variance + eps)
    result = x_normed.to(weight.dtype) * weight  # Multiply in weight.dtype
    return result.to(orig_dtype)
[... 12 lines truncated ...]
# v0.20.0+: ~0.03 (bug)
```

**Test results:**

| Version | Max Diff | Status |
|---------|----------|--------|
| v0.19.1 | ~0.0 | ✅ Matches specification |
| v0.20.0 | ~0.03 | ❌ Violates specification |
| v0.20.1 | ~0.03 | ❌ Violates specification |
| v0.20.2 | ~0.03 | ❌ Violates specification |

## Fix

Revert the regular RMSNorm kernel to v0.19.1 behavior:

```diff
// csrc/layernorm_kernels.cu (line ~77-82)
 #pragma unroll
 for (int j = 0; j < VEC_SIZE; j++) {
   float x = static_cast<float>(src1.val[j]);
-  float w = static_cast<float>(src2.val[j]);
-  dst.val[j] = static_cast<scalar_t>(x * s_variance * w);
+  dst.val[j] = ((scalar_t)(x * s_variance)) * src2.val[j];
 }
```

The same fix is needed in `fused_add_rms_norm_kernel` (line ~182):

```diff
 for (int idx = threadIdx.x; idx < hidden_size; idx += blockDim.x) {
   float x = (float)residual[blockIdx.x * hidden_size + idx];
-  float w = (float)weight[idx];
-  input[blockIdx.x * input_stride + idx] = (scalar_t)(x * s_variance * w);
+  input[blockIdx.x * input_stride + idx] = ((scalar_t)(x * s_variance)) * weight[idx];
 }
```

**Important**: Keep the FP32 cast in `layernorm_quant_kernels.cu` — it's correct there for FP8 quantization.

## Additional Context

- **Python reference specification**: [`vllm/ir/ops/layernorm.py`](https://github.com/vllm-project/vllm/blob/main/vllm/ir/ops/layernorm.py#L19-L21)
- **Introducing commit**: [4d51588e23](https://github.com/vllm-project/vllm/commit/4d51588e23) (DeepSeek V4 Rebased #40860, April 26, 2026)
- **Last good release**: v0.19.1 (April 15, 2026)
- **Python IR ops remain correct**: Only the CUDA kernel is affected; the Python reference in `vllm/ir/ops/layernorm.py` correctly follows the specification

This is a regression that breaks the contract between the IR ops specification and the kernel implementation. The fix restores specification compliance without affecting the FP8 quantization features added in v0.20.0.

---

### Before submitting a new issue...

- [x] I have searched for relevant issues, and asked the chatbot at the [documentation page](https://docs.vllm.ai/en/latest/)
- [x] I have tested this bug across multiple vLLM versions (v0.19.1, v0.20.0, v0.20.1) to confirm it's a regression
- [x] I have identified the root cause commit and analyzed the code change

## comment @liulanze 2026-05-12T05:46:28Z
Hi @AlonKellner-RedHat, I reproduced this on an A100-SXM4-40GB (`rms_norm` max diff `3.125e-02`, BUG CONFIRMED). Root cause is PR #40860 which changed `layernorm_kernels.cu` to multiply the weight in `float32` instead of the weight's native dtype, contradicting the Python spec in `vllm/ir/ops/layernorm.py`. The fix restores the v0.19.1 pattern and also updates the matching locations in `layernorm_quant_kernels.cu` to stay consistent. Built from source and verified on the same A100: max diff drops to `0.000e+00`, all 865 + 1442 layernorm tests pass. PR (https://github.com/vllm-project/vllm/pull/42379) is up.

## comment @zyongye 2026-05-30T17:15:44Z
IR python should not be a specification to guide CUDA impl. If it is, then the spec itself is wrong. 