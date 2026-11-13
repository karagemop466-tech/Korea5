#!/usr/bin/env python3
"""Stage 5 - injury and lineup-tier tracker.

Two halves, both source-labelled:

A. 2026 official week-10 tracker.
   Input: the official NFL injury report page for 2026 week 10 (captured in
   nfl-lines/data/official/injury-report-2026-week10.json).
   For every officially listed player we attach a ROLE TIER computed from the most
   recent full season of production in the archive (2025), ranked within club and
   position group. The tier is OUR measurement, NOT an official depth chart: nfl.com's
   /teams/<club>/depth-chart returns 404 from this environment (checked 2026-11-13).
   Players with no 2025 production record get tier "" (blank, unverified) - never a guess.

B. 2025 empirical injury impact.
   Input: the 2025 injury mirror (season, week, club, player, report status) and the
   2025 player-week statistics mirror.
   For each club-week we rank players by trailing production BEFORE that week, find the
   tier-1 player in each position group, and check whether he was officially Out /
   Injured Reserve. We then compare club points scored and allowed with and without a
   tier-1 absence, with a bootstrap interval. This is a measured association on one
   season, not a causal effect.

Outputs:
  nfl-lines/data/injuries/tracker-2026-week10.json
  nfl-lines/data/injuries/impact-2025.json
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "nfl-lines" / "data"
OUT = DATA / "injuries"
SEED = 20261113
DRAWS = 2000

OFF_GROUPS = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}
DEF_GROUPS = {"DE": "DL", "DT": "DL", "NT": "DL", "LB": "LB", "ILB": "LB", "OLB": "LB",
              "CB": "CB", "S": "S", "SAF": "S", "FS": "S", "SS": "S", "DB": "S"}
OL_GROUPS = {"T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL", "OL": "OL"}


def group_of(pos: str) -> str:
    p = (pos or "").upper()
    return OFF_GROUPS.get(p) or DEF_GROUPS.get(p) or OL_GROUPS.get(p) or "OTHER"


def side_of(grp: str) -> str:
    if grp in ("QB", "RB", "WR", "TE", "OL"):
        return "offense"
    if grp in ("DL", "LB", "CB", "S"):
        return "defense"
    return "other"


def load_stats():
    rows = list(csv.DictReader((DATA / "stats_player_week_2025.csv").open(encoding="utf-8")))
    for r in rows:
        r["week"] = int(r["week"])
        for k in ("fantasy_points_ppr", "receiving_yards", "rushing_yards", "passing_yards",
                  "def_tackles_solo", "def_tackles_with_assist", "def_sacks",
                  "def_interceptions", "def_pass_defended", "targets", "carries"):
            try:
                r[k] = float(r[k]) if r[k] not in ("", None) else 0.0
            except ValueError:
                r[k] = 0.0
    return rows


def production(row: dict) -> float:
    """A single 'role size' number per player-week. Documented, not tuned."""
    return (row["fantasy_points_ppr"] + row["def_tackles_solo"] + 0.5 * row["def_tackles_with_assist"]
            + 2.0 * row["def_sacks"] + 3.0 * row["def_interceptions"])


def tier_label(rank: int) -> str:
    return {1: "1st string (tier 1)", 2: "2nd string (tier 2)", 3: "3rd string (tier 3)",
            4: "4th string (tier 4)"}.get(rank, f"{rank}th string")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stats = load_stats()

    # ---- season production by (club, position group, player) for tier assignment
    season_prod = defaultdict(float)
    player_pos = {}
    for r in stats:
        key = (r["team"], group_of(r["position"]), r["player_display_name"].strip().lower())
        season_prod[key] += production(r)
        player_pos[(r["team"], r["player_display_name"].strip().lower())] = r["position"]

    def tier_for(team: str, name: str):
        nm = name.strip().lower()
        pos = player_pos.get((team, nm))
        if pos is None:
            return None, None, None
        grp = group_of(pos)
        peers = sorted(((v, k) for k, v in season_prod.items() if k[0] == team and k[1] == grp), reverse=True)
        rank = next((i + 1 for i, (_, k) in enumerate(peers) if k[2] == nm), None)
        repl = None
        for i, (v, k) in enumerate(peers):
            if k[2] != nm and i < 6 and rank is not None and i + 1 > rank:
                repl = {"player": k[2].title(), "tier": tier_label(i + 1), "seasonProduction": round(v, 1)}
                break
        return pos, (rank, tier_label(rank)) if rank else None, repl

    # ================================================= A. 2026 week-10 official tracker
    official = json.loads((DATA / "official" / "injury-report-2026-week10.json").read_text())
    tracker_rows = []
    for game in official["games"]:
        for team, players in game["teams"].items():
            for name, pos, injury, practice, status in players:
                derived_pos, tier, repl = tier_for(team, name)
                grp = group_of(pos)
                tracker_rows.append({
                    "team": team, "opponent": game["home"] if team == game["away"] else game["away"],
                    "gameDate": game["date"], "player": name, "position": pos,
                    "positionGroup": grp, "side": side_of(grp),
                    "injury": injury, "practiceStatus": practice, "gameStatus": status,
                    "tier": tier[1] if tier else "", "tierRank": tier[0] if tier else None,
                    "tierBasis": "last full season (2025) production rank within club and position group"
                                 if tier else "no 2025 production record in the archive - tier left blank",
                    "candidateReplacement": repl,
                    "sourceUrl": official["sourceUrl"],
                })
    # club-level summary: how many tier-1 players are officially out, split offence/defence
    summary = defaultdict(lambda: {"offenseTier1Out": 0, "defenseTier1Out": 0,
                                   "offenseListed": 0, "defenseListed": 0, "sourceUrl": official["sourceUrl"]})
    for t in tracker_rows:
        s = summary[t["team"]]
        if t["side"] == "offense":
            s["offenseListed"] += 1
            if t["tierRank"] == 1 and t["gameStatus"] == "Out":
                s["offenseTier1Out"] += 1
        elif t["side"] == "defense":
            s["defenseListed"] += 1
            if t["tierRank"] == 1 and t["gameStatus"] == "Out":
                s["defenseTier1Out"] += 1

    tracker = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": 2026, "week": 10,
        "sourceUrl": official["sourceUrl"],
        "officialStatusCounts": {
            "Out": sum(1 for t in tracker_rows if t["gameStatus"] == "Out"),
            "Doubtful": sum(1 for t in tracker_rows if t["gameStatus"] == "Doubtful"),
            "Questionable": sum(1 for t in tracker_rows if t["gameStatus"] == "Questionable"),
            "blank": sum(1 for t in tracker_rows if not t["gameStatus"]),
        },
        "blankPracticeStatus": sum(1 for t in tracker_rows if not t["practiceStatus"]),
        "rows": tracker_rows,
        "clubSummary": {k: v for k, v in sorted(summary.items())},
        "depthChartStatus": {
            "officialDepthChartRetrieved": False,
            "evidence": "https://www.nfl.com/teams/detroit-lions/depth-chart returns HTTP 404 (fetched 2026-11-13). "
                        "The official roster page returns 200 and lists position + ACT status only, with no "
                        "1st/2nd/3rd string order.",
            "consequence": "Tiers on this page are measured from production, not read from an official depth chart. "
                           "They are labelled as such everywhere.",
        },
        "methodNotes": [
            "The official injury page publishes position, injury, practice status and game status per club.",
            "Many players have a blank practice status and/or blank game status on the page. They stay blank here.",
            "Tier = rank by last full season (2025) production within the same club and position group. "
            "A rookie or a new signing with no 2025 record is left blank.",
            "Candidate replacement = the next-ranked player at the same club and position group. It is a "
            "production-ranked candidate, not an official lineup announcement.",
        ],
    }
    (OUT / "tracker-2026-week10.json").write_text(json.dumps(tracker, indent=1) + "\n", encoding="utf-8")

    # ================================================= B. 2025 empirical impact
    inj = list(csv.DictReader((DATA / "injuries_2025_mirror.csv").open(encoding="utf-8")))
    for r in inj:
        r["week"] = int(r["week"])
    inj_by = defaultdict(set)
    for r in inj:
        inj_by[(r["team"], r["week"])].add((r["full_name"].strip().lower(), r["report_status"]))

    games = list(csv.DictReader((DATA / "games.csv").open(encoding="utf-8")))
    games = [g for g in games if g["season"] == "2025" and g["home_score"]]
    for g in games:
        g["week"] = int(g["week"])

    # trailing production, point-in-time
    by_player = defaultdict(list)
    for r in stats:
        by_player[(r["team"], r["player_display_name"].strip().lower(), group_of(r["position"]))].append(r)
    for k in by_player:
        by_player[k].sort(key=lambda r: r["week"])

    def trailing(key, week, n=4):
        rows = [r for r in by_player[key] if r["week"] < week][-n:]
        if not rows:
            return None
        return sum(production(r) for r in rows) / len(rows)

    def tier1_for(team, grp, week):
        cands = []
        for (t, nm, g), rows in by_player.items():
            if t != team or g != grp:
                continue
            tr = trailing((t, nm, g), week)
            if tr is not None:
                cands.append((tr, nm))
        if not cands:
            return None
        return max(cands)[1]

    records = []
    for g in games:
        if g["week"] < 6:      # need 4 trailing games + 1 warm-up week
            continue
        for team, opp_pts, team_pts in ((g["home_team"], g["away_score"], g["home_score"]),
                                        (g["away_team"], g["home_score"], g["away_score"])):
            listed = {nm: st for nm, st in inj_by.get((team, g["week"]), set())}
            absences = {}
            for grp in ("QB", "RB", "WR", "TE", "DL", "LB", "CB", "S"):
                top = tier1_for(team, grp, g["week"])
                if top is None:
                    continue
                status = listed.get(top, "")
                absences[grp] = {"player": top, "status": status,
                                 "out": status in ("Out", "Injured Reserve", "Doubtful")}
            records.append({
                "season": 2025, "week": g["week"], "team": team, "gameId": g["game_id"],
                "opponent": g["away_team"] if team == g["home_team"] else g["home_team"],
                "pointsFor": int(team_pts), "pointsAgainst": int(opp_pts),
                "absences": absences,
                "offenseTier1Out": sum(1 for grp, v in absences.items() if side_of(grp) == "offense" and v["out"]),
                "defenseTier1Out": sum(1 for grp, v in absences.items() if side_of(grp) == "defense" and v["out"]),
            })

    def boot_mean_diff(a, b):
        if len(a) < 20 or len(b) < 20:
            return {"low": None, "high": None, "note": "group smaller than 20 - interval not estimated"}
        rnd = random.Random(SEED)
        diffs = []
        for _ in range(DRAWS):
            sa = [a[rnd.randrange(len(a))] for _ in range(len(a))]
            sb = [b[rnd.randrange(len(b))] for _ in range(len(b))]
            diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
        diffs.sort()
        return {"low": round(diffs[int(0.025 * len(diffs))], 2),
                "high": round(diffs[int(0.975 * len(diffs))], 2), "draws": DRAWS}

    impact = {}
    for label, key_side in (("anyTier1OffenseOut", "offense"), ("anyTier1DefenseOut", "defense")):
        with_ = [r for r in records if r[f"{key_side}Tier1Out"] > 0]
        without = [r for r in records if r[f"{key_side}Tier1Out"] == 0]
        # offence out -> effect on own points; defence out -> effect on opponent points
        if key_side == "offense":
            a = [r["pointsFor"] for r in with_]
            b = [r["pointsFor"] for r in without]
            metric = "own points scored"
        else:
            a = [r["pointsAgainst"] for r in with_]
            b = [r["pointsAgainst"] for r in without]
            metric = "points allowed"
        impact[label] = {
            "metric": metric, "nWith": len(a), "nWithout": len(b),
            "meanWith": round(sum(a) / len(a), 2) if a else None,
            "meanWithout": round(sum(b) / len(b), 2) if b else None,
            "difference": round(sum(a) / len(a) - sum(b) / len(b), 2) if a and b else None,
            "ci": boot_mean_diff(a, b),
        }
    # by position group, the biggest single measured effect
    by_group = {}
    for grp in ("QB", "RB", "WR", "TE", "DL", "LB", "CB", "S"):
        a, b = [], []
        for r in records:
            v = r["absences"].get(grp)
            if v is None:
                continue
            target = r["pointsFor"] if side_of(grp) == "offense" else r["pointsAgainst"]
            (a if v["out"] else b).append(target)
        by_group[grp] = {"positionGroup": grp, "side": side_of(grp),
                         "metric": "own points scored" if side_of(grp) == "offense" else "points allowed",
                         "nWith": len(a), "nWithout": len(b),
                         "meanWith": round(sum(a) / len(a), 2) if a else None,
                         "meanWithout": round(sum(b) / len(b), 2) if b else None,
                         "difference": round(sum(a) / len(a) - sum(b) / len(b), 2) if a and b else None,
                         "ci": boot_mean_diff(a, b)}

    payload = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": 2025,
        "nClubWeeks": len(records),
        "nGames": len({r["gameId"] for r in records}),
        "weeksCovered": [min(r["week"] for r in records), max(r["week"] for r in records)],
        "sources": [
            {"id": "mirror-injuries-2025", "what": "official-report status values, mirrored",
             "officialUrl": "https://www.nfl.com/injuries/league/2025/reg{week}"},
            {"id": "mirror-stats-player-week-2025", "what": "player-week production"},
            {"id": "nfldata-games", "what": "final scores"},
        ],
        "method": [
            "Tier-1 player for a club and position group = highest trailing 4-game production among players "
            "with a game in that group before the week in question.",
            "An absence is counted only when the mirror records the official status Out, Doubtful or Injured "
            "Reserve for that club-week.",
            "The comparison is a raw difference of means with a bootstrap interval. It is a measured "
            "association in one season, not a causal estimate, and it is not used as a betting input.",
            "Offensive line is NOT included: the archive has no per-snap or per-start line data, so no "
            "line-breakdown claim is made.",
        ],
        "limitations": [
            "Injured Reserve is a season-long designation in the mirror, so a player on IR from week 1 is "
            "counted as unavailable for every later week.",
            "The 2025 mirror carries no practice participation or primary injury, so severity cannot be graded.",
            "Only one season of overlap exists in the reachable archive, so the sample is about one season of "
            "club-weeks.",
            "Name matching is exact (club + full name). Unmatched players are dropped rather than fuzzy-matched.",
        ],
        "overall": impact,
        "byPositionGroup": by_group,
        "records": records,
    }
    (OUT / "impact-2025.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    print(f"2026 W10 tracker rows: {len(tracker_rows)}  official status counts "
          f"{tracker['officialStatusCounts']}  blank practice {tracker['blankPracticeStatus']}")
    print(f"2025 impact club-weeks: {len(records)}")
    for k, v in impact.items():
        print(f"  {k}: {v['metric']} with={v['meanWith']} without={v['meanWithout']} "
              f"diff={v['difference']} ci={v['ci']}")
    for k, v in by_group.items():
        print(f"  {k:3s} {v['metric']:18s} n={v['nWith']}/{v['nWithout']} diff={v['difference']} ci={v['ci']}")


if __name__ == "__main__":
    main()
