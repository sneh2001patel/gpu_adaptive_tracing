"""Summarize run_episode.py session directories: episode outcome, bursts, diagnoses and cheap signals."""
import json
import sys
from collections import Counter
from pathlib import Path


def summarize(d):
    d = Path(d)
    s = json.loads((d / 'summary.json').read_text())
    ev = [json.loads(l) for l in (d / 'events.jsonl').read_text().splitlines() if l.strip()]
    win = [e for e in ev if e.get('kind') == 'window']
    bur = [e for e in ev if e.get('kind') == 'burst']
    req = [json.loads(l) for l in (d / 'requests.jsonl').read_text().splitlines() if l.strip()]
    start = next((e for e in win if e.get('episode_started')), None)
    ep = s.get('episode') or {}
    lat = [e['cheap']['latency_ratio'] for e in win if e['cheap']['latency_ratio'] is not None]
    gpu = [e['cheap']['gpu_util'] for e in win if e['cheap']['gpu_util'] is not None]
    return dict(
        session=d.name, error=s.get('error'), requests=s.get('requests'),
        episode_start_t=start and round(start['t'], 1),
        stop_reason=(ep.get('decision') or {}).get('reason'), stop_label=(ep.get('decision') or {}).get('diagnosis_label'),
        bursts=[dict(id=b['capture_id'], t=round(b['t'], 1), failure=b['failure'], dx=b['heavy_diagnosis'],
                     kernel=b['kernel'], decision=b['decision']['reason']) for b in bur],
        cheap_dx_active=Counter(e['cheap_diagnosis'] for e in win if e['state'] == 'active').most_common(5),
        max_latency_ratio=round(max(lat), 2) if lat else None,
        max_waiting=max((e['cheap']['waiting_requests'] or 0) for e in win),
        gpu_util_mean=round(sum(gpu) / len(gpu), 3) if gpu else None,
        p95_latency_s=round(sorted(r['latency_s'] for r in req if r['ok'])[int(0.95 * sum(r['ok'] for r in req))], 2) if req else None)


if __name__ == '__main__':
    for d in sys.argv[1:]:
        print(json.dumps(summarize(d), indent=1))
