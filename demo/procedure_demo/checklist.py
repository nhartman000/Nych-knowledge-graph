"""Deterministic procedure text -> T.O.T.E. checklist. No model call, no network.

Stages
  1. nych3 (existing encoder) decides which natural-language sentences are imperative actions and
     gives each a stable loop id and its exit-gate rule.
  2. A few explicit, documented rules (below) recognise things the cookbook-tuned encoder cannot:
     shell command lines, "exit status is zero if ...", "do not print anything when ...",
     and "must not be higher than N unit" thresholds. These produce machine-checkable exit checks.
  3. Everything else that is an instruction gets a human_review exit check (honest: not machine-checkable).
  Lines that match nothing are reported in `unmapped_lines`, never silently dropped.
"""
import re

from .common import canonical, load_source, sha256_text

RULES_VERSION = "procedure-rules-1"

_CMD = re.compile(r"^\$\s+(?P<cmd>\S.*)$")
_NO_OUTPUT = re.compile(r"^(?:do not|don't)\s+print anything when\s+(?P<when>.+?)\.?$", re.I)
_EXIT_STATUS = re.compile(
    r"^when\s+(?P<what>.+?),\s+the exit status is zero if\s+(?P<ok>.+?),\s+and nonzero if\s+(?P<bad>.+?)\.?$", re.I)
_MUST_EXIT_ZERO = re.compile(r"^(?P<what>.+?)\s+must exit with status zero\.?$", re.I)
_THRESHOLD = re.compile(
    r"^(?P<subject>.+?)\s+(?:should|must)\s+not\s+be\s+(?:higher|greater|more|larger)\s+than\s+"
    r"(?P<limit>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%]+)\b.*$", re.I)
_CHECK_THAT = re.compile(r"^(?:check|confirm|verify|ensure)\s+that\s+.+", re.I)
_CONFIRM = re.compile(r"^(?:confirm|verify|ensure)\s+.+", re.I)


def _step(step_id, line, text, kind, operation, checks, extra=None):
    s = {
        "step_id": step_id,
        "kind": kind,
        "source_lines": [line],
        "source_quote": text,
        "tote": {
            "initial_test": "none stated in source",
            "operate": operation,
            "exit": "all exit_checks pass on fresh evidence",
            "max_iterations": 3,
        },
        "exit_checks": checks,
    }
    if extra:
        s["nych3"] = extra
    return s


def _nych3_action(text):
    """Ask the existing nych3 extractor whether `text` is an imperative action; return its metadata or None."""
    from nych3.config import registry
    from nych3.harvest.harvester import loop_id_for
    from nych3.harvest.spacy_extract import extract

    outcome, loops, _reason = extract(text, registry("modality"), set(registry("lexicon")["verbs"]), "cooking")
    if outcome != "action" or not loops:
        return None
    lp = loops[0]
    return {"loop_id": loop_id_for(lp["key"]), "action_lemma": lp["lemma"], "outcome": outcome}


def build_checklist(source_path, use_nych3=True):
    src = load_source(source_path)
    steps, unmapped = [], []
    last_cmd = None
    for lineno, text in src["body"]:
        t = text.strip()
        sid = f"S{lineno}"
        m = _CMD.match(t)
        if m:
            cmd = m.group("cmd")
            last_cmd = _step(
                sid, lineno, text, "command", cmd,
                [{"type": "exit_code_equals", "params": {"value": 0}, "basis": "convention_default",
                  "note": "POSIX convention: exit status 0 means success; the source does not state it"}])
            steps.append(last_cmd)
            continue
        m = _NO_OUTPUT.match(t)
        if m and last_cmd is not None:
            last_cmd["exit_checks"].append(
                {"type": "stdout_empty", "params": {}, "basis": "source_stated",
                 "note": f"source line {lineno}: no output when {m.group('when')}"})
            last_cmd["source_lines"].append(lineno)
            continue
        m = _EXIT_STATUS.match(t)
        if m:
            steps.append(_step(sid, lineno, text, "exit_status_rule", f"Run the check when {m.group('what')}",
                               [{"type": "exit_code_equals", "params": {"value": 0}, "basis": "source_stated",
                                 "note": f"zero only if {m.group('ok')}"}]))
            continue
        m = _MUST_EXIT_ZERO.match(t)
        if m:
            target = last_cmd if last_cmd is not None else None
            check = {"type": "exit_code_equals", "params": {"value": 0}, "basis": "source_stated",
                     "note": f"source line {lineno}: must exit with status zero"}
            if target is not None:
                target["exit_checks"] = [c for c in target["exit_checks"] if c["type"] != "exit_code_equals"] + [check]
                target["source_lines"].append(lineno)
            else:
                steps.append(_step(sid, lineno, text, "exit_status_rule", m.group("what"), [check]))
            continue
        m = _THRESHOLD.match(t)
        if m:
            limit = float(m.group("limit"))
            limit = int(limit) if limit == int(limit) else limit
            steps.append(_step(sid, lineno, text, "threshold",
                               f"Measure {m.group('subject')} in {m.group('unit')}",
                               [{"type": "numeric_at_most", "params": {"limit": limit, "unit": m.group("unit")},
                                 "basis": "source_stated", "note": f"limit {limit} appears in source line {lineno}"}]))
            continue
        if _CHECK_THAT.match(t) or _CONFIRM.match(t):
            steps.append(_step(sid, lineno, text, "instruction", t.rstrip("."),
                               [{"type": "human_review", "params": {}, "basis": "human_judgement",
                                 "note": "no machine-checkable predicate in the source"}]))
            continue
        meta = _nych3_action(t) if use_nych3 else None
        if meta:
            steps.append(_step(sid, lineno, text, "instruction", t.rstrip("."),
                               [{"type": "human_review", "params": {}, "basis": "human_judgement",
                                 "note": "no machine-checkable predicate in the source"}], extra=meta))
            continue
        unmapped.append({"line": lineno, "text": text, "reason": "no rule or encoder action matched"})
    doc = {
        "checklist_version": "1.0",
        "rules_version": RULES_VERSION,
        "source": {"path": src["path"].split("/")[-1], "sha256": src["sha256"], "title": src["title"],
                   "url": src["url"], "rights": src["meta"].get("rights")},
        "steps": steps,
        "unmapped_lines": unmapped,
    }
    doc["checklist_sha256"] = sha256_text(canonical({k: v for k, v in doc.items()}))
    return doc
