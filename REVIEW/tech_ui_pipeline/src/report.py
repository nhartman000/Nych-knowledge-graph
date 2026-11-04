"""Build canonical_actions.json, coverage.md + coverage.png, spotcheck sample."""
import json, os, re, collections, random
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.join(os.path.dirname(__file__), ".."); O = lambda *p: os.path.join(ROOT, "out", *p)
A = [a for a in json.load(open(O("actions_canon.json"))) if a["canonical"] != "NON_ACTION"]
cov = json.load(open(O("coverage.json")))
# exit-state phrase per canonical (g8son-style gate condition); 🙌 = external kinesthetic operate, 👀² = external visual verify (base form)
EXIT = {"TAP_OR_CLICK": "screen_shows(next view or state for <target>)", "SELECT_ITEM": "item_selected(<target>) [highlight visible]",
 "LONG_PRESS": "screen_shows(context menu or jiggle mode)", "DOUBLE_CLICK_TAP": "screen_shows(<target> opened or zoomed)",
 "RIGHT_CLICK": "screen_shows(context menu)", "PRESS_HARDWARE_BUTTON": "device_shows(response to button: slider/lock/volume HUD)",
 "PRESS_KEY_COMBO": "screen_shows(shortcut result)", "SWIPE": "screen_shows(new panel from <direction>)", "SCROLL": "screen_shows(<target> in view)",
 "DRAG_AND_DROP": "item_at(<destination>)", "PINCH_ZOOM": "screen_shows(zoom level changed)", "HOVER": "screen_shows(tooltip or revealed control)",
 "TOGGLE_ON": "toggle_state(<target>) == on", "TOGGLE_OFF": "toggle_state(<target>) == off", "TOGGLE": "toggle_state(<target>) == desired",
 "POWER_ON_DEVICE": "device_shows(boot logo or lock screen)", "POWER_OFF_DEVICE": "device_screen == off", "RESTART_DEVICE": "device_shows(lock/login screen after reboot)",
 "OPEN_SETTINGS": "screen_shows(Settings)", "OPEN_APP": "screen_shows(<app> main view)", "OPEN_MENU": "screen_shows(<menu> items)", "OPEN_FILE": "screen_shows(<file> contents)",
 "OPEN_WEBPAGE": "browser_shows(<url/page>)", "OPEN_TAB_PANEL": "screen_shows(<tab/panel>)", "NAVIGATE_TO": "screen_shows(<destination> page)", "GO_BACK": "screen_shows(previous view)",
 "OPEN_ITEM": "screen_shows(<target>)", "CLOSE_ITEM": "screen_not_shows(<target>)", "SIGN_IN": "screen_shows(signed-in account name)", "SIGN_OUT": "screen_shows(sign-in prompt)",
 "CREATE_ACCOUNT": "screen_shows(account created)", "ENTER_PASSWORD": "screen_shows(accepted / next step)", "ENTER_CODE": "screen_shows(code accepted)",
 "TYPE_TEXT": "field_contains(<text>)", "SEARCH": "screen_shows(results for <query>)", "SELECT_OPTION": "option_selected(<option>)", "CONFIRM_DIALOG": "dialog_closed and action_applied",
 "CANCEL_ACTION": "dialog_closed and no_change", "COPY": "clipboard_has(<item>)", "PASTE": "field_contains(pasted item)", "CUT": "clipboard_has(<item>) and item_removed",
 "UNDO_REDO": "screen_shows(previous state)", "SAVE": "screen_shows(saved indicator)", "DELETE_ITEM": "screen_not_shows(<item>)", "UNINSTALL_APP": "app_absent(<app>)",
 "INSTALL_APP": "app_present(<app>)", "DOWNLOAD": "file_present(<download>)", "UPLOAD_FILE": "screen_shows(<file> attached/uploaded)", "UPDATE_SOFTWARE": "screen_shows(up to date)",
 "CREATE_ITEM": "screen_shows(new <item>)", "ADD_ITEM": "screen_shows(<item> in list)", "EDIT_ITEM": "screen_shows(<item> changed)", "SET_VALUE": "setting_value(<target>) == desired",
 "MOVE_ITEM": "item_at(<destination>)", "SHARE_SEND": "screen_shows(sent/shared confirmation)", "PRINT": "printer_output_present", "CONNECT_DEVICE": "screen_shows(Connected)",
 "DISCONNECT_DEVICE": "screen_shows(Not connected)", "CHARGE_DEVICE": "screen_shows(charging indicator)", "BACKUP_RESTORE": "screen_shows(backup/restore complete)", "RESET": "screen_shows(reset complete / setup screen)",
 "LOCK_UNLOCK": "screen_shows(locked or unlocked state)", "MEDIA_PLAYBACK": "player_state == desired", "CALL_COMMUNICATE": "screen_shows(call connected/ended)", "SCAN_CAPTURE": "screen_shows(captured item)",
 "VOICE_COMMAND": "screen_shows(assistant response)", "PROMPT_AI": "screen_shows(AI response to prompt)", "VERIFY_STATE": "screen_shows(<expected state>)", "REVIEW_CONTENT": "content_reviewed(<target>) [inferred]",
 "WAIT": "screen_shows(<awaited state>) [explicit until/for]", "FOLLOW_PROMPTS": "screen_shows(final 'Done'/'Finish' step)", "ALLOW_PERMISSION": "permission_state(<target>) == allowed", "VERIFY_IDENTITY": "screen_shows(identity verified)",
 "CONTACT_SUPPORT": "support_contact_opened", "REFRESH_RELOAD": "screen_shows(reloaded content)", "EXPORT_IMPORT": "file_present(<export>)", "FILTER_SORT": "screen_shows(filtered/sorted list)",
 "USE_FEATURE": "<feature>_complete == true [inferred]", "KEEP_REMEMBER": "<item>_noted == true [inferred]", "PAY_PURCHASE": "screen_shows(purchase confirmation)", "PHYSICAL_HANDLE": "device_in_position(<target>) [inferred]"}
