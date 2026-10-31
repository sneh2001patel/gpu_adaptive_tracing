"""Write screening.csv: one row per issue in raw/candidates.jsonl with stage, decision and reason (proposal §4.1).

Decisions are the screener's judgements recorded here by hand; threads for thread-stage rows are in raw/threads/.
Reason codes: not_performance, benchmark_tooling, install_build, feature_only, multi_gpu, non_cuda_hardware,
gpu_unavailable (needs Hopper/Blackwell or >24 GB with no scale-down), cpu_backend, startup_or_one_shot,
no_measured_shortfall, fix_does_not_address_slowdown, effect_too_small, slow_onset, cause_unclear, accuracy.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).parent

TITLE = {
    119: "benchmark_tooling", 462: "cause_unclear", 545: "install_build", 1658: "benchmark_tooling",
    1854: "benchmark_tooling", 1966: "benchmark_tooling", 4212: "feature_only", 4509: "gpu_unavailable",
    4632: "multi_gpu", 4755: "not_performance", 4847: "benchmark_tooling", 5532: "startup_or_one_shot",
    5535: "gpu_unavailable", 5564: "startup_or_one_shot", 5579: "gpu_unavailable", 6072: "multi_gpu",
    6340: "not_performance", 6461: "not_performance", 9728: "non_cuda_hardware", 9778: "benchmark_tooling",
    12567: "not_performance", 14600: "benchmark_tooling", 15619: "startup_or_one_shot", 19317: "startup_or_one_shot",
    19650: "not_performance", 20974: "not_performance", 21206: "benchmark_tooling", 22861: "benchmark_tooling",
    25189: "gpu_unavailable", 26070: "gpu_unavailable", 26320: "gpu_unavailable", 26856: "feature_only",
    27828: "cause_unclear", 30655: "multi_gpu", 32786: "cpu_backend", 33616: "not_performance",
    33962: "not_performance", 34731: "feature_only", 35641: "non_cuda_hardware", 37444: "not_performance",
    39751: "feature_only", 44003: "multi_gpu", 45733: "not_performance", 45741: "gpu_unavailable",
    47328: "cpu_backend", 47639: "not_performance", 48205: "gpu_unavailable", 49640: "cpu_backend",
    50615: "not_performance", 51151: "non_cuda_hardware", 52180: "feature_only", 52330: "multi_gpu",
    52884: "benchmark_tooling", 52907: "multi_gpu", 54101: "benchmark_tooling", 55729: "multi_gpu",
    58100: "benchmark_tooling", 58849: "non_cuda_hardware", 61374: "non_cuda_hardware", 63844: "not_performance",
}
# Title notes where the code alone is not self-explanatory.
TITLE_NOTES = {
    119: "2023 tokenizer slow-path; pre-dates the OpenAI server and fix is a tokenizer default, not a serving toggle",
    462: "2023 Starcoder vs TGI comparison; fix PR is a general feature, cause not isolated",
    5532: "LoRA loading time, not steady-state serving", 5564: "LoRA loading time, not steady-state serving",
    15619: "Triton JIT compile time", 19317: "startup subprocess overhead", 27828: "torch.compile partition; cause spans many PRs",
    58849: "WSL2-specific pinned memory",
}
THREAD = {
    6240: ("include", "", "FP8 CUTLASS scaled_mm untuned for SM89 (Ada); L4 is SM89. Toggle v0.5.1 -> v0.5.2 (PR #6384). Needs CUDA>=12.4-built kernels: reporter used the vllm/vllm-openai:v0.5.1 image; Docker GPU passthrough is not configured on the L4 host."),
    7619: ("include", "", "Reported on an L4. Prefix-cache blocks not marked computed in block manager v2, so the model runner recomputes. Toggles: v1 vs v2 block manager; v0.5.5 -> v0.6.0 (PR #7822)."),
    6923: ("include", "", "Single-GPU Llama-3-8B: prefix caching raises TTFT up to 5x via O(n) evictor lookups (host CPU). Toggles: prefix caching on/off; v0.6.4.post1 -> v0.6.5 (PR #7209). 8B bf16 is tight on 24 GB; use an 8B FP8 or smaller model."),
    7592: ("include", "", "RTX 4090 (Ada): scheduler change #6867 drops chunked-prefill peak throughput ~15% via preemption thrashing. Toggles: chunked prefill on/off; v0.5.5 -> v0.6.0 (PR #7874). Smaller effect than the others."),
    25418: ("include", "", "Single L40S, Qwen2.5-VL-7B: per-request mm_processor_kwargs re-create the HF processor, 7.28 -> 0.32 req/s. Toggles: workload (with/without per-request kwargs); v0.11.0 -> v0.11.1 (PR #26483). Use a 3B VL model if 7B leaves too little KV cache."),
    19732: ("include", "", "xgrammar 0.1.19 nested-list schema gives <3 tok/s; fixed by bumping xgrammar to 0.1.21 (PR #20992). Toggle: xgrammar version under the same vLLM (v0.9.2), or v0.9.2 -> v0.10.0. Model unstated; choose a small one. Cause stated only as 'xgrammar performance improvements'."),
    3087: ("include", "", "v0.3.2 deep-copies logits processors per request: 58 s -> 418 s plus host RAM growth. Toggle v0.3.2 -> v0.3.3 (PR #3099). Old stack (torch 2.1, outlines) may be hard to install; check first."),
    49013: ("maybe", "gpu_unavailable", "Strong case (2-5x structured-output decode slowdown from torch CPU thread spin; toggle OMP_NUM_THREADS=1 or v0.26.0 -> v0.28.0, PR #49919), but affected releases (>= v0.24) use CUDA 13-era PyTorch, which failed on the L4 driver. Feasible only with a driver update or cu12 wheels; needs a 262k-vocab model that fits (for example a small Gemma 3)."),
    15105: ("maybe", "multi_gpu", "Multimodal processing cache sized as ~0 bytes (unbounded): 45 -> 7 tok/s and extra memory on 2x3090. Toggle v0.8.0 -> v0.8.1 (PR #15114). Cause is not multi-GPU specific; may scale down to one L4 with a small VL model."),
    42325: ("exclude", "accuracy", "RMSNorm numerical precision, not performance."),
    49699: ("exclude", "non_cuda_hardware", "ROCm MI100 only."),
    25671: ("exclude", "effect_too_small", "About 10 ms over 3 requests from repeated config hashing."),
    9238: ("exclude", "fix_does_not_address_slowdown", "PR #9818 removes the heartbeat timeout; the slow HF image preprocessing remains."),
    14450: ("exclude", "no_measured_shortfall", "LoRA memory ignored in KV block sizing; no measured slowdown or OOM in the thread."),
    12529: ("exclude", "multi_gpu", "4x RTX 3070; fix only moves the OOM check."),
    12410: ("exclude", "non_cuda_hardware", "Intel Gaudi (HPU) fork."),
    42520: ("exclude", "cpu_backend", "VLLM_TARGET_DEVICE=cpu."),
    44175: ("exclude", "slow_onset", "Latency step-up after ~7 h at 150 RPS; too slow for a tracing episode budget."),
    39163: ("exclude", "startup_or_one_shot", "First-request-only delay on Blackwell; one-shot and unverified fix."),
    43444: ("exclude", "cause_unclear", "Reranker regression; fix adds parallel preprocessing without identifying the regressing change."),
    11568: ("exclude", "accuracy", "Reranker output order vs HF; fix is truncation side."),
}


def main():
    rows = []
    for d in map(json.loads, open(HERE / "raw" / "candidates.jsonl")):
        n = d["number"]
        prs = ";".join(f"#{p['number']}" for p in d["fix_prs"])
        if n in THREAD:
            decision, reason, note = THREAD[n]
            stage = "thread"
        else:
            decision, reason, note, stage = "exclude", TITLE[n], TITLE_NOTES.get(n, ""), "title"
        rows.append({"issue": n, "url": d["url"], "title": d["title"], "fix_prs": prs,
                     "stage": stage, "decision": decision, "reason": reason, "note": note})
    assert len(rows) == len(TITLE) + len(THREAD), "every candidate needs exactly one decision"
    with open(HERE / "screening.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(Counter((r["stage"], r["decision"]) for r in rows))


if __name__ == "__main__":
    main()
