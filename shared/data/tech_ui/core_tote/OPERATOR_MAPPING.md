# 4 process operators ↔ 10 modality operators: explicit mapping

**Status:** authored by an agent on 2026-11-03 and not reviewed by a human. Where a mapping is not exact, the row is marked as a gap. Nothing is assumed.

- **4 process operators:** from the `T.O.T.E-loops` seed (`data/seed_loops.json`, `operators`): 👀 `external_observe`, 👁️🧠 `internal_model`, 🗯️ `operative_intent`, 💪 `execute`. These are *process roles*: what a step does inside a T-O-T-E cycle.
- **10 modality operators:** from this repo's `shared/data/tote_seed.json` and the review ZIP: OP-KI 🫶, OP-KE 🙌, OP-VE 👀 (test form 👀²), OP-VI 👁️, OP-AI 👂, OP-AE 👂👂, OP-MEM 💭, OP-IMG 🧠🗯, OP-OLF 👃, OP-GUS 👅. These are *sensory/representational channels*: which sense or representation a step uses.

The two sets classify different things, so the mapping cannot be one-to-one. To convert between them you need extra fields. Those fields are listed in the table.

## Process → modality

| 4-op | Maps to (10-op) | Kind | Extra field needed to convert | Notes / flag |
|---|---|---|---|---|
| 👀 `external_observe` | OP-VE 👀², OP-AE 👂👂, OP-OLF 👃, OP-GUS 👅 | one → many | `channel` (visual/auditory/smell/taste) | Exact for any one channel once `channel` is known. **GAP-1:** external *touch* observation (feeling a click or vibration) has no observe-only 10-op. OP-KE 🙌 is used for operating, not for sensing. |
| 👁️🧠 `internal_model` | OP-VI 👁️, OP-AI 👂, OP-KI 🫶, OP-MEM 💭, OP-IMG 🧠🗯 | one → many | `sense` + `recall_cue` (bool) | Convention: 🧠🗯 is the default on internal senses. 💭 is used only when the text has an explicit recall cue. **FLAG:** the symbols collide. 4-op 👁️🧠 is a compound, while 10-op 👁️ alone means internal *visual*. Don't parse 👁️🧠 as OP-VI. |
| 🗯️ `operative_intent` | *(none exact)*. Nearest is OP-IMG 🧠🗯 | **GAP-2** | `intent=true` | The 10-op set has no "intention/plan" operator. 🧠🗯 means *imagine*. Core loops record `intent_marker: 🧠🗯` by convention and carry this flag. That is not an equivalence. |
| 💪 `execute` | OP-KE 🙌 | near-exact for motor operations | `effector` (hand/voice/device) | **GAP-3:** the 10-op set has no operator for *voice/speech output* (a voice command, dictation) or for *non-bodily software execution* (an API or system action with no human motor act). 🙌 implies kinesthetic action. |

## Modality → process

| 10-op | Maps to (4-op) | Flag |
|---|---|---|
| OP-VE 👀 / 👀² | `external_observe` | exact |
| OP-AE 👂👂 | `external_observe` | exact |
| OP-OLF 👃, OP-GUS 👅 | `external_observe` | exact (does not come up in software loops) |
| OP-KE 🙌 | `execute` (when operating) | **GAP-1 (reverse):** if 🙌 is used for a tactile *test*, there is no 4-op observe equivalent that keeps "touch" |
| OP-VI 👁️, OP-AI 👂, OP-KI 🫶 | `internal_model` | exact role, but the sense is lost unless `sense` is kept |
| OP-MEM 💭 | `internal_model` | exact role, but recall is lost unless `recall_cue` is kept |
| OP-IMG 🧠🗯 | `internal_model` **or** `operative_intent` | **AMBIGUOUS (GAP-2):** you need `intent=true/false` to decide |

## Conflicting flags (unresolved)

- **GAP-4 `may_assert_action`:** In `tote_seed.json`, every *external* modality operator carries `true` in the 5th field, including 👀, 👂👂, 👃 and 👅. In the 4-op seed, only `execute` has `may_assert_action=1`, and its README says "an action is never recorded as an observation". Either the 10-op field means something else (e.g. "can be asserted from external evidence"), or the two disagree. This needs an owner decision. Core loops follow the 4-op rule: only the operate step asserts an action.

## How CORE loops use this

Each loop in `core_loops.json` stores **both** labels on every step:
- `test_pre` / `test_post`: `operator: 👀²`, `modality_operator: OP-VE`, `process_operator: external_observe`
- `operate`: `operator: 🙌`, `modality_operator: OP-KE`, `process_operator: execute`, plus `intent_marker: 🧠🗯` / `intent_process_operator: operative_intent`, flagged GAP-2

GAP-3 affects voice loops (`TEXT_DICTATE`, `AI_VOICE_INPUT`). They are still labeled 🙌 (tap the mic control). The spoken part has no operator.
