# Lilongwe Fuel Map: update runbook

The page is published at **https://claude.ai/artifact/KoZN8Rvj4fmS3mSuFnbvBa**. Its live data is the
published file `data.json`. That file is the source of truth, not the copy in git.

A scheduled task runs this runbook six times a day (06, 09, 12, 15, 18, 21 h Malawi time). A person can also
send a screenshot of a MERA Facebook post. Follow "Screenshot update" below for that.

## Rules
- Never invent information. Every status needs a real source you read in this run: a MERA notice, a news
  article or company post, or a screenshot the user sent. When unsure, leave the station as it is and only add a notice.
- Times are Malawi time (CAT, `+02:00`). `at` is when the source published the information, not when you read it.
  WordPress `date_gmt` is UTC, so add 2 hours.
- Every note, title and summary needs both `ko` (Korean) and `en` (English).
- WebFetch has no network access in these sessions. Use Bash (`curl` / `python3`), which does.
- MERA's Facebook (facebook.com/MERAMalawi) needs a login. Do not try to scrape it or work around the login.
  News sites sometimes copy MERA's posts as text or as a screenshot image: read those.

## Steps (scheduled run)
1. Get the tools: `git fetch origin claude/ecstatic-wozniak-qxm44k && git checkout FETCH_HEAD -- lilongwe-fuel`
2. Get the live data. Use the Artifact tool: `action: "read"`, `url` = the artifact URL, `path: "data.json"`.
   Then `python3 lilongwe-fuel/tools/restore_from_published.py <saved data.json path>`.
3. Collect sources: `python3 lilongwe-fuel/tools/fetch_sources.py 36 > /tmp/sources.txt`, then read it.
   Posts listed in `meta.seen` are skipped automatically. Also run one WebSearch (standard) for
   `MERA fuel delivery schedule Lilongwe filling stations` to catch sources the script doesn't cover.
   If a post has an image that looks like a MERA schedule or Facebook screenshot (see `IMAGES:`), download it
   with curl and read it with the Read tool.
4. Update `lilongwe-fuel/data/` (edit the JSON files with Python or Edit):
   - `status.json`: `{ "<station id>": { "petrol": {...}, "diesel": {...} } }`, each entry
     `{"state", "at", "source", "url", "note": {"ko","en"}}`.
     - `state`: `scheduled` (MERA says a delivery is planned), `delivering` (tanker arrived / offloading),
       `available` (selling), `out` (sold out / dry).
     - `source`: `mera`, `news`, `company` or `screenshot`.
     - Replace an entry only with newer information (`at` later than the existing one).
   - Match station names to `stations.json` by brand plus road, area or alias. Use `lat`/`lon` to break ties.
     If a station in Lilongwe is named but missing, add it to `stations.json`. To find its coordinates,
     search Nominatim with curl (`https://nominatim.openstreetmap.org/search?q=...&format=jsonv2`, with a
     User-Agent and at most 1 request per second). Use `"added": "<source>"`. If you can't place it reliably
     within ~150 m, don't add it. Mention it in the notice instead.
   - `notices.json`: add one notice per relevant source (newest info first is handled by the build).
     Use `stations` to list the station ids it affects.
   - `meta.json`: set `lastCheck` to now (+02:00) and `lastResult` (ko/en, one sentence: what was checked and
     what changed). Add every URL you read to `seen`, keeping the last 400. Add a line to `runLog`
     (`{"at", "by": "scheduled", "summary"}`), keeping the last 60.
5. `python3 lilongwe-fuel/tools/build_data.py`. It must print `ok`. If it doesn't, fix the data.
6. Publish only the data file to the existing artifact: Artifact publish with
   `url` = the artifact URL, `files: {"data.json": "lilongwe-fuel/site/data.json"}` and no page changes.
   If you were refused because you hadn't read it, you already read it in step 2. Retry once.
   Also publish when nothing changed, so `lastCheck` moves and readers can see the check ran.
7. Improve the automation when you learn something. Examples: a source moved, a new site that republishes MERA
   schedules, a station alias. Put tool changes in `lilongwe-fuel/tools/` or this file. Commit and push them on
   this session's own branch, and mention them in `runLog` so the owner can merge them.

## Screenshot update (a person sends a MERA post image)
Read the image. List every Lilongwe station and fuel it names, with the date and time on the post.
Use `state: "scheduled"` for a delivery schedule, `source: "screenshot"` and `url` = the MERA Facebook page.
Then do steps 1, 2, 4, 5 and 6, and reply with what was added.

## Freshness on the page
Info older than 24 h is faded. After 72 h, a station shows "no info" again, with the old status kept in its detail view.
The thresholds are `STALE_H` / `EXPIRE_H` in `site/index.src.html`.
