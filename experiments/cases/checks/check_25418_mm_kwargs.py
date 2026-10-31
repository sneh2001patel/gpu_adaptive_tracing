"""vllm#25418 symptom check: multimodal throughput with and without per-request mm_processor_kwargs.

Mirrors the reporter's patch, which gives every request {"fps": random.uniform(1.9, 2.1)}, so that each request
carries distinct processor kwargs. Offline engine instead of `vllm bench serve`; synthetic images instead of the
VisionArena dataset; Qwen2.5-VL-3B instead of 7B (KV room on the L4). Prints one JSON object.
"""

import argparse
import json
import random
import time

import numpy as np
from PIL import Image
from vllm import LLM, SamplingParams

MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
PROMPT = ("<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>Describe this image.<|im_end|>\n"
          "<|im_start|>assistant\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kwargs", choices=["none", "per_request"], required=True)
    p.add_argument("--requests", type=int, default=100)
    args = p.parse_args()
    rng = random.Random(0)
    np_rng = np.random.default_rng(0)
    llm = LLM(model=MODEL, max_model_len=8192, gpu_memory_utilization=0.9, seed=0, limit_mm_per_prompt={"image": 1})
    sp = SamplingParams(temperature=0.0, max_tokens=112, ignore_eos=True)

    def make(i):
        img = Image.fromarray(np_rng.integers(0, 255, (448, 448, 3), dtype=np.uint8))
        req = {"prompt": PROMPT, "multi_modal_data": {"image": img}}
        if args.kwargs == "per_request":
            req["mm_processor_kwargs"] = {"fps": rng.uniform(1.9, 2.1)}
        return req

    llm.generate([make(0)], sp, use_tqdm=False)  # warmup
    reqs = [make(i) for i in range(args.requests)]
    t0 = time.perf_counter()
    outs = llm.generate(reqs, sp, use_tqdm=False)
    dt = time.perf_counter() - t0
    tokens = sum(len(o.outputs[0].token_ids) for o in outs)
    print(json.dumps({"kwargs": args.kwargs, "requests": len(outs), "elapsed_s": round(dt, 2),
                      "requests_per_s": round(len(outs) / dt, 3), "output_tok_per_s": round(tokens / dt, 1)}))


if __name__ == "__main__":
    main()
