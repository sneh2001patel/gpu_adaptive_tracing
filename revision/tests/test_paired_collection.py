"""CPU-only paired manifest, raw receipt and exact playback checks."""
import asyncio,json,tempfile,hashlib
from pathlib import Path
from dataclasses import replace
import unittest
from unittest.mock import patch
from revision.feasibility.paired_collection import load_pairs,BoundCollector,RawCompletions,collect_job,validate_playback,adjudication_packet
from revision.tracing.arrival_schedule import ArrivalSchedule,canonical
from revision.tracing.timing import MonotonicClock
from revision.tracing.live_features import ServingBinding,MetricReceipt
from revision.scripts.demo_live_feasibility import metric_text

SOURCE=Path('revision/hardware/l4_20261028/capacity_001/paired_schedules')
class PairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for p in SOURCE.iterdir():
            if p.is_file():(self.root/p.name).write_bytes(p.read_bytes())
    def test_saved_pairs_validate_exact_shared_hashes_and_order(self):
        manifest,jobs=load_pairs(self.root);self.assertEqual(len(jobs),4)
        self.assertEqual([j['role'] for j,s in jobs],['feature_collection','matched_full_trace','matched_full_trace','feature_collection'])
        self.assertEqual(jobs[0][1].file_sha256,jobs[1][1].file_sha256)
    def change(self,update):
        p=self.root/'PAIRS.json';d=json.loads(p.read_text());update(d);p.write_text(json.dumps(d))
    def test_offered_byte_tampering_rejected(self):
        p=self.root/'short_offered.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):load_pairs(self.root)
    def test_duplicate_role_order_restart_or_executed_jobs_rejected(self):
        original=(self.root/'PAIRS.json').read_bytes()
        for changes in (dict(role='matched_full_trace'),dict(order_in_pair=1),dict(executed=True),dict(fresh_owned_restart_required=False),dict(schedule_path='../escape')):
            (self.root/'PAIRS.json').write_bytes(original);self.change(lambda d:d['jobs'][0].update(changes))
            with self.assertRaises(ValueError):load_pairs(self.root)
    def test_frozen_or_calibration_manifest_rejected(self):
        self.change(lambda d:d.update(calibration_enabled=True))
        with self.assertRaises(ValueError):load_pairs(self.root)
    def test_missing_trace_cannot_become_adjudication_packet(self):
        d=self.root/'job';(d/'collection/requests').mkdir(parents=True)
        (d/'collection/requests/receipts.json').write_text('[]');(d/'collection/playback.json').write_text('{}')
        with self.assertRaises(ValueError):adjudication_packet(self.root,[dict(directory='job',job_id='j',role='matched_full_trace')])

    def test_artifact_packet_has_no_adjudicated_causes_or_reference_lock(self):
        d=self.root/'job';(d/'collection/requests').mkdir(parents=True)
        (d/'collection/requests/receipts.json').write_text('[]');(d/'collection/playback.json').write_text('{}')
        packet=adjudication_packet(self.root,[dict(directory='job',job_id='j',role='feature_collection')])
        self.assertEqual(packet['references_created'],0);self.assertEqual(packet['references_locked'],0)
        self.assertNotIn('supported_causes',packet);self.assertFalse(packet['predictions_computed'])
        self.assertEqual(len(packet['artifacts']),2)
    def test_skipped_or_failed_playback_cannot_pass(self):
        for status,admitted,completed in (('aborted',2,2),('completed',1,1),('completed',2,1)):
            with self.assertRaises(ValueError):validate_playback(dict(status=status,admitted=admitted,offered=2,counts=dict(completed=completed)))

class LiveHookTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=MonotonicClock();self.scope=ServingBinding('session',0,43,'GPU-test','model','0',self.clock.domain)
    async def http(self,endpoint,**options):
        if endpoint.endswith('/metrics'):return 200,metric_text(model='model')
        await asyncio.sleep(.005)
        return 200,b'{"usage":{"prompt_tokens":7,"completion_tokens":32}}'
    def schedule(self):
        return ArrivalSchedule.from_bytes(canonical(dict(version='offered_arrivals_v1',duration_ns=80_000_000,requests=[
            dict(request_id='r1',offset_ns=0,payload=dict(model='model',prompt='actual prompt',max_tokens=32,stream=False))])))
    async def test_exact_playback_retains_raw_usage_scoped_windows_and_no_tasks(self):
        with patch('revision.feasibility.paired_collection.http_body',side_effect=self.http),patch('revision.tracing.live_features.http_body',side_effect=self.http):
            result=await collect_job(self.clock,'http://127.0.0.1:8012',self.scope,self.schedule(),self.root/'collection',provenance='synthetic_simulation')
        validate_playback(result);self.assertEqual(result['counts']['completed'],1)
        observation=json.loads((self.root/'collection/window-0/observation.json').read_text())
        self.assertEqual(observation['provenance'],'synthetic_simulation')
        metrics={m['name']:m for m in observation['metrics']};self.assertIsNone(metrics['request_wait_p95_ms']['value'])
        self.assertEqual(metrics['output_tokens_mean']['value'],32)
        receipts=json.loads((self.root/'collection/requests/receipts.json').read_text());self.assertEqual(receipts[0]['http_status'],200)
        for key in ('live_request_tasks','live_sampling_tasks'):self.assertEqual(result[key],0)
    async def test_foreign_backing_raw_scope_rejected(self):
        collector=BoundCollector('http://127.0.0.1:8012/metrics',self.scope);collector.provenance='synthetic_simulation'
        now=self.clock.now_ns();collector.receipts['s']=MetricReceipt('s',replace(self.scope,generation=1),now,now,200,metric_text(model='model'),None)
        window=collector.window(self.clock,now,now+1_000_000_000,min_latency_samples=1)
        from revision.tracing.feature_collection import ServerSample
        with self.assertRaises(ValueError):window.on_server(ServerSample('s',now,now,self.clock.domain,0,None))
    async def test_http_error_raw_response_and_failure_retained(self):
        raw=RawCompletions(self.root/'responses')
        with patch('revision.feasibility.paired_collection.http_body',return_value=(503,b'{"error":"busy"}')):
            result=await raw.collect(self.clock,'../arbitrary','http://127.0.0.1:1',dict(max_tokens=32))
        self.assertFalse(result.completion.success);self.assertEqual(len(list((self.root/'responses').glob('*.json'))),2)
    async def test_output_usage_mismatch_cannot_be_successful(self):
        raw=RawCompletions(self.root/'responses')
        with patch('revision.feasibility.paired_collection.http_body',return_value=(200,b'{"usage":{"prompt_tokens":7,"completion_tokens":1}}')):
            result=await raw.collect(self.clock,'r1','http://127.0.0.1:1',dict(max_tokens=32))
        self.assertEqual(result.completion.error_kind,'output_token_usage_mismatch')
    async def test_cancelled_request_preserves_failed_receipt(self):
        raw=RawCompletions(self.root/'responses')
        with patch('revision.feasibility.paired_collection.http_body',side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):await raw.collect(self.clock,'r1','http://127.0.0.1:1',dict(max_tokens=32))
        self.assertEqual(raw.rows[0]['error'],'client_cancelled')
