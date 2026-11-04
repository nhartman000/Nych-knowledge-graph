"""spaCy-based action extraction for the harvester (deterministic, on-device model).

Fixes over the rule path: real object heads + coordinated objects (one loop, many
objects), quantity/unit invariants (_config/invariants), 'with' resolved by noun class
(instrument -> tool, ingredient -> co-object, else unresolved), mood/passive carried along
coordination correctly, implied exits (goal/destination/result-state/bare duration).

Imperative trick (disclosed): en_core_web_sm often mis-tags sentence-initial imperatives
('Melt' NN, 'Cut' JJ). When the first word is a lexicon verb, the sentence is parsed as
'you <verb> ...' and the 'you' is reported as implied (actor 'you(implied)')."""
from __future__ import annotations
import functools, json, re
from ..config import CONFIG, registry
from ..nlp.analysis import operator_cell

STATIVE_EXTRA = {"be", "have", "do", "say", "will", "would", "could", "should", "might", "may", "must", "can", "let"}
MODALS = {"should", "must", "may", "can", "might", "could", "would", "will", "shall", "ought"}


@functools.lru_cache(maxsize=1)
def inv():
    d = json.loads((CONFIG / "invariants" / "domain_invariants.json").read_text(encoding="utf-8"))
    d["_measures"] = json.loads((CONFIG / "invariants" / "measures.json").read_text(encoding="utf-8"))
    d["_classes"] = {k: set(v) for k, v in d["noun_classes"].items()}
    d["_verbs"] = {k: set(v) for k, v in d["verb_classes"].items()}
    d["_app"] = [re.compile(p, re.I) for p in d["apparatus_patterns"]]
    return d


@functools.lru_cache(maxsize=1)
def nlp():
    import spacy
    return spacy.load("en_core_web_sm", disable=["ner"])


def is_apparatus(text: str) -> str | None:
    I = inv()
    for p in I["_app"]:
        if p.search(text):
            return f"pattern:{p.pattern}"
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= I["apparatus_all_caps_min_letters"] and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return "all_caps_caption"
    return None


def _num(tok):
    w = tok.text.lower()
    return inv()["number_words"].get(w, tok.text)


def _lemma(t):
    return t.lemma_.lower() if t.pos_ != "PROPN" else t.text


_DOMAIN = [None]   # current domain (set per extract call)


def sense_weight(word: str, domain: str | None = None):
    """-> (class, source) for the measurement sense; None if not in the master list."""
    M = inv()["_measures"]
    e = M["entries"].get(word)
    if e is None:
        return None
    dom = M["domain_aliases"].get(domain or "", domain)
    return (e.get("domains", {}).get(dom, e["sense_weight"]), M["weight_source"])


def _has_number(t):
    return any(c.dep_ == "nummod" or c.text.lower() in inv()["number_words"] for c in t.children) or \
        (t.i > 0 and (t.doc[t.i - 1].like_num or t.doc[t.i - 1].lower_ in inv()["number_words"]))


def _worth(t):
    d = t.doc
    return (t.i + 1 < len(d) and d[t.i + 1].lower_ == "worth") or \
        (t.i + 2 < len(d) and d[t.i + 1].text in ("'s", "’s") and d[t.i + 2].lower_ == "worth")


def measure_decision(t, domain=None):
    """-> (is_measurement, rule_id, weight). Context rules override the assumed_prior weight."""
    lem = _lemma(t)
    w = sense_weight(lem, domain) or sense_weight(t.lower_, domain)
    if _worth(t):
        return True, "MEAS-WORTH", w[0] if w else None
    if w is None:
        return False, "MEAS-NOT-LISTED", None
    kind = inv()["_measures"]["entries"].get(lem, inv()["_measures"]["entries"].get(t.lower_, {})).get("kind", "")
    art = t.i > 0 and t.doc[t.i - 1].lower_ in ("a", "an") and kind.startswith("approx")
    if _has_number(t) or art:
        return True, "MEAS-NUM-BEFORE", w[0]
    if t.dep_ == "pobj" and t.head.lower_ in ("with", "using"):
        if t.i > 0 and t.doc[t.i - 1].lower_ in ("a", "an") and any(c.dep_ == "prep" and c.lower_ == "of" for c in t.children):
            return True, "MEAS-A-X-OF", w[0]
        return False, "MEAS-WITH-TOOL", w[0]
    if any(c.dep_ in ("det", "poss") and c.lower_ in ("the", "this", "that", "these", "those", "his", "her", "its", "their", "your", "my")
           for c in t.children):
        return False, "MEAS-DEFINITE-REFERENCE", w[0]
    return w[0] == "high", "MEAS-WEIGHT", w[0]


def _is_unit(t):
    return measure_decision(t, _DOMAIN[0])[0]


LENGTH_UNITS = {"inch", "inches", "in.", "foot", "feet", "ft.", "yard", "yards", "line", "lines"}


def is_length_fraction(t):
    """'one thirty-second of an inch': 'second' here is an ordinal fraction of a length, never a time."""
    d = t.doc
    after = [x.lower_ for x in d[t.i + 1:t.i + 4]]
    return "of" in after and any(a in LENGTH_UNITS for a in after) or (t.i > 0 and d[t.i - 1].text in ("-", "–") and "of" in after)


def _is_time(t):
    return _lemma(t) in inv()["time_units"] and not is_length_fraction(t)


FRACTION_WORDS = {"half": 2, "halves": 2, "third": 3, "thirds": 3, "fourth": 4, "fourths": 4, "quarter": 4, "quarters": 4,
                  "fifth": 5, "fifths": 5, "sixth": 6, "sixths": 6, "eighth": 8, "eighths": 8}
SIZE_MARKERS = {"no", "no.", "number", "size", "#"}
_UNI_FRAC = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8"}


ORDINAL = re.compile(r"^\d+(st|nd|rd|th|d)$", re.I)


