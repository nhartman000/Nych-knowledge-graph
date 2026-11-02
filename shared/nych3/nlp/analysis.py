"""Deterministic analysis for stages 03 (scope/attribution), 04 (temporal) and
05 (semantics). Pure functions over the stage-02 structure + parser tags.
Rule ids are recorded on every output so each inference is traceable."""
from __future__ import annotations
from ..config import registry
from ..provenance import prov

# --------------------------------------------------------------------------- helpers

def _L():
    return registry("lexicon")


def iter_sentences(structure):
    for p in structure["pages"]:
        for s in p["sentences"]:
            yield s


def ref(sent, a, b=None):
    """Span reference for tokens a..b (inclusive) of a sentence."""
    b = a if b is None else b
    t = sent["tokens"]
    return {"page_idx": sent["page_idx"], "sent_idx": sent["sent_idx"], "sent_id": sent["sent_id"],
            "tok_start": a, "tok_end": b, "char_start": t[a]["char_start"], "char_end": t[b]["char_end"]}


def _in_dialogue(sent, tok):
    return any(d["char_start"] <= tok["char_start"] < d["char_end"] for d in sent["dialogue_spans"])


def clauses(sent):
    """Split a sentence into clauses at ';' or at a coordinator directly followed by a
    pronoun/proper-name subject and a verb. Returns [(start, end_exclusive)]."""
    T = sent["tokens"]
    cuts, start = [], 0
    for i, t in enumerate(T):
        if t["text"] == ";":
            cuts.append((start, i)); start = i + 1
        elif t["pos"] == "CCONJ" and ((i + 2 < len(T) and T[i + 1]["pos"] in ("PRON", "PROPN") and T[i + 2]["pos"] in ("VERB", "AUX"))
                                      or (i + 1 < len(T) and T[i + 1]["pos"] == "VERB" and T[i + 1].get("tag") == "VB")):
            end = i - 1 if i > 0 and T[i - 1]["text"] == "," else i
            cuts.append((start, end)); start = i + 1
    cuts.append((start, len(T)))
    return [c for c in cuts if any(T[k]["pos"] != "PUNCT" for k in range(*c))]


# --------------------------------------------------------------------------- stage 03

