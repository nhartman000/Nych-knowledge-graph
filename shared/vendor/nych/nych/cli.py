import argparse
import json
from nych.competency import analyze_utterance
from nych.lexicon import LEXICON
from nych.semantic_encoding import audit_summary, encode_text
from nych.state_roles import tag_roles
from nych.tote_lookup import lookup_loop


def cmd_inspect(args):
    print("NYCH INSPECT")
    print("============")
    for glyph, sym in LEXICON.items():
        print(
            f"{glyph} | meaning={sym.meaning} | address={sym.address}"
        )


def cmd_visualize(args):
    # Imported lazily so the matplotlib dependency is only required for
    # the visualize subcommand, not for parse/analyze/encode/lookup/gst.
    from nych.visualizer import NychVisualizer

    viz = NychVisualizer()
    viz.plot_symbols(list(LEXICON.values()))

    if args.save:
        viz.save(args.save)
        print(f"saved visualization to {args.save}")

    if args.show or not args.save:
        viz.show()


def _sense_bindings(values):
    result = {}
    for value in values or []:
        try:
            position, sense_id = value.split("=", 1)
            result[int(position)] = sense_id
        except (ValueError, TypeError) as exc:
            raise SystemExit(f"invalid --sense {value!r}; expected POSITION=SENSE_ID") from exc
    return result


def cmd_encode(args):
    encoded, records = encode_text(
        args.text,
        sense_choices=_sense_bindings(args.sense),
        registry_path=args.registry,
        enable_spans=not args.no_spans,
    )
    payload = {"original": args.text, "encoded": encoded, "records": records,
               "audit": audit_summary(records)}
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else encoded)


def cmd_analyze(args):
    result = analyze_utterance(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_parse(args):
    print(json.dumps(tag_roles(args.text), ensure_ascii=False, indent=2))


def cmd_lookup(args):
    roles = tag_roles(args.text)
    result = lookup_loop(roles, args.db, domain=args.domain, subdomain=args.subdomain)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_skeleton(args):
    from nych.skeleton import describe
    print(json.dumps(describe(args.word, args.namespace),
                     ensure_ascii=False, indent=2))


def cmd_gst(args):
    from nych.gst_export import build_gst, write_gst
    from nych.session_invariants import SessionInvariants

    session = SessionInvariants.load(args.pins) if args.pins else None
    payload = build_gst(args.text, db_path=args.db, session=session,
                        subdomain=args.subdomain, dither=args.dither)
    if args.out:
        write_gst(payload, args.out)
        print(f"wrote {args.out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(prog="nych")
    sub = parser.add_subparsers(dest="command")

    inspect_p = sub.add_parser("inspect", help="inspect NYCH symbols")
    inspect_p.set_defaults(func=cmd_inspect)

    vis_p = sub.add_parser("visualize", help="visualize NYCH locality")
    vis_p.add_argument("--save", type=str, default=None)
    vis_p.add_argument("--show", action="store_true")
    vis_p.set_defaults(func=cmd_visualize)

    encode_p = sub.add_parser("encode", help="sense-first semantic encoding")
    encode_p.add_argument("text")
    encode_p.add_argument("--sense", action="append", default=[],
                          help="explicit zero-based POSITION=SENSE_ID binding")
    encode_p.add_argument("--registry", default=None, help="alternate registry JSON")
    encode_p.add_argument("--no-spans", action="store_true", help="disable multiword Gestalts")
    encode_p.add_argument("--json", action="store_true", help="include records and audit")
    encode_p.set_defaults(func=cmd_encode)

    analyze_p = sub.add_parser(
        "analyze", help="vernacular-based modality/domain classification + competency score"
    )
    analyze_p.add_argument("text")
    analyze_p.set_defaults(func=cmd_analyze)

    parse_p = sub.add_parser(
        "parse", help="pre-Gestalt state-role tagging (action/enumerator/object/tense/state)"
    )
    parse_p.add_argument("text")
    parse_p.set_defaults(func=cmd_parse)

    lookup_p = sub.add_parser(
        "lookup",
        help="tag state roles, then look up a known TOTE loop in a "
             "T.O.T.E-loops SQLite database (falls back to the raw roles)",
    )
    lookup_p.add_argument("text")
    lookup_p.add_argument("--db", required=True,
                          help="path to a T.O.T.E-loops tote_loops.sqlite3 database")
    lookup_p.add_argument("--domain", default=None,
                          help="nych competency domain label (e.g. COMPUTER_SCIENCE)")
    lookup_p.add_argument("--subdomain", default=None,
                          help="TOTE loop_id namespace prefix (e.g. code, ai)")
    lookup_p.set_defaults(func=cmd_lookup)

    skeleton_p = sub.add_parser(
        "skeleton", help="consonant-skeleton disambiguation clue for one word"
    )
    skeleton_p.add_argument("word")
    skeleton_p.add_argument("--namespace", default="gestalt")
    skeleton_p.set_defaults(func=cmd_skeleton)

    gst_p = sub.add_parser(
        "gst",
        help="run the full deterministic pre-LLM pipeline and emit the .gst "
             "pretext for the LLM pruning/Gestalt-mapping step",
    )
    gst_p.add_argument("text")
    gst_p.add_argument("--db", default=None,
                       help="optional T.O.T.E-loops SQLite database path")
    gst_p.add_argument("--subdomain", default=None,
                       help="TOTE loop_id namespace prefix (e.g. code, ai)")
    gst_p.add_argument("--dither", type=float, default=0.1,
                       help="boundary-leakage margin for the LLM prune (0-1)")
    gst_p.add_argument("--pins", default=None,
                       help="path to a saved #temp-invariant session pin file")
    gst_p.add_argument("--out", default=None,
                       help="write the .gst JSON to this path instead of stdout")
    gst_p.set_defaults(func=cmd_gst)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
