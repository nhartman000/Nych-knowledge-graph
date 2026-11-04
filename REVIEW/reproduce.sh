#!/usr/bin/env bash
# One-command reproduction for third-party review. Run from a fresh clone:
#   bash REVIEW/reproduce.sh            # venv + pinned deps, checksums, rebuild store, tests, nych3-eval, tech.ui coverage
#   PY=/path/to/python bash REVIEW/reproduce.sh   # reuse an existing interpreter that already has REVIEW/requirements.lock installed
# Network: pip (PyPI + spaCy model wheel from GitHub) and, only if REVIEW/_run/corpus/ lacks them, 4 Project Gutenberg books
#   (an existing shared/data/corpus/ is only READ, to seed REVIEW/_run/corpus/ and avoid re-downloading).
# Write locations: inside the repository, only REVIEW/_run/ (gitignored): venv, pip cache, Gutenberg cache
#   (NYCH3_CORPUS_DIR), rebuilt store, harvest output, pytest temp dirs (--basetemp) and logs. Python bytecode is
#   disabled (PYTHONDONTWRITEBYTECODE=1) and pytest's cache plugin is off. The user-level pip config is not changed. Outside the repo, kg_run/nych3 use short-lived tempfile.TemporaryDirectory() dirs (auto-deleted).
#   Exit code != 0 on any failed check.
set -euo pipefail
cd "$(dirname "$0")/.."; ROOT=$PWD; RUN=$ROOT/REVIEW/_run; mkdir -p "$RUN"; LOG=$RUN/reproduce.log; : > "$LOG"
ts() { TZ=America/New_York date '+%Y-%m-%d %H:%M:%S %Z'; }
say() { echo "[$(ts)] $*" | tee -a "$LOG"; }
export PYTHONDONTWRITEBYTECODE=1 PIP_CACHE_DIR=$RUN/pip-cache NYCH3_CORPUS_DIR=$RUN/corpus
mkdir -p "$NYCH3_CORPUS_DIR"
if [ -d shared/data/corpus ]; then for f in shared/data/corpus/*.html; do [ -e "$f" ] && cp -n "$f" "$NYCH3_CORPUS_DIR/"; done; fi
FAIL=0; check() { if eval "$2" >>"$LOG" 2>&1; then say "PASS  $1"; else say "FAIL  $1"; FAIL=1; fi; }
if [ -z "${PY:-}" ]; then
  say "creating venv $RUN/venv"; python3 -m venv "$RUN/venv"; PY=$RUN/venv/bin/python
  "$PY" -m pip install -q --upgrade pip >>"$LOG" 2>&1
  "$PY" -m pip install -q -r REVIEW/requirements.lock >>"$LOG" 2>&1
fi
export PYTHONPATH=$ROOT/shared:$ROOT/stages/04-kg-run
say "python: $("$PY" -c 'import sys;print(sys.version.split()[0])')"
check "pinned versions (python 3.13, spaCy 3.8.18, en_core_web_sm 3.8.0, kuzu 0.11.3)" \
  "\"$PY\" -c 'import sys,spacy,kuzu,en_core_web_sm as m; assert sys.version_info[:2]==(3,13); assert spacy.__version__==\"3.8.18\" and m.__version__==\"3.8.0\" and kuzu.__version__==\"0.11.3\"'"
check "spaCy model files match REVIEW/model.sha256" "\"$PY\" REVIEW/tools/model_hash.py --check REVIEW/model.sha256"
# inputs: public-domain books by Gutenberg ID/URL (fetched politely only if missing), then checksums
check "fetch missing Gutenberg sources into REVIEW/_run/corpus (by ID/URL from _config registry)" "\"$PY\" -c 'from nych3.harvest.source import sources, fetch; [fetch(b) for b in sources()[\"books\"]]'"
check "Gutenberg corpus checksums (REVIEW/corpus.sha256, 4 books in REVIEW/_run/corpus)" "(cd \"$NYCH3_CORPUS_DIR\" && sha256sum -c \"$ROOT/REVIEW/corpus.sha256\")"
check "input checksums (gold set, tech.ui export incl. unmapped records, registries)" "sha256sum -c REVIEW/inputs.sha256"
# rebuild the store from scratch in a temp location (never touches shared/data/tote.kuzu)
DB=$RUN/tote.kuzu; rm -rf "$DB" "$DB.wal" "$RUN/harvest"
check "rebuild seed store" "\"$PY\" -m nych3.store.tote_db --db \"$DB\""
check "harvest 4 books (parallel, deterministic)" "\"$PY\" -m nych3.harvest.cli --db \"$DB\" --out \"$RUN/harvest\" prun --workers 4"
check "ingest tech.ui (provisional)" "\"$PY\" -m nych3.harvest.tech_ui --db \"$DB\" > \"$RUN/tech_ui_ingest.json\""
check "store totals == REVIEW/expected_store.json" "\"$PY\" REVIEW/tools/store_totals.py \"$DB\" --check REVIEW/expected_store.json --out \"$RUN/store_totals.json\""
check "pytest (full suite)" "(cd \"$ROOT\" && \"$PY\" -m pytest -q -p no:cacheprovider --basetemp=\"$RUN/pytest-tmp\" > \"$RUN/pytest.txt\" 2>&1; rc=\$?; tail -1 \"$RUN/pytest.txt\"; exit \$rc)"
check "nych3-eval on gold_v1 (AGENT-GRADED) == REVIEW/expected_eval.json" "\"$PY\" -m nych3.eval.accuracy --json \"$RUN/eval.json\" > \"$RUN/eval.txt\" && \"$PY\" REVIEW/tools/compare_eval.py \"$RUN/eval.json\" REVIEW/expected_eval.json"
check "tech.ui coverage: denominator rebuilt from mapped + unmapped export == committed coverage.json" "\"$PY\" REVIEW/tools/tech_ui_coverage.py shared/data/tech_ui > \"$RUN/tech_ui_coverage.txt\""
say "outputs in $RUN ; overall: $([ $FAIL = 0 ] && echo ALL PASS || echo SOME CHECKS FAILED)"
exit $FAIL
