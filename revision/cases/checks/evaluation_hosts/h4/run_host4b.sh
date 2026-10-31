#!/bin/bash
# Host #4 after the orphaned-server failure: block 202 controlled, part B. #3087's failed sessions move to host #1.
cd /workspace/cases
export HF_HOME=/workspace/hf-cache
CTL="ctl_shift ctl_overlap ctl_persistent ctl_withhold" ./queue_evaluation.sh "202" controlled
