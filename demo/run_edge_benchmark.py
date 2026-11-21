#!/usr/bin/env python3
# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Edge-device ("gumball machine") footprint benchmark, one command:

  python demo/run_edge_benchmark.py                      # trains a PLACEHOLDER model if no weights given
  python demo/run_edge_benchmark.py --package <D16 dir>  # real trained weights (or set NYCH_WEIGHTS)
  python demo/run_edge_benchmark.py --quick              # smoke run

Writes demo/results/edge-footprint.{md,html,json}. Constraints are SIMULATED on x86; see the page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edge_bench.run import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
