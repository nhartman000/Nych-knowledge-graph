"""
NYCH CLI

Command-line interface for inspection and visualization.
"""

import argparse
from typing import List

from .lexicon import LEXICON
from .inspection import inspect_all
from .visualizer import NychVisualizer


def cmd_inspect():
    symbols = list(LEXICON.values())
    records = inspect_all(symbols)
    for rec in records:
        print(rec)


def cmd_visualize(save: str = None):
    symbols = list(LEXICON.values())
    viz = NychVisualizer()
    viz.plot_symbols(symbols)
    viz.render(save_path=save, show=(save is None))


def main():
    parser = argparse.ArgumentParser(prog="nych")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("inspect")
    viz = sub.add_parser("visualize")
    viz.add_argument("--save", type=str)

    args = parser.parse_args()

    if args.cmd == "inspect":
        cmd_inspect()
    elif args.cmd == "visualize":
        cmd_visualize(args.save)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
