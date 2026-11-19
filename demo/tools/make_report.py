#!/usr/bin/env python3
"""Build the single self-contained HTML report (demo/results/report.html): no network, no external assets.

  python demo/tools/make_report.py [--bench demo/results/benchmark_summary_2026-11-19.json] [--out demo/results/report.html]

Everything shown is recomputed when this runs (checklists, gate outcomes, the tamper test) except the baseline table,
which is read from the saved benchmark summary (real model calls made earlier; see demo/results/RESULTS.md).
"""
import argparse
import html
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))

from procedure_demo import audit  # noqa: E402
from procedure_demo.checklist import build_checklist  # noqa: E402
from procedure_demo.common import load_source  # noqa: E402

SMALL = ["pg_verifybackup", "pg_checksums", "original_release_check_sop"]
E = html.escape

CSS = """
body{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;margin:0;color:#1d2330;background:#f6f7f9}
header{background:#14213d;color:#fff;padding:18px 28px}header h1{margin:0 0 4px;font-size:21px}header p{margin:2px 0;color:#cdd5e6}
main{padding:18px 28px;max-width:1500px;margin:auto}h2{margin:28px 0 8px;font-size:18px;border-bottom:2px solid #d8dce5;padding-bottom:4px}
.note{background:#fff8e1;border-left:4px solid #f0b429;padding:8px 12px;margin:8px 0}.warn{background:#fdecea;border-left:4px solid #d64545;padding:8px 12px;margin:8px 0}
.grid{display:grid;grid-template-columns:minmax(340px,5fr) minmax(420px,7fr);gap:14px;align-items:start}
.panel{background:#fff;border:1px solid #d8dce5;border-radius:6px;overflow:hidden}.panel h3{margin:0;padding:8px 12px;background:#eef1f6;font-size:13px}
.src{font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;padding:6px 0;max-height:720px;overflow:auto}
.src div{display:flex;padding:0 10px;white-space:pre-wrap}.src b{flex:0 0 34px;color:#8a93a6;font-weight:normal}.src .cited{background:#e8f3ff}.src .un{color:#8a93a6}
.steps{max-height:720px;overflow:auto;padding:8px}.step{border:1px solid #e1e5ee;border-radius:5px;padding:7px 9px;margin-bottom:7px}
.step .top{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.step code{background:#f1f3f8;padding:0 4px;border-radius:3px}
q{display:block;margin:4px 0;color:#34405a;font-style:italic;quotes:none;border-left:3px solid #c9d3ea;padding-left:7px}
.badge{display:inline-block;padding:0 7px;border-radius:9px;font-size:11px;font-weight:600;color:#fff}.PASS{background:#2e8b57}.FAIL{background:#c0392b}.INTERMEDIATE{background:#d68910}
.chk{font-size:12px;color:#4a566e}table{border-collapse:collapse;width:100%;background:#fff}td,th{border:1px solid #d8dce5;padding:5px 8px;text-align:right}
th:first-child,td:first-child{text-align:left}th{background:#eef1f6}tr.sec td{background:#f6f7f9;font-weight:600;text-align:left}
pre{background:#10172a;color:#d6e0ff;padding:10px;border-radius:6px;overflow:auto;font-size:12px}pre .bad{color:#ff8f8f}pre .ok{color:#8fe3a8}
details{margin:8px 0}summary{cursor:pointer;font-weight:600;padding:5px 0}.pend{color:#9a6700;font-weight:600}.tiny{font-size:12px;color:#5b667d}
"""


def badge(o):
    return f'<span class="badge {o}">{o}</span>'


def source_section(name, tmp):
    path = HERE / "sources" / f"{name}.txt"
    src = load_source(path)
    cl = build_checklist(path)
    outcomes = {}
    for sc in audit.SCENARIOS:
        m = audit.run_audit(cl, sc, tmp / sc / name)
        outcomes[sc] = {r["step_id"]: r["outcome"] for r in m["results"]}
    cited = {n for st in cl["steps"] for n in st["source_lines"]}
    left = "".join(f'<div class="{"cited" if n in cited else "un"}"><b>{n}</b><span>{E(t)}</span></div>' for n, t in src["body"])
    cards = []
    for st in cl["steps"]:
        sid = st["step_id"]
        checks = "; ".join(f'{c["type"]} {json.dumps(c["params"])} <i>[{c["basis"]}]</i>' for c in st["exit_checks"])
        gates = " ".join(f'<span class="tiny">{sc}:</span> {badge(outcomes[sc][sid])}' for sc in audit.SCENARIOS)
        cards.append(f'<div class="step"><div class="top"><code>{E(sid)}</code> <b>{E(st["tote"]["operate"][:110])}</b></div>'
                     f'<q>"{E(st["source_quote"])}" <span class="tiny">(source line{"s" if len(st["source_lines"])>1 else ""} '
                     f'{", ".join(map(str, st["source_lines"]))})</span></q><div class="chk">exit check: {checks}</div>'
                     f'<div style="margin-top:3px">{gates}</div></div>')
    n_un = len(cl["unmapped_lines"])
    meta = f'{E(src["title"])} &middot; {len(cl["steps"])} steps &middot; {n_un} source lines not turned into steps (shown grey, listed in the checklist as unmapped)'
    return (f'<div class="tiny">{meta}<br>Source: {E(src["url"] or "")} &middot; Rights: {E(src["meta"].get("rights", ""))}</div>'
            f'<div class="grid"><div class="panel"><h3>Procedure text (blue = cited by a step)</h3><div class="src">{left}</div></div>'
            f'<div class="panel"><h3>Generated checklist: source quote, exit check, gate result per scenario</h3><div class="steps">{"".join(cards)}</div></div></div>')


