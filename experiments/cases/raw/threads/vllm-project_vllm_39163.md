# vllm-project/vllm#39163: [Bug]: First request after startup is unexpectedly slow with Qwen3.5-27B-FP8
state=closed reason=completed created=2026-04-07T08:51:47Z closed=2026-04-10T00:49:52Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/39169']

## body (@gakugaku)
### Your current environment

<details>
<summary>The output of <code>python collect_env.py</code></summary>

```text
Collecting environment information...
==============================
        System Info
==============================
OS                           : Ubuntu 24.04.3 LTS (x86_64)
GCC version                  : (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0
Clang version                : Could not collect
CMake version                : Could not collect
Libc version                 : glibc-2.39

==============================
[... 109 lines truncated ...]
==============================
```

</details>

### 🐛 Describe the bug

The first request after healthy startup has TTFT around `43 s`, while the second and later requests are normal.

I reproduced this with `vllm/vllm-openai:v0.19.0-cu130` serving `Qwen/Qwen3.5-27B-FP8` on a single `NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition` GPU with driver `580.95.05`.

This does not look like normal startup spillover because:

- `/health` is already `200` before the first request
- the engine is awake
- `prefix_cache_hits_total=0`
- queue time is effectively zero
- the delay is almost entirely first-request prefill time

### How to reproduce?

Start the server like this:

The arguments below are adapted from the official Qwen3.5 recipe to match this single-GPU reproduction:
<https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html>

```bash
docker run --rm --gpus '"device=0"' \
  -p 8002:8000 \
  -e VLLM_LOGGING_LEVEL=INFO \
  -e VLLM_NO_USAGE_STATS=1 \
  vllm/vllm-openai:v0.19.0-cu130 \
  vllm serve Qwen/Qwen3.5-27B-FP8 \
    --served-model-name Qwen3.5-27B-FP8 \
    --tensor-parallel-size 1 \
    --trust-remote-code \
    --gpu-memory-utilization 0.95 \
    --max-model-len 128000 \
[... 5 lines truncated ...]
    --tool-call-parser qwen3_coder
```

Wait until `http://HOST:8002/health` returns `200`, then send the same short streaming request twice:

```bash
endpoint=http://HOST:8002
payload='{
  "model": "Qwen3.5-27B-FP8",
  "messages": [{"role": "user", "content": "1+1をひとことで答えて。"}],
  "max_tokens": 32,
  "stream": true,
  "extra_body": {
    "chat_template_kwargs": {
      "enable_thinking": false
    }
  }
[... 9 lines truncated ...]
  "$endpoint/v1/chat/completions"
```

results:

- first request: `starttransfer=0.016977 total=43.449701`
- second request: `starttransfer=0.004942 total=0.095591`
- third request with a different prompt: `starttransfer=0.006630 total=0.796733`
- cumulative metrics after the third request:
  - `time_to_first_token_seconds_sum=43.536531925201416`
  - `e2e_request_latency_seconds_sum=44.33244299888611`
  - `request_prefill_time_seconds_sum=43.5066136789992`
  - `prefix_cache_hits_total=0.0`

### Observed behavior

Almost all of the one-time delay appears to be in the first request's prefill path, not queueing.

### Expected behavior

Once the server is healthy, the first request should be in the same rough TTFT range as later requests, not about `43 seconds` slower.

### Additional context

As a workaround, I can send one synthetic warmup request right after startup. That warmup request itself takes about `43 s`, and then user-facing requests are normal.


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @NickLucche 2026-04-08T07:26:16Z
@gakugaku what's the PR that fixed this bug? I don't see any that got merged among the referenced ones here

## comment @gakugaku 2026-04-08T07:39:26Z
@NickLucche 
Sorry, I accidentally auto-closed this issue via a commit message in a private project while validating it. I noted that this workaround could be removed once `vllm-project/vllm#39163` is fixed, and GitHub seems to have treated that as a closing keyword 😅
Reopening now.