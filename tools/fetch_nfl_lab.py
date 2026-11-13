#!/usr/bin/env python3
"""NFL Signal Lab official-data fetcher (runs on GitHub Actions: the sandbox has no outbound network).

Collects ONLY data that the NFL publishes itself, and never fills a field that the official
page does not carry:

  1. 2026 by-week schedule pages      -> per-game result rows (status, scores, venue, teams)
  2. 2026 weekly official injury pages -> per-player practice / game status rows
  3. 2026 official team statistics page-> points-for / points-against cross-check rows
  4. endpoint probe                     -> HTTP status for candidate official endpoints used to
                                           record which sources exist (inactives, in-game injury CSV)

Outputs (committed by .github/workflows/nfl-lab.yml):
  official/lab/results-2026.json
  official/lab/injuries-2026.json
  official/lab/team-stats-2026.json
  official/lab/probe-report.json
  official/lab/fetch-report.json

Rules enforced here:
  * every row carries `sourceUrl` (the exact official page it came from) and `sourceName`;
  * a value absent from the official payload stays `null` and is counted in the fetch report;
  * nothing is transcribed by hand, so nothing can be invented.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = "official/lab"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5SignalLab/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}
SEASON = 2026
NFL_WEEK_SLUGS = [(f"week-{i}", f"Week {i}") for i in range(1, 19)]
SCHEDULE_BASE = f"https://www.nfl.com/schedules/{SEASON}/by-week/"
INJURY_URLS = [
    f"https://www.nfl.com/injuries/?season={SEASON}&week={i}" for i in range(1, 12)
]
TEAM_STATS_URL = f"https://www.nfl.com/stats/team-stats/?season={SEASON}&statType=season&sortOrder=DESC&sort=points&category=points"
PROBE_ENDPOINTS = [
    ("nfl.com injuries landing", "https://www.nfl.com/injuries/"),
    ("nfl.com transactions", "https://www.nfl.com/transactions/"),
    ("nfl.com stats portal", "https://www.nfl.com/stats/"),
    ("nfl.com team stats", "https://www.nfl.com/stats/team-stats/"),
    ("nfl.com player stats", "https://www.nfl.com/stats/player-stats/"),
    ("nfl.com league rules index", "https://www.nfl.com/news/nfl-scheduling-candidates"),
    ("nfl.com depth charts (league)", "https://www.nfl.com/depth-charts/"),
    ("nfl.com club depth chart", "https://www.nfl.com/teams/san-francisco-49ers/depth-chart/"),
    ("nfl.com inactives page", "https://www.nfl.com/inactives/"),
    ("nfl.com rosters page", "https://www.nfl.com/teams/san-francisco-49ers/roster/"),
    ("operations.nfl.com rulebook", "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"),
    ("operations.nfl.com homepage", "https://operations.nfl.com/"),
    ("api.nfl.com season games", f"https://api.nfl.com/season/{SEASON}/games/?seasonType=REG&week=9"),
    ("api.nfl.com club injuries", f"https://api.nfl.com/club/san-francisco-49ers/teams/current/injuries.json"),
    ("static.www.nfl.com in-game injury CSV (per-game)",
     "https://static.www.nfl.com/public/stats/statistics/games/injuries/2026/reg/2026110801.csv"),
    ("static.www.nfl.com in-game injury CSV (alt path)",
     "https://static.www.nfl.com/stats/statistics/games/injuries/2026/reg/2026110801.csv"),
    ("static.www.nfl.com game inactives CSV (per-game)",
     "https://static.www.nfl.com/public/stats/statistics/games/inactives/2026/reg/2026110801.csv"),
]

notes: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    notes.append(msg)


def get(url, tries=3, timeout=45, text=True):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                return body.decode("utf-8", "replace") if text else body
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(1.0 + attempt)
    log(f"  ! fetch failed {url}: {type(last).__name__}: {last}")
    return None


def status_of(url):
    """HTTP status code for a URL (probe only; body discarded)."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def jwrite(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


# ------------------------------------------------------------------- payload mining
def rsc_payloads(page: str):
    """Yield dehydrated react-query payloads embedded in an NFL.com page."""
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


