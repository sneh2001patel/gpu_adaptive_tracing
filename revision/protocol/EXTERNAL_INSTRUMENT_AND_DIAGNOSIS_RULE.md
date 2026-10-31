# External instrument and diagnosis rule (draft for author review)

Date: 2026-10-29. Status: **draft, rule v2 (step 053, after commissioning flaws in §7)**. Nothing here is frozen.
- Thresholds are named but not set. They are set only on calibration data (§3.4) and then frozen before any evaluation run.
- Author decisions behind this draft (2026-10-29):
  1. use an external instrument for all vLLM releases;
  2. draft the rule with the categories queue pressure, KV-cache pressure, host-bound, kernel hotspot, healthy, unknown.

This document fills proposal §10 steps 3 (reference method) and 5 (pilot prerequisites), and replaces the abstaining `UncalibratedClassifier` for the study.

## 1. Why a new instrument path

The existing tracer (`revision/tracing/`) plugs into vLLM V1 internals:
- a worker subclass;
- a scheduler subclass;
- the `/start_profile` and `/stop_profile` endpoints.

It is built against vLLM 0.10.2. Three accepted cases (vllm#6240, #7619, #3087) run on V0-engine releases (0.3.x–0.5.x), where those hooks do not exist.

The external path controls capture and reads metrics from outside the serving process, so **every case uses the same instrument**. The trade-off: capture boundaries are timed externally rather than acknowledged by the worker, so start/stop precision is lower and is measured, not assumed (§2.3).

## 2. External instrument

### 2.1 Processes

| Role | Mechanism | Works on |
|---|---|---|
| Serving process | `nsys launch --session-new=<id> --trace=cuda,nvtx,osrt --sample=none --cpuctxsw=none <server or driver command>`; the process runs un-captured until a burst starts; `nsys shutdown --session=<id>` at the end | all releases |
| Heavy burst (T2) | `nsys start --session=<id> --output=<path>`, wait the burst length, then `nsys stop --session=<id>`; export with `nsys export --type=sqlite` | all releases |
| Cheap metrics (T0) | Poll the engine's Prometheus endpoint every window (default 1 s), using the name map in §2.2 | all releases |
| GPU counters (T1) | NVML sampler in a separate process (existing `nvml_sampler.py`), 100 ms | all releases |
| Workload | Open-loop HTTP client replaying a fixed arrival schedule (existing `arrival_schedule.py` / `schedule_playback.py` formats) | server-mode cases |
| In-process driver | For cases the server cannot express (vllm#3087: v0.3.2 has no `guided_json`). The driver runs the engine in-process, replays the same schedule, and serves the engine's own Prometheus collectors with `prometheus_client.start_http_server`, so T0 has the same source | in-process cases |

**Container limits** (from [REPRODUCTION.md](../cases/REPRODUCTION.md)):
- no CPU sampling (`perf_event_paranoid = 4`), so `--sample=none` is fixed;
- Nsight therefore shows host-side causes only as GPU idle time and CUDA API and OS-runtime activity.

**Open check:** whether `nsys launch` follows vLLM's engine subprocesses (V1 engine core, multiprocess workers) on each release. Verify per release at commissioning, and record the captured PIDs.

### 2.2 Cheap-metric name map

Names were checked in source at each case's release tag.

| Measure | v0.3.x | v0.5.x / v0.6.x (V0) | v0.9.x / v0.11.x (V1) |
|---|---|---|---|
| running requests | `vllm:num_requests_running` | same | same |
| waiting requests | `vllm:num_requests_waiting` | same | same |
| KV-cache usage | `vllm:gpu_cache_usage_perc` | same | `vllm:kv_cache_usage_perc` (`gpu_cache_usage_perc` also present) |
| preemptions | **absent** | `vllm:num_preemptions_total` | `vllm:num_preemptions` (counter) |
| prompt tokens | `vllm:prompt_tokens_total` | same | `vllm:prompt_tokens` (counter) |
| generation tokens | `vllm:generation_tokens_total` | same | `vllm:generation_tokens` (counter) |
| TTFT, TPOT | `vllm:time_to_first_token_seconds`, `vllm:time_per_output_token_seconds` (histograms) | same | same |

- A missing measure is recorded as `unavailable`, never as zero.
- The rule (§3) must say what it does when an input is unavailable: the dependent condition is `unknown`.

### 2.3 Cost and timing measured per burst

- **Wall-clock stamps:** `start` command issued and returned; `stop` command issued and returned; report file present; export finished. Each is recorded separately.
- **Capture window:** taken from the first and last CUDA activity timestamps inside the report, compared with the command times. The difference is reported as boundary uncertainty.
- **Serving impact:** p95 latency, throughput and failures per arm, against the unprofiled arm (proposal §6).

## 3. Diagnosis rule (draft)

### 3.1 Vocabulary

`queue_pressure`, `kv_pressure`, `host_bound`, `kernel_hotspot(<kernel>)`, `healthy`, `unknown`.
- More than one firing condition gives a **set** (for example `{queue_pressure, kv_pressure}`), so overlapping causes can be scored per cause (proposal §4.3).
- `unknown` means no condition fired while latency is elevated, or a required input is unavailable.

### 3.2 Inputs per window

**Cheap (T0, T1)**, on a window of length Δ:

| Symbol | Measure |
|---|---|
| `L` | **(v2)** p95 *age of in-flight requests* divided by the same measure in a separate healthy calibration session (median over its steady windows; proposal §5.2). v1 used completed-request latency, which lags a queue drain (§7, flaw 1). Completed latency is still recorded for reporting |
| `w` | mean waiting requests |
| `u` | mean KV-cache usage (0–1) |
| `p` | preemption rate per second (`unavailable` on v0.3.x) |
| `g` | mean NVML GPU utilization (0–1) |

**Heavy (T2)**, per burst:

| Symbol | Measure |
|---|---|
| `r` | **(v2)** running requests |
| `b` | GPU busy fraction: the union of kernel, memcpy, memset and graph-replay intervals divided by the capture window |
| `t_f` | **(v2)** GPU kernel time per processed token for kernel family `f` (GEMM, attention, norm, other), in ns per token. Tokens come from the `/metrics` prompt and generation counters read right after `nsys start` returns and right before `nsys stop` is issued. v1 used shares of exact kernel names, which change with batch size (§7, flaw 2) |
| `t_f^base` | the same measure in the healthy baseline capture of the same deployment configuration |

### 3.3 Conditions

All thresholds (θ) are free parameters until calibration.

| Category | Condition | Tier |
|---|---|---|
| `kv_pressure` | `L ≥ θ_L` and (`p ≥ θ_p`, or `u ≥ θ_u` and `w ≥ 1`) | cheap |
| `queue_pressure` | `L ≥ θ_L` and `w ≥ θ_w` and `g ≥ θ_g` and not `kv_pressure` | cheap |
| `host_bound` | cheap proxy: `L ≥ θ_L` and `g < θ_g`. Heavy: `L ≥ θ_L` and `b < θ_b`. **(v2)** Both also need pending work (`w ≥ 1` or `r ≥ 1`); unknown if both counts are missing | cheap proxy; heavy confirms or overrides |
| `kernel_hotspot(f)` | **(v2)** `L ≥ θ_L` and `b ≥ θ_b` and `t_f / t_f^base ≥ θ_r` for the family `f` with the largest ratio (families missing from the baseline are skipped; a missing token count gives unknown). The label carries the family; the top kernel in that family is reported, not labelled | heavy only |
| `healthy` | `L < θ_L` and no other condition fires | either |
| `unknown` | otherwise | — |

- **Inside an active episode, heavy-burst diagnoses use `assume_elevated`** (step 051).
  - They assess the cause conditions for the incident under investigation, without re-gating on the current window's latency.
  - Recovery is a separate signal, judged by the stopping policy (CR/HS). Without this, a recovered window always reads `healthy`, and a hybrid stop could never see a stable cause together with recovery.
  - Known consequence: after a load drop, an idle GPU can read as `host_bound`. That is the lull/recurrence failure mode RQ3 measures, and it is reported, not suppressed.
- **Cheap-only arm (NT):** the heavy terms are absent, so `kernel_hotspot` can never fire, and `host_bound` rests on the NVML proxy.
- That asymmetry is exactly what RQ1 measures: on which cases the cheap diagnosis equals the heavy one.

### 3.4 Calibration and freezing

- **Calibration data:**
  - healthy sessions;
  - the controlled cases (§4.2 of the proposal: overload, KV pressure, lull/recurrence, overlap, changing bottleneck), plus a **host-stall** case added in step 054 so that θ_g and θ_b have a host-bound calibration condition;
  - three calibration seeds per real case's **toggle-off** (fixed) configuration only (step 054; was one).
- **Evaluation data:** the six real cases with the toggle **on**, never seen during calibration. Thresholds are therefore held out from every real slowdown.
- **Sessions, seeds and the pre-declared rule for each θ:** [CALIBRATION_PLAN.md](CALIBRATION_PLAN.md).
- **Procedure:**
  1. For each θ, choose the value that separates calibration conditions, and record the margin.
  2. Write all θ to a versioned config file with its hash.
  3. Freeze it before the first evaluation session.
  4. Any later change creates a new version, and evaluation data seen before the change is re-labelled exploratory.
- The threshold sweeps for RQ4 (proposal §5.4) vary these frozen values around their calibrated points.

### 3.5 Expected reference mapping for the real cases

This is fixed now, before any evaluation data exists.

| Case | Upstream cause | Reference category | Note |
|---|---|---|---|
| vllm#6240 | Slow CUTLASS FP8 GEMM selected | `kernel_hotspot(cutlass FP8 GEMM)` | GPU busy; the kernel share shifts |
| vllm#3087 | Per-request deepcopy on the host | `host_bound` | GPU idle while the host copies |
| vllm#25418 | Per-request HF processor rebuild | `host_bound` | GPU idle during preprocessing |
| vllm#19732 | Grammar mask computation on the host | `host_bound` | Per-step host work between GPU steps |
| vllm#7592 (if confirmed) | Scheduler ordering causes preemption thrashing | `kv_pressure` | Preemption counter available on v0.5.5 |
| vllm#7619 | Prefix-cache blocks not marked computed, so prefill is recomputed | **outside the vocabulary** | Extra GPU prefill work: it may look like `queue_pressure` or a prefill-kernel `kernel_hotspot`. Score it as "vocabulary gap" unless the author adds a `prefill_heavy` category before freezing |

**Author decision (2026-10-29):** no `prefill_heavy` category. vllm#7619 stays in the benchmark as a **documented vocabulary-gap case**.
- Any diagnosis it receives is scored as "outside vocabulary".
- The case is reported separately, to show how the rule and each stopping policy behave on a cause the vocabulary cannot name.

## 4. What is reused from `revision/tracing/`

- `policies.py`: FIX / SS / CR / HS stop rules, unchanged. They consume `d_t` from §3.
- `nvml_sampler.py`, `arrival_schedule.py`, `schedule_playback.py`, `aggregation.py`, `windows.py`.
- `nsys_backend.parse_kernel_database`: reused for kernel extraction, extended with busy-fraction union and name normalization.
- **Not reused for external cases:** `vllm_cuda_worker.py`, `vllm_event_scheduler.py`, `worker_barrier.py`, and the HTTP profile endpoints. These remain the V1-internal path.

## 5. Commissioning checks before the pilot

All of these run on the L4 after the vllm#7592 blocks finish:

1. `nsys launch` + `nsys start/stop` bursts on one V0 release (v0.5.5) and one V1 release (v0.11.0). Check that kernels from the engine process are captured, and record the PIDs.
2. Per-burst cost and boundary uncertainty (§2.3) on a healthy workload.
3. Cheap-metric polling on every case release, using the §2.2 map.
4. One end-to-end episode per policy (FIX(3), SS, HS, NT) on a healthy-then-overload schedule, counted separately from the pilot (proposal §10 step 5).

## 6. Commissioning results (step 050)

Runs: [commission_external.py](../cases/checks/commission_external.py). Results: [cases/checks/commissioning/](../cases/checks/commissioning/); raw captures are kept locally and git-ignored.

**Setup:**
- Qwen2.5-7B-Instruct, 8 closed-loop clients, two 2-second external bursts per run.
- Counted separately from the pilot.

| Check | v0.5.5 (V0 engine) | v0.11.0 (V1 engine) |
|---|---|---|
| Server under `nsys launch`; external `nsys start/stop` bursts | works | works; follows the engine-core subprocess |
| PIDs with kernels | one engine PID per run | one (engine core) |
| Kernels per 2-second burst, node-level graph tracing | about 10.2k–10.4k | about 14.9k–16.2k |
| Busy fraction | 0.857, 0.871 | 0.852, 0.936 |
| Top kernel share (CUTLASS bf16 GEMM 128x2) | 0.905, 0.907 | 0.906, 0.905 |
| `nsys start` returns | 195–486 ms | 236–534 ms |
| `nsys stop` returns | **6.2–6.6 s** | **7.6–8.4 s** |
| SQLite export | 0.24–0.25 s | 0.42–0.48 s |
| Cheap metrics via the §2.2 name map | running, waiting, KV, preemptions, tokens all present | all present (V1 names) |

**Findings that changed the design:**
1. **`--sample` and `--cpuctxsw` are `nsys start` options**, not `nsys launch` options, in Nsight 2026.3. The launch failed until they were moved.
2. **Activity times are relative to the session start, while `ANALYSIS_DETAILS` is absolute.** The capture window in activity time is `[0, duration]`. Before this fix, busy fraction read 0.0.
3. **CUDA graphs:**
   - With the default graph-level tracing, decode-step graph replays appear only in `CUPTI_ACTIVITY_KIND_GRAPH_TRACE`. Kernel shares then miss the decode GEMMs, and busy fraction read 0.07.
   - **The study uses `--cuda-graph-trace=node`.** Graph replays also count as busy time when graph-level tracing is used, and such captures are flagged `graph_kernels_opaque`.
4. **Records crossing the window edges:** up to 311 per burst of graph-node kernels "start" seconds before the capture. These are in flight at `nsys start`, and their times are unreliable.
   - Kernel shares use only records inside the window.
   - Busy fraction uses intervals clipped to the window.
   - The count is reported as `kernels_crossing_window`.
5. **Kernel identity uses Nsight's `shortName`,** plus the first template argument when it is a plain identifier. Demangled names with templated return types (`std::enable_if<…>::type`) defeat parsing, and stripping all templates merged every CUTLASS GEMM into one name.
6. **Cost:** `nsys stop` takes 6–8 s for a 2-second capture, mostly flushing node-level records. That makes each heavy burst roughly 3–4× its nominal length in controller time. This is a primary cost measurement for RQ2/RQ3. Perturbation of serving during that flush is not yet measured.

**Not yet done:**
- Commissioning check 3 for v0.3.x and v0.9.2.
- Check 4: one end-to-end episode per policy. It needs the episode runner (controller loop: windows → trigger → burst → rule → policy), which is not built yet.

## 7. Commissioning check 4: episodes per arm (step 052)

**Setup:**
- vLLM 0.11.0, Qwen2.5-7B-Instruct; schedules from [make_schedule.py](../cases/checks/make_schedule.py).
- **Provisional thresholds (commissioning only, not calibration):** θ_L 1.5, θ_w 4, θ_u 0.9, θ_p 0.5, θ_g 0.6, θ_b 0.5, θ_s 0.15.
- Healthy baseline at 1 req/s: p95 8.06 s, busy 0.865.
- Results: [cases/checks/episodes_commission/](../cases/checks/episodes_commission/).

**Pass 1, 6 req/s:**
- No arm triggered: max latency ratio 1.30–1.31, waiting always 0.
- Continuous batching absorbed the load, so this was not an overload.
- The four runs agree closely (p95 10.36–10.43 s), which gives a first noise-floor estimate.

**Pass 2, 20 req/s for 60 s:**

| Arm | Bursts | Stop reason | Heavy diagnoses |
|---|---|---|---|
| NT | 0 | horizon (records only) | cheap: `queue_pressure` 79 windows, `unknown` 60, `host_bound` 3 |
| FIX(3) | 3 | repeated_bursts_complete | `kernel_hotspot:<GEMM 256x128>+queue_pressure` ×2, `kernel_hotspot:flash_fwd_splitkv+queue_pressure` ×1 |
| SS | 4 | diagnosis_stable (after the label alternated) | as FIX(3), then the same label twice |
| HS | 6 | budget_exhausted (latency never recovered within budget) | alternating GEMM / flash_fwd_splitkv hotspot |

- **Mechanics pass:**
  - every episode started at t = 54 s, 14 s into the incident;
  - 13/13 bursts succeeded;
  - `nsys stop` took 6.9–7.4 s;
  - the arms took different online decisions (a pilot proceed criterion).
- **Two rule flaws found.** Both must be resolved before calibration.

**Flaw 1: the latency signal lags.**
- The window latency is the p95 end-to-end time of requests *completed* in the last 5 s. After the queue drains (waiting = 0), it still reads 4–5× for about 15–20 s.
- The rule then says `unknown` (correct), and once GPU utilization drops it says **`host_bound` (wrong)**: idle GPU plus elevated, lagging latency.
- **Options:**
  - (a) measure latency from requests *in flight or admitted* in the window, for example the p95 age of outstanding requests or TTFT via streaming;
  - (b) require pending work (`waiting > 0` or `running > 0`) for `host_bound`;
  - (c) both.

**Flaw 2: kernel shares are confounded by load.**
- At high load, vLLM runs larger batches and the GEMMs switch tile configurations (here 256x128 instead of the baseline's 128x2 variant).
- The share shift against a 1 req/s baseline exceeds θ_s, so a pure overload gets a false `kernel_hotspot`. The "hottest" kernel also alternates between GEMM and attention, which delays stability.
- In this case, the heavy arms' diagnosis was **worse** than cheap-only (`queue_pressure`).
- **Options:**
  - (a) compare **GPU time per processed token by kernel family** (GEMM / attention / normalization / other; token counts from the `/metrics` counters) against the baseline, rather than raw shares of exact kernel names. Batching lowers per-token GEMM time, while a slow kernel such as vllm#6240's raises it.
  - (b) record baselines at several matched load levels and compare at the nearest one.
  - (c) keep shares, but at the kernel-family level only.
- Option (a) is recommended. It keeps the kernel name for reporting (which GEMM) while making the test load-invariant.

Neither fix is applied yet: both change what the rule measures, so they need author review. The commissioning runs are kept as development data and are not used for calibration.

## 8. Commissioning with rule v2 (step 053)

**Setup:**
- The same 20 req/s overload. New healthy baseline:
  - in-flight p95 age 7.19 s (median of 94 steady windows; completed p95 8.04 s);
  - per-token GPU time over 727 tokens: GEMM 2,521 µs, attention 38 µs, other 36 µs;
  - busy 0.874.
- No `norm` family appears on v0.11.0. Normalization is likely fused into `torch.compile` Triton kernels and counted as `other`.
- Provisional θ_r = 1.3.
- Results: [cases/checks/episodes_commission_v2/](../cases/checks/episodes_commission_v2/).

| Arm | Bursts | Stop | Heavy diagnosis (all bursts) |
|---|---|---|---|
| NT | 0 | horizon | cheap: `queue_pressure` 82 windows, `unknown` 62 (drain) |
| FIX(3) | 3 | repeated_bursts_complete | `kernel_hotspot:attention+queue_pressure` |
| SS | 2 | diagnosis_stable | same (v1 needed 4, because the label alternated) |
| HS | 6 | budget_exhausted | same |

**Results:**
- **Flaw 1 fixed:** no `host_bound` anywhere. During the drain the rule says `unknown`, because queued requests are still being served (in-flight age elevated) and no named cause applies.
- **Flaw 2 partly fixed:**
  - Per-token GEMM time falls under load (94–201 µs vs 2,521 µs at baseline), so there is no GEMM hotspot.
  - Per-token **attention** time rises (58–87 µs vs 38 µs; ratio 1.5–2.3), so a false `kernel_hotspot:attention` remains at θ_r = 1.3. Attention cost per token depends on context length and the prompt/generation mix, which overload changes.
- **Implication for calibration:**
  - θ_r must exceed the overload's attention ratio on this configuration (≥ 2.3), yet stay below the ratio of a genuinely slow kernel. For vllm#6240, CUTLASS FP8 GEMMs are 1.7–5.2× slower in isolation.
  - If a single θ_r cannot separate the calibration overload from the toggle-off/on contrast of the kernel case, the fallback is per-family thresholds or load-matched baselines (§7, option b). Calibration decides, and the outcome is reported either way.
