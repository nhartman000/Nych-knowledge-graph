"""nych3-harvest run|suggest|promote|stats"""
from __future__ import annotations
import argparse, json
from ..store.tote_db import ToteDB, DEFAULT_DB
from .harvester import Harvester, HARVEST_DIR


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3-harvest")
    ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--out", default=str(HARVEST_DIR))
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--books", nargs="*"); r.add_argument("--max-sentences", type=int)
    r.add_argument("--max-seconds", type=int); r.add_argument("--parser", default="rule")
    s = sub.add_parser("suggest", help="threshold SUGGESTION only; never promotes")
    s.add_argument("--min-repeats", type=int, default=5); s.add_argument("--min-sources", type=int, default=2)
    p = sub.add_parser("promote"); p.add_argument("loop_id"); p.add_argument("--authority", required=True); p.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        st = Harvester(a.db, a.out, a.parser).run(a.books, a.max_sentences, a.max_seconds)
        print(json.dumps({k: v for k, v in st.items() if k not in ("samples_new", "error_samples")}, indent=1))
    elif a.cmd == "suggest":
        print(json.dumps(ToteDB(a.db).suggest_promotions(a.min_repeats, a.min_sources), indent=1, ensure_ascii=False))
        print("# suggestion only -- nothing was promoted. Use: nych3-harvest promote <loop_id> --authority 'Name'")
    elif a.cmd == "promote":
        ToteDB(a.db).promote(a.loop_id, a.authority, a.note); print(f"promoted {a.loop_id} (authority: {a.authority})")


if __name__ == "__main__":
    main()
