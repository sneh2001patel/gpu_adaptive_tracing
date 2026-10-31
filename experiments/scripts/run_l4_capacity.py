#!/usr/bin/env python3
"""Two owned serving sessions, six bounded probes, no profiler or main study."""
import argparse,asyncio,hashlib,json,uuid
from pathlib import Path
from experiments.feasibility.activity import OwnedLiveActivity
from experiments.feasibility.capacity import pin_corpus,probe_cell,materialize_pairs,ProbeConfig
from experiments.feasibility.harness import check
from experiments.scripts.play_arrivals import write_sources
from experiments.scripts.run_l4_discovery import save
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.feature_collection import http_body,response_usage
from experiments.tracing.timing import MonotonicClock


async def pilot(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);write_sources(output)
    config=json.loads(Path('experiments/configs/l4_feasibility_v1.json').read_text());config['device_uuid']=args.device_uuid
    clock=MonotonicClock();adapter=OwnedLiveActivity(config,clock,args.endpoint,args.model_path)
    probe=ProbeConfig();save(output/'probe_configuration.json',dict(duration_s=probe.duration_s,concurrency=probe.concurrency,
        max_requests=probe.max_requests,request_timeout_s=probe.request_timeout_s,drain_s=probe.drain_s,sample_interval_s=probe.sample_interval_s))
    save(output/'serving_configuration.json',config)
    errors=[];cells=[];pairs=None;warmups=[]
    async def work():
        nonlocal pairs
        from transformers import AutoTokenizer
        tokenizer=AutoTokenizer.from_pretrained(str(args.model_path),local_files_only=True)
        pinned=pin_corpus(tokenizer);save(output/'corpus.json',pinned)
        tokenizer_files={}
        for name in ('tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','config.json'):
            path=args.model_path/name
            if path.is_file():tokenizer_files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        save(output/'tokenizer_files.json',tokenizer_files)
        for generation,row in enumerate(pinned['prompts']):
            if adapter.current is not None:await adapter.stop(adapter.current)
            session=await adapter.start(output,generation,reset_token=uuid.uuid4().hex,profile=False)
            inventory=await adapter.discovery().inventory(output,{})
            check('inventory',inventory,config,{},output,'live_online',clock.domain)
            save(output/f'inventory-{generation}.json',inventory)
            await adapter.quiet(output,f'before-{row["band"]}')
            worker=session['worker'];scope=ServingBinding(session['nonce'],generation,worker['pid'],worker['device_uuid'],config['model'],config['engine'],clock.domain)
            # One declared warmup per fresh server; raw actual usage is retained.
            requested=clock.now_ns();status,raw=await http_body(args.endpoint+'/v1/completions',method='POST',payload=dict(model=config['model'],
                prompt=row['prompt'],max_tokens=32,stream=False,temperature=0,ignore_eos=True),timeout_s=15)
            path=output/f'warmup-{generation}.json';path.write_bytes(raw);prompt,completed,error=response_usage(raw)
            warmups.append(dict(generation=generation,requested_at_ns=requested,received_at_ns=clock.now_ns(),http_status=status,
                response_path=path.name,response_sha256=hashlib.sha256(raw).hexdigest(),prompt_tokens=prompt,output_tokens=completed,
                tokenizer_prompt_tokens=row['tokenizer_prompt_tokens'],usage_error=error))
            save(output/'warmups.json',warmups)
            if status!=200 or error or completed!=32 or prompt!=row['tokenizer_prompt_tokens']:raise RuntimeError('Warmup/tokenizer usage mismatch')
            await adapter.quiet(output,f'after-warmup-{row["band"]}')
            for concurrency in probe.concurrency:
                result=await probe_cell(clock,args.endpoint,scope,row['prompt'],output/f'{row["band"]}-c{concurrency}',probe,concurrency,provenance='live_online',expected_prompt_tokens=row['tokenizer_prompt_tokens'])
                cells.append(result|dict(band=row['band'],generation=generation,worker_pid=worker['pid']));save(output/'cells.json',cells)
                await adapter.quiet(output,f'after-{row["band"]}-c{concurrency}')
                print(json.dumps(dict(event='probe_cell_complete',band=row['band'],concurrency=concurrency,
                    successful_in_horizon=result['successful_in_horizon'],issued=result['issued'],request_errors=result['request_errors'])),flush=True)
        pairs=materialize_pairs(pinned,cells,config['model'],output/'paired_schedules')
    try:await asyncio.wait_for(work(),420)
    except asyncio.CancelledError:
        errors.append('pilot_cancelled');raise
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    finally:
        try:await asyncio.wait_for(adapter.cleanup(output,{}),45)
        except Exception as exc:errors.append('cleanup: '+type(exc).__name__+': '+str(exc))
        passed=not errors and len(cells)==6 and pairs is not None
        save(output/'RESULT.json',dict(version='bounded_capacity_corpus_probe_v1',pilot_passed=passed,errors=errors,
            cells_completed=len(cells),capture_count=0,calibration_enabled=False,study_ready=False,protocol_frozen=False,
            saturation_capacity_established=False,note='Finite closed-loop throughput probes, not a calibrated maximum-capacity or diagnostic experiment.'))
        files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
        save(output/'artifact_manifest.json',dict(files=files))
    print(json.dumps(dict(pilot_passed=passed,cells_completed=len(cells),errors=errors)),flush=True)
    return int(not passed)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-path',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012');args=p.parse_args()
    raise SystemExit(asyncio.run(pilot(args)))
