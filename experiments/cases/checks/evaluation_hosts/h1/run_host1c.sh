#!/bin/bash
# Host #1, second rerun: run_host1b.sh's sessions all failed on an orphaned v055 engine worker (missed by gpu_clear's
# first pattern). Reruns 201/3087/SS (against host #4's 201 baseline), all of 202/3087, 201/7592/FIX3 and 202/7592/CR.
cd /workspace/cases
export HF_HOME=/dev/shm/hf-cache
D=evaluation/201/3087
for a in U NT FIX1 FIX3 CR HS; do mkdir -p $D/incident/$a && echo "ran on host #4" > $D/incident/$a/PLACEHOLDER && touch $D/incident/$a/done; done
./queue_evaluation.sh "201 202" 3087
for a in U NT FIX1 FIX3 CR HS; do [ -f $D/incident/$a/PLACEHOLDER ] && rm -rf $D/incident/$a; done
./queue_evaluation.sh "201 202" 7592
