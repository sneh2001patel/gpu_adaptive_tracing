import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiments.tracing.external_instrument import (ExternalBursts, cheap_measures, engine_family, gpu_activity,
                                                  parse_prometheus)
from experiments.tracing.rule_diagnosis import busy_fraction, kernel_shares

V0_TEXT = """# HELP vllm:num_requests_waiting Number of requests waiting.
# TYPE vllm:num_requests_waiting gauge
vllm:num_requests_waiting{model_name="m"} 7.0
vllm:num_requests_running{model_name="m"} 3.0
vllm:gpu_cache_usage_perc{model_name="m"} 0.92
vllm:num_preemptions_total{model_name="m"} 12.0
vllm:prompt_tokens_total{model_name="m"} 1000.0
vllm:generation_tokens_total{model_name="m"} 500.0
vllm:num_preemptions_created{model_name="m"} 1.7e9
"""


class MetricTests(unittest.TestCase):
    def test_engine_family_by_release(self):
        self.assertEqual(engine_family('0.3.2'), 'v0_early')
        self.assertEqual(engine_family('0.5.5'), 'v0')
        self.assertEqual(engine_family('0.6.4.post1'), 'v0')
        self.assertEqual(engine_family('0.9.2'), 'v1')
        self.assertEqual(engine_family('0.11.0'), 'v1')

    def test_parse_sums_label_sets_and_skips_comments_and_created(self):
        parsed = parse_prometheus(V0_TEXT + 'vllm:num_requests_waiting{model_name="n"} 1.0\n')
        self.assertEqual(parsed['vllm:num_requests_waiting'], 8.0)
        self.assertNotIn('vllm:num_preemptions_created', parsed)

    def test_v0_measures(self):
        m = cheap_measures(V0_TEXT, 'v0')
        self.assertEqual((m['waiting'], m['kv_usage'], m['preemptions']), (7.0, 0.92, 12.0))

    def test_early_v0_has_no_preemption_counter(self):
        self.assertIsNone(cheap_measures(V0_TEXT, 'v0_early')['preemptions'])

    def test_metric_absent_from_scrape_is_none_not_zero(self):
        self.assertIsNone(cheap_measures(V0_TEXT, 'v1')['kv_usage'])  # v1 uses kv_cache_usage_perc


