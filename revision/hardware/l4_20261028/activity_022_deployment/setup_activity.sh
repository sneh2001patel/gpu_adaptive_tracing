set -e
mkdir /workspace/gpu_adaptive_tracing_step022
tar -xzf /tmp/step022_source.tar.gz -C /workspace/gpu_adaptive_tracing_step022
mkdir -p /workspace/gpu_adaptive_tracing_step022/revision/hardware/l4_20261028
cat > /opt/supervisor-scripts/revision-l4-activity-022.sh <<'EOF'
#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step022
exec /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_activity --output revision/hardware/l4_20261028/activity_001 --model-path /dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
EOF
chmod 700 /opt/supervisor-scripts/revision-l4-activity-022.sh
cat > /etc/supervisor/conf.d/revision-l4-activity-022.conf <<'EOF'
[program:revision-l4-activity-022]
command=/opt/supervisor-scripts/revision-l4-activity-022.sh
environment=PROC_NAME="revision-l4-activity-022"
autostart=false
autorestart=false
stopsignal=INT
stopasgroup=true
killasgroup=true
stdout_logfile=/workspace/gpu_adaptive_tracing_step022/revision/hardware/l4_20261028/activity_service.log
stderr_logfile=/workspace/gpu_adaptive_tracing_step022/revision/hardware/l4_20261028/activity_service.stderr.log
stdout_logfile_maxbytes=10000000
stderr_logfile_maxbytes=10000000
EOF
supervisorctl reread
supervisorctl update revision-l4-activity-022
supervisorctl start revision-l4-activity-022
