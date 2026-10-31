#!/bin/bash
# Host 4: #3087 (blocks 201, 202), then block 202 controlled, second half of the conditions. Models on disk (/dev/shm is 11 GB).
cd /workspace/cases
export HF_HOME=/workspace/hf-cache
./queue_evaluation.sh "201 202" 3087
CTL="ctl_shift ctl_overlap ctl_persistent ctl_withhold" ./queue_evaluation.sh "202" controlled
