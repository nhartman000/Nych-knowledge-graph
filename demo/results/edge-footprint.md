<!-- Copyright (c) 2026 American Milestone Inc. All rights reserved. -->

# Edge-device footprint: can NYCH run on a gumball-machine computer?

Generated 2026-11-21T09:08:03-05:00 on Intel(R) Xeon(R) Processor (x86_64), Python 3.13.5, NumPy 2.5.5, PyTorch 2.7.0+cpu.

> **Read this first.** Every number here comes from an x86 server with **simulated** limits: CPU cores pinned with `taskset`, memory policed by a watchdog, and SD-card reads simulated in software. It is not a Raspberry Pi or any ARM board. Treat these as a sizing guide, not device results.

Model weights used: **PLACEHOLDER weights** (trained by this benchmark on synthetic token IDs; real size and speed for this shape, meaningless outputs). Shape: the approved V1 decoder (d_model 128, 2 layers, 4 heads, SwiGLU 512, vocab 10,000) = **1,804,928 parameters**, the low end of the D14 size band.

## The short version

* **The checklist pipeline needs no model.** On 1 CPU / 512 MB it took about **112.8 ms per procedure** to build the checklist and **1.94 s** to run the gates and write the hash-chained audit log (**2.05 s total**). Peak memory was **293 MiB** for the whole process tree; the main process alone peaked at 156 MiB, and the rest is the isolated subprocess mg8-runtime starts for each gate check. The first procedure is slower (662.3 ms) because it loads the encoder and spaCy.
* **Do not ship PyTorch next to spaCy.** If PyTorch is installed, spaCy's backend imports it, and the main pipeline process peaks at **320 MiB** instead of 156 MiB, and its first procedure takes 1.56 s instead of 662.3 ms.
* **The model is small; the runtime is not.** The weights are 7.22 MB as trained (float32), 1.86 MB as int8 and 1.02 MB as 4-bit. Running them with PyTorch peaks at **236 MiB**, mostly PyTorch itself. The NumPy runtime in this branch runs the same model from an int8 file memory-mapped off the simulated SD card at **43 MiB** peak.
* **Speed:** one new token takes about **0.7 ms** (NumPy, int8, memory-mapped, 1 CPU, with a KV cache) versus **2.1 ms** for the PyTorch reference decoder, which has no KV cache and re-reads the whole window for every token.
* **Everything fits on any SD card.** Our code, symbol tables (including the 15 MB spaCy English model) and gate files total about **28.75 MB**; the int8 weights add 1.86 MB. The large items are third-party libraries (see the footprint table).
* **No ambiguous-symbol hook exists yet**, so the model is not wired into the checklist pipeline. Model speed is measured on its own, and the combined run below uses a stand-in (one short model call per checklist step).

## 1. Installed footprint (what goes on the SD card)

Sizes are bytes on disk. Code counts `.py` files only. Library sizes are this box's x86 wheels; ARM wheels differ.

| Group | Item | Size | Files |
|---|---|---|---|
| code | checklist pipeline (demo/procedure_demo) | 0.03 MB | 8 |
| code | NYCH3 encoder (shared/nych3) | 0.23 MB | 32 |
| code | vendored nych tokenizer (shared/vendor) | 0.30 MB | 55 |
| code | edge runtime: numpy decoder + loader (demo/edge_bench) | 0.07 MB | 11 |
| code | mg8-runtime (gates, permits, QSON log) | 0.11 MB | 13 |
| code | nych-language-model package (.py only) | 0.14 MB | 30 |
| symbol tables | _config (NYCH3 registries, BONIT config) | 0.04 MB | 9 |
| symbol tables | shared/data (sense registry, TOTE seed, how-to tables) | 10.29 MB | 14 |
| symbol tables | NYCH emoji inventory + dictionaries (nych-language-model data) | 2.28 MB | 5 |
| symbol tables | spaCy English model (en_core_web_sm) | 15.24 MB | 28 |
| gate / context files | .qson / .gst / .g8son files in the repo | 0.01 MB | 3 |
| model weights | float32 package model.pt (as trained, D16) | 7.22 MB | 1 |
| model weights | f32 flat file for numpy/memmap | 7.22 MB | 1 |
| model weights | int8 flat file for numpy/memmap | 1.86 MB | 1 |
| model weights | int4 flat file for numpy/memmap | 1.02 MB | 1 |
| model weights | torch dynamic int8 state_dict (Linear layers only) | 5.66 MB | 1 |
| runtime libraries (not ours, x86 wheels) | numpy | 28.73 MB | 902 |
| runtime libraries (not ours, x86 wheels) | torch | 658.12 MB | 10948 |
| runtime libraries (not ours, x86 wheels) | spacy | 122.22 MB | 1032 |
| runtime libraries (not ours, x86 wheels) | thinc | 15.18 MB | 192 |
| runtime libraries (not ours, x86 wheels) | kuzu | 21.45 MB | 12 |

