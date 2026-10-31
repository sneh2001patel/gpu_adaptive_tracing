"""vllm#6240 symptom check: offline decode throughput of the reporter's FP8 model with the CUTLASS FP8 path on or off.

--cutlass off forces fp8.cutlass_fp8_supported() to False, which is the effect of fix PR #6384 on Ada (SM89):
vLLM then uses torch._scaled_mm. Everything else (build, model, prompts) is identical. Prints one JSON object.
"""

import argparse
import json
import time

from vllm.model_executor.layers.quantization.utils import w8a8_utils as fp8

MODEL = "neuralmagic/Meta-Llama-3-8B-Instruct-FP8"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cutlass", choices=["on", "off"], required=True)
    p.add_argument("--max-tokens", type=int, default=256)
    args = p.parse_args()
    if args.cutlass == "off":
        fp8.cutlass_fp8_supported = lambda: False
    selected = fp8.cutlass_fp8_supported()

    from vllm import LLM, SamplingParams
    llm = LLM(model=MODEL, max_model_len=4096, gpu_memory_utilization=0.85, seed=0)
    sp = SamplingParams(max_tokens=args.max_tokens, ignore_eos=True, temperature=0.0)
    prompt = "Write a detailed history of the printing press."
    llm.generate([prompt], sp, use_tqdm=False)  # warmup
    results = {}
    for batch in (1, 8, 32):
        t0 = time.perf_counter()
        outs = llm.generate([prompt] * batch, sp, use_tqdm=False)
        dt = time.perf_counter() - t0
        tokens = sum(len(o.outputs[0].token_ids) for o in outs)
        results[f"batch_{batch}"] = {"seconds": round(dt, 3), "output_tok_per_s": round(tokens / dt, 2)}
    print(json.dumps({"cutlass_arg": args.cutlass, "cutlass_selected": selected, "model": MODEL, "results": results}))


if __name__ == "__main__":
    main()
