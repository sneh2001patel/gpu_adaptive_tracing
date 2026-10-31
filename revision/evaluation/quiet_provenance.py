"""Resolve cumulative historical quiet rows without rewriting campaign evidence."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from revision.feasibility.metrics import inspect
from revision.tracing.live_features import ServingBinding
from revision.tracing.worker_barrier import validate_barrier


def digest(raw):return hashlib.sha256(raw).hexdigest()


def build_index(campaign):
    campaign=Path(campaign).resolve()
    manifest_raw=(campaign/'artifact_manifest.json').read_bytes()
    files=json.loads(manifest_raw)['files'];verified={}
    for name,expected in files.items():
        path=Path(name);full=campaign/path
        if path.is_absolute() or '..' in path.parts or full.is_symlink() or not full.resolve().is_relative_to(campaign):
            raise ValueError('Unsafe campaign artifact path')
        raw=full.read_bytes()
        if digest(raw)!=expected:raise ValueError('Campaign artifact hash mismatch: '+name)
        verified[name]=expected
    def load(name):
        if name not in verified:raise ValueError('Unmanifested provenance input: '+name)
        raw=(campaign/name).read_bytes()
        if digest(raw)!=verified[name]:raise ValueError('Provenance input changed during audit')
        return raw
    origins={};jobs={}
    for name in sorted(files):
        parts=Path(name).parts
        if len(parts)!=2 or parts[-1]!='binding.json':continue
        binding=ServingBinding(**json.loads(load(name)));job=parts[0]
        key=(binding.session_nonce,binding.generation,binding.worker_pid)
        if key in origins:raise ValueError('Ambiguous original session binding')
        origins[key]=(job,binding);jobs[job]=binding
    if not jobs:raise ValueError('No bound jobs to index')
    barriers={};occurrences=[];own_tokens=set();per_job=[]
    for job in sorted(jobs):
        source=job+'/quiet_evidence.json';rows=json.loads(load(source));counts=Counter()
        for index,row in enumerate(rows):
            command=row['barrier_command'];receipt=row['barrier_receipt'];token=command['token']
            if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):
                raise ValueError('Invalid barrier token')
            key=(command['session_nonce'],command['generation'],receipt['pid'])
            if key not in origins:raise ValueError('Missing original quiet-evidence job')
            origin,binding=origins[key]
            if command['clock_domain']!=binding.clock_domain:raise ValueError('Foreign original clock domain')
            validate_barrier(receipt,command,pid=binding.worker_pid,device_uuid=binding.device_uuid,
                received_at_ns=row['barrier_received_at_ns'])
            if (row['owned_client_outstanding']!=0 or not
                row['requested_at_ns']<=row['before_received_at_ns']<=command['requested_at_ns']<=
                row['barrier_received_at_ns']<=row['observed_at_ns']):
                raise ValueError('Invalid quiet-evidence acquisition or outstanding work')
            raw_files={}
            for side in ('before','after'):
                name=row[side+'_path']
                if not isinstance(name,str) or Path(name).name!=name or '\\' in name or name in ('.','..'):
                    raise ValueError('Quiet metric path must be an original-job basename')
                relative=origin+'/'+name;raw=load(relative)
                if digest(raw)!=row[side+'_sha256']:raise ValueError('Original quiet metric hash mismatch')
                gauges=inspect(raw,model=binding.model,engine=binding.engine)['gauges']
                if not all(g['available'] and g['value']==0 for g in gauges.values()):
                    raise ValueError('Original quiet gauges unavailable or nonzero')
                raw_files[side]=dict(path=relative,sha256=digest(raw))
            row_sha=digest(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
            if token in barriers and barriers[token]['row_sha256']!=row_sha:
                raise ValueError('Conflicting repeated quiet row')
            if token not in barriers:
                barriers[token]=dict(token=token,origin_job=origin,binding=asdict(binding),row_sha256=row_sha,
                    raw_files=raw_files,original_quiet_file=origin+'/quiet_evidence.json',original_row_index=None)
            historical=origin!=job;counts['historical' if historical else 'own']+=1
            if not historical:
                if token in own_tokens:raise ValueError('Repeated original barrier token')
                own_tokens.add(token);barriers[token]['original_row_index']=index
            occurrences.append(dict(observed_file=source,row_index=index,token=token,origin_job=origin,
                historical=historical,row_sha256=row_sha))
        per_job.append(dict(job_id=job,quiet_file=source,quiet_file_sha256=verified[source],
            own_rows=counts['own'],historical_rows=counts['historical'],total_rows=len(rows)))
    if set(barriers)!=own_tokens:raise ValueError('Historical row has no identical original occurrence')
    return dict(version='quiet_evidence_provenance_index_v1',
        processing_mode='offline_index_of_unchanged_campaign_bytes',GPU_used=False,
        campaign_manifest_sha256=digest(manifest_raw),campaign_artifact_hashes_verified=len(files),
        jobs=len(jobs),unique_barriers=len(barriers),observed_rows=len(occurrences),
        historical_rows=sum(o['historical'] for o in occurrences),
        original_files_rewritten=False,per_job_files_self_contained=not any(o['historical'] for o in occurrences),
        references_created=0,study_ready=False,protocol_frozen=False,
        per_job=per_job,barriers=sorted(barriers.values(),key=lambda b:b['token']),occurrences=occurrences)
