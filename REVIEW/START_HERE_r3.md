# START HERE — review revision r3 (2026-11-03, evening ET)

Branch: `nych3-integration` of https://github.com/nhartman000/knowledge-graph. Everything here is an AI-agent (Grok Bot) draft. Please try to break it.
Read in order: this file → `LIMITATIONS.md` → `REVIEWER_BRIEF.md` (claims C1–C10 and how to check each) → `RESPONSE_TO_REVIEW.md` (r2 answers).

## Reproduce (exact commands)
```bash
git clone -b nych3-integration https://github.com/nhartman000/knowledge-graph.git && cd knowledge-graph
bash REVIEW/reproduce.sh          # ~15 min, ~3 GB RAM, Python 3.13; writes only under REVIEW/_run/
# or with an interpreter that already has REVIEW/requirements.lock installed:
PY=/path/to/python bash REVIEW/reproduce.sh
# individual checks
PYTHONPATH=shared python -m pytest tests -q          # 189 tests
PYTHONPATH=shared python tools/core_tote/validate.py   # core TOTE loop validator; expects "0 errors"
sha256sum -c REVIEW/inputs.sha256 && sha256sum -c REVIEW/MANIFEST.sha256
```
Expected: the last line of `REVIEW/_run/reproduce.log` reads `overall: ALL PASS`.

## New since r2 (2026-11-03)
- **Core TOTE loops — commit `bb83f89`.** 88 CANONICAL-CANDIDATE loops for basic software / AI-tool functions (open, create folder, delete, copy, paste, upload, ...), each grounded in ≥2 sources in two passes; a 4-operator ↔ 10-operator mapping. Files: `shared/data/tech_ui/core_tote/` (`core_loops.json`, `candidates.json`, `verify_report.json`, `OPERATOR_MAPPING.md`, `README.md`), code `tools/core_tote/`, tests `tests/nych3/test_core_tote.py`.
- **Four-part NYCH TOTE rule — commit `93fefd0`.** Senses are input or sub-action and never count as the action itself (resolves GAP-4); `tool_or_object` is filled on all 88 core loops; tests added.
- **Harvest of help/how-to pages (end of day).** Job A (tech.ui vendor help) export grew to 150,052 extracted UI actions (144,655 mapped to the 81 classes, 5,397 unmapped). Job B (how-to sites) is 6,990 pages fetched, 6,862 used, 41,062 actions. Raw pages are **not** shipped; only compact exports with ≤25-token quotes plus URLs. Final build drops lines that repeat across ≥max(5, 3%) of a site's pages (site chrome/promos); "make sure …" is now an internal-sense step. Commit `102d296`.
- `expected_store.json`, `inputs.sha256` and `MANIFEST.sha256` were regenerated for the r3 data. The r2 values (36,445 tech.ui instances, 65,929 denominator) are superseded.

## Known limitations (read before judging any number)
1. **All loops are provisional and not human-verified.** That includes the 88 core loops ("canonical-candidate" means proposed, not approved) and every harvested tech.ui/how-to instance. No row is canonical without authority metadata (C6).
2. **The 86% figure is self-graded.** The agent graded its own output. The same applies to the gold set behind C3 (agreement bias). Blinded human annotation is still pending.
3. **No runtime executor yet.** Loops are data. Nothing here runs a TOTE loop against a real UI, so "coverage" means a share of extracted text, not executable coverage.
4. **Open question: the multi-action gate.** We have not decided how one Gate should guard a step that contains several actions. Reviewer input is welcome.
5. Harvest-scale caveats: locator quality varies (see C7). Some sources were blocked or rate-limited; see the harvest tally in `RUNLOG.md`.
