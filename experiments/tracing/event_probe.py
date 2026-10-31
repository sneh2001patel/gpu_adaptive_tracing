"""Fixed idle RPC backed by the scheduler journal in the same interpreter/PID."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from experiments.tracing.server_events import atomic_json

_sources = {}


class EventSource:
    def __init__(self, directory, journal):
        self.directory = Path(directory).resolve()
        self.journal = journal
        self.pid = os.getpid()
        self.commands = {}
        self.lock = RLock()

    def publish(self):
        if os.getpid() != self.pid:
            raise ValueError('Event source inherited by a different process')
        with self.lock:
            command = json.loads((self.directory / 'probe_command.json').read_text())
            token = command.get('token')
            if isinstance(token, str) and token in self.commands:
                # The hook and idle RPC can see the same command. Return the
                # original receipt without inventing a newer source timestamp.
                if command != self.commands[token]:
                    raise ValueError('Consumed event token has a changed command')
                return token
            data = self.journal.probe(command)
            atomic_json(self.directory / ('snapshot-' + data['token'] + '.json'), data)
            self.commands[data['token']] = command
            return data['token']


def register_source(directory, journal):
    key = str(Path(directory).resolve())
    if key in _sources:
        raise ValueError('Scheduler event source already registered')
    source = EventSource(directory, journal)
    _sources[key] = source
    return source


def worker_probe(directory, *, pid, device_uuid, session_nonce, generation,
                 clock_domain, capture_active):
    if capture_active:
        raise ValueError('Event commissioning cannot run during capture')
    source = _sources.get(str(Path(directory).resolve()))
    if source is None:
        raise ValueError('No scheduler journal in the CUDA worker interpreter')
    binding = asdict(source.journal.binding)
    expected = dict(worker_pid=pid, device_uuid=device_uuid,
                    session_nonce=session_nonce, generation=generation,
                    clock_domain=clock_domain)
    if pid != os.getpid() or any(binding[k] != v for k, v in expected.items()):
        raise ValueError('Event source/worker identity mismatch')
    return source.publish()


def install_event_route(api_server):
    @api_server.router.post('/experiments/events/probe')
    async def probe(raw_request: api_server.Request):
        await api_server.engine_client(raw_request).collective_rpc('revision_event_probe', timeout=10)
        return api_server.Response(status_code=200)
    return probe