def tamper_section(tmp):
    cl = build_checklist(HERE / "sources" / "pg_verifybackup.txt")
    d = tmp / "tamper"
    manifest = audit.run_audit(cl, "one-fails", d)
    failed = next(r for r in manifest["results"] if r["outcome"] != "PASS")
    sid = failed["step_id"]
    ok0, p0 = audit.verify_audit(d)
    out = [f"scenario one-fails: step {sid} is recorded as {failed['outcome']} (simulated bad evidence)",
           f'verify BEFORE any edit: <span class="ok">{"OK" if ok0 else "FAILED " + str(p0)}</span>']
    target = d / failed["qson"]
    doc = json.loads(target.read_text())
    ev = next(e for e in doc["events"] if e["action"] == "evidence_collected")
    before = json.dumps(ev["evidence"]["value"], sort_keys=True)
    key = "exit_code" if "exit_code" in ev["evidence"]["value"] else next(iter(ev["evidence"]["value"]))
    ev["evidence"]["value"][key] = 0 if key == "exit_code" else True
    after = json.dumps(ev["evidence"]["value"], sort_keys=True)
    target.write_text(json.dumps(doc))
    ok1, p1 = audit.verify_audit(d)
    out += [f"EDIT 1 in {failed['qson']}: recorded evidence {before}  ->  {after}   (hide the failure)",
            f'verify AFTER edit 1: <span class="bad">{"OK (NOT CAUGHT)" if ok1 else "CAUGHT: " + "; ".join(p1)}</span>']
    d2 = tmp / "tamper2"
    audit.run_audit(cl, "all-pass", d2)
    t2 = d2 / "S10.qson"
    doc2 = json.loads(t2.read_text())
    removed = doc2["events"].pop(2)
    t2.write_text(json.dumps(doc2))
    ok2, p2 = audit.verify_audit(d2)
    out += [f"EDIT 2 in S10.qson (all-pass run): delete the '{removed['action']}' event (remove inconvenient history)",
            f'verify AFTER edit 2: <span class="bad">{"OK (NOT CAUGHT)" if ok2 else "CAUGHT: " + "; ".join(p2)}</span>']
    d3 = tmp / "tamper3"
    audit.run_audit(cl, "all-pass", d3)
    m = json.loads((d3 / "audit_manifest.json").read_text())
    m["scenario"] = "doctored"
    (d3 / "audit_manifest.json").write_text(json.dumps(m))
    ok3, p3 = audit.verify_audit(d3)
    out += ["EDIT 3 in audit_manifest.json: change scenario 'all-pass' -> 'doctored'",
            f'verify AFTER edit 3: <span class="bad">{"OK (NOT CAUGHT)" if ok3 else "CAUGHT: " + "; ".join(p3)}</span>']
    assert not (ok1 or ok2 or ok3) and ok0
    return "<pre>" + "\n".join(out) + "</pre>"


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "n/a"