def _numtok(x):
    w = x.lower_
    if ORDINAL.match(x.text) or w in ("first", "second", "last", "next"):
        return False   # '1st 18 stitches', 'miss 1st stitch': an ordinal is a position, not an amount
    return x.like_num or w in inv()["number_words"] or w in FRACTION_WORDS or w in _UNI_FRAC or bool(re.fullmatch(r"\d+/\d+|\d*[½¼¾⅓⅔⅛]", x.text))


def normalize_quantity(words):
    """'two or three' / '18 to 20' -> '2-3' / '18-20' (a RANGE, never the upper bound).
    ['one','-','half'] -> '1/2'; ['one','and','one','-','half'] -> '1 1/2'; ['two','-','thirds'] -> '2/3'; ['1/2'] -> '1/2'."""
    nw = inv()["number_words"]
    lw_ = [w.lower() for w in words]
    for sep in ("or", "to"):
        if sep in lw_:
            k = lw_.index(sep)
            a, b = normalize_quantity(words[:k]), normalize_quantity(words[k + 1:])
            return f"{a}-{b}" if a and b else (a or b)
    out, cur = [], []
    for w in words + ["and"]:
        lw = w.lower()
        if lw in ("and", "a"):
            if cur:
                out.append(cur); cur = []
            continue
        if lw in ("-", "–"):
            continue
        cur.append(lw)
    parts = []
    for c in out:
        if len(c) >= 2 and c[-1] in FRACTION_WORDS:
            num = nw.get(c[-2], c[-2])
            parts.append(f"{num}/{FRACTION_WORDS[c[-1]]}")
        elif len(c) == 1 and c[0] in FRACTION_WORDS:
            parts.append(f"1/{FRACTION_WORDS[c[0]]}")
        else:
            parts.append(" ".join(_UNI_FRAC.get(x, nw.get(x, x)) for x in c))
    return " ".join(parts) if parts else None


def dur_cond(q, unit, prefix=""):
    """elapsed condition; a range 'a-b' becomes a window, never just the upper bound."""
    m = re.fullmatch(r"([\d/ ]+)-([\d/ ]+)", q or "")
    if m:
        return f"{m.group(1).strip()} {unit} <= elapsed <= {m.group(2).strip()} {unit}"
    return f"elapsed >= {q} {unit}"


def quantity_range(q):
    m = re.fullmatch(r"([\d/ ]+)-([\d/ ]+)", (q or "").split(" ")[0] if q else "")
    return [m.group(1), m.group(2)] if m else None


def _size(t):
    """'No. 16 steel needles' -> 'No. 16' (a size, not a count)."""
    d = t.doc
    for j in range(max(0, t.i - 4), t.i):
        if d[j].lower_.rstrip(".") in ("no", "number", "size", "#") and j + 1 < len(d):
            k = j + 1
            if d[k].text == ".":
                k += 1
            if k < t.i + 1 and d[k].like_num:
                return f"No. {d[k].text}"
    return None


def _quantity(t):
    """Number words / fractions immediately left of the head (or as nummod/quantmod children). None if it is a size."""
    if _size(t):
        return None
    d = t.doc
    j = t.i - 1
    while j >= 0 and (d[j].dep_ in ("compound", "amod") and not _numtok(d[j]) and d[j].pos_ in ("NOUN", "ADJ") and j > t.i - 3):
        j -= 1   # skip one or two compounds/adjectives ('one-half cup cracker crumbs')
    words = []
    while j >= 0 and (_numtok(d[j]) or (d[j].text in ("-", "–") and j > 0 and _numtok(d[j - 1])) or
                      (d[j].lower_ in ("and", "or", "to") and j > 0 and _numtok(d[j - 1]) and words)):
        words.insert(0, d[j].text); j -= 1
    if words and words[0].lower() in ("and", "or", "to"):
        words = words[1:]
    if words:
        return normalize_quantity(words)
    nums = [c for c in t.children if c.dep_ == "nummod" or (c.dep_ in ("amod", "det", "quantmod") and c.text.lower() in inv()["number_words"])]
    return " ".join(_num(n) for n in nums) if nums else None


