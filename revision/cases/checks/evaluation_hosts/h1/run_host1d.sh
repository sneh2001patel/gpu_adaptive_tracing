#!/bin/bash
# Host #1, third rerun: 201/3087/CR (failed on host #4 at 22:45 UTC, wrongly placeholdered before), then all of #6240
# (both baselines failed out of memory at 01:17 UTC on the orphaned v055 worker).
cd /workspace/cases
export HF_HOME=/dev/shm/hf-cache
D=evaluation/201/3087
for a in U NT FIX1 FIX3 HS; do mkdir -p $D/incident/$a && echo "ran on host #4" > $D/incident/$a/PLACEHOLDER && touch $D/incident/$a/done; done
./queue_evaluation.sh "201" 3087
for a in U NT FIX1 FIX3 HS; do [ -f $D/incident/$a/PLACEHOLDER ] && rm -rf $D/incident/$a; done
mkdir -p evaluation_failed_orphan_server && for b in 201 202; do mv evaluation/$b/6240 evaluation_failed_orphan_server/${b}_6240; done
./queue_evaluation.sh "201 202" 6240
