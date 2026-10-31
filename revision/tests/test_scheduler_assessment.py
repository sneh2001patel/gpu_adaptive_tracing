"""Synthetic declaration/worksheet contracts. Fixture values are not study choices."""
from dataclasses import asdict
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from revision.evaluation.scheduler_assessment import (VERSION,SPEC,REVIEW_FIELDS,prepare_packet,
    criteria_template,validate_criteria,review_template,validate_review)
from revision.evaluation.evidence_assessment import digest
from revision.evaluation.references import ReferenceArtifact
from revision.tracing.measured_evidence import Acquisition
from revision.tracing.live_features import ServingBinding
from revision.scripts.prepare_scheduler_assessment import prepare


def fixture_packet():
    catalog={}
    for name,family in [('source-a','host_schedule_event_history'),('source-b','host_schedule_event_history'),('client','client_response_timing')]:
        channel='request_diagnostics' if family=='client_response_timing' else 'server_diagnostics'
        catalog[name]=dict(artifact=asdict(ReferenceArtifact(name,name+'.json','a'*64,channel,Acquisition(10,20,100,'synthetic'))),family=family)
    return dict(audit_sha256='a'*64,campaign_manifest_sha256='b'*64,catalog=catalog,
        cases=[dict(case_id='window-a',allowed_artifact_ids=['source-a','client']),dict(case_id='window-b',allowed_artifact_ids=['source-b'])],
        fixture_role='synthetic_only_not_actual_assessment')


def complete_fixture_criteria(packet):
    criteria=criteria_template(packet)
    for key,(kind,_) in SPEC.items():
        value='synthetic_definition_not_a_study_choice' if kind=='text' else (2 if kind=='integer' else (.95 if kind=='probability' else .1))
        criteria['scientific_limits'][key].update(value=value,definition='Synthetic test definition only.',rationale='Synthetic test rationale only.')
    criteria['decision_provenance'].update(author='synthetic-criterion-author',decided_at_utc='2026-10-28T00:00:00Z',
        development_data_informed=True,rationale='Synthetic declaration; no actual scientific decisions.')
    criteria['evidence_separation'].update(classifier_evidence_families=['client_response_timing'],
        reference_evidence_families=['host_schedule_event_history'],rationale='Separate synthetic families, not demonstrated causal independence.')
    return criteria


def complete_fixture_review(packet,criteria):
    review=review_template(packet,criteria)
    review.update(assessor_id='synthetic-assessor',blinded_to_predictions_and_policy=False,
        blinding_scope_statement='Unblinded synthetic metadata.',independence_statement='Fixture declaration only.',limitations=['Synthetic test, not a human assessment.'])
    for row,case in zip(review['cases'],packet['cases']):
        row.update(outcome='unresolved',reviewed_artifacts=[dict(artifact_id=case['allowed_artifact_ids'][0],purpose='candidate_reference')],
            **{key:'Synthetic gap rationale only.' for key in REVIEW_FIELDS})
    return review


