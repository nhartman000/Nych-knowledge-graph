# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""NumPy-only inference for the V1 NYCH decoder, with a KV cache, for small devices.

Same math as nych_language_model.model.decoder.NYCHDecoder in eval mode (pre-RMSNorm, RoPE,
causal attention, SwiGLU, tied output head), so a device does not need PyTorch to run the model.
Weights may be plain arrays, np.memmap views (weights stay on storage, pages load on demand),
or int8 matrices with per-row scales that are dequantized on the fly at each use.
"""
from __future__ import annotations

import math

import numpy as np

from .weights import dequantize_int4

EPS = 1e-6


class _Matrix:
    """y = W @ x for float32 or int8+scale weights (W stored [out, in])."""

    def __init__(self, tensors: dict, name: str):
        if name in tensors:
            self.w, self.scale = tensors[name], None
        elif name + ".q" in tensors:
            self.w, self.scale = tensors[name + ".q"], tensors[name + ".scale"]
        elif name + ".q4" in tensors:   # 4-bit: unpack once at load, keep float32 in RAM
            self.w, self.scale = dequantize_int4(tensors[name + ".q4"], tensors[name + ".scale"]), None
        else:
            raise KeyError(name)

    def __matmul__(self, x: np.ndarray) -> np.ndarray:
        if self.scale is None:
            return self.w @ x
        return (self.w @ x.astype(np.float32)) * self.scale

    def row(self, i: int) -> np.ndarray:
        r = np.asarray(self.w[i], dtype=np.float32)
        return r * self.scale[i] if self.scale is not None else r


def _rms(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    return x / np.sqrt(np.mean(x * x) + EPS) * w


class NumpyDecoder:
    def __init__(self, config: dict, tensors: dict):
        self.cfg = config
        d, h = config["d_model"], config["n_heads"]
        self.hd = d // h
        self.emb = _Matrix(tensors, "token_embeddings.embedding.weight")
        self.layers = []
        for i in range(config["n_layers"]):
            p = f"blocks.{i}."
            self.layers.append({
                "an": np.asarray(tensors[p + "attention_norm.weight"], np.float32),
                "qkv": _Matrix(tensors, p + "attention.qkv.weight"),
                "out": _Matrix(tensors, p + "attention.output.weight"),
                "fn": np.asarray(tensors[p + "feed_forward_norm.weight"], np.float32),
                "gate": _Matrix(tensors, p + "feed_forward.gate.weight"),
                "up": _Matrix(tensors, p + "feed_forward.up.weight"),
                "down": _Matrix(tensors, p + "feed_forward.down.weight"),
            })
        self.final = np.asarray(tensors["final_norm.weight"], np.float32)
        inv = 1.0 / (config["rope_theta"] ** (np.arange(0, self.hd, 2, dtype=np.float32) / self.hd))
        ang = np.outer(np.arange(config["max_seq_len"], dtype=np.float32), inv)
        self.cos, self.sin = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
        self.reset()

    def reset(self) -> None:
        n, h, L = self.cfg["n_layers"], self.cfg["n_heads"], self.cfg["max_seq_len"]
        self.k = np.zeros((n, h, L, self.hd), np.float32)
        self.v = np.zeros((n, h, L, self.hd), np.float32)
        self.pos = 0

    def _rope(self, t: np.ndarray, pos: int) -> np.ndarray:
        c, s = self.cos[pos], self.sin[pos]
        even, odd = t[:, 0::2], t[:, 1::2]
        out = np.empty_like(t)
        out[:, 0::2] = even * c - odd * s
        out[:, 1::2] = even * s + odd * c
        return out

    def step(self, token: int) -> np.ndarray:
        """Feed one token, return next-token logits (float32 [vocab])."""
        if self.pos >= self.cfg["max_seq_len"]:
            raise ValueError("sequence exceeds the 1,024 position limit")
        pos, h, hd = self.pos, self.cfg["n_heads"], self.hd
        x = self.emb.row(token)
        for li, L in enumerate(self.layers):
            qkv = (L["qkv"] @ _rms(x, L["an"])).reshape(3, h, hd)
            q, k = self._rope(qkv[0], pos), self._rope(qkv[1], pos)
            self.k[li, :, pos], self.v[li, :, pos] = k, qkv[2]
            scores = np.einsum("hd,htd->ht", q, self.k[li, :, :pos + 1]) / math.sqrt(hd)
            scores = np.exp(scores - scores.max(axis=1, keepdims=True))
            scores /= scores.sum(axis=1, keepdims=True)
            att = np.einsum("ht,htd->hd", scores, self.v[li, :, :pos + 1]).reshape(-1)
            x = x + L["out"] @ att
            f = _rms(x, L["fn"])
            g = L["gate"] @ f
            x = x + L["down"] @ ((g / (1.0 + np.exp(-g))) * (L["up"] @ f))
        self.pos += 1
        return self.emb @ _rms(x, self.final)

    def generate(self, prompt: list[int], new_tokens: int) -> list[int]:
        logits = None
        for t in prompt:
            logits = self.step(int(t))
        out = []
        for _ in range(new_tokens):
            nxt = int(np.argmax(logits))
            out.append(nxt)
            logits = self.step(nxt)
        return out