LOOK = {"VERIFY_STATE", "REVIEW_CONTENT", "WAIT"}
def ops(c):
    if c in LOOK: return [{"op": "👀²", "verb": "look", "role": "OPERATE"}, {"op": "👀²", "verb": "verify", "role": "TEST"}]
    if c == "KEEP_REMEMBER": return [{"op": "🙌", "verb": "note", "role": "OPERATE"}, {"op": "💭", "verb": "remember", "role": "internal (explicit recall cue 'remember'/'note')"}, {"op": "👀²", "verb": "verify", "role": "TEST"}]
    return [{"op": "🙌", "verb": "operate", "role": "OPERATE"}, {"op": "👀²", "verb": "verify", "role": "TEST"}]
def quote(a):
    w = a["text"].split()
    if len(w) <= 25: return a["text"]
    i = next((k for k, x in enumerate(w) if a["surface"].lower() in x.lower()), 0); s = max(0, i - 5)
    return ("… " if s else "") + " ".join(w[s:s + 25]) + " …"
C = collections.Counter(a["canonical"] for a in A); N = len(A); rng = random.Random(7); res = []
for rank, (c, n) in enumerate(C.most_common(), 1):
    if c.startswith("UNMAPPED"): continue
    rows = [a for a in A if a["canonical"] == c]
    ex = rng.sample(rows, min(3, len(rows)))
    top_v = collections.Counter(a["surface"].lower() for a in rows).most_common(5); top_o = collections.Counter(a["obj_type"] for a in rows).most_common(5)
    objs = collections.Counter(re.sub(r"^(the|a|an|your)\s+", "", a["object"].lower())[:40] for a in rows if a["object"]).most_common(5)
    res.append({"rank": rank, "canonical": c, "count": n, "share_pct": round(100 * n / N, 2),
      "platform_split": dict(collections.Counter(a["platform"] for a in rows).most_common()),
      "top_surface_verbs": top_v, "top_object_types": top_o, "top_objects": objs,
      "params": dict(collections.Counter(a.get("canonical_param", "") for a in rows if a.get("canonical_param")).most_common(6)) or None,
      "examples": [{"quote": quote(a), "url": a["url"], "retrieved": a["retrieved"], "section": a["section"], "step_no": a["step_no"] or None} for a in ex],
      "tote_template": {"test_entry": "👀² verify precondition: target <object> visible/available", "operate": [o for o in ops(c) if o["role"] != "TEST"] + [{"canonical": c, "object": "<object>"}],
        "test_exit": "👀² verify", "exit_gate": {"type": "exit", "conditions": EXIT.get(c, f"{c.lower()}_complete == true [inferred]"), "outcomes": ["PASS", "FAIL", "INTERMEDIATE"],
        "on_fail": "repeat OPERATE (max 3) else INTERMEDIATE"}, "internal_senses": "none (text-implied only)" if c != "KEEP_REMEMBER" else "💭 (explicit recall cue)"}})
