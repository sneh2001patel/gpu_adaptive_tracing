"""Finalize this CPU-only source/artifact/document record outside frozen outputs."""
import ast,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
source={}
for folder in ('revision/tracing','revision/feasibility','revision/evaluation','revision/scripts','revision/tests'):
    for path in sorted((ROOT/folder).glob('*.py')):
        ast.parse(path.read_text(),filename=str(path));source[str(path.relative_to(ROOT))]=sha(path)
for path in sorted((ROOT/'revision/configs').glob('*.json')):source[str(path.relative_to(ROOT))]=sha(path)
version=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
preservation=read(OUT/'PRESERVATION.json');assert preservation['audit_passed']
assert preservation['working_activity_sha256']==source['revision/feasibility/activity.py']
manifest=dict(version='CPU_working_source_manifest_step034',source_version_sha256=version,files=source,
    parent_engineering_archive_sha256='a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51',
    CPU_tests_passed=565,new_tests=16,hardware_validated=False,engineering_archive_created=False,study_ready=False,protocol_frozen=False)
(OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name,count in [('focused_tests.log',33),('cpu_suite.log',565)]:
    text=(OUT/name).read_text();assert re.search(r'Ran '+str(count)+r' tests in ',text) and text.rstrip().endswith('OK')
base=ROOT/'revision/hardware/l4_20261028';index_dir=base/'challenges_v2_quiet_provenance_034'
index=read(index_dir/'INDEX.json')
for name,expected in read(index_dir/'artifact_manifest.json')['files'].items():assert sha(index_dir/name)==expected
assert index['campaign_manifest_sha256']==sha(base/'challenges_v2_001/artifact_manifest.json')
assert (index['jobs'],index['unique_barriers'],index['observed_rows'],index['historical_rows'])==(16,64,544,480)
assert all(j['own_rows']==4 for j in index['per_job'])
documents=['CAIN_REVISION_PLAN.md','revision/PROGRESS.md','revision/README.md','revision/protocol/SERVER_EVENT_INSTRUMENTATION.md',
    'revision/progress/034_quiet_evidence_isolation_and_provenance.md','revision/examples/quiet_evidence_isolation/REPORT.md']
links=0
for name in documents:
    path=ROOT/name;text=path.read_text();assert all(line==line.rstrip() for line in text.splitlines()),name
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
        target=target.strip('<>').split('#')[0]
        if not target or re.match(r'[a-zA-Z]+:',target):continue
        assert (path.parent/target).exists(),(name,target)
        links+=1
for path in OUT.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
checks=dict(checks_passed=True,CPU_tests_passed=565,new_tests=16,focused_tests_passed=33,GPU_used=False,SSH_used=False,
    local_links_checked=links,source_version_sha256=version,source_files=len(source),
    syntax_and_whitespace_passed=True,original_live_audit_reproduced_without_write=True,
    original_archives_and_backups_preserved=True,new_snapshot_created=False,hardware_validation_of_fix=False,
    provenance_index_sha256=sha(index_dir/'INDEX.json'),
    initial_reproduction_harness_error_retained=True,expected_frozen_regression_failure_verified=True,
    document_sha256={name:sha(ROOT/name) for name in documents})
(OUT/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
example=OUT.parent
(example/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(example)):sha(p) for p in sorted(example.rglob('*'))
    if p.is_file() and '__pycache__' not in p.parts and p!=example/'artifact_manifest.json'}),indent=2)+'\n')
print(json.dumps(checks,indent=2))
