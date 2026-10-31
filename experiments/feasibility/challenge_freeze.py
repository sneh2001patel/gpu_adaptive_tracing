"""Immutable engineering source/packet snapshot; never a main-study freeze."""
import hashlib,json,re,tarfile
from pathlib import Path
from importlib.metadata import distribution,version
from experiments.feasibility.challenge_protocol import load_prepared


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(root,packet,output,test_log,*,loader=load_prepared,archive_name='source_step030.tar.gz',extra_documents=()):
    root=Path(root).resolve();packet=Path(packet).resolve();output=Path(output).resolve();test_log=Path(test_log).resolve()
    plan,_=loader(packet)
    if not packet.is_relative_to(root) or not test_log.is_relative_to(root):raise ValueError('Packet/test log must be in the deployment checkout')
    log=test_log.read_text();matches=re.findall(r'Ran (\d+) tests? in ',log)
    if not matches or not log.rstrip().endswith('OK'):raise ValueError('Passing full CPU test log required')
    paths=set()
    for folder in ('experiments/tracing','experiments/feasibility','experiments/evaluation','experiments/scripts','experiments/tests'):
        paths.update((root/folder).glob('*.py'))
    paths.update((root/'experiments/configs').glob('*.json'))
    paths.update(p for p in (root/'experiments/protocol/sources').rglob('*') if p.is_file())
    paths.update(packet.iterdir());paths.add(test_log)
    paths.update(root/'experiments/protocol'/name for name in ('EVENT_CHALLENGE_PROTOCOL.md','CHALLENGE_EXECUTION.md'))
    paths.update(root/Path(name) for name in extra_documents)
    files={str(p.relative_to(root)):sha(p) for p in sorted(paths)}
    installed=json.loads((root/'experiments/protocol/sources/vllm_0_10_2/event_ids/SOURCE_MANIFEST.json').read_text())['files']
    source=root/'experiments/protocol/sources/vllm_0_10_2/worker_config'
    for saved,installed_path in (
        ('gpu_worker.py.txt','vllm/v1/worker/gpu_worker.py'),('v1_worker_base.py.txt','vllm/v1/worker/worker_base.py'),
        ('worker_base.py.txt','vllm/worker/worker_base.py')):
        installed[installed_path]=sha(source/saved)
    installed['vllm/v1/core/sched/scheduler.py']=sha(root/'experiments/protocol/sources/vllm_0_10_2/events/scheduler.py.txt')
    if Path(archive_name).name!=archive_name:raise ValueError('Archive basename required')
    output.mkdir(parents=True,exist_ok=False);archive=output/archive_name
    with tarfile.open(archive,'w:gz') as tar:
        for name in files:tar.add(root/name,arcname=name,recursive=False)
    record=dict(version='event_challenge_engineering_snapshot_v1',challenge_protocol_version=plan['version'],study_ready=False,protocol_frozen=False,
        hardware_validated=False,engineering_launcher_available=True,cpu_tests_passed=int(matches[-1]),
        packet_directory=str(packet.relative_to(root)),packet_manifest_sha256=sha(packet/'artifact_manifest.json'),
        source_archive_sha256=sha(archive),files=files,installed_vllm_pins=installed,
        supplement=dict(consumer_decision_grace_ns=750_000_000,late_owner_decisions='unresolved_no_retrofill',
            metric_sampling='half_second_horizon_samples_plus_surrounding_quiet_receipts_not_continuous_drain_telemetry',
            profiler_enabled=False,max_jobs=16,max_total_requests=plan['budgets']['max_total_requests_including_warmups'],per_job_work_deadline_s=240,cleanup_deadline_s=45))
    (output/'FREEZE.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def validate_freeze(root,packet,freeze_path,*,loader=load_prepared):
    root=Path(root).resolve();packet=Path(packet).resolve();record=json.loads(Path(freeze_path).read_text())
    if record['version']!='event_challenge_engineering_snapshot_v1' or record['study_ready'] or record['protocol_frozen']:
        raise ValueError('Engineering source freeze required; no study protocol is frozen')
    if packet!=root/record['packet_directory'] or sha(packet/'artifact_manifest.json')!=record['packet_manifest_sha256']:
        raise ValueError('Frozen packet differs')
    for name,expected in record['files'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or (root/path).is_symlink():raise ValueError('Unsafe frozen source path')
        if sha(root/path)!=expected:raise ValueError('Source/input changed after freeze: '+name)
    plan,_=loader(packet)
    if record.get('challenge_protocol_version',plan['version'])!=plan['version']:raise ValueError('Frozen protocol version differs')
    return record


def validate_installed(record):
    if version('vllm')!='0.10.2':raise ValueError('Unreviewed vLLM version')
    dist=distribution('vllm')
    for name,expected in record['installed_vllm_pins'].items():
        if sha(dist.locate_file(name))!=expected:raise ValueError('Installed source differs from reviewed pin: '+name)
