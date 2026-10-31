#!/bin/bash
set -e
test ! -e /workspace/gpu_adaptive_tracing_step033
test ! -e /etc/supervisor/conf.d/revision-l4-challenges-v2-033.conf
mkdir /workspace/gpu_adaptive_tracing_step033
tar -xzf /tmp/step033_source.tar.gz -C /workspace/gpu_adaptive_tracing_step033
cd /workspace/gpu_adaptive_tracing_step033
mkdir -p revision/examples/event_challenges_v2/snapshot_001
install -m 600 /tmp/step033_FREEZE.json revision/examples/event_challenges_v2/snapshot_001/FREEZE.json
PYTHONPATH=/workspace/gpu_adaptive_tracing_step033 /workspace/envs/vllm/bin/python /tmp/step033_preflight.py
install -m 700 /tmp/step033_supervisor_wrapper.sh /opt/supervisor-scripts/revision-l4-challenges-v2-033.sh
install -m 600 /tmp/step033_supervisor.conf /etc/supervisor/conf.d/revision-l4-challenges-v2-033.conf
supervisorctl reread
supervisorctl update revision-l4-challenges-v2-033
supervisorctl start revision-l4-challenges-v2-033
