"""Proposal §10 step 8 analysis (EVALUATION_PLAN.md §3): blocks 201-203 under the frozen thresholds.

Reads every finished session (a `done` marker) under evaluation_hosts/<host>/evaluation/, scores each arm's initial stop
against the unit's reference (LOCKED_REFERENCE_SCORING.md outcomes), and writes the pre-declared comparisons:
  primary    SS, CR, HS each against FIX3, paired by (block, unit): bursts, profiler wall time, supported diagnosis,
             time from incident onset to a supported stop; cluster bootstrap over blocks, Wilcoxon + Holm, A12, Wilson
  secondary  NT (cheap label at the trigger) against FIX1 (RQ1); serving impact of each arm against U; per-unit outcomes
Scoring rules (pre-declared, EVALUATION_PLAN.md):
  - stop label and reference are cause sets ('+'); equal = supported_complete, proper subset = supported_partial,
    anything outside the reference = unsupported_concrete, no label = unresolved
  - horizon_ended, budget_exhausted, profiler_failed and evidence_missing stops are never scored as supported
  - #6240 and #7619: reference unreachable by the frozen rule -> reference_unavailable, outside the agreement denominator
  - ctl_shift: reference is queue_pressure before the shift (60 s into the incident) and prefill_heavy after; the rule has
    no prefill_heavy label, so evidence acquired after (or across) the shift is reference_unavailable, like #6240 and #7619
  - RQ1 scores cheap evidence with the rule in its in-episode mode (as every burst is scored): the window classifier
    logged online gates on theta_L (1.95) while the trigger fires at 1.5, so at the trigger it reports 'healthy' by
    construction. Both are reported; the logged label is `trigger_cheap_label`
  - times are measured from the episode trigger: units whose load runs from t = 0 (ctl_kv, the real cases) trigger before
    the scheduled onset, so onset is not a common origin
    python3 analyze_evaluation.py evaluation_hosts --out evaluation_analysis
"""
import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import case_workloads

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tracing'))  # hosts ran identical copies from ext/
from rule_diagnosis import CheapWindow, RuleThresholds, diagnose  # noqa: E402  (the frozen rule, as run online)

ARMS = ['U', 'NT', 'FIX1', 'FIX3', 'SS', 'CR', 'HS']
POLICIES = ['SS', 'CR', 'HS']
ONSET = 60.0              # SHAPE --warmup 60: scheduled incident onset in session time
SHIFT = ONSET + 60.0      # ctl_shift: second half of the 120 s incident
HORIZON = 240.0           # offered schedule length (warmup 60 + incident 120 + tail 60): censoring value for times
UNREACHABLE = {'6240', '7619'}
NOT_SCORED = {'horizon_ended', 'budget_exhausted', 'profiler_failed', 'evidence_missing'}
SUPPORTED = {'supported_complete', 'supported_partial'}


def reference(unit):
    cfg = case_workloads.CONTROLLED[unit] if unit.startswith('ctl_') else case_workloads.config(unit, 'bug')
    return cfg['reference']


def score(label, unit, t0=None, t1=None):
    """Outcome for a label whose evidence was acquired over session time [t0, t1]."""
    if unit in UNREACHABLE:
        return 'reference_unavailable'
    if not label or label in ('unknown', 'healthy'):
        return 'unresolved'
    ref = reference(unit)
    if unit == 'ctl_shift':
        if t0 is None or t1 >= SHIFT:
            return 'reference_unavailable'
        ref = 'queue_pressure'
    got, want = set(label.split('+')), set(ref.split('+'))
    return 'supported_complete' if got == want else 'supported_partial' if got < want else 'unsupported_concrete'


def jsonl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def cheap_label(window, th):
    """The frozen rule on one window's cheap evidence, inside an episode (no latency re-gating), as for bursts."""
    c = window['cheap']
    cw = CheapWindow(**{f: c.get(f) for f in ('latency_ratio', 'waiting_requests', 'kv_usage', 'preemptions_per_s',
                                              'gpu_util', 'running_requests')})
    return diagnose(cw, th, None, assume_elevated=True).label


