"""vllm#6923 symptom check: TTFT with and without prefix caching under N closed-loop clients.

Follows the report's llmperf setting: 1536 input tokens (512-token shared prefix + 1024 random tokens), 512 output
tokens, N concurrent clients. llmperf is replaced by a closed loop inside the engine: N requests stay in flight and
a new one is added when one finishes. TTFT = first-token time - arrival time, from the engine's request metrics.
Deviation: Llama-3-8B FP8 (fits the L4) instead of bf16 Llama-3-8B on an A100. Prints one JSON object.
"""

import argparse
import json
import random
import time

import numpy as np
from vllm import EngineArgs, LLMEngine, SamplingParams, TokensPrompt

MODEL = "neuralmagic/Meta-Llama-3-8B-Instruct-FP8"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=MODEL, help="model name or local snapshot path")
    p.add_argument("--prefix-caching", choices=["on", "off"], required=True)
    p.add_argument("--clients", type=int, default=32)
    p.add_argument("--requests", type=int, default=256)
    args = p.parse_args()
    engine = LLMEngine.from_engine_args(EngineArgs(
        model=args.model, seed=0, max_model_len=4096, gpu_memory_utilization=0.9,
        enable_prefix_caching=args.prefix_caching == "on", disable_log_stats=True))
    vocab = engine.get_tokenizer().vocab_size
    rng = random.Random(0)
    prefix = [rng.randrange(1000, vocab - 1000) for _ in range(512)]
    sp = SamplingParams(temperature=0.0, max_tokens=512, ignore_eos=True)

    def submit(i):
        tokens = prefix + [rng.randrange(1000, vocab - 1000) for _ in range(1024)]
        engine.add_request(str(i), TokensPrompt(prompt_token_ids=tokens), sp)

    submitted = 0
    for _ in range(args.clients):
        submit(submitted)
        submitted += 1
    ttft = []
    start = time.perf_counter()
    while engine.has_unfinished_requests():
        for out in engine.step():
            if out.finished:
                m = out.metrics
                ttft.append(m.first_token_time - m.arrival_time)
                if submitted < args.requests:
                    submit(submitted)
                    submitted += 1
    elapsed = time.perf_counter() - start
    print(json.dumps({"model": args.model, "prefix_caching": args.prefix_caching, "clients": args.clients,
                      "requests": len(ttft), "elapsed_s": round(elapsed, 1),
                      "ttft_mean_ms": round(1000 * float(np.mean(ttft)), 1),
                      "ttft_p50_ms": round(1000 * float(np.median(ttft)), 1),
                      "ttft_p95_ms": round(1000 * float(np.percentile(ttft, 95)), 1)}))


if __name__ == "__main__":
    main()
