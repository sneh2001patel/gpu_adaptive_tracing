#!/usr/bin/env python3
"""Commission one owned event scheduler; eight total requests, zero captures."""
import argparse,asyncio,hashlib,json,uuid
from importlib.metadata import distribution,version
from pathlib import Path
from experiments.feasibility.activity import OwnedLiveActivity
from experiments.feasibility.event_commission import validate_join
from experiments.feasibility.harness import check
from experiments.scripts.play_arrivals import write_sources
from experiments.scripts.run_l4_discovery import save,ROOT
from experiments.tracing.feature_collection import http_body
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.server_events import collect_snapshot,validate_snapshot,scheduler_wait_bounds
from experiments.tracing.timing import MonotonicClock


async def pilot(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);write_sources(output)
    config=json.loads((ROOT/'experiments/configs/l4_feasibility_v1.json').read_text());config['device_uuid']=args.device_uuid
    clock=MonotonicClock();adapter=OwnedLiveActivity(config,clock,args.endpoint,args.model_path)
    errors=[];rows=[];joined=[];cleanup=None
    save(output/'serving_configuration.json',config)
    async def work():
        nonlocal joined
        # Exact installed ID/CLI sources must match the read-only reviewed copy.
        pins=json.loads((ROOT/'experiments/protocol/sources/vllm_0_10_2/event_ids/SOURCE_MANIFEST.json').read_text())
        if version('vllm')!='0.10.2':raise ValueError('Unreviewed vLLM version')
        dist=distribution('vllm')
        for name,expected in pins['files'].items():
            if hashlib.sha256(Path(dist.locate_file(name)).read_bytes()).hexdigest()!=expected:
                raise ValueError('Installed ID/CLI source mismatch: '+name)
        save(output/'installed_source_pins.json',pins)
        spec_path=ROOT/'experiments/examples/server_events/prospective_001/SPECIFICATION.json'
        corpus_path=ROOT/'experiments/hardware/l4_20261028/capacity_001/corpus.json'
        save(output/'input_hashes.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (spec_path,corpus_path)})
        corpus=json.loads(corpus_path.read_text());save(output/'corpus.json',corpus)
        save(output/'prospective_specification.json',json.loads(spec_path.read_text()))
        # Every attempt is charged in the saved plan before sending; no retries,
        # warmups or inference-based probes are added outside these eight.
        plans=[]
        for index in range(8):
            prompt=corpus['prompts'][index%2]
            plans.append(dict(index=index,expected_prompt_tokens=prompt['tokenizer_prompt_tokens'],payload=dict(
                model=config['model'],request_id='events028-'+uuid.uuid4().hex,prompt=prompt['prompt'],
                n=1,max_tokens=32,stream=False,temperature=0,ignore_eos=True)))
        save(output/'request_plan.json',dict(max_total_attempts=8,extra_warmups=0,extra_inference_probe_triggers=0,
            concurrency=1,requests=plans,scope='commissioning_only_no_challenging_case_or_p95_claim'))
        session=await adapter.start(output,0,reset_token=uuid.uuid4().hex,event_instrumentation=True)
        inventory=await adapter.discovery().inventory(output,{})
        check('inventory',inventory,config,{},output,'live_online',clock.domain);save(output/'inventory.json',inventory)
        worker=session['worker'];binding=ServingBinding(session['nonce'],0,worker['pid'],worker['device_uuid'],config['model'],config['engine'],clock.domain)
        directory=session['directory']/'scheduler-events';startup=json.loads((directory/'startup.json').read_text())
        from dataclasses import asdict
        if startup['binding']!=asdict(binding) or startup['effective_config']!=dict(enable_prefix_caching=False,max_num_seqs=16,async_scheduling=False):
            raise ValueError('Effective scheduler/cache configuration or worker binding mismatch')
        async def trigger():
            status,_=await http_body(args.endpoint+'/experiments/events/probe',method='POST',payload={},timeout_s=10)
            if status!=200:raise RuntimeError('Fixed idle event RPC failed')
        await adapter.quiet(output,'before')
        initial=await collect_snapshot(clock,binding,directory,trigger,timeout_s=10);save(output/'initial_probe.json',initial)
        if validate_snapshot(initial['data'],initial['command'],binding,initial['received_at_ns']):
            raise ValueError('Fresh scheduler contains unexpected requests')
        for plan in plans:
            row=plan|dict(requested_at_ns=clock.now_ns(),http_status=None,response=None)
            rows.append(row);save(output/'requests.json',rows)
            status,raw=await http_body(args.endpoint+'/v1/completions',method='POST',payload=plan['payload'],timeout_s=20)
            row.update(received_at_ns=clock.now_ns(),http_status=status,raw_sha256=hashlib.sha256(raw).hexdigest())
            path=output/f'response-{plan["index"]}.json';path.write_bytes(raw)
            row['response_path']=path.name;row['response']=json.loads(raw);save(output/'requests.json',rows)
            if status!=200:raise RuntimeError('Commissioning completion failed; no retry')
            print(json.dumps(dict(event='completion_received',index=plan['index'],http_status=status)),flush=True)
        await adapter.quiet(output,'after')
        final=await collect_snapshot(clock,binding,directory,trigger,timeout_s=10);save(output/'final_probe.json',final)
        joined=validate_join(rows,final,binding);save(output/'joined_requests.json',joined)
        bounds=scheduler_wait_bounds(final['data'],final['command'],binding,received_at_ns=final['received_at_ns'],
            start_ns=initial['data']['source_probe_ns'],end_ns=final['data']['source_probe_ns'])
        save(output/'scheduler_delay_bounds.json',bounds)
    try:await asyncio.wait_for(work(),240)
    except asyncio.CancelledError:
        errors.append('commission_cancelled');raise
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    finally:
        try:cleanup=await asyncio.wait_for(adapter.cleanup(output,{}),45)
        except Exception as exc:errors.append('cleanup: '+type(exc).__name__+': '+str(exc))
        passed=not errors and len(joined)==8 and cleanup is not None and cleanup['confirmed_absent']
        save(output/'RESULT.json',dict(version='scheduler_events_commission_v1',commission_passed=passed,errors=errors,
            total_request_attempts=len(rows),joined_requests=len(joined),capture_count=0,cleanup=cleanup,
            calibration_enabled=False,study_ready=False,protocol_frozen=False,references_created=0,
            runtime_wait_metric_enabled=False,GPU_phase_mapping_enabled=False,challenge_cases_executed=0))
        save(output/'artifact_manifest.json',dict(files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(commission_passed=passed,errors=errors)),flush=True)
    return int(not passed)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-path',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012');args=p.parse_args()
    raise SystemExit(asyncio.run(pilot(args)))
