"""vllm#6240 feasibility: does this vLLM build select CUTLASS FP8 scaled_mm on this GPU, and is it slower than torch._scaled_mm?

Kernel-level check only (no model): times both GEMM paths at Llama-3-8B linear-layer shapes.
Run inside the environment of the vLLM release under test; prints one JSON object.
"""

import json
import torch
import vllm
from vllm import _custom_ops as ops

SHAPES = {"qkv": (6144, 4096), "o": (4096, 4096), "gate_up": (28672, 4096), "down": (4096, 14336)}  # (N, K)
BATCH = [1, 16, 64, 256]
ITERS, WARMUP = 200, 20


def bench(fn):
    for _ in range(WARMUP):
        fn()
    start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERS):
        fn()
    end.record()
    torch.cuda.synchronize()
    return start.elapsed_time(end) / ITERS * 1000  # microseconds


def main():
    cap = torch.cuda.get_device_capability()
    cap_int = cap[0] * 10 + cap[1]
    supports = ops.cutlass_scaled_mm_supports_fp8(cap_int) if hasattr(ops, "cutlass_scaled_mm_supports_fp8") else None
    rows = []
    for name, (n, k) in SHAPES.items():
        b = torch.randn(n, k, device="cuda").to(torch.float8_e4m3fn).t()  # column-major (K, N)
        for m in BATCH:
            a = torch.randn(m, k, device="cuda").to(torch.float8_e4m3fn)
            sa = torch.ones(1, device="cuda", dtype=torch.float32)
            sb = torch.ones(1, device="cuda", dtype=torch.float32)
            cutlass_us = bench(lambda: ops.cutlass_scaled_mm(a, b, sa, sb, torch.bfloat16))
            torch_us = bench(lambda: torch._scaled_mm(a, b, out_dtype=torch.bfloat16, scale_a=sa, scale_b=sb))
            rows.append({"layer": name, "M": m, "N": n, "K": k, "cutlass_us": round(cutlass_us, 2),
                         "torch_scaled_mm_us": round(torch_us, 2), "ratio": round(cutlass_us / torch_us, 2)})
    print(json.dumps({"vllm": vllm.__version__, "torch": torch.__version__, "gpu": torch.cuda.get_device_name(),
                      "capability": cap_int, "cutlass_scaled_mm_supports_fp8": supports, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
