#!/bin/bash
# Block 203 (author decision 2026-10-29: three blocks, 204-205 decided later). Starts when this host's current queue ends.
# Split for balance: ctl_persistent runs ~16 min per session (no recovery tail), so it gets a host of its own with shift.
cd /workspace/cases
while kill -0 5804 2>/dev/null; do sleep 30; done
export HF_HOME=/workspace/hf-cache
CTL="ctl_overload ctl_kv ctl_engine_stall ctl_lull" ./queue_evaluation.sh "203" controlled
