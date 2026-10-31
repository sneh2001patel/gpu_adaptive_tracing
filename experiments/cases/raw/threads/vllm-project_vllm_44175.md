# vllm-project/vllm#44175: [Bug]: Linear host RSS growth + step-up in E2E latency under sustained `max_tokens=1` classification load (Gemma-3-1b, V1, prefix caching)
state=closed reason=completed created=2026-06-01T08:11:09Z closed=2026-07-07T07:32:56Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/44490']

## body (@ashgold)
### Your current environment

<details>
<summary>The output of <code>python collect_env.py</code></summary>

```text
Collecting environment information...
==============================
        System Info
==============================
OS                           : Ubuntu 22.04.5 LTS (x86_64)
GCC version                  : (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0
Clang version                : Could not collect
CMake version                : Could not collect
Libc version                 : glibc-2.35

==============================
[... 162 lines truncated ...]

```

</details>


### 🐛 Describe the bug


```yaml
containers:
- args:
  - --model=/data/models/gemma-3-1b-it/
  - --served-model-name=gemma-3-1b-it
  - --gpu-memory-utilization=0.90
  - --uvicorn-log-level=warning
  env:
  - name: OMP_NUM_THREADS
    value: "1"
  image: <registry>/serving/vllm:v0.21.0
  resources:
[... 5 lines truncated ...]
      memory: 16Gi
```

- Engine: V1 (default in 0.21.0).
- Prefix caching: default (enabled) — not explicitly disabled.
- Chunked prefill: default (enabled).
- `/dev/shm`: 16 GiB `emptyDir` (medium: Memory).
- 1 replica, no autoscaling.

## 🐛 Describe the bug

### Summary

Under a sustained 12-hour stability test, the server shows **a continuous, linear increase in container (host) RSS** and a **step-up in E2E latency after ~7 hours**, while **per-pod CPU usage gradually declines** even though request rate is held constant. Throughput is fixed by the load generator, so the workload itself does not change over time; only the server's internal state does.

### Workload

- Prompt length: ~550 tokens average.
- `max_tokens: 1` (single output token per request — effectively prefill-dominated).
- Load: constant **150 RPS** for **12 hours**.
- Prompts are mostly unique per request (only a short shared instruction/template prefix); they do **not** share long common prefixes.

### Observations (over the 12h run, traffic held constant at 150 RPS)

1. **Host memory (container RSS): linear growth.**
   - From ~6.00 GiB to ~6.57 GiB over 12h (Mean 6.30, Max 6.57, Min 6.01 GiB).
   - Perfectly linear, monotonic, no plateau. ~570 MiB growth over ~6.5M requests ≈ **~90 bytes retained per request**.
   - This is **host RAM**, not GPU memory.

2. **CPU usage: gradual decline at constant RPS.**
   - 1m-avg CPU drops from ~1.3 cores to ~1.0 cores over the run (Mean 1.12, Max 1.39 cores).
   - Caps around ~1.3 cores despite a 2-core limit (appears single-thread / GIL-bound; `OMP_NUM_THREADS=1` is set).
   - Since RPS is constant and per-request work shouldn't decrease, declining CPU suggests the process spends **increasing time blocked/idle**, not less time computing.

3. **E2E latency: flat, then a step-up.**
   - Flat at ~0.03–0.05 s for the first ~7 hours, then **steps up to ~0.13–0.18 s** and plateaus (Mean 0.07 s, Max 0.18 s over the window).
   - The step is a discrete knee, not a smooth ramp from t=0.


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.