"""Evaluator-only, content-addressed references with exclusive durable commits.

Readonly files and an independently retained lock digest make alteration
observable; this is not administrator-proof storage, proof of blinding or a
trusted clock. No prediction input is accepted during reference locking.
"""
from dataclasses import asdict, dataclass, replace
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from revision.evaluation.references import ReferenceRecord
from revision.tracing.arrival_schedule import canonical, unique_object
from revision.tracing.measured_evidence import fields_only, identity, integer

VERSION='locked_reference_set_v1'
MAX_BYTES=32*1024*1024
MAX_ARTIFACT_BYTES=2*1024*1024*1024


def sha(data):return hashlib.sha256(data).hexdigest()


def digest(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Expected lowercase SHA-256')
    return value


def read_regular(path):
    """No symlinks; bound bytes and read the same opened descriptor."""
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 0<meta.st_size<=MAX_BYTES:
            raise ValueError('Missing/empty/oversized/nonregular artifact')
        with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise ValueError('Artifact exceeds size limit')
        return data
    finally:os.close(fd)



def stream_artifact(path,sink=None):
    """Hash/copy raw evidence with bounded memory; metadata JSON stays small."""
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 0<meta.st_size<=MAX_ARTIFACT_BYTES:
            raise ValueError('Raw artifact size/type outside supported bounds')
        result=hashlib.sha256();size=0
        with os.fdopen(fd,'rb',closefd=False) as stream:
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_ARTIFACT_BYTES:raise ValueError('Raw artifact exceeds limit')
                result.update(chunk)
                if sink is not None:sink.write(chunk)
        if size!=meta.st_size:raise ValueError('Artifact size changed during snapshot')
        return result.hexdigest()
    finally:os.close(fd)


def fsync_directory(path):
    descriptor=os.open(path,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


@dataclass(frozen=True)
class LockedReferences:
    lock_sha256: str
    run_id: str
    provenance: str
    clock_domain: str
    locked_at_ns: int
    rubric_version: str
    records: tuple[ReferenceRecord,...]


class ReferenceStore:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        for name in ('blobs','locks'):
            path=self.root/name
            if path.is_symlink():raise ValueError('Store namespaces cannot be symlinks')
            path.mkdir(exist_ok=True)
        fsync_directory(self.root);fsync_directory(self.root.parent)

    def _read(self,namespace,expected):
        expected=digest(expected);directory=self.root/namespace
        if directory.is_symlink():raise ValueError('Store namespace changed into a symlink')
        data=read_regular(directory/expected)
        if sha(data)!=expected:raise ValueError('Stored content hash mismatch')
        return data

    def _put(self,namespace,data):
        if not 0<len(data)<=MAX_BYTES:raise ValueError('Stored object size outside limit')
        expected=sha(data);directory=self.root/namespace
        if directory.is_symlink():raise ValueError('Store namespace changed into a symlink')
        temporary=directory/('.pending-'+uuid.uuid4().hex)
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:
                stream.write(data);stream.flush();os.fsync(fd)
            os.fchmod(fd,0o444);os.fsync(fd)
            try:os.link(temporary,directory/expected)  # Atomic exclusive publication; never replace.
            except FileExistsError:
                if self._read(namespace,expected)!=data:raise ValueError('Existing object changed')
            fsync_directory(directory)
        finally:
            os.close(fd);temporary.unlink(missing_ok=True)
        return expected


    def _snapshot_artifact(self,path,expected):
        expected=digest(expected);directory=self.root/'blobs'
        if directory.is_symlink():raise ValueError('Store namespace changed into a symlink')
        temporary=directory/('.pending-'+uuid.uuid4().hex)
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as sink:
                actual=stream_artifact(path,sink)
                sink.flush();os.fsync(fd)
            if actual!=expected:raise ValueError('Reference artifact hash mismatch')
            os.fchmod(fd,0o444);os.fsync(fd)
            try:os.link(temporary,directory/expected)
            except FileExistsError:self._verify_artifact(expected)
            fsync_directory(directory)
        finally:os.close(fd);temporary.unlink(missing_ok=True)

    def _verify_artifact(self,expected):
        expected=digest(expected);directory=self.root/'blobs'
        if directory.is_symlink():raise ValueError('Store namespace changed into a symlink')
        if stream_artifact(directory/expected)!=expected:raise ValueError('Stored content hash mismatch')

    def _rubric(self,data):
        rubric=json.loads(data,object_pairs_hook=unique_object)
        fields_only(rubric,{'version','provenance','criterion_ids','description'})
        identity(rubric['version'],'rubric version');identity(rubric['description'],'rubric description')
        if type(rubric['criterion_ids']) is not list or not rubric['criterion_ids']:
            raise ValueError('Explicit rubric criteria required')
        for identifier in rubric['criterion_ids']:identity(identifier,'criterion ID')
        if len(set(rubric['criterion_ids']))!=len(rubric['criterion_ids']):raise ValueError('Duplicate rubric criterion')
        return rubric

    def lock(self,records,artifact_root,rubric_path,*,clock):
        """Verify/copy adjudicated evidence, then commit a new digest last.

        Caller supplies the actual same-domain evaluator clock. A synthetic clock
        is only appropriate for synthetic fixtures. No prediction is loaded here.
        """
        if not records or any(type(r) is not ReferenceRecord for r in records):
            raise ValueError('Nonempty typed adjudicated references required')
        records=tuple(sorted(records,key=lambda r:r.interval.start_ns));first=records[0]
        if any((r.run_id,r.provenance,r.interval.clock_domain,r.reference_version)!=(
                first.run_id,first.provenance,first.interval.clock_domain,first.reference_version) for r in records):
            raise ValueError('A lock covers exactly one run/provenance/domain/rubric')
        if clock.domain!=first.interval.clock_domain:raise ValueError('Evaluator clock has no mapping to reference domain')
        for previous,current in zip(records,records[1:]):
            if previous.interval.end_ns>current.interval.start_ns:raise ValueError('Overlapping reference intervals are ambiguous')
        rubric_bytes=read_regular(rubric_path);rubric=self._rubric(rubric_bytes)
        if (rubric['version'],rubric['provenance'])!=(first.reference_version,first.provenance):
            raise ValueError('Rubric version/provenance mismatch')
        root=Path(artifact_root).resolve();snapshots=[]
        for record in records:
            if record.locked_at_ns is not None:raise ValueError('Lock only unlocked adjudications; corrections create new records/lock')
            if record.adjudicated_at_ns>clock.now_ns():raise ValueError('Future adjudication')
            if any(c.criterion_id not in rubric['criterion_ids'] for c in record.criteria):raise ValueError('Criterion absent from frozen rubric')
            for artifact in record.artifacts:
                path=(root/artifact.path).resolve()
                if not path.is_relative_to(root) or (root/artifact.path).is_symlink():raise ValueError('Reference artifact path escapes/root symlink')
                self._snapshot_artifact(path,artifact.sha256)
            snapshots.append(record)
        rubric_hash=self._put('blobs',rubric_bytes)
        locked_at=clock.now_ns();integer(locked_at,'locked_at_ns')
        record_hashes=[self._put('blobs',canonical(asdict(replace(r,locked_at_ns=locked_at)))) for r in snapshots]
        manifest=dict(version=VERSION,run_id=first.run_id,provenance=first.provenance,clock_domain=clock.domain,
            locked_at_ns=locked_at,rubric_version=first.reference_version,rubric_sha256=rubric_hash,
            record_sha256=record_hashes,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        anchor=self._put('locks',canonical(manifest))
        self.load(anchor)  # An incomplete/invalid commit is never returned as accepted.
        return anchor

    def load(self,anchor):
        """Read only the requested digest, verifying every rubric/record/artifact."""
        manifest=json.loads(self._read('locks',anchor),object_pairs_hook=unique_object)
        fields_only(manifest,{'version','run_id','provenance','clock_domain','locked_at_ns','rubric_version',
            'rubric_sha256','record_sha256','created_utc'})
        if manifest['version']!=VERSION:raise ValueError('Unknown reference lock version')
        integer(manifest['locked_at_ns'],'locked_at_ns')
        if type(manifest['record_sha256']) is not list or not manifest['record_sha256']:
            raise ValueError('Lock has no reference records')
        if len(set(manifest['record_sha256']))!=len(manifest['record_sha256']):raise ValueError('Duplicate locked reference')
        rubric=self._rubric(self._read('blobs',manifest['rubric_sha256']))
        if (rubric['version'],rubric['provenance'])!=(manifest['rubric_version'],manifest['provenance']):
            raise ValueError('Locked rubric identity mismatch')
        records=[]
        for record_hash in manifest['record_sha256']:
            record=ReferenceRecord.from_dict(json.loads(self._read('blobs',record_hash),object_pairs_hook=unique_object))
            if (record.run_id,record.provenance,record.interval.clock_domain,record.reference_version,record.locked_at_ns)!=(
                    manifest['run_id'],manifest['provenance'],manifest['clock_domain'],manifest['rubric_version'],manifest['locked_at_ns']):
                raise ValueError('Locked reference metadata differs from manifest')
            if any(c.criterion_id not in rubric['criterion_ids'] for c in record.criteria):raise ValueError('Unfrozen criterion')
            for artifact in record.artifacts:self._verify_artifact(artifact.sha256)
            records.append(record)
        for previous,current in zip(records,records[1:]):
            if previous.interval.end_ns>current.interval.start_ns:raise ValueError('Overlapping/out-of-order locked references')
        return LockedReferences(anchor,manifest['run_id'],manifest['provenance'],manifest['clock_domain'],manifest['locked_at_ns'],
            manifest['rubric_version'],tuple(records))
