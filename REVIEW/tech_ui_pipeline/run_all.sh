#!/usr/bin/env bash
# Full pipeline. Scrapes are resumable (cached in data/raw/); rerun to continue.
set -e; cd "$(dirname "$0")"; PY=.venv/bin/python
if [ "$1" = "scrape" ]; then
  for j in microsoft:1500 claude:400 google:450 apple:500; do DELAY=1.5 nohup $PY src/scrape.py ${j%%:*} ${j##*:} > logs/${j%%:*}.log 2>&1 & done; wait
fi
$PY src/extract.py && $PY src/parse.py && $PY src/canon.py > /dev/null && $PY src/report.py && $PY src/export_kg.py
