#!/usr/bin/env python3
"""Fetch official schedule/broadcast data for the Korea5 free-time planner.

Runs on GitHub Actions (runners have outbound internet). Every record written by
this script carries an official source URL. Nothing is invented: if a field is
absent from the official page it is left null/blank and reported in the fetch
report so it can be listed on the Flagged for Review page.

Outputs (committed by the workflow):
  official/nfl-2026.json         all NFL preseason + regular-season games, nfl.com
  official/westwoodone.json      Westwood One Sports national radio broadcasts
  official/w1-stations.json      Westwood One station-finder rows for San Francisco
  official/mlb-tbd.json          startTimeTBD flags from MLB StatsAPI
  official/fetch-report.json     counts, failures, retrieval time, source URLs
"""
import concurrent.futures
import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

OUT = "official"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5FreeTime/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}
PT = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

NFL_WEEK_SLUGS = (
    [("hall-of-fame-game", "Hall of Fame Game"), ("preseason-week-1", "Preseason Week 1"),
     ("preseason-week-2", "Preseason Week 2"), ("preseason-week-3", "Preseason Week 3")]
    + [(f"week-{i}", f"Week {i}") for i in range(1, 19)]
)
NFL_BASE = "https://www.nfl.com/schedules/2026/by-week/"

W1_BASE = "https://www.westwoodonesports.com"
W1_WIDGETS = {
    "NFL": ("https://www.westwoodonesports.com/nfl-schedule/", 47029),
    "NCAA Football": ("https://www.westwoodonesports.com/ncaa-football/", 47030),
    "NCAA Basketball": ("https://www.westwoodonesports.com/ncaa-basketball/", 47031),
    "U.S. Soccer": ("https://www.westwoodonesports.com/us-soccer/", 47032),
    "Golf": ("https://www.westwoodonesports.com/golf/", 47033),
    "NCAA MCWS": ("https://www.westwoodonesports.com/ncaa-mcws/", 47420),
    "NCAA WCWS": ("https://www.westwoodonesports.com/ncaa-wcws/", 47419),
    "NCAA Lacrosse": ("https://www.westwoodonesports.com/ncaa-lacrosse/", 47418),
    "NCAA Hockey": ("https://www.westwoodonesports.com/ncaa-hockey/", 47044),
}


def get(url, tries=3, timeout=60):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(1.0 + attempt)
    print(f"  ! failed {url}: {last}")
    return None


