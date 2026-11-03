"""Pure rules for harvest job B (no spaCy): amount ranges, modality (🧠🗯 default for internal senses, 💭 only for explicit
recall cues), platform hints, boilerplate/CTA filters, <=25-token quotes."""
import re
NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30}
N = r"(\d+(?:\.\d+)?|" + "|".join(NUM) + r")"
RANGE = re.compile(rf"\b{N}\s*(?:or|to|-|–|—)\s*{N}\b\s*([a-z%]+)?", re.I)
VAGUE = {"a couple of": (2, 3), "a couple": (2, 3), "a few": (2, 4), "several": (3, 7)}
def num(x): return float(NUM.get(x.lower(), x)) if x.lower() in NUM or re.match(r"^\d", x) else None
def ranges(t):
    out = []
    for m in RANGE.finditer(t):
        a, b = num(m.group(1)), num(m.group(2))
        if a is None or b is None or not a < b or (a >= 1900 and b < 2100) or (b >= 100 and (m.group(3) or '').lower() not in ('%', 'dollars', 'percent', 'words', 'characters', 'followers', 'subscribers', 'views', 'hours', 'days')): continue
        out.append({"min": a, "max": b, "unit": (m.group(3) or "").lower(), "text": m.group(0).strip(), "approx": True})
    for k, (a, b) in VAGUE.items():
        m = re.search(rf"\b{k}\s+([a-z]+)", t, re.I)
        if m and not any(k in r["text"] for r in out): out.append({"min": a, "max": b, "unit": m.group(1).lower(), "text": m.group(0), "approx": True, "vague": True}); break
    return out
RECALL = re.compile(r"\b(remember|recall|as before|as last time)\b", re.I)
MENTAL = {"decide", "consider", "think", "determine", "evaluate", "plan", "figure", "imagine", "understand", "know", "weigh", "estimate", "budget", "prioritize", "trust", "assume", "expect", "beware", "be"}
LOOK = {"check", "look", "verify", "review", "read", "watch", "inspect", "confirm", "compare", "monitor", "research", "scan", "see", "view", "examine", "notice", "browse", "search"}
LISTEN = {"listen", "hear"}
def modality(verb, text, canonical, obj=""):
    v = verb.split()[0]
    if v in ("remember", "recall") or (v == "keep" and RECALL.search(text) and "mind" in text.lower()):
        return "💭", "explicit_recall_cue"
    if (v == "make" and re.match(r"(?i)\s*(sure|certain)\b", obj or "")) or v in MENTAL or verb in ("make sure", "keep in mind", "think about") or (v == "keep" and re.search(r"(?i)\bkeep\b[^.]{0,20}\bin mind\b", text)): return "🧠🗯", "internal_sense_default"
    if v in LOOK or canonical in ("VERIFY_STATE", "REVIEW_CONTENT"): return "👀²", "look"
    if v in LISTEN: return "👂👂", "listen_external"
    return "🙌", "operate"
PLATS = [("iphone", r"\biphone\b|\bios\b"), ("ipad", r"\bipad\b"), ("android", r"\bandroid\b"), ("windows", r"\bwindows\b"), ("mac", r"\bmac(os|book)?\b"),
         ("venmo", r"\bvenmo\b"), ("paypal", r"\bpaypal\b"), ("zelle", r"\bzelle\b"), ("cash_app", r"\bcash app\b"), ("youtube", r"\byoutube\b"), ("tiktok", r"\btiktok\b"),
         ("instagram", r"\binstagram\b"), ("facebook", r"\bfacebook\b"), ("offerup", r"\bofferup\b"), ("mercari", r"\bmercari\b"), ("chatgpt", r"\bchatgpt\b"), ("copilot", r"\bcopilot\b"),
         ("gemini", r"\bgemini\b"), ("discord", r"\bdiscord\b"), ("reddit", r"\breddit\b"), ("snapchat", r"\bsnapchat\b|\bsnap\b"), ("amazon", r"\bamazon\b")]
BOILER = re.compile(r"(?i)cookie|privacy policy|terms of (use|service)|subscribe to (our|the) newsletter|sign up for (our|email)|all rights reserved|was this (article|page) helpful|share this page|skip to (main )?content|^(home|menu)\b|javascript")
CTA = re.compile(r"(?i)\b(try|start|get|book|sign up for|download)\b[^.]{0,40}\b(free|trial|demo|today)\b|\b(hootsuite|later|buffer|zapier|grammarly|bitwarden|1password|aarp)\b.{0,30}\b(free|trial|demo|plan|pricing|premium|membership)\b|\bwith (hootsuite|later|buffer|zapier)\b")
STOPV = {"let", "back", "put", "say", "thank", "welcome", "meet", "subscribe", "explore", "discover", "learn", "see"}   # "see" = cross-references (known non-step noise)
ENTERPRISE = re.compile(r"(?i)directory-connector|scim|\bsso\b|-sso|sso-|gpo|self-host|docker|ldap|kubernetes|helm|on-premise|install-and-deploy|deploy|/cli|api|entra|okta|jumpcloud|onelogin|kolide|azure|active-directory|saml|oidc|ping-?identity|duo-|provisioning|policies|event-logs|splunk|elastic|sentinel|admin-console|secrets-manager|bitwarden-send-api|key-connector|trusted-devices-sso")
def quote(text, surface):
    w = text.split()
    if len(w) <= 25: return text
    i = next((k for k, x in enumerate(w) if surface.lower() in x.lower()), 0); s = max(0, min(i - 5, len(w) - 25))
    return ("… " if s else "") + " ".join(w[s:s + 25]) + (" …" if s + 25 < len(w) else "")
