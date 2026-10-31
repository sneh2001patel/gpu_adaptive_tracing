#!/usr/bin/env python3
"""Run read-only pinned-stack discovery; unavailable activity gates stay closed."""
import argparse,asyncio,json
from pathlib import Path
from revision.feasibility.discovery import ReadOnlyDiscovery
from revision.feasibility.harness import run
from revision.tracing.timing import MonotonicClock


async def main(args):
    config=json.loads(args.config.read_text());config['device_uuid']=args.device_uuid
    clock=MonotonicClock()
    adapter=ReadOnlyDiscovery(config,clock,args.endpoint,args.model_path,args.session_directory)
    result=await run(adapter,config,args.output,provenance='live_online',clock_domain=clock.domain)
    print(json.dumps(dict(discovery_passed=result['discovery_passed'],live_feasibility_passed=result['live_feasibility_passed'],
        study_ready=False,gates=result['gates']),indent=2))
    return int(not result['discovery_passed'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('revision/configs/l4_feasibility_v1.json'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',required=True);p.add_argument('--model-path',type=Path,required=True)
    p.add_argument('--session-directory',type=Path,required=True)
    raise SystemExit(asyncio.run(main(p.parse_args())))
