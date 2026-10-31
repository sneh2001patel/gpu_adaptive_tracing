"""Derive the diagnosis-rule thresholds from calibration sessions (CALIBRATION_PLAN.md §4, author-approved rules).

Reads only <root>/<seed>/<unit>/ as written by queue_calibration.sh:
  controlled/  baseline/ + baseline.json (healthy) and one directory per controlled condition (ctl_*)
  <case>/      baseline/ + baseline.json (fixed side, healthy rate) and incident/ (fixed side, incident schedule)
No bug-side session exists under the root, and none is read.

Prints a JSON report (each θ with its rule, inputs and margin; the θ_r option chain; leave-one-out ranges) and,
with --out, writes the thresholds file. Standard library only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

RATIO_CEILING, MULTIPLIER = 2.0, 1.25  # §4, approved 2026-10-29
INTERVENTION = {'ctl_lull': [(60, 120), (150, 210)]}  # every other condition: [(60, 180)]
HOST_STALL = 'ctl_engine_stall'  # the §4 "host-stall" condition (per-step stall in the engine loop)
DEFAULT_PHASE = [(60, 180)]


def quantile(values, q):
    s = sorted(values)
    if not s:
        return None
    pos = q * (len(s) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def median(values):
    return quantile(values, 0.5)


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).is_file() else []


def load(root):
    """Sessions as dicts: seed, unit, condition, kind ('healthy' | 'condition'), windows, bursts, baseline."""
    sessions = []
    for seed_dir in sorted(p for p in Path(root).iterdir() if p.is_dir() and p.name.isdigit()):
        for unit_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
            base_file = unit_dir / 'baseline.json'
            if not base_file.is_file():
                continue
            baseline = json.loads(base_file.read_text())
            p95_base = baseline.get('p95_base_s')
            events = read_jsonl(unit_dir / 'baseline' / 'events.jsonl')
            horizon = max((e['t'] for e in events if e.get('kind') == 'window'), default=0)
            healthy = [dict(e['cheap'], latency_ratio=(e['inflight_p95_s'] / p95_base
                                                      if e.get('inflight_p95_s') is not None and p95_base else None))
                       for e in events if e.get('kind') == 'window' and e['t'] >= 0.25 * horizon]
            sessions.append(dict(seed=seed_dir.name, unit=unit_dir.name, condition='healthy', kind='healthy',
                                 windows=healthy, bursts=[], baseline=baseline))
            # Only session directories: a replaced baseline kept beside them (baseline_idle_capture) is not one.
            wanted = (lambda n: n.startswith('ctl_')) if unit_dir.name == 'controlled' else (lambda n: n == 'incident')
            for cond_dir in sorted(p for p in unit_dir.iterdir() if p.is_dir() and wanted(p.name)):
                condition = cond_dir.name if unit_dir.name == 'controlled' else f'{unit_dir.name}:incident'
                phases = INTERVENTION.get(cond_dir.name, DEFAULT_PHASE)
                # L is recomputed from the raw in-flight age and the final baseline file: a baseline rerun after
                # the session (vllm#7619 seed 101) must not leave ratios computed against the replaced baseline.
                windows = [dict(e['cheap'], latency_ratio=(e['inflight_p95_s'] / p95_base
                                                           if e.get('inflight_p95_s') is not None and p95_base else None))
                           for e in read_jsonl(cond_dir / 'events.jsonl')
                           if e.get('kind') == 'window' and any(lo <= e['t'] < hi for lo, hi in phases)]
                bursts = [b for b in read_jsonl(cond_dir / 'bursts.jsonl')
                          if b['capture_id'].startswith('cal') and b.get('activity')]
                sessions.append(dict(seed=seed_dir.name, unit=unit_dir.name, condition=condition, kind='condition',
                                     windows=windows, bursts=bursts, baseline=baseline))
    return sessions


def values(sessions, measure, *, kind=None, condition=None):
    return [w[measure] for s in sessions if (kind is None or s['kind'] == kind)
            and (condition is None or s['condition'] == condition) for w in s['windows'] if w.get(measure) is not None]


def burst_values(sessions, measure, condition):
    return [b['activity'][measure] for s in sessions if s['condition'] == condition for b in s['bursts']
            if b['activity'].get(measure) is not None]


def family_ratios(per_token, base):
    """Ratio per family present in both (families missing from the baseline are skipped, as in the rule)."""
    if not per_token or not base:
        return {}
    return {f: v / base[f] for f, v in per_token.items() if base.get(f)}


def kernel_options(sessions):
    """θ_r ordered fallback (§4). Returns the chain with every option's value and whether it qualifies."""
    conds = [s for s in sessions if s['kind'] == 'condition']
    # Option 1: each burst against the healthy baseline of the same seed and unit.
    opt1 = [r for s in conds for b in s['bursts']
            for r in family_ratios(b['activity'].get('family_ns_per_token'), s['baseline'].get('baseline_ns_per_token')).values()]
    # Option 2: load-matched. Burst k of a session against the per-family median of burst k in the other seeds'
    # sessions of the same unit and condition (leave-one-seed-out, same schedule time). Bursts are matched by
    # capture id (cal00075 = 75 s), not position: a burst with no activity is dropped and would shift the rest.
    opt2, by_family = [], {}
    for s in conds:
        peers = [p for p in conds if p['unit'] == s['unit'] and p['condition'] == s['condition'] and p['seed'] != s['seed']]
        for b in s['bursts']:
            mine = b['activity'].get('family_ns_per_token') or {}
            peer_k = [pb['activity'].get('family_ns_per_token') or {} for p in peers for pb in p['bursts']
                      if pb['capture_id'] == b['capture_id']]
            ref = {f: median([pk[f] for pk in peer_k if pk.get(f)]) for f in mine}
            for f, r in family_ratios(mine, {f: v for f, v in ref.items() if v}).items():
                opt2.append(r)
                by_family.setdefault(f, []).append(r)
    chain = []
    for name, ratios in (('healthy_load_baseline', opt1), ('load_matched_baseline', opt2)):
        theta = MULTIPLIER * max(ratios) if ratios else None
        chain.append(dict(option=name, theta=theta, max_ratio=max(ratios) if ratios else None, n_ratios=len(ratios),
                          qualifies=theta is not None and theta <= RATIO_CEILING))
    per_family = {f: MULTIPLIER * max(r) for f, r in by_family.items()}
    chain.append(dict(option='per_family_load_matched', theta=per_family,
                      qualifies=bool(per_family) and all(v <= RATIO_CEILING for v in per_family.values())))
    chosen = next((c for c in chain if c['qualifies']), None)
    return dict(chain=chain, chosen=chosen['option'] if chosen else 'not_separable',
                theta=chosen['theta'] if chosen else per_family)


