"""Bounded pilot primitives; CPU HTTP mocks are explicitly synthetic."""
import asyncio
from dataclasses import replace
import hashlib,json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from experiments.feasibility.capacity import corpus,pin_corpus,ProbeConfig,probe_cell,materialize_pairs
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.timing import MonotonicClock
from experiments.tracing.arrival_schedule import ArrivalSchedule
from experiments.scripts.demo_live_feasibility import metric_text


class Tokenizer:
    def encode(self,text,**kwargs):return list(range(len(text.split())))


class ContractTests(unittest.TestCase):
    def test_corpus_hashes_actual_prompt_and_token_ids(self):
        record=pin_corpus(Tokenizer());self.assertEqual(len(record['prompts']),2)
        for row in record['prompts']:
            self.assertEqual(hashlib.sha256(row['prompt'].encode()).hexdigest(),row['prompt_utf8_sha256'])
            self.assertEqual(row['tokenizer_prompt_tokens'],len(row['prompt'].split()))
        self.assertEqual(corpus(),corpus())
    def test_overlength_corpus_rejected_before_gpu_use(self):
        class Large:
            def encode(self,*args,**kwargs):return [1]*2040
        with self.assertRaises(ValueError):pin_corpus(Large())
    def test_config_bounds_reject_unbounded_or_ambiguous_probes(self):
        for changes in (dict(duration_s=0),dict(duration_s=100),dict(duration_s=float('nan')),dict(max_requests=100),
            dict(concurrency=(1,1)),dict(concurrency=(8,)),dict(concurrency=(True,)),dict(drain_s=-1),dict(request_timeout_s=True)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):ProbeConfig(**changes)
    def test_pairs_are_exact_deterministic_and_not_executed(self):
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/'a';b=Path(root)/'b';cells=[dict(successful_in_horizon_rps=2,request_errors=0)]*6
            one=materialize_pairs(pin_corpus(Tokenizer()),cells,'model',a)
            two=materialize_pairs(pin_corpus(Tokenizer()),cells,'model',b)
            self.assertEqual(one,two);self.assertEqual(len(one['jobs']),4)
            for row in one['schedules']:
                name=row['band']+'_offered.json'
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                schedule=ArrivalSchedule.load(a/name)
                jobs=[j for j in one['jobs'] if j['pair_id']==row['band']]
                self.assertTrue(all(j['file_sha256']==schedule.file_sha256 and not j['executed'] for j in jobs))
                self.assertLessEqual(len(schedule.requests),12)
            with self.assertRaises(FileExistsError):materialize_pairs(pin_corpus(Tokenizer()),cells,'model',a)
    def test_failed_zero_and_empty_probes_cannot_generate_schedule_rates(self):
        for cells in ([],[dict(successful_in_horizon_rps=0,request_errors=0)],[dict(successful_in_horizon_rps=1,request_errors=1)],[dict(successful_in_horizon_rps=float('inf'),request_errors=0)]):
            with tempfile.TemporaryDirectory() as root,self.assertRaises(ValueError):materialize_pairs(pin_corpus(Tokenizer()),cells,'model',Path(root)/'new')


class CellTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.output=Path(self.temp.name)/'cell'
        self.clock=MonotonicClock();self.binding=ServingBinding('owned',0,43,'GPU-test','model','0',self.clock.domain)
        self.config=ProbeConfig(duration_s=.03,concurrency=(1,2),max_requests=4,request_timeout_s=.1,drain_s=.03,sample_interval_s=.005)
    async def transport(self,endpoint,**options):
        if endpoint.endswith('/metrics'):return 200,metric_text(model='model',waiting=1)
        await asyncio.sleep(.002)
        return 200,json.dumps(dict(usage=dict(prompt_tokens=7,completion_tokens=32))).encode()
    async def run_cell(self,transport=None,**options):
        with patch('experiments.feasibility.capacity.http_body',side_effect=transport or self.transport),patch('experiments.tracing.live_features.http_body',side_effect=self.transport):
            return await probe_cell(self.clock,'http://127.0.0.1:8012',self.binding,'actual prompt',self.output,self.config,2,
                provenance='synthetic_simulation',expected_prompt_tokens=7,**options)
    async def test_budget_ownership_actual_usage_and_persisted_mapping(self):
        result=await self.run_cell();self.assertEqual((result['issued'],result['terminal_count']), (4,4))
        self.assertLessEqual(result['peak_inflight'],2);self.assertTrue(result['request_budget_reached'])
        observation=json.loads((self.output/'features/observation.json').read_text())
        self.assertEqual(observation['provenance'],'synthetic_simulation')
        metrics={m['name']:m for m in observation['metrics']}
        self.assertEqual(metrics['prompt_tokens_mean']['value'],7);self.assertIsNone(metrics['request_wait_p95_ms']['value'])
        self.assertFalse(any(not task.done() for task in asyncio.all_tasks() if task is not asyncio.current_task()))
    async def test_failed_http_preserves_responses_and_cannot_pass(self):
        async def fail(*args,**kwargs):return 503,b'{"error":"busy"}'
        with self.assertRaises(RuntimeError):await self.run_cell(fail)
        rows=json.loads((self.output/'requests.json').read_text());self.assertEqual(len(rows),4)
        self.assertTrue(all(r['error']=='http_503' for r in rows))
        self.assertTrue((self.output/'RESULT.json').exists())
    async def test_actual_token_mismatch_fails_with_raw_response(self):
        async def wrong(*args,**kwargs):return 200,b'{"usage":{"prompt_tokens":999,"completion_tokens":2}}'
        with self.assertRaises(RuntimeError):await self.run_cell(wrong)
        self.assertTrue(all(r['error']=='actual_token_usage_mismatch' for r in json.loads((self.output/'requests.json').read_text())))
    async def test_cancelled_cell_awaits_clients_and_saves_terminals(self):
        started=asyncio.Event()
        async def blocked(*args,**kwargs):started.set();await asyncio.Future()
        task=asyncio.create_task(self.run_cell(blocked));await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        rows=json.loads((self.output/'requests.json').read_text());self.assertEqual(len(rows),2)
        self.assertTrue(all(r['error']=='drain_cancelled' for r in rows))
    async def test_drain_deadline_is_bounded_failure_and_clients_are_awaited(self):
        async def blocked(*args,**kwargs):await asyncio.Future()
        with self.assertRaisesRegex(RuntimeError,'drain deadline'):await asyncio.wait_for(self.run_cell(blocked),1)
        rows=json.loads((self.output/'requests.json').read_text());self.assertEqual(len(rows),2)
        self.assertTrue(all(r['error']=='drain_cancelled' for r in rows))
    async def test_drain_completions_do_not_enter_horizon_throughput(self):
        async def slow(*args,**kwargs):
            await asyncio.sleep(.04)
            return 200,b'{"usage":{"prompt_tokens":7,"completion_tokens":32}}'
        result=await self.run_cell(slow)
        self.assertEqual(result['successful_in_horizon'],0)
        self.assertEqual(result['terminal_count'],2)
    async def test_duplicate_output_cannot_overwrite_results(self):
        await self.run_cell();before=(self.output/'requests.json').read_bytes()
        with self.assertRaises(FileExistsError):await self.run_cell()
        self.assertEqual(before,(self.output/'requests.json').read_bytes())
