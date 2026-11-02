"""spaCy (en_core_web_sm, deterministic) parse of candidate lines -> out/actions.jsonl (one row per imperative action)."""
import json, os, re, spacy
ROOT = os.path.join(os.path.dirname(__file__), "..")
nlp = spacy.load("en_core_web_sm")
MAP = json.load(open(os.path.join(ROOT, "config", "mapping.json")))
LEX = {v.split()[0] for r in MAP["rules"] for v in r.get("verbs", [])}
OBJ = [  # (type, regex) first match wins; edit freely
 ("hardware_button", r"\b(side|top|home|power|volume( up| down)?|sleep/wake|digital crown|action|camera control|reset) button\b|\bcrown\b"),
 ("key", r"\b(ctrl|control|alt|option|shift|cmd|command|win(dows)?( logo)? key|fn|esc|enter key|return key|tab key|delete key|backspace|space ?bar|f\d{1,2}|key(s)?|keyboard shortcut|\+ ?[a-z]\b)"),
 ("settings_app", r"\bsettings\b|system preferences|system settings|control panel"),
 ("password", r"pass(word|code|key)|\bpin\b"),
 ("code", r"\b(verification|security|confirmation|qr|activation|product) code\b|\bcode\b"),
 ("account", r"\baccount\b|apple id|apple account|microsoft account|google account|\bprofile\b"),
 ("web", r"https?:|www\.|\.com\b|website|web ?page|\bsite\b|\bportal\b|\burl\b|\blink\b"),
 ("toggle", r"\btoggle\b|\bswitch\b|on/off"),
 ("checkbox", r"check ?box|\bbox\b|\btick"),
 ("dropdown", r"drop-?down|list box|combo box|pop-up menu|\bpicker\b"),
 ("menu", r"\bmenu\b|context menu|\bellipsis\b|\bmore options\b|\bthree dots\b|\.\.\.|⋮"),
 ("tab", r"\btab\b"), ("window", r"\bwindow\b|\bpane\b|\bpanel\b|\bsidebar\b|\bdialog\b"),
 ("button", r"\bbutton\b|\bicon\b|\blink\b"),
 ("field", r"\bfield\b|\btext box\b|\bsearch box\b|\bsearch bar\b|\baddress bar\b|\binput\b"),
 ("option", r"\boption\b|\bsetting\b|\bpreference\b|\bmode\b|\bradio\b"),
 ("update", r"\bupdates?\b|\bupgrade\b"),
 ("app", r"\bapp\b|\bapplication\b|\bbrowser\b|\bprogram\b|\bclaude\b|\bgemini\b|\bchrome\b|\byoutube\b|\bfinder\b|\bfile explorer\b|\boutlook\b|\bteams\b|\bword\b|\bexcel\b|\bedge\b|\bsafari\b|\bapp store\b|\bplay store\b"),
 ("file", r"\bfiles?\b|\bphotos?\b|\bvideos?\b|\bimages?\b|\bdocuments?\b|\battachments?\b|\bpdf\b"),
 ("folder", r"\bfolders?\b|\bdirectory\b"),
 ("device", r"\b(iphone|ipad|mac|computer|pc|phone|device|tablet|watch|airpods|laptop|console|tv|printer|router|chromebook)\b"),
 ("cable", r"\bcable\b|\bcharger\b|\badapter\b|\busb\b"),
 ("network", r"wi-?fi|bluetooth|\bnetwork\b|\bvpn\b|hotspot"),
 ("notification", r"notifications?|\balerts?\b"),
 ("ai", r"\bprompt\b|\bchat\b|\bconversation\b|\bquestion\b|\bresponse\b|\bproject\b|\bartifact\b"),
 ("content", r"\bmessage\b|\bemail\b|\btext\b|\bcontent\b|\bpost\b|\bcomment\b"),
 ("list", r"\blist\b|\bitems?\b"),
]
DIR = re.compile(r"\b(up|down|left|right|from the (top|bottom|left|right)( edge| of the screen)?|to the (left|right)|clockwise|counterclockwise)\b", re.I)
COUNT = re.compile(r"\b(twice|three times|\d+ times|once)\b", re.I)
DUR = re.compile(r"\b(\d+|a few|several|ten|five|two|three|30)\s*(seconds?|minutes?|hours?|secs?)\b", re.I)
COND = re.compile(r"\b(until|when you see|when prompted|if prompted|after|once|then|wait for|if you see|as soon as|appears|is displayed)\b", re.I)
PLAT = [("iphone", r"\biphone\b"), ("ipad", r"\bipad\b"), ("mac", r"\bmac(os|book)?\b"), ("windows", r"\bwindows\b"), ("android", r"\bandroid\b"), ("chromebook", r"chromebook|chromeos"), ("web", r"\bbrowser\b|\bweb\b|\bonline\b")]
def otype(s):
    for t, rx in OBJ:
        if re.search(rx, s, re.I): return t
    if re.search(r"\b[A-Z][a-zA-Z]+", s): return "named_control"
    return "other" if s.strip() else "none"
