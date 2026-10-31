"""Immutable, hashed offered requests; no evaluator labels or GPU dependencies."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from experiments.tracing.measured_evidence import fields_only, integer, identity, finite

VERSION='offered_arrivals_v1'


def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


def validate_payload(payload):
    required={'model','prompt','max_tokens','stream'}
    optional={'temperature','seed','ignore_eos'}
    if type(payload) is not dict or not required <= set(payload) or set(payload)-required-optional:
        raise ValueError('Only declared completion request fields are allowed')
    identity(payload['model'],'model');identity(payload['prompt'],'actual prompt text')
    integer(payload['max_tokens'],'max_tokens',1)
    if payload['stream'] is not False:raise ValueError('Only finite nonstreaming requests supported')
    if 'temperature' in payload:finite(payload['temperature'],'temperature')
    if 'seed' in payload:integer(payload['seed'],'seed')
    if 'ignore_eos' in payload and type(payload['ignore_eos']) is not bool:
        raise ValueError('ignore_eos must be boolean')


@dataclass(frozen=True)
class OfferedRequest:
    request_id: str
    offset_ns: int
    payload_json: str

    def __post_init__(self):
        identity(self.request_id,'request_id');integer(self.offset_ns,'offset_ns')
        payload=json.loads(self.payload_json,object_pairs_hook=unique_object)
        validate_payload(payload)
        if canonical(payload).decode() != self.payload_json:
            raise ValueError('Request payload must use canonical immutable JSON')

    @property
    def payload(self):
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class ArrivalSchedule:
    duration_ns: int
    requests: tuple[OfferedRequest,...]
    file_sha256: str
    content_sha256: str

    def __post_init__(self):
        integer(self.duration_ns,'duration_ns',1)
        if type(self.requests) is not tuple or any(type(r) is not OfferedRequest for r in self.requests):
            raise ValueError('Typed immutable offered requests required')
        if len({r.request_id for r in self.requests}) != len(self.requests):
            raise ValueError('Duplicate offered request ID')
        offsets=[r.offset_ns for r in self.requests]
        if offsets != sorted(offsets) or any(t>=self.duration_ns for t in offsets):
            raise ValueError('Arrivals must be ordered and inside the half-open horizon')
        if self.content_sha256 != hashlib.sha256(canonical(self.as_dict())).hexdigest():
            raise ValueError('Schedule content hash mismatch')
        if not isinstance(self.file_sha256,str) or len(self.file_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.file_sha256):
            raise ValueError('Raw file SHA-256 required')

    def as_dict(self):
        return dict(version=VERSION,duration_ns=self.duration_ns,requests=[
            dict(request_id=r.request_id,offset_ns=r.offset_ns,payload=r.payload) for r in self.requests])

    @classmethod
    def from_bytes(cls,raw):
        if type(raw) is not bytes:raise ValueError('Exact file bytes required')
        data=json.loads(raw,object_pairs_hook=unique_object)
        fields_only(data,{'version','duration_ns','requests'})
        if data['version']!=VERSION or type(data['requests']) is not list:
            raise ValueError('Unsupported schedule version/requests')
        requests=[]
        for row in data['requests']:
            fields_only(row,{'request_id','offset_ns','payload'})
            validate_payload(row['payload'])
            requests.append(OfferedRequest(row['request_id'],row['offset_ns'],canonical(row['payload']).decode()))
        return cls(data['duration_ns'],tuple(requests),hashlib.sha256(raw).hexdigest(),
                   hashlib.sha256(canonical(data)).hexdigest())

    @classmethod
    def load(cls,path):
        return cls.from_bytes(Path(path).read_bytes())
