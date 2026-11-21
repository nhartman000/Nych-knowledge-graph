# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Render demo/results/edge-footprint.md and .html from the results JSON."""
from __future__ import annotations

import html
import re
from pathlib import Path

COPYRIGHT = "Copyright (c) 2026 American Milestone Inc. All rights reserved."


def mb(b) -> str:
    return "–" if b is None else f"{b / 1e6:,.2f} MB"


def mib(x) -> str:
    return "–" if x is None else f"{x:,.0f} MiB"


def sec(x) -> str:
    if x is None:
        return "–"
    return f"{x * 1000:,.1f} ms" if x < 1 else f"{x:,.2f} s"


def peak(r: dict) -> float | None:
    """Larger of the main process's kernel high-water mark and the sampled process-tree total."""
    vals = [v for v in (r.get("peak_rss_mib"), r.get("watchdog_peak_tree_rss_mib")) if v]
    return max(vals) if vals else None


def first_answer_s(r: dict) -> float | None:
    """Verify + load + first call (32-token prompt) + modeled SD reads for mapped pages."""
    if r.get("status") != "ok":
        return None
    return (r.get("verify_s") or 0) + r["load_s"] + r["first_call_prompt_s"] + \
        (r.get("sd_read") or {}).get("modeled_storage_s", 0)


def mapped_only_s(r: dict) -> float | None:
    """Memory-mapped start without a whole-file hash (e.g. per-block hashes checked on fault)."""
    if r.get("status") != "ok" or r.get("load") != "mmap":
        return None
    return r["load_s"] + r["first_call_prompt_s"] + (r.get("sd_read") or {}).get("modeled_storage_s", 0)