def walk(node, pred, out, depth=0):
    """Collect every dict/list for which pred returns True (bounded depth)."""
    if depth > 24:
        return
    if isinstance(node, dict):
        if pred(node):
            out.append(node)
        for v in node.values():
            walk(v, pred, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            walk(v, pred, out, depth + 1)


def find_key(node, names, depth=0):
    """First value under any of `names` in a nested structure (case-insensitive)."""
    if depth > 12 or not isinstance(node, (dict, list)):
        return None
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in names and not isinstance(v, (dict, list)):
                return v
        for v in node.values():
            got = find_key(v, names, depth + 1)
            if got is not None:
                return got
    else:
        for v in node:
            got = find_key(v, names, depth + 1)
            if got is not None:
                return got
    return None


# ------------------------------------------------------------------------- results
def parse_results(page, url, week_label):
    """Return one row per game on an official by-week schedule page."""
    rows, seen = [], set()
    games: list[dict] = []
    walk(
        [q.get("state", {}).get("data") for q in page],
        lambda d: d.get("id") and ("awayTeam" in d or "homeTeam" in d) and ("status" in d or "gameStatus" in d),
        games,
    )
    for g in games:
        gid = str(g.get("id"))
        if gid in seen:
            continue
        seen.add(gid)
        away_obj = g.get("awayTeam") or {}
        home_obj = g.get("homeTeam") or {}
        away = away_obj.get("fullName") or away_obj.get("nameShort") or away_obj.get("nickname")
        home = home_obj.get("fullName") or home_obj.get("nameShort") or home_obj.get("nickname")
        status = (g.get("status") or g.get("gameStatus") or "")
        if isinstance(status, dict):
            status = status.get("type") or status.get("label")
        status = str(status)
        a_pts = find_key(away_obj, {"points", "score", "totalpoints"})
        h_pts = find_key(home_obj, {"points", "score", "totalpoints"})
        slug = None
        for e in (g.get("externalIds") or []):
            if isinstance(e, dict) and e.get("source") == "slug" and e.get("id"):
                slug = e["id"]
                break
        game_url = f"https://www.nfl.com/games/{slug}" if slug else url
        winner = None
        if a_pts is not None and h_pts is not None:
            try:
                ai, hi = int(a_pts), int(h_pts)
                winner = "away" if ai > hi else ("home" if hi > ai else "tie")
            except (TypeError, ValueError):
                winner = None
        rows.append({
            "gameId": gid,
            "season": SEASON,
            "seasonType": g.get("seasonType"),
            "week": g.get("week"),
            "weekType": g.get("weekType"),
            "weekLabel": week_label,
            "dateUTC": g.get("time"),
            "away": away,
            "home": home,
            "awayAbbr": away_obj.get("abbreviation") or away_obj.get("abbr"),
            "homeAbbr": home_obj.get("abbreviation") or home_obj.get("abbr"),
            "awayPoints": int(a_pts) if str(a_pts or "").isdigit() else None,
            "homePoints": int(h_pts) if str(h_pts or "").isdigit() else None,
            "status": status,
            "winner": winner,
            "venue": (g.get("venue") or {}).get("name") if isinstance(g.get("venue"), dict) else g.get("venue"),
            "sourceUrl": game_url,
            "listUrl": url,
            "sourceName": "NFL.com official 2026 schedule (by-week page, embedded game payload)",
            "verification": "verified" if "FINAL" in status.upper() and str(a_pts or "") != "" else "scheduled",
        })
    return rows, games


# ------------------------------------------------------------------------ injuries
INJURY_FIELDS = {
    "player": ("player", "playerName", "full_name", "name"),
    "position": ("position", "pos"),
    "injury": ("injuryDescription", "injury", "injuryType", "description"),
    "practice": ("practiceStatus", "practiceParticipation", "practice", "practiceStatusDescription"),
    "game": ("gameStatus", "gameStatusDescription", "status", "gameParticipation"),
    "updated": ("statusDate", "updatedDate", "reportDate", "date", "lastUpdated"),
}


def parse_injuries(page, url, label):
    """Return injury rows from any embedded payload that looks like an official injury report."""
    rows: list[dict] = []
    cands: list[dict] = []
    walk([q.get("state", {}).get("data") for q in page],
         lambda d: any(k.lower() in {"playername", "full_name", "player", "position", "practicestatus", "gamestatus"}
                       for k in d.keys()), cands)
    seen = set()
    for d in cands:
        low = {k.lower(): v for k, v in d.items()}
        player = None
        for key in INJURY_FIELDS["player"]:
            v = low.get(key)
            if isinstance(v, str) and v.strip():
                player = v.strip()
            elif isinstance(v, dict):
                player = (v.get("firstName", "") + " " + v.get("lastName", "")).strip() or v.get("fullName")
            if player:
                break
        if not player:
            continue
        def pick(names):
            for key in names:
                if key in low and isinstance(low[key], (str, int, float)) and str(low[key]).strip():
                    return str(low[key]).strip()
                if key in low and isinstance(low[key], dict):
                    got = find_key(low[key], {"description", "label", "name", "value", "code"})
                    if got is not None:
                        return str(got)
            return None
        pos = pick(INJURY_FIELDS["position"])
        inj = pick(INJURY_FIELDS["injury"])
        prac = pick(INJURY_FIELDS["practice"])
        game = pick(INJURY_FIELDS["game"])
        upd = pick(INJURY_FIELDS["updated"])
        key = (label, player, pos, prac, game)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "weekLabel": label,
            "team": None,
            "player": player,
            "position": pos,
            "injury": inj,
            "practiceStatus": prac,
            "gameStatus": game,
            "reportedDate": upd,
            "sourceUrl": url,
            "sourceName": "NFL.com official injury report (embedded page payload)",
            "verification": "verified" if (prac or game) else "present-no-status",
        })
    return rows, cands