def scope_attribution(structure, tagged, prompt: str = ""):
    """tagged: {sent_id: [tokens with pos]}. Returns entities, mentions, coref, narrator, focalizer, speakers."""
    entities, mentions, chains, speakers = [], [], [], []
    name_index = {}
    first_person_outside = False
    subj_counts = {}
    for sent in iter_sentences(structure):
        T = tagged[sent["sent_id"]]
        sent = dict(sent, tokens=T)
        i = 0
        while i < len(T):
            t = T[i]
            if t["pos"] == "PROPN":
                j = i
                while j + 1 < len(T) and T[j + 1]["pos"] == "PROPN":
                    j += 1
                name = " ".join(x["text"] for x in T[i:j + 1])
                nxt = T[j + 1] if j + 1 < len(T) else None
                if name not in name_index:
                    eid = f"E{len(entities)}"
                    is_person = t["rule"].startswith("NAME") or (nxt is not None and nxt["pos"] in ("VERB", "AUX"))
                    entities.append({"entity_id": eid, "name": name, "type": "person" if is_person else "named",
                                     "protected": True, "gender": None, "gender_evidence": [],
                                     **prov(t["rule"], "explicit" if is_person else "inferred")})
                    name_index[name] = eid
                eid = name_index[name]
                m = {"mention_id": f"M{len(mentions)}", "entity_id": eid, "text": name, "kind": "name",
                     "span": ref(sent, i, j), **prov("COREF-NAME", "explicit")}
                mentions.append(m)
                if nxt is not None and nxt["pos"] in ("VERB", "AUX"):
                    subj_counts[eid] = subj_counts.get(eid, 0) + 1
                i = j + 1
                continue
            if t["pos"] in ("PRON", "POSS"):
                morph = t["morph"]
                if morph.get("person") == 1 and not _in_dialogue(sent, t):
                    first_person_outside = True
                cands = [e for e in entities if morph.get("person") == 3 and morph.get("number") == "sg"
                         and morph.get("gender") in ("m", "f") and e["type"] == "person"
                         and e["gender"] in (None, morph["gender"])]
                m = {"mention_id": f"M{len(mentions)}", "text": t["text"], "kind": "possessive" if t["pos"] == "POSS" else "pronoun",
                     "span": ref(sent, i)}
                if len(cands) == 1:
                    e = cands[0]
                    m.update(entity_id=e["entity_id"], **prov("COREF-R1-SINGLE-COMPATIBLE-PERSON", "inferred", status="inferred"))
                    e["gender_evidence"].append({"pronoun": t["text"].lower(), "mention_id": m["mention_id"]})
                    if t["pos"] == "PRON" and i + 1 < len(T) and T[i + 1]["pos"] in ("VERB", "AUX"):
                        subj_counts[e["entity_id"]] = subj_counts.get(e["entity_id"], 0) + 1
                elif len(cands) > 1:
                    m.update(entity_id=None, **prov("COREF-R2-AMBIGUOUS", "inferred", status="inferred",
                                                     alternatives=[c["entity_id"] for c in cands]))
                else:
                    m.update(entity_id=None, **prov("COREF-R0-NO-ANTECEDENT", "inferred", status="inferred"))
                mentions.append(m)
            i += 1
        for d in sent["dialogue_spans"]:
            speakers.append({"span": d, "speaker_entity": None, "status": "unresolved",
                             **prov("DIALOGUE-SPEAKER-UNRESOLVED", "inferred", status="explicit_dialogue")})
    for e in entities:
        chain = [m["mention_id"] for m in mentions if m.get("entity_id") == e["entity_id"]]
        chains.append({"entity_id": e["entity_id"], "mentions": chain})
    narr_person = "first" if first_person_outside else "third"
    narrator = {"narrative_person": narr_person, "narrator": "homodiegetic_or_unresolved" if first_person_outside else "external_narrator",
                **prov("NARR-PRONOUN-PERSON", "inferred", status="inferred")}
    label = None
    for lab in ("first person", "second person", "third person"):
        if lab in (prompt or "").lower():
            label = lab.split()[0]
    narrator["user_label"] = label
    narrator["user_label_differs"] = bool(label and label != narr_person)
    foc = max(subj_counts, key=lambda k: (subj_counts[k], -int(k[1:]))) if subj_counts else None
    focalizer = {"entity_id": foc, "basis": "most frequent grammatical subject (character-centred viewpoint is distinct from grammatical person)",
                 **prov("FOCAL-MOST-SUBJECT", "inferred", status="inferred")}
    return {"entities": entities, "mentions": mentions, "coref_chains": chains, "narrator": narrator,
            "focalizer": focalizer, "speakers": speakers}


# --------------------------------------------------------------------------- stage 04

PAST_AUX = {"was", "were", "had", "did"}
PRES_AUX = {"is", "are", "am", "has", "have", "does", "do"}
MODALS = {"could", "should", "might", "may", "must", "can", "would"}


