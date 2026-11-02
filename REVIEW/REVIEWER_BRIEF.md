# Reviewer brief — NYCH3 TOTE store + tech.ui canonical UI actions

Everything here is a **draft produced by an AI agent (Grok Bot) on 2026-11-02**. Please try to break it. Start with
`REVIEW/LIMITATIONS.md`, then run `bash REVIEW/reproduce.sh` (about 10–15 min, ~3 GB RAM; it writes only under `REVIEW/_run/`).

## What the project is
Instructional text -> T.O.T.E. loops (Test-Operate-Test-Exit). Each loop row has modality operators (🙌 external kinesthetic
operate, 👀 external visual test with superscript verb form, internal senses with a 🧠🗯/💭 marker), actor, action, object,
perspective/location and an exit condition stored as a g8son-style Gate. Rows live in a Kùzu graph (`shared/data/tote.kuzu`,
rebuilt by the script). Every row carries provenance (book: Gutenberg ID + page; web: URL + retrieval date + section/step + quote).

## Claims, and how to verify each
| # | Claim | How to verify |
|---|---|---|
| C1 | The store rebuilds deterministically from public inputs + committed exports | `reproduce.sh` steps "rebuild seed store", "harvest 4 books", "ingest tech.ui", then `store totals == REVIEW/expected_store.json` |
| C2 | Inputs are exactly the ones we used | `sha256sum -c REVIEW/inputs.sha256` (books, gold set, tech.ui export, registries); `REVIEW/MANIFEST.sha256` covers all shipped files |
| C3 | Book harvester vs gold set: sentence verdicts 146/132/22 (correct/partial/wrong), action P 0.938 R 0.679, modality F1 0.979, exit F1 0.900 | `nych3-eval` step; compare `REVIEW/_run/eval.txt`. **Gold is agent-graded** (LIMITATIONS 1) |
| C4 | Phone/PC instructions largely reduce to a small action vocabulary: in 65,929 extracted UI actions from 2,887 help articles, the top 10/25/50/100 canonical actions cover 55.9/79.7/93.1/96.3% (raw verb lemmas: 40.4/58.4/71.6/83.1%); numbered-list steps only: 69.5/86.2/96.8/98.9% | `tech_ui_coverage.py` recomputes from the export; `tech_ui_pipeline/out/coverage.md`, `coverage.png`; mapping rules in `tech_ui_pipeline/config/mapping.json` |
| C5 | tech.ui labels are only ~half right (spot check 21/40 correct, 6 partial, 13 wrong) | `tech_ui_pipeline/out/spotcheck_40.csv` — please regrade it |
| C6 | No tech.ui row is canonical; all are provisional candidates; canonical status needs a named authority | `store_totals.py` -> `tech_ui.non_provisional_rows == 0`; `ToteDB.add_loop` raises without authority; tests `tests/nych3/test_tech_ui.py`, `test_tote_db.py` |
| C7 | Every tech.ui instance cites its source (URL, retrieval date, section/step, <=25-word quote) and no article text is stored | queries Q3–Q4 below; test asserts quote length |
| C8 | Test suite passes | `pytest` step (mg8 compat tests skip without private repos) |

## Sample queries (Kùzu Cypher; `python -c "import kuzu;c=kuzu.Connection(kuzu.Database('REVIEW/_run/tote.kuzu'))..."`)
```cypher
// Q1 canonical UI actions by frequency
MATCH (l:TOTELoop) WHERE l.domain='tech.ui' AND NOT l.loop_id STARTS WITH 'TL-UI-I-' RETURN l.name, l.repeat_count, l.modality_cell ORDER BY l.repeat_count DESC LIMIT 25;
// Q2 a canonical action, its gate, and its most frequent instances
MATCH (g:Gate)-[:GUARDS]->(c:TOTELoop {loop_id:'TL-UI-TOGGLE_ON'})<-[:INSTANCE_OF]-(i:TOTELoop) RETURN g.conditions, i.name, i.repeat_count ORDER BY i.repeat_count DESC LIMIT 10;
// Q3 provenance of one instance
MATCH (i:TOTELoop)-[:SOURCED_FROM]->(s:SourceRef) WHERE i.loop_id STARTS WITH 'TL-UI-I-' RETURN i.name, s.sent_key AS url, s.page AS section_step, s.sentence_text AS quote, s.flags LIMIT 5;
// Q4 longest stored quote (should be <= 25 words + ellipses)
MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'UI:' RETURN max(size(s.sentence_text));
// Q5 book loops with page provenance
MATCH (l:TOTELoop)-[:SOURCED_FROM]->(s:SourceRef) WHERE l.domain='cooking' RETURN l.name, l.modality_cell, s.fallback_gutenberg_id, s.page, s.sentence_text LIMIT 5;
// Q6 cross-domain commonality
MATCH (a:Domain)-[r:DOMAIN_LINK]->(b:Domain) RETURN a.domain_id, b.domain_id, r.shared_loops;
```

## Questions for reviewers
1. Is the coverage curve evidence for "~100 canonical actions" or mostly an artifact of a hand-written mapping with catch-all classes?
   What would a fair null model be (e.g. random merges of verb lemmas to 81 classes)?
2. Should the denominator exclude non-step prose (8 of 13 spot-check errors)? How would you define a "step" operationally?
3. Is merging select/tap/click/choose into TAP_OR_CLICK justified, or should device modality (touch vs pointer) split it?
4. Are per-canonical exit-gate templates (`screen_shows(...)`) acceptable TOTE exits, or must exits be observed per instance?
5. Gold set: which judgment calls in `tests/nych3/gold/README.md` would you reverse? Would you accept agent-graded gold at all?
6. Provenance: is URL + retrieval date + section/step + <=25-word quote sufficient for an auditor, given pages change?
   Should we archive page hashes (we have raw HTML locally but do not ship it)?
7. Is anything claimed in this brief not verifiable from the package? Please list it — we treat that as a defect.
8. Licensing/ToS: is storing <=25-word quotes plus abstracted actions from vendor help centers defensible in your view?

## Package map
`REVIEW/` reproduce.sh, requirements.lock, model.sha256, inputs.sha256, MANIFEST.sha256, expected_*.json, RUNLOG.md, tools/,
tech_ui_pipeline/ (scraper/extractor/mapping/report code + coverage report + spot check). `shared/` code + compact exports.
`tests/` incl. gold set. `stages/` ICM stage docs and schema (`stages/02-schema/output/schema.cypher`).
