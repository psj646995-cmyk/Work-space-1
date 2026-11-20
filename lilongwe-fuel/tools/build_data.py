"""Validate data/*.json and write site/data.json (the file the map page reads).
Run after every update:  python3 tools/build_data.py
Exits non-zero with a message if anything is invalid, so a bad update never gets published."""
import json, sys, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"
STATES = {"available", "delivering", "scheduled", "out"}
SOURCES = {"mera", "news", "company", "screenshot"}
errs = []
def ts(v, where):
    try:
        t = datetime.datetime.fromisoformat(v)
        if t.tzinfo is None: errs.append(f"{where}: time needs a timezone offset (+02:00): {v}")
        return t
    except Exception: errs.append(f"{where}: bad time {v!r}")
def bi(v, where):
    if not (isinstance(v, dict) and v.get("ko") and v.get("en")): errs.append(f"{where}: needs both ko and en text")
stations = json.load(open(D / "stations.json"))
status = json.load(open(D / "status.json"))
notices = json.load(open(D / "notices.json"))
meta = json.load(open(D / "meta.json"))
# Lilongwe City "Area N" boundaries (OCHA). Every station gets the Area it sits in, so the page can search by Area.
areas = json.load(open(D / "areas.json"))["areas"]
def inside(x, y, ring):
    c = False
    for i in range(len(ring)):
        x1, y1 = ring[i]; x2, y2 = ring[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def seg_m(px, py, ax, ay, bx, by):
    k = 108000  # metres per degree of longitude at Lilongwe's latitude; latitude uses 110600
    px, ax, bx = px * k, ax * k, bx * k; py, ay, by = py * 110600, ay * 110600, by * 110600
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** .5
def area_of(lon, lat, max_gap_m=500):
    for a in areas:
        if any(inside(lon, lat, r) for r in a["rings"]): return a["n"]
    # boundaries leave small gaps (roads, edges): take the nearest Area within max_gap_m
    best = min(((min(seg_m(lon, lat, *r[i - 1], *r[i]) for r in a["rings"] for i in range(1, len(r))), a["n"]) for a in areas))
    return best[1] if best[0] <= max_gap_m else None
ids = set()
for s in stations:
    s["area"] = area_of(s["lon"], s["lat"])
    for k in ("id", "name", "lat", "lon"):
        if s.get(k) in (None, ""): errs.append(f"station {s.get('id')}: missing {k}")
    if s["id"] in ids: errs.append(f"duplicate station id {s['id']}")
    ids.add(s["id"])
    if not (-14.3 < s["lat"] < -13.7 and 33.5 < s["lon"] < 34.0): errs.append(f"station {s['id']}: outside Lilongwe")
for sid, fu in status.items():
    if sid not in ids: errs.append(f"status: unknown station id {sid}")
    for fuel, e in fu.items():
        w = f"status {sid}.{fuel}"
        if fuel not in ("petrol", "diesel"): errs.append(f"{w}: fuel must be petrol or diesel"); continue
        if e.get("state") not in STATES: errs.append(f"{w}: state must be one of {sorted(STATES)}")
        if e.get("source") not in SOURCES: errs.append(f"{w}: source must be one of {sorted(SOURCES)}")
        ts(e.get("at", ""), w)
        if "note" in e: bi(e["note"], w + ".note")
for i, n in enumerate(notices):
    w = f"notice {n.get('id', i)}"
    ts(n.get("at", ""), w); bi(n.get("title"), w + ".title"); bi(n.get("summary"), w + ".summary")
    if n.get("source") not in SOURCES: errs.append(f"{w}: bad source")
    for sid in n.get("stations", []):
        if sid not in ids: errs.append(f"{w}: unknown station {sid}")
ts(meta.get("lastCheck", ""), "meta.lastCheck"); bi(meta.get("lastResult"), "meta.lastResult")
if errs:
    print("INVALID DATA:\n- " + "\n- ".join(errs)); sys.exit(1)
notices.sort(key=lambda n: n["at"], reverse=True)
out = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
       "meta": meta, "stations": stations, "areas": areas, "status": status, "notices": notices[:60]}
(ROOT / "site" / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"ok: {len(stations)} stations ({sum(1 for s in stations if s['area'])} inside a Lilongwe Area), {sum(len(v) for v in status.values())} fuel statuses, {len(notices)} notices")
