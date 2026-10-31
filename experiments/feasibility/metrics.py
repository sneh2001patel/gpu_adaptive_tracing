"""Strict scoped classic Prometheus inspection for vLLM 0.10.2 V1.

Discovery only: finished-request histograms cannot supply admission cohorts or
exclusive GPU phase attribution. No MeasuredMetric is constructed here.
"""
import json,math,re
from decimal import Decimal,InvalidOperation
from experiments.tracing.measured_evidence import identity,finite

GAUGES=('vllm:num_requests_waiting','vllm:num_requests_running')
HISTOGRAMS=('vllm:request_queue_time_seconds','vllm:request_prefill_time_seconds','vllm:request_decode_time_seconds')
_LABEL=re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)=("(?:[^"\\]|\\[\\"n])*")')
_SAMPLE=re.compile(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([^\s]+)\s*')


def labels(text):
    if text is None:return {}
    result={};position=0
    while position<len(text):
        match=_LABEL.match(text,position)
        if match is None:raise ValueError('Unsupported label syntax/escape')
        if match[1] in result:raise ValueError('Duplicate label')
        result[match[1]]=json.loads(match[2]);position=match.end()
        if position<len(text):
            if text[position]!=',':raise ValueError('Invalid label separator')
            position+=1
            if position==len(text):raise ValueError('Trailing label separator')
    return result


def count(value):
    try:parsed=Decimal(value)
    except InvalidOperation:raise ValueError('Invalid histogram count')
    if not parsed.is_finite() or parsed<0 or parsed!=parsed.to_integral_value() or parsed>2**53:raise ValueError('Exact bounded integer histogram count required')
    return int(parsed)


def inspect(raw,*,model,engine='0'):
    identity(model,'model');identity(engine,'engine')
    if type(raw) is not bytes or len(raw)>1048576:raise ValueError('Bounded metric bytes required')
    text=raw.decode('utf-8');wanted=dict(model_name=model,engine=engine)
    types={};samples={};other_scopes=set()
    known=set(GAUGES)|{f+suffix for f in HISTOGRAMS for suffix in ('_bucket','_count','_sum')}
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('# TYPE '):
            parts=line.split()
            if len(parts)!=4:raise ValueError('Invalid TYPE declaration')
            name,kind=parts[2:]
            if name in GAUGES+HISTOGRAMS:
                if name in types:raise ValueError('Duplicate TYPE declaration')
                types[name]=kind
            continue
        if not line or line.startswith('#'):continue
        name=re.split(r'[\s{]',line,maxsplit=1)[0]
        if name not in known:continue
        match=_SAMPLE.fullmatch(line)
        if match is None:raise ValueError('Unsupported selected sample/timestamp/exemplar')
        scope=labels(match[2]);value=match[3]
        if scope.get('model_name')!=model or scope.get('engine')!=engine:
            other_scopes.add((scope.get('model_name'),scope.get('engine')));continue
        expected=set(wanted)|({'le'} if name.endswith('_bucket') else set())
        if set(scope)!=expected:raise ValueError('Unexpected selected-series labels')
        key=(name,scope.get('le'))
        if key in samples:raise ValueError('Duplicate selected series')
        samples[key]=value
    gauges={}
    for name in GAUGES:
        value=samples.get((name,None));reason=None
        if types.get(name)!='gauge':reason='missing_or_wrong_gauge_type'
        elif value is None:reason='selected_series_missing'
        else:
            value=float(value);finite(value,'queue/running gauge')
            if value!=int(value):raise ValueError('Request gauge must be integral')
        gauges[name]=dict(value=None if reason else value,available=reason is None,reason=reason)
    histograms={}
    for family in HISTOGRAMS:
        reason=None;hist=None
        if types.get(family)!='histogram':reason='missing_or_wrong_histogram_type'
        else:
            pairs=[(float(bound),count(value)) for (name,bound),value in samples.items() if name==family+'_bucket']
            pairs.sort()
            total=samples.get((family+'_count',None));summed=samples.get((family+'_sum',None))
            if not pairs or total is None or summed is None:reason='incomplete_histogram_components'
            else:
                total=count(total);summed=float(summed);finite(summed,'histogram sum')
                bounds=[b for b,n in pairs];counts=[n for b,n in pairs]
                if len(bounds)<2 or bounds[-1]!=math.inf or any(not math.isfinite(b) or b<0 for b in bounds[:-1]) or any(a>=b for a,b in zip(bounds,bounds[1:])):
                    raise ValueError('Invalid histogram bucket schema')
                if counts[-1]!=total or any(a>b for a,b in zip(counts,counts[1:])):raise ValueError('Incoherent histogram snapshot')
                hist=dict(upper_seconds=['+Inf' if b==math.inf else b for b in bounds],cumulative_counts=counts,count=total,sum_seconds=summed)
        histograms[family]=dict(present=reason is None,reason=reason,snapshot=hist,
            cohort='finished_requests_reported_by_logger',source_timestamp_mapping=False)
    return dict(profile='vllm_0_10_2_v1_finished_request_metrics',selected_labels=wanted,gauges=gauges,histograms=histograms,
        other_scope_count=len(other_scopes),
        admission_window_wait_supported=False,prefill_service_fraction_supported=False,
        note='Presence is not calibration, atomicity, source-clock mapping, admission-cohort coverage or exclusive GPU phase attribution.')


def sequence(raws,*,model,engine='0'):
    if not raws:raise ValueError('At least one metric snapshot required')
    snapshots=[]
    for raw in raws:
        try:snapshots.append(dict(ok=True,inspection=inspect(raw,model=model,engine=engine),error=None))
        except (ValueError,TypeError,UnicodeError) as exc:snapshots.append(dict(ok=False,inspection=None,error=str(exc)))
    transitions=[]
    for index,(a,b) in enumerate(zip(snapshots,snapshots[1:])):
        for family in HISTOGRAMS:
            reason=None;delta=None
            if not a['ok'] or not b['ok']:reason='invalid_snapshot'
            else:
                x=a['inspection']['histograms'][family]['snapshot'];y=b['inspection']['histograms'][family]['snapshot']
                if x is None or y is None:reason='histogram_unavailable'
                elif x['upper_seconds']!=y['upper_seconds']:reason='bucket_schema_changed'
                else:
                    d=[v-u for u,v in zip(x['cumulative_counts'],y['cumulative_counts'])]
                    if any(v<0 for v in d) or y['sum_seconds']<x['sum_seconds']:reason='counter_decrease_or_reset'
                    elif any(u>v for u,v in zip(d,d[1:])):reason='incoherent_bucket_deltas'
                    else:delta=d[-1]
            transitions.append(dict(from_snapshot=index,to_snapshot=index+1,family=family,reason=reason,
                newly_reported_finished_requests=delta,usable_as_controller_feature=False))
    return dict(snapshots=snapshots,transitions=transitions,admission_wait_mapping='unsupported_cohort_and_clock',
        prefill_fraction_mapping='unsupported_exclusive_service_attribution')
