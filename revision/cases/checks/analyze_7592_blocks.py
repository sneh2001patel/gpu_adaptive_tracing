"""vllm#7592 acceptance (proposal §4.1): paired per-block throughput difference, v0.6.0 minus v0.5.5.

Accept the case if the 95% interval of the mean paired difference excludes zero. Reports both a percentile
bootstrap (10,000 resamples, seed 7592) and a Student-t interval, since five blocks make the bootstrap coarse.
Usage: python3 analyze_7592_blocks.py <dir containing 7592_block{b}_{v055,v060}.json>
"""
import json
import random
import statistics
import sys
from pathlib import Path

T_975 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}  # df -> t


def last_json(path):
    lines = [l for l in Path(path).read_text().splitlines() if l.startswith('{')]
    return json.loads(lines[-1]) if lines else None


def main():
    d = Path(sys.argv[1])
    rows = []
    for b in range(1, 100):
        a, f = d / f'7592_block{b}_v055.json', d / f'7592_block{b}_v060.json'
        if not (a.exists() and f.exists()):
            break
        ra, rf = last_json(a), last_json(f)
        if ra and rf:
            rows.append(dict(block=b, v055=ra['requests_per_s'], v060=rf['requests_per_s'],
                             v055_delay_ms=ra['delay_ms'], v060_delay_ms=rf['delay_ms']))
    diffs = [r['v060'] - r['v055'] for r in rows]
    n = len(diffs)
    if n < 2:
        print(json.dumps(dict(blocks=rows, error='fewer than 2 complete blocks')))
        return
    mean, sd = statistics.mean(diffs), statistics.stdev(diffs)
    half = T_975[n - 1] * sd / n ** 0.5
    rng = random.Random(7592)
    boots = sorted(statistics.mean(rng.choices(diffs, k=n)) for _ in range(10000))
    boot = (boots[249], boots[9749])
    rel = [d / r['v055'] for d, r in zip(diffs, rows)]
    out = dict(blocks=rows, n_blocks=n, mean_diff_req_s=round(mean, 4), sd=round(sd, 4),
               t_ci95=(round(mean - half, 4), round(mean + half, 4)), bootstrap_ci95=(round(boot[0], 4), round(boot[1], 4)),
               mean_relative_gain=round(statistics.mean(rel), 4), positive_blocks=sum(x > 0 for x in diffs))
    out['accepted'] = out['t_ci95'][0] > 0 and out['bootstrap_ci95'][0] > 0
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
