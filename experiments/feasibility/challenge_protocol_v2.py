"""Development-informed v2 packet; original artifacts and v1 semantics are retained."""
import copy,hashlib,json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from experiments.feasibility.challenge_protocol import (NS,job_design,wire_payload,
    load_prepared as load_v1,make_schedule as make_v1,select_pressure_profile)
from experiments.tracing.arrival_schedule import ArrivalSchedule,canonical

VERSION='event_challenge_preparation_v2'
RATES=(.5,1,2,3,4)
PARENT_MANIFEST_SHA256='e7b6bac5ec791f7ba3892be6031421fa6f5d1f857ad1382164f8142a4fafd8aa'
INPUTS=('legacy_plan_input','legacy_manifest_input','corpus_input','development_result_input',
    'development_manifest_input','development_playback_input','development_validation_input','development_analysis_input')
CASES=('rate_ladder','pressure_then_removal','lull_then_recurrence','unresolved_source_gap_control')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def phases(case,rate=None):
    if case=='rate_ladder':
        if rate is not None:raise ValueError('Ladder has a fixed grid')
        return [(f'level-{i}',8*i,8*(i+1),r) for i,r in enumerate(RATES)]+[('removal',40,60,0)]
    if type(rate) not in (int,float) or rate not in RATES:raise ValueError('Exact v2 rate required')
    if case in ('pressure_then_removal','unresolved_source_gap_control'):
        return [('baseline',0,10,.5),('pressure',10,40,rate),('removal',40,60,0)]
    if case=='lull_then_recurrence':
        return [('baseline',0,10,.5),('pressure',10,25,rate),('lull',25,30,0),('recurrence',30,50,rate),('removal',50,60,0)]
    raise ValueError('Unknown case')


def make_schedule(case,prompt,model,rate=None):
    rows=[]
    for _,start,end,rps in phases(case,rate):
        if not rps:continue
        rational=Fraction(str(rps));num,den=rational.numerator,rational.denominator
        count=((end-start)*num+den-1)//den
        for i in range(count):
            # Derive each rational offset independently. Repeated rounded periods
            # would create an extra request just before an integer phase edge.
            offset=start*NS+(i*NS*den)//num
            rows.append(dict(request_id=f'v2-{case}-r{rate if rate is not None else "ladder"}-{len(rows):04d}',
                offset_ns=offset,payload=dict(model=model,prompt=prompt,max_tokens=32,stream=False,temperature=0,ignore_eos=True)))
    if len(rows)+1>512:raise ValueError('Warmup-inclusive session budget exceeded')
    return ArrivalSchedule.from_bytes(canonical(dict(version='offered_arrivals_v1',duration_ns=60*NS,requests=rows)))


def select_pressure(receipts,binding,*,case_start_ns,request_rows,schedule,job):
    if not schedule.requests:raise ValueError('Nonempty v2 ladder required')
    expected=make_schedule('rate_ladder',schedule.requests[0].payload['prompt'],schedule.requests[0].payload['model'])
    return select_pressure_profile(receipts,binding,case_start_ns=case_start_ns,request_rows=request_rows,
        schedule=schedule,job=job,expected=expected,rates=RATES)


