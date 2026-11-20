#!/bin/bash
# Detached, resumable free-tier worker for one subject. On daily-quota stop (exit 4) sleeps until 03:10 EST (after
# midnight-Pacific reset) and resumes; any other stop (billing, non-free-tier quota, errors) ends the worker.
cd /workspace/knowledge-graph
M="$1"; LOG=/workspace/e3_worker_$M.log
for day in 1 2 3 4 5 6 7; do
  /workspace/kgenv/bin/python tools/e3/run_e3.py --gemini-free --only-subject "$M" >> "$LOG" 2>&1; rc=$?
  echo "$(date) EXIT $rc" >> "$LOG"
  [ $rc -eq 4 ] || exit $rc
  now=$(date +%s); tgt=$(date -d "tomorrow 03:10" +%s); [ $(date +%H) -lt 3 ] && tgt=$(date -d "today 03:10" +%s)
  sleep $((tgt-now))
done
