#!/usr/bin/env python3
"""
Fetch official MLB schedules (all 30 clubs) from the MLB StatsAPI.

Source of record: https://statsapi.mlb.com/api/v1/schedule  (Major League Baseball's
own data service, the same feed that powers MLB.com and the official MLB app).

Output: data/mlb-<year>.json  with a compact, site-ready game list plus a provenance block.
Nothing is inferred here: if a year has not been released, the API simply returns no games
and we record that fact instead of inventing a schedule.

Usage:  python3 scripts/fetch_mlb.py [--years 2026 2027 2028 2029]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

API = "https://statsapi.mlb.com/api/v1/schedule"
FIELDS = ",".join([
    "dates", "date", "totalGames",
    "games", "gamePk", "gameDate", "gameType",
    "teams", "away", "home", "team", "id", "name",
    "status", "detailedState", "abstractGameState",
    "venue", "name",
])
UA = {"User-Agent": "Korea5-free-time-planner/1.0 (+data verification pipeline)"}

# gameType codes used by the MLB StatsAPI
GAME_TYPE_LABEL = {
    "S": "Spring Training",
    "R": "Regular Season",
    "F": "Wild Card",
    "D": "Division Series",
    "L": "League Championship Series",
    "W": "World Series",
    "A": "All-Star Game",
    "E": "Exhibition",
}


def month_windows(year):
    for m in range(2, 12):  # Feb..Nov covers ST -> World Series
        start = date(year, m, 1)
        end = date(year + (m // 12), (m % 12) + 1, 1)
        yield f"{start.isoformat()}", f"{(end.toordinal() - 1 and date.fromordinal(end.toordinal() - 1)).isoformat()}"


def get(url, tries=4):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  ! failed {url}: {last}", file=sys.stderr)
    return None


def fetch_year(year):
    games = []
    seen = set()
    errors = []
    for start, end in month_windows(year):
        q = {"sportId": 1, "startDate": start, "endDate": end, "fields": FIELDS}
        url = API + "?" + urllib.parse.urlencode(q)
        data = get(url)
        if data is None:
            errors.append(f"{start}..{end}")
            continue
        for d in data.get("dates", []):
            for g in d.get("games", []):
                pk = g.get("gamePk")
                if pk in seen:
                    continue
                seen.add(pk)
                away = g.get("teams", {}).get("away", {}).get("team", {})
                home = g.get("teams", {}).get("home", {}).get("team", {})
                gt = g.get("gameType", "")
                games.append({
                    "id": pk,
                    "date": d.get("date"),
                    "utc": g.get("gameDate"),
                    "away": away.get("name"),
                    "home": home.get("name"),
                    "type": gt,
                    "typeLabel": GAME_TYPE_LABEL.get(gt, gt),
                    "status": g.get("status", {}).get("detailedState"),
                    "abstract": g.get("status", {}).get("abstractGameState"),
                    "venue": g.get("venue", {}).get("name"),
                })
        time.sleep(0.15)
    games.sort(key=lambda g: (g["date"] or "", g["utc"] or "", g["id"] or 0))
    return games, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2026, 2027, 2028, 2029])
    args = ap.parse_args()

    os.makedirs("data", exist_ok=True)
    summary = {}
    for year in args.years:
        print(f"== MLB {year}")
        games, errors = fetch_year(year)
        counts = Counter(g["type"] for g in games)
        reg = [g for g in games if g["type"] == "R"]
        payload = {
            "meta": {
                "league": "MLB",
                "year": year,
                "source": API,
                "sourceName": "MLB StatsAPI (official Major League Baseball data service)",
                "sourceExampleUrl": (f"{API}?sportId=1&startDate={year}-03-25&endDate={year}-03-26"
                                    "&fields=dates,date,games,gamePk,gameDate,gameType,teams,away,home,team,name"),
                "retrievedUTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "gameTypeCounts": dict(sorted(counts.items())),
                "hasRegularSeason": len(reg) > 0,
                "regularSeasonGames": len(reg),
                "regularSeasonFirst": reg[0]["date"] if reg else None,
                "regularSeasonLast": reg[-1]["date"] if reg else None,
                "failedWindows": errors,
                "verified": len(games) > 0,
                "note": ("Official MLB schedule data returned by the league's own API."
                         if games else
                         "The MLB StatsAPI returned no games for this year: the schedule has not been released."),
            },
            "games": games,
        }
        path = f"data/mlb-{year}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
            f.write("\n")
        summary[year] = {k: payload["meta"][k] for k in
                         ("regularSeasonGames", "regularSeasonFirst", "regularSeasonLast",
                          "gameTypeCounts", "verified", "failedWindows")}
        print(f"   games={len(games)} types={dict(counts)} reg={len(reg)} "
              f"{payload['meta']['regularSeasonFirst']}..{payload['meta']['regularSeasonLast']} "
              f"errors={len(errors)}")

    with open("data/mlb-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    if any(v["failedWindows"] for v in summary.values()):
        print("WARNING: some windows failed; see data/mlb-summary.json", file=sys.stderr)


if __name__ == "__main__":
    main()
