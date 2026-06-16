#!/usr/bin/env python3
"""Write reproducibility manifests for RQ1 repetition directories."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch


def run_command(command: list[str], timeout: int = 15) -> str:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (completed.stdout or completed.stderr).strip()


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def environment() -> dict[str, Any]:
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "torch_cuda_available": torch.cuda.is_available(),
        "gpu_name": gpu_name,
        "nvidia_smi": first_line(run_command(["nvidia-smi", "--query-gpu=driver_version,name", "--format=csv,noheader"])),
        "nsys_version": first_line(run_command(["nsys", "--version"])),
    }


def run_files(run_dir: Path) -> dict[str, list[str]]:
    return {
        "comparison_files": sorted(str(path) for path in run_dir.glob("comparison_*.json")),
        "summary_files": sorted(str(path) for path in run_dir.glob("*/summary_*.json")),
        "window_csv_files": sorted(str(path) for path in run_dir.glob("*/*.csv")),
        "nsight_reports": sorted(str(path) for path in run_dir.glob("*/profiles/*.nsys-rep")),
        "kernel_summary_files": sorted(str(path) for path in run_dir.glob("*/profiles/*.kernel_summary.json")),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--duration-seconds", type=float, default=20.0)
    parser.add_argument("--window-seconds", type=float, default=5.0)
    parser.add_argument("--nsys-burst-seconds", type=float, default=2.0)
    parser.add_argument("--fixed-window-nsys-seconds", type=float, default=8.0)
    parser.add_argument("--max-nsys-bursts-per-workload", type=int, default=1)
    parser.add_argument("--fixed-window-bursts-per-workload", type=int, default=1)
    parser.add_argument("--stability-stop-windows", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = environment()
    command_settings = {
        "mode": "compare",
        "workload": "all",
        "duration_seconds": args.duration_seconds,
        "window_seconds": args.window_seconds,
        "enable_nsys_bursts": True,
        "nsys_burst_seconds": args.nsys_burst_seconds,
        "fixed_window_nsys_seconds": args.fixed_window_nsys_seconds,
        "max_nsys_bursts_per_workload": args.max_nsys_bursts_per_workload,
        "fixed_window_bursts_per_workload": args.fixed_window_bursts_per_workload,
        "stability_stop_windows": args.stability_stop_windows,
    }

    for run_dir in args.run_dir:
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "run_dir": str(run_dir),
            "command_settings": command_settings,
            "environment": env,
            "artifacts": run_files(run_dir),
        }
        path = run_dir / "experiment_manifest.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