def temporal(structure, tagged):
    L = _L()
    catenative = set(L["catenative_verbs"]); stative = set(L["stative_affective_verbs"])
    events, anchors, relations, clause_recs = [], [], [], []
    for sent in iter_sentences(structure):
        T = tagged[sent["sent_id"]]
        s = dict(sent, tokens=T)
        for ci, (a, b) in enumerate(clauses(s)):
            cid = f"{sent['sent_id']}c{ci}"
            # anchor: leading [NUM|DET]? ADJ* time-noun before subject
            anchor, k = None, a
            while k < b and T[k]["pos"] in ("NUM", "DET", "ADJ"):
                k += 1
            if k < b and T[k]["pos"] == "NOUN" and T[k]["morph"].get("time_noun") and k + 1 < b:
                anchor = (a, k)
                body = k + 1 + (1 if k + 1 < b and T[k + 1]["text"] == "," else 0)
            else:
                body = a
            subord = None
            if body < b and T[body]["text"].lower() in set(L.get("subordinators", [])):
                comma = next((x for x in range(body, b) if T[x]["text"] == ","), None)
                if comma is not None:
                    subord = (body, comma - 1); body = comma + 1
            lead = body
            while lead < b and (T[lead]["pos"] in ("ADV", "CCONJ") or T[lead]["text"] in (",", ":")):
                lead += 1
            # verb group
            v = next((i for i in range(body, b) if T[i]["pos"] in ("VERB", "AUX")), None)
            if v is None:
                clause_recs.append({"clause_id": cid, "span": ref(s, a, b - 1), "events": []})
                continue
            auxes, i = [], v
            while i < b and (T[i]["pos"] == "AUX" or (auxes and T[i]["text"].lower() in ("not", "never") and i + 1 < b
                                                       and T[i + 1]["pos"] in ("AUX", "VERB"))):
                if T[i]["pos"] == "AUX":
                    auxes.append(T[i])
                i += 1
            main = i if i < b and T[i]["pos"] == "VERB" else (v + len(auxes) - 1)
            mt = T[main]
            first = auxes[0]["text"].lower() if auxes else None
            if first in ("will", "shall"):
                tense = "future"
            elif first in MODALS:
                tense = "modal"
            elif first in PAST_AUX or (not auxes and mt.get("tag") in ("VBD", "VBN")):
                tense = "past"
            elif first in PRES_AUX or (not auxes and mt.get("tag") in ("VBZ", "VBP")):
                tense = "present"
            else:
                tense = "unresolved"
            aux_lem = [x["lemma"] for x in auxes]
            if "have" in aux_lem and mt.get("tag") == "VBN":
                aspect = "perfect"
            elif "be" in aux_lem and mt.get("tag") == "VBG":
                aspect = "progressive"
            else:
                aspect = "simple"
            habit_q = any(T[x]["text"].lower() in ("every", "each") for x in range(a, b)) or \
                any(T[x]["text"].lower() in ("always", "often", "usually", "sometimes") for x in range(a, b))
            voice = "passive" if (auxes and auxes[-1]["lemma"] == "be" and mt.get("tag") in ("VBN", "VBD") and main != v) else "active"
            if voice == "passive" and mt.get("tag") == "VBD":
                mt["tag"] = "VBN"
            mood = "indicative"
            if v == lead and not auxes and mt.get("tag") == "VB":
                mood, tense = "imperative", "none_imperative"
            elif v == lead and auxes and auxes[0]["lemma"] == "do" and mt.get("tag") == "VB":
                mood, tense = "imperative", "none_imperative"
            eid = f"ev{len(events)}"
            matrix = {"mood": mood, "voice": voice, "subordinate_lead": ref(s, *subord) if subord else None,"event_id": eid, "clause_id": cid, "predicate": mt["text"], "lemma": mt["lemma"], "tok": main,
                      "span": ref(s, v, main), "tense": tense, "aspect": aspect, "finite": True, "parent_event": None,
                      "verb_form": mt.get("tag") if not auxes else "+".join([x["text"].lower() for x in auxes] + [mt.get("tag") or "?"]),
                      "time_anchor": None, **prov("TENSE-FINITE-VERB-GROUP", "explicit")}
            events.append(matrix)
            chain = [matrix]
            j = main + 1
            # nested non-finite complements: catenative + gerund, or to + base
            while j < b:
                cur = chain[-1]
                if T[j]["pos"] == "VERB" and T[j].get("tag") == "VBG" and cur["lemma"] in catenative:
                    form, k2 = "gerund", j
                elif T[j]["pos"] == "PART" and j + 1 < b and T[j + 1]["pos"] == "VERB":
                    form, k2 = "infinitive", j + 1
                else:
                    break
                nid = f"ev{len(events)}"
                nt = T[k2]
                nested = {"event_id": nid, "clause_id": cid, "predicate": nt["text"] if form == "gerund" else f"to {nt['text']}",
                          "lemma": nt["lemma"], "tok": k2, "span": ref(s, j, k2), "tense": None, "finite": False,
                          "governed_tense": matrix["tense"], "aspect": "ongoing_activity_nonfinite" if form == "gerund" else "nonfinite",
                          "verb_form": "VBG" if form == "gerund" else "TO+VB", "form": form, "parent_event": cur["event_id"],
                          "time_anchor": None,
                          "note": "non-finite complement: time is governed by the matrix clause; it does NOT create present tense",
                          **prov("TENSE-NESTED-GOVERNED", "explicit")}
                events.append(nested); chain.append(nested)
                j = k2 + 1
            matrix["end_tok"] = j
            if anchor:
                an = {"anchor_id": f"ta{len(anchors)}", "text": " ".join(T[x]["text"] for x in range(anchor[0], anchor[1] + 1)),
                      "span": ref(s, anchor[0], anchor[1]), "scoped_to_events": [e["event_id"] for e in chain],
                      "scope": "clause", "propagates_backward": False, "kind": "habitual_quantified" if habit_q else "episodic",
                      **prov("ANCHOR-LEADING-TIME-NP", "explicit")}
                anchors.append(an)
                for e in chain:
                    e["time_anchor"] = an["anchor_id"]
            blanket = tense == "past" and not anchor and (mt["lemma"] in stative or habit_q)
            if blanket:
                matrix["aspect"] = "habitual_or_stative"
            matrix["blanket_statement"] = blanket
            matrix["time_anchor_note"] = None if anchor else "no time anchor in this clause; none is borrowed from other clauses"
            clause_recs.append({"clause_id": cid, "span": ref(s, a, b - 1), "events": [e["event_id"] for e in chain],
                                "body_start": body, "end": b})
    # event ordering between consecutive matrix events
    mats = [e for e in events if e["parent_event"] is None]
    for x, y in zip(mats, mats[1:]):
        if x.get("blanket_statement") or y.get("blanket_statement"):
            rel, rule = "background_of", "ORDER-HABITUAL-BACKGROUND"
        else:
            rel, rule = "precedes", "ORDER-NARRATIVE-SEQUENCE"
        relations.append({"from": x["event_id"], "to": y["event_id"], "relation": rel, **prov(rule, "inferred", status="inferred")})
    return {"events": events, "time_anchors": anchors, "temporal_relations": relations, "clauses": clause_recs}


