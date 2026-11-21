# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Simulated SD-card storage without root.

The box has no writable cgroup io.max, dm-delay or FUSE, so the slow-storage profile is simulated
in two ways, both documented on the results page:

1. Full reads (weights loaded into RAM): `throttled_read` reads the file in 1 MiB chunks and
   sleeps so the wall-clock rate never beats the profile's sequential bandwidth, plus one
   random-read latency to start. This is a real, measured delay in the read path.

2. Memory-mapped weights: page faults happen inside the kernel, where an unprivileged process
   cannot add a delay. So the file is first evicted from the page cache (posix_fadvise
   DONTNEED, checked with mincore), the workload runs, and mincore then reports exactly which
   pages the kernel had to bring in from storage, including its readahead. The SD-card cost of
   those pages is added on top of the measured time: bytes / sequential bandwidth plus one
   random-read latency per contiguous run of pages.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import mmap
import os
import time
from pathlib import Path

import numpy as np

from .profiles import StorageProfile

PAGE = os.sysconf("SC_PAGE_SIZE")
_libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
_libc.mincore.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte))


def throttled_read(path: Path, profile: StorageProfile, chunk: int = 1 << 20) -> bytes:
    start = time.perf_counter()
    if profile.seq_bytes_per_s is None:
        return Path(path).read_bytes()
    parts, done = [], 0
    with open(path, "rb") as handle:
        while data := handle.read(chunk):
            parts.append(data)
            done += len(data)
            due = start + profile.random_read_s + done / profile.seq_bytes_per_s
            delay = due - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
    return b"".join(parts)


def evict(path: Path) -> None:
    """Drop the file's clean pages from the page cache (no root needed)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)   # freshly written pages are dirty and cannot be dropped until flushed
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def residency(path: Path) -> list[bool]:
    """Per-page page-cache residency of a file (mincore). Mapping it does not fault pages in."""
    size = os.path.getsize(path)
    if size == 0:
        return []
    with open(path, "rb") as handle:
        mm = mmap.mmap(handle.fileno(), size, prot=mmap.PROT_READ)
        try:
            view = np.frombuffer(mm, dtype=np.uint8)   # read-only view; exposes the address only
            pages = (size + PAGE - 1) // PAGE
            vec = (ctypes.c_ubyte * pages)()
            if _libc.mincore(ctypes.c_void_p(view.ctypes.data), size, vec) != 0:
                raise OSError(ctypes.get_errno(), "mincore failed")
            del view
            return [bool(b & 1) for b in vec]
        finally:
            mm.close()


def resident_bytes(paths) -> int:
    return sum(sum(residency(p)) * PAGE for p in paths)


def sd_cost(paths, profile: StorageProfile) -> dict:
    """Pages now resident (= read from storage since eviction) and their modeled SD-card time."""
    pages = runs = 0
    for p in paths:
        prev = False
        for r in residency(p):
            pages += r
            runs += r and not prev
            prev = r
    nbytes = pages * PAGE
    seconds = 0.0 if profile.seq_bytes_per_s is None else nbytes / profile.seq_bytes_per_s + runs * profile.random_read_s
    return {"bytes_read_from_storage": nbytes, "read_requests": runs, "modeled_storage_s": seconds}
