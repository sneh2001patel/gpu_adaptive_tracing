#!/usr/bin/env python3
"""Read-only metric endpoint snapshots for later server/GPU feasibility review.

Records parent request/receipt times, raw bytes, status and declared TYPE lines.
Does not map source clocks, compute interval features, or validate diagnoses.
"""
import argparse,asyncio,hashlib,json,math,re
from pathlib import Path
from revision.tracing.feature_collection import http_body
from revision.tracing.timing import MonotonicClock
from revision.tracing.measured_evidence import integer
from revision.scripts.play_arrivals import write_sources


async def snapshot(endpoint,output,*,samples=3,interval_s=1,timeout_s=2):
    integer(samples,'samples',1)
    if samples>100:raise ValueError('At most 100 probe snapshots')
    if isinstance(interval_s,bool) or not math.isfinite(interval_s) or interval_s<0:raise ValueError('Nonnegative probe interval required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);write_sources(output)
    clock=MonotonicClock();rows=[]
    for index in range(samples):
        requested=clock.now_ns();status=None;raw=None;error=None;types=[]
        try:
            status,raw=await http_body(endpoint,timeout_s=timeout_s)
            if status!=200:error='metrics_http_status_'+str(status)
            for line in raw.decode('utf-8').splitlines():
                match=re.fullmatch(r'# TYPE ([a-zA-Z_:][a-zA-Z0-9_:]*) (counter|gauge|histogram|summary|untyped)',line.strip())
                if match:types.append(dict(name=match[1],declared_type=match[2]))
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        received=clock.now_ns();path=None;digest=None
        if raw is not None:
            path=f'metrics-{index:03d}.txt';(output/path).write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
        rows.append(dict(requested_at_ns=requested,received_at_ns=received,http_status=status,
            error=error,path=path,sha256=digest,declared_type_lines=types))
        if index+1<samples:await asyncio.sleep(interval_s)
    result=dict(version='passive_server_metric_snapshot_v1',endpoint=endpoint,clock_domain=clock.domain,
        gpu_validation=False,server_clock_mapping=False,interval_features_validated=False,
        snapshots=rows,note='TYPE declarations are inventory hints only; raw histogram/generation/cohort/phase semantics need validation on the pinned server.')
    (output/'SERVER_METRICS.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--endpoint',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--samples',type=int,default=3);p.add_argument('--interval-s',type=float,default=1);p.add_argument('--timeout-s',type=float,default=2)
    a=p.parse_args();r=asyncio.run(snapshot(a.endpoint,a.output,samples=a.samples,interval_s=a.interval_s,timeout_s=a.timeout_s))
    print(json.dumps(dict(saved=len(r['snapshots']),errors=sum(s['error'] is not None for s in r['snapshots']),interval_features_validated=False)))
    raise SystemExit(int(any(s['error'] is not None for s in r['snapshots'])))