# --------------------------------------------------------------------------- stage 05

def _np(T, j, b):
    """Noun phrase starting at j. Returns dict or None."""
    k, det, possessor = j, None, None
    while k < b and T[k]["pos"] in ("DET", "POSS", "NUM", "ADJ"):
        if T[k]["pos"] == "DET":
            det = T[k]["text"].lower()
        if T[k]["pos"] == "POSS":
            possessor = k
        k += 1
    if k < b and T[k]["pos"] in ("NOUN", "PROPN", "PRON"):
        while k + 1 < b and T[k + 1]["pos"] in ("NOUN", "PROPN") and T[k]["pos"] != "PRON":
            k += 1
        return {"start": j, "head": k, "end": k, "det": det, "possessor_tok": possessor}
    if k > j and T[k - 1]["pos"] == "NUM":
        return {"start": j, "head": k - 1, "end": k - 1, "det": det, "possessor_tok": possessor, "quantity_only": True}
    return None


def semantics(structure, tagged, scope, temp):
    L = _L()
    channels = registry("modality")
    spatial = set(L["spatial_relational_preps"]); vprep = L["verb_attached_preps"]; objprep = L["verb_object_preps"]
    quant = {"every", "each", "some", "no", "all", "any"}
    mention_at = {(m["span"]["sent_id"], m["span"]["tok_start"]): m for m in scope["mentions"]}
    sents = {s["sent_id"]: dict(s, tokens=tagged[s["sent_id"]]) for s in iter_sentences(structure)}
    ev_by_clause = {}
    for e in temp["events"]:
        ev_by_clause.setdefault(e["clause_id"], []).append(e)
    props, spatial_rels, causal = [], [], []

    def arg(s, np_):
        T = s["tokens"]
        h = np_["head"]
        m = mention_at.get((s["sent_id"], h))
        a = {"text": " ".join(x["text"] for x in T[np_["start"]:np_["end"] + 1]), "head": T[h]["text"],
             "head_lemma": T[h]["lemma"], "span": ref(s, np_["start"], np_["end"]), "det": np_["det"],
             "quantifier": np_["det"] if np_["det"] in quant else None,
             "entity_id": m.get("entity_id") if m else None}
        if np_["possessor_tok"] is not None:
            pm = mention_at.get((s["sent_id"], np_["possessor_tok"]))
            a["possessor"] = {"text": T[np_["possessor_tok"]]["text"], "entity_id": pm.get("entity_id") if pm else None,
                              "mention_id": pm["mention_id"] if pm else None}
        return a

    for c in temp["clauses"]:
        evs = ev_by_clause.get(c["clause_id"], [])
        if not evs:
            continue
        s = sents[evs[0]["span"]["sent_id"]]
        T = s["tokens"]
        a, b = c["body_start"], c["end"]
        while b > a and T[b - 1]["pos"] == "PUNCT":
            b -= 1
        matrix = evs[0]
        # subject = NP before the verb group
        subj_np = _np(T, a, matrix["span"]["tok_start"])
        actor = arg(s, subj_np) if subj_np else None
        if matrix.get("voice") == "passive":
            obj_from_subject = actor
            by = next((x for x in range(matrix["end_tok"], b) if T[x]["text"].lower() == "by"), None)
            agent_np = _np(T, by + 1, b) if by is not None else None
            actor = arg(s, agent_np) if agent_np else {"text": "you", "head": "you", "head_lemma": "you", "implied": True,
                                                        "entity_id": None, "span": None, "det": None, "quantifier": None,
                                                        "rule": "SEM-AGENTLESS-PASSIVE-IMPLIED-AGENT"}
        else:
            obj_from_subject = None
        if actor is None and matrix.get("mood") == "imperative":
            actor = {"text": "you", "head": "you", "head_lemma": "you", "implied": True, "entity_id": None,
                     "span": None, "det": None, "quantifier": None, "rule": "SEM-IMPERATIVE-IMPLIED-YOU"}
        exit_cond = None
        neg = any(T[x]["text"].lower() in ("not", "never", "n't") for x in range(a, b))
        modal = next((T[x]["text"].lower() for x in range(a, matrix["tok"]) if T[x]["pos"] == "AUX" and T[x]["text"].lower() in MODALS), None)
        leaf = evs[-1]
        j = matrix["end_tok"]
        obj, pps = None, []
        if j < b and T[j]["pos"] == "ADP" and T[j]["text"].lower() in objprep.get(leaf["lemma"], []):
            np_ = _np(T, j + 1, b)
            if np_:
                obj = dict(arg(s, np_), via_prep=T[j]["text"].lower()); j = np_["end"] + 1
        elif j < b:
            np_ = _np(T, j, b)
            if np_:
                obj = arg(s, np_); j = np_["end"] + 1
        if obj_from_subject is not None:
            obj = dict(obj_from_subject, via="passive_subject")
        while j < b:
            if T[j]["pos"] == "ADP":
                np_ = _np(T, j + 1, b)
                if not np_:
                    j += 1; continue
                if T[j]["text"].lower() == "for" and T[np_["head"]]["morph"].get("time_noun") and \
                        any(T[x]["pos"] == "NUM" for x in range(np_["start"], np_["head"])) and exit_cond is None:
                    exit_cond = {"kind": "duration", "text": " ".join(T[x]["text"] for x in range(j, np_["end"] + 1)),
                                 "span": ref(s, j, np_["end"]), **prov("EXIT-DURATION", "explicit")}
                    j = np_["end"] + 1; continue
                pps.append({"prep": T[j]["text"].lower(), "prep_tok": j, "np": arg(s, np_)})
                j = np_["end"] + 1
            elif T[j]["text"].lower() in ("until", "till") and exit_cond is None:
                exit_cond = {"kind": "until", "text": " ".join(T[x]["text"] for x in range(j, b)), "span": ref(s, j, b - 1),
                             **prov("EXIT-UNTIL-CLAUSE", "explicit")}
                break
            elif T[j]["text"].lower() in ("because", "so", "if", "when"):
                causal.append({"marker": T[j]["text"].lower(), "span": ref(s, j), "from_event": matrix["event_id"], "to": "unresolved",
                               **prov("CAUSAL-MARKER", "explicit")})
                j += 1
            else:
                j += 1
        locations, prev_np = [], None
        for pp in pps:
            if pp["prep"] in spatial and prev_np is not None:
                rel = {"relation": pp["prep"], "figure": prev_np["head_lemma"], "figure_span": prev_np["span"],
                       "ground": pp["np"]["head_lemma"], "ground_arg": pp["np"], **prov("SPATIAL-NOUN-ATTACH", "explicit")}
                spatial_rels.append(rel)
                prev_np.setdefault("located_by", []).append(rel)
            else:
                role = vprep.get(pp["prep"], "location")
                loc = dict(pp["np"], prep=pp["prep"], role=role, attaches_to=leaf["event_id"],
                           perspective_level=2 if role == "perspective" else None,
                           **prov("PP-VERB-ATTACH", "explicit"))
                locations.append(loc)
                prev_np = loc
        for e in evs:
            nested = e is not matrix
            chan = channels["lemma_channels"].get(e["lemma"])
            chan_prov = "explicit"; alts = []
            if chan is None and e["lemma"] in channels["lemma_channels_inferred"]:
                inf = channels["lemma_channels_inferred"][e["lemma"]]
                chan, chan_prov, alts = inf["channel"], "inferred", inf["alternatives"]
            props.append({
                "event_id": e["event_id"], "predicate": e["predicate"], "lemma": e["lemma"], "parent_event": e["parent_event"],
                "actor": actor, "actor_binding": "control_from_parent_subject" if nested else "grammatical_subject",
                "object": obj if e is leaf else None,
                "complement_event": evs[evs.index(e) + 1]["event_id"] if e is not leaf else None,
                "locations": locations if e is leaf else [], "polarity": "negative" if neg and not nested else "positive",
                "grammatical_modality": modal if not nested else None, "channel": chan, "channel_provenance": chan_prov,
                "channel_alternatives": alts, "span": e["span"], "mood": matrix.get("mood"),
                "exit_condition": exit_cond if e is leaf else None,
                **prov("SEM-CONTROL" if nested else "SEM-CLAUSE-ROLES", "inferred" if nested else "explicit",
                       status="narrator_asserted")})
    return {"propositions": props, "spatial_relations": spatial_rels, "causal_links": causal}


def operator_cell(prop, ev, modality_reg):
    """'word,emoji' for one event: superscript only on external visual (user rule)."""
    chan = prop["channel"]
    if not chan or chan == "unresolved":
        return None
    glyph = modality_reg["operators"][chan]
    if chan in modality_reg["verb_form_superscripts"]["_applies_to"]:
        sup = modality_reg["verb_form_superscripts"]
        vf = ev.get("verb_form") or ""
        if vf == "VBG" or vf.endswith("VBG"):
            glyph += sup["progressive_or_gerund"]
        elif vf in ("TO+VB", "VB"):
            glyph += sup["base_or_infinitive"]
        elif vf in ("VBD", "VBN") or vf.endswith(("VBD", "VBN")):
            glyph += sup["past_or_past_participle"]
        elif vf in ("VBZ", "VBP"):
            glyph += sup["present_finite"]
    word = ev["predicate"].split()[-1]
    tag = " [inferred]" if prop.get("channel_provenance") == "inferred" else ""
    return f"{word},{glyph}{tag}"
