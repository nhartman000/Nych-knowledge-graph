# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Orchestrates the whole edge benchmark. Entry point: demo/run_edge_benchmark.py."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import sys
from pathlib import Path

from . import footprint, report, weights
from .limits import run_limited
from .placeholder import build_placeholder, ensure_nych_lm, is_placeholder
from .profiles import DEVICE_PROFILES, STORAGE_PROFILES, thread_env

DEMO = Path(__file__).resolve().parents[1]
REPO = DEMO.parent
OUT = DEMO / "output" / "edge"

# (engine, format, load). Torch rows use the repo's own decoder; numpy rows use edge_bench.npdecoder.
MODEL_CONFIGS = (
    ("torch", "f32", "ram"), ("torch", "f32", "mmap"), ("torch", "torch-int8", "ram"),
    ("numpy", "f32", "ram"), ("numpy", "f32", "mmap"), ("numpy", "int8", "ram"),
    ("numpy", "int8", "mmap"), ("numpy", "int4", "ram"),
)


def torch_dynamic_int8(package: Path, out_dir: Path) -> Path:
    import torch
    from nych_language_model.training.train import load
    model = torch.ao.quantization.quantize_dynamic(load(package), {torch.nn.Linear}, dtype=torch.qint8)
    path = out_dir / "torch_dynamic_int8.pt"
    torch.save(model.state_dict(), path)
    return path


def prepare_weights(package: Path, no_torch: bool = False) -> dict:
    out_dir = OUT / "weights"
    out_dir.mkdir(parents=True, exist_ok=True)
    weights.verify_package(package)
    if no_torch:   # device run: flat files were exported elsewhere and copied here
        files = {"float32 package model.pt (as trained, D16)": package / "model.pt"}
        for fmt in weights.FORMATS:
            path = out_dir / f"{fmt}.bin"
            if not path.exists():
                raise SystemExit(f"--no-torch needs {path}: export it on a machine with PyTorch first")
            files[f"{fmt} flat file for numpy/memmap"] = path
        return {"dir": out_dir, "files": files}
    files = {"float32 package model.pt (as trained, D16)": package / "model.pt"}
    for fmt in weights.FORMATS:
        files[f"{fmt} flat file for numpy/memmap"] = weights.export_flat(package, out_dir, fmt)
    files["torch dynamic int8 state_dict (Linear layers only)"] = torch_dynamic_int8(package, out_dir)
    return {"dir": out_dir, "files": files}


