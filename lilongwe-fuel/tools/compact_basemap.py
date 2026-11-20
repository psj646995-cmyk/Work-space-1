"""Shrink the extracted basemap: simplify lines and round coordinates.
Usage: python3 compact_basemap.py basemap_raw.json labels.json ../site/basemap.json"""
import json, sys
from shapely.geometry import LineString, Polygon
raw, labels, out = sys.argv[1:4]
d = json.load(open(raw))
def sl(l, tol, nd):
    if len(l) < 3: return [[round(x, nd), round(y, nd)] for x, y in l]
    s = LineString(l).simplify(tol, preserve_topology=False)
    return [[round(x, nd), round(y, nd)] for x, y in s.coords]
def sp(rings, tol, nd):
    o = []
    for r in rings:
        if len(r) < 4: continue
        p = Polygon(r).simplify(tol)
        if p.is_empty or p.area < 2e-7: continue
        o.append([[round(x, nd), round(y, nd)] for x, y in p.exterior.coords])
    return o
res = {"roads": {}}
for k, ls in d["roads"].items():
    tol, nd = (0.00006, 4) if k == "minor" else (0.00003, 5)
    res["roads"][k] = [x for x in (sl(l, tol, nd) for l in ls) if len(x) > 1]
res["water"] = [x for x in (sp(p, 0.0001, 4) for p in d["water"]) if x]
res["parks"] = [x for x in (sp(p, 0.0001, 4) for p in d["parks"]) if x]
res["aero"] = [x for x in (sp(p, 0.0001, 4) for p in d["aero"]) if x]
res["rivers"] = [x for x in (sl(l, 0.0001, 4) for l in d["rivers"]) if len(x) > 1]
res["labels"] = json.load(open(labels))
res["attribution"] = "© OpenStreetMap contributors · OpenFreeMap / OpenMapTiles"
json.dump(res, open(out, "w"), separators=(",", ":"))
import os; print(os.path.getsize(out))
