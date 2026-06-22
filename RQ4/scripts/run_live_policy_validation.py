#!/usr/bin/env python3
"""Run live vLLM/Nsight validation for RQ4 policy-selected trace windows."""

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


DEFAULT_POLICIES = (
    "fixed_burst",
    "repeated_fixed_burst",
    "stability_stop",
    "marginal_utility_stop",
    "counter_recovery_stop",
    "hybrid_stop",
)


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def api_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}{path}"


def wait_for_server(host: str, port: int, timeout_seconds: float, log_path: Path) -> None:
    deadline = time.time() + timeout_seconds
    url = api_url(host, port, "/v1/models")
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


def load_policy_jobs(detail_csv: Path, scenarios: set[str], seeds: set[str], policies: set[str]) -> list[dict[str, Any]]:
    jobs = []
    with detail_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            scenario = str(row.get("scenario", ""))
            seed = str(row.get("seed", ""))
            policy = str(row.get("policy", ""))
            if scenarios and scenario not in scenarios:
                continue
            if seeds and seed not in seeds:
                continue
            if policies and policy not in policies:
                continue
            duration = as_float(row.get("heavy_trace_duration_s"))
            if duration <= 0:
                duration = max(as_int(row.get("selected_windows")), 1) * 10.0
            jobs.append(
                {
                    "scenario": scenario,
                    "seed": seed,
                    "policy": policy,
                    "expected_label": row.get("expected_label", ""),
                    "selected_windows": as_int(row.get("selected_windows")),
                    "heavy_trace_duration_s": duration,
                    "replay_top1_correct": as_int(row.get("top1_correct")),
                    "replay_ever_correct": as_int(row.get("ever_correct")),
                    "replay_premature_stop": as_int(row.get("premature_stop")),
                    "replay_re_escalation_needed": as_int(row.get("re_escalation_needed")),
                    "replay_diagnosis_sequence": row.get("diagnosis_sequence", ""),
                }
            )
    return sorted(jobs, key=lambda job: (job["scenario"], int(job["seed"] or 0), job["policy"]))


def job_output_dir(root: Path, job: dict[str, Any]) -> Path:
    return root / str(job["scenario"]) / f"seed{job['seed']}" / str(job["policy"])


