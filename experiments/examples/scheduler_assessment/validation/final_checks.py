"""Verify the actual blank workflow and preservation; fingerprint CPU source only."""
from dataclasses import asdict
import ast,hashlib,json,re,subprocess,tarfile
from pathlib import Path
from experiments.evaluation.evidence_assessment import Bundle,digest
from experiments.evaluation.references import ReferenceArtifact
from experiments.evaluation.scheduler_assessment import criteria_template,validate_criteria,review_template,validate_review
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
BASE=ROOT/'experiments/hardware/l4_20261028';WORK=BASE/'scheduler_assessment_036'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
source=Bundle(BASE/'challenges_v2_001','d7243e5159c79fc0e704dcf693453a44af0393e25cda924cedb6d40f37f121db')
audit=Bundle(BASE/'scheduler_bounds_035','264f2d82a58bb0ac374b4c60277e377d423023cd9e3aeac27a5af304c72be7f2')
for name,expected in read(WORK/'artifact_manifest.json')['files'].items():assert sha(WORK/name)==expected
packet=read(WORK/'PACKET.json');criteria=read(WORK/'CRITERIA.json');review=read(WORK/'REVIEW_INPUT.json')
assert criteria==criteria_template(packet) and review==review_template(packet,criteria)==read(WORK/'REVIEW_TEMPLATE.json')
assert validate_criteria(criteria,packet)==read(WORK/'CRITERIA_VALIDATION.json')
assert validate_review(review,packet,criteria)==read(WORK/'REVIEW_VALIDATION.json')
assert len(packet['cases'])==96 and len(packet['catalog'])==3932
assert all(row['value'] is None for row in criteria['scientific_limits'].values())
assert criteria['decision_provenance']['author'] is None and review['assessor_id'] is None
assert review['blinded_to_predictions_and_policy'] is None and all(c['outcome'] is None for c in review['cases'])
for record in packet['catalog'].values():ReferenceArtifact.from_dict(record['artifact']).verify_content(source.root)
for case in packet['cases']:
 checkpoint=source.json(case['job_id']+'/RESULT.json')['cleanup']['completed_at_ns']
 assert case['artifact_availability_upper_bound_ns']==checkpoint
 for aid in case['allowed_artifact_ids']:
  artifact=packet['catalog'][aid]['artifact']
  assert artifact['path'].startswith(case['job_id']+'/')
  assert artifact['acquisition']['available_at_ns']==checkpoint
  assert artifact['acquisition']['clock_domain']==case['interval']['clock_domain']
