import json
import sys
import tempfile
import unittest
from pathlib import Path

CHECKS = Path(__file__).resolve().parents[1] / 'cases' / 'checks'
sys.path.insert(0, str(CHECKS))
import derive_thresholds as dt  # noqa: E402


def window(t, **cheap):
    age = cheap.pop('age', None)
    base = dict(latency_ratio=None, waiting_requests=0.0, kv_usage=0.2, preemptions_per_s=0.0, gpu_util=0.9,
                running_requests=4.0)
    base.update(cheap)
    return dict(kind='window', t=t, cheap=base, inflight_p95_s=age)


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))


def burst(i, busy, gemm, attention):
    return dict(capture_id=f'cal{i:05d}', activity=dict(busy_fraction=busy,
                                                        family_ns_per_token=dict(gemm=gemm, attention=attention)))


def build(root, *, overload_attention=(2.0, 2.0, 2.0)):
    """Three seeds; controlled healthy/overload/kv/host_stall and one real case's fixed side."""
    for k, seed in enumerate(('101', '102', '103')):
        ctl = root / seed / 'controlled'
        (ctl / 'baseline.json').parent.mkdir(parents=True, exist_ok=True)
        (ctl / 'baseline.json').write_text(json.dumps(dict(p95_base_s=2.0, baseline_ns_per_token=dict(gemm=100.0, attention=10.0))))
        # healthy: ages 1.6-2.4 s around p95_base 2.0 -> L 0.8-1.2; first quarter (t < 25) is excluded
        write(ctl / 'baseline' / 'events.jsonl', [window(t, age=(9.0 if t < 25 else 1.6 + 0.008 * (t - 25)),
                                                         waiting_requests=float(t % 3)) for t in range(100)])
        write(ctl / 'ctl_overload' / 'events.jsonl', [window(t, age=8.0, latency_ratio=99.0, waiting_requests=40.0, gpu_util=0.95)
                                                      for t in range(60, 180)])
        write(ctl / 'ctl_overload' / 'bursts.jsonl', [burst(i, 0.95, 50.0, 10.0 * overload_attention[k]) for i in range(4)])
        write(ctl / 'ctl_kv' / 'events.jsonl', [window(t, age=6.0, kv_usage=0.98, preemptions_per_s=2.0)
                                                for t in range(60, 180)])
        write(ctl / 'ctl_engine_stall' / 'events.jsonl', [window(t, age=6.0, gpu_util=0.25) for t in range(60, 180)])
        write(ctl / 'ctl_engine_stall' / 'bursts.jsonl', [burst(i, 0.15, 100.0, 10.0) for i in range(4)])
        case = root / seed / '6240'
        (case / 'baseline.json').parent.mkdir(parents=True, exist_ok=True)
        (case / 'baseline.json').write_text(json.dumps(dict(p95_base_s=5.0, baseline_ns_per_token=dict(gemm=1000.0))))
        write(case / 'baseline' / 'events.jsonl', [window(t, age=5.0) for t in range(100)])
        write(case / 'incident' / 'events.jsonl', [window(t, age=6.0) for t in range(60, 180)])
        write(case / 'incident' / 'bursts.jsonl', [burst(i, 0.9, 900.0, 5.0) for i in range(4)])


