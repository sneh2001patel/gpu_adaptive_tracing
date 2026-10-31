"""Bounded CPU scheduler event history and same-host snapshot validation.

No GPU imports, client-ID inference, histogram substitution or reference labels.
"""
from dataclasses import asdict
import json
from pathlib import Path
from revision.tracing.live_features import ServingBinding
from revision.tracing.measured_evidence import fields_only,identity,integer

VERSION='scheduler_hook_events_v1'
KINDS={'engine_admitted','first_positive_schedule','scheduler_finished'}


def atomic_json(path,data):
    path=Path(path);pending=path.with_suffix('.pending')
    pending.write_text(json.dumps(data,allow_nan=False)+'\n');pending.replace(path)


class EventJournal:
    def __init__(self,binding,now_ns,*,max_events=4096,max_requests=512):
        if type(binding) is not ServingBinding:raise ValueError('Typed scope required')
        integer(max_events,'max_events',1);integer(max_requests,'max_requests',1)
        if max_events>4096 or max_requests>512:raise ValueError('Event pilot budget exceeded')
        self.binding,self.now_ns=binding,now_ns;self.epoch=now_ns();self.events=[];self.states={}
        self.max_events,self.max_requests=max_events,max_requests
        self.attempted=0;self.dropped=0;self.faults=[];self.last_end=self.epoch;self.used_probes=set()
    def fault(self,reason):
        if len(self.faults)<32:self.faults.append(reason)
    def record(self,kind,request_id,start_ns,end_ns,*,terminal_status=None):
        self.attempted+=1
        try:
            identity(request_id,'engine request ID')
            if len(request_id)>256 or kind not in KINDS:raise ValueError('Invalid event kind/ID')
            integer(start_ns,'hook entry');integer(end_ns,'hook return')
            if not self.epoch<=start_ns<=end_ns<=self.now_ns():raise ValueError('Invalid hook clock order')
            state=self.states.get(request_id)
            if kind=='engine_admitted':
                if state is not None:raise ValueError('Duplicate engine request admission')
                if len(self.states)>=self.max_requests:raise ValueError('Request history budget exceeded')
                state={'admitted':True,'scheduled':False,'finished':False};self.states[request_id]=state
            elif state is None or state['finished']:raise ValueError('Missing admission or event after finish')
            elif kind=='first_positive_schedule':
                if state['scheduled']:raise ValueError('Duplicate first schedule')
                state['scheduled']=True
            elif kind=='scheduler_finished':
                identity(terminal_status,'terminal status');state['finished']=True
            self.last_end=max(self.last_end,end_ns)
            if len(self.events)>=self.max_events:self.dropped+=1;return
            self.events.append(dict(sequence=self.attempted,kind=kind,request_id=request_id,
                hook_enter_ns=start_ns,hook_return_ns=end_ns,observed_at_ns=self.now_ns(),terminal_status=terminal_status))
        except (ValueError,TypeError) as exc:
            self.dropped+=1;self.fault(str(exc))
    def scheduled(self,request_ids,start_ns,end_ns):
        for request_id in request_ids:
            state=self.states.get(request_id)
            if state is not None and state['scheduled'] and not state['finished']:continue
            # A batch shares the same enclosing source hook bracket.
            self.record('first_positive_schedule',request_id,start_ns,end_ns)
    def probe(self,command):
        fields_only(command,{'token','binding','requested_at_ns'})
        if command['binding']!=asdict(self.binding):raise ValueError('Foreign event probe scope')
        token=command['token']
        if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Hex probe token required')
        if token in self.used_probes:raise ValueError('Repeated event probe token')
        if len(self.used_probes)>=32:raise ValueError('Probe budget exceeded')
        integer(command['requested_at_ns'],'probe request time');observed=self.now_ns()
        if observed<command['requested_at_ns'] or observed<self.last_end:raise ValueError('Source probe clock precedes parent/history')
        self.used_probes.add(token)
        return dict(version=VERSION,binding=asdict(self.binding),token=token,requested_at_ns=command['requested_at_ns'],
            source_probe_ns=observed,epoch_ns=self.epoch,clock_name='time.monotonic_ns',
            attempted=self.attempted,dropped=self.dropped,faults=list(self.faults),events=list(self.events),
            history_complete=self.dropped==0 and not self.faults,
            semantics='engine_admission_to_first_positive_CPU_schedule_decision_not_GPU_execution',
            phase_attribution='not_instrumented',client_request_ID_mapping='not_validated',
            scope='single_owned_scheduler_host_process_no_GPU_clock_mapping')


