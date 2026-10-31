#!/usr/bin/env python3
"""Run at most sixteen owned engineering jobs from an exact frozen snapshot."""
import argparse,asyncio,json
from pathlib import Path
from revision.feasibility.challenge_freeze import validate_freeze,validate_installed
from revision.feasibility.challenge_runner import OwnedChallengeTarget,run_campaign
from revision.scripts.run_l4_discovery import ROOT
from revision.tracing.timing import MonotonicClock


async def main(args):
    record=validate_freeze(ROOT,args.packet,args.freeze);validate_installed(record)
    config=json.loads((ROOT/'revision/configs/l4_feasibility_v1.json').read_text());config['device_uuid']=args.device_uuid
    clock=MonotonicClock();target=OwnedChallengeTarget(config,clock,args.endpoint,args.model_path)
    return int(not await run_campaign(target,clock,args.packet,args.output))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,default=Path('revision/examples/event_challenges/prepared_001'))
    p.add_argument('--freeze',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-path',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012');args=p.parse_args()
    raise SystemExit(asyncio.run(main(args)))
