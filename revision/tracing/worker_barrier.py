"""CUDA-free validation for worker barriers and same-host acknowledgements."""
from revision.tracing.measured_evidence import fields_only,identity,integer


def worker_barrier(command,*,pid,device_uuid,clock_domain,session_nonce,generation,capture_active,synchronize,now_ns):
    fields_only(command,{'token','session_nonce','generation','clock_domain','requested_at_ns'})
    identity(command['token'],'barrier token');integer(command['generation'],'generation')
    integer(command['requested_at_ns'],'request time');integer(pid,'worker PID',1)
    if (command['session_nonce'],command['generation'],command['clock_domain'])!=(session_nonce,generation,clock_domain):
        raise ValueError('Foreign worker barrier command')
    if not session_nonce or capture_active is not False:raise ValueError('Worker/session not available for quiet barrier')
    started=now_ns();integer(started,'barrier start')
    if started<command['requested_at_ns']:raise ValueError('Worker barrier clock precedes parent request')
    synchronize();completed=now_ns();integer(completed,'barrier completion')
    if completed<started:raise ValueError('Worker barrier clock reversed')
    return dict(source='validated_worker_barrier_v1',token=command['token'],session_nonce=session_nonce,
        generation=generation,clock_domain=clock_domain,pid=pid,device_uuid=device_uuid,
        requested_at_ns=command['requested_at_ns'],started_at_ns=started,completed_at_ns=completed,capture_active=False,
        scope='configured_worker_prior_issued_cuda_work_not_future_admissions_or_other_devices')


def validate_barrier(receipt,command,*,pid,device_uuid,received_at_ns):
    expected=dict(source='validated_worker_barrier_v1',token=command['token'],session_nonce=command['session_nonce'],
        generation=command['generation'],clock_domain=command['clock_domain'],pid=pid,device_uuid=device_uuid,
        requested_at_ns=command['requested_at_ns'],capture_active=False)
    if type(receipt) is not dict or any(receipt.get(k)!=v for k,v in expected.items()):raise ValueError('Foreign/stale barrier receipt')
    for key in ('requested_at_ns','started_at_ns','completed_at_ns','generation','pid'):integer(receipt[key],key)
    integer(received_at_ns,'parent receipt time')
    if not receipt['requested_at_ns']<=receipt['started_at_ns']<=receipt['completed_at_ns']<=received_at_ns:
        raise ValueError('Unmapped/future worker barrier clock')
    return receipt


def install_barrier_route(api_server):
    """The only new RPC is the fixed barrier method, with no arbitrary method input."""
    @api_server.router.post('/revision/barrier')
    async def barrier(raw_request: api_server.Request):
        await api_server.engine_client(raw_request).collective_rpc('revision_barrier',timeout=10)
        return api_server.Response(status_code=200)
    return barrier