def resolve_np(head):
    """-> {head, lemma, quantity, unit, span_text} applying the unit invariant."""
    if head is None:
        return None
    if head.lower_ in FRACTION_WORDS:
        of = next((c for c in head.children if c.dep_ == "prep" and c.lower_ == "of"), None)
        noun = next((c for c in of.children if c.dep_ == "pobj"), None) if of is not None else None
        if noun is not None:
            q = _quantity(head)
            q = q if q and "/" in q else normalize_quantity([*(q.split() if q else ["one"]), head.lower_])
            return {"head": noun.text, "lemma": _lemma(noun), "quantity": q, "rule": "INV-FRACTION-OF"}
    sz = _size(head)
    if sz:
        return {"head": head.text, "lemma": _lemma(head), "quantity": None, "size": sz, "rule": "INV-SIZE-NOT-COUNT"}
    if head.lower_ != "worth" and _worth(head):
        wt = next((c for c in head.children if c.lower_ == "worth"), None) or \
            next((x for x in head.doc[head.i + 1:head.i + 3] if x.lower_ == "worth"), None)
        of = next((c for c in list(head.children) + (list(wt.children) if wt is not None else []) if c.dep_ == "prep" and c.lower_ == "of"), None)
        noun = next((c for c in of.children if c.dep_ == "pobj"), None) if of is not None else None
        qty = f"{_quantity(head) or '1'} {_lemma(head)} worth"
        if noun is not None:
            return {"head": noun.text, "lemma": _lemma(noun), "quantity": qty, "rule": "MEAS-WORTH"}
        return {"head": qty, "lemma": "amount", "quantity": qty, "object_is_unit": True, "rule": "MEAS-WORTH"}
    if head.lower_ == "worth":
        meas = next((c for c in head.children if c.pos_ in ("NOUN", "PROPN") and c.dep_ in ("poss", "compound", "npadvmod", "nmod", "amod")), None)
        if meas is None and head.i > 0 and head.doc[head.i - 1].pos_ == "NOUN":
            meas = head.doc[head.i - 1]
        q = (_quantity(meas) if meas is not None else None) or ("1" if meas is not None else "")
        of = next((c for c in head.children if c.dep_ == "prep" and c.lower_ == "of"), None)
        noun = next((c for c in of.children if c.dep_ == "pobj"), None) if of is not None else None
        qty = f"{q} {_lemma(meas)} worth".strip() if meas is not None else "worth"
        if noun is not None:
            return {"head": noun.text, "lemma": _lemma(noun), "quantity": qty, "rule": "MEAS-WORTH"}
        return {"head": qty, "lemma": "amount", "quantity": qty, "object_is_unit": True, "rule": "MEAS-WORTH"}
    if _is_unit(head):
        q = _quantity(head) or ""
        follow = [c for c in head.children if c.dep_ == "prep" and c.text.lower() == "of"]
        noun = None
        if follow:
            noun = next((c for c in follow[0].children if c.dep_ == "pobj"), None)
        if noun is None:
            nxt = head.doc[head.i + 1] if head.i + 1 < len(head.doc) else None
            if nxt is not None and nxt.pos_ in ("NOUN", "PROPN") and not _is_unit(nxt):
                noun = nxt
        if noun is not None:
            return {"head": noun.text, "lemma": _lemma(noun), "quantity": f"{q} {_lemma(head)}".strip(), "rule": "INV-UNIT-QUANTITY-MODIFIER"}
        return {"head": head.text, "lemma": _lemma(head), "quantity": q or None, "object_is_unit": True, "rule": "INV-UNIT-AS-COUNTED-OBJECT"}
    unit_child = next((c for c in head.children if c.dep_ in ("compound", "nmod", "amod") and _is_unit(c)), None)
    if unit_child is not None:
        q = _quantity(unit_child) or _quantity(head) or ""
        return {"head": head.text, "lemma": _lemma(head), "quantity": f"{q} {_lemma(unit_child)}".strip(), "rule": "INV-UNIT-QUANTITY-MODIFIER"}
    return {"head": head.text, "lemma": _lemma(head), "quantity": _quantity(head), "rule": "SPACY-HEAD"}


def _conj_nouns(t):
    out, stack = [], [t]
    while stack:
        x = stack.pop()
        out.append(x)
        stack.extend(c for c in x.children if c.dep_ == "conj" and c.pos_ in ("NOUN", "PROPN", "NUM"))
    return sorted(out, key=lambda x: x.i)


def _verb_form(t):
    return {"VBG": "VBG", "VB": "VB", "VBD": "VBD", "VBN": "VBN", "VBZ": "VBZ", "VBP": "VB"}.get(t.tag_, "VB")


def _clause_text_from(tok):
    doc, j = tok.doc, tok.i
    end = j
    while end + 1 < len(doc) and doc[end + 1].text not in (",", ";", ".", ":", "!"):
        end += 1
    return doc[j:end + 1].text


def parse(text: str):
    """Return (doc, imperative_injected, offset)."""
    verbs = set(registry("lexicon")["verbs"]); noimp = set(registry("lexicon").get("not_imperative_initial", []))
    words = text.split()
    first = re.sub(r"[^A-Za-z-]", "", words[0]).lower() if words else ""
    second = re.sub(r"[^A-Za-z]", "", words[1]).lower() if len(words) > 1 else ""
    if first in verbs and first not in noimp and second not in ("is", "are", "was", "were", "has", "have", "will", "can"):
        return nlp()("you " + text[0].lower() + text[1:]), True, 1
    return nlp()(text), False, 0


CROSS_REF = re.compile(r"^\s*(see|cf\.?|compare|refer to)\b|\b(see|cf\.?)\s+(page|p\.|pp\.|fig\.?|figure|chapter|directions|recipe|rule|table)\b|"
                       r"\(\s*(see|follow)\b[^)]*\bp(age|\.)\s*\d+|^[^.]{0,60}\bon page \d+\.?$", re.I)
PROHIBIT = re.compile(r"^\s*(never|do not|don't|avoid|nor)\b", re.I)
_ENUM = re.compile(r"^\s*(?:\(?\d{1,3}[.)]|\(?[a-z][.)]|[A-Z][A-Za-z -]{0,30}:)\s+(?=[A-Z])")
PRONOUN_OBJ = {"it", "them", "this", "that", "these", "those", "one", "ones", "him", "her", "us", "me", "you", "itself", "themselves",
               "each", "all", "both", "some", "any", "other", "others", "same", "which", "what", "former", "latter", "rest"}


def strip_enumerator(text: str) -> str:
    """'8. Slip 1, purl 1' -> 'Slip 1, purl 1'; 'Left front: Cast on 65' -> 'Cast on 65'."""
    return _ENUM.sub("", text, count=1)


def bad_object(n) -> str | None:
    """Fix 2: pronouns and bare numbers are never objects."""
    if n.pos_ == "PRON" or n.lower_ in PRONOUN_OBJ:
        return "pronoun_object"
    if n.pos_ == "NUM" or n.like_num or n.lower_ in inv()["number_words"] or re.fullmatch(r"[\d/.,½¼¾-]+(st|nd|rd|th|d)?", n.text):
        return "bare_number_object"
    return None


def non_location(p: str, pobj) -> bool:
    """Fix 3: 'in place of X' / 'instead of' / 'in order to' are not locations."""
    nl = inv()["non_location_prep_objects"]
    lst = nl.get(p)
    if lst is None:
        return False
    if _lemma(pobj) in ("place", "lieu"):   # only 'in place of X' / 'in lieu of X'; 'in a cool place' is a real location
        return any(c.dep_ == "prep" and c.lower_ == "of" for c in pobj.children) and not any(c.dep_ in ("det", "amod") for c in pobj.children)
    return "*" in lst or _lemma(pobj) in lst


