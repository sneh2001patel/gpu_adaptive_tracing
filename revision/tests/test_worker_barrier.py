"""No CUDA imports: token/clock/capture-state validation and fixed route."""
import unittest
from types import SimpleNamespace
from revision.tracing.worker_barrier import worker_barrier,validate_barrier,install_barrier_route


class BarrierTests(unittest.TestCase):
    def setUp(self):
        self.command=dict(token='a'*32,session_nonce='owned-session',generation=1,clock_domain='host',requested_at_ns=10)
        self.calls=[]
    def build(self,**changes):
        values=iter((11,12));options=dict(pid=43,device_uuid='GPU-test',clock_domain='host',session_nonce='owned-session',generation=1,
            capture_active=False,synchronize=lambda:self.calls.append('cuda_sync'),now_ns=lambda:next(values))|changes
        return worker_barrier(self.command,**options)
    def test_sync_receipt_and_parent_visibility(self):
        receipt=self.build();self.assertEqual(self.calls,['cuda_sync'])
        self.assertEqual(validate_barrier(receipt,self.command,pid=43,device_uuid='GPU-test',received_at_ns=13),receipt)
    def test_foreign_nonce_generation_clock_or_active_capture_rejected_before_sync(self):
        for changes in (dict(session_nonce='other'),dict(generation=2),dict(clock_domain='other'),dict(capture_active=True),dict(session_nonce='')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.build(**changes)
        self.assertEqual(self.calls,[])
    def test_future_parent_request_and_reversed_worker_time_rejected(self):
        for pair in ((9,12),(11,10)):
            values=iter(pair)
            with self.assertRaises(ValueError):self.build(now_ns=lambda:next(values))
    def test_sync_failure_does_not_produce_success(self):
        def fail():raise RuntimeError('cuda failure')
        with self.assertRaises(RuntimeError):self.build(synchronize=fail)
    def test_stale_foreign_and_future_receipts_rejected(self):
        receipt=self.build()
        for changes in (dict(token='old'),dict(pid=44),dict(device_uuid='GPU-other'),dict(generation=2),dict(clock_domain='other'),dict(capture_active=True),dict(completed_at_ns=100)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_barrier(receipt|changes,self.command,pid=43,device_uuid='GPU-test',received_at_ns=13)
    def test_extra_command_fields_and_invalid_timestamps_rejected(self):
        self.command['expected_label']='must_not_be_an_input'
        with self.assertRaises(ValueError):self.build()
        self.command.pop('expected_label');self.command['requested_at_ns']=True
        with self.assertRaises(ValueError):self.build()


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_only_calls_fixed_worker_barrier(self):
        calls=[];routes={}
        class Router:
            def post(self,path):
                def decorate(fn):routes[path]=fn;return fn
                return decorate
        class Client:
            async def collective_rpc(self,method,timeout):calls.append((method,timeout))
        api=SimpleNamespace(router=Router(),Request=object,engine_client=lambda request:Client(),Response=lambda **k:k)
        install_barrier_route(api);result=await routes['/revision/barrier'](object())
        self.assertEqual(calls,[('revision_barrier',10)]);self.assertEqual(result,dict(status_code=200))
