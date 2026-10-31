"""Local HTTP + deterministic feature-window/parsed-evidence joins, no GPU."""
import asyncio
from dataclasses import replace
import json
import unittest

from revision.tracing.aggregation import RequestCompletion, GpuSample
from revision.tracing.feature_collection import (ObservedCompletion, ServerSample, QueueGaugeCollector,
    FeatureWindow, collect_completion, http_body, response_usage)
from revision.tracing.feature_bridge import FeatureClassifierBridge
from revision.tracing.measured_evidence import Acquisition
from revision.tracing.profiler import ReadyEvidence, EvidenceNotReady
from revision.tracing.timing import ManualClock, MonotonicClock


class HttpFixture:
    def __init__(self,body=b'',status=200,delay=0,headers=None):
        self.body,self.status,self.delay=body,status,delay
        self.headers=headers;self.tasks=set()
    async def __aenter__(self):
        self.server=await asyncio.start_server(self.handle,'127.0.0.1',0)
        self.endpoint=f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/metrics'
        return self
    async def __aexit__(self,*args):
        self.server.close();await self.server.wait_closed()
        for task in list(self.tasks):task.cancel()
        await asyncio.gather(*list(self.tasks),return_exceptions=True)
    async def handle(self,reader,writer):
        self.tasks.add(asyncio.current_task())
        try:
            head=await reader.readuntil(b'\r\n\r\n')
            length=next((int(line.split(b':',1)[1]) for line in head.split(b'\r\n') if line.lower().startswith(b'content-length:')),0)
            await reader.readexactly(length)
            await asyncio.sleep(self.delay)
            headers=self.headers if self.headers is not None else f'Content-Length: {len(self.body)}\r\n'.encode()
            writer.write(f'HTTP/1.1 {self.status} fixture\r\n'.encode()+headers+b'Connection: close\r\n\r\n'+self.body)
            await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError):pass
        finally:
            writer.close();self.tasks.discard(asyncio.current_task())


def completion(clock,identity='request-1',end=50,success=True,prompt=10,output=5):
    return ObservedCompletion(RequestCompletion(identity,1,end,end,clock.domain,success,
        None if success else 'http_500'),prompt if success else None,output if success else None,
        None if success and prompt is not None and output is not None else 'usage_unavailable')


def ready(clock,identity='evidence-1',at=130,**changes):
    payload=dict(source='synthetic_fixture',device_uuid='GPU-test',captured_worker_pids=[123],
        kernel_count=20,kernel_time_sum_s=.1,coverage='single_configured_worker_and_device_verified')
    payload.update(changes)
    return ReadyEvidence('capture-1',identity,at,clock.domain,payload,'synthetic_simulation')


def closed_window(clock,**options):
    window=FeatureWindow(clock,0,100,min_latency_samples=2,grace_ns=10,**options)
    clock.advance_to(60)
    window.on_completion(completion(clock))
    window.on_server(ServerSample('sample-1',40,50,clock.domain,0,None))
    window.on_gpu(GpuSample('gpu-1',50,50,clock.domain,90))
    clock.advance_to(110);window.close()
    return window


class CollectorHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_response_usage_ignores_requested_lengths_and_truth_fields(self):
        body=json.dumps(dict(usage=dict(prompt_tokens=7,completion_tokens=3),expected_label='injected')).encode()
        clock=MonotonicClock()
        async with HttpFixture(body) as service:
            result=await collect_completion(clock,'r',service.endpoint,{'prompt':'x','max_tokens':9999,'expected_label':'other'})
        self.assertTrue(result.completion.success)
        self.assertEqual((result.prompt_tokens,result.output_tokens),(7,3))
        self.assertIsNone(result.usage_error)
        self.assertFalse(hasattr(result,'expected_label'))
        self.assertLess(result.completion.start_ns,result.completion.end_ns)

    async def test_http_success_without_usage_does_not_invent_tokens(self):
        async with HttpFixture(b'{"choices":[]}') as service:
            result=await collect_completion(MonotonicClock(),'r',service.endpoint,{'max_tokens':128})
        self.assertTrue(result.completion.success)
        self.assertIsNone(result.prompt_tokens)
        self.assertIsNotNone(result.usage_error)

    async def test_failures_and_timeouts_are_terminal_completions(self):
        for status,delay,timeout in [(503,0,1),(200,.1,.01)]:
            async with HttpFixture(b'{}',status,delay) as service:
                result=await collect_completion(MonotonicClock(),'r',service.endpoint,{},timeout_s=timeout)
            self.assertFalse(result.completion.success)
            self.assertIsNotNone(result.completion.error_kind)
            self.assertIsNone(result.output_tokens)

    async def test_exact_queue_series_preserves_zero_and_ignores_other_models(self):
        text=b'# TYPE queue gauge\nqueue{model="other"} 99\nqueue{model="target"} 0\n'
        async with HttpFixture(text) as service:
            result=await QueueGaugeCollector(service.endpoint,'queue{model="target"}').sample(MonotonicClock(),'s')
        self.assertEqual(result.queue_depth,0)
        self.assertIsNone(result.error)

    async def test_missing_duplicate_invalid_and_timestamped_series_remain_missing(self):
        for text in (b'other 2',b'queue 1\nqueue 2',b'queue NaN',b'queue -1',b'queue 1 12345',b'queue bad'):
            text=b'# TYPE queue gauge\n'+text
            with self.subTest(text=text):
                async with HttpFixture(text) as service:
                    result=await QueueGaugeCollector(service.endpoint,'queue').sample(MonotonicClock(),'s')
                self.assertIsNone(result.queue_depth)
                self.assertIsNotNone(result.error)

    async def test_queue_counter_cannot_be_mislabeled_as_depth_gauge(self):
        async with HttpFixture(b'# TYPE queue counter\nqueue 100') as service:
            result=await QueueGaugeCollector(service.endpoint,'queue').sample(MonotonicClock(),'s')
        self.assertIsNone(result.queue_depth)
        self.assertIn('gauge_type',result.error)

    async def test_queue_http_timeout_is_missing_not_zero(self):
        async with HttpFixture(b'# TYPE queue gauge\nqueue 0',delay=.1) as service:
            result=await QueueGaugeCollector(service.endpoint,'queue',timeout_s=.01).sample(MonotonicClock(),'s')
        self.assertIsNone(result.queue_depth)
        self.assertEqual(result.error,'TimeoutError')

    async def test_transition_http_fixture_reaches_typed_adapter_after_fake_parse(self):
        from revision.scripts.demo_feature_bridge import run_case
        result=await run_case('transition')
        self.assertFalse(result['gpu_used'])
        self.assertEqual(result['pending_evidence_checks'],2)
        self.assertEqual(len(result['observations']),2)
        queues=[next(m['value'] for m in o['metrics'] if m['name']=='queue_depth_mean') for o in result['observations']]
        self.assertEqual(queues,[8,0])
        for observation,prediction in zip(result['observations'],result['predictions']):
            self.assertIsNone(prediction['policy_label'])
            self.assertGreater(observation['kernel']['acquisition']['available_at_ns'],observation['acquisition']['end_ns'])
            self.assertGreaterEqual(prediction['decision_at_ns'],prediction['available_at_ns'])

    async def test_response_bounds_and_chunked_rejection(self):
        for body,headers,options in [(b'12345',None,{'max_bytes':2}),(b'',b'Transfer-Encoding: chunked\r\n',{})]:
            async with HttpFixture(body,headers=headers) as service:
                with self.assertRaises(ValueError):await http_body(service.endpoint,**options)

    async def test_collector_cancellation_propagates(self):
        async with HttpFixture(b'queue 0',delay=1) as service:
            task=asyncio.create_task(QueueGaugeCollector(service.endpoint,'queue').sample(MonotonicClock(),'s'))
            await asyncio.sleep(.01);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task

    def test_usage_booleans_negative_or_config_fields_are_not_counts(self):
        for usage in ({'prompt_tokens':True,'completion_tokens':3},{'prompt_tokens':-1,'completion_tokens':3},
                      {'max_tokens':99},{'prompt_tokens':2,'completion_tokens':3.5}):
            self.assertEqual(response_usage(json.dumps({'usage':usage})),(None,None,'missing_or_invalid_response_usage'))


