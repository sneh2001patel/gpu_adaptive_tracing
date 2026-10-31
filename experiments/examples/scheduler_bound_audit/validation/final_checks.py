"""Preservation and source/document fingerprints for the CPU-only step-035 audit."""
import ast,hashlib,json,re,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
BASE=ROOT/'experiments/hardware/l4_20261028';DERIVED=BASE/'scheduler_bounds_035'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
expected='d7243e5159c79fc0e704dcf693453a44af0393e25cda924cedb6d40f37f121db'
assert sha(BASE/'challenges_v2_001/artifact_manifest.json')==expected
for name,digest in read(DERIVED/'artifact_manifest.json')['files'].items():assert sha(DERIVED/name)==digest
audit=read(DERIVED/'AUDIT.json');summary=read(DERIVED/'SUMMARY.json');draft=read(DERIVED/'CRITERIA_DRAFT.json')
assert audit['summary']==summary and audit['campaign_manifest_sha256']==expected
assert summary['final_source_case_requests']==958 and summary['consumer_usable_bound_observations']==798
assert summary['raw_withheld_observations']==160 and summary['raw_ready_windows']==60
assert summary['consumer_bound_windows']==54 and summary['withheld_windows']==6
assert summary['probe_vs_window_end_unscheduled_mismatch_windows']==1
assert len(draft['scientific_limits'])==14 and all(v is None for v in draft['scientific_limits'].values())
assert draft['references_created']==0 and not draft['numerical_acceptance_established']
assert all(not w['classifier_feature_accepted'] and not w['existing_request_wait_p95_mapping_supported'] and w['diagnosis'] is None for j in audit['jobs'] for w in j['windows'])
assert (BASE/'CHALLENGES_V2_VALIDATION.json').read_bytes()==(ROOT/'experiments/examples/quiet_evidence_isolation/validation/live_campaign_reaudit.log').read_bytes()
prior_index=BASE/'challenges_v2_quiet_provenance_034'
for name,digest in read(prior_index/'artifact_manifest.json')['files'].items():assert sha(prior_index/name)==digest
counts=[]
for folder,archive,expected_archive,expected_descriptor in [
 ('challenge_runner','source_step030.tar.gz','c4bc872cb5eb0fe583e29ab94bef6c7afd466f482a80dd77b1a93bb0b18fa747','07f3bc3270ff5a404569a318c8ca320f7ebad14b1f23b9250716a40a138615d9'),
 ('event_challenges_v2','source_step032.tar.gz','a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51','60587c553e979b1103497f10685241dbfe282980565e19b723bfc59cf8972ec9')]:
 snapshot=ROOT/'experiments/examples'/folder/'snapshot_001';freeze=read(snapshot/'FREEZE.json')
 assert sha(snapshot/archive)==expected_archive and sha(snapshot/'FREEZE.json')==expected_descriptor
 with tarfile.open(snapshot/archive) as tar:
  for name,digest in freeze['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==digest
 counts.append(len(freeze['files']))
for directory,digest in [('challenges_031_deployment','8686b5b489dc6edb350a08a929a4845bacd2155f9bb0e29f2e204c7eaa14d40e'),
                         ('challenges_v2_033_deployment','90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54')]:assert sha(BASE/directory/'results_backup.tar.gz')==digest
failed=BASE/'challenges_001'
for name,digest in read(failed/'artifact_manifest.json')['files'].items():assert sha(failed/name)==digest
assert read(failed/'RESULT.json')['status']=='failed' and read(failed/'RESULT.json')['selection'] is None
for name,count in [('focused_tests.log',31),('cpu_suite.log',579),('older_fixture_corrected.log',1),('busy_reset_corrected.log',1)]:
 text=(OUT/name).read_text();assert re.search(r'Ran '+str(count)+r' tests? in ',text) and text.rstrip().endswith('OK')
assert 'FAILED (failures=1)' in (OUT/'cpu_suite_initial_failed.log').read_text()
assert 'FAILED (failures=1)' in (OUT/'older_fixture_isolated.log').read_text()
assert 'FAILED (failures=1)' in (OUT/'cpu_suite_second_failed.log').read_text()
source={}
for folder in ('experiments/tracing','experiments/feasibility','experiments/evaluation','experiments/scripts','experiments/tests'):
 for path in sorted((ROOT/folder).glob('*.py')):
  ast.parse(path.read_text(),filename=str(path));source[str(path.relative_to(ROOT))]=sha(path)
for path in sorted((ROOT/'experiments/configs').glob('*.json')):source[str(path.relative_to(ROOT))]=sha(path)
version=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
(OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(dict(version='CPU_working_source_manifest_step035',files=source,
 source_version_sha256=version,CPU_tests_passed=579,new_tests=14,hardware_validated=False,
 engineering_archive_created=False,study_ready=False,protocol_frozen=False),indent=2)+'\n')
documents=['CAIN_REVISION_PLAN.md','experiments/PROGRESS.md','experiments/README.md','experiments/protocol/SERVER_EVENT_INSTRUMENTATION.md',
 'experiments/protocol/SCHEDULER_BOUND_ASSESSMENT.md','experiments/progress/035_scheduler_bound_precision_and_cohort_audit.md',
 'experiments/examples/scheduler_bound_audit/REPORT.md']
links=0
for name in documents:
 path=ROOT/name;text=path.read_text();assert all(line==line.rstrip() for line in text.splitlines()),name
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
  target=target.strip('<>').split('#')[0]
  if not target or re.match(r'[a-zA-Z]+:',target):continue
  resolved=(path.parent/target).resolve()
  assert resolved.exists() or resolved==OUT/'CHECKS.json',(name,target)
  links+=1
for path in OUT.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
checks=dict(checks_passed=True,CPU_tests_passed=579,new_tests=14,focused_tests_passed=31,
 CPU_fixture_timing_windows_extended=2,initial_full_suite_and_isolated_failures_retained=True,
 live_GPU_guards_relaxed=False,GPU_used=False,SSH_used=False,artifact_hashes_verified=audit['artifact_hashes_verified'],
 original_live_validation_unchanged=True,original_source_snapshots_entries_verified=counts,
 original_backups_and_failed_v1_artifacts_unchanged=True,prior_provenance_index_unchanged=True,
 scientific_limits_left_null=14,source_version_sha256=version,source_files=len(source),
 local_links_checked=links,syntax_and_whitespace_passed=True,new_engineering_snapshot_created=False,
 references_created=0,calibration_enabled=False,study_ready=False,protocol_frozen=False,
 document_sha256={name:sha(ROOT/name) for name in documents})
(OUT/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
example=OUT.parent
(example/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(example)):sha(p) for p in sorted(example.rglob('*'))
 if p.is_file() and '__pycache__' not in p.parts and p!=example/'artifact_manifest.json'}),indent=2)+'\n')
print(json.dumps(checks,indent=2))
