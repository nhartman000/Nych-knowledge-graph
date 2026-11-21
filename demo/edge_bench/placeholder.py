# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Find the NYCH model code and weights, or train a clearly labelled PLACEHOLDER package.

The placeholder uses nych-language-model's own B11 trainer and the approved V1 shape at the low
end of the D14 size band (vocab 10,000 -> 1,804,928 parameters), trained for a few hundred steps
on synthetic token IDs. Its size, memory and speed match a real model of that shape; its outputs
mean nothing. Results built on it are marked "placeholder" everywhere.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

PLACEHOLDER_ARM = "edge-bench-placeholder (synthetic token IDs, not NYCH text)"
PLACEHOLDER_VOCAB = 10_000          # total IDs; D14 band low end
BYTE_AND_EOW_IDS = 257


def ensure_nych_lm() -> None:
    """Make nych_language_model importable: installed, $NYCH_LM_SRC, or a sibling checkout."""
    try:
        import nych_language_model  # noqa: F401
        return
    except ImportError:
        pass
    repo = Path(__file__).resolve().parents[2]
    candidates = [os.environ.get("NYCH_LM_SRC")] + [str(repo.parent / n / "src") for n in
                                                     ("nych-language-model", "nlm")]
    for c in candidates:
        if c and (Path(c) / "nych_language_model").is_dir():
            sys.path.insert(0, c)
            return
    raise SystemExit("nych_language_model not found: pip install it, or set NYCH_LM_SRC=<checkout>/src")


def is_placeholder(package: Path) -> bool:
    manifest = json.loads((Path(package) / "manifest.json").read_text(encoding="utf-8"))
    return manifest.get("dataset_meta", {}).get("arm") == PLACEHOLDER_ARM


def build_placeholder(out_dir: Path, steps: int = 300, seed: int = 0) -> Path:
    ensure_nych_lm()
    from nych_language_model.training.dataset import TokenDataset, write
    from nych_language_model.training.train import train
    out_dir = Path(out_dir)
    if (out_dir / "manifest.json").exists() and is_placeholder(out_dir):
        return out_dir
    rng = random.Random(seed)
    words = PLACEHOLDER_VOCAB - BYTE_AND_EOW_IDS
    vocab = [f"placeholder_{i}" for i in range(words)]
    # Short repeating "phrases" over a Zipf-like word pick, so the loss can fall a little.
    phrases = [[min(words - 1, int(rng.paretovariate(1.1))) for _ in range(6)] for _ in range(400)]
    stream = [t for _ in range(4000) for t in rng.choice(phrases)]
    data_dir = out_dir.parent / (out_dir.name + "_dataset")
    write(data_dir, vocab, PLACEHOLDER_VOCAB, stream[:20000], stream[20000:24000],
          {"arm": PLACEHOLDER_ARM, "eval_words": 4000})
    train(TokenDataset.load(data_dir), out_dir, steps=steps, batch=8, length=64, lr=3e-3,
          eval_every=0, device="cpu", seed=seed, dataset_dir=data_dir)
    return out_dir
