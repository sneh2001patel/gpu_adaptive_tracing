"""Synthetic locked-reference durability/integrity and denominator semantics."""
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import copy
from dataclasses import replace
import io
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from revision.evaluation.reference_store import ReferenceStore,sha
from revision.evaluation.scoring import InitialStopPrediction,evaluate,evaluate_files
from revision.scripts.demo_reference_scoring import make_references,make_predictions,DOMAIN
from revision.scripts.reference_eval import main as cli
from revision.tracing.timing import ManualClock


class LockedFixture(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.records=make_references(self.root/'adjudication')
        self.clock=ManualClock(800);self.clock.domain=DOMAIN
        self.store=ReferenceStore(self.root/'store')
        self.anchor=self.store.lock(self.records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)
        self.predictions,self.snapshot=make_predictions();self.clock.advance_to(1000)

    def score(self,predictions=None,snapshot=None,anchor=None):
        return evaluate(self.store,anchor or self.anchor,json.dumps(self.predictions if predictions is None else predictions).encode(),
            json.dumps(self.snapshot if snapshot is None else snapshot).encode(),clock=self.clock)

    def manifest(self):return json.loads((self.root/'store/locks'/self.anchor).read_text())

    def corrupt(self,path):
        path.chmod(0o644);path.write_bytes(b'{"changed":true}')


class ReferenceLockTests(LockedFixture):
    def test_lock_assigns_timestamp_snapshots_records_and_preserves_unlocked_input(self):
        locked=self.store.load(self.anchor)
        self.assertEqual(locked.locked_at_ns,800)
        self.assertTrue(all(r.locked_at_ns==800 for r in locked.records))
        self.assertTrue(all(r.locked_at_ns is None for r in self.records))
        self.assertFalse((self.root/'store/locks'/self.anchor).stat().st_mode & 0o222)
        self.assertFalse(any((self.root/'store/blobs').glob('.pending-*')))

    def test_snapshot_survives_changes_to_original_source_but_new_lock_rejects_them(self):
        (self.root/'adjudication/server.json').write_text('changed original')
        self.assertEqual(self.store.load(self.anchor).run_id,'synthetic-run')
        with self.assertRaisesRegex(ValueError,'artifact hash mismatch'):
            self.store.lock(self.records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)

    def test_artifact_record_rubric_and_manifest_tampering_are_rejected(self):
        manifest=self.manifest()
        paths=[self.root/'store/blobs'/self.records[0].artifacts[0].sha256,
               self.root/'store/blobs'/manifest['record_sha256'][0],self.root/'store/blobs'/manifest['rubric_sha256'],
               self.root/'store/locks'/self.anchor]
        # Restore bytes between subcases, so each independent link is exercised.
        for path in paths:
            original=path.read_bytes()
            with self.subTest(path=path.name):
                self.corrupt(path)
                with self.assertRaisesRegex(ValueError,'hash mismatch'):self.store.load(self.anchor)
                path.write_bytes(original);path.chmod(0o444)

    def test_missing_artifact_and_symlink_snapshot_are_rejected(self):
        path=self.root/'store/blobs'/self.records[0].artifacts[0].sha256;original=path.read_bytes();path.unlink()
        with self.assertRaises(FileNotFoundError):self.store.load(self.anchor)
        target=self.root/'outside';target.write_bytes(original);path.symlink_to(target)
        with self.assertRaises(OSError):self.store.load(self.anchor)

    def test_raw_evidence_larger_than_metadata_limit_is_streamed_and_verified(self):
        path=self.root/'adjudication/large.raw';chunk=b'x'*(1024*1024);checksum=hashlib.sha256()
        with path.open('wb') as stream:
            for _ in range(33):stream.write(chunk);checksum.update(chunk)
        records=[]
        for record in self.records:
            artifacts=tuple(replace(a,path='large.raw',sha256=checksum.hexdigest()) if a.artifact_id=='server' else a for a in record.artifacts)
            records.append(replace(record,artifacts=artifacts))
        anchor=self.store.lock(records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)
        self.assertEqual(self.store.load(anchor).records[0].artifacts[0].sha256,checksum.hexdigest())

    def test_corrections_create_new_lock_without_overwriting_original(self):
        corrected=list(self.records);corrected[0]=replace(corrected[0],alternatives=('Corrected fixture alternative',))
        new=self.store.lock(corrected,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)
        self.assertNotEqual(new,self.anchor)
        self.assertNotEqual(self.store.load(new).records[0].alternatives,self.store.load(self.anchor).records[0].alternatives)

    def test_overlapping_cross_run_and_pretimestamped_references_are_rejected(self):
        for mode in ('overlap','run','locked'):
            records=list(self.records)
            if mode=='overlap':records[1]=replace(records[1],interval=replace(records[1].interval,start_ns=90))
            elif mode=='run':records[1]=replace(records[1],run_id='other')
            else:records[1]=replace(records[1],locked_at_ns=800)
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                self.store.lock(records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)

    def test_future_adjudication_unmapped_clock_and_unfrozen_rubric_are_rejected(self):
        for mode in ('future','clock','rubric'):
            clock=ManualClock(600 if mode=='future' else 1000);clock.domain='foreign' if mode=='clock' else DOMAIN
            rubric=self.root/'adjudication/rubric.json'
            if mode=='rubric':
                rubric=self.root/'bad-rubric.json'
                data=json.loads((self.root/'adjudication/rubric.json').read_text());data['criterion_ids']=['other']
                rubric.write_text(json.dumps(data))
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                self.store.lock(self.records,self.root/'adjudication',rubric,clock=clock)

    def test_concurrent_deduplicating_locks_never_replace_existing_objects(self):
        def lock(_):return self.store.lock(self.records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)
        with ThreadPoolExecutor(max_workers=2) as pool:anchors=list(pool.map(lock,range(2)))
        for anchor in anchors:self.assertEqual(self.store.load(anchor).run_id,'synthetic-run')
        self.assertEqual(self.store.load(self.anchor).locked_at_ns,800)

    def test_invalid_anchor_and_namespace_symlink_are_rejected(self):
        with self.assertRaises(ValueError):self.store.load('../outside')
        path=self.root/'symlink-store';path.mkdir();(path/'blobs').symlink_to(self.root/'store/blobs',target_is_directory=True)
        with self.assertRaises(ValueError):ReferenceStore(path)


class ReferenceScoringTests(LockedFixture):
    def test_complete_outcome_denominators_and_stable_counterexamples(self):
        result=self.score()
        self.assertEqual(result['denominators'],dict(all_logged_activated_episodes=12,all_initial_stops=12,
            reference_adjudicable_stops=7,reference_unavailable_stops=5))
        self.assertEqual(result['outcomes'],dict(supported_complete=1,supported_partial=1,unsupported_concrete=2,unresolved=3,reference_unavailable=5))
        self.assertEqual(result['stable_unsupported'],2)
        self.assertEqual(result['stable_incomplete'],1)
        self.assertEqual(result['stable_unadjudicable'],3)
        self.assertEqual(result['terminal_reasons']['budget_exhausted'],2)
        self.assertEqual(result['decision_statuses']['capture_failed'],1)
        self.assertEqual(result['decision_statuses']['horizon_censored'],1)
        self.assertEqual(result['prediction_file_sha256'],sha(json.dumps(self.predictions).encode()))

    def test_generic_mixed_is_unresolved_not_complete_cause_coverage(self):
        row=next(r for r in self.score()['initial_stop_rows'] if r['prediction_id']=='generic_mixed')
        self.assertEqual(row['diagnosis_outcome'],'unresolved');self.assertTrue(row['unmapped_concrete_label'])
        self.assertEqual(row['supported_causes_covered'],[])

    def test_transitions_gaps_and_unresolved_references_are_not_selected_for_best_score(self):
        rows={r['prediction_id']:r for r in self.score()['initial_stop_rows']}
        self.assertEqual(rows['transition']['reference_status'],'reference_transition')
        self.assertEqual(rows['gap']['reference_status'],'no_reference_interval')
        self.assertEqual(rows['unresolved_reference']['reference_status'],'unresolved_reference')
        self.assertEqual(rows['incomplete_reference']['reference_status'],'incomplete_reference_for_asserted_cause')

    def test_known_subset_of_incomplete_reference_cannot_be_complete(self):
        predictions=copy.deepcopy(self.predictions)
        predictions[8]['cause_set']=['queue_pressure'];predictions[8]['policy_label']='vllm_queue_pressure'
        row=self.score(predictions)['initial_stop_rows'][8]
        self.assertEqual(row['diagnosis_outcome'],'supported_partial')
        self.assertFalse(row['reference_cause_set_complete'])

    def test_explicit_contradiction_can_reject_a_cause_even_with_incomplete_reference(self):
        records=list(self.records);reference=records[2]
        negative=replace(reference.criteria[0],criterion_id='fixture-prefill_dominated_service',cause='prefill_dominated_service',passed=False)
        records[2]=replace(reference,contradicted_causes=('prefill_dominated_service',),criteria=reference.criteria+(negative,))
        anchor=self.store.lock(records,self.root/'adjudication',self.root/'adjudication/rubric.json',clock=self.clock)
        row=self.score(anchor=anchor)['initial_stop_rows'][8]
        self.assertEqual(row['diagnosis_outcome'],'unsupported_concrete')
        self.assertEqual(self.score()['initial_stop_rows'][8]['diagnosis_outcome'],'reference_unavailable')

    def test_missing_extra_duplicate_episode_or_prediction_ids_are_rejected(self):
        for mode in ('missing','duplicate_episode','duplicate_id','extra'):
            data=copy.deepcopy(self.predictions)
            if mode=='missing':data.pop()
            elif mode=='duplicate_episode':data[-1]['episode_id']=data[0]['episode_id']
            elif mode=='duplicate_id':data[-1]['prediction_id']=data[0]['prediction_id']
            else:data[-1]['episode_id']='unlogged'
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.score(data)

    def test_empty_logged_cohort_has_explicit_zero_denominator_and_null_fraction(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['controller'].update(episodes=[],events=[])
        result=self.score([],snapshot)
        self.assertEqual(result['denominators']['all_logged_activated_episodes'],0)
        self.assertIsNone(result['complete_agreement_fraction_all'])

    def test_activation_snapshot_completeness_identity_and_start_order_are_checked(self):
        for mode in ('events','run','domain','start'):
            data=copy.deepcopy(self.snapshot)
            if mode=='events':data['controller']['events'].pop()
            elif mode=='run':data['run_id']='other'
            elif mode=='domain':data['controller']['clock_domain']='foreign'
            else:data['controller']['events'][0]['timestamp_ns']=1000
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.score(snapshot=data)

    def test_cross_run_synthetic_live_domain_and_future_decision_joins_are_rejected(self):
        for changes in ({'run_id':'other'},{'provenance':'live_online'},{'decision_at_ns':1001}):
            data=copy.deepcopy(self.predictions);data[0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.score(data)
        data=copy.deepcopy(self.predictions);data[0]['evidence_interval']['clock_domain']='foreign'
        with self.assertRaises(ValueError):self.score(data)

    def test_early_join_and_corrupt_lock_reject_before_prediction_file_open(self):
        clock=ManualClock(799);clock.domain=DOMAIN
        with self.assertRaises(ValueError):evaluate(self.store,self.anchor,b'not JSON',b'not JSON',clock=clock)
        self.corrupt(self.root/'store/locks'/self.anchor)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            evaluate_files(self.store,self.anchor,self.root/'nonexistent-predictions',self.root/'nonexistent-activation',clock=self.clock)

    def test_prediction_availability_status_and_exact_fields_are_validated(self):
        baseline=self.predictions[0]
        changes=[{'expected_label':'queue'},{'policy_label':None,'cause_set':[]},
                 {'decision_status':'capture_failed'},{'cause_set':['invented']},{'evidence_id':None}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):InitialStopPrediction.from_dict(baseline|change)
        row=copy.deepcopy(baseline);row['evidence_interval']['available_at_ns']=row['decision_at_ns']+1
        with self.assertRaises(ValueError):InitialStopPrediction.from_dict(row)

    def test_failure_stays_in_denominator_without_being_a_successful_abstention(self):
        row=next(r for r in self.score()['initial_stop_rows'] if r['prediction_id']=='capture_failure')
        self.assertEqual(row['diagnosis_outcome'],'unresolved')
        self.assertFalse(row['abstained']);self.assertEqual(row['decision_status'],'capture_failed')

    def test_cli_lock_anchor_cannot_be_overwritten_and_score_is_separate(self):
        anchor_path=self.root/'ANCHOR.json'
        args=Namespace(command='lock',store=self.root/'cli-store',references=self.root/'adjudication/references.json',
            artifact_root=self.root/'adjudication',rubric=self.root/'adjudication/rubric.json',anchor_output=anchor_path,
            synthetic_clock_ns=800,clock_domain=DOMAIN)
        with redirect_stdout(io.StringIO()):cli(args)
        with self.assertRaises(FileExistsError):cli(args)
        anchor=json.loads(anchor_path.read_text())['reference_lock_sha256']
        predictions=self.root/'predictions.json';snapshot=self.root/'controller.json'
        predictions.write_text(json.dumps(self.predictions));snapshot.write_text(json.dumps(self.snapshot))
        score_args=Namespace(command='score',store=args.store,lock_sha256=anchor,predictions=predictions,
            controller_snapshot=snapshot,output=self.root/'score',synthetic_clock_ns=1000,clock_domain=DOMAIN)
        with redirect_stdout(io.StringIO()):cli(score_args)
        self.assertEqual(json.loads((score_args.output/'SCORE.json').read_text())['denominators']['all_initial_stops'],12)
        self.assertTrue((score_args.output/'REPORT.md').is_file())


if __name__=='__main__':unittest.main()
