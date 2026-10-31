"""Fixed same-host configuration receipt; no GPU imports or synchronization."""
from revision.tracing.worker_barrier import validate_barrier


def configuration_receipt(command,*,pid,device_uuid,session_nonce,generation,clock_domain,capture_active,config,now_ns):
    from revision.tracing.worker_barrier import worker_barrier
    receipt=worker_barrier(command,pid=pid,device_uuid=device_uuid,session_nonce=session_nonce,generation=generation,
        clock_domain=clock_domain,capture_active=capture_active,synchronize=lambda:None,now_ns=now_ns)
    if type(config['enable_prefix_caching']) is not bool or type(config['async_scheduling']) is not bool:
        raise ValueError('Actual boolean cache/scheduler settings required')
    return receipt|dict(source='worker_effective_configuration_v1',config=config,
        scope='actual_worker_configuration_not_CUDA_barrier')


def validate_configuration(receipt,command,binding,received_at_ns):
    if receipt.get('source')!='worker_effective_configuration_v1':raise ValueError('Unrecognized configuration source')
    if (command['session_nonce'],command['generation'],command['clock_domain'])!=(binding.session_nonce,binding.generation,binding.clock_domain):
        raise ValueError('Foreign configuration command binding')
    validate_barrier(receipt|dict(source='validated_worker_barrier_v1'),command,pid=binding.worker_pid,
        device_uuid=binding.device_uuid,received_at_ns=received_at_ns)
    expected=dict(enable_prefix_caching=False,async_scheduling=False,max_num_seqs=16,
        tensor_parallel_size=1,pipeline_parallel_size=1,data_parallel_size=1)
    config=receipt.get('config')
    if config!=expected or any(type(config[k]) is not type(v) for k,v in expected.items()):raise ValueError('Effective worker configuration differs from the challenge contract')
    return receipt


def install_configuration_route(api_server):
    @api_server.router.post('/revision/configuration')
    async def configuration(raw_request:api_server.Request):
        await api_server.engine_client(raw_request).collective_rpc('revision_configuration',timeout=10)
        return api_server.Response(status_code=200)
    return configuration
