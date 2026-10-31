import unittest

from experiments.tracing.rule_diagnosis import (CheapWindow, HeavyBurst, RuleThresholds, busy_fraction, diagnose,
                                             kernel_shares, normalize_kernel_name)

# Synthetic thresholds for unit tests only; the study values come from calibration.
T = RuleThresholds(latency_ratio=1.5, waiting_requests=4, kv_usage=0.9, preemptions_per_s=0.5,
                   gpu_util=0.6, busy_fraction=0.5, kernel_time_ratio=1.3)


def cheap(**kw):
    base = dict(latency_ratio=2.0, waiting_requests=0, kv_usage=0.3, preemptions_per_s=0.0, gpu_util=0.95,
                running_requests=8)
    return CheapWindow(**{**base, **kw})


def burst(busy=0.9, per_token=None, baseline=None):
    # ns of GPU time per processed token by kernel family
    return HeavyBurst('ev-1', busy, per_token or {'gemm': 1000.0, 'attention': 300.0},
                      baseline or {'gemm': 1000.0, 'attention': 300.0}, {'gemm': 'Kernel<cutlass_x>', 'attention': 'flash'})


class RuleDiagnosisTests(unittest.TestCase):
    def test_unset_thresholds_never_produce_a_concrete_diagnosis(self):
        d = diagnose(cheap(), RuleThresholds())
        self.assertEqual(d.causes, ('unknown',))
        self.assertIsNone(d.label)
        self.assertFalse(RuleThresholds().frozen())
        self.assertTrue(T.frozen())

    def test_latency_not_elevated_is_healthy(self):
        self.assertEqual(diagnose(cheap(latency_ratio=1.1), T).causes, ('healthy',))

    def test_missing_latency_is_unknown_not_healthy(self):
        self.assertEqual(diagnose(cheap(latency_ratio=None), T).causes, ('unknown',))

    def test_preemptions_give_kv_pressure(self):
        self.assertEqual(diagnose(cheap(preemptions_per_s=2.0, waiting_requests=10), T).causes, ('kv_pressure',))

    def test_kv_pressure_without_preemption_counter_uses_usage_and_queue(self):
        # v0.3.x exposes no preemption counter
        d = diagnose(cheap(preemptions_per_s=None, kv_usage=0.95, waiting_requests=3), T)
        self.assertEqual(d.causes, ('kv_pressure',))
        d = diagnose(cheap(preemptions_per_s=None, kv_usage=0.95, waiting_requests=0), T)
        self.assertNotIn('kv_pressure', d.causes)

    def test_queue_pressure_needs_busy_gpu_and_waiting(self):
        self.assertEqual(diagnose(cheap(waiting_requests=8), T).causes, ('queue_pressure',))
        self.assertEqual(diagnose(cheap(waiting_requests=1), T).causes, ('unknown',))

    def test_cheap_host_bound_proxy(self):
        self.assertEqual(diagnose(cheap(gpu_util=0.2, waiting_requests=8), T).causes, ('host_bound',))

    def test_heavy_busy_fraction_overrides_cheap_proxy(self):
        d = diagnose(cheap(gpu_util=0.95), T, burst(busy=0.2))
        self.assertEqual(d.causes, ('host_bound',))
        self.assertEqual(d.evidence_id, 'ev-1')

    def test_kernel_hotspot_names_the_family_with_the_largest_per_token_time_ratio(self):
        d = diagnose(cheap(), T, burst(per_token={'gemm': 1800.0, 'attention': 310.0}))
        self.assertEqual(d.causes, ('kernel_hotspot',))
        self.assertEqual((d.kernel, d.top_kernel), ('gemm', 'Kernel<cutlass_x>'))
        self.assertEqual(d.label, 'kernel_hotspot:gemm')

    def test_batching_lowers_per_token_time_and_is_not_a_hotspot(self):
        # Commissioning flaw 2: overload changes the GEMM variant mix but lowers per-token GEMM time.
        d = diagnose(cheap(waiting_requests=50), T, burst(per_token={'gemm': 400.0, 'attention': 200.0}))
        self.assertEqual(d.causes, ('queue_pressure',))

    def test_missing_token_count_makes_kernel_condition_unknown(self):
        d = diagnose(cheap(), T, HeavyBurst('ev', 0.9, None, {'gemm': 1.0}))
        self.assertIn('unknown:kernel_time_per_token', d.reasons)
        self.assertNotIn('kernel_hotspot', d.causes)

    def test_family_absent_from_baseline_is_skipped(self):
        d = diagnose(cheap(), T, burst(per_token={'gemm': 1000.0, 'attention': 300.0, 'other': 900.0}))
        self.assertNotIn('kernel_hotspot', d.causes)

    def test_kernel_hotspot_is_impossible_without_heavy_evidence(self):
        self.assertNotIn('kernel_hotspot', diagnose(cheap(), T).causes)

    def test_overlapping_causes_form_a_set(self):
        d = diagnose(cheap(preemptions_per_s=2.0), T, burst(per_token={'gemm': 2000.0, 'attention': 300.0}))
        self.assertEqual(d.causes, ('kernel_hotspot', 'kv_pressure'))
        self.assertEqual(d.label, 'kernel_hotspot:gemm+kv_pressure')

    def test_idle_gpu_without_pending_work_is_not_host_bound(self):
        # Commissioning flaw 1: queue drained, lagging latency, idle GPU.
        for heavy in (None, burst(busy=0.1)):
            d = diagnose(cheap(gpu_util=0.1, waiting_requests=0, running_requests=0), T, heavy)
            self.assertNotIn('host_bound', d.causes)
            self.assertIn('idle_without_pending_work', d.reasons)

    def test_unknown_pending_work_is_not_host_bound(self):
        d = diagnose(cheap(gpu_util=0.1, waiting_requests=None, running_requests=None), T)
        self.assertIn('unknown:host_bound_without_pending_work', d.reasons)

    def test_missing_gpu_util_is_reported_unknown(self):
        d = diagnose(cheap(gpu_util=None, waiting_requests=8), T)
        self.assertEqual(d.causes, ('unknown',))
        self.assertIn('unknown:gpu_util', d.reasons)

    def test_assume_elevated_assesses_causes_in_a_recovered_window(self):
        recovered = cheap(latency_ratio=1.0)
        self.assertEqual(diagnose(recovered, T, burst(busy=0.2)).causes, ('healthy',))
        self.assertEqual(diagnose(recovered, T, burst(busy=0.2), assume_elevated=True).causes, ('host_bound',))

    def test_digest_changes_with_any_threshold(self):
        from dataclasses import replace
        self.assertNotEqual(T.digest(), replace(T, gpu_util=0.61).digest())

    def test_kernel_families(self):
        from experiments.tracing.rule_diagnosis import kernel_family
        self.assertEqual(kernel_family('Kernel2<cutlass_80_tensorop_bf16_s16816gemm_relu_bf16_256x128_32x3_tn_align8>'), 'gemm')
        self.assertEqual(kernel_family('ampere_bf16_s16816gemm_bf16_64x64_ldg8_f2f_stages_64x5_tn'), 'gemm')
        self.assertEqual(kernel_family('flash_fwd_splitkv_kernel'), 'attention')
        self.assertEqual(kernel_family('fused_add_rms_norm_kernel<c10::BFloat16>'), 'norm')
        self.assertEqual(kernel_family('act_and_mul_kernel<c10::BFloat16>'), 'other')

    def test_family_time_per_token(self):
        from experiments.tracing.rule_diagnosis import family_time_per_token
        per, top = family_time_per_token([('Kernel<cutlass_a>', 600), ('Kernel<cutlass_b>', 200), ('flash_fwd', 200)], 100)
        self.assertEqual(per, {'gemm': 8.0, 'attention': 2.0})
        self.assertEqual(top, {'gemm': 'Kernel<cutlass_a>', 'attention': 'flash_fwd'})
        self.assertEqual(family_time_per_token([('x', 1)], 0)[0], None)


