"""nych3-demo: paste an instructional sentence -> encoded TOTE loop(s) + exit gate + provenance + graph lookup.

    nych3-demo "Stir the sauce with a spoon until thick."            # CLI (text)
    nych3-demo --json "Beat the whites until stiff."                  # CLI (JSON)
    nych3-demo --serve [--port 8765]                                  # local page at http://127.0.0.1:8765/

Local only: the server binds 127.0.0.1 and opens the Kuzu store read-only. Nothing is written.
"""
from __future__ import annotations
import argparse, json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import registry
from .harvest.harvester import loop_id_for
from .harvest.spacy_extract import extract
from .store.tote_db import DEFAULT_DB, ToteDB

DOMAINS = ["cooking", "craft.woodworking", "craft.knitting", "craft.ropework"]
_DB = {}


def db(path=DEFAULT_DB):
    if str(path) not in _DB:
        _DB[str(path)] = ToteDB(path, seed=False, read_only=True) if Path(path).exists() else None
    return _DB[str(path)]


def _graph(d, lp):
    if d is None:
        return {"available": False}
    lid = lp["loop_id"]
    same = d.q("MATCH (l:TOTELoop {loop_id:$l}) RETURN l.loop_id AS id, l.status AS status, l.repeat_count AS repeats, l.domain AS domain", {"l": lid})
    refs = []
    for extra in (", s.flags AS flags, s.sentence_text AS sentence", ""):   # nych-3-pro's SourceRef has fewer columns
        try:
            refs = d.q("MATCH (l:TOTELoop {loop_id:$l})-[:SOURCED_FROM]->(s:SourceRef) RETURN s.isbn AS isbn, s.page AS page, "
                       "s.page_kind AS page_kind, s.fallback_gutenberg_id AS gutenberg_id" + extra + " LIMIT 3", {"l": lid})
            break
        except RuntimeError:
            continue
    similar = d.q("MATCH (l:TOTELoop) WHERE l.action_lemma=$a AND l.loop_id<>$l RETURN l.loop_id AS id, l.name AS name, l.domain AS domain, "
                  "l.status AS status, l.repeat_count AS repeats, l.exit_gate_id AS gate ORDER BY l.repeat_count DESC LIMIT 5",
                  {"a": lp["lemma"], "l": lid})
    lk = d.lookup(lp["lemma"], lp["object_lemma"] or None)
    return {"available": True, "same_structure": same[0] if same else None, "stored_sources": refs, "same_action": similar,
            "lookup": {"method": lk["method"], "match": (lk["match"] or {}).get("loop_id")}}


def encode(text: str, domain: str = "cooking", db_path=DEFAULT_DB) -> dict:
    MR, LV = registry("modality"), set(registry("lexicon")["verbs"])
    t = text.strip()
    if t and t[-1] not in ".!;:…":
        t += "."   # pasted sentences often lack the terminator the book gate expects
    outcome, loops, reason = extract(t, MR, LV, domain)
    d = db(db_path)
    out = []
    for lp in loops:
        lp["loop_id"] = loop_id_for(lp["key"])
        ex = lp["exit"]
        out.append({
            "loop_id": lp["loop_id"], "row": lp["row"],
            "steps": [{"role": s["role"], "step": s["step"], "mental_marker": s.get("mental_marker"), "cue": s.get("marker_cue")}
                      for s in lp["sense_tests"]],
            "modality_links": lp["modality_links"],
            "objects": [{k: o.get(k) for k in ("head", "lemma", "quantity", "quantity_range", "size", "role") if o.get(k)} for o in lp["objects"]],
            "tool": lp["tool"], "prohibition": lp["prohibition"],
            "exit_gate": {"gate_id": "G-" + lp["loop_id"], "condition": lp["row"]["exit"],
                          "tier": "explicit (prohibition)" if lp["prohibition"] else (ex or {}).get("provenance", "inferred"),
                          "rule": (ex or {}).get("rule", "EXIT-INFERRED-COMPLETION"), "outcomes": {"PASS": "exit", "FAIL": "repeat"}},
            "provenance": {"source": "demo input (pasted by user)", "isbn": None, "page": None,
                           "flags": ["no_source_isbn_or_page: pasted text; stored loops below carry book provenance"]},
            "graph": _graph(d, lp)})
    return {"sentence": t, "domain": domain, "outcome": outcome, "reason": reason, "loops": out}


def render(res: dict) -> str:
    L = [f"sentence: {res['sentence']}", f"domain:   {res['domain']}   outcome: {res['outcome']}" + (f" ({res['reason']})" if res["reason"] else "")]
    for i, lp in enumerate(res["loops"], 1):
        r = lp["row"]
        L += [f"\nLOOP {i}  {lp['loop_id']}",
              f"  modality : {r['modality']}", f"  actor    : {r['actor']}", f"  action   : {r['action']}",
              f"  object   : {r['object']}", f"  location : {r['perspective_location']}",
              f"  exit gate: {lp['exit_gate']['gate_id']}  [{lp['exit_gate']['tier']}]  {lp['exit_gate']['condition']}  PASS->exit FAIL->repeat"]
        for s in lp["steps"]:
            L.append(f"  {s['role']:9s}: {s['step']}" + (f"   (marker {s['mental_marker']}, cue: {s['cue']})" if s["mental_marker"] else ""))
        L.append(f"  provenance: {lp['provenance']['source']} (no ISBN/page)")
        g = lp["graph"]
        if not g["available"]:
            L.append("  graph: store not found"); continue
        ss = g["same_structure"]
        L.append(f"  graph: same structure stored -> {ss['id']} ({ss['status']}, seen {ss['repeats']}x, {ss['domain']})" if ss else "  graph: same structure not in store (new loop)")
        for s in g["stored_sources"]:
            L.append(f"         source: gutenberg {s['gutenberg_id']} page {s['page']} ({s['page_kind']}) {s.get('flags') or ''}  \"{(s.get('sentence') or '')[:90]}\"")
        if g["same_action"]:
            L.append("         same action: " + "; ".join(f"{x['name']} [{x['domain']}, {x['repeats']}x]" for x in g["same_action"]))
        L.append(f"         lookup({r['action'].rstrip(',')}): {g['lookup']['method']} -> {g['lookup']['match']}")
    if not res["loops"]:
        L.append("\n(no TOTE loop: not an instruction, or no object/tool/exit)")
    return "\n".join(L)


