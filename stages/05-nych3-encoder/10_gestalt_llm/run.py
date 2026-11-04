"""Stage 10: build request -> provider (mock by default) -> validate (NYCH3 + mg8) -> proposed mappings.
Persisting to Kuzu requires --approve (GATE.md)."""
import sys, json, pathlib, argparse
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))
from nych3.llm.gestalt_call import build_request, MockProvider, validate_plan, validate_with_mg8, fill_cells, persist
from nych3.store.tote_db import ToteDB, DEFAULT_DB

ap = argparse.ArgumentParser(); ap.add_argument("gst"); ap.add_argument("--approve", action="store_true"); ap.add_argument("--db", default=str(DEFAULT_DB))
a = ap.parse_args()
gst = json.loads(pathlib.Path(a.gst).read_text(encoding="utf-8"))
req = build_request(gst)
plan = MockProvider().propose(req)
accepted = validate_plan(plan, req)
mg8 = validate_with_mg8(plan, gst)
rows = [dict(i, row=fill_cells(i["row"], accepted)) for i in gst["nych3"]["tote"]["instances"]]
out = ROOT / "10_gestalt_llm" / "output"; out.mkdir(exist_ok=True)
(out / "mappings.json").write_text(json.dumps({"request": req, "plan": plan, "accepted": accepted, "mg8_validator": mg8,
                                               "rows": [r["row"] for r in rows], "gate_10": "approved" if a.approve else "pending"}, ensure_ascii=False, indent=2), encoding="utf-8")
if a.approve:
    print("persisted", persist(ToteDB(a.db), accepted, gst, session=gst["state_id"], approved=True))
print(f"stage 10: {len(accepted)} mappings validated (nych3 ok, mg8 validator: {mg8}); gate 10 {'approved' if a.approve else 'pending'}")
