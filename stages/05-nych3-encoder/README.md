# NYCH 3.0 Pro (first working version, 3.0.0-pre1)

A fresh rebuild of the NYCH narrative encoder. Deterministic stages 01-09 run before any LLM and produce an mg8-engine-compatible `.gst` plus a `.bonit`. Not a retrofit of `nhartman000/nych`. Merged into nhartman000/knowledge-graph (stage 05); the KG store is the shared store.

Start with `CLAUDE.md` (routing) and `CONTEXT.md` (spec summary, user decisions, row model, modality table).

## Quick start
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   (repo root)
python -m nych3.store.tote_db       # build the seed TOTE DB (shared/data/tote.kuzu)
nych3 encode --prompt "Encode this story with NYCH." --story tests/nych3/golden/peter/story.txt --name peter
python stages/05-nych3-encoder/10_gestalt_llm/run.py stages/05-nych3-encoder/09_gst_pretext/output/peter.gst      # mock provider + validators (GATE 10 pending)
python stages/05-nych3-encoder/11_paths/run.py stages/05-nych3-encoder/09_gst_pretext/output/peter.gst            # ordered likelihood classes, trace.jsonl
pytest -q
```
Optional: `pip install spacy && python -m spacy download en_core_web_sm`, then `--parser spacy` (or `auto`).
mg8 compatibility tests need mg8-engine importable: `pip install --no-deps -e <mg8-engine>` plus its pinned deps `nych@57b81e9` and `TCTA@f2882c1` (installed with `--no-deps`). Without it, `tests/test_mg8_compat.py` is skipped and does not fail.

## Layout (ICM)
`_config/` (nych3.bonit, schema_versions.yaml, registries/) · `shared/nych3/` (library) · `stages/02-schema/output/schema.cypher` · `shared/data/tote_seed.json` · `01_boot` … `12_mg8_handoff` (each with CONTEXT.md; `run.py` for 01-11; GATE.md at 10 and 11) · `tests/nych3/`.

## Status
| Stage | State |
|---|---|
| 01-09 | Working, deterministic, with no LLM or network imports (contract test) |
| 10 | Contract, validators (NYCH3 rules plus mg8-engine's `validate_mapping_plan`), and Kuzu persistence behind GATE 10. **Provider is a stub (`MockProvider`).** |
| 11 | Ordered likelihood classes, latent/expanded alternatives, pruned list, and trace.jsonl. **The Bayesian formula is not evaluated, because there are no sourced priors.** |
| 12 | CONTEXT.md only. The mg8 unit assembly is exercised in tests, not shipped as a stage. |

## TOTE harvester
See `HARVEST.md`. It is a resumable batch extraction of candidate TOTE rows from public-domain instructional books, with ISBN + page provenance.

## Open questions
1. **Page marking** (user decision 5, undecided): form-feed or `--- page N ---` lines are accepted, and the default is a single page. Is a JSON page list, or an explicit `expected_pages` from the prompt, preferred?
2. **Superscript ⁴** for present finite (*looks*) is a NYCH3 extension to the user's ¹/²/³ table. Should superscripts also apply to channels other than 👀?
3. **"perspective 2"**: implemented as level 1 = narrator/focal viewpoint and level 2 = in-scene vantage (`from the hill`). Please confirm.
4. **Canonical authority**: the seed star-looking loop is `canonical` on the authority of the user's golden case. Hill-approach is `candidate`. Who may promote harvested candidates?
5. **Commonality seed**: TL-LOOK-AT-STARS-001 is cross-linked to `astronomy.observation` as an illustrative 5th-dimension example. Keep it or drop it?
6. The other four axes of the 5D DB are still undefined (audit OQ1). Only domain partition and commonality are modelled.
7. mg8-engine's `build_mapping_prompt` still prints a `PRUNING` header from its own template, which is empty here because NYCH3 emits no pruning. Consider removing it upstream in mg8-engine.
8. Coreference does not assume gender from the name. `he`/`his` link only when exactly one compatible person exists. Otherwise they stay unresolved with alternatives.
9. Real Gestalt provider (model, on-device or not) for stage 10.
