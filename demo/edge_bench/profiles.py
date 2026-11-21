# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Constrained device profiles and the simulated SD-card storage profile."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    cpus: int
    memory_mib: int
    note: str


DEVICE_PROFILES = (
    DeviceProfile("1cpu-512mb", 1, 512, "Pi Zero 2 W / Pi 3A+ class: one core, 512 MB"),
    DeviceProfile("4cpu-1gb", 4, 1024, "Pi 3B / Pi 4 1 GB class: four cores, 1 GB"),
)


@dataclass(frozen=True)
class StorageProfile:
    name: str
    # Sustained sequential read, bytes per second. None = page cache / RAM speed.
    seq_bytes_per_s: float | None
    # Cost of one random read request (seek + command overhead), seconds.
    random_read_s: float
    note: str


# A1-rated microSD card in a Raspberry Pi SD slot. The A1 class guarantees 1,500 random
# 4 KiB read IOPS (0.67 ms each); 25 MB/s is a conservative sustained read for the
# Pi 3/Zero-class SD interface (Pi 4 reaches roughly 40-45 MB/s, Pi 5 roughly 90 MB/s).
SD_CARD = StorageProfile("sd-card", 25e6, 1 / 1500,
                         "simulated A1 microSD: 25 MB/s sequential, 1,500 random-read IOPS")
PAGE_CACHE = StorageProfile("page-cache", None, 0.0, "file already in RAM (page cache), no storage cost")

STORAGE_PROFILES = {p.name: p for p in (PAGE_CACHE, SD_CARD)}


def thread_env(cpus: int) -> dict[str, str]:
    """Environment that keeps BLAS / OpenMP thread pools inside the CPU budget."""
    n = str(cpus)
    return {"OMP_NUM_THREADS": n, "OPENBLAS_NUM_THREADS": n, "MKL_NUM_THREADS": n,
            "NUMEXPR_NUM_THREADS": n, "EDGE_BENCH_THREADS": n}
