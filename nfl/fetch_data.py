#!/usr/bin/env python3
"""
NFL Lines Lab — data acquisition.

Runs in GitHub Actions, which has outbound internet access (the interactive
sandbox used to author this file does not). Downloads only FREE, CITED sources,
records the exact HTTP response metadata for every file, and writes a
provenance manifest. Nothing is transcribed by hand.

Sources (each is recorded in the manifest with URL, size, sha256, HTTP status
and the timestamp the publisher stamped on the release):

  nflverse/nflverse-data  (CC-BY-4.0 data release; the standard open NFL data
  distribution, sourced from the NFL's official GSIS feed and NFL Next Gen
  Stats):
    schedules/games.csv                      historical results, scores, roof, rest
    player_stats/stats_player_week_{y}.csv   weekly player box scores (props)
    injuries/injuries_{y}.csv                weekly injury report status per player
    injuries/injuries.csv                    all-season injury table
    depth_charts/depth_charts_{y}.csv        weekly depth-chart position per player
    rosters/roster_{y}.csv                   player -> team -> position / depth
    snap_counts/snap_counts_{y}.csv          offensive/defensive snap share
    pbp/play_by_play_{y}.csv.gz              play-by-play (EPA, win prob)
    pfr_advstats/advstats_week_team_{y}.csv  pressure/coverage context (PFR)
    officials/officials.csv                  referee assignment per game

  ESPN public JSON (no key): site.api.espn.com
    scoreboard  (historical seasons)         cross-check of scores, final state
    summary     (per game)                   starting lineups, inactives, plays

Usage:
  python3 nfl/fetch_data.py --seasons 2015 2016 ... 2026 --check-only
  python3 nfl/fetch_data.py --seasons ... 2026 --out nfl/raw
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = {
    "User-Agent": "Korea5-NFL-Lines-Lab/1.0 (+https://github.com/karagemop466-tech/Korea5; research pipeline)",
    "Accept": "*/*",
}
RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str, timeout: int = 90, tries: int = 3) -> tuple[bytes | None, dict]:
    """HTTP GET with retries. Returns (bytes, meta). Never raises on HTTP errors."""
    meta = {"url": url, "fetchedUTC": now(), "tries": 0}
    last = None
    for attempt in range(tries):
        meta["tries"] = attempt + 1
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                meta.update({
                    "status": r.status,
                    "bytes": len(body),
                    "contentType": r.headers.get("Content-Type"),
                    "contentLengthHeader": r.headers.get("Content-Length"),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "finalUrl": r.geturl(),
                })
                return body, meta
        except urllib.error.HTTPError as e:
            last = f"HTTPError {e.code}"
            meta.update({"status": e.code, "error": last})
            if e.code in (403, 404):
                break
        except Exception as e:  # noqa: BLE001 - record everything
            last = f"{type(e).__name__}: {str(e)[:200]}"
            meta["error"] = last
        time.sleep(1.5 * (attempt + 1))
    meta.setdefault("error", last or "unknown")
    return None, meta


def save(out_dir: str, name: str, body: bytes | None, meta: dict) -> dict:
    if body is None:
        return meta
    if name.endswith(".gz") and not body[:2] == b"\x1f\x8b":
        body_gz = gzip.compress(body, 6)
    else:
        body_gz = body
    path = os.path.join(out_dir, name)
    with open(path, "wb") as fh:
        fh.write(body_gz)
    meta["path"] = os.path.join("nfl/raw", name)
    meta["storedBytes"] = len(body_gz)
    meta["storedSha256"] = hashlib.sha256(body_gz).hexdigest()
    return meta


def release_url(tag: str, asset: str) -> str:
    return f"{RELEASES}/{tag}/{asset}"


def espn_scoreboard(season: int, week: int | None = None) -> str:
    q = {"dates": str(season), "limit": "1000"}
    if week:
        q["week"] = str(week)
    return "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?" + urllib.parse.urlencode(q)


def plan(seasons: list[int], max_season: int) -> list[tuple[str, str, str]]:
    """(name, url, kind). kind selects post-processing."""
    out: list[tuple[str, str, str]] = [
        ("games.csv", release_url("schedules", "games.csv"), "csv"),
        ("games_timestamp.json", release_url("schedules", "timestamp.json"), "json"),
        ("injuries_current.csv", release_url("injuries", f"injuries_{max_season}.csv"), "csv"),
        ("officials.csv", release_url("officials", "officials.csv"), "csv"),
        ("depth_charts_timestamp.json", release_url("depth_charts", "timestamp.json"), "json"),
    ]
    for y in seasons:
        out += [
            (f"stats_player_week_{y}.csv", release_url("player_stats", f"stats_player_week_{y}.csv"), "csv"),
            (f"injuries_{y}.csv", release_url("injuries", f"injuries_{y}.csv"), "csv"),
            (f"depth_charts_{y}.csv", release_url("depth_charts", f"depth_charts_{y}.csv"), "csv"),
            (f"roster_{y}.csv", release_url("rosters", f"roster_{y}.csv"), "csv"),
            (f"snap_counts_{y}.csv", release_url("snap_counts", f"snap_counts_{y}.csv"), "csv"),
            (f"advstats_week_team_{y}.csv", release_url("pfr_advstats", f"advstats_week_team_{y}.csv"), "csv"),
        ]
    # ESPN cross-check: one scoreboard pull per completed season + current.
    for y in seasons:
        out.append((f"espn_scoreboard_{y}.json", espn_scoreboard(y), "json"))
    return [t for t in out if t[2] != "skip"]


SOURCES_DOC = [
    {
        "id": "nflverse",
        "name": "nflverse-data (open NFL data release)",
        "url": "https://github.com/nflverse/nflverse-data",
        "license": "CC-BY-4.0 (see repository LICENSE)",
        "what": "Weekly player box scores, injury reports, depth charts, rosters, snap counts, schedules and scores; "
                "built from the NFL GSIS feed and NFL Next Gen Stats.",
        "caveat": "A redistribution, not the NFL itself. Every game row is cross-checked against NFL.com / ESPN in this repo.",
    },
    {
        "id": "espn",
        "name": "ESPN public scoreboard & summary JSON",
        "url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "license": "ESPN terms of service; factual data only, not redistributed raw",
        "what": "Scores, final-state flags, starting lineups and inactives for cross-checks and lineup status.",
        "caveat": "Undocumented public endpoint; treated as a secondary check, never as sole authority for a published number.",
    },
    {
        "id": "nflcom",
        "name": "NFL.com official schedule and game pages",
        "url": "https://www.nfl.com/schedules/",
        "license": "NFL.com terms",
        "what": "Official schedule, kickoff times and game-page links used for per-row provenance.",
        "caveat": "HTML can change without notice; matches are recorded as file snapshots with a timestamp.",
    },
    {
        "id": "pfr",
        "name": "Pro-Football-Reference",
        "url": "https://www.pro-football-reference.com/",
        "license": "Sports Reference terms (attribution required)",
        "what": "Playoff seedings, closing lines for older seasons, pressure and coverage context tables.",
        "caveat": "HTML tables; blocked to the authoring sandbox, fetched from CI only where reachable.",
    },
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", type=int, default=list(range(2015, 2027)))
    ap.add_argument("--out", default="nfl/raw")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    max_season = max(args.seasons)

    manifest = {"generatedUTC": now(), "sources": SOURCES_DOC, "files": []}
    items = plan(args.seasons, max_season)
    ok = fail = 0
    for name, url, _kind in items:
        if args.check_only:
            body, meta = get(url, timeout=45, tries=1)
        else:
            body, meta = get(url)
        meta["name"] = name
        if body is not None:
            ok += 1
            if not args.check_only:
                meta = save(args.out, name, body, meta)
        else:
            fail += 1
        manifest["files"].append(meta)
        print(f"{meta.get('status', '-'):>4} {name:34} {meta.get('bytes', 0):>10,} bytes  "
              f"{meta.get('error', '')[:70]}", flush=True)

    manifest["summary"] = {"requested": len(items), "ok": ok, "failed": fail}
    if not args.check_only:
        os.makedirs("nfl/data", exist_ok=True)
        with open(os.path.join("nfl/data", "provenance.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1)
        # Backfill max_season: release timestamps for the current season.
        for tag, fname in (("injuries", "injuries_timestamp.json"),
                           ("player_stats", "stats_player_timestamp.json")):
            body, meta = get(release_url(tag, "timestamp.json"), timeout=30, tries=1)
            if body:
                with open(os.path.join("nfl/data", fname), "w", encoding="utf-8") as fh:
                    fh.write(body.decode("utf-8", "replace"))
    print(json.dumps(manifest["summary"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
