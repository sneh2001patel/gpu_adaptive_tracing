"""Independent scoped PID/group and device checks after the one-shot exits."""
import os,json,subprocess,time
from pathlib import Path
ROOT=Path('/workspace/gpu_adaptive_tracing_step031');pilot=ROOT/'revision/hardware/l4_20261028/challenges_001'
rows=[]
for path in sorted(pilot.glob('*/session-*/launch.json')):
 launch=json.loads(path.read_text());row=dict(session=str(path.parent.relative_to(pilot)),parent_pid=launch['pid'])
 targets=[('parent',launch['pid'])];workers=list(path.parent.glob('worker-*.json'))
 if workers:
  row['worker_pid']=json.loads(workers[0].read_text())['pid'];targets.append(('worker',row['worker_pid']))
 for label,pid in targets:
  try:os.kill(pid,0);row[label+'_absent']=False
  except ProcessLookupError:row[label+'_absent']=True
 try:os.killpg(launch['pid'],0);row['group_absent']=False
 except ProcessLookupError:row['group_absent']=True
 rows.append(row)
result=dict(checked_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),processes=rows,rental_stopped=False)
for name,args in dict(gpu=['nvidia-smi','--query-gpu=uuid,name,memory.used','--format=csv,noheader,nounits'],
 compute=['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],
 supervisor=['supervisorctl','status','revision-l4-challenges-031']).items():
 p=subprocess.run(args,capture_output=True,text=True);result[name]=dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
(ROOT/'post_cleanup_checks.json').write_text(json.dumps(result,indent=2)+'\n')
assert all(all(row[k] for k in row if k.endswith('_absent')) for row in rows)
assert result['gpu']['returncode']==result['compute']['returncode']==0
assert not result['compute']['stdout'].strip() and result['gpu']['stdout'].strip().endswith(', 0')
assert 'EXITED' in result['supervisor']['stdout']
print(json.dumps(result,indent=2))
