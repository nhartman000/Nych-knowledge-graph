#!/usr/bin/env python3
"""Rebuild the extra procedure sources from their public web pages (one-time provenance script; not run in tests).

Each output file uses the layout load_source() expects: a header ending in a 'Change notice:' line, then one
sentence, list item or command per line. Text is taken verbatim (whitespace collapsed, split into sentences; code
blocks become '$ ' lines). Requires: requests-free curl access and beautifulsoup4.
"""
import re
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parents[1] / "sources"
PG = ("PostgreSQL License; https://www.postgresql.org/about/licence/", "The PostgreSQL Global Development Group")
PSF = ("Python Software Foundation License (documentation); https://docs.python.org/3/license.html", "Python Software Foundation")
GOV = ("US federal government work, free of copyright per FEMA website information (https://www.fema.gov/about/website-information)", "FEMA / US Department of Homeland Security")

SOURCES = [
    # name, url, css root, (first_line_contains, last_line_contains), (rights, publisher)
    ("pg_upgrade", "https://www.postgresql.org/docs/18/pgupgrade.html", "#docContent", ("Usage", "Notes"), PG),
    ("pg_continuous_archiving", "https://www.postgresql.org/docs/18/continuous-archiving.html", "#docContent", (None, None), PG),
    ("pg_sql_dump", "https://www.postgresql.org/docs/18/backup-dump.html", "#docContent", (None, None), PG),
    ("python_venv", "https://docs.python.org/3/tutorial/venv.html", "div[role=main]", (None, None), PSF),
    ("ready_power_outages", "https://www.ready.gov/power-outages", None, ("How to Protect Yourself During", "Associated Content"), GOV),
    ("ready_floods", "https://www.ready.gov/floods", None, ("If you are under a flood warning", "Additional Resources"), GOV),
    ("ready_home_fires", "https://www.ready.gov/home-fires", None, ("Before a Fire", "Prevent Home Fires"), GOV),
]


def fetch(url):
    return subprocess.run(["curl", "-s", "-L", "--max-time", "40", "-A", "Mozilla/5.0", url],
                          capture_output=True, check=True).stdout.decode("utf-8", "ignore")


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text) if s.strip()]


def extract(html, root_sel, window):
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(root_sel) if root_sel else (soup.find("main") or soup.body)
    for t in root.select("script,style,nav,footer,.navheader,.navfooter,figure"):
        t.decompose()
    items = []
    for el in root.find_all(["h2", "h3", "p", "li", "pre"]):
        if el.name == "p" and el.find_parent("li"):
            continue  # captured through the <li>
        if el.name == "li":
            clone = BeautifulSoup(str(el), "html.parser")
            for nested in clone.find_all(["ul", "ol", "pre"]):
                nested.decompose()
            raw = clone.get_text(" ")
        elif el.name == "pre":
            raw = el.get_text()
        else:
            raw = el.get_text(" ")
        if el.name == "pre":
            text = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in raw.splitlines() if l.strip())
        else:
            text = re.sub(r"\s+", " ", raw).strip()
            text = re.sub(r"\s+([.,;:)])", r"\1", text)
        if not text:
            continue
        if el.name == "pre":
            items.append(("cmd", text))
        elif el.name in ("h2", "h3"):
            items.append(("head", text))
        elif len(text) >= 25 or text.endswith("."):
            items.append(("text", text))
    first, last = window
    if first:
        idx = next((i for i, (k, t) in enumerate(items) if k == "head" and first.lower() in t.lower()), 0)
        items = items[idx:]
    if last:
        idx = next((i for i, (k, t) in enumerate(items) if k == "head" and last.lower() in t.lower() and i > 0), len(items))
        items = items[:idx]
    lines = []
    for kind, text in items:
        if kind == "head":
            continue
        if kind == "cmd":
            lines.extend("$ " + l.strip() for l in text.splitlines() if l.strip())
        else:
            lines.extend(sentences(text))
    seen, out = set(), []
    for l in lines:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def main(only=None):
    for name, url, sel, window, (rights, publisher) in SOURCES:
        if only and name not in only:
            continue
        lines = extract(fetch(url), sel, window)[:90]
        header = [
            "PUBLIC PROCEDURE EXCERPT - NOT A COMPLETE DOCUMENT",
            name.replace("_", " "),
            url,
            f"Publisher: {publisher}",
            f"Rights: {rights}",
            "Change notice: text extracted from the web page on 2026-11-19, whitespace collapsed, split one sentence/item "
            "per line, headings and navigation removed; first 90 lines at most.",
        ]
        (OUT / f"{name}.txt").write_text("\n".join(header + lines) + "\n", encoding="utf-8")
        print(name, len(lines), "lines")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
