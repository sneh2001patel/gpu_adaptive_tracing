#!/usr/bin/env python3
"""Run Phase 0 GPU-heavy microbenchmarks with cheap metric logging."""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil
import pynvml
import torch


WORKLOADS = (
    "launch_overhead_or_small_kernel",
    "mixed",
    "compute_bound",
)

BASELINE_MODE = "fixed_window"
AUTOMATIC_MODE = "automatic"
COMPARE_MODE = "compare"


@dataclass
class IterationStats:
    latency_ms: float
    operations: int


@dataclass
class Window:
    index: int
    start_ts: float
    end_ts: float
    workload: str
    label: str
    latencies_ms: list[float] = field(default_factory=list)
    operations: int = 0
    samples: list[dict[str, float | int | str | None]] = field(default_factory=list)


class NvmlReader:
    def __init__(self, gpu_index: int) -> None:
        pynvml.nvmlInit()
        self.handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        self.gpu_index = gpu_index

    def close(self) -> None:
        pynvml.nvmlShutdown()

    def sample(self, pid: int) -> dict[str, float | int | str | None]:
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
            "process_gpu_memory_used_mib": self._process_gpu_memory_mib(pid),
        }

    def _optional(self, fn: Callable[[], int | float]) -> int | float | None:
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

    def _process_gpu_memory_mib(self, pid: int) -> float | None:
        processes = []
        for getter in (pynvml.nvmlDeviceGetComputeRunningProcesses, pynvml.nvmlDeviceGetGraphicsRunningProcesses):
            try:
                processes.extend(getter(self.handle))
            except pynvml.NVMLError:
                continue

        total_bytes = 0
        found = False
        unavailable = getattr(pynvml, "NVML_VALUE_NOT_AVAILABLE", None)
        for proc in processes:
            if proc.pid == pid and proc.usedGpuMemory not in (None, unavailable):
                total_bytes += int(proc.usedGpuMemory)
                found = True
        return total_bytes / (1024 * 1024) if found else None


class MetricSampler:
    def __init__(self, nvml: NvmlReader, pid: int, interval_seconds: float) -> None:
        self.nvml = nvml
        self.pid = pid
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, float | int | str | None]] = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="gpu-metric-sampler", daemon=True)

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

    def latest_sample(self) -> dict[str, float | int | str | None] | None:
        with self.lock:
            return self.samples[-1] if self.samples else None

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                sample = self.nvml.sample(self.pid)
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


def mean_numeric(samples: list[dict[str, float | int | str | None]], key: str) -> float | None:
    values = [float(sample[key]) for sample in samples if isinstance(sample.get(key), (int, float))]
    return statistics.fmean(values) if values else None


def max_numeric(samples: list[dict[str, float | int | str | None]], key: str) -> float | None:
    values = [float(sample[key]) for sample in samples if isinstance(sample.get(key), (int, float))]
    return max(values) if values else None


def timed_cuda(fn: Callable[[], int]) -> IterationStats:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    start.record()
    operations = fn()
    end.record()
    torch.cuda.synchronize()
    return IterationStats(latency_ms=start.elapsed_time(end), operations=operations)


def build_workload(workload: str, args: argparse.Namespace) -> Callable[[], IterationStats]:
    if workload == "compute_bound":
        a = torch.randn((args.gemm_size, args.gemm_size), device="cuda", dtype=torch.float32)
        b = torch.randn((args.gemm_size, args.gemm_size), device="cuda", dtype=torch.float32)

        def compute_bound() -> IterationStats:
            def run() -> int:
                c = a @ b
                c = torch.relu(c)
                return 2

            return timed_cuda(run)

        return compute_bound

    if workload == "mixed":
        a = torch.randn((args.mixed_gemm_size, args.mixed_gemm_size), device="cuda", dtype=torch.float32)
        b = torch.randn((args.mixed_gemm_size, args.mixed_gemm_size), device="cuda", dtype=torch.float32)
        x = torch.randn((args.mixed_vector_size,), device="cuda", dtype=torch.float32)
        y = torch.empty_like(x)

        def mixed() -> IterationStats:
            def run() -> int:
                c = a @ b
                y.copy_(x)
                y.mul_(1.0001).add_(0.25)
                reduced = y.sum()
                c = c + reduced
                return 5

            return timed_cuda(run)

        return mixed

    if workload == "launch_overhead_or_small_kernel":
        x = torch.randn((args.small_kernel_size,), device="cuda", dtype=torch.float32)

        def launch_frequency() -> IterationStats:
            def run() -> int:
                y = x
                for _ in range(args.small_kernel_launches):
                    y = torch.sin(y + 0.001)
                return args.small_kernel_launches

            return timed_cuda(run)

        return launch_frequency

    raise ValueError(f"Unsupported workload: {workload}")


