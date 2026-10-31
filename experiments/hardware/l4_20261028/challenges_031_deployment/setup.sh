#!/bin/bash
set -e
test ! -e /workspace/gpu_adaptive_tracing_step031
test ! -e /etc/supervisor/conf.d/revision-l4-challenges-031.conf
mkdir /workspace/gpu_adaptive_tracing_step031
tar -xzf /tmp/step031_source.tar.gz -C /workspace/gpu_adaptive_tracing_step031
cd /workspace/gpu_adaptive_tracing_step031
mkdir -p revision/examples/challenge_runner/snapshot_001
install -m 600 /tmp/step031_FREEZE.json revision/examples/challenge_runner/snapshot_001/FREEZE.json
PYTHONPATH=/workspace/gpu_adaptive_tracing_step031 /workspace/envs/vllm/bin/python /tmp/step031_preflight.py
install -m 700 /tmp/step031_supervisor_wrapper.sh /opt/supervisor-scripts/revision-l4-challenges-031.sh
install -m 600 /tmp/step031_supervisor.conf /etc/supervisor/conf.d/revision-l4-challenges-031.conf
supervisorctl reread
supervisorctl update revision-l4-challenges-031
supervisorctl start revision-l4-challenges-031