Group totals: code: 0.88 MB; symbol tables: 27.86 MB; gate / context files: 0.01 MB; model weights: 22.98 MB; runtime libraries (not ours, x86 wheels): 845.70 MB.

## 2. Model weight size: actual files and estimates

Actual files are listed above under *model weights*. The int8 file keeps one float32 scale per matrix row; the 4-bit file packs two weights per byte with a float16 scale for every 32 weights (llama.cpp Q4_0 style). PyTorch dynamic int8 quantizes only the linear layers; the tied embedding, most of this model, stays float32.

| Model | Parameters | float32 | int8 | 4-bit |
|---|---|---|---|---|
| this model | 1,804,928 | 7.22 MB | 1.86 MB | 1.02 MB |
| D14 band low (vocab 10,000) | 1,804,928 | 7.22 MB | 1.86 MB | 1.02 MB |
| D14 band high (vocab 50,257) | 6,957,824 | 27.83 MB | 7.18 MB | 3.92 MB |
| 30M-parameter what-if (shape not chosen) | 30,000,000 | 120.00 MB | 30.94 MB | 16.88 MB |

## 3. Checklist pipeline, no model (seconds per procedure)

All 10 bundled public procedures, one pass, evidence simulated (`all-pass`). *Checklist* is text to T.O.T.E. steps; *gates + log* is mg8-runtime evaluating every exit check (each in its own isolated subprocess) and writing the hash-chained QSON log, then verifying it. *Tree peak* includes those subprocesses.

| Profile | Install | First procedure (cold) | Checklist / procedure | Gates + log / procedure | Total / procedure | Peak RSS (main) | Tree peak | Audit log / procedure | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1cpu-512mb | device install (no PyTorch) | 662.3 ms | 112.8 ms | 1.94 s | 2.05 s | 156 MiB | 293 MiB | 0.31 MB | ok |
| 1cpu-512mb | as installed here (PyTorch present) | 1.56 s | 115.0 ms | 1.91 s | 2.02 s | 320 MiB | 323 MiB | 0.31 MB | ok |
| 4cpu-1gb | device install (no PyTorch) | 655.3 ms | 119.0 ms | 2.08 s | 2.20 s | 156 MiB | 292 MiB | 0.31 MB | ok |
| 4cpu-1gb | as installed here (PyTorch present) | 1.67 s | 115.1 ms | 1.98 s | 2.10 s | 320 MiB | 565 MiB | 0.31 MB | ok |

## 4. Model on its own

Prompt of 32 token IDs, then 32 new tokens, greedy. *Per token* is the warm average. *Runtime baseline* is memory after imports, before any weights. *Peak* is the larger of the main process's high-water mark and the sampled process-tree total. *Time to first answer* = integrity check + load + first call, plus the modeled SD-card time for memory-mapped pages.

