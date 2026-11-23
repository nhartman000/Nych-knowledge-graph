"""Stage 06 CLI.

  python -m nych3.taxonomy.cli fetch                       # download pinned public inputs, check SHA-256
  python -m nych3.taxonomy.cli build [--db PATH] [--no-spacy]
  python -m nych3.taxonomy.cli resolve "text ..." [--db PATH] [--k 5]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from ..config import CONFIG, SHARED
from .build import build, load_sources
from .resolve import resolve

REGISTRY = CONFIG / "registries" / "taxonomy_sources.json"
DATA = SHARED / "data" / "taxonomy"


def fetch() -> None:
    reg = json.loads(REGISTRY.read_text())
    DATA.mkdir(parents=True, exist_ok=True)
    for key, item in reg["inputs"].items():
        if item["how"] != "fetch":
            continue
        target = DATA / item["file"]
        if not target.exists():
            req = urllib.request.Request(item["url"], headers={"User-Agent": "Mozilla/5.0 nych-knowledge-graph"})
            with urllib.request.urlopen(req) as r:
                target.write_bytes(r.read())
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise SystemExit(f"{item['file']}: sha256 {digest} != pinned {item['sha256']}")
        print("ok", item["file"])


def _open(db: str, read_only: bool):
    from ..store.tote_db import ToteDB

    return ToteDB(db, rebuild=False, seed=False, read_only=read_only) if Path(db).exists() else ToteDB(db, rebuild=True)


def main(argv=None) -> None:
    from ..store.tote_db import DEFAULT_DB

    p = argparse.ArgumentParser(prog="python -m nych3.taxonomy.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("build")
    b.add_argument("--db", default=str(DEFAULT_DB))
    b.add_argument("--no-spacy", action="store_true", help="skip task action/object lemmas (no TOTE links)")
    r = sub.add_parser("resolve")
    r.add_argument("text")
    r.add_argument("--db", default=str(DEFAULT_DB))
    r.add_argument("--k", type=int, default=5)
    a = p.parse_args(argv)
    if a.cmd == "fetch":
        fetch()
    elif a.cmd == "build":
        src = load_sources(REGISTRY, DATA)
        nlp = None
        if not a.no_spacy:
            import spacy

            nlp = spacy.load("en_core_web_sm", disable=["ner"])
        db = _open(a.db, read_only=False)
        print(json.dumps(build(db.c, src, nlp), indent=1))
        db.close()
    else:
        db = _open(a.db, read_only=True)
        json.dump(resolve(db.c, a.text, a.k), sys.stdout, indent=1, ensure_ascii=False)
        print()
        db.close()


if __name__ == "__main__":
    main()
