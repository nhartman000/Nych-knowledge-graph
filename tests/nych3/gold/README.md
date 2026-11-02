# NYCH3 TOTE gold set v1 — AGENT-GRADED, PENDING HUMAN REVIEW

`gold_v1.jsonl`: 300 sentences, 75 per domain (cooking, craft.woodworking, craft.knitting, craft.ropework),
drawn deterministically by `sample_gold.py` (seed 20261102) from the round-3 shard outcomes:
58 sentences the harvester accepted + 17 it rejected per domain (ropework had only 38 usable accepted
sentences, so it is topped up with rejected ones — these test the gate's recall). Every row carries
`sent_key` + `page` / `page_kind` provenance.

**Grading status:** written by the agent (Grok Bot, 2026-11-02) sentence by sentence, from the text,
with the extractor's draft visible. Treat it as a reviewed first draft, not ground truth; a human
pass is required before numbers are quoted externally. Known judgment calls are listed below.

## Notation (`gold` field; parsed by `shared/nych3/eval/compact.py`)

    action: obj1, obj2 @loc1 @loc2 ; mod 🙌,👀 ; exit TIER "text" ; amt q1, q2 ; actor passive
    loops separated by ` || `;   `-` = no loop expected

* action = lemma; objects = head lemmas incl. with-ingredients and tool; @ = head of a locative /
  directional PP (in the pan, into moulds, to the line); not manner/instrument PPs.
* mod = set of modality glyphs on the loop (action channel + sense-test steps), default `🙌`.
  Internal senses carry 🧠🗯 by default; 💭 only for explicit recall cues.
* exit tier: `explicit` (until / for-duration), `implied` (bare duration, destination, result state,
  sense word), omitted = `inferred` (completion).
* amt = object quantities as the harvester writes them (`2-3` for "two or three", `2 square`).
* actor: `you` (default, imperative) or `passive` (procedural modal passive, "should be held").

## Conventions / judgment calls
* Every instructed step is a loop, including bare verbs with no object ("strain, cool, add cream") —
  the harvester drops these by design (`no_object_tool_or_exit`), so they count as misses (reported
  separately as `missed_loop:bare_verb`).
* Cross-references ("Test as shown in Fig. 149", "(see p. 54)") are `-` per the skip rule;
  "Follow recipe for X" is kept as `follow: recipe`.
* Advice statements ("It is safer to …", "it is a good plan to …") and descriptive modals ("may be made
  higher") are `-`. "Care must be taken that …" is `-` unless it names a physical action.
* Index lines ("Ice Cream, 446.") and plate captions ("—Page 43.") are `-`.
* Participial/reduced clauses on ingredients ("whites beaten until stiff") are preparation states, not
  exits/tests of the main verb. Concurrent participles ("stirring constantly") are not separate loops.
* Crochet/rope "ring" is an object, never 👂.

Run: `nych3-eval` (or `PYTHONPATH=shared python -m nych3.eval.accuracy`); `--json out.json` for details.
