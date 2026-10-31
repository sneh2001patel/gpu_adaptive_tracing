"""One serving session with the external instrument (proposal §5; EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md).

Runs under the host's system Python with only the flat copies in ./ext (no vLLM import):
  1. starts the case environment's OpenAI server, under `nsys launch` unless --unprofiled;
  2. replays an open-loop schedule (JSONL: {"t": seconds, "path": "/v1/...", "body": {...}});
  3. every window: p95 age of in-flight requests / p95_base (same measure in the healthy baseline; step 053),
     waiting and running requests, KV usage, preemption rate (/metrics) and mean GPU utilization (nvidia-smi,
     100 ms) -> EpisodeController. Completed-request p95 latency is recorded for reporting only (it lags);
  4. when the controller asks, takes one external burst in a background thread and returns its busy fraction
     and GPU time per processed token by kernel family (tokens from /metrics counters read right after `start`
     and right before `stop`).
Writes events.jsonl, requests.jsonl, bursts.jsonl and summary.json in --out.

--baseline-out records a healthy calibration session instead: the median over steady windows of the in-flight p95
age (p95_base_s) and per-token family time from one mid-load burst (baseline_ns_per_token).
"""
import argparse
import json
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ext'))
from episode_controller import ArmConfig, EpisodeController  # noqa: E402
from external_instrument import ExternalBursts, cheap_measures, engine_family, gpu_activity  # noqa: E402
from policies import PolicyConfig  # noqa: E402
from rule_diagnosis import CheapWindow, RuleThresholds, busy_fraction, family_time_per_token, kernel_shares  # noqa: E402


def http(url, body=None, timeout=600):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def p95(values):
    s = sorted(values)
    return s[min(len(s) - 1, int(0.95 * len(s)))] if s else None


class GpuUtil:
    """nvidia-smi streaming reader; mean utilization (0-1) of samples received since the last call."""
    def __init__(self, index=0):
        self.samples, self.lock = [], threading.Lock()
        try:
            self.proc = subprocess.Popen(['nvidia-smi', '-i', str(index), '--query-gpu=utilization.gpu',
                                          '--format=csv,noheader,nounits', '-lms', '100'],
                                         stdout=subprocess.PIPE, text=True)
        except FileNotFoundError:  # no NVIDIA driver (local smoke test): utilization stays unavailable
            self.proc = None
            return
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                value = float(line.strip()) / 100
            except ValueError:
                continue
            with self.lock:
                self.samples.append(value)

    def take(self):
        with self.lock:
            s, self.samples = self.samples, []
        return sum(s) / len(s) if s else None

    def close(self):
        if self.proc:
            self.proc.terminate()


