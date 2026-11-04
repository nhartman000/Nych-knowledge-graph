# TOTE batch harvester ("training" = populating the TOTE loop DB)

Code: `shared/nych3/harvest/` (`source.py` fetch/pages, `harvester.py` extraction + persistence, `cli.py`). Sources: `_config/registries/harvest_sources.json`. Schema additions: `SourceRef`, `SOURCED_FROM`, `HarvestSentence`, and `TOTELoop.repeat_count` / `structure_key`, all in `stages/02-schema/output/schema.cypher`.

## Sources (public domain, verified 2026-11-01)
Rights were checked from each Gutenberg HTML file's `<meta name="dc.rights">` (which reads "Public domain in the USA.") and from gutendex `copyright=false`.
| book_id | Title | Year | Why | Pages |
|---|---|---|---|---|
| pg71855 | Griffith, *Essentials of Woodworking* | 1908 | step-by-step tool procedures | printed (`span.pagenum`) |
| pg65061 | Farmer, *Boston Cooking-School Cook Book* | 1896– | thousands of imperative recipe steps with explicit exits ("until soft", "for 10 minutes") | printed (`span.pageno`) |
| pg13510 | Verrill, *Knots, Splices and Rope Work* | 1917 | step-by-step knots, splices, seizings (replaced the Boy Scouts Handbook pg29558 on 2026-11-02) | derived |
| pg26113 | *Handbook of Wool Knitting and Crochet* | n.d. | very fine-grained stitch instructions | derived |

## Provenance (user decision: ISBN + page only, at first)
- **ISBN:** none of the four files contains an ISBN, and three of the books predate the ISBN system (1970). `isbn` is stored as empty/null with `isbn_status` (`none_exists_pre_isbn*` / `none_found_in_source`). Modern reprints have their own ISBNs, but they are different editions with different pagination, so they are not used. No ISBN is ever invented.
- **Fallback:** `fallback_gutenberg_id` is always recorded and flagged as a fallback.
- **Page:** the printed page number when the HTML marks it (`page_kind=printed`). Otherwise `page = floor(char_offset_in_extracted_body_text / 2000) + 1`, recorded with `page_kind=derived` and the method in `page_method`. Paragraphs in a printed book that come before its first page marker also get a derived page.

## Guarantees
- **At most once:** each paragraph's `HarvestSentence` ledger rows and its loop writes commit in one Kuzu transaction. A sentence key (`book_id:offset`) that is already in the ledger is never processed again, even if `checkpoint.json` is deleted (this is tested).
- **Resumable:** `shared/data/harvest/checkpoint.json` stores `{book: next_offset, done}`. SIGTERM/SIGINT finishes the current paragraph and then exits cleanly.
- **Polite:** each book is fetched once, cached in `shared/data/corpus/`, with at least 5 s between requests and an identifying User-Agent. For many more books, use a Gutenberg mirror.
- **Skips:** dialogue (quotes), questions, lines with no sentence terminator (headings, ingredient lists), sentences over 80 tokens, and non-action sentences (copulas, statives, modals).
- **Actors:** an imperative gets `you(implied)`. An agentless passive gets `agent(implied; agentless passive)`, and its subject becomes the object.
- **Rows:** saved as `candidate`, deduped by normalized structure `[action lemma, object lemma, tool lemma, actor kind, channels, exit kind]` into `TL-H-<sha1[:12]>`. A repeat increments `repeat_count` and adds a SourceRef. The same structure from another domain adds an `IN_DOMAIN cross_link` (commonality).
- **Exits:** explicit `until …` / `for N <time>` text becomes a g8son gate marked `[explicit]`. Otherwise the gate reads `<action>_complete == true [inferred]`.
- **Promotion:** `nych3-harvest suggest` lists candidates with repeats ≥ 5 from ≥ 2 books. It is only a suggestion and promotes nothing. `nych3-harvest promote <loop_id> --authority "Name"` is the only path to canonical.
- **Stats:** each run writes `shared/data/harvest/runs/<run_id>.json` (sentences seen, skips, action sentences/clauses, loops new/repeat, no_match plus reasons, modality_unresolved, errors, per-book counts, and 40 sample rows with their sentences).

## Commands
```bash
VENV=/workspace/nych3pro-venv/bin; cd /workspace/nych-3-pro
$VENV/python -m nych3.harvest.cli run --max-sentences 3000            # bounded
# long run in the background (resumable; stop with kill -TERM <pid>):
nohup $VENV/python -m nych3.harvest.cli run --max-seconds 28800 >> shared/data/harvest/harvest.log 2>&1 &
$VENV/python -m nych3.harvest.cli suggest --min-repeats 5 --min-sources 2
$VENV/python -m nych3.harvest.cli promote TL-H-xxxxxxxxxxxx --authority "N Hartman"
```
**Scheduled job:** because every run resumes from the checkpoint and ledger, a cron entry such as `0 2 * * * cd /workspace/nych-3-pro && flock -n /tmp/nych3-harvest.lock /workspace/nych3pro-venv/bin/python -m nych3.harvest.cli run --max-seconds 3300 >> shared/data/harvest/harvest.log 2>&1` (or a systemd timer, or a Grok Bot routine running that command) adds work each night. `flock` matters because Kuzu allows only one writer. When all books are `done`, add more books to `harvest_sources.json`.

