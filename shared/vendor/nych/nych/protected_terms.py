"""
protected_terms.py -- terms that are NEVER rendered into Gestalt symbols.

Rule (canon): scientific names, names of people, and prescription drug
names are not Gestalt-mapped. They pass through the pipeline literally --
no glyph, no consonant-skeleton id, no #temp-invariant pin. The reason is
recoverability: these are precise referents where any symbolic compression
risks a dangerous or unrecoverable ambiguity (one drug name mistaken for
another, one species or person for another).

Detection heuristics, disclosed at the same honesty bar as the rest of
this package -- small hand-built lists and surface patterns, not NER:

    person      -- an honorific (Dr./Mr./Ms. ...) followed by capitalized
                   words; or an adjacent pair of capitalized words, either
                   mid-sentence or at sentence start when the first word
                   isn't a common sentence opener ("The", "Then", ...).
    possible_name -- a lone capitalized word mid-sentence ("emailed
                   Maurice"); or the capitalized first word of a sentence
                   when it has no dictionary definition ("Maurice called"
                   -- rule: an opener with no definition is a name). The
                   dictionary is the bundled ESDB/SCOWL size-60 word list,
                   lowercase entries only, so names that exist only in
                   capitalized form never count as defined. Also catches
                   months, places, product names, and coined words;
                   labelled separately so that over-protection is visible
                   rather than presented as a confirmed person.
    scientific  -- a binomial pattern: a known genus (small list) or an
                   abbreviated genus ("E.") followed by a lowercase
                   species word.
    drug        -- a word on a small known-prescription-drug list, or one
                   carrying a characteristic pharmaceutical suffix
                   (-cillin, -statin, -pril, -azepam, ...).

Remaining known gaps: a name that is also a dictionary word ("Mark",
"Will", "Grace", "Rose") opening a sentence reads as a word, by the
definition of the rule; lowercase names ("emailed maurice") are not caught.
These rules over-protect (months, places, products, coined words like
"Multiword", a capitalized pair that isn't a person). Over-protection
is the safe failure mode here: a word wrongly left literal loses nothing,
while a protected term wrongly symbolized loses its referent.
"""

from __future__ import annotations

import functools
import gzip
import re
from pathlib import Path

DICTIONARY_PATH = Path(__file__).with_name("data") / "dictionary_words.txt.gz"


@functools.lru_cache(maxsize=1)
def _dictionary() -> frozenset[str]:
    """Lowercase English dictionary entries (ESDB/SCOWL size 60; see
    data/DICTIONARY_LICENSE.txt). Names that exist only in capitalized form
    are not in it -- that is what makes the first-word rule work."""
    with gzip.open(DICTIONARY_PATH, "rt", encoding="utf-8") as f:
        return frozenset(line.strip() for line in f if line.strip())


def has_dictionary_definition(word: str) -> bool:
    """True if `word` (any case) is an ordinary dictionary word.

    Checks the lowercase form; for hyphenated words also the joined form
    ("Re-ran" -> "reran") or all parts defined; for contractions also the
    stem ("Don't" is listed; "Maurice's" -> "maurice", not listed)."""
    lower = re.sub(r"^[^a-z]+|[^a-z]+$", "", word.lower())
    if not lower:
        return False
    d = _dictionary()
    if lower in d:
        return True
    if "'" in lower and lower.split("'")[0] in d:
        return True
    if "-" in lower:
        parts = [p for p in lower.split("-") if p]
        if lower.replace("-", "") in d or (parts and all(p in d for p in parts)):
            return True
        # Hyphenated prefix + defined word ("Pre-repurposing", "Non-trivial").
        # Deliberately NOT applied to unhyphenated words: stripping "under"
        # from "Underwood" would let a surname pass as a dictionary word.
        if len(parts) >= 2 and parts[0] in HYPHEN_PREFIXES and \
                has_dictionary_definition("-".join(parts[1:])):
            return True
    return False


HYPHEN_PREFIXES = {
    "anti", "auto", "bi", "co", "counter", "de", "dis", "inter", "micro",
    "mid", "mini", "multi", "non", "over", "post", "pre", "pro", "re",
    "self", "semi", "sub", "super", "trans", "tri", "un", "under",
}

HONORIFICS = {
    "mr", "mrs", "ms", "mx", "dr", "prof", "professor", "sir", "madam",
    "miss", "rev", "capt", "sgt", "lt", "col", "gen",
}

# Small known-genus list for binomial ("Genus species") detection.
GENERA = {
    "homo", "escherichia", "staphylococcus", "streptococcus", "salmonella",
    "drosophila", "arabidopsis", "saccharomyces", "canis", "felis", "mus",
    "rattus", "danio", "caenorhabditis", "bacillus", "mycobacterium",
    "plasmodium", "candida", "aspergillus", "clostridium", "helicobacter",
}

# Small known prescription-drug list.
KNOWN_DRUGS = {
    "metformin", "amoxicillin", "lisinopril", "atorvastatin", "sertraline",
    "fluoxetine", "warfarin", "prednisone", "gabapentin", "omeprazole",
    "levothyroxine", "amlodipine", "alprazolam", "lorazepam", "oxycodone",
    "hydrocodone", "insulin", "albuterol", "losartan", "metoprolol",
    "simvastatin", "azithromycin", "ciprofloxacin", "tramadol", "adderall",
    "ritalin", "xanax", "valium", "prozac", "zoloft", "lipitor", "ozempic",
}

