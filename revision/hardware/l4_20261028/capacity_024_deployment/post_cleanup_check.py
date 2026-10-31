import os,json,subprocess,time
from pathlib import Path
root=Path('/workspace/gpu_adaptive_tracing_step024/revision/hardware/l4_20261028');pilot=root/'capacity_001'
checks=[]
for path in sorted(pilot.glob('session-*/launch.json')):
 launch=json.loads(path.read_text());worker=json.loads(next(path.parent.glob('worker-*.json')).read_text())
 row=dict(session=path.parent.name,parent_pid=launch['pid'],worker_pid=worker['pid'])
 for label,pid in (('parent',launch['pid']),('worker',worker['pid'])):
  try:os.kill(pid,0);row[label+'_absent']=False
  except ProcessLookupError:row[label+'_absent']=True
 try:os.killpg(launch['pid'],0);row['group_absent']=False
 except ProcessLookupError:row['group_absent']=True
 checks.append(row)
result=dict(checked_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),processes=checks,rental_stopped=False)
for name,argv in {
 'gpu':['nvidia-smi','--query-gpu=uuid,name,memory.used','--format=csv,noheader,nounits'],
 'compute':['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],
 'supervisor':['supervisorctl','status','revision-l4-capacity-024']}.items():
 p=subprocess.run(argv,capture_output=True,text=True);result[name]=dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
(root/'capacity_post_cleanup_checks.json').write_text(json.dumps(result,indent=2)+'\n')
assert checks and all(all(row[k] for k in ('parent_absent','worker_absent','group_absent')) for row in checks)
assert not result['compute']['stdout'].strip() and result['gpu']['stdout'].strip().endswith(', 0')
assert 'EXITED' in result['supervisor']['stdout']
print(json.dumps(result,indent=2))
