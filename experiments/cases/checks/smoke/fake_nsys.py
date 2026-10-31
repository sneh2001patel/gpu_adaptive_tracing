"""Fake `nsys` for smoke tests: launch/start/stop/export/shutdown with a tiny exported SQLite trace.

State (launched pid, pending output per session) lives in $FAKE_NSYS_STATE. The exported trace has two kernels
(one GEMM, one attention) inside a 1 s capture window, in the Nsight 2026.3 layout (relative activity times,
absolute ANALYSIS_DETAILS).
"""
import json
import os
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ['FAKE_NSYS_STATE'])


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(d):
    STATE.write_text(json.dumps(d))


def export(db):
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE StringIds(id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE PROCESSES(globalPid INTEGER, pid INTEGER);
        CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL(start INTEGER, end INTEGER, demangledName INTEGER, shortName INTEGER,
                                                globalPid INTEGER, deviceId INTEGER);
        CREATE TABLE ANALYSIS_DETAILS(startTime INTEGER, stopTime INTEGER);
        INSERT INTO StringIds VALUES (1, 'void cutlass::Kernel2<cutlass_80_gemm>(Params)'), (2, 'Kernel2'),
                                     (3, 'void flash_fwd_kernel<true>(Params)'), (4, 'flash_fwd_kernel');
        INSERT INTO PROCESSES VALUES (100, 4242);
        INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (100000000, 500000000, 1, 2, 100, 0),
                                                      (600000000, 700000000, 3, 4, 100, 0);
        INSERT INTO ANALYSIS_DETAILS VALUES (222961076860952, 222962076860952);
    """)
    con.commit()
    con.close()


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    opts = {a.split('=', 1)[0]: (a.split('=', 1) + [''])[1] for a in args if a.startswith('--')}
    if cmd == 'launch':
        target = args[next(i for i, a in enumerate(args) if not a.startswith('--')):]  # nsys options precede the command
        proc = subprocess.Popen(target)
        save(dict(state(), pid=proc.pid))
        sys.exit(proc.wait())
    if cmd == 'start':
        save(dict(state(), output=opts['--output']))
    elif cmd == 'stop':
        Path(state()['output'] + '.nsys-rep').write_bytes(b'x' * 200)
    elif cmd == 'export':
        export(opts['--output'])
    elif cmd == 'shutdown':
        pid = state().get('pid')
        if pid:
            os.kill(pid, signal.SIGTERM)


if __name__ == '__main__':
    main()
