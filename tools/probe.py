#!/usr/bin/env python3
"""One-shot research probe: download raw official pages inside GitHub Actions.

The sandbox running this project has no direct outbound internet, but GitHub Actions
runners do. This script downloads the RAW bytes of official source pages and saves
them as an artifact so parsers can be written against the real markup, not guesses.
It does not transform, infer, or fabricate any data.
"""
import hashlib
import json
import os
import urllib.request
import urllib.error

OUT = "research-ef8b5b30/raw"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5FreeTime/1.0; +official-source-verification)"}

URLS = [
    ("nfl_week9", "https://www.nfl.com/schedules/2026/by-week/week-9"),
    ("nfl_pre", "https://www.nfl.com/schedules/2026/PRE"),
    ("nfl_post", "https://www.nfl.com/schedules/2026/POST"),
    ("nfl_reg", "https://www.nfl.com/schedules/2026/REG"),
    ("nfl_kickoff_guide", "https://media.nfl.com/football-information/2026/news/2026-kickoff-guide"),
    ("nfl_sb_lxii", "https://www.nfl.com/news/mercedes-benz-stadium-in-atlanta-to-host-super-bowl-lxii-in-2028"),
    ("49ers_2026", "https://www.49ers.com/schedule/2026/"),
    ("wwo_nfl_schedule", "https://www.westwoodonesports.com/nfl-schedule/"),
    ("wwo_station_finder", "https://www.westwoodonesports.com/station-finder/"),
    ("wwo_ncaa_football", "https://www.westwoodonesports.com/ncaa-football/"),
    ("wwo_live_shows", "https://www.westwoodonesports.com/live-shows/"),
    ("stanford_2026", "https://gostanford.com/sports/football/schedule"),
    ("cal_2026", "https://calbears.com/sports/football/schedule/2026"),
    ("cal_2027_opponents", "https://calbears.com/news/2026/9/16/california-football-announces-2027-conference-opponents"),
    ("cal_future_schedules", "https://calbears.com/news/2024/7/10/football-cal-ucla-schedule-4-games-from-2026-29"),
    ("stanford_2027_opponents", "https://gostanford.com/news/2026/09/16/acc-announces-2027-conference-opponents"),
    ("stanford_notre_dame", "https://gostanford.com/news/2026/05/20/two-dates-added-to-notre-dame-rivalry"),
    ("knbr_shows", "https://www.thesportsleader.com/shows/"),
    ("giants_watch", "https://www.mlb.com/giants/schedule/watch"),
    ("athletics_watch", "https://www.mlb.com/athletics/schedule/watch"),
    ("mlb_2027_release", "https://www.mlb.com/news/mlb-2027-schedule-released"),
    ("mlb_api_sample", "https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2026&startDate=2026-09-27&endDate=2026-09-28&fields=dates,date,games,gamePk,gameDate,gameType,teams,away,home,team,name,status,detailedState,gameDurationMinutes"),
    ("wwo_more_current", "https://www.westwoodonesports.com/more/eventGrid/?id=47029&range=current&offset=0&limit=100&timezone=America/New_York&widgetTitle=Event+Display"),
    ("wwo_more_past", "https://www.westwoodonesports.com/more/eventGrid/?id=47030&range=current&offset=0&limit=100&timezone=America/New_York&widgetTitle=Event+Display"),
    ("wwo_event_548540", "https://www.westwoodonesports.com/events/548540/"),
    ("wwo_ncaab", "https://www.westwoodonesports.com/ncaa-basketball/"),
    ("wwo_golf", "https://www.westwoodonesports.com/golf/"),
    ("wwo_soccer", "https://www.westwoodonesports.com/us-soccer/"),
    ("wwo_mcws", "https://www.westwoodonesports.com/ncaa-mcws/"),
    ("wwo_wcws", "https://www.westwoodonesports.com/ncaa-wcws/"),
    ("wwo_lacrosse", "https://www.westwoodonesports.com/ncaa-lacrosse/"),
    ("wwo_hockey", "https://www.westwoodonesports.com/ncaa-hockey/"),
    ("fcc_search", "https://www.fcc.gov/media/radio/fcc-station-search"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for name, url in URLS:
        rec = {"name": name, "url": url}
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                rec["status"] = r.status
                rec["ctype"] = r.headers.get("Content-Type", "")
                rec["finalUrl"] = r.geturl()
            fn = os.path.join(OUT, name + ".raw")
            with open(fn, "wb") as f:
                f.write(body)
            rec["bytes"] = len(body)
            rec["sha256"] = hashlib.sha256(body).hexdigest()[:16]
            rec["file"] = fn
        except Exception as e:  # noqa: BLE001 - diagnostics only
            rec["error"] = repr(e)
        manifest.append(rec)
        print(json.dumps(rec))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
