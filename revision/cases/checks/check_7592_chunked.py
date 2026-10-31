"""vllm#7592 symptom check: the reporter's engine-loop throughput benchmark, chunked prefill on, one max_num_seqs value.

Follows the script in the issue body: "hi" * 511 prompts, 512 output tokens, ignore_eos, temperature 1.0,
enforce_eager, max_num_batched_tokens = max_num_seqs. Deviation: Qwen2.5-7B-Instruct (cached on the host) instead of
Qwen2-7B-Instruct; same Qwen2 architecture and size. Prints one JSON object.
"""

import argparse
import json
import time

import numpy as np
from vllm import EngineArgs, LLMEngine, SamplingParams, TextPrompt

MODEL = "Qwen/Qwen2.5-7B-Instruct"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-num-seqs", type=int, default=256)
    p.add_argument("--num-prompts", type=int, default=1000)
    p.add_argument("--chunked-prefill", choices=["on", "off"], default="on")
    p.add_argument("--model", default=MODEL, help="model name or local snapshot path")
    args = p.parse_args()
    chunked = args.chunked_prefill == "on"
    engine = LLMEngine.from_engine_args(EngineArgs(
        model=args.model, seed=0, max_model_len=10000, gpu_memory_utilization=0.9, enforce_eager=True,
        enable_chunked_prefill=chunked, max_num_seqs=args.max_num_seqs,
        max_num_batched_tokens=args.max_num_seqs if chunked else None, disable_log_stats=True))
    prompt = "hi" * 511
    for i in range(args.num_prompts):
        engine.add_request(str(i), TextPrompt(prompt=prompt),
                           SamplingParams(n=1, temperature=1.0, top_p=1.0, ignore_eos=True, max_tokens=512))
    start = time.perf_counter()
    stamps = {}
    while engine.has_unfinished_requests():
        outs = engine.step()
        now = time.perf_counter()
        for r in outs:
            stamps.setdefault(r.request_id, []).append(now)
    elapsed = time.perf_counter() - start
    tpot = np.mean([b - a for v in stamps.values() for a, b in zip(v, v[1:])])
    print(json.dumps({"model": args.model, "max_num_seqs": args.max_num_seqs, "chunked_prefill": chunked,
                      "num_prompts": args.num_prompts, "requests_per_s": round(args.num_prompts / elapsed, 4),
                      "elapsed_s": round(elapsed, 1), "delay_ms": round(tpot * 1000, 2)}))


if __name__ == "__main__":
    main()
