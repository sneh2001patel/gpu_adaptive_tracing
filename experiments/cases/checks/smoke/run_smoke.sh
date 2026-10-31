#!/bin/bash
# Local end-to-end smoke test of run_episode.py against a fake vLLM server (no GPU, no Nsight; --unprofiled).
# Usage: experiments/cases/checks/smoke/run_smoke.sh <scratch dir>
set -euo pipefail
C=$(cd "$(dirname "$0")/.." && pwd); R=$(cd "$C/../.." && pwd); S=$1
rm -rf "$S" && mkdir -p "$S"/ext "$S"/fakeenv/bin "$S"/fakepkg/vllm/entrypoints/openai
cp "$C"/run_episode.py "$C"/make_schedule.py "$C"/case_workloads.py "$C"/case_server.py "$C"/run_case.py "$S"/
cp "$R"/tracing/{episode_controller,external_instrument,rule_diagnosis,policies}.py "$S"/ext/
ln -s "$(command -v python3)" "$S"/fakeenv/bin/python
mkdir -p "$S"/fakepkg/vllm/model_executor/layers/quantization
for d in vllm vllm/entrypoints vllm/entrypoints/openai vllm/model_executor vllm/model_executor/layers \
         vllm/model_executor/layers/quantization; do touch "$S"/fakepkg/$d/__init__.py; done
echo 'def cutlass_fp8_supported(): return True' > "$S"/fakepkg/vllm/model_executor/layers/quantization/fp8.py
cp "$C"/smoke/fake_api_server.py "$S"/fakepkg/vllm/entrypoints/openai/api_server.py
cd "$S"
python3 make_schedule.py --pattern healthy --model m --base-rate 4 --warmup 5 --incident 5 --tail 5 --out healthy.jsonl
python3 make_schedule.py --pattern overload --model m --base-rate 4 --high-rate 25 --warmup 8 --incident 12 --tail 6 --out overload.jsonl
PYTHONPATH="$S"/fakepkg python3 run_episode.py --env fakeenv --version 0.5.5 --model m --schedule healthy.jsonl \
  --out base --baseline-out baseline.json --unprofiled --drain-seconds 3
echo '{"latency_ratio":1.5,"waiting_requests":4,"kv_usage":0.9,"preemptions_per_s":0.5,"gpu_util":0.6,"busy_fraction":0.5,"kernel_time_ratio":1.3}' > thr.json
PYTHONPATH="$S"/fakepkg python3 run_episode.py --env fakeenv --version 0.5.5 --model m --schedule overload.jsonl \
  --out nt --arm NT --thresholds thr.json --baseline baseline.json --unprofiled --drain-seconds 3
# Case path: registry -> schedule -> run_case.py -> case_server.py patch -> server (v051 is the fake env here).
ln -s fakeenv v051
python3 make_schedule.py --pattern overload --case 6240 --side fixed --model m --base-rate 4 --high-rate 25 \
  --warmup 4 --incident 6 --tail 3 --out case.jsonl
CASE_ALLOW_MODEL_MISMATCH=1 PYTHONPATH="$S"/fakepkg python3 run_case.py --case 6240 --side fixed --out case6240 --schedule case.jsonl --arm NT \
  --thresholds thr.json --baseline baseline.json --unprofiled --drain-seconds 3
grep -q 'case_server: patch 6240_cutlass_off applied' case6240/server.log && echo "smoke: case patch applied"
# Incomplete evidence: withheld fields reach the controller as None; the observed values are still logged.
PYTHONPATH="$S"/fakepkg python3 run_episode.py --env fakeenv --version 0.5.5 --model m --schedule overload.jsonl \
  --out withheld --arm NT --thresholds thr.json --baseline baseline.json --unprofiled --drain-seconds 3 --withhold kv_usage,heavy
python3 -c "import json; e=[json.loads(l) for l in open('withheld/events.jsonl')][-1]; assert e['cheap']['kv_usage'] is None and e['observed']['kv_usage'] == 0.3, e; print('smoke: withheld ok')"
# A server whose /metrics stops answering: windows record the scrape error and continue (vllm#25418 stall).
PYTHONPATH="$S"/fakepkg FAKE_METRICS_HANG_AFTER=5 python3 run_episode.py --env fakeenv --version 0.5.5 --model m \
  --schedule healthy.jsonl --out hang --arm NT --thresholds thr.json --baseline baseline.json --unprofiled \
  --drain-seconds 2 --scrape-timeout 0.5
python3 -c "import json; s=json.load(open('hang/summary.json')); e=[json.loads(l) for l in open('hang/events.jsonl')]; assert s.get('error') is None and s['requests']['ok'] > 0, s; assert any(x['scrape_error'] for x in e) and all(x['cheap']['waiting_requests'] is None for x in e if x['scrape_error']); print('smoke: metrics hang tolerated')"
# Profiled path with a fake nsys: baseline burst, then scheduled calibration bursts that never reach the controller.
mkdir -p "$S"/fakebin && printf '#!/bin/sh\nexec python3 %s "$@"\n' "$C/smoke/fake_nsys.py" > "$S"/fakebin/nsys && chmod +x "$S"/fakebin/nsys
export FAKE_NSYS_STATE="$S"/nsys_state.json
PATH="$S"/fakebin:$PATH PYTHONPATH="$S"/fakepkg python3 run_episode.py --env fakeenv --version 0.5.5 --model m \
  --schedule healthy.jsonl --out pbase --baseline-out pbaseline.json --drain-seconds 2 --burst-seconds 0.5
PATH="$S"/fakebin:$PATH PYTHONPATH="$S"/fakepkg python3 run_episode.py --env fakeenv --version 0.5.5 --model m \
  --schedule overload.jsonl --out pcal --arm NT --thresholds thr.json --baseline pbaseline.json --drain-seconds 2 \
  --burst-seconds 0.5 --calibration-bursts 9,14,19
python3 - <<'PY'
import json
b = json.load(open('pbaseline.json'))
assert b['baseline_ns_per_token'] and set(b['baseline_ns_per_token']) == {'gemm', 'attention'}, b
ev = [json.loads(l) for l in open('pcal/events.jsonl')]
cal = [e for e in ev if e['kind'] == 'calibration_burst']
bursts = [json.loads(l) for l in open('pcal/bursts.jsonl')]
assert len(cal) == 3 and all(e['failure'] is None for e in cal), cal
assert all(x['activity'] and x['activity']['family_ns_per_token'] for x in bursts), bursts
assert not any(e['kind'] == 'burst' for e in ev) and json.load(open('pcal/summary.json'))['episode']['bursts'] == 0
print('smoke: calibration bursts ok', [x['capture_id'] for x in bursts])
PY
