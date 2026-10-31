"""Raw-event windowing correctness and CPU controller integration."""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.aggregation import GpuSample, RequestCompletion, RequestStarted, StreamingWindowAdapter, WindowConfig
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import ManualClock, TimingRecorder
from revision.tracing.windows import HealthyBaseline


def ns(seconds):
    return round(seconds * 1e9)


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.windows = []
        self.adapter = self.make()

    def make(self, **changes):
        return StreamingWindowAdapter(self.clock, WindowConfig(0, ns(2), window_s=1, **changes),
                                      self.windows.append, provenance="synthetic_simulation")

    def complete(self, identity, start, end, *, received=None, available=None, success=True):
        received = end if received is None else received
        available = received if available is None else available
        self.clock.advance_to(ns(received))
        return self.adapter.on_request_completed(RequestCompletion(identity, ns(start), ns(end), ns(available),
                                                                  self.clock.domain, success))

    def sample(self, identity, at, value, *, received=None):
        received = at if received is None else received
        self.clock.advance_to(ns(received))
        return self.adapter.on_gpu_sample(GpuSample(identity, ns(at), ns(received), self.clock.domain, value))

    def close(self, at=2):
        self.clock.advance_to(ns(at))
        return self.adapter.finish()

    def test_metrics_interpolate_p95_and_average_only_actual_samples(self):
        self.complete("a", 0, 0.1)
        self.complete("b", 0.2, 0.4)
        self.sample("g1", 0.5, 0)
        self.sample("g2", 0.6, 100)
        self.clock.advance_to(ns(1))
        self.adapter.advance()
        window = self.windows[0]
        self.assertEqual(window.p95_latency_ms, 195)
        self.assertEqual(window.gpu_util, 50)
        self.assertEqual(window.sample_count, 2)
        self.assertEqual(window.throughput_rps, 2)
        self.assertEqual(window.gpu_sample_count, 2)

    def test_regular_boundary_goes_next_but_final_boundary_is_included_once(self):
        self.complete("regular", 0.9, 1)
        self.sample("regular-gpu", 1, 20)
        self.complete("final", 1.9, 2)
        self.sample("final-gpu", 2, 40)
        self.adapter.finish()
        self.assertEqual([window.sample_count for window in self.windows], [0, 2])
        self.assertEqual(self.windows[-1].gpu_util, 30)
        self.assertEqual(self.adapter.reports[-1]["request_ids"], ["regular", "final"])

    def test_partial_final_window_uses_its_actual_width(self):
        self.adapter = StreamingWindowAdapter(self.clock, WindowConfig(0, ns(2.5), window_s=1),
                                               self.windows.append, provenance="synthetic_simulation")
        self.complete("a", 2.3, 2.4)
        self.complete("boundary", 2.4, 2.5)
        self.adapter.finish()
        self.assertEqual(self.windows[-1].throughput_rps, 4)
        self.assertEqual(self.windows[-1].end_ns, ns(2.5))
        self.assertTrue(self.adapter.reports[-1]["partial_window"])

    def test_empty_windows_preserve_unknowns_and_zero_observed_completions(self):
        self.close()
        self.assertEqual(len(self.windows), 2)
        for window in self.windows:
            self.assertIsNone(window.p95_latency_ms)
            self.assertIsNone(window.gpu_util)
            self.assertEqual(window.sample_count, 0)
            self.assertEqual(window.throughput_rps, 0)

    def test_missing_gpu_reading_is_distinct_from_observed_zero(self):
        self.sample("missing", 0.1, None)
        self.sample("zero", 1.1, 0)
        self.close()
        self.assertIsNone(self.windows[0].gpu_util)
        self.assertEqual(self.windows[0].gpu_sample_count, 0)
        self.assertEqual(self.windows[1].gpu_util, 0)
        self.assertEqual(self.windows[1].gpu_sample_count, 1)

    def test_arrival_grace_allows_delayed_data_before_window_closure(self):
        self.adapter = self.make(allowed_lateness_s=0.5)
        self.complete("a", 0.6, 0.7, received=1.2)
        self.clock.advance_to(ns(1.49))
        self.adapter.advance()
        self.assertEqual(self.windows, [])
        self.clock.advance_to(ns(1.5))
        self.adapter.advance()
        self.assertEqual(self.windows[0].sample_count, 1)
        self.assertEqual(self.windows[0].available_at_ns, ns(1.5))

    def test_producer_timestamp_cannot_hide_actual_late_ingestion(self):
        self.assertFalse(self.complete("late", 0.4, 0.5, received=1.2, available=0.6))
        self.assertEqual(self.adapter.late_completions, 1)
        self.assertEqual(self.windows[0].sample_count, 0)
        self.assertEqual(self.adapter.events[-1]["received_at_ns"], ns(1.2))

    def test_late_samples_never_rewrite_closed_windows(self):
        self.sample("early", 0.2, 20)
        self.clock.advance_to(ns(1))
        self.adapter.advance()
        original = asdict(self.windows[0])
        self.assertFalse(self.sample("late", 0.3, 99, received=1.2))
        self.assertEqual(asdict(self.windows[0]), original)
        self.assertEqual(self.adapter.late_samples, 1)

    def test_out_of_order_event_times_work_within_the_open_window(self):
        self.sample("gpu", 0.6, 20, received=0.8)
        self.complete("completion", 0.3, 0.4, received=0.9)
        self.close()
        self.assertEqual(self.windows[0].sample_count, 1)

    def test_duplicate_ids_cannot_double_count(self):
        self.complete("a", 0, 0.1)
        with self.assertRaises(ValueError):
            self.complete("a", 0, 0.1)
        self.sample("gpu", 0.2, 20)
        with self.assertRaises(ValueError):
            self.sample("gpu", 0.2, 20)

    def test_future_and_foreign_clock_events_are_rejected_without_mutation(self):
        for record in (RequestCompletion("future", 0, ns(0.1), ns(0.2), self.clock.domain, True),
                       RequestCompletion("foreign", 0, 1, 1, "foreign", True)):
            with self.assertRaises(ValueError):
                self.adapter.on_request_completed(record)
        self.assertEqual(self.adapter.events, [])
        self.assertEqual(self.windows, [])

    def test_require_starts_validates_request_identity_and_lifetime(self):
        self.adapter = self.make(require_request_starts=True)
        with self.assertRaises(ValueError):
            self.complete("a", 0.1, 0.2)
        self.adapter.on_request_started(RequestStarted("a", ns(0.1), ns(0.2), self.clock.domain))
        with self.assertRaises(ValueError):
            self.complete("a", 0.11, 0.3)
        self.complete("a", 0.1, 0.4)
        self.assertEqual(self.adapter.summary()["untracked_completions"], 0)

    def test_post_horizon_drain_is_recorded_separately_and_resolves_outstanding(self):
        self.clock.advance_to(ns(1.5))
        self.adapter.on_request_started(RequestStarted("slow", ns(1.5), ns(1.5), self.clock.domain))
        self.assertFalse(self.complete("slow", 1.5, 2.2))
        summary = self.adapter.finish()
        self.assertEqual(summary["drain_completions"], 1)
        self.assertEqual(summary["outstanding_tracked_requests"], [])
        self.assertTrue(all(window.sample_count == 0 for window in self.windows))

    def test_unfinished_requests_remain_explicitly_censored(self):
        self.clock.advance_to(ns(0.1))
        self.adapter.on_request_started(RequestStarted("pending", ns(0.1), ns(0.1), self.clock.domain))
        summary = self.close()
        self.assertEqual(summary["outstanding_tracked_requests"], [{"request_id": "pending", "start_ns": ns(0.1)}])
        self.assertEqual(self.windows[-1].oldest_pending_ms, 1900)

    def test_admissions_after_horizon_are_not_counted_as_censored_work(self):
        self.clock.advance_to(ns(2.1))
        self.assertFalse(self.adapter.on_request_started(RequestStarted("outside", ns(2.1), ns(2.1), self.clock.domain)))
        self.assertEqual(self.adapter.summary()["tracked_admissions"], 0)

    def test_errors_contribute_latency_but_not_successful_throughput(self):
        self.complete("error", 0.1, 0.101, success=False)
        self.close()
        window = self.windows[0]
        self.assertEqual(window.p95_latency_ms, 1)
        self.assertEqual(window.request_error_count, 1)
        self.assertEqual(window.throughput_rps, 0)
        self.assertEqual(self.adapter.reports[0]["completed_throughput_rps"], 1)

    def test_finish_requires_horizon_and_grace_and_is_idempotent(self):
        self.adapter = self.make(allowed_lateness_s=0.5)
        with self.assertRaises(ValueError):
            self.close(2)
        first = self.close(2.5)
        self.assertEqual(self.adapter.finish(), first)
        with self.assertRaises(RuntimeError):
            self.complete("after-finish", 2.5, 2.6)

    def test_late_poll_records_actual_window_availability(self):
        self.clock.advance_to(ns(2))
        self.adapter.advance()
        self.assertEqual([window.available_at_ns for window in self.windows], [ns(2), ns(2)])

    def test_consumer_failure_is_visible_and_not_silently_retried(self):
        def fail(window):
            raise RuntimeError("synthetic consumer failure")
        self.adapter = StreamingWindowAdapter(self.clock, WindowConfig(0, ns(2), window_s=1), fail,
                                               provenance="synthetic_simulation")
        self.clock.advance_to(ns(1))
        with self.assertRaises(RuntimeError):
            self.adapter.advance()
        self.assertTrue(self.adapter.delivery_failed)
        self.assertEqual(self.adapter.reports[0]["window"]["window_id"], "raw-window-0")
        with self.assertRaises(RuntimeError):
            self.adapter.advance()

    def test_nonzero_origin_and_outside_records(self):
        self.adapter = StreamingWindowAdapter(self.clock, WindowConfig(ns(1), ns(2), window_s=1),
                                               self.windows.append, provenance="synthetic_simulation")
        self.assertFalse(self.complete("before", 0, 0.1))
        self.complete("inside", 1.1, 1.2)
        self.close()
        self.assertEqual(self.windows[0].sample_count, 1)
        self.assertEqual(self.adapter.outside_completions, 1)

    def test_no_truth_fields_in_raw_event_interfaces(self):
        with self.assertRaises(TypeError):
            RequestCompletion("a", 0, 1, 1, self.clock.domain, True, expected_label="compute_bound")
        with self.assertRaises(TypeError):
            GpuSample("a", 0, 0, self.clock.domain, 20, scenario="healthy")

    def test_invalid_event_data_is_rejected(self):
        with self.assertRaises(ValueError):
            RequestCompletion("a", 1, 1, 1, self.clock.domain, True)
        with self.assertRaises(ValueError):
            GpuSample("a", 0, 0, self.clock.domain, float("nan"))
        with self.assertRaises(ValueError):
            WindowConfig(0, ns(1), window_s=0)