def make_db(path, *, with_session=True):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE StringIds(id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE PROCESSES(globalPid INTEGER, pid INTEGER);
        CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL(start INTEGER, end INTEGER, demangledName INTEGER, globalPid INTEGER, deviceId INTEGER);
        CREATE TABLE CUPTI_ACTIVITY_KIND_MEMCPY(start INTEGER, end INTEGER, deviceId INTEGER);
        INSERT INTO StringIds VALUES (1, 'gemm<1>(a)'), (2, 'attn');
        INSERT INTO PROCESSES VALUES (100, 4242);
        INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (100, 300, 1, 100, 0), (250, 400, 2, 100, 0), (600, 700, 1, 100, 0);
        INSERT INTO CUPTI_ACTIVITY_KIND_MEMCPY VALUES (450, 500, 0);
    """)
    if with_session:
        con.executescript('CREATE TABLE ANALYSIS_DETAILS(startTime INTEGER, stopTime INTEGER); '
                          'INSERT INTO ANALYSIS_DETAILS VALUES (0, 1000);')
    con.commit()
    con.close()


class GpuActivityTests(unittest.TestCase):
    def test_busy_fraction_uses_capture_window_not_activity_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db)
            act = gpu_activity(db)
        self.assertEqual(act['window_source'], 'analysis_details')
        self.assertEqual(act['pids'], [4242])
        # union: 100-400 (300) + 450-500 (50) + 600-700 (100) = 450 of 1000
        self.assertAlmostEqual(busy_fraction(act['intervals'], *act['window']), 0.45)
        self.assertEqual(kernel_shares(act['kernel_totals']), {'gemm': 300 / 450, 'attn': 150 / 450})

    def test_relative_activity_times_with_absolute_session_times(self):
        # Nsight 2026.3: kernels relative to session start, ANALYSIS_DETAILS absolute
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db, with_session=False)
            con = sqlite3.connect(db)
            con.executescript('CREATE TABLE ANALYSIS_DETAILS(startTime INTEGER, stopTime INTEGER); '
                              'INSERT INTO ANALYSIS_DETAILS VALUES (222961076860952, 222961076861952);')
            con.commit()
            con.close()
            act = gpu_activity(db)
        self.assertEqual((act['window'], act['window_source']), ((0, 1000), 'analysis_details'))
        self.assertAlmostEqual(busy_fraction(act['intervals'], *act['window']), 0.45)

    def test_graph_replays_count_as_busy_and_flag_opaque_kernel_shares(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db)
            con = sqlite3.connect(db)
            con.executescript('CREATE TABLE CUPTI_ACTIVITY_KIND_GRAPH_TRACE(start INTEGER, end INTEGER, deviceId INTEGER); '
                              'INSERT INTO CUPTI_ACTIVITY_KIND_GRAPH_TRACE VALUES (750, 950, 0);')
            con.commit()
            con.close()
            act = gpu_activity(db)
        self.assertEqual(act['graph_count'], 1)
        self.assertTrue(act['graph_kernels_opaque'])
        self.assertAlmostEqual(busy_fraction(act['intervals'], *act['window']), 0.65)

    def test_kernels_crossing_the_window_are_excluded_from_shares_but_clipped_for_busy(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db)
            con = sqlite3.connect(db)
            con.execute('INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (-5000, 50, 2, 100, 0)')  # in flight at start
            con.commit()
            con.close()
            act = gpu_activity(db)
        self.assertEqual(act['kernels_crossing_window'], 1)
        self.assertEqual(kernel_shares(act['kernel_totals']), {'gemm': 300 / 450, 'attn': 150 / 450})
        self.assertAlmostEqual(busy_fraction(act['intervals'], *act['window']), 0.5)  # 0-50 clipped in

    def test_envelope_fallback_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db, with_session=False)
            act = gpu_activity(db)
        self.assertEqual(act['window_source'], 'activity_envelope')
        self.assertEqual(act['window'], (100, 700))

    def test_capture_without_kernels_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'c.sqlite'
            make_db(db)
            con = sqlite3.connect(db)
            con.execute('DELETE FROM CUPTI_ACTIVITY_KIND_KERNEL')
            con.commit()
            con.close()
            with self.assertRaises(ValueError):
                gpu_activity(db)


class FakeNsys:
    def __init__(self, fail=None, write_report=True):
        self.calls, self.fail, self.write_report = [], fail, write_report

    def __call__(self, cmd):
        self.calls.append(cmd)
        step = cmd[1]
        if step == self.fail:
            return 1, 'error'
        if step == 'stop' and self.write_report:
            out = next(a for a in self.calls[-2] if a.startswith('--output=')).split('=', 1)[1]
            Path(out + '.nsys-rep').write_bytes(b'x' * 200)
        if step == 'export':
            out = next(a for a in cmd if a.startswith('--output=')).split('=', 1)[1]
            Path(out).write_bytes(b'db')
        return 0, 'ok'


class ExternalBurstTests(unittest.TestCase):
    def setUp(self):
        self.ticks = iter(range(1, 100))
        self.slept = []

    def bursts(self, d, fake):
        return ExternalBursts('s1', d, run=fake, clock=lambda: next(self.ticks), sleep=self.slept.append)

    def test_successful_burst_records_every_stamp_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeNsys()
            rec = self.bursts(d, fake).capture(2.5)
        self.assertIsNone(rec.failure)
        stamps = [rec.start_issued_ns, rec.start_returned_ns, rec.stop_issued_ns, rec.stop_returned_ns,
                  rec.report_present_ns, rec.export_done_ns]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(self.slept, [2.5])
        self.assertEqual([c[1] for c in fake.calls], ['start', 'stop', 'export'])
        self.assertIn('--session=s1', fake.calls[0])

    def test_callbacks_bracket_the_capture_window(self):
        order = []
        with tempfile.TemporaryDirectory() as d:
            fake = FakeNsys()
            orig = fake.__call__
            b = ExternalBursts('s1', d, run=lambda cmd: (order.append(cmd[1]), orig(cmd))[1],
                               clock=lambda: next(self.ticks), sleep=lambda s: order.append('sleep'))
            b.capture(1, on_started=lambda: order.append('on_started'), before_stop=lambda: order.append('before_stop'))
        self.assertEqual(order, ['start', 'on_started', 'sleep', 'before_stop', 'stop', 'export'])

    def test_failed_start_stops_before_capture(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeNsys(fail='start')
            rec = self.bursts(d, fake).capture(1)
        self.assertEqual(rec.failure, 'start_failed')
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(self.slept, [])

    def test_missing_report_is_a_failure_not_empty_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            rec = self.bursts(d, FakeNsys(write_report=False)).capture(1)
        self.assertEqual(rec.failure, 'report_missing')
        self.assertIsNone(rec.database)

    def test_ordinals_and_outputs_are_unique(self):
        with tempfile.TemporaryDirectory() as d:
            b = self.bursts(d, FakeNsys())
            r1, r2 = b.capture(1), b.capture(1)
        self.assertEqual((r1.ordinal, r2.ordinal), (1, 2))
        self.assertNotEqual(r1.output, r2.output)


if __name__ == '__main__':
    unittest.main()