def classify_window(
    window: Window,
    process: psutil.Process,
    baseline_latency_ms: float | None,
    args: argparse.Namespace,
) -> dict[str, float | int | str | None]:
    duration_s = max(window.end_ts - window.start_ts, 1e-9)
    latency_mean = statistics.fmean(window.latencies_ms) if window.latencies_ms else None
    latency_p95 = percentile(window.latencies_ms, 0.95)
    throughput_ops = window.operations / duration_s
    gpu_util_mean = mean_numeric(window.samples, "gpu_util_percent")
    mem_used_percent_mean = mean_numeric(window.samples, "gpu_memory_used_percent")
    mem_used_percent_max = max_numeric(window.samples, "gpu_memory_used_percent")

    cpu_percent = process.cpu_percent(interval=None)
    rss_mib = process.memory_info().rss / (1024 * 1024)

    latency_ratio = None
    if baseline_latency_ms and latency_mean:
        latency_ratio = latency_mean / baseline_latency_ms

    score = 0.0
    reasons = []
    if gpu_util_mean is not None and gpu_util_mean >= args.suspicious_gpu_util:
        score += 0.45
        reasons.append("high_gpu_util")
    if mem_used_percent_mean is not None and mem_used_percent_mean >= args.suspicious_mem_percent:
        score += 0.25
        reasons.append("high_memory_use")
    if window.workload == "launch_overhead_or_small_kernel" and throughput_ops >= args.suspicious_launch_ops_per_s:
        score += 0.45
        reasons.append("high_launch_rate")
    if latency_ratio is not None and latency_ratio >= args.suspicious_latency_ratio:
        score += 0.30
        reasons.append("latency_regression")

    is_suspicious = score >= args.suspicious_score
    controller_state = "suspicious" if is_suspicious else "idle"
    diagnosis_label, diagnosis_confidence, diagnosis_evidence = diagnose(
        workload=window.workload,
        reasons=reasons,
        gpu_util_mean=gpu_util_mean,
        mem_used_percent_mean=mem_used_percent_mean,
        throughput_ops=throughput_ops,
    )

    first_sample = window.samples[0] if window.samples else {}
    row = {
        "timestamp_start": window.start_ts,
        "timestamp_end": window.end_ts,
        "window_id": window.index,
        "workload": window.workload,
        "workload_phase_label": window.label,
        "gpu_name": first_sample.get("gpu_name"),
        "duration_s": duration_s,
        "iterations": len(window.latencies_ms),
        "operations": window.operations,
        "benchmark_iteration_latency_mean_ms": latency_mean,
        "benchmark_iteration_latency_p95_ms": latency_p95,
        "benchmark_throughput_ops_per_s": throughput_ops,
        "gpu_util_percent_mean": gpu_util_mean,
        "gpu_memory_util_percent_mean": mean_numeric(window.samples, "gpu_memory_util_percent"),
        "gpu_memory_used_mib_mean": mean_numeric(window.samples, "gpu_memory_used_mib"),
        "gpu_memory_free_mib_mean": mean_numeric(window.samples, "gpu_memory_free_mib"),
        "gpu_memory_total_mib_mean": mean_numeric(window.samples, "gpu_memory_total_mib"),
        "gpu_memory_used_percent_mean": mem_used_percent_mean,
        "gpu_memory_used_percent_max": mem_used_percent_max,
        "gpu_temperature_c_mean": mean_numeric(window.samples, "gpu_temperature_c"),
        "gpu_power_watts_mean": mean_numeric(window.samples, "gpu_power_watts"),
        "gpu_power_limit_watts_mean": mean_numeric(window.samples, "gpu_power_limit_watts"),
        "sm_clock_mhz_mean": mean_numeric(window.samples, "sm_clock_mhz"),
        "memory_clock_mhz_mean": mean_numeric(window.samples, "memory_clock_mhz"),
        "pcie_tx_kbps_mean": mean_numeric(window.samples, "pcie_tx_kbps"),
        "pcie_rx_kbps_mean": mean_numeric(window.samples, "pcie_rx_kbps"),
        "process_gpu_memory_used_mib_mean": mean_numeric(window.samples, "process_gpu_memory_used_mib"),
        "controller_cpu_util_percent": cpu_percent,
        "controller_memory_rss_mib": rss_mib,
        "baseline_latency_ms": baseline_latency_ms,
        "latency_ratio_vs_baseline": latency_ratio,
        "suspicion_score": min(score, 1.0),
        "suspicion_reasons": "|".join(reasons) if reasons else "",
        "controller_state": controller_state,
        "trigger_trace": int(is_suspicious),
        "diagnosis_label": diagnosis_label,
        "diagnosis_confidence": diagnosis_confidence,
        "diagnosis_evidence": diagnosis_evidence,
        "profiler_mode": "",
        "profiler_output_prefix": "",
        "profiler_report_paths": "",
        "profiler_status": "",
        "profiler_returncode": "",
        "profiler_duration_s": "",
        "profiler_kernel_count": "",
        "profiler_kernel_instances": "",
        "profiler_kernel_total_time_ns": "",
        "profiler_kernel_avg_duration_ns": "",
        "profiler_top_kernel_name": "",
        "profiler_stats_path": "",
        "automatic_stop_reason": "",
    }
    return row


