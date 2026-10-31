"""Staged feasibility gates. Cleanup always runs; no study-readiness shortcut.

A live read-only adapter can discover capabilities, but cannot supply mutation
receipts. Positive synthetic gate checks never become live feasibility results.
"""
import asyncio,hashlib,json,math
from pathlib import Path
from revision.feasibility.metrics import sequence,GAUGES
from revision.tracing.measured_evidence import integer,identity,fields_only
from revision.tracing.nsys_backend import parse_kernel_database

STAGES=('inventory','metrics','quiet_reset','capture','cleanup')


class NotAvailable(RuntimeError):pass


def bounded_file(root,relative):
    if not isinstance(relative,str) or not relative:raise ValueError('Artifact path required')
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts:raise ValueError('Artifacts must be relative to the output')
    candidate=Path(root)/path
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(Path(root).resolve()):raise ValueError('Artifact path escape')
    if not candidate.is_file() or candidate.stat().st_size>64*1024*1024:raise ValueError('Missing/oversized artifact')
    return candidate


def check(stage,data,config,context,root,provenance,clock_domain):
    if type(data) is not dict:raise ValueError('Stage receipt must be an object')
    if stage=='inventory':
        for key in ('vllm_version','nsys_version','model_revision','device_name'):
            if data.get(key)!=config[key]:raise ValueError('Pinned '+key+' mismatch')
        if data.get('device_uuid')!=config['device_uuid']:raise ValueError('GPU UUID mismatch')
        pids=data.get('worker_pids')
        if type(pids) is not list or len(pids)!=1:raise ValueError('Exactly one worker required')
        integer(pids[0],'worker PID',1)
        if data.get('worker_device_uuids')!=[config['device_uuid']]:raise ValueError('Worker/device mismatch')
        for key in ('model_config_sha256','source_manifest_sha256'):
            value=data.get(key)
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Explicit '+key+' required')
        if data['source_manifest_sha256']!=hashlib.sha256((Path(root)/'source_manifest.json').read_bytes()).hexdigest():raise ValueError('Source manifest fingerprint mismatch')
        context['worker_pid']=pids[0]
    elif stage=='metrics':
        samples=data.get('samples')
        if type(samples) is not list or len(samples)<config['metric_samples']:raise ValueError('Insufficient metric snapshots')
        raws=[];last=-1
        for sample in samples:
            requested=sample['requested_at_ns'];received=sample['received_at_ns']
            integer(requested,'request time');integer(received,'receipt time')
            if requested<last or received<requested or sample['clock_domain']!=clock_domain:raise ValueError('Invalid metric receipt order/domain')
            last=received;raw=bounded_file(root,sample['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sample['sha256']:raise ValueError('Metric artifact hash mismatch')
            if sample['http_status']!=200:raise ValueError('Metric HTTP request failed')
            raws.append(raw)
        result=sequence(raws,model=config['model'],engine=config['engine']);context['metric_capabilities']=result
        if any(not row['ok'] for row in result['snapshots']):raise ValueError('Invalid selected metric exposition')
        for row in result['snapshots']:
            if any(not row['inspection']['gauges'][name]['available'] for name in GAUGES):raise ValueError('Required running/waiting gauges unavailable')
        # TYPE/presence is discovery only, not validated source/cohort mapping.
    elif stage=='quiet_reset':
        if data.get('clock_domain')!=clock_domain:raise ValueError('Unmapped quiet/reset clock')
        reset=data['reset'];before=data['before'];after=data['after'];pid=context['worker_pid']
        for key in ('requested_at_ns','completed_at_ns','generation_before','generation_after'):integer(reset[key],key)
        if reset['method']!='fresh_owned_worker_restart' or reset['generation_after']!=reset['generation_before']+1:raise ValueError('Unsupported reset or generation')
        identity(reset['request_token'],'reset token')
        if reset['request_token']!=reset['ack_token'] or reset['old_worker_pid']!=pid:raise ValueError('Stale reset acknowledgement')
        integer(reset['new_worker_pid'],'new worker PID',1)
        if reset['new_worker_pid']==pid:raise ValueError('Fresh-worker reset reused PID')
        if reset['completed_at_ns']<reset['requested_at_ns']:raise ValueError('Reset acknowledgement precedes request')
        previous=-1;tokens=set()
        for rows,expected_pid,generation in ((before,pid,reset['generation_before']),(after,reset['new_worker_pid'],reset['generation_after'])):
            if type(rows) is not list or len(rows)<config['quiet_observations']:raise ValueError('Repeated server/worker quiet observations required')
            for row in rows:
                for key in ('observed_at_ns','barrier_completed_at_ns','queued','running','worker_pid','generation'):integer(row[key],key)
                if row['observed_at_ns']<previous or not previous<=row['barrier_completed_at_ns']<=row['observed_at_ns']:raise ValueError('Invalid barrier/observation ordering')
                if row['queued'] or row['running'] or row['worker_pid']!=expected_pid or row['generation']!=generation:raise ValueError('Busy or foreign quiet observation')
                if row.get('barrier_source')!=('synthetic_worker_barrier' if provenance=='synthetic_simulation' else 'validated_worker_barrier_v1'):raise ValueError('Worker quiet barrier unavailable')
                identity(row['barrier_token'],'worker barrier token')
                if row['barrier_token'] in tokens:raise ValueError('Cached worker barrier cannot establish repeated quiet')
                tokens.add(row['barrier_token']);previous=row['observed_at_ns']
            if rows[-1]['observed_at_ns']-rows[0]['observed_at_ns']<config['quiet_hold_ns']:raise ValueError('Insufficient quiet hold')
        if not before[-1]['observed_at_ns']<=reset['requested_at_ns']<=reset['completed_at_ns']<=after[0]['observed_at_ns']:raise ValueError('Reset outside quiet boundaries')
        context['worker_pid']=reset['new_worker_pid'];context['reset_completed_ns']=after[-1]['observed_at_ns']
    elif stage=='capture':
        if data.get('clock_domain')!=clock_domain:raise ValueError('Capture clock mismatch')
        if data.get('source')!=('synthetic_sqlite_fixture' if provenance=='synthetic_simulation' else 'nsys_sqlite'):raise ValueError('Capture provenance mismatch')
        times=[data[k] for k in ('start_ack_ns','stop_ack_ns','report_ready_ns','parsed_ready_ns','decision_ns','serving_continued_ns')]
        for stamp in times:integer(stamp,'capture lifecycle timestamp')
        if times[0]<context['reset_completed_ns'] or any(a>b for a,b in zip(times,times[1:])) or times[0]==times[1]:raise ValueError('Capture/readiness/continuation ordering invalid')
        if times[1]-times[0]<round(config['requested_capture_s']*1e9):raise ValueError('Acknowledged control range is shorter than the requested capture')
        if data.get('continuation_http_status')!=200:raise ValueError('Serving continuation failed')
        path=bounded_file(root,data['sqlite_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=data['sqlite_sha256']:raise ValueError('Capture artifact hash mismatch')
        context['kernel_evidence']=parse_kernel_database(path,expected_uuid=config['device_uuid'],expected_pids=[context['worker_pid']])
        context['capture_completed_ns']=times[-1]
    elif stage=='cleanup':
        if data.get('scope')=='read_only_no_owned_processes':
            context['owned_cleanup_verified']=False;return
        if data.get('clock_domain')!=clock_domain:raise ValueError('Cleanup clock mismatch')
        if data.get('scope')!='all_pilot_owned_process_groups' or data.get('confirmed_absent') is not True:raise ValueError('Owned cleanup not confirmed')
        integer(data.get('completed_at_ns'),'cleanup completion')
        if data['completed_at_ns']<context.get('capture_completed_ns',0):raise ValueError('Cleanup precedes capture completion')
        context['owned_cleanup_verified']=True


async def run(adapter,config,output,*,provenance,clock_domain):
    from revision.scripts.play_arrivals import write_sources
    if provenance not in ('synthetic_simulation','live_online'):raise ValueError('Explicit provenance required')
    fields_only(config,{'version','vllm_version','nsys_version','model','model_revision','device_name','engine','stage_timeout_s','metric_samples','metric_interval_s','quiet_observations','quiet_hold_ns','capture_attempts','requested_capture_s','main_matrix_enabled','calibration_enabled','device_uuid'})
    if config['version']!='l4_feasibility_v1' or config['main_matrix_enabled'] is not False or config['calibration_enabled'] is not False or config['capture_attempts']!=1:
        raise ValueError('Feasibility cannot enable a matrix/calibration or multiple captures')
    integer(config['capture_attempts'],'capture attempts',1)
    for key,minimum,maximum in (('stage_timeout_s',0,60),('requested_capture_s',0,5),('metric_interval_s',-1,10)):
        value=config[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<value<=maximum or (key=='metric_interval_s' and value<0):raise ValueError('Invalid bounded '+key)
    integer(config['metric_samples'],'metric samples',2)
    if config['metric_samples']>100:raise ValueError('Metric sample limit exceeded')
    identity(config['device_uuid'],'device UUID')
    if not config['device_uuid'].startswith('GPU-'):raise ValueError('Explicit GPU UUID required')
    for key in ('vllm_version','nsys_version','model','model_revision','device_name','engine'):identity(config[key],key)
    integer(config['quiet_observations'],'quiet observations',2)
    integer(config['quiet_hold_ns'],'quiet hold',1);identity(clock_domain,'clock domain');identity(config['device_uuid'],'device UUID')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);write_sources(output)
    (output/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    context={};gates={};blocked=False;primary=None
    async def execute(stage):
        try:
            receipt=await asyncio.wait_for(getattr(adapter,stage)(output,context),config['stage_timeout_s'])
            (output/(stage+'_receipt.json')).write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
            check(stage,receipt,config,context,output,provenance,clock_domain)
            gates[stage]=dict(status='passed',reason=None)
        except NotAvailable as exc:gates[stage]=dict(status='unavailable',reason=str(exc))
        except Exception as exc:gates[stage]=dict(status='failed',reason=type(exc).__name__+': '+str(exc))
        (output/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
    try:
        for stage in STAGES[:-1]:
            if blocked:gates[stage]=dict(status='skipped',reason='prior_gate_not_passed');continue
            try:await execute(stage)
            except BaseException as exc:
                gates[stage]=dict(status='cancelled',reason=type(exc).__name__);raise
            blocked=gates[stage]['status']!='passed'
    except BaseException as exc:primary=exc
    finally:
        for stage in STAGES[:-1]:gates.setdefault(stage,dict(status='skipped',reason='run_interrupted'))
        cleanup=asyncio.create_task(execute('cleanup'))
        while not cleanup.done():
            try:await asyncio.shield(cleanup)
            except asyncio.CancelledError as exc:
                if primary is None:primary=exc
        try:cleanup.result()
        except BaseException as exc:
            gates['cleanup']=dict(status='failed',reason=type(exc).__name__)
            if primary is None:primary=exc
    all_passed=all(gates[s]['status']=='passed' for s in STAGES) and context.get('owned_cleanup_verified',False)
    result=dict(version='live_feasibility_gates_v1',provenance=provenance,clock_domain=clock_domain,gates=gates,
        discovery_passed=all(gates[s]['status']=='passed' for s in ('inventory','metrics')),
        gate_mechanics_passed=all_passed,live_feasibility_passed=all_passed and provenance=='live_online',
        study_ready=False,diagnosis_ready=False,protocol_frozen=False,context=context,
        capture_active_s=None,note='Receipt validation is conditional on adapter observations, not proof against fabricated evidence. Discovery never supplies worker quiet/reset, phase attribution, calibrated diagnosis or main-study readiness.')
    (output/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
    if primary is not None:raise primary
    return result
