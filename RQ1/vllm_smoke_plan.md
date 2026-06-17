# RQ1 Step 11: L4 vLLM Smoke Plan

## Goal

Extend RQ1 from controlled PyTorch microbenchmarks to a first realistic serving smoke test on the NVIDIA L4 24GB host. The smoke test should validate that the controller schema can combine request-level evidence with cheap GPU evidence before building the full vLLM experiment.

This is not yet the final vLLM evaluation. It is the smallest L4 serving run that proves the measurement loop works.

## Target GPU

- GPU: NVIDIA L4
- VRAM: 24GB class, observed as 23034 MiB through NVML.
- Role: active cloud-GPU baseline for current RQ1 work.

## Model Choice

Use `Qwen/Qwen2.5-7B-Instruct` as the default L4 smoke model.

Rationale:

- 7B class, matching the Stage 2 plan better than a tiny model.
- Open model family suitable for repeatable research runs.
- Fits comfortably on a 24GB L4 with moderate context length and conservative vLLM memory settings.
- Large enough to exercise prefill, decode, KV-cache, and queueing behavior without needing multi-GPU serving.

Initial serving settings:

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.82 \
  --max-model-len 4096 \
  --max-num-seqs 32
```

If model download time or network access is a blocker, use `Qwen/Qwen2.5-1.5B-Instruct` only as a plumbing fallback. Do not use the fallback for headline RQ1 L4 results.

## Smoke Scenarios

Run these scenarios first:

| Scenario | Label | Purpose |
|---|---|---|
| Healthy low concurrency | `vllm_healthy` | Establish request latency and GPU baseline. |
| Queue pressure | `vllm_queue_pressure` | Increase concurrent requests to create queueing and latency growth. |
| Long prompt | `vllm_long_prompt` | Stress prefill and prompt processing. |
| Long output | `vllm_long_output` | Stress decode and sustained generation. |
| Compute saturation | `vllm_compute_saturation` | Drive high GPU utilization with short prompts and higher concurrency. |
| KV-cache pressure | `vllm_kv_cache_pressure` | Use longer contexts and moderate concurrency to raise memory pressure. |

Initial smoke command:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario all \
  --duration-seconds 60 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_smoke
```

For a faster first check:

```bash
python RQ1/scripts/run_vllm_smoke.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --scenario healthy \
  --duration-seconds 20 \
  --window-seconds 10 \
  --output-dir RQ1/runs/vllm_l4_smoke_quick
```

## Minimal Request Metrics

The vLLM smoke harness records:

1. Request start timestamp.
2. Request end timestamp.
3. Scenario label.
4. Prompt token estimate.
5. Requested max output tokens.
6. Output token estimate.
7. End-to-end latency.
8. Time to first token if streaming is enabled later.
9. Success or error status.
10. HTTP status code.
11. Per-window request count.
12. Per-window success rate.
13. Per-window throughput in requests per second.
14. Per-window output token throughput.
15. Per-window p50 and p95 latency.

Cheap GPU metrics remain aligned with the RQ1 microbenchmark schema:

- GPU utilization percent.
- GPU memory used/free/total.
- GPU memory used percent.
- GPU memory utilization percent.
- GPU temperature.
- GPU power draw and power limit.
- SM clock and memory clock.
- PCIe throughput if available.

## Controller Schema Extension

The first vLLM controller row should include the existing RQ1 fields plus:

- `scenario`
- `request_count`
- `request_success_count`
- `request_error_count`
- `request_success_rate`
- `request_latency_p50_ms`
- `request_latency_p95_ms`
- `request_latency_mean_ms`
- `request_throughput_rps`
- `prompt_tokens_mean`
- `output_tokens_mean`
- `output_tokens_per_s`
- `queue_pressure_proxy`
- `time_to_first_token_p50_ms`
- `time_to_first_token_p95_ms`

For the smoke phase, `queue_pressure_proxy` is estimated from latency growth relative to the healthy baseline and request concurrency. Later, if vLLM exposes queueing delay directly, replace the proxy with measured scheduler queue time.

## Success Checks

The Step 11 smoke is successful if:

- The L4 vLLM server can answer requests for the selected model.
- The harness writes per-request and per-window CSV files for at least the healthy and queue-pressure scenarios.
- NVML GPU metrics are present in every non-empty window.
- The window table contains request latency, throughput, prompt/output token estimates, and scenario labels.
- At least one pressure scenario produces higher p95 latency or higher GPU utilization than the healthy scenario.

## Next After Smoke

After the smoke works, add the same automatic versus fixed-window profiling comparison used by microbenchmarks:

- Automatic mode: trigger short Nsight bursts when request latency is suspicious and cheap GPU evidence is ambiguous.
- Fixed-window baseline: collect a fixed profiler window after anomaly detection.
- Use the same RQ1 aggregate/table/figure pattern so microbenchmark and vLLM results can be compared.
