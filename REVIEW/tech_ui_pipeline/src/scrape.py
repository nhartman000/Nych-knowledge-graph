"""Polite resumable scraper. 1 req/s/host, robots.txt respected, raw HTML cached in data/raw/<site>/."""
import hashlib, json, os, re, sys, time, threading, urllib.robotparser as rp
from urllib.parse import urljoin, urlparse
import requests
UA = "NYCH-research-bot/0.1 (+procedural-text research; polite 1 req/s)"
ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
S = requests.Session(); S.headers["User-Agent"] = UA
_robots = {}
def allowed(url):
    h = urlparse(url).netloc
    if h not in _robots:
        r = rp.RobotFileParser(); t = S.get(f"https://{h}/robots.txt", timeout=30)
        r.parse(t.text.splitlines() if t.status_code == 200 else []); _robots[h] = r
    return _robots[h].can_fetch(UA, url)
_last = {}
DELAY = float(os.environ.get("DELAY", "1.0"))
def get(url, site, cache=True):
    d = os.path.join(ROOT, site); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, hashlib.sha1(url.encode()).hexdigest() + ".html")
    if cache and os.path.exists(f): return open(f, encoding="utf-8").read()
    if not allowed(url): return None
    h = urlparse(url).netloc; w = DELAY - (time.time() - _last.get(h, 0))
    if w > 0: time.sleep(w)
    for attempt in range(4):
        _last[h] = time.time()
        try: r = S.get(url, timeout=30)
        except Exception as e: print("ERR", url, e, flush=True); return None
        if r.status_code != 429: break
        print("429 backoff", url, flush=True); time.sleep(60 * (attempt + 1))
    if r.status_code != 200: print(r.status_code, url, flush=True); return None
    open(f, "w", encoding="utf-8").write(r.text)
    with open(os.path.join(d, "_index.jsonl"), "a") as ix:
        ix.write(json.dumps({"url": url, "file": os.path.basename(f), "retrieved": time.strftime("%Y-%m-%d")}) + "\n")
    return r.text
def locs(xml): return re.findall(r"<loc>([^<]+)</loc>", xml or "")
def done(site):
    p = os.path.join(ROOT, site, "_index.jsonl")
    return {json.loads(l)["url"] for l in open(p)} if os.path.exists(p) else set()
def run_list(site, urls, cap):
    have = done(site); n = len(have)
    for u in urls:
        if n >= cap: break
        if u in have: continue
        if get(u, site): n += 1
    print(site, "DONE", n, flush=True)
def apple(cap):
    urls = [u for u in locs(get("https://support.apple.com/en-us/sitemaps/sitemap-en-us-ac-1.xml", "_sm", cache=False)) if re.search(r"/en-us/\d+$", u)]
    run_list("apple", urls, cap)
def microsoft(cap):
    urls = []
    for s in ["windows", "microsoft-365", "edge", "support", "teams", "surface"]:
        urls += [u for u in locs(get(f"https://support.microsoft.com/_sitemaps/{s}_en-us_1.xml", "_sm", cache=False)) if "/en-us/" in u]
    # interleave products
    run_list("microsoft", list(dict.fromkeys(urls)), cap)
def claude(cap):
    urls = [u for u in locs(get("https://support.claude.com/sitemap.xml", "_sm", cache=False)) if "/en/articles/" in u]
    run_list("claude", urls, cap)
def google(product, cap):
    site = "google_" + product; base = f"https://support.google.com/{product}"
    seen, q = set(), [base + "?hl=en"]; have = done(site); n = len(have)
    while q and n < cap:
        u = q.pop(0)
        if u in seen: continue
        seen.add(u); html = get(u, site)
        if not html: continue
        if u in have or "/answer/" in u: n += ("/answer/" in u)
        for m in re.findall(rf'href="(/{product}/(?:answer|topic)/\d+)', html):
            v = "https://support.google.com" + m + "?hl=en"
            if v not in seen: (q.insert(0, v) if "/topic/" in m else q.append(v))
    print(site, "DONE", n, flush=True)
if __name__ == "__main__":
    job, cap = sys.argv[1], int(sys.argv[2])
    if job == "google":
        for p in ["android", "youtube", "gemini", "chrome"]: google(p, cap)
        sys.exit()
    {"apple": apple, "microsoft": microsoft, "claude": claude}.get(job, lambda c: google(job, c))(cap)
