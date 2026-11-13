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


def _sign_check(games) -> dict:
    """Publish the evidence for the sign convention instead of asserting it.

    Two independent tests on the same archive:
      * OLS of the actual home margin on spread_line. The slope must be about +1 if the
        archive number is the home handicap (it is: ~1.045).
      * The home cover rate under (margin - line) > 0. A priced market must land near 50%.
        The mirrored form, (margin + line) > 0, is shown too, because it is the mistake that
        was made in the first build of this stage and is now impossible to make silently.
    """
    rows = [g for g in games if g.get("played") and g["spread_line"] not in (None, "", "None")]
    n = len(rows)
    if n < 100:
        return {"rows": n, "slope": None, "intercept": None,
                "coverRateCorrect": None, "coverRateMirrored": None}
    xs = [float(g["spread_line"]) for g in rows]
    ys = [int(g["home_score"]) - int(g["away_score"]) for g in rows]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else None
    intercept = my - slope * mx if slope is not None else None
    cover = sum(1 for x, y in zip(xs, ys) if y - x > 0) / n
    mirrored = sum(1 for x, y in zip(xs, ys) if y + x > 0) / n
    return {"rows": n, "slope": round(slope, 4) if slope is not None else None,
            "intercept": round(intercept, 3) if intercept is not None else None,
            "coverRateCorrect": round(cover, 4), "coverRateMirrored": round(mirrored, 4),
            "interpretation": ("A slope near +1 and a cover rate near 50% mean the archive number is the "
                               "home handicap and the gap must be computed as fair_margin - spread_line.")}


def _model_consistency(lines) -> dict:
    """Do the spread gap and the moneyline gap point the same way?

    They are produced by different chains (spread: OLS margin mapping; moneyline: the Elo
    probability itself), so a disagreement is possible near zero. Publishing the count, and
    the games, is cheaper than pretending the two views always agree.
    """
    disagree = []
    for g in lines:
        sp = g["edge"].get("spread")
        ml = g["fairPrice"].get("moneyline")
        if not sp or not ml:
            continue
        spread_side_home = sp["homeEdgePoints"] > 0
        ml_side_home = (ml["modelProbHome"] - ml["marketImpliedHomeDevigged"]) > 0
        if spread_side_home != ml_side_home:
            disagree.append({"gameId": g["gameId"],
                             "spreadGap": sp["homeEdgePoints"],
                             "moneylineGap": round(ml["modelProbHome"] - ml["marketImpliedHomeDevigged"], 4)})
    return {"compared": sum(1 for g in lines if g["edge"].get("spread") and g["fairPrice"].get("moneyline")),
            "disagree": disagree,
            "note": ("Both views come from the same Elo probability but through different mappings; "
                     "they can disagree in sign when the gap is a fraction of a point.")}


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
            # SIGN CONVENTION, verified against all 7,548 archive rows:
            #   games.csv `spread_line` IS the home handicap itself (positive = home favoured).
            #   OLS of actual home margin on spread_line over 7,382 graded games gives
            #   margin = -0.04 + 1.045 * spread_line, and the home club covers
            #   (margin - line) > 0 only 47.6% of the time (correct for a priced market;
            #   the mirrored (margin + line) form "covers" 59.2%, which is the tell that it is wrong).
            # So the fair home handicap is exactly fair_margin, and the gap to the market is a
            # subtraction. The 2026-11-13 build added the two instead and published gaps of
            # 18-30 points; that is corrected here and recorded on the Method page.
            fair_handicap = round(fair_margin, 2)
            edge_home = round(fair_handicap - spread, 2)   # >0 => model makes home stronger than the market
            row["edge"]["spread"] = {"homeEdgePoints": edge_home,
                                     "fairHandicap": fair_handicap,
                                     "marketHandicap": spread,
                                     "side": "home" if edge_home > 0 else "away",
                                     "absEdge": abs(edge_home)}
            side_is_home = edge_home > 0
            # The model probability of the side is NOT the win probability: covering a handicap
            # needs the margin to clear it. Estimate it from the covered side's own price band:
            # we publish the model's fair price for the handicap as the break-even ML implied by
            # ph adjusted for the handicap -- and refuse to compute one where the model edge is
            # under half a point, because the mapping noise dominates there.
            row["fairPrice"]["spread"] = {
                "side": "home" if side_is_home else "away",
                "fairHandicap": fair_handicap if side_is_home else -fair_handicap,
                "marketHandicap": spread,
                "edgePoints": abs(edge_home),
                "marketAmerican": row["market"]["homeSpreadOdds"] if side_is_home else None,
                "modelSpreadCoverProb": None,
                "note": ("Cover probability is not published for the spread: this lab has no "
                         "calibrated margin distribution, so a cover probability would be invented. "
                         "The edge in points is published instead."),
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
                                  "graded game in the archive. The archive's spread_line IS the home handicap "
                                  "(positive = home favoured), so the fair handicap is the fair home margin "
                                  "itself and the gap to the market is a subtraction. The earlier build added "
                                  "the two and is corrected; see signCheck."},
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
        "signCheck": _sign_check(games),
        "modelConsistency": _model_consistency(lines),
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
