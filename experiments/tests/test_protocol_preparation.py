"""CPU design contracts: no workload truth in jobs, no pretend protocol freeze."""
import copy
import json
from pathlib import Path
import unittest

from experiments.scripts.prepare_protocol import compile_design, validate

ROOT=Path(__file__).resolve().parents[2]


class ProtocolPreparationTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'experiments/configs/l4_protocol_draft.json').read_text())

    def test_design_pairs_every_case_seed_with_every_arm_once(self):
        public,private,summary=compile_design(self.config)
        self.assertEqual(summary['runs'],144)
        self.assertEqual(summary['blocks'],18)
        self.assertEqual(summary['observation_hours'],4.8)
        self.assertEqual(summary['observation_plus_max_drain_hours'],6.6)
        self.assertFalse(summary['gpu_used'])
        self.assertFalse(summary['launch_supported'])
        observed={(r['case_id'],r['seed'],r['arm']) for r in private['runs']}
        expected={(c['id'],s,a) for c in self.config['cases']
                  for s in self.config['splits']['development']['seeds'] for a in self.config['arms']}
        self.assertEqual(observed,expected)
        self.assertEqual(len(observed),len(public['controller_jobs']))
        self.assertEqual({r['run_id'] for r in private['runs']},{r['run_id'] for r in public['controller_jobs']})

    def test_controller_jobs_exclude_intervention_and_reference_metadata(self):
        allowed={'run_id','block','arm','split','horizon_s','window_s','drain_s','requested_burst_s',
                 'max_bursts','stability_windows','repeated_bursts','recovery_windows','reactivation_enabled'}
        public,private,_=compile_design(self.config)
        for row in public['controller_jobs']:
            self.assertEqual(set(row),allowed)
            self.assertFalse(any(case['id'] in row['run_id'] for case in self.config['cases']))
        self.assertTrue(all('phases' in row and 'case_id' in row for row in private['runs']))

    def test_compilation_is_deterministic_without_mutating_configuration(self):
        original=copy.deepcopy(self.config)
        self.assertEqual(compile_design(self.config),compile_design(self.config))
        self.assertEqual(self.config,original)
        self.config['schedule_seed']+=1
        self.assertNotEqual(compile_design(self.config),compile_design(original))

    def test_phase_gap_and_overlap_are_rejected(self):
        for offset in (-1,1):
            with self.subTest(offset=offset):
                config=copy.deepcopy(self.config)
                config['cases'][1]['phases'][1]['start_s']+=offset
                with self.assertRaisesRegex(ValueError,'gap, overlap'):
                    validate(config)

    def test_calibration_and_confirmation_seed_overlap_is_rejected(self):
        self.config['splits']['confirmation']['seeds'][0]=2101
        with self.assertRaisesRegex(ValueError,'disjoint'):
            validate(self.config)

    def test_new_seeds_with_reused_corpus_are_not_a_heldout_split(self):
        self.config['splits']['confirmation']['request_corpus']=self.config['splits']['calibration']['request_corpus']
        with self.assertRaisesRegex(ValueError,'corpora and workload families'):
            validate(self.config)

    def test_mu_alias_cannot_be_an_extra_comparison_arm(self):
        self.config['arms'].append('marginal_utility_stop')
        with self.assertRaisesRegex(ValueError,'five distinct policies'):
            validate(self.config)

    def test_insufficient_budget_cannot_claim_to_exercise_stability(self):
        self.config['max_bursts']=1
        with self.assertRaisesRegex(ValueError,'Budget cannot exercise'):
            validate(self.config)

    def test_draft_compiler_cannot_certify_a_frozen_study(self):
        for status,blockers in [('frozen',self.config['unresolved_before_freeze']),('draft_not_frozen',[])]:
            with self.subTest(status=status):
                config=copy.deepcopy(self.config);config.update(status=status,unresolved_before_freeze=blockers)
                with self.assertRaisesRegex(ValueError,'cannot certify a freeze'):
                    validate(config)


if __name__=='__main__':
    unittest.main()
