"""CPU rejection tests for same-process probes and exact client/engine joins."""
import asyncio,copy,json,os,tempfile,time,types,unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from revision.tracing.event_probe import register_source,worker_probe,install_event_route
from revision.tracing.server_events import EventJournal,atomic_json
from revision.tracing.live_features import ServingBinding
from revision.feasibility.event_commission import validate_join


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.binding=ServingBinding('session',0,os.getpid(),'GPU-test','model','0','host')
        self.journal=EventJournal(self.binding,time.monotonic_ns)
        self.source=register_source(self.root,self.journal)
        self.command=dict(token='a'*32,binding=asdict(self.binding),requested_at_ns=time.monotonic_ns())
        atomic_json(self.root/'probe_command.json',self.command)
        self.kw=dict(pid=os.getpid(),device_uuid='GPU-test',session_nonce='session',generation=0,clock_domain='host',capture_active=False)
    def test_hook_and_idle_rpc_preserve_original_snapshot(self):
        self.source.publish();path=self.root/('snapshot-'+'a'*32+'.json');original=path.read_bytes()
        worker_probe(self.root,**self.kw)
        self.assertEqual(path.read_bytes(),original);self.assertEqual(len(self.journal.used_probes),1)
    def test_changed_command_under_consumed_token_rejected(self):
        self.source.publish();atomic_json(self.root/'probe_command.json',self.command|dict(requested_at_ns=time.monotonic_ns()))
        with self.assertRaises(ValueError):worker_probe(self.root,**self.kw)
    def test_foreign_identity_capture_and_missing_registry_rejected(self):
        for changes in (dict(pid=os.getpid()+1),dict(session_nonce='other'),dict(generation=1),dict(clock_domain='other'),dict(device_uuid='GPU-other'),dict(capture_active=True)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):worker_probe(self.root,**(self.kw|changes))
        with self.assertRaises(ValueError):worker_probe(self.root/'missing',**self.kw)
        with patch('revision.tracing.event_probe.os.getpid',return_value=os.getpid()+1),self.assertRaises(ValueError):self.source.publish()
    def test_source_registration_cannot_be_replaced(self):
        with self.assertRaises(ValueError):register_source(self.root,self.journal)
    def test_fixed_route_exposes_only_named_rpc(self):
        calls=[]
        async def rpc(*args,**kwargs):calls.append((args,kwargs))
        router=types.SimpleNamespace(post=lambda path:lambda fn:fn)
        api=types.SimpleNamespace(router=router,Request=object,Response=lambda **kw:kw,
            engine_client=lambda req:types.SimpleNamespace(collective_rpc=rpc))
        result=asyncio.run(install_event_route(api)(object()))
        self.assertEqual(result,dict(status_code=200));self.assertEqual(calls,[(('revision_event_probe',),dict(timeout=10))])


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.binding=ServingBinding('s',0,43,'GPU-test','model','0','host');clock=lambda:100
        journal=EventJournal(self.binding,lambda:0)
        journal.now_ns=clock
        journal.record('engine_admitted','cmpl-id-0',10,20)
        journal.record('first_positive_schedule','cmpl-id-0',30,40)
        journal.record('scheduler_finished','cmpl-id-0',50,60,terminal_status='FINISHED_LENGTH_CAPPED')
        command=dict(token='a'*32,binding=asdict(self.binding),requested_at_ns=90)
        self.receipt=dict(command=command,data=journal.probe(command),received_at_ns=110)
        self.row=dict(payload=dict(prompt='text',n=1,stream=False,request_id='id',max_tokens=32),
            http_status=200,response=dict(id='cmpl-id',usage=dict(prompt_tokens=17,completion_tokens=32,total_tokens=49),
                choices=[dict(finish_reason='length')]),expected_prompt_tokens=17,requested_at_ns=1,received_at_ns=80)
    def test_exact_mapping_and_delay_bounds(self):
        rows=validate_join([self.row],self.receipt,self.binding)
        self.assertEqual(rows[0]['engine_request_id'],'cmpl-id-0');self.assertEqual(rows[0]['wait_lower_ms'],10/1e6)
    def test_duplicate_and_request_budget_rejected(self):
        for rows in ([],[self.row,self.row],[self.row]*9):
            with self.assertRaises(ValueError):validate_join(rows,self.receipt,self.binding)
    def test_suffix_guess_unsupported_shape_tokens_and_clock_rejected(self):
        changes=[('response','id','cmpl-id-0'),('payload','n',2),('payload','prompt',['text']),('payload','stream',True)]
        for location,key,value in changes:
            row=copy.deepcopy(self.row);row[location][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_join([row],self.receipt,self.binding)
        row=copy.deepcopy(self.row);row['response']['usage']['completion_tokens']=31
        with self.assertRaises(ValueError):validate_join([row],self.receipt,self.binding)
        row=self.row|dict(received_at_ns=55)
        with self.assertRaises(ValueError):validate_join([row],self.receipt,self.binding)


if __name__=='__main__':unittest.main()
