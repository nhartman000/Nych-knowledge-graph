"""Pluggable parser. Interface: Parser.tag(tokens, sent_is_first) -> tokens with
pos/tag/lemma/morph. Default RuleParser is offline and deterministic. SpacyParser
is optional (used only if spaCy + en_core_web_sm import); it must be versioned in
the run manifest. Both feed the SAME downstream rules; nothing here calls an LLM.

POS set: PUNCT DET PRON POSS ADP CCONJ AUX PART ADV NUM ADJ NOUN PROPN VERB
Verb tags: VB (base) VBD (past) VBN (past participle) VBG (-ing) VBZ/VBP (present).
"""
from __future__ import annotations
import functools, gzip
from ..config import SHARED, registry


@functools.lru_cache(maxsize=1)
def dictionary() -> frozenset:
    with gzip.open(SHARED / "vendor" / "dictionary_words.txt.gz", "rt", encoding="utf-8") as f:
        return frozenset(l.strip() for l in f if l.strip())


@functools.lru_cache(maxsize=1)
def _lex():
    L = registry("lexicon")
    return L, set(L["verbs"]), L["irregular_verbs"]


def verb_lemma(word: str):
    """Return (lemma, tag_hint, rule_id) or None if not verb-like.
    Lexicon first; morphology rules second; never a bare '-ed' strip (old 'lov' bug)."""
    w = word.lower()
    L, verbs, irr = _lex()
    if w in irr:
        return irr[w], "VBD", "LEM-IRREG"
    if w in verbs:
        return w, "VB", "LEM-BASE"
    for suf, tag in (("ing", "VBG"), ("ed", "VBD"), ("es", "VBZ"), ("s", "VBZ")):
        if w.endswith(suf) and len(w) > len(suf) + 1:
            stem = w[: -len(suf)]
            cands = [stem, stem + "e"]
            if len(stem) > 2 and stem[-1] == stem[-2]:
                cands.append(stem[:-1])
            if suf == "ed" and stem.endswith("i"):
                cands.append(stem[:-1] + "y")
            if suf == "ing" and stem.endswith("y"):
                cands.append(stem[:-1] + "ie")
            for c in cands:
                if c in verbs:
                    return c, tag, "LEM-LEXICON"
            if suf in ("ed", "ing"):
                D = dictionary()
                for c in ([stem[:-1]] if len(stem) > 2 and stem[-1] == stem[-2] else []) + [stem + "e", stem]:
                    if c in D and len(c) > 2:
                        return c, tag, "LEM-DICTIONARY"
                # unknown verb: rule guess. English stems never end in v/c(not ck)/z/u -> restore 'e'
                if suf == "ed" and len(stem) > 2 and stem.endswith("i") and stem[-2] not in "aeiou":
                    return stem[:-1] + "y", tag, "LEM-RULE-IED"
                if stem[-1] in "vzu" or (stem.endswith("c") and not stem.endswith("ck")):
                    return stem + "e", tag, "LEM-RULE-E"
                if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
                    return stem[:-1], tag, "LEM-RULE-UNDOUBLE"
                return stem, tag, "LEM-RULE-STEM"
    return None


def noun_lemma(word: str) -> str:
    w = word.lower()
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if len(w) > 2 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