def diagnose(
    workload: str,
    reasons: list[str],
    gpu_util_mean: float | None,
    mem_used_percent_mean: float | None,
    throughput_ops: float,
) -> tuple[str, float, str]:
    evidence = list(reasons)
    if "high_launch_rate" in reasons:
        return "launch_overhead_or_small_kernel", 0.75, "|".join(evidence)
    if "high_memory_use" in reasons and gpu_util_mean is not None and gpu_util_mean >= 60:
        return "mixed_compute_memory_pressure", 0.65, "|".join(evidence)
    if "high_gpu_util" in reasons and workload == "compute_bound":
        return "compute_bound", 0.70, "|".join(evidence)
    if "high_gpu_util" in reasons and workload == "mixed":
        return "mixed", 0.65, "|".join(evidence)
    if "latency_regression" in reasons:
        return "latency_regression_unknown_gpu_cause", 0.45, "|".join(evidence)
    if throughput_ops > 0 and workload == "launch_overhead_or_small_kernel":
        return "possible_launch_overhead_or_small_kernel", 0.35, "launch_workload_observed"
    if mem_used_percent_mean is not None and mem_used_percent_mean >= 50:
        return "possible_memory_pressure", 0.35, "moderate_memory_use"
    return "healthy_or_not_suspicious", 0.25, "no_trigger"


def append_profiler_evidence(row: dict[str, float | int | str | None], burst: dict[str, object], mode: str) -> None:
    row["profiler_mode"] = mode
    row["profiler_output_prefix"] = str(burst.get("output_prefix", ""))
    row["profiler_report_paths"] = "|".join(str(path) for path in burst.get("report_paths", []))
    row["profiler_status"] = str(burst.get("status", ""))
    row["profiler_returncode"] = str(burst.get("returncode", ""))
    row["profiler_duration_s"] = str(burst.get("duration_s", ""))
    stats = burst.get("kernel_summary", {})
    if isinstance(stats, dict):
        row["profiler_kernel_count"] = str(stats.get("kernel_count", ""))
        row["profiler_kernel_instances"] = str(stats.get("kernel_instances", ""))
        row["profiler_kernel_total_time_ns"] = str(stats.get("kernel_total_time_ns", ""))
        row["profiler_kernel_avg_duration_ns"] = str(stats.get("kernel_avg_duration_ns", ""))
        row["profiler_top_kernel_name"] = str(stats.get("top_kernel_name", ""))
        row["profiler_stats_path"] = str(stats.get("stats_path", ""))
    if burst.get("status") == "ok":
        row["diagnosis_evidence"] = f"{row['diagnosis_evidence']}|profiler_burst_collected"
        row["diagnosis_confidence"] = min(float(row["diagnosis_confidence"]) + 0.15, 0.95)
    else:
        row["diagnosis_evidence"] = f"{row['diagnosis_evidence']}|profiler_burst_failed"


