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


def _is_time(t):
    return _lemma(t) in inv()["time_units"]


def _quantity(t):
    nums = [c for c in t.children if c.dep_ == "nummod" or (c.dep_ in ("amod", "det", "quantmod") and c.text.lower() in inv()["number_words"])]
    return " ".join(_num(n) for n in nums) if nums else None


def resolve_np(head):
    """-> {head, lemma, quantity, unit, span_text} applying the unit invariant."""
    if head is None:
        return None
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
    return "*" in lst or _lemma(pobj) in lst


def sense_mentions(doc):
    """-> [(token_index, channel, cue_word, step_text)] for every sense word in the sentence."""
    out = []
    cues = {k: v for k, v in inv()["sense_cues"].items() if not k.startswith("_")}
    for t in doc:
        w = t.lower_
        if t.dep_ in ("amod", "compound", "nmod") and t.head.pos_ in ("NOUN", "PROPN"):
            continue   # attributive ('boiling water', 'cold milk', 'soft-shelled clams'): describes an ingredient, not a sense test
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
    while stack:
        v = stack.pop()
        for c in v.children:
            if (c.dep_ == "conj" or (c.dep_ == "parataxis" and injected) or (c.dep_ == "ccomp" and injected and any(g.dep_ == "nsubj" and g.i == 0 for g in c.children))) \
                    and verbish(c) and c not in cands:
                cands.append(c); stack.append(c)
    if not cands:
        return _ret("non_action", [], "no_action_verb")
    cands.sort(key=lambda t: t.i)
    loops, reasons, state = [], [], {}
    for v in cands:
        lem = v.lower_ if v.pos_ != "VERB" else _lemma(v)
        subj = next((c for c in v.children if c.dep_ in ("nsubj", "nsubjpass")), None)
        passive = any(c.dep_ in ("auxpass", "nsubjpass") for c in v.children)
        auxes = [c for c in v.children if c.dep_ in ("aux", "auxpass")]
        modal = any(a.lower_ in MODALS for a in auxes)
        neg = any(c.dep_ == "neg" for c in v.children)
        # carry-over along coordination: inherit only when the conjunct has no own subject AND matches form
        parent = state.get(v.head.i) if v.dep_ == "conj" else None
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
            if parent["mood"] == "imperative" and (v.tag_ in ("VB", "VBP", "NN", "JJ") or (injected and lem in lexverbs and not auxes)):
                mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
            elif parent["passive"] and v.tag_ == "VBN":
                mood, actor_kind, actor_text, passive = "indicative", parent["actor_kind"], parent["actor_text"], True
                modal = parent["modal"]
            elif parent["mood"] == "indicative" and not parent["passive"]:
                mood, actor_kind, actor_text = "indicative", parent["actor_kind"], parent["actor_text"]
            else:
                mood, actor_kind, actor_text = "unresolved", "unresolved", "UNRESOLVED"
        elif (v.tag_ == "VB" or (injected and (v.tag_ == "VBP" or (lem in lexverbs and v.tag_ in ("VBZ", "VBD", "NN"))))) and not passive and not auxes:   # base-form verb with no subject = imperative
            mood, actor_kind, actor_text = "imperative", "implied_you", "you(implied)"
        else:
            mood, actor_kind, actor_text = "unresolved", "unresolved", "UNRESOLVED"
        state[v.i] = {"mood": mood, "passive": passive, "actor_kind": actor_kind, "actor_text": actor_text, "modal": modal}
        if lem in STATIVE_EXTRA or lem in I["_verbs"]["stative_or_descriptive"]:
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
            procedural = (strong and (passive or subj_l in G["procedural_subjects"])) or \
                         (passive and not modal and manip and actor_kind == "implied_agent_passive") or \
                         (not passive and subj_l in G["procedural_subjects"] and v.tag_ in ("VBP", "VB") and manip)
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
        objs, co_objs, tool, locs, exitc = [], [], None, [], None
        dobj = next((c for c in leaf.children if c.dep_ in ("dobj", "obj")), None)
        if passive and subj is not None:
            dobj = subj
        prt_in = next((c for c in leaf.children if c.dep_ == "prt" and c.lower_ in ("in", "into", "on")), None)
        if dobj is not None:
            for n in _conj_nouns(dobj):
                if _is_time(n):
                    q = _quantity(n)
                    if q and exitc is None:
                        exitc = {"kind": "duration", "text": f"{q} {_lemma(n)}", "condition": f"elapsed >= {q} {_lemma(n)}",
                                 "provenance": "implied_by_text", "rule": "EXIT-BARE-DURATION"}
                    continue
                if bad_object(n):
                    reasons.append(bad_object(n)); continue
                r = resolve_np(n)
                if r and not (r.get("object_is_unit") and r["lemma"] != "amount" and not r.get("quantity")) and r["lemma"] not in PRONOUN_OBJ:
                    objs.append(r)
        for c in leaf.children:
            if c.dep_ == "npadvmod" and _is_time(c) and _quantity(c) and exitc is None:
                q = _quantity(c)
                exitc = {"kind": "duration", "text": f"{q} {_lemma(c)}", "condition": f"elapsed >= {q} {_lemma(c)}",
                         "provenance": "implied_by_text", "rule": "EXIT-BARE-DURATION"}
        for prep in [c for c in leaf.children if c.dep_ in ("prep", "agent")] + ([prt_in] if prt_in is not None else []):
            p = prep.lower_
            pobj = next((c for c in prep.children if c.dep_ == "pobj"), None)
            if prep is prt_in:
                pobj = dobj if dobj is not None else None
                if pobj is not None:
                    objs = [o for o in objs if o["lemma"] != _lemma(pobj)]
            if p in ("until", "till"):
                exitc = {"kind": "until", "text": _clause_text_from(prep), "condition": _clause_text_from(prep),
                         "provenance": "explicit", "rule": "EXIT-UNTIL"}
                continue
            if pobj is None or prep.dep_ == "agent":
                continue
            if non_location(p, pobj):
                continue
            if (leaf_lem, p) in (("cast", "on"), ("bind", "off"), ("pick", "up")) and not objs and not bad_object(pobj):
                objs.append(resolve_np(pobj)); continue
            if bad_object(pobj):
                continue
            if p == "for" and _is_time(pobj) and _quantity(pobj):
                q = _quantity(pobj)
                exitc = {"kind": "duration", "text": f"for {q} {_lemma(pobj)}", "condition": f"elapsed >= {q} {_lemma(pobj)}",
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
            u = next((t for t in doc if t.lower_ in ("until", "till") and v.i < t.i < nxt_v), None)
            if u is not None:
                exitc = {"kind": "until", "text": _clause_text_from(u), "condition": _clause_text_from(u),
                         "provenance": "explicit", "rule": "EXIT-UNTIL-SPAN"}
        if not objs and _DOMAIN[0] in I["implied_count_noun"] and leaf_lem in I["implied_count_noun"][_DOMAIN[0]]["verbs"]:
            n = next((c for c in leaf.children if c.dep_ in ("dobj", "obj", "npadvmod", "nummod", "attr") and bad_object(c) == "bare_number_object"), None)
            if n is not None:
                spec = I["implied_count_noun"][_DOMAIN[0]]
                objs.append({"head": f"{spec['noun']}(implied)", "lemma": spec["noun"], "quantity": _num(n), "rule": "INV-IMPLIED-COUNT-NOUN"})
        # modality cells over the chain
        ops, links = [], []
        for t in chain:
            tl = _lemma(t) if t.pos_ == "VERB" else t.lower_
            if tl in STATIVE_EXTRA or tl in I["_verbs"]["stative_or_descriptive"]:
                continue
            ch, prov_ = channel_for(tl, modreg)
            links.append({"channel": ch, "word": tl, "provenance": prov_, "role": "action"})
            c = operator_cell({"channel": ch, "channel_provenance": prov_}, {"predicate": (text.split()[0].strip(",.;:") if injected and t.i == off else t.text), "verb_form": _verb_form(t)}, modreg)
            if c:
                ops.append(c.replace(" [inferred]", "") + ("" if prov_ == "explicit" else f" [{prov_}]"))
        chans = sorted({modreg["lemma_channels"].get(_lemma(t)) for t in chain} - {None})
        # sense mentions -> TEST/EXIT steps of THIS loop (never stored alone)
        nxt_v = min([c.i for c in cands if c.i > v.i] or [len(doc)])
        prev_v = max([c.i for c in cands if c.i < v.i] or [-1])
        mine = [m for m in senses if (prev_v < m[0] < nxt_v or (m[0] == v.i)) and m[0] not in state.setdefault("_used", set())]
        sense_tests = []
        for (ti, ch, w, step) in mine:
            if ti in {x.i for x in chain}:
                continue   # the action verb itself is a sense verb (look, feel): already its modality
            state["_used"].add(ti)
            in_exit = bool(exitc) and w in (exitc.get("text") or "").lower()
            sense_tests.append({"op": modreg["operators"][ch], "channel": ch, "word": w, "step": f"{modreg['operators'][ch]} {step}",
                                "role": "exit" if in_exit else "test"})
            links.append({"channel": ch, "word": w, "provenance": "sense_mention", "role": "exit" if in_exit else "test"})
        if exitc is None and sense_tests:
            st0 = sense_tests[0]
            st0["role"] = "exit"
            exitc = {"kind": "sense_test", "text": st0["step"], "condition": f"{st0['channel']}: {st0['step']}",
                     "provenance": "implied_by_text", "rule": "EXIT-SENSE-TEST"}
        if not (objs or co_objs or tool or exitc):
            for (ti, ch, w, step) in mine:
                state["_used"].discard(ti)
            reasons.append("no_object_tool_or_exit"); continue
        for ti in {x.i for x in chain}:
            if any(m[0] == ti for m in senses):
                state.setdefault("_used", set()).add(ti)
        allobjs = objs + co_objs
        ol = sorted(o["lemma"] for o in allobjs)
        key = json.dumps([leaf_lem, ol, tool["lemma"] if tool else "", actor_kind, chans, exitc["kind"] if exitc else "inferred_completion"],
                         ensure_ascii=False)
        def ocell(o):
            q = f" [{o['quantity']}]" if o.get("quantity") else ""
            role = " (with)" if o.get("role") == "with_ingredient" else ""
            return f"{o['head']}{q}{role},"
        loops.append({
            "key": key, "negated": neg, "lemma": leaf_lem, "object_lemma": ol[0] if ol else (tool["lemma"] if tool else ""),
            "objects": allobjs, "tool": tool, "exit": exitc, "mood": mood, "passive": passive,
            "modality_unresolved": not ops, "modality_links": links, "sense_tests": sense_tests,
            "row": {"modality": " ; ".join(ops) or "UNRESOLVED,", "actor": f"{actor_text},",
                    "action": f"{leaf_lem},",
                    "object": " ; ".join([ocell(o) for o in allobjs] + ([f"tool: {tool['head']},"] if tool else [])) or "UNRESOLVED,",
                    "perspective_location": " ; ".join(locs) or "UNRESOLVED,",
                    "exit": (f"{exitc['condition']} [{exitc['provenance']}]" if exitc else f"{leaf_lem}_complete == true [inferred]")},
            "sentence": text})
    if not loops:
        return _ret("non_action" if all(r in ("stative_or_nonaction_verb", "descriptive_passive", "descriptive_present", "unresolved_mood",
                                               "not_instruction", "narrative_past", "figurative_imperative") for r in reasons)
                    else "no_match", [], (reasons[0] if reasons else "unknown"))
    if stats is not None:
        used = state.get("_used", set())
        stats["sense_attached"] = stats.get("sense_attached", 0) + sum(1 for m in senses if m[0] in used)
        stats["sense_unattached"] = stats.get("sense_unattached", 0) + sum(1 for m in senses if m[0] not in used)
    return "action", loops, None