def in_reduced_clause(t):
    """True when t sits inside a reduced relative / participial modifier of a noun ('yolks of eggs beaten until thick'):
    that describes how an ingredient was prepared, not a test of the current action."""
    x = t
    while x.head.i != x.i:
        if x.dep_ in ("acl", "relcl") and x.head.pos_ in ("NOUN", "PROPN"):
            return True
        x = x.head
    return False


SENSE_NOUN_OBJECTS = {"ring", "rings"}   # crochet/rope 'ring' is a thing, not a sound


def sense_mentions(doc):
    """-> [(token_index, channel, cue_word, step_text)] for every sense word in the sentence."""
    out = []
    cues = {k: v for k, v in inv()["sense_cues"].items() if not k.startswith("_")}
    for t in doc:
        w = t.lower_
        if t.dep_ in ("amod", "compound", "nmod") and t.head.pos_ in ("NOUN", "PROPN"):
            continue   # attributive ('boiling water', 'cold milk', 'soft-shelled clams'): describes an ingredient, not a sense test
        if t.dep_ in ("pobj", "conj", "nmod", "appos", "dobj") and any(
                _lemma(x) in inv()["_classes"]["instrument"] or x.lower_.endswith("plane") for x in list(t.conjuncts) + list(t.subtree) if x is not t):
            continue   # 'smooth, jack and fore-plane': names of tools, not a feel test
        if (w in SENSE_NOUN_OBJECTS and t.pos_ in ("NOUN", "PROPN")) or in_reduced_clause(t):
            continue
        for ch, spec in cues.items():
            if w in spec["words"] or _lemma(t) in spec["cue_verbs"]:
                if _lemma(t) in spec["cue_verbs"] or w in spec["cue_verbs"]:
                    step = spec["step"]
                elif w in spec.get("color_words", ()):
                    step = f"{spec['step']} color {w}"
                else:
                    step = f"{spec['step']} {w}"
                out.append((t.i, ch, w, step))
                break
    return out


def mental_marker(text: str, modreg: dict):
    """-> (glyph, cue). Internal senses carry 💭 (remembered) when a memory cue is present, else 🧠🗯 (imagined)."""
    mm = modreg["mental_markers"]
    low = " " + text.lower() + " "
    cue = next((c for c in mm["memory_cues"] if re.search(r"\b" + re.escape(c) + r"\b", low)), None)
    return (mm["memory"], cue) if cue else (mm["imagined"], mm["default_cue"])


def channel_for(lem: str, modreg: dict):
    """Fix 4: -> (channel, provenance). Every action verb gets one; unknown verbs get the default (🙌)."""
    ch = modreg["lemma_channels"].get(lem)
    if ch:
        return ch, "explicit"
    inf = modreg.get("lemma_channels_inferred", {}).get(lem)
    if inf and inf.get("channel") not in (None, "unresolved"):
        return inf["channel"], "inferred"
    d = modreg.get("default_action_channel") or {"channel": "external_kinesthetic"}
    return d["channel"], "default"


