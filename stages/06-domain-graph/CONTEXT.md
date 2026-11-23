# Stage 06 — domain graph (where does this text belong, and who talks like this?)

Owner, 2026-11-23, verbatim:
- "I need to build a private knowledge graph that handles the domain subdomain function technique tote loop that can connect to the tote loop database. it should be the extensive word associations between professions domains and vernaculars"
- "top top top level domains are university areas of study like liberal arts medical law science math government military sports religion etc.."
- "this has to mergwe into the nych knowledge graph and serve as the ultimate tool for the model to do its shortcutting"

## What it adds to the shared store
| Level | Node | Source | Count |
|---|---|---|---|
| Area of study | `StudyArea` (family > series > program) | NCES CIP 2020 | 2,499 |
| Domain / subdomain | `Domain` kind=`naics` (sector > … > industry) | NAICS 2022 | 2,125 |
| Profession | `Profession` | O*NET 30.3 occupations | 1,016 |
| Function | `WorkFunction` GWA > IWA | O*NET work activities | 41 + 332 |
| Technique | `Technique` | O*NET detailed work activities | 2,087 |
| Task | `Task` (+ action/object lemma, spaCy) | O*NET task statements | 18,796 |
| TOTE loop | existing `TOTELoop` via `TASK_LOOP` | exact action/object lemma only, never nearest | depends on the store's loops |
| Vernacular | `Term` (tier expert/intermediate/novice) | D4 vocabulary v1 + glossary layer (mg8-model-builder PR #63, #64) | 88,158 |
| Web-domain endings | `SubjectTLD` | D4 TLD layer (approved 2026-11-19) | 345 |

Edges: `STUDY_PARENT`, `DOMAIN_PARENT`, `FUNCTION_PARENT`, `TECHNIQUE_OF` (child → parent); `STUDY_LEADS_TO` (CIP→profession, NCES CIP–SOC crosswalk, 8,324); `PERFORMS`, `TASK_TECHNIQUE` (23,850), `TASK_LOOP`; `TERM_DOMAIN` (109,053), `TERM_PROFESSION` (58,800); `TLD_OF`; `WORKS_IN` (profession → industry) once the BLS National Employment Matrix is supplied.

Tiers come from everyday-English Zipf frequency (wordfreq 3.1.1; data CC BY-SA 4.0, Robyn Speer et al.) in the van Heuven et al. (2014) bands: < 3 expert, 3–4 intermediate, ≥ 4 novice.

## Run
```
export PYTHONPATH=shared
python -m nych3.taxonomy.cli fetch            # public inputs, SHA-256 pinned in _config/registries/taxonomy_sources.json
python -m nych3.taxonomy.cli build            # into shared/data/tote.kuzu (or --db PATH); ~4 min, spaCy for task lemmas
python -m nych3.taxonomy.cli resolve "The plaintiff moved for summary judgment."
```
`resolve` is the shortcut for the model: ranked areas of study, sectors, subsectors, industries, professions, techniques and TOTE loops, plus a competency estimate (share of expert / intermediate / novice terms). Rules R1–R5 are in `shared/nych3/taxonomy/resolve.py`; R5 (ignore single words with Zipf ≥ 5.0) is a proposal.

## Open (owner)
1. Gate approval of the schema additions (stage 02) and of this stage.
2. Plural "s": D4's approved suffix rule covers ing/ion/ed/er only, so "dentist" does not match "dentists". Allow plurals in `resolve`?
3. BLS National Employment Matrix: bls.gov refuses scripted downloads (HTTP 403). Download it in a browser to `shared/data/taxonomy/bls-national-employment-matrix.xlsx` to add `WORKS_IN`.
4. Science vocabulary is thin (e.g. "supramolecular" is absent): journal / OpenAlex terms are the next layer.
5. The existing informal loop domains (`cooking`, `craft.knitting`, …) are not yet mapped to NAICS or CIP nodes.

## Attribution
This product includes information from the O*NET 30.3 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. USDOL/ETA has not approved, endorsed, or tested these modifications. NAICS (US Census Bureau) and CIP 2020 / CIP-SOC crosswalk (NCES) are US government works. Word frequencies: wordfreq (Robyn Speer et al.), data CC BY-SA 4.0.