def session(d, host):
    parts = d.parts
    i = parts.index('evaluation')
    block, unit = parts[i + 1], parts[i + 2]
    if unit == 'controlled':
        unit = parts[i + 3]
    s = json.loads((d / 'summary.json').read_text())
    ev = jsonl(d / 'events.jsonl')
    win = {e['window_id']: e for e in ev if e.get('kind') == 'window'}
    records = {json.loads(l)['capture_id']: json.loads(l)['record'] for l in (d / 'bursts.jsonl').read_text().splitlines()
               if l.strip()} if (d / 'bursts.jsonl').exists() else {}
    bursts = []
    for e in ev:
        if e.get('kind') != 'burst':
            continue
        r = records.get(e['capture_id']) or {}
        wall = (r['export_done_ns'] - r['start_issued_ns']) / 1e9 if r.get('export_done_ns') else None
        capture = (r['stop_returned_ns'] - r['start_issued_ns']) / 1e9 if r.get('stop_returned_ns') else None
        t1 = e['t']
        t0 = t1 - wall if wall is not None else None  # capture start in session time: the decision follows the export
        bursts.append(dict(t0=t0, t1=t1, label=e['heavy_diagnosis'], failure=e['failure'], wall_s=wall,
                           capture_s=capture, outcome=score(e['heavy_diagnosis'], unit, t0, t1 - (wall or 0) + (capture or 0))))
    ep = s.get('episode') or {}
    dec = ep.get('decision') or {}
    start = win.get(ep.get('started_window'))
    stop = win.get(ep.get('stopped_window'))
    last = bursts[-1] if bursts else None
    label = dec.get('diagnosis_label')
    outcome = score(label, unit, last and last['t0'], last and last['t1'] - (last['wall_s'] or 0) + (last['capture_s'] or 0)) \
        if last else score(None, unit)
    if dec.get('reason') in NOT_SCORED and outcome in SUPPORTED:
        outcome = 'unresolved'  # EVALUATION_PLAN §3: these terminal reasons are never scored as correct
    th = RuleThresholds(**s['thresholds'])
    in_episode = [w for w in win.values() if start and w['t'] >= start['t']]
    episode_labels = Counter(cheap_label(w, th) for w in sorted(in_episode, key=lambda w: w['t'])[:10])
    req = jsonl(d / 'requests.jsonl')
    ok = sorted(r['latency_s'] for r in req if r['ok'])
    first_sup = next((b for b in bursts if b['outcome'] in SUPPORTED), None)
    return dict(
        block=block, unit=unit, arm=d.name, host=host, path=str(d), reference=reference(unit),
        p95_base_s=s.get('p95_base_s'), started=start is not None, start_t=start and start['t'],
        trigger_cheap_label=start and start['cheap_diagnosis'],
        trigger_cheap_outcome=score(start and start['cheap_diagnosis'], unit, start and start['t'] - 1, start and start['t']),
        trigger_rule_label=start and cheap_label(start, th),
        trigger_rule_outcome=score(start and cheap_label(start, th), unit, start and start['t'] - 1, start and start['t']),
        first10_rule_label=episode_labels.most_common(1)[0][0] if episode_labels else None,
        stop_reason=dec.get('reason'), stop_label=label, stop_t=stop and stop['t'], outcome=outcome,
        bursts=len(bursts), profiler_wall_s=sum(b['wall_s'] or 0 for b in bursts),
        capture_s=sum(b['capture_s'] or 0 for b in bursts), burst_failures=sum(1 for b in bursts if b['failure']),
        burst_labels=[b['label'] for b in bursts], burst_outcomes=[b['outcome'] for b in bursts],
        t_supported_stop=(stop['t'] - start['t']) if (stop and start and outcome in SUPPORTED) else None,
        t_first_supported_burst=(first_sup['t1'] - start['t']) if (first_sup and start) else None,
        abstain_reasons=sorted({x for e in ev if e.get('kind') == 'burst' and not e['heavy_diagnosis']
                                 for x in (e['reasons'] or [f"capture_failure:{e['failure']}"])}),
        scheduled=(s.get('requests') or {}).get('scheduled'), ok=len(ok),
        censored=(s.get('requests') or {}).get('censored_at_horizon'),
        p95_latency_s=ok[min(len(ok) - 1, int(0.95 * len(ok)))] if ok else None,
        # load-generator validity: requests never sent before the horizon, and how late the sent ones went out
        unsent=((s.get('requests') or {}).get('scheduled') or 0) - len(req),
        lateness_p50_s=sorted(r['lateness_s'] for r in req)[len(req) // 2] if req else None)


def load(root):
    rows, seen = [], {}
    for done in sorted(Path(root).glob('*/evaluation/*/**/done')):
        d = done.parent
        if (d / 'PLACEHOLDER').exists():
            continue
        r = session(d, d.relative_to(root).parts[0])
        key = (r['block'], r['unit'], r['arm'])
        if key in seen:
            sys.exit(f'duplicate session {key}: {seen[key]} and {d}')
        seen[key] = d
        rows.append(r)
    return rows


# --- statistics (stdlib + scipy for the Wilcoxon p-value) ---

def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    c = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    m = (p + z * z / (2 * n)) / (1 + z * z / n)
    return [round(m - c, 3), round(m + c, 3)]


def a12(x, y):
    """Vargha-Delaney A12: P(X > Y) + 0.5 P(X = Y) over all pairs."""
    if not x or not y:
        return None
    return round(sum((a > b) + 0.5 * (a == b) for a in x for b in y) / (len(x) * len(y)), 3)


def cluster_bootstrap(pairs, n=10000, seed=0):
    """95% CI of the mean paired difference, resampling blocks (clusters) with replacement."""
    by = defaultdict(list)
    for blk, diff in pairs:
        by[blk].append(diff)
    blocks = sorted(by)
    if len(blocks) < 2:
        return None
    rnd, means = random.Random(seed), []
    for _ in range(n):
        xs = [v for b in (rnd.choice(blocks) for _ in blocks) for v in by[b]]
        means.append(sum(xs) / len(xs))
    means.sort()
    return [round(means[int(0.025 * n)], 3), round(means[int(0.975 * n) - 1], 3)]


def wilcoxon(diffs):
    from scipy.stats import wilcoxon as w
    nz = [d for d in diffs if d != 0]
    if len(nz) < 1:
        return None
    return float(w(nz).pvalue)


def holm(ps):
    order = sorted((p, k) for k, p in ps.items() if p is not None)
    out, run = {}, 0.0
    for i, (p, k) in enumerate(order):
        run = max(run, min(1.0, p * (len(order) - i)))
        out[k] = run
    return out


def primary(rows):
    by = {(r['block'], r['unit'], r['arm']): r for r in rows}
    units = sorted({(r['block'], r['unit']) for r in rows})
    measures = {
        'bursts': (lambda r: r['bursts'], False),
        'profiler_wall_s': (lambda r: r['profiler_wall_s'], False),
        'supported': (lambda r: int(r['outcome'] in SUPPORTED), True),
        't_supported_stop_s': (lambda r: r['t_supported_stop'] if r['t_supported_stop'] is not None else HORIZON, True),
    }
    out = {}
    for m, (f, adjudicable_only) in measures.items():
        res, ps = {}, {}
        for p in POLICIES:
            pairs, xs, ys = [], [], []
            for blk, u in units:
                if adjudicable_only and u in UNREACHABLE:
                    continue
                a, b = by.get((blk, u, p)), by.get((blk, u, 'FIX3'))
                if not a or not b:
                    continue
                pairs.append((blk, f(a) - f(b)))
                xs.append(f(a))
                ys.append(f(b))
            diffs = [d for _, d in pairs]
            ps[p] = wilcoxon(diffs)
            res[p] = dict(n_pairs=len(pairs), mean_policy=round(sum(xs) / len(xs), 3), mean_FIX3=round(sum(ys) / len(ys), 3),
                          mean_diff=round(sum(diffs) / len(diffs), 3), ci95_cluster_bootstrap=cluster_bootstrap(pairs),
                          wilcoxon_p=ps[p], a12=a12(xs, ys),
                          wins=sum(d < 0 for d in diffs), ties=sum(d == 0 for d in diffs), losses=sum(d > 0 for d in diffs))
            if m == 't_supported_stop_s':
                res[p]['censored_policy'] = sum(x == HORIZON for x in xs)
                res[p]['censored_FIX3'] = sum(y == HORIZON for y in ys)
        for p, q in holm(ps).items():
            res[p]['holm_p'] = q
        out[m] = res
    return out


def agreement(rows, field='outcome'):
    out = {}
    for arm in ARMS[1:]:
        rs = [r for r in rows if r['arm'] == arm and r['unit'] not in UNREACHABLE]
        c = Counter(r[field] for r in rs)
        k = c['supported_complete'] + c['supported_partial']
        adj = len(rs) - c['reference_unavailable']
        out[arm] = dict(n=len(rs), outcomes=dict(c), supported=k, rate_all=round(k / len(rs), 3) if rs else None,
                        wilson_all=wilson(k, len(rs)), adjudicable=adj, rate_adjudicable=round(k / adj, 3) if adj else None,
                        wilson_adjudicable=wilson(k, adj))
    return out


def rq1(rows):
    by = {(r['block'], r['unit'], r['arm']): r for r in rows}
    out = []
    for (blk, u, arm), r in sorted(by.items()):
        if arm != 'NT':
            continue
        f = by.get((blk, u, 'FIX1'))
        out.append(dict(block=blk, unit=u, reference=r['reference'], NT_logged_label=r['trigger_cheap_label'],
                        NT_logged_outcome=r['trigger_cheap_outcome'], NT_rule_label=r['trigger_rule_label'],
                        NT_rule_outcome=r['trigger_rule_outcome'], NT_first10_label=r['first10_rule_label'],
                        FIX1_label=f and f['stop_label'], FIX1_outcome=f and f['outcome']))
    tables = {}
    for name in ('NT_rule_outcome', 'NT_logged_outcome'):
        agree = Counter((x[name] in SUPPORTED, x['FIX1_outcome'] in SUPPORTED) for x in out if x['unit'] not in UNREACHABLE)
        tables[name] = {'NT+FIX1+': agree[(True, True)], 'NT+FIX1-': agree[(True, False)],
                        'NT-FIX1+': agree[(False, True)], 'NT-FIX1-': agree[(False, False)]}
    return dict(pairs=out, table=tables['NT_rule_outcome'], table_logged=tables['NT_logged_outcome'])


def by_burst(rows):
    """RQ2: outcome of the k-th burst, over every burst any profiled arm took on an adjudicable unit."""
    out = {}
    for k in range(6):
        c = Counter(r['burst_outcomes'][k] for r in rows if r['arm'] in ('FIX1', 'FIX3', 'SS', 'CR', 'HS')
                    and r['unit'] not in UNREACHABLE and len(r['burst_outcomes']) > k)
        n = sum(c.values())
        k_sup = c['supported_complete'] + c['supported_partial']
        out[k + 1] = dict(n=n, outcomes=dict(c), supported=k_sup, rate=round(k_sup / n, 3) if n else None,
                          wilson=wilson(k_sup, n))
    return out


def serving(rows):
    by = {(r['block'], r['unit'], r['arm']): r for r in rows}
    out = {}
    for arm in ARMS[1:]:
        ratios, dok, dcens, worst, unsent, late = [], [], [], None, 0, []
        for (blk, u, a), r in by.items():
            base = by.get((blk, u, 'U'))
            if a != arm or not base:
                continue
            if r['p95_latency_s'] and base['p95_latency_s']:
                ratios.append(r['p95_latency_s'] / base['p95_latency_s'])
            dok.append(r['ok'] - base['ok'])
            if worst is None or dok[-1] < worst[2]:
                worst = (blk, u, dok[-1])
            dcens.append((r['censored'] or 0) - (base['censored'] or 0))
            unsent += r['unsent']
            if r['lateness_p50_s'] is not None:
                late.append(r['lateness_p50_s'])
        ratios.sort()
        out[arm] = dict(n=len(dok), p95_ratio_median=round(ratios[len(ratios) // 2], 3) if ratios else None,
                        p95_ratio_range=[round(ratios[0], 3), round(ratios[-1], 3)] if ratios else None,
                        completed_diff_mean=round(sum(dok) / len(dok), 2) if dok else None,
                        completed_diff_median=sorted(dok)[len(dok) // 2] if dok else None, completed_diff_worst=worst,
                        censored_diff_mean=round(sum(dcens) / len(dcens), 2) if dcens else None,
                        unsent_total=unsent, lateness_p50_median=round(sorted(late)[len(late) // 2], 2) if late else None)
    base = [r for r in by.values() if r['arm'] == 'U']
    out['U'] = dict(n=len(base), unsent_total=sum(r['unsent'] for r in base),
                    lateness_p50_median=round(sorted(r['lateness_p50_s'] for r in base)[len(base) // 2], 2))
    return out


def per_unit(rows):
    out = defaultdict(dict)
    for r in sorted(rows, key=lambda r: (r['unit'], r['arm'], r['block'])):
        out[r['unit']].setdefault(r['arm'], []).append(dict(
            block=r['block'], reason=r['stop_reason'], label=r['stop_label'], outcome=r['outcome'], bursts=r['bursts'],
            t_stop=r['stop_t'] and r['start_t'] and round(r['stop_t'] - r['start_t'], 1), p95_s=r['p95_latency_s'] and round(r['p95_latency_s'], 2)))
    return out


SHORT = dict(supported_complete='complete', supported_partial='partial', unsupported_concrete='unsupported',
             unresolved='unresolved', reference_unavailable='ref. unavailable')


def fmt_p(p):
    return None if p is None else f'{p:.2g}'


def markdown(res):
    L = ['# Evaluation results (blocks %s)' % ', '.join(res['blocks']), '',
         f"{res['n_sessions']} sessions. Units: {', '.join(res['units'])}.", '',
         '## Primary: each policy against FIX3 (paired by block and unit)', '',
         'Negative difference = policy lower than FIX3. `supported` and time to a supported stop use the adjudicable units '
         'only (#6240 and #7619 excluded); time is from the episode trigger to a supported stop, censored at %d s '
         '(the schedule length) when the stop is not supported.' % HORIZON, '',
         'With three blocks the block bootstrap has at most 10 distinct resamples, so its intervals are narrow and coarse; '
         'read them with the per-unit tables. Lower/equal/higher counts the pairs where the policy is below, equal to or '
         'above FIX3 (for `supported`, higher is better).', '',
         '| Measure | Policy | Pairs | Policy mean | FIX3 mean | Mean diff | 95% CI (block bootstrap) | Wilcoxon p | Holm p | A12 | Lower/equal/higher |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for m, rs in res['primary'].items():
        for p, x in rs.items():
            L.append(f"| {m} | {p} | {x['n_pairs']} | {x['mean_policy']} | {x['mean_FIX3']} | {x['mean_diff']} | "
                     f"{x['ci95_cluster_bootstrap']} | {fmt_p(x['wilcoxon_p'])} | {fmt_p(x.get('holm_p'))} | {x['a12']} | "
                     f"{x['wins']}/{x['ties']}/{x['losses']} |")
    L += ['', '## Diagnosis outcome at the initial stop (adjudicable units)', '',
          '| Arm | n | Complete | Partial | Unsupported | Unresolved | Ref. unavailable | Supported rate | Wilson 95% |',
          '|---|---|---|---|---|---|---|---|---|']
    for arm, x in res['agreement'].items():
        o = x['outcomes']
        L.append(f"| {arm} | {x['n']} | {o.get('supported_complete', 0)} | {o.get('supported_partial', 0)} | "
                 f"{o.get('unsupported_concrete', 0)} | {o.get('unresolved', 0)} | {o.get('reference_unavailable', 0)} | "
                 f"{x['rate_all']} | {x['wilson_all']} |")
    L += ['', 'NT has no heavy evidence and stops at the horizon, so its stop is never scored as supported; its cheap label '
          'at the trigger is scored in the RQ1 table.', '',
          '## RQ1: NT cheap label at the trigger against FIX1 (adjudicable units)', '',
          'Primary: the frozen rule in its in-episode mode on the trigger window (as every burst is scored). In brackets: '
          'the label the window classifier logged online, which gates on theta_L = 1.95 > trigger 1.5.', '',
          '| | FIX1 supported | FIX1 not |', '|---|---|---|',
          f"| NT supported | {res['rq1']['table']['NT+FIX1+']} ({res['rq1']['table_logged']['NT+FIX1+']}) | "
          f"{res['rq1']['table']['NT+FIX1-']} ({res['rq1']['table_logged']['NT+FIX1-']}) |",
          f"| NT not | {res['rq1']['table']['NT-FIX1+']} ({res['rq1']['table_logged']['NT-FIX1+']}) | "
          f"{res['rq1']['table']['NT-FIX1-']} ({res['rq1']['table_logged']['NT-FIX1-']}) |", '',
          '| Block | Unit | Reference | NT rule label | NT first-10-windows label | FIX1 label |', '|---|---|---|---|---|---|']
    for x in res['rq1']['pairs']:
        L.append(f"| {x['block']} | {x['unit']} | {x['reference']} | {x['NT_rule_label']} ({SHORT[x['NT_rule_outcome']]}) | "
                 f"{x['NT_first10_label']} | {x['FIX1_label']} ({SHORT.get(x['FIX1_outcome'], '—')}) |")
    L += ['',
          '## RQ2: outcome of the k-th burst (all profiled arms, adjudicable units)', '',
          '| Burst | n | Supported | Unsupported | Unresolved | Ref. unavailable | Supported rate | Wilson 95% |',
          '|---|---|---|---|---|---|---|---|']
    for k, x in res['by_burst'].items():
        o = x['outcomes']
        L.append(f"| {k} | {x['n']} | {x['supported']} | {o.get('unsupported_concrete', 0)} | {o.get('unresolved', 0)} | "
                 f"{o.get('reference_unavailable', 0)} | {x['rate']} | {x['wilson']} |")
    L += ['', '## Serving impact against U (paired by block and unit)', '',
          'The load generator falls behind under overload in every arm, U included: `lateness` is the median over sessions '
          'of each session\'s median send delay, and `unsent` counts scheduled requests never sent before the horizon. '
          'The offered load is therefore not identical across arms.', '',
          '| Arm | Pairs | Median p95 ratio | p95 ratio range | Completed diff (median / mean) | Worst pair | Censored diff (mean) | Unsent | Lateness (s) |',
          '|---|---|---|---|---|---|---|---|---|']
    for arm, x in res['serving'].items():
        if arm == 'U':
            L.append(f"| U (reference) | {x['n']} | | | | | | {x['unsent_total']} | {x['lateness_p50_median']} |")
            continue
        L.append(f"| {arm} | {x['n']} | {x['p95_ratio_median']} | {x['p95_ratio_range']} | {x['completed_diff_median']} / "
                 f"{x['completed_diff_mean']} | {x['completed_diff_worst']} | {x['censored_diff_mean']} | {x['unsent_total']} | "
                 f"{x['lateness_p50_median']} |")
    L += ['', '## Why the rule abstained (bursts with no label, reasons per unit)', '', '| Unit | Reasons |', '|---|---|']
    for u, rs in res['abstain'].items():
        L.append(f"| {u} | {', '.join(f'{k} ({v})' for k, v in rs.items())} |")
    L += ['', '## Per unit: stop reason, label and bursts per block', '']
    for u, arms in res['per_unit'].items():
        L += [f"### {u} (reference `{reference(u)}`{', unreachable by the frozen rule' if u in UNREACHABLE else ''})", '',
              '| Arm | ' + ' | '.join(res['blocks']) + ' |', '|---|' + '---|' * len(res['blocks'])]
        for arm in ARMS:
            cells = {x['block']: x for x in arms.get(arm, [])}
            L.append(f'| {arm} | ' + ' | '.join(
                (f"{c['reason']} · {c['label'] or '—'} · {c['bursts']}b · {SHORT[c['outcome']]}"
                 if arm != 'U' else f"p95 {c['p95_s']} s") if (c := cells.get(b)) else 'missing' for b in res['blocks']) + ' |')
        L.append('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('root', help='evaluation_hosts directory')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = load(a.root)
    res = dict(blocks=sorted({r['block'] for r in rows}), units=sorted({r['unit'] for r in rows}), n_sessions=len(rows),
               primary=primary(rows), agreement=agreement(rows), rq1=rq1(rows), by_burst=by_burst(rows),
               serving=serving(rows),
               per_unit=per_unit(rows),
               abstain={u: dict(Counter(x for r in rows if r['unit'] == u for x in r['abstain_reasons']).most_common())
                        for u in sorted({r['unit'] for r in rows})})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'sessions.json').write_text(json.dumps(rows, indent=1, default=str))
    (out / 'results.json').write_text(json.dumps(res, indent=1, default=str))
    (out / 'results.md').write_text(markdown(res))
    print(f"{len(rows)} sessions -> {out}/results.md")


if __name__ == '__main__':
    main()
