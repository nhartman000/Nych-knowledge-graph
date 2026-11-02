# LIMITATIONS (candid) — state as of 2026-11-02 (ET)

Read this before quoting any number from this repo.

## Evaluation status
1. **Gold set is agent-graded, not human-graded.** `tests/nych3/gold/gold_v1.jsonl` (300 sentences, 4 domains) was written by the
   agent (Grok Bot) with the extractor's draft visible. It is a reviewed first draft, *pending human review*; agreement bias toward the
   extractor is likely. No inter-annotator agreement exists. nych3-eval numbers (e.g. action F1 0.788, sentence-level 146/132/22
   correct/partial/wrong) measure agreement with that draft, not ground truth.
2. **tech.ui spot check is small and agent-graded**: 40 random actions, 21 correct / 6 partial / 13 wrong (52.5% correct, 67.5% incl.
   partial). 95% CI on 52.5% with n=40 is roughly ±15 points. `REVIEW/tech_ui_pipeline/out/spotcheck_40.csv`.
3. Spot-check errors are dominated by *non-step prose admitted as steps* (8/13 wrong): descriptive feature text, cross-references
   ("see X"), policy text. The coverage denominator therefore contains noise; we have not measured how that biases the curve.

## tech.ui (canonical UI actions) — PROVISIONAL / UNREVIEWED
4. **All tech.ui rows are `status=candidate`, `epistemic_status=PROVISIONAL`, `review_status=provisional_unreviewed`.** None is canonical;
   promotion requires a named human authority (enforced in `ToteDB.add_loop/promote`).
5. **The 81 canonical actions are a hand-written mapping** (`tech_ui_pipeline/config/mapping.json`, ordered rules), not learned clusters.
   The coverage curve is therefore partly a property of the mapping we chose. Several classes are vague catch-alls
   (USE_FEATURE, CREATE_ITEM, SET_VALUE, FOLLOW_PROMPTS). TAP_OR_CLICK deliberately merges select/tap/click/choose on UI controls.
6. **Coverage tops out at 96.3% because only 81 classes exist**; N=100 and N=150 are identical. 3.7% of actions (2,442) are
   UNMAPPED long-tail verbs (~1,300 distinct) and are NOT ingested. 3,797 actions with listed "non-action" verbs
   (help, discuss, suggest, ...) were excluded from the denominator by a hand list (`non_action_verbs`).
7. **Source skew**: Microsoft Support = 1,500 of 2,887 articles and 51% of actions. Apple Support rate-limited our polite bot (HTTP 429
   even at 5 s/request): only 29 articles. Mozilla SUMO served a bot challenge: skipped (its GitHub repo has 32 files only).
   OpenAI and Patreon help are fetcher-blocked; Facebook/Craigslist/eBay forbid crawling: not used. ~20 pages returned 403/timeouts.
8. Raw HTML (1.8+ GB) is NOT in the repo or the zip; reproduction of the tech.ui *scrape* depends on live pages that change.
   What is reproducible offline is everything downstream of the compact export (`shared/data/tech_ui/`, SHA256 in `inputs.sha256`).
9. Object types come from a regex lexicon; platform comes from the site plus keyword hints; modifiers (direction/count/duration) and
   condition cues are regex. Exit gates for tech.ui are per-canonical *templates* (e.g. `screen_shows(Settings)`), not per-instance
   observations. Instances are deduped by (canonical, verb, normalized object); each occurrence keeps its own SourceRef.
10. Quotes are <=25-word excerpts for citation; no article text is stored. Platform help-center ToS were checked only at robots.txt level
    plus a skim; the use is observation/abstraction of individual actions, but this is not legal advice.

## Book harvester (cooking / woodworking / knitting / ropework)
11. Only 4 public-domain books (Project Gutenberg 13510, 26113, 65061, 71855). ISBNs do not exist (pre-1970): provenance is Gutenberg ID +
    printed page (or derived page, flagged). Results do not generalize beyond these books' register.
12. Action recall is the weak point (0.679 vs gold): bare verbs without object are dropped by design (`missed_loop:bare_verb` = 44),
    plus 142 other missed loops. Location precision is low (0.549).
13. **Secondary pass not built**: no LLM/second-stage review of candidates; no automatic promotion (by design).
14. **0 Gestalts on harvested rows**: Gestalt cells are blank until stage 10 (`10_gestalt_llm`), which has not been run on the harvest.
    The Gestalt table holds only the legacy POC set.
15. Superscript ⁴ (present finite, 👀⁴) is a NYCH3 extension still marked "open question" in stages/05-nych3-encoder/CONTEXT.md.

## Known bugs / rough edges
16. tech.ui parse: "select and hold" can be labelled SELECT_ITEM instead of LONG_PRESS; "deselect" is unmapped; a button named
    "Ask Facilitator" was read as PROMPT_AI; menu labels like "Privacy, search, and services" can yield a SEARCH action.
17. spaCy en_core_web_sm mis-tags sentence-initial "Tap"/"Select" as nouns; a lexicon fallback compensates, which can over-trigger on
    headings that start with a verb-like word.
18. tech.ui ingest was OOM-killed on a 15.6 GB box: memory grew ~0.45 GB per 1,000 instance loops on one long-lived Kuzu
    connection. Fixed by reopening the connection after every 500-loop transaction and a 2 GiB buffer pool
    (`NYCH3_KUZU_BUFFER_POOL`); `--replace` deletes in 5,000-row batches. Root cause inside Kuzu 0.11.3 not investigated.
19. mg8-engine compatibility tests skip without the private repos in requirements-mg8.txt.
20. Agent-run: the whole pipeline, mapping, gold set and spot checks were produced by an AI agent in one day; treat all as draft.
