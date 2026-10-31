#!/usr/bin/env python3
"""Four owned paired jobs; two full-range traces; no classifier/reference locks."""
import argparse,asyncio,hashlib,json,shutil,uuid
from pathlib import Path
from experiments.feasibility.activity import OwnedLiveActivity
from experiments.feasibility.paired_collection import load_pairs,collect_job,validate_playback,adjudication_packet
from experiments.feasibility.harness import check
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.nsys_backend import NsightServingBackend
from experiments.tracing.feature_collection import http_body,response_usage
from experiments.tracing.timing import MonotonicClock
from experiments.scripts.run_l4_discovery import save
from experiments.scripts.play_arrivals import write_sources


async def pilot(args):
    manifest,planned=load_pairs(args.pairs)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);write_sources(output)
    save(output/'input_pairs.json',manifest)
    config=json.loads(Path('experiments/configs/l4_feasibility_v1.json').read_text());config['device_uuid']=args.device_uuid
    save(output/'configuration.json',config)
    clock=MonotonicClock();adapter=OwnedLiveActivity(config,clock,args.endpoint,args.model_path)
    jobs=[];errors=[];trace_attempts=0
    async def work():
        nonlocal trace_attempts
        for generation,(job,schedule) in enumerate(planned):
            identity=f'job-{generation}';directory=output/identity;directory.mkdir();write_sources(directory)
            raw=(args.pairs/job['schedule_path']).read_bytes();(directory/'offered.json').write_bytes(raw)
            if hashlib.sha256(raw).hexdigest()!=schedule.file_sha256:raise ValueError('Offered bytes changed after validation')
            session=await adapter.start(directory,generation,reset_token=uuid.uuid4().hex,profile=job['role']=='matched_full_trace')
            inventory=await adapter.discovery().inventory(directory,{})
            check('inventory',inventory,config,{},directory,'live_online',clock.domain);save(directory/'inventory.json',inventory)
            await adapter.quiet(output,'before-'+identity)
            # Identical declared warmup per pair role, outside the captured range.
            status,warmup=await http_body(args.endpoint+'/v1/completions',method='POST',payload=schedule.requests[0].payload,timeout_s=15)
            (directory/'warmup.json').write_bytes(warmup)
            p,t,error=response_usage(warmup)
            if status!=200 or error or t!=32:raise ValueError('Warmup failed')
            await adapter.quiet(output,'after-warmup-'+identity)
            worker=session['worker'];scope=ServingBinding(session['nonce'],generation,worker['pid'],worker['device_uuid'],config['model'],config['engine'],clock.domain)
            backend=None;capture_id='trace-'+identity
            if job['role']=='matched_full_trace':
                trace_attempts+=1
                if trace_attempts>2:raise RuntimeError('Trace attempt budget exceeded')
                backend=NsightServingBackend(adapter.recorder,session['directory'],session['prefix'],[worker['pid']],config['device_uuid'],args.endpoint,session['process'],timeout_s=30)
                adapter.backend=backend;backend.start(capture_id);await adapter.wait_capture(capture_id,'capturing')
            playback=await collect_job(clock,args.endpoint,scope,schedule,directory/'collection',provenance='live_online')
            validate_playback(playback)
            trace=None
            if backend is not None:
                backend.stop(capture_id);await adapter.wait_capture(capture_id,'ready');ready=backend.evidence(capture_id)
                attempt=backend.attempts[capture_id];shutil.copyfile(attempt['database'],directory/'trace.sqlite')
                trace=dict(start_ack_ns=attempt['start_ack'][0]['returned_at_ns'],start_callback_ns=attempt['start_callback']['timestamp_ns'],
                    stop_ack_ns=attempt['stop_ack'][0]['returned_at_ns'],parsed_ready_ns=ready.ready_at_ns,
                    playback_start_ns=playback['start_ns'],playback_finished_ns=playback['finished_at_ns'],
                    expected_worker_pid=worker['pid'],device_uuid=worker['device_uuid'],kernel_evidence=ready.payload,capture_active_s=None)
                if max(trace['start_ack_ns'],trace['start_callback_ns'])>playback['start_ns'] or trace['stop_ack_ns']<playback['finished_at_ns']:
                    raise ValueError('Trace control did not bracket full playback/drain')
                save(directory/'trace_receipt.json',trace)
                await backend.aclose();save(directory/'backend.json',backend.snapshot());adapter.backend=None
            await adapter.quiet(output,'after-'+identity)
            await adapter.stop(session)
            record=dict(job_id=identity,directory=identity,pair_id=job['pair_id'],role=job['role'],order_in_pair=job['order_in_pair'],
                schedule_sha256=schedule.file_sha256,worker_pid=worker['pid'],generation=generation,session_nonce=session['nonce'],
                offered=playback['offered'],completed=playback['counts']['completed'],
                request_latency_ms=[(r['terminal']['completion']['end_ns']-r['terminal']['completion']['start_ns'])/1e6 for r in playback['ledger']],
                has_trace=trace is not None,correlation_limit='separate_execution_not_same_request_GPU_event_correlation')
            jobs.append(record);save(output/'jobs.json',jobs)
            print(json.dumps(dict(event='paired_job_complete',job_id=identity,role=job['role'],completed=record['completed'],has_trace=trace is not None)),flush=True)
        packet=adjudication_packet(output,jobs)
        packet['matched_run_differences']=[dict(pair_id=pair,
            runs=[dict(job_id=j['job_id'],role=j['role'],latencies_ms=j['request_latency_ms'],completed=j['completed']) for j in jobs if j['pair_id']==pair],
            status='requires_assessor_mismatch_assessment_no_automatic_equivalence') for pair in ('short','long')]
        save(output/'ADJUDICATION_PACKET.json',packet)
    try:await asyncio.wait_for(work(),480)
    except asyncio.CancelledError:errors.append('pilot_cancelled');raise
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    finally:
        try:save(output/'cleanup_receipt.json',await asyncio.wait_for(adapter.cleanup(output,{}),45))
        except Exception as exc:errors.append('cleanup: '+str(exc))
        (output/'timing_events.jsonl').write_text(adapter.recorder.jsonl())
        passed=not errors and len(jobs)==4 and trace_attempts==2
        save(output/'RESULT.json',dict(version='owned_live_pair_pilot_v1',pilot_passed=passed,errors=errors,jobs_completed=len(jobs),
            trace_attempts=trace_attempts,references_created=0,references_locked=0,classifier_run=False,
            study_ready=False,calibration_enabled=False,protocol_frozen=False,capture_active_s=None))
        save(output/'artifact_manifest.json',dict(files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(pilot_passed=passed,jobs_completed=len(jobs),errors=errors)),flush=True);return int(not passed)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--pairs',type=Path,required=True)
    p.add_argument('--model-path',type=Path,required=True);p.add_argument('--device-uuid',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012');args=p.parse_args();raise SystemExit(asyncio.run(pilot(args)))
