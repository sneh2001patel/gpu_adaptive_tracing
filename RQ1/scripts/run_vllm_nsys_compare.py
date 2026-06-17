#!/usr/bin/env python3
"""Compare automatic and fixed-window Nsight bursts around a vLLM smoke workload."""

from __future__ import annotations

import argparse
import csv
import ctypes
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


AUTOMATIC_MODE = "automatic"
FIXED_WINDOW_MODE = "fixed_window"
MODES = (AUTOMATIC_MODE, FIXED_WINDOW_MODE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--scenario", default="queue_pressure")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--vllm-python", default="/venv/vllm/bin/python")
    parser.add_argument("--client-python", default=sys.executable)
    parser.add_argument("--hf-home", default="/dev/shm/hf-cache")
    parser.add_argument("--output-dir", type=Path, default=Path("RQ1/runs/vllm_l4_nsys_compare"))
    parser.add_argument("--automatic-smoke-seconds", type=float, default=12.0)
    parser.add_argument("--fixed-window-smoke-seconds", type=float, default=24.0)
    parser.add_argument("--window-seconds", type=float, default=6.0)
    parser.add_argument("--server-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--nsys-path", default="nsys")
    parser.add_argument("--nsys-trace", default="cuda,nvtx,osrt")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.82)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=32)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile-target-mode", choices=MODES)
    return parser.parse_args()


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


def cuda_profiler_call(name: str) -> None:
    cudart = ctypes.CDLL("libcudart.so")
    fn = getattr(cudart, name)
    rc = fn()
    if rc != 0:
        raise RuntimeError(f"{name} failed with CUDA error {rc}")


def smoke_duration(args: argparse.Namespace) -> float:
    if args.profile_target_mode == AUTOMATIC_MODE:
        return args.automatic_smoke_seconds
    return args.fixed_window_smoke_seconds


