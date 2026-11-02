"""Stage 02 structure: pages -> sentences -> tokens with character spans.

Page marking is an OPEN CHOICE (user decision 5). Accepted today:
  * form-feed  \\f  between pages
  * a line exactly like  --- page N ---  (case-insensitive)
  * neither present -> single page (default)
expected_pages may be supplied by the caller; completed_pages is what was built.
"""
from __future__ import annotations
import re

TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*|\d+(?:\.\d+)?|\.\.\.|…|[^\sA-Za-z\d]")
PAGE_MARK_RE = re.compile(r"^[ \t]*-{3}[ \t]*page[ \t]+(\d+)[ \t]*-{3}[ \t]*$", re.I | re.M)
ABBREV = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "mt", "vs", "etc"}
TERMINATORS = {".", "!", "?", "...", "…"}
CLOSERS = {'"', "”", "’", "'", ")"}
QUOTES_OPEN = {'"', "“"}
QUOTES_CLOSE = {'"', "”"}


def split_pages(text: str):
    """Return (pages, marker_kind). Each page: {page_idx, char_start, char_end, label}."""
    marks = list(PAGE_MARK_RE.finditer(text))
    if marks:
        pages = []
        for i, m in enumerate(marks):
            start = m.end() + (1 if text[m.end():m.end() + 1] == "\n" else 0)
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            pages.append({"page_idx": i, "label": m.group(1), "char_start": start, "char_end": end})
        if text[:marks[0].start()].strip():
            pages.insert(0, {"page_idx": -1, "label": "preamble", "char_start": 0, "char_end": marks[0].start()})
            for i, p in enumerate(pages):
                p["page_idx"] = i
        return pages, "line_marker"
    if "\f" in text:
        pages, pos = [], 0
        for i, chunk in enumerate(text.split("\f")):
            pages.append({"page_idx": i, "label": str(i + 1), "char_start": pos, "char_end": pos + len(chunk)})
            pos += len(chunk) + 1
        return pages, "form_feed"
    return [{"page_idx": 0, "label": "1", "char_start": 0, "char_end": len(text)}], "single_page_default"


def tokenize(text: str, offset: int = 0):
    return [{"text": m.group(), "char_start": m.start() + offset, "char_end": m.end() + offset}
            for m in TOKEN_RE.finditer(text)]


def split_sentences(tokens):
    """Rule splitter: a terminator (plus closing quotes) followed by end-of-text or a
    token starting uppercase/quote ends a sentence, unless the previous token is a
    known abbreviation. Returns lists of token dicts."""
    sents, cur, i = [], [], 0
    while i < len(tokens):
        t = tokens[i]
        cur.append(t)
        if t["text"] in TERMINATORS and not (t["text"] == "." and len(cur) > 1 and cur[-2]["text"].lower() in ABBREV):
            j = i + 1
            while j < len(tokens) and tokens[j]["text"] in CLOSERS and tokens[j]["text"] not in QUOTES_OPEN - QUOTES_CLOSE:
                # closing quote attaches to this sentence only if a quote is open in it
                opens = sum(1 for x in cur if x["text"] in QUOTES_OPEN or x["text"] in QUOTES_CLOSE)
                if opens % 2 == 1 or tokens[j]["text"] in {"”", ")", "’"}:
                    cur.append(tokens[j]); j += 1
                else:
                    break
            nxt = tokens[j] if j < len(tokens) else None
            if nxt is None or nxt["text"][:1].isupper() or nxt["text"] in QUOTES_OPEN or nxt["text"][:1].isdigit():
                sents.append(cur); cur = []
            i = j
            continue
        i += 1
    if cur:
        sents.append(cur)
    return sents


def structure(story: str, expected_pages: int | None = None) -> dict:
    pages, kind = split_pages(story)
    out_pages, sid = [], 0
    for p in pages:
        toks = tokenize(story[p["char_start"]:p["char_end"]], p["char_start"])
        sentences = []
        for k, st in enumerate(split_sentences(toks)):
            cs, ce = st[0]["char_start"], st[-1]["char_end"]
            text = story[cs:ce]
            words = [x["text"] for x in st]
            in_q, dialogue = False, []
            for x in st:
                if x["text"] in QUOTES_OPEN | QUOTES_CLOSE:
                    if not in_q:
                        in_q, qs = True, x["char_start"]
                    else:
                        in_q = False
                        dialogue.append({"char_start": qs, "char_end": x["char_end"], "text": story[qs:x["char_end"]]})
            sentences.append({
                "sent_id": f"p{p['page_idx']}s{k}", "page_idx": p["page_idx"], "sent_idx": k, "global_sent_idx": sid,
                "char_start": cs, "char_end": ce, "text": text,
                "tokens": [dict(x, tok_idx=n) for n, x in enumerate(st)],
                "is_question": words[-1] == "?" or (len(words) > 1 and words[-2] == "?" and words[-1] in CLOSERS),
                "dialogue_spans": dialogue,
            })
            sid += 1
        out_pages.append({**p, "sentences": sentences})
    completed = sum(1 for p in out_pages if p["sentences"])
    return {"page_marker_kind": kind, "expected_pages": expected_pages if expected_pages is not None else len(out_pages),
            "expected_pages_source": "caller" if expected_pages is not None else "derived_from_markers_or_default",
            "completed_pages": completed, "sentence_count": sid, "pages": out_pages}
