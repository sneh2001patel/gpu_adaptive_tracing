#!/usr/bin/env python3
"""One owned L4 reset/barrier/capture feasibility pilot; not the study matrix."""
import argparse,asyncio,json
from pathlib import Path
from experiments.feasibility.activity import OwnedLiveActivity
from experiments.feasibility.harness import run
from experiments.tracing.timing import MonotonicClock


async def main(args):
    args.output=args.output.resolve()
    config=json.loads(args.config.read_text());config['device_uuid']=args.device_uuid;config['stage_timeout_s']=60
    clock=MonotonicClock();adapter=OwnedLiveActivity(config,clock,args.endpoint,args.model_path)
    result=await run(adapter,config,args.output,provenance='live_online',clock_domain=clock.domain)
    print(json.dumps(dict(live_feasibility_passed=result['live_feasibility_passed'],study_ready=False,gates=result['gates']),indent=2),flush=True)
    return int(not result['live_feasibility_passed'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path('experiments/configs/l4_feasibility_v1.json'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--model-path',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012')
    raise SystemExit(asyncio.run(main(p.parse_args())))
