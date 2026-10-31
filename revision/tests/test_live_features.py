"""Cohort/availability regression checks; no GPU or external network."""
import asyncio
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from revision.tracing.live_features import (ServingBinding, MetricReceipt, map_receipt,
    LiveMetricCollector, LiveFeatureWindow, persist_receipt, load_receipt, UNSUPPORTED)
from revision.tracing.timing import ManualClock
from revision.tracing.feature_collection import ObservedCompletion, ServerSample
from revision.tracing.aggregation import RequestCompletion, GpuSample
from revision.tracing.diagnosis import UncalibratedClassifier
from revision.scripts.demo_live_feasibility import metric_text


def binding(domain='host'):
    return ServingBinding('session-1',1,43,'GPU-test','Qwen/Qwen2.5-7B-Instruct','0',domain)


def receipt(scope=None, **changes):
    return replace(MetricReceipt('sample-1',scope or binding(),100,120,200,metric_text(waiting=3),None),**changes)


class MappingTests(unittest.TestCase):
    def test_exact_queue_mapping_keeps_histograms_out_of_controller(self):
        sample,audit=map_receipt(receipt(),binding(),now_ns=130)
        self.assertEqual(sample.queue_depth,3)
        self.assertEqual(audit['histogram_role'],'diagnostic_only_not_controller_features')
        self.assertFalse(audit['source_event_clock_mapping'])
        self.assertEqual(set(audit['controller_mapping']),{'queue_depth_mean',*UNSUPPORTED})
    def test_foreign_worker_session_generation_device_model_engine_clock_rejected(self):
        for changes in (dict(worker_pid=44),dict(session_nonce='new'),dict(generation=2),dict(device_uuid='GPU-other'),
                        dict(model='other'),dict(engine='1'),dict(clock_domain='other')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                map_receipt(receipt(replace(binding(),**changes)),binding(),now_ns=130)
    def test_future_receipt_and_reversed_clock_rejected(self):
        with self.assertRaises(ValueError):map_receipt(receipt(),binding(),now_ns=119)
        with self.assertRaises(ValueError):receipt(received_at_ns=90)
    def test_missing_gauge_is_unavailable_not_zero(self):
        raw=metric_text().replace(b'vllm:num_requests_waiting{',b'other:waiting{')
        sample,_=map_receipt(receipt(raw=raw),binding(),now_ns=130)
        self.assertIsNone(sample.queue_depth);self.assertTrue(sample.error)
    def test_invalid_or_ambiguous_exposition_fails_closed(self):
        for raw in (b'\xff',metric_text()+b'vllm:num_requests_waiting{model_name="Qwen/Qwen2.5-7B-Instruct",engine="0"} 7\n'):
            sample,_=map_receipt(receipt(raw=raw),binding(),now_ns=130)
            self.assertIsNone(sample.queue_depth);self.assertIn('invalid_metric_exposition',sample.error)
    def test_http_and_transport_errors_preserved(self):
        for r in (receipt(http_status=503,error='metrics_http_503'),receipt(http_status=None,raw=None,error='TimeoutError')):
            sample,audit=map_receipt(r,binding(),now_ns=130)
            self.assertIsNone(sample.queue_depth);self.assertEqual(audit['error'],r.error)
    def test_persistence_roundtrip_hash_and_exclusive_names(self):
        with tempfile.TemporaryDirectory() as root:
            path=persist_receipt(root,receipt());self.assertEqual(load_receipt(root,path),receipt())
            with self.assertRaises(FileExistsError):persist_receipt(root,receipt(raw=b'changed'))
            self.assertEqual(load_receipt(root,path),receipt())
            p=next(Path(root).glob('*.txt'));p.write_bytes(b'tampered')
            with self.assertRaises(ValueError):load_receipt(root,path)
    def test_persisted_path_escape_and_extra_truth_fields_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=persist_receipt(root,receipt());p=Path(root)/path;record=json.loads(p.read_text())
            for changed in (record|dict(raw_path='../escape'),record|dict(expected_cause='queue_pressure')):
                p.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):load_receipt(root,path)
    def test_invalid_binding_and_silent_failed_receipt_rejected(self):
        with self.assertRaises(ValueError):replace(binding(),generation=True)
        with self.assertRaises(ValueError):receipt(http_status=500)


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.clock=ManualClock(120);self.scope=binding(self.clock.domain)
        self.window=LiveFeatureWindow(self.clock,100,200,binding=self.scope,provenance='synthetic_simulation',min_latency_samples=1)
    def test_histogram_presence_cannot_fill_unsupported_features(self):
        self.window.on_scrape(receipt(self.scope));self.clock.advance_to(200)
        observation=self.window.observation('window-1');metrics={m.name:m for m in observation.metrics}
        self.assertEqual(metrics['queue_depth_mean'].value,3)
        for name,reason in UNSUPPORTED.items():
            self.assertIsNone(metrics[name].value);self.assertEqual(metrics[name].missing_reason,reason)
        prediction=UncalibratedClassifier().classify(observation,now_ns=200,clock_domain=self.clock.domain)
        self.assertIsNone(prediction.policy_label)
        self.assertTrue(all('missing:'+name in prediction.reasons for name in UNSUPPORTED))
    def test_actual_client_usage_and_gpu_samples_retained(self):
        self.window.on_scrape(receipt(self.scope))
        self.window.on_completion(ObservedCompletion(RequestCompletion('r1',101,115,120,self.clock.domain,True,None),7,3,None))
        self.window.on_gpu(GpuSample('g1',110,120,self.clock.domain,40))
        self.clock.advance_to(200);metrics={m.name:m for m in self.window.close()}
        self.assertEqual(metrics['prompt_tokens_mean'].value,7);self.assertEqual(metrics['output_tokens_mean'].value,3)
        self.assertEqual(metrics['gpu_util_mean'].value,40)
    def test_persisted_window_and_bridge_keep_abstention_and_raw_hashes(self):
        from revision.tracing.feature_bridge import FeatureClassifierBridge
        import hashlib
        self.window.on_scrape(receipt(self.scope));self.clock.advance_to(200)
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'window'
            observation=self.window.persist(output,'o1')
            manifest=json.loads((output/'artifact_manifest.json').read_text())['files']
            self.assertTrue(all(hashlib.sha256((output/p).read_bytes()).hexdigest()==h for p,h in manifest.items()))
            self.assertEqual(observation.metrics,self.window.metrics)
            bridge=FeatureClassifierBridge(self.clock,provenance='synthetic_simulation',device_uuid='GPU-test',worker_pid=43)
            bridge.register('w1',self.window);prediction=bridge.classify('w1')
            self.assertIsNone(prediction.policy_label)
            with self.assertRaises(FileExistsError):self.window.persist(output,'o1')
    def test_bridge_rejects_foreign_worker_device_and_provenance(self):
        from revision.tracing.feature_bridge import FeatureClassifierBridge
        self.window.on_scrape(receipt(self.scope));self.clock.advance_to(200);self.window.close()
        for options in (dict(worker_pid=44),dict(device_uuid='GPU-other'),dict(provenance='live_online')):
            values=dict(provenance='synthetic_simulation',device_uuid='GPU-test',worker_pid=43)|options
            bridge=FeatureClassifierBridge(self.clock,**values)
            with self.assertRaises(ValueError):bridge.register('w',self.window)
    def test_histogram_changes_do_not_change_measured_features(self):
        windows=[]
        for count in (0,1000):
            w=LiveFeatureWindow(self.clock,100,200,binding=self.scope,provenance='synthetic_simulation',min_latency_samples=1)
            w.on_scrape(receipt(self.scope,raw=metric_text(count=count,waiting=3)));windows.append(w)
        self.clock.advance_to(200)
        self.assertEqual(windows[0].close(),windows[1].close())
    def test_missing_samples_accounted_as_partial_without_zero_fill(self):
        self.window.on_scrape(receipt(self.scope))
        self.clock.advance_to(130);self.window.on_scrape(receipt(self.scope,sample_id='failed',received_at_ns=130,http_status=None,raw=None,error='TimeoutError'))
        self.clock.advance_to(200);metric=next(m for m in self.window.close() if m.name=='queue_depth_mean')
        self.assertEqual((metric.value,metric.valid_samples,metric.attempted_samples,metric.coverage),(3,1,2,'partial'))
    def test_duplicate_late_and_outside_receipts_do_not_rewrite_features(self):
        self.window.on_scrape(receipt(self.scope))
        with self.assertRaises(ValueError):self.window.on_scrape(receipt(self.scope))
        self.clock.advance_to(200);before=self.window.close()
        self.assertFalse(self.window.on_scrape(receipt(self.scope,sample_id='late')))
        self.assertFalse(self.window.on_scrape(receipt(self.scope,sample_id='outside',received_at_ns=200)))
        self.assertEqual(before,self.window.close())
    def test_unbound_server_and_interval_injection_rejected(self):
        with self.assertRaises(ValueError):self.window.on_server(ServerSample('x',100,120,self.clock.domain,3,None))
        with self.assertRaises(ValueError):self.window.on_interval_metric(object())


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_loopback_receipt_can_enter_window(self):
        async def handle(reader,writer):
            await reader.readuntil(b'\r\n\r\n');body=metric_text(waiting=4)
            writer.write(f'HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()+body)
            await writer.drain();writer.close();await writer.wait_closed()
        server=await asyncio.start_server(handle,'127.0.0.1',0)
        from revision.tracing.timing import MonotonicClock
        clock=MonotonicClock();scope=binding(clock.domain);start=clock.now_ns()
        try:
            collector=LiveMetricCollector(f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}/metrics',scope)
            r=await collector.sample(clock,'live-loopback')
            window=LiveFeatureWindow(clock,start,r.received_at_ns+1,binding=scope,provenance='synthetic_simulation',min_latency_samples=1,grace_ns=1_000_000_000)
            self.assertTrue(window.on_scrape(r));self.assertEqual(window.server[0].queue_depth,4)
        finally:server.close();await server.wait_closed()
    async def test_cancelled_collection_is_not_converted_to_missing_sample(self):
        clock=ManualClock(100);collector=LiveMetricCollector('http://127.0.0.1:8012/metrics',binding(clock.domain))
        with patch('revision.tracing.live_features.http_body',side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):await collector.sample(clock,'cancelled')
    async def test_timeout_is_explicit_missing_receipt(self):
        clock=ManualClock(100);collector=LiveMetricCollector('http://127.0.0.1:8012/metrics',binding(clock.domain))
        with patch('revision.tracing.live_features.http_body',side_effect=TimeoutError):r=await collector.sample(clock,'timeout')
        self.assertIsNone(r.raw);self.assertIn('TimeoutError',r.error)
    async def test_nonlocal_endpoint_and_wrong_clock_rejected(self):
        for endpoint in ('http://example.com:80/metrics','http://127.0.0.1/metrics','http://u:p@127.0.0.1:80/metrics'):
            with self.assertRaises(ValueError):LiveMetricCollector(endpoint,binding())
        with self.assertRaises(ValueError):await LiveMetricCollector('http://127.0.0.1:80/metrics',binding()).sample(ManualClock(),'x')