class RuleParser:
    name = "rule"
    version = "nych3-rule-1"

    def tag(self, tokens):
        L, verbs, irr = _lex()
        dets, prons, poss = set(L["determiners"]), L["pronouns"], L["possessives"]
        preps, conj, aux = set(L["prepositions"]), set(L["conjunctions"]), L["auxiliaries"]
        advs, nums, adjs = set(L["adverbs"]), set(L["numerals"]), set(L["adjectives"])
        openers, timen = set(L["sentence_openers"]), set(L["time_nouns"])
        out = []
        words = [t["text"] for t in tokens]
        first_word = next((i for i, w in enumerate(words) if w[:1].isalpha()), 0)
        for i, t in enumerate(tokens):
            w, lw = t["text"], t["text"].lower()
            prev = out[-1] if out else None
            nxt = words[i + 1].lower() if i + 1 < len(words) else ""
            r = dict(t, lemma=lw, tag=None, morph={}, rule="POS-DEFAULT")
            if not w[:1].isalnum():
                r.update(pos="PUNCT")
            elif w[:1].isdigit():
                r.update(pos="NUM", rule="POS-DIGIT")
            elif lw in poss and not (lw == "her" and (not nxt or nxt in preps or not nxt[:1].isalpha())):
                r.update(pos="POSS", morph=poss[lw], rule="POS-CLOSED")
            elif lw in prons:
                r.update(pos="PRON", morph=prons[lw], rule="POS-CLOSED")
            elif lw in nums:
                r.update(pos="NUM", rule="POS-CLOSED")
            elif lw in dets:
                r.update(pos="DET", rule="POS-CLOSED")
            elif lw in aux:
                r.update(pos="AUX", lemma=aux[lw], rule="POS-CLOSED")
            elif lw == "to" and verb_lemma(nxt) and nxt in verbs:
                r.update(pos="PART", rule="POS-TO-INF")
            elif lw in preps:
                r.update(pos="ADP", rule="POS-CLOSED")
            elif lw in set(L.get("function_words", [])):
                r.update(pos="SCONJ", rule="POS-CLOSED")
            elif lw in conj:
                r.update(pos="CCONJ", rule="POS-CLOSED")
            elif lw in advs:
                r.update(pos="ADV", rule="POS-CLOSED")
            elif w[:1].isupper() and i != first_word:
                r.update(pos="PROPN", lemma=w, rule="POS-CAP-MIDSENT")
            elif lw in adjs:
                r.update(pos="ADJ", rule="POS-ADJ-LIST")
            elif (i == first_word or (prev is not None and prev["text"] in (";", ":"))) and lw in verbs and lw not in set(L.get("not_imperative_initial", [])) and (i + 1 >= len(words) or words[i + 1].lower() not in prons):
                # sentence-initial base verb = imperative candidate (beats irregular homographs: 'Saw the board')
                r.update(pos="VERB", lemma=lw, tag="VB", rule="POS-INITIAL-BASE-VERB")
            else:
                vl = verb_lemma(w)
                prev_pos = prev["pos"] if prev else None
                after_det = prev_pos in ("DET", "POSS", "ADJ", "NUM", "ADP")
                if vl and not (after_det and vl[1] in ("VB", "VBZ")):
                    lemma, tag, rule = vl
                    if tag == "VBD" and prev and prev["pos"] == "AUX" and prev["lemma"] in ("have", "be"):
                        tag = "VBN"
                    if tag == "VB" and prev and prev["pos"] in ("PRON", "PROPN", "NOUN") and lw == lemma:
                        tag = "VBP"
                    if tag in ("VBD", "VBN") and after_det:
                        r.update(pos="ADJ", rule="POS-PARTICIPLE-AFTER-DET")
                    elif tag == "VBZ" and after_det:
                        r.update(pos="NOUN", lemma=noun_lemma(w), rule="POS-NOUN-AFTER-DET")
                    else:
                        r.update(pos="VERB", lemma=lemma, tag=tag, rule=rule)
                elif lw.endswith("ly") and len(lw) > 4:
                    r.update(pos="ADV", rule="POS-LY")
                else:
                    r.update(pos="NOUN", lemma=noun_lemma(w), rule="POS-NOUN-DEFAULT")
            if r["pos"] == "NOUN" and r["lemma"] in timen:
                r["morph"] = {"time_noun": True}
            out.append(r)
        # 'Chisel boards are ...': an initial base verb followed by NOUN + finite verb is a noun-phrase subject.
        for i in range(len(out) - 2):
            if out[i]["rule"] == "POS-INITIAL-BASE-VERB" and out[i + 1]["pos"] == "NOUN" and \
                    (out[i + 2]["pos"] == "AUX" or out[i + 2].get("tag") in ("VBZ", "VBD", "VBP")):
                out[i].update(pos="NOUN", tag=None, lemma=noun_lemma(out[i]["text"]), rule="POS-INITIAL-NOUN-COMPOUND-SUBJECT")
        # Sentence-initial capitalized word: name heuristic (fixes 'Peter unprotected').
        if out and out[first_word]["pos"] not in ("PUNCT",):
            f = out[first_word]
            lw = f["text"].lower()
            nxt = out[first_word + 1] if first_word + 1 < len(out) else None
            if f["text"][:1].isupper() and lw not in openers and f["pos"] in ("NOUN", "VERB", "ADJ") and f["rule"] != "POS-INITIAL-BASE-VERB":
                undefined = lw not in dictionary()
                followed_by_verb = nxt is not None and (nxt["pos"] in ("VERB", "AUX"))
                plural_common = lw.endswith("s") and noun_lemma(lw) in dictionary()
                if undefined or (followed_by_verb and not plural_common):
                    f.update(pos="PROPN", lemma=f["text"], tag=None,
                             rule="NAME-UNDEFINED" if undefined else "NAME-INITIAL-SUBJECT-BEFORE-VERB")
        return out


class SpacyParser:
    """Optional adapter. Maps spaCy UD tags onto the NYCH3 POS set."""
    name = "spacy"

    def __init__(self, model: str = "en_core_web_sm"):
        import spacy  # optional dependency
        self.nlp = spacy.load(model, disable=["ner"])
        self.version = f"spacy-{spacy.__version__}/{model}-{self.nlp.meta.get('version')}"

    def tag(self, tokens):
        from spacy.tokens import Doc
        doc = self.nlp(Doc(self.nlp.vocab, words=[t["text"] for t in tokens]))
        out = []
        for t, s in zip(tokens, doc):
            pos = {"PRON": "POSS" if s.tag_ == "PRP$" else "PRON", "SCONJ": "ADP", "SYM": "PUNCT"}.get(s.pos_, s.pos_)
            tag = s.tag_ if s.tag_.startswith("VB") else None
            if pos == "AUX" and s.dep_ == "ROOT":
                pos = "VERB"
            lem = s.text if pos == "PROPN" else s.lemma_.lower()
            L = _lex()[0]
            low = s.text.lower()
            morph = {}
            if pos == "POSS" and low in L["possessives"]:
                morph = L["possessives"][low]
            elif pos == "PRON" and low in L["pronouns"]:
                morph = L["pronouns"][low]
            elif pos == "NOUN" and lem in L["time_nouns"]:
                morph = {"time_noun": True}
            if pos == "NUM" or (pos == "DET" and low in L["numerals"]):
                pos = "NUM"
            out.append(dict(t, pos=pos, tag=tag, lemma=lem, morph=morph,
                            rule=("NAME-SPACY-PROPN" if pos == "PROPN" else f"SPACY-{s.tag_}")))
        return out


def get_parser(name: str = "rule"):
    if name == "rule":
        return RuleParser()
    if name == "spacy":
        return SpacyParser()
    if name == "auto":
        try:
            return SpacyParser()
        except Exception:
            return RuleParser()
    raise ValueError(f"unknown parser {name!r}")
