"""Collect recent fuel-related posts from sources that can be read without a login.
Usage: python3 tools/fetch_sources.py [hours=48] > /tmp/sources.txt
Prints each new post (title, date, link, cleaned text) so Claude can read it and update data/.
Posts already listed in data/meta.json "seen" are skipped unless --all is given."""
import json, re, sys, html, datetime, urllib.request, urllib.parse, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
hours = int(next((a for a in sys.argv[1:] if a.isdigit()), 48))
show_all = "--all" in sys.argv
seen = set(json.load(open(ROOT / "data/meta.json")).get("seen", []))
WP = {  # name: (base, source type, use search)
    "MERA": ("https://mera.mw", "mera", False),
    "Nyasa Times": ("https://www.nyasatimes.com", "news", True),
    "Malawi24": ("https://malawi24.com", "news", True),
    "Nation": ("https://mwnation.com", "news", True),
    "Times": ("https://times.mw", "news", True),
    "Malawi Voice": ("https://www.malawivoice.com", "news", True),
}
KEY = re.compile(r"\b(fuel|petrol|diesel|filling station|service station|tanker|MERA|NOCMA|oil marketing)\b", re.I)
LOCAL = re.compile(r"(?i:lilongwe|kanengo|chinsapo|kawale|biwi|old town|city cent|mount meru|delivery schedule|filling stations? (?:scheduled|to receive))|\bArea \d+|\b(?:Puma|Total(?:Energies)?|Petroda|Engen|Energem|Mt Meru)\b")
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lilongwe-fuel-map)"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf8", "ignore")
def clean(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S)
    h = re.sub(r"<br\s*/?>|</p>|</li>|</tr>|</h\d>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", html.unescape(h))).strip()
since = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=hours)
out, errors = [], []
for name, (base, typ, search) in WP.items():
    q = {"per_page": 20, "after": since.strftime("%Y-%m-%dT%H:%M:%S"), "_fields": "date,date_gmt,link,title,content"}
    if search: q["search"] = "fuel"
    try:
        posts = json.loads(get(f"{base}/wp-json/wp/v2/posts?" + urllib.parse.urlencode(q)))
    except Exception as e:
        errors.append(f"{name}: {e}"); continue
    for p in posts:
        title = clean(p["title"]["rendered"]); text = clean(p["content"]["rendered"])
        if p["link"] in seen and not show_all: continue
        if not KEY.search(title + " " + text): continue
        local = bool(LOCAL.search(title + " " + text))
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', p["content"]["rendered"])
        out.append(dict(source=name, type=typ, date_gmt=p.get("date_gmt"), link=p["link"], title=title, local=local, images=imgs[:6], text=text[:6000]))
out.sort(key=lambda x: (x["local"], x["date_gmt"] or ""), reverse=True)
print(f"# {len(out)} new fuel-related posts in the last {hours} h (Lilongwe-related first)")
for e in errors: print("# SOURCE ERROR", e)
for x in out:
    print("\n" + "=" * 80)
    print(f"[{x['source']} · {x['type']}] {x['title']}\nPUBLISHED (UTC): {x['date_gmt']}\nURL: {x['link']}\nLILONGWE-RELATED: {x['local']}")
    if x["images"]: print("IMAGES:", " ".join(x["images"]))
    print("-" * 80 + "\n" + x["text"])
