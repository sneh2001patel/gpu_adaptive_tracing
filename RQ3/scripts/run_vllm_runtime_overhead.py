#!/usr/bin/env python3
"""Run vLLM runtime-overhead repetitions without Nsight profiling."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


RQ1_SCRIPTS = Path(__file__).resolve().parents[2] / "RQ1" / "scripts"
sys.path.insert(0, str(RQ1_SCRIPTS))
import run_vllm_smoke as smoke  # noqa: E402


MODES = ("no_profiler", "cheap_metrics_only")


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_percent(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else (numerator / denominator) * 100.0


def percentile(values: list[float], pct: float) -> float:
    return as_float(smoke.percentile(values, pct))


def request_metrics(records: list[smoke.RequestRecord]) -> dict[str, float]:
    latencies = [record.latency_ms for record in records]
    starts = [record.start_ts for record in records]
    ends = [record.end_ts for record in records]
    duration = max(ends) - min(starts) if starts and ends and max(ends) > min(starts) else 0.0
    return {
        "request_count": float(len(records)),
        "success_rate": safe_percent(sum(record.success for record in records), len(records)) if records else 0.0,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "throughput_rps": len(records) / duration if duration > 0 else 0.0,
        "prompt_tokens_mean": statistics.fmean([record.prompt_tokens_estimate for record in records]) if records else 0.0,
        "output_tokens_mean": statistics.fmean([record.output_tokens_estimate for record in records]) if records else 0.0,
        "duration_s": duration,
    }


def api_url(args: argparse.Namespace, path: str) -> str:
    return f"http://{args.host}:{args.port}{path}"


def wait_for_server(args: argparse.Namespace, log_path: Path) -> None:
    deadline = time.time() + args.server_timeout_seconds
    url = api_url(args, "/v1/models")
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(2)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.exists() else ""
    raise RuntimeError(f"vLLM server did not become ready: {last_error}\n{tail}")


def start_server(args: argparse.Namespace, output_dir: Path) -> tuple[subprocess.Popen[str], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "vllm_server.log"
    env = os.environ.copy()
    env["HF_HOME"] = args.hf_home
    env.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    command = [
        args.vllm_python,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        args.model,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--dtype",
        "auto",
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--max-model-len",
        str(args.max_model_len),
        "--max-num-seqs",
        str(args.max_num_seqs),
    ]
    log = log_path.open("w", encoding="utf-8")
    server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True, env=env)
    return server, log_path


def stop_server(server: subprocess.Popen[str]) -> None:
    server.send_signal(signal.SIGINT)
    try:
        server.wait(timeout=30)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=30)


def write_request_csv(path: Path, records: list[smoke.RequestRecord]) -> None:
    rows = [smoke.request_row(record) for record in records]
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_no_profiler(args: argparse.Namespace, mode_dir: Path) -> dict[str, Any]:
    mode_dir.mkdir(parents=True, exist_ok=True)
    scenario = smoke.SCENARIOS[args.scenario]
    records = smoke.run_scenario(args.scenario, scenario, args)
    request_path = mode_dir / f"{args.scenario}_requests_{int(time.time())}.csv"
    write_request_csv(request_path, records)
    return {
        "mode": "no_profiler",
        "status": "ok",
        "request_csv": str(request_path),
        **request_metrics(records),
    }


def run_cheap_metrics_only(args: argparse.Namespace, mode_dir: Path) -> dict[str, Any]:
    mode_dir.mkdir(parents=True, exist_ok=True)
    scenario = smoke.SCENARIOS[args.scenario]
    nvml = smoke.NvmlReader(args.gpu_index)
    sampler = smoke.MetricSampler(nvml, args.sample_interval_seconds)
    try:
        sampler.start()
        records = smoke.run_scenario(args.scenario, scenario, args)
        request_rows = [smoke.request_row(record) for record in records]
        window_rows = smoke.aggregate_windows(records, sampler, args.scenario, scenario, args)
    finally:
        sampler.stop()
        nvml.close()
    request_path = mode_dir / f"{args.scenario}_requests_{int(time.time())}.csv"
    window_path = mode_dir / f"{args.scenario}_windows_{int(time.time())}.csv"
    smoke.write_csv(request_path, request_rows)
    smoke.write_csv(window_path, window_rows)
    return {
        "mode": "cheap_metrics_only",
        "status": "ok",
        "request_csv": str(request_path),
        "window_csv": str(window_path),
        "window_count": len(window_rows),
        **request_metrics(records),
    }


def compare_modes(no_profiler: dict[str, Any], cheap_metrics: dict[str, Any]) -> dict[str, float]:
    p95_delta = as_float(cheap_metrics.get("p95_latency_ms")) - as_float(no_profiler.get("p95_latency_ms"))
    throughput_delta = as_float(cheap_metrics.get("throughput_rps")) - as_float(no_profiler.get("throughput_rps"))
    return {
        "p95_latency_delta_ms": p95_delta,
        "p95_latency_regression_percent": safe_percent(p95_delta, as_float(no_profiler.get("p95_latency_ms"))),
        "throughput_delta_rps": throughput_delta,
        "throughput_change_percent": safe_percent(throughput_delta, as_float(no_profiler.get("throughput_rps"))),
    }


def mode_order(args: argparse.Namespace, seed: int) -> list[str]:
    if args.mode_order == "no_profiler_first":
        return ["no_profiler", "cheap_metrics_only"]
    if args.mode_order == "cheap_metrics_first":
        return ["cheap_metrics_only", "no_profiler"]
    order = ["no_profiler", "cheap_metrics_only"]
    random.Random(seed).shuffle(order)
    return order


def run_repetition(args: argparse.Namespace, rep_index: int, seed: int) -> dict[str, Any]:
    rep_dir = args.output_dir / f"{args.scenario}_seed{seed}"
    args.seed = seed
    args.port = args.base_port + rep_index
    args.endpoint = api_url(args, "/v1/completions")
    server, log_path = start_server(args, rep_dir)
    try:
        wait_for_server(args, log_path)
        results: dict[str, dict[str, Any]] = {}
        order = mode_order(args, seed)
        for index, mode in enumerate(order):
            if index > 0 and args.cooldown_seconds > 0:
                time.sleep(args.cooldown_seconds)
            if mode == "no_profiler":
                results[mode] = run_no_profiler(args, rep_dir / mode)
            elif mode == "cheap_metrics_only":
                results[mode] = run_cheap_metrics_only(args, rep_dir / mode)
            else:
                raise RuntimeError(f"Unknown mode {mode}")
    finally:
        stop_server(server)
    no_profiler = results["no_profiler"]
    cheap_metrics = results["cheap_metrics_only"]
    comparison = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": args.model,
        "scenario": args.scenario,
        "seed": seed,
        "port": args.port,
        "duration_seconds": args.duration_seconds,
        "mode_order": order,
        "no_profiler": no_profiler,
        "cheap_metrics_only": cheap_metrics,
        "comparison": compare_modes(no_profiler, cheap_metrics),
    }
    comparison_path = rep_dir / f"runtime_overhead_comparison_{int(time.time())}.json"
    comparison_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    return {"comparison_path": str(comparison_path), **comparison}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--scenario", choices=smoke.SCENARIOS.keys(), default="queue_pressure")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--base-port", type=int, default=8061)
    parser.add_argument("--port", type=int, default=8061)
    parser.add_argument("--vllm-python", default="/venv/vllm/bin/python")
    parser.add_argument("--hf-home", default="/dev/shm/hf-cache")
    parser.add_argument("--output-dir", type=Path, default=Path("RQ3/runs/vllm_runtime_overhead"))
    parser.add_argument("--duration-seconds", type=float, default=30.0)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--request-pause-seconds", type=float, default=0.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.10)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--seeds", nargs="+", type=int, default=[6101, 6102, 6103])
    parser.add_argument("--server-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--cooldown-seconds", type=float, default=5.0)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.82)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=32)
    parser.add_argument("--suspicious-latency-ratio", type=float, default=1.50)
    parser.add_argument("--queue-pressure-latency-ratio", type=float, default=1.25)
    parser.add_argument("--queue-delay-pressure-ms", type=float, default=250.0)
    parser.add_argument("--queue-delay-recovery-ms", type=float, default=100.0)
    parser.add_argument("--suspicious-gpu-util", type=float, default=60.0)
    parser.add_argument("--recovery-latency-ratio", type=float, default=1.10)
    parser.add_argument("--recovery-gpu-util", type=float, default=60.0)
    parser.add_argument("--throughput-recovery-ratio", type=float, default=0.95)
    parser.add_argument(
        "--mode-order",
        choices=("no_profiler_first", "cheap_metrics_first", "randomized"),
        default="no_profiler_first",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for rep_index, seed in enumerate(args.seeds):
        print(f"running scenario={args.scenario} seed={seed} port={args.base_port + rep_index}", flush=True)
        records.append(run_repetition(args, rep_index, seed))
    summary_path = args.output_dir / f"runtime_overhead_summary_{int(time.time())}.json"
    summary_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "model": args.model,
                "scenario": args.scenario,
                "seeds": args.seeds,
                "mode_order": args.mode_order,
                "records": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {summary_path}", flush=True)


if __name__ == "__main__":
    main()
