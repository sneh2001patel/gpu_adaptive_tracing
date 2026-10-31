#!/usr/bin/env python3
"""Prepare a separate development-informed packet; never launch GPU work."""
import argparse,json
from pathlib import Path
from revision.feasibility.challenge_protocol_v2 import materialize,load_prepared

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    base=Path('revision/hardware/l4_20261028')
    plan=materialize(args.output,parent=Path('revision/examples/event_challenges/prepared_001'),failed_run=base/'challenges_001',
        audit=base/'CHALLENGES_VALIDATION.json',analysis=base/'CHALLENGES_FAILURE_ANALYSIS.json')
    load_prepared(args.output)
    print(json.dumps(dict(version=plan['version'],rates=plan['rates_rps'],schedules=len(plan['schedules']),
        max_total_requests=plan['budgets']['max_total_requests_including_warmups'],GPU_used=False,launch_supported=False)))
