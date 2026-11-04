# LIMITATIONS (candid) — state as of 2026-11-03 (ET), revision r2 (see RESPONSE_TO_REVIEW.md)

Read this before quoting any number from this repo.

## Evaluation status
1. **Gold set is agent-graded, not human-graded.** `tests/nych3/gold/gold_v1.jsonl` (300 sentences, 4 domains) was written by the
   agent (Grok Bot) with the extractor's draft visible. It is a reviewed first draft, *pending human review*; agreement bias toward the
   extractor is likely (agreement bias). **Blinded human annotation is still pending.** No inter-annotator agreement exists.
   nych3-eval numbers (e.g. action F1 0.788, sentence-level 146/132/22 correct/partial/wrong) measure agreement with that draft,
   not ground truth. The historical gold set is left untouched in r2.
1a. **Per-field scores: conditional vs end-to-end.** The originally published per-field numbers (modality F1 0.979, exit 0.900,
   objects 0.856, locations 0.642, amount 0.870, actor 1.000) are *conditional (action-matched)*: computed only on gold/pred loop
   pairs whose action lemma matched (301 of 443 gold loops, 301 of 321 predicted). In r2 the metric definition was **extended,
   not replaced**: `fields_end_to_end` counts every unmatched gold loop (recall) and predicted loop (precision) against each field:
   objects F1 0.733, locations 0.566, modality 0.771, exit_tier/exit 0.709, amount 0.676, actor 0.788. Quote the end-to-end
   numbers for pipeline quality; the conditional ones only describe field quality *given* a correctly detected action.
2. **tech.ui spot check is small and agent-graded**: 40 random actions, 21 correct / 6 partial / 13 wrong (52.5% correct, 67.5% incl.
   partial). 95% CI on 52.5% with n=40 is roughly ±15 points. `REVIEW/tech_ui_pipeline/out/spotcheck_40.csv`.
3. Spot-check errors are dominated by *non-step prose admitted as steps* (8/13 wrong): descriptive feature text, cross-references
   ("see X"), policy text. The coverage denominator therefore contains noise; we have not measured how that biases the curve.

## tech.ui (canonical UI actions) — PROVISIONAL / UNREVIEWED
4. **All tech.ui rows are `status=candidate`, `epistemic_status=PROVISIONAL`, `review_status=provisional_unreviewed`.** None is canonical;
   promotion requires **authority metadata (a named authority string; required, not authenticated)**, enforced in
   `ToteDB.add_loop/promote`. Nothing verifies who the authority is; an optional allow-list (`ToteDB.authority_registry`)
   only checks the name against a set.
5. **The 81 canonical actions are a hand-written mapping** (`tech_ui_pipeline/config/mapping.json`, ordered rules), not learned clusters.
   The coverage curve is therefore partly a property of the mapping we chose. Several classes are vague catch-alls
   (USE_FEATURE, CREATE_ITEM, SET_VALUE, FOLLOW_PROMPTS). TAP_OR_CLICK deliberately merges select/tap/click/choose on UI controls.
6. **Coverage wording.** An authored 81-class mapping accounts for 96.3% of the recorded extracted-action denominator; extraction
   and labeling remain provisional. This is not executable coverage. It tops out at 96.3% because only 81 classes exist (N=100
   and N=150 are identical). 3.7% of actions (2,442) are UNMAPPED long-tail verbs (~1,300 distinct) and are NOT ingested; they
   ship in `shared/data/tech_ui/ui_actions_unmapped.jsonl.gz` so the 65,929 denominator can be rebuilt independently
   (mapped 63,487 + unmapped 2,442; `REVIEW/tools/tech_ui_coverage.py`). The labels behind the 96.3% were spot-checked at
   21 correct / 6 partial / 13 wrong (n=40). 3,797 actions with listed "non-action" verbs
   (help, discuss, suggest, ...) were excluded from the denominator by a hand list (`non_action_verbs`).
7. **Source skew**: Microsoft Support = 1,500 of 2,887 articles and 51% of actions. Apple Support rate-limited our polite bot (HTTP 429
   even at 5 s/request): only 29 articles. Mozilla SUMO served a bot challenge: skipped (its GitHub repo has 32 files only).
   OpenAI and Patreon help are fetcher-blocked; Facebook/Craigslist/eBay forbid crawling: not used. ~20 pages returned 403/timeouts.