json.dump({"generated": __import__("time").strftime("%Y-%m-%d"), "n_actions": N, "actions": res}, open(O("canonical_actions.json"), "w"), indent=1, ensure_ascii=False)
# chart
cv = cov["curve"]; xs = [int(k) for k in cv]; ys = [100 * v for v in cv.values()]
vv = cov["verb_curve"]; vx = [int(k) for k in vv]; vy = [100 * v for v in vv.values()]
plt.figure(figsize=(8, 5)); plt.plot(xs, ys, lw=2.5, label=f"canonical actions ({len(xs)})"); plt.plot(vx, vy, "--", label="raw verb lemmas (no canonicalization)")
for n in (10, 25, 50, 100): plt.axvline(n, color="#ccc", lw=.8)
plt.xscale("log"); plt.ylim(0, 100); plt.xlabel("top-N types (log)"); plt.ylabel("% of extracted UI actions covered"); plt.title(f"Coverage of {N:,} UI actions from tech help centers"); plt.legend(); plt.grid(alpha=.3)
plt.savefig(O("coverage.png"), dpi=130, bbox_inches="tight")
site = collections.Counter(a["site"] for a in A)
md = [f"# Coverage report ({res and json.load(open(O('canonical_actions.json')))['generated']})", "", f"Extracted UI actions: **{N:,}** (non-action verbs excluded: {cov['n_non_action_excluded']}); distinct verb lemmas: {cov['n_distinct_verbs']}; canonical actions used: {cov['n_canonical']}; unmapped: {cov['unmapped_share']}%.", "",
      "| top-N | canonical coverage % | raw verb-lemma coverage % |", "|---|---|---|"] + [f"| {k} | {cov['coverage_topN_canonical_pct'][k]} | {cov['coverage_topN_raw_verb_lemmas_pct'][k]} |" for k in cov["coverage_topN_canonical_pct"]] + \
     ["", "![coverage](coverage.png)", "", "Actions by site: " + ", ".join(f"{k} {v}" for k, v in site.most_common()), "", "## Top 25", "", "| # | canonical | count | % | top surface verbs |", "|---|---|---|---|---|"] + \
     [f"| {r['rank']} | {r['canonical']} | {r['count']} | {r['share_pct']} | {', '.join(v for v, _ in r['top_surface_verbs'][:4])} |" for r in res[:25]] + ["", "## Top unmapped verbs", "", ", ".join(f"{v} ({n})" for v, n in cov["top_unmapped"][:25])]
open(O("coverage.md"), "w").write("\n".join(md) + "\n")
# spot check sample
sp = random.Random(42).sample(A, 40)
json.dump([{k: a[k] for k in ("step_id", "text", "verb", "object", "obj_type", "canonical", "url")} for a in sp], open(O("spotcheck_sample.json"), "w"), indent=1)
print("ok", N, len(res))
# subset: numbered-list steps only (highest-precision procedural text)
ol = [a for a in A if a["kind"] == "ol"]; Co = collections.Counter(a["canonical"] for a in ol); m = [n for k, n in Co.most_common() if not k.startswith("UNMAPPED")]
sub = {n: round(100 * sum(m[:n]) / len(ol), 1) for n in (10, 25, 50, 100, 150)}
open(O("coverage.md"), "a").write(f"\n## Numbered-list steps only ({len(ol):,} actions)\n\n" + " | ".join(f"top-{k}: {v}%" for k, v in sub.items()) + "\n\nSpot-check (40 random actions, agent-graded, PENDING HUMAN REVIEW): see spotcheck_40.csv\n")
print("ol", len(ol), sub)