class KernelEvidenceTests(unittest.TestCase):
    def test_busy_fraction_takes_the_union_of_overlapping_intervals(self):
        self.assertAlmostEqual(busy_fraction([(0, 40), (20, 60), (80, 90)], 0, 100), 0.7)

    def test_busy_fraction_clips_to_window(self):
        self.assertAlmostEqual(busy_fraction([(-10, 10), (95, 120)], 0, 100), 0.15)

    def test_busy_fraction_rejects_empty_window(self):
        with self.assertRaises(ValueError):
            busy_fraction([], 5, 5)

    def test_kernel_name_keeps_cutlass_configuration_argument(self):
        # Real name from the v0.5.5 commissioning capture
        name = 'void cutlass::Kernel<cutlass_80_wmma_tensorop_bf16_s161616gemm_bf16_16x16_128x1_tn_align8>(T1::Params)'
        self.assertEqual(normalize_kernel_name(name),
                         'cutlass::Kernel<cutlass_80_wmma_tensorop_bf16_s161616gemm_bf16_16x16_128x1_tn_align8>')
        self.assertEqual(normalize_kernel_name('ampere_fp16_s16816gemm_fp16_128x128_ldg8_f2f_tn'),
                         'ampere_fp16_s16816gemm_fp16_128x128_ldg8_f2f_tn')

    def test_kernel_name_drops_non_identifier_templates_and_unnamed_namespaces(self):
        name = ('void at::native::<unnamed>::cunn_SoftMaxForward<(int)4, float, float, float, '
                'at::native::<unnamed>::SoftMaxForwardEpilogue>(T4 *, const T2 *, int)')
        self.assertEqual(normalize_kernel_name(name), 'at::native::anon::cunn_SoftMaxForward')
        lam = 'void at::native::elementwise_kernel<(int)128, (int)4, void at::native::gpu_kernel_impl<F>(X)::[lambda()]>(int, T3)'
        self.assertEqual(normalize_kernel_name(lam), 'at::native::elementwise_kernel')

    def test_kernel_identity_uses_short_name_past_templated_return_types(self):
        from experiments.tracing.rule_diagnosis import kernel_identity
        # Real demangled name from the v0.5.5 node-traced capture
        name = ('std::enable_if<T2>(int)0&&vllm::_typeConvert<T1>::exists, void>::type '
                'vllm::fused_add_rms_norm_kernel<c10::BFloat16, (int)8>(T1 *, T1 *, const T1 *, float, int, int)')
        self.assertEqual(kernel_identity(name, 'fused_add_rms_norm_kernel'), 'fused_add_rms_norm_kernel<c10::BFloat16>')
        cut = 'void cutlass::Kernel<cutlass_80_wmma_tensorop_bf16_s161616gemm_bf16_16x16_128x2_tn_align8>(T1::Params)'
        self.assertEqual(kernel_identity(cut, 'Kernel'),
                         'Kernel<cutlass_80_wmma_tensorop_bf16_s161616gemm_bf16_16x16_128x2_tn_align8>')
        self.assertEqual(kernel_identity('flash_fwd_splitkv_kernel', 'flash_fwd_splitkv_kernel'), 'flash_fwd_splitkv_kernel')
        self.assertEqual(kernel_identity(cut, None), normalize_kernel_name(cut))

    def test_kernel_shares_merge_normalized_names_and_sum_to_one(self):
        shares = kernel_shares([('k<1>(a)', 30), ('k<2>(b)', 30), ('other', 40)])
        self.assertEqual(shares, {'k': 0.6, 'other': 0.4})


if __name__ == '__main__':
    unittest.main()


class PolicyLabelTests(unittest.TestCase):
    def test_study_rule_labels_drive_stability_and_healthy_does_not(self):
        from experiments.tracing.policies import is_concrete_label
        for label in ('host_bound', 'kv_pressure+queue_pressure', 'kernel_hotspot:cutlass_scaled_mm',
                      'kernel_hotspot:a+kv_pressure', 'vllm_queue_pressure'):
            self.assertTrue(is_concrete_label(label), label)
        for label in (None, '', 'healthy', 'unknown', 'kernel_hotspot:', 'host_bound+healthy', 'made_up'):
            self.assertFalse(is_concrete_label(label), label)

    def test_rule_label_round_trip(self):
        from experiments.tracing.policies import is_concrete_label
        d = diagnose(cheap(gpu_util=0.2), T)
        self.assertTrue(is_concrete_label(d.label))
        self.assertTrue(is_concrete_label('kernel_hotspot:gemm'))
        healthy = diagnose(cheap(latency_ratio=1.0), T).label
        self.assertEqual(healthy, 'healthy')
        self.assertFalse(is_concrete_label(healthy))
        self.assertIsNone(diagnose(cheap(latency_ratio=None), T).label)
