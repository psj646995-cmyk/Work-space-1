# 릴롱궤 연료 지도 / Lilongwe Fuel Map

**지도 / Map:** https://claude.ai/artifact/KoZN8Rvj4fmS3mSuFnbvBa

릴롱궤 주유소 48곳(OpenStreetMap)의 휘발유·경유 상태를 MERA 공지, 현지 뉴스, 정유사 공지를 바탕으로 보여줍니다.
매일 06·09·12·15·18·21시(말라위 시간)에 Claude가 자동으로 확인하고 업데이트합니다. 페이스북 MERA 게시물은
로그인 없이 읽을 수 없어서, 급한 공지는 캡처를 Claude에게 보내면 반영합니다.

Shows petrol and diesel status at 48 Lilongwe filling stations (from OpenStreetMap), based on MERA notices, local news
and oil company notices. Claude checks automatically six times a day. MERA's Facebook needs a login, so urgent posts
are added from screenshots.

| Path | What |
|---|---|
| `site/index.src.html` | Page source (edit this) → `tools/build_page.py` → `site/index.html` |
| `site/basemap.json` | Roads, water, parks and labels drawn on the map (OpenStreetMap via OpenFreeMap) |
| `data/*.json` | Stations, statuses, notices, run info → `tools/build_data.py` validates → `site/data.json` |
| `tools/fetch_sources.py` | Collects new fuel posts from MERA and news sites |
| `AUTOMATION.md` | Step-by-step runbook each automatic run follows |

Rebuild the basemap: `tools/vt.py` (download tiles) → `tools/extract.py` → `tools/compact_basemap.py`.
Rebuild the station list: `tools/build_stations.py` (then re-apply name fixes by hand).
