"""CPU SQLite contract tests for the hardware-pilot parser; no CUDA imports."""
from pathlib import Path
import sqlite3
import json
import shutil
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from revision.tracing.nsys_backend import parse_kernel_database,NsightServingBackend
from revision.tracing.profiler import EvidenceNotReady,CaptureFailed
from revision.tracing.timing import ManualClock,TimingRecorder


class KernelDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'capture.sqlite'
        c=sqlite3.connect(self.path)
        c.executescript('''
        CREATE TABLE TARGET_INFO_GPU(id INTEGER,uuid TEXT,name TEXT);
        CREATE TABLE PROCESSES(globalPid INTEGER,pid INTEGER,name TEXT);
        CREATE TABLE StringIds(id INTEGER,value TEXT);
        CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL(start INTEGER,end INTEGER,deviceId INTEGER,globalPid INTEGER,demangledName INTEGER);
        INSERT INTO TARGET_INFO_GPU VALUES(0,'test-device','test GPU');
        INSERT INTO PROCESSES VALUES(1000001,42,'worker');
        INSERT INTO StringIds VALUES(1,'observed_kernel');
        INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES(10,30,0,1000001,1);
        INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES(40,70,0,1000001,1);
        ''')
        c.commit();c.close()

    def tearDown(self):self.temp.cleanup()

    def parse(self):return parse_kernel_database(self.path,expected_uuid='GPU-test-device',expected_pids=[42])

    def modify(self,sql):
        c=sqlite3.connect(self.path);c.execute(sql);c.commit();c.close()

    def test_observed_counts_units_device_and_worker(self):
        result=self.parse()
        self.assertEqual(result['kernel_count'],2)
        self.assertEqual(result['kernels'],[dict(name='observed_kernel',count=2,total_ns=50)])
        self.assertEqual(result['captured_worker_pids'],[42])
        self.assertEqual(result['kernel_time_sum_s'],50/1e9)
        self.assertEqual(result['kernel_envelope_s'],60/1e9)
        self.assertNotIn('capture_active_s',result)
        self.assertNotIn('diagnosis_label',result)

    def test_device_mismatch_rejected(self):
        self.modify("UPDATE TARGET_INFO_GPU SET uuid='other'")
        with self.assertRaises(ValueError):self.parse()

    def test_missing_worker_rejected(self):
        self.modify('UPDATE PROCESSES SET pid=99')
        with self.assertRaises(ValueError):self.parse()

    def test_extra_worker_rejected(self):
        self.modify("INSERT INTO PROCESSES VALUES(1000002,43,'other')")
        self.modify('INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES(100,110,0,1000002,1)')
        with self.assertRaises(ValueError):self.parse()

    def test_empty_capture_rejected(self):
        self.modify('DELETE FROM CUPTI_ACTIVITY_KIND_KERNEL')
        with self.assertRaises(ValueError):self.parse()

    def test_wrong_kernel_device_rejected(self):
        self.modify('UPDATE CUPTI_ACTIVITY_KIND_KERNEL SET deviceId=1')
        with self.assertRaises(ValueError):self.parse()

    def test_unsupported_schema_rejected(self):
        self.modify('DROP TABLE StringIds')
        with self.assertRaises(sqlite3.DatabaseError):self.parse()

    def test_zero_or_negative_duration_rejected(self):
        self.modify('UPDATE CUPTI_ACTIVITY_KIND_KERNEL SET end=start')
        with self.assertRaises(ValueError):self.parse()


class FakeProcess:
    pid=12345
    def __init__(self,*args,**kwargs):self.returncode=0
    def poll(self):return self.returncode
    def terminate(self):self.returncode=-15
    def kill(self):self.returncode=-9


