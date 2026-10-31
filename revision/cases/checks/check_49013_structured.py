"""vllm#49013 symptom check: guided-JSON decode throughput with many concurrent structured-output requests.

Mechanism from the issue and fix PR #49919: per-step host work on the (rows x vocab/32) grammar bitmask fans out
across torch's intra-op thread pool, sized to the visible core count; the OpenMP workers spin-wait and contend with
the engine loop, worse under a cgroup CPU quota. Toggles: release (v0.26.0 vs v0.28.0) and OMP_NUM_THREADS=1 on the
same release (the reporter's workaround). Needs a 262k-vocabulary model; Gemma 3 1B (ungated mirror) is used instead
of Gemma-4-26B/31B. All requests use one JSON schema (concurrency-gated per the second reproducer). Prints one JSON object.
"""

import argparse
import json
import os
import time

import torch
import vllm
from vllm import LLM, SamplingParams

MODEL = "unsloth/gemma-3-1b-it"
SCHEMA = {
    "type": "object",
    "properties": {"category": {"type": "string", "enum": ["billing", "delivery", "product", "account", "other"]},
                   "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                   "summary": {"type": "string"}},
    "required": ["category", "sentiment", "summary"],
}


def structured_params(max_tokens, guided):
    if not guided:
        return SamplingParams(temperature=0.0, max_tokens=max_tokens, ignore_eos=False)
    try:  # newer API
        from vllm.sampling_params import StructuredOutputsParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens, structured_outputs=StructuredOutputsParams(json=SCHEMA))
    except ImportError:
        from vllm.sampling_params import GuidedDecodingParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens, guided_decoding=GuidedDecodingParams(json=SCHEMA))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--requests", type=int, default=256)
    p.add_argument("--max-num-seqs", type=int, default=64)
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--guided", choices=["on", "off"], default="on")
    args = p.parse_args()
    llm = LLM(model=MODEL, max_model_len=4096, gpu_memory_utilization=0.85, seed=0, max_num_seqs=args.max_num_seqs)
    sp = structured_params(args.max_tokens, args.guided == "on")
    msgs = [[{"role": "user", "content": f"Classify this customer message as JSON: 'Order #{i} arrived late and the box was damaged.'"}]
            for i in range(args.requests)]
    llm.chat(msgs[:4], sp, use_tqdm=False)  # warmup, includes grammar compilation
    t0 = time.perf_counter()
    outs = llm.chat(msgs, sp, use_tqdm=False)
    dt = time.perf_counter() - t0
    tokens = sum(len(o.outputs[0].token_ids) for o in outs)
    print(json.dumps({"vllm": vllm.__version__, "torch": torch.__version__, "guided": args.guided,
                      "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"), "requests": len(outs),
                      "elapsed_s": round(dt, 2), "output_tok_per_s": round(tokens / dt, 1),
                      "output_tokens": tokens}))


if __name__ == "__main__":
    main()