def result_is_ok(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("status") == "ok" and data.get("kernel_summary", {}).get("status") == "ok"


def run_profile_target(args: argparse.Namespace) -> None:
    mode_dir = args.output_dir
    mode_dir.mkdir(parents=True, exist_ok=True)
    log_path = mode_dir / "vllm_server.log"
    endpoint = api_url(args.host, args.port, "/v1/completions")
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
            wait_for_server(args.host, args.port, args.server_timeout_seconds, log_path)
            cuda_profiler_call("cudaProfilerStart")
            client_command = [
                args.client_python,
                str(Path(__file__).parents[1] / ".." / "RQ1" / "scripts" / "run_vllm_smoke.py"),
                "--model",
                args.model,
                "--endpoint",
                endpoint,
                "--scenario",
                args.scenario,
                "--duration-seconds",
                str(args.duration_seconds),
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


def extract_kernel_summary(report_path: Path, nsys_path: str) -> dict[str, Any]:
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
        summary = {"status": "no_kernel_table", "returncode": completed.returncode, "stats_path": str(stats_path)}
        stats_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    rows = list(csv.DictReader(io.StringIO("\n".join(lines[header_idx:]))))
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


def load_smoke_metrics(smoke_dir: Path, scenario: str) -> dict[str, Any]:
    paths = sorted(smoke_dir.glob("vllm_smoke_summary_*.json"))
    if not paths:
        return {"smoke_summary_paths": [], "request_count": 0.0, "success_rate": 0.0}
    data = json.loads(paths[-1].read_text(encoding="utf-8"))
    summary = data.get("scenarios", {}).get(scenario, {})
    request_csv = Path(summary.get("request_csv", ""))
    if request_csv.exists():
        request_rows = list(csv.DictReader(request_csv.open("r", newline="", encoding="utf-8")))
    else:
        request_rows = []
    latencies = [as_float(row.get("request_latency_ms")) for row in request_rows if as_float(row.get("request_latency_ms")) > 0]
    starts = [as_float(row.get("request_start_ts")) for row in request_rows if as_float(row.get("request_start_ts")) > 0]
    ends = [as_float(row.get("request_end_ts")) for row in request_rows if as_float(row.get("request_end_ts")) > 0]
    duration_s = max(ends) - min(starts) if starts and ends and max(ends) > min(starts) else 0.0
    return {
        "smoke_summary_paths": [str(path) for path in paths],
        "request_count": as_float(summary.get("request_count")),
        "success_rate": as_float(summary.get("success_rate")),
        "request_csv": str(request_csv) if request_csv else "",
        "p95_latency_ms": percentile(latencies, 0.95),
        "throughput_rps": len(request_rows) / duration_s if duration_s > 0 else 0.0,
    }


def run_live_job(job: dict[str, Any], index: int, args: argparse.Namespace) -> dict[str, Any]:
    out_dir = job_output_dir(args.output_dir, job)
    result_path = out_dir / "live_policy_result.json"
    if not args.force and result_is_ok(result_path):
        return json.loads(result_path.read_text(encoding="utf-8"))

    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = out_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    nsys_path = shutil.which(args.nsys_path) or args.nsys_path
    port = args.base_port + index
    output_prefix = profiles_dir / f"vllm_{job['scenario']}_{job['policy']}_seed{job['seed']}_{int(time.time())}"
    target_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile-target",
        "--model",
        args.model,
        "--scenario",
        str(job["scenario"]),
        "--seed",
        str(job["seed"]),
        "--host",
        args.host,
        "--port",
        str(port),
        "--vllm-python",
        args.vllm_python,
        "--client-python",
        args.client_python,
        "--hf-home",
        args.hf_home,
        "--output-dir",
        str(out_dir),
        "--duration-seconds",
        str(job["heavy_trace_duration_s"]),
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
    ]
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
        *target_command,
    ]
    start = time.time()
    timeout = args.server_timeout_seconds + as_float(job["heavy_trace_duration_s"]) + 180
    completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=timeout)
    duration_s = time.time() - start
    (out_dir / "nsys_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (out_dir / "nsys_stderr.log").write_text(completed.stderr, encoding="utf-8")
    report_paths = sorted(profiles_dir.glob(f"{output_prefix.name}*.nsys-rep"))
    kernel_summary = extract_kernel_summary(report_paths[0], nsys_path) if report_paths else {}
    smoke_metrics = load_smoke_metrics(out_dir / "smoke", str(job["scenario"]))
    result = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "ok" if completed.returncode == 0 and report_paths and kernel_summary.get("status") == "ok" else "failed",
        "returncode": completed.returncode,
        "model": args.model,
        "scenario": job["scenario"],
        "seed": as_int(job["seed"]),
        "policy": job["policy"],
        "expected_label": job.get("expected_label", ""),
        "selected_windows": job.get("selected_windows", 0),
        "requested_trace_duration_s": job.get("heavy_trace_duration_s", 0.0),
        "wall_duration_s": duration_s,
        "port": port,
        "report_paths": [str(path) for path in report_paths],
        "kernel_summary": kernel_summary,
        "smoke_metrics": smoke_metrics,
        "replay": {
            "top1_correct": job.get("replay_top1_correct", 0),
            "ever_correct": job.get("replay_ever_correct", 0),
            "premature_stop": job.get("replay_premature_stop", 0),
            "re_escalation_needed": job.get("replay_re_escalation_needed", 0),
            "diagnosis_sequence": job.get("replay_diagnosis_sequence", ""),
        },
        "stderr_tail": completed.stderr[-2000:],
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def write_summary(results: list[dict[str, Any]], args: argparse.Namespace) -> Path:
    path = args.output_dir / f"live_policy_summary_{int(time.time())}.json"
    aggregate: dict[str, dict[str, Any]] = {}
    for policy in sorted({str(result.get("policy", "")) for result in results}):
        group = [result for result in results if result.get("policy") == policy]
        ok = [result for result in group if result.get("status") == "ok"]
        aggregate[policy] = {
            "runs": len(group),
            "ok_runs": len(ok),
            "mean_requested_trace_duration_s": sum(as_float(r.get("requested_trace_duration_s")) for r in group) / len(group)
            if group
            else 0.0,
            "mean_wall_duration_s": sum(as_float(r.get("wall_duration_s")) for r in group) / len(group) if group else 0.0,
            "mean_kernel_instances": sum(as_float(r.get("kernel_summary", {}).get("kernel_instances")) for r in ok) / len(ok)
            if ok
            else 0.0,
            "mean_success_rate": sum(as_float(r.get("smoke_metrics", {}).get("success_rate")) for r in ok) / len(ok)
            if ok
            else 0.0,
        }
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detail_csv": str(args.policy_detail),
        "output_dir": str(args.output_dir),
        "job_count": len(results),
        "ok_count": sum(1 for result in results if result.get("status") == "ok"),
        "aggregate_by_policy": aggregate,
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-detail", type=Path, default=Path("RQ4/analysis/policy_stress_l4_vllm/rq4_policy_detail_1781806067.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("RQ4/runs/live_policy_validation_l4_vllm"))
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--scenarios", nargs="*", default=[])
    parser.add_argument("--seeds", nargs="*", default=[])
    parser.add_argument("--policies", nargs="*", default=list(DEFAULT_POLICIES))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--base-port", type=int, default=8101)
    parser.add_argument("--vllm-python", default="/venv/vllm/bin/python3")
    parser.add_argument("--client-python", default="/venv/main/bin/python")
    parser.add_argument("--hf-home", default="/dev/shm/hf-cache")
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--server-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--nsys-path", default="/opt/nvidia/nsight-systems/2024.6.2/bin/nsys")
    parser.add_argument("--nsys-trace", default="cuda,nvtx,osrt")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.82)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=32)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--profile-target", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--scenario", default="", help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--duration-seconds", type=float, default=0.0, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.profile_target:
        run_profile_target(args)
        return

    jobs = load_policy_jobs(args.policy_detail, set(args.scenarios), set(args.seeds), set(args.policies))
    if args.limit:
        jobs = jobs[: args.limit]
    if not jobs:
        raise SystemExit("No live RQ4 jobs selected")
    if args.dry_run:
        for job in jobs:
            print(
                f"{job['scenario']} seed={job['seed']} policy={job['policy']} "
                f"duration={job['heavy_trace_duration_s']:.3f}s"
            )
        print(f"jobs={len(jobs)}")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, job in enumerate(jobs):
        print(
            f"[{index + 1}/{len(jobs)}] scenario={job['scenario']} seed={job['seed']} "
            f"policy={job['policy']} duration={job['heavy_trace_duration_s']:.3f}s",
            flush=True,
        )
        results.append(run_live_job(job, index, args))
        summary_path = write_summary(results, args)
        print(f"updated {summary_path}", flush=True)
    summary_path = write_summary(results, args)
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
