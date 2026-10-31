# vllm-project/vllm PR #51453: [Performance] Register Triton W4A16 GEMM as a custom op
merged_at=2026-09-02T03:55:35Z merge_commit=ee3c00bbf47e0ef7e975705cc980b06ee5576bb0 author=@giuseppegrossi
files: tests/kernels/quantization/test_triton_w4a16.py, vllm/model_executor/kernels/linear/mixed_precision/triton_w4a16.py

## body
## Summary

Register the Triton W4A16 GEMM as an opaque custom op with a fake implementation similar to how `rdna_hybrid_w4a16.py` does it.

Without this boundary, `torch.compile` traces the Python tile-selection logic and freezes the prefill configuration for decode workloads. The custom op ensures tile selection runs with the actual runtime shape.

This fixes #49699.

## Test Plan

```bash
pytest -q \
  tests/kernels/quantization/test_triton_w4a16.py \
  tests/kernels/quantization/test_w4a16_kernel_selection.py \
  tests/kernels/quantization/test_rocm_compressed_tensors_w4a16.py
```


## Results

- 41 relevant tests passed
- GSM8K accuracy was unchanged over 50 samples
- MI300 decode throughput improved +20.8%