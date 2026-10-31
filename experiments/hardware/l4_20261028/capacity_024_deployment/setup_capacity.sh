set -e
cat > /opt/supervisor-scripts/revision-l4-capacity-024.sh <<'SH'
#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step024
exec /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_capacity --output revision/hardware/l4_20261028/capacity_001 --model-path /dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
SH
chmod 700 /opt/supervisor-scripts/revision-l4-capacity-024.sh
cat > /etc/supervisor/conf.d/revision-l4-capacity-024.conf <<'CONF'
[program:revision-l4-capacity-024]
command=/opt/supervisor-scripts/revision-l4-capacity-024.sh
environment=PROC_NAME="revision-l4-capacity-024"
autostart=false
autorestart=false
stopsignal=INT
stopasgroup=true
killasgroup=true
stdout_logfile=/workspace/gpu_adaptive_tracing_step024/capacity_service.log
stderr_logfile=/workspace/gpu_adaptive_tracing_step024/capacity_service.stderr.log
stdout_logfile_maxbytes=10000000
stderr_logfile_maxbytes=10000000
CONF
supervisorctl reread
supervisorctl update revision-l4-capacity-024
supervisorctl start revision-l4-capacity-024
