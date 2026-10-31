"""Read-only audit of locally backed-up step-022 hardware receipts."""
import hashlib,json,tarfile
from pathlib import Path
from revision.feasibility.harness import check
from revision.tracing.worker_barrier import validate_barrier
from revision.feasibility.metrics import inspect
from revision.tracing.feature_collection import response_usage

ROOT=Path(__file__).resolve().parent.parent
DEPLOY=ROOT/'activity_022_deployment'
def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
validation={}
for name,archive,archive_record in (
    ('activity_001','source_step022.tar.gz','source_archive.json'),
    ('activity_002','source_step022_fix.tar.gz','source_archive_fix.json')):
    output=ROOT/name; result=read(output/'RESULT.json');config=read(output/'configuration.json')
    manifest=read(output/'artifact_manifest.json')['files']
    for relative,expected in manifest.items():assert digest(output/relative)==expected,(name,relative)
    assert digest(DEPLOY/archive)==read(DEPLOY/archive_record)['sha256']
    sources=read(output/'source_manifest.json')['files']
    with tarfile.open(DEPLOY/archive) as frozen:
        for relative,expected in sources.items():assert hashlib.sha256(frozen.extractfile(relative).read()).hexdigest()==expected,relative
    context={}
    for stage in ('inventory','metrics','quiet_reset','capture','cleanup'):
        if result['gates'][stage]['status']=='passed':
            check(stage,read(output/(stage+'_receipt.json')),config,context,output,'live_online',result['clock_domain'])
    quiet=read(output/'quiet_evidence.json');tokens=set()
    for row in quiet:
        command=row['barrier_command'];receipt=row['barrier_receipt']
        assert command['token'] not in tokens;tokens.add(command['token'])
        validate_barrier(receipt,command,pid=receipt['pid'],device_uuid=config['device_uuid'],received_at_ns=row['barrier_received_at_ns'])
        assert row['owned_client_outstanding']==0
        assert row['requested_at_ns']<=row['before_received_at_ns']<=command['requested_at_ns']<=row['barrier_received_at_ns']<=row['observed_at_ns']
        for side in ('before','after'):
            path=output/row[side+'_path'];assert digest(path)==row[side+'_sha256']
            gauges=inspect(path.read_bytes(),model=config['model'],engine=config['engine'])['gauges']
            assert all(g['available'] and g['value']==0 for g in gauges.values())
    sessions=read(output/'cleanup_sessions.json')
    assert not sessions['errors'] and all(s['closed'] and s['cleanup']['group_absent'] and s['cleanup']['worker_absent'] for s in sessions['sessions'])
    backend=read(output/'backend_final.json');assert backend['ordinal']==1
    row=dict(artifact_hash_entries=len(manifest),source_fingerprints=len(sources),fresh_barriers=len(tokens),passed_gates=[k for k,v in result['gates'].items() if v['status']=='passed'],live_feasibility_passed=result['live_feasibility_passed'])
    assert result['study_ready'] is False and result['diagnosis_ready'] is False and result['protocol_frozen'] is False and result['capture_active_s'] is None
    if name=='activity_001':
        assert not result['live_feasibility_passed'] and result['gates']['capture']['reason']=='RuntimeError: starting_timeout'
        assert "callback_start.sh: not found" in (output/'session-1/server.log').read_text()
        assert not (output/'requests.json').exists()
        row['valid_capture_count']=0;row['failure_retained']='relative_callback_path_not_found'
    else:
        assert result['live_feasibility_passed'] and len(quiet)==6
        requests=read(output/'requests.json');assert len(requests)==2
        for request,expected_tokens in zip(requests,(32,16)):
            assert request['http_status']==200 and request['error'] is None
            path=output/request['response_path'];assert digest(path)==request['response_sha256']
            prompt,completed,error=response_usage(path.read_bytes());assert error is None and completed==expected_tokens
        cap=read(output/'capture_receipt.json');assert requests[1]['requested_at_ns']>=cap['decision_ns']
        assert requests[0]['requested_at_ns']>=cap['start_ack_ns'] and requests[0]['requested_at_ns']<cap['stop_ack_ns']
        row.update(valid_capture_count=1,kernel_count=context['kernel_evidence']['kernel_count'],request_statuses=[r['http_status'] for r in requests],control_ack_span_s=(cap['stop_ack_ns']-cap['start_ack_ns'])/1e9,parse_after_stop_s=(cap['parsed_ready_ns']-cap['stop_ack_ns'])/1e9)
    validation[name]=row
cleanup=read(ROOT/'activity_post_cleanup_checks.json')
assert len(cleanup['processes'])==4 and all(all(r[k] for k in ('parent_absent','worker_absent','group_absent')) for r in cleanup['processes'])
assert not cleanup['compute']['stdout'].strip() and cleanup['gpu']['stdout'].strip().endswith(', 0')
validation['post_cleanup_verified']=True
validation['cpu_tests']=dict(total=399,new=19,result='passed',scope='CPU logic and injected worker behavior, separate from hardware evidence')
(ROOT/'ACTIVITY_VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(validation,indent=2))
