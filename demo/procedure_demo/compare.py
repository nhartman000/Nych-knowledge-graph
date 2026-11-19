"""Small, honest metrics for comparing checklist producers. They do NOT measure whether the steps are
semantically right (that needs human grading); they measure properties a buyer can check mechanically."""
import json
from pathlib import Path

from .common import MACHINE_TYPES, canonical, load_source
from .exitchecks import is_machine_checkable
from .schema import CHECKLIST_SCHEMA


def parse(raw):
    """raw text -> (checklist dict | None, error | None)"""
    try:
        return json.loads(raw), None
    except (TypeError, ValueError) as e:
        return None, f"not JSON: {type(e).__name__}"


def schema_valid(doc):
    import jsonschema
    try:
        jsonschema.validate(doc, CHECKLIST_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False


def _line_map(source_path):
    return {n: t for n, t in load_source(source_path)["body"]}


def step_metrics(doc, source_path):
    """Per-step mechanical metrics for a schema-valid checklist."""
    lines = _line_map(source_path)
    total = trace_ok = machine = unsupported_numbers = 0
    for step in doc.get("steps", []):
        total += 1
        cited = step.get("source_lines", [])
        quote = step.get("source_quote", "")
        joined = "\n".join(lines[n] for n in sorted(set(cited)) if n in lines)
        if cited and all(n in lines for n in cited) and quote.strip() and (
                quote.strip() in joined or any(quote.strip() in lines[n] for n in cited)):
            trace_ok += 1
        if is_machine_checkable(step):
            machine += 1
        for c in step.get("exit_checks", []):
            if c.get("type") == "numeric_at_most":
                limit = (c.get("params") or {}).get("limit")
                text = " ".join(lines.get(n, "") for n in cited)
                if limit is None or str(limit) not in text:
                    unsupported_numbers += 1
    return {"steps": total, "traceable": trace_ok, "machine_checkable": machine,
            "numeric_limits_not_in_cited_lines": unsupported_numbers}


def load_gold(gold_dir):
    """{source_stem: gold dict} from demo/gold/*.json. Gold = hand-checked list of the procedure's real steps, each
    with the source line numbers that state it. Graded by the author of the file (see its 'graded_by' field)."""
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(gold_dir).glob("*.json"))}


def recall_metrics(doc, gold):
    """Line-based step recall: a gold step is covered when some produced step cites at least one of its lines;
    a produced step is spurious when it cites no line of any gold step. Mechanical matching, human-made gold."""
    gold_sets = [set(g["lines"]) for g in gold["steps"]]
    all_gold_lines = set().union(*gold_sets) if gold_sets else set()
    cited = [set(st.get("source_lines", [])) for st in doc.get("steps", [])]
    covered = sum(1 for gs in gold_sets if any(gs & c for c in cited))
    spurious = sum(1 for c in cited if not (c & all_gold_lines))
    return {"gold_steps": len(gold_sets), "gold_covered": covered, "spurious_steps": spurious, "steps_on_gold_sources": len(cited)}


def summarize(runs_by_source, source_paths, gold=None):
    """runs_by_source: {name: [raw_text_or_dict, ...]} -> aggregate metrics dict."""
    per_source, tot = {}, {"runs": 0, "api_errors": 0, "schema_valid_runs": 0, "steps": 0, "traceable": 0, "machine_checkable": 0,
                           "numeric_limits_not_in_cited_lines": 0, "sources": 0, "sources_identical_across_runs": 0}
    if gold:
        tot.update({"gold_steps": 0, "gold_covered": 0, "spurious_steps": 0, "steps_on_gold_sources": 0})
    for name, runs in runs_by_source.items():
        docs, valid, errors, api_errors = [], 0, 0, 0
        for r in runs:
            if isinstance(r, str) and r.startswith("ERROR:"):
                api_errors += 1  # infrastructure failure: excluded from every metric, reported separately
                continue
            doc, err = (r, None) if isinstance(r, dict) else parse(r)
            if doc is None or not schema_valid(doc):
                errors += 1
                docs.append(None)
                continue
            valid += 1
            docs.append(doc)
        distinct = len({canonical(d) if d is not None else "INVALID" for d in docs}) if docs else 0
        m = {"steps": 0, "traceable": 0, "machine_checkable": 0, "numeric_limits_not_in_cited_lines": 0}
        for d in docs:
            if d is not None:
                for k, v in step_metrics(d, source_paths[name]).items():
                    m[k] += v
        if gold and name in gold:
            rm = {"gold_steps": 0, "gold_covered": 0, "spurious_steps": 0, "steps_on_gold_sources": 0}
            for d in docs:
                # an invalid output covers nothing: count its gold steps as missed
                for k, v in (recall_metrics(d, gold[name]) if d is not None else
                             {"gold_steps": len(gold[name]["steps"]), "gold_covered": 0, "spurious_steps": 0, "steps_on_gold_sources": 0}).items():
                    rm[k] += v
            m.update(rm)
        per_source[name] = {"runs": len(docs), "api_errors": api_errors, "schema_valid_runs": valid, "distinct_outputs": distinct, **m}
        tot["runs"] += len(docs)
        tot["api_errors"] += api_errors
        tot["schema_valid_runs"] += valid
        tot["sources"] += 1
        tot["sources_identical_across_runs"] += 1 if distinct == 1 else 0
        for k in m:
            tot[k] += m[k]
    return {"per_source": per_source, "total": tot}