def validate_snapshot(data,command,binding,received_at_ns):
    if type(binding) is not ServingBinding:raise ValueError('Typed expected binding required')
    integer(received_at_ns,'parent receipt time')
    if (data.get('version'),data.get('clock_name'),data.get('semantics'))!=(VERSION,'time.monotonic_ns','engine_admission_to_first_positive_CPU_schedule_decision_not_GPU_execution'):
        raise ValueError('Unsupported scheduler event semantics')
    if data.get('binding')!=asdict(binding) or command['binding']!=asdict(binding) or data.get('token')!=command['token'] or data.get('requested_at_ns')!=command['requested_at_ns']:
        raise ValueError('Foreign/stale snapshot')
    for key in ('epoch_ns','source_probe_ns','attempted','dropped'):integer(data[key],key)
    if not data['epoch_ns']<=command['requested_at_ns']<=data['source_probe_ns']<=received_at_ns:raise ValueError('Source clock outside parent probe bracket')
    if data['history_complete'] is not True or data['dropped'] or data['faults']:raise ValueError('Incomplete/dropped/faulted scheduler history')
    if data['attempted']!=len(data['events']) or len(data['events'])>4096:raise ValueError('Missing event sequences')
    states={};last_observed=data['epoch_ns']
    for index,event in enumerate(data['events'],1):
        fields_only(event,{'sequence','kind','request_id','hook_enter_ns','hook_return_ns','observed_at_ns','terminal_status'})
        if event['sequence']!=index or event['kind'] not in KINDS:raise ValueError('Invalid event sequence/kind')
        for key in ('hook_enter_ns','hook_return_ns','observed_at_ns'):integer(event[key],key)
        if not data['epoch_ns']<=event['hook_enter_ns']<=event['hook_return_ns']<=event['observed_at_ns']<=data['source_probe_ns'] or event['observed_at_ns']<last_observed:raise ValueError('Invalid event acquisition order')
        last_observed=event['observed_at_ns'];rid=event['request_id'];identity(rid,'request ID');state=states.get(rid)
        if event['kind']=='engine_admitted':
            if state is not None:raise ValueError('Duplicate admission')
            states[rid]={'admission':event,'scheduled':None,'finished':None}
        else:
            if state is None or state['finished'] is not None:raise ValueError('Missing admission/event after terminal')
            key='scheduled' if event['kind']=='first_positive_schedule' else 'finished'
            if state[key] is not None:raise ValueError('Duplicate lifecycle event')
            previous=state['scheduled'] or state['admission']
            if event['hook_return_ns']<previous['hook_return_ns']:raise ValueError('Request lifecycle clock reversed')
            if key=='finished':identity(event['terminal_status'],'terminal status')
            state[key]=event
    return states


def scheduler_wait_bounds(data,command,binding,*,received_at_ns,start_ns,end_ns):
    states=validate_snapshot(data,command,binding,received_at_ns)
    integer(start_ns,'window start');integer(end_ns,'window end')
    if not data['epoch_ns']<=start_ns<end_ns<=data['source_probe_ns']:raise ValueError('Window outside complete probed history')
    rows=[];ambiguous=[]
    for rid,state in states.items():
        scheduled=state['scheduled']
        if scheduled is None:continue  # admitted but not scheduled remains censored, never zero wait
        lo,hi=scheduled['hook_enter_ns'],scheduled['hook_return_ns']
        if hi<start_ns or lo>=end_ns:continue
        if not start_ns<=lo<=hi<end_ns:
            ambiguous.append(rid);continue
        admitted=state['admission']
        rows.append(dict(request_id=rid,wait_lower_ms=max(0,lo-admitted['hook_return_ns'])/1e6,
            wait_upper_ms=(hi-admitted['hook_enter_ns'])/1e6))
    return dict(version=VERSION,cohort='first_positive_CPU_schedule_bracket_wholly_inside_half_open_window',
        start_ns=start_ns,end_ns=end_ns,available_at_ns=received_at_ns,observations=rows,boundary_ambiguous_request_ids=ambiguous,
        still_unscheduled_at_probe_request_ids=[rid for rid,s in states.items() if s['scheduled'] is None and s['finished'] is None],
        finished_without_schedule_at_probe_request_ids=[rid for rid,s in states.items() if s['scheduled'] is None and s['finished'] is not None],
        existing_request_wait_p95_mapping='unsupported_scheduler_decision_proxy_and_interval_uncertainty',
        pending_status_scope='source_probe_not_historical_window_end',
        prefill_service_fraction=None,phase_attribution='not_instrumented')


async def collect_snapshot(clock,binding,directory,trigger,*,timeout_s=2):
    """Parent-owned file probe; caller supplies a bounded source-hook trigger.

    This is same-host collection, not an HTTP or GPU clock calibration. An idle
    scheduler may need a declared diagnostic request outside the measured case.
    """
    import asyncio,hashlib,math,uuid
    if type(binding) is not ServingBinding or clock.domain!=binding.clock_domain:raise ValueError('Unmapped parent/source clock')
    if isinstance(timeout_s,bool) or not isinstance(timeout_s,(int,float)) or not math.isfinite(timeout_s) or not 0<timeout_s<=10:raise ValueError('Bounded probe deadline required')
    directory=Path(directory)
    command=dict(token=uuid.uuid4().hex,binding=asdict(binding),requested_at_ns=clock.now_ns())
    atomic_json(directory/'probe_command.json',command)
    async def exchange():
        await trigger()
        path=directory/('snapshot-'+command['token']+'.json')
        while not path.exists():await asyncio.sleep(.005)
        if path.is_symlink() or path.stat().st_size>8*1024*1024:raise ValueError('Invalid/oversized snapshot file')
        raw=path.read_bytes();received=clock.now_ns();data=json.loads(raw)
        validate_snapshot(data,command,binding,received)
        return dict(command=command,received_at_ns=received,raw_sha256=hashlib.sha256(raw).hexdigest(),data=data)
    return await asyncio.wait_for(exchange(),timeout_s)
