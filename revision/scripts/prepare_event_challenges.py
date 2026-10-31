#!/usr/bin/env python3
"""Materialize prospective event challenges without SSH, GPU imports or launch."""
import argparse,json
from pathlib import Path
from revision.feasibility.challenge_protocol import materialize,load_prepared


def main(args):
    base=Path('revision/hardware/l4_20261028')
    plan=materialize(args.output,corpus_raw=(base/'capacity_001/corpus.json').read_bytes(),
        spec_raw=Path('revision/examples/server_events/prospective_001/SPECIFICATION.json').read_bytes(),
        commission_raw=(base/'events_001/RESULT.json').read_bytes(),validation_raw=(base/'EVENTS_VALIDATION.json').read_bytes())
    load_prepared(args.output)
    print(json.dumps(dict(status=plan['status'],schedules=len(plan['schedules']),planned_jobs=len(plan['jobs']),
        worst_case_total_requests=plan['budgets']['max_total_requests_including_warmups'],GPU_used=False,launch_supported=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
