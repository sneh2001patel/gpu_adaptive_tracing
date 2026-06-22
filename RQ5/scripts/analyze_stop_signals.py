#!/usr/bin/env python3
"""Analyze which runtime signals best predict useful stopping decisions."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any


EXPECTED_LABELS = {
    "healthy": "vllm_healthy",
    "queue_pressure": "vllm_queue_pressure",
    "long_prompt": "vllm_long_prompt",
    "long_output": "vllm_long_output",
    "compute_saturation": "vllm_compute_saturation",
    "kv_cache_pressure": "vllm_kv_cache_pressure",
}


SIGNALS = (
    "diagnosis_stable_2",
    "diagnosis_changed_from_previous",
    "diagnosis_confident",
    "diagnosis_margin_clear",
    "latency_recovered",
    "queue_delay_recovered",
    "gpu_util_recovered",
    "memory_pressure_low",
    "throughput_recovered",
    "queue_pressure_low",
    "kernel_duration_stable",
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


def safe_div(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def scenario_seed_from_path(path: Path) -> tuple[str, str]:
    scenario = path.name.split("_windows_")[0]
    seed = ""
    for part in path.parts:
        if "_seed" in part:
            seed = part.rsplit("_seed", 1)[-1]
    return scenario, seed


def iter_window_files(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*_windows_*.csv")
        if "automatic" in path.parts
        and not path.name.startswith("all_windows_")
        and path.name.split("_windows_")[0] in EXPECTED_LABELS
    )


def is_suspicious(row: dict[str, str]) -> bool:
    return as_int(row.get("trigger_trace")) == 1 or row.get("controller_state") == "suspicious"


def diagnosis(row: dict[str, str]) -> str:
    return str(row.get("diagnosis_label", ""))


def stable_streak(rows: list[dict[str, str]], index: int) -> int:
    current = diagnosis(rows[index])
    if not current:
        return 0
    streak = 0
    for row in reversed(rows[: index + 1]):
        if diagnosis(row) != current:
            break
        streak += 1
    return streak


def baseline_throughput(rows: list[dict[str, str]]) -> float:
    values = [as_float(row.get("request_throughput_rps")) for row in rows[:2]]
    return mean([value for value in values if value > 0])


def signal_record(
    rows: list[dict[str, str]],
    index: int,
    scenario: str,
    seed: str,
    args: argparse.Namespace,
    throughput_baseline: float,
) -> dict[str, Any]:
    row = rows[index]
    expected = EXPECTED_LABELS[scenario]
    previous_label = diagnosis(rows[index - 1]) if index > 0 else ""
    latency_ratio = as_float(row.get("latency_ratio_vs_baseline"))
    gpu_util = as_float(row.get("gpu_util_percent_mean"))
    mem_used = as_float(row.get("gpu_memory_used_percent_mean"))
    throughput = as_float(row.get("request_throughput_rps"))
    queue_score = as_float(row.get("queue_pressure_score"))
    queue_delay_p95 = as_float(row.get("queue_delay_proxy_p95_ms"))
    throughput_ratio = as_float(row.get("request_throughput_ratio_vs_baseline")) or safe_div(throughput, throughput_baseline)
    confidence = as_float(row.get("diagnosis_confidence"))
    margin = as_float(row.get("diagnosis_rank_margin"))
    stable_count = as_int(row.get("diagnosis_stability_streak")) or stable_streak(rows, index)
    kernel_stable = as_int(row.get("kernel_duration_stable"))
    return {
        "scenario": scenario,
        "seed": seed,
        "window_id": as_int(row.get("window_id")),
        "expected_label": expected,
        "diagnosis_label": diagnosis(row),
        "target_correct_stop": int(diagnosis(row) == expected),
        "target_ambiguous_stop": int("unknown" in diagnosis(row) or diagnosis(row) == ""),
        "diagnosis_stable_2": int(stable_count >= 2),
        "diagnosis_changed_from_previous": as_int(row.get("diagnosis_changed_from_previous"))
        if row.get("diagnosis_changed_from_previous", "") != ""
        else int(index > 0 and diagnosis(row) != previous_label),
        "diagnosis_confident": int(confidence >= args.diagnosis_confidence_threshold),
        "diagnosis_margin_clear": int(margin >= args.diagnosis_margin_threshold),
        "latency_recovered": int(latency_ratio == 0.0 or latency_ratio <= args.recovery_latency_ratio),
        "queue_delay_recovered": int(queue_delay_p95 == 0.0 or queue_delay_p95 <= args.queue_delay_recovery_ms),
        "gpu_util_recovered": int(gpu_util == 0.0 or gpu_util <= args.recovery_gpu_util),
        "memory_pressure_low": int(mem_used == 0.0 or mem_used <= args.memory_pressure_threshold),
        "throughput_recovered": int(throughput_baseline <= 0 or throughput_ratio >= args.throughput_recovery_ratio),
        "queue_pressure_low": int(queue_score == 0.0 or queue_score <= args.queue_pressure_threshold),
        "kernel_duration_stable": kernel_stable,
        "latency_ratio_vs_baseline": latency_ratio,
        "queue_delay_proxy_p95_ms": queue_delay_p95,
        "gpu_util_percent_mean": gpu_util,
        "gpu_memory_used_percent_mean": mem_used,
        "request_throughput_rps": throughput,
        "throughput_ratio_vs_baseline": throughput_ratio,
        "queue_pressure_score": queue_score,
        "diagnosis_confidence": confidence,
        "diagnosis_rank_margin": margin,
        "kernel_duration_cv": as_float(row.get("kernel_duration_cv")),
        "kernel_duration_stability_delta_percent": as_float(row.get("kernel_duration_stability_delta_percent")),
    }


def build_signal_rows(input_root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    records = []
    for path in iter_window_files(input_root):
        scenario, seed = scenario_seed_from_path(path)
        rows = [row for row in load_csv(path) if is_suspicious(row)]
        if not rows:
            continue
        rows.sort(key=lambda row: as_int(row.get("window_id")))
        throughput_base = baseline_throughput(rows)
        for index in range(len(rows)):
            records.append(signal_record(rows, index, scenario, seed, args, throughput_base))
    return records


def confusion(rows: list[dict[str, Any]], signal: str, target: str) -> dict[str, float]:
    tp = fp = tn = fn = 0
    for row in rows:
        pred = as_int(row.get(signal)) == 1
        actual = as_int(row.get(target)) == 1
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif not pred and actual:
            fn += 1
        else:
            tn += 1
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    specificity = safe_div(tn, tn + fp)
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "support": tp + fn,
        "predicted_positive": tp + fp,
    }


def point_biserial(rows: list[dict[str, Any]], value_key: str, target_key: str) -> float:
    pairs = [(as_float(row.get(value_key)), as_float(row.get(target_key))) for row in rows]
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    if not xs or len(set(ys)) < 2:
        return 0.0
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    return safe_div(numerator, denom_x * denom_y)


def build_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for signal in SIGNALS:
        correct = confusion(rows, signal, "target_correct_stop")
        ambiguous = confusion(rows, signal, "target_ambiguous_stop")
        output.append(
            {
                "signal": signal,
                "correct_stop_precision": correct["precision"],
                "correct_stop_recall": correct["recall"],
                "correct_stop_f1": correct["f1"],
                "ambiguous_stop_precision": ambiguous["precision"],
                "ambiguous_stop_recall": ambiguous["recall"],
                "ambiguous_stop_f1": ambiguous["f1"],
                "predicted_positive": correct["predicted_positive"],
                "support_correct": correct["support"],
                "support_ambiguous": ambiguous["support"],
            }
        )
    output.sort(key=lambda row: (-as_float(row["correct_stop_f1"]), -as_float(row["ambiguous_stop_f1"]), row["signal"]))
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_numeric_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "latency_ratio_vs_baseline",
        "queue_delay_proxy_p95_ms",
        "gpu_util_percent_mean",
        "gpu_memory_used_percent_mean",
        "request_throughput_rps",
        "throughput_ratio_vs_baseline",
        "queue_pressure_score",
        "diagnosis_confidence",
        "diagnosis_rank_margin",
        "kernel_duration_cv",
        "kernel_duration_stability_delta_percent",
    )
    output = []
    for key in keys:
        output.append(
            {
                "signal": key,
                "correlation_with_correct_stop": point_biserial(rows, key, "target_correct_stop"),
                "correlation_with_ambiguous_stop": point_biserial(rows, key, "target_ambiguous_stop"),
                "mean_when_correct_stop": mean([as_float(row.get(key)) for row in rows if as_int(row.get("target_correct_stop")) == 1]),
                "mean_when_not_correct_stop": mean([as_float(row.get(key)) for row in rows if as_int(row.get("target_correct_stop")) == 0]),
            }
        )
    output.sort(key=lambda row: -abs(as_float(row["correlation_with_correct_stop"])))
    return output


def rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = [
        "Rank",
        "Signal",
        "Correct precision",
        "Correct recall",
        "Correct F1",
        "Ambiguous precision",
        "Ambiguous recall",
        "Ambiguous F1",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["signal"]),
                    str(row["correct_stop_precision"]),
                    str(row["correct_stop_recall"]),
                    str(row["correct_stop_f1"]),
                    str(row["ambiguous_stop_precision"]),
                    str(row["ambiguous_stop_recall"]),
                    str(row["ambiguous_stop_f1"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("RQ5/analysis/stop_signals"))
    parser.add_argument("--recovery-latency-ratio", type=float, default=1.10)
    parser.add_argument("--recovery-gpu-util", type=float, default=60.0)
    parser.add_argument("--memory-pressure-threshold", type=float, default=95.0)
    parser.add_argument("--throughput-recovery-ratio", type=float, default=0.95)
    parser.add_argument("--queue-pressure-threshold", type=float, default=0.10)
    parser.add_argument("--queue-delay-recovery-ms", type=float, default=100.0)
    parser.add_argument("--diagnosis-confidence-threshold", type=float, default=0.60)
    parser.add_argument("--diagnosis-margin-threshold", type=float, default=0.15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [rounded(row) for row in build_signal_rows(args.input_root, args)]
    summary_rows = [rounded(row) for row in build_summary(rows)]
    numeric_rows = [rounded(row) for row in build_numeric_summary(rows)]
    if not rows:
        raise SystemExit("No RQ5 signal rows found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    detail_csv = args.output_dir / f"rq5_signal_detail_{timestamp}.csv"
    summary_csv = args.output_dir / f"rq5_signal_summary_{timestamp}.csv"
    summary_md = args.output_dir / f"rq5_signal_summary_{timestamp}.md"
    numeric_csv = args.output_dir / f"rq5_numeric_signal_summary_{timestamp}.csv"
    output_json = args.output_dir / f"rq5_signal_summary_{timestamp}.json"
    write_csv(detail_csv, rows)
    write_csv(summary_csv, summary_rows)
    write_markdown(summary_md, summary_rows)
    write_csv(numeric_csv, numeric_rows)
    output_json.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "input_root": str(args.input_root),
                "settings": {
                    "recovery_latency_ratio": args.recovery_latency_ratio,
                    "recovery_gpu_util": args.recovery_gpu_util,
                    "memory_pressure_threshold": args.memory_pressure_threshold,
                    "throughput_recovery_ratio": args.throughput_recovery_ratio,
                    "queue_pressure_threshold": args.queue_pressure_threshold,
                    "queue_delay_recovery_ms": args.queue_delay_recovery_ms,
                    "diagnosis_confidence_threshold": args.diagnosis_confidence_threshold,
                    "diagnosis_margin_threshold": args.diagnosis_margin_threshold,
                },
                "rows": rows,
                "summary": summary_rows,
                "numeric_summary": numeric_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"signal_rows={len(rows)}")
    print(f"wrote {detail_csv}")
    print(f"wrote {summary_csv}")
    print(f"wrote {summary_md}")
    print(f"wrote {numeric_csv}")
    print(f"wrote {output_json}")


if __name__ == "__main__":
    main()
