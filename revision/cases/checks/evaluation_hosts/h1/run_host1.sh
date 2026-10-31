#!/bin/bash
# Host 1: #7619, #7592, #6240, blocks 201 and 202. Models in /dev/shm (125 GB, noexec: models only).
cd /workspace/cases
./queue_evaluation.sh "201 202" "7619 7592 6240"
