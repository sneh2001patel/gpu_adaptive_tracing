"""Step 6 gate summary for one case directory from queue_case_symptoms.sh: fixed vs bug side under the instrument.

Only the incident phase is compared (requests sent, and windows observed, in [warmup, warmup + incident)).
Pre-declared criterion (CALIBRATION_PLAN.md §2): the symptom is shown when the bug side's incident p50 latency is
at least 1.1x the fixed side's, or its generated-token throughput at most 0.9x. Prints one JSON object.

The bug side is evaluation-side data (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §3.4): only its symptom measures are
reported here, never the rule's inputs or diagnoses, so thresholds are set without having seen them. Its raw files
are kept and are excluded from calibration.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def quantile(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))] if s else None


SYMPTOM_KEYS = ('error', 'scheduled', 'completed', 'ok', 'failed', 'errors', 'p50_latency_s', 'p95_latency_s',
                'mean_lateness_s', 'gen_tokens_per_s')


def side(d, lo, hi):
    d = Path(d)
    summary = json.loads((d / 'summary.json').read_text())
    req = [json.loads(l) for l in (d / 'requests.jsonl').read_text().splitlines() if l.strip()]
    win = [e for e in (json.loads(l) for l in (d / 'events.jsonl').read_text().splitlines() if l.strip())
           if e.get('kind') == 'window' and lo <= e['t'] < hi]
    schedule = [json.loads(l) for l in Path(summary['config']['schedule']).read_text().splitlines() if l.strip()]
    sent = [r for r in req if lo <= r['scheduled_t'] < hi]
    ok = [r['latency_s'] for r in sent if r['ok']]
    gen = [(e['t'], e['raw']['generation_tokens']) for e in win if e['raw'].get('generation_tokens') is not None]
    cheap = [e['cheap'] for e in win]

    def mean(key):
        v = [c[key] for c in cheap if c[key] is not None]
        return round(sum(v) / len(v), 3) if v else None
    lat = [c['latency_ratio'] for c in cheap if c['latency_ratio'] is not None]
    return dict(
        error=summary.get('error'), scheduled=sum(lo <= s['t'] < hi for s in schedule), completed=len(sent),
        ok=len(ok), failed=sum(not r['ok'] for r in sent), errors=Counter(r['error'][:60] for r in sent if not r['ok']).most_common(3),
        p50_latency_s=quantile(ok, 0.5), p95_latency_s=quantile(ok, 0.95),
        mean_lateness_s=round(sum(r['lateness_s'] for r in sent) / len(sent), 3) if sent else None,
        gen_tokens_per_s=round((gen[-1][1] - gen[0][1]) / (gen[-1][0] - gen[0][0]), 1) if len(gen) > 1 else None,
        latency_ratio_median=quantile(lat, 0.5), latency_ratio_max=max(lat) if lat else None,
        elevated_window_share=round(sum(v >= 1.5 for v in lat) / len(lat), 3) if lat else None,
        waiting_mean=mean('waiting_requests'), kv_usage_mean=mean('kv_usage'),
        preemptions_per_s_mean=mean('preemptions_per_s'), gpu_util_mean=mean('gpu_util'),
        cheap_diagnoses=Counter(e['cheap_diagnosis'] for e in win).most_common(4),
        episode=summary.get('episode'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('case_dir')
    p.add_argument('--warmup', type=float, default=60)
    p.add_argument('--incident', type=float, default=120)
    args = p.parse_args()
    c = Path(args.case_dir)
    lo, hi = args.warmup, args.warmup + args.incident
    result = dict(case=c.name, phase=[lo, hi], baseline=json.loads((c / 'baseline.json').read_text()))
    for s in ('fixed', 'bug'):
        result[s] = side(c / f'NT_{s}', lo, hi) if (c / f'NT_{s}' / 'summary.json').is_file() else None
    if result['bug']:
        result['bug'] = {k: result['bug'][k] for k in SYMPTOM_KEYS}
    f, b = result['fixed'], result['bug']
    if f and b:
        def ratio(key):
            return round(b[key] / f[key], 3) if b[key] is not None and f[key] else None
        result['bug_over_fixed'] = dict(p50_latency=ratio('p50_latency_s'), p95_latency=ratio('p95_latency_s'),
                                        gen_tokens_per_s=ratio('gen_tokens_per_s'), completed=ratio('completed'))
        r = result['bug_over_fixed']
        result['symptom_shown'] = bool((r['p50_latency'] or 0) >= 1.1 or (r['gen_tokens_per_s'] or 1) <= 0.9)
    print(json.dumps(result, indent=1, default=str))


if __name__ == '__main__':
    main()
