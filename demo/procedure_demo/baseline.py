"""Baseline: a plain model asked for the same checklist as JSON. Optional; needs a model key.

Providers (standard library only, no SDK):
  gemini  Google Gemini REST API. Key from env GEMINI_API_KEY. Default model gemini-3.1-flash-lite-preview.
  openai  OpenAI Chat Completions API. Key from env OPENAI_API_KEY (read only from the environment, never written
          anywhere). Default model gpt-4.1-mini.
The model can be changed with --model-name (or BASELINE_MODEL). Temperature is 0 or the provider's default
(parameter omitted). Without a key nothing is called and the comparison is reported as PENDING; no numbers are ever
invented. HTTP/network failures are returned as 'ERROR: ...' strings and are excluded from the metrics.
"""
import json
import os
import time
import urllib.error
import urllib.request

from .common import BASES, CHECK_TYPES, load_source

PROVIDERS = ("gemini", "openai")
DEFAULT_MODELS = {"gemini": "gemini-3.1-flash-lite-preview", "openai": "gpt-4.1-mini"}
KEY_ENV = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
DEFAULT_MODEL = DEFAULT_MODELS["gemini"]  # kept for older callers

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


def have_key(provider="gemini"):
    return bool(os.environ.get(KEY_ENV[provider]))


def _request(provider, model, prompt, temperature):
    """Build (url, body bytes, headers) for one call. temperature None = provider default (parameter omitted)."""
    key = os.environ[KEY_ENV[provider]]
    if provider == "gemini":
        cfg = {"responseMimeType": "application/json"}
        if temperature is not None:
            cfg["temperature"] = temperature
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
        return (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                json.dumps(body).encode(), {"Content-Type": "application/json", "x-goog-api-key": key})
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
    if temperature is not None:
        body["temperature"] = temperature
    return ("https://api.openai.com/v1/chat/completions", json.dumps(body).encode(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})


def _extract(provider, data):
    if provider == "gemini":
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return data["choices"][0]["message"]["content"]


def call_model(prompt, model=None, timeout=120, retries=3, provider="gemini", temperature=0):
    model = model or os.environ.get("BASELINE_MODEL") or DEFAULT_MODELS[provider]
    url, body, headers = _request(provider, model, prompt, temperature)
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return _extract(provider, json.load(r))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429 and provider == "openai":
                detail = e.read().decode("utf-8", "ignore")
                if "insufficient_quota" in detail or "credit_balance" in detail:  # permanent for this key: stop retrying
                    raise RuntimeError("HTTP 429 insufficient_quota (no API credit on this key)") from None
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last) from None
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as e:
            last = type(e).__name__
        time.sleep(20 * (attempt + 1) if last == "HTTP 429" else 2 ** attempt)
    raise RuntimeError(f"model call failed after {retries} tries: {last}")


def run_baseline(source_path, runs, model=None, workers=1, progress=None, provider="gemini", temperature=0):
    """Return a list of raw text responses (or error strings prefixed 'ERROR:'). Sequential by default: free-tier keys rate-limit (HTTP 429) concurrent calls."""
    from concurrent.futures import ThreadPoolExecutor

    prompt = build_prompt(source_path)

    def one(_i):
        try:
            text = call_model(prompt, model, timeout=150, retries=5, provider=provider, temperature=temperature)
        except RuntimeError as e:
            text = f"ERROR: {e}"
        if progress:
            progress(text)
        return text

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, range(runs)))
