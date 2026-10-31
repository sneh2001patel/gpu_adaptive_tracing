#!/usr/bin/env python3
"""Freeze the engineering source/packet after CPU checks; no GPU launch."""
import argparse,json
from pathlib import Path
from experiments.feasibility.challenge_freeze import freeze,validate_freeze
from experiments.scripts.run_l4_discovery import ROOT
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,default=Path('experiments/examples/event_challenges/prepared_001'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--test-log',type=Path,required=True);args=p.parse_args()
    record=freeze(ROOT,args.packet,args.output,args.test_log);validate_freeze(ROOT,args.packet,args.output/'FREEZE.json')
    print(json.dumps(dict(snapshot_created=True,source_files=len(record['files']),cpu_tests=record['cpu_tests_passed'],GPU_used=False,protocol_frozen=False)))
