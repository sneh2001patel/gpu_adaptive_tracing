"""vllm#19732 symptom check: structured-output decode speed for the issue's nested length-constrained list schema.

Schema from the issue: Table.content = conlist(conlist(str, min_length=5, max_length=10), min_length=5, max_length=10).
The toggle is the installed xgrammar version (0.1.19 pinned by vLLM 0.9.2 vs 0.1.21 from fix PR #20992); run this
script in each environment. Model unstated in the issue; Qwen2.5-1.5B-Instruct is used. Prints one JSON object.
"""

import argparse
import json
import time
from importlib.metadata import version

from vllm import LLM, SamplingParams
from vllm.sampling_params import GuidedDecodingParams

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
SCHEMA = {
    "properties": {"content": {"items": {"items": {"type": "string"}, "maxItems": 10, "minItems": 5, "type": "array"},
                               "maxItems": 10, "minItems": 5, "title": "Content", "type": "array"}},
    "required": ["content"], "title": "Table", "type": "object",
}  # = Table.model_json_schema() for the issue's pydantic model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--requests", type=int, default=8)
    p.add_argument("--max-tokens", type=int, default=512)
    args = p.parse_args()
    llm = LLM(model=MODEL, max_model_len=4096, gpu_memory_utilization=0.6, seed=0, guided_decoding_backend="xgrammar")
    sp = SamplingParams(temperature=0.0, max_tokens=args.max_tokens,
                        guided_decoding=GuidedDecodingParams(json=SCHEMA))  # backend is fixed at engine init in 0.9.x
    prompt = [{"role": "user", "content": "Return a 6x6 table of fruit names as JSON."}]
    llm.chat(prompt, sp, use_tqdm=False)  # warmup, includes grammar compilation
    t0 = time.perf_counter()
    outs = llm.chat([prompt] * args.requests, sp, use_tqdm=False)
    dt = time.perf_counter() - t0
    tokens = sum(len(o.outputs[0].token_ids) for o in outs)
    valid = sum(_valid(o.outputs[0].text) for o in outs)
    print(json.dumps({"xgrammar": version("xgrammar"), "requests": len(outs), "elapsed_s": round(dt, 2),
                      "output_tokens": tokens, "output_tok_per_s": round(tokens / dt, 2), "valid_json": valid}))


def _valid(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    main()
