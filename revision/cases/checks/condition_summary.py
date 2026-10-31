"""Per-condition summary of calibration or pre-run sessions (intervention-phase medians of each rule input, burst
busy fraction and per-family per-token ratio against the same seed's healthy baseline). Calibration data only."""
import json
import sys

import derive_thresholds as dt

for s in dt.load(sys.argv[1]):
    row = {m: dt.median([w[m] for w in s['windows'] if w.get(m) is not None])
           for m in ('latency_ratio', 'waiting_requests', 'running_requests', 'kv_usage', 'preemptions_per_s', 'gpu_util')}
    base = s['baseline'].get('baseline_ns_per_token')
    ratios = [dt.family_ratios(b['activity'].get('family_ns_per_token'), base) for b in s['bursts']]
    print(json.dumps(dict(seed=s['seed'], unit=s['unit'], condition=s['condition'], windows=len(s['windows']),
                          **{k: None if v is None else round(v, 3) for k, v in row.items()},
                          bursts=len(s['bursts']),
                          busy=[round(b['activity']['busy_fraction'], 2) for b in s['bursts']],
                          ratios=[{f: round(v, 2) for f, v in r.items()} for r in ratios])))
