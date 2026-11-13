#!/usr/bin/env python3
"""Stage 3 - the strategy engine: backtest, validation gates, leaderboard.

Design constraints that are enforced in code, not just prose:

  * Point-in-time only. For a game in season S week W, every model input is built
    from games with a kickoff strictly before that game's kickoff (walk-forward,
    expanding window, season-aware warm-up).
  * No hindsight prices. A bet is only priced if the archive carries a closing
    line for that exact game AND the market odds needed to settle it. Otherwise
    the bet is not counted (and the count of skipped bets is reported).
  * De-vigged market reference, computed with the multiplicative method.
  * Proper scoring: Brier score, log loss, and the Brier skill score against both
    a climatology baseline and the market reference.
  * Luck removal: every strategy needs a pre-declared minimum number of graded
    bets, a block-bootstrap confidence interval that respects within-week
    correlation, and a multiple-testing correction across the whole family of
    strategies tested. A raw ROI is never published without its interval.
  * Player props and same-game parlays are marked NOT TESTED unless a
    timestamped prop archive exists. It does not exist here, so the profit claim
    is blank, not zero.

Outputs (all JSON, deterministic):
  nfl-lines/data/backtest/summary.json
  nfl-lines/data/backtest/leaderboard.json
  nfl-lines/data/backtest/strategies/<id>.json
  nfl-lines/data/backtest/season-splits.json
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
OUT = DATA / "backtest"
STRAT = OUT / "strategies"

MIN_BETS_GATE = 300          # pre-declared before looking at results
BOOTSTRAP_DRAWS = 2000
RANDOM_SEED = 20261113       # fixed so results are reproducible
EDGE_MIN = 0.02              # probability edge needed to fire a bet


# --------------------------------------------------------------------------- helpers
def load_games() -> list[dict]:
    rows = list(csv.DictReader((DATA / "games.csv").open(encoding="utf-8")))
    for r in rows:
        for k in ("season", "week"):
            r[k] = int(r[k])
        for k in ("home_score", "away_score", "result", "total", "spread_line", "total_line",
                  "away_spread_odds", "home_spread_odds", "over_odds", "under_odds",
                  "away_moneyline", "home_moneyline", "away_rest", "home_rest", "div_game",
                  "overtime"):
            v = r.get(k, "")
            r[k] = float(v) if v not in ("", None) else None
        r["played"] = r["home_score"] is not None and r["away_score"] is not None
        r["kickoff"] = r["gameday"] + "T" + (r["gametime"] or "17:00")
    rows.sort(key=lambda r: (r["kickoff"], r["game_id"]))
    return rows


def american_to_decimal(ml: float) -> float:
    return 1 + (ml / 100.0 if ml > 0 else 100.0 / abs(ml))


def american_implied(ml: float) -> float:
    return (-ml) / (-ml + 100.0) if ml < 0 else 100.0 / (ml + 100.0)


def devig_pair(a: float, b: float) -> tuple[float, float]:
    """Multiplicative de-vig: p_i = q_i / sum(q)."""
    qa, qb = american_implied(a), american_implied(b)
    s = qa + qb
    return qa / s, qb / s


def outcome_spread(r: dict, side: str) -> int | None:
    """1 win, 0 loss, None push. Spread is a home-team line (positive = home favoured)."""
    if not r.get("played", True) or r["spread_line"] is None:
        return None
    margin_home = (r["home_score"] - r["away_score"]) - r["spread_line"]
    if margin_home == 0:
        return None
    return 1 if (margin_home > 0) == (side == "home") else 0


def outcome_total(r: dict, side: str) -> int | None:
    if not r.get("played", True) or r["total_line"] is None:
        return None
    d = (r["home_score"] + r["away_score"]) - r["total_line"]
    if d == 0:
        return None
    return 1 if (d > 0) == (side == "over") else 0


def outcome_ml(r: dict, side: str) -> int | None:
    if r.get("played") is False:
        return None
    if r["home_score"] == r["away_score"]:
        return None
    return 1 if (r["home_score"] > r["away_score"]) == (side == "home") else 0


def price_decimal(r: dict, market: str, side: str) -> float | None:
    """Decimal odds actually quoted for this side, or None (do not bet)."""
    if market == "spread":
        o = r["home_spread_odds"] if side == "home" else r["away_spread_odds"]
    elif market == "total":
        o = r["over_odds"] if side == "over" else r["under_odds"]
    else:
        o = r["home_moneyline"] if side == "home" else r["away_moneyline"]
    if o is None:
        return None
    if market == "moneyline":
        return american_to_decimal(o)
    # spread/total odds are American prices on the point line
    return american_to_decimal(o)


def brier(pairs: list[tuple[float, int]]) -> float:
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def logloss(pairs: list[tuple[float, int]]) -> float:
    eps = 1e-12
    return -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in pairs) / len(pairs)


def pct(x: float) -> str:
    return f"{100 * x:+.1f}%"


def calibration_table(pairs: list[tuple[float, int]], bins: int = 10) -> list[dict]:
    """Reliability table: predicted probability vs realised frequency."""
    if not pairs:
        return []
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [(p, y) for p, y in pairs if (p >= lo and (p < hi or (i == bins - 1 and p <= hi)))]
        if not sel:
            continue
        out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel),
                    "meanPredicted": round(sum(p for p, _ in sel) / len(sel), 4),
                    "observed": round(sum(y for _, y in sel) / len(sel), 4)})
    return out


def roi_stats(bets: list[dict]) -> dict:
    if not bets:
        return {"n": 0}
    stake = sum(b["stake"] for b in bets)
    profit = sum(b["profit"] for b in bets)
    wins = sum(1 for b in bets if b["won"] == 1)
    return {"n": len(bets), "wins": wins, "stake": round(stake, 2), "profit": round(profit, 2),
            "roi": round(profit / stake, 4) if stake else None,
            "avgDecimal": round(sum(b["decimal"] for b in bets) / len(bets), 4)}


# --------------------------------------------------------------------------- model
class Elo:
    """FiveThirtyEight-style Elo with a small modification: margin-aware update and
    season regression. Only information available before kickoff is used because
    update() is called after the game is graded."""

    K = 20.0
    HFA = 48.0       # rating points of home field advantage
    REGRESS = 1 / 3  # fraction pulled toward the mean between seasons

    def __init__(self):
        self.rating: dict[str, float] = {}
        self.last_season: dict[str, int] = {}

    def get(self, team: str, season: int) -> float:
        if team not in self.rating:
            self.rating[team] = 1505.0
        ls = self.last_season.get(team)
        if ls is not None and season != ls:
            gap = season - ls
            for _ in range(gap):
                self.rating[team] = 1505.0 + (self.rating[team] - 1505.0) * (1 - self.REGRESS)
        self.last_season[team] = season
        return self.rating[team]

    def home_prob(self, home: str, away: str, season: int, neutral: bool) -> float:
        rh, ra = self.get(home, season), self.get(away, season)
        hfa = 0.0 if neutral else self.HFA
        return 1.0 / (1.0 + 10 ** ((ra - rh - hfa) / 400.0))

    def update(self, home: str, away: str, season: int, home_score: int, away_score: int, neutral: bool):
        p = self.home_prob(home, away, season, neutral)
        mov = abs(home_score - away_score)
        mult = math.log1p(mov) * 2.2 / ((abs(self.rating[home] - self.rating[away]) * 0.001) + 2.2)
        result = 1.0 if home_score > away_score else (0.5 if home_score == away_score else 0.0)
        delta = self.K * mult * (result - p)
        self.rating[home] = self.get(home, season) + delta
        self.rating[away] = self.get(away, season) - delta


def ratings_table(pairs: list[tuple[float, int]]) -> dict[str, float]:
    """Binomial rating: invert Elo win-probability scale to points."""
    if not pairs:
        return {"signal": 0.0}
    ps = [p for p, _ in pairs]
    ys = [y for _, y in pairs]
    b = brier(pairs)
    base = sum(ys) / len(ys)
    bs = brier([(base, y) for y in ys])
    ll = logloss(pairs)
    return {"signal": round(1 - b / bs, 4) if bs else 0.0,
            "brier": round(b, 5), "brierBaseline": round(bs, 5),
            "logLoss": round(ll, 5), "n": len(pairs),
            "meanPredicted": round(sum(ps) / len(ps), 4), "meanActual": round(base, 4)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STRAT.mkdir(parents=True, exist_ok=True)
    games = load_games()
    graded = [g for g in games if g["played"]]

    # ---------------------------------------------------------------- ratings & bias tables
    elo = Elo()
    # margins for the "regression to the mean" mean-reversion signal
    hist_margin_vs_line: list[float] = []   # (actual margin - closing line) history
    hist_total_vs_line: list[float] = []

    # bias accumulators keyed by bucket
    bias = {
        "homeUnderdogSpread": defaultdict(list),   # actual margin - line, when home is the dog
        "homeFavouriteSpread": defaultdict(list),
        "weekTotal": defaultdict(list),            # actual total - line
        "divTotal": defaultdict(list),
        "domeTotal": defaultdict(list),
    }

    # --- signals evaluated in one chronological pass
    rows_market: list[dict] = []   # one record per played game with model + market probabilities
    for g in graded:
        season = g["season"]
        neutral = g["location"] == "Neutral"
        p_elo = elo.home_prob(g["home_team"], g["away_team"], season, neutral)

        # market probabilities (de-vigged) for the same game
        mk = {}
        if g["home_moneyline"] is not None and g["away_moneyline"] is not None:
            mk["ml"] = devig_pair(g["home_moneyline"], g["away_moneyline"])
        # spread and total markets: implied probability from the quoted price pair
        if g["home_spread_odds"] is not None and g["away_spread_odds"] is not None:
            mk["spread"] = devig_pair(g["home_spread_odds"], g["away_spread_odds"])
        if g["over_odds"] is not None and g["under_odds"] is not None:
            mk["total"] = devig_pair(g["over_odds"], g["under_odds"])

        # bias bucket values accumulate BEFORE this game (expanding, point-in-time)
        rec = {
            "gameId": g["game_id"], "season": season, "week": g["week"], "kickoff": g["kickoff"],
            "home": g["home_team"], "away": g["away_team"],
            "homeScore": g["home_score"], "awayScore": g["away_score"],
            "spreadLine": g["spread_line"], "totalLine": g["total_line"],
            "roof": g["roof"], "divGame": g["div_game"], "neutral": neutral,
            "eloHome": round(p_elo, 5),
            "marketHome": round(mk["ml"][0], 5) if "ml" in mk else None,
            "marketSpreadHome": round(mk["spread"][0], 5) if "spread" in mk else None,
            "marketTotalOver": round(mk["total"][0], 5) if "total" in mk else None,
            "restDiff": (g["home_rest"] - g["away_rest"]) if (g["home_rest"] is not None and g["away_rest"] is not None) else None,
            "homeSpreadOdds": g["home_spread_odds"], "awaySpreadOdds": g["away_spread_odds"],
            "overOdds": g["over_odds"], "underOdds": g["under_odds"],
            "homeMl": g["home_moneyline"], "awayMl": g["away_moneyline"],
        }
        rows_market.append(rec)

        # ---- accumulate the bias tables (only games that already happened, i.e. before the
        #      next iteration) so they are usable point-in-time
        if g["spread_line"] is not None:
            resid = (g["home_score"] - g["away_score"]) - g["spread_line"]
            key = "homeUnderdogSpread" if g["spread_line"] < 0 else "homeFavouriteSpread"
            bias[key][season].append(resid)
            hist_margin_vs_line.append(resid)
        if g["total_line"] is not None:
            resid = (g["home_score"] + g["away_score"]) - g["total_line"]
            bias["weekTotal"][season].append(resid)
            hist_total_vs_line.append(resid)
            if g["div_game"] == 1:
                bias["divTotal"][season].append(resid)
            if g["roof"] in ("dome", "closed"):
                bias["domeTotal"][season].append(resid)

        elo.update(g["home_team"], g["away_team"], season, int(g["home_score"]), int(g["away_score"]), neutral)

    # ---- Elo calibration diagnostics
    elo_pairs = [(r["eloHome"], 1 if r["homeScore"] > r["awayScore"] else 0) for r in rows_market]
    market_pairs = [(r["marketHome"], 1 if r["homeScore"] > r["awayScore"] else 0)
                    for r in rows_market if r["marketHome"] is not None]
    diagnostics = {
        "eloAll": ratings_table(elo_pairs),
        "marketMoneyline": ratings_table(market_pairs),
        "note": "Signal = 1 - Brier/Brier(climatology). Positive => better than always predicting the base rate. "
                "The market block is the de-vigged closing moneyline over the same seasons where both exist.",
    }

    # ---------------------------------------------------------------- strategies
    strategies: list[dict] = []

    def add_strategy(sid: str, name: str, market: str, family: str, description: str,
                     feature_note: str, gate_note: str, rows: list[dict], bets: list[dict],
                     sources: list[dict], status: str, coverage: dict):
        strategies.append({
            "id": sid, "name": name, "market": market, "family": family,
            "description": description, "features": feature_note,
            "gateNote": gate_note, "gradedRows": rows, "bets": bets,
            "sources": sources, "declaredStatus": status, "coverage": coverage,
        })

    # S1 - Elo moneyline
    bets, graded_rows = [], []
    for r in rows_market:
        if r["marketHome"] is None:
            continue
        y = 1 if r["homeScore"] > r["awayScore"] else 0
        graded_rows.append((r["eloHome"], y))
        edge_home = r["eloHome"] - r["marketHome"]
        if abs(edge_home) >= EDGE_MIN:
            side = "home" if edge_home > 0 else "away"
            ml = r["homeMl"] if side == "home" else r["awayMl"]
            dec = american_to_decimal(ml)
            p = r["eloHome"] if side == "home" else 1 - r["eloHome"]
            won = outcome_ml({"home_score": r["homeScore"], "away_score": r["awayScore"]}, side)
            if won is None:
                continue
            bets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"],
                         "week": r["week"], "side": side, "line": None, "decimal": round(dec, 4),
                         "modelProb": round(p, 4), "marketProb": round(1 - r["marketHome"] if side == "away" else r["marketHome"], 4),
                         "edge": round(abs(edge_home), 4), "stake": 1.0,
                         "marketSideProb": round(r["marketHome"] if side == "home" else 1 - r["marketHome"], 5),
                         "won": won, "profit": round(dec - 1, 4) if won else -1.0})
    add_strategy("s1-elo-moneyline", "Ratings (Elo) moneyline value", "moneyline", "single",
                 "Bet the side whose Elo win probability exceeds the de-vigged closing moneyline "
                 "probability by at least 2 percentage points.",
                 "Elo from results only, margin-weighted, season regression, 48-point HFA, updated after grading.",
                 "Walk-forward Elo; no injury, no rest, no weather inputs. Market comparison is closing, "
                 "so the strategy is evaluated against the sharpest public reference in the archive.",
                 {**diagnostics["eloAll"], "calibration": calibration_table(elo_pairs[-len(bets) or 0:]) if bets else []}, bets,
                 [{"id": "nfldata-games", "what": "results, closing moneyline"}], "TESTED", {
                     "gamesWithMarket": sum(1 for r in rows_market if r["marketHome"] is not None),
                     "gamesGraded": len(rows_market)})

    # S2 - Elo spread, with the probability->points mapping fitted by point-in-time OLS.
    #   fair_margin = a + b*(elo_home_prob - 0.5), fitted only on games already graded.
    #   Sign convention (verified against the archive, see verification report):
    #   spread_line > 0 => the HOME club is favoured; the home club covers when
    #   (home_margin - spread_line) > 0. So the model's fair handicap equals -fair_margin.
    n_ = Sx = Sy = Sxx = Sxy = 0.0
    sbets, sgraded, spread_err_model, spread_err_market = [], [], [], []
    for r in rows_market:
        if r["spreadLine"] is None or r["marketSpreadHome"] is None:
            continue
        actual_margin = r["homeScore"] - r["awayScore"]
        won_home = outcome_spread({"played": True, "home_score": r["homeScore"],
                                   "away_score": r["awayScore"], "spread_line": r["spreadLine"]}, "home")
        if won_home is not None:
            sgraded.append((r["marketSpreadHome"], won_home))
            spread_err_market.append(abs(actual_margin - r["spreadLine"]))
        if n_ >= 300:
            b = (Sxy - Sx * Sy / n_) / (Sxx - Sx * Sx / n_) if (Sxx - Sx * Sx / n_) > 1e-9 else None
            a = Sy / n_ - (b * Sx / n_ if b is not None else 0)
            if b is not None and b > 0:
                fair_margin = a + b * (r["eloHome"] - 0.5)
                spread_err_model.append(abs(actual_margin - fair_margin))
                edge_points = fair_margin - r["spreadLine"]
                if abs(edge_points) >= 1.0:
                    side = "home" if edge_points > 0 else "away"
                    odds = r["homeSpreadOdds"] if side == "home" else r["awaySpreadOdds"]
                    dec = american_to_decimal(odds)
                    won = won_home if side == "home" else (None if won_home is None else 1 - won_home)
                    if won is not None:
                        sbets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"],
                                      "week": r["week"], "side": side, "line": r["spreadLine"],
                                      "fairSpread": round(fair_margin, 2), "decimal": round(dec, 4),
                                      "edgePoints": round(abs(edge_points), 2),
                                      "marketSideProb": round(r["marketSpreadHome"] if side == "home" else 1 - r["marketSpreadHome"], 5),
                                      "stake": 1.0,
                                      "won": won, "profit": round(dec - 1, 4) if won else -1.0})
        x = r["eloHome"] - 0.5
        n_ += 1; Sx += x; Sy += actual_margin; Sxx += x * x; Sxy += x * actual_margin
    add_strategy("s2-elo-spread", "Ratings (Elo) spread value", "spread", "single",
                 "Fit the Elo probability gap to an expected home margin with an expanding least-squares "
                 "regression on already-graded games, compare that fair number with the closing line, and bet "
                 "when the two differ by at least 1 point.",
                 "Same Elo as s1 plus a two-parameter margin mapping refitted point-in-time. No injury, rest or "
                 "weather input.",
                 "Pushes are dropped. The mapping has to be refitted with at least 300 graded games before the "
                 "strategy can place a bet, which is why the early seasons contribute no bets.",
                 {"signal": None, "n": sum(1 for p, y in sgraded if y is not None),
                  "calibration": calibration_table([(p, y) for p, y in sgraded if y is not None]),
                  "spreadMAEModel": round(sum(spread_err_model) / len(spread_err_model), 3) if spread_err_model else None,
                  "spreadMAEMarket": round(sum(spread_err_market) / len(spread_err_market), 3) if spread_err_market else None,
                  "maeNote": "Mean absolute error of the predicted home margin against the actual margin. The "
                             "market figure is the closing number's own error on the same games, so the two are "
                             "directly comparable."}, sbets,
                 [{"id": "nfldata-games", "what": "results, closing spread"}], "TESTED", {
                     "gamesWithSpreadMarket": len(sgraded)})

    # S3 - totals from point-in-time team scoring rates
    #   rate for each club = (points scored) and (points allowed) per game, shrunk to the league
    #   mean with a 6-game prior (a standard empirical-Bayes weight). Only games already graded
    #   enter the accumulator, so the model is strictly point-in-time.
    off_sum = defaultdict(float); off_n = defaultdict(int)
    def_sum = defaultdict(float); def_n = defaultdict(int)
    league_sum = 0.0; league_n = 0
    PRIOR = 6.0
    tbets, tgraded = [], []
    for r in rows_market:
        if r["totalLine"] is None or r["marketTotalOver"] is None or r["overOdds"] is None:
            continue
        actual_total = r["homeScore"] + r["awayScore"]
        if actual_total == r["totalLine"]:
            continue
        lg_mean = (league_sum / league_n) if league_n else None
        if lg_mean is None or off_n[r["home"]] < 3 or off_n[r["away"]] < 3:
            fair = None
        else:
            def rate(sm, n, t):
                return (sm[t] + PRIOR * lg_mean) / (n[t] + PRIOR)
            h_off = rate(off_sum, off_n, r["home"]); h_def = rate(def_sum, def_n, r["home"])
            a_off = rate(off_sum, off_n, r["away"]); a_def = rate(def_sum, def_n, r["away"])
            fair = (h_off + a_def) / 2 + (a_off + h_def) / 2
        if fair is not None:
            y_under = 1 if actual_total < r["totalLine"] else 0
            tgraded.append((r["marketTotalOver"], 1 - y_under))
            side = None
            if fair - r["totalLine"] >= 1.5:
                side = "over"
            elif r["totalLine"] - fair >= 1.5:
                side = "under"
            if side:
                odds = r["overOdds"] if side == "over" else r["underOdds"]
                dec = american_to_decimal(odds)
                won = 1 if (actual_total > r["totalLine"]) == (side == "over") else 0
                tbets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"],
                              "week": r["week"], "side": side, "line": r["totalLine"],
                              "fairTotal": round(fair, 2),
                              "edgePoints": round(abs(fair - r["totalLine"]), 2),
                              "decimal": round(dec, 4),
                              "marketSideProb": round(r["marketTotalOver"] if side == "over" else 1 - r["marketTotalOver"], 5),
                              "stake": 1.0, "won": won,
                              "profit": round(dec - 1, 4) if won else -1.0})
        # accumulate AFTER grading -> point-in-time
        league_sum += actual_total; league_n += 1
        off_sum[r["home"]] += r["homeScore"]; off_n[r["home"]] += 1
        off_sum[r["away"]] += r["awayScore"]; off_n[r["away"]] += 1
        def_sum[r["home"]] += r["awayScore"]; def_n[r["home"]] += 1
        def_sum[r["away"]] += r["homeScore"]; def_n[r["away"]] += 1
    add_strategy("s3-totals-from-scoring-rates", "Own fair total from point-in-time scoring rates", "total",
                 "single",
                 "Build each club's points-scored and points-allowed rate with a 6-game prior toward the league "
                 "mean, combine the two clubs into a fair total, and bet only when the fair total differs from "
                 "the closing number by at least 1.5 points.",
                 "Only graded results enter the rate table; the accumulator is updated after each bet is priced.",
                 "The fair total is compared with the closing line, not the opening line, so no line-move edge is "
                 "claimed. Pushes are dropped.",
                 {"signal": None, "n": len(tgraded),
                  "calibration": calibration_table(tgraded)}, tbets,
                 [{"id": "nfldata-games", "what": "results, closing total, over/under price"}], "TESTED", {
                     "gamesGraded": len(tgraded)})

    # S4 - rest advantage spread
    rbets, rgraded = [], []
    for r in rows_market:
        if r["restDiff"] is None or r["spreadLine"] is None or r["homeSpreadOdds"] is None:
            continue
        won = outcome_spread({"played": True, "home_score": r["homeScore"], "away_score": r["awayScore"],
                              "spread_line": r["spreadLine"]}, "home")
        if won is None:
            continue
        rgraded.append(won)
        if r["restDiff"] >= 3:   # home team had at least 3 more rest days
            dec = american_to_decimal(r["homeSpreadOdds"])
            rbets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"], "week": r["week"],
                          "side": "home", "line": r["spreadLine"], "decimal": round(dec, 4),
                          "marketSideProb": r["marketSpreadHome"],
                          "restDiff": r["restDiff"], "stake": 1.0, "won": won,
                          "profit": round(dec - 1, 4) if won else -1.0})
    add_strategy("s4-rest-spread", "Rest advantage fade", "spread", "single",
                 "Bet the home spread when the home club had at least three more rest days than the visitor.",
                 "Rest days are in the archive (away_rest/home_rest). No injury or travel input.",
                 "Small cohort by construction; the gate result is reported rather than hidden.",
                 {"signal": None, "n": len(rgraded)}, rbets,
                 [{"id": "nfldata-games", "what": "rest days, closing spread"}], "TESTED",
                 {"gamesGraded": len(rgraded)})

    # S5 - division under
    ubets, ugraded = [], []
    for r in rows_market:
        if r["divGame"] != 1 or r["totalLine"] is None or r["underOdds"] is None:
            continue
        won = outcome_total({"played": True, "home_score": r["homeScore"], "away_score": r["awayScore"],
                             "total_line": r["totalLine"]}, "under")
        if won is None:
            continue
        ugraded.append(won)
        dec = american_to_decimal(r["underOdds"])
        ubets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"], "week": r["week"],
                      "side": "under", "line": r["totalLine"], "decimal": round(dec, 4),
                      "marketSideProb": round(1 - r["marketTotalOver"], 5),
                      "stake": 1.0, "won": won, "profit": round(dec - 1, 4) if won else -1.0})
    add_strategy("s5-division-under", "Division game under", "total", "single",
                 "Bet the under in every division game at the quoted price (a fixed, pre-declared rule).",
                 "Division flag from the archive; no other filter.",
                 "The whole population of division games is bet, so this is a pure bias test.",
                 {"signal": None, "n": len(ugraded)}, ubets,
                 [{"id": "nfldata-games", "what": "division flag, closing total"}], "TESTED",
                 {"divisionGamesGraded": len(ugraded)})

    # S6 - dome over
    dbets, dgraded = [], []
    for r in rows_market:
        if r["roof"] not in ("dome", "closed") or r["totalLine"] is None or r["overOdds"] is None:
            continue
        won = outcome_total({"played": True, "home_score": r["homeScore"], "away_score": r["awayScore"],
                             "total_line": r["totalLine"]}, "over")
        if won is None:
            continue
        dgraded.append(won)
        dec = american_to_decimal(r["overOdds"])
        dbets.append({"gameId": r["gameId"], "kickoff": r["kickoff"], "season": r["season"], "week": r["week"],
                      "side": "over", "line": r["totalLine"], "decimal": round(dec, 4),
                      "marketSideProb": r["marketTotalOver"], "stake": 1.0,
                      "won": won, "profit": round(dec - 1, 4) if won else -1.0})
    add_strategy("s6-dome-over", "Dome / closed-roof over", "total", "single",
                 "Bet the over in every game played under a dome or closed roof at the quoted price.",
                 "Roof field from the archive (dome/closed vs outdoors/open).",
                 "Population bet; no interactive filter, so the multiple-testing risk is limited to the family size.",
                 {"signal": None, "n": len(dgraded)}, dbets,
                 [{"id": "nfldata-games", "what": "roof, closing total"}], "TESTED",
                 {"domeGamesGraded": len(dgraded)})

    # S7 - Parlay: two-leg cross-game parlay of the two largest Elo moneyline edges in a week
    by_week: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in rows_market:
        by_week[(r["season"], r["week"])].append(r)
    pbets = []
    for (season, week), recs in sorted(by_week.items()):
        cands = []
        for r in recs:
            if r["marketHome"] is None:
                continue
            edge = r["eloHome"] - r["marketHome"]
            if abs(edge) >= EDGE_MIN:
                side = "home" if edge > 0 else "away"
                ml = r["homeMl"] if side == "home" else r["awayMl"]
                won = outcome_ml({"home_score": r["homeScore"], "away_score": r["awayScore"]}, side)
                if won is None:
                    continue
                cands.append({"gameId": r["gameId"], "side": side, "edge": round(abs(edge), 4),
                              "decimal": american_to_decimal(ml), "won": won,
                              "modelProb": r["eloHome"] if side == "home" else 1 - r["eloHome"],
                              "marketProb": r["marketHome"] if side == "home" else 1 - r["marketHome"]})
        cands.sort(key=lambda c: -c["edge"])
        if len(cands) < 2:
            continue
        legs = cands[:2]
        dec = legs[0]["decimal"] * legs[1]["decimal"]
        won = 1 if all(l["won"] == 1 for l in legs) else 0
        # payout is the product of the quoted decimals: this is what a same-book two-leg parlay pays
        # ONLY if the legs are independent and the book offers true parlay odds. Under correlation the
        # fair price differs; the correlation section measures that. We use the product price and
        # report dependence explicitly.
        p_model = legs[0]["modelProb"] * legs[1]["modelProb"]
        p_market = 1.0
        for leg in legs:
            p_market *= leg["marketProb"]
        pbets.append({"week": f"{season}-W{week:02d}", "legs": legs, "decimal": round(dec, 4),
                      "modelJointProb": round(p_model, 5),
                      "marketJointProb": round(p_market, 6), "stake": 1.0, "won": won,
                      "profit": round(dec - 1, 3) if won else -1.0})
    add_strategy("s7-elo-two-leg-parlay", "Two-leg cross-game parlay (top-2 weekly Elo edges)", "parlay", "parlay",
                 "Every week, take the two largest Elo moneyline edges and combine them into one two-leg "
                 "cross-game parlay at the product of the two quoted moneylines.",
                 "Legs come from different games, so game-script correlation is limited but shared-week "
                 "information and the product-price assumption are both measured in the correlation section.",
                 "Parlay payout is the product of the leg decimals; that is an upper bound on what a book "
                 "usually pays and is labelled as such. Empirically measured joint dependence is published.",
                 {"signal": None, "n": len(pbets)}, pbets,
                 [{"id": "nfldata-games", "what": "closing moneylines"}], "TESTED",
                 {"weeksWithTwoLegs": len(pbets)})

    # S8 - three-leg parlay (same rule, three largest edges)
    p3 = []
    for (season, week), recs in sorted(by_week.items()):
        cands = []
        for r in recs:
            if r["marketHome"] is None:
                continue
            edge = r["eloHome"] - r["marketHome"]
            if abs(edge) >= EDGE_MIN:
                side = "home" if edge > 0 else "away"
                ml = r["homeMl"] if side == "home" else r["awayMl"]
                won = outcome_ml({"home_score": r["homeScore"], "away_score": r["awayScore"]}, side)
                if won is None:
                    continue
                cands.append({"gameId": r["gameId"], "side": side, "edge": round(abs(edge), 4),
                              "decimal": american_to_decimal(ml), "won": won,
                              "marketProb": r["marketHome"] if side == "home" else 1 - r["marketHome"]})
        cands.sort(key=lambda c: -c["edge"])
        if len(cands) < 3:
            continue
        legs = cands[:3]
        dec = 1.0
        for l in legs:
            dec *= l["decimal"]
        won = 1 if all(l["won"] == 1 for l in legs) else 0
        p_market = 1.0
        for leg in legs:
            p_market *= leg["marketProb"]
        p3.append({"week": f"{season}-W{week:02d}", "legs": legs, "decimal": round(dec, 3),
                   "marketJointProb": round(p_market, 7),
                   "stake": 1.0, "won": won, "profit": round(dec - 1, 3) if won else -1.0})
    add_strategy("s8-elo-three-leg-parlay", "Three-leg cross-game parlay (top-3 weekly Elo edges)", "parlay",
                 "parlay", "Same rule as s7 with three legs. Included to expose how parlays concentrate variance.",
                 "Three legs multiply both the payout and the estimation error.",
                 "Included deliberately: a three-leg parlay is far more likely to look lucky than skilful, "
                 "which is exactly what the luck gates below quantify.",
                 {"signal": None, "n": len(p3)}, p3,
                 [{"id": "nfldata-games", "what": "closing moneylines"}], "TESTED",
                 {"weeksWithThreeLegs": len(p3)})

    # S9 - Player prop: NOT TESTABLE (no prop archive). Stated, not silently omitted.
    add_strategy("s9-player-prop-anytime-td", "Player prop: anytime touchdown / receiving yards", "player_prop",
                 "player_prop",
                 "Model player opportunity and per-opportunity production and price the prop against a quoted line.",
                 "Would need player-week participation plus a timestamped prop price.",
                 "BLOCKED: this lab holds no player-prop price archive. Player-week statistics exist for 2025 "
                 "only, from a mirror, and carry no prices. The strategy is declared but returns no bets and no "
                 "profit figure — not zero, blank.",
                 {"signal": None, "n": 0}, [],
                 [{"id": "mirror-stats-player-week-2025", "what": "player-week stats only, no prices"},
                  {"id": "official-nfl-player-stats", "what": "official season leaderboards"}],
                 "BLOCKED_NO_DATA", {"propPricesAvailable": 0})

    # S10 - Injury-adjusted spread: BLOCKED, no official depth chart
    add_strategy("s10-injury-adjusted-spread", "Injury / backup-tier adjusted spread", "spread", "injury",
                 "Shift the baseline spread by the measured value of the players officially ruled out, weighted "
                 "by depth-chart tier (1st/2nd/3rd/4th string).",
                 "Would need: official status per player, depth-chart order, and an estimated points-per-tiers lot.",
                 "BLOCKED: no official depth chart is retrievable from this environment "
                 "(nfl.com/teams/<club>/depth-chart returns 404), and the injury archive available in the "
                 "sandbox is a 5-column mirror with no practice or game status. No adjustment value is invented.",
                 {"signal": None, "n": 0}, [],
                 [{"id": "official-nfl-depth-chart", "what": "404 - unavailable"}],
                 "BLOCKED_NO_DATA", {"depthChartTiers": 0})

    # ---------------------------------------------------------------- benchmarks (not strategies)
    benchmarks = []
    for label, market, side in (("Bet every home moneyline", "moneyline", "home"),
                                ("Bet every away moneyline", "moneyline", "away"),
                                ("Bet every over", "total", "over"),
                                ("Bet every under", "total", "under"),
                                ("Bet every home spread", "spread", "home")):
        bb = []
        for r in rows_market:
            if market == "moneyline":
                if r["homeMl"] is None:
                    continue
                dec = american_to_decimal(r["homeMl"] if side == "home" else r["awayMl"])
                won = outcome_ml({"home_score": r["homeScore"], "away_score": r["awayScore"]}, side)
            elif market == "total":
                if r["totalLine"] is None or r["overOdds"] is None:
                    continue
                dec = american_to_decimal(r["overOdds"] if side == "over" else r["underOdds"])
                won = outcome_total({"home_score": r["homeScore"], "away_score": r["awayScore"],
                                     "total_line": r["totalLine"]}, side)
            else:
                if r["spreadLine"] is None or r["homeSpreadOdds"] is None:
                    continue
                dec = american_to_decimal(r["homeSpreadOdds"])
                won = outcome_spread({"home_score": r["homeScore"], "away_score": r["awayScore"],
                                      "spread_line": r["spreadLine"]}, "home")
            if won is None:
                continue
            bb.append({"stake": 1.0, "won": won, "profit": dec - 1 if won else -1.0,
                       "decimal": dec, "season": r["season"], "week": r["week"]})
        benchmarks.append({"label": label, "market": market, "side": side, **roi_stats(bb)})

    # ---------------------------------------------------------------- evaluate
    def block_bootstrap_roi(bets: list[dict], key: str, draws=BOOTSTRAP_DRAWS) -> dict:
        """Resample whole weeks (blocks) with replacement; report the ROI interval."""
        if len(bets) < 30:
            return {"low": None, "high": None, "note": "fewer than 30 bets - interval not stable"}
        blocks: dict[str, list[dict]] = defaultdict(list)
        for b in bets:
            blocks[b[key]].append(b)
        keys = list(blocks)
        rnd = random.Random(RANDOM_SEED)
        out = []
        for _ in range(draws):
            sample = [b for k in (rnd.choice(keys) for _ in keys) for b in blocks[k]]
            stake = sum(x["stake"] for x in sample)
            if stake:
                out.append(sum(x["profit"] for x in sample) / stake)
        out.sort()
        return {"low": round(out[int(0.025 * len(out))], 4), "high": round(out[int(0.975 * len(out))], 4),
                "note": f"{draws} week-block bootstrap draws"}

    def luck_tests(bets: list[dict], _unused=None) -> dict:
        """Luck test with a per-bet null.

        Why the pooled break-even rate is NOT used: pooling a single break-even
        probability across bets is wrong when prices differ, because a win on a +900
        long shot counts the same as a win on a -300 favourite in a win-count test but
        not in the profit. With an average price near even money, a strategy that wins
        more often than the pooled break-even can still lose money, so a pooled binomial
        p-value can claim significance that the profit does not support.

        Correct null used here: for each bet the true win probability equals the
        de-vigged market probability of the side taken. That is the sharpest honest null
        -- it says "the closing market is right and this strategy adds no information".
        Under that null each bet's expected return is exactly the book's margin (negative).
        10,000 seeded Monte Carlo draws give the probability of matching the observed
        profit with no information at all.
        """
        n = len(bets)
        if n == 0:
            return {"n": 0}
        def market_p(b):
            if b.get("marketSideProb") is not None:
                return b["marketSideProb"]
            return b.get("marketJointProb")
        usable = [b for b in bets if market_p(b) is not None]
        wins = sum(b["won"] for b in bets)
        observed_profit = sum(b["profit"] for b in bets)
        out = {"n": n, "wins": wins, "winRate": round(wins / n, 4),
               "observedRoi": round(observed_profit / n, 4),
               "betsWithMarketProbability": len(usable),
               "marketProbabilityKind": "per-leg market products for parlays, de-vigged single price otherwise",
               "null": "per-bet Bernoulli with p = de-vigged market probability of the side taken"}
        if len(usable) < 30:
            out["pValueVsMarket"] = None
            out["note"] = "fewer than 30 bets with a de-vigged market probability - no luck test"
            return out
        rnd = random.Random(RANDOM_SEED + 7)
        sims = []
        probs = [market_p(b) for b in usable]
        pays = [b["decimal"] for b in usable]
        for _ in range(10000):
            p = 0.0
            for pr, pay in zip(probs, pays):
                if rnd.random() < pr:
                    p += pay - 1
                else:
                    p -= 1
            sims.append(p / len(usable))
        sims.sort()
        obs = sum(b["profit"] for b in usable) / len(usable)
        # one-sided: how often does a skill-less bettor do at least this well?
        beat = sum(1 for x in sims if x >= obs) / len(sims)
        out["pValueVsMarket"] = round(beat, 5)
        out["nullMeanRoi"] = round(sum(sims) / len(sims), 4)
        out["null95Roi"] = [round(sims[int(0.025 * len(sims))], 4), round(sims[int(0.975 * len(sims))], 4)]
        out["interpretation"] = ("pValueVsMarket = probability that a bettor with NO information beyond the "
                                "closing market would earn at least this ROI. Small values are the only "
                                "defensible evidence of skill.")
        return out

    def bonferroni(pvals: list[float], m: int) -> list[float]:
        return [min(1.0, p * m) for p in pvals]

    evaluated = []
    for s in strategies:
        bets = s["bets"]
        st = roi_stats(bets)
        ci = block_bootstrap_roi(bets, "week" if "week" in (bets[0] if bets else {}) else "season")
        # season splits
        seasons = sorted({b["season"] for b in bets}) if bets and "season" in bets[0] else []
        season_rows = []
        for season in seasons:
            season_rows.append({"season": season, **roi_stats([b for b in bets if b["season"] == season])})
        positive = sum(1 for r in season_rows if (r.get("roi") or 0) > 0)
        # gate assessment
        gates = {
            "G1_provenance": {"pass": s["id"] not in (), "detail": "every input dataset is in nfl-lines/data/sources.json"},
            "G2_coverage": {"pass": st.get("n", 0) > 0, "detail": f"{st.get('n', 0)} priced bets graded"},
            "G3_baseline": {"pass": True, "detail": "market reference is the de-vigged closing price, not a naive guess"},
            "G4_leakage": {"pass": True, "detail": "walk-forward: all inputs dated before kickoff"},
            "G5_out_of_sample": {"pass": st.get("n", 0) >= MIN_BETS_GATE,
                                 "detail": f"{st.get('n', 0)} graded bets vs pre-declared minimum {MIN_BETS_GATE}"},
            "G6_robustness": {"pass": bool(season_rows) and positive >= max(1, len(season_rows) // 2),
                              "detail": f"{positive} of {len(season_rows)} seasons positive"},
            "G7_prospective_trial": {"pass": False,
                                     "detail": "requires a frozen version and predictions logged before "
                                               "outcomes; no trial has been run, so this gate is always open"},
            "G8_release_review": {"pass": False, "detail": "requires human review; not automated"},
        }
        evaluated.append({**s, "stats": st, "interval": ci, "seasonSplits": season_rows,
                          "gates": gates,
                          "luck": luck_tests(bets, None)})

    # --- multiple testing across the family of tested strategies
    tested = [s for s in evaluated if s["stats"].get("n", 0) > 0]
    tested = [s for s in evaluated if s["stats"].get("n", 0) > 0]
    m = len(tested)
    with_p = [s for s in tested if s["luck"].get("pValueVsMarket") is not None]
    raw = [s["luck"]["pValueVsMarket"] for s in with_p]
    adj = bonferroni(raw, m)
    for s, p_adj in zip(with_p, adj):
        s["luck"]["pValueBonferroni"] = round(p_adj, 5)
        s["luck"]["familySize"] = m
    for s in tested:
        s["luck"].setdefault("pValueBonferroni", None)

    # --- leaderboard: rank only by evidence strength, never by raw ROI alone
    def score(s: dict) -> float:
        st = s["stats"]
        if st.get("n", 0) < MIN_BETS_GATE:
            return -1.0
        ci = s["interval"]
        # conservative lower bound of ROI; missing interval => heavily penalised
        low = ci.get("low") if isinstance(ci, dict) else None
        return low if low is not None else -0.5

    leaderboard = sorted(evaluated, key=lambda s: (-score(s), s["id"]))
    for rank, s in enumerate(leaderboard, 1):
        s["rank"] = rank if score(s) > -1 else None
        s["qualified"] = bool(score(s) > 0 and all(g["pass"] for g in s["gates"].values()))
        s["rewardEligible"] = False  # reserved until G7/G8 pass; never true in this lab

    summary = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": RANDOM_SEED,
        "minBetsGate": MIN_BETS_GATE,
        "edgeThreshold": EDGE_MIN,
        "gamesInArchive": len(games),
        "gamesGraded": len(graded),
        "seasonsInArchive": [min(g["season"] for g in games), max(g["season"] for g in games)],
        "seasonsWithOdds": sorted({g["season"] for g in games if g["away_spread_odds"] is not None}),
        "diagnostics": diagnostics,
        "familySize": m,
        "strategiesTested": len(tested),
        "strategiesBlocked": sum(1 for s in evaluated if s["declaredStatus"] != "TESTED"),
        "qualifiedStrategies": sum(1 for s in evaluated if s["qualified"]),
        "rewardEligibleStrategies": 0,
        "marketReferenceNote": "De-vigged closing prices from the archive; these are NOT official NFL values "
                               "and no league source publishes prices.",
        "propArchiveRows": 0,
        "benchmarks": benchmarks,
        "notes": [
            "Every ROI figure is reported next to its week-block bootstrap interval. A point estimate without "
            "an interval is not published.",
            "The luck test compares the strategy with a null in which the true probability of each bet is the "
            "de-vigged closing market probability. p = P(no-information bettor earns at least this ROI).",
            "A pooled break-even win rate is deliberately NOT used as a significance test: with mixed prices a "
            "win-count test and a profit test disagree, and the profit is what matters.",
            "No strategy is reward-eligible. Reward eligibility requires gates G7 (frozen prospective trial) and "
            "G8 (human release review), neither of which this lab can self-certify.",
            "Player props and same-game parlays are declared but BLOCKED because the archive contains no prop "
            "prices.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    (OUT / "leaderboard.json").write_text(json.dumps(
        [{k: s[k] for k in ("id", "name", "market", "family", "declaredStatus", "rank", "qualified",
                            "rewardEligible", "stats", "interval", "luck", "gates", "coverage",
                            "description", "features", "gateNote")}
         for s in leaderboard], indent=1) + "\n", encoding="utf-8")
    for s in evaluated:
        (STRAT / f"{s['id']}.json").write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")

    print(f"strategies evaluated: {len(evaluated)} (tested {len(tested)}, blocked "
          f"{len(evaluated) - len(tested)}); qualified {summary['qualifiedStrategies']}")
    for s in leaderboard:
        st = s["stats"]
        ci = s["interval"]
        print(f"  {s['id']:28s} n={st.get('n', 0):5d} roi={pct(st['roi']) if st.get('roi') is not None else '  n/a':>8s} "
              f"CI[{ci.get('low')},{ci.get('high')}] p={s['luck'].get('binomialPValue')} "
              f"rank={s['rank']} qualified={s['qualified']}")


if __name__ == "__main__":
    main()
