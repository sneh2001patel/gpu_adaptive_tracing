import unittest

from revision.tracing.episode_controller import ArmConfig, EpisodeController
from revision.tracing.policies import PolicyConfig
from revision.tracing.rule_diagnosis import CheapWindow, RuleThresholds

# Synthetic thresholds for unit tests only.
T = RuleThresholds(latency_ratio=1.5, waiting_requests=4, kv_usage=0.9, preemptions_per_s=0.5,
                   gpu_util=0.6, busy_fraction=0.5, kernel_time_ratio=1.3)
BASE = {'gemm': 1000.0, 'attention': 300.0}     # baseline GPU ns per processed token by family
HOT = dict(busy_fraction=0.9, family_ns_per_token={'gemm': 1800.0, 'attention': 300.0},
           family_top_kernel={'gemm': 'Kernel<cutlass_x>'})                  # kernel_hotspot:gemm
IDLE = dict(busy_fraction=0.2, family_ns_per_token={'gemm': 1000.0, 'attention': 300.0})   # host_bound


def w(latency=2.0, gpu=0.95):
    return CheapWindow(latency_ratio=latency, waiting_requests=0, kv_usage=0.2, preemptions_per_s=0.0, gpu_util=gpu,
                       running_requests=8)


def run(arm, windows, bursts):
    """Feed windows; whenever a capture is requested, answer with the next burst result."""
    c, results, bursts = EpisodeController(arm, T, BASE), [], list(bursts)
    for i, cheap in enumerate(windows):
        if c.on_window(f'w{i}', float(i), cheap)['capture']:
            activity = bursts.pop(0)
            results.append(c.on_burst(f'b{len(results) + 1}', activity, None if activity else 'export_failed'))
    return c, results, c.finish()


class TriggerTests(unittest.TestCase):
    def test_episode_starts_after_consecutive_elevated_windows(self):
        c = EpisodeController(ArmConfig('FIX', fixed_bursts=1), T, BASE)
        self.assertFalse(c.on_window('w0', 0, w(latency=2.0))['capture'])
        self.assertEqual(c.state, 'idle')
        self.assertTrue(c.on_window('w1', 1, w(latency=2.0))['capture'])
        self.assertEqual(c.state, 'active')

    def test_interrupted_elevation_resets_the_trigger(self):
        c = EpisodeController(ArmConfig('FIX'), T, BASE)
        for i, lat in enumerate((2.0, 1.0, 2.0)):
            c.on_window(f'w{i}', i, w(latency=lat))
        self.assertEqual(c.state, 'idle')

    def test_missing_latency_never_triggers(self):
        c = EpisodeController(ArmConfig('FIX'), T, BASE)
        for i in range(5):
            c.on_window(f'w{i}', i, w(latency=None))
        self.assertEqual(c.state, 'idle')


class ArmTests(unittest.TestCase):
    def test_nt_never_captures_but_records_cheap_diagnoses(self):
        c, results, ep = run(ArmConfig('NT'), [w(gpu=0.2)] * 6, [])
        self.assertEqual(results, [])
        self.assertEqual(ep['bursts'], 0)
        self.assertEqual(ep['decision']['reason'], 'horizon_ended')
        self.assertEqual(c.events[-1]['cheap_diagnosis'], 'host_bound')

    def test_fix3_takes_exactly_three_bursts(self):
        _, results, ep = run(ArmConfig('FIX', fixed_bursts=3), [w()] * 10, [HOT] * 5)
        self.assertEqual(len(results), 3)
        self.assertEqual(ep['decision']['reason'], 'repeated_bursts_complete')
        self.assertEqual(results[0]['heavy_diagnosis'], 'kernel_hotspot:gemm')

    def test_fix1_is_fixed_burst(self):
        _, results, ep = run(ArmConfig('FIX', fixed_bursts=1), [w()] * 6, [IDLE])
        self.assertEqual((len(results), ep['decision']['reason']), (1, 'fixed_burst_complete'))

    def test_stability_stops_when_two_fresh_bursts_agree(self):
        _, results, ep = run(ArmConfig('SS'), [w()] * 10, [IDLE, IDLE, IDLE])
        self.assertEqual(len(results), 2)
        self.assertEqual(ep['decision']['reason'], 'diagnosis_stable')

    def test_stability_restarts_when_the_diagnosis_changes(self):
        _, results, ep = run(ArmConfig('SS'), [w()] * 10, [IDLE, HOT, HOT])
        self.assertEqual(len(results), 3)
        self.assertEqual(ep['decision']['diagnosis_label'], 'kernel_hotspot:gemm')

    def test_failed_burst_spends_budget_and_cannot_establish_stability(self):
        arm = ArmConfig('SS', policy=PolicyConfig(max_bursts=3))
        _, results, ep = run(arm, [w()] * 10, [None, IDLE, None])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['failure'], 'export_failed')
        self.assertEqual(ep['decision']['reason'], 'budget_exhausted')

    def test_hybrid_needs_recovery_as_well_as_stability(self):
        # Stable host_bound diagnoses, latency stays elevated: hybrid exhausts its budget.
        arm = ArmConfig('HS', policy=PolicyConfig(max_bursts=4))
        _, results, ep = run(arm, [w()] * 12, [IDLE] * 4)
        self.assertEqual(ep['decision']['reason'], 'budget_exhausted')
        # Same diagnoses, but latency recovers before the second burst: stable_and_recovered.
        windows = [w(), w()] + [w(latency=1.0, gpu=0.3)] * 6
        _, _, ep = run(arm, windows, [IDLE] * 4)
        self.assertEqual(ep['decision']['reason'], 'stable_and_recovered')

    def test_only_one_burst_outstanding_at_a_time(self):
        c = EpisodeController(ArmConfig('FIX', fixed_bursts=3), T, BASE)
        c.on_window('w0', 0, w())
        self.assertTrue(c.on_window('w1', 1, w())['capture'])
        self.assertFalse(c.on_window('w2', 2, w())['capture'])   # burst still running
        c.on_burst('b1', HOT)
        self.assertTrue(c.on_window('w3', 3, w())['capture'])

    def test_burst_without_request_is_rejected(self):
        with self.assertRaises(ValueError):
            EpisodeController(ArmConfig('FIX'), T, BASE).on_burst('b1', HOT)

    def test_windows_after_stop_are_still_recorded(self):
        c, _, ep = run(ArmConfig('FIX', fixed_bursts=1), [w()] * 3 + [w(latency=1.0)] * 3, [HOT])
        self.assertEqual(ep['final_state'], 'done')
        # Triggered at w1 and stopped at w1's burst, so w2..w5 follow the stop.
        self.assertEqual(sum(e['kind'] == 'window' and e['state'] == 'done' for e in c.events), 4)


if __name__ == '__main__':
    unittest.main()
