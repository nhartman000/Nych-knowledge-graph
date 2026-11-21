# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Edge footprint benchmark: quantization, the NumPy decoder, slow-storage simulation, limits, report.
Offline. Tests that need PyTorch or nych-language-model skip when they are missing."""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))

from edge_bench import limits, report, slowio, weights  # noqa: E402
from edge_bench.npdecoder import NumpyDecoder  # noqa: E402
from edge_bench.profiles import StorageProfile  # noqa: E402


# ------------------------------------------------------------- quantization and estimates

def test_int8_roundtrip_error_is_within_half_a_step():
    w = np.random.default_rng(0).normal(size=(64, 128)).astype(np.float32)
    q, s = weights.quantize_int8(w)
    assert q.dtype == np.int8 and s.shape == (64,)
    assert np.all(np.abs(weights.dequantize_int8(q, s) - w) <= s[:, None] / 2 + 1e-6)


def test_int4_packs_two_weights_per_byte_and_roundtrips():
    w = np.random.default_rng(1).normal(size=(8, 64)).astype(np.float32)
    packed, scale = weights.quantize_int4(w)
    assert packed.shape == (8, 32) and packed.dtype == np.uint8 and scale.shape == (8, 2)
    back = weights.dequantize_int4(packed, scale)
    step = np.repeat(scale.astype(np.float32), weights.GROUP, axis=1)
    assert np.all(np.abs(back - w) <= step * 0.5 + 1e-3)


def test_int4_rejects_width_not_multiple_of_group():
    with pytest.raises(ValueError):
        weights.quantize_int4(np.zeros((2, 30), np.float32))


def test_size_estimates_match_d14_band():
    cfg = {"d_model": 128, "n_layers": 2, "n_heads": 4, "ffn_width": 512}
    assert weights.parameter_count(dict(cfg, vocab_size=10000)) == 1_804_928    # D14 low end
    assert weights.parameter_count(dict(cfg, vocab_size=50257)) == 6_957_824    # D14 high end
    est = weights.size_estimates(30_000_000)
    assert est["float32_bytes"] == 120_000_000
    assert 15_000_000 < est["int4_bytes"] < 17_500_000        # ~15 MB plus scales
    assert est["int4_bytes"] < est["int8_bytes"] < est["float32_bytes"]


# ------------------------------------------------------------- numpy decoder vs the reference decoder

@pytest.fixture(scope="module")
def package(tmp_path_factory):
    pytest.importorskip("torch")
    from edge_bench.placeholder import ensure_nych_lm
    try:
        ensure_nych_lm()
    except SystemExit:
        pytest.skip("nych_language_model not available")
    from nych_language_model.training.dataset import TokenDataset, write
    from nych_language_model.training.train import train
    tmp = tmp_path_factory.mktemp("edge")
    pattern = [0, 1, 2, 259, 3, 300]
    write(tmp / "data", ["a", "b", "c", "d"] + [f"w{i}" for i in range(60)], 321, pattern * 100, pattern * 20,
          {"arm": "test", "eval_words": 60})
    train(TokenDataset.load(tmp / "data"), tmp / "pkg", steps=5, batch=2, length=16, lr=1e-3,
          eval_every=0, device="cpu", seed=0, dataset_dir=tmp / "data")
    return tmp / "pkg"


def _torch_logits(package, ids):
    import torch
    from nych_language_model.training.train import load
    with torch.no_grad():
        return load(package)(torch.tensor([ids]))[0][0].numpy()


@pytest.mark.parametrize("mode", ["ram", "mmap"])
def test_numpy_decoder_matches_reference_float32(package, tmp_path, mode):
    ids = [0, 1, 2, 259, 3, 300, 5, 9]
    ref = _torch_logits(package, ids)
    _, tensors = weights.open_flat(weights.export_flat(package, tmp_path, "f32"), mode)
    model = NumpyDecoder(weights.load_config(package), tensors)
    got = np.stack([model.step(t) for t in ids])
    np.testing.assert_allclose(got, ref, atol=2e-4, rtol=1e-4)


@pytest.mark.parametrize("fmt,tol", [("int8", 0.05), ("int4", 0.5)])
def test_quantized_decoder_stays_close(package, tmp_path, fmt, tol):
    ids = [0, 1, 2, 259, 3, 300]
    ref = _torch_logits(package, ids)
    _, tensors = weights.open_flat(weights.export_flat(package, tmp_path, fmt), "mmap")
    got = np.stack(_steps(package, tensors, ids))
    assert np.max(np.abs(got - ref)) < tol


def _steps(package, tensors, ids):
    model = NumpyDecoder(weights.load_config(package), tensors)
    return [model.step(t) for t in ids]


def test_flat_file_is_smaller_when_quantized(package, tmp_path):
    sizes = {f: weights.export_flat(package, tmp_path, f).stat().st_size for f in weights.FORMATS}
    assert sizes["int4"] < sizes["int8"] < sizes["f32"]


def test_tampered_flat_file_is_refused_in_ram_mode(package, tmp_path):
    path = weights.export_flat(package, tmp_path, "int8")
    data = bytearray(path.read_bytes())
    data[100] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="does not match"):
        weights.open_flat(path, "ram")


def test_tampered_package_is_refused(package, tmp_path):
    import shutil
    copy = tmp_path / "pkg"
    shutil.copytree(package, copy)
    with open(copy / "model.pt", "ab") as handle:
        handle.write(b"x")
    with pytest.raises(ValueError, match="manifest"):
        weights.verify_package(copy)


def test_kv_cache_limit(package, tmp_path):
    _, tensors = weights.open_flat(weights.export_flat(package, tmp_path, "f32"), "ram")
    cfg = dict(weights.load_config(package), max_seq_len=4)
    model = NumpyDecoder(cfg, tensors)
    for t in range(4):
        model.step(t)
    with pytest.raises(ValueError):
        model.step(0)


# ------------------------------------------------------------- slow storage simulation

SLOW = StorageProfile("test", 4e6, 0.001, "4 MB/s")


def test_throttled_read_never_beats_the_bandwidth(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(os.urandom(2_000_000))
    t = time.perf_counter()
    assert slowio.throttled_read(path, SLOW) == path.read_bytes()
    assert time.perf_counter() - t >= 2_000_000 / 4e6


def test_eviction_and_mincore_count_only_touched_pages(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(os.urandom(4 << 20))
    slowio.evict(path)
    if sum(slowio.residency(path)) > 16:
        pytest.skip("filesystem does not honour POSIX_FADV_DONTNEED")
    mm = np.memmap(path, dtype=np.uint8, mode="r")
    int(mm[:4096].sum())
    cost = slowio.sd_cost([path], SLOW)
    assert 0 < cost["bytes_read_from_storage"] < (4 << 20)          # readahead, not the whole file
    assert cost["modeled_storage_s"] >= cost["bytes_read_from_storage"] / 4e6


# ------------------------------------------------------------- limits

def test_memory_watchdog_kills_a_process_over_budget():
    code = "import time; x = bytearray(200 * 1024 * 1024); x[::4096] = b'1' * len(x[::4096]); time.sleep(2)"
    res = limits.run_limited([sys.executable, "-c", code], cpus=1, memory_mib=64, env=dict(os.environ))
    assert res["exceeded_memory"] and res["returncode"] != 0


def test_cpu_pinning_limits_affinity():
    code = "import os; print(len(os.sched_getaffinity(0)))"
    res = limits.run_limited([sys.executable, "-c", code], cpus=1, memory_mib=512, env=dict(os.environ))
    assert res["stdout"].strip() == "1" and not res["exceeded_memory"]


# ------------------------------------------------------------- report

def _fake_results(placeholder=True):
    ok_model = lambda engine, fmt, load, storage, profile: {  # noqa: E731
        "kind": "model", "profile": profile, "engine": engine, "format": fmt, "load": load, "storage": storage,
        "status": "ok", "exceeded_memory": False, "watchdog_peak_tree_rss_mib": 40.0, "peak_rss_mib": 45.0,
        "rss_after_import_mib": 30.0, "load_s": 0.01, "verify_s": 0.02, "first_call_prompt_s": 0.03,
        "per_token_s": 0.001, "resident_weight_bytes": 2e6,
        "sd_read": {"bytes_read_from_storage": 2e6, "read_requests": 1, "modeled_storage_s": 0.08}}
    runs = []
    for profile in ("1cpu-512mb", "4cpu-1gb"):
        runs += [{"kind": "pipeline", "profile": profile, "variant": "device install (no PyTorch)", "status": "ok",
                  "exceeded_memory": False, "watchdog_peak_tree_rss_mib": 160.0, "peak_rss_mib": 150.0,
                  "first_procedure_s": 1.5, "checklist_s_per_procedure": 0.05, "audit_s_per_procedure": 2.0,
                  "total_s_per_procedure": 2.05, "audit_log_bytes_per_procedure": 1e5},
                 {"kind": "pipeline", "profile": profile, "variant": "as installed here (PyTorch present)",
                  "status": "error", "exceeded_memory": True, "watchdog_peak_tree_rss_mib": 520.0}]
        for engine, fmt in (("numpy", "int8"), ("numpy", "f32"), ("torch", "f32")):
            for load in ("ram", "mmap"):
                runs.append(ok_model(engine, fmt, load, "sd-card", profile))
        runs.append({"kind": "combined", "profile": profile, "status": "ok", "exceeded_memory": False,
                     "watchdog_peak_tree_rss_mib": 170.0, "peak_rss_mib": 160.0, "model_calls": 9,
                     "pipeline_s_per_procedure": 0.4, "model_s_per_procedure": 0.06, "total_s_per_procedure": 0.5})
    est = dict(label="this model", **weights.size_estimates(1_804_928))
    return {"generated": "2026-11-21T09:00:00-05:00",
            "host": {"processor": "x86 test", "machine": "x86_64", "python": "3.13", "numpy": "2", "torch": "2.7"},
            "weights": {"placeholder": placeholder, "parameters": 1_804_928,
                        "config": {"d_model": 128, "n_layers": 2, "n_heads": 4, "ffn_width": 512, "vocab_size": 10000}},
            "profiles": {"storage": {"sd-card": {"note": "simulated A1 microSD"}}},
            "estimates": {"this_model": est, "reference": weights.reference_shapes()},
            "footprint": [{"group": "code", "item": "pipeline", "bytes": 1000, "files": 2},
                          {"group": "model weights", "item": "float32 package model.pt", "bytes": 7_224_455, "files": 1},
                          {"group": "model weights", "item": "int8 flat", "bytes": 1_860_160, "files": 1},
                          {"group": "model weights", "item": "int4 flat", "bytes": 1_100_000, "files": 1}],
            "sources": ["a.txt"], "combined_sources": ["a.txt"], "runs": runs}


def test_report_states_caveats_placeholder_and_license(tmp_path):
    report.write(_fake_results(), tmp_path)
    md = (tmp_path / "edge-footprint.md").read_text()
    page = (tmp_path / "edge-footprint.html").read_text()
    for text in (md, page):
        assert "American Milestone Inc. All rights reserved" in text
        assert "PLACEHOLDER" in text and "simulated" in text.lower() and "not a Raspberry Pi" in text
    assert "over memory limit" in md
    assert "<table>" in page and "<script" not in page


def test_report_for_real_weights_drops_placeholder_label(tmp_path):
    report.write(_fake_results(placeholder=False), tmp_path)
    assert "PLACEHOLDER" not in (tmp_path / "edge-footprint.md").read_text()


def test_first_answer_adds_modeled_sd_time():
    r = {"status": "ok", "verify_s": 0.1, "load_s": 0.2, "first_call_prompt_s": 0.3,
         "sd_read": {"modeled_storage_s": 0.4}}
    assert report.first_answer_s(r) == pytest.approx(1.0)
    assert report.first_answer_s({"status": "error"}) is None


def test_results_json_has_no_secrets():
    path = ROOT / "demo" / "results" / "edge-footprint.json"
    if not path.exists():
        pytest.skip("benchmark not run yet")
    text = path.read_text()
    for marker in ("GEMINI_API_KEY=", "OPENAI_API_KEY=", "sk-", "AIza", "gho_", "ghp_"):
        assert marker not in text
    json.loads(text)
