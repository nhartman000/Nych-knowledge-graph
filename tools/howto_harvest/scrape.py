"""Polite resumable scraper for harvest job B. One request per host at a time (host lock), delay = max(DELAY, robots Crawl-delay),
robots.txt checked per URL with our UA, 429 -> exponential backoff, raw HTML cached under $HOWTO_RAW/<source>/ with _index.jsonl
(url, file, retrieved, domain, platform). Rerun to resume. Hard stop: STOP_AT=HH:MM (box-local time).
Usage: python scrape.py [source ...]"""
import gzip, hashlib, json, os, re, sys, time, threading, urllib.robotparser as rp
from urllib.parse import urljoin, urlparse, urldefrag
import requests
sys.path.insert(0, os.path.dirname(__file__))
from sources import SOURCES, classify
UA = "NYCH-research-bot/0.1 (+procedural-text research; polite, 1 request per host at a time)"
RAW = os.environ.get("HOWTO_RAW", "/workspace/howto_raw")
DELAY = float(os.environ.get("DELAY", "2.0")); STOP_AT = os.environ.get("STOP_AT", "15:15")
S = requests.Session(); S.headers["User-Agent"] = UA
_robots, _locks, _last, _g = {}, {}, {}, threading.Lock()
STATS = {}
def stop():
    return time.strftime("%H:%M") >= STOP_AT
def lock(h):
    with _g: return _locks.setdefault(h, threading.Lock())
def robots(h):
    if h not in _robots:
        r = rp.RobotFileParser()
        try: t = S.get(f"https://{h}/robots.txt", timeout=30); lines = t.text.splitlines() if t.status_code == 200 else []
        except Exception: lines = []
        r.parse(lines); _robots[h] = r
    return _robots[h]
def fetch(url, cache_dir=None):
    h = urlparse(url).netloc; r0 = robots(h)
    if not r0.can_fetch(UA, url): return None, "robots"
    d = max(DELAY, float(r0.crawl_delay(UA) or 0))
    with lock(h):
        for attempt in range(5):
            w = d - (time.time() - _last.get(h, 0))
            if w > 0: time.sleep(w)
            _last[h] = time.time()
            try: r = S.get(url, timeout=40)
            except Exception as e: return None, f"err:{type(e).__name__}"
            if r.status_code == 429 or r.status_code == 503:
                ra = r.headers.get("Retry-After", ""); time.sleep(int(ra) if ra.isdigit() else 30 * 2 ** attempt); continue
            break
    if r.status_code != 200: return None, str(r.status_code)
    c = r.content
    if url.endswith(".gz") or c[:2] == b"\x1f\x8b":
        try: c = gzip.decompress(c)
        except Exception: pass
    return c.decode(r.encoding or "utf-8", "replace") if isinstance(c, bytes) else c, "ok"
def sitemap_urls(sm, depth=0, out=None):
    out = [] if out is None else out
    x, st = fetch(sm)
    if not x: print("sitemap fail", sm, st, flush=True); return out
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", x)
    if "<sitemapindex" in x and depth < 3:
        for l in locs:
            if stop(): break
            sitemap_urls(l.replace("&amp;", "&"), depth + 1, out)
    else: out += [l.replace("&amp;", "&") for l in locs]
    return out
def run(src):
    name = src["name"]; d = os.path.join(RAW, name); os.makedirs(d, exist_ok=True); ix = os.path.join(d, "_index.jsonl")
    have = {json.loads(l)["url"] for l in open(ix)} if os.path.exists(ix) else set()
    st = STATS.setdefault(name, {"fetched": len(have), "new": 0, "fail": {}, "skipped_offtopic": 0})
    cand_f = os.path.join(d, "_candidates.json")
    if os.path.exists(cand_f): cands = json.load(open(cand_f))
    else:
        cands = []
        for sm in src.get("sitemaps", []): cands += sitemap_urls(sm)
        cands += src.get("seeds", [])
        cands = list(dict.fromkeys(cands)); json.dump(cands, open(cand_f, "w"))
    inc = re.compile(src["include"]); crawl = re.compile(src["crawl"]) if src.get("crawl") else None
    q = [u for u in cands if inc.search(u) or (crawl and crawl.search(u)) or u in src.get("seeds", [])]
    seen = set(q); i = 0
    print(name, "candidates", len(q), "have", len(have), flush=True)
    while i < len(q) and st["fetched"] < src["cap"] and not stop():
        u = q[i]; i += 1
        dom = src["domain"]
        if src.get("classify"):
            dom = classify(u, "", None)
            if dom is None and not crawl: st["skipped_offtopic"] += 1; continue
            dom = dom or src["domain"]
        f = os.path.join(d, hashlib.sha1(u.encode()).hexdigest() + ".html")
        if u in have and os.path.exists(f):
            html = open(f, encoding="utf-8").read()
        else:
            html, s = fetch(u)
            if not html: st["fail"][s] = st["fail"].get(s, 0) + 1; continue
            open(f, "w", encoding="utf-8").write(html)
            with open(ix, "a") as w:
                w.write(json.dumps({"url": u, "file": os.path.basename(f), "retrieved": time.strftime("%Y-%m-%d"), "domain": dom, "platform": src["platform"]}) + "\n")
            have.add(u); st["fetched"] += 1; st["new"] += 1
        if crawl:
            for m in re.findall(r'href="([^"#]+)"', html):
                v = urldefrag(urljoin(u, m.replace("&amp;", "&")))[0].rstrip("/")
                if v not in seen and crawl.search(v): seen.add(v); q.append(v)
    print(name, "DONE", st, flush=True)
def checkpoint():
    while True:
        time.sleep(3600)
        json.dump({"at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "stats": STATS}, open(os.path.join(RAW, f"_checkpoint_{time.strftime('%H%M')}.json"), "w"), indent=1)
if __name__ == "__main__":
    want = set(sys.argv[1:])
    threading.Thread(target=checkpoint, daemon=True).start()
    ts = [threading.Thread(target=run, args=(s,)) for s in SOURCES if not want or s["name"] in want]
    [t.start() for t in ts]; [t.join() for t in ts]
    json.dump({"at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "stats": STATS}, open(os.path.join(RAW, "_checkpoint_final.json"), "w"), indent=1)
