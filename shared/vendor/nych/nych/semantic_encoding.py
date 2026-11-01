"""Auditable sense-first and longest-span NYCH semantic encoding."""

from __future__ import annotations

import re

from .semantic_registry import load_registry, sense_by_id


WORD_CORE = re.compile(r"^([^\w]*)([\w'-]+)([^\w]*)$", re.UNICODE)


def _split(token: str) -> tuple[str, str, str]:
    match = WORD_CORE.match(token)
    return match.groups() if match else ("", token, "")


def _surface_index(registry: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for entry in registry["senses"]:
        for form in entry["surface_forms"]:
            result.setdefault(form.lower(), []).append(entry)
    return result


def match_gestalt_spans(tokens: list[str], explicit_positions: set[int], registry: dict) -> dict[int, dict]:
    cores = [_split(token)[1].lower() for token in tokens]
    phrases = []
    for span in registry["gestalt_spans"]:
        phrases.extend((tuple(phrase.lower().split()), span) for phrase in span["phrases"])
    phrases.sort(key=lambda item: len(item[0]), reverse=True)

    matches: dict[int, dict] = {}
    occupied: set[int] = set()
    for start in range(len(tokens)):
        candidates = []
        for parts, span in phrases:
            end = start + len(parts)
            positions = set(range(start, end))
            if end <= len(tokens) and not positions & (occupied | explicit_positions):
                if tuple(cores[start:end]) == parts:
                    candidates.append((len(parts), span, end))
        if not candidates:
            continue
        longest = max(item[0] for item in candidates)
        winners = [item for item in candidates if item[0] == longest]
        if len({item[1]["span_id"] for item in winners}) != 1:
            continue
        _, span, end = winners[0]
        matches[start] = {**span, "start": start, "end": end, "surface": " ".join(tokens[start:end])}
        occupied.update(range(start, end))
    return matches


def _resolve_fallback(core: str, left: str, right: str, registry: dict) -> tuple[dict | None, str, float]:
    candidates = _surface_index(registry).get(core.lower(), [])
    if not candidates:
        return None, "unsymbolized", 0.0
    if len(candidates) == 1:
        return candidates[0], "surface_form_unambiguous", 1.0
    context = {_split(left)[1].lower(), _split(right)[1].lower()}
    scored = [(len(context & set(entry.get("cue_words", []))), entry) for entry in candidates]
    best_score = max(score for score, _ in scored)
    winners = [entry for score, entry in scored if score == best_score]
    if best_score > 0 and len(winners) == 1:
        return winners[0], "cue_match", 0.7
    defaults = [entry for entry in candidates if entry.get("is_default")]
    return (defaults[0] if len(defaults) == 1 else None), "default_fallback", 0.0


def encode_text(
    text: str,
    sense_choices: dict[int, str] | None = None,
    registry_path: str | None = None,
    enable_spans: bool = True,
) -> tuple[str, list[dict]]:
    """Encode text while recording whether each decision was explicit or inferred."""
    choices = sense_choices or {}
    registry = load_registry(registry_path)
    tokens = text.split()
    spans = match_gestalt_spans(tokens, set(choices), registry) if enable_spans else {}
    output, records = [], []
    i = 0
    while i < len(tokens):
        if i in spans:
            span = spans[i]
            lead = _split(tokens[i])[0]
            trail = _split(tokens[span["end"] - 1])[2]
            output.append(f"{lead}{span['gestalt']}{trail}")
            records.append({
                "word": span["surface"], "position": i, "end_position": span["end"],
                "gestalt": span["gestalt"], "sense_id": span["span_id"],
                "canonical_expression": span["canonical_expression"],
                "protected_invariants": span["protected_invariants"], "method": "gestalt_span",
            })
            i = span["end"]
            continue

        lead, core, trail = _split(tokens[i])
        if i in choices:
            entry = sense_by_id(choices[i], registry)
            if not entry or core.lower() not in {form.lower() for form in entry["surface_forms"]}:
                raise ValueError(f"invalid sense {choices[i]!r} for token {i}: {core!r}")
            method, confidence = "explicit", 1.0
        else:
            entry, method, confidence = _resolve_fallback(
                core, tokens[i - 1] if i else "", tokens[i + 1] if i + 1 < len(tokens) else "", registry
            )
        if entry:
            output.append(f"{lead}{entry['gestalt']}{trail}")
            records.append({"word": core, "position": i, "gestalt": entry["gestalt"],
                            "sense_id": entry["sense_id"], "method": method,
                            "confidence": confidence})
        else:
            output.append(tokens[i])
            records.append({"word": core, "position": i, "gestalt": None,
                            "sense_id": None, "method": method, "confidence": confidence})
        i += 1
    return " ".join(output), records


def audit_summary(records: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["method"]] = counts.get(record["method"], 0) + 1
    total_words = sum(record.get("end_position", record["position"] + 1) - record["position"] for record in records)
    guessed = counts.get("cue_match", 0) + counts.get("default_fallback", 0)
    return {"total_words": total_words, "total_units": len(records), "by_method": counts,
            "fraction_guessed": guessed / total_words if total_words else 0.0}
