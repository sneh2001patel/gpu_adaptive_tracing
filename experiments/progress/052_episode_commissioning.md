# Step 052: Episode commissioning on the L4 (check 4)

Date: 2026-10-29. vLLM 0.11.0, Qwen2.5-7B-Instruct. Provisional thresholds, commissioning only. Details: [design doc §7](../protocol/EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md).

## Results

- **Pipeline:** works end to end on real hardware. 1291/1291 requests per run; episodes start 14 s into the overload; 13/13 bursts succeed.
- **Arms:** they take different online decisions. FIX(3) uses 3 bursts, SS 4, HS 6 (budget exhausted); NT is cheap-only. This meets a pilot proceed criterion mechanically.
- **Burst cost:** `nsys stop` takes 6.9–7.4 s per 2-second burst.
- **First pass (6 req/s) did not overload:** the latency ratio stayed at most 1.31. The four runs agree closely, giving a first noise-floor estimate.

## Rule flaws found (author review needed before calibration)

1. **Lagging latency signal:** after the queue drains, completed-request latency stays 4–5× high, which yields a false `host_bound` once the GPU idles.
2. **Load-confounded kernel shares:** high load changes the GEMM tile variants, which yields a false `kernel_hotspot` in a pure overload. Here the heavy diagnosis was worse than the cheap-only one.

Recommended fixes:
- latency of outstanding/admitted requests, plus a pending-work requirement for `host_bound`;
- per-token GPU time by kernel family compared against the baseline.

## Scope of this step

About 1 L4 GPU-hour. Data is development-only. Raw bursts are git-ignored.
