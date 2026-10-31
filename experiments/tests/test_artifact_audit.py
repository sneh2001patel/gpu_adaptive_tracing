"""Check audit safeguards and timing interpretation with temporary fixtures."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_artifacts import Audit, file_kind, percentile


class AuditTests(unittest.TestCase):
    def test_lfs_pointer_is_not_a_profiler_blob(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "capture.sqlite"
            path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1000\n")
            self.assertEqual(file_kind(path), "lfs_pointer")
            path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
            self.assertEqual(file_kind(path), "sqlite_blob")

    def test_wall_and_kernel_times_never_fill_capture_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "archive/icse_2026/RQ1/runs/example/vllm_nsys_comparison_1.json"
            path.parent.mkdir(parents=True)
            payload = {"scenario": "healthy", "automatic": {
                "duration_s": 100, "kernel_summary": {"kernel_total_time_ns": 2_000_000_000}},
                "fixed_window": {"duration_s": 150}}
            path.write_text(json.dumps(payload))
            rows = Audit(root).timing_rows()
            self.assertEqual(rows[0]["profile_process_wall_s"], 100)
            self.assertEqual(rows[0]["summed_kernel_execution_s"], 2)
            for row in rows:
                for field in ("capture_active_s", "server_startup_s", "report_finalization_s",
                              "stats_export_parse_s", "lifecycle_total_s"):
                    self.assertIsNone(row[field], field)

    def test_missing_latency_data_is_not_zero_overhead(self):
        with self.assertRaises(ValueError):
            percentile([], 0.95)
        self.assertEqual(percentile([10, 20], 0.95), 19.5)

    def test_outputs_cannot_target_historical_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                Audit(root).run(root / "archive/icse_2026/RQ1/analysis")

    def test_tracking_reads_preserve_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "record.json"
            content = b'{"duration_s": 123}\n'
            path.write_bytes(content)
            audit = Audit(root)
            self.assertEqual(audit.read_json("record.json"), {"duration_s": 123})
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(len(audit.inputs["record.json"]), 64)


if __name__ == "__main__":
    unittest.main()
