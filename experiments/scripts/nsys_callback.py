#!/usr/bin/env python3
"""Nsight 2026.3 callback receipt; no credentials or arbitrary environment dump."""
import json
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    directory = Path(sys.argv[1])
    action = sys.argv[2]
    session = json.loads((directory / 'session.json').read_text())
    record = dict(source='nsys_callback', action=action, timestamp_ns=time.monotonic_ns(),
                  clock_domain=session['clock_domain'], session_name=os.environ.get('NSYS_SESSION_NAME'),
                  callback_name=os.environ.get('NSYS_CALLBACK_NAME'))
    if action == 'report_ready':
        record['report_path'] = os.environ.get('NSYS_REPORT_PATH')
    else:
        control = directory / 'control.json'
        if control.exists():
            record.update(json.loads(control.read_text()))
    path = directory / f'callback-{action}-{uuid.uuid4().hex}.json'
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(record) + '\n')
    temporary.replace(path)


if __name__ == '__main__':
    main()
