"""Stage 11: candidate paths with ordered likelihood classes; appends to output/trace.jsonl."""
import sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))
from nych3.paths import candidate_paths, write_trace

gst = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
res = candidate_paths(gst)
out = ROOT / "11_paths" / "output"; out.mkdir(exist_ok=True)
(out / "paths.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
write_trace(res, out / "trace.jsonl")
print(json.dumps(res, ensure_ascii=False, indent=1))
