# sgl-project/sglang#38700: [Feature] Fuse shared to sparse experts in DSV4 DeepGEMM MegaMoE
state=closed reason=completed created=2026-09-09T15:13:46Z closed=2026-09-30T01:48:17Z labels=['performance', 'nvidia']
cross-referenced PRs: ['https://github.com/sgl-project/sglang/pull/39296', 'https://github.com/sgl-project/sglang/pull/39313']

## body (@b8zhong)
### Checklist

- [x] If this is not a feature request but a general question, please start a discussion at https://github.com/sgl-project/sglang/discussions. Otherwise, it will be closed.
- [x] Please use English. Otherwise, it will be closed.

### Motivation

Part of https://github.com/sgl-project/sglang/issues/33636

Technically, the approach of https://github.com/sgl-project/sglang/pull/27349 is not the same as the kernel support in https://github.com/deepseek-ai/DeepGEMM/pull/377, it appends the shared expert as one more physical expert slot and increase topK by 1. **Also more importantly,** it doesn't apply to original DSV4 checkpoints at all (`deepseek-ai/DeepSeek-V4-Pro-0813`/`deepseek-ai/DeepSeek-V4-Flash-0731`) as the routed expert is in different precision (blockwise FP8 vs MXFP4), #27349 only supports it in 3rd party checkpoints when the shared expert precision is lowered (or using enforce shared experts fusion).  For more details, we can read the diff of the DeepGEMM PR.

### Related resources

trtllm-gen also has done it: https://github.com/sgl-project/sglang/pull/35505
Latest `sgl-deep-gemm` should already include this PR.

## comment @seongyun1104 2026-09-09T18:58:21Z
@b8zhong I can take this if nobody is already working on it. I reviewed the current MegaMoE path and the shared-weight API in sgl-deep-gemm 0.1.7.

My proposed minimal integration is to keep the original DSV4 shared expert as a separate FP8 MLP during loading, transform its L1/L2 weights for DeepGEMM, size the symmetric buffer with num_shared_experts=1, and pass those weight pairs to fp8_fp4_mega_moe. I would not reuse num_fused_shared_experts, because that field currently means an appended routed slot and changes top-k width plus checkpoint remapping. The standalone shared MLP would be skipped only when the native DeepGEMM shared path is available; other backends keep the existing behavior.

I plan focused CPU contract tests first, then 2x B200 synthetic correctness and the existing 4x B200 DSV4 MegaMoE E2E test. Is this the intended split, and should the validated path remain behind --enforce-shared-experts-fusion or become automatic?

## comment @leonardHONG 2026-09-18T13:03:28Z
hi, we've contributed to megamoe in flashinfer and would be interested in helping here too. are there any related tasks still open to pick up?

## comment @b8zhong 2026-09-30T01:48:17Z
Completed by @xikronz in https://github.com/sgl-project/sglang/pull/39313