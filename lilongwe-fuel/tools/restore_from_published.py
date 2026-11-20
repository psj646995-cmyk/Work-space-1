"""Split a published data.json back into data/*.json so a fresh session continues from the live state.
Usage: python3 tools/restore_from_published.py /path/to/published/data.json"""
import json, sys, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
d = json.load(open(sys.argv[1]))
for k in ("stations", "status", "notices", "meta"):
    (R / "data" / f"{k}.json").write_text(json.dumps(d[k], ensure_ascii=False, indent=1))
print(f"restored: {len(d['stations'])} stations, {len(d['status'])} with status, {len(d['notices'])} notices, last check {d['meta']['lastCheck']}")
