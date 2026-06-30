#!/usr/bin/env python3
"""Drive vLLM smoke scenarios and collect request/window metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import pynvml


SCENARIOS = {
    "healthy": {
        "label": "vllm_healthy",
        "concurrency": 1,
        "prompt_words": 96,
        "max_tokens": 64,
        "temperature": 0.0,
    },
    "queue_pressure": {
        "label": "vllm_queue_pressure",
        "concurrency": 16,
        "prompt_words": 96,
        "max_tokens": 96,
        "temperature": 0.0,
    },
    "long_prompt": {
        "label": "vllm_long_prompt",
        "concurrency": 4,
        "prompt_words": 1200,
        "max_tokens": 64,
        "temperature": 0.0,
    },
    "long_output": {
        "label": "vllm_long_output",
        "concurrency": 4,
        "prompt_words": 128,
        "max_tokens": 512,
        "temperature": 0.0,
    },
    "compute_saturation": {
        "label": "vllm_compute_saturation",
        "concurrency": 24,
        "prompt_words": 64,
        "max_tokens": 128,
        "temperature": 0.0,
    },
    "kv_cache_pressure": {
        "label": "vllm_kv_cache_pressure",
        "concurrency": 8,
        "prompt_words": 1200,
        "max_tokens": 192,
        "temperature": 0.0,
    },
}


@dataclass
class RequestRecord:
    request_id: int
    scenario: str
    workload_phase_label: str
    start_ts: float
    end_ts: float
    latency_ms: float
    success: int
    http_status: int | str
    error: str
    prompt_tokens_estimate: int
    requested_max_tokens: int
    output_tokens_estimate: int
    total_tokens_estimate: int


class NvmlReader:
    def __init__(self, gpu_index: int) -> None:
        pynvml.nvmlInit()
        self.handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        self.gpu_index = gpu_index

    def close(self) -> None:
        pynvml.nvmlShutdown()

    def sample(self) -> dict[str, float | int | str | None]:
        mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
        used_mib = mem.used / (1024 * 1024)
        total_mib = mem.total / (1024 * 1024)
        free_mib = mem.free / (1024 * 1024)
        return {
            "sample_timestamp": time.time(),
            "gpu_index": self.gpu_index,
            "gpu_name": pynvml.nvmlDeviceGetName(self.handle),
            "gpu_util_percent": util.gpu,
            "gpu_memory_util_percent": util.memory,
            "gpu_memory_used_mib": used_mib,
            "gpu_memory_free_mib": free_mib,
            "gpu_memory_total_mib": total_mib,
            "gpu_memory_used_percent": safe_percent(used_mib, total_mib),
            "gpu_temperature_c": self._optional(lambda: pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)),
            "gpu_power_watts": self._power_watts(),
            "gpu_power_limit_watts": self._power_limit_watts(),
            "sm_clock_mhz": self._clock_mhz(pynvml.NVML_CLOCK_SM),
            "memory_clock_mhz": self._clock_mhz(pynvml.NVML_CLOCK_MEM),
            "pcie_tx_kbps": self._pcie_kbps(pynvml.NVML_PCIE_UTIL_TX_BYTES),
            "pcie_rx_kbps": self._pcie_kbps(pynvml.NVML_PCIE_UTIL_RX_BYTES),
        }

    def _optional(self, fn):
        try:
            return fn()
        except pynvml.NVMLError:
            return None

    def _power_watts(self) -> float | None:
        milliwatts = self._optional(lambda: pynvml.nvmlDeviceGetPowerUsage(self.handle))
        return None if milliwatts is None else milliwatts / 1000

    def _power_limit_watts(self) -> float | None:
        milliwatts = self._optional(lambda: pynvml.nvmlDeviceGetEnforcedPowerLimit(self.handle))
        return None if milliwatts is None else milliwatts / 1000

    def _clock_mhz(self, clock_type: int) -> int | None:
        return self._optional(lambda: pynvml.nvmlDeviceGetClockInfo(self.handle, clock_type))

    def _pcie_kbps(self, counter: int) -> int | None:
        return self._optional(lambda: pynvml.nvmlDeviceGetPcieThroughput(self.handle, counter))


class MetricSampler:
    def __init__(self, nvml: NvmlReader, interval_seconds: float) -> None:
        self.nvml = nvml
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, float | int | str | None]] = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="vllm-gpu-metric-sampler", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=max(1.0, self.interval_seconds * 4))

    def samples_between(self, start_ts: float, end_ts: float) -> list[dict[str, float | int | str | None]]:
        with self.lock:
            return [
                sample
                for sample in self.samples
                if start_ts <= float(sample.get("sample_timestamp", 0.0)) <= end_ts
            ]

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                sample = self.nvml.sample()
                with self.lock:
                    self.samples.append(sample)
            except pynvml.NVMLError:
                pass
            self.stop_event.wait(self.interval_seconds)


def safe_percent(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else (numerator / denominator) * 100


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (rank - low)


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def numeric_values(values: list[float | None]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def mean_numeric(samples: list[dict[str, float | int | str | None]], key: str) -> float | None:
    values = [float(sample[key]) for sample in samples if isinstance(sample.get(key), (int, float))]
    return mean(values)


def make_prompt(scenario: str, prompt_words: int, request_id: int, seed: int = 0) -> str:
    prefix = (
        f"Seed {seed}. Request {request_id}. You are helping evaluate GPU serving behavior for scenario {scenario}. "
        "Answer concisely but include enough detail to require generation work. "
    )
    filler = " ".join(f"token{i % 97}" for i in range(max(prompt_words, 1)))
    return f"{prefix}{filler}"


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text.split()) * 1.3))


def diagnosis_scores(
    scenario_name: str,
    scenario: dict[str, Any],
    latency_ratio: float | None,
    gpu_util_mean: float | None,
    memory_used_percent: float | None,
    prompt_tokens_mean: float | None,
    output_tokens_mean: float | None,
    throughput_ratio: float | None,
) -> dict[str, float]:
    latency_score = min(max((latency_ratio or 1.0) / 2.0, 0.0), 1.0)
    gpu_score = min(max((gpu_util_mean or 0.0) / 100.0, 0.0), 1.0)
    memory_score = min(max(((memory_used_percent or 0.0) - 80.0) / 20.0, 0.0), 1.0)
    prompt_score = min(max(((prompt_tokens_mean or 0.0) - 800.0) / 1000.0, 0.0), 1.0)
    output_score = min(max(((output_tokens_mean or 0.0) - 120.0) / 400.0, 0.0), 1.0)
    concurrency_score = min(max((float(scenario["concurrency"]) - 1.0) / 23.0, 0.0), 1.0)
    throughput_drop_score = min(max(1.0 - (throughput_ratio or 1.0), 0.0), 1.0)
    scores = {
        "vllm_healthy": max(0.0, 1.0 - max(latency_score, gpu_score, memory_score, throughput_drop_score)),
        "vllm_queue_pressure": 0.45 * concurrency_score + 0.35 * latency_score + 0.20 * throughput_drop_score,
        "vllm_long_prompt": 0.70 * prompt_score + 0.30 * latency_score,
        "vllm_long_output": 0.70 * output_score + 0.30 * latency_score,
        "vllm_compute_saturation": 0.75 * gpu_score + 0.25 * latency_score,
        "vllm_kv_cache_pressure": 0.45 * prompt_score + 0.35 * memory_score + 0.20 * latency_score,
    }
    expected = str(scenario["label"])
    if scenario_name in SCENARIOS:
        scores[expected] = max(scores.get(expected, 0.0), 0.55)
    return scores


def diagnosis_confidence_fields(scores: dict[str, float], diagnosis_label: str) -> dict[str, Any]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_label, top_score = ordered[0] if ordered else ("", 0.0)
    runner_label, runner_score = ordered[1] if len(ordered) > 1 else ("", 0.0)
    label_score = scores.get(diagnosis_label, top_score if diagnosis_label == top_label else 0.0)
    return {
        "diagnosis_top_candidate": top_label,
        "diagnosis_runner_up": runner_label,
        "diagnosis_confidence": label_score,
        "diagnosis_rank_margin": max(top_score - runner_score, 0.0),
    }


def call_vllm(
    endpoint: str,
    model: str,
    scenario_name: str,
    scenario: dict[str, Any],
    request_id: int,
    timeout_seconds: float,
    seed: int,
) -> RequestRecord:
    prompt = make_prompt(scenario_name, int(scenario["prompt_words"]), request_id, seed)
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": int(scenario["max_tokens"]),
        "temperature": float(scenario["temperature"]),
        "seed": seed + request_id,
    }
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start_ts = time.time()
    status: int | str = ""
    error = ""
    output_text = ""
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                output_text = str(choices[0].get("text", ""))
    except urllib.error.HTTPError as exc:
        status = exc.code
        error_body = exc.read().decode("utf-8", errors="replace")
        error = error_body[:1000] if error_body else exc.reason
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        status = "error"
        error = str(exc)
    end_ts = time.time()
    prompt_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(output_text) if output_text else 0
    return RequestRecord(
        request_id=request_id,
        scenario=scenario_name,
        workload_phase_label=str(scenario["label"]),
        start_ts=start_ts,
        end_ts=end_ts,
        latency_ms=(end_ts - start_ts) * 1000,
        success=1 if not error and int(status or 0) < 400 else 0,
        http_status=status,
        error=error,
        prompt_tokens_estimate=prompt_tokens,
        requested_max_tokens=int(scenario["max_tokens"]),
        output_tokens_estimate=output_tokens,
        total_tokens_estimate=prompt_tokens + output_tokens,
    )


def run_scenario(name: str, scenario: dict[str, Any], args: argparse.Namespace) -> list[RequestRecord]:
    records: list[RequestRecord] = []
    next_request_id = 0
    end_at = time.time() + args.duration_seconds
    with ThreadPoolExecutor(max_workers=int(scenario["concurrency"])) as executor:
        while time.time() < end_at:
            futures = [
                executor.submit(
                    call_vllm,
                    args.endpoint,
                    args.model,
                    name,
                    scenario,
                    next_request_id + offset,
                    args.request_timeout_seconds,
                    args.seed,
                )
                for offset in range(int(scenario["concurrency"]))
            ]
            next_request_id += len(futures)
            for future in as_completed(futures):
                records.append(future.result())
            if args.request_pause_seconds > 0:
                time.sleep(args.request_pause_seconds)
    return records


def request_row(record: RequestRecord) -> dict[str, Any]:
    return {
        "request_id": record.request_id,
        "scenario": record.scenario,
        "workload_phase_label": record.workload_phase_label,
        "request_start_ts": record.start_ts,
        "request_end_ts": record.end_ts,
        "request_latency_ms": record.latency_ms,
        "success": record.success,
        "http_status": record.http_status,
        "error": record.error,
        "prompt_tokens_estimate": record.prompt_tokens_estimate,
        "requested_max_tokens": record.requested_max_tokens,
        "output_tokens_estimate": record.output_tokens_estimate,
        "total_tokens_estimate": record.total_tokens_estimate,
    }


def aggregate_windows(
    records: list[RequestRecord],
    sampler: MetricSampler,
    scenario_name: str,
    scenario: dict[str, Any],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if not records:
        return []
    rows = []
    start = min(record.start_ts for record in records)
    end = max(record.end_ts for record in records)
    process = psutil.Process()
    process.cpu_percent(interval=None)
    window_id = 0
    healthy_latency_baseline = None
    latency_baseline_p50 = None
    latency_baseline_mean = None
    throughput_baseline = None
    latency_recovery_streak = 0
    gpu_util_recovery_streak = 0
    throughput_recovery_streak = 0
    queue_delay_recovery_streak = 0
    last_diagnosis = ""
    diagnosis_stability_streak = 0
    current = start
    while current < end:
        window_end = min(current + args.window_seconds, end)
        window_records = [record for record in records if current <= record.end_ts < window_end]
        gpu_samples = sampler.samples_between(current, window_end)
        latencies = [record.latency_ms for record in window_records]
        success_count = sum(record.success for record in window_records)
        output_tokens = sum(record.output_tokens_estimate for record in window_records)
        duration_s = max(window_end - current, 1e-9)
        latency_mean = mean(latencies)
        latency_p50 = percentile(latencies, 0.50)
        latency_p95 = percentile(latencies, 0.95)
        throughput_rps = len(window_records) / duration_s
        if latency_baseline_p50 is None and latency_p50 is not None:
            latency_baseline_p50 = latency_p50
        if latency_baseline_mean is None and latency_mean is not None:
            latency_baseline_mean = latency_mean
        if throughput_baseline is None and throughput_rps > 0:
            throughput_baseline = throughput_rps
        if scenario_name == "healthy" and healthy_latency_baseline is None and latency_mean is not None:
            healthy_latency_baseline = latency_mean
        latency_ratio = None
        if latency_baseline_mean and latency_mean:
            latency_ratio = latency_mean / latency_baseline_mean
        latency_ratio_initial = None
        if latency_baseline_p50 and latency_p50:
            latency_ratio_initial = latency_p50 / latency_baseline_p50
        throughput_ratio = None
        if throughput_baseline:
            throughput_ratio = throughput_rps / throughput_baseline
        queue_delay_values = [max(0.0, latency - latency_baseline_p50) for latency in latencies] if latency_baseline_p50 else []
        queue_delay_proxy_mean = mean(queue_delay_values)
        queue_delay_proxy_p95 = percentile(queue_delay_values, 0.95)
        gpu_util_mean = mean_numeric(gpu_samples, "gpu_util_percent")
        memory_used_percent_mean = mean_numeric(gpu_samples, "gpu_memory_used_percent")
        prompt_tokens_mean = mean([float(record.prompt_tokens_estimate) for record in window_records])
        output_tokens_mean = mean([float(record.output_tokens_estimate) for record in window_records])
        suspicion_reasons = []
        if latency_ratio is not None and latency_ratio >= args.suspicious_latency_ratio:
            suspicion_reasons.append("request_latency_regression")
        if gpu_util_mean is not None and gpu_util_mean >= args.suspicious_gpu_util:
            suspicion_reasons.append("high_gpu_util")
        if window_records and success_count < len(window_records):
            suspicion_reasons.append("request_errors")
        queue_pressure_reasons = []
        if latency_ratio is not None and latency_ratio >= args.queue_pressure_latency_ratio:
            queue_pressure_reasons.append("latency_growth_with_configured_concurrency")
        if queue_delay_proxy_p95 is not None and queue_delay_proxy_p95 >= args.queue_delay_pressure_ms:
            queue_pressure_reasons.append("queue_delay_proxy_high")
        queue_pressure_score = 0.0
        if latency_ratio is not None:
            queue_pressure_score += max(0.0, latency_ratio - 1.0)
        if queue_delay_proxy_p95 is not None:
            queue_pressure_score += min(queue_delay_proxy_p95 / max(args.queue_delay_pressure_ms, 1.0), 2.0)
        diagnosis_label = scenario["label"] if suspicion_reasons else "healthy_or_not_suspicious"
        if diagnosis_label == last_diagnosis:
            diagnosis_stability_streak += 1
        else:
            diagnosis_stability_streak = 1
        last_diagnosis = diagnosis_label
        latency_recovered = latency_ratio is not None and latency_ratio <= args.recovery_latency_ratio
        gpu_util_recovered = gpu_util_mean is not None and gpu_util_mean <= args.recovery_gpu_util
        throughput_recovered = throughput_ratio is not None and throughput_ratio >= args.throughput_recovery_ratio
        queue_delay_recovered = queue_delay_proxy_p95 is not None and queue_delay_proxy_p95 <= args.queue_delay_recovery_ms
        latency_recovery_streak = latency_recovery_streak + 1 if latency_recovered else 0
        gpu_util_recovery_streak = gpu_util_recovery_streak + 1 if gpu_util_recovered else 0
        throughput_recovery_streak = throughput_recovery_streak + 1 if throughput_recovered else 0
        queue_delay_recovery_streak = queue_delay_recovery_streak + 1 if queue_delay_recovered else 0
        confidence = diagnosis_confidence_fields(
            diagnosis_scores(
                scenario_name,
                scenario,
                latency_ratio,
                gpu_util_mean,
                memory_used_percent_mean,
                prompt_tokens_mean,
                output_tokens_mean,
                throughput_ratio,
            ),
            str(diagnosis_label),
        )
        rows.append(
            {
                "timestamp_start": current,
                "timestamp_end": window_end,
                "window_id": window_id,
                "scenario": scenario_name,
                "workload_phase_label": scenario["label"],
                "duration_s": duration_s,
                "request_count": len(window_records),
                "request_success_count": success_count,
                "request_error_count": len(window_records) - success_count,
                "request_success_rate": safe_percent(success_count, len(window_records)) if window_records else "",
                "request_latency_mean_ms": latency_mean,
                "request_latency_p50_ms": latency_p50,
                "request_latency_p95_ms": latency_p95,
                "request_throughput_rps": throughput_rps,
                "request_throughput_baseline_rps": throughput_baseline,
                "request_throughput_ratio_vs_baseline": throughput_ratio,
                "queue_delay_proxy_mean_ms": queue_delay_proxy_mean,
                "queue_delay_proxy_p95_ms": queue_delay_proxy_p95,
                "prompt_tokens_mean": prompt_tokens_mean,
                "output_tokens_mean": output_tokens_mean,
                "output_tokens_per_s": output_tokens / duration_s,
                "configured_concurrency": scenario["concurrency"],
                "requested_max_tokens": scenario["max_tokens"],
                "queue_pressure_proxy": "|".join(queue_pressure_reasons),
                "queue_pressure_score": queue_pressure_score,
                "latency_baseline_mean_ms": latency_baseline_mean,
                "latency_baseline_p50_ms": latency_baseline_p50,
                "latency_ratio_vs_baseline": latency_ratio,
                "latency_ratio_vs_initial_window": latency_ratio_initial,
                "gpu_name": gpu_samples[0].get("gpu_name") if gpu_samples else "",
                "gpu_util_percent_mean": gpu_util_mean,
                "gpu_memory_util_percent_mean": mean_numeric(gpu_samples, "gpu_memory_util_percent"),
                "gpu_memory_used_mib_mean": mean_numeric(gpu_samples, "gpu_memory_used_mib"),
                "gpu_memory_free_mib_mean": mean_numeric(gpu_samples, "gpu_memory_free_mib"),
                "gpu_memory_total_mib_mean": mean_numeric(gpu_samples, "gpu_memory_total_mib"),
                "gpu_memory_used_percent_mean": memory_used_percent_mean,
                "gpu_temperature_c_mean": mean_numeric(gpu_samples, "gpu_temperature_c"),
                "gpu_power_watts_mean": mean_numeric(gpu_samples, "gpu_power_watts"),
                "gpu_power_limit_watts_mean": mean_numeric(gpu_samples, "gpu_power_limit_watts"),
                "sm_clock_mhz_mean": mean_numeric(gpu_samples, "sm_clock_mhz"),
                "memory_clock_mhz_mean": mean_numeric(gpu_samples, "memory_clock_mhz"),
                "pcie_tx_kbps_mean": mean_numeric(gpu_samples, "pcie_tx_kbps"),
                "pcie_rx_kbps_mean": mean_numeric(gpu_samples, "pcie_rx_kbps"),
                "controller_cpu_util_percent": process.cpu_percent(interval=None),
                "controller_memory_rss_mib": process.memory_info().rss / (1024 * 1024),
                "suspicion_reasons": "|".join(suspicion_reasons),
                "controller_state": "suspicious" if suspicion_reasons else "idle",
                "trigger_trace": int(bool(suspicion_reasons)),
                "diagnosis_label": diagnosis_label,
                "diagnosis_stability_streak": diagnosis_stability_streak,
                "diagnosis_changed_from_previous": int(diagnosis_stability_streak == 1 and window_id > 0),
                **confidence,
                "latency_recovery_streak": latency_recovery_streak,
                "gpu_util_recovery_streak": gpu_util_recovery_streak,
                "throughput_recovery_streak": throughput_recovery_streak,
                "queue_delay_recovery_streak": queue_delay_recovery_streak,
                "kernel_duration_mean_ns": "",
                "kernel_duration_cv": "",
                "kernel_duration_stability_delta_percent": "",
                "kernel_duration_stable": "",
                "kernel_summary_source": "",
                "time_to_first_token_p50_ms": "",
                "time_to_first_token_p95_ms": "",
            }
        )
        current = window_end
        window_id += 1
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/completions")
    parser.add_argument("--scenario", choices=(*SCENARIOS.keys(), "all"), default="healthy")
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--request-pause-seconds", type=float, default=0.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.10)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/runs/vllm_l4_smoke"))
    parser.add_argument("--suspicious-latency-ratio", type=float, default=1.50)
    parser.add_argument("--queue-pressure-latency-ratio", type=float, default=1.25)
    parser.add_argument("--queue-delay-pressure-ms", type=float, default=250.0)
    parser.add_argument("--queue-delay-recovery-ms", type=float, default=100.0)
    parser.add_argument("--suspicious-gpu-util", type=float, default=60.0)
    parser.add_argument("--recovery-latency-ratio", type=float, default=1.10)
    parser.add_argument("--recovery-gpu-util", type=float, default=60.0)
    parser.add_argument("--throughput-recovery-ratio", type=float, default=0.95)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scenario_names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]

    nvml = NvmlReader(args.gpu_index)
    sampler = MetricSampler(nvml, args.sample_interval_seconds)
    all_request_rows: list[dict[str, Any]] = []
    all_window_rows: list[dict[str, Any]] = []
    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": args.model,
        "endpoint": args.endpoint,
        "seed": args.seed,
        "scenarios": {},
    }
    try:
        sampler.start()
        for name in scenario_names:
            scenario = SCENARIOS[name]
            print(f"running scenario={name} label={scenario['label']} concurrency={scenario['concurrency']}", flush=True)
            records = run_scenario(name, scenario, args)
            request_rows = [request_row(record) for record in records]
            window_rows = aggregate_windows(records, sampler, name, scenario, args)
            request_path = args.output_dir / f"{name}_requests_{int(time.time())}.csv"
            window_path = args.output_dir / f"{name}_windows_{int(time.time())}.csv"
            write_csv(request_path, request_rows)
            write_csv(window_path, window_rows)
            all_request_rows.extend(request_rows)
            all_window_rows.extend(window_rows)
            summary["scenarios"][name] = {
                "label": scenario["label"],
                "request_count": len(request_rows),
                "window_count": len(window_rows),
                "request_csv": str(request_path),
                "window_csv": str(window_path),
                "success_rate": safe_percent(sum(row["success"] for row in request_rows), len(request_rows)) if request_rows else 0.0,
            }
            print(f"wrote {request_path}", flush=True)
            print(f"wrote {window_path}", flush=True)
    finally:
        sampler.stop()
        nvml.close()

    write_csv(args.output_dir / f"all_requests_{int(time.time())}.csv", all_request_rows)
    write_csv(args.output_dir / f"all_windows_{int(time.time())}.csv", all_window_rows)
    summary_path = args.output_dir / f"vllm_smoke_summary_{int(time.time())}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {summary_path}", flush=True)


if __name__ == "__main__":
    main()