def jwrite(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def pt_parts(utc_iso):
    """Return (Pacific date, Pacific HH:MM, Pacific abbreviation) for a UTC ISO string."""
    d = dt.datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    p = d.astimezone(PT)
    return p.date().isoformat(), p.strftime("%H:%M"), p.tzname()


# --------------------------------------------------------------------------- NFL
def extract_rsc_queries(page):
    """Yield dehydrated react-query objects from NFL.com RSC payloads."""
    for raw in re.findall(r"self\.__next_f\.push\((\[.*?\])\)</script>", page, re.S):
        try:
            arr = json.loads(raw)
        except Exception:
            continue
        if not isinstance(arr, list) or len(arr) < 2 or not isinstance(arr[1], str):
            continue
        payload = arr[1]
        if ":" not in payload:
            continue
        try:
            obj = json.loads(payload.split(":", 1)[1])
        except Exception:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    yield cur
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def fetch_nfl_week(item):
    slug, label = item
    url = NFL_BASE + slug
    failures = []
    page = get(url)
    if page is None:
        return [], [f"{slug}: page fetch failed"], url
    games = []
    seen = set()
    for q in extract_rsc_queries(page):
        key = q.get("queryKey") or []
        if not key or key[0] != "useFetchFootballWeeklyGameDetails":
            continue
        data = (q.get("state") or {}).get("data")
        if not isinstance(data, list):
            continue
        for g in data:
            if not isinstance(g, dict):
                continue
            gid = g.get("id")
            if not gid or gid in seen:
                continue
            seen.add(gid)
            slugs = [x.get("id") for x in (g.get("externalIds") or [])
                     if isinstance(x, dict) and x.get("source") == "slug" and x.get("id")]
            game_url = ("https://www.nfl.com/games/" + slugs[0]) if slugs else url
            t = g.get("time")
            audio = ((g.get("broadcastInfo") or {}).get("audioNetworks") or [])
            w1 = any("WESTWOOD_ONE" in str(a.get("audience", "")) for a in audio if isinstance(a, dict))
            away = (g.get("awayTeam") or {}).get("fullName")
            home = (g.get("homeTeam") or {}).get("fullName")
            rec = {
                "id": "nfl-2026-" + str(gid),
                "league": "NFL",
                "season": 2026,
                "seasonType": g.get("seasonType"),
                "week": g.get("week"),
                "weekType": g.get("weekType"),
                "weekLabel": label,
                "category": g.get("category"),
                "away": away,
                "home": home,
                "title": (f"{away} at {home}" if away and home else None),
                "venue": (g.get("venue") or {}).get("name"),
                "status": g.get("status"),
                "startUTC": t,
                "datePT": None,
                "startPT": None,
                "timezone": None,
                "nationalRadio": "Westwood One Sports (national)" if w1 else None,
                "audioNetworks": [a.get("audience") for a in audio if isinstance(a, dict)],
                "tv": (g.get("broadcastInfo") or {}).get("homeNetworkChannels"),
                "priority": "high" if (w1 or "49ers" in (str(away) + str(home))) else "normal",
                "sourceUrl": game_url,
                "sourceName": "NFL.com official schedule/game page",
                "verification": "verified" if t else "unverified-no-time",
                "timeStatus": "verified" if t else "unverified",
            }
            if t:
                try:
                    rec["datePT"], rec["startPT"], rec["timezone"] = pt_parts(t)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{slug}/{gid}: bad time {t}: {e}")
            games.append(rec)
    if not games:
        failures.append(f"{slug}: no weekly-game query found")
    return games, failures, url


# ------------------------------------------------------------------ Westwood One
def w1_grid_url(widget_id, rng, offset):
    q = urllib.parse.urlencode({
        "id": widget_id, "range": rng, "offset": offset, "limit": 100,
        "timezone": "America/New_York", "widgetTitle": "Event Display",
    })
    return f"{W1_BASE}/more/eventGrid/?{q}"


def parse_w1_grid(page):
    """Return [{eventId, title, venue, description, monthDay}] from the official grid HTML."""
    out = []
    for block in page.split("<div class='event'>")[1:]:
        seg = block[:2500]
        eid = re.search(r"/events/(\d+)", seg)
        title = re.search(r"<div class='name'><a[^>]*>(.*?)</a>", seg, re.S)
        venue = re.search(r"<div class='venue'>(.*?)</div>", seg, re.S)
        desc = re.search(r"<div class='description'>(.*?)</div>", seg, re.S)
        day = re.search(r"<div class='date'[^>]*>\s*([A-Z]{3}\s+\d{1,2})\s*</div>", seg)
        if not eid:
            continue
        clean = lambda m: html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None  # noqa: E731
        out.append({
            "eventId": eid.group(1),
            "title": clean(title),
            "venue": clean(venue),
            "description": clean(desc),
            "monthDay": clean(day),
        })
    return out


def parse_w1_detail(event_id, category, stub, page):
    rec = {
        "id": "w1-" + event_id,
        "league": "Westwood One Sports",
        "sport": category,
        "priority": "high",
        "tags": ["westwoodone", "national-radio"],
        "title": stub.get("title"),
        "venue": stub.get("venue"),
        "description": stub.get("description"),
        "monthDay": stub.get("monthDay"),
        "sourceUrl": f"{W1_BASE}/events/{event_id}/",
        "sourceName": "Westwood One Sports official event page",
        "verification": "verified",
    }
    if page is None:
        rec.update({"startUTC": None, "endUTC": None, "datePT": None, "startPT": None,
                    "endPT": None, "timeStatus": "unverified", "verification": "unverified-page-fetch"})
        return rec
    st = re.search(r"class='start_time'[^>]*data-time='(\d+)'", page)
    en = re.search(r"class='end_time'[^>]*data-time='(\d+)'", page)
    ld = re.search(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S)
    if ld:
        try:
            obj = json.loads(html.unescape(ld.group(1)))
            if isinstance(obj, dict):
                rec["title"] = rec["title"] or obj.get("name")
                rec["description"] = rec["description"] or obj.get("description")
                if not rec["venue"]:
                    loc = obj.get("location") or {}
                    rec["venue"] = loc.get("name") if isinstance(loc, dict) else None
        except Exception:
            pass
    if st:
        s = dt.datetime.fromtimestamp(int(st.group(1)), UTC)
        rec["startUTC"] = s.isoformat().replace("+00:00", "Z")
        p = s.astimezone(PT)
        rec["datePT"] = p.date().isoformat()
        rec["startPT"] = p.strftime("%H:%M")
        rec["timezone"] = p.tzname()
        rec["timeStatus"] = "verified"
    else:
        rec["timeStatus"] = "unverified"
    if en:
        e = dt.datetime.fromtimestamp(int(en.group(1)), UTC)
        rec["endUTC"] = e.isoformat().replace("+00:00", "Z")
        rec["endPT"] = e.astimezone(PT).strftime("%H:%M")
        rec["durationMin"] = int((e - dt.datetime.fromtimestamp(int(st.group(1)), UTC)).total_seconds() // 60)
    else:
        rec["endUTC"] = None
        rec["endPT"] = None
        rec["durationMin"] = None
    if not rec.get("startUTC"):
        rec["verification"] = "unverified-no-time"
    return rec


def fetch_w1():
    stubs = {}
    grid_sources = []
    failures = []
    for category, (page_url, wid) in W1_WIDGETS.items():
        for rng in ("current", "past"):
            for offset in (0, 100, 200, 300):
                u = w1_grid_url(wid, rng, offset)
                page = get(u)
                grid_sources.append(u)
                if page is None:
                    failures.append(f"W1 {category}/{rng}/{offset}: grid fetch failed")
                    continue
                rows = parse_w1_grid(page)
                for r in rows:
                    stubs.setdefault(r["eventId"], dict(r, category=category, widgetId=wid))
                if len(rows) < 100:
                    break
                time.sleep(0.15)
    def one(item):
        eid, stub = item
        page = get(f"{W1_BASE}/events/{eid}/", tries=2, timeout=45)
        return parse_w1_detail(eid, stub["category"], stub, page)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        events = list(ex.map(one, stubs.items()))
    events.sort(key=lambda e: (e.get("startUTC") or "9999", e["id"]))
    return events, grid_sources, failures


# ------------------------------------------------------------------ W1 stations
def fetch_w1_stations():
    url = W1_BASE + "/station-finder/"
    page = get(url)
    rows = []
    if page:
        for tr in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", page, re.S):
            city = html.unescape(re.sub(r"<[^>]+>", "", tr[0])).strip()
            call = html.unescape(re.sub(r"<[^>]+>", "", tr[1])).strip()
            if "San Francisco" in city:
                rows.append({"market": city, "callLetters": call})
    # de-duplicate
    uniq = {r["callLetters"]: r for r in rows}
    return {
        "sourceUrl": url,
        "sourceName": "Westwood One Sports official Station Finder",
        "market": "San Francisco, CA (Outer Sunset 94122 AM/FM reception area)",
        "note": "Westwood One station-finder lists affiliates by market; it does not publish exact frequencies. "
                "Because of local blackouts and programming conflicts, not every affiliate airs every broadcast.",
        "affiliates": sorted(uniq.values(), key=lambda r: r["callLetters"]),
    }


# ------------------------------------------------------------------- MLB TBD flags
def fetch_mlb_tbd():
    flags = {}
    sources = []
    failures = []
    fields = "dates,date,games,gamePk,gameDate,gameType,status,startTimeTBD,detailedState"
    for year in (2026, 2027):
        for m in range(2, 12):
            start = dt.date(year, m, 1)
            end = dt.date(year + (m // 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
            u = "https://statsapi.mlb.com/api/v1/schedule?" + urllib.parse.urlencode({
                "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
                "fields": fields,
            })
            sources.append(u)
            raw = get(u, tries=2)
            if raw is None:
                failures.append(f"MLB {year}-{m:02d}: fetch failed")
                continue
            try:
                data = json.loads(raw)
            except Exception as e:  # noqa: BLE001
                failures.append(f"MLB {year}-{m:02d}: JSON error {e}")
                continue
            for d in data.get("dates", []):
                for g in d.get("games", []):
                    flags[str(g.get("gamePk"))] = {
                        "startTimeTBD": bool((g.get("status") or {}).get("startTimeTBD")),
                        "detailedState": (g.get("status") or {}).get("detailedState"),
                        "gameDate": g.get("gameDate"),
                        "gameType": g.get("gameType"),
                    }
    return {
        "sourceUrl": "https://statsapi.mlb.com/api/v1/schedule",
        "sourceName": "MLB StatsAPI (official Major League Baseball data service)",
        "note": "startTimeTBD is MLB's own flag. When true, gameDate is a placeholder and no exact first-pitch time "
                "is confirmed; the site leaves the start-time cell blank and flags the row.",
        "sourceQueries": sources,
        "flags": flags,
    }, failures


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {
        "generatedUTC": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sources": {},
        "failures": [],
        "counts": {},
    }

    print("NFL by-week pages ...")
    nfl = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for games, fails, url in ex.map(fetch_nfl_week, NFL_WEEK_SLUGS):
            nfl.extend(games)
            report["failures"].extend(fails)
    nfl.sort(key=lambda g: (g.get("startUTC") or "9999", g["id"]))
    jwrite("nfl-2026.json", {
        "meta": {
            "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-9",
            "sourceName": "NFL.com official 2026 schedule (by-week pages)",
            "sourcePages": [NFL_BASE + s for s, _ in NFL_WEEK_SLUGS],
            "retrievedUTC": report["generatedUTC"],
            "note": "Game records are extracted from NFL.com's own embedded schedule data. Pacific times are "
                    "converted from NFL.com UTC kickoff times using the America/Los_Angeles zone (PST/PDT). "
                    "Postseason matchups for Jan-Feb 2027 were not published as game records on 2026-11-02; "
                    "their official calendar windows are listed separately in season-anchors.json.",
        },
        "games": nfl,
    })
    report["counts"]["nflGames"] = len(nfl)
    report["sources"]["nfl"] = "https://www.nfl.com/schedules/2026/by-week/week-9"

    print("Westwood One events ...")
    w1, grid_sources, w1_fail = fetch_w1()
    report["failures"].extend(w1_fail)
    jwrite("westwoodone.json", {
        "meta": {
            "sourceUrl": "https://www.westwoodonesports.com/nfl-schedule/",
            "sourceName": "Westwood One Sports official schedule and event pages",
            "categoryPages": {k: v[0] for k, v in W1_WIDGETS.items()},
            "gridQueries": grid_sources[:12],
            "retrievedUTC": report["generatedUTC"],
            "note": "National radio broadcast windows come from each official event page's start_time/end_time "
                    "epoch attributes (America/New_York on the source page), converted to UTC and Pacific. "
                    "These are network on-air windows, not game durations. All Westwood One Sports broadcasts "
                    "are treated as high priority in this project.",
        },
        "events": w1,
    })
    report["counts"]["westwoodOneEvents"] = len(w1)
    report["sources"]["westwoodone"] = "https://www.westwoodonesports.com/nfl-schedule/"

    print("Westwood One station finder ...")
    stations = fetch_w1_stations()
    jwrite("w1-stations.json", stations)
    report["counts"]["w1SfAffiliates"] = len(stations["affiliates"])

    print("MLB startTimeTBD flags ...")
    mlb_tbd, mlb_fail = fetch_mlb_tbd()
    report["failures"].extend(mlb_fail)
    jwrite("mlb-tbd.json", mlb_tbd)
    report["counts"]["mlbTbdFlags"] = len(mlb_tbd["flags"])
    report["sources"]["mlb"] = "https://statsapi.mlb.com/api/v1/schedule"

    jwrite("fetch-report.json", report)
    print(json.dumps({"counts": report["counts"], "failures": report["failures"][:20]}, indent=2))


if __name__ == "__main__":
    main()