def collect_nsys_burst(
    workload: str,
    output_dir: Path,
    args: argparse.Namespace,
    tag: str,
    burst_seconds: float,
) -> dict[str, object]:
    profiles_dir = output_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    nsys_path = shutil.which(args.nsys_path) or args.nsys_path
    if not Path(nsys_path).exists() and shutil.which(nsys_path) is None:
        return {
            "status": "missing_nsys",
            "returncode": "",
            "output_prefix": "",
            "report_paths": [],
            "duration_s": 0.0,
        }

    output_prefix = profiles_dir / f"{workload}_{tag}_{int(time.time())}"
    command = [
        nsys_path,
        "profile",
        "--trace",
        args.nsys_trace,
        "--sample",
        "none",
        "--cpuctxsw",
        "none",
        "--force-overwrite",
        "true",
        "--duration",
        str(burst_seconds),
        "--output",
        str(output_prefix),
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile-target",
        workload,
        "--duration-seconds",
        str(burst_seconds),
        "--gemm-size",
        str(args.gemm_size),
        "--mixed-gemm-size",
        str(args.mixed_gemm_size),
        "--mixed-vector-size",
        str(args.mixed_vector_size),
        "--small-kernel-size",
        str(args.small_kernel_size),
        "--small-kernel-launches",
        str(args.small_kernel_launches),
    ]
    start = time.time()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(burst_seconds + 30, 45),
    )
    duration_s = time.time() - start
    report_paths = sorted(str(path) for path in profiles_dir.glob(f"{output_prefix.name}*.nsys-rep"))
    ok_returncodes = {0, 143}
    status = "ok" if completed.returncode in ok_returncodes and report_paths else "failed"
    kernel_summary = {}
    if status == "ok" and args.extract_nsys_stats:
        kernel_summary = extract_kernel_summary(Path(report_paths[0]), args)
    return {
        "status": status,
        "returncode": completed.returncode,
        "output_prefix": str(output_prefix),
        "report_paths": report_paths,
        "duration_s": duration_s,
        "kernel_summary": kernel_summary,
        "stderr_tail": completed.stderr[-1000:],
    }


def extract_kernel_summary(report_path: Path, args: argparse.Namespace) -> dict[str, object]:
    nsys_path = shutil.which(args.nsys_path) or args.nsys_path
    command = [
        nsys_path,
        "stats",
        "--report",
        "cuda_gpu_kern_sum",
        "--format",
        "csv",
        "--output",
        "-",
        str(report_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    stats_path = report_path.with_suffix(".kernel_summary.json")
    if completed.returncode != 0:
        summary = {
            "status": "failed",
            "returncode": completed.returncode,
            "stats_path": str(stats_path),
            "stderr_tail": completed.stderr[-1000:],
        }
        stats_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    lines = completed.stdout.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("Time (%),")), None)
    if header_idx is None:
        summary = {
            "status": "no_kernel_table",
            "returncode": completed.returncode,
            "stats_path": str(stats_path),
        }
        stats_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    rows = list(reader)
    kernel_count = len(rows)
    instances = sum(int(float(row.get("Instances", 0) or 0)) for row in rows)
    total_time_ns = sum(float(row.get("Total Time (ns)", 0) or 0) for row in rows)
    avg_duration_ns = total_time_ns / instances if instances else 0.0
    top_kernel = rows[0].get("Name", "") if rows else ""
    summary = {
        "status": "ok",
        "returncode": completed.returncode,
        "stats_path": str(stats_path),
        "kernel_count": kernel_count,
        "kernel_instances": instances,
        "kernel_total_time_ns": total_time_ns,
        "kernel_avg_duration_ns": avg_duration_ns,
        "top_kernel_name": top_kernel,
    }
    stats_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def run_profile_target(workload: str, args: argparse.Namespace) -> None:
    run_one_iteration = build_workload(workload, args)
    torch.cuda.synchronize()
    run_end = time.time() + args.duration_seconds
    iterations = 0
    operations = 0
    while time.time() < run_end:
        stats = run_one_iteration()
        iterations += 1
        operations += stats.operations
    print(f"profile_target_done workload={workload} iterations={iterations} operations={operations}", flush=True)