class LiveBackendProtocolTests(unittest.TestCase):
    def setUp(self):
        KernelDatabaseTests.setUp(self)
        self.clock=ManualClock()
        self.directory=Path(self.temp.name)/'session';self.directory.mkdir()
        self.backend=NsightServingBackend(TimingRecorder(self.clock,provenance='live_online'),
            self.directory,self.directory/'capture',[42],'GPU-test-device','http://127.0.0.1:1',
            SimpleNamespace(poll=lambda:None))
        self.patcher=patch('revision.tracing.nsys_backend.subprocess.Popen',FakeProcess)
        self.patcher.start()
        self.backend.start('c')
        self.attempt=self.backend.attempts['c']

    def tearDown(self):
        self.patcher.stop();self.temp.cleanup()

    def ack(self,action,**changes):
        a=self.attempt
        record=dict(capture_id='c',token=a['token'],ordinal=a['ordinal'],action=action,
            source='cuda_worker_api',pid=42,device_uuid='GPU-test-device',clock_domain=self.clock.domain,
            requested_at_ns=0,returned_at_ns=0,cuda_return_code=0)
        record.update(changes)
        (self.directory/f'{a["token"]}-42-{action}.json').write_text(json.dumps(record))

    def start_callback(self,**changes):
        record=dict(source='nsys_callback',capture_id='c',token=self.attempt['token'],
            clock_domain=self.clock.domain,timestamp_ns=0)
        record.update(changes)
        (self.directory/'callback-start-test.json').write_text(json.dumps(record))

    def start_capture(self):
        self.ack('start');self.start_callback()
        self.assertEqual(self.backend.poll('c'),'capturing')

    def test_requires_worker_and_nsight_start_ack(self):
        self.ack('start')
        self.assertEqual(self.backend.poll('c'),'starting')
        with self.assertRaises(EvidenceNotReady):self.backend.evidence('c')
        self.start_callback()
        self.assertEqual(self.backend.poll('c'),'capturing')

    def test_foreign_worker_ack_fails(self):
        self.ack('start',device_uuid='GPU-other');self.start_callback()
        self.assertEqual(self.backend.poll('c'),'failed')
        self.assertFalse(self.backend.can_start_capture())

    def test_future_nsight_callback_fails(self):
        self.ack('start');self.start_callback(timestamp_ns=1)
        self.assertEqual(self.backend.poll('c'),'failed')

    def test_failed_rpc_poisoning_prevents_uncertain_recapture(self):
        self.attempt['processes']['start'].returncode=7
        self.assertEqual(self.backend.poll('c'),'failed')
        self.assertFalse(self.backend.can_start_capture())
        with self.assertRaises(CaptureFailed):self.backend.evidence('c')
        with self.assertRaises(ValueError):self.backend.start('second')

    def test_readiness_requires_sync_stop_ack_export_and_validated_parse(self):
        self.start_capture();self.backend.stop('c');self.ack('stop')
        self.assertEqual(self.backend.poll('c'),'waiting_report')
        with self.assertRaises(EvidenceNotReady):self.backend.evidence('c')
        report=self.directory/'capture.1.nsys-rep';report.write_bytes(b'fixture report '*20)
        (self.directory/'callback-report_ready-test.json').write_text(json.dumps(dict(
            source='nsys_callback',report_path=str(report),clock_domain=self.clock.domain,timestamp_ns=0)))
        self.assertEqual(self.backend.poll('c'),'exporting')
        shutil.copyfile(self.path,self.attempt['database'])
        self.assertEqual(self.backend.poll('c'),'parsing')
        with self.assertRaises(EvidenceNotReady):self.backend.evidence('c')
        self.assertEqual(self.backend.poll('c'),'ready')
        evidence=self.backend.evidence('c')
        self.assertEqual(evidence.payload['kernel_count'],2)
        self.assertEqual(evidence.provenance,'live_online')
        self.assertTrue(self.backend.can_start_capture())
        self.assertIsNone(self.backend.recorder.metrics('c')['capture_active_s'])


if __name__=='__main__':unittest.main()
