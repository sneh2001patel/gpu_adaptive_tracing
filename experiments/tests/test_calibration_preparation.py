"""Preparation must not promote fixtures, intended interventions or heldout data."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from experiments.evaluation.calibration_preparation import prepare
from experiments.tracing.live_features import LiveFeatureWindow
from experiments.tracing.timing import ManualClock
from experiments.tests.test_live_features import binding,receipt


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config=json.loads(Path('experiments/configs/l4_protocol_draft.json').read_text())
        clock=ManualClock(120);scope=binding(clock.domain)
        window=LiveFeatureWindow(clock,100,200,binding=scope,provenance='synthetic_simulation',min_latency_samples=1)
        window.on_scrape(receipt(scope));clock.advance_to(200)
        self.observation=asdict(window.observation('o1'));self.path=self.root/'observation.json'
        self.path.write_text(json.dumps(self.observation))
        self.entry=dict(run_id='cal-run',split='calibration',observation_path='observation.json')
    def test_empty_packet_is_explicit_non_executable_preparation(self):
        packet=prepare(self.config,[],self.root)
        self.assertEqual(len(packet['collection_jobs']),18);self.assertEqual(len(packet['evaluator_only']),9)
        for field in ('calibration_enabled','fitting_supported','launch_supported','study_ready','protocol_frozen'):
            self.assertFalse(packet[field])
        self.assertTrue(packet['blockers']);self.assertEqual(packet['observed_feature_inventory'],[])
    def test_availability_inventory_preserves_nulls_counts_and_fixture_provenance(self):
        row=prepare(self.config,[self.entry],self.root)['observed_feature_inventory'][0]
        self.assertEqual(row['provenance'],'synthetic_simulation')
        self.assertEqual(row['features']['queue_depth_mean']['value'],3)
        self.assertIsNone(row['features']['request_wait_p95_ms']['value'])
        self.assertIn('sha256',row)
    def test_confirmation_and_development_rejected(self):
        for split in ('development','confirmation'):
            with self.assertRaises(ValueError):prepare(self.config,[self.entry|dict(split=split)],self.root)
    def test_extra_truth_fields_rejected_at_entry_and_observation(self):
        with self.assertRaises(ValueError):prepare(self.config,[self.entry|dict(expected_cause='queue_pressure')],self.root)
        self.path.write_text(json.dumps(self.observation|dict(expected_cause='queue_pressure')))
        with self.assertRaises(ValueError):prepare(self.config,[self.entry],self.root)
    def test_duplicate_observations_and_path_escape_rejected(self):
        with self.assertRaises(ValueError):prepare(self.config,[self.entry,self.entry],self.root)
        with self.assertRaises(ValueError):prepare(self.config,[self.entry|dict(observation_path='../outside')],self.root)
    def test_mixed_live_and_synthetic_inventory_rejected(self):
        (self.root/'live.json').write_text(json.dumps(self.observation|dict(provenance='live_online',observation_id='o2')))
        with self.assertRaises(ValueError):prepare(self.config,[self.entry,self.entry|dict(observation_path='live.json')],self.root)
    def test_collection_jobs_have_no_reference_labels_or_prediction_inputs(self):
        packet=prepare(self.config,[],self.root)
        self.assertTrue(all('intended_intervention' not in job for job in packet['collection_jobs']))
        self.assertTrue(all(job['fresh_owned_restart'] and not job['schedule_resolved'] for job in packet['collection_jobs']))
        self.assertTrue(all(r['adjudication_status']=='not_started' for r in packet['evaluator_only']))
        self.assertNotIn('supported_causes',json.dumps(packet))
