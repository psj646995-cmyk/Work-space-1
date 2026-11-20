"""Merge OSM fuel points (Nominatim + OpenFreeMap POIs) into data/stations.json.
Usage: python3 build_stations.py nominatim.json pois.json ../data/stations.json"""
import json, math, re, sys
nomi, pois, out = sys.argv[1:4]
BRANDS = [("TotalEnergies", r"total"), ("Puma", r"puma"), ("Petroda", r"petroda"), ("Engen", r"engen"),
          ("Mount Meru", r"m(oun)?t\.? ?mee?ru|^meru"), ("Energem", r"energe?m"), ("BP", r"^bp$"), ("Best Oil", r"best oil")]
def brand(n):
    for b, rx in BRANDS:
        if n and re.search(rx, n, re.I): return b
    return None
pts = []
for x in json.load(open(nomi)):
    a = x.get("address") or {}
    pts.append(dict(n=x.get("name") or None, lat=float(x["lat"]), lon=float(x["lon"]), road=a.get("road"), osm=x["osm_type"][0] + str(x["osm_id"])))
for x in json.load(open(pois)):
    pts.append(dict(n=x.get("n"), lat=x["p"][1], lon=x["p"][0], road=None, osm=None))
def dist(a, b): return math.hypot((a["lat"] - b["lat"]) * 110600, (a["lon"] - b["lon"]) * 108000)
clusters = []
for q in pts:
    bq = brand(q["n"])
    for c in clusters:
        bc = next((brand(m["n"]) for m in c if brand(m["n"])), None)
        if any(dist(q, m) < 45 for m in c) and (bq is None or bc is None or bq == bc):
            c.append(q); break
    else: clusters.append([q])
ROAD_FIX = {"M1": "M1", "M12": "M12", "M14": "M14"}
stations, used = [], set()
for c in clusters:
    names = [m["n"] for m in c if m["n"]]
    b = next((brand(n) for n in names if brand(n)), None)
    road = next((m["road"] for m in c if m["road"]), None)
    lat = sum(m["lat"] for m in c) / len(c); lon = sum(m["lon"] for m in c) / len(c)
    if lat < -14.12 or lat > -13.84: continue
    generic = {n for n in names if re.fullmatch(r"(?i)(total|puma|petroda|engen|energe?m|bp)( filling station| fuelstation \d+)?", n.strip())}
    special = [n for n in names if n not in generic]
    label = special[0].strip() if special else ((b or "Filling station") + (" · " + road if road else ""))
    label = re.sub(r"\s+", " ", label)
    slug = re.sub(r"[^a-z0-9]+", "-", ((b or "station") + "-" + (road or f"{lat:.3f}{lon:.3f}")).lower()).strip("-")
    base, k = slug, 2
    while slug in used: slug = f"{base}-{k}"; k += 1
    used.add(slug)
    stations.append(dict(id=slug, name=label, brand=b, road=road, lat=round(lat, 5), lon=round(lon, 5),
                         aliases=sorted(set(names)), osm=[m["osm"] for m in c if m["osm"]], added="osm"))
stations.sort(key=lambda s: (s["brand"] or "~", s["name"]))
json.dump(stations, open(out, "w"), ensure_ascii=False, indent=1)
print(len(stations))
for s in stations: print(s["id"], "|", s["name"], "|", s["aliases"])
