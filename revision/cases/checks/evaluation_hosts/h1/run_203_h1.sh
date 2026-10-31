#!/bin/bash
# Block 203 (author decision 2026-10-29: three blocks, 204-205 decided later). Starts when this host's current queue ends.
# Split for balance: ctl_persistent runs ~16 min per session (no recovery tail), so it gets a host of its own with shift.
cd /workspace/cases
while kill -0 27589 2>/dev/null; do sleep 30; done
export HF_HOME=/dev/shm/hf-cache
./queue_evaluation.sh "203" "6240 7619 7592"
CTL="ctl_withhold" ./queue_evaluation.sh "203" controlled
