#!/usr/bin/env python3
"""Stage 2 - validation of the mirror archive against official NFL sources.

The archive (nflverse mirror) is only usable if it agrees with the league's own published
numbers. This script compares, field by field:

  1. every club's 2026 win/loss/tie record and points for/against, against
     https://www.nfl.com/standings/ (fetched 2026-11-13)
  2. selected 2026 player season totals against
     https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc
  3. the two most recent Super Bowl results against their official game pages
  4. internal consistency of the archive itself (result == home-away, total == home+away,
     no duplicate game ids, all 32 clubs present every season)

Every mismatch is published with both numbers and both URLs. Nothing is silently repaired.

Outputs: nfl-lines/data/validation/validation.json
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "nfl-lines" / "data"
OUT = DATA / "validation"

STANDINGS_URL = "https://www.nfl.com/standings/"
PLAYER_STATS_URL = ("https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/"
                    "rushingyards/desc")

# Transcribed from https://www.nfl.com/standings/ (2026, regular season, division view)
# columns: club, W, L, T, PF, PA
# The official standings page prints AZ; the archive uses ARI. The mapping is explicit so a
# silent rename can never mask a real disagreement.
CLUB_ALIAS = {"AZ": "ARI"}

# 1999-2001 seasons: the Houston Texans did not exist (first season 2002), so a 31-club
# count is correct for those three seasons, not a data defect. Verified against the
# archive's own club set and the franchise's official first season.
EXPECTED_CLUBS = {1999: 31, 2000: 31, 2001: 31}

OFFICIAL_STANDINGS_2026 = [
    ("BUF", 7, 1, 0, 256, 187), ("NE", 5, 4, 0, 211, 207), ("NYJ", 2, 7, 0, 182, 223),
    ("MIA", 1, 7, 0, 126, 200),
    ("PIT", 6, 2, 0, 180, 144), ("CIN", 6, 2, 0, 240, 175), ("CLE", 5, 4, 0, 161, 196),
    ("BAL", 4, 5, 0, 189, 236),
    ("JAX", 6, 2, 0, 229, 121), ("HOU", 3, 5, 0, 209, 192), ("IND", 2, 7, 0, 184, 249),
    ("TEN", 1, 7, 0, 144, 199),
    ("DEN", 7, 2, 0, 198, 186), ("KC", 6, 2, 0, 202, 143), ("LV", 4, 5, 0, 238, 268),
    ("LAC", 0, 8, 0, 121, 219),
    ("NYG", 5, 3, 1, 203, 196), ("DAL", 4, 5, 0, 246, 236), ("WAS", 3, 5, 1, 196, 223),
    ("PHI", 2, 7, 0, 148, 221),
    ("CHI", 7, 2, 0, 241, 184), ("DET", 6, 2, 0, 222, 189), ("MIN", 6, 2, 0, 146, 116),
    ("GB", 6, 3, 0, 216, 191),
    ("CAR", 3, 5, 0, 199, 219), ("NO", 3, 5, 0, 185, 216), ("TB", 3, 6, 0, 202, 178),
    ("ATL", 3, 6, 0, 188, 223),
    ("SF", 7, 1, 0, 235, 156), ("SEA", 5, 4, 0, 202, 162), ("LA", 5, 4, 0, 214, 181),
    ("AZ", 3, 6, 0, 178, 255),
]

# Transcribed from the official rushing leaderboard page (season totals, 2026 reg).
OFFICIAL_2026_RUSHING = [
    ("Bijan Robinson", "ATL", 880, 169, 5, 9),
    ("Kenneth Walker III", "SEA", 872, 159, 7, 7),
    ("Jahmyr Gibbs", "DET", 847, 177, 9, 3),
    ("Bucky Irving", "TB", 825, 167, 7, 6),
    ("James Cook", "BUF", 814, 169, 8, 4),
]

OFFICIAL_SUPER_BOWLS = [
    {"season": 2024, "gameId": "2024_22_KC_PHI", "away": "KC", "awayScore": 22, "home": "PHI",
     "homeScore": 40, "date": "2025-02-09",
     "url": "https://www.nfl.com/games/chiefs-at-eagles-2024-post-22"},
    {"season": 2025, "gameId": "2025_22_SEA_NE", "away": "SEA", "awayScore": 29, "home": "NE",
     "homeScore": 13, "date": "2026-02-08",
     "url": "https://www.nfl.com/games/seahawks-at-patriots-2025-post-22"},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = list(csv.DictReader((DATA / "games.csv").open(encoding="utf-8")))
    for g in games:
        g["season"] = int(g["season"])
        g["week"] = int(g["week"])

    # ---------------------------------------------------------- internal consistency
    internal = {"resultMismatches": 0, "totalMismatches": 0, "duplicateIds": 0,
                "missingClubsBySeason": {}, "rows": len(games)}
    seen = defaultdict(int)
    for g in games:
        seen[g["game_id"]] += 1
        if g["home_score"]:
            if int(g["home_score"]) - int(g["away_score"]) != int(g["result"]):
                internal["resultMismatches"] += 1
            if int(g["home_score"]) + int(g["away_score"]) != int(g["total"]):
                internal["totalMismatches"] += 1
    internal["duplicateIds"] = sum(1 for v in seen.values() if v > 1)
    by_season = defaultdict(set)
    for g in games:
        by_season[g["season"]].update([g["home_team"], g["away_team"]])
    for season, clubs in sorted(by_season.items()):
        want = EXPECTED_CLUBS.get(season, 32)
        if len(clubs) != want:
            internal["missingClubsBySeason"][season] = want - len(clubs)
    internal["expectedClubCounts"] = {str(k): v for k, v in EXPECTED_CLUBS.items()}
    internal["fewerClubsNote"] = ("1999-2001 have 31 clubs because the Houston Texans did not exist "
                                  "before 2002; that is expected, not a defect.")

    # ---------------------------------------------------------- 2026 standings check
    rec = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "games": 0})
    for g in games:
        if g["season"] != 2026 or not g["home_score"]:
            continue
        hs, as_ = int(g["home_score"]), int(g["away_score"])
        for team, own, opp in ((g["home_team"], hs, as_), (g["away_team"], as_, hs)):
            r = rec[team]
            r["games"] += 1
            r["pf"] += own
            r["pa"] += opp
            if own > opp:
                r["w"] += 1
            elif own < opp:
                r["l"] += 1
            else:
                r["t"] += 1
    standings_rows, standings_mismatches = [], 0
    for club_official, w, l, t, pf, pa in OFFICIAL_STANDINGS_2026:
        club = CLUB_ALIAS.get(club_official, club_official)
        a = rec.get(club, {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "games": 0})
        diffs = []
        if (a["w"], a["l"], a["t"]) != (w, l, t):
            diffs.append(f"record archive {a['w']}-{a['l']}-{a['t']} vs official {w}-{l}-{t}")
        if a["pf"] != pf:
            diffs.append(f"points for archive {a['pf']} vs official {pf}")
        if a["pa"] != pa:
            diffs.append(f"points against archive {a['pa']} vs official {pa}")
        if diffs:
            standings_mismatches += 1
        standings_rows.append({"club": club, "officialClubLabel": club_official,
                               "aliasApplied": club != club_official,
                               "gamesArchive": a["games"],
                               "archive": {"w": a["w"], "l": a["l"], "t": a["t"], "pf": a["pf"], "pa": a["pa"]},
                               "official": {"w": w, "l": l, "t": t, "pf": pf, "pa": pa},
                               "match": not diffs, "differences": diffs,
                               "sourceUrl": STANDINGS_URL})

    # ---------------------------------------------------------- 2026 player stats check
    stats = list(csv.DictReader((DATA / "stats_player_week_2025.csv").open(encoding="utf-8")))
    # (the 2026 week-level file is not reachable; the 2026 official leaderboard is checked
    #  against the official page itself rather than the archive - see note)
    player_rows = []
    for name, team, yds, att, td, _ in OFFICIAL_2026_RUSHING:
        player_rows.append({"player": name, "club": team, "officialRushYards": yds,
                            "officialAttempts": att, "officialRushTds": td,
                            "archiveSeason": "2025 only - the reachable mirror holds no 2026 week-level player file",
                            "archiveValue": None, "match": None,
                            "note": "recorded as an official value for cross-reference, not as an archive match",
                            "sourceUrl": PLAYER_STATS_URL})
    # cross-check the 2025 archive against the same player's official 2025 total where the
    # official 2026 page also exposes 2025 selections; not available in a single fetch, so the
    # check is explicitly recorded as not performed.

    # ---------------------------------------------------------- Super Bowl check
    sb_rows = []
    for sb in OFFICIAL_SUPER_BOWLS:
        match = [g for g in games if g["game_id"] == sb["gameId"]]
        if not match:
            sb_rows.append({**sb, "archiveFound": False, "match": False})
            continue
        g = match[0]
        ok = (int(g["away_score"]) == sb["awayScore"] and int(g["home_score"]) == sb["homeScore"]
              and g["gameday"] == sb["date"])
        sb_rows.append({"season": sb["season"], "gameId": sb["gameId"],
                        "archive": {"away": g["away_team"], "awayScore": int(g["away_score"]),
                                    "home": g["home_team"], "homeScore": int(g["home_score"]),
                                    "date": g["gameday"]},
                        "official": {"away": sb["away"], "awayScore": sb["awayScore"],
                                     "home": sb["home"], "homeScore": sb["homeScore"], "date": sb["date"]},
                        "archiveFound": True, "match": ok, "sourceUrl": sb["url"]})

    # ---------------------------------------------------------- 2025 injury mirror check
    inj = list(csv.DictReader((DATA / "injuries_2025_mirror.csv").open(encoding="utf-8")))
    statuses = defaultdict(int)
    for r in inj:
        statuses[r["report_status"]] += 1
    injury_check = {
        "rows": len(inj),
        "weeksCovered": [min(int(r["week"]) for r in inj), max(int(r["week"]) for r in inj)],
        "clubs": len({r["team"] for r in inj}),
        "statusCounts": dict(sorted(statuses.items())),
        "columns": list(inj[0]),
        "missingOfficialColumns": ["practice_status", "report_primary_injury", "position",
                                   "game_status distinction", "publication timestamp"],
        "sourceUrl": "https://www.nfl.com/injuries/league/2025/reg{week}",
        "note": "The 2025 mirror carries five columns. The official page carries position, injury, "
                "practice status and game status. Statuses present here are report_status values, so an "
                "'Out' in the mirror means the official report listed the player as Out for that week.",
    }

    payload = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": {
            "internalConsistency": internal,
            "standings2026": {"rows": standings_rows, "mismatches": standings_mismatches,
                              "checked": len(standings_rows), "sourceUrl": STANDINGS_URL},
            "playerStats2026": {"rows": player_rows, "sourceUrl": PLAYER_STATS_URL,
                                "note": "The reachable mirror contains 2025 player-week data only, so no "
                                        "archive-vs-official match is claimed for 2026 player totals."},
            "superBowls": {"rows": sb_rows, "matches": sum(1 for r in sb_rows if r["match"])},
            "injuryMirror2025": injury_check,
        },
        "verdict": {
            "standingsAgreement": f"{len(standings_rows) - standings_mismatches}/{len(standings_rows)} clubs",
            "superBowlAgreement": f"{sum(1 for r in sb_rows if r['match'])}/{len(sb_rows)} games",
            "internalErrors": internal["resultMismatches"] + internal["totalMismatches"] + internal["duplicateIds"],
        },
        "notVerified": [
            "2026 player-level totals from the archive (no 2026 week-level player file is reachable).",
            "historical betting prices (no official source exists at all).",
            "practice participation and injury severity in the 2025 mirror (columns absent).",
        ],
    }
    (OUT / "validation.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"standings: {payload['verdict']['standingsAgreement']}  "
          f"super bowls: {payload['verdict']['superBowlAgreement']}  "
          f"internal errors: {payload['verdict']['internalErrors']}")
    for r in standings_rows:
        if not r["match"]:
            print("  MISMATCH", r["club"], r["differences"])


if __name__ == "__main__":
    main()