def derive(sessions):
    h = dict(kind='healthy')
    L_h, w_h, u_h, p_h = (quantile(values(sessions, m, **h), 0.99)
                          for m in ('latency_ratio', 'waiting_requests', 'kv_usage', 'preemptions_per_s'))
    L_over, w_over, g_over = (median(values(sessions, m, condition='ctl_overload'))
                              for m in ('latency_ratio', 'waiting_requests', 'gpu_util'))
    u_kv, p_kv = (median(values(sessions, m, condition='ctl_kv')) for m in ('kv_usage', 'preemptions_per_s'))
    g_stall = median(values(sessions, 'gpu_util', condition=HOST_STALL))
    b_stall, b_over = (median(burst_values(sessions, 'busy_fraction', c)) for c in (HOST_STALL, 'ctl_overload'))

    def mid(a, b):
        return None if a is None or b is None else (a + b) / 2

    def ratio(a, b):
        return None if a is None or not b else a / b
    t = {}
    t['latency_ratio'] = None if L_h is None else math.ceil(L_h / 0.05 - 1e-9) * 0.05
    t['waiting_requests'] = None if w_h is None else w_h + 1
    t['kv_usage'] = mid(u_h, u_kv)
    t['preemptions_per_s'] = None if p_h is None else max(p_h, 0.5)
    t['gpu_util'] = mid(g_stall, g_over)
    t['busy_fraction'] = mid(b_stall, b_over)
    kernel = kernel_options(sessions)
    t['kernel_time_ratio'] = kernel['theta']
    inputs = dict(healthy_p99=dict(latency_ratio=L_h, waiting_requests=w_h, kv_usage=u_h, preemptions_per_s=p_h),
                  overload_median=dict(latency_ratio=L_over, waiting_requests=w_over, gpu_util=g_over, busy_fraction=b_over),
                  kv_median=dict(kv_usage=u_kv, preemptions_per_s=p_kv),
                  host_stall_median=dict(gpu_util=g_stall, busy_fraction=b_stall))
    margins = dict(
        latency_ratio=ratio(L_over, t['latency_ratio']), waiting_requests=ratio(w_over, t['waiting_requests']),
        kv_usage=None if None in (u_kv, u_h) or not t['kv_usage'] else (u_kv - u_h) / t['kv_usage'],
        preemptions_per_s=ratio(p_kv, t['preemptions_per_s']),
        gpu_util=None if None in (g_over, g_stall) else g_over - g_stall,      # negative: not separable
        busy_fraction=None if None in (b_over, b_stall) else b_over - b_stall)
    return dict(thresholds=t, inputs=inputs, margins=margins, kernel=kernel)


