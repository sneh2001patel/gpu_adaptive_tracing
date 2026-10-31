"""Synthetic contract checks only; no GPU evidence or diagnosis validation."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from revision.tracing.measured_evidence import Acquisition, MeasuredMetric, MeasuredObservation, KernelObservation, METRICS
from revision.tracing.diagnosis import UncalibratedClassifier, REFERENCE_TO_POLICY
from revision.tracing.policies import PolicyConfig, PolicyEvidence, StoppingPolicy
from revision.evaluation.references import ReferenceRecord, ReferenceArtifact


def stamp():
    return Acquisition(10,20,30,'synthetic-clock')


def observation():
    metrics=tuple(MeasuredMetric(name,source,unit,2 if unit not in ('fraction','percent') else .5,
        3,3,'complete',None,stamp()) for name,(source,unit) in METRICS.items())
    kernel=KernelObservation('cap-1','evidence-1','GPU-test',(123,),10,.01,
        'single_configured_worker_and_device_verified',stamp())
    return MeasuredObservation('obs-1','synthetic_simulation',stamp(),metrics,kernel)


def json_data(value):
    return json.loads(json.dumps(asdict(value)))


def reference():
    return dict(record_role='adjudicated_reference',run_id='opaque-1',reference_version='synthetic-rubric-v1',
        provenance='synthetic_simulation',interval=asdict(stamp()),status='supported',
        supported_causes=['queue_pressure'],contradicted_causes=[],cause_set_complete=True,
        criteria=[dict(criterion_id='queue-criterion',cause='queue_pressure',passed=True,
            artifact_ids=['server','requests'],rationale='Synthetic queue and wait fixtures, not experimental evidence')],
        artifacts=[dict(artifact_id=name,path=name+'.json',sha256='a'*64,channel=channel,acquisition=asdict(stamp()))
                   for name,channel in [('server','server_diagnostics'),('requests','request_diagnostics')]],
        alternatives=['Synthetic service-mix alternative'],matched_reference_run_id=None,reference_run_mismatch=None,
        assessor_ids=['synthetic-author'],blinded_to_predictions_and_policy=True,
        adjudicated_at_ns=40,locked_at_ns=50,limitations=['Synthetic single-assessor fixture; no measured truth'])


class MeasuredContractTests(unittest.TestCase):
    def test_roundtrip_complete_observation_still_abstains(self):
        obs=MeasuredObservation.from_dict(json_data(observation()))
        result=UncalibratedClassifier().classify(obs,now_ns=30,clock_domain='synthetic-clock')
        self.assertIsNone(result.policy_label)
        self.assertEqual(result.cause_set,())
        self.assertIn('calibration_unavailable',result.reasons)
        self.assertIn(('prefill_dominated_service',None),REFERENCE_TO_POLICY)

    def test_unknown_fields_are_rejected_at_each_classifier_input_layer(self):
        for layer in ('bundle','metric','stamp','kernel'):
            with self.subTest(layer=layer):
                data=json_data(observation())
                target={'bundle':data,'metric':data['metrics'][0],
                        'stamp':data['acquisition'],'kernel':data['kernel']}[layer]
                target['expected_label']='queue_pressure'
                with self.assertRaises(ValueError):MeasuredObservation.from_dict(data)

    def test_raw_dict_and_reference_cannot_be_classifier_inputs(self):
        for value in (json_data(observation()),ReferenceRecord.from_dict(reference())):
            with self.subTest(value=type(value)):
                with self.assertRaises(ValueError):
                    UncalibratedClassifier().classify(value,now_ns=50,clock_domain='synthetic-clock')

    def test_future_evidence_and_unmapped_clocks_are_rejected(self):
        for now,clock in ((29,'synthetic-clock'),(30,'different-domain')):
            with self.subTest(now=now,clock=clock):
                with self.assertRaises(ValueError):
                    UncalibratedClassifier().classify(observation(),now_ns=now,clock_domain=clock)

    def test_bundle_cannot_be_ready_before_kernel_or_metric(self):
        for target in ('kernel','metric'):
            data=json_data(observation())
            field=data['kernel'] if target=='kernel' else data['metrics'][0]
            field['acquisition']['available_at_ns']=31
            with self.subTest(target=target),self.assertRaises(ValueError):MeasuredObservation.from_dict(data)

    def test_missing_is_distinct_from_measured_zero_and_partial(self):
        missing=MeasuredMetric('queue_depth_mean','server','requests',None,0,3,'unavailable','endpoint_missing',stamp())
        zero=MeasuredMetric('queue_depth_mean','server','requests',0,3,3,'complete',None,stamp())
        partial=MeasuredMetric('queue_depth_mean','server','requests',1,2,3,'partial',None,stamp())
        self.assertIsNone(missing.value);self.assertEqual(zero.value,0)
        for metric,reason in ((missing,'missing:queue_depth_mean'),(partial,'partial:queue_depth_mean')):
            obs=MeasuredObservation('id','synthetic_simulation',stamp(),(metric,),None)
            result=UncalibratedClassifier().classify(obs,now_ns=30,clock_domain='synthetic-clock')
            self.assertIn(reason,result.reasons)

    def test_invalid_values_counts_units_and_bool_timestamps_are_rejected(self):
        cases=[('value',float('nan')),('value',True),('valid_samples',0),('attempted_samples',2),
               ('coverage','partial'),('unit','seconds')]
        base=json_data(observation())['metrics'][0]
        for key,value in cases:
            data=base|{key:value}
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):MeasuredMetric.from_dict(data)
        with self.assertRaises(ValueError):Acquisition(True,20,30,'clock')

    def test_gpu_fraction_and_worker_coverage_are_bounded(self):
        for name,value in [('gpu_util_mean',101),('prefill_service_fraction',1.01)]:
            data=json_data(observation())
            for metric in data['metrics']:
                if metric['name']==name:metric['value']=value
            with self.subTest(name=name),self.assertRaises(ValueError):MeasuredObservation.from_dict(data)
        data=json_data(observation());data['kernel']['worker_pids']=[123,456]
        with self.assertRaises(ValueError):MeasuredObservation.from_dict(data)

    def test_unaligned_metrics_and_duplicates_are_rejected(self):
        for mode in ('shift','duplicate'):
            data=json_data(observation())
            if mode=='shift':data['metrics'][0]['acquisition']['start_ns']=11
            else:data['metrics'].append(copy.deepcopy(data['metrics'][0]))
            with self.subTest(mode=mode),self.assertRaises(ValueError):MeasuredObservation.from_dict(data)

    def test_reference_metadata_changes_cannot_change_diagnosis(self):
        obs=observation();classifier=UncalibratedClassifier()
        before=classifier.classify(obs,now_ns=50,clock_domain='synthetic-clock')
        first=ReferenceRecord.from_dict(reference())
        changed=reference();changed['supported_causes']=['prefill_dominated_service']
        changed['criteria'][0]['cause']='prefill_dominated_service'
        second=ReferenceRecord.from_dict(changed)
        self.assertNotEqual(first.supported_causes,second.supported_causes)
        self.assertEqual(before,classifier.classify(obs,now_ns=50,clock_domain='synthetic-clock'))

    def test_unknowns_across_transition_do_not_establish_stability(self):
        policy=StoppingPolicy('stability_stop',PolicyConfig(max_bursts=2))
        for i,queue in enumerate((20,0)):
            data=json_data(observation());data['observation_id']=f'obs-{i}'
            data['kernel']['capture_id']=f'cap-{i}';data['kernel']['evidence_id']=f'evidence-{i}'
            for metric in data['metrics']:
                if metric['name']=='queue_depth_mean':metric['value']=queue
            prediction=UncalibratedClassifier().classify(MeasuredObservation.from_dict(data),now_ns=30,clock_domain='synthetic-clock')
            decision=policy.observe(PolicyEvidence(window_id=f'w{i}',capture_id=f'cap-{i}',
                diagnosis_evidence_id=prediction.evidence_id,diagnosis_label=prediction.policy_label))
        self.assertEqual(decision.reason,'budget_exhausted')
        self.assertEqual(decision.diagnosis_streak,0)
        self.assertFalse(decision.policy_condition_met)


class ReferenceContractTests(unittest.TestCase):
    def test_adjudicated_reference_can_join_after_lock_in_matching_run(self):
        record=ReferenceRecord.from_dict(reference())
        record.require_joinable(run_id='opaque-1',provenance='synthetic_simulation',join_at_ns=50,clock_domain='synthetic-clock')

    def test_reference_join_rejects_unlocked_future_lock_cross_run_and_live_mix(self):
        for changes,join in [({'locked_at_ns':None},{}),({'locked_at_ns':60},{}),({}, {'run_id':'another'}),
                             ({},{'provenance':'live_online'}),({}, {'clock_domain':'foreign'})]:
            data=reference()|changes;args=dict(run_id='opaque-1',provenance='synthetic_simulation',join_at_ns=50,clock_domain='synthetic-clock')|join
            with self.subTest(changes=changes,join=join),self.assertRaises(ValueError):
                ReferenceRecord.from_dict(data).require_joinable(**args)

    def test_template_and_injection_records_cannot_be_reference_truth(self):
        for role in ('template_not_observation','intervention_schedule'):
            with self.subTest(role=role),self.assertRaises(ValueError):
                ReferenceRecord.from_dict(reference()|{'record_role':role})

    def test_cause_assertions_require_linked_corroboration_not_just_injection(self):
        for mode in ('missing_link','intervention_only','same_channel'):
            data=reference()
            if mode=='missing_link':data['criteria'][0]['artifact_ids']=['absent']
            else:
                for artifact in data['artifacts']:
                    artifact['channel']='intervention_log' if mode=='intervention_only' else 'server_diagnostics'
            with self.subTest(mode=mode),self.assertRaises(ValueError):ReferenceRecord.from_dict(data)

    def test_unsupported_and_contradictory_cause_sets_are_rejected(self):
        for changes in ({'supported_causes':['invented']},{'contradicted_causes':['queue_pressure']},
                        {'status':'unresolved'},{'supported_causes':[]},{'cause_set_complete':'yes'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):ReferenceRecord.from_dict(reference()|changes)

    def test_healthy_requires_explicit_negative_adjudication(self):
        data=reference()|dict(status='healthy',supported_causes=[])
        data['criteria'][0]['cause']=None
        self.assertEqual(ReferenceRecord.from_dict(data).status,'healthy')
        data['criteria']=[]
        with self.assertRaises(ValueError):ReferenceRecord.from_dict(data)

    def test_matched_trace_needs_separate_run_and_mismatch_assessment(self):
        data=reference();data['artifacts'][0]['channel']='matched_full_trace'
        with self.assertRaises(ValueError):ReferenceRecord.from_dict(data)
        data.update(matched_reference_run_id='separate-reference',reference_run_mismatch='Synthetic trajectory differs; corroboration only')
        self.assertEqual(ReferenceRecord.from_dict(data).matched_reference_run_id,'separate-reference')
        data['matched_reference_run_id']=data['run_id']
        with self.assertRaises(ValueError):ReferenceRecord.from_dict(data)

    def test_explicit_unresolved_reference_is_valid_without_invented_causes(self):
        data=reference()|dict(status='unresolved',supported_causes=[],cause_set_complete=False,criteria=[],artifacts=[])
        self.assertEqual(ReferenceRecord.from_dict(data).status,'unresolved')

    def test_evidence_availability_and_adjudication_lock_order_are_checked(self):
        for mode in ('future_artifact','lock_before_adjudication','domain'):
            data=reference()
            if mode=='future_artifact':data['artifacts'][0]['acquisition']['available_at_ns']=41
            elif mode=='domain':data['artifacts'][0]['acquisition']['clock_domain']='unmapped'
            else:data['locked_at_ns']=39
            with self.subTest(mode=mode),self.assertRaises(ValueError):ReferenceRecord.from_dict(data)

    def test_single_assessor_limitations_and_unknown_fields_cannot_be_omitted(self):
        for changes in ({'limitations':[]},{'predicted_label':'queue_pressure'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):ReferenceRecord.from_dict(reference()|changes)

    def test_reference_hashes_and_path_escape_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'artifact.json').write_text('{}')
            data=reference()['artifacts'][0]|dict(path='artifact.json',sha256=hashlib.sha256(b'{}').hexdigest())
            ReferenceArtifact.from_dict(data).verify_content(root)
            (root/'artifact.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):ReferenceArtifact.from_dict(data).verify_content(root)
            with tempfile.TemporaryDirectory() as external:
                outside=Path(external)/'external.json';outside.write_text('{}')
                (root/'link.json').symlink_to(outside)
                with self.assertRaisesRegex(ValueError,'escapes'):
                    ReferenceArtifact.from_dict(data|{'path':'link.json'}).verify_content(root)
            for path in ('../escape','/absolute'):
                with self.subTest(path=path),self.assertRaises(ValueError):ReferenceArtifact.from_dict(data|{'path':path})


if __name__=='__main__':unittest.main()
