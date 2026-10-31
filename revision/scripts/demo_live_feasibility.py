#!/usr/bin/env python3
"""Synthetic gate receipts/SQLite fixtures, never a hardware feasibility pass."""
import argparse,asyncio,hashlib,json,sqlite3
from pathlib import Path
from revision.feasibility.harness import run,NotAvailable


def metric_text(model='Qwen/Qwen2.5-7B-Instruct',count=2,*,waiting=0):
    label='model_name='+json.dumps(model)+',engine="0"'
    lines=[]
    for name,value in [('vllm:num_requests_waiting',waiting),('vllm:num_requests_running',0)]:
        lines.extend([f'# TYPE {name} gauge',f'{name}{{{label}}} {value}'])
    for family in ('vllm:request_queue_time_seconds','vllm:request_prefill_time_seconds','vllm:request_decode_time_seconds'):
        lines.append(f'# TYPE {family} histogram')
        for upper in ('0.1','1','+Inf'):lines.append(f'{family}_bucket{{{label},le="{upper}"}} {count}')
        lines.extend([f'{family}_count{{{label}}} {count}',f'{family}_sum{{{label}}} {count*.01}'])
    return ('\n'.join(lines)+'\n').encode()


class FixtureAdapter:
    """All receipts are hand-authored fixtures, including claimed worker barriers."""
    def __init__(self,config,mode='positive',domain='fixture-feasibility-clock'):
        self.config,self.mode,self.domain=config,mode,domain;self.calls=[]
    async def inventory(self,output,context):
        self.calls.append('inventory');c=self.config
        data={k:c[k] for k in ('vllm_version','nsys_version','model_revision','device_name','device_uuid')}
        data.update(worker_pids=[42],worker_device_uuids=[c['device_uuid']],model_config_sha256='a'*64,
            source_manifest_sha256=hashlib.sha256((output/'source_manifest.json').read_bytes()).hexdigest())
        if self.mode=='wrong_pin':data['vllm_version']='wrong'
        return data
    async def metrics(self,output,context):
        self.calls.append('metrics');samples=[]
        for i in range(self.config['metric_samples']):
            raw=metric_text(count=i+1);path=f'metrics-{i}.txt';(output/path).write_bytes(raw)
            samples.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),http_status=200,
                requested_at_ns=i*100,received_at_ns=i*100+1,clock_domain=self.domain))
        if self.mode=='bad_hash':samples[0]['sha256']='0'*64
        return dict(samples=samples)
    async def quiet_reset(self,output,context):
        self.calls.append('quiet_reset')
        if self.mode=='discovery_only':raise NotAvailable('Owned activity adapter unavailable')
        def row(t,pid,generation):return dict(observed_at_ns=t,barrier_completed_at_ns=t,queued=0,running=0,
            worker_pid=pid,generation=generation,barrier_source='synthetic_worker_barrier',barrier_token='barrier-'+str(t))
        result=dict(clock_domain=self.domain,before=[row(1000,42,0),row(10_001_000,42,0)],
            reset=dict(method='fresh_owned_worker_restart',requested_at_ns=10_002_000,completed_at_ns=10_003_000,
                generation_before=0,generation_after=1,old_worker_pid=42,new_worker_pid=43,request_token='reset-token',ack_token='reset-token'),
            after=[row(10_004_000,43,1),row(20_004_000,43,1)])
        if self.mode=='busy':result['after'][0]['running']=1
        if self.mode=='stale_reset':result['reset']['ack_token']='stale'
        return result
    async def capture(self,output,context):
        self.calls.append('capture');path=output/'capture.sqlite';c=sqlite3.connect(path)
        c.executescript('CREATE TABLE TARGET_INFO_GPU(id INTEGER,uuid TEXT,name TEXT); CREATE TABLE PROCESSES(globalPid INTEGER,pid INTEGER); CREATE TABLE StringIds(id INTEGER,value TEXT); CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL(start INTEGER,end INTEGER,deviceId INTEGER,globalPid INTEGER,demangledName INTEGER);')
        c.execute('INSERT INTO TARGET_INFO_GPU VALUES(0,?,?)',(self.config['device_uuid'],'synthetic L4 fixture'))
        c.execute('INSERT INTO PROCESSES VALUES(1,43)');c.execute("INSERT INTO StringIds VALUES(1,'synthetic_kernel')")
        c.execute('INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES(1,10,0,1,1)');c.commit();c.close()
        result=dict(clock_domain=self.domain,source='synthetic_sqlite_fixture',sqlite_path=path.name,
            sqlite_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),start_ack_ns=21_000_000,stop_ack_ns=1_021_000_000,
            report_ready_ns=1_022_000_000,parsed_ready_ns=1_023_000_000,decision_ns=1_024_000_000,
            serving_continued_ns=1_025_000_000,continuation_http_status=200)
        if self.mode=='future_parse':result['parsed_ready_ns']=4_000_000_000
        return result
    async def cleanup(self,output,context):
        self.calls.append('cleanup')
        return dict(scope='all_pilot_owned_process_groups',confirmed_absent=self.mode!='cleanup_failure',
            completed_at_ns=2_000_000_000,clock_domain=self.domain)


async def main(output):
    from revision.scripts.play_arrivals import write_sources
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    config=json.loads(Path('revision/configs/l4_feasibility_v1.json').read_text());config['device_uuid']='GPU-fixture'
    rows=[]
    for mode in ('positive','wrong_pin','bad_hash','busy','stale_reset','future_parse','cleanup_failure','discovery_only'):
        adapter=FixtureAdapter(config,mode)
        result=await run(adapter,config,output/mode,provenance='synthetic_simulation',clock_domain=adapter.domain)
        rows.append(dict(case=mode,gates=result['gates'],mechanics_passed=result['gate_mechanics_passed'],
            live_feasibility_passed=result['live_feasibility_passed'],study_ready=result['study_ready'],calls=adapter.calls))
    summary=dict(gpu_used=False,provenance='synthetic_simulation',cases=rows,
        note='Hand-authored gate receipts and synthetic SQLite kernels; not hardware/reset/capture validation.')
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Live-feasibility gate checks on CPU','',summary['note'],'',
        '| Case | Gate mechanics passed | Live feasibility passed | Study ready |',
        '|---|---|---|---|']
    for row in rows:lines.append(f"| {row['case']} | {row['mechanics_passed']} | {row['live_feasibility_passed']} | {row['study_ready']} |")
    lines+=['','Positive fixture receipts exercise ordered gates, including synthetic worker barriers and SQLite kernels. They do not validate those operations on hardware.','',
        'Discovery-only stops before capture when owned activity evidence is unavailable. Receipt validation and cleanup mechanics do not establish causal truth or calibration. The real read-only adapter never restarts or profiles a server.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);asyncio.run(main(p.parse_args().output))
