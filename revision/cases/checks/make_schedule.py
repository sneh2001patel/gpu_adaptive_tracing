"""Open-loop arrival schedules (JSONL) for run_episode.py: Poisson arrivals with piecewise-constant rates.

Patterns (proposal §4.2; step-037 pilot): rates are requests/second per phase, durations in seconds.
  healthy        one phase at --base-rate
  overload       --warmup s at --base-rate, then --incident s at --high-rate, then --tail s at --base-rate
  lull           base, high, base for --lull s, high again, then base (lull and recurrence)
  shift          like overload, but the second half of the incident sends prefill-heavy requests
                 (--shift-prompt-words) at --shift-rate: the bottleneck changes mid-incident (changing bottleneck)
Bodies are /v1/completions requests with a fixed prompt and token budget, or, with --case/--side, the case's own
requests from case_workloads.py (rates then default to the case's healthy and incident rates; a case with a
group_size sends that many requests per arrival). Seeded, so blocks can replay the same schedule across arms.
"""
import argparse
import json
import random

import case_workloads


def phases(args):
    b, h = args.base_rate, args.high_rate
    if args.pattern == 'healthy':
        return [(args.warmup + args.incident + args.tail, b)]
    if args.pattern == 'overload':
        return [(args.warmup, b), (args.incident, h), (args.tail, b)]
    if args.pattern == 'lull':
        half = args.incident / 2
        return [(args.warmup, b), (half, h), (args.lull, b), (half, h), (args.tail, b)]
    if args.pattern == 'shift':
        half = args.incident / 2
        return [(args.warmup, b), (half, h), (half, args.shift_rate or h), (args.tail, b)]
    raise ValueError(args.pattern)


def prefill_heavy_phase(args, index):
    """Phase index whose requests use --shift-prompt-words (shift pattern only)."""
    return args.pattern == 'shift' and index == 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pattern', choices=['healthy', 'overload', 'lull', 'shift'], required=True)
    p.add_argument('--model', help='served model name; default: the case model (required without --case)')
    p.add_argument('--case', choices=sorted(case_workloads.CASES))
    p.add_argument('--side', choices=['bug', 'fixed'], default='fixed')
    p.add_argument('--base-rate', type=float, help='default 1.0, or the case healthy_rate')
    p.add_argument('--high-rate', type=float, help='default 8.0, or the case incident_rate')
    p.add_argument('--warmup', type=float, default=60)
    p.add_argument('--incident', type=float, default=90)
    p.add_argument('--lull', type=float, default=30)
    p.add_argument('--shift-prompt-words', type=int, default=2000)
    p.add_argument('--shift-rate', type=float, help='rate of the prefill-heavy half (default --high-rate)')
    p.add_argument('--tail', type=float, default=60)
    p.add_argument('--prompt-words', type=int, default=200)
    p.add_argument('--max-tokens', type=int, default=128)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    case = case_workloads.CASES.get(args.case, {})
    args.model = args.model or case.get('model')
    if not args.model:
        p.error('--model is required without --case')
    if args.base_rate is None:
        args.base_rate = case.get('healthy_rate', 1.0)
    if args.high_rate is None:
        args.high_rate = case.get('incident_rate', 8.0)
    # Arrival times and body randomness use separate streams, so both sides of a case get the same arrivals.
    rng, body_rng, t, lines = random.Random(args.seed), random.Random(args.seed + 1), 0.0, []
    prompts = [' '.join(['token'] * n) for n in (args.prompt_words, args.shift_prompt_words)]
    start, group = 0.0, 0
    for index, (duration, rate) in enumerate(phases(args)):
        prompt = prompts[prefill_heavy_phase(args, index)]
        t = start
        while True:
            t += rng.expovariate(rate)
            if t >= start + duration:
                break
            for _ in range(case.get('group_size', 1)):
                if args.case:
                    path, body = case_workloads.request(args.case, args.side, args.model, len(lines), group, body_rng)
                else:
                    path, body = '/v1/completions', dict(model=args.model, prompt=prompt, max_tokens=args.max_tokens,
                                                         temperature=0, ignore_eos=True)
                lines.append(dict(t=round(t, 4), path=path, body=body))
            group += 1
        start += duration
    with open(args.out, 'w') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')
    print(json.dumps(dict(pattern=args.pattern, case=args.case, side=args.side, requests=len(lines), groups=group, horizon_s=start, phases=phases(args))))


if __name__ == '__main__':
    main()
