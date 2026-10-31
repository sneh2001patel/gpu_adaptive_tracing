#!/usr/bin/env python3
"""Stream synthetic cheap windows through a fake GPU-profiler episode controller.

This is a behavior simulation, not a CPU/GPU performance comparison. Fixture
selection and fake summaries live outside controller/classifier input metadata.
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.policies import POLICIES
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import ManualClock, TimingRecorder
from revision.tracing.windows import CheapWindow, HealthyBaseline


def run_demo(scenario: str, policy: str) -> tuple[StreamingController, list[CheapWindow]]:
    clock = ManualClock()
    recorder = TimingRecorder(clock, provenance="synthetic_simulation")
    backend = FakeProfilerBackend(recorder)
    count = 0

    def start_attempt(capture_id, window):
        nonlocal count
        name = "gemm"
        if scenario == "unknown" or (scenario == "ambiguous_first" and count == 0):
            name = "unresolved"
        elif scenario == "changing" and count >= 2:
            name = "prefill"
        count += 1
        backend.start(capture_id, FakeCapturePlan(startup_s=0.2, finalization_s=0.2,
                      stats_s=0.2, parse_s=0.1, kernel_summary={"top_kernel_name": name}))

    def classify(summary):
        return {"gemm": "compute_bound", "prefill": "vllm_long_prompt"}.get(summary.get("top_kernel_name"))

    config = ControllerConfig(policy=policy, burst_s=1, cooldown_s=2,
                              startup_timeout_s=0.1 if scenario == "timeout" else 5)
    controller = StreamingController(backend, HealthyBaseline(100, "synthetic-calibration", 1),
                                     classify, start_attempt, config)
    windows = []
    for second in range(1, 31):
        deadline = second * 1_000_000_000
        # Cheap-window arrival wins ties with backend polling, so the controller
        # can use every observation actually available at this timestamp.
        for _ in range(1000):
            wake = controller.next_wakeup_ns()
            if wake is None or wake >= deadline:
                break
            clock.advance_to(wake)
            controller.tick()
        else:
            raise RuntimeError("Synthetic scheduler did not make progress")
        clock.advance_to(deadline)
        anomalous = scenario != "healthy" and 4 <= second <= 18
        latency = 400 if anomalous and scenario == "changing" and second >= 12 else 200 if anomalous else 100
        window = CheapWindow(f"window-{second}", deadline - 1_000_000_000, deadline,
                             deadline, clock.domain, latency, 95 if anomalous else 20, 10, 1)
        windows.append(window)
        controller.on_window(window)
    controller.finish()
    return controller, windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("healthy", "stable", "ambiguous_first", "changing", "unknown", "timeout"), default="stable")
    parser.add_argument("--policy", choices=POLICIES, default="stability_stop")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = (args.output_dir or ROOT / "revision/examples/streaming" / args.scenario / args.policy).resolve()
    output.relative_to((ROOT / "revision").resolve())
    controller, windows = run_demo(args.scenario, args.policy)
    payload = controller.snapshot()
    payload.update(gpu_used=False, cpu_role="simulation_execution_not_experimental_baseline",
                   healthy_baseline_role="latency_calibration_reference_not_hardware_baseline",
                   note="Synthetic mechanics only. No GPU savings, overhead, or diagnostic accuracy established.")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    (output / "controller_events.jsonl").write_text(controller.jsonl())
    (output / "timing_events.jsonl").write_text(controller.recorder.jsonl())
    (output / "input_windows.jsonl").write_text("".join(json.dumps(asdict(window)) + "\n" for window in windows))
    print(f"Synthetic {args.scenario}: {len(controller.episodes)} episodes, "
          f"{sum(len(e.attempts) for e in controller.episodes)} capture attempts; output: {output}")


if __name__ == "__main__":
    main()
