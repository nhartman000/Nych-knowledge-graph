#!/bin/bash
# Detached, resumable E3b worker (PRELIMINARY). Both Gemma subjects in one process, 12 s spacing (polite: shares free
# quota with E3). Daily-quota stop (4) -> sleep to 03:10 EST and resume; transient stop (3) -> retry after 10 min, max 6.
cd /workspace/knowledge-graph; LOG=/workspace/e3b_worker.log; fails=0
for i in $(seq 1 40); do
  /workspace/kgenv/bin/python tools/e3b/run_e3b.py --gemini-free >> "$LOG" 2>&1; rc=$?; echo "$(date) EXIT $rc" >> "$LOG"
  [ $rc -eq 0 ] && exit 0
  if [ $rc -eq 4 ]; then now=$(date +%s); tgt=$(date -d "tomorrow 03:10" +%s); [ $(date +%H) -lt 3 ] && tgt=$(date -d "today 03:10" +%s); sleep $((tgt-now))
  elif [ $rc -eq 3 ] && [ $fails -lt 6 ] && ! grep -q "billing\|not tagged free_tier\|COST CAP" <(tail -n 40 "$LOG"); then fails=$((fails+1)); sleep 600
  else exit $rc; fi
done
