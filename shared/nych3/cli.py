"""nych3 encode --prompt P --story FILE [--name N] [--expected-pages K] [--parser rule|spacy|auto] [--harvest]"""
from __future__ import annotations
import argparse
from pathlib import Path
from .pipeline import run
from .report import tote_table


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("encode")
    e.add_argument("--prompt", required=True); e.add_argument("--story", required=True, help="path to story text file")
    e.add_argument("--name", default="run"); e.add_argument("--expected-pages", type=int)
    e.add_argument("--parser", default="rule"); e.add_argument("--db"); e.add_argument("--harvest", action="store_true")
    a = ap.parse_args(argv)
    story = Path(a.story).read_bytes().decode("utf-8")
    state, g, gp, bp = run(a.prompt, story, name=a.name, expected_pages=a.expected_pages, parser=a.parser,
                           db_path=a.db, harvest=a.harvest)
    print(tote_table(state))
    print(f"\nwrote {gp}\nwrote {bp}")


if __name__ == "__main__":
    main()