## Quality layer (v3.1)
- **Parser:** spaCy en_core_web_sm is the default (`--parser auto`). Imperatives get a "you " prefix injected; mood carries over through conj/ccomp.
- **Apparatus filter:** drops ALL-CAPS captions, Fig./Plate lines, transcriber's notes and page notes. Descriptive, stative and agentless-descriptive passive sentences are rejected, with the reasons recorded in run stats.
- **Measures:** `_config/invariants/measures.json` is the MASTER list of measurements and quantity modifiers, shared across domains, with per-domain overrides.
  - Every sense_weight is an ordered class (high/medium/low) and a hand-set **assumed_prior**. None are calibrated.
  - Context rules, applied in order, override the weight: MEAS-WORTH (always an amount), MEAS-NUM-BEFORE, MEAS-A-X-OF, MEAS-WITH-TOOL, MEAS-DEFINITE-REFERENCE.
- **Exits:** the provenance tier `implied_by_text` ranks explicit > implied_by_text > inferred.
  - Explicit exits: "until X", "for N minutes".
  - Implied by text: destinations (ride to the store gives actor_location == store), into/onto placements, result states, bare durations.
- **'with' resolution:** an instrument-class noun becomes the tool; an ingredient-class noun becomes a co-object with role with_ingredient; anything else stays unresolved, marked "(?)".
## 2026-11-02 quality pass (fixes 1–7)
1. **Instruction gate** (`domain_invariants.json → instruction_gate`): a clause becomes a loop only if it is imperative, or a procedural pattern: `should/must/shall/ought` + passive or `you/one` ("should be planed"), a present agentless passive of a hands-on verb ("is then cut"), or `you` + present hands-on verb. Rejected: past-tense narrative (`narrative_past`), other indicatives (`not_instruction`), `may/can be used` (optional/descriptive), idiomatic imperatives (`take care`, `make sure`... → `figurative_imperative`) and figurative markers. Leading enumerators/labels (`8. `, `Left front: `) are stripped first.
2. **Pronouns and bare numbers are never objects** (`bad_object`). In knitting, a bare count after a stitch verb becomes `stitch(implied) [N]` (`INV-IMPLIED-COUNT-NOUN`), because the stitch is the domain's canonical counted measure.
3. **Non-locations:** `in place of`, `instead of`, `in order`, `in case`, `in the same way` ... (`non_location_prep_objects`) are never perspective/location.
4. **Default modality:** every action verb gets a channel: `lemma_channels` (explicit), `lemma_channels_inferred`, else `default_action_channel` = 🙌 external kinesthetic, marked `[default]`. Each loop links to `Operator` rows through `USES_MODALITY {word: "<word>|<role>|<provenance>"}`. Valence (good or bad) belongs to the Gestalt and never to the modality.
   **Sense-mention rule (user, 2026-11-02):** a sense word (sight, feel, hearing, smell, taste, memory, imagining; `sense_cues`) is never stored alone. It is attached to the action loop whose clause contains it, as a TEST step (`initial_test`, `techniques[kind=sense_test]`) or as the EXIT step when it sits in the exit clause. Example: "Fry until golden" gives the fry loop the exit test `👀 verify color golden`. If the loop has no other exit, the sense test becomes its exit (`EXIT-SENSE-TEST`, implied_by_text). Attributive uses ("boiling water", "cold milk") describe an ingredient and are not tests. Mentions in sentences that yield no loop are only counted (`sense_unattached`).