# Characteristic pharmaceutical suffixes (INN naming stems).
DRUG_SUFFIXES = (
    "cillin", "mycin", "floxacin", "statin", "pril", "sartan", "olol",
    "dipine", "azole", "azepam", "oxetine", "prazole", "tinib", "ciclib",
    "mab", "nib", "vir", "gliptin", "glitazone", "setron", "triptan",
)

# Common sentence-opening words. A capitalized pair at sentence start whose
# first word is one of these is not treated as a two-word name.
SENTENCE_OPENERS = {
    "the", "a", "an", "then", "after", "before", "when", "while", "if",
    "this", "that", "these", "those", "we", "he", "she", "they", "it", "you",
    "our", "my", "his", "her", "their", "its", "your", "yesterday", "today",
    "tomorrow", "and", "but", "so", "also", "please", "ask", "tell", "email",
    "emailed", "call", "called", "met", "meet", "send", "sent", "thanks",
}

_PRONOUN_I = {"i", "i'm", "i'd", "i'll", "i've"}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'.-]*")


def _is_pronoun_i(core: str) -> bool:
    return core.lower() in _PRONOUN_I


def _core(token: str) -> str:
    """Token stripped of surrounding punctuation, case preserved."""
    m = _WORD_RE.search(token)
    return m.group(0).rstrip(".-") if m else ""


def _is_capitalized(core: str) -> bool:
    return bool(core) and core[0].isupper() and core[1:].islower()


def _is_drug(core: str) -> bool:
    lower = core.lower()
    if lower in KNOWN_DRUGS:
        return True
    return len(lower) > 6 and any(lower.endswith(s) for s in DRUG_SUFFIXES)


def find_protected(sentence: str) -> list[dict]:
    """Find protected terms in `sentence`.

    Returns a list of {"word", "position", "category", "reason"} records,
    one per protected token, in token order. Tokens are whitespace-split to
    stay aligned with state_roles.tag_roles positions."""
    tokens = sentence.split()
    cores = [_core(t) for t in tokens]
    records: dict[int, dict] = {}

    def protect(i: int, category: str, reason: str) -> None:
        if i not in records and cores[i]:
            records[i] = {"word": tokens[i], "position": i,
                          "category": category, "reason": reason}

    for i, core in enumerate(cores):
        lower = core.lower()

        # drugs: position-independent list/suffix check
        if _is_drug(core):
            protect(i, "drug",
                    "known prescription drug" if lower in KNOWN_DRUGS
                    else "pharmaceutical name suffix")
            continue

        # scientific binomial: known or abbreviated genus + lowercase species
        # The period is required: "E. coli" is a binomial, but "A dog" and
        # "I re-ran" are not.
        abbrev_genus = bool(re.fullmatch(r"[A-Z]\.", tokens[i].rstrip(",;:")))
        if (lower in GENERA or abbrev_genus) and i + 1 < len(cores):
            nxt = cores[i + 1]
            if nxt and nxt.islower():
                if lower in GENERA and _is_capitalized(core):
                    protect(i, "scientific", "binomial genus")
                    protect(i + 1, "scientific", "binomial species")
                    continue
                if abbrev_genus:
                    protect(i, "scientific", "abbreviated binomial genus")
                    protect(i + 1, "scientific", "binomial species")
                    continue

        # person: honorific followed by capitalized word(s)
        if lower in HONORIFICS and i + 1 < len(cores) and _is_capitalized(cores[i + 1]):
            protect(i + 1, "person", "follows honorific")
            j = i + 2
            while j < len(cores) and _is_capitalized(cores[j]):
                protect(j, "person", "follows honorific")
                j += 1
            continue

        sentence_start = i == 0 or tokens[i - 1].endswith((".", "!", "?"))

        # person: adjacent capitalized pair -- mid-sentence, or at sentence
        # start when the first word isn't an ordinary sentence opener
        # ("Nicholas Hartman fixed it" yes; "Then Maurice called" no --
        # that falls through so "Maurice" is caught by the lone-word rule).
        if (_is_capitalized(core) and not _is_pronoun_i(core)
                and i + 1 < len(cores) and _is_capitalized(cores[i + 1])
                and not (sentence_start and lower in SENTENCE_OPENERS)):
            reason = ("capitalized pair at sentence start" if sentence_start
                      else "capitalized adjacent pair")
            protect(i, "person", reason)
            protect(i + 1, "person", reason)
            continue

        # possible_name: the first word of a sentence, capitalized, with no
        # dictionary definition is treated as a name ("Maurice called").
        # Ordinary openers ("Fixed", "Re-ran", "Emailed") are dictionary
        # words and pass through to Gestalt mapping as normal.
        if (sentence_start and _is_capitalized(core)
                and not _is_pronoun_i(core) and lower not in HONORIFICS
                and not has_dictionary_definition(core)):
            protect(i, "possible_name",
                    "sentence-initial word with no dictionary definition")
            continue

        # possible_name: a lone capitalized word mid-sentence. Catches
        # single names ("emailed Maurice"), and will also catch months,
        # places, and product names -- over-protection by design.
        if (not sentence_start and _is_capitalized(core)
                and not _is_pronoun_i(core) and lower not in HONORIFICS):
            protect(i, "possible_name",
                    "capitalized mid-sentence word (may be a name; "
                    "over-protects by design)")

    return [records[i] for i in sorted(records)]


def protected_positions(sentence: str) -> dict[int, dict]:
    """{token position -> protected record} for `sentence`."""
    return {r["position"]: r for r in find_protected(sentence)}
