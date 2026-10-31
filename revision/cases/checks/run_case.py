"""Run one run_episode.py session for one side of a real case (case_workloads.py).

Usage: run_case.py --case 6240 --side bug <run_episode.py args except env/version/model/server args>
Fills in --env, --version, --model, --server-args and --case-patch from the registry, swaps xgrammar in place
for vllm#19732, and writes case.json (resolved settings and installed component versions) into --out.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import case_workloads

HERE = Path(__file__).resolve().parent


def installed(env, package):
    proc = subprocess.run([f'{env}/bin/python', '-c', f"from importlib.metadata import version; print(version('{package}'))"],
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def snapshot(env, model):
    proc = subprocess.run([f'{env}/bin/python', '-c', 'import sys; from huggingface_hub import snapshot_download as s; '
                           'print(s(sys.argv[1], local_files_only=True))', model], capture_output=True, text=True)
    return proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True, choices=sorted(case_workloads.CASES) + sorted(case_workloads.CONTROLLED))
    p.add_argument('--side', required=True, choices=['bug', 'fixed'])  # controlled cases have only 'fixed'
    p.add_argument('--out', required=True)
    args, rest = p.parse_known_args()
    cfg = case_workloads.config(args.case, args.side)
    schedule = next(i for i, a in enumerate(rest) if a == '--schedule')
    with open(rest[schedule + 1]) as f:
        served = json.loads(f.readline())['body']['model']
    if served != cfg['model'] and not os.environ.get('CASE_ALLOW_MODEL_MISMATCH'):  # the server would reject every request
        raise SystemExit(f"schedule requests model {served!r}, case serves {cfg['model']!r}")
    if cfg.get('xgrammar') and installed(cfg['env'], 'xgrammar') != cfg['xgrammar']:
        subprocess.run(['uv', 'pip', 'install', '-q', '--no-deps', f"xgrammar=={cfg['xgrammar']}"], check=True,
                       env=dict(os.environ, VIRTUAL_ENV=str(Path(cfg['env']).resolve())))
    Path(args.out).mkdir(parents=True, exist_ok=True)
    record = dict(case=args.case, side=args.side, config=cfg,
                  installed={pkg: installed(cfg['env'], pkg) for pkg in ('vllm', 'torch', 'transformers', 'xgrammar', 'outlines')})
    if cfg.get('xgrammar') and record['installed']['xgrammar'] != cfg['xgrammar']:
        raise SystemExit(f"xgrammar is {record['installed']['xgrammar']}, expected {cfg['xgrammar']}")
    (Path(args.out) / 'case.json').write_text(json.dumps(record, indent=1))
    # Serve the local snapshot under the case's model name: old releases (0.3.x) query the Hub while loading a model
    # given by name, which fails in offline mode. Requests keep using the name (--served-model-name).
    local = snapshot(cfg['env'], cfg['model'])
    server_args = cfg['server_args'] + (f" --served-model-name {cfg['model']}" if local else '')
    record['served_from'] = local or cfg['model']
    (Path(args.out) / 'case.json').write_text(json.dumps(record, indent=1))
    cmd = [sys.executable, str(HERE / 'run_episode.py'), '--env', cfg['env'], '--version', cfg['version'],
           '--model', local or cfg['model'], f'--server-args={server_args}', '--out', args.out, *rest]  # value starts with --
    if cfg.get('patch'):
        cmd += ['--case-patch', cfg['patch']]
    if cfg.get('withhold') and '--withhold' not in rest:
        cmd += ['--withhold', cfg['withhold']]
    if cfg.get('min_latency_samples') and '--min-latency-samples' not in rest:
        cmd += ['--min-latency-samples', str(cfg['min_latency_samples'])]
    sys.exit(subprocess.run(cmd).returncode)


if __name__ == '__main__':
    main()
