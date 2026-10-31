import os,json,subprocess,time
from pathlib import Path
root=Path('/workspace/gpu_adaptive_tracing_step022/revision/hardware/l4_20261028')
checks=[]
for name in ('activity_001','activity_002'):
 for p in sorted((root/name).glob('session-*/launch.json')):
  launch=json.loads(p.read_text());worker=json.loads(next(p.parent.glob('worker-*.json')).read_text())
  record=dict(run=name,session=p.parent.name,parent_pid=launch['pid'],worker_pid=worker['pid'])
  for label,pid in (('parent',launch['pid']),('worker',worker['pid'])):
   try:os.kill(pid,0);record[label+'_absent']=False
   except ProcessLookupError:record[label+'_absent']=True
  try:os.killpg(launch['pid'],0);record['group_absent']=False
  except ProcessLookupError:record['group_absent']=True
  checks.append(record)
commands={
 'gpu': ['nvidia-smi','--query-gpu=uuid,name,memory.used','--format=csv,noheader,nounits'],
 'compute': ['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],
 'supervisor': ['supervisorctl','status','revision-l4-activity-022']}
result=dict(checked_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),processes=checks,rental_stopped=False)
for name,argv in commands.items():
 p=subprocess.run(argv,capture_output=True,text=True);result[name]=dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
assert all(all(r[k] for k in ('parent_absent','worker_absent','group_absent')) for r in checks)
assert not result['compute']['stdout'].strip()
assert result['gpu']['stdout'].strip().endswith(', 0')
(root/'activity_post_cleanup_checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
