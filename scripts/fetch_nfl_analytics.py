#!/usr/bin/env python3
"""Fetch NFL analytics raw sources (official) into research/nfl-analytics-raw/.

Runs in GitHub Actions, which has outbound internet (the sandbox does not).
Sources fetched here (all official league / club domains, plus one clearly
labelled ESPN market-odds reference):

  * https://www.nfl.com/injuries/                          — official Week 10 injury report
  * https://www.nfl.com/standings/league/2026/REG          — official standings (W-L-T, PF, PA)
  * https://www.nfl.com/schedules/2026/by-week/week-N      — official results + slate (weeks 1-10)
  * https://www.<club>.com/team/depth-chart/               — each club's published depth chart (32 clubs)
  * https://site.api.espn.com/.../nfl/scoreboard?dates=... — ESPN market odds reference (NOT official)

Every file is recorded in fetch-report.json with status, byte size and sha256 so a
reviewer can re-fetch and compare. Nothing is parsed here; parsing happens in
scripts/parse_nfl_analytics.py against the committed snapshots.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "nfl-analytics-raw"
OUT.mkdir(parents=True, exist_ok=True)

UA = "Korea5-research-fetcher/1.0 (verification snapshots; contact via GitHub repo issues)"

# Official club depth-chart pages (club CMS pattern confirmed on detroitlions.com).
CLUBS = {
    "ARI": "https://www.azcardinals.com/team/depth-chart/",
    "ATL": "https://www.atlantafalcons.com/team/depth-chart/",
    "BAL": "https://www.baltimoreravens.com/team/depth-chart/",
    "BUF": "https://www.buffalobills.com/team/depth-chart/",
    "CAR": "https://www.carolinapanthers.com/team/depth-chart/",
    "CHI": "https://www.chicagobears.com/team/depth-chart/",
    "CIN": "https://www.bengals.com/team/depth-chart/",
    "CLE": "https://www.clevelandbrowns.com/team/depth-chart/",
    "DAL": "https://www.dallascowboys.com/team/depth-chart/",
    "DEN": "https://www.denverbroncos.com/team/depth-chart/",
    "DET": "https://www.detroitlions.com/team/depth-chart/",
    "GB":  "https://www.packers.com/team/depth-chart/",
    "HOU": "https://www.houstontexans.com/team/depth-chart/",
    "IND": "https://www.colts.com/team/depth-chart/",
    "JAX": "https://www.jaguars.com/team/depth-chart/",
    "KC":  "https://www.chiefs.com/team/depth-chart/",
    "LAC": "https://www.chargers.com/team/depth-chart/",
    "LAR": "https://www.therams.com/team/depth-chart/",
    "LV":  "https://www.raiders.com/team/depth-chart/",
    "MIA": "https://www.miamidolphins.com/team/depth-chart/",
    "MIN": "https://www.vikings.com/team/depth-chart/",
    "NE":  "https://www.patriots.com/team/depth-chart/",
    "NO":  "https://www.neworleanssaints.com/team/depth-chart/",
    "NYG": "https://www.giants.com/team/depth-chart/",
    "NYJ": "https://www.newyorkjets.com/team/depth-chart/",
    "PHI": "https://www.philadelphiaeagles.com/team/depth-chart/",
    "PIT": "https://www.steelers.com/team/depth-chart/",
    "SEA": "https://www.seahawks.com/team/depth-chart/",
    "SF":  "https://www.49ers.com/team/depth-chart/",
    "TB":  "https://www.buccaneers.com/team/depth-chart/",
    "TEN": "https://www.titansonline.com/team/depth-chart/",
    "WAS": "https://www.commanders.com/team/depth-chart/",
}

TARGETS: list[tuple[str, str, str]] = [("injuries-week10", "https://www.nfl.com/injuries/", "html"),
                                       ("standings-2026-reg", "https://www.nfl.com/standings/league/2026/REG", "html")]
for wk in range(1, 11):
    TARGETS.append((f"schedule-week-{wk:02d}", f"https://www.nfl.com/schedules/2026/by-week/week-{wk}", "html"))
for team, url in CLUBS.items():
    TARGETS.append((f"depth-{team.lower()}", url, "html"))
# ESPN market-odds reference (trusted secondary source, NOT an official league source).
for d in ("20261112", "20261115", "20261116"):
    TARGETS.append((f"espn-scoreboard-{d}", f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}", "json"))


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, resp.read()


def main() -> None:
    report = {"fetchedUTC": datetime.now(timezone.utc).isoformat(), "targets": []}
    for name, url, ext in TARGETS:
        entry = {"name": name, "url": url, "kind": ext}
        try:
            status, body = fetch(url)
            digest = hashlib.sha256(body).hexdigest()
            path = OUT / f"{name}.{ext}"
            path.write_bytes(body)
            entry.update(status=status, bytes=len(body), sha256=digest, file=str(path.relative_to(ROOT)))
            print(f"OK  {name} status={status} bytes={len(body)}")
        except urllib.error.HTTPError as exc:
            entry.update(status=exc.code, error=f"HTTP {exc.code}")
            print(f"ERR {name} HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            entry.update(status=0, error=repr(exc))
            print(f"ERR {name} {exc!r}")
        report["targets"].append(entry)
        time.sleep(0.4)
    (OUT / "fetch-report.json").write_text(json.dumps(report, indent=1) + "\n")
    ok = sum(1 for t in report["targets"] if t.get("status") == 200)
    print(f"done: {ok}/{len(report['targets'])} targets fetched")


if __name__ == "__main__":
    main()
