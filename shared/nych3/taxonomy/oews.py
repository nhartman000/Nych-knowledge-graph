"""BLS OEWS May 2025 national industry-by-occupation estimates -> profession -> industry (WORKS_IN) table.

Source: https://www.bls.gov/oes/special-requests/oesm25in4.zip (public domain; requested as American Milestone Inc,
the BLS-registered identity, per BLS's access policy). Rows kept: detailed occupations (O_GROUP = detailed) at every
industry level in the national files (sector, 3-, 4-, 5- and 6-digit NAICS). TOT_EMP and PCT_TOTAL (the occupation's
share of the industry's employment, %) are kept as published; suppressed values ("**", "#") become empty.
"""
from __future__ import annotations

import gzip
import zipfile
from pathlib import Path

from nych3.taxonomy.xlsx import rows as xlsx_rows

FILES = ("natsector_M2025_dl.xlsx", "nat3d_M2025_dl.xlsx", "nat4d_M2025_dl.xlsx", "nat5d_6d_M2025_dl.xlsx")
DIGITS = {"sector": 2, "3-digit": 3, "4-digit": 4, "5-digit": 5, "6-digit": 6}


def naics_code(code: str, group: str) -> str:
    if "-" in code:
        return code
    return code[:DIGITS[group]] if group in DIGITS else code.rstrip("0")


def _num(v: str):
    try:
        return float(v)
    except ValueError:
        return ""


def convert(zip_path: Path, out: Path, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    stats, n = {}, 0
    with zipfile.ZipFile(zip_path) as z, gzip.open(out, "wt", encoding="utf-8") as f:
        f.write("soc_code\tnaics_code\ti_group\ttot_emp\tpct_total\n")
        for name in FILES:
            member = next(m for m in z.namelist() if m.endswith("/" + name))
            target = workdir / name
            target.write_bytes(z.read(member))
            table = xlsx_rows(target)
            head = table[0]
            col = {k: head.index(k) for k in ("NAICS", "I_GROUP", "OCC_CODE", "O_GROUP", "TOT_EMP", "PCT_TOTAL")}
            kept = 0
            for r in table[1:]:
                if len(r) <= col["PCT_TOTAL"] or r[col["O_GROUP"]] != "detailed":
                    continue
                code = naics_code(r[col["NAICS"]].strip(), r[col["I_GROUP"]].strip())
                f.write(f"{r[col['OCC_CODE']]}\t{code}\t{r[col['I_GROUP']]}\t{_num(r[col['TOT_EMP']])}\t{_num(r[col['PCT_TOTAL']])}\n")
                kept += 1
            stats[name] = kept
            n += kept
            target.unlink()
            del table
    stats["rows"] = n
    return stats
