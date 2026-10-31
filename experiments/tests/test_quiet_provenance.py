"""Explicit CPU fixtures for cumulative-row provenance, never live observations."""
from dataclasses import asdict
import json,tempfile,unittest
from pathlib import Path
from experiments.evaluation.quiet_provenance import build_index,digest
from experiments.scripts.audit_quiet_provenance import audit
from experiments.scripts.demo_live_feasibility import metric_text
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.worker_barrier import worker_barrier


class QuietProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'campaign';self.root.mkdir();self.rows=[]
        for i,job in enumerate(('a','b')):
            directory=self.root/job;directory.mkdir();binding=ServingBinding(job,i,43+i,'GPU-fixture','Qwen/Qwen2.5-7B-Instruct','0','fixture-clock')
            (directory/'binding.json').write_text(json.dumps(asdict(binding)))
            command=dict(token=str(i+1)*32,session_nonce=job,generation=i,clock_domain='fixture-clock',requested_at_ns=3)
            receipt=worker_barrier(command,pid=43+i,device_uuid='GPU-fixture',clock_domain='fixture-clock',session_nonce=job,
                generation=i,capture_active=False,synchronize=lambda:None,now_ns=lambda:4)
            row=dict(label='before',index=0,requested_at_ns=1,before_received_at_ns=2,barrier_command=command,
                barrier_receipt=receipt,barrier_received_at_ns=5,observed_at_ns=6,owned_client_outstanding=0)
            raw=metric_text()+f'\n# synthetic job {job}\n'.encode()
            for side in ('before','after'):
                name='before-0-'+side+'.txt';(directory/name).write_bytes(raw)
                row[side+'_path']=name;row[side+'_sha256']=digest(raw)
            self.rows.append(row)
            (directory/'quiet_evidence.json').write_text(json.dumps(self.rows))
        self.manifest()

    def manifest(self):
        paths=[p for p in self.root.rglob('*') if p.is_file() and p.name!='artifact_manifest.json']
        (self.root/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(self.root)):digest(p.read_bytes()) for p in paths})))

    def mutate(self,change):
        path=self.root/'b/quiet_evidence.json';rows=json.loads(path.read_text());change(rows)
        path.write_text(json.dumps(rows));self.manifest()

    def test_original_job_resolution_is_explicit_and_inputs_remain_unchanged(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        index=build_index(self.root)
        self.assertEqual((index['unique_barriers'],index['observed_rows'],index['historical_rows']),(2,3,1))
        historical=next(o for o in index['occurrences'] if o['historical'])
        self.assertEqual((historical['observed_file'],historical['origin_job']),('b/quiet_evidence.json','a'))
        original=next(b for b in index['barriers'] if b['origin_job']=='a')
        self.assertEqual(original['raw_files']['before']['path'],'a/before-0-before.txt')
        self.assertEqual(original['original_row_index'],0)
        self.assertFalse(index['per_job_files_self_contained'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_changed_raw_bytes_are_rejected(self):
        (self.root/'a/before-0-before.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):build_index(self.root)

    def test_foreign_binding_is_rejected_even_with_new_manifest(self):
        self.mutate(lambda rows:rows[0]['barrier_command'].update(session_nonce='foreign'))
        with self.assertRaisesRegex(ValueError,'Missing original'):build_index(self.root)

    def test_foreign_clock_is_rejected_even_when_receipt_and_command_agree(self):
        def change(rows):
            rows[0]['barrier_command']['clock_domain']='other-clock'
            rows[0]['barrier_receipt']['clock_domain']='other-clock'
        self.mutate(change)
        with self.assertRaisesRegex(ValueError,'Foreign original clock'):build_index(self.root)

    def test_repeated_original_token_is_not_counted_as_two_barriers(self):
        path=self.root/'a/quiet_evidence.json';rows=json.loads(path.read_text());rows.append(rows[0])
        path.write_text(json.dumps(rows));self.manifest()
        with self.assertRaisesRegex(ValueError,'Repeated original'):build_index(self.root)

    def test_conflicting_historical_copy_is_rejected(self):
        self.mutate(lambda rows:rows[0].update(observed_at_ns=7))
        with self.assertRaisesRegex(ValueError,'Conflicting repeated'):build_index(self.root)

    def test_cross_job_metric_path_cannot_replace_origin_resolution(self):
        self.mutate(lambda rows:rows[0].update(before_path='../b/before-0-before.txt'))
        with self.assertRaisesRegex(ValueError,'basename'):build_index(self.root)

    def test_historical_row_requires_an_original_occurrence(self):
        (self.root/'a/quiet_evidence.json').write_text('[]');self.manifest()
        with self.assertRaisesRegex(ValueError,'no identical original'):build_index(self.root)

    def test_busy_original_gauges_cannot_be_quiet_evidence(self):
        raw=metric_text(waiting=1);(self.root/'a/before-0-before.txt').write_bytes(raw)
        for job in ('a','b'):
            path=self.root/job/'quiet_evidence.json';rows=json.loads(path.read_text())
            rows[0]['before_sha256']=digest(raw);path.write_text(json.dumps(rows))
        self.manifest()
        with self.assertRaisesRegex(ValueError,'nonzero'):build_index(self.root)

    def test_cli_output_must_be_fresh_and_outside_campaign(self):
        with self.assertRaises(ValueError):audit(self.root,self.root/'derived')
        output=self.root.parent/'index';result=audit(self.root,output)
        self.assertEqual(result['unique_barriers'],2)
        manifest=json.loads((output/'artifact_manifest.json').read_text())['files']
        self.assertEqual(manifest['INDEX.json'],digest((output/'INDEX.json').read_bytes()))
        with self.assertRaises(FileExistsError):audit(self.root,output)
