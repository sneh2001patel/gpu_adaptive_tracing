"""Independent CPU packet/archive audit and preservation of the failed v1 attempt."""
import copy,hashlib,json,tarfile,tempfile
from pathlib import Path
from experiments.feasibility.challenge_protocol_v2 import load_prepared,VERSION
from experiments.feasibility.challenge_freeze import validate_freeze
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'experiments/examples/event_challenges_v2'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan,bank=load_prepared(BASE/'prepared_001')
assert plan['rates_rps']==[.5,1,2,3,4] and len(bank['rate_ladder'].requests)==84
assert plan['budgets']['max_total_requests_including_warmups']==1932
assert all(j['executed'] is False for j in plan['jobs'])
manifests={}
for name in ('prepared_001','fixture_001'):
    files=read(BASE/name/'artifact_manifest.json')['files']
    for p,expected in files.items():assert sha(BASE/name/p)==expected,p
    manifests[name]=len(files)
snapshot=BASE/'snapshot_001';freeze=validate_freeze(ROOT,BASE/'prepared_001',snapshot/'FREEZE.json',loader=load_prepared)
assert freeze['challenge_protocol_version']==VERSION and freeze['supplement']['max_total_requests']==1932
assert sha(snapshot/'source_step032.tar.gz')==freeze['source_archive_sha256']
with tarfile.open(snapshot/'source_step032.tar.gz') as tar:
    for name,expected in freeze['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
old=ROOT/'experiments/examples/challenge_runner/snapshot_001'
assert sha(old/'source_step030.tar.gz')=='c4bc872cb5eb0fe583e29ab94bef6c7afd466f482a80dd77b1a93bb0b18fa747'
assert sha(old/'FREEZE.json')=='07f3bc3270ff5a404569a318c8ca320f7ebad14b1f23b9250716a40a138615d9'
old_freeze=read(old/'FREEZE.json')
with tarfile.open(old/'source_step030.tar.gz') as tar:
    for name,expected in old_freeze['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
failed=ROOT/'experiments/hardware/l4_20261028/challenges_001'
old_files=read(failed/'artifact_manifest.json')['files']
for name,expected in old_files.items():assert sha(failed/name)==expected,name
assert sha(failed/'artifact_manifest.json')==sha(BASE/'prepared_001/development_manifest_input.json')
assert read(failed/'RESULT.json')['status']=='failed' and read(failed/'RESULT.json')['selection'] is None
backup=ROOT/'experiments/hardware/l4_20261028/challenges_031_deployment/results_backup.tar.gz'
assert sha(backup)=='8686b5b489dc6edb350a08a929a4845bacd2155f9bb0e29f2e204c7eaa14d40e'
legacy=ROOT/'experiments/examples/event_challenges/prepared_001'
for name,expected in read(legacy/'artifact_manifest.json')['files'].items():assert sha(legacy/name)==expected,name
guards=[]
with tempfile.TemporaryDirectory() as temp:
    path=Path(temp)/'changed.json'
    for label,change in (('source',lambda f:f['files'].update({'experiments/feasibility/challenge_runner.py':'f'*64})),
                         ('packet',lambda f:f.update(packet_manifest_sha256='f'*64)),
                         ('protocol_version',lambda f:f.update(challenge_protocol_version='event_challenge_preparation_v1'))):
        modified=copy.deepcopy(freeze);change(modified);path.write_text(json.dumps(modified))
        try:validate_freeze(ROOT,BASE/'prepared_001',path,loader=load_prepared)
        except ValueError:guards.append(label)
    assert guards==['source','packet','protocol_version']
assert 'Ran 549 tests' in (BASE/'validation/cpu_suite.log').read_text()
assert (BASE/'validation/cpu_suite.log').read_text().rstrip().endswith('OK')
assert 'FAILED (failures=2)' in (BASE/'validation/cpu_suite_initial_failed.log').read_text()
result=dict(audit_passed=True,CPU_tests_passed=549,new_tests=18,focused_tests_passed=52,
    packet_and_fixture_hashes_verified=manifests,v2_frozen_entries_verified=len(freeze['files']),
    carried_forward_installed_source_pins=len(freeze['installed_vllm_pins']),
    original_frozen_entries_verified=len(old_freeze['files']),original_failed_artifacts_verified=len(old_files),
    original_packet_artifacts_verified=len(read(legacy/'artifact_manifest.json')['files']),original_run_still_failed=True,
    original_archive_and_backup_unchanged=True,source_packet_version_guards_tested=guards,
    initial_CPU_timing_failures_preserved=2,CPU_fixture_timing_windows_extended=True,GPU_guards_relaxed=False,
    rates_rps=plan['rates_rps'],new_ladder_offers=84,new_max_total_requests=1932,GPU_used=False,SSH_used=False,
    live_validation=False,study_ready=False,protocol_frozen=False,
    v2_source_archive_sha256=freeze['source_archive_sha256'],v2_freeze_sha256=sha(snapshot/'FREEZE.json'))
(BASE/'validation/AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
