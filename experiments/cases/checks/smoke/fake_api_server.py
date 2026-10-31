"""Fake vLLM OpenAI server for smoke tests: capacity 4 concurrent; latency grows when overloaded."""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
port = int(sys.argv[sys.argv.index('--port') + 1])
import os; hang_after = float(os.environ['FAKE_METRICS_HANG_AFTER']) if 'FAKE_METRICS_HANG_AFTER' in os.environ else None; started = time.time()
state = dict(running=0, waiting=0, preempt=0, prompt=0, gen=0); lock = threading.Lock(); sem = threading.Semaphore(4)
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, body, ctype='application/json'):
        b = body.encode(); self.send_response(200); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == '/health': return self._send('{}')
        if self.path == '/metrics':
            if hang_after is not None and time.time() - started > hang_after:
                time.sleep(3600)  # blocked like an event loop busy with host-side work
            with lock: s = dict(state)
            return self._send(f'vllm:num_requests_running{{model_name="m"}} {s["running"]}\nvllm:num_requests_waiting{{model_name="m"}} {s["waiting"]}\nvllm:gpu_cache_usage_perc{{model_name="m"}} 0.3\nvllm:num_preemptions_total{{model_name="m"}} {s["preempt"]}\nvllm:prompt_tokens_total{{model_name="m"}} {s["prompt"]}\nvllm:generation_tokens_total{{model_name="m"}} {s["gen"]}\n', 'text/plain')
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        with lock: state['waiting'] += 1
        with sem:
            with lock: state['waiting'] -= 1; state['running'] += 1
            time.sleep(0.4)
            with lock: state['running'] -= 1; state['prompt'] += 200; state['gen'] += 16
        self._send(json.dumps(dict(choices=[dict(text='ok')])))
ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
