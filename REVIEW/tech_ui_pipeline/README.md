# nych-ui-actions — do computer/phone instructions reduce to ~100 canonical actions?

Pipeline (all deterministic; spaCy en_core_web_sm):
1. `src/scrape.py` — polite, resumable scraper. UA `NYCH-research-bot/0.1`, robots.txt checked per URL, >=1.5 s/host (DELAY env), 429 backoff, raw HTML cached in `data/raw/<site>/` with `_index.jsonl` (url, file, retrieval date). Sources: Microsoft Support (sitemaps), Claude Help (sitemap), Google Help android/youtube/gemini/chrome (topic->answer link crawl), Apple Support (sitemap; rate-limited us, only 29 pages).
2. `src/extract.py` — candidate lines (ordered/unordered list items, paragraphs) with section heading + step number -> `out/steps_raw.jsonl`.
3. `src/parse.py` — imperative-verb detection (spaCy + lexicon fallback for mis-tagged sentence-initial "Tap"), verb lemma+particle, object span + object type (regex lexicon in file), direction/count/duration modifiers, condition cues, platform hints -> `out/actions.jsonl`.
4. `src/canon.py` + **`config/mapping.json`** (editable, ordered rules: verbs + optional object types/regex; `non_action_verbs` excluded) -> `out/steps_all.csv`, `out/coverage.json`.
5. `src/report.py` -> `out/canonical_actions.json` (per action: count, platform split, top verbs/objects, 3 cited quotes (<=25 source tokens + `…` markers when truncated) with URL+retrieval date+section/step, NYCH TOTE template 🙌 operate / 👀² verify / g8son exit gate), `out/coverage.md`, `out/coverage.png`, spot-check sample.

Run: `python3 -m venv .venv && .venv/bin/pip install spacy requests beautifulsoup4 lxml matplotlib && .venv/bin/python -m spacy download en_core_web_sm`, then `./run_all.sh scrape` (resume scraping) or `./run_all.sh` (rebuild outputs from cache). After editing mapping.json only: `.venv/bin/python src/canon.py && .venv/bin/python src/report.py`.

Spot check: `out/spotcheck_40.csv` (agent-graded, pending human review).

`src/export_unmapped.py` (added in review r2) writes the 2,442 UNMAPPED records in the same compact format; shipped as `shared/data/tech_ui/ui_actions_unmapped.jsonl.gz`.