class CriteriaTests(unittest.TestCase):
    def setUp(self):self.packet=fixture_packet();self.criteria=complete_fixture_criteria(self.packet)

    def test_blank_draft_stays_blocked_and_does_not_fill_values(self):
        draft=criteria_template(self.packet);before=copy.deepcopy(draft);gate=validate_criteria(draft,self.packet)
        self.assertFalse(gate['structure_complete']);self.assertEqual(draft,before)
        self.assertEqual(sum(r['value'] is None for r in draft['scientific_limits'].values()),14)

    def test_complete_declarations_do_not_validate_science_or_enable_export(self):
        gate=validate_criteria(self.criteria,self.packet)
        self.assertTrue(gate['structure_complete']);self.assertFalse(gate['scientific_adequacy_verified'])
        self.assertFalse(gate['existing_development_data_confirmed']);self.assertFalse(gate['reference_export_enabled'])
        self.assertEqual(gate['references_locked'],0)

    def test_boolean_nonfinite_negative_and_fraction_values_are_rejected(self):
        for key,value in [('max_hook_bracket_width_ms',True),('max_wait_interval_width_ms',float('nan')),
            ('max_source_probe_gap_ms',float('inf')),('max_pair_latency_mismatch',-1),
            ('max_boundary_ambiguous_fraction',1.1),('min_independent_repetitions',1.5),('target_confidence_level',1)]:
            with self.subTest(key=key,value=value):
                changed=copy.deepcopy(self.criteria);changed['scientific_limits'][key]['value']=value
                with self.assertRaises(ValueError):validate_criteria(changed,self.packet)

    def test_units_and_semantic_scope_cannot_be_silently_changed(self):
        for key,value in [('measurand','GPU_execution_start'),('cohort','HTTP_completion_cohort'),('source_audit_sha256','c'*64)]:
            changed=copy.deepcopy(self.criteria);changed[key]=value
            with self.assertRaises(ValueError):validate_criteria(changed,self.packet)
        changed=copy.deepcopy(self.criteria);changed['scientific_limits']['max_wait_interval_width_ms']['unit']='seconds'
        with self.assertRaises(ValueError):validate_criteria(changed,self.packet)

    def test_actual_development_data_and_utc_provenance_must_be_declared(self):
        for key,value in [('development_data_informed','false'),('decided_at_utc','2026-10-28T00:00:00'),('confirmation_scope','retroactively_confirm_this_campaign')]:
            changed=copy.deepcopy(self.criteria);changed['decision_provenance'][key]=value
            with self.assertRaises(ValueError):validate_criteria(changed,self.packet)
        changed=copy.deepcopy(self.criteria);changed['decision_provenance']['development_data_informed']=None
        self.assertFalse(validate_criteria(changed,self.packet)['structure_complete'])

    def test_same_feature_and_reference_family_or_intervention_only_is_rejected(self):
        for references in (['client_response_timing'],['intervention_record'],[]):
            changed=copy.deepcopy(self.criteria);changed['evidence_separation']['reference_evidence_families']=references
            with self.assertRaises(ValueError):validate_criteria(changed,self.packet)

    def test_blank_rationales_and_extra_fields_are_not_completion(self):
        changed=copy.deepcopy(self.criteria);changed['scientific_limits']['target_percentile_precision']['rationale']=' '
        with self.assertRaises(ValueError):validate_criteria(changed,self.packet)
        changed=copy.deepcopy(self.criteria);changed['calibration_enabled']=True
        with self.assertRaises(ValueError):validate_criteria(changed,self.packet)