def run_workload(workload: str, args: argparse.Namespace, output_dir: Path) -> Path:
    csv_path = output_dir / f"{workload}_{int(time.time())}.csv"
    pid = os.getpid()
    process = psutil.Process(os.getpid())
    process.cpu_percent(interval=None)
    nvml = NvmlReader(args.gpu_index)
    sampler = MetricSampler(nvml, pid, args.sample_interval_seconds)

    rows = []
    baseline_latency_ms = None
    profiler_bursts = 0
    last_diagnosis = None
    diagnosis_streak = 0
    automatic_stop_reason = ""
    next_window_end = time.time() + args.window_seconds
    window = Window(index=0, start_ts=time.time(), end_ts=time.time(), workload=workload, label=workload)
    run_end = time.time() + args.duration_seconds

    try:
        run_one_iteration = build_workload(workload, args)
        torch.cuda.synchronize()
        sampler.start()
        while time.time() < run_end:
            stats = run_one_iteration()
            now = time.time()
            window.end_ts = now
            window.latencies_ms.append(stats.latency_ms)
            window.operations += stats.operations

            if now >= next_window_end:
                window.samples = sampler.samples_between(window.start_ts, window.end_ts)
                if not window.samples:
                    latest = sampler.latest_sample()
                    window.samples = [latest] if latest else [nvml.sample(pid)]
                if baseline_latency_ms is None and window.latencies_ms:
                    baseline_latency_ms = statistics.fmean(window.latencies_ms)
                row = classify_window(window, process, baseline_latency_ms, args)
                last_diagnosis, diagnosis_streak, automatic_stop_reason = update_stability_stop(
                    row=row,
                    last_diagnosis=last_diagnosis,
                    diagnosis_streak=diagnosis_streak,
                    automatic_stop_reason=automatic_stop_reason,
                    args=args,
                )
                row["automatic_stop_reason"] = automatic_stop_reason
                should_profile = (
                    args.mode == AUTOMATIC_MODE
                    and args.enable_nsys_bursts
                    and row["trigger_trace"] == 1
                    and profiler_bursts < args.max_nsys_bursts_per_workload
                    and not automatic_stop_reason
                )
                should_profile = should_profile or (
                    args.mode == BASELINE_MODE
                    and args.enable_nsys_bursts
                    and profiler_bursts < args.fixed_window_bursts_per_workload
                )
                if should_profile:
                    mode = "automatic_trigger" if args.mode == AUTOMATIC_MODE else "fixed_window"
                    burst_seconds = args.nsys_burst_seconds if args.mode == AUTOMATIC_MODE else args.fixed_window_nsys_seconds
                    burst = collect_nsys_burst(workload, output_dir, args, f"window{window.index}_{mode}", burst_seconds)
                    append_profiler_evidence(row, burst, mode)
                    run_end += float(burst.get("duration_s") or 0)
                    profiler_bursts += 1
                rows.append(row)
                window = Window(
                    index=window.index + 1,
                    start_ts=now,
                    end_ts=now,
                    workload=workload,
                    label=workload,
                )
                next_window_end += args.window_seconds

        if window.latencies_ms:
            window.samples = sampler.samples_between(window.start_ts, window.end_ts)
            if not window.samples:
                latest = sampler.latest_sample()
                window.samples = [latest] if latest else [nvml.sample(pid)]
            if baseline_latency_ms is None:
                baseline_latency_ms = statistics.fmean(window.latencies_ms)
            row = classify_window(window, process, baseline_latency_ms, args)
            last_diagnosis, diagnosis_streak, automatic_stop_reason = update_stability_stop(
                row=row,
                last_diagnosis=last_diagnosis,
                diagnosis_streak=diagnosis_streak,
                automatic_stop_reason=automatic_stop_reason,
                args=args,
            )
            row["automatic_stop_reason"] = automatic_stop_reason
            should_profile = (
                args.mode == AUTOMATIC_MODE
                and args.enable_nsys_bursts
                and row["trigger_trace"] == 1
                and profiler_bursts < args.max_nsys_bursts_per_workload
                and not automatic_stop_reason
            )
            should_profile = should_profile or (
                args.mode == BASELINE_MODE
                and args.enable_nsys_bursts
                and profiler_bursts < args.fixed_window_bursts_per_workload
            )
            if should_profile:
                mode = "automatic_trigger" if args.mode == AUTOMATIC_MODE else "fixed_window"
                burst_seconds = args.nsys_burst_seconds if args.mode == AUTOMATIC_MODE else args.fixed_window_nsys_seconds
                burst = collect_nsys_burst(workload, output_dir, args, f"window{window.index}_{mode}", burst_seconds)
                append_profiler_evidence(row, burst, mode)
                run_end += float(burst.get("duration_s") or 0)
                profiler_bursts += 1
            rows.append(row)
    finally:
        sampler.stop()
        nvml.close()

    if not rows:
        raise RuntimeError(f"No rows generated for workload {workload}")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def update_stability_stop(
    row: dict[str, float | int | str | None],
    last_diagnosis: str | None,
    diagnosis_streak: int,
    automatic_stop_reason: str,
    args: argparse.Namespace,
) -> tuple[str | None, int, str]:
    if automatic_stop_reason or row["trigger_trace"] != 1:
        return last_diagnosis, diagnosis_streak, automatic_stop_reason

    diagnosis = str(row["diagnosis_label"])
    if diagnosis == last_diagnosis:
        diagnosis_streak += 1
    else:
        last_diagnosis = diagnosis
        diagnosis_streak = 1

    if diagnosis_streak >= args.stability_stop_windows:
        automatic_stop_reason = f"stable_diagnosis:{diagnosis}:{diagnosis_streak}_windows"
    return last_diagnosis, diagnosis_streak, automatic_stop_reason