def burst_activity(rec, tokens):
    if rec.failure or not rec.database:
        return None
    act = gpu_activity(rec.database)
    per_token, top = family_time_per_token(act['kernel_totals'], tokens)
    return dict(busy_fraction=busy_fraction(act['intervals'], *act['window']), tokens=tokens,
                family_ns_per_token=per_token, family_top_kernel=top,
                kernel_shares=kernel_shares(act['kernel_totals']), pids=act['pids'],
                kernel_count=act['kernel_count'], window_source=act['window_source'],
                kernels_crossing_window=act['kernels_crossing_window'], graph_kernels_opaque=act['graph_kernels_opaque'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', required=True)
    p.add_argument('--version', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--schedule', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--arm', default='NT', choices=['NT', 'FIX', 'SS', 'CR', 'HS'])
    p.add_argument('--fixed-bursts', type=int, default=3)
    p.add_argument('--thresholds', help='RuleThresholds JSON')
    p.add_argument('--baseline', help='baseline JSON with p95_base_s and baseline_shares')
    p.add_argument('--baseline-out', help='record a healthy calibration baseline instead of running an arm')
    p.add_argument('--policy', default='{}', help='PolicyConfig fields as JSON')
    p.add_argument('--trigger-latency-ratio', type=float, default=1.5)
    p.add_argument('--trigger-windows', type=int, default=2)
    p.add_argument('--burst-seconds', type=float, default=2.0)
    p.add_argument('--window-seconds', type=float, default=1.0)
    p.add_argument('--latency-window-seconds', type=float, default=5.0)
    p.add_argument('--min-latency-samples', type=int, default=3)
    p.add_argument('--drain-seconds', type=float, default=30.0)
    p.add_argument('--unprofiled', action='store_true')
    p.add_argument('--graph-trace', choices=['graph', 'node'], default='node')
    p.add_argument('--server-args', default='--max-model-len 4096 --gpu-memory-utilization 0.85')
    p.add_argument('--port', type=int, default=8123)
    p.add_argument('--calibration-bursts', default='', help='comma-separated session times (s) for scheduled bursts '
                   '(calibration evidence at fixed points; arm NT only; never passed to the controller)')
    p.add_argument('--scrape-timeout', type=float, default=5.0, help='seconds per /metrics read')
    p.add_argument('--withhold', default='', help='controlled case "incomplete evidence": comma-separated CheapWindow '
                   'fields, or "heavy", hidden from the controller; raw values are still logged')
    p.add_argument('--case-patch', help='start the server through case_server.py with this patch (case_workloads.py)')
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    family, base = engine_family(args.version), f'http://127.0.0.1:{args.port}'
    schedule = [json.loads(l) for l in Path(args.schedule).read_text().splitlines() if l.strip()]
    recording = bool(args.baseline_out)
    thresholds = RuleThresholds(**json.loads(Path(args.thresholds).read_text())) if args.thresholds else RuleThresholds()
    baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else {}
    p95_base = baseline.get('p95_base_s')
    arm = ArmConfig(args.arm, fixed_bursts=args.fixed_bursts, trigger_latency_ratio=args.trigger_latency_ratio,
                    trigger_windows=args.trigger_windows, policy=PolicyConfig(**json.loads(args.policy)))
    controller = EpisodeController(arm, thresholds, baseline.get('baseline_ns_per_token'))
    withheld = {w for w in args.withhold.split(',') if w}
    unknown = withheld - {f.name for f in fields(CheapWindow)} - {'heavy'}
    if unknown:
        raise SystemExit(f'--withhold: unknown fields {sorted(unknown)}')
    if args.calibration_bursts and (args.arm != 'NT' or args.baseline_out or args.unprofiled):
        raise SystemExit('--calibration-bursts needs a profiled NT session')
    if args.unprofiled and args.arm != 'NT':
        raise SystemExit('--unprofiled sessions cannot take bursts; use --arm NT')

    session = f'ep_{int(time.time())}'
    entry = (['-m', 'vllm.entrypoints.openai.api_server'] if not args.case_patch
             else [str(Path(__file__).resolve().parent / 'case_server.py'), args.case_patch])
    server = [f'{args.env}/bin/python', *entry, '--model', args.model, '--port', str(args.port), *args.server_args.split()]
    cmd = server if args.unprofiled else ['nsys', 'launch', f'--session-new={session}', '--trace=cuda,nvtx,osrt',
                                         f'--cuda-graph-trace={args.graph_trace}', *server]
    log = open(out / 'server.log', 'w')
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    files = {k: open(out / f'{k}.jsonl', 'w') for k in ('events', 'requests', 'bursts')}
    summary = dict(config=vars(args), launch=cmd, thresholds=asdict(thresholds), thresholds_digest=thresholds.digest(),
                   thresholds_frozen=thresholds.frozen(), p95_base_s=p95_base)
    gpu = None
    try:
        for _ in range(900):
            try:
                http(base + '/health', timeout=2)
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(f'server exited {proc.returncode}')
                time.sleep(1)
        else:
            raise RuntimeError('server not healthy after 900 s')
        gpu = GpuUtil()
        done, lock, closing, inflight = [], threading.Lock(), threading.Event(), {}
        t0 = time.time()

        def send(i, item):
            start = time.time()
            with lock:
                inflight[i] = start
            ok, err = True, None
            try:
                http(base + item['path'], item['body'])
            except Exception as e:
                ok, err = False, f'{type(e).__name__}: {e}'[:300]
            end = time.time()
            rec = dict(i=i, scheduled_t=item['t'], sent_t=start - t0, lateness_s=start - t0 - item['t'],
                       done_t=end - t0, latency_s=end - start, ok=ok, error=err)
            with lock:
                inflight.pop(i, None)
                if closing.is_set():  # finished after the horizon: counted as censored, not written
                    return
                done.append(rec)
                files['requests'].write(json.dumps(rec) + '\n')

        pool = ThreadPoolExecutor(max_workers=512)

        def dispatch():  # open loop: submit each request at its scheduled offset, independent of completions
            for i, item in enumerate(schedule):
                delay = t0 + item['t'] - time.time()
                if delay > 0:
                    time.sleep(delay)
                pool.submit(send, i, item)
        threading.Thread(target=dispatch, daemon=True).start()
        bursts = None if args.unprofiled else ExternalBursts(session, out)
        burst_results, burst_thread = queue.Queue(), None
        last_preempt, horizon = None, schedule[-1]['t'] + args.drain_seconds
        baseline_activity, steady_ages = None, []

        def scrape():
            """(measures, error, seconds). A failed or timed-out scrape gives all measures None and is recorded,
            not fatal: a host-side stall can block the server's event loop, /metrics included (vllm#25418)."""
            start = time.time()
            try:
                m, err = cheap_measures(http(base + '/metrics', timeout=args.scrape_timeout), family), None
            except Exception as e:
                m, err = dict.fromkeys(cheap_measures('', family)), f'{type(e).__name__}: {e}'[:200]
            return m, err, time.time() - start

        def token_count():
            m = scrape()[0]
            parts = (m['prompt_tokens'], m['generation_tokens'])
            return None if None in parts else sum(parts)

        def capture_with_tokens():
            marks = {}
            rec = bursts.capture(args.burst_seconds, on_started=lambda: marks.__setitem__('a', token_count()),
                                 before_stop=lambda: marks.__setitem__('b', token_count()))
            a, b = marks.get('a'), marks.get('b')
            return rec, None if a is None or b is None else b - a
        def handle_result(cid, rec, activity):
            nonlocal baseline_activity
            files['bursts'].write(json.dumps(dict(capture_id=cid, record=vars(rec), activity=activity), default=str) + '\n')
            if recording:
                baseline_activity = activity
            elif cid.startswith('cal'):  # scheduled calibration evidence: logged, never shown to the controller
                files['events'].write(json.dumps(dict(kind='calibration_burst', capture_id=cid, t=time.time() - t0,
                                                      failure=rec.failure)) + '\n')
            else:
                files['events'].write(json.dumps(controller.on_burst(
                    cid, None if 'heavy' in withheld else activity,
                    'withheld' if 'heavy' in withheld and not rec.failure else rec.failure)) + '\n')

        def start_burst(cid):
            def worker():
                rec, tokens = capture_with_tokens()
                try:
                    activity = burst_activity(rec, tokens)
                except Exception as e:  # e.g. no CUDA activity at all in the window: recorded, not lost
                    rec.failure, activity = f'analysis_failed: {type(e).__name__}: {e}'[:200], None
                burst_results.put((cid, rec, activity))
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            return thread
        calibration_times = sorted(float(x) for x in args.calibration_bursts.split(',') if x)
        window = 0
        while time.time() - t0 < horizon:
            tick = time.time()
            m, scrape_error, scrape_s = scrape()
            now = tick - t0
            with lock:
                recent = [r['latency_s'] for r in done if r['ok'] and now - args.latency_window_seconds <= r['done_t'] <= now]
                ages = [tick - s for s in inflight.values()]
            completed_p95 = p95(recent) if len(recent) >= args.min_latency_samples else None
            lat = p95(ages) if len(ages) >= args.min_latency_samples else None  # in-flight age; does not lag a drain
            rate = None
            if m['preemptions'] is not None:
                if last_preempt is not None:  # over the real gap: a failed scrape can stretch it past one window
                    rate = (m['preemptions'] - last_preempt[0]) / max(1e-6, tick - last_preempt[1])
                last_preempt = (m['preemptions'], tick)
            cheap = CheapWindow(latency_ratio=None if lat is None or not p95_base else lat / p95_base,
                                waiting_requests=m['waiting'], kv_usage=m['kv_usage'], preemptions_per_s=rate,
                                gpu_util=gpu.take(), running_requests=m['running'])
            observed, cheap = cheap, replace(cheap, **{k: None for k in withheld if k != 'heavy'})
            wid = f'w{window:05d}'
            while not burst_results.empty():
                handle_result(*burst_results.get())
            if recording:
                files['events'].write(json.dumps(dict(kind='window', window_id=wid, t=now, inflight_p95_s=lat,
                                                      completed_p95_s=completed_p95, cheap=asdict(cheap), raw=m,
                                                      scrape_error=scrape_error, scrape_s=scrape_s)) + '\n')
                if lat is not None and now >= 0.25 * schedule[-1]['t']:
                    steady_ages.append(lat)
                # mid steady load, with requests in flight (sparse arrivals, e.g. vllm#7619's request groups, can
                # otherwise leave the capture on an idle GPU)
                if bursts and burst_thread is None and now >= 0.5 * schedule[-1]['t'] and ages:
                    burst_thread = start_burst('baseline')
            else:
                action = controller.on_window(wid, now, cheap)
                event = controller.events[-1]
                event.update(inflight_p95_s=lat, completed_p95_s=completed_p95, raw=m, scrape_error=scrape_error,
                             scrape_s=scrape_s)
                if withheld:
                    event['observed'] = asdict(observed)
                files['events'].write(json.dumps(event) + '\n')
                if action['capture']:
                    burst_thread = start_burst(f'b{controller.episode["bursts"] + 1:03d}')
                elif (calibration_times and now >= calibration_times[0]
                      and (burst_thread is None or not burst_thread.is_alive())):
                    calibration_times.pop(0)
                    burst_thread = start_burst(f'cal{now:05.0f}')
            for f in files.values():
                f.flush()
            window += 1
            time.sleep(max(0.0, args.window_seconds - (time.time() - tick)))
        if burst_thread is not None:
            burst_thread.join(timeout=120)
            while not burst_results.empty():
                handle_result(*burst_results.get())
        with lock:
            closing.set()
            summary['requests'] = dict(scheduled=len(schedule), completed=len(done), ok=sum(r['ok'] for r in done),
                                       censored_at_horizon=len(schedule) - len(done))
        pool.shutdown(wait=False, cancel_futures=True)
        if recording:
            steady = [r['latency_s'] for r in done if r['ok'] and r['sent_t'] >= 0.25 * schedule[-1]['t']]
            act = baseline_activity
            ages = sorted(steady_ages)
            Path(args.baseline_out).write_text(json.dumps(dict(
                p95_base_s=ages[len(ages) // 2] if ages else None, p95_base_measure='median over steady windows of p95 in-flight age',
                n_windows=len(ages), completed_p95_s=p95(steady), n_completed=len(steady),
                baseline_ns_per_token=None if act is None else act['family_ns_per_token'],
                baseline_tokens=None if act is None else act['tokens'],
                baseline_shares=None if act is None else act['kernel_shares'],
                baseline_busy_fraction=None if act is None else act['busy_fraction'], env=args.env, version=args.version,
                model=args.model, schedule=args.schedule, server_args=args.server_args), indent=1))
        else:
            summary['episode'] = controller.finish()
    except Exception as e:
        summary['error'] = f'{type(e).__name__}: {e}'
    finally:
        if gpu:
            gpu.close()
        if not args.unprofiled:
            subprocess.run(['nsys', 'shutdown', f'--session={session}'], capture_output=True)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=90)
        except subprocess.TimeoutExpired:
            proc.kill()
        for f in files.values():
            f.close()
        log.close()
        (out / 'summary.json').write_text(json.dumps(summary, indent=1, default=str))
        print(json.dumps({k: summary.get(k) for k in ('error', 'requests', 'episode')}, default=str))


if __name__ == '__main__':
    main()