def extract(text: str, modreg: dict, lexverbs: set, domain: str | None = None, stats: dict | None = None):
    """-> (outcome, loops, reason). `stats` (optional) collects sense_attached / sense_unattached counts."""
    _DOMAIN[0] = domain
    app = is_apparatus(text)
    if app:
        return "skipped_apparatus", [], app
    I = inv()
    text = strip_enumerator(text)
    low = text.lower()
    if any(m in low for m in I["instruction_gate"]["figurative_markers"]):
        return "non_action", [], "figurative"
    if CROSS_REF.search(text):
        return "non_action", [], "cross_reference"
    doc, injected, off = parse(text)
    senses = sense_mentions(doc)

    def _ret(outcome, loops, reason):
        if stats is not None:
            att = sum(len(lp.get("sense_tests", [])) for lp in loops)
            stats["sense_attached"] = stats.get("sense_attached", 0) + att
            stats["sense_unattached"] = stats.get("sense_unattached", 0) + (len(senses) - att)
        return outcome, loops, reason
    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if root is None:
        return _ret("non_action", [], "no_root")

    def verbish(t):
        return t.pos_ in ("VERB",) or (t.lower_ in lexverbs and t.pos_ in ("NOUN", "ADJ", "PROPN") and not any(c.dep_ == "det" for c in t.children))

    # candidate action verbs: root + coordinated verbs (+ repair of conj verbs tagged NN, e.g. 'cook')
    cands = [root] if verbish(root) else []
    stack = list(cands)
    promoted = set()   # verbs the parser hung off a noun ('spread saltines with mixture and bake'; 'add milk, season, and bind')
    keepnoun = I["_classes"]["ingredient"] | I["_classes"]["instrument"] | I["_classes"]["container"] | set(I.get("noun_verbs_kept_as_nouns", []))
    while stack:
        v = stack.pop()
        for c in v.children:
            if (c.dep_ == "conj" or (c.dep_ == "dep" and c.pos_ == "VERB" and c.tag_ in ("VB", "VBP")) or (c.dep_ == "parataxis" and injected) or (c.dep_ == "ccomp" and injected and any(g.dep_ == "nsubj" and g.i == 0 for g in c.children))) \
                    and verbish(c) and c not in cands:
                cands.append(c); stack.append(c)
        for c in v.children:   # 'Take from water, dry between towels, and fry': verb used as advcl (dry/cool/warm are actions here)
            if c.dep_ == "advcl" and c not in cands and ((c.lower_ in lexverbs and c.pos_ in ("VERB", "ADJ", "NOUN")) or (c.pos_ == "VERB" and c.tag_ in ("VB", "VBP"))) \
                    and not any(g.dep_ in ("mark", "nsubj", "nsubjpass", "aux", "auxpass") for g in c.children) and c.i > v.i:
                cands.append(c); stack.append(c); promoted.add(c.i)
        for c in v.subtree:
            if c in cands or c.dep_ != "conj" or c.head.pos_ not in ("NOUN", "PROPN"):
                continue
            bare = not any(g.dep_ in ("det", "amod", "compound", "nummod", "poss") for g in c.children)
            if c.lower_ in keepnoun:
                continue   # 'cook butter, shallot, and pepper': an ingredient, not a verb
            if (c.pos_ == "VERB" and c.tag_ in ("VB", "VBP")) or (c.lower_ in lexverbs and c.lower_ not in keepnoun and bare and c.pos_ in ("NOUN", "PROPN")):
                cands.append(c); stack.append(c); promoted.add(c.i)
    if injected and off < len(doc) and doc[off] not in cands and doc[off].lower_ in lexverbs and doc[off].dep_ in ("amod", "advcl", "compound", "nmod"):
        cands.append(doc[off])   # 'Clean one-fourth pound mushrooms, break ...': parser hung the first imperative off its object
    if not cands:
        return _ret("non_action", [], "no_action_verb")
    cands.sort(key=lambda t: t.i)
    cand_i = {c.i for c in cands}
    senses = [m for m in senses if m[0] not in cand_i or _lemma(doc[m[0]]) in
              {w for k, sp in I["sense_cues"].items() if not k.startswith("_") for w in sp["cue_verbs"]}]   # 'dry', 'cool', 'warm' used as verbs are actions
    loops, reasons, state = [], [], {}
    for v in cands:
        lem = v.lower_ if v.pos_ != "VERB" else _lemma(v)
        if v.lower_ in lexverbs and lem not in lexverbs:
            lem = v.lower_          # 'Bore these holes' -> bore, not bear (lemmatizer picked another verb's past tense)
        elif injected and v.i == off and v.lower_ in lexverbs:
            lem = v.lower_          # sentence-initial imperative is already base form
        subj = next((c for c in v.children if c.dep_ in ("nsubj", "nsubjpass")), None)
        passive = any(c.dep_ in ("auxpass", "nsubjpass") for c in v.children)
        auxes = [c for c in v.children if c.dep_ in ("aux", "auxpass")]
        modal = any(a.lower_ in MODALS for a in auxes)
        neg = any(c.dep_ == "neg" for c in v.children) or bool(PROHIBIT.match(text) and v.i == min(x.i for x in cands))
        # carry-over along coordination: inherit only when the conjunct has no own subject AND matches form
        parent = state.get(v.head.i) if v.dep_ == "conj" else None
        if v.i in promoted:
            parent = next((state[c.i] for c in sorted(cands, key=lambda x: -x.i) if c.i < v.i and c.i in state), None)
        if subj is not None and injected and subj.i == 0:
            mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
        elif subj is not None:
            mood = "indicative"
            if passive:
                agent = next((c for c in v.children if c.dep_ == "agent"), None)
                ag = next((c for c in agent.children if c.dep_ == "pobj"), None) if agent is not None else None
                actor_kind, actor_text = ("agent", ag.text) if ag is not None else ("implied_agent_passive", "agent(implied; agentless passive)")
            else:
                actor_kind, actor_text = ("you" if subj.lower_ == "you" else "agent"), subj.text
        elif parent is not None:
            if parent["mood"] == "imperative" and (v.tag_ in ("VB", "VBP", "NN", "NNP", "JJ") or (injected and lem in lexverbs and not auxes)):
                mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
            elif parent["passive"] and v.tag_ == "VBN":
                mood, actor_kind, actor_text, passive = "indicative", parent["actor_kind"], parent["actor_text"], True
                modal = parent["modal"]
            elif parent["mood"] == "indicative" and not parent["passive"]:
                mood, actor_kind, actor_text = "indicative", parent["actor_kind"], parent["actor_text"]
            else:
                mood, actor_kind, actor_text = "unresolved", "unresolved", "UNRESOLVED"
        elif v.tag_ == "VB" and not passive and auxes and all(a.lower_ in ("do", "don't") for a in auxes) and neg:
            mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
        elif (v.tag_ == "VB" or (injected and (v.tag_ == "VBP" or (lem in lexverbs and v.tag_ in ("VBZ", "VBD", "NN"))))) and not passive and not auxes:   # base-form verb with no subject = imperative
            mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
        else:
            mood, actor_kind, actor_text = "unresolved", "unresolved", "UNRESOLVED"
        state[v.i] = {"mood": mood, "passive": passive, "actor_kind": actor_kind, "actor_text": actor_text, "modal": modal}
        let_aux = any(c.lower_ == "let" for c in v.children if c.dep_ in ("aux", "auxpass"))
        if let_aux and mood == "unresolved":
            mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
            state[v.i].update(mood=mood, actor_kind=actor_kind, actor_text=actor_text)
        if (lem in STATIVE_EXTRA or lem in I["_verbs"]["stative_or_descriptive"]) and not (let_aux and lem in ("stand", "rise", "cool", "rest", "simmer", "boil")):
            reasons.append("stative_or_nonaction_verb"); continue
        manip = modreg["lemma_channels"].get(lem) == "external_kinesthetic"
        G = I["instruction_gate"]
        if mood == "imperative":
            dob = next((c for c in v.children if c.dep_ in ("dobj", "obj", "prep")), None)
            pair_objs = {_lemma(c) for c in v.children if c.dep_ in ("dobj", "obj")} | \
                        {_lemma(g) for c in v.children if c.dep_ == "prep" for g in c.children if g.dep_ == "pobj"}
            if any(lem == a and b in pair_objs for a, b in G["figurative_imperatives"]):
                reasons.append("figurative_imperative"); continue
        else:
            if any(a.lower_ in G["narrative_aux"] for a in auxes) or (v.tag_ == "VBD" and not passive):
                reasons.append("narrative_past"); continue
            subj_l = subj.lower_ if subj is not None else ""
            strong = any(a.lower_ in G["procedural_modals"] for a in auxes)
            freq = any(c.lower_ in G["descriptive_adverbs"] for c in v.children) or (subj is not None and subj.lower_ in G["descriptive_subjects"])
            procedural = not freq and ((strong and (passive or subj_l in G["procedural_subjects"])) or
                                       (not passive and subj_l in G["procedural_subjects"] and v.tag_ in ("VBP", "VB") and manip))
            if passive and not strong:
                reasons.append("descriptive_passive" if not freq else "descriptive_frequency"); continue
            if not procedural:
                reasons.append("not_instruction"); continue
            if passive and not modal and not manip:
                reasons.append("descriptive_passive"); continue
            if not passive and v.tag_ in ("VBZ", "VBP") and actor_kind == "agent" and subj is not None \
                    and subj.pos_ not in ("PRON", "PROPN") and not manip:
                reasons.append("descriptive_present"); continue
            if mood == "unresolved":
                reasons.append("unresolved_mood"); continue
        # xcomp chain ('keep testing', 'begin to stir')
        chain = [v]
        while True:
            x = next((c for c in chain[-1].children if c.dep_ == "xcomp" and c.pos_ == "VERB"), None)
            if x is None:
                break
            chain.append(x)
        leaf = chain[-1]
        leaf_lem = _lemma(leaf) if leaf is not v else lem
        # objects
        objs, co_objs, tool, locs, exitc, manner = [], [], None, [], None, []
        dobj = next((c for c in leaf.children if c.dep_ in ("dobj", "obj")), None)
        if dobj is None and leaf.dep_ in ("amod", "compound", "nmod") and leaf.head.pos_ in ("NOUN", "PROPN"):
            dobj = leaf.head
        if dobj is None:
            dobj = next((c for c in leaf.children if c.dep_ == "appos" and c.pos_ in ("NOUN", "PROPN")), None)   # 'Braise the beef' (NN root + appos)
        if passive and subj is not None:
            dobj = subj
        prt_in = next((c for c in leaf.children if c.dep_ == "prt" and c.lower_ in ("in", "into", "on")), None)
        if dobj is not None:
            for n in _conj_nouns(dobj):
                if _is_time(n):
                    q = _quantity(n)
                    if q and exitc is None:
                        exitc = {"kind": "duration", "text": f"{q} {_lemma(n)}", "condition": dur_cond(q, _lemma(n)),
                                 "provenance": "implied_by_text", "rule": "EXIT-BARE-DURATION"}
                    continue
                if bad_object(n):
                    reasons.append(bad_object(n)); continue
                if n.i in promoted or (n.lower_ in lexverbs and n.lower_ not in keepnoun and n.dep_ == "conj"
                                       and not any(g.dep_ in ("det", "amod", "compound", "nummod") for g in n.children)):
                    continue   # a verb ('season', 'bake') is never an object
                if leaf_lem in I["_verbs"]["placement"] and _lemma(n) in I["_classes"]["container"] and \
                        any(c.dep_ == "prep" and c.i < n.i and c.lower_ in ("in", "into", "on") and not list(c.children) for c in leaf.children):
                    locs.append(f"in {n.text},"); exitc = exitc or {"kind": "object_location", "text": f"in {n.text}", "condition": f"object_location == {_lemma(n)}",
                                                                     "provenance": "implied_by_text", "rule": "EXIT-PLACEMENT-CONTAINER"}
                    continue   # 'Put in a stone jar': the jar is where, not what
                r = resolve_np(n)
                if r and not (r.get("object_is_unit") and r["lemma"] != "amount" and not r.get("quantity")) and r["lemma"] not in PRONOUN_OBJ:
                    objs.append(r)
        for c in leaf.children:
            if c.dep_ == "npadvmod" and _is_time(c) and _quantity(c) and exitc is None:
                q = _quantity(c)
                exitc = {"kind": "duration", "text": f"{q} {_lemma(c)}", "condition": dur_cond(q, _lemma(c)),
                         "provenance": "implied_by_text", "rule": "EXIT-BARE-DURATION"}
        for prep in [c for c in leaf.children if c.dep_ in ("prep", "agent")] + ([prt_in] if prt_in is not None else []):
            p = prep.lower_
            pobj = next((c for c in prep.children if c.dep_ == "pobj"), None)
            if prep is prt_in:
                pobj = dobj if dobj is not None else None
                if pobj is not None:
                    objs = [o for o in objs if o["lemma"] != _lemma(pobj)]
            if p in ("until", "till"):
                owner = max([c.i for c in cands if c.i < prep.i] or [v.i])
                if owner != v.i and owner != leaf.i:
                    continue   # the until-clause belongs to a later verb in the sentence
                exitc = {"kind": "until", "text": _clause_text_from(prep), "condition": _clause_text_from(prep),
                         "provenance": "explicit", "rule": "EXIT-UNTIL"}
                continue
            if pobj is None or prep.dep_ == "agent":
                continue
            if p in ("as", "like", "than"):
                manner.append(f"{p} {pobj.text}"); continue   # 'exactly as last time': comparison, not a place
            if non_location(p, pobj):
                continue
            if (leaf_lem, p) in (("cast", "on"), ("bind", "off"), ("pick", "up")) and not objs and not bad_object(pobj):
                objs.append(resolve_np(pobj)); continue
            if bad_object(pobj):
                continue
            if p in ("in", "into") and prep.i == leaf.i + 1 and leaf_lem in I["_verbs"].get("particle_in", []) and not objs \
                    and _lemma(pobj) not in I["_classes"]["container"] and not _is_time(pobj):
                objs.append(resolve_np(pobj)); continue   # 'fold in remaining sugar', 'stir in the flour'
            if p in ("with", "using") and _lemma(pobj) in I["_classes"]["container"] and leaf_lem in I["_verbs"]["placement"]:
                locs.append(f"{p} {pobj.text},"); continue
            if p == "for" and _is_time(pobj) and _quantity(pobj):
                q = _quantity(pobj)
                exitc = {"kind": "duration", "text": f"for {q} {_lemma(pobj)}", "condition": dur_cond(q, _lemma(pobj)),
                         "provenance": "explicit", "rule": "EXIT-FOR-DURATION"}
                continue
            pl = _lemma(pobj)
            if p in ("with", "using"):
                for n in _conj_nouns(pobj):
                    nl = _lemma(n)
                    if (nl in I["_classes"]["instrument"] or measure_decision(n, _DOMAIN[0])[1] == "MEAS-WITH-TOOL") and tool is None:
                        tool = {"head": n.text, "lemma": nl, "rule": "WITH-INSTRUMENT-CLASS"}
                    elif bad_object(n):
                        continue
                    elif nl in I["_classes"]["ingredient"] or _is_unit(n):
                        r = resolve_np(n); r["role"] = "with_ingredient"; co_objs.append(r)
                    else:
                        locs.append(f"with {n.text}(?),")
                continue
            if exitc is None or exitc["provenance"] not in ("explicit",):
                if p in ("into", "in", "to") and leaf_lem in I["_verbs"]["transform"] and pl not in I["_classes"]["container"] and not (_is_unit(pobj) and _quantity(pobj)):
                    exitc = exitc or {"kind": "result_state", "text": f"{p} {pobj.text}", "condition": f"object_state == {pl}",
                                      "provenance": "implied_by_text", "rule": "EXIT-RESULT-STATE"}
                    locs.append(f"{p} {pobj.text},"); continue
                if p in ("into", "onto", "in", "on", "to") and (objs or prt_in is not None) and leaf_lem in I["_verbs"]["placement"]:
                    exitc = exitc or {"kind": "object_location", "text": f"{p} {pobj.text}", "condition": f"object_location == {pl}",
                                      "provenance": "implied_by_text", "rule": "EXIT-PLACEMENT-DESTINATION"}
                    locs.append(f"{p} {pobj.text},"); continue
                if p in ("to", "into", "toward", "towards", "onto") and (not objs or leaf_lem in I["_verbs"]["motion"]):
                    who = "object_location" if objs and leaf_lem in ("carry", "bring", "take", "send", "lead") else "actor_location"
                    exitc = exitc or {"kind": who, "text": f"{p} {pobj.text}", "condition": f"{who} == {pl}",
                                      "provenance": "implied_by_text", "rule": "EXIT-GOAL-DESTINATION"}
                    locs.append(f"{p} {pobj.text},"); continue
            locs.append(f"{p} {pobj.text},")
        if exitc is None:
            nxt_v = min([c.i for c in cands if c.i > v.i] or [len(doc)])
            u = next((t for t in doc if t.lower_ in ("until", "till") and v.i < t.i < nxt_v and not in_reduced_clause(t)), None)
            if u is not None:
                exitc = {"kind": "until", "text": _clause_text_from(u), "condition": _clause_text_from(u),
                         "provenance": "explicit", "rule": "EXIT-UNTIL-SPAN"}
        if exitc is None:
            nxt_v2 = min([c.i for c in cands if c.i > v.i] or [len(doc)])
            tt = next((t for t in doc if v.i < t.i < nxt_v2 and _is_time(t) and _quantity(t) and t.dep_ in ("npadvmod", "appos", "dobj", "nsubj")
                       and not any(x.lower_ in ("every", "each", "after", "before", "last", "first") for x in doc[max(0, t.i - 4):t.i])), None)
            if tt is not None:
                q = _quantity(tt)
                exitc = {"kind": "duration", "text": f"{q} {_lemma(tt)}", "condition": dur_cond(q, _lemma(tt)),
                         "provenance": "implied_by_text", "rule": "EXIT-BARE-DURATION-SPAN"}
        if not objs and not co_objs:
            prev = next((lp for lp in reversed(loops) if lp["lemma"] == leaf_lem and lp["objects"]), None)
            if prev is not None:
                objs = [dict(o, rule="INHERIT-SAME-VERB-IN-SENTENCE") for o in prev["objects"]]   # 'beat whites ..., continue beating until ...'
        if not objs and _DOMAIN[0] in I["implied_count_noun"] and leaf_lem in I["implied_count_noun"][_DOMAIN[0]]["verbs"]:
            n = next((c for c in leaf.children if c.dep_ in ("dobj", "obj", "npadvmod", "nummod", "attr") and bad_object(c) == "bare_number_object"), None)
            if n is not None:
                spec = I["implied_count_noun"][_DOMAIN[0]]
                q = _num(n)
                if ORDINAL.match(n.text):   # '1st 18 stitches': the ordinal is a position; the count (if any) follows it
                    nx = n.doc[n.i + 1] if n.i + 1 < len(n.doc) else None
                    q = _num(nx) if nx is not None and nx.like_num and not ORDINAL.match(nx.text) else None
                objs.append({"head": f"{spec['noun']}(implied)", "lemma": spec["noun"], "quantity": q, "rule": "INV-IMPLIED-COUNT-NOUN"})
        # modality cells over the chain
        ops, links = [], []
        for t in chain:
            tl = _lemma(t) if t.pos_ == "VERB" else t.lower_
            if tl in STATIVE_EXTRA or tl in I["_verbs"]["stative_or_descriptive"]:
                continue
            ch, prov_ = channel_for(tl, modreg)
            links.append({"channel": ch, "word": tl, "provenance": prov_, "role": "action"})
            if ch in modreg["mental_markers"]["internal_channels"]:
                g, cue = mental_marker(text, modreg)
                links.append({"channel": "memory" if g == modreg["mental_markers"]["memory"] else "imagine", "word": tl,
                              "provenance": f"mental_marker:{cue}", "role": "mental_marker"})
            c = operator_cell({"channel": ch, "channel_provenance": prov_}, {"predicate": (text.split()[0].strip(",.;:") if injected and t.i == off else t.text), "verb_form": _verb_form(t)}, modreg)
            if c:
                c = c.replace(" [inferred]", "")
                if ch in modreg["mental_markers"]["internal_channels"]:
                    c += mental_marker(text, modreg)[0]
                ops.append(c + ("" if prov_ == "explicit" else f" [{prov_}]"))
        if not any(l["role"] == "action" for l in links):
            ch, prov_ = channel_for(leaf_lem, modreg)
            links.append({"channel": ch, "word": leaf_lem, "provenance": prov_, "role": "action"})
            ops.append(f"{leaf.text},{modreg['operators'][ch]}" + ("" if prov_ == "explicit" else f" [{prov_}]"))
        chans = sorted({modreg["lemma_channels"].get(_lemma(t)) for t in chain} - {None})
        prohibition_hint = bool(neg)
        # sense mentions -> TEST/EXIT steps of THIS loop (never stored alone)
        nxt_v = min([c.i for c in cands if c.i > v.i] or [len(doc)])
        prev_v = max([c.i for c in cands if c.i < v.i] or [-1])
        first_v = min(c.i for c in cands)
        mine = [m for m in senses if ((v.i <= m[0] < nxt_v) or (v.i == first_v and m[0] < v.i)) and m[0] not in state.setdefault("_used", set())]
        sense_tests = []
        for (ti, ch, w, step) in mine:
            if ti in {x.i for x in chain}:
                continue   # the action verb itself is a sense verb (look, feel): already its modality
            state["_used"].add(ti)
            in_exit = bool(exitc) and w in (exitc.get("text") or "").lower()
            op = modreg["operators"][ch]
            st_ = {"op": op, "channel": ch, "word": w, "step": f"{op} {step}", "role": "exit" if in_exit else "test"}
            links.append({"channel": ch, "word": w, "provenance": "sense_mention", "role": st_["role"]})
            if ch in modreg["mental_markers"]["internal_channels"]:
                g, cue = mental_marker(text, modreg)
                st_.update(op=op + g, step=f"{op}{g} {step}", mental_marker=g, marker_cue=cue)
                links.append({"channel": "memory" if g == modreg["mental_markers"]["memory"] else "imagine", "word": w,
                              "provenance": f"mental_marker:{cue}", "role": "mental_marker"})
            sense_tests.append(st_)
        if exitc is None and sense_tests:
            st0 = sense_tests[0]
            st0["role"] = "exit"
            exitc = {"kind": "sense_test", "text": st0["step"], "condition": f"{st0['channel']}: {st0['step']}",
                     "provenance": "implied_by_text", "rule": "EXIT-SENSE-TEST"}
        if not (objs or co_objs or tool or exitc or (mood == "imperative" and (locs or manner) and not prohibition_hint)):
            for (ti, ch, w, step) in mine:
                state["_used"].discard(ti)
            reasons.append("no_object_tool_or_exit"); continue
        for ti in {x.i for x in chain}:
            if any(m[0] == ti for m in senses):
                state.setdefault("_used", set()).add(ti)
        allobjs = objs + co_objs
        for o in allobjs:
            if quantity_range(o.get("quantity")):
                o["quantity_range"] = quantity_range(o.get("quantity"))
        ol = sorted(o["lemma"] for o in allobjs)
        prohibition = bool(neg)
        key = json.dumps(([("PROHIBIT")] if prohibition else []) + [leaf_lem, ol, tool["lemma"] if tool else "", actor_kind, chans, exitc["kind"] if exitc else "inferred_completion"],
                         ensure_ascii=False)
        def ocell(o):
            q = f" [{o['quantity']}]" if o.get("quantity") else (f" [size {o['size']}]" if o.get("size") else "")
            role = " (with)" if o.get("role") == "with_ingredient" else ""
            return f"{o['head']}{q}{role},"
        loops.append({
            "key": key, "negated": neg, "prohibition": prohibition, "lemma": leaf_lem, "object_lemma": ol[0] if ol else (tool["lemma"] if tool else ""),
            "objects": allobjs, "tool": tool, "exit": exitc, "mood": mood, "passive": passive,
            "modality_unresolved": not ops, "modality_links": links, "sense_tests": sense_tests,
            "row": {"modality": " ; ".join(ops) or "UNRESOLVED,", "actor": f"{actor_text},",
                    "action": (f"NEVER {leaf_lem}, [prohibition]" if prohibition else f"{leaf_lem},"),
                    "object": " ; ".join([ocell(o) for o in allobjs] + ([f"tool: {tool['head']},"] if tool else [])) or "UNRESOLVED,",
                    "perspective_location": " ; ".join(locs) or "UNRESOLVED,",
                    "exit": ("prohibition: the action must not occur (no exit test) [explicit]" if prohibition else
                             f"{exitc['condition']} [{exitc['provenance']}]" if exitc else f"{leaf_lem}_complete == true [inferred]")},
            "sentence": text})
    if not loops:
        return _ret("non_action" if all(r in ("stative_or_nonaction_verb", "descriptive_passive", "descriptive_present", "unresolved_mood",
                                               "not_instruction", "narrative_past", "figurative_imperative", "descriptive_frequency") for r in reasons)
                    else "no_match", [], (reasons[0] if reasons else "unknown"))
    if stats is not None:
        used = state.get("_used", set())
        stats["sense_attached"] = stats.get("sense_attached", 0) + sum(1 for m in senses if m[0] in used)
        stats["sense_unattached"] = stats.get("sense_unattached", 0) + sum(1 for m in senses if m[0] not in used)
    return "action", loops, None
