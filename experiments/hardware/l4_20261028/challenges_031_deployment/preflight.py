"""Read-only source/model/GPU preflight before the supervised campaign."""
import hashlib,json,socket,subprocess,time
from pathlib import Path
from revision.feasibility.challenge_freeze import validate_freeze,validate_installed
ROOT=Path('/workspace/gpu_adaptive_tracing_step031')
freeze=ROOT/'revision/examples/challenge_runner/snapshot_001/FREEZE.json'
record=validate_freeze(ROOT,ROOT/'revision/examples/event_challenges/prepared_001',freeze);validate_installed(record)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
assert sha(Path('/tmp/step031_source.tar.gz'))==record['source_archive_sha256']
assert sha(freeze)=='07f3bc3270ff5a404569a318c8ca320f7ebad14b1f23b9250716a40a138615d9'
model=Path('/dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28')
expected=json.loads(Path('/tmp/step031_model_files.json').read_text())['files'];checked={}
for name,entry in expected.items():
 path=model/name;assert path.stat().st_size==entry['bytes'],name
 digest=sha(path);assert digest==entry['sha256'],name;checked[name]=dict(bytes=path.stat().st_size,sha256=digest)
with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',8012))!=0,'Port already occupied'
result=dict(checked_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),model_files=checked,
 frozen_entries_verified=len(record['files']),installed_source_pins_verified=len(record['installed_vllm_pins']),
 source_archive_sha256=record['source_archive_sha256'],freeze_sha256=sha(freeze))
for name,args in dict(gpu=['nvidia-smi','--query-gpu=uuid,name,memory.used','--format=csv,noheader,nounits'],
 compute=['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits']).items():
 p=subprocess.run(args,check=True,capture_output=True,text=True);result[name]=p.stdout
assert not result['compute'].strip() and result['gpu'].strip()=='GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb, NVIDIA L4, 0'
(ROOT/'preflight.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(preflight_passed=True,model_files_verified=len(checked),frozen_entries_verified=len(record['files']),installed_source_pins_verified=len(record['installed_vllm_pins']))))