5. **User seed loop** `TL-STIR-SAUCE-001` (canonical, authority N Hartman, `source_kind=user_prior_knowledge`, no ISBN or page): cooking / stir / sauce / tool spoon / in saucepan. Steps: 🙌 hold spoon in sauce; 🫶 feel sauce resistance (test); 🙌 stir in a circular motion (saucepans are round); 👀 verify the sauce is agitated or in motion, and if true, exit.
   **Secondary pass (NOT built):** implicit checks the text never states, such as *check the bottom of the saucepan for burning sauce* and *check the heat*, are separate loops. They will be extracted in a later secondary pass, after the fully described loops are parsed (listed in the seed's `provenance.deferred_secondary_loops`).
6. **Sources:** the Boy Scouts Handbook (pg29558) was replaced by Verrill, *Knots, Splices and Rope Work* (1917, pg13510, derived pages, `craft.ropework`). Knitting now yields loops: before, it was never reached, and its numbered rows and bare counts failed.
7. **Parallel harvest** (`harvest/parallel.py`, `nych3-harvest prun --workers N`): shards are (book, 60-paragraph range). N worker processes run the pure extractor and write `harvest/shards/<book>@<lo>-<hi>.jsonl` (tmp file plus atomic rename, so a file that exists is complete). Then ONE writer merges them into Kuzu, one transaction per shard, skipping ledger keys (at most once), and records `_merged_shards` in `checkpoint.json`. Re-running resumes both stages. Sentence keys are `<book>:p<para>:s<n>`. Use `--extract-only` or `--merge-only` to run the stages separately.
```bash
$VENV/python -m nych3.harvest.cli prun --workers 6
```
## 2026-11-02 round 2 (user-approved)
1. **Descriptive and passive sentences are rejected.** A passive without `should/must/shall/ought` is `descriptive_passive`. Frequency or ease adverbs (`often`, `easily`, `usually`, `now`...) or a demonstrative subject give `descriptive_frequency`.
2. **Exits and sense tests go to the right verb.** Verbs the parser hangs off a noun ("spread saltines with mixture **and bake**") are promoted to their own loop. An `until` clause goes to the nearest verb before it. Sense words are searched only from a verb up to the next verb. Bare durations ("cook ... five minutes") are read within the verb's own span.
3. **Objects.** A verb is never an object ("season", "bake"). Ingredient and tool nouns that happen to be verbs (butter, pepper...) stay nouns (`noun_verbs_kept_as_nouns`). With placement verbs, containers are locations ("Put in a stone jar" gives `in jar`). "fold/stir in X" makes X the object. A repeated verb in the same sentence inherits the object ("beat whites ... continue beating").
4. **Quantities.** `one-half cup` → `1/2 cup`, `one and one-half cups` → `1 1/2 cup`, `two-thirds of sugar` → sugar `[2/3]`, `1/2` and `½` are kept. `No. 16` is a **size** (`[size No. 16]`), not a count.
5. **Cross-references** ("See directions ..., page 434") are skipped (`cross_reference`). **Negatives** ("Never ...", "Do not ...") are stored as **prohibitions**: the action cell reads `NEVER put, [prohibition]`, the name starts with "never", techniques include `kind=prohibition`, the exit is "the action must not occur", and the structure key carries `PROHIBIT`, so a prohibition never merges with the positive action.
- `Bore` is no longer lemmatized to `bear` (the lexicon verb wins), and tool names such as "smooth, jack and fore-plane" are no longer read as feel tests.
## 2026-11-02 round 3 (user-approved): modality rule change and verb fixes
- **Imagine is 🧠🗯** (it replaces the old eye-in-speech-bubble glyph, which was too close to 👁️ internal visual) in the invariants, the `OP-IMG` Operator row, docs and tests. Mental and projection verbs (determine, decide, judge, estimate, plan, consider, calculate, design, anticipate, think ...) map to imagine 🧠🗯.
- **Every internal sense carries a mental marker** (`modality.json → mental_markers`). Internal visual 👁️, internal auditory 👂 and internal kinesthetic 🫶 each get 💭 (remembered) when a memory cue is in the sentence (`remember`, `recall`, `recollect`, `as before`, `as previously`), and 🧠🗯 (imagined) otherwise. The deciding cue is recorded (`marker_cue`, or `no_memory_cue`), the step glyph becomes e.g. `🫶🧠🗯 feel stiff`, and a second USES_MODALITY link (`role mental_marker`) points to OP-IMG or OP-MEM. External senses carry no marker.
- **More verbs:** sauté, braise, parboil, blanch, poach, simmer, soak, `let stand` / `let cool` (let + verb), verbs the parser hangs as `dep`/`advcl`, and a first imperative hung off its own object. Time and `until` clauses now attach to these verbs instead of the previous one.
- **dry / cool / warm used as verbs are actions**, not sense tests.
- **Place filter narrowed:** only `in place of` / `in lieu of` is dropped. `in a cool place` is a real location.
- **Fractions of an inch** ("one thirty-second of an inch") are lengths, never times.
- An imperative with only a location ("fry in deep fat") is now a loop.

## State 2026-11-02 (end of day)
- Book store: 3,545 harvested/seed loops (4 Gutenberg books); gold set v1 (300 sentences) is **agent-graded, pending human review**.
- **tech.ui** added (provisional, unreviewed): 81 canonical UI-action loops + 36,445 instance loops + 63,487 web SourceRefs; nothing promoted.
  Ingest: `python -m nych3.harvest.tech_ui`. Store total 40,071 loops (40,069 candidate, 2 canonical seed). No cross-domain links involve tech.ui.
- Secondary pass not built; Gestalt cells blank (stage 10 not run). Full list: `REVIEW/LIMITATIONS.md`.
