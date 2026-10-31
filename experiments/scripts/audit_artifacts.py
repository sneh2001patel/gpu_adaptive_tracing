#!/usr/bin/env python3
"""Read-only reconciliation of submitted-paper claims and historical artifacts.

Writes audit products only, never original analyses or paper tables. Missing
capture boundaries stay unknown; neither kernel-time sums nor requested workload
durations are substituted for measured capture-active time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def file_kind(path: Path) -> str:
    with path.open("rb") as handle:
        head = handle.read(160)
    if head.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
        return "lfs_pointer"
    if head.startswith(b"SQLite format 3"):
        return "sqlite_blob"
    return "local_file"


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("No request latencies; do not replace missing measurements with zero")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# The ICSE-era artifacts (RQ1-RQ5, paper/) were moved here; audited paths keep their original names.
LEGACY_DIR = "archive/icse_2026"
LEGACY_PREFIXES = ("RQ1/", "RQ2/", "RQ3/", "RQ4/", "RQ5/", "paper/")
LEGACY_FILES = ("README.md",)


class Audit:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.inputs: dict[str, str] = {}

    def base(self, relative: str) -> Path:
        legacy = relative.startswith(LEGACY_PREFIXES) or relative in LEGACY_FILES
        return self.root / LEGACY_DIR if legacy else self.root

    def resolve(self, relative: str) -> Path:
        return self.base(relative) / relative

    def track(self, relative: str) -> Path:
        path = self.resolve(relative)
        if relative not in self.inputs:
            self.inputs[relative] = digest(path)
        return path

    def read_json(self, relative: str):
        return json.loads(self.track(relative).read_text())

    def read_csv(self, relative: str) -> list[dict]:
        with self.track(relative).open(newline="") as handle:
            return list(csv.DictReader(handle))

    def glob(self, pattern: str) -> list[str]:
        base = self.base(pattern)
        return sorted(str(path.relative_to(base)) for path in base.glob(pattern) if path.is_file())

    def availability(self) -> list[dict]:
        rows = []
        for directory in ("RQ1/runs", "RQ4/runs"):
            for suffix in ("nsys-rep", "sqlite"):
                for relative in self.glob(f"{directory}/**/*.{suffix}"):
                    path = self.track(relative)
                    kind = file_kind(path)
                    oid, original_size = "", ""
                    if kind == "lfs_pointer":
                        for line in path.read_text().splitlines():
                            if line.startswith("oid sha256:"):
                                oid = line.split(":", 1)[1]
                            if line.startswith("size "):
                                original_size = line.split()[1]
                    rows.append(dict(path=relative, availability=kind,
                                     local_bytes=path.stat().st_size, lfs_oid_sha256=oid,
                                     lfs_declared_blob_bytes=original_size))
        return rows

    def request_span(self, mode: dict, scenario: str) -> float | None:
        for summary_path in mode.get("smoke_summary_paths", []):
            if not self.resolve(summary_path).is_file():
                continue
            entry = self.read_json(summary_path).get("scenarios", {}).get(scenario, {})
            path = entry.get("request_csv", "")
            if path and self.resolve(path).is_file():
                rows = self.read_csv(path)
                if rows:
                    return max(float(row["request_end_ts"]) for row in rows) - min(float(row["request_start_ts"]) for row in rows)
        return None

    def timing_rows(self) -> list[dict]:
        rows = []

        def add(source, family, mode, workload, wall, kernel_ns, request_span=None, requested=None):
            rows.append(dict(
                source=source, family=family, mode=mode, workload=workload,
                profile_process_wall_s=wall,
                capture_active_s=None, capture_active_status="not_measured_in_saved_scalar_fields",
                server_startup_s=None, target_initialization_s=None, shutdown_s=None,
                report_finalization_s=None, stats_export_parse_s=None, lifecycle_total_s=None,
                observed_request_span_s=request_span, requested_workload_s=requested,
                summed_kernel_execution_s=kernel_ns / 1e9 if kernel_ns is not None else None,
                interpretation="Profile subprocess wall time; separate nsys stats is excluded. Unknown phase times are not zero.",
            ))

        for path in self.glob("RQ1/runs/**/vllm_nsys_comparison_*.json"):
            payload = self.read_json(path)
            for mode in ("automatic", "fixed_window"):
                record = payload.get(mode, {})
                add(path, "vllm_fixed_duration", mode, payload.get("scenario"), record.get("duration_s"),
                    record.get("kernel_summary", {}).get("kernel_total_time_ns"),
                    self.request_span(record, payload.get("scenario", "")))
        for path in self.glob("RQ1/runs/**/comparison_*.json"):
            for workload, record in self.read_json(path).get("workloads", {}).items():
                for mode in ("automatic", "fixed_window"):
                    add(path, "microbenchmark", mode, workload,
                        record.get(f"{mode}_profiler_duration_s"),
                        record.get(f"{mode}_profiler_kernel_total_time_ns"))
        for path in self.glob("RQ4/runs/**/live_policy_result.json"):
            record = self.read_json(path)
            add(path, "live_capture_at_replay_selected_duration", record.get("policy"),
                record.get("scenario"), record.get("wall_duration_s"),
                record.get("kernel_summary", {}).get("kernel_total_time_ns"),
                requested=record.get("requested_trace_duration_s"))
        return rows

    def overhead(self, source: str) -> list[dict]:
        rows = []
        for record in self.read_json(source)["records"]:
            p95, rates, success = {}, {}, {}
            for mode in ("no_profiler", "cheap_metrics_only"):
                requests = self.read_csv(record[mode]["request_csv"])
                p95[mode] = percentile([float(row["request_latency_ms"]) for row in requests], 0.95)
                span = max(float(row["request_end_ts"]) for row in requests) - min(float(row["request_start_ts"]) for row in requests)
                rates[mode] = len(requests) / span
                success[mode] = 100 * sum(int(row["success"]) for row in requests) / len(requests)
            change = 100 * (p95["cheap_metrics_only"] / p95["no_profiler"] - 1)
            rows.append(dict(source=source, seed=record["seed"],
                             p95_regression_percent=change,
                             saved_p95_regression_percent=record["comparison"]["p95_latency_regression_percent"],
                             absolute_difference=abs(change - record["comparison"]["p95_latency_regression_percent"]),
                             throughput_change_percent=100 * (rates["cheap_metrics_only"] / rates["no_profiler"] - 1),
                             minimum_success_percent=min(success.values())))
        return rows

    def reconcile(self) -> tuple[dict, list[dict]]:
        paths = self.glob("RQ1/runs/vllm_rq2_multiclass_long/*/vllm_nsys_comparison_*.json")
        totals = {mode: dict(wall_s=0.0, kernels=0) for mode in ("automatic", "fixed_window")}
        scenario_totals: dict[str, dict] = {}
        for path in paths:
            payload = self.read_json(path)
            scenario = scenario_totals.setdefault(payload["scenario"], {})
            for mode in totals:
                record = payload[mode]
                totals[mode]["wall_s"] += record["duration_s"]
                totals[mode]["kernels"] += record["kernel_summary"]["kernel_instances"]
                scenario[mode + "_wall_s"] = scenario.get(mode + "_wall_s", 0) + record["duration_s"]
                scenario[mode + "_kernels"] = scenario.get(mode + "_kernels", 0) + record["kernel_summary"]["kernel_instances"]
        canonical = self.glob("RQ1/runs/vllm_rq2_multiclass_long/*/*/smoke/*_windows_*.csv")
        canonical = [p for p in canonical if not Path(p).name.startswith("all_")]
        named_count = sum(len(self.read_csv(path)) for path in canonical)
        all_windows = self.glob("RQ1/runs/vllm_rq2_multiclass_long/*/*/smoke/*_windows_*.csv")
        unique_windows = set()
        all_count = 0
        for path in all_windows:
            for row in self.read_csv(path):
                all_count += 1
                unique_windows.add((str(Path(path).parent), row.get("scenario"), row.get("window_id"),
                                    row.get("timestamp_start"), row.get("timestamp_end")))
        old = self.read_json("RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_1781706527.json")
        clean = self.read_json("RQ2/analysis/vllm_multiclass_long_accuracy/rq2_accuracy_1782148663.json")
        manifests = [dict(path=p, settings=self.read_json(p)["command_settings"])
                     for p in self.glob("RQ1/runs/rq1_l4_compare_rep*/experiment_manifest.json")]
        signals = self.read_json("RQ5/analysis/stop_signals_enriched_real_l4_vllm/rq5_signal_summary_1781810012.json")
        selected_signals = {row["signal"]: row for row in signals["summary"]
                            if row["signal"] in {"diagnosis_changed_from_previous", "diagnosis_confident", "diagnosis_stable_2"}}
        overhead_rows = []
        for source in (
            "RQ3/runs/vllm_runtime_overhead_queue_pressure_randomized_5rep/runtime_overhead_summary_1781728923.json",
            *self.glob("RQ3/runs/vllm_runtime_overhead_healthy_randomized/runtime_overhead_summary_*.json"),
        ):
            overhead_rows.extend(self.overhead(source))
        grouped = {}
        for source in sorted({row["source"] for row in overhead_rows}):
            rows = [row for row in overhead_rows if row["source"] == source]
            values = [row["p95_regression_percent"] for row in rows]
            grouped[source] = dict(repetitions=len(rows), p95_mean=statistics.mean(values),
                                   historical_normal_ci_half_width=1.96 * statistics.stdev(values) / len(values)**0.5,
                                   max_raw_vs_saved_difference=max(row["absolute_difference"] for row in rows))
        summary = dict(
            canonical_comparison_files=len(paths), canonical_window_csvs=len(canonical),
            canonical_window_records=named_count,
            all_window_csv_records=all_count, unique_window_identities=len(unique_windows),
            old_analysis_records=sum(row["windows"] for row in old["summary"]),
            deduplicated_analysis_records=sum(row["windows"] for row in clean["summary"]),
            multiclass_totals=totals, multiclass_by_scenario=scenario_totals,
            wall_time_saved_percent=100 * (1 - totals["automatic"]["wall_s"] / totals["fixed_window"]["wall_s"]),
            kernel_instances_saved_percent=100 * (1 - totals["automatic"]["kernels"] / totals["fixed_window"]["kernels"]),
            l4_microbenchmark_manifests=manifests,
            enriched_signal_checks=selected_signals, raw_request_overhead_checks=grouped,
        )
        return summary, overhead_rows

    @staticmethod
    def table_vi_rows(scenarios: dict) -> list[dict]:
        # Transcribed from the authoritative submitted PDF, Table VI (page 8).
        paper = {
            "healthy": (301.3, 391.9, 730000, 1380000),
            "queue_pressure": (309.7, 403.4, 748000, 1380000),
            "long_prompt": (290.4, 381.0, 732000, 1380000),
            "long_output": (291.0, 397.1, 729000, 1380000),
            "compute_saturation": (336.8, 415.1, 757000, 1380000),
            "kv_cache_pressure": (329.4, 449.3, 731000, 1380000),
        }
        rows = []
        for scenario, (auto_s, fixed_s, auto_k, fixed_k) in paper.items():
            raw = scenarios[scenario]
            rows.append(dict(
                scenario=scenario,
                paper_auto_seconds=auto_s, artifact_auto_profile_wall_seconds=raw["automatic_wall_s"],
                paper_fixed_seconds=fixed_s, artifact_fixed_profile_wall_seconds=raw["fixed_window_wall_s"],
                times_match_rounding=abs(auto_s - raw["automatic_wall_s"]) <= 0.05
                and abs(fixed_s - raw["fixed_window_wall_s"]) <= 0.05,
                paper_auto_kernels_rounded=auto_k, artifact_auto_kernel_instances=raw["automatic_kernels"],
                paper_fixed_kernels_rounded=fixed_k, artifact_fixed_kernel_instances=raw["fixed_window_kernels"],
                kernels_match_rounding=abs(auto_k - raw["automatic_kernels"]) <= 500
                and abs(fixed_k - raw["fixed_window_kernels"]) <= 500,
            ))
        return rows

    def run(self, output: Path) -> dict:
        # Keep audit writes away from historical data and analysis directories.
        output = output.resolve()
        output.relative_to((self.root / "experiments").resolve())
        registry = self.read_json("experiments/audit/claim_registry.json")
        self.track("experiments/scripts/audit_artifacts.py")
        self.track("paper/ICSE_GPU_Adaptive_Tracing (2).pdf")
        artifact_checks = []
        inventory = []
        for claim in registry:
            for category in ("analysis_artifacts", "raw_artifacts", "source_scripts"):
                for pattern in claim[category]:
                    matches = self.glob(pattern)
                    for path in matches:
                        self.track(path)
                    artifact_checks.append(dict(claim_id=claim["claim_id"], category=category,
                                                pattern=pattern, matched_files=len(matches)))
            inventory.append({key: " | ".join(value) if isinstance(value, list) else value
                              for key, value in claim.items()})
        availability = self.availability()
        timing = self.timing_rows()
        reconciliation, overhead = self.reconcile()
        summary = dict(
            source_pdf_sha256=self.inputs["paper/ICSE_GPU_Adaptive_Tracing (2).pdf"],
            claim_groups=len(registry), timing_records=len(timing),
            profiler_files=len(availability),
            profiler_lfs_pointers=sum(row["availability"] == "lfs_pointer" for row in availability),
            missing_registry_patterns=[row for row in artifact_checks if not row["matched_files"]],
            reconciliation=reconciliation,
            limits="Local artifact audit; no GPU runs, LFS download, raw profiler export, or independent production diagnosis validation.",
        )
        baseline = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root,
                                  text=True, capture_output=True, check=False)
        summary["repository_head_at_audit"] = baseline.stdout.strip() if baseline.returncode == 0 else None
        summary["code_provenance_limit"] = "Per-run source commits are absent; repository code supports reconstruction, not proof of exact historical executable identity."
        fingerprints = []
        for path, before in sorted(self.inputs.items()):
            unchanged = before == digest(self.resolve(path))
            if not unchanged:
                raise RuntimeError(f"Input changed during audit: {path}")
            fingerprints.append(dict(path=path, sha256=before, unchanged_during_audit=True))
        output.mkdir(parents=True, exist_ok=True)
        for name, rows in (("artifact_audit.csv", inventory), ("artifact_checks.csv", artifact_checks),
                           ("profiler_availability.csv", availability), ("timing_audit.csv", timing),
                           ("table_vi_reconciliation.csv", self.table_vi_rows(reconciliation["multiclass_by_scenario"])),
                           ("raw_request_overhead_checks.csv", overhead), ("input_fingerprints.csv", fingerprints)):
            write_csv(output / name, rows)
        (output / "audit_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/audit/generated"))
    args = parser.parse_args()
    audit = Audit(args.root)
    output = args.output_dir if args.output_dir.is_absolute() else audit.root / args.output_dir
    summary = audit.run(output)
    print(json.dumps({key: summary[key] for key in ("claim_groups", "timing_records", "profiler_files", "profiler_lfs_pointers")}))
    print(f"Audit written to {output}")


if __name__ == "__main__":
    main()
