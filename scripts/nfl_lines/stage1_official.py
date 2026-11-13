#!/usr/bin/env python3
"""Stage 1 - official-source capture for the parts of the lab that have an official source.

Writes `nfl-lines/data/official/*.json`:

  * injury-report-2026-week10.json  - parsed from https://www.nfl.com/injuries/league/2026/reg10
  * official-crosschecks.json       - nfl.com values captured by hand from the fetched markdown,
                                      each one keeping the exact page URL it came from
  * roster-2026/*.json              - club roster pages (position, status, jersey) for clubs in scope

Nothing here is invented. Fields the official page leaves blank stay blank (`""`),
and are counted so the site can report them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "nfl-lines" / "data" / "official"

# ---------------------------------------------------------------------------
# Injury report for 2026 week 10 as published on
# https://www.nfl.com/injuries/league/2026/reg10  (fetched 2026-11-13)
# Columns on the page: Player | Position | Injuries | Practice Status | Game Status
# Rows transcribed verbatim; blank cells stay "".
# ---------------------------------------------------------------------------
INJURY_URL = "https://www.nfl.com/injuries/league/2026/reg10"
INJURY_WEEK = {
    "season": 2026, "week": 10, "sourceUrl": INJURY_URL, "fetchedUTC": "2026-11-13",
    "notes": "Official NFL injury report page. Practice Status and Game Status are blank on the page for "
             "many players and are left blank here (never inferred). SCOPE: three games of week 10 were "
             "transcribed verbatim in this session (WAS@NYG, NE@DET, KC@ATL). The other week-10 games are NOT "
             "transcribed and are therefore absent rather than blank - a tracked coverage gap.",
    "games": [
        {"date": "2026-11-12", "kickoffET": "8:15 PM", "tv": ["Prime Video"],
         "away": "WAS", "awayRecord": "3-5-1", "home": "NYG", "homeRecord": "5-3-1",
         "teams": {
            "WAS": [
                ["John Bates", "TE", "", "Full Participation in Practice", ""],
                ["Treylon Burks", "WR", "", "Did Not Participate In Practice", ""],
                ["Jayden Daniels", "QB", "", "Full Participation in Practice", ""],
                ["Matt Gulbin", "C", "", "Full Participation in Practice", ""],
                ["Chig Okonkwo", "TE", "", "Full Participation in Practice", ""],
                ["Lucas Patrick", "C", "Concussion", "Did Not Participate In Practice", "Out"],
                ["Amik Robertson", "CB", "", "Limited Participation in Practice", ""],
                ["Shy Tuttle", "DT", "", "Full Participation in Practice", ""],
                ["Colson Yankoff", "TE", "Knee", "Did Not Participate In Practice", "Out"],
            ],
            "NYG": [
                ["Abdul Carter", "LB", "", "Full Participation in Practice", ""],
                ["Jermaine Eluemunor", "T", "", "Full Participation in Practice", ""],
                ["Malik Harrison", "LB", "Groin", "Limited Participation in Practice", "Questionable"],
                ["Colton Hood", "CB", "", "Full Participation in Practice", ""],
                ["Theo Johnson", "TE", "", "Full Participation in Practice", ""],
                ["Charlie Jones", "WR", "", "Full Participation in Practice", ""],
                ["J.J. McCarthy", "QB", "", "Full Participation in Practice", ""],
                ["Darnell Mooney", "WR", "", "Full Participation in Practice", ""],
                ["Malik Nabers", "WR", "", "Full Participation in Practice", ""],
                ["Cam Skattebo", "RB", "", "Full Participation in Practice", ""],
                ["Andrew Thomas", "T", "", "Full Participation in Practice", ""],
            ],
         }},
        {"date": "2026-11-15", "kickoffET": "9:30 AM", "tv": ["FOX", "FOX DEPORTES"],
         "away": "NE", "awayRecord": "5-4", "home": "DET", "homeRecord": "6-2",
         "teams": {
            "NE": [
                ["Ben Brown", "C", "Knee", "Did Not Participate In Practice", "Out"],
                ["A.J. Brown", "WR", "", "Limited Participation in Practice", ""],
                ["Kevin Byard", "S", "", "Limited Participation in Practice", ""],
                ["Carlton Davis III", "CB", "Knee", "Did Not Participate In Practice", "Out"],
                ["Reggie Gilliam", "FB", "", "Limited Participation in Practice", ""],
                ["TreVeyon Henderson", "RB", "Illness", "Did Not Participate In Practice", "Out"],
                ["Hunter Henry", "TE", "", "Limited Participation in Practice", ""],
                ["Cameron Latu", "TE", "", "Limited Participation in Practice", ""],
                ["Drake Maye", "QB", "", "Full Participation in Practice", ""],
                ["Morgan Moses", "T", "", "Limited Participation in Practice", ""],
                ["Walter Rouse", "T", "", "Limited Participation in Practice", ""],
                ["Brenden Schooler", "S", "", "Limited Participation in Practice", ""],
                ["Rhamondre Stevenson", "RB", "", "Limited Participation in Practice", ""],
                ["Greg Van Roten", "G", "", "Limited Participation in Practice", ""],
                ["Charles Woods", "CB", "", "Limited Participation in Practice", ""],
            ],
            "DET": [
                ["Brian Branch", "S", "", "Full Participation in Practice", ""],
                ["Jared Goff", "QB", "", "Full Participation in Practice", ""],
                ["Kerby Joseph", "S", "Knee", "Full Participation in Practice", "Out"],
                ["Cade Mays", "C", "Ankle", "Did Not Participate In Practice", "Out"],
                ["D.J. Reed", "CB", "Hip", "Did Not Participate In Practice", "Out"],
                ["Jacob Saylors", "RB", "", "Full Participation in Practice", ""],
                ["Amon-Ra St. Brown", "WR", "", "Limited Participation in Practice", ""],
                ["Sione Vaki", "RB", "", "Did Not Participate In Practice", ""],
                ["DJ Wonnum", "DE", "", "Full Participation in Practice", ""],
            ],
         }},
        {"date": "2026-11-15", "kickoffET": "1:00 PM", "tv": ["CBS"],
         "away": "KC", "awayRecord": "6-2", "home": "ATL", "homeRecord": "3-6",
         "teams": {
            "KC": [
                ["Jeffrey Bassa", "LB", "", "Full Participation in Practice", ""],
                ["Mansoor Delane", "CB", "", "Full Participation in Practice", ""],
                ["Justin Fields", "QB", "", "Full Participation in Practice", ""],
                ["Jaden Hicks", "S", "", "Full Participation in Practice", ""],
                ["Travis Kelce", "TE", "", "Full Participation in Practice", ""],
                ["Patrick Mahomes", "QB", "", "Full Participation in Practice", ""],
                ["Jaylon Moore", "T", "", "Did Not Participate In Practice", ""],
                ["Omarr Norman-Lott", "DT", "", "Limited Participation in Practice", ""],
                ["Jaydn Ott", "RB", "", "Limited Participation in Practice", ""],
                ["Rashee Rice", "WR", "", "Full Participation in Practice", ""],
                ["Peter Woods", "DT", "", "Did Not Participate In Practice", ""],
                ["Xavier Worthy", "WR", "", "Full Participation in Practice", ""],
            ],
            "ATL": [
                ["Zachariah Branch", "WR", "", "Did Not Participate In Practice", ""],
                ["Kendal Daniels", "LB", "", "Limited Participation in Practice", ""],
                ["Divine Deablo", "LB", "", "Did Not Participate In Practice", ""],
                ["Gervon Dexter Sr.", "DT", "", "Limited Participation in Practice", ""],
                ["James Pearce Jr.", "DE", "", "Limited Participation in Practice", ""],
                ["Za'Darius Smith", "DE", "", "Full Participation in Practice", ""],
                ["Jawaan Taylor", "T", "", "Did Not Participate In Practice", ""],
                ["Cameron Thomas", "DE", "", "Limited Participation in Practice", ""],
                ["Josh Woods", "LB", "", "Limited Participation in Practice", ""],
            ],
         }},
    ],
}

# ---------------------------------------------------------------------------
# Official cross-checks captured from nfl.com pages this session.
# Each record: the exact page, the field, the value as printed.
# ---------------------------------------------------------------------------
OFFICIAL_CROSSCHECKS = {
    "fetchedUTC": "2026-11-13",
    "records": [
        {"page": "https://www.nfl.com/injuries/league/2026/reg10",
         "field": "report week", "value": "Week 10 of the 2026 season",
         "usedFor": "injury tracker header"},
        {"page": "https://www.nfl.com/teams/detroit-lions/roster",
         "field": "roster row", "value": "Brian Branch | 32 | CB | ACT", "usedFor": "roster presence"},
        {"page": "https://www.nfl.com/games/patriots-at-lions-2026-reg-10",
         "field": "injury card", "value": "K. Joseph | DB #31 | O | Knee | Full participation",
         "usedFor": "jersey number and position label cross-check against the injury report"},
        {"page": "https://www.nfl.com/games/patriots-at-lions-2026-reg-10",
         "field": "venue", "value": "FC BAYERN MUNICH STADIUM / MUNICH",
         "usedFor": "neutral-site identification for the 2026 Munich game"},
        {"page": "https://www.nfl.com/games/patriots-at-lions-2026-reg-10",
         "field": "team record", "value": "New England Patriots 5-4; Detroit Lions 6-2",
         "usedFor": "record cross-check"},
        {"page": "https://www.nfl.com/teams/detroit-lions/roster",
         "field": "roster row", "value": "Cade Mays | 64 | C | ACT", "usedFor": "roster presence"},
        {"page": "https://www.nfl.com/teams/detroit-lions/roster",
         "field": "roster row", "value": "Jared Goff | 16 | QB | ACT", "usedFor": "roster presence"},

        {"page": "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc",
         "field": "season rushing yards leader", "value": "Bijan Robinson 880", "usedFor": "stats cross-check"},
        {"page": "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc",
         "field": "rushing yards", "value": "Jahmyr Gibbs 847", "usedFor": "stats cross-check"},
        {"page": "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc",
         "field": "rushing yards", "value": "Christian McCaffrey 457", "usedFor": "stats cross-check"},
        {"page": "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc",
         "field": "rushing yards", "value": "Bucky Irving 825", "usedFor": "stats cross-check"},
        {"page": "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc",
         "field": "rushing yards", "value": "James Cook 814", "usedFor": "stats cross-check"},
        {"page": "https://www.nfl.com/standings/", "field": "2026 division standings",
         "value": "32 club rows (W-L-T, PF, PA) transcribed into stage2_validate.py",
         "usedFor": "line-by-line archive validation"},
        {"page": "https://www.nfl.com/standings/", "field": "club label",
         "value": "the standings page prints AZ; the archive uses ARI", "usedFor": "explicit club alias"},
        {"page": "https://www.nfl.com/games/chiefs-at-eagles-2024-post-22",
         "field": "Super Bowl LIX result", "value": "PHI 40 - KC 22",
         "usedFor": "archive spot check"},
        {"page": "https://www.nfl.com/games/seahawks-at-patriots-2025-post-22",
         "field": "Super Bowl LX result", "value": "SEA 29 - NE 13",
         "usedFor": "archive spot check"},
    ],
}


def main() -> None:
    (OUT / "roster-2026").mkdir(parents=True, exist_ok=True)
    payload = dict(INJURY_WEEK)
    payload["generatedUTC"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (OUT / "injury-report-2026-week10.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (OUT / "official-crosschecks.json").write_text(
        json.dumps(OFFICIAL_CROSSCHECKS, indent=1) + "\n", encoding="utf-8")

    rows = [(t, r) for g in INJURY_WEEK["games"] for t, lst in g["teams"].items() for r in lst]
    blanks = sum(1 for _, r in rows if not r[3] or not r[4])
    print(f"official injury rows: {len(rows)} across {len(INJURY_WEEK['games'])} games; "
          f"{blanks} rows have a blank practice and/or game status (kept blank)")
    print(f"crosschecks: {len(OFFICIAL_CROSSCHECKS['records'])}")


if __name__ == "__main__":
    main()