| Profile | Engine | Weights | Load | Storage | Time to first answer | Per token (warm) | Runtime baseline | Peak RSS | Weights resident | Read from SD | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1cpu-512mb | torch | f32 | fully in RAM | page-cache | 38.3 ms | 1.9 ms | 203 MiB | 236 MiB | 7.23 MB | – | ok |
| 1cpu-512mb | torch | f32 | fully in RAM | sd-card | 326.4 ms | 2.1 ms | 202 MiB | 236 MiB | 7.23 MB | – | ok |
| 1cpu-512mb | torch | f32 | memory-mapped | page-cache | 28.4 ms | 2.0 ms | 203 MiB | 236 MiB | 7.23 MB | – | ok |
| 1cpu-512mb | torch | f32 | memory-mapped | sd-card | 627.2 ms | 1.9 ms | 202 MiB | 236 MiB | 7.23 MB | 7.23 MB | ok |
| 1cpu-512mb | torch | torch-int8 | fully in RAM | page-cache | 35.9 ms | 1.9 ms | 203 MiB | 240 MiB | 5.66 MB | – | ok |
| 1cpu-512mb | torch | torch-int8 | fully in RAM | sd-card | 264.8 ms | 2.1 ms | 202 MiB | 239 MiB | 5.66 MB | – | ok |
| 1cpu-512mb | numpy | f32 | fully in RAM | page-cache | 25.5 ms | 0.4 ms | 32 MiB | 46 MiB | 7.22 MB | – | ok |
| 1cpu-512mb | numpy | f32 | fully in RAM | sd-card | 314.7 ms | 0.4 ms | 32 MiB | 46 MiB | 7.22 MB | – | ok |
| 1cpu-512mb | numpy | f32 | memory-mapped | page-cache | 21.7 ms | 0.4 ms | 32 MiB | 43 MiB | 7.22 MB | – | ok |
| 1cpu-512mb | numpy | f32 | memory-mapped | sd-card | 609.4 ms | 0.4 ms | 32 MiB | 46 MiB | 7.22 MB | 7.22 MB | ok |
| 1cpu-512mb | numpy | int8 | fully in RAM | page-cache | 29.8 ms | 0.7 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 1cpu-512mb | numpy | int8 | fully in RAM | sd-card | 101.3 ms | 0.7 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 1cpu-512mb | numpy | int8 | memory-mapped | page-cache | 27.6 ms | 0.7 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 1cpu-512mb | numpy | int8 | memory-mapped | sd-card | 186.2 ms | 0.7 ms | 32 MiB | 43 MiB | 1.86 MB | 1.86 MB | ok |
| 1cpu-512mb | numpy | int4 | fully in RAM | page-cache | 33.5 ms | 0.4 ms | 32 MiB | 47 MiB | 1.02 MB | – | ok |
| 1cpu-512mb | numpy | int4 | fully in RAM | sd-card | 70.5 ms | 0.4 ms | 32 MiB | 47 MiB | 1.02 MB | – | ok |
| 4cpu-1gb | torch | f32 | fully in RAM | page-cache | 42.0 ms | 1.1 ms | 203 MiB | 234 MiB | 7.23 MB | – | ok |
| 4cpu-1gb | torch | f32 | fully in RAM | sd-card | 325.3 ms | 1.1 ms | 202 MiB | 234 MiB | 7.23 MB | – | ok |
| 4cpu-1gb | torch | f32 | memory-mapped | page-cache | 27.3 ms | 1.2 ms | 203 MiB | 233 MiB | 7.23 MB | – | ok |
| 4cpu-1gb | torch | f32 | memory-mapped | sd-card | 624.8 ms | 1.1 ms | 203 MiB | 233 MiB | 7.23 MB | 7.23 MB | ok |
| 4cpu-1gb | torch | torch-int8 | fully in RAM | page-cache | 41.8 ms | 1.5 ms | 203 MiB | 239 MiB | 5.66 MB | – | ok |
| 4cpu-1gb | torch | torch-int8 | fully in RAM | sd-card | 269.2 ms | 1.6 ms | 203 MiB | 239 MiB | 5.66 MB | – | ok |
| 4cpu-1gb | numpy | f32 | fully in RAM | page-cache | 23.6 ms | 0.2 ms | 32 MiB | 46 MiB | 7.22 MB | – | ok |
| 4cpu-1gb | numpy | f32 | fully in RAM | sd-card | 310.3 ms | 0.2 ms | 32 MiB | 46 MiB | 7.22 MB | – | ok |
| 4cpu-1gb | numpy | f32 | memory-mapped | page-cache | 17.3 ms | 0.2 ms | 32 MiB | 43 MiB | 7.22 MB | – | ok |
| 4cpu-1gb | numpy | f32 | memory-mapped | sd-card | 605.0 ms | 0.2 ms | 32 MiB | 46 MiB | 7.22 MB | 7.22 MB | ok |
| 4cpu-1gb | numpy | int8 | fully in RAM | page-cache | 29.2 ms | 0.6 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 4cpu-1gb | numpy | int8 | fully in RAM | sd-card | 103.8 ms | 0.6 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 4cpu-1gb | numpy | int8 | memory-mapped | page-cache | 27.5 ms | 0.6 ms | 32 MiB | 43 MiB | 1.86 MB | – | ok |
| 4cpu-1gb | numpy | int8 | memory-mapped | sd-card | 178.7 ms | 0.6 ms | 32 MiB | 43 MiB | 1.86 MB | 1.86 MB | ok |
| 4cpu-1gb | numpy | int4 | fully in RAM | page-cache | 26.0 ms | 0.2 ms | 32 MiB | 46 MiB | 1.02 MB | – | ok |
| 4cpu-1gb | numpy | int4 | fully in RAM | sd-card | 70.1 ms | 0.2 ms | 32 MiB | 47 MiB | 1.02 MB | – | ok |