def leave_one_out(sessions):
    """Range of each θ when one real case's fixed-side data, or one controlled condition, is left out (§4)."""
    real_units = sorted({s['unit'] for s in sessions if s['unit'] != 'controlled'})
    controlled = sorted({s['condition'] for s in sessions if s['unit'] == 'controlled' and s['kind'] == 'condition'})
    runs = {f'without_case_{u}': [s for s in sessions if s['unit'] != u] for u in real_units}
    runs.update({f'without_{c}': [s for s in sessions if not (s['unit'] == 'controlled' and s['condition'] == c)]
                 for c in controlled})
    results = {name: derive(subset)['thresholds'] for name, subset in runs.items()}
    ranges = {}
    for key in ('latency_ratio', 'waiting_requests', 'kv_usage', 'preemptions_per_s', 'gpu_util', 'busy_fraction',
                'kernel_time_ratio'):
        vals = [r[key] for r in results.values() if isinstance(r[key], (int, float))]
        ranges[key] = [min(vals), max(vals)] if vals else None
    return dict(ranges=ranges, runs=results)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', help='calibration directory (seeds 101-103)')
    p.add_argument('--out', help='write the thresholds JSON here')
    p.add_argument('--version', default='study_rule_v2_calibrated')
    args = p.parse_args()
    sessions = load(args.root)
    result = derive(sessions)
    result['sessions'] = sorted({(s['seed'], s['unit'], s['condition']) for s in sessions})
    result['leave_one_out'] = leave_one_out(sessions)
    if args.out:
        t = {k: round(v, 4) for k, v in result['thresholds'].items() if k != 'kernel_time_ratio'}
        # §4 option 4 (approved 2026-10-29): kernel_hotspot not separable from load, so it never fires. ∞ keeps the
        # comparison defined (None would make every burst "unknown") and the config complete for RuleThresholds.frozen.
        not_separable = result['kernel']['chosen'] == 'not_separable'
        t['kernel_time_ratio'] = math.inf if not_separable else round(result['thresholds']['kernel_time_ratio'], 4)
        t['version'] = args.version
        text = json.dumps(t, indent=1)  # ∞ is written as Infinity, which Python's json reads back
        Path(args.out).write_text(text)
        digest = hashlib.sha256(json.dumps(json.loads(text), sort_keys=True).encode()).hexdigest()  # = RuleThresholds.digest
        Path(args.out).with_suffix('.sha256').write_text(digest + '\n')
        result['frozen'] = dict(file=args.out, digest=digest, kernel_hotspot_not_separable=not_separable)
    print(json.dumps(result, indent=1, default=str))


if __name__ == '__main__':
    main()
