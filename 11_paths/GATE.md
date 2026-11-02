# GATE 11 -- human review before MG8 handoff

1. Every path carries `confidence.kind = likelihood_class` (high > medium > low > latent) or `unavailable`. Any bare float is a failure.
2. Defaults name their source rule; alternatives remain (latent or expanded with an `expansion_reason`).
3. NO_MATCH instances are listed under `pruned` with the fallback reason, not silently dropped.
4. `trace.jsonl` recorded predicted and pruned paths, so later evidence can be logged for calibration.
5. Nothing here authored .g8son gates or an .ork flow (that is MG8's job after stage 12).
