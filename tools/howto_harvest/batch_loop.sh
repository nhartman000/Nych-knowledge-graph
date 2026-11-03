#!/usr/bin/env bash
# Job B orchestrator: every ~90 min (until STOP_AT) rebuild the compact export from cache, ingest under the Kuzu writer lock,
# commit export (pull --rebase first; never force). Final batch runs after scrapers stop. Log: $HOWTO_RAW/batch_loop.log
set -u; cd "$(dirname "$0")/../.."; source /workspace/kgenv/bin/activate
RAW=${HOWTO_RAW:-/workspace/howto_raw}; STOP=${STOP_AT:-15:15}; export NYCH3_KUZU_BUFFER_POOL=$((2<<30))
GIT=(git -c "user.name=Grok Bot (for N Hartman)" -c user.email=grokbot@localhost)
batch() {
  n=$1; echo "[$(date +%H:%M)] batch $n build" >> $RAW/batch_loop.log
  python tools/howto_harvest/build.py >| $RAW/build.log 2>&1 || { echo build failed >> $RAW/batch_loop.log; return; }
  flock /workspace/kg.ingest.lock env PYTHONPATH=shared python -m nych3.harvest.howto >| $RAW/ingest_logs/batch$n.json 2>| $RAW/ingest_logs/batch$n.err
  echo "[$(date +%H:%M)] batch $n ingest rc=$? $(head -c 300 $RAW/ingest_logs/batch$n.json | tr '\n' ' ')" >> $RAW/batch_loop.log
  "${GIT[@]}" add shared/data/howto && "${GIT[@]}" commit -qm "Harvest job B batch $n: compact howto export update" && \
  "${GIT[@]}" pull --rebase --autostash -q origin nych3-integration && "${GIT[@]}" push -q origin nych3-integration
  echo "[$(date +%H:%M)] batch $n commit $(git log -1 --format=%h)" >> $RAW/batch_loop.log
}
n=${START_N:-2}
while [[ $(date +%H:%M) < "$STOP" ]]; do
  sleep 5400; [[ $(date +%H:%M) < "$STOP" ]] || break; batch $n; n=$((n+1))
done
while pgrep -f "howto_harvest/scrape.py|python scrape.py" >/dev/null; do sleep 20; done
batch final; echo "[$(date +%H:%M)] DONE" >> $RAW/batch_loop.log