class DeriveTests(unittest.TestCase):
    def derive(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            build(Path(d), **kw)
            sessions = dt.load(d)
            return dt.derive(sessions), dt.leave_one_out(sessions), sessions

    def test_cheap_thresholds_follow_the_rules(self):
        r, _, _ = self.derive()
        t = r['thresholds']
        self.assertAlmostEqual(t['latency_ratio'], 1.10)  # p99 of healthy L (ages up to 2.19 s / 2.0 s), up to 0.05
        self.assertAlmostEqual(t['waiting_requests'], 3.0)  # p99 waiting 2 + 1
        self.assertAlmostEqual(t['kv_usage'], (0.2 + 0.98) / 2)
        self.assertEqual(t['preemptions_per_s'], 0.5)       # healthy p99 is 0, floor 0.5
        self.assertAlmostEqual(t['gpu_util'], (0.25 + 0.95) / 2)
        self.assertAlmostEqual(t['busy_fraction'], (0.15 + 0.95) / 2)
        self.assertGreater(r['margins']['gpu_util'], 0)
        # overload L recomputed from age 8.0 / p95_base 2.0 = 4.0, not the stale stored 99.0
        self.assertAlmostEqual(r['inputs']['overload_median']['latency_ratio'], 4.0)

    def test_kernel_ratio_falls_back_to_load_matched_when_load_inflates_attention(self):
        r, _, _ = self.derive()  # overload attention 2x the healthy baseline: option 1 = 2.5 > 2.0
        chain = {c['option']: c for c in r['kernel']['chain']}
        self.assertAlmostEqual(chain['healthy_load_baseline']['theta'], 2.5)
        self.assertFalse(chain['healthy_load_baseline']['qualifies'])
        self.assertEqual(r['kernel']['chosen'], 'load_matched_baseline')
        self.assertAlmostEqual(r['thresholds']['kernel_time_ratio'], 1.25)  # identical seeds: max ratio 1.0

    def test_seed_to_seed_variation_sets_the_load_matched_threshold(self):
        r, _, _ = self.derive(overload_attention=(2.0, 2.0, 2.4))
        # seed 103's attention vs the median of seeds 101/102: 24/20 = 1.2 -> theta 1.5
        self.assertAlmostEqual(r['thresholds']['kernel_time_ratio'], 1.5)

    def test_healthy_load_option_wins_when_it_qualifies(self):
        r, _, _ = self.derive(overload_attention=(1.2, 1.2, 1.2))
        self.assertEqual(r['kernel']['chosen'], 'healthy_load_baseline')
        self.assertAlmostEqual(r['thresholds']['kernel_time_ratio'], 1.5)

    def test_leave_one_out_covers_cases_and_conditions(self):
        _, loo, _ = self.derive()
        self.assertIn('without_case_6240', loo['runs'])
        self.assertIn('without_ctl_kv', loo['runs'])
        self.assertNotIn('without_healthy', loo['runs'])
        self.assertIsNone(loo['runs']['without_ctl_kv']['kv_usage'])  # no KV condition left: rule cannot be applied

    def test_only_fixed_and_controlled_sessions_are_loaded(self):
        _, _, sessions = self.derive()
        self.assertEqual({s['condition'] for s in sessions},
                         {'healthy', 'ctl_overload', 'ctl_kv', 'ctl_engine_stall', '6240:incident'})

    def test_replaced_baseline_directory_is_not_a_session(self):
        with tempfile.TemporaryDirectory() as d:
            build(Path(d))
            write(Path(d) / '101' / '6240' / 'baseline_idle_capture' / 'events.jsonl', [window(t, age=50.0) for t in range(60, 180)])
            sessions = dt.load(d)
        self.assertEqual(sum(s['condition'] == '6240:incident' for s in sessions), 3)

    def test_load_matched_bursts_pair_by_capture_id(self):
        with tempfile.TemporaryDirectory() as d:
            build(Path(d))
            # seed 101 lost its first burst (no activity): the remaining ones must still pair with the same times
            rows = [burst(i, 0.95, 50.0, 10.0 * (1 + i)) for i in range(4)]
            for seed in ('101', '102', '103'):
                write(Path(d) / seed / 'controlled' / 'ctl_overload' / 'bursts.jsonl', rows[1:] if seed == '101' else rows)
            r = dt.derive(dt.load(d))
        self.assertAlmostEqual(dict((c['option'], c) for c in r['kernel']['chain'])['load_matched_baseline']['max_ratio'], 1.0)


if __name__ == '__main__':
    unittest.main()
