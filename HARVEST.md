# TOTE batch harvester ("training" = populating the TOTE loop DB)

Code: `shared/nych3/harvest/` (`source.py` fetch/pages, `harvester.py` extraction + persistence, `cli.py`). Sources: `_config/registries/harvest_sources.json`. Schema additions: `SourceRef`, `SOURCED_FROM`, `HarvestSentence`, and `TOTELoop.repeat_count` / `structure_key`, all in `shared/schemas/tote_kuzu.cypher`.

## Sources (public domain, verified 2026-11-01)
Rights were checked from each Gutenberg HTML file's `<meta name="dc.rights">` (which reads "Public domain in the USA.") and from gutendex `copyright=false`.
| book_id | Title | Year | Why | Pages |
|---|---|---|---|---|
| pg71855 | Griffith, *Essentials of Woodworking* | 1908 | step-by-step tool procedures | printed (`span.pagenum`) |
| pg65061 | Farmer, *Boston Cooking-School Cook Book* | 1896– | thousands of imperative recipe steps with explicit exits ("until soft", "for 10 minutes") | printed (`span.pageno`) |
| pg29558 | *Boy Scouts Handbook*, 1st ed. | 1911 | first aid, knots, camping, signalling | derived |
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