## 5. Fully in RAM versus memory-mapped from the SD card

Simulated SD card, same weights, both device profiles. Both paths check the sha256 of the weights first, which reads the whole file once. The mmap run then starts from a cold cache (the file is evicted after the check, as if memory pressure had pushed it out), so it pays for the reads twice: this is the worst case. The *no whole-file hash* column shows the mmap start if integrity were checked per block instead. Peak memory is the larger of the process high-water mark and the sampled tree total.

| Profile | Weights | First answer: RAM | First answer: mmap | mmap, no whole-file hash | Peak RSS: RAM | Peak RSS: mmap | Per token: RAM | Per token: mmap |
|---|---|---|---|---|---|---|---|---|
| 1cpu-512mb | numpy f32 | 314.7 ms | 609.4 ms | 310.2 ms | 46 MiB | 46 MiB | 0.4 ms | 0.4 ms |
| 1cpu-512mb | numpy int8 | 101.3 ms | 186.2 ms | 108.5 ms | 43 MiB | 43 MiB | 0.7 ms | 0.7 ms |
| 1cpu-512mb | torch f32 | 326.4 ms | 627.2 ms | 308.2 ms | 236 MiB | 236 MiB | 2.1 ms | 1.9 ms |
| 4cpu-1gb | numpy f32 | 310.3 ms | 605.0 ms | 306.0 ms | 46 MiB | 46 MiB | 0.2 ms | 0.2 ms |
| 4cpu-1gb | numpy int8 | 103.8 ms | 178.7 ms | 101.2 ms | 43 MiB | 43 MiB | 0.6 ms | 0.6 ms |
| 4cpu-1gb | torch f32 | 325.3 ms | 624.8 ms | 302.5 ms | 234 MiB | 233 MiB | 1.1 ms | 1.1 ms |

What this means: on this small model, loading fully into RAM is the faster start, because one sequential read beats page-by-page faults and the whole file is needed anyway. Memory-mapping lets the operating system load weight pages only when they are touched and drop them again under memory pressure, so the weights do not have to fit in RAM up front. For this model the saving is small, because the output layer is tied to the embedding table, so every token touches the whole table: after the first token essentially all weights are resident either way. Memory-mapping pays off when the model is larger than RAM, or when an untied or sparse lookup touches only a few rows per token. Separately, the NumPy runtime dequantizes int8 weights on every use, so int8 is smaller but slightly slower per token than float32; the 4-bit file is unpacked to float32 at load.