class WorksheetTests(unittest.TestCase):
    def setUp(self):
        self.packet=fixture_packet();self.criteria=complete_fixture_criteria(self.packet)
        self.review=complete_fixture_review(self.packet,self.criteria)

    def test_structure_complete_is_still_not_authenticated_adjudication(self):
        gate=validate_review(self.review,self.packet,self.criteria)
        self.assertTrue(gate['review_structure_complete']);self.assertTrue(gate['criteria_structure_complete'])
        for key in ('causal_reference_validated','assessor_identity_authenticated','actual_blinding_verified','reference_export_enabled','calibration_enabled'):
            self.assertFalse(gate[key])

    def test_filled_gap_review_does_not_bypass_missing_criteria(self):
        criteria=criteria_template(self.packet);review=complete_fixture_review(self.packet,criteria)
        for row in review['cases']:row['reviewed_artifacts'][0]['purpose']='context'
        gate=validate_review(review,self.packet,criteria)
        self.assertTrue(gate['review_structure_complete']);self.assertFalse(gate['criteria_structure_complete'])
        self.assertEqual(gate['status'],'blocked_missing_criteria_or_assessor_input')

    def test_blank_assessor_and_case_fields_stay_pending(self):
        gate=validate_review(review_template(self.packet,self.criteria),self.packet,self.criteria)
        self.assertFalse(gate['review_structure_complete']);self.assertIn('assessor_id',gate['missing_fields'])

    def test_changed_criteria_or_packet_invalidates_old_worksheet(self):
        criteria=copy.deepcopy(self.criteria);criteria['scientific_limits']['max_hook_bracket_width_ms']['value']=.2
        with self.assertRaises(ValueError):validate_review(self.review,self.packet,criteria)
        packet=copy.deepcopy(self.packet);packet['metadata_disclosed']=True
        with self.assertRaises(ValueError):validate_review(self.review,packet,self.criteria)

    def test_supported_healthy_or_injected_truth_fields_are_rejected(self):
        for outcome in ('supported','healthy','queue_pressure'):
            review=copy.deepcopy(self.review);review['cases'][0]['outcome']=outcome
            with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)
        review=copy.deepcopy(self.review);review['cases'][0]['cause_set']=['queue_pressure']
        with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)

    def test_wrong_case_unknown_or_duplicate_evidence_is_rejected(self):
        for links in ([dict(artifact_id='source-b',purpose='context')],[dict(artifact_id='unknown',purpose='context')],self.review['cases'][0]['reviewed_artifacts']*2):
            review=copy.deepcopy(self.review);review['cases'][0]['reviewed_artifacts']=links
            with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)

    def test_candidate_reference_cannot_use_classifier_family(self):
        review=copy.deepcopy(self.review);review['cases'][0]['reviewed_artifacts']=[dict(artifact_id='client',purpose='candidate_reference')]
        with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)

    def test_missing_or_duplicate_cases_and_false_boolean_strings_are_rejected(self):
        for cases in (self.review['cases'][:1],self.review['cases'][:1]*2):
            review=copy.deepcopy(self.review);review['cases']=cases
            with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)
        review=copy.deepcopy(self.review);review['blinded_to_predictions_and_policy']='false'
        with self.assertRaises(ValueError):validate_review(review,self.packet,self.criteria)


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        self.campaign=root/'campaign';self.audit=root/'audit';self.campaign.mkdir();self.audit.mkdir();job=self.campaign/'synthetic-job';job.mkdir()
        binding=asdict(ServingBinding('fixture',0,43,'GPU-fixture','model','0','synthetic'))
        for name,data in [('binding.json',binding),('RESULT.json',dict(cleanup=dict(confirmed_absent=True,clock_domain='synthetic',completed_at_ns=100))),
            ('consumer_windows.json',[dict(start_ns=10,end_ns=20,owner_observed_at_ns=25,status='unresolved',reason='missing_event_receipt')])]:
            (job/name).write_text(json.dumps(data))
        (job/'requests').mkdir();(job/'requests/receipts.jsonl').write_text(json.dumps(dict(admitted_at_ns=1,completed_at_ns=40))+'\n')
        self.campaign_pin=self.manifest(self.campaign)
        audit=dict(version='scheduler_bound_precision_audit_v1',campaign_manifest_sha256=self.campaign_pin,
            classifier_activated=False,references_created=0,calibration_enabled=False,
            jobs=[dict(job_id='synthetic-job',binding=binding,windows=[dict(start_ns=10,end_ns=20,consumer_status='unresolved',consumer_reason='missing_event_receipt',selected_probe=None)])])
        (self.audit/'AUDIT.json').write_text(json.dumps(audit));self.audit_pin=self.manifest(self.audit)

    def manifest(self,root):
        data=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
        path=root/'artifact_manifest.json';path.write_text(json.dumps(data));return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_catalog_reuses_reference_contract_with_conservative_file_availability(self):
        packet=prepare_packet(self.campaign,self.audit,self.campaign_pin,self.audit_pin)
        self.assertEqual(packet['cases'][0]['interval']['available_at_ns'],25)
        for record in packet['catalog'].values():
            artifact=ReferenceArtifact.from_dict(record['artifact']);artifact.verify_content(self.campaign)
            self.assertEqual(artifact.acquisition.available_at_ns,100)
        self.assertTrue(packet['metadata_disclosed']);self.assertFalse(packet['reference_export_enabled'])

    def test_tampered_original_input_fails_before_packet_generation(self):
        (self.campaign/'synthetic-job/binding.json').write_text('{}')
        with self.assertRaises(ValueError):prepare_packet(self.campaign,self.audit,self.campaign_pin,self.audit_pin)

    def test_cli_outputs_are_fresh_separate_and_remain_blocked(self):
        output=self.campaign.parent/'packet';result=prepare(self.campaign,self.audit,output,self.campaign_pin,self.audit_pin)
        self.assertEqual(result['criteria_status'],'blocked_incomplete_criteria')
        self.assertEqual(result['references_locked'],0)
        with self.assertRaises(FileExistsError):prepare(self.campaign,self.audit,output,self.campaign_pin,self.audit_pin)
        with self.assertRaises(ValueError):prepare(self.campaign,self.audit,self.audit/'nested',self.campaign_pin,self.audit_pin)