def compile_inputs(raws):
    if set(raws)!=set(INPUTS):raise ValueError('Exact parent/development inputs required')
    d={k:json.loads(v) for k,v in raws.items()}
    if sha(raws['legacy_manifest_input'])!=PARENT_MANIFEST_SHA256:raise ValueError('Wrong parent packet')
    legacy_manifest=d['legacy_manifest_input']['files']
    for name,key in (('PLAN.json','legacy_plan_input'),('corpus_input.json','corpus_input')):
        if sha(raws[key])!=legacy_manifest[name]:raise ValueError('Parent input hash mismatch')
    parent=d['legacy_plan_input'];result=d['development_result_input'];playback=d['development_playback_input']
    audit=d['development_validation_input'];analysis=d['development_analysis_input']
    old_manifest=d['development_manifest_input']['files']
    for name,key in (('RESULT.json','development_result_input'),('rate_ladder-b0-off/playback.json','development_playback_input')):
        if sha(raws[key])!=old_manifest[name]:raise ValueError('Failed-run input hash mismatch')
    if result['status']!='failed' or result['completed_jobs']!=0 or result['selection'] is not None:
        raise ValueError('The development attempt must remain failed and unselected')
    if not audit['audit_passed'] or audit['campaign_status']!='failed' or analysis['eligibility_repaired'] or analysis['selected_rate_rps'] is not None:
        raise ValueError('Development evidence cannot be relabeled eligible')
    corpus=d['corpus_input'];long=[p for p in corpus['prompts'] if p['band']=='long']
    if len(long)!=1 or long[0]['tokenizer_prompt_tokens']!=1072 or sha(long[0]['prompt'].encode())!=long[0]['prompt_utf8_sha256']:
        raise ValueError('Pinned long corpus required')
    prompt=long[0]['prompt'];model='Qwen/Qwen2.5-7B-Instruct'
    old=make_v1('rate_ladder',prompt,model)
    if playback['schedule_file_sha256']!=old.file_sha256:raise ValueError('Unexpected old offered schedule')
    ledger=playback['ledger'];by_id={r['request_id']:r for r in ledger}
    if len(by_id)!=124 or set(by_id)!={r.request_id for r in old.requests}:raise ValueError('Old offer denominator changed')
    if Counter(r['state'] for r in ledger)!=Counter(completed=90,skipped_capacity=34):raise ValueError('Old work/skip outcomes changed')
    if any(by_id[r.request_id]['offset_ns']!=r.offset_ns for r in old.requests):raise ValueError('Old offered offsets changed')
    if any(r['offset_ns']<32*NS for r in ledger if r['state']=='skipped_capacity'):raise ValueError('Unexpected failure phase')
    entries=[];files={}
    for case in CASES:
        for rate in ((None,) if case=='rate_ladder' else RATES):
            key=case if rate is None else case+'-'+str(rate)
            schedule=make_schedule(case,prompt,model,rate);raw=canonical(schedule.as_dict())
            boundaries=sorted({10,20,30,40,50,60}|{p[2] for p in phases(case,rate)})
            files[key+'.json']=raw
            entries.append(dict(schedule_id=key,path=key+'.json',file_sha256=sha(raw),
                wire_content_sha256=sha(canonical([dict(offset_ns=r.offset_ns,payload=wire_payload(r)) for r in schedule.requests])),
                case_id=case,rate_rps=rate,offered_requests=len(schedule.requests),total_requests_with_warmup=len(schedule.requests)+1,
                phase_table=[dict(name=n,start_ns=s*NS,end_ns=e*NS,rate_rps=r) for n,s,e,r in phases(case,rate)],
                event_probe_offsets_ns=[t*NS for t in boundaries],total_event_probes_including_before_and_after_drain=len(boundaries)+2))
    worst=sum(4*max(e['total_requests_with_warmup'] for e in entries if e['case_id']==case) for case in CASES)
    plan=copy.deepcopy(parent)
    plan.update(version=VERSION,status='CPU_prepared_v2_not_executed',input_sha256={k:sha(v) for k,v in raws.items()},
        rates_rps=list(RATES),schedules=entries,jobs=job_design(),
        development_basis=dict(role='development_tuning_not_independent_confirmation',source_step='031',
            original_status='failed',original_selection=None,retrospective_eligibility_repair=False,
            rationale='8rps_level_hit_client_cap;4rps_phase_delivered_all_offers_with_sampled_queue;new3rps_level_fills_gap;fresh_validation_required',
            pressure_or_complete_delivery_guaranteed=False,prior_result_is_diagnostic_reference=False),
        arrival_algorithm='phase_left_inclusive_right_exclusive;ceil(duration*rate)_requests;offset_i=floor(i*1e9*denominator/numerator)',
        next_blockers=['fresh_supervised_v2_L4_validation','under_load_source_and_paired_observer_validation',
            'scientific_precision_mismatch_repetition_and_reference_adjudication'])
    plan['budgets']['max_total_requests_including_warmups']=worst
    if worst!=1932:raise ValueError('Unexpected v2 total budget')
    return plan,files


def materialize(output,*,parent,failed_run,audit,analysis):
    parent=Path(parent);failed_run=Path(failed_run)
    load_v1(parent)
    manifest_raw=(failed_run/'artifact_manifest.json').read_bytes()
    for name,expected in json.loads(manifest_raw)['files'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or (failed_run/path).is_symlink() or sha((failed_run/path).read_bytes())!=expected:
            raise ValueError('Original failed-run artifact changed')
    paths=dict(legacy_plan_input=parent/'PLAN.json',legacy_manifest_input=parent/'artifact_manifest.json',corpus_input=parent/'corpus_input.json',
        development_result_input=failed_run/'RESULT.json',development_manifest_input=failed_run/'artifact_manifest.json',
        development_playback_input=failed_run/'rate_ladder-b0-off/playback.json',development_validation_input=Path(audit),development_analysis_input=Path(analysis))
    raws={k:p.read_bytes() for k,p in paths.items()};plan,files=compile_inputs(raws)
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():(root/name).write_bytes(raw)
    for name,raw in raws.items():(root/(name+'.json')).write_bytes(raw)
    (root/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    (root/'artifact_manifest.json').write_text(json.dumps(dict(files={p.name:sha(p.read_bytes()) for p in sorted(root.iterdir()) if p.is_file()}),indent=2)+'\n')
    return plan


def load_prepared(directory):
    root=Path(directory);manifest=json.loads((root/'artifact_manifest.json').read_text())['files'];raws={}
    if len(manifest)!=25:raise ValueError('Exact v2 packet required')
    for name,expected in manifest.items():
        if Path(name).name!=name or (root/name).is_symlink():raise ValueError('Unsafe packet path')
        raw=(root/name).read_bytes()
        if len(raw)>2*1024*1024 or sha(raw)!=expected:raise ValueError('Packet hash/size mismatch')
        raws[name]=raw
    plan,files=compile_inputs({k:raws[k+'.json'] for k in INPUTS})
    if json.loads(raws['PLAN.json'])!=plan or set(raws)!=set(files)|{'PLAN.json'}|{k+'.json' for k in INPUTS}:
        raise ValueError('V2 design/eligibility/guard settings changed')
    for name,raw in files.items():
        if raws[name]!=raw:raise ValueError('V2 offered bytes differ from exact compiler')
    return plan,{e['schedule_id']:ArrivalSchedule.from_bytes(raws[e['path']]) for e in plan['schedules']}