def pre(t):
    t = re.sub(r"(?i)double[- ]click", "doubleclick", t); t = re.sub(r"(?i)right[- ]click", "rightclick", t)
    return t
def actions(text):
    doc = nlp(pre(text)); out = []
    for sent in doc.sents:
        toks = list(sent)
        for i, t in enumerate(toks):
            low = t.text.lower()
            clause_start = i == 0 or toks[i-1].text in (",", ";", ":", "then", "and", "or", "Then", "(") or toks[i-1].dep_ == "mark"
            is_v = t.tag_ == "VB" and not any(c.dep_ in ("nsubj", "nsubjpass", "aux", "auxpass") for c in t.children) and t.dep_ in ("ROOT", "conj", "advcl", "xcomp", "ccomp") and not (i and toks[i-1].text.lower() in ("to", "can", "will", "may", "might", "must", "should", "could", "would", "please") and t.dep_ != "ROOT")
            if t.dep_ == "xcomp" and t.head.lemma_ not in ("try", "remember", "make"): is_v = False if not clause_start else is_v
            lex = clause_start and low in LEX and t.tag_ not in ("VBZ", "VBD", "VBN", "VBG", "MD") and not (i+1 < len(toks) and toks[i+1].dep_ in ("nsubj",))
            if not (is_v or lex): continue
            if i and toks[i-1].text.lower() in ("to",) and not clause_start: continue
            lemma = {"doubleclick": "doubleclick", "rightclick": "rightclick"}.get(low, t.lemma_.lower() if t.pos_ in ("VERB", "AUX") else low)
            prt = [c.text.lower() for c in t.children if c.dep_ == "prt"]
            j = i + 1
            if not prt and j < len(toks) and toks[j].text.lower() in ("on", "off", "in", "out", "up", "down", "back", "to", "for", "through", "over") and toks[j].dep_ in ("prt", "prep", "advmod"):
                prt = [toks[j].text.lower()]
            if prt and toks[i+1].text.lower() == prt[0]: j = i + 2
            obj = []
            for k in range(j, min(len(toks), j + 10)):
                w = toks[k]
                if w.text in (",", ";", ".", ":", "(") or (w.text.lower() in ("and", "then", "to", "until", "if", "when", "so", "or") and obj): break
                if w.tag_ == "VB" and obj and w.dep_ in ("conj", "advcl"): break
                obj.append(w.text)
            obj_s = " ".join(obj).strip()
            if lemma in ("be", "have", "do", "need", "want", "can", "let's", "note", "learn", "get") and not prt: continue
            out.append({"verb": (lemma + " " + " ".join(prt)).strip(), "surface": t.text, "object": obj_s[:80], "obj_type": otype(obj_s)})
    return out
def main():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "out", "steps_raw.jsonl"))]
    w = open(os.path.join(ROOT, "out", "actions.jsonl"), "w"); ns = na = 0
    for sid, r in enumerate(rows):
        acts = actions(r["text"])
        if not acts: continue
        ns += 1; txt = r["text"]
        plat = [p for p, rx in PLAT if re.search(rx, txt + " " + r["title"], re.I)] or [r["platform"]]
        for k, a in enumerate(acts):
            a.update(step_id=sid, action_idx=k, text=txt, kind=r["kind"], step_no=r["step_no"], section=r["section"], site=r["site"],
                     platform=r["platform"], platform_hints="|".join(plat), url=r["url"], retrieved=r["retrieved"], title=r["title"],
                     direction=";".join(m.group(0) for m in DIR.finditer(txt)), count=";".join(m.group(0) for m in COUNT.finditer(txt)),
                     duration=";".join(m.group(0) for m in DUR.finditer(txt)), condition_cues=";".join(sorted({m.group(0).lower() for m in COND.finditer(txt)})))
            w.write(json.dumps(a) + "\n"); na += 1
    print("steps with >=1 action", ns, "of", len(rows), "| actions", na)
if __name__ == "__main__": main()
