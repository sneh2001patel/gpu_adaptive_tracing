import base64
import json
import random
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

CHECKS = Path(__file__).resolve().parents[1] / 'cases' / 'checks'
sys.path.insert(0, str(CHECKS))
import case_workloads as cw  # noqa: E402


def decode_png(url):
    """Minimal decoder for the encoder's own output: 8-bit RGB, filters None and Up only."""
    raw = base64.b64decode(url.split(',', 1)[1])
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    pos, idat, size = 8, b'', None
    while pos < len(raw):
        n = int.from_bytes(raw[pos:pos + 4], 'big')
        kind, data = raw[pos + 4:pos + 8], raw[pos + 8:pos + 8 + n]
        if zlib.crc32(kind + data) & 0xffffffff != int.from_bytes(raw[pos + 8 + n:pos + 12 + n], 'big'):
            raise ValueError('bad CRC')
        if kind == b'IHDR':
            size = int.from_bytes(data[:4], 'big'), int.from_bytes(data[4:8], 'big')
        idat += data if kind == b'IDAT' else b''
        pos += 12 + n
    width, height = size
    stream, rows, prev = zlib.decompress(idat), [], bytes(3 * width)
    for y in range(height):
        line = stream[y * (3 * width + 1):(y + 1) * (3 * width + 1)]
        row = line[1:] if line[0] == 0 else bytes((a + b) % 256 for a, b in zip(line[1:], prev))
        assert line[0] in (0, 2)
        rows.append(row)
        prev = row
    return width, height, rows


class RegistryTests(unittest.TestCase):
    def test_every_case_resolves_both_sides(self):
        for case_id in cw.CASES:
            for side in ('bug', 'fixed'):
                cfg = cw.config(case_id, side)
                for key in ('env', 'version', 'model', 'server_args', 'reference', 'healthy_rate', 'incident_rate'):
                    self.assertIn(key, cfg, (case_id, side, key))
                self.assertTrue(cfg['server_args'].endswith(cw.COMMON_ARGS))

    def test_toggles_differ_only_where_declared(self):
        self.assertIn('--use-v2-block-manager', cw.config('7619', 'bug')['server_args'])
        self.assertNotIn('--use-v2-block-manager', cw.config('7619', 'fixed')['server_args'])
        self.assertEqual((cw.config('6240', 'bug').get('patch'), cw.config('6240', 'fixed')['patch']),
                         (None, '6240_cutlass_off'))
        self.assertEqual((cw.config('7592', 'bug')['env'], cw.config('7592', 'fixed')['env']), ('v055', 'v060'))
        self.assertEqual(cw.config('3087', 'bug')['patch'], cw.config('3087', 'fixed')['patch'])

    def test_case_patches_exist_in_the_server_wrapper(self):
        source = (CHECKS / 'case_server.py').read_text()
        for case in cw.CASES.values():
            for side in case['configs'].values():
                if 'patch' in side:
                    self.assertIn(f"'{side['patch']}'", source)

    def test_engine_stall_patch_spins_before_scheduling(self):
        import types
        calls = []
        sched_mod = types.ModuleType('vllm.v1.core.sched.scheduler')
        sched_mod.Scheduler = type('Scheduler', (), {'schedule': lambda self: calls.append(1) or 'out'})
        names = ['vllm', 'vllm.v1', 'vllm.v1.core', 'vllm.v1.core.sched', 'vllm.v1.core.sched.scheduler']
        saved = {n: sys.modules.get(n) for n in names}
        for n in names[:-1]:
            sys.modules[n] = types.ModuleType(n)
        sys.modules[names[-1]] = sched_mod
        try:
            import case_server
            case_server.PATCHES['engine_stall_v1']('30')
            import time
            start = time.perf_counter()
            self.assertEqual(sched_mod.Scheduler().schedule(), 'out')
            self.assertGreaterEqual(time.perf_counter() - start, 0.03)
            self.assertEqual(calls, [1])
        finally:
            for n, m in saved.items():
                if m is None:
                    sys.modules.pop(n, None)
                else:
                    sys.modules[n] = m

class RequestTests(unittest.TestCase):
    def test_png_is_valid_and_matches_its_pixel_formula(self):
        width, height, rows = decode_png(cw.png_data_url(9, size=32))
        self.assertEqual((width, height), (32, 32))
        a, c = 1 + 9 % 7, 9 * 37 % 256
        for x, y in ((0, 0), (5, 7), (31, 31)):
            self.assertEqual(tuple(rows[y][3 * x:3 * x + 3]), ((a * x + c) % 256, (y + 9) % 256, (x + y) % 256))

    def test_images_are_distinct_per_request_and_small(self):
        urls = {cw.png_data_url(i) for i in range(20)}
        self.assertEqual(len(urls), 20)
        self.assertLess(max(len(u) for u in urls), 20_000)

    def test_mm_kwargs_only_on_the_bug_side(self):
        rng = random.Random(0)
        _, bug = cw.request('25418', 'bug', 'm', 0, 0, rng)
        _, fixed = cw.request('25418', 'fixed', 'm', 0, 0, rng)
        self.assertTrue(1.9 <= bug['mm_processor_kwargs']['fps'] <= 2.1)
        self.assertNotIn('mm_processor_kwargs', fixed)
        self.assertEqual(bug['messages'], fixed['messages'])

    def test_prefix_groups_share_a_prompt_and_groups_differ(self):
        rng = random.Random(0)
        prompts = [cw.request('7619', 'bug', 'm', i, g, rng)[1]['prompt'] for g in (0, 0, 1) for i in (0,)]
        self.assertEqual(prompts[0], prompts[1])
        self.assertNotEqual(prompts[0][:20], prompts[2][:20])  # differs in the first block, so no cache sharing

    def test_bodies_follow_the_reproduction_checks(self):
        rng = random.Random(0)
        self.assertEqual(cw.request('7592', 'bug', 'm', 0, 0, rng)[1]['prompt'], 'hi' * 511)
        self.assertEqual(cw.request('19732', 'bug', 'm', 0, 0, rng)[1]['guided_json'], cw.TABLE_SCHEMA)
        self.assertEqual(cw.request('6240', 'fixed', 'm', 0, 0, rng)[1]['max_tokens'], 256)


class ScheduleTests(unittest.TestCase):
    def schedule(self, d, case, side):
        out = Path(d) / f'{case}_{side}.jsonl'
        subprocess.run([sys.executable, str(CHECKS / 'make_schedule.py'), '--pattern', 'overload', '--case', case,
                        '--side', side, '--warmup', '20', '--incident', '30', '--tail', '10', '--out', str(out)],
                       check=True, capture_output=True)
        return [json.loads(line) for line in out.read_text().splitlines()]

    def test_both_sides_get_the_same_arrivals(self):
        with tempfile.TemporaryDirectory() as d:
            bug, fixed = self.schedule(d, '25418', 'bug'), self.schedule(d, '25418', 'fixed')
        self.assertEqual([r['t'] for r in bug], [r['t'] for r in fixed])
        self.assertTrue(all(r['body']['model'] == cw.CASES['25418']['model'] for r in bug))

    def test_group_size_sends_simultaneous_requests(self):
        with tempfile.TemporaryDirectory() as d:
            rows = self.schedule(d, '7619', 'bug')
        size = cw.CASES['7619']['group_size']
        self.assertEqual(len(rows) % size, 0)
        first = rows[:size]
        self.assertEqual(len({r['t'] for r in first}), 1)
        self.assertEqual(len({r['body']['prompt'] for r in first}), 1)


if __name__ == '__main__':
    unittest.main()