def run_profile_target(args: argparse.Namespace) -> None:
    mode_dir = args.output_dir / args.profile_target_mode
    mode_dir.mkdir(parents=True, exist_ok=True)
    log_path = mode_dir / "vllm_server.log"
    endpoint = api_url(args, "/v1/completions")
    env = os.environ.copy()
    env["HF_HOME"] = args.hf_home
    env.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    server_command = [
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
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(server_command, stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            wait_for_server(args, log_path)
            cuda_profiler_call("cudaProfilerStart")
            client_command = [
                args.client_python,
                str(Path(__file__).with_name("run_vllm_smoke.py")),
                "--model",
                args.model,
                "--endpoint",
                endpoint,
                "--scenario",
                args.scenario,
                "--duration-seconds",
                str(smoke_duration(args)),
                "--window-seconds",
                str(args.window_seconds),
                "--request-timeout-seconds",
                str(args.request_timeout_seconds),
                "--seed",
                str(args.seed),
                "--output-dir",
                str(mode_dir / "smoke"),
            ]
            completed = subprocess.run(client_command, check=False, text=True, capture_output=True, env=env)
            (mode_dir / "client_stdout.log").write_text(completed.stdout, encoding="utf-8")
            (mode_dir / "client_stderr.log").write_text(completed.stderr, encoding="utf-8")
            cuda_profiler_call("cudaProfilerStop")
            if completed.returncode != 0:
                raise RuntimeError(f"smoke client failed with return code {completed.returncode}")
        finally:
            server.send_signal(signal.SIGINT)
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=30)


def run_nsys_mode(mode: str, args: argparse.Namespace) -> dict[str, Any]:
    mode_dir = args.output_dir / mode
    profiles_dir = mode_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    nsys_path = shutil.which(args.nsys_path) or args.nsys_path
    output_prefix = profiles_dir / f"vllm_{args.scenario}_{mode}_{int(time.time())}"
    command = [
        nsys_path,
        "profile",
        "--trace",
        args.nsys_trace,
        "--capture-range",
        "cudaProfilerApi",
        "--capture-range-end",
        "stop",
        "--sample",
        "none",
        "--cpuctxsw",
        "none",
        "--force-overwrite",
        "true",
        "--output",
        str(output_prefix),
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile-target-mode",
        mode,
        "--model",
        args.model,
        "--scenario",
        args.scenario,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--vllm-python",
        args.vllm_python,
        "--client-python",
        args.client_python,
        "--hf-home",
        args.hf_home,
        "--output-dir",
        str(args.output_dir),
        "--automatic-smoke-seconds",
        str(args.automatic_smoke_seconds),
        "--fixed-window-smoke-seconds",
        str(args.fixed_window_smoke_seconds),
        "--window-seconds",
        str(args.window_seconds),
        "--server-timeout-seconds",
        str(args.server_timeout_seconds),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--max-model-len",
        str(args.max_model_len),
        "--max-num-seqs",
        str(args.max_num_seqs),
        "--request-timeout-seconds",
        str(args.request_timeout_seconds),
        "--seed",
        str(args.seed),
    ]
    start = time.time()
    completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=args.server_timeout_seconds + smoke_duration_for_mode(mode, args) + 120)
    duration_s = time.time() - start
    (mode_dir / "nsys_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (mode_dir / "nsys_stderr.log").write_text(completed.stderr, encoding="utf-8")
    report_paths = sorted(str(path) for path in profiles_dir.glob(f"{output_prefix.name}*.nsys-rep"))
    kernel_summary = extract_kernel_summary(Path(report_paths[0]), args) if report_paths else {}
    return {
        "mode": mode,
        "status": "ok" if completed.returncode == 0 and report_paths else "failed",
        "returncode": completed.returncode,
        "duration_s": duration_s,
        "output_prefix": str(output_prefix),
        "report_paths": report_paths,
        "kernel_summary": kernel_summary,
        "smoke_summary_paths": sorted(str(path) for path in (mode_dir / "smoke").glob("vllm_smoke_summary_*.json")),
        "stderr_tail": completed.stderr[-2000:],
    }


def smoke_duration_for_mode(mode: str, args: argparse.Namespace) -> float:
    return args.automatic_smoke_seconds if mode == AUTOMATIC_MODE else args.fixed_window_smoke_seconds


def extract_kernel_summary(report_path: Path, args: argparse.Namespace) -> dict[str, Any]:
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
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    stats_path = report_path.with_suffix(".kernel_summary.json")
    if completed.returncode != 0:
        summary = {
            "status": "failed",
            "returncode": completed.returncode,
            "stats_path": str(stats_path),
            "stderr_tail": completed.stderr[-2000:],
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
    instances = sum(int(float(row.get("Instances", 0) or 0)) for row in rows)
    total_time_ns = sum(float(row.get("Total Time (ns)", 0) or 0) for row in rows)
    summary = {
        "status": "ok",
        "returncode": completed.returncode,
        "stats_path": str(stats_path),
        "kernel_count": len(rows),
        "kernel_instances": instances,
        "kernel_total_time_ns": total_time_ns,
        "kernel_avg_duration_ns": total_time_ns / instances if instances else 0.0,
        "top_kernel_name": rows[0].get("Name", "") if rows else "",
    }
    stats_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def write_comparison(results: dict[str, dict[str, Any]], args: argparse.Namespace) -> Path:
    automatic = results.get(AUTOMATIC_MODE, {})
    fixed = results.get(FIXED_WINDOW_MODE, {})
    automatic_duration = float(automatic.get("duration_s") or 0)
    fixed_duration = float(fixed.get("duration_s") or 0)
    comparison = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": args.model,
        "scenario": args.scenario,
        "seed": args.seed,
        "port": args.port,
        "automatic": automatic,
        "fixed_window": fixed,
        "profiler_duration_saved_s": fixed_duration - automatic_duration,
        "profiler_duration_saved_percent": ((fixed_duration - automatic_duration) / fixed_duration * 100) if fixed_duration else 0.0,
    }
    path = args.output_dir / f"vllm_nsys_comparison_{int(time.time())}.json"
    path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    write_table(comparison, args.output_dir)
    return path


def write_table(comparison: dict[str, Any], output_dir: Path) -> Path:
    path = output_dir / f"vllm_nsys_summary_table_{int(time.time())}.csv"
    fieldnames = [
        "scenario",
        "automatic_status",
        "fixed_window_status",
        "automatic_duration_s",
        "fixed_window_duration_s",
        "profiler_duration_saved_s",
        "profiler_duration_saved_percent",
        "automatic_kernel_instances",
        "fixed_window_kernel_instances",
        "automatic_kernel_total_time_ns",
        "fixed_window_kernel_total_time_ns",
    ]
    automatic = comparison["automatic"]
    fixed = comparison["fixed_window"]
    row = {
        "scenario": comparison["scenario"],
        "automatic_status": automatic.get("status", ""),
        "fixed_window_status": fixed.get("status", ""),
        "automatic_duration_s": automatic.get("duration_s", 0),
        "fixed_window_duration_s": fixed.get("duration_s", 0),
        "profiler_duration_saved_s": comparison.get("profiler_duration_saved_s", 0),
        "profiler_duration_saved_percent": comparison.get("profiler_duration_saved_percent", 0),
        "automatic_kernel_instances": automatic.get("kernel_summary", {}).get("kernel_instances", 0),
        "fixed_window_kernel_instances": fixed.get("kernel_summary", {}).get("kernel_instances", 0),
        "automatic_kernel_total_time_ns": automatic.get("kernel_summary", {}).get("kernel_total_time_ns", 0),
        "fixed_window_kernel_total_time_ns": fixed.get("kernel_summary", {}).get("kernel_total_time_ns", 0),
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    return path


def port_is_free(args: argparse.Namespace) -> bool:
    try:
        urllib.request.urlopen(api_url(args, "/v1/models"), timeout=1)
        return False
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError:
        return True


def main() -> None:
    args = parse_args()
    if args.profile_target_mode:
        run_profile_target(args)
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not port_is_free(args):
        raise RuntimeError(f"Port {args.port} already has a server; choose a free port.")
    results = {}
    for mode in MODES:
        print(f"running vLLM Nsight mode={mode} scenario={args.scenario}", flush=True)
        results[mode] = run_nsys_mode(mode, args)
        print(f"mode={mode} status={results[mode]['status']}", flush=True)
    comparison_path = write_comparison(results, args)
    print(f"wrote {comparison_path}", flush=True)


if __name__ == "__main__":
    main()