assert not packet['reference_export_enabled'] and packet['references_locked']==0
prior=read(ROOT/'experiments/examples/scheduler_bound_audit/validation/SOURCE_MANIFEST.json')['files']
for name,expected in prior.items():assert sha(ROOT/name)==expected,('Earlier source changed',name)
assert (BASE/'CHALLENGES_V2_VALIDATION.json').read_bytes()==(ROOT/'experiments/examples/quiet_evidence_isolation/validation/live_campaign_reaudit.log').read_bytes()
for name,expected in read(BASE/'challenges_v2_quiet_provenance_034/artifact_manifest.json')['files'].items():assert sha(BASE/'challenges_v2_quiet_provenance_034'/name)==expected
archive_entries=[]
for folder,archive,expected,descriptor in [
 ('challenge_runner','source_step030.tar.gz','c4bc872cb5eb0fe583e29ab94bef6c7afd466f482a80dd77b1a93bb0b18fa747','07f3bc3270ff5a404569a318c8ca320f7ebad14b1f23b9250716a40a138615d9'),
 ('event_challenges_v2','source_step032.tar.gz','a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51','60587c553e979b1103497f10685241dbfe282980565e19b723bfc59cf8972ec9')]:
 snapshot=ROOT/'experiments/examples'/folder/'snapshot_001';freeze=read(snapshot/'FREEZE.json')
 assert sha(snapshot/archive)==expected and sha(snapshot/'FREEZE.json')==descriptor
 with tarfile.open(snapshot/archive) as tar:
  for name,value in freeze['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==value
 archive_entries.append(len(freeze['files']))
for directory,expected in [('challenges_031_deployment','8686b5b489dc6edb350a08a929a4845bacd2155f9bb0e29f2e204c7eaa14d40e'),
                           ('challenges_v2_033_deployment','90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54')]:assert sha(BASE/directory/'results_backup.tar.gz')==expected
failed=BASE/'challenges_001'
for name,value in read(failed/'artifact_manifest.json')['files'].items():assert sha(failed/name)==value
assert read(failed/'RESULT.json')['status']=='failed' and read(failed/'RESULT.json')['selection'] is None
suite=(OUT/'cpu_suite.log').read_text();assert re.search(r'Ran 597 tests in ',suite)
full_passed=suite.rstrip().endswith('OK')
new_passed=len(re.findall(r'\(test_scheduler_assessment\.[^\n]+\) \.\.\. ok',suite))
assert new_passed==18
failures=re.search(r'failures=(\d+)',suite);errors=re.search(r'errors=(\d+)',suite)
for name,count in [('focused_tests.log',34),('older_timing_checks_isolated.log',6)]:
 text=(OUT/name).read_text();assert re.search(r'Ran '+str(count)+r' tests in ',text) and text.rstrip().endswith('OK')
assert 'FAILED (failures=5, errors=1)' in (OUT/'cpu_suite_initial_failed.log').read_text()
current={}
for folder in ('experiments/tracing','experiments/feasibility','experiments/evaluation','experiments/scripts','experiments/tests'):
 for path in sorted((ROOT/folder).glob('*.py')):
  ast.parse(path.read_text(),filename=str(path));current[str(path.relative_to(ROOT))]=sha(path)
for path in sorted((ROOT/'experiments/configs').glob('*.json')):current[str(path.relative_to(ROOT))]=sha(path)
version=digest(current)
(OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(dict(version='CPU_working_source_manifest_step036',files=current,
 source_version_sha256=version,CPU_tests_run=597,CPU_suite_passed=full_passed,new_tests=18,
 hardware_validated=False,engineering_archive_created=False,study_ready=False),indent=2)+'\n')
documents=['CAIN_REVISION_PLAN.md','experiments/PROGRESS.md','experiments/README.md','experiments/protocol/SCHEDULER_BOUND_ASSESSMENT.md',
 'experiments/protocol/SCHEDULER_ASSESSMENT_WORKFLOW.md','experiments/progress/036_scientific_criteria_and_assessment_workflow.md',
 'experiments/examples/scheduler_assessment/REPORT.md']
links=0
for name in documents:
 path=ROOT/name;text=path.read_text();assert all(l==l.rstrip() for l in text.splitlines()),name
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
  target=target.strip('<>').split('#')[0]
  if not target or re.match(r'[a-zA-Z]+:',target):continue
  resolved=(path.parent/target).resolve();assert resolved.exists() or resolved==OUT/'CHECKS.json',(name,target)
  links+=1
for path in OUT.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
checks=dict(artifact_and_workflow_checks_passed=True,full_CPU_suite_passed=full_passed,CPU_tests_run=597,new_tests=18,
 new_tests_passed_in_full_run=new_passed,full_suite_failures=0 if failures is None else int(failures[1]),
 full_suite_errors=0 if errors is None else int(errors[1]),
 focused_tests_passed=34,older_timing_checks_passed_in_isolation=6,initial_full_failure_log_and_host_load_retained=True,
 prior_source_files_unchanged=len(prior),runtime_or_test_guards_changed=False,GPU_used=False,SSH_used=False,
 campaign_artifacts_verified=len(source.files),audit_artifacts_verified=len(audit.files),catalog_artifacts_verified=3932,
 cases=96,actual_scientific_values_left_null=14,actual_assessor_input_supplied=False,
 criteria_and_review_remain_blocked=True,old_archive_entries_verified=archive_entries,
 original_archives_backups_and_v1_failure_preserved=True,original_live_validation_and_prior_index_unchanged=True,
 packet_sha256=digest(packet),criteria_sha256=digest(criteria),source_version_sha256=version,
 source_files=len(current),local_links_checked=links,syntax_and_whitespace_passed=True,
 references_created=0,references_locked=0,calibration_enabled=False,new_engineering_snapshot_created=False,
 study_ready=False,protocol_frozen=False,document_sha256={name:sha(ROOT/name) for name in documents})
(OUT/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
example=OUT.parent
(example/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(example)):sha(p) for p in sorted(example.rglob('*'))
 if p.is_file() and '__pycache__' not in p.parts and p!=example/'artifact_manifest.json'}),indent=2)+'\n')
print(json.dumps(checks,indent=2))