class AdapterControllerTests(unittest.TestCase):
    def setup_stream(self):
        clock = ManualClock()
        recorder = TimingRecorder(clock, provenance="synthetic_simulation")
        backend = FakeProfilerBackend(recorder)
        controller = StreamingController(backend, HealthyBaseline(100, "separate-synthetic-calibration"),
            lambda summary: "compute_bound", lambda capture_id, window: backend.start(capture_id, FakeCapturePlan()),
            ControllerConfig())
        adapter = StreamingWindowAdapter(clock, WindowConfig(0, ns(2), window_s=1),
                                         controller.on_window, provenance="synthetic_simulation")
        return clock, controller, adapter

    def test_fast_request_errors_trigger_controller_despite_low_latency(self):
        clock, controller, adapter = self.setup_stream()
        clock.advance_to(ns(0.2))
        adapter.on_request_completed(RequestCompletion("error", ns(0.199), ns(0.2), ns(0.2), clock.domain, False))
        adapter.on_gpu_sample(GpuSample("gpu", ns(0.2), ns(0.2), clock.domain, 20))
        clock.advance_to(ns(1))
        adapter.advance()
        self.assertEqual(controller.state, "starting")
        self.assertIn("request_errors", next(event for event in controller.events if event["event"] == "cheap_window_available")["suspicion_reasons"])
        self.assertEqual(controller.baseline.p95_latency_ms, 100)

    def test_slow_pending_request_is_not_hidden_by_fast_completions(self):
        clock, controller, adapter = self.setup_stream()
        clock.advance_to(ns(0.05))
        adapter.on_request_started(RequestStarted("slow", ns(0.05), ns(0.05), clock.domain))
        clock.advance_to(ns(0.8))
        adapter.on_request_completed(RequestCompletion("fast", ns(0.7), ns(0.8), ns(0.8), clock.domain, True))
        adapter.on_gpu_sample(GpuSample("gpu", ns(0.8), ns(0.8), clock.domain, 20))
        clock.advance_to(ns(1))
        adapter.advance()
        self.assertTrue(controller.suspicious)
        self.assertIn("long_pending_request", next(event for event in controller.events if event["event"] == "cheap_window_available")["suspicion_reasons"])

    def test_raw_stream_demo_cli_emits_only_synthetic_results(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "revision") as temp:
            result = subprocess.run([sys.executable, str(ROOT / "revision/scripts/demo_raw_stream.py"),
                                     "--scenario", "drain", "--output-dir", temp], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((Path(temp) / "results.json").read_text())
            self.assertFalse(payload["gpu_used"])
            self.assertEqual(payload["evidence_mode"], "synthetic_simulation")
            self.assertEqual(payload["aggregation"]["drain_completions"], 1)
            self.assertEqual(payload["aggregation"]["outstanding_tracked_requests"], [])
            self.assertEqual(payload["aggregation"]["emitted_windows"], 20)


if __name__ == "__main__":
    unittest.main()
