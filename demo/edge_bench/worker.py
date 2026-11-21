# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""One measurement, run in its own process so peak RSS belongs to that workload alone.

  python -m edge_bench.worker pipeline --sources a.txt b.txt
  python -m edge_bench.worker model --package DIR --weights DIR --engine numpy --format int8 --load mmap --storage sd-card
  python -m edge_bench.worker combined ...   (pipeline and model resident in one process)

Prints one JSON object on the last stdout line.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(DEMO.parent / "shared"))

if os.environ.get("EDGE_BENCH_BLOCK_TORCH") == "1":
    # Simulate a device install without PyTorch: spaCy/thinc import torch when it is present.
    import importlib.abc

    class _NoTorch(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("torch blocked for the no-torch device profile")
            return None
    sys.meta_path.insert(0, _NoTorch())

from edge_bench import slowio  # noqa: E402
from edge_bench.profiles import STORAGE_PROFILES  # noqa: E402


def rss_mib() -> float:
    with open("/proc/self/status") as handle:
        for line in handle:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


def peak_rss_mib() -> float:
    """VmHWM: this process's peak resident set. (ru_maxrss is not used: Linux carries it across
    execve, so it would include the launching process.)"""
    with open("/proc/self/status") as handle:
        for line in handle:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    return 0.0


# ------------------------------------------------------------------ pipeline

def run_pipeline(sources: list[Path], runs: int, out: dict) -> list:
    t0 = time.perf_counter()
    from procedure_demo import audit
    from procedure_demo.checklist import build_checklist
    out["import_s"] = time.perf_counter() - t0
    out["rss_after_import_mib"] = rss_mib()
    out["heavy_modules_loaded"] = sorted({m.split(".")[0] for m in sys.modules} & {"torch", "spacy", "thinc", "kuzu", "numpy"})
    t = time.perf_counter()
    build_checklist(sources[0])
    out["first_procedure_s"] = time.perf_counter() - t   # includes lazy loading (encoder, spaCy, tables)
    build_s, audit_s, steps, checklists = [], [], 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(runs):
            for src in sources:
                t = time.perf_counter()
                cl = build_checklist(src)
                build_s.append(time.perf_counter() - t)
                t = time.perf_counter()
                audit.run_audit(cl, "all-pass", Path(tmp) / src.stem)
                ok, _problems = audit.verify_audit(Path(tmp) / src.stem)
                audit_s.append(time.perf_counter() - t)
                if not ok:
                    raise RuntimeError(f"audit chain failed for {src.name}")
                steps += len(cl["steps"])
                checklists.append(cl)
        out["audit_log_bytes_per_procedure"] = sum(
            f.stat().st_size for f in Path(tmp).rglob("*") if f.is_file()) / len(sources)
    out.update(procedures=len(sources), runs=runs, steps_per_run=steps // runs,
               checklist_s_per_procedure=sum(build_s) / len(build_s),
               audit_s_per_procedure=sum(audit_s) / len(audit_s),
               total_s_per_procedure=(sum(build_s) + sum(audit_s)) / len(build_s))
    return checklists


# ------------------------------------------------------------------ model

def _prompt(vocab_size: int, n: int, seed: int = 7) -> list[int]:
    rng = random.Random(seed)
    return [rng.randrange(vocab_size) for _ in range(n)]


def load_model(args, out: dict, storage):
    """Returns (generate(prompt, n) -> (first_token_s, per_token_s), files_backing_weights)."""
    package, weights = Path(args.package), Path(args.weights)
    config = json.loads((package / "config.json").read_text())
    reader = (lambda p: slowio.throttled_read(p, storage))
    if args.engine == "numpy":
        from edge_bench.npdecoder import NumpyDecoder
        from edge_bench.weights import open_flat
        out["rss_after_import_mib"] = rss_mib()
        bin_path = weights / f"{args.format}.bin"
        files = [bin_path]
        if args.storage != "page-cache":
            slowio.evict(bin_path)
        t = time.perf_counter()
        if args.load == "mmap":
            # Integrity check reads the file once (as the trainer's load() does); then drop it from
            # the cache again so the run starts cold and only touched pages come back.
            data = reader(bin_path)
            index = json.loads(bin_path.with_suffix(".index.json").read_text())
            if hashlib.sha256(data).hexdigest() != index["sha256"]:
                raise ValueError("weights do not match their index")
            del data
            out["verify_s"] = time.perf_counter() - t
            if args.storage != "page-cache":
                slowio.evict(bin_path)
            t = time.perf_counter()
            _, tensors = open_flat(bin_path, "mmap")
        else:
            _, tensors = open_flat(bin_path, "ram", reader=reader)   # verifies the hash while loading
        model = NumpyDecoder(config, tensors)
        out["load_s"] = time.perf_counter() - t

        def generate(prompt, n):
            model.reset()
            t0 = time.perf_counter()
            for tok in prompt:
                logits = model.step(tok)
            first = time.perf_counter() - t0
            t1 = time.perf_counter()
            tok = int(logits.argmax())
            for _ in range(n):
                tok = int(model.step(tok).argmax())
            return first, (time.perf_counter() - t1) / max(1, n)
        return generate, files

    import torch
    torch.set_num_threads(int(os.environ.get("EDGE_BENCH_THREADS", "1")))
    from nych_language_model.model.config import DecoderConfig
    from nych_language_model.model.decoder import NYCHDecoder
    out["rss_after_import_mib"] = rss_mib()
    pt = package / "model.pt" if args.format == "f32" else weights / "torch_dynamic_int8.pt"
    files = [pt]
    if args.storage != "page-cache":
        slowio.evict(pt)
    t = time.perf_counter()
    model = NYCHDecoder(DecoderConfig(**config))
    if args.format == "f32":
        from edge_bench.weights import verify_package
        if args.load == "mmap":
            # Hash every package file through the same (throttled) reader the RAM path uses.
            manifest = json.loads((package / "manifest.json").read_text())
            for name, expected in manifest["sha256"].items():
                if hashlib.sha256(reader(package / name)).hexdigest() != expected:
                    raise ValueError(f"{name} does not match the manifest")
            out["verify_s"] = time.perf_counter() - t
            if args.storage != "page-cache":
                slowio.evict(pt)
            t = time.perf_counter()
            state = torch.load(pt, map_location="cpu", weights_only=True, mmap=True)
            model.load_state_dict(state, assign=True)   # keep the mmap-backed tensors, no copy
        else:
            data = reader(pt)
            state = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
            verify_package(package)
            model.load_state_dict(state)
            del data, state
    else:  # torch dynamic int8 (nn.Linear only; the tied embedding / output head stays float32)
        model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
        data = reader(pt)
        model.load_state_dict(torch.load(io.BytesIO(data), map_location="cpu", weights_only=False))
        del data
    model.eval()
    out["load_s"] = time.perf_counter() - t

    @torch.no_grad()
    def generate(prompt, n):
        # The V1 reference decoder has no KV cache (D8), so each new token re-runs the window.
        ids = list(prompt)
        t0 = time.perf_counter()
        logits, _ = model(torch.tensor([ids]))
        first = time.perf_counter() - t0
        t1 = time.perf_counter()
        for _ in range(n):
            ids.append(int(logits[0, -1].argmax()))
            logits, _ = model(torch.tensor([ids]))
        return first, (time.perf_counter() - t1) / max(1, n)
    return generate, files


def run_model(args, out: dict) -> None:
    storage = STORAGE_PROFILES[args.storage]
    config = json.loads((Path(args.package) / "config.json").read_text())
    generate, files = load_model(args, out, storage)
    out["rss_after_load_mib"] = rss_mib()
    prompt = _prompt(config["vocab_size"], args.prompt_tokens)
    first, per = generate(prompt, args.new_tokens)            # cold: pages fault in here when mapped
    out["first_call_prompt_s"] = first
    out["cold_per_token_s"] = per
    if args.load == "mmap" and args.storage != "page-cache":
        out["sd_read"] = slowio.sd_cost(files, storage)
    first, per = generate(prompt, args.new_tokens)             # warm
    out["warm_prompt_s"] = first
    out["per_token_s"] = per
    out["prompt_tokens"], out["new_tokens"] = args.prompt_tokens, args.new_tokens
    out["resident_weight_bytes"] = slowio.resident_bytes(files)
    out["weight_file_bytes"] = sum(os.path.getsize(f) for f in files)


def run_combined(args, out: dict) -> None:
    """Pipeline and model in one process. No ambiguous-symbol hook exists yet, so as a stand-in the
    model makes one short call (prompt + 1 token) per checklist step."""
    storage = STORAGE_PROFILES[args.storage]
    config = json.loads((Path(args.package) / "config.json").read_text())
    generate, files = load_model(args, out, storage)
    sub: dict = {}
    t = time.perf_counter()
    checklists = run_pipeline([Path(s) for s in args.sources], 1, sub)
    pipeline_s = time.perf_counter() - t
    t = time.perf_counter()
    calls = 0
    for cl in checklists:
        for _ in cl["steps"]:
            generate(_prompt(config["vocab_size"], args.prompt_tokens, seed=calls), 1)
            calls += 1
    model_s = time.perf_counter() - t
    out.update(procedures=len(checklists), model_calls=calls,
               pipeline_s_per_procedure=sub["total_s_per_procedure"],
               model_s_per_procedure=model_s / len(checklists),
               total_s_per_procedure=(pipeline_s + model_s) / len(checklists))
    if args.load == "mmap" and args.storage != "page-cache":
        out["sd_read"] = slowio.sd_cost(files, storage)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=("pipeline", "model", "combined"))
    ap.add_argument("--sources", nargs="*", default=[])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--package")
    ap.add_argument("--weights")
    ap.add_argument("--engine", choices=("numpy", "torch"), default="numpy")
    ap.add_argument("--format", default="f32")
    ap.add_argument("--load", choices=("ram", "mmap"), default="ram")
    ap.add_argument("--storage", choices=tuple(STORAGE_PROFILES), default="page-cache")
    ap.add_argument("--prompt-tokens", type=int, default=32)
    ap.add_argument("--new-tokens", type=int, default=32)
    args = ap.parse_args(argv)
    out: dict = {"task": args.task, "python_rss_at_start_mib": rss_mib()}
    t = time.perf_counter()
    if args.task == "pipeline":
        run_pipeline([Path(s) for s in args.sources], args.runs, out)
    elif args.task == "model":
        run_model(args, out)
    else:
        run_combined(args, out)
    out["wall_s"] = time.perf_counter() - t
    out["peak_rss_mib"] = peak_rss_mib()
    print(json.dumps(out))


if __name__ == "__main__":
    main()
