#!/usr/bin/env python3
"""Probe candidate official sources for machine-readable schedules.

Writes research/probe.json with, for each URL: HTTP status, content type, byte size,
and fingerprints that tell us how to parse it (embedded JSON, sidearm, etc.).
This is a discovery tool only; it does not write schedule data.
"""
import json
import os
import urllib.request
import urllib.error

UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5-free-time-planner/1.0)"}

TARGETS = [
    # NFL
    "https://www.nfl.com/schedules/2026/by-week/week-1",
    "https://www.nfl.com/schedules/2026/by-week/week-5",
    "https://www.49ers.com/schedule/",
    "https://www.49ers.com/schedule/2026/",
    # Westwood One
    "https://www.westwoodonesports.com/nfl-schedule/",
    "https://www.westwoodonesports.com/wp-json/wp/v2/posts?per_page=1",
    "https://www.westwoodonesports.com/events/548540",
    # NCAAF official school sites
    "https://gostanford.com/sports/football/schedule",
    "https://gostanford.com/sports/football/schedule/2026",
    "https://calbears.com/sports/football/schedule",
    "https://calbears.com/sports/football/schedule/2026",
    # radio
    "https://knbr.com/",
    "https://www.audacy.com/knbr/schedule",
    # cross-check feeds (secondary, not official)
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20260910",
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/stanford/schedule?season=2026",
]


def probe(url):
    rec = {"url": url}
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            rec["status"] = r.status
            rec["contentType"] = r.headers.get("content-type")
            rec["bytes"] = len(raw)
            txt = raw.decode("utf-8", "replace")
            rec["fingerprints"] = {
                "__NEXT_DATA__": "__NEXT_DATA__" in txt,
                "__NUXT__": "__NUXT__" in txt,
                "sidearm": "sidearm" in txt.lower(),
                "window.__": txt.count("window.__"),
                "ld+json": "application/ld+json" in txt,
                "application/json": "application/json" in txt,
                "sportsEvent": "SportsEvent" in txt,
                "script count": txt.count("<script"),
            }
            rec["head"] = txt[:400].replace("\n", " ")
            rec["sample"] = txt[3000:3600].replace("\n", " ")
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["error"] = f"HTTPError {e.code}"
    except Exception as e:  # noqa: BLE001
        rec["status"] = None
        rec["error"] = repr(e)
    return rec


def main():
    os.makedirs("research", exist_ok=True)
    out = [probe(u) for u in TARGETS]
    with open("research/probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    for r in out:
        print(f"{r.get('status')!s:>5} {r.get('bytes','-'):>8} {r['url']} {r.get('error','')}")


if __name__ == "__main__":
    main()
