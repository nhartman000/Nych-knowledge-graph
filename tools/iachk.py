# archive.org item check: page-number JSON + djvu text availability (usage: python tools/iachk.py <identifier>)
import json,sys,urllib.request,urllib.parse,re,time
i=sys.argv[1]
m=json.load(urllib.request.urlopen(f"https://archive.org/metadata/{i}",timeout=60))
files=[f["name"] for f in m.get("files",[])]
pn=[f for f in files if f.endswith("_page_numbers.json")]
txt=[f for f in files if f.endswith("_djvu.txt")][0]
t=None
for k in range(3):
    try:
        t=urllib.request.urlopen(f"https://archive.org/download/{i}/{urllib.parse.quote(txt)}",timeout=90).read().decode("utf-8","replace"); break
    except Exception as e:
        err=e; time.sleep(6)
pages=None
if pn:
    try:
        d=json.load(urllib.request.urlopen(f"https://archive.org/download/{i}/{urllib.parse.quote(pn[0])}",timeout=60))
        pages=(d.get("confidence"), sum(1 for p in d.get("pages",[]) if p.get("pageNumber")))
    except Exception as e: pages=("err",str(e)[:40])
if t is None:
    print("==",i,"TXT FAIL",err); sys.exit()
words=re.findall(r"[A-Za-z]+",t); bad=sum(1 for w in words if len(w)>2 and not re.search(r"[aeiouy]",w.lower()))
imp=len(re.findall(r"(?:^|[.;:]\s+)(Cut|Place|Hold|Take|Put|Apply|Remove|Fill|Wash|Heat|Strike|Lay|Tie|Turn|Dig|Plant|Sew|Pack|Boil|Cover|Pull|Push|Draw|Keep|Make|Spread|Set|Bend|Raise|Press|Fold|Baste|Hem|Mix|Sow|Thin|Water|Bring|Allow|Lift|Grasp|Wrap|Lower|Do|Never)\b",t))
s=t[len(t)//3:len(t)//3+260]
print("==",i,"| txt",txt,"| chars",len(t),"| vowelless%",round(100*bad/max(1,len(words)),2),"| imperative-starts",imp,"| printed page map",pages,"\n   sample:",re.sub(r"\s+"," ",s))
