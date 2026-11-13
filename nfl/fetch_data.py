#!/usr/bin/env python3
"""
NFL Lines Lab — data acquisition (runs in GitHub Actions).

Downloads only free, citable sources, records HTTP metadata + sha256 for every
file in nfl/data/provenance.json, and never transcribes a value by hand.

Sources
-------
nflverse/nflverse-data (CC-BY-4.0)   https://github.com/nflverse/nflverse-data/releases
  schedules/games.csv                       results, scores, roof, rest, seeds
  stats_player_week_{y}.csv                 weekly player box scores  (2016+)
  player_stats/player_stats_{y}.csv         consolidated player stats (fallback, 2019 gap)
  injuries/injuries_{y}.csv                 weekly injury-report status
  depth_charts/depth_charts_{y}.csv         weekly depth-chart position
  rosters/roster_{y}.csv                    team membership + positions
  snap_counts/snap_counts_{y}.csv           snap share
  pbp/play_by_play_{y}.csv.gz               play-by-play
  officials/officials.csv                   referee per game

ESPN public JSON (no key)
  site.api.espn.com/.../nfl/scoreboard      scores, final state, book odds
                                            (spread / total / moneylines)
  site.api.espn.com/.../nfl/summary?event=  lineups, inactives (fetched later per game)

Usage
  python3 nfl/fetch_data.py --probe                 # inventory + schema snapshot, no big commits
  python3 nfl/fetch_data.py --seasons 2016 ... 2026 # full pull into nfl/raw/ (git-ignored)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
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
REL = "https://github.com/nflverse/nflverse-data/releases/download"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

SOURCES = [
    {"id": "nflverse", "name": "nflverse-data (open NFL data release, CC-BY-4.0)",
     "url": "https://github.com/nflverse/nflverse-data",
     "what": "Weekly player box scores, injury reports, depth charts, rosters, snap counts, schedules, scores. "
             "Derived from the NFL GSIS feed and NFL Next Gen Stats.",
     "caveat": "Redistribution, not the NFL. Used for signals; results are cross-checked against ESPN in this repo."},
    {"id": "espn", "name": "ESPN public scoreboard JSON",
     "url": f"{ESPN}/scoreboard",
     "what": "Final scores, game state, and book odds (provider, spread, total, moneylines) for cross-checks and "
             "the market-relative scoring track.",
     "caveat": "Undocumented endpoint. Odds are a single book's published line, not a timestamped line history; "
               "opening/closing times are therefore unknown and no closing-line-value claim is made."},
    {"id": "nflcom", "name": "NFL.com schedule pages",
     "url": "https://www.nfl.com/schedules/",
     "what": "Official schedule and kickoff times used for per-row provenance links.",
     "caveat": "HTML; matched as file snapshots with timestamps, never asserted from memory."},
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str, timeout: int = 90, tries: int = 3) -> tuple[bytes | None, dict]:
    meta = {"url": url, "fetchedUTC": now(), "tries": 0}
    last = None
    for attempt in range(tries):
        meta["tries"] = attempt + 1
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                meta.update({"status": r.status, "bytes": len(body),
                             "contentType": r.headers.get("Content-Type"),
                             "sha256": hashlib.sha256(body).hexdigest(),
                             "finalUrl": r.geturl()})
                return body, meta
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            meta.update({"status": e.code, "error": last})
            if e.code in (401, 403, 404):
                break
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:160]}"
            meta["error"] = last
        time.sleep(1.2 * (attempt + 1))
    meta.setdefault("error", last or "unknown")
    return None, meta


def espn_week(season: int, seasontype: int, week: int) -> str:
    q = {"dates": str(season), "seasontype": str(seasontype), "week": str(week), "limit": "100"}
    return f"{ESPN}/scoreboard?" + urllib.parse.urlencode(q)


def inventory(seasons: list[int]) -> list[tuple[str, str]]:
    """(filename, url) — verified against the release asset listing."""
    mx = max(seasons)
    out = [
        ("games.csv", f"{REL}/schedules/games.csv"),
        ("officials.csv", f"{REL}/officials/officials.csv"),
        ("player_stats.parquet", f"{REL}/player_stats/player_stats.parquet"),
        (f"injuries_{mx}.csv", f"{REL}/injuries/injuries_{mx}.csv"),
        ("depth_charts_timestamp.json", f"{REL}/depth_charts/timestamp.json"),
        ("player_stats_timestamp.json", f"{REL}/player_stats/timestamp.json"),
        ("injuries_timestamp.json", f"{REL}/injuries/timestamp.json"),
    ]
    for y in seasons:
        out += [(f"stats_player_week_{y}.csv", f"{REL}/player_stats/stats_player_week_{y}.csv")]
        if y < 2016 or y == 2019:
            out.append((f"player_stats_{y}.csv", f"{REL}/player_stats/player_stats_{y}.csv"))
        out += [
            (f"injuries_{y}.csv", f"{REL}/injuries/injuries_{y}.csv"),
            (f"depth_charts_{y}.csv", f"{REL}/depth_charts/depth_charts_{y}.csv"),
            (f"roster_{y}.csv", f"{REL}/rosters/roster_{y}.csv"),
            (f"snap_counts_{y}.csv", f"{REL}/snap_counts/snap_counts_{y}.csv"),
        ]
        if y < mx:
            out.append((f"play_by_play_{y}.csv.gz", f"{REL}/pbp/play_by_play_{y}.csv.gz"))
    return out


def espn_inventory(seasons: list[int]) -> list[tuple[str, str]]:
    out = []
    for y in seasons:
        for st, weeks in ((2, range(1, 19)), (3, range(1, 5)), (1, range(1, 5))):
            for w in weeks:
                if y >= 2026 and st == 1:
                    continue
                out.append((f"espn_{y}_t{st}_w{w}.json", espn_week(y, st, w)))
    return out


def dump_samples(raw: dict[str, bytes], outdir: str, rows: int = 240) -> None:
    """Commit small, real excerpts so parsers can be developed/validated offline (no network)."""
    os.makedirs(outdir, exist_ok=True)
    caps = {"games.csv": 6000, "stats_player_week_2025.csv": 6000, "injuries_2025.csv": 6000,
            "depth_charts_2025.csv": 8000, "snap_counts_2025.csv": 6000, "injuries_2026.csv": 6000,
            "depth_charts_2026.csv": 8000, "snap_counts_2026.csv": 6000}
    for name, body in raw.items():
        if name.endswith(".csv"):
            n = caps.get(name, rows)
            sample = b"\n".join(body.split(b"\n")[:n])
            with open(os.path.join(outdir, name), "wb") as fh:
                fh.write(sample)
        elif name.startswith("espn_"):
            try:
                d = json.loads(body)
                d["events"] = d.get("events", [])[:3]
                with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
                    json.dump(d, fh)
            except Exception:  # noqa: BLE001
                pass
        elif name.endswith("timestamp.json"):
            with open(os.path.join(outdir, name), "wb") as fh:
                fh.write(body[:200])


def dump_schema(raw: dict[str, bytes], path: str) -> None:
    """Record enough of each file's shape that parsers can be written without the raw file."""
    import csv
    import io

    probe: dict[str, object] = {"generatedUTC": now(), "files": {}}
    for name, body in raw.items():
        info: dict[str, object] = {"bytes": len(body)}
        try:
            if name.endswith(".csv"):
                text = body.decode("utf-8", "replace").splitlines()
                info["rows"] = len(text) - 1
                info["header"] = next(csv.reader([text[0]])) if text else []
                rows = list(csv.DictReader(io.StringIO("\n".join(text[:400]))))
                if rows:
                    info["sample"] = {k: rows[0][k] for k in info["header"]}  # type: ignore[index]
                    info["sample2"] = {k: rows[min(1, len(rows) - 1)][k] for k in info["header"]}  # type: ignore[index]
                # column completeness across the sampled window
                if rows:
                    info["nonEmptyShare"] = {
                        k: round(sum(1 for r in rows if str(r.get(k, "")).strip() not in ("", "NA", "NULL")) / len(rows), 3)
                        for k in info["header"]}  # type: ignore[index]
            elif name.endswith(".json"):
                d = json.loads(body)
                info["jsonTopKeys"] = list(d)[:12] if isinstance(d, dict) else f"list[{len(d)}]"
                if name.startswith("espn_"):
                    evs = d.get("events", [])
                    info["events"] = len(evs)
                    if evs:
                        c = evs[0]["competitions"][0]
                        o = (c.get("odds") or [{}])[0]
                        info["competitionKeys"] = sorted(c)
                        info["oddsKeys"] = sorted(o)
                        info["oddsExample"] = {k: o.get(k) for k in
                                               ("provider", "details", "overUnder", "spread",
                                                "moneylineHome", "moneylineAway") if k in o}
                        info["hasOddsShare"] = round(sum(1 for e in evs if (e["competitions"][0].get("odds") or [])
                                                       ) / max(1, len(evs)), 3)
                        info["statusExample"] = c["status"]["type"]["name"]
            elif name.endswith(".gz"):
                info["gzipOk"] = body[:2] == b"\x1f\x8b"
                if info["gzipOk"]:
                    head = gzip.decompress(body)[:4000].decode("utf-8", "replace").splitlines()
                    info["header"] = next(csv.reader([head[0]])) if head else []
                    info["rowsHead"] = len(head) - 1
        except Exception as e:  # noqa: BLE001
            info["schemaError"] = f"{type(e).__name__}: {str(e)[:160]}"
        probe["files"][name] = info  # type: ignore[index]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(probe, fh, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", type=int, default=list(range(2016, 2027)))
    ap.add_argument("--out", default="nfl/raw")
    ap.add_argument("--probe", action="store_true", help="small pulls, write schema snapshot, no raw files")
    ap.add_argument("--with-espn", action="store_true")
    ap.add_argument("--sample-rows", type=int, default=240)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs("nfl/data", exist_ok=True)

    items = inventory(args.seasons)
    if args.with_espn or args.probe:
        items += espn_inventory(args.seasons)

    manifest = {"generatedUTC": now(), "sources": SOURCES, "mode": "probe" if args.probe else "full", "files": []}
    keep: dict[str, bytes] = {}
    ok = fail = 0
    for name, url in items:
        body, meta = get(url, timeout=45 if args.probe else 120)
        meta["name"] = name
        manifest["files"].append(meta)
        if body is None:
            fail += 1
            print(f"{meta.get('status', '-'):>4} {name:32} FAIL {meta.get('error', '')[:60]}", flush=True)
            continue
        ok += 1
        print(f"{meta.get('status'):>4} {name:32} {len(body):>11,} bytes", flush=True)
        if args.probe:
            # keep a bounded sample for the schema dump
            if name.endswith(".csv"):
                keep[name] = body  # full bytes; dump_samples caps them
            elif name.endswith(".json"):
                keep[name] = body
            else:
                keep[name] = body[:200000]
        else:
            blob = gzip.compress(body, 6) if (name.endswith(".gz") and body[:2] != b"\x1f\x8b") else body
            with open(os.path.join(args.out, name), "wb") as fh:
                fh.write(blob)

    manifest["summary"] = {"requested": len(items), "ok": ok, "failed": fail}
    with open("nfl/data/provenance.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    if args.probe:
        dump_schema(keep, "nfl/data/schema_probe.json")
        dump_samples(keep, "nfl/raw/samples", rows=args.sample_rows)
    print(json.dumps(manifest["summary"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