def write_summary(csv_paths: list[Path], output_dir: Path) -> Path:
    summary = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "csv_files": [str(path) for path in csv_paths],
        "workloads": {},
    }
    for path in csv_paths:
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        suspicious = [row for row in rows if row["trigger_trace"] == "1"]
        profiler_rows = [row for row in rows if row.get("profiler_report_paths")]
        profiler_duration_s = sum(float(row.get("profiler_duration_s") or 0) for row in profiler_rows)
        kernel_instances = sum(int(float(row.get("profiler_kernel_instances") or 0)) for row in profiler_rows)
        kernel_total_time_ns = sum(float(row.get("profiler_kernel_total_time_ns") or 0) for row in profiler_rows)
        profiler_paths = []
        for row in profiler_rows:
            profiler_paths.extend(path for path in row["profiler_report_paths"].split("|") if path)
        diagnosis_counts: dict[str, int] = {}
        for row in rows:
            diagnosis = row.get("diagnosis_label", "")
            diagnosis_counts[diagnosis] = diagnosis_counts.get(diagnosis, 0) + 1
        summary["workloads"][path.stem] = {
            "workload": rows[0].get("workload", ""),
            "windows": len(rows),
            "suspicious_windows": len(suspicious),
            "first_suspicious_window": suspicious[0]["window_id"] if suspicious else None,
            "profiler_bursts": len(profiler_rows),
            "profiler_duration_s": profiler_duration_s,
            "profiler_report_paths": profiler_paths,
            "profiler_kernel_instances": kernel_instances,
            "profiler_kernel_total_time_ns": kernel_total_time_ns,
            "diagnosis_counts": diagnosis_counts,
            "csv": str(path),
        }
    summary_path = output_dir / f"summary_{int(time.time())}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary_path


