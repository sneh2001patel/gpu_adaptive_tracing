# vllm-project/vllm#3087: Use of `logits_processors` has become very slow in v0.3.2
state=closed reason=completed created=2024-02-28T17:19:43Z closed=2024-02-29T19:20:44Z labels=[]
cross-referenced PRs: ['https://github.com/EuroEval/EuroEval/pull/270', 'https://github.com/IBM/vllm/pull/33', 'https://github.com/vllm-project/vllm/pull/16349', 'https://github.com/vllm-project/vllm/pull/3099', 'https://github.com/vllm-project/vllm/pull/3454']

## body (@saattrupdan)
I am using vLLM together with [`outlines`](https://github.com/outlines-dev/outlines) for structured generation.

After having upgraded from v0.3.2, generation became very slow, and the RAM usage leads to OOM crashes now.

Here is a minimal example:

```python
from vllm import LLM, SamplingParams
from outlines.serve.vllm import JSONLogitsProcessor
from pydantic import BaseModel, conlist
import datetime as dt

class Output(BaseModel):
    names: conlist(str, max_length=5)
    organizations: conlist(str, max_length=5)
    locations: conlist(str, max_length=5)
    miscellanous: conlist(str, max_length=5)

[... 11 lines truncated ...]
print(f"Generation took {time_elapsed:,} seconds.")
```

When I run the above with `vllm==0.3.1`, the generation takes 58 seconds and use ~6GB memory, but if I upgrade `vllm` to v0.3.2 (and none of the other packages are changed), then suddenly the generation takes 418 seconds and spend ~18GB memory. Almost all of the time is spent stalling, not generating anything, but slowly using more and more memory, until it finally begins to generate.

I tried installing a forked version of `outlines` to see if the stalling was due to the internals of the `JSONLogitsProcessor`, but it is only called after the "stalling process" is done, so it seems like this is a vLLM issue.

## comment @saattrupdan 2024-02-28T17:38:22Z
This seems to be due to the `deepcopy` of the `SamplingParams` on [this line in the `LLMEngine`](https://github.com/vllm-project/vllm/blame/e46fa5d52e02ee48d5fdd12b35e39993008b4bd6/vllm/engine/llm_engine.py#L471-L473), which will thus also copy out the logits processors, which take up a considerable amount of memory in my case. This was added 2 weeks ago [in this PR](https://github.com/vllm-project/vllm/pull/2881), and which is part of the [v0.3.2 release](https://github.com/vllm-project/vllm/releases/tag/v0.3.2). 

Tagging relevant people to that PR: @njhill @Yard1 

## comment @simon-mo 2024-02-28T19:06:27Z
@Yard1 I think this should be fixed by next release, especially we are shipping #2819 

## comment @Yard1 2024-02-28T19:24:43Z
Hmm, I see, we should probably make it so that the logit processors are exempt from the deepcopy (unless #2819 already fixes that)

## comment @njhill 2024-02-28T19:56:16Z
Ah, yes sorry about this. I can open a PR to do what @Yard1 suggests.

## comment @njhill 2024-02-29T03:49:05Z
@Yard1 @simon-mo @saattrupdan fix is in #3099 