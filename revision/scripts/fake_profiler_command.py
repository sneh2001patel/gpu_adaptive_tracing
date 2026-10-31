#!/usr/bin/env python3
"""File-protocol subprocess fixture. Does not invoke Nsight or touch a GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time


def atomic(path, record):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(record, allow_nan=False) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('collect', 'stop', 'export', 'parse'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--mode', default='ok')
    parser.add_argument('--delay', type=float, default=.01)
    args = parser.parse_args()
    plan = json.loads((args.directory / 'plan.json').read_text())
    base = {key:plan[key] for key in ('protocol', 'capture_id', 'token')}
    base['source'] = 'fake_executable'
    def write(name, **values):
        atomic(args.directory / name, dict(base, **values))
    if args.mode == args.stage + '-exit':
        return 7
    if args.mode == args.stage + '-hang':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        (args.directory / 'command-hanging').touch()
        while True:
            time.sleep(.1)
    if args.stage == 'collect':
        if args.mode != 'no-start-ack':
            if args.mode == 'wrong-start-ack':
                base['token'] = 'wrong-attempt'
            write('start_ack.json', kind='capture_started', ack_basis='synthetic_fixture')
        while not (args.directory / 'stop.request').exists():
            time.sleep(.005)
        request = json.loads((args.directory / 'stop.request').read_text())
        if request['token'] != base['token']:
            return 8
        if args.mode != 'no-stop-ack':
            write('stop_ack.json', kind='capture_stopped', ack_basis='synthetic_fixture')
        if args.mode == 'finalization-hang':
            while True:
                time.sleep(.1)
        time.sleep(args.delay)
        if args.mode != 'missing-report':
            data = b'version https://git-lfs.github.com/spec/v1\noid sha256:fake\nsize 123\n' if args.mode == 'lfs-report' else b'FAKE CPU REPORT\x00no CUDA evidence\n'
            (args.directory / 'report.bin').write_bytes(data)
    elif args.stage == 'stop':
        write('stop.request', kind='stop_requested')
        if args.mode == 'stop-helper-hold':
            while not (args.directory / 'allow-stop-exit').exists():
                time.sleep(.005)
    elif args.stage == 'export':
        time.sleep(args.delay)
        if args.mode == 'export-invalid':
            (args.directory / 'export.json').write_text('{broken')
        else:
            digest = hashlib.sha256((args.directory / 'report.bin').read_bytes()).hexdigest()
            write('export.json', kind='exported_report', report_sha256='wrong' if args.mode == 'export-wrong-hash' else digest)
    else:
        time.sleep(args.delay)
        kernels = [] if args.mode == 'empty-summary' else [dict(name='fixture_gemm', count=3, total_ns=100)]
        values = dict(schema='kernel_summary_v1', device_uuid=plan['plan']['device_uuid'],
            worker_pids=plan['plan']['worker_pids'], coverage='fixture_verified',
            units={'kernel_duration': 'ns'}, kernels=kernels,
            export_sha256=hashlib.sha256((args.directory / 'export.json').read_bytes()).hexdigest())
        if args.mode == 'wrong-summary-hash':
            values['export_sha256'] = 'wrong'
        if args.mode == 'wrong-device':
            values['device_uuid'] = 'GPU-other'
        if args.mode == 'wrong-workers':
            values['worker_pids'] = []
        if args.mode == 'unknown-coverage':
            values['coverage'] = 'unknown'
        if args.mode == 'truth-summary':
            values['expected_label'] = 'compute_bound'
        if args.mode == 'wrong-units':
            values['units'] = {'kernel_duration': 'ms'}
        if args.mode == 'wrong-summary-id':
            base['capture_id'] = 'different-capture'
        write('summary.json', **values)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
