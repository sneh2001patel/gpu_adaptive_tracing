"""Commissioning check for the external instrument (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §5, checks 1-3).

Runs under the host's system Python (no vLLM import). Starts the case environment's OpenAI server under
`nsys launch --session-new`, applies light closed-loop load, polls /metrics every second, takes two short
external bursts, and reports per burst: captured PIDs, busy fraction (capture-window denominator), top kernels
and every timing step. Not a study session; counted separately (proposal §10 step 5).

Usage: python3 commission_external.py --env v055 --version 0.5.5 --model <path> --out commission_v055.json
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ext'))
from external_instrument import ExternalBursts, cheap_measures, engine_family, gpu_activity  # noqa: E402
from rule_diagnosis import busy_fraction, kernel_shares  # noqa: E402


def http(url, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', required=True)
    p.add_argument('--version', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--port', type=int, default=8123)
    p.add_argument('--out', required=True)
    p.add_argument('--extra', default='', help='extra server arguments')
    p.add_argument('--graph-trace', choices=['graph', 'node'], default='node',
                   help='node: kernels inside CUDA graph replays are traced individually (needed for kernel shares)')
    args = p.parse_args()
    family, base = engine_family(args.version), f'http://127.0.0.1:{args.port}'
    work = Path(args.out).with_suffix('')
    work.mkdir(exist_ok=True)
    session = f'commission_{args.env}_{int(time.time())}'
    server = [f'{args.env}/bin/python', '-m', 'vllm.entrypoints.openai.api_server', '--model', args.model,
              '--port', str(args.port), '--max-model-len', '4096', '--gpu-memory-utilization', '0.85', *args.extra.split()]
    launch = ['nsys', 'launch', f'--session-new={session}', '--trace=cuda,nvtx,osrt',
              f'--cuda-graph-trace={args.graph_trace}', *server]
    log = open(work / 'server.log', 'w')
    proc = subprocess.Popen(launch, stdout=log, stderr=subprocess.STDOUT)
    result = dict(env=args.env, version=args.version, family=family, session=session, launch=launch, bursts=[], metrics=[])
    try:
        for _ in range(600):
            try:
                http(base + '/health', timeout=2)
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(f'server exited {proc.returncode}')
                time.sleep(1)
        else:
            raise RuntimeError('server not healthy after 600 s')
        model = json.loads(http(base + '/v1/models'))['data'][0]['id']
        stop = threading.Event()

        def client():
            while not stop.is_set():
                try:
                    http(base + '/v1/completions', dict(model=model, prompt='Explain GPUs. ' * 20, max_tokens=64, temperature=0))
                except Exception:
                    time.sleep(0.5)
        clients = [threading.Thread(target=client, daemon=True) for _ in range(8)]
        for c in clients:
            c.start()
        bursts = ExternalBursts(session, work)
        t0 = time.time()
        burst_at = {5: None, 12: None}
        while time.time() - t0 < 20:
            tick = time.time()
            result['metrics'].append(dict(t=round(tick - t0, 2), **cheap_measures(http(base + '/metrics'), family)))
            due = [k for k, v in burst_at.items() if v is None and tick - t0 >= k]
            if due:
                rec = bursts.capture(2.0)
                burst_at[due[0]] = rec
                entry = dict(vars(rec))
                if rec.database:
                    act = gpu_activity(rec.database)
                    shares = kernel_shares(act['kernel_totals'])
                    entry.update(pids=act['pids'], kernel_count=act['kernel_count'], memcpy_count=act['memcpy_count'],
                                 graph_count=act['graph_count'], graph_kernels_opaque=act['graph_kernels_opaque'],
                                 graph_node_kernel_count=act['graph_node_kernel_count'],
                                 window_source=act['window_source'], window_s=(act['window'][1] - act['window'][0]) / 1e9,
                                 busy_fraction=round(busy_fraction(act['intervals'], *act['window']), 4),
                                 top_kernels=sorted(shares.items(), key=lambda kv: -kv[1])[:5])
                ns = lambda a, b: None if a is None or b is None else round((b - a) / 1e6, 1)
                entry.update(start_cmd_ms=ns(rec.start_issued_ns, rec.start_returned_ns),
                             stop_cmd_ms=ns(rec.stop_issued_ns, rec.stop_returned_ns),
                             export_ms=ns(rec.report_present_ns, rec.export_done_ns),
                             start_to_report_ms=ns(rec.start_issued_ns, rec.report_present_ns))
                result['bursts'].append(entry)
            time.sleep(max(0.0, 1.0 - (time.time() - tick)))
        stop.set()
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
    finally:
        subprocess.run(['nsys', 'shutdown', f'--session={session}'], capture_output=True)
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        Path(args.out).write_text(json.dumps(result, indent=1, default=str))
        print(json.dumps({k: result.get(k) for k in ('env', 'error')} | dict(
            bursts=[{k: b.get(k) for k in ('ordinal', 'failure', 'pids', 'kernel_count', 'graph_count', 'graph_kernels_opaque', 'busy_fraction', 'window_source', 'window_s',
                                           'start_cmd_ms', 'stop_cmd_ms', 'export_ms', 'top_kernels')} for b in result['bursts']],
            metrics_last=result['metrics'][-1] if result['metrics'] else None), default=str))


if __name__ == '__main__':
    main()
