"""CPU ownership/persistence checks for the one-shot GPU discovery wrapper."""
import asyncio,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from experiments.scripts.run_l4_discovery import close_owned,group_exists,save,sha_file
from experiments.tracing.timing import MonotonicClock


class DiscoveryWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_closes_only_its_owned_serving_process_group(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            self.assertTrue(group_exists(process.pid))
            result=await close_owned(process,MonotonicClock())
            self.assertTrue(result['group_absent']);self.assertEqual(result['pid'],process.pid)
            self.assertFalse(group_exists(process.pid));os.kill(os.getpid(),0)
            self.assertGreaterEqual(result['completed_at_ns'],result['started_at_ns'])
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)

    async def test_transient_visibility_denial_is_not_confirmed_absence(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        original=os.killpg;denied=False
        def once(pid,sig):
            nonlocal denied
            if sig==0 and not denied:denied=True;raise PermissionError('fixture transient visibility')
            return original(pid,sig)
        try:
            with patch('experiments.scripts.run_l4_discovery.os.killpg',side_effect=once):result=await close_owned(process,MonotonicClock())
            self.assertTrue(denied);self.assertTrue(result['group_absent'])
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)

    async def test_absent_process_needs_no_signal(self):
        self.assertEqual(await close_owned(None,MonotonicClock()),dict(owned=False,group_absent=True))

    async def test_already_exited_owned_group_is_reaped(self):
        process=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
        await asyncio.to_thread(process.wait,3)
        result=await close_owned(process,MonotonicClock())
        self.assertTrue(result['group_absent']);self.assertFalse(result['escalated'])

    async def test_artifact_json_and_streamed_model_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'model';raw=b'fixed bytes'*(1024*1024);path.write_bytes(raw)
            self.assertEqual(sha_file(path),hashlib.sha256(raw).hexdigest())
            save(root/'result.json',dict(role='test',value=None))
            self.assertEqual(json.loads((root/'result.json').read_text()),dict(role='test',value=None))
            with self.assertRaises(ValueError):save(root/'invalid.json',dict(value=float('nan')))
