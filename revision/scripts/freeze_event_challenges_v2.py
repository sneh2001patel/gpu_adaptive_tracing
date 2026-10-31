#!/usr/bin/env python3
"""Create a new engineering snapshot for v2, preserving the v1 snapshot."""
import argparse,json
from pathlib import Path
from revision.feasibility.challenge_freeze import freeze,validate_freeze
from revision.feasibility.challenge_protocol_v2 import load_prepared
from revision.scripts.run_l4_discovery import ROOT

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,default=Path('revision/examples/event_challenges_v2/prepared_001'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--test-log',type=Path,required=True);args=p.parse_args()
    record=freeze(ROOT,args.packet,args.output,args.test_log,loader=load_prepared,archive_name='source_step032.tar.gz',
        extra_documents=('revision/protocol/EVENT_CHALLENGE_PROTOCOL_V2.md',
            'revision/examples/event_challenges_v2/validation/cpu_suite_initial_failed.log',
            'revision/examples/event_challenges_v2/validation/timing_diagnostic.log'))
    validate_freeze(ROOT,args.packet,args.output/'FREEZE.json',loader=load_prepared)
    print(json.dumps(dict(snapshot_created=True,protocol_version=record['challenge_protocol_version'],source_files=len(record['files']),
        cpu_tests=record['cpu_tests_passed'],max_requests=record['supplement']['max_total_requests'],GPU_used=False,protocol_frozen=False)))