PAGE = """<!doctype html><meta charset=utf-8><title>NYCH3 TOTE demo (local)</title>
<style>body{font:14px system-ui;max-width:960px;margin:2em auto}textarea{width:100%;height:4em;font:15px system-ui}
.loop{border:1px solid #ccc;border-radius:8px;padding:.6em 1em;margin:.8em 0}td{padding:2px 8px;vertical-align:top}
.k{color:#666}.tier{font-weight:bold}small{color:#777}code{background:#f4f4f4;padding:0 3px}</style>
<h2>NYCH 3.0 TOTE encoder &mdash; local demo</h2>
<p><small>Local only (127.0.0.1); the graph is opened read-only. Accuracy numbers come from an agent-graded gold set pending human review.</small></p>
<textarea id=t>Stir the sauce with a spoon until thick, exactly as last time.</textarea><br>
<select id=d>%DOMS%</select> <button onclick=go()>Encode</button>
<div id=out></div>
<script>
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function go(){const r=await fetch('/api/encode?d='+encodeURIComponent(d.value)+'&t='+encodeURIComponent(t.value));const j=await r.json();
let h=`<p>outcome: <b>${esc(j.outcome)}</b> ${j.reason?'('+esc(j.reason)+')':''}</p>`;
for(const l of j.loops){const r=l.row,g=l.graph;h+=`<div class=loop><b>${esc(l.loop_id)}</b><table>
<tr><td class=k>modality</td><td>${esc(r.modality)}</td></tr><tr><td class=k>actor</td><td>${esc(r.actor)}</td></tr>
<tr><td class=k>action</td><td>${esc(r.action)}</td></tr><tr><td class=k>object</td><td>${esc(r.object)}</td></tr>
<tr><td class=k>location</td><td>${esc(r.perspective_location)}</td></tr>
<tr><td class=k>exit gate</td><td><code>${esc(l.exit_gate.gate_id)}</code> <span class=tier>[${esc(l.exit_gate.tier)}]</span> ${esc(l.exit_gate.condition)} &nbsp;PASS&rarr;exit FAIL&rarr;repeat</td></tr>
${l.steps.map(s=>`<tr><td class=k>${esc(s.role)}</td><td>${esc(s.step)} ${s.mental_marker?'<small>(marker '+esc(s.mental_marker)+', cue: '+esc(s.cue)+')</small>':''}</td></tr>`).join('')}
<tr><td class=k>provenance</td><td>${esc(l.provenance.source)} <small>(no ISBN/page)</small></td></tr>
<tr><td class=k>graph</td><td>${!g.available?'store not found':(g.same_structure?`same structure stored: <b>${esc(g.same_structure.id)}</b> (${esc(g.same_structure.status)}, seen ${g.same_structure.repeats}&times;, ${esc(g.same_structure.domain)})`:'new structure (not in store)')}
${(g.stored_sources||[]).map(s=>`<br><small>source: Gutenberg ${esc(s.gutenberg_id)} p.${esc(s.page)} (${esc(s.page_kind)}) &ldquo;${esc((s.sentence||'').slice(0,110))}&rdquo;</small>`).join('')}
${(g.same_action||[]).length?'<br><small>same action: '+g.same_action.map(x=>esc(x.name)+' ['+esc(x.domain)+', '+x.repeats+'&times;]').join('; ')+'</small>':''}</td></tr></table></div>`}
if(!j.loops.length)h+='<p>(no TOTE loop: not an instruction, or no object/tool/exit)</p>';out.innerHTML=h}
go()</script>"""


class _H(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/encode":
            q = parse_qs(u.query)
            body = json.dumps(encode(q.get("t", [""])[0], q.get("d", ["cooking"])[0], self.db_path), ensure_ascii=False, default=str).encode()
            ctype = "application/json; charset=utf-8"
        elif u.path == "/":
            body = PAGE.replace("%DOMS%", "".join(f"<option>{d}</option>" for d in DOMAINS)).encode()
            ctype = "text/html; charset=utf-8"
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3-demo")
    ap.add_argument("sentence", nargs="*"); ap.add_argument("--domain", default="cooking", choices=DOMAINS)
    ap.add_argument("--json", action="store_true"); ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--serve", action="store_true"); ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    if a.serve:
        _H.db_path = a.db
        print(f"NYCH3 demo on http://127.0.0.1:{a.port}/  (local only, read-only store {a.db}; Ctrl-C to stop)", flush=True)
        ThreadingHTTPServer(("127.0.0.1", a.port), _H).serve_forever()
        return
    text = " ".join(a.sentence) or sys.stdin.read()
    res = encode(text, a.domain, a.db)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str) if a.json else render(res))


if __name__ == "__main__":
    main()