## 6. Pipeline and model in one process (stand-in for ambiguous-symbol calls)

No hook exists yet for the model to resolve ambiguous symbols inside the checklist pipeline. As a stand-in, this run loads the int8 model memory-mapped from the simulated SD card, runs the pipeline on 3 procedures, and makes one 32-token model call per checklist step. It shows the combined memory and a rough time budget, not real disambiguation quality.

| Profile | Model calls | Pipeline / procedure | Model / procedure | Total / procedure | Peak RSS (main) | Tree peak | Status |
|---|---|---|---|---|---|---|---|
| 1cpu-512mb | 18 | 822.9 ms | 132.4 ms | 1.17 s | 159 MiB | 168 MiB | ok |
| 4cpu-1gb | 18 | 827.6 ms | 142.0 ms | 1.20 s | 159 MiB | 292 MiB | ok |

## How the constraints were simulated

* **CPUs:** `taskset -c` pins each run, and its child processes, to 1 or 4 cores; BLAS/OpenMP/PyTorch thread pools are set to the same number.
* **Memory:** the box has no writable cgroup, Docker or user systemd, so a watchdog samples the resident memory of the whole process tree (PSS, so pages shared with forked children count once) every 10 ms and kills the run if it passes 512 MB or 1 GB. RLIMIT_AS was not used because it caps reserved address space, which PyTorch and OpenBLAS reserve far beyond what they use. *Peak RSS (main)* is the kernel's high-water mark for the main process (`VmHWM`). A real cgroup counts page cache too but can reclaim it; very short spikes between samples could be missed.
* **SD card:** a simulated A1 microSD: 25 MB/s sequential, 1,500 random-read IOPS profile. Weights loaded fully into RAM are read through a throttled reader that sleeps so the rate never beats 25 MB/s (a real delay in the read path). Memory-mapped weights fault in inside the kernel, where an unprivileged program cannot add delay, so the file is evicted from the page cache first (`posix_fadvise DONTNEED`), and afterwards `mincore` reports exactly which pages were read from storage, readahead included. Their SD time (bytes / 25 MB/s plus 0.67 ms per contiguous read) is added to the measured time.
* Code, Python and libraries are always loaded from the page cache, so start-up from a real SD card will be slower.

## Caveats

* Simulated constraints on an x86 server CPU, not ARM hardware. A Cortex-A53 (Pi Zero 2 W / Pi 3) is several times slower per core than this CPU; expect proportionally longer times.
* The model is a placeholder trained on synthetic IDs: memory, size and speed are real for this shape, its outputs are meaningless. Re-run with `--package` once real weights exist.
* Gate evidence is simulated, as in the main demo.
* One run per configuration; timings on a shared server vary by a few percent.

## Still needed before a real Raspberry Pi run

1. Real hardware: a Pi Zero 2 W (512 MB) and a Pi 4 / Pi 5 (1 GB+), 64-bit Raspberry Pi OS, an A1/A2 microSD card.
2. Install without PyTorch: NumPy, spaCy and the `en_core_web_sm` model have aarch64 wheels; `kuzu` aarch64 support needs checking. Export the flat weight files on a PC (that step needs PyTorch), copy `demo/output/edge/weights/` to the device, then run `python demo/run_edge_benchmark.py --package <weights> --no-torch`.
3. Use real limits: a cgroup (`systemd-run --scope -p MemoryMax=512M -p AllowedCPUs=0`) instead of the watchdog, and the real card instead of the simulated profile (drop caches with `echo 3 > /proc/sys/vm/drop_caches` between runs).
4. Trained NYCH weights from the stage 2 run, and an ambiguous-symbol hook so the model is called only where the deterministic rules cannot decide.
5. Optional: a per-block hash manifest, so a memory-mapped model can be verified without reading the whole file at boot.

<sub>Copyright (c) 2026 American Milestone Inc. All rights reserved. Raw numbers: `edge-footprint.json`. Re-run: `python demo/run_edge_benchmark.py`.</sub>
