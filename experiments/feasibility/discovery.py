"""Read-only discovery on an already running local pinned serving stack.

Does not launch serving, submit workload, reset workers, start capture, or kill
processes. A separate owned activity adapter is required for those stages.
"""
import asyncio,csv,hashlib,json,os,re,subprocess
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit
from experiments.feasibility.harness import NotAvailable
from experiments.tracing.feature_collection import http_body
from experiments.evaluation.reference_store import read_regular


def command(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=5,check=True)
    return result.stdout.strip()


class ReadOnlyDiscovery:
    def __init__(self,config,clock,endpoint,model_path,session_directory):
        url=urlsplit(endpoint)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
            raise ValueError('Explicit local serving endpoint required')
        self.config,self.clock=config,clock;self.endpoint=endpoint.rstrip('/')
        self.model_path=Path(model_path).resolve();self.session_directory=Path(session_directory)

    async def inventory(self,output,context):
        config=self.config
        if self.model_path.name!=config['model_revision']:raise ValueError('Pinned local model revision path mismatch')
        config_path=(self.model_path/'config.json').resolve(strict=True)
        cache_root=self.model_path.parent.parent if self.model_path.parent.name=='snapshots' else self.model_path
        if not config_path.is_relative_to(cache_root):raise ValueError('Model config symlink escapes configured cache')
        config_raw=read_regular(config_path)
        observed_version=version('vllm')
        nsys=await asyncio.to_thread(command,['nsys','--version']);match=re.search(r'\b(20\d{2}\.\d+\.\d+)\b',nsys)
        if match is None:raise ValueError('Unrecognized Nsight version output')
        gpu=await asyncio.to_thread(command,['nvidia-smi','--query-gpu=uuid,name','--format=csv,noheader','--id='+config['device_uuid']])
        rows=list(csv.reader(gpu.splitlines()))
        if len(rows)!=1 or len(rows[0])!=2:raise ValueError('Exactly one selected GPU required')
        uuid,name=[v.strip() for v in rows[0]]
        workers=[json.loads(read_regular(p)) for p in sorted(self.session_directory.glob('worker-*.json'))]
        if len(workers)!=1:raise ValueError('Exactly one worker record required')
        pid=workers[0]['pid'];os.kill(pid,0)  # Liveness only; CUDA mapping checked separately.
        compute=await asyncio.to_thread(command,['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'])
        selected=[int(row[1].strip()) for row in csv.reader(compute.splitlines()) if len(row)==2 and row[0].strip()==uuid]
        if selected!=[pid]:raise ValueError('Live selected-device compute PID differs from worker record')
        status,health=await http_body(self.endpoint+'/health')
        if status!=200:raise ValueError('Serving health failed')
        status,body=await http_body(self.endpoint+'/v1/models')
        if status!=200 or config['model'] not in [m['id'] for m in json.loads(body)['data']]:raise ValueError('Served model label mismatch')
        return dict(vllm_version=observed_version,nsys_version=match[1],model_revision=self.model_path.name,
            model_config_sha256=hashlib.sha256(config_raw).hexdigest(),device_uuid=uuid,device_name=name,
            worker_pids=[pid],worker_device_uuids=[workers[0]['device_uuid']],
            source_manifest_sha256=hashlib.sha256((output/'source_manifest.json').read_bytes()).hexdigest(),
            raw_nsys_version=nsys,raw_gpu_inventory=gpu,raw_compute_inventory=compute,worker_records=workers,
            model_identity_scope='local_revision_config_and_served_label_not_proof_of_loaded_weight_bytes',
            source_clock_mapping=False,ownership_scope='read_only_existing_server_not_owned_by_this_probe')

    async def metrics(self,output,context):
        samples=[]
        for index in range(self.config['metric_samples']):
            requested=self.clock.now_ns();status,raw=await http_body(self.endpoint+'/metrics');received=self.clock.now_ns()
            path=f'metrics-{index:03d}.txt';(output/path).write_bytes(raw)
            samples.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),http_status=status,
                requested_at_ns=requested,received_at_ns=received,clock_domain=self.clock.domain))
            if index+1<self.config['metric_samples']:await asyncio.sleep(self.config['metric_interval_s'])
        return dict(samples=samples)

    async def quiet_reset(self,output,context):
        raise NotAvailable('Read-only discovery has no owned worker barrier/restart adapter; zero gauges are insufficient')

    async def capture(self,output,context):
        raise NotAvailable('Capture needs an owned activity adapter; historical pilot reports cannot satisfy a fresh gate')

    async def cleanup(self,output,context):return dict(scope='read_only_no_owned_processes')
