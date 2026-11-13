#!/usr/bin/env python3
"""Stage 4 - correlation engine.

Measures, from joint outcomes only:

  1. same-game market dependence   (spread cover vs total over, moneyline vs total, ...)
  2. same-team player dependence   (QB passing yards vs WR receiving yards, RB vs RB, ...)
  3. cross-player same-game pairs  (QB vs opposing pass rush proxy, WR vs WR, ...)
  4. parlay dependence vs the independence assumption used to price the s7/s8 parlays

For binary pairs it reports the phi coefficient together with n, the observed joint
probability and the product of the marginals, so the reader can see the size of the error
you make by assuming independence. phi is a descriptive statistic; it is NOT a pricing
formula. Pricing must use the joint probability (or a fitted joint model), and the joint
probability is what is published here.

Player prop "lines" are a PROXY: each player's own trailing 4-week average. This is not a
sportsbook line because this lab holds no prop prices. Every table row says so.

Outputs: nfl-lines/data/correlation/*.json
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
OUT = DATA / "correlation"
SEED = 20261113
DRAWS = 1000


def phi(pairs: list[tuple[int, int]]) -> dict:
    n = len(pairs)
    if n < 2:
        return {"n": n, "phi": None}
    a = sum(1 for x, y in pairs if x == 1 and y == 1)
    b = sum(1 for x, y in pairs if x == 1 and y == 0)
    c = sum(1 for x, y in pairs if x == 0 and y == 1)
    d = sum(1 for x, y in pairs if x == 0 and y == 0)
    denom = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    ph = ((a * d - b * c) / denom) if denom else None
    p1 = (a + b) / n
    p2 = (a + c) / n
    joint = a / n
    indep = p1 * p2
    return {"n": n, "phi": round(ph, 4) if ph is not None else None,
            "pA": round(p1, 4), "pB": round(p2, 4),
            "jointObserved": round(joint, 4), "jointIfIndependent": round(indep, 4),
            "jointDifference": round(joint - indep, 4),
            "relativeError": round((joint - indep) / indep, 4) if indep else None,
            "cells": {"both": a, "aOnly": b, "bOnly": c, "neither": d}}


def phi_ci(pairs, key_blocks=None, draws=DRAWS) -> dict:
    """Bootstrap CI resampling whole weeks (games within a week share conditions)."""
    if len(pairs) < 100:
        return {"low": None, "high": None, "note": "n<100: interval not estimated"}
    blocks = defaultdict(list)
    if key_blocks:
        for p, k in zip(pairs, key_blocks):
            blocks[k].append(p)
    else:  # no block key supplied: resample individual observations and say so
        for i, p in enumerate(pairs):
            blocks[i].append(p)
    keys = list(blocks)
    note = "week-block bootstrap" if key_blocks else "observation bootstrap (no week key available)"
    rnd = random.Random(SEED)
    vals = []
    for _ in range(draws):
        sample = []
        for _k in keys:
            sample.extend(blocks[rnd.choice(keys)])
        r = phi(sample)["phi"]
        if r is not None:
            vals.append(r)
    if not vals:
        return {"low": None, "high": None, "note": "bootstrap produced no valid draws"}
    vals.sort()
    return {"low": round(vals[int(0.025 * len(vals))], 4),
            "high": round(vals[int(0.975 * len(vals))], 4),
            "draws": draws, "note": note}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = list(csv.DictReader((DATA / "games.csv").open(encoding="utf-8")))
    for g in games:
        g["season"] = int(g["season"])
        g["week"] = int(g["week"])
        g["played"] = bool(g["home_score"])

    # ---------------------------------------------------------------- 1. same-game markets
    pairs_spread_total, keys_st = [], []
    pairs_ml_total, keys_mt = [], []
    pairs_fav_under = []
    for g in games:
        if not g["played"] or not g["spread_line"] or not g["total_line"]:
            continue
        hs, as_ = int(g["home_score"]), int(g["away_score"])
        spread = float(g["spread_line"]); total = float(g["total_line"])
        margin = hs - as_ - spread
        tot = hs + as_ - total
        if margin == 0 or tot == 0:
            continue
        home_covered = 1 if margin > 0 else 0
        over = 1 if tot > 0 else 0
        pairs_spread_total.append((home_covered, over))
        keys_st.append((g["season"], g["week"]))
        if g["home_moneyline"]:
            pairs_ml_total.append((1 if hs > as_ else 0, over))
            keys_mt.append((g["season"], g["week"]))
        if spread != 0:
            fav_home = spread > 0
            fav_cover = home_covered if fav_home else 1 - home_covered
            pairs_fav_under.append((fav_cover, 1 - over))

    same_game = {
        "spreadTotal": {"label": "home covers the spread  vs  total goes over",
                        **phi(pairs_spread_total), "ci": phi_ci(pairs_spread_total, keys_st)},
        "moneylineTotal": {"label": "home wins outright  vs  total goes over",
                           **phi(pairs_ml_total), "ci": phi_ci(pairs_ml_total, keys_mt)},
        "favouriteUnder": {"label": "favourite covers  vs  total stays under",
                           **phi(pairs_fav_under), "ci": phi_ci(pairs_fav_under)},
        "interpretation": "phi is the Pearson correlation of two 0/1 outcomes. jointDifference is the absolute "
                          "error (in probability) of pricing the pair by multiplying the two marginals.",
    }

    # ---------------------------------------------------------------- 2/3. player dependence
    stats = list(csv.DictReader((DATA / "stats_player_week_2025.csv").open(encoding="utf-8")))
    for r in stats:
        r["week"] = int(r["week"])
        for k in ("receiving_yards", "rushing_yards", "passing_yards", "receptions", "targets",
                  "receiving_tds", "rushing_tds", "passing_tds", "fantasy_points_ppr"):
            try:
                r[k] = float(r[k]) if r[k] not in ("", None) else None
            except ValueError:
                r[k] = None
    by_player = defaultdict(list)
    for r in stats:
        by_player[(r["player_id"], r["team"], r["position"])].append(r)
    for k in by_player:
        by_player[k].sort(key=lambda r: r["week"])

    def trailing(pid_team_pos, week, field, n=4, min_games=2):
        rows = [r for r in by_player[pid_team_pos] if r["week"] < week][-n:]
        vals = [r[field] for r in rows if r[field] is not None]
        if len(vals) < min_games:
            return None
        return sum(vals) / len(vals)

    # Build per-game, per-team leaderboards of trailing production to pick the "top" players.
    # The tier is OUR trailing-production rank, not an official depth chart (stated on the site).
    team_week_top = defaultdict(list)   # (season week team) -> [(trailing fp, player key, position)]
    for (pid, team, pos), rows in by_player.items():
        for r in rows:
            t = trailing((pid, team, pos), r["week"], "fantasy_points_ppr")
            if t is not None:
                team_week_top[(r["season"], r["week"], team)].append((t, (pid, team, pos), pos))
    for k in team_week_top:
        team_week_top[k].sort(reverse=True)

    def over_proxy(player_key, week, field):
        t = trailing(player_key, week, field)
        if t is None:
            return None, None
        rows = [r for r in by_player[player_key] if r["week"] == week]
        if not rows:
            return None, None
        actual = rows[0][field]
        if actual is None:
            return None, None
        return (1 if actual > t else 0), t

    def pair_rate(cond_field_a, pos_a, cond_field_b, pos_b, same_team, max_rank=2, limit_pos_a=None):
        pairs, keys = [], []
        for (season, week, team), ranked in team_week_top.items():
            a_candidates = [x for x in ranked if x[2] in pos_a][:max_rank]
            if not a_candidates:
                continue
            for _, akey, _ in a_candidates[:1]:
                oa, _t = over_proxy(akey, week, cond_field_a)
                if oa is None:
                    continue
                if same_team:
                    b_candidates = [x for x in ranked if x[2] in pos_b and x[1] != akey][:max_rank]
                else:
                    opp = None
                    b_candidates = []
                    for (s2, w2, t2), r2 in team_week_top.items():
                        if s2 == season and w2 == week and t2 != team:
                            b_candidates = [x for x in r2 if x[2] in pos_b][:max_rank]
                            opp = t2
                            break
                    if opp is None:
                        continue
                if not b_candidates:
                    continue
                _, bkey, _ = b_candidates[0]
                ob, _t2 = over_proxy(bkey, week, cond_field_b)
                if ob is None:
                    continue
                pairs.append((oa, ob)); keys.append((season, week))
        if not pairs:
            return {"n": 0}
        return {**phi(pairs), "ci": phi_ci(pairs, keys)}

    player_pairs = {
        "qbPassYds_wr1RecYds_sameTeam": {
            "label": "QB passing yards over his trailing average  vs  his WR1 receiving yards over his",
            "assumedPricing": "positive dependence",
            **pair_rate("passing_yards", {"QB"}, "receiving_yards", {"WR"}, True)},
        "rb1RushYds_rb2RushYds_sameTeam": {
            "label": "RB1 rushing yards over  vs  RB2 rushing yards over (same club)",
            "assumedPricing": "negative dependence (shared carries)",
            **pair_rate("rushing_yards", {"RB"}, "rushing_yards", {"RB"}, True)},
        "wr1RecYds_wr2RecYds_sameTeam": {
            "label": "WR1 receiving yards over  vs  WR2 receiving yards over (same club)",
            "assumedPricing": "negative dependence (shared targets)",
            **pair_rate("receiving_yards", {"WR"}, "receiving_yards", {"WR"}, True)},
        "qbPassYds_oppWr1RecYds": {
            "label": "QB passing yards over  vs  opposing WR1 receiving yards over",
            "assumedPricing": "positive dependence (game script / pace)",
            **pair_rate("passing_yards", {"QB"}, "receiving_yards", {"WR"}, False)},
        "rb1RushYds_qbPassYds_sameTeam": {
            "label": "RB1 rushing yards over  vs  own QB passing yards over",
            "assumedPricing": "negative dependence (run-heavy vs pass-heavy script)",
            **pair_rate("rushing_yards", {"RB"}, "passing_yards", {"QB"}, True)},
    }

    # ---------------------------------------------------------------- 4. parlay dependence
    # For every tested week take the two / three largest Elo edges and compare the observed
    # joint hit rate with the product of the leg hit rates.
    engine = json.loads((DATA / "backtest" / "strategies" / "s7-elo-two-leg-parlay.json").read_text())
    two = engine["bets"]
    joint_two = sum(b["won"] for b in two)
    indep_two = 0.0
    for b in two:
        p = 1.0
        for leg in b["legs"]:
            p *= leg["modelProb"]
        indep_two += p
    engine3 = json.loads((DATA / "backtest" / "strategies" / "s8-elo-three-leg-parlay.json").read_text())
    three = engine3["bets"]
    joint_three = sum(b["won"] for b in three)
    n2, n3 = len(two), len(three)
    parlay_dependence = {
        "twoLeg": {"n": n2, "observedJointHitRate": round(joint_two / n2, 4) if n2 else None,
                   "meanModelJointProbability": round(indep_two / n2, 4) if n2 else None,
                   "note": "Legs are in different games, so the dependence is only through shared week-level "
                           "information and market structure. Compare observed vs modelled joint rate."},
        "threeLeg": {"n": n3, "observedJointHitRate": round(joint_three / n3, 4) if n3 else None,
                     "note": "No model joint probability is published for three legs because the legs were "
                             "selected by edge size, which biases any independence calculation."},
        "correlationLesson": "A parlay priced by multiplying marginals is only correct when phi = 0. Where phi "
                             "is materially non-zero the fair price moves, and the direction is given by the sign "
                             "of phi: positive dependence makes the product price too generous to the bettor; "
                             "negative dependence makes it too generous to the book.",
    }

    payload = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "sameGame": same_game,
        "playerPairs": player_pairs,
        "parlayDependence": parlay_dependence,
        "propLineMethod": "PROXY: each player's trailing 4-game average, computed strictly from weeks before the "
                          "game in question. This is not a sportsbook line and cannot be used to price a real "
                          "prop. It is the only joint player outcome data this lab can construct without a "
                          "prop-price archive.",
        "officialStatus": "Correlations are model-measured from public record-level data. No official NFL source "
                          "publishes correlations or prices; these are NOT official values.",
        "sources": [
            {"id": "nfldata-games", "what": "results and closing spread/total"},
            {"id": "mirror-stats-player-week-2025", "what": "player-week 2025 mirror"},
        ],
    }
    (OUT / "correlations.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    parlay_dependence["generatedUTC"] = payload["generatedUTC"]
    (OUT / "parlay-dependence.json").write_text(json.dumps(parlay_dependence, indent=1) + "\n", encoding="utf-8")

    print("same-game:")
    for k, v in same_game.items():
        if isinstance(v, dict) and "phi" in v:
            print(f"  {k:22s} n={v.get('n')} phi={v.get('phi')} joint={v.get('jointObserved')} "
                  f"indep={v.get('jointIfIndependent')} ci={v.get('ci')}")
    print("player pairs:")
    for k, v in player_pairs.items():
        print(f"  {k:36s} n={v.get('n')} phi={v.get('phi')} joint={v.get('jointObserved')} "
              f"indep={v.get('jointIfIndependent')}")


if __name__ == "__main__":
    main()
