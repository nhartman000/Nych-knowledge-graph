"""Polite fetch + HTML -> paragraphs with page numbers.
Printed page when the Gutenberg HTML marks it (span.pagenum / span.pageno), otherwise a
DERIVED page (char offset / 2000, flagged). Gutenberg boilerplate outside
*** START/END OF THE PROJECT GUTENBERG EBOOK *** is dropped."""
from __future__ import annotations
import html, re, time, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from ..config import SHARED, registry

CORPUS = SHARED / "data" / "corpus"
_last = [0.0]
DERIVED_CHARS = 2000


def sources():
    return registry("harvest_sources")


def fetch(book: dict, cache: Path = CORPUS) -> str:
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"{book['gutenberg_id']}.html"
    if f.exists():
        return f.read_text(encoding="utf-8", errors="replace")
    pol = sources()["politeness"]
    wait = pol["min_seconds_between_requests"] - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(book["url"], headers={"User-Agent": pol["user_agent"]})
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec: public-domain text, cached once
        data = r.read().decode("utf-8", errors="replace")
    _last[0] = time.time()
    f.write_text(data, encoding="utf-8")
    return data


class _P(HTMLParser):
    BLOCK = {"p", "li", "dd", "td", "h1", "h2", "h3", "h4", "blockquote", "div"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras, self.buf, self.page, self.in_pn, self.pn_buf = [], [], None, 0, []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if self.in_pn:
            self.in_pn += 1; return
        if tag == "span" and ("pagenum" in cls.split() or "pageno" in cls.split()):
            self.in_pn = 1; self.pn_buf = []; return
        if tag in ("style", "script"):
            self.skip += 1
        if tag in self.BLOCK:
            self.flush()
        if tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if self.in_pn:
            self.in_pn -= 1
            if self.in_pn == 0:
                txt = re.sub(r"[\[\]\s]|Pg", "", "".join(self.pn_buf))
                if txt:
                    self.page = txt
            return
        if tag in ("style", "script"):
            self.skip -= 1
        if tag in self.BLOCK:
            self.flush()

    def handle_data(self, d):
        if self.in_pn:
            self.pn_buf.append(d)
        elif not self.skip:
            self.buf.append(d)

    def flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t:
            self.paras.append((t, self.page))
        self.buf = []


def paragraphs(raw_html: str, book: dict):
    """-> list of {para_idx, text, page, page_kind, page_method}. Deterministic for a given cached file."""
    m1 = re.search(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG", raw_html)
    m2 = re.search(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", raw_html)
    body = raw_html[raw_html.find(">", m1.end()) + 1 if m1 else 0: m2.start() if m2 else len(raw_html)]
    p = _P(); p.feed(body); p.flush()
    out, off = [], 0
    printed = book.get("page_mode") == "printed"
    for i, (t, pg) in enumerate(p.paras):
        if printed and pg is not None:
            page, kind, meth = pg, "printed", f"Gutenberg HTML {book.get('page_marker')} marker preceding the paragraph"
        else:
            page, kind, meth = str(off // DERIVED_CHARS + 1), "derived", f"floor(char_offset/{DERIVED_CHARS})+1 over extracted body text"
        out.append({"para_idx": i, "text": html.unescape(t), "page": page, "page_kind": kind, "page_method": meth})
        off += len(t) + 1
    return out
