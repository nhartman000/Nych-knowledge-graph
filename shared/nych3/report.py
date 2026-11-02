"""Human-readable TOTE row table (user TOTE DB model)."""
COLS = [("modality", "modality operators"), ("actor", "actor"), ("action", "action"), ("object", "tool/object"),
        ("perspective_location", "perspective/location"), ("exit", "exit condition (g8son gate)")]


def tote_table(state, sent_id=None) -> str:
    lines = ["| instance | template | " + " | ".join(h for _, h in COLS) + " |", "|" + "---|" * (len(COLS) + 2)]
    for i in state["tote"]["instances"]:
        if sent_id and not any(r["sent_id"] == sent_id for r in i["source_refs"]):
            continue
        tag = f"{i['template_id']} ({i.get('template_status') or 'fallback'})"
        lines.append(f"| {i['instance_id']} | {tag} | " + " | ".join(i["row"].get(k, "") for k, _ in COLS) + " |")
    return "\n".join(lines)
