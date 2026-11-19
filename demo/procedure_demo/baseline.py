"""Baseline: a plain model asked for the same checklist as JSON. Optional; needs a model key.

Provider: Google Gemini REST API via the standard library (no SDK). Key from env GEMINI_API_KEY, model from
BASELINE_MODEL (default gemini-3-flash-preview), temperature 0. Without a key nothing is called and the comparison is
reported as PENDING; no numbers are ever invented.
"""
import json
import os
import time
import urllib.error
import urllib.request

from .common import BASES, CHECK_TYPES, load_source

DEFAULT_MODEL = "gemini-3-flash-preview"

PROMPT = """You convert a short procedure into a checklist of Test-Operate-Test-Exit (T.O.T.E.) loops.
Below is the procedure text. Each line is prefixed with its line number as `<n>| `.

Return ONLY a JSON object {{"steps": [...]}}. Each step must have:
  "step_id": short id such as "S9"
  "source_lines": list of integer line numbers the step comes from
  "source_quote": a verbatim copy of the cited source line text (no line number prefix)
  "tote": {{"initial_test": str, "operate": str, "exit": str, "max_iterations": int}}
  "exit_checks": non-empty list; each item {{"type": T, "params": {{...}}, "basis": B}}
      T is one of: {types}
        exit_code_equals  params {{"value": <int>}}      a command's exit status
        stdout_empty      params {{}}                     the command printed nothing
        numeric_at_most   params {{"limit": <number>, "unit": str}}  a measured value must be <= limit
        human_review      params {{}}                     only a person can judge it
      B is one of: {bases}
        source_stated = the cited line states it; convention_default = a general convention not stated in the
        source; human_judgement = a person decides.
Prefer a machine-checkable exit check whenever the text supports one. Do not invent facts that are not in the text.

PROCEDURE ({title})
{body}
"""


def build_prompt(source_path):
    src = load_source(source_path)
    body = "\n".join(f"{n}| {t}" for n, t in src["body"])
    return PROMPT.format(types=", ".join(CHECK_TYPES), bases=", ".join(BASES), title=src["title"], body=body)


def have_key():
    return bool(os.environ.get("GEMINI_API_KEY"))


def call_model(prompt, model=None, timeout=120, retries=3):
    model = model or os.environ.get("BASELINE_MODEL", DEFAULT_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last) from None
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            last = type(e).__name__
        time.sleep(20 * (attempt + 1) if last == "HTTP 429" else 2 ** attempt)
    raise RuntimeError(f"model call failed after {retries} tries: {last}")


def run_baseline(source_path, runs, model=None, workers=1, progress=None):
    """Return a list of raw text responses (or error strings prefixed 'ERROR:'). Sequential by default: the free-tier key rate-limits (HTTP 429) concurrent calls."""
    from concurrent.futures import ThreadPoolExecutor

    prompt = build_prompt(source_path)

    def one(_i):
        try:
            text = call_model(prompt, model, timeout=150, retries=5)
        except RuntimeError as e:
            text = f"ERROR: {e}"
        if progress:
            progress(text)
        return text

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, range(runs)))
