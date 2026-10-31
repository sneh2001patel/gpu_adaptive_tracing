"""Feasibility contracts and local mocked discovery; no GPU libraries/calls."""
import asyncio,copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from experiments.feasibility.metrics import inspect,sequence,count,GAUGES,HISTOGRAMS
from experiments.feasibility.harness import run,check,bounded_file
from experiments.feasibility.discovery import ReadOnlyDiscovery
from experiments.scripts.demo_live_feasibility import FixtureAdapter,metric_text
from experiments.tracing.timing import MonotonicClock


def config():
    data=json.loads(Path('experiments/configs/l4_feasibility_v1.json').read_text())
    data.update(device_uuid='GPU-fixture',metric_interval_s=0)
    return data


class MetricTests(unittest.TestCase):
    def setUp(self):self.raw=metric_text();self.model=config()['model']
    def inspect(self,raw=None):return inspect(self.raw if raw is None else raw,model=self.model)

    def test_exact_model_engine_and_cohort_no_phase_mapping(self):
        result=self.inspect();self.assertTrue(all(v['available'] for v in result['gauges'].values()))
        self.assertFalse(result['admission_window_wait_supported']);self.assertFalse(result['prefill_service_fraction_supported'])
        for histogram in result['histograms'].values():
            self.assertTrue(histogram['present']);self.assertEqual(histogram['cohort'],'finished_requests_reported_by_logger')

    def test_label_order_and_json_escaped_model(self):
        raw=self.raw.replace(b'model_name="Qwen/Qwen2.5-7B-Instruct",engine="0"',b'engine="0",model_name="Qwen/Qwen2.5-7B-Instruct"')
        self.assertTrue(self.inspect(raw)['gauges'][GAUGES[0]]['available'])
        model='model,"quoted\\name'
        self.assertTrue(inspect(metric_text(model=model),model=model)['histograms'][HISTOGRAMS[0]]['present'])

    def test_other_models_engines_do_not_mix_or_satisfy_missing_target(self):
        wrong=metric_text(model='other').replace(b'engine="0"',b'engine="9"')
        # TYPE declarations are family-wide, not repeated per model.
        wrong=b'\n'.join(l for l in wrong.splitlines() if not l.startswith(b'#'))+b'\n'
        result=self.inspect(self.raw+wrong);self.assertEqual(result['other_scope_count'],1)
        empty=self.inspect(self.raw.replace(b'engine="0"',b'engine="9"'))
        self.assertFalse(empty['gauges'][GAUGES[0]]['available'])

    def test_duplicate_types_samples_labels_and_extra_labels_rejected(self):
        line=next(l for l in self.raw.splitlines() if l.startswith(GAUGES[0].encode()+b'{'))
        for raw in (self.raw+line+b'\n',self.raw+b'# TYPE '+GAUGES[0].encode()+b' gauge\n',
                    self.raw.replace(b'engine="0"',b'engine="0",engine="0"'),
                    self.raw.replace(b'engine="0"',b'engine="0",worker="unknown"')):
            with self.assertRaises(ValueError):self.inspect(raw)

    def test_wrong_type_and_missing_histogram_components_unavailable(self):
        result=self.inspect(self.raw.replace(b'num_requests_waiting gauge',b'num_requests_waiting counter'))
        self.assertFalse(result['gauges'][GAUGES[0]]['available'])
        family=HISTOGRAMS[0].encode();raw=b'\n'.join(l for l in self.raw.splitlines() if not l.startswith(family+b'_count'))
        self.assertFalse(self.inspect(raw)['histograms'][HISTOGRAMS[0]]['present'])

    def test_timestamps_nonfinite_gauges_and_fractional_requests_rejected(self):
        line=next(l for l in self.raw.splitlines() if l.startswith(GAUGES[0].encode()+b'{'))
        for value in (b'NaN',b'+Inf',b'-1',b'.5',b'0 1234'):
            with self.assertRaises(ValueError):self.inspect(self.raw.replace(line,line.rsplit(b' ',1)[0]+b' '+value))

    def test_histogram_count_sum_and_buckets_checked(self):
        for raw in (self.raw.replace(b'le="1"} 2',b'le="1"} 1'),
                    self.raw.replace(b'le="+Inf"} 2',b'le="+Inf"} 3'),
                    self.raw.replace(b'_sum{',b'_sum{').replace(b'} 0.02',b'} NaN'),
                    self.raw.replace(b'le="1"',b'le="0.1"')):
            with self.assertRaises(ValueError):self.inspect(raw)
        for value in ('9007199254740993','-1','NaN','Infinity','1.1'):
            with self.assertRaises(ValueError):count(value)

    def test_histogram_decrease_or_schema_change_never_maps_to_feature(self):
        result=sequence([metric_text(count=3),metric_text(count=1)],model=self.model)
        self.assertTrue(all(r['reason']=='counter_decrease_or_reset' for r in result['transitions']))
        changed=sequence([self.raw,self.raw.replace(b'le="1"',b'le="2"')],model=self.model)
        self.assertTrue(all(r['reason']=='bucket_schema_changed' for r in changed['transitions']))
        self.assertTrue(all(not r['usable_as_controller_feature'] for r in changed['transitions']))

    def test_newly_reported_finished_counts_are_inventory_only(self):
        result=sequence([metric_text(count=1),metric_text(count=3)],model=self.model)
        self.assertTrue(all(r['newly_reported_finished_requests']==2 for r in result['transitions']))
        self.assertTrue(all(not r['usable_as_controller_feature'] for r in result['transitions']))

    def test_invalid_snapshot_remains_in_sequence_and_size_limit(self):
        result=sequence([self.raw,b'\xff'],model=self.model)
        self.assertFalse(result['snapshots'][1]['ok']);self.assertTrue(all(r['reason']=='invalid_snapshot' for r in result['transitions']))
        with self.assertRaises(ValueError):self.inspect(b'x'*(1048576+1))
        with self.assertRaises(ValueError):sequence([],model=self.model)


class GateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.cfg=config()
    async def execute(self,mode='positive',adapter=None,changes=None):
        c=self.cfg|(changes or {});adapter=adapter or FixtureAdapter(c,mode)
        result=await run(adapter,c,self.root/mode,provenance='synthetic_simulation',clock_domain=adapter.domain)
        return result,adapter

    async def test_positive_mechanics_are_never_live_or_study_readiness(self):
        result,adapter=await self.execute();self.assertTrue(result['gate_mechanics_passed'])
        self.assertFalse(result['live_feasibility_passed']);self.assertFalse(result['study_ready']);self.assertFalse(result['diagnosis_ready'])
        self.assertIsNone(result['capture_active_s']);self.assertEqual(adapter.calls,['inventory','metrics','quiet_reset','capture','cleanup'])
        self.assertEqual(result['context']['worker_pid'],43)
        manifest=json.loads((self.root/'positive/artifact_manifest.json').read_text())
        for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((self.root/'positive'/name).read_bytes()).hexdigest(),digest)

    async def test_wrong_pins_block_activity_but_cleanup_still_runs(self):
        result,adapter=await self.execute('wrong_pin');self.assertEqual(adapter.calls,['inventory','cleanup'])
        self.assertEqual(result['gates']['capture']['status'],'skipped')

    async def test_bad_metric_hash_blocks_quiet_reset(self):
        result,adapter=await self.execute('bad_hash');self.assertNotIn('quiet_reset',adapter.calls)
        self.assertEqual(result['gates']['metrics']['status'],'failed')

    async def test_busy_and_stale_reset_block_capture(self):
        for mode in ('busy','stale_reset'):
            result,adapter=await self.execute(mode);self.assertNotIn('capture',adapter.calls);self.assertIn('cleanup',adapter.calls)
            self.assertEqual(result['gates']['quiet_reset']['status'],'failed')

    async def test_future_evidence_and_cleanup_failure_prevent_pass(self):
        for mode in ('future_parse','cleanup_failure'):
            result,adapter=await self.execute(mode);self.assertFalse(result['gate_mechanics_passed']);self.assertIn('cleanup',adapter.calls)

    async def test_discovery_does_not_skip_unavailable_activity_gate(self):
        result,adapter=await self.execute('discovery_only');self.assertTrue(result['discovery_passed'])
        self.assertEqual(result['gates']['quiet_reset']['status'],'unavailable');self.assertNotIn('capture',adapter.calls)

    async def test_invalid_configs_rejected_before_output_creation(self):
        for index,changes in enumerate((dict(main_matrix_enabled=True),dict(calibration_enabled=True),dict(capture_attempts=2),
            dict(capture_attempts=True),dict(stage_timeout_s=0),dict(metric_interval_s=-.5),dict(metric_samples=101),dict(device_uuid='wrong'))):
            with self.subTest(changes=changes),self.assertRaises(ValueError):await self.execute('invalid'+str(index),changes=changes)
            self.assertFalse((self.root/('invalid'+str(index))).exists())

    async def test_fresh_run_never_overwrites_output(self):
        await self.execute()
        with self.assertRaises(FileExistsError):await self.execute()

    async def test_deadline_and_cancellation_keep_cleanup_and_results(self):
        adapter=FixtureAdapter(self.cfg)
        async def slow(*args):await asyncio.sleep(10)
        adapter.inventory=slow
        result,_=await self.execute('timeout',adapter=adapter,changes=dict(stage_timeout_s=.005))
        self.assertEqual(result['gates']['inventory']['status'],'failed');self.assertIn('cleanup',adapter.calls)
        adapter=FixtureAdapter(self.cfg);adapter.inventory=slow
        task=asyncio.create_task(self.execute('cancelled',adapter=adapter));await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        saved=json.loads((self.root/'cancelled/RESULT.json').read_text())
        self.assertEqual(saved['gates']['inventory']['status'],'cancelled');self.assertIn('cleanup',adapter.calls)

    async def test_cached_barrier_and_no_worker_barrier_rejected(self):
        base=FixtureAdapter(self.cfg);data=await base.quiet_reset(self.root,{})
        for mode in ('cached','source','clock','pid'):
            bad=copy.deepcopy(data)
            if mode=='cached':bad['before'][1]['barrier_token']=bad['before'][0]['barrier_token']
            elif mode=='source':bad['after'][0]['barrier_source']='gauge_only'
            elif mode=='clock':bad['clock_domain']='foreign'
            else:bad['after'][0]['worker_pid']=42
            with self.assertRaises(ValueError):check('quiet_reset',bad,self.cfg,dict(worker_pid=42),self.root,'synthetic_simulation',base.domain)

    async def test_capture_worker_uuid_and_artifact_integrity(self):
        result,adapter=await self.execute();root=self.root/'positive';data=json.loads((root/'capture_receipt.json').read_text())
        for c,changed in ((self.cfg|dict(device_uuid='GPU-other'),data),(self.cfg,data|dict(sqlite_sha256='0'*64)),
                          (self.cfg,data|dict(stop_ack_ns=data['start_ack_ns']+1))):
            with self.assertRaises(ValueError):check('capture',changed,c,dict(worker_pid=43,reset_completed_ns=20_004_000),root,'synthetic_simulation',adapter.domain)

    async def test_artifact_path_escape_symlink_and_missing_rejected(self):
        (self.root/'file').write_text('x');(self.root/'link').symlink_to(self.root/'file')
        for path in ('../outside','/etc/passwd','missing','link'):
            with self.assertRaises(ValueError):bounded_file(self.root,path)


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=config();self.clock=MonotonicClock();self.model=self.root/self.cfg['model_revision'];self.model.mkdir();(self.model/'config.json').write_text('{}')
        self.session=self.root/'session';self.session.mkdir();(self.session/'worker-1.json').write_text(json.dumps(dict(pid=os.getpid(),device_uuid='GPU-fixture')))
        self.paths=[]
        async def handle(reader,writer):
            try:
                header=await reader.readuntil(b'\r\n\r\n');path=header.split(b' ')[1].decode();self.paths.append(path)
                raw=metric_text() if path=='/metrics' else json.dumps(dict(data=[dict(id=self.cfg['model'])])).encode() if path=='/v1/models' else b'{}'
                writer.write(f'HTTP/1.1 200 OK\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n'.encode()+raw);await writer.drain()
            finally:writer.close()
        self.server=await asyncio.start_server(handle,'127.0.0.1',0)
        self.endpoint=f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        self.addAsyncCleanup(self.close)
    async def close(self):self.server.close();await self.server.wait_closed()
    def adapter(self,endpoint=None):return ReadOnlyDiscovery(self.cfg,self.clock,endpoint or self.endpoint,self.model,self.session)
    def command(self,argv):
        if argv[0]=='nsys':return 'NVIDIA Nsight Systems version 2026.3.1'
        if '--query-gpu=uuid,name' in argv:return 'GPU-fixture, NVIDIA L4'
        return 'GPU-fixture, '+str(os.getpid())

    async def test_actual_loopback_discovery_remains_read_only_and_activity_blocked(self):
        with patch('experiments.feasibility.discovery.command',side_effect=self.command),patch('experiments.feasibility.discovery.version',return_value='0.10.2'):
            result=await run(self.adapter(),self.cfg,self.root/'output',provenance='synthetic_simulation',clock_domain=self.clock.domain)
        self.assertTrue(result['discovery_passed']);self.assertFalse(result['gate_mechanics_passed']);self.assertFalse(result['live_feasibility_passed'])
        self.assertEqual(result['gates']['quiet_reset']['status'],'unavailable');self.assertEqual(result['gates']['capture']['status'],'skipped')
        self.assertFalse(result['context']['owned_cleanup_verified'])
        self.assertEqual(set(self.paths),{'/health','/v1/models','/metrics'})
        self.assertFalse(result['context']['metric_capabilities']['snapshots'][0]['inspection']['prefill_service_fraction_supported'])

    async def test_nonlocal_or_credential_endpoints_rejected(self):
        for endpoint in ('http://example.com:8000','http://user:password@localhost:8000','http://127.0.0.1:8000/path','http://127.0.0.1:8000?token=x'):
            with self.assertRaises(ValueError):self.adapter(endpoint)

    async def test_model_config_symlinks_must_remain_in_the_configured_cache(self):
        output=self.root/'out';output.mkdir();(output/'source_manifest.json').write_text('{}')
        path=self.model/'config.json';path.unlink();inside=self.model/'actual-config.json';inside.write_text('{}');path.symlink_to(inside)
        with patch('experiments.feasibility.discovery.command',side_effect=self.command),patch('experiments.feasibility.discovery.version',return_value='0.10.2'):
            receipt=await self.adapter().inventory(output,{})
        self.assertEqual(receipt['model_config_sha256'],hashlib.sha256(b'{}').hexdigest())
        path.unlink();outside=self.root/'foreign-config.json';outside.write_text('{}');path.symlink_to(outside)
        with self.assertRaises(ValueError):await self.adapter().inventory(output,{})

    async def test_mismatched_live_compute_pid_blocks_inventory(self):
        def wrong(argv):return 'GPU-fixture, 99999999' if '--query-compute-apps=gpu_uuid,pid' in argv else self.command(argv)
        output=self.root/'out';output.mkdir();(output/'source_manifest.json').write_text('{}')
        with patch('experiments.feasibility.discovery.command',side_effect=wrong),patch('experiments.feasibility.discovery.version',return_value='0.10.2'):
            with self.assertRaises(ValueError):await self.adapter().inventory(output,{})
