"""Minimal standard-library .xlsx reader: shared and inline strings, sheet chosen by name."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def rows(path: Path, sheet: str | None = None) -> list[list[str]]:
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            for item in ET.fromstring(book.read("xl/sharedStrings.xml")).findall(f"{_NS}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{_NS}t")))
        target = "xl/worksheets/sheet1.xml"
        if sheet is not None:
            wb = ET.fromstring(book.read("xl/workbook.xml"))
            rid = next(s.get(_REL) for s in wb.iter(f"{_NS}sheet") if s.get("name") == sheet)
            rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
            href = next(r.get("Target") for r in rels if r.get("Id") == rid)
            target = "xl/" + href.lstrip("/").removeprefix("xl/")
        root = ET.fromstring(book.read(target))
    out = []
    for row in root.iter(f"{_NS}row"):
        values: list[str] = []
        for cell in row.findall(f"{_NS}c"):
            i = _col(cell.get("r")) if cell.get("r") else len(values)
            while len(values) < i:
                values.append("")
            v = cell.find(f"{_NS}v")
            if cell.get("t") == "s" and v is not None:
                values.append(shared[int(v.text)])
            elif cell.get("t") == "inlineStr":
                values.append("".join(n.text or "" for n in cell.iter(f"{_NS}t")))
            else:
                values.append("" if v is None else v.text or "")
        out.append(values)
    return out
