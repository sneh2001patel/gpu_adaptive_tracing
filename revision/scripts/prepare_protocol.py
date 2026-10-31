#!/usr/bin/env python3
"""Validate and compile a CPU-only draft design; never launch workloads or SSH."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random

from revision.tracing.policies import POLICIES, PolicyConfig

ROOT = Path(__file__).resolve().parents[2]
ARMS = set(POLICIES) | {'no_profiler', 'cheap_only', 'full_horizon_reference'}


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def validate(config):
    if config['status'] != 'draft_not_frozen' or not config['unresolved_before_freeze']:
        raise ValueError('This compiler accepts incomplete draft protocols only; it cannot certify a freeze')
    for key in ('horizon_s', 'window_s', 'drain_s', 'requested_burst_s'):
        if not positive(config[key]):
            raise ValueError(f'Invalid {key}')
    if config['horizon_s'] % config['window_s']:
        raise ValueError('Horizon must contain whole windows')
    if type(config['repetitions']) is not int or config['repetitions'] < 1:
        raise ValueError('Invalid repetitions')
    if type(config['reactivation_enabled']) is not bool:
        raise ValueError('Invalid reactivation flag')
    PolicyConfig(max_bursts=config['max_bursts'], stability_windows=config['stability_windows'],
                 repeated_bursts=config['repeated_bursts'], recovery_windows=config['recovery_windows'])
    if config['max_bursts'] < max(config['stability_windows'], config['repeated_bursts']):
        raise ValueError('Budget cannot exercise the planned stability/repetition rules')
    arms=config['arms']
    if len(set(arms)) != len(arms) or set(arms) != ARMS:
        raise ValueError('Require the five distinct policies and three instrument/control arms')
    seen_seeds=set();corpora=set();families=set()
    for split in ('calibration','development','confirmation'):
        spec=config['splits'][split]
        if spec['request_corpus'] in corpora or spec['workload_family'] in families:
            raise ValueError('Splits must separate request corpora and workload families')
        corpora.add(spec['request_corpus']);families.add(spec['workload_family'])
        if len(spec['seeds']) != len(set(spec['seeds'])) or seen_seeds.intersection(spec['seeds']):
            raise ValueError('Split seeds must be unique and disjoint')
        if any(type(seed) is not int for seed in spec['seeds']):
            raise ValueError('Seeds must be integers')
        seen_seeds.update(spec['seeds'])
    if len(config['splits']['development']['seeds']) < config['repetitions']:
        raise ValueError('Not enough development repetition labels')
    identities=set()
    for case in config['cases']:
        if case['id'] in identities:
            raise ValueError('Duplicate case')
        identities.add(case['id']);end=0
        for phase in case['phases']:
            if phase['start_s'] != end or not positive(phase['end_s']-end):
                raise ValueError('Phase schedule has a gap, overlap or empty phase')
            if not positive(phase['arrival_capacity_ratio']) or type(phase['output_tokens']) is not int or phase['output_tokens'] < 1:
                raise ValueError('Invalid offered load or output length')
            if phase['prompt_band'] not in ('short','long'):
                raise ValueError('Unknown prompt band')
            end=phase['end_s']
        if end != config['horizon_s']:
            raise ValueError('Phases must cover the entire observation horizon')
    if identities != {'healthy','persistent','prefill_only','changing','temporary_lull','overlap'}:
        raise ValueError('Missing required challenge or single-intervention control')


def compile_design(config):
    validate(config)
    rng=random.Random(config['schedule_seed'])
    blocks=[(case,seed) for case in config['cases'] for seed in config['splits']['development']['seeds'][:config['repetitions']]]
    rng.shuffle(blocks)
    rows=[];private=[]
    for block,(case,seed) in enumerate(blocks,1):
        arms=list(config['arms']);rng.shuffle(arms)
        for arm in arms:
            identity=f'dev-b{block:03d}-{arm}'
            # Case names, phase schedules and intended interventions stay here.
            private.append(dict(run_id=identity,block=block,case_id=case['id'],seed=seed,arm=arm,phases=case['phases']))
            rows.append(dict(run_id=identity,block=block,arm=arm,split='development',
                horizon_s=config['horizon_s'],window_s=config['window_s'],drain_s=config['drain_s'],
                requested_burst_s=config['requested_burst_s'],max_bursts=config['max_bursts'],
                stability_windows=config['stability_windows'],repeated_bursts=config['repeated_bursts'],
                recovery_windows=config['recovery_windows'],reactivation_enabled=config['reactivation_enabled']))
    count=len(rows)
    return dict(status='draft_not_executable',controller_jobs=rows),dict(status='evaluator_only_not_reference_truth',runs=private),dict(
        status='planning_bounds_not_measured_cost',runs=count,blocks=len(blocks),
        observation_hours=count*config['horizon_s']/3600,
        observation_plus_max_drain_hours=count*(config['horizon_s']+config['drain_s'])/3600,
        excludes=['startup','warmup','healthy_calibration','capacity_measurement','export_after_horizon','failures_and_retries','sensitivity','confirmation','GPU_reference_pilot'],
        gpu_used=False,launch_supported=False,freeze_blockers=config['unresolved_before_freeze'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'revision/configs/l4_protocol_draft.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=args.config.read_bytes();config=json.loads(data)
    public,private,summary=compile_design(config)
    args.output.mkdir(parents=True,exist_ok=False)
    for name,value in [('controller_jobs',public),('evaluator_schedule',private),('planning_summary',summary)]:
        (args.output/f'{name}.json').write_text(json.dumps(value,indent=2)+'\n')
    (args.output/'manifest.json').write_text(json.dumps(dict(protocol_sha256=hashlib.sha256(data).hexdigest(),
        compiler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),status='draft_not_frozen'),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
