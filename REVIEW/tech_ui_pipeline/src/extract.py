"""Extract procedural steps from cached HTML -> out/steps_raw.jsonl (candidate steps with provenance)."""
import json, os, re, glob
from bs4 import BeautifulSoup, NavigableString
ROOT = os.path.join(os.path.dirname(__file__), "..")
PLAT = {"apple": "apple", "microsoft": "windows/microsoft", "claude": "ai_claude", "google_android": "android",
        "google_youtube": "youtube", "google_gemini": "ai_gemini", "google_chrome": "chrome", "sumo": "firefox"}
def main_node(s):
    for sel in ["#sections", "div.cc", "article", "main", "#ocArticleContent", "body"]:
        n = s.select_one(sel)
        if n: return n
def own_text(li):
    parts = []
    for c in li.children:
        if getattr(c, "name", None) in ("ol", "ul", "table"): continue
        parts.append(c.get_text(" ", strip=True) if not isinstance(c, NavigableString) else str(c).strip())
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
def steps_from(html):
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "nav", "header", "footer", "aside", "noscript"]): t.decompose()
    title = (s.title.get_text(strip=True) if s.title else "")
    root = main_node(s); out = []; sec = ""; seen = set()
    for el in root.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
        if el.name[0] == "h": sec = el.get_text(" ", strip=True)[:120]; continue
        if el.name == "li":
            par = el.find_parent(["ol", "ul"])
            if par is None or par.find_parent(["nav"]) : continue
            txt = own_text(el); kind = "ol" if par.name == "ol" else "ul"
            idx = [x for x in par.find_all("li", recursive=False)].index(el) + 1 if el in par.find_all("li", recursive=False) else 0
        else:
            if el.find_parent("li"): continue
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)); kind = "p"; idx = 0
        if not (3 <= len(txt.split()) <= 80) or txt in seen: continue
        seen.add(txt); out.append({"text": txt, "kind": kind, "step_no": idx, "section": sec})
    return title, out
def main():
    w = open(os.path.join(ROOT, "out", "steps_raw.jsonl"), "w"); n = 0
    for site in PLAT:
        ixp = os.path.join(ROOT, "data", "raw", site, "_index.jsonl")
        if not os.path.exists(ixp): continue
        for line in open(ixp):
            e = json.loads(line)
            if site.startswith("google") and "/answer/" not in e["url"]: continue
            html = open(os.path.join(ROOT, "data", "raw", site, e["file"]), encoding="utf-8").read()
            title, st = steps_from(html)
            for x in st:
                x.update(site=site, platform=PLAT[site], url=e["url"], retrieved=e["retrieved"], title=title)
                w.write(json.dumps(x) + "\n"); n += 1
    print("candidate lines", n)
if __name__ == "__main__": main()