8. Raw HTML (1.8+ GB) is NOT in the repo or the zip; reproduction of the tech.ui *scrape* depends on live pages that change.
   What is reproducible offline is everything downstream of the compact export (`shared/data/tech_ui/`, SHA256 in `inputs.sha256`).
9. Object types come from a regex lexicon; platform comes from the site plus keyword hints; modifiers (direction/count/duration) and
   condition cues are regex. Exit gates for tech.ui are per-canonical *templates* (e.g. `screen_shows(Settings)`), not per-instance
   observations. Instances are deduped by (canonical, verb, normalized object); each occurrence keeps its own SourceRef.
9a. **Lookup context.** `ToteDB.lookup(action, object, domain=, platform=)` prefers rows matching the given domain/platform within
   the exact tier and records `context.fell_back=True` when none match (then the old order applies). Precondition and actor are
   never used for selection. Instance groups mix contexts: of 36,445 tech.ui groups, 2,010 span more than one platform and 345
   have conflicting modifiers (direction 329, count 11, duration 14, param 6); 2,198 have either. An instance's
   `perspective_cell` shows only its first occurrence's platform (all platforms are in `techniques[0].platforms`). 71
   (verb, object) keys are shared by more than one instance loop (143 loops), resolved by status then loop_id unless context
   disambiguates. The encoder (stage 07) passes domain only when the context stage resolves exactly one domain; it never passes platform.
9b. **Locator quality.** 2,399 tech.ui records have an empty section heading and 1,257 have neither section nor step number
   (URL-only locator). Each SourceRef carries `locator_quality:<section+step|section_only|step_only|url_only>`; counts are
   39,899 / 21,189 / 1,142 / 1,257.
10. Quotes are short excerpts for citation: at most 25 whitespace tokens of source text; when truncated, a leading and/or trailing
    `…` marker is added, so a stored quote can be 27 whitespace tokens (12,197 quotes are 26–27 tokens). No article text is stored. Platform help-center ToS were checked only at robots.txt level
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

## kg_run gate / permit / ledger (stage 04)
21. **Unkeyed hash chain.** QSON ledgers use plain SHA-256 chaining (no key, no signature). `verify` catches corruption and naive
    edits, but anyone able to rewrite a file can recompute all hashes. Strong tamper claims need external anchoring of the final
    event hash (signed timestamp / write-once log); none is implemented.
22. **Gate checks only the selected loop.** `kg_run` binds the FIRST TOTE instance the encoder finds and gates that one loop; other
    actions in a multi-action input are not checked or authorized. Not fixed in r2 (it changes the gate's result semantics and
    the ledger shape; needs a design decision: per-action permits vs one all-or-nothing gate).
23. Permits: issued before the GST transition; `record_trace` consumes the permit single-use (ISSUED -> CONSUMED, digest/run/loop
    and expiry checked) in ONE Kùzu transaction with the output state, TRANSITIONS_TO edge and ledger mirror; the ledger file is
    written ahead as `.pending` and renamed only after COMMIT (deleted on rollback). The permit row itself is committed in its own
    earlier transaction, so a crash between issue and commit leaves an ISSUED, unconsumed permit (it expires after 15 min).
    A crash after COMMIT but before the rename leaves a `.pending` file next to a committed graph state (the graph is authoritative).
24. **The kg_run gate is lexical-membership consistency, not semantic approval.** PASS means: the selected loop is CANONICAL,
    the grounded gestalt words all belong to it, no negation cue is present, and (legacy path) every content word of the
    utterance occurs in the selected loop's own text or the gestalt list (r3 guards, `kg_run.context_guard`). The guards are
    crude: a fixed negation word list and a stemmed bag-of-words check. They withhold PASS for the reviewer's controls
    ("do not repair ...", "repair the failing pregnancy test", "test the patient"), but they also send legitimate paraphrases with
    unseen words (e.g. "repair the failing integration test") to INTERMEDIATE, and they do not understand scope, sarcasm, or
    negation they do not list ("refrain from", "skip"). No population error rate has been measured (see RESPONSE_TO_REVIEW_r3 E1).
