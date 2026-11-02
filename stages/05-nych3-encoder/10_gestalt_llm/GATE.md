# GATE 10 -- human review before Gestalt mappings become persistent

Stage 10 output (`output/mappings.json`) is a PROPOSAL until this gate passes.

Check, then re-run with `--approve`:
1. NYCH3 validator passed and `mg8_validator` reads `passed`.
2. No protected term (names such as Peter) was mapped.
3. Every `symbol_id` ends with `.<skeleton>` of its word; distinct words sharing a skeleton got distinct ids.
4. No modality operator glyph (🫶 🙌 👀 👁️ 👂 👂👂 💭 👁️‍🗨️ 👃 👅) appears in a symbol_id or glyph.
5. Pins were reused, never re-decided.
6. The provider was a real model, not `MockProvider` -- mock ids (`gst3.mock.*`) must never be approved as canon.

Persisted mappings keep the full word and its occurrence; status `accepted`, provenance `predicted` from the provider.
