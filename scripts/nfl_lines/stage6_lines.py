#!/usr/bin/env python3
"""Stage 6 - line origination for the next slate.

Produces, for every 2026 Week 11 game that has a closing market line in the archive:
  * the model fair spread, fair total and fair moneylines (from the same point-in-time
    rating/rate machinery as the backtest),
  * the market number and price,
  * the edge in points (spread/total) or probability (moneyline),
  * the price at which taking the side would be break-even given the model probability
    (a *fair price*, which is the thing the user asked to originate),
  * a label: PASS / WATCH / PLAY-candidate, where any PLAY label requires the strategy to
    have passed the release gates. In this lab no strategy has, so every game is PASS or
    WATCH and the reason is printed with the row.

No price is invented: a game without a line in the archive produces no fair price.
Outputs: nfl-lines/data/lines/week-11-2026.json
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "nfl-lines" / "data"
OUT = DATA / "lines"


def am_to_dec(ml: float) -> float:
    return 1 + (ml / 100.0 if ml > 0 else 100.0 / abs(ml))


def dec_to_am(dec: float) -> int:
    if dec >= 2.0:
        return round((dec - 1) * 100)
    return -round(100 / (dec - 1))


def implied(ml: float) -> float:
    return (-ml) / (-ml + 100.0) if ml < 0 else 100.0 / (ml + 100.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = list(csv.DictReader((DATA / "games.csv").open(encoding="utf-8")))
    for g in games:
        g["season"] = int(g["season"]); g["week"] = int(g["week"])
        g["played"] = bool(g["home_score"])
    games.sort(key=lambda r: (r["gameday"], r["gametime"] or "17:00"))

    # ---- rebuild point-in-time ratings and scoring rates through the end of week 10
    K, HFA, REGRESS = 20.0, 48.0, 1 / 3
    rating, last_seen = {}, {}

    def get(t, s):
        if t not in rating:
            rating[t] = 1505.0
        if t in last_seen and last_seen[t] != s:
            rating[t] = 1505.0 + (rating[t] - 1505.0) * (1 - REGRESS)
        last_seen[t] = s
        return rating[t]

    off_sum, off_n = defaultdict(float), defaultdict(int)
    def_sum, def_n = defaultdict(float), defaultdict(int)
    lg_sum, lg_n = 0.0, 0
    PRIOR = 6.0
    # OLS mapping from (elo probability - 0.5) to the actual home margin, fitted on graded games
    n_ = Sx = Sy = Sxx = Sxy = 0.0

    for g in games:
        if not g["played"]:
            continue
        s = g["season"]
        ph = 1 / (1 + 10 ** ((get(g["away_team"], s) - get(g["home_team"], s) - HFA) / 400))
        mov = abs(int(g["home_score"]) - int(g["away_score"]))
        mult = math.log1p(mov) * 2.2 / ((abs(rating[g["home_team"]] - rating[g["away_team"]]) * 0.001) + 2.2)
        res = 1.0 if int(g["home_score"]) > int(g["away_score"]) else (
            0.5 if int(g["home_score"]) == int(g["away_score"]) else 0.0)
        d = K * mult * (res - ph)
        rating[g["home_team"]] += d
        rating[g["away_team"]] -= d
        x = ph - 0.5
        n_ += 1; Sx += x; Sy += (int(g["home_score"]) - int(g["away_score"])); Sxx += x * x; Sxy += x * (int(g["home_score"]) - int(g["away_score"]))
        # scoring rates
        lg_sum += int(g["home_score"]) + int(g["away_score"]); lg_n += 1
        off_sum[g["home_team"]] += int(g["home_score"]); off_n[g["home_team"]] += 1
        off_sum[g["away_team"]] += int(g["away_score"]); off_n[g["away_team"]] += 1
        def_sum[g["home_team"]] += int(g["away_score"]); def_n[g["home_team"]] += 1
        def_sum[g["away_team"]] += int(g["home_score"]); def_n[g["away_team"]] += 1

    b = (Sxy - Sx * Sy / n_) / (Sxx - Sx * Sx / n_) if n_ and (Sxx - Sx * Sx / n_) > 1e-9 else None
    a_int = Sy / n_ - b * Sx / n_ if b is not None else None
    lg_mean = lg_sum / lg_n if lg_n else None

    def rate(sm, n, t):
        return (sm[t] + PRIOR * lg_mean) / (n[t] + PRIOR)

    lines = []
    for g in games:
        if g["season"] != 2026 or g["week"] != 11 or g["played"]:
            continue
        s = 2026
        neutral = g["location"] == "Neutral"
        ph = 1 / (1 + 10 ** ((get(g["away_team"], s) - get(g["home_team"], s) - (0 if neutral else HFA)) / 400))
        fair_margin = (a_int + b * (ph - 0.5)) if (a_int is not None) else None
        fair_total = None
        if lg_mean is not None and off_n[g["home_team"]] >= 3 and off_n[g["away_team"]] >= 3:
            h_off, h_def = rate(off_sum, off_n, g["home_team"]), rate(def_sum, def_n, g["home_team"])
            a_off, a_def = rate(off_sum, off_n, g["away_team"]), rate(def_sum, def_n, g["away_team"])
            fair_total = (h_off + a_def) / 2 + (a_off + h_def) / 2
        spread = float(g["spread_line"]) if g["spread_line"] else None
        total = float(g["total_line"]) if g["total_line"] else None
        row = {
            "gameId": g["game_id"], "kickoff": f'{g["gameday"]}T{g["gametime"] or "TBD"}',
            "away": g["away_team"], "home": g["home_team"], "venue": g["stadium"],
            "neutral": neutral,
            "market": {"spread": spread, "total": total,
                       "homeMl": float(g["home_moneyline"]) if g["home_moneyline"] else None,
                       "awayMl": float(g["away_moneyline"]) if g["away_moneyline"] else None,
                       "homeSpreadOdds": float(g["home_spread_odds"]) if g["home_spread_odds"] else None,
                       "overOdds": float(g["over_odds"]) if g["over_odds"] else None},
            "model": {"homeWinProb": round(ph, 4),
                      "fairSpread": round(fair_margin, 2) if fair_margin is not None else None,
                      "fairTotal": round(fair_total, 2) if fair_total is not None else None},
            "edge": {},
            "fairPrice": {},
            "label": "PASS",
            "reasons": [],
        }
        if fair_margin is not None and spread is not None:
            # the archive stores the home handicap with the opposite sign convention to a
            # margin expectation; the fair home handicap is -fair_margin
            edge_home = round(fair_margin + spread, 2)   # spread is negative when home is favoured
            row["edge"]["spread"] = {"homeEdgePoints": edge_home,
                                     "side": "home" if edge_home > 0 else "away",
                                     "absEdge": abs(edge_home)}
            side_prob = ph if edge_home > 0 else 1 - ph
            row["fairPrice"]["spread"] = {
                "side": "home" if edge_home > 0 else "away",
                "modelProb": round(side_prob, 4),
                "fairDecimal": round(1 / side_prob, 3) if side_prob > 0 else None,
                "fairAmerican": dec_to_am(1 / side_prob) if side_prob > 0 else None,
                "marketAmerican": row["market"]["homeSpreadOdds"] if edge_home > 0 else None,
            }
        if fair_total is not None and total is not None:
            edge_total = round(fair_total - total, 2)
            row["edge"]["total"] = {"overEdgePoints": edge_total,
                                    "side": "over" if edge_total > 0 else "under",
                                    "absEdge": abs(edge_total)}
        if row["market"]["homeMl"] is not None:
            dec_h = am_to_dec(row["market"]["homeMl"])
            dec_a = am_to_dec(row["market"]["awayMl"])
            row["fairPrice"]["moneyline"] = {
                "modelProbHome": round(ph, 4), "modelProbAway": round(1 - ph, 4),
                "fairAmericanHome": dec_to_am(1 / ph) if ph > 0 else None,
                "fairAmericanAway": dec_to_am(1 / (1 - ph)) if ph < 1 else None,
                "marketAmericanHome": row["market"]["homeMl"],
                "marketAmericanAway": row["market"]["awayMl"],
                "marketImpliedHomeDevigged": round(implied(row["market"]["homeMl"]) /
                                                   (implied(row["market"]["homeMl"]) + implied(row["market"]["awayMl"])), 4),
            }
        # labelling: a PLAY label is impossible until a strategy passes every gate
        row["reasons"].append("No strategy in this lab has passed the release gates "
                              "(G7 prospective trial and G8 human review), so no row can be labelled PLAY.")
        if row["edge"].get("spread") and row["edge"]["spread"]["absEdge"] >= 1.0:
            row["label"] = "WATCH"
            row["reasons"].append(f"model spread differs from the number by "
                                  f"{row['edge']['spread']['absEdge']} points")
        if row["edge"].get("total") and row["edge"]["total"]["absEdge"] >= 1.5:
            row["label"] = "WATCH"
            row["reasons"].append(f"model total differs from the number by "
                                  f"{row['edge']['total']['absEdge']} points")
        lines.append(row)

    payload = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": 2026, "week": 11,
        "marginMapping": {"intercept": round(a_int, 3) if a_int is not None else None,
                          "slope": round(b, 3) if b is not None else None,
                          "fittedOn": int(n_),
                          "note": "fair_home_margin = intercept + slope * (elo_home_prob - 0.5), fitted on every "
                                  "graded game in the archive. The archive records the home handicap with the "
                                  "opposite sign (positive = home favoured), so the fair handicap = -fair_margin."},
        "leagueMeanTotal": round(lg_mean, 2) if lg_mean else None,
        "marketSource": "nfldata-games closing lines (NOT OFFICIAL - the NFL publishes no betting prices)",
        "method": [
            "Ratings: Elo with margin-weighted updates and season regression, built only from graded games.",
            "Fair spread: an OLS mapping from (home win probability - 0.5) to the actual home margin, fitted "
            "on every graded game in the archive and reported in marginMapping.",
            "Fair total: each club's points-for and points-allowed rate shrunk toward the league mean with a "
            "6-game prior, averaged across both clubs.",
            "Fair price: 1 / model probability, converted to American odds. It is the price at which the "
            "model thinks the bet is a coin flip - exactly what 'originating a line' means.",
        ],
        "blockedInputs": [
            "Official depth-chart tiers: nfl.com depth-chart pages return 404 here, so injury/backup tier "
            "adjustment is NOT applied to these fair lines.",
            "Player props: no prop prices exist in the archive, so no prop lines are originated.",
            "Weather: not in the archive. Indoor/outdoor is known but conditions are not.",
        ],
        "lines": lines,
        "counts": {
            "games": len(lines),
            "withSpread": sum(1 for r in lines if r["model"]["fairSpread"] is not None),
            "withTotal": sum(1 for r in lines if r["model"]["fairTotal"] is not None),
            "watch": sum(1 for r in lines if r["label"] == "WATCH"),
            "play": sum(1 for r in lines if r["label"] == "PLAY"),
        },
    }
    (OUT / "week-11-2026.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"week 11 lines: {payload['counts']}  mapping={payload['marginMapping']} "
          f"leagueMean={payload['leagueMeanTotal']}")
    for r in lines:
        print(" ", r["away"], "@", r["home"], r["market"]["spread"], r["market"]["total"],
              "fair", r["model"]["fairSpread"], r["model"]["fairTotal"], r["label"],
              r["fairPrice"].get("moneyline"))


if __name__ == "__main__":
    main()
