# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Weight packages: verification, flat export (float32 / int8 / 4-bit) and size estimates.

Input is a D16 package written by nych-language-model's B11 trainer
(model.pt, config.json, vocab.json, metrics.json, manifest.json with sha256 hashes).

Flat formats written here are plain little-endian arrays at 64-byte-aligned offsets plus a
JSON index, so they can be opened with numpy.memmap without unpickling anything:

  f32   every tensor as float32
  int8  2-D matrices as int8 with one float32 scale per output row (symmetric, weight-only);
        1-D tensors (norm scales) stay float32
  int4  2-D matrices as signed 4-bit values packed two per byte, one float16 scale per group of
        32 input weights (the same layout family as llama.cpp Q4_0); 1-D tensors stay float32
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ALIGN = 64
GROUP = 32
FORMATS = ("f32", "int8", "int4")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package(package: Path) -> dict:
    """Check every file against manifest.json (same rule as the trainer's load()). Returns the manifest."""
    package = Path(package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        if sha256(package / name) != expected:
            raise ValueError(f"{name} does not match the manifest")
    return manifest


def load_config(package: Path) -> dict:
    return json.loads((Path(package) / "config.json").read_text(encoding="utf-8"))


def parameter_count(config: dict) -> int:
    d, f, n, v = config["d_model"], config["ffn_width"], config["n_layers"], config["vocab_size"]
    return v * d + n * (4 * d * d + 3 * d * f + 2 * d) + d


# ---------------------------------------------------------------- quantization

def quantize_int8(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w = np.asarray(w, dtype=np.float32)
    scale = np.abs(w).max(axis=1) / 127.0
    scale[scale == 0] = 1.0
    q = np.clip(np.rint(w / scale[:, None]), -127, 127).astype(np.int8)
    return q, scale.astype(np.float32)


def dequantize_int8(q: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return q.astype(np.float32) * scale[:, None]


def quantize_int4(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Returns (packed uint8 [rows, cols/2], float16 scales [rows, cols/GROUP])."""
    w = np.asarray(w, dtype=np.float32)
    rows, cols = w.shape
    if cols % GROUP:
        raise ValueError(f"input width {cols} is not a multiple of {GROUP}")
    groups = w.reshape(rows, cols // GROUP, GROUP)
    scale = np.abs(groups).max(axis=2) / 7.0
    scale[scale == 0] = 1.0
    scale = scale.astype(np.float16)
    q = np.clip(np.rint(groups / scale.astype(np.float32)[:, :, None]), -8, 7).astype(np.int8)
    nib = (q.reshape(rows, cols) & 0x0F).astype(np.uint8)
    packed = nib[:, 0::2] | (nib[:, 1::2] << 4)
    return packed, scale


def dequantize_int4(packed: np.ndarray, scale: np.ndarray) -> np.ndarray:
    rows, half = packed.shape
    lo = (packed & 0x0F).astype(np.int8)
    hi = (packed >> 4).astype(np.int8)
    lo[lo > 7] -= 16
    hi[hi > 7] -= 16
    q = np.empty((rows, half * 2), dtype=np.int8)
    q[:, 0::2], q[:, 1::2] = lo, hi
    groups = q.reshape(rows, -1, GROUP).astype(np.float32) * scale.astype(np.float32)[:, :, None]
    return groups.reshape(rows, half * 2)


# ---------------------------------------------------------------- flat files

def _state_dict_numpy(package: Path) -> dict[str, np.ndarray]:
    import torch  # only the exporter needs torch; the numpy runtime does not
    state = torch.load(Path(package) / "model.pt", map_location="cpu", weights_only=True)
    return {k: v.detach().float().numpy() for k, v in state.items()}


def export_flat(package: Path, out_dir: Path, fmt: str) -> Path:
    """Write <out_dir>/<fmt>.bin and <fmt>.index.json. Returns the .bin path."""
    if fmt not in FORMATS:
        raise ValueError(fmt)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arrays: list[tuple[str, np.ndarray]] = []
    for name, w in _state_dict_numpy(package).items():
        if fmt == "f32" or w.ndim == 1:
            arrays.append((name, w.astype(np.float32)))
        elif fmt == "int8":
            q, s = quantize_int8(w)
            arrays += [(name + ".q", q), (name + ".scale", s)]
        else:
            q, s = quantize_int4(w)
            arrays += [(name + ".q4", q), (name + ".scale", s)]
    index, offset = {"format": fmt, "group": GROUP, "config": load_config(package), "tensors": {}}, 0
    bin_path = out_dir / f"{fmt}.bin"
    with open(bin_path, "wb") as handle:
        for name, arr in arrays:
            pad = (-offset) % ALIGN
            handle.write(b"\0" * pad)
            offset += pad
            data = np.ascontiguousarray(arr).astype(arr.dtype.newbyteorder("<"), copy=False).tobytes()
            index["tensors"][name] = {"offset": offset, "dtype": arr.dtype.str.lstrip("<>|="),
                                      "shape": list(arr.shape)}
            handle.write(data)
            offset += len(data)
    index["sha256"] = sha256(bin_path)
    (out_dir / f"{fmt}.index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return bin_path


def open_flat(bin_path: Path, mode: str, reader=None) -> tuple[dict, dict[str, np.ndarray]]:
    """Open a flat file. mode='mmap' maps it read-only; mode='ram' reads it fully into memory.

    `reader(path) -> bytes` lets the caller supply a throttled reader for the slow-storage profile.
    """
    bin_path = Path(bin_path)
    index = json.loads(bin_path.with_suffix(".index.json").read_text(encoding="utf-8"))
    if mode == "mmap":
        buf = np.memmap(bin_path, dtype=np.uint8, mode="r")
    elif mode == "ram":
        data = reader(bin_path) if reader else bin_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != index["sha256"]:
            raise ValueError(f"{bin_path.name} does not match its index")
        buf = np.frombuffer(bytearray(data), dtype=np.uint8)
    else:
        raise ValueError(mode)
    tensors = {}
    for name, meta in index["tensors"].items():
        dtype = np.dtype(meta["dtype"]).newbyteorder("<")
        count = int(np.prod(meta["shape"])) if meta["shape"] else 1
        nbytes = count * dtype.itemsize
        tensors[name] = buf[meta["offset"]:meta["offset"] + nbytes].view(dtype).reshape(meta["shape"])
    return index, tensors


# ---------------------------------------------------------------- estimates

def size_estimates(params: int, matrix_params: int | None = None) -> dict:
    """Bytes for float32, int8 (per-row scale) and 4-bit (fp16 scale per 32 weights).

    `matrix_params` is the share in 2-D matrices (quantized); the rest stays float32. When it is
    unknown, every parameter is treated as quantizable (a lower bound for int8/int4).
    """
    m = params if matrix_params is None else matrix_params
    rest = params - m
    return {"parameters": params,
            "float32_bytes": 4 * params,
            "int8_bytes": m + 4 * rest + int(4 * m / 128),        # ~one f32 scale per 128-wide row
            "int4_bytes": m // 2 + 2 * (m // GROUP) + 4 * rest}


def reference_shapes() -> list[dict]:
    """The D14 size band plus the 30M-parameter what-if from the owner's note."""
    base = {"d_model": 128, "n_layers": 2, "n_heads": 4, "ffn_width": 512}
    rows = []
    for label, vocab in (("D14 band low (vocab 10,000)", 10000), ("D14 band high (vocab 50,257)", 50257)):
        cfg = dict(base, vocab_size=vocab)
        p = parameter_count(cfg)
        rows.append(dict(label=label, **size_estimates(p, p - (2 * 2 * 128 + 128))))
    rows.append(dict(label="30M-parameter what-if (shape not chosen)", **size_estimates(30_000_000)))
    return rows
