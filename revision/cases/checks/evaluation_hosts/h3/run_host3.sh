#!/bin/bash
# Host 3: #25418 (blocks 201, 202), then block 202 controlled, first half of the conditions. Models on disk (/dev/shm is 11 GB).
cd /workspace/cases
export HF_HOME=/workspace/hf-cache
./queue_evaluation.sh "201 202" 25418
CTL="ctl_overload ctl_kv ctl_engine_stall ctl_lull" ./queue_evaluation.sh "202" controlled
