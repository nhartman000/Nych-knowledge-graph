import hashlib
import json
import re


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_source(path):
    """Return {path, sha256, header, lines:[(lineno, text)]}. Line numbers are 1-based over the whole file.

    The header is everything up to and including the first line that starts with 'Change notice:'
    (the layout used by the T.O.T.E-loops evidence excerpts). Body lines are the procedure text.
    """
    raw = open(path, encoding="utf-8").read()
    all_lines = raw.splitlines()
    cut = next((i for i, l in enumerate(all_lines) if l.startswith("Change notice:")), -1)
    meta = {}
    for l in all_lines[: cut + 1]:
        for key in ("Rights", "Publisher", "Source"):
            if l.startswith(key + ":"):
                meta[key.lower()] = l.split(":", 1)[1].strip()
    url = next((l for l in all_lines[: cut + 1] if l.startswith("http")), None)
    return {
        "path": str(path),
        "sha256": sha256_text(raw),
        "title": all_lines[1] if len(all_lines) > 1 else "",
        "url": url,
        "meta": meta,
        "body": [(i + 1, all_lines[i]) for i in range(cut + 1, len(all_lines)) if all_lines[i].strip()],
    }


# ---- exit-check vocabulary shared by the pipeline and the baseline -------------------------------
CHECK_TYPES = ("exit_code_equals", "stdout_empty", "numeric_at_most", "human_review")
MACHINE_TYPES = ("exit_code_equals", "stdout_empty", "numeric_at_most")
BASES = ("source_stated", "convention_default", "human_judgement")


def evidence_paths(step_id):
    """Where the gate looks for each check type's evidence value."""
    return {
        "exit_code_equals": f"/evidence/{step_id}/exit_code",
        "stdout_empty": f"/evidence/{step_id}/stdout_empty",
        "numeric_at_most": f"/evidence/{step_id}/value",
        "human_review": f"/evidence/{step_id}/approved",
    }


STEP_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