# ----------------------------------------------------------------------- team stats
def parse_team_stats(page, url):
    rows: list[dict] = []
    cands: list[dict] = []
    walk([q.get("state", {}).get("data") for q in page],
         lambda d: any(k.lower() in {"team", "pointsfor", "pointsagainst", "pf", "pa", "stat"} for k in d.keys()), cands)
    for d in cands:
        low = {k.lower(): v for k, v in d.items()}
        team = low.get("team")
        if isinstance(team, dict):
            team = team.get("displayName") or team.get("shortName") or team.get("name")
        stat = low.get("stat") or low.get("value")
        label = low.get("statName") or low.get("label") or low.get("category") or low.get("name")
        if team and (stat is not None or label):
            rows.append({
                "team": team if isinstance(team, str) else None,
                "stat": str(label) if label else None,
                "value": str(stat) if stat is not None else None,
                "rank": low.get("rank"),
                "sourceUrl": url,
                "sourceName": "NFL.com official team statistics (embedded page payload)",
                "verification": "verified" if label and stat is not None else "partial",
            })
    return rows, cands


def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    os.makedirs(OUT, exist_ok=True)


    # ---- 1. results -----------------------------------------------------------
    all_rows: list[dict] = []
    per_week: dict[str, int] = {}
    sample_dumped = False
    for slug, label in NFL_WEEK_SLUGS:
        url = SCHEDULE_BASE + slug
        page = get(url)
        if page is None:
            per_week[label] = -1
            continue
        payloads = list(rsc_payloads(page))
        rows, games = parse_results(payloads, url, label)
        per_week[label] = len(rows)
        all_rows.extend(rows)
        if rows and not sample_dumped and any("FINAL" in r["status"].upper() for r in rows):
            jwrite("sample-final-game-object.json", games[0] if games else {})
            sample_dumped = True
        log(f"results {label}: {len(rows)} games")

    finals = [r for r in all_rows if "FINAL" in r["status"].upper()]
    jwrite("results-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} season game results captured from official nfl.com by-week pages",
            "retrievedUTC": started,
            "games": len(all_rows),
            "final": len(finals),
            "withScores": len([r for r in finals if r["awayPoints"] is not None and r["homePoints"] is not None]),
            "perWeek": per_week,
            "sourceName": "NFL.com official schedule (by-week)",
            "sourcePages": [SCHEDULE_BASE + s for s, _ in NFL_WEEK_SLUGS],
            "note": "Scores come from the same embedded payload the by-week page renders. "
                    "A game with no score in the payload keeps null fields.",
        },
        "games": all_rows,
    })

    # ---- 2. injuries ----------------------------------------------------------
    inj_rows: list[dict] = []
    inj_keys: dict[str, int] = {}
    for url in INJURY_URLS:
        wk = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("week", ["?"])[0]
        page = get(url)
        if page is None:
            inj_keys[f"week {wk}"] = -1
            continue
        rows, cands = parse_injuries(list(rsc_payloads(page)), url, f"Week {wk}")
        inj_keys[f"week {wk}"] = len(rows)
        inj_rows.extend(rows)
        log(f"injuries week {wk}: {len(rows)} rows")
    jwrite("injuries-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} weekly official injury reports captured from nfl.com/injuries",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(inj_rows),
            "perWeek": inj_keys,
            "sourceName": "NFL.com official injury report",
            "sourcePages": INJURY_URLS,
            "note": "Team attribution and depth-chart order are NOT part of the embedded payload if the page "
                    "omits them; those fields stay null rather than being inferred.",
        },
        "rows": inj_rows,
    })

    # ---- 3. team stats --------------------------------------------------------
    stats_rows: list[dict] = []
    page = get(TEAM_STATS_URL)
    if page:
        stats_rows, _ = parse_team_stats(list(rsc_payloads(page)), TEAM_STATS_URL)
    jwrite("team-stats-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} official team statistics (points), cross-check for derived scoring rates",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(stats_rows),
            "sourceUrl": TEAM_STATS_URL,
            "sourceName": "NFL.com official statistics",
            "note": "Empty rows array means the page renders client-side; no values were assumed.",
        },
        "rows": stats_rows,
    })

    # ---- 4. endpoint probe ----------------------------------------------------
    probe = []
    for name, url in PROBE_ENDPOINTS:
        code, ctype = status_of(url)
        probe.append({"name": name, "url": url, "httpStatus": code,
                      "contentType": ctype if isinstance(ctype, str) else str(ctype),
                      "reachable": code == 200})
        log(f"probe {name}: {code}")
    jwrite("probe-report.json", {
        "meta": {
            "purpose": "Record which official endpoints exist for injury / inactive / results data. "
                       "Used by the site's source-availability table; a non-200 is reported, never guessed.",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        "endpoints": probe,
    })

    # ---- 4b. payload probe (field-name discovery; lets the local parser be developed offline) ----
    probe_pages = {
        "injuries-current": "https://www.nfl.com/injuries/",
        "schedule-week-9": SCHEDULE_BASE + "week-9",
        "team-stats": TEAM_STATS_URL,
    }
    payload_probe = {}
    for name, url in probe_pages.items():
        page = get(url)
        if not page:
            payload_probe[name] = {"url": url, "fetched": False}
            continue
        payloads = list(rsc_payloads(page))
        keys = []
        samples = []
        for q in payloads:
            data = (q.get("state") or {}).get("data")
            keys.append("|".join(str(k) for k in (q.get("queryKey") or [])[:3]))
            if isinstance(data, list) and data and isinstance(data[0], dict):
                samples.append({
                    "queryKey": keys[-1],
                    "itemKeys": sorted(data[0].keys())[:40],
                    "sample": json.dumps(data[0], ensure_ascii=False)[:1200],
                })
            elif isinstance(data, dict):
                samples.append({"queryKey": keys[-1], "itemKeys": sorted(data.keys())[:40],
                                "sample": json.dumps(data, ensure_ascii=False)[:1200]})
        hrefs = sorted({h for h in re.findall(r'href="(/injuries[^"]*)"', page)})[:40]
        payload_probe[name] = {
            "url": url,
            "fetched": True,
            "bytes": len(page),
            "queryKeys": keys[:60],
            "samples": samples[:8],
            "injuryHrefs": hrefs,
        }
        log(f"payload-probe {name}: {len(keys)} queries, {len(hrefs)} injury hrefs")
    jwrite("payload-probe.json", {
        "meta": {"purpose": "Field-name discovery for the parsers above; keeps parser development offline.",
                 "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat()},
        "pages": payload_probe,
    })

    # ---- 4c. per-game official CSV endpoints (in-game injury report / inactives) ----
    csv_probe = []
    last_final = finals[-1] if finals else None
    if last_final:
        d = (last_final.get("dateUTC") or "")[:10].replace("-", "")
        for seq in range(1, 5):
            gid = f"{d}0{seq}"
            for kind in ("injuries", "inactives"):
                url = ("https://static.www.nfl.com/public/stats/statistics/games/"
                       f"{kind}/{SEASON}/reg/{gid}.csv")
                code, _ = status_of(url)
                body = get(url, tries=1) if code == 200 else None
                csv_probe.append({
                    "gameId": gid, "kind": kind, "url": url, "httpStatus": code,
                    "bytes": len(body) if body else 0,
                    "head": (body or "")[:400],
                })
                log(f"csv probe {kind} {gid}: {code}")
    jwrite("csv-endpoint-probe.json", {
        "meta": {
            "purpose": "Check whether the NFL publishes per-game injury-report / inactive-list CSVs at "
                       "static.www.nfl.com, and capture the header row of any file that does resolve. "
                       "Findings feed the source-availability table; failures are recorded, not guessed.",
            "game": (last_final or {}).get("title"),
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        "probes": csv_probe,
    })

    # ---- 5. fetch report ------------------------------------------------------
    keys_seen = {}
    for label in ("results", "injuries", "stats"):
        keys_seen[label] = {"parsed": {"results": len(all_rows), "injuries": len(inj_rows), "stats": len(stats_rows)}[label]}
    jwrite("fetch-report.json", {
        "meta": {
            "script": "tools/fetch_nfl_lab.py",
            "startedUTC": started,
            "finishedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "python": sys.version.split()[0],
        },
        "counts": {
            "games": len(all_rows),
            "gamesFinal": len(finals),
            "gamesWithScores": len([r for r in finals if r["awayPoints"] is not None]),
            "injuryRows": len(inj_rows),
            "teamStatRows": len(stats_rows),
        },
        "perWeek": per_week,
        "injuryPerWeek": inj_keys,
        "notes": notes[-40:],
    })
    log(f"wrote {OUT}: games={len(all_rows)} final={len(finals)} injury={len(inj_rows)} stats={len(stats_rows)}")


if __name__ == "__main__":
    main()