def write_comparison_summary(automatic_summary_path: Path, fixed_summary_path: Path, output_dir: Path) -> Path:
    automatic = json.loads(automatic_summary_path.read_text(encoding="utf-8"))
    fixed = json.loads(fixed_summary_path.read_text(encoding="utf-8"))

    by_workload = {}
    for mode_name, summary in ((AUTOMATIC_MODE, automatic), (BASELINE_MODE, fixed)):
        for result in summary["workloads"].values():
            workload = result["workload"]
            by_workload.setdefault(workload, {})[mode_name] = result

    comparison = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "automatic_summary": str(automatic_summary_path),
        "fixed_window_summary": str(fixed_summary_path),
        "workloads": {},
    }
    for workload, results in by_workload.items():
        auto = results.get(AUTOMATIC_MODE, {})
        fixed_result = results.get(BASELINE_MODE, {})
        comparison["workloads"][workload] = {
            "automatic_windows": auto.get("windows", 0),
            "fixed_window_windows": fixed_result.get("windows", 0),
            "automatic_suspicious_windows": auto.get("suspicious_windows", 0),
            "fixed_window_suspicious_windows": fixed_result.get("suspicious_windows", 0),
            "automatic_profiler_bursts": auto.get("profiler_bursts", 0),
            "fixed_window_profiler_bursts": fixed_result.get("profiler_bursts", 0),
            "automatic_profiler_duration_s": auto.get("profiler_duration_s", 0),
            "fixed_window_profiler_duration_s": fixed_result.get("profiler_duration_s", 0),
            "automatic_profiler_kernel_instances": auto.get("profiler_kernel_instances", 0),
            "fixed_window_profiler_kernel_instances": fixed_result.get("profiler_kernel_instances", 0),
            "automatic_profiler_kernel_total_time_ns": auto.get("profiler_kernel_total_time_ns", 0),
            "fixed_window_profiler_kernel_total_time_ns": fixed_result.get("profiler_kernel_total_time_ns", 0),
            "automatic_profiler_report_paths": auto.get("profiler_report_paths", []),
            "fixed_window_profiler_report_paths": fixed_result.get("profiler_report_paths", []),
            "automatic_diagnosis_counts": auto.get("diagnosis_counts", {}),
            "fixed_window_diagnosis_counts": fixed_result.get("diagnosis_counts", {}),
        }

    comparison_path = output_dir / f"comparison_{int(time.time())}.json"
    comparison_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    write_rq1_table(comparison, output_dir)
    return comparison_path


