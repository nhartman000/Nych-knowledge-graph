#!/usr/bin/env bash
# Self-contained review zip: tracked files only (code, compact exports, gold set, reports). No raw HTML, no Kuzu store.
set -e; cd "$(dirname "$0")/../.."; OUT=${1:-/workspace/nych3-review-package.zip}; rm -f "$OUT"
git archive --format=zip --prefix=nych3-review/ -o "$OUT" HEAD && ls -la "$OUT"
