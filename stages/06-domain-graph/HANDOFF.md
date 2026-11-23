# Stage 06 handoff: domain knowledge graph (for a new chat)

Written 2026-11-23 by Claude Opus 5.5. It describes the state of branch `stage-06-domain-graph` at commit `1dcda2f`.

## 0. Before anything else
- **Where the code is:** a local clone of the private repo `nhartman000/Nych-knowledge-graph`, branch `stage-06-domain-graph`. It has 6 commits that are **not on GitHub**. The agent's push was blocked by the auto-mode safety check, so the owner has to push it themselves:
  `git push -u origin stage-06-domain-graph`
  Until that happens, this work exists only on this machine. The clone sits inside a temporary session folder, and deleting that Claude session deletes the folder.
- **Setup:** read `CLAUDE.md`, then `CONTEXT.md`, then `stages/06-domain-graph/CONTEXT.md`.

## 1. Owner rules (verbatim where quoted; these override defaults)
- "no invented values, no approvals unless you say 'approved'". Never set any `GATE.md` to approved yourself. Stage 02 (schema additions) and stage 06 are both `PENDING`.
- "no more google cloud until they approve my credits" (2026-11-23). Earlier rule: "ddont run locally run on your machine" for heavy compute. With the cloud paused, heavy runs wait. Light local runs go under a memory cap: `systemd-run --user --scope -q -p MemoryMax=4G ...`.
- Record owner statements verbatim, in commit messages or `CONTEXT.md`.
- NYCH results are pushed and merged as they arrive (the owner does the push, see §0).
- CLAUDE.md rules:
  - Stages are deterministic, with no LLM.
  - Never force a nearest TOTE match.
  - DDL lives only in `stages/02-schema/output/schema.cypher`.
- Every rule that is the agent's interpretation and not the owner's is labelled R1–R8 in code, and must stay labelled.
- Don't put personal emails or BLS registration details in the repo.

## 2. Owner's intent (verbatim, 2026-11-23)
- "I need to build a private knowledge graph that handles the domain subdomain function technique tote loop that can connect to the tote loop database. it should be the extensive word associations between professions domains and vernaculars"
- "top top top level domains are university areas of study like liberal arts medical law science math government military sports religion etc.."
- "this has to mergwe into the nych knowledge graph and serve as the ultimate tool for the model to do its shortcutting"
- Approvals given today:
  - "yes add plurals" (R6)
  - "yes do A and B" (most-specific links; profession words to home industries)
  - "use the other words it works for humans" (R8, sense from context)

## 3. What exists
| Piece | File |
|---|---|
| Schema additions (StudyArea, Profession, WorkFunction, Technique, Task, Term, SubjectTLD, and the rels) | `stages/02-schema/output/schema.cypher` |
| Builder: NAICS 2022, CIP 2020, CIP→SOC, O\*NET 30.3, D4 vocabulary/glossary, BLS OEWS May 2025 | `shared/nych3/taxonomy/build.py` |
| Lookup ("shortcut"): text → ranked study areas, sectors, subsectors, industry groups, industries, professions, techniques, TOTE loops, competency | `shared/nych3/taxonomy/resolve.py` |
| CLI: `fetch`, `build`, `resolve` | `shared/nych3/taxonomy/cli.py` |
| Pinned inputs (SHA-256) | `_config/registries/taxonomy_sources.json`, data in `shared/data/taxonomy/` |
| Unit tests (10, all pass) | `tests/nych3/test_taxonomy.py` |
| Cross-field eval: 53 sentences, scorer, results | `stages/06-domain-graph/eval/` |

Last full build: 2,125 Domain, 2,499 StudyArea, 1,016 Profession, 18,796 Task, 110,589 Term, 235,259 TERM_DOMAIN, 170,747 TERM_PROFESSION, 88,625 WORKS_IN. TASK_LOOP is 0, because a fresh store has only the 3 seed loops.

### Commands (run from repo root)
```bash
# unit tests (seconds)
systemd-run --user --scope -q -p MemoryMax=4G uv run -q --python 3.12 --with kuzu==0.11.3 --with pytest --with wordfreq==3.1.1 -m pytest -q tests/nych3/test_taxonomy.py
# full build (~9 min, ~2 GB RAM; run in background). DB is a run artifact, keep it outside the repo
PYTHONPATH=shared systemd-run --user --scope -q -p MemoryMax=4G uv run -q --python 3.12 --with kuzu==0.11.3 --with wordfreq==3.1.1 --with spacy==3.8.7 --with en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl python -m nych3.taxonomy.cli build --db /path/outside/repo/kg.kuzu
# eval (seconds, needs a built DB)
PYTHONPATH=shared systemd-run --user --scope -q -p MemoryMax=4G uv run -q --python 3.12 --with kuzu==0.11.3 --with wordfreq==3.1.1 python stages/06-domain-graph/eval/run_eval.py --db /path/outside/repo/kg.kuzu
```
Kùzu needs Python 3.12, which is why the commands use `uv run --python 3.12`. Builds need `shared/data/taxonomy/` populated: `cli fetch` downloads the public inputs, and the BLS zip `oesm25in4.zip` is already there. That zip is gitignored, and the derived TSV is committed.