def table_section(bench):
    if not bench:
        return '<p class="pend">Baseline comparison not available in this build (no benchmark summary found).</p>'
    pm = bench["pipeline_metrics"]
    cols = [("Pipeline (deterministic rules)", pm, len(bench["sources"]))]
    base = bench.get("baseline")
    notes = []
    if isinstance(base, dict):
        for cond, label in (("t0", "temperature 0"), ("tdefault", "default temperature")):
            if cond in base["conditions"]:
                cols.append((f'{base["model"]} ({label})', base["conditions"][cond]["total"], None))
    rows = []

    def row(label, f):
        rows.append(f"<tr><td>{label}</td>" + "".join(f"<td>{f(t)}</td>" for _n, t, _s in cols) + "<td class='pend'>PENDING</td></tr>")

    rows.append("<tr class='sec'><td colspan='%d'>Mechanical checks (anyone can re-run them)</td></tr>" % (len(cols) + 2))
    row("Runs counted (API errors excluded)", lambda t: f'{t["runs"]}' + (f' (+{t["api_errors"]} API errors)' if t["api_errors"] else ""))
    row("Schema-valid outputs", lambda t: f'{t["schema_valid_runs"]}/{t["runs"]} ({pct(t["schema_valid_runs"], t["runs"])})')
    row("Sources with identical output on every rerun", lambda t: f'{t["sources_identical_across_runs"]}/{t["sources"]}')
    row("Steps whose quote is verbatim in the cited lines", lambda t: f'{t["traceable"]}/{t["steps"]} ({pct(t["traceable"], t["steps"])})')
    row("Steps with a machine-runnable exit check", lambda t: f'{t["machine_checkable"]}/{t["steps"]} ({pct(t["machine_checkable"], t["steps"])})')
    row("Numeric limits not found in the cited line", lambda t: f'{t["numeric_limits_not_in_cited_lines"]}')
    rows.append("<tr class='sec'><td colspan='%d'>Step recall against hand-made gold lists (graded by an AI assistant, not a human)</td></tr>" % (len(cols) + 2))
    row("Gold steps covered", lambda t: f'{t["gold_covered"]}/{t["gold_steps"]} ({pct(t["gold_covered"], t["gold_steps"])})' if t.get("gold_steps") else "n/a")
    row("Produced steps that match no gold step (extra/spurious)", lambda t: f'{t["spurious_steps"]}/{t["steps_on_gold_sources"]} ({pct(t["spurious_steps"], t["steps_on_gold_sources"])})' if t.get("gold_steps") else "n/a")
    head = "".join(f"<th>{E(n)}</th>" for n, _t, _s in cols) + "<th>OpenAI baseline</th>"
    tbl = f"<table><tr><th>Measure</th>{head}</tr>{''.join(rows)}</table>"
    per = ""
    if isinstance(base, dict):
        names = sorted(bench["sources"])
        ps_rows = []
        for nm in names:
            cells = [f'{bench["sources"][nm]["steps"]} steps']
            for cond in ("t0", "tdefault"):
                if cond in base["conditions"]:
                    ps = base["conditions"][cond]["per_source"][nm]
                    cells.append(f'{ps["steps"] // ps["schema_valid_runs"] if ps["schema_valid_runs"] else 0} steps/run, {ps["distinct_outputs"]} distinct')
            pp = bench["pipeline_per_source"][nm] if "pipeline_per_source" in bench else {}
            g = lambda d: (f'{d["gold_covered"]}/{d["gold_steps"]}' if d.get("gold_steps") else "-")
            cells2 = [g(pp)] if pp else ["-"]
            for cond in ("t0", "tdefault"):
                if cond in base["conditions"]:
                    cells2.append(g(base["conditions"][cond]["per_source"][nm]))
            ps_rows.append(f"<tr><td>{nm}</td><td>{' | '.join(cells)}</td><td>{' | '.join(cells2)}</td></tr>")
        per = ("<h3>Per source</h3><p class='tiny'>Gold recall columns: pipeline | model t=0 | model default temperature, summed over reruns.</p>"
               "<table><tr><th>Source</th><th>Steps (pipeline | model t=0 | model default)</th><th>Gold steps covered (summed over reruns)</th></tr>" + "".join(ps_rows) + "</table>")
    meta = (f'<p class="tiny">Model: {E(base["provider"])}:{E(base["model"])}; {base["runs_per_source"]} reruns per source per setting; '
            f'{len(bench["sources"])} public procedures.</p>') if isinstance(base, dict) else ""
    return meta + tbl + per


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(HERE / "results" / "benchmark_summary_2026-11-19.json"))
    ap.add_argument("--out", default=str(HERE / "results" / "report.html"))
    ap.add_argument("--copy-to", help="also write a copy here")
    a = ap.parse_args(argv)
    bench = json.loads(Path(a.bench).read_text()) if Path(a.bench).exists() else None
    names = sorted(p.stem for p in (HERE / "sources").glob("*.txt") if "LICENSE" not in p.name)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        small = "".join(f"<h2>Procedure to checklist: {n}</h2>{source_section(n, tmp)}" for n in SMALL)
        more = "".join(f"<details><summary>{n}</summary>{source_section(n, tmp)}</details>" for n in names if n not in SMALL)
        tamper = tamper_section(tmp)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>NYCH procedure-to-checklist demo report</title><style>{CSS}</style></head><body>
<header><h1>Procedure &rarr; checklist &rarr; gated, tamper-evident audit log</h1>
<p>Generated by demo/tools/make_report.py from the code and public sources in this repository. One self-contained file; opens offline.</p></header><main>
<div class="warn"><b>Read this first.</b> The gate evidence in this report is <b>simulated</b> (the demo does not run pg_verifybackup etc.). What is real: the checklist extraction, the gate evaluation, single-use permits, the hash-chained QSON log, and the tamper detection. Step recall uses gold lists made by an AI assistant, not a human expert. Gate outcomes: PASS = all checks satisfied by tool evidence; FAIL = a check failed; INTERMEDIATE = evidence missing or from the wrong source (for example a human approval cannot satisfy a tool check).</div>
{small}
<h2>Seven more public procedures (click to open)</h2>{more}
<h2>Tamper test: edit the log, watch it get caught</h2>{tamper}
<h2>Baseline comparison: pipeline vs a plain model asked for the same checklist</h2>{table_section(bench)}
</main></body></html>"""
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(page, encoding="utf-8")
    if a.copy_to:
        shutil.copyfile(a.out, a.copy_to)
    print(f"wrote {a.out} ({len(page) // 1024} KiB)")


if __name__ == "__main__":
    main()
