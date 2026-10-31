#!/bin/bash
set -e
test ! -e /workspace/gpu_adaptive_tracing_step028
test ! -e /etc/supervisor/conf.d/revision-l4-events-028.conf
mkdir /workspace/gpu_adaptive_tracing_step028
tar -xzf /tmp/step028_source.tar.gz -C /workspace/gpu_adaptive_tracing_step028
cd /workspace/gpu_adaptive_tracing_step028/revision/hardware/l4_20261028/events_028_deployment
install -m 700 supervisor_wrapper.sh /opt/supervisor-scripts/revision-l4-events-028.sh
install -m 600 supervisor.conf /etc/supervisor/conf.d/revision-l4-events-028.conf
supervisorctl reread
supervisorctl update revision-l4-events-028
supervisorctl start revision-l4-events-028