def _table(head: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def _status(r: dict) -> str:
    return "ok" if r["status"] == "ok" else ("**over memory limit, killed**" if r["exceeded_memory"] else "**error**")


def build_markdown(res: dict) -> str:
    w = res["weights"]
    label = ("**PLACEHOLDER weights** (trained by this benchmark on synthetic token IDs; real size and "
             "speed for this shape, meaningless outputs)" if w["placeholder"] else "**trained NYCH weights**")
    runs = res["runs"]
    pipe = [r for r in runs if r["kind"] == "pipeline"]
    model = [r for r in runs if r["kind"] == "model"]
    comb = [r for r in runs if r["kind"] == "combined"]
    fp = res["footprint"]
    groups: dict[str, int] = {}
    for row in fp:
        groups[row["group"]] = groups.get(row["group"], 0) + row["bytes"]
    wfile = {row["item"]: row["bytes"] for row in fp if row["group"] == "model weights"}
    ours = groups.get("code", 0) + groups.get("symbol tables", 0) + groups.get("gate / context files", 0)
    int8_flat = next((b for k, b in wfile.items() if k.startswith("int8")), 0)
    int4_flat = next((b for k, b in wfile.items() if k.startswith("int4")), 0)

    def pick(profile, **kw):
        for r in model:
            if r["profile"] == profile and all(r.get(k) == v for k, v in kw.items()):
                return r
        return None

    L = [f"<!-- {COPYRIGHT} -->", "", "# Edge-device footprint: can NYCH run on a gumball-machine computer?", "",
         f"Generated {res['generated']} on {res['host']['processor']} ({res['host']['machine']}), "
         f"Python {res['host']['python']}, NumPy {res['host']['numpy']}, PyTorch {res['host']['torch']}.", "",
         "> **Read this first.** Every number here comes from an x86 server with **simulated** limits: CPU cores "
         "pinned with `taskset`, memory policed by a watchdog, and SD-card reads simulated in software. "
         "It is not a Raspberry Pi or any ARM board. Treat these as a sizing guide, not device results.", "",
         f"Model weights used: {label}. Shape: the approved V1 decoder (d_model {w['config']['d_model']}, "
         f"{w['config']['n_layers']} layers, {w['config']['n_heads']} heads, SwiGLU {w['config']['ffn_width']}, "
         f"vocab {w['config']['vocab_size']:,}) = **{w['parameters']:,} parameters**, the low end of the D14 size band.", "",
         "## The short version", ""]
    one = [p for p in pipe if p["profile"] == "1cpu-512mb" and p["variant"].startswith("device") and p["status"] == "ok"]
    if one:
        p = one[0]
        L.append(f"* **The checklist pipeline needs no model.** On 1 CPU / 512 MB it took about "
                 f"**{sec(p['checklist_s_per_procedure'])} per procedure** to build the checklist and "
                 f"**{sec(p['audit_s_per_procedure'])}** to run the gates and write the hash-chained audit log "
                 f"(**{sec(p['total_s_per_procedure'])} total**). Peak memory was **{mib(peak(p))}** for the whole "
                 f"process tree; the main process alone peaked at {mib(p['peak_rss_mib'])}, and the rest is the isolated "
                 f"subprocess mg8-runtime starts for each gate check. The first procedure is slower ({sec(p['first_procedure_s'])}) because it loads the "
                 f"encoder and spaCy.")
    two = [p for p in pipe if p["profile"] == "1cpu-512mb" and not p["variant"].startswith("device") and p["status"] == "ok"]
    if one and two:
        L.append(f"* **Do not ship PyTorch next to spaCy.** If PyTorch is installed, spaCy's backend imports it, and the "
                 f"main pipeline process peaks at **{mib(two[0]['peak_rss_mib'])}** instead of {mib(one[0]['peak_rss_mib'])}, "
                 f"and its first procedure takes {sec(two[0]['first_procedure_s'])} instead of {sec(one[0]['first_procedure_s'])}.")
    nm = pick("1cpu-512mb", engine="numpy", format="int8", load="mmap", storage="sd-card")
    tr = pick("1cpu-512mb", engine="torch", format="f32", load="ram", storage="sd-card")
    if nm and tr and nm["status"] == tr["status"] == "ok":
        L.append(f"* **The model is small; the runtime is not.** The weights are {mb(wfile.get(next(iter(wfile))))} as trained "
                 f"(float32), {mb(int8_flat)} as int8 and {mb(int4_flat)} as 4-bit. Running them with PyTorch peaks at "
                 f"**{mib(peak(tr))}**, mostly PyTorch itself. The NumPy runtime in this branch runs the same "
                 f"model from an int8 file memory-mapped off the simulated SD card at **{mib(peak(nm))}** peak.")
        L.append(f"* **Speed:** one new token takes about **{sec(nm['per_token_s'])}** (NumPy, int8, memory-mapped, 1 CPU, "
                 f"with a KV cache) versus **{sec(tr['per_token_s'])}** for the PyTorch reference decoder, which has no KV "
                 f"cache and re-reads the whole window for every token.")
    L.append(f"* **Everything fits on any SD card.** Our code, symbol tables (including the 15 MB spaCy English model) and gate files total about **{mb(ours)}**; "
             f"the int8 weights add {mb(int8_flat)}. The large items are third-party libraries (see the footprint table).")
    L.append("* **No ambiguous-symbol hook exists yet**, so the model is not wired into the checklist pipeline. Model speed is "
             "measured on its own, and the combined run below uses a stand-in (one short model call per checklist step).")
    L += ["", "## 1. Installed footprint (what goes on the SD card)", "",
          "Sizes are bytes on disk. Code counts `.py` files only. Library sizes are this box's x86 wheels; ARM wheels differ.", ""]
    L += _table(["Group", "Item", "Size", "Files"],
                [[r["group"], r["item"], mb(r["bytes"]), r["files"]] for r in fp])
    L += ["", f"Group totals: " + "; ".join(f"{g}: {mb(b)}" for g, b in groups.items()) + ".", "",
          "## 2. Model weight size: actual files and estimates", "",
          "Actual files are listed above under *model weights*. The int8 file keeps one float32 scale per matrix row; "
          "the 4-bit file packs two weights per byte with a float16 scale for every 32 weights (llama.cpp Q4_0 style). "
          "PyTorch dynamic int8 quantizes only the linear layers; the tied embedding, most of this model, stays float32.", ""]
    est = [res["estimates"]["this_model"]] + res["estimates"]["reference"]
    L += _table(["Model", "Parameters", "float32", "int8", "4-bit"],
                [[e["label"], f"{e['parameters']:,}", mb(e["float32_bytes"]), mb(e["int8_bytes"]), mb(e["int4_bytes"])]
                 for e in est])
    L += ["", "## 3. Checklist pipeline, no model (seconds per procedure)", "",
          f"All {len(res['sources'])} bundled public procedures, one pass, evidence simulated (`all-pass`). "
          "*Checklist* is text to T.O.T.E. steps; *gates + log* is mg8-runtime evaluating every exit check (each in its own "
          "isolated subprocess) and writing the hash-chained QSON log, then verifying it. *Tree peak* includes those subprocesses.", ""]
    L += _table(["Profile", "Install", "First procedure (cold)", "Checklist / procedure", "Gates + log / procedure",
                 "Total / procedure", "Peak RSS (main)", "Tree peak", "Audit log / procedure", "Status"],
                [[r["profile"], r["variant"], sec(r.get("first_procedure_s")), sec(r.get("checklist_s_per_procedure")),
                  sec(r.get("audit_s_per_procedure")), sec(r.get("total_s_per_procedure")), mib(r.get("peak_rss_mib")),
                  mib(r["watchdog_peak_tree_rss_mib"]), mb(r.get("audit_log_bytes_per_procedure")), _status(r)] for r in pipe])
    L += ["", "## 4. Model on its own", "",
          "Prompt of 32 token IDs, then 32 new tokens, greedy. *Per token* is the warm average. *Runtime baseline* is memory "
          "after imports, before any weights. *Peak* is the larger of the main process's high-water mark and the sampled process-tree total. *Time to first answer* = integrity check + load + first call, plus the "
          "modeled SD-card time for memory-mapped pages.", ""]
    L += _table(["Profile", "Engine", "Weights", "Load", "Storage", "Time to first answer", "Per token (warm)",
                 "Runtime baseline", "Peak RSS", "Weights resident", "Read from SD", "Status"],
                [[r["profile"], r["engine"], r["format"], "memory-mapped" if r["load"] == "mmap" else "fully in RAM",
                  r["storage"], sec(first_answer_s(r)), sec(r.get("per_token_s")), mib(r.get("rss_after_import_mib")),
                  mib(peak(r)), mb(r.get("resident_weight_bytes")),
                  mb((r.get("sd_read") or {}).get("bytes_read_from_storage")), _status(r)] for r in model])
    L += ["", "## 5. Fully in RAM versus memory-mapped from the SD card", "",
          "Simulated SD card, same weights, both device profiles. Both paths check the sha256 of the weights first, which "
          "reads the whole file once. The mmap run then starts from a cold cache (the file is evicted after the check, as "
          "if memory pressure had pushed it out), so it pays for the reads twice: this is the worst case. The *no whole-file "
          "hash* column shows the mmap start if integrity were checked per block instead. Peak memory is the larger of the process high-water mark and the sampled tree total.", ""]
    rows = []
    for profile in ("1cpu-512mb", "4cpu-1gb"):
        for engine, fmt in (("numpy", "f32"), ("numpy", "int8"), ("torch", "f32")):
            a, b = pick(profile, engine=engine, format=fmt, load="ram", storage="sd-card"), \
                pick(profile, engine=engine, format=fmt, load="mmap", storage="sd-card")
            if a and b:
                rows.append([profile, f"{engine} {fmt}", sec(first_answer_s(a)), sec(first_answer_s(b)),
                             sec(mapped_only_s(b)),
                             mib(peak(a)), mib(peak(b)),
                             sec(a.get("per_token_s")), sec(b.get("per_token_s"))])
    L += _table(["Profile", "Weights", "First answer: RAM", "First answer: mmap", "mmap, no whole-file hash", "Peak RSS: RAM", "Peak RSS: mmap",
                 "Per token: RAM", "Per token: mmap"], rows)
    L += ["", "What this means: on this small model, loading fully into RAM is the faster start, because one sequential read "
          "beats page-by-page faults and the whole file is needed anyway. Memory-mapping lets the operating system load weight pages only when they are touched and "
          "drop them again under memory pressure, so the weights do not have to fit in RAM up front. For this model the "
          "saving is small, because the output layer is tied to the embedding table, so every token touches the whole "
          "table: after the first token essentially all weights are resident either way. Memory-mapping pays off when "
          "the model is larger than RAM, or when an untied or sparse lookup touches only a few rows per token. "
          "Separately, the NumPy runtime dequantizes int8 weights on every use, so int8 is smaller but slightly slower per "
          "token than float32; the 4-bit file is unpacked to float32 at load.", "",
          "## 6. Pipeline and model in one process (stand-in for ambiguous-symbol calls)", "",
          "No hook exists yet for the model to resolve ambiguous symbols inside the checklist pipeline. As a stand-in, "
          f"this run loads the int8 model memory-mapped from the simulated SD card, runs the pipeline on {len(res['combined_sources'])} "
          "procedures, and makes one 32-token model call per checklist step. It shows the combined memory and a rough time "
          "budget, not real disambiguation quality.", ""]
    L += _table(["Profile", "Model calls", "Pipeline / procedure", "Model / procedure", "Total / procedure",
                 "Peak RSS (main)", "Tree peak", "Status"],
                [[r["profile"], r.get("model_calls", "–"), sec(r.get("pipeline_s_per_procedure")),
                  sec(r.get("model_s_per_procedure")), sec(r.get("total_s_per_procedure")), mib(r.get("peak_rss_mib")),
                  mib(r["watchdog_peak_tree_rss_mib"]), _status(r)] for r in comb])
    sd = res["profiles"]["storage"]["sd-card"]
    L += ["", "## How the constraints were simulated", "",
          "* **CPUs:** `taskset -c` pins each run, and its child processes, to 1 or 4 cores; BLAS/OpenMP/PyTorch thread "
          "pools are set to the same number.",
          "* **Memory:** the box has no writable cgroup, Docker or user systemd, so a watchdog samples the resident memory of "
          "the whole process tree (PSS, so pages shared with forked children count once) every 10 ms and kills the run if it passes 512 MB or 1 GB. RLIMIT_AS was not used because it "
          "caps reserved address space, which PyTorch and OpenBLAS reserve far beyond what they use. *Peak RSS (main)* is the "
          "kernel's high-water mark for the main process (`VmHWM`). A real cgroup counts page cache too but can reclaim it; very short spikes "
          "between samples could be missed.",
          f"* **SD card:** a {sd['note']} profile. Weights loaded fully into RAM are read through a throttled reader that "
          "sleeps so the rate never beats 25 MB/s (a real delay in the read path). Memory-mapped weights fault in inside the "
          "kernel, where an unprivileged program cannot add delay, so the file is evicted from the page cache first "
          "(`posix_fadvise DONTNEED`), and afterwards `mincore` reports exactly which pages were read from storage, "
          "readahead included. Their SD time (bytes / 25 MB/s plus 0.67 ms per contiguous read) is added to the measured time.",
          "* Code, Python and libraries are always loaded from the page cache, so start-up from a real SD card will be slower.",
          "", "## Caveats", "",
          "* Simulated constraints on an x86 server CPU, not ARM hardware. A Cortex-A53 (Pi Zero 2 W / Pi 3) is several times "
          "slower per core than this CPU; expect proportionally longer times.",
          "* " + ("The model is a placeholder trained on synthetic IDs: memory, size and speed are real for this shape, its "
                  "outputs are meaningless. Re-run with `--package` once real weights exist." if w["placeholder"] else
                  "Model quality is not measured here, only size, memory and speed."),
          "* Gate evidence is simulated, as in the main demo.",
          "* One run per configuration; timings on a shared server vary by a few percent.",
          "", "## Still needed before a real Raspberry Pi run", "",
          "1. Real hardware: a Pi Zero 2 W (512 MB) and a Pi 4 / Pi 5 (1 GB+), 64-bit Raspberry Pi OS, an A1/A2 microSD card.",
          "2. Install without PyTorch: NumPy, spaCy and the `en_core_web_sm` model have aarch64 wheels; `kuzu` aarch64 support "
          "needs checking. Export the flat weight files on a PC (that step needs PyTorch), copy `demo/output/edge/weights/` "
          "to the device, then run `python demo/run_edge_benchmark.py --package <weights> --no-torch`.",
          "3. Use real limits: a cgroup (`systemd-run --scope -p MemoryMax=512M -p AllowedCPUs=0`) instead of the watchdog, and the "
          "real card instead of the simulated profile (drop caches with `echo 3 > /proc/sys/vm/drop_caches` between runs).",
          "4. Trained NYCH weights from the stage 2 run, and an ambiguous-symbol hook so the model is called only where the "
          "deterministic rules cannot decide.",
          "5. Optional: a per-block hash manifest, so a memory-mapped model can be verified without reading the whole file at boot.",
          "", f"<sub>{COPYRIGHT} Raw numbers: `edge-footprint.json`. Re-run: `python demo/run_edge_benchmark.py`.</sub>", ""]
    return "\n".join(L)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text.replace("&lt;sub&gt;", "<sub>").replace("&lt;/sub&gt;", "</sub>")


def markdown_to_html(md: str) -> str:
    """Tiny renderer for the subset this page uses (headings, lists, tables, quotes, paragraphs)."""
    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("<!--") or not ln.strip():
            i += 1
            continue
        if ln.startswith("#"):
            level = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{level}>{_inline(ln[level:].strip())}</h{level}>")
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split(" | ")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>")
            out += ["<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows[2:]]
            out.append("</tbody></table>")
        elif ln.startswith("* ") or re.match(r"\d+\. ", ln):
            tag = "ul" if ln.startswith("* ") else "ol"
            out.append(f"<{tag}>")
            while i < len(lines) and (lines[i].startswith("* ") or re.match(r"\d+\. ", lines[i])):
                out.append(f"<li>{_inline(re.sub(r'^(\* |\d+\. )', '', lines[i]))}</li>")
                i += 1
            out.append(f"</{tag}>")
        elif ln.startswith("> "):
            out.append(f"<blockquote>{_inline(ln[2:])}</blockquote>")
            i += 1
        else:
            out.append(f"<p>{_inline(ln)}</p>")
            i += 1
    style = ("body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;line-height:1.5;color:#1d1d1f}"
             "table{border-collapse:collapse;margin:1em 0;font-size:.85em}th,td{border:1px solid #ccc;padding:4px 8px;text-align:left}"
             "th{background:#f3f3f3}blockquote{border-left:4px solid #e0a800;background:#fff8e1;margin:1em 0;padding:.6em 1em}"
             "code{background:#f3f3f3;padding:0 3px}")
    return ("<!DOCTYPE html>\n<!-- " + COPYRIGHT + " -->\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>Edge-device footprint benchmark</title><style>" + style + "</style></head><body>\n"
            + "\n".join(out) + "\n</body></html>\n")


def write(results: dict, results_dir: Path) -> None:
    md = build_markdown(results)
    (Path(results_dir) / "edge-footprint.md").write_text(md, encoding="utf-8")
    (Path(results_dir) / "edge-footprint.html").write_text(markdown_to_html(md), encoding="utf-8")
