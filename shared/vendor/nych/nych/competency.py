"""
competency.py -- vernacular-based modality classification, domain
classification, and a competency score.

This fills a gap the rest of the package doesn't cover: symbol/sense
encoding (encoding.py, semantic_encoding.py) turns words into Gestalts, but
nothing here previously judged *how* something was said -- which sensory
modality a speaker's language leans on, which subject-matter domain their
vocabulary belongs to, or how fluently they're using that domain's
vernacular. That's what this module adds, as one step that can run before
semantic encoding in a larger pipeline (see mg8-engine's gate runtime for
where "competency and domain" feed into a gate decision).

Honesty note, at the same bar as the rest of this package: this is a small,
hand-built keyword lexicon, not a trained classifier. It will get things
wrong outside its listed markers/jargon. `classify_modality` and
`classify_domain` both report "UNRESOLVED" with score 0 rather than forcing
a guess when nothing matches -- the same disclosed-uncertainty pattern used
in semantic_encoding.py's resolution methods.
"""

from __future__ import annotations
import re

MODALITY_MARKERS = {
    "VISUAL_EXTERNAL": [
        "looks good", "looks right", "i see", "looks like", "appears", "watch",
        "observe", "picture this", "show me", "clear picture", "visibly", "on screen",
    ],
    "VISUAL_INTERNAL": [
        "i can see it", "envision", "imagine", "visualize", "in my mind's eye",
        "picture in my head", "mental image", "i can picture",
    ],
    "AUDITORY_EXTERNAL": [
        "sounds good", "sounds right", "i hear", "tell me", "that clicks",
        "loud and clear", "resonates aloud", "listen",
    ],
    "AUDITORY_INTERNAL": [
        "rings true", "sounds off in my head", "inner voice", "tells me", "quiet voice",
        "i keep telling myself", "self-talk",
    ],
    "KINESTHETIC_INTERNAL": [
        "feels right", "feels off", "doesn't feel right", "gut feeling", "sense that",
        "feel like", "comfortable with", "uneasy", "intuition",
    ],
    "KINESTHETIC_EXTERNAL": [
        "grasp", "handle", "grab", "solid", "smooth", "rough", "hands-on", "tangible",
        "pressure", "warm", "concrete feel",
    ],
}

HEDGES = ["i guess", "maybe", "sort of", "kind of", "i think", "not sure", "probably",
          "i dunno", "dunno", "whatever"]

DOMAIN_JARGON = {
    "COMPUTER_SCIENCE": ["algorithm", "recursion", "buffer", "latency", "throughput",
                          "manifold", "orthogonal", "invariant", "boundary", "vector",
                          "convergence", "midpoint", "allocation"],
    "MANUAL_TRADES": ["torque", "fastener", "kerf", "tolerance", "countersink",
                       "grain", "joist", "shim"],
    "MEDICAL": ["etiology", "differential", "contraindication", "prognosis",
                "presenting", "titrate", "comorbidity"],
}


def _marker_pattern(marker: str) -> str:
    return r"\b" + re.escape(marker) + r"\b"


def classify_modality(text: str) -> tuple[str, int]:
    """Word-boundary-safe modality classification. Returns (modality, hit
    count). ('UNRESOLVED', 0) when no marker phrase matches -- disclosed,
    not guessed."""
    lower = text.lower()
    scores = {}
    for modality, markers in MODALITY_MARKERS.items():
        hits = sum(1 for m in markers if re.search(_marker_pattern(m), lower))
        if hits:
            scores[modality] = hits
    if not scores:
        return "UNRESOLVED", 0
    best = max(scores, key=scores.get)
    return best, scores[best]


def classify_domain(text: str) -> tuple[str, int]:
    """Vernacular-based domain classification, the same scoring shape as
    classify_modality: whichever DOMAIN_JARGON group has the most hits in
    the text wins. ('UNRESOLVED', 0) when no domain jargon appears at all --
    most everyday sentences will land here, honestly, rather than being
    forced into one of the three listed domains."""
    lower = text.lower()
    scores = {}
    for domain, jargon in DOMAIN_JARGON.items():
        hits = sum(1 for j in jargon if re.search(_marker_pattern(j), lower))
        if hits:
            scores[domain] = hits
    if not scores:
        return "UNRESOLVED", 0
    best = max(scores, key=scores.get)
    return best, scores[best]


def competency_score(text: str, domain: str) -> int:
    """1-10 competency estimate for how fluently `text` uses `domain`'s
    vernacular: rewards domain jargon and lexical diversity, penalizes
    hedging language. `domain` is a caller-supplied label (e.g. from
    classify_domain, or from an external caller who already knows the
    domain) -- this function does not classify domain itself."""
    lower = text.lower()
    words = re.findall(r"[a-z']+", lower)
    if not words:
        return 1
    jargon = DOMAIN_JARGON.get(domain.upper(), [])
    jargon_hits = sum(1 for j in jargon if re.search(_marker_pattern(j), lower))
    hedge_hits = sum(1 for h in HEDGES if re.search(_marker_pattern(h), lower))
    diversity = len(set(words)) / len(words)
    raw = 2.0 + (jargon_hits * 1.8) + (diversity * 4.0) - (hedge_hits * 1.5)
    return max(1, min(10, round(raw)))


def analyze_utterance(text: str) -> dict:
    """Convenience entry point combining all three: modality, domain
    (inferred via classify_domain), and a competency score against that
    inferred domain. This is the single step a pipeline (e.g. mg8-engine's
    gate runtime) can call to get 'competency and domain via vernacular'
    before handing the text to semantic_encoding.encode_text for Gestalt
    symbolization."""
    modality, modality_score = classify_modality(text)
    domain, domain_score = classify_domain(text)
    competency = competency_score(text, domain) if domain != "UNRESOLVED" else None
    return {
        "text": text,
        "modality": modality,
        "modality_score": modality_score,
        "domain": domain,
        "domain_score": domain_score,
        "competency": competency,
    }