class FeatureWindowTests(unittest.TestCase):
    def test_sparse_latency_and_unsupported_interval_statistics_are_explicit(self):
        clock=ManualClock();window=closed_window(clock)
        metrics={m.name:m for m in window.metrics}
        self.assertIsNone(metrics['request_p95_ms'].value)
        self.assertEqual(metrics['prompt_tokens_mean'].value,10)
        self.assertEqual(metrics['queue_depth_mean'].value,0)
        self.assertIn('insufficient',metrics['request_p95_ms'].missing_reason)
        for name in ('request_wait_p95_ms','prefill_service_fraction'):
            self.assertIsNone(metrics[name].value)
            self.assertIn('unsupported',metrics[name].missing_reason)
        self.assertEqual(window.audit()['successful_completions'],1)

    def test_completion_p95_failure_accounting_partial_usage_and_samples(self):
        clock=ManualClock();window=FeatureWindow(clock,0,100,min_latency_samples=2)
        clock.advance_to(90)
        window.on_completion(completion(clock,'r1',40))
        window.on_completion(completion(clock,'r2',60,prompt=None,output=None))
        window.on_completion(completion(clock,'r3',70,success=False))
        window.on_server(ServerSample('s1',10,20,clock.domain,2,None))
        window.on_server(ServerSample('s2',20,30,clock.domain,None,'missing'))
        clock.advance_to(100);metrics={m.name:m for m in window.close()}
        self.assertEqual(metrics['request_p95_ms'].coverage,'partial')
        self.assertEqual(metrics['prompt_tokens_mean'].coverage,'partial')
        self.assertEqual(metrics['queue_depth_mean'].coverage,'partial')
        self.assertEqual(window.audit()['request_errors'],1)
        self.assertEqual(metrics['completed_rps'].value,2e7)

    def test_empty_closed_window_records_zero_completions_without_zero_latency(self):
        clock=ManualClock();window=FeatureWindow(clock,0,100,min_latency_samples=2)
        clock.advance_to(100);metrics={m.name:m for m in window.close()}
        self.assertEqual(metrics['completed_rps'].value,0)
        self.assertIsNone(metrics['request_p95_ms'].value)
        self.assertIsNone(metrics['queue_depth_mean'].value)

    def test_late_receipt_is_not_backdated_and_closed_metrics_do_not_change(self):
        clock=ManualClock();window=closed_window(clock);before=window.metrics
        clock.advance_to(120)
        self.assertFalse(window.on_completion(completion(clock,'late',end=90)))
        self.assertIs(window.close(),before)
        self.assertEqual(window.audit()['events'][-1]['reason'],'late_receipt')

    def test_boolean_gpu_utilization_cannot_be_averaged_into_a_valid_number(self):
        clock=ManualClock();window=FeatureWindow(clock,0,100,min_latency_samples=1)
        clock.advance_to(50)
        with self.assertRaises(ValueError):window.on_gpu(GpuSample('g',40,40,clock.domain,True))

    def test_future_foreign_duplicate_and_early_close_rejected(self):
        clock=ManualClock();window=FeatureWindow(clock,0,100,min_latency_samples=2)
        with self.assertRaises(ValueError):window.on_completion(completion(clock))
        with self.assertRaises(ValueError):window.close()
        clock.advance_to(60);window.on_completion(completion(clock))
        with self.assertRaises(ValueError):window.on_completion(completion(clock))
        foreign=replace(completion(clock,'foreign').completion,clock_domain='foreign')
        with self.assertRaises(ValueError):window.on_completion(ObservedCompletion(foreign,10,5,None))

    def test_boundary_belongs_to_next_window_except_explicit_final_boundary(self):
        for include_end in (False,True):
            clock=ManualClock();window=FeatureWindow(clock,0,100,min_latency_samples=1,include_end=include_end)
            clock.advance_to(100)
            self.assertEqual(window.on_completion(completion(clock,end=100)),include_end)


class FeatureBridgeTests(unittest.TestCase):
    def make(self):
        clock=ManualClock();window=closed_window(clock)
        bridge=FeatureClassifierBridge(clock,provenance='synthetic_simulation',device_uuid='GPU-test',worker_pid=123)
        bridge.register('window-1',window)
        return clock,window,bridge

    def test_delayed_evidence_waits_and_then_uses_original_closed_window(self):
        clock,window,bridge=self.make();evidence=ready(clock)
        interval=Acquisition(10,90,130,clock.domain)
        with self.assertRaises(EvidenceNotReady):bridge.classify('window-1',ready=evidence,capture_acquisition=interval)
        self.assertEqual(bridge.predictions,[])
        clock.advance_to(130)
        result=bridge.classify('window-1',ready=evidence,capture_acquisition=interval)
        self.assertIsNone(result.policy_label)
        self.assertEqual(result.available_at_ns,130)
        self.assertIs(bridge.observations[0].metrics,window.metrics)
        self.assertIn('missing:prefill_service_fraction',result.reasons)
        with self.assertRaises(ValueError):bridge.classify('window-1',ready=evidence,capture_acquisition=interval)

    def test_capture_from_adjacent_window_is_not_latest_window_fallback(self):
        clock,_,bridge=self.make();clock.advance_to(230)
        with self.assertRaises(ValueError):
            bridge.classify('window-1',ready=ready(clock,at=230),capture_acquisition=Acquisition(110,190,230,clock.domain))
        self.assertFalse(bridge.consumed)

    def test_worker_device_source_provenance_domain_and_ready_identity_are_verified(self):
        clock,_,bridge=self.make();clock.advance_to(130)
        baseline=ready(clock);stamp=Acquisition(10,90,130,clock.domain)
        variants=[replace(baseline,provenance='live_online'),replace(baseline,clock_domain='unmapped'),
                  replace(baseline,ready_at_ns=129),ready(clock,device_uuid='GPU-other'),
                  ready(clock,captured_worker_pids=[456]),ready(clock,source='wrong')]
        for evidence in variants:
            with self.subTest(evidence=evidence),self.assertRaises(ValueError):
                bridge.classify('window-1',ready=evidence,capture_acquisition=stamp)

    def test_truth_fields_and_kernel_names_never_enter_measured_bundle(self):
        clock,_,bridge=self.make();clock.advance_to(130)
        evidence=ready(clock,expected_label='prefill',scenario='overlap',top_kernel_name='misleading-name')
        bridge.classify('window-1',ready=evidence,capture_acquisition=Acquisition(10,90,130,clock.domain))
        observation=bridge.observations[0]
        self.assertFalse(hasattr(observation.kernel,'expected_label'))
        self.assertFalse(hasattr(observation.kernel,'top_kernel_name'))
        self.assertIsNone(bridge.predictions[0].policy_label)

    def test_cheap_only_is_unknown_and_cannot_be_classified_twice(self):
        _,_,bridge=self.make();result=bridge.classify('window-1')
        self.assertIn('kernel_evidence_unavailable',result.reasons)
        with self.assertRaises(ValueError):bridge.classify('window-1')


if __name__=='__main__':unittest.main()
