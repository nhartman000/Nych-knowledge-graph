# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Run a command under a CPU and memory budget without root.

The box has cgroup v2 but no write access to it, no Docker and no user systemd, so:
  * CPUs: `taskset` pins the process (and its children) to N cores, and BLAS/OpenMP pools are set
    to N threads. This is a hard limit on parallelism.
  * Memory: a watchdog samples the memory (PSS, so shared pages count once) of the whole process tree every 10 ms and
    kills it the moment the total passes the budget, recording "exceeded". RLIMIT_AS is not used:
    it caps virtual address space, which PyTorch and OpenBLAS reserve far beyond what they touch,
    so it fails workloads a real 512 MB device would run. Unlike a kernel cgroup, the watchdog
    cannot reclaim page cache or make memory-mapped pages cheaper, so a run that passes here would
    also fit a real cgroup with the same limit; a short spike between samples can be missed.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path


def _children(pid: int) -> list[int]:
    out = []
    try:
        for task in Path(f"/proc/{pid}/task").iterdir():
            text = (task / "children").read_text().split()
            out += [int(c) for c in text]
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    return out


def tree_rss_bytes(pid: int) -> int:
    """Memory of a process tree as the sum of PSS (proportional set size): pages shared between a
    parent and its forked children are split between them instead of being counted twice."""
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        try:
            with open(f"/proc/{p}/smaps_rollup") as handle:
                for line in handle:
                    if line.startswith("Pss:"):
                        total += int(line.split()[1]) * 1024
                        break
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        stack += _children(p)
    return total


def cpu_list(cpus: int) -> str:
    available = sorted(os.sched_getaffinity(0))
    if cpus > len(available):
        raise ValueError(f"profile wants {cpus} CPUs, box has {len(available)}")
    return ",".join(str(c) for c in available[:cpus])


def run_limited(cmd: list[str], cpus: int, memory_mib: int, env: dict, cwd: str | None = None,
                timeout: float = 900, interval: float = 0.01) -> dict:
    full = ["taskset", "-c", cpu_list(cpus)] + cmd
    proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd, text=True)
    limit, peak, killed = memory_mib * 1024 * 1024, [0], [False]

    def watch():
        while proc.poll() is None:
            rss = tree_rss_bytes(proc.pid)
            peak[0] = max(peak[0], rss)
            if rss > limit:
                killed[0] = True
                proc.kill()
                return
            time.sleep(interval)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    thread.join()
    return {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr[-4000:],
            "exceeded_memory": killed[0], "watchdog_peak_tree_rss_mib": peak[0] / 1024 / 1024}