def _worker(args: list[str], profile, block_torch: bool, extra_env: dict | None = None) -> dict:
    env = dict(os.environ, **thread_env(profile.cpus), PYTHONDONTWRITEBYTECODE="1")
    env["EDGE_BENCH_BLOCK_TORCH"] = "1" if block_torch else "0"
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(DEMO), *sys.path) if p)
    if extra_env:
        env.update(extra_env)
    res = run_limited([sys.executable, "-m", "edge_bench.worker"] + args, profile.cpus,
                      profile.memory_mib, env, cwd=str(DEMO))
    row = {"exceeded_memory": res["exceeded_memory"],
           "watchdog_peak_tree_rss_mib": round(res["watchdog_peak_tree_rss_mib"], 1)}
    lines = [ln for ln in res["stdout"].splitlines() if ln.startswith("{")]
    if res["returncode"] == 0 and lines:
        row.update(json.loads(lines[-1]), status="ok")
    else:
        row.update(status="killed: over memory limit" if res["exceeded_memory"] else "error",
                   error=res["stderr"][-1500:])
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Edge-device footprint benchmark (simulated constraints on x86).")
    ap.add_argument("--package", default=os.environ.get("NYCH_WEIGHTS"),
                    help="trained D16 package dir (model.pt, config.json, manifest.json...). "
                         "Default $NYCH_WEIGHTS, else a PLACEHOLDER is trained.")
    ap.add_argument("--profiles", nargs="*", default=[p.name for p in DEVICE_PROFILES])
    ap.add_argument("--quick", action="store_true", help="3 sources and fewer model configs (smoke run)")
    ap.add_argument("--results-dir", default=str(DEMO / "results"))
    ap.add_argument("--no-torch", action="store_true",
                    help="device run without PyTorch: skip torch rows; needs --package and pre-exported flat files")
    args = ap.parse_args(argv)
    if args.no_torch and not args.package:
        raise SystemExit("--no-torch needs --package (a placeholder cannot be trained without PyTorch)")
    if not args.no_torch:
        ensure_nych_lm()

    package = Path(args.package) if args.package else build_placeholder(OUT / "placeholder_package")
    placeholder = is_placeholder(package)
    print(f"weights: {package} ({'PLACEHOLDER' if placeholder else 'trained package'})", flush=True)
    prepared = prepare_weights(package, args.no_torch)
    config = weights.load_config(package)
    manifest = json.loads((package / "manifest.json").read_text())

    sources = [p for p in sorted((DEMO / "sources").glob("*.txt")) if "LICENSE" not in p.name]
    if args.quick:
        sources = [DEMO / "sources" / n for n in ("pg_verifybackup.txt", "pg_checksums.txt",
                                                  "original_release_check_sop.txt")]
    combined_sources = sources[:3]
    configs = MODEL_CONFIGS if not args.quick else (("torch", "f32", "ram"), ("numpy", "int8", "mmap"))
    if args.no_torch:
        configs = tuple(c for c in configs if c[0] != "torch")
    base = ["--package", str(package), "--weights", str(prepared["dir"])]

    runs = []
    for profile in [p for p in DEVICE_PROFILES if p.name in args.profiles]:
        for block in ((True,) if args.no_torch else (True, False)):
            print(f"[{profile.name}] pipeline ({'no torch' if block else 'torch installed'})", flush=True)
            row = _worker(["pipeline", "--runs", "1", "--sources", *map(str, sources)], profile, block)
            runs.append(dict(row, profile=profile.name, kind="pipeline",
                             variant="device install (no PyTorch)" if block else "as installed here (PyTorch present)"))
        for engine, fmt, load in configs:
            for storage in STORAGE_PROFILES:
                print(f"[{profile.name}] model {engine}/{fmt}/{load}/{storage}", flush=True)
                row = _worker(["model", *base, "--engine", engine, "--format", fmt, "--load", load,
                               "--storage", storage], profile, block_torch=(engine == "numpy"))
                runs.append(dict(row, profile=profile.name, kind="model", engine=engine, format=fmt,
                                 load=load, storage=storage))
        print(f"[{profile.name}] combined pipeline + numpy int8 mmap (sd-card)", flush=True)
        row = _worker(["combined", *base, "--engine", "numpy", "--format", "int8", "--load", "mmap",
                       "--storage", "sd-card", "--sources", *map(str, combined_sources)], profile, True)
        runs.append(dict(row, profile=profile.name, kind="combined", engine="numpy", format="int8",
                         load="mmap", storage="sd-card"))

    params = weights.parameter_count(config)
    matrix = params - (2 * config["n_layers"] + 1) * config["d_model"]
    import numpy
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        torch_version = None
    results = {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": {"machine": platform.machine(), "processor": _cpu_model(), "python": platform.python_version(),
                 "numpy": numpy.__version__, "torch": torch_version, "logical_cpus": os.cpu_count()},
        "weights": {"placeholder": placeholder, "package": package.name, "config": config,
                    "parameters": params, "dataset_arm": manifest.get("dataset_meta", {}).get("arm"),
                    "model_pt_sha256": manifest["sha256"]["model.pt"],
                    "metrics": {k: v for k, v in json.loads((package / "metrics.json").read_text()).items()
                                if k in ("steps", "eval_bits_per_token", "seconds")}},
        "profiles": {"devices": [p.__dict__ for p in DEVICE_PROFILES],
                     "storage": {k: v.__dict__ for k, v in STORAGE_PROFILES.items()}},
        "estimates": {"this_model": dict(label="this model", **weights.size_estimates(params, matrix)),
                      "reference": weights.reference_shapes()},
        "footprint": footprint.measure({k: v for k, v in prepared["files"].items()}),
        "sources": [p.name for p in sources], "combined_sources": [p.name for p in combined_sources],
        "runs": runs,
    }
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "edge-footprint.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    report.write(results, results_dir)
    print(f"wrote {results_dir / 'edge-footprint.md'} and edge-footprint.html")
    return 0 if all(r["status"] == "ok" or r["exceeded_memory"] for r in runs) else 1


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()