def write_rq1_table(comparison: dict[str, object], output_dir: Path) -> Path:
    table_path = output_dir / f"rq1_summary_table_{int(time.time())}.csv"
    fieldnames = [
        "workload",
        "automatic_windows",
        "fixed_window_windows",
        "automatic_suspicious_windows",
        "fixed_window_suspicious_windows",
        "automatic_profiler_bursts",
        "fixed_window_profiler_bursts",
        "automatic_profiler_duration_s",
        "fixed_window_profiler_duration_s",
        "profiler_duration_saved_s",
        "automatic_kernel_instances",
        "fixed_window_kernel_instances",
        "automatic_kernel_total_time_ns",
        "fixed_window_kernel_total_time_ns",
        "automatic_diagnosis_counts",
        "fixed_window_diagnosis_counts",
    ]
    rows = []
    workloads = comparison.get("workloads", {})
    if isinstance(workloads, dict):
        for workload, result in workloads.items():
            if not isinstance(result, dict):
                continue
            auto_duration = float(result.get("automatic_profiler_duration_s", 0) or 0)
            fixed_duration = float(result.get("fixed_window_profiler_duration_s", 0) or 0)
            rows.append(
                {
                    "workload": workload,
                    "automatic_windows": result.get("automatic_windows", 0),
                    "fixed_window_windows": result.get("fixed_window_windows", 0),
                    "automatic_suspicious_windows": result.get("automatic_suspicious_windows", 0),
                    "fixed_window_suspicious_windows": result.get("fixed_window_suspicious_windows", 0),
                    "automatic_profiler_bursts": result.get("automatic_profiler_bursts", 0),
                    "fixed_window_profiler_bursts": result.get("fixed_window_profiler_bursts", 0),
                    "automatic_profiler_duration_s": auto_duration,
                    "fixed_window_profiler_duration_s": fixed_duration,
                    "profiler_duration_saved_s": fixed_duration - auto_duration,
                    "automatic_kernel_instances": result.get("automatic_profiler_kernel_instances", 0),
                    "fixed_window_kernel_instances": result.get("fixed_window_profiler_kernel_instances", 0),
                    "automatic_kernel_total_time_ns": result.get("automatic_profiler_kernel_total_time_ns", 0),
                    "fixed_window_kernel_total_time_ns": result.get("fixed_window_profiler_kernel_total_time_ns", 0),
                    "automatic_diagnosis_counts": json.dumps(result.get("automatic_diagnosis_counts", {}), sort_keys=True),
                    "fixed_window_diagnosis_counts": json.dumps(result.get("fixed_window_diagnosis_counts", {}), sort_keys=True),
                }
            )
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return table_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=(*WORKLOADS, "all"), default="all")
    parser.add_argument("--mode", choices=(AUTOMATIC_MODE, BASELINE_MODE, COMPARE_MODE), default=AUTOMATIC_MODE)
    parser.add_argument("--enable-nsys-bursts", action="store_true")
    parser.add_argument("--extract-nsys-stats", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-nsys-bursts-per-workload", type=int, default=1)
    parser.add_argument("--fixed-window-bursts-per-workload", type=int, default=1)
    parser.add_argument("--stability-stop-windows", type=int, default=2)
    parser.add_argument("--nsys-path", default="nsys")
    parser.add_argument("--nsys-trace", default="cuda,nvtx,osrt")
    parser.add_argument("--nsys-burst-seconds", type=float, default=2.0)
    parser.add_argument("--fixed-window-nsys-seconds", type=float, default=5.0)
    parser.add_argument("--profile-target", choices=WORKLOADS)
    parser.add_argument("--duration-seconds", type=float, default=20.0)
    parser.add_argument("--window-seconds", type=float, default=5.0)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/runs"))
    parser.add_argument("--gemm-size", type=int, default=4096)
    parser.add_argument("--mixed-gemm-size", type=int, default=3072)
    parser.add_argument("--mixed-vector-size", type=int, default=16_777_216)
    parser.add_argument("--small-kernel-size", type=int, default=4096)
    parser.add_argument("--small-kernel-launches", type=int, default=128)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.10)
    parser.add_argument("--suspicious-gpu-util", type=float, default=60.0)
    parser.add_argument("--suspicious-mem-percent", type=float, default=70.0)
    parser.add_argument("--suspicious-launch-ops-per-s", type=float, default=50_000.0)
    parser.add_argument("--suspicious-latency-ratio", type=float, default=1.50)
    parser.add_argument("--suspicious-score", type=float, default=0.45)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA is not available")

    if args.profile_target:
        run_profile_target(args.profile_target, args)
        return

    workloads = WORKLOADS if args.workload == "all" else (args.workload,)

    if args.mode == COMPARE_MODE:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        summaries = {}
        for mode in (AUTOMATIC_MODE, BASELINE_MODE):
            phase_args = copy.copy(args)
            phase_args.mode = mode
            phase_output_dir = args.output_dir / mode
            phase_output_dir.mkdir(parents=True, exist_ok=True)
            csv_paths = []
            for workload in workloads:
                print(f"running mode={mode} workload={workload}", flush=True)
                csv_path = run_workload(workload, phase_args, phase_output_dir)
                print(f"wrote {csv_path}", flush=True)
                csv_paths.append(csv_path)
                torch.cuda.empty_cache()
            summaries[mode] = write_summary(csv_paths, phase_output_dir)
            print(f"wrote {summaries[mode]}", flush=True)
        comparison_path = write_comparison_summary(summaries[AUTOMATIC_MODE], summaries[BASELINE_MODE], args.output_dir)
        print(f"wrote {comparison_path}", flush=True)
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_paths = []
    for workload in workloads:
        print(f"running workload={workload}", flush=True)
        csv_path = run_workload(workload, args, args.output_dir)
        print(f"wrote {csv_path}", flush=True)
        csv_paths.append(csv_path)
        torch.cuda.empty_cache()

    summary_path = write_summary(csv_paths, args.output_dir)
    print(f"wrote {summary_path}", flush=True)


if __name__ == "__main__":
    main()
