"""Offline audit contracts and synthetic gap-review inputs; no GPU or adjudication."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from revision.evaluation.evidence_assessment import (Bundle,audit_bundle,draft_rubric,review_template,validate_gap_review)

ROOT=Path('revision/hardware/l4_20261028/pairs_001')

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'data.json').write_text('{}');self.expected=hashlib.sha256(b'{}').hexdigest()
        self.manifest=dict(files={'data.json':self.expected});self.write_manifest()
    def write_manifest(self):
        (self.root/'artifact_manifest.json').write_text(json.dumps(self.manifest))
    def test_manifest_and_expected_identity_verified(self):
        expected=hashlib.sha256((self.root/'artifact_manifest.json').read_bytes()).hexdigest()
        self.assertEqual(Bundle(self.root,expected).json('data.json'),{})
        with self.assertRaises(ValueError):Bundle(self.root,'0'*64)
    def test_modified_raw_file_rejected(self):
        (self.root/'data.json').write_text('{"changed":1}')
        with self.assertRaises(ValueError):Bundle(self.root)
    def test_unmanifested_metadata_rejected(self):
        (self.root/'extra.json').write_text('{}')
        with self.assertRaises(ValueError):Bundle(self.root).json('extra.json')
    def test_parent_escape_and_absolute_paths_rejected(self):
        for path in ('../escape','/tmp/escape'):
            self.manifest=dict(files={path:self.expected});self.write_manifest()
            with self.assertRaises(ValueError):Bundle(self.root)
    def test_symlink_not_accepted_even_to_file_inside_root(self):
        (self.root/'link.json').symlink_to(self.root/'data.json')
        self.manifest=dict(files={'link.json':self.expected});self.write_manifest()
        with self.assertRaises(ValueError):Bundle(self.root)


class AuditReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=audit_bundle(ROOT);cls.rubric=draft_rubric()
        cls.paths=[path for pair in cls.audit['pairs'] for path in pair['artifact_paths']]
    def form(self):
        form=review_template(self.audit,self.rubric)
        form.update(assessor_id='synthetic_test_assessor_not_actual_adjudication',blinded_to_predictions_and_policy=False,status='completed',limitations=['Fixture review only; no human adjudication.'])
        for pair in form['pairs']:
            pair.update(outcome='unresolved',reviewed_artifacts=next(p['artifact_paths'] for p in self.audit['pairs'] if p['pair_id']==pair['pair_id']))
            for name in ('work_mismatch_rationale','latency_mismatch_rationale','negative_evidence_limits','clock_and_cohort_limits','additional_evidence_needed'):
                pair[name]='Synthetic review text for contract validation only.'
        return form
    def validate(self,form):return validate_gap_review(form,self.audit,self.rubric,self.paths)
    def test_real_saved_receipts_show_sparse_p95_and_zero_sampled_queue(self):
        self.assertEqual(self.audit['verified_artifact_entries'],472)
        self.assertEqual(sum(j['queue_sample_count'] for j in self.audit['jobs']),64)
        self.assertEqual(sum(j['queue_positive_samples'] for j in self.audit['jobs']),0)
        self.assertTrue(all('request_p95_ms' in w['missing'] for j in self.audit['jobs'] for w in j['windows']))
        self.assertTrue(all(j['max_queue_receipt_gap_including_edges_ms']>0 for j in self.audit['jobs']))
    def test_no_healthy_or_run_equivalence_inferred_from_close_latency(self):
        for pair in self.audit['pairs']:
            self.assertTrue(pair['actual_ID_and_token_work_equal'])
            self.assertIsNone(pair['latency_tolerance_ratio']);self.assertEqual(pair['reference_eligibility'],'not_established')
            self.assertEqual(len(pair['client_latency_deltas']),2)
        self.assertFalse(self.audit['calibration_enabled'])
    def test_two_traces_reparsed_without_invented_clock_mapping(self):
        traces=[j['trace'] for j in self.audit['jobs'] if j['trace']]
        self.assertEqual([t['kernel_count'] for t in traces],[21308,23044])
        self.assertTrue(all(not t['per_request_GPU_clock_mapping'] and t['capture_active_s'] is None for t in traces))
    def test_rubric_is_draft_has_no_fitted_limits_or_reference_export(self):
        self.assertTrue(all(v is None for v in self.rubric['prospective_limits_required'].values()))
        self.assertFalse(self.rubric['reference_export_enabled']);self.assertFalse(self.rubric['threshold_fitting_enabled'])
        self.assertNotIn('prefill_service_fraction',self.rubric['candidate_features'])
    def test_template_is_unstarted_and_not_a_reference(self):
        form=review_template(self.audit,self.rubric)
        self.assertIsNone(form['assessor_id']);self.assertEqual(form['status'],'not_started')
        with self.assertRaises(ValueError):self.validate(form)
    def test_completed_gap_review_still_creates_no_reference(self):
        result=self.validate(self.form())
        self.assertEqual(result['references_created'],0);self.assertEqual(result['references_locked'],0)
        self.assertFalse(result['reference_export_enabled']);self.assertFalse(result['calibration_enabled'])
    def test_stale_audit_or_rubric_hash_rejected(self):
        for field in ('audit_sha256','rubric_sha256'):
            form=self.form();form[field]='0'*64
            with self.assertRaises(ValueError):self.validate(form)
    def test_missing_identity_blinding_limitations_or_rationale_rejected(self):
        for changes in (dict(assessor_id=None),dict(blinded_to_predictions_and_policy='yes'),dict(limitations=[])):
            with self.assertRaises(ValueError):self.validate(self.form()|changes)
        form=self.form();form['pairs'][0]['negative_evidence_limits']=' '
        with self.assertRaises(ValueError):self.validate(form)
    def test_healthy_supported_or_cause_truth_fields_rejected(self):
        for outcome in ('healthy','supported','queue_pressure'):
            form=self.form();form['pairs'][0]['outcome']=outcome
            with self.assertRaises(ValueError):self.validate(form)
        form=self.form();form['expected_cause']='queue_pressure'
        with self.assertRaises(ValueError):self.validate(form)
    def test_unknown_wrong_pair_duplicate_and_unreviewed_artifacts_rejected(self):
        for paths in ([],['missing'],[self.paths[0],self.paths[0]],self.audit['pairs'][1]['artifact_paths']):
            form=self.form();form['pairs'][0]['reviewed_artifacts']=paths
            with self.assertRaises(ValueError):self.validate(form)
    def test_missing_or_duplicate_pair_review_rejected(self):
        form=self.form();form['pairs']=form['pairs'][:1]
        with self.assertRaises(ValueError):self.validate(form)
        form=self.form();form['pairs'][1]=copy.deepcopy(form['pairs'][0])
        with self.assertRaises(ValueError):self.validate(form)
