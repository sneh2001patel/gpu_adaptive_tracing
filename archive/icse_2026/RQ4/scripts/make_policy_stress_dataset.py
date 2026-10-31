#!/usr/bin/env python3
"""Create a harder RQ4 policy-replay dataset from existing vLLM windows."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from pathlib import Path


EXPECTED_LABELS = {
    "healthy": "vllm_healthy",
    "queue_pressure": "vllm_queue_pressure",
    "long_prompt": "vllm_long_prompt",
    "long_output": "vllm_long_output",
    "compute_saturation": "vllm_compute_saturation",
    "kv_cache_pressure": "vllm_kv_cache_pressure",
}


def as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def is_suspicious(row: dict[str, str]) -> bool:
    return as_int(row.get("trigger_trace")) == 1 or row.get("controller_state") == "suspicious"


def scenario_seed_from_path(path: Path) -> tuple[str, str]:
    scenario = path.name.split("_windows_")[0]
    seed = ""
    for part in path.parts:
        if "_seed" in part:
            seed = part.rsplit("_seed", 1)[-1]
    return scenario, seed


def iter_source_files(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*_windows_*.csv")
        if "automatic" in path.parts
        and not path.name.startswith("all_windows_")
        and path.name.split("_windows_")[0] in EXPECTED_LABELS
    )


def transform_rows(rows: list[dict[str, str]], scenario: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    expected = EXPECTED_LABELS[scenario]
    suspicious_indices = [index for index, row in enumerate(rows) if is_suspicious(row)]
    changed = []
    if suspicious_indices:
        first = suspicious_indices[0]
        rows[first]["diagnosis_label"] = "vllm_latency_regression_unknown_gpu_cause"
        rows[first]["suspicion_reasons"] = append_reason(rows[first].get("suspicion_reasons", ""), "stress_first_window_ambiguous")
        changed.append(as_int(rows[first].get("window_id")))
        for index in suspicious_indices[1:]:
            rows[index]["diagnosis_label"] = expected
    return rows, {
        "expected_label": expected,
        "suspicious_windows": len(suspicious_indices),
        "ambiguous_window_ids": changed,
    }


def append_reason(existing: str, reason: str) -> str:
    if not existing:
        return reason
    if reason in existing.split("|"):
        return existing
    return f"{existing}|{reason}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("RQ1/runs/vllm_rq2_multiclass_long"))
    parser.add_argument("--output-root", type=Path, default=Path("RQ4/datasets/policy_stress_l4_vllm"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_root": str(args.input_root),
        "output_root": str(args.output_root),
        "transformation": "first suspicious window diagnosis is made ambiguous; later suspicious windows retain expected label",
        "files": [],
    }
    for source in iter_source_files(args.input_root):
        scenario, seed = scenario_seed_from_path(source)
        fieldnames, rows = read_csv(source)
        transformed, info = transform_rows(rows, scenario)
        relative = source.relative_to(args.input_root)
        target = args.output_root / relative
        write_csv(target, fieldnames, transformed)
        manifest["files"].append(
            {
                "source": str(source),
                "target": str(target),
                "scenario": scenario,
                "seed": seed,
                **info,
            }
        )
    manifest_path = args.output_root / "stress_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path}")
    print(f"files={len(manifest['files'])}")


if __name__ == "__main__":
    main()