## 4. Baseline score (2026-11-23, `eval/results.json`)
| Metric | Score |
|---|---|
| sector@1 | 32/53 |
| sector@3 | 46/53 |
| CIP family@1 | 32/53 |
| CIP family@3 | 44/53 |
| unresolved | 0 |

The expected labels in `eval/sentences.tsv` were written by Claude and have **not been reviewed by the owner**. Some misses are arguably label problems, for example electrical expecting CIP 46 when it got 47 then 46. Don't tune to the labels: when one looks wrong, say so.

## 5. Diagnosed problems, in priority order (the work for this chat)
1. **Government is invisible.** BLS OEWS puts public employment under OEWS-only codes `99`, `999`, `9991`/`9992`/`9993` (federal / state / local). These are not NAICS 2022, so the builder skips them (`oews_industry_codes_not_in_naics_2022: 21`). Result: 0 WORKS_IN links into NAICS 92 Public Administration, and only 1,661 term links reach 92. The police, military, firefighting and government sentences all miss their sector.
   *Task:* propose how to represent them. For example, add OEWS government Domain nodes (`kind = "oews"`) under a parent, or link them to NAICS 92. Write the options in `stages/06-domain-graph/CONTEXT.md` under "Open (owner)". **Don't pick one and present it as settled.** The owner decides.
2. **Hub sectors soak up evidence.** Educational Services (611x has 16,242 term links), Professional/Scientific/Technical (54) and Health Care show up in the top 3 for unrelated sentences. Likely cause, not yet verified: rule B sends each profession's words to its home industry. Postsecondary teachers (SOC 25-1xxx) bring the vocabulary of their subject (agriculture, physics, law…) to colleges (6113), and consultants do the same to 5416.
   *Task:* measure it. Count how many TERM_DOMAIN links into 611/5416 come from which SOC groups (the link `source` field names the profession). Then propose a rule, for example excluding 25-1xxx from B, and show its eval effect. Label it as an interpretation until the owner approves.
3. **Ties at sector level.** R2 ranks by number of distinct supporting words first, so sectors often tie at 3–4 words and the order is decided by summed evidence. Inspect a few eval misses to see whether they are ties. Report this; don't change R2 without the owner.
4. **Thin profession vocabulary.** Lawyers is not linked to "plaintiff" or "summary judgment"; O\*NET lawyer tasks don't use those words, but Judges' tasks do. A possible source is O\*NET's other files in the same zip (e.g. Alternate Titles, Technology Skills, DWAs). List the candidates with their licence (O\*NET is CC BY 4.0) and propose; don't add sources without approval.
5. **TOTE loops.** The link code (exact action+object lemma, never nearest) is in place but has only been exercised against 3 seed loops. Connecting to the real TOTE loop database is open. Ask the owner where it is.

**Done looks like:** for items 1–2, a short write-up in `CONTEXT.md` "Open (owner)" with measured numbers and the eval delta of each proposal (run on a copy, not committed as the default until approved), plus a commit. Keep unit tests passing. Rebuilds take about 9 minutes, so batch your changes.

## 6. Interpretation rules currently in code (all need owner review)
- **R1:** each word's evidence is split evenly over its links.
- **R2:** rank by the number of distinct supporting words, then by summed evidence.
- **R3:** competency = the vocabulary tier (expert/novice) with the largest share.
- **R4:** ties at the cut are kept.
- **R5:** single words with everyday Zipf ≥ 5.0 are ignored.
- **R6:** plural endings tried: -ies, -es, -s.
- **R7:** profession words go to the 4-digit industries holding ≥ 10% of the profession's employment.
- **R8:** word sense is chosen from the other words at subsector level; a word is set aside as off-context when ≥ 2 other words agree on a field and it agrees with none.
- **Fixed rules (approved D4):** NAICS 2022 + O\*NET 30.3 base; Zipf bands from van Heuven et al. (2014), < 3 expert, ≥ 4 novice; tiers by wordfreq 3.1.1.
