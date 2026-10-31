"""vllm#3087 symptom check: the reporter's outlines JSONLogitsProcessor example, timed, plus peak host RSS.

Follows the issue body exactly (schema, prompt, 256 copies, max_tokens=128, temperature 0, the vocabulary-to-list
workaround), except the model: TinyLlama-1.1B (32k Llama vocabulary, like Mistral-7B-v0.1) instead of Mistral-7B-v0.1.
The copied object is the outlines FSM, whose size depends on the schema and vocabulary, not on model size.
Prints one JSON object.
"""

import datetime as dt
import json
import resource

import vllm
from outlines.serve.vllm import JSONLogitsProcessor
from pydantic import BaseModel, conlist
from vllm import LLM, SamplingParams

MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


class Output(BaseModel):
    names: conlist(str, max_length=5)
    organizations: conlist(str, max_length=5)
    locations: conlist(str, max_length=5)
    miscellanous: conlist(str, max_length=5)


def main():
    llm = LLM(MODEL, max_model_len=2048, gpu_memory_utilization=0.9)
    logits_processor = JSONLogitsProcessor(schema=Output, llm=llm.llm_engine)
    logits_processor.fsm.vocabulary = list(logits_processor.fsm.vocabulary)
    prompt = """
Locate all the names, organizations, locations and other miscellaneous entities in the following sentence:
"Charles went and saw Anna at the coffee shop Starbucks, which was based in a small town in Germany called Essen."
"""
    sampling_params = SamplingParams(max_tokens=128, temperature=0, logits_processors=[logits_processor])
    t0 = dt.datetime.now()
    llm.generate([prompt] * 256, sampling_params=sampling_params, use_tqdm=False)
    elapsed = (dt.datetime.now() - t0).total_seconds()
    peak_rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
    print(json.dumps({"vllm": vllm.__version__, "model": MODEL, "elapsed_s": round(elapsed, 2),
                      "peak_rss_gb": round(peak_rss_gb, 2)}))


if __name__ == "__main__":
    main()
