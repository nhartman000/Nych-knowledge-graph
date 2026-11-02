# NYCH 3.0 Pro -- CONTEXT (spec summary + glossary)

Source spec: "NYCH Narrative Extraction and Dynamic TOTE Database" handoff (11-step extraction order). Audit: `/workspace/nych3-audit/AUDIT.md`.

## User decisions (authoritative, 2026-11-01)
1. Encoding is deterministic and runs before any LLM. Parsing/coreference is pluggable: rule-based default (offline), spaCy small optional (`--parser spacy|auto`).
2. Storage: Kuzu 0.11.3, in the knowledge-graph schema style (`stages/02-schema/output/schema.cypher`).
3. The .gst stays compatible with mg8-engine's `.gst` (verified with mg8-engine's own loaders and validator in `tests/test_mg8_compat.py`).
4. TOTE loops are harvested from natural language until binding is a lookup. Rows carry provenance and status `candidate | canonical`. No nearest match; explicit `NO_MATCH` fallback.
5. Page marking is UNDECIDED (open choice). Accepted now: form-feed, or a line `--- page N ---`; default single page. `expected_pages` and `completed_pages` are recorded.
6. Questions/dialogue in a story are invariant content, flagged by the encoder, never answered.

## TOTE DB row model (user)
One row = one TOTE loop. Cells: **modality operators** (one cell, every operator: `loved,🫶 ; looking,👀¹`), **actor**, **action**, **tool/object**, **perspective/location**, **exit condition** (a g8son gate that TEST checks; stored in the DB as a `Gate` node linked by `GUARDS`). Each cell is `word,Gestalt` (Gestalt blank until stage 10; protected names show `[protected]`). The DB is partitioned by domain (`IN_DOMAIN`); a loop in more than one domain is a cross-link = **commonality, the 5th dimension** (`ToteDB.commonality()`).

## Modality operators (invariant)
| channel | glyph |
|---|---|
| internal kinesthetic | 🫶 |
| external kinesthetic | 🙌 |
| external visual | 👀 + verb-form superscript |
| internal visual | 👁️ |
| internal auditory | 👂 |
| external auditory | 👂👂 |
| memory | 💭 |
| imagine | 👁️‍🗨️ |
| smell | 👃 |
| taste | 👅 |

Superscripts (external visual only, per user): **¹** progressive/gerund (*looking*), **²** base/infinitive (*to look*), **³** past or past participle (*looked*). **⁴** present finite (*looks*) is a NYCH3 extension -- open question. Emotional connotation belongs in the Gestalt, never the modality.

## Lexical rule
Full words are always kept. Skeleton = remove repeated adjacent letters, then vowels; it is appended at the END of the Gestalt id as a clue (`gst3.mock.ab12cd.strs`), never used as meaning or as a key. Names are protected (never mapped).

## Glossary
- **provenance**: explicit | inferred | predicted | assumed_default (how the system knows). Separate from **channel** (the actor's modality) and from proposition status (narrator_asserted | explicit_dialogue | inferred | predicted).
- **confidence**: `{kind: calibrated|likelihood_class|unavailable}`; classes ordered high > medium > low > latent.
- **perspective level**: 1 = narrator/focal viewpoint; 2 = the in-scene vantage (e.g. `from the hill`).
- **template vs instance**: DB row vs story-bound binding with per-component explicit/inferred status.

## Open choices
See README "Open questions".
