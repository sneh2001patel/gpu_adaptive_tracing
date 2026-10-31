#!/bin/bash
set -euo pipefail
cd /workspace/gpu_adaptive_tracing_step033
PYTHONPATH="$PWD" /workspace/envs/vllm/bin/python /tmp/step033_post_cleanup_check.py
cp /opt/supervisor-scripts/revision-l4-challenges-v2-033.sh installed_supervisor_wrapper.sh
cp /etc/supervisor/conf.d/revision-l4-challenges-v2-033.conf installed_supervisor.conf
tar -czf /tmp/step033_results.tar.gz \
 revision/hardware/l4_20261028/challenges_v2_001 \
 preflight.json post_cleanup_checks.json challenges_service.log challenges_service.stderr.log \
 installed_supervisor_wrapper.sh installed_supervisor.conf
sha256sum /tmp/step033_results.tar.gz
