"""Final read-only preservation/link/syntax checks; write only new check output."""
import ast,hashlib,json,re,subprocess,tarfile
from pathlib import Path
from revision.feasibility.challenge_freeze import validate_freeze
from revision.feasibility.challenge_protocol_v2 import load_prepared
DEPLOY=Path(__file__).resolve().parent
ROOT=DEPLOY.parents[3]
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot=ROOT/'revision/examples/event_challenges_v2/snapshot_001'
freeze=validate_freeze(ROOT,ROOT/'revision/examples/event_challenges_v2/prepared_001',snapshot/'FREEZE.json',loader=load_prepared)
assert sha(snapshot/'source_step032.tar.gz')=='a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51'
assert sha(snapshot/'FREEZE.json')=='60587c553e979b1103497f10685241dbfe282980565e19b723bfc59cf8972ec9'
old=ROOT/'revision/examples/challenge_runner/snapshot_001'
assert sha(old/'source_step030.tar.gz')=='c4bc872cb5eb0fe583e29ab94bef6c7afd466f482a80dd77b1a93bb0b18fa747'
assert sha(old/'FREEZE.json')=='07f3bc3270ff5a404569a318c8ca320f7ebad14b1f23b9250716a40a138615d9'
with tarfile.open(old/'source_step030.tar.gz') as tar:
 for name,expected in read(old/'FREEZE.json')['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected
failed=DEPLOY.parent/'challenges_001'
for name,expected in read(failed/'artifact_manifest.json')['files'].items():assert sha(failed/name)==expected
assert read(failed/'RESULT.json')['status']=='failed' and read(failed/'RESULT.json')['selection'] is None
assert sha(DEPLOY.parent/'challenges_031_deployment/results_backup.tar.gz')=='8686b5b489dc6edb350a08a929a4845bacd2155f9bb0e29f2e204c7eaa14d40e'
assert sha(DEPLOY/'results_backup.tar.gz')=='90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54'
for src,dst in [('supervisor_wrapper.sh','installed_supervisor_wrapper.sh'),('supervisor.conf','installed_supervisor.conf')]:assert (DEPLOY/src).read_bytes()==(DEPLOY/dst).read_bytes()
for path in DEPLOY.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
for path in DEPLOY.glob('*.sh'):subprocess.run(['bash','-n',str(path)],check=True)
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
documents=['CAIN_REVISION_PLAN.md','revision/PROGRESS.md','revision/README.md',
 'revision/protocol/SERVER_EVENT_INSTRUMENTATION.md','revision/progress/033_fresh_v2_l4_validation.md',
 'revision/hardware/l4_20261028/CHALLENGES_V2_REPORT.md']
links=0
for name in documents:
 path=ROOT/name;text=path.read_text()
 assert all(line.rstrip()==line for line in text.splitlines()),name
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
  target=target.strip('<>').split('#')[0]
  if not target or re.match(r'[a-zA-Z]+:',target):continue
  assert (path.parent/target).exists(),(name,target)
  links+=1
audit=read(DEPLOY.parent/'CHALLENGES_V2_VALIDATION.json');summary=read(DEPLOY.parent/'CHALLENGES_V2_SUMMARY.json')
assert audit['audit_passed'] and summary['scheduled_completed']==summary['scheduled_offers']==1536
assert audit['completed_jobs']==16 and audit['quiet_barriers_verified']==64
assert audit['repeated_historical_quiet_rows']==480 and audit['cleanup_verified']
result=dict(campaign_passed=True,independent_audit_passed=True,prior_frozen_CPU_tests_passed=549,
 CPU_suite_rerun_this_step=False,runtime_code_or_guard_changed=False,frozen_entries_verified=len(freeze['files']),
 original_failed_artifacts_preserved=True,original_archive_and_backup_unchanged=True,
 results_backup_sha256=sha(DEPLOY/'results_backup.tar.gz'),local_links_checked=links,
 syntax_and_whitespace_passed=True,installed_service_files_match=True,frozen_snapshot_unchanged=True,
 persistence_limitation_retained=True,owned_cleanup_verified=True,study_ready=False,protocol_frozen=False,
 document_sha256={name:sha(ROOT/name) for name in documents},
 deployment_helper_sha256={p.name:sha(p) for p in sorted(DEPLOY.iterdir()) if p.suffix in ('.py','.sh','.conf')})
(DEPLOY/'local_checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
