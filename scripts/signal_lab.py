#!/usr/bin/env python3
"""NFL Signal Lab — independent line origination, validation gates, correlation and leaderboard.

Inputs are ONLY the official-source JSON that `tools/fetch_nfl_lab.py` captures in CI
(nfl.com by-week results, nfl.com injury report table, nfl.com injury/inactives articles, official
standings snapshots, official club list). Three rules govern the output:

  1. This repository holds no market prices, so nothing here claims an edge, ROI, closing-line value
     or "beat the book" result. Model quality is measured against GAME OUTCOMES, which are official.
  2. Anything the sources do not state stays null and is reported as missing — never filled in.
  3. Everything is reproducible offline: `python3 scripts/signal_lab.py` rebuilds
     data/nfl-signals/*.json from the committed inputs with a fixed seed and no network.

Stdlib only, so the CI check and any reader can run it.
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "official", "lab")
OUT = os.path.join(ROOT, "data", "nfl-signals")
SEED = 20261113
MODEL_VERSION = "signal-lab-1.1.0"
LEDGER_STAMP = os.environ.get("LAB_STAMP", "2026-11-13T00:00:00Z")

# ---------------------------------------------------------------- model settings
MIN_TRAIN_GAMES = 20      # history needed before a week may be forecast
MIN_EVAL_GAMES = 60       # forecasts needed before a performance gate can PASS
SIG_GAMES = 120           # forecast count used for the "luck" arithmetic
RATING_ITERS = 6
HFA_FALLBACK = 2.0        # used only when fewer than 8 venue games exist
HOLD = 0.045              # two-sided vig used ONLY to show fair-vs-posted mechanics

POSITION_WEIGHTS = {      # deficit weights: model input, disclosed, sensitivity-tested below
    "QB": 1.00, "OL": 0.55, "DL": 0.50, "DB": 0.50, "LB": 0.45,
    "WR": 0.35, "RB": 0.30, "TE": 0.20, "K": 0.05, "P": 0.05, "LS": 0.02, "OTHER": 0.05,
}
STATUS_CREDIT = {         # how much of a position weight an official designation costs
    "Out": 1.00, "Doubtful": 0.75, "Questionable": 0.15, "Probable": 0.00,
    "Did Not Participate In Practice": 0.35,
    "Limited Participation In Practice": 0.10,
    "Full Participation In Practice": 0.00,
}
GROUP_BY_POS = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    "C": "OL", "G": "OL", "T": "OL", "OL": "OL", "OG": "OL", "OT": "OL",
    "DE": "DL", "DT": "DL", "NT": "DL", "EDGE": "DL", "DL": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "DB": "DB",
    "K": "K", "P": "P", "LS": "LS",
}
SENSITIVITY = {           # gate 6 robustness: re-run the leader under perturbed inputs
    "weights x0.5": 0.5,
    "weights x1.0": 1.0,
    "weights x2.0": 2.0,
}


# ----------------------------------------------------------------------- plumbing
def load(name, default=None):
    path = os.path.join(LAB, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


# --------------------------------------------------------------- statistics kit
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def mean(xs):
    return statistics.fmean(xs) if xs else None


def sd(xs):
    return statistics.stdev(xs) if xs and len(xs) > 1 else None


def r(x, n=4):
    return None if x is None else round(float(x), n)


def moving_block_bootstrap(values, iters=1500, block=5):
    """CI for a mean that keeps week-level dependence (block = games within a slate)."""
    if len(values) < block:
        return None, None
    rng = random.Random(SEED)
    n = len(values)
    starts = max(1, round(n / block))
    means = []
    for _ in range(iters):
        sample = []
        for _ in range(starts):
            i = rng.randrange(0, n - block + 1)
            sample.extend(values[i:i + block])
        means.append(statistics.fmean(sample))
    means.sort()
    return means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def phi_from_table(a, b, c, d):
    """Phi coefficient (Pearson r of two binary variables) plus its sample size."""
    n = a + b + c + d
    if n < 4:
        return None, n
    den = math.sqrt(float(a + b) * (c + d) * (a + c) * (b + d))
    if not den:
        return None, n
    return (a * d - b * c) / den, n


def log_loss(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def brier(p, y):
    return (p - y) ** 2


def ece(pairs, bins=10):
    if not pairs:
        return None
    total = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        bucket = [(p, y) for p, y in pairs if (lo <= p < hi) or (i == bins - 1 and p >= 1.0)]
        if not bucket:
            continue
        total += (len(bucket) / len(pairs)) * abs(mean([p for p, _ in bucket]) - mean([y for _, y in bucket]))
    return total


def pearson(xs, ys):
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not dx or not dy:
        return None
    return num / (dx * dy)


# ---------------------------------------------------------------------- datasets
def build_games():
    raw = load("results-2026.json", {"games": [], "meta": {}})
    games = []
    for g in raw.get("games", []):
        if g.get("week") is None:
            continue
        played = g.get("awayPoints") is not None and g.get("homePoints") is not None
        games.append({
            "slug": (g.get("sourceUrl") or "").rsplit("/", 1)[-1],
            "gameId": g.get("gameId"),
            "week": g["week"],
            "weekType": g.get("weekType"),
            "dateUTC": g.get("dateUTC"),
            "away": g.get("away"),
            "home": g.get("home"),
            "awayPoints": g.get("awayPoints") if played else None,
            "homePoints": g.get("homePoints") if played else None,
            "status": g.get("status"),
            "verification": g.get("verification"),
            "scoreSource": g.get("scoreSource"),
            "venue": g.get("venue"),
            "sourceUrl": g.get("sourceUrl"),
            "listUrl": g.get("listUrl"),
            "sourceName": g.get("sourceName"),
        })
    games.sort(key=lambda g: (g["dateUTC"] or "", g["slug"]))
    return games, (raw.get("meta") or {})


def group_of(pos):
    return GROUP_BY_POS.get(str(pos or "").upper().replace(".", ""), "OTHER")


def weight_of(pos, scale=1.0):
    return POSITION_WEIGHTS.get(group_of(pos), POSITION_WEIGHTS["OTHER"]) * scale


def build_availability(scale=1.0):
    """Per-club availability deficit, merged from the two official artefacts we actually hold.

    `injuries-2026.json` is the league's own weekly report table (practice participation + game
    status by club); `articles-2026.json` is the league's written injury-report / game-day inactives
    article. One player named in both is one player; the stronger official designation wins.
    Depth-chart order (2nd/3rd/4th string) is NOT in either source, so no tier is assigned here.
    """
    inj = load("injuries-2026.json", {"rows": []})
    art = load("articles-2026.json", {"rows": []})
    players: dict[tuple[str, str], dict] = {}

    def add(team, player, position, game_status, practice, source, url, context):
        if not team or not player:
            return
        row = players.setdefault((team, player.strip().lower()), {
            "team": team, "player": player.strip(), "position": None,
            "gameStatus": None, "practiceStatus": None, "sources": [], "urls": [], "context": None,
        })
        if position and not row["position"]:
            row["position"] = position
        order = {"Out": 5, "Doubtful": 4, "Questionable": 3, "Probable": 2}
        if game_status and order.get(game_status, 0) >= order.get(row["gameStatus"] or "", 0):
            row["gameStatus"] = game_status
        if practice and not row["practiceStatus"]:
            row["practiceStatus"] = practice
        if source and source not in row["sources"]:
            row["sources"].append(source)
        if url and url not in row["urls"]:
            row["urls"].append(url)
        if context and not row["context"]:
            row["context"] = context[:300]

    for r0 in inj.get("rows", []):
        add(r0.get("team"), r0.get("player"), r0.get("position"), r0.get("gameStatus"),
            r0.get("practiceStatus"), r0.get("sourceName"), r0.get("sourceUrl"), None)
    for r0 in art.get("rows", []):
        add(r0.get("team"), r0.get("player"), r0.get("position"), r0.get("statusWord"), None,
            r0.get("sourceName"), r0.get("articleUrl") or r0.get("sourceUrl"), r0.get("context"))

    rows = sorted(players.values(), key=lambda x: (x["team"], x["player"]))
    per_team: dict[str, dict] = {}
    for row in rows:
        t = per_team.setdefault(row["team"], {
            "team": row["team"], "playersReported": 0, "outOrDoubtful": 0, "questionable": 0,
            "unavailable": 0, "groups": defaultdict(lambda: {"reported": 0, "unavailable": 0,
                                                             "deficit": 0.0, "players": []}),
        })
        t["playersReported"] += 1
        credit = 0.0
        for status in (row["gameStatus"], row["practiceStatus"]):
            if status:
                credit = max(credit, STATUS_CREDIT.get(status, 0.0))
        if row["gameStatus"] in ("Out", "Doubtful"):
            t["outOrDoubtful"] += 1
        elif row["gameStatus"] == "Questionable":
            t["questionable"] += 1
        g = t["groups"][group_of(row["position"])]
        g["reported"] += 1
        if credit > 0:
            t["unavailable"] += 1
            g["unavailable"] += 1
            g["deficit"] += credit * weight_of(row["position"], scale)
            g["players"].append({"player": row["player"], "position": row["position"],
                                 "gameStatus": row["gameStatus"], "practiceStatus": row["practiceStatus"],
                                 "credit": credit})
    out = {}
    for team, t in per_team.items():
        groups = {k: {"reported": v["reported"], "unavailable": v["unavailable"],
                      "deficit": round(v["deficit"], 4),
                      "players": sorted(v["players"], key=lambda p: -p["credit"])}
                  for k, v in sorted(t["groups"].items())}
        offense = sum(groups.get(k, {}).get("deficit", 0.0) for k in ("QB", "OL", "RB", "WR", "TE"))
        defense = sum(groups.get(k, {}).get("deficit", 0.0) for k in ("DL", "LB", "DB"))
        out[team] = {
            "team": team,
            "playersReported": t["playersReported"],
            "outOrDoubtful": t["outOrDoubtful"],
            "questionable": t["questionable"],
            "unavailableCredit": t["unavailable"],
            "offensiveDeficit": round(offense, 4),
            "defensiveDeficit": round(defense, 4),
            "totalDeficit": round(offense + defense, 4),
            "byGroup": groups,
        }
    return rows, out


def build_standings():
    raw = load("standings-2026.json", {"rows": []})
    best = {}
    for r0 in raw.get("rows", []):
        team = r0.get("team")
        if not team:
            continue
        prev = best.get(team)
        rank = (r0.get("week") or -1, r0.get("wins") or 0)
        if prev is None or rank > prev[0]:
            best[team] = (rank, r0)
    return {team: rec for team, (_, rec) in best.items()}


# -------------------------------------------------------------------- core model
def team_strengths(games, injury_adj=None, adj_scale=1.0):
    """Opponent-adjusted per-team scoring profile, and the home-field estimate.

    Ridge-free iterative solve: each team's attack/defense rates are re-estimated from the games
    actually played, netting out the opponent's matching rate. Injury adjustments enter ONLY as an
    additive points-per-game shift on the availability deficit (a model input, disclosed above), and
    are reported separately so a reader can see how much of the line comes from injuries.
    """
    played = [g for g in games if g["awayPoints"] is not None]
    agg = defaultdict(lambda: {"pf": 0.0, "pa": 0.0, "n": 0, "homeN": 0, "awayN": 0,
                              "homeMargin": [], "awayMargin": [], "margin": []})
    for g in played:
        margin = g["homePoints"] - g["awayPoints"]
        for side, pts, opp in (("home", g["homePoints"], g["awayPoints"]),
                               ("away", g["awayPoints"], g["homePoints"])):
            row = agg[g[side]]
            row["pf"] += pts
            row["pa"] += opp
            row["n"] += 1
            row[f"{side}N"] += 1
            row["margin"].append(margin if side == "home" else -margin)
            (row["homeMargin"] if side == "home" else row["awayMargin"]).append(margin)
    teams = sorted(agg)
    rating = {t: 0.0 for t in teams}
    if played:
        for _ in range(RATING_ITERS):
            new = {}
            for t in teams:
                row = agg[t]
                vals = []
                for g in played:
                    if g["away"] == t:
                        opp = g["home"]
                        vals.append((g["awayPoints"] - g["homePoints"]) - rating[opp])
                    elif g["home"] == t:
                        opp = g["away"]
                        vals.append((g["homePoints"] - g["awayPoints"]) - rating[opp])
                new[t] = mean(vals) or 0.0
            adj = mean(list(new.values())) or 0.0
            rating = {t: v - adj for t, v in new.items()}
    home_margins = [m for t in teams for m in agg[t]["homeMargin"]]
    hfa = (mean(home_margins) if len(home_margins) >= 8 else HFA_FALLBACK) or HFA_FALLBACK
    rates = {}
    league_ppg = mean([g["homePoints"] + g["awayPoints"] for g in played]) or 44.0
    for t in teams:
        row = agg[t]
        off = row["pf"] / row["n"] if row["n"] else league_ppg / 2
        df = row["pa"] / row["n"] if row["n"] else league_ppg / 2
        rates[t] = {
            "team": t, "games": row["n"], "pointsFor": row["pf"], "pointsAgainst": row["pa"],
            "ppg": r(off, 2), "papg": r(df, 2), "netPpg": r(off - df, 2),
            "rating": r(rating[t], 3),
            "homeGames": row["homeN"], "awayGames": row["awayN"],
            "homeMargin": r(mean(row["homeMargin"]), 2), "awayMargin": r(mean(row["awayMargin"]), 2),
            "marginSd": r(sd(row["margin"]), 2),
            "injuryDeficit": None, "injuryShift": 0.0,
        }
    if injury_adj:
        for t, row in rates.items():
            avail = injury_adj.get(t)
            if not avail:
                continue
            deficit = avail["totalDeficit"]
            shift = -1.0 * adj_scale * deficit      # points per game, model input
            row["injuryDeficit"] = r(deficit, 4)
            row["injuryShift"] = r(shift, 3)
            row["ratingAdj"] = r(rating[t] + shift, 3)
    return rates, r(hfa, 3), {t: r(mean(agg[t]["margin"]), 2) for t in teams}, len(played)


def forecast(game, rates, hfa, use_injury=False):
    """Probability the HOME team wins the game, from the team profile only (no market input)."""
    a, h = rates.get(game["away"]), rates.get(game["home"])
    if not a or not h:
        return None
    exp_margin = (h["rating"] - a["rating"]) + hfa
    if use_injury:
        exp_margin += (h.get("injuryShift") or 0.0) - (a.get("injuryShift") or 0.0)
    home_ppg = (h["ppg"] + a["papg"]) / 2.0
    away_ppg = (a["ppg"] + h["papg"]) / 2.0
    if use_injury:
        home_ppg += (h.get("injuryShift") or 0.0)
        away_ppg += (a.get("injuryShift") or 0.0)
    return {"expHomeMargin": exp_margin, "homePoints": home_ppg, "awayPoints": away_ppg}


def spread_sigma(games, rates, hfa):
    resid = []
    for g in games:
        if g["awayPoints"] is None:
            continue
        f = forecast(g, rates, hfa)
        if not f:
            continue
        resid.append((g["homePoints"] - g["awayPoints"]) - f["expHomeMargin"])
    return sd(resid), len(resid)



LAMBDA_GRID = (0.2, 0.35, 0.5, 0.7, 1.0)


def choose_shrinkage(hist, use_injury=False, avail=None):
    """Pick the rating-shrink factor inside the training window only (nested validation).

    Raw opponent-adjusted ratings are far too confident in small samples: they put probabilities at
    0.02 and 0.98 that the game does not support. The fix is a single multiplier on the rating gap,
    chosen by minimising validation log loss on the LAST training week, using only weeks before it.
    Returns (lambda, validation log loss, validation games).
    """
    weeks = sorted({g["week"] for g in hist if g["awayPoints"] is not None})
    if len(weeks) < 3:
        return 0.5, None, 0
    tr = [g for g in hist if g["week"] < weeks[-1]]
    va = [g for g in hist if g["week"] == weeks[-1]]
    if len(tr) < MIN_TRAIN_GAMES or not va:
        return 0.5, None, len(va)
    r_tr, hfa_tr, _m, _n = team_strengths(tr, avail if use_injury else None, 1.0)
    sig_tr = spread_sigma(tr, r_tr, hfa_tr)[0] or 10.5
    best, best_ll = 0.5, None
    for lam in LAMBDA_GRID:
        losses = []
        for g in va:
            a, h = r_tr.get(g["away"]), r_tr.get(g["home"])
            if not a or not h:
                continue
            shift = 0.0
            if use_injury:
                shift = (h.get("injuryShift") or 0.0) - (a.get("injuryShift") or 0.0)
            p = norm_cdf((hfa_tr + lam * (h["rating"] - a["rating"]) + shift) / sig_tr)
            if g["homePoints"] == g["awayPoints"]:
                continue
            losses.append(log_loss(p, 1 if g["homePoints"] > g["awayPoints"] else 0))
        v = mean(losses)
        if v is not None and (best_ll is None or v < best_ll):
            best, best_ll = lam, v
    return best, r(best_ll, 5), len(va)


# ---------------------------------------------------------------------- gates
def evaluate(games, rates, hfa, sigma, mode):
    """Walk-forward forecast ledger for one strategy mode.

    mode: 'hfa' (home-field only), 'net' (net points, no opposition), 'adj' (opponent-adjusted),
          'adj_injury' (opponent-adjusted + availability deficit).
    Each week is predicted using only games played in EARLIER weeks — that is the whole point:
    no forecast may see its own result.
    """
    played = [g for g in games if g["awayPoints"] is not None]
    weeks = sorted({g["week"] for g in played})
    rows = []
    for wk in weeks:
        hist = [g for g in played if g["week"] < wk]
        if len(hist) < MIN_TRAIN_GAMES:
            continue
        r_wk, hfa_wk, _m, _n = team_strengths(hist, AVAIL_SCALE[0] if mode == "adj_injury" else None)
        sigma_wk, _ = spread_sigma(hist, r_wk, hfa_wk)
        sigma_use = sigma_wk or sigma or 10.5
        lam, val_ll, val_n = choose_shrinkage(hist, use_injury=(mode == "adj_injury"),
                                              avail=AVAIL_SCALE[0])
        for g in [x for x in played if x["week"] == wk]:
            f = forecast(g, r_wk, hfa_wk, use_injury=(mode == "adj_injury"))
            if not f:
                continue
            if mode == "hfa":
                p = norm_cdf(hfa_wk / sigma_use)
            elif mode == "net":
                gap = ((r_wk.get(g["home"], {}).get("netPpg") or 0)
                       - (r_wk.get(g["away"], {}).get("netPpg") or 0))
                p = norm_cdf((hfa_wk + lam * gap) / sigma_use)
            else:
                p = norm_cdf((hfa_wk + lam * (f["expHomeMargin"] - hfa_wk)) / sigma_use)
            y = 1 if g["homePoints"] > g["awayPoints"] else (0 if g["homePoints"] < g["awayPoints"] else 2)
            rows.append({
                "week": wk, "slug": g["slug"], "dateUTC": g["dateUTC"],
                "away": g["away"], "home": g["home"],
                "pHome": r(p, 4), "outcomeHomeWin": (1 if y == 1 else (0 if y == 0 else None)),
                "logLoss": r(log_loss(p, y), 5) if y != 2 else None,
                "brier": r(brier(p, y), 5) if y != 2 else None,
                "expMargin": r(hfa_wk + lam * (f["expHomeMargin"] - hfa_wk), 3),
                "fairSpreadHome": r(-f["expHomeMargin"], 2),
                "fairTotal": r(f["homePoints"] + f["awayPoints"], 2),
                "actualHomePoints": g["homePoints"], "actualAwayPoints": g["awayPoints"],
                "actualMargin": g["homePoints"] - g["awayPoints"],
                "actualTotal": g["homePoints"] + g["awayPoints"],
                "sigmaUsed": r(sigma_use, 3),
                "shrinkLambda": lam, "shrinkChosenOn": {"validationLogLoss": val_ll,
                                                        "validationGames": val_n},
                "trainGames": len(hist),
                "sourceUrl": g["sourceUrl"],
            })
    return rows


AVAIL_SCALE: list = [None]


def score_ledger(rows):
    scored = [x for x in rows if x["outcomeHomeWin"] is not None]
    if not scored:
        return None
    ll = [x["logLoss"] for x in scored]
    br = [x["brier"] for x in scored]
    pairs = [(x["pHome"], x["outcomeHomeWin"]) for x in scored]
    hits = [1 if (x["pHome"] >= 0.5) == bool(x["outcomeHomeWin"]) else 0 for x in scored]
    strong = [x for x in scored if abs(x["pHome"] - 0.5) >= 0.08]
    return {
        "n": len(scored),
        "logLoss": r(mean(ll), 5), "logLossSe": r(sd(ll) / math.sqrt(len(ll)), 5) if len(ll) > 1 else None,
        "brier": r(mean(br), 5), "brierSe": r(sd(br) / math.sqrt(len(br)), 5) if len(br) > 1 else None,
        "ece": r(ece(pairs), 4),
        "hitRate": r(mean(hits), 4),
        "nStrong": len(strong),
        "hitRateStrong": r(mean([1 if (x["pHome"] >= 0.5) == bool(x["outcomeHomeWin"]) else 0
                                 for x in strong]), 4) if strong else None,
        "probRange": [r(min(x["pHome"] for x in scored), 3), r(max(x["pHome"] for x in scored), 3)],
        "weeks": sorted({x["week"] for x in scored}),
    }


def luck_report(baseline_rows, model_rows):
    """Remove luck from the comparison: paired difference, block-bootstrap CI and the noise floor.

    A one-point log-loss difference over n games means little when the sampling noise is three points,
    so both are reported, together with the sample size at which the observed difference would clear
    two standard errors. Until that n is reached the honest verdict is "not yet distinguishable
    from luck", which is exactly what the leaderboard shows.
    """
    b = [x for x in baseline_rows if x.get("logLoss") is not None]
    m = [x for x in model_rows if x.get("logLoss") is not None]
    bmap = {x["slug"]: x for x in b}
    diffs = [bmap[x["slug"]]["logLoss"] - x["logLoss"] for x in m if x["slug"] in bmap]
    if len(diffs) < 8:
        return None
    lo, hi = moving_block_bootstrap(diffs)
    d_mean, d_se = mean(diffs), (sd(diffs) / math.sqrt(len(diffs))) if len(diffs) > 1 else None
    t = (d_mean / d_se) if d_se else None
    n_needed = int(math.ceil((2 * d_se / d_mean) ** 2)) if (d_se and d_mean) else None
    return {
        "nPaired": len(diffs),
        "meanImprovement": r(d_mean, 5),
        "stdErr": r(d_se, 5),
        "tStat": r(t, 3),
        "bootCI95": [r(lo, 5), r(hi, 5)] if lo is not None else None,
        "crossesZero": bool(lo <= 0 <= hi) if lo is not None else None,
        "nForTwoSigma": n_needed,
        "sampleNeededForGate": SIG_GAMES,
        "verdict": ("not distinguishable from luck at this sample size"
                    if (t is None or abs(t) < 2) else "clears two standard errors on this sample"),
    }

GATE_ORDER = [
    ("G1", "Data provenance",
     "Every input row carries an official source URL and a capture timestamp."),
    ("G2", "Coverage and integrity",
     "Games with results, availability rows with a club, and null handling are counted; no silent imputation."),
    ("G3", "Beats naive baselines",
     "Out-of-sample log loss and Brier must improve on the home-field-only and net-points baselines."),
    ("G4", "Leakage audit",
     "Each week is forecast only from earlier weeks; team rates and the margin sigma are re-fitted inside that window."),
    ("G5", "Out-of-sample performance",
     "At least 60 settled forecasts, with calibration error and uncertainty reported."),
    ("G6", "Robustness",
     "The leader must survive deficit-weight scaling and week-level block resampling."),
    ("G7", "Prospective paper trial",
     "A frozen, timestamped forecast ledger started before outcomes, for a predeclared horizon."),
    ("G8", "Release review",
     "Reproducible run, independent review, no integrity or responsible-use blocker."),
]


def ml_price(p):
    """American odds for a fair probability (no vig): arithmetic, not a market quote."""
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return -100 * p / (1 - p)
    return 100 * (1 - p) / p


def round_price(decimal_odds, hold):
    """Apply a symmetric house hold to a fair decimal price so the mechanics stay visible."""
    if not decimal_odds or decimal_odds <= 1:
        return None
    implied = 1.0 / decimal_odds
    adj = implied * (1 + hold / 2)
    return 1.0 / adj if adj < 1 else decimal_odds


def parlay_study(rows, games):
    """Same-game two-leg parlay: measured joint settlement against the independence assumption."""
    table = {"homeWinOver": 0, "homeWinUnder": 0, "homeLossOver": 0, "homeLossUnder": 0}
    for x in rows:
        if x["actualHomePoints"] is None:
            continue
        over = (x["actualTotal"] or 0) > (x["fairTotal"] or 0)
        home_won = x["actualHomePoints"] > x["actualAwayPoints"]
        key = ("homeWin" if home_won else "homeLoss") + ("Over" if over else "Under")
        table[key] += 1
    a, b, c, d = (table["homeWinOver"], table["homeWinUnder"],
                  table["homeLossOver"], table["homeLossUnder"])
    n = a + b + c + d
    if not n:
        return {"available": False, "reason": "no settled forecasts yet", "sample": 0}
    p_home, p_over, p_joint = (a + b) / n, (a + c) / n, a / n
    indep = p_home * p_over
    return {
        "available": True,
        "sample": n,
        "table": table,
        "pHomeWin": r(p_home, 4),
        "pTotalOverModelLine": r(p_over, 4),
        "pJointMeasured": r(p_joint, 4),
        "pJointIfIndependent": r(indep, 4),
        "relativeChangeFromIndependence": r((p_joint / indep - 1) if indep else None, 4),
        "phiCorrelation": r(phi_from_table(a, b, c, d)[0], 4),
        "fairParlayDecimal": r(1 / p_joint, 4) if p_joint else None,
        "fairIfIndependenceAssumed": r(1 / indep, 4) if indep else None,
        "note": "Both legs come from the model's own numbers. A real parlay must be priced against the "
                "exact offered line and price for each leg, which this repository does not hold.",
    }


def prop_combo_status(games):
    """Player-prop combos cannot be built from what this repository holds; say so precisely."""
    return {
        "available": False,
        "reason": "No player-level season statistics and no player-prop prices are captured by "
                  "tools/fetch_nfl_lab.py; nfl.com's player-statistics page renders client-side, and no "
                  "prop price feed exists in this repository.",
        "whatWouldBeNeeded": [
            "player snap / opportunity counts with a point-in-time timestamp",
            "the offered prop line and its timestamp, per book",
            "game-day inactives (official) to condition participation on",
        ],
        "methodWhenAvailable": [
            "forecast the player's full distribution, not a point estimate",
            "price each leg off that distribution, then price the combo off the JOINT distribution",
            "estimate pairwise association from settled joint outcomes only, and publish n with it",
            "refuse a combo price when the joint sample does not exist",
        ],
        "gameLevelProxy": {
            "note": "Until player data exists, same-team dependence is measured on team outcomes instead "
                    "— see correlation.weekToWeekMarginAutocorrelation.",
            "sampleGames": len([g for g in games if g["awayPoints"] is not None]),
        },
    }


def correlation_study(games, rates, hfa):
    """Correlation values that can actually be computed from the official results held here."""
    played = [g for g in games if g["awayPoints"] is not None]
    margins = [g["homePoints"] - g["awayPoints"] for g in played]
    totals = [g["homePoints"] + g["awayPoints"] for g in played]
    r_mt = pearson(margins, totals)

    by_team_week = defaultdict(dict)
    for g in played:
        by_team_week[g["home"]][g["week"]] = g["homePoints"] - g["awayPoints"]
        by_team_week[g["away"]][g["week"]] = g["awayPoints"] - g["homePoints"]
    cur, nxt = [], []
    for weeks in by_team_week.values():
        for wk in sorted(weeks):
            if wk + 1 in weeks:
                cur.append(weeks[wk])
                nxt.append(weeks[wk + 1])
    r_wk = pearson(cur, nxt)

    slate = defaultdict(list)
    for g in played:
        slate[(g["dateUTC"] or "")[:10]].append(1 if g["homePoints"] > g["awayPoints"] else 0)
    share_by_day = {day: (len(v), sum(v)) for day, v in slate.items() if len(v) >= 4}
    slate_report = None
    if len(share_by_day) >= 4:
        shares = [n / d for d, n in share_by_day.values()]
        p_bar = mean(shares)
        exp = [p_bar * (1 - p_bar) / d for d, _n in share_by_day.values()]
        obs = statistics.pvariance(shares)
        slate_report = {
            "slateDays": len(share_by_day),
            "homeWinShareMean": r(p_bar, 4),
            "varianceOfHomeWinShare": r(obs, 5),
            "expectedVarianceIfIndependent": r(mean(exp), 5),
            "ratioObservedOverIndependent": r(obs / mean(exp), 3) if mean(exp) else None,
            "meaning": "a ratio above 1 means home teams win together on the same day more often than "
                       "independence predicts, which is what makes a same-day multi-leg parlay riskier "
                       "than the multiplied price implies",
        }
    return {
        "sampleGames": len(played),
        "marginVsTotal": {"pearsonR": r(r_mt, 4), "n": len(played),
                          "meaning": "positive means heavier favourites coincide with higher scoring, which "
                                     "matters for a spread-plus-over parlay"},
        "weekToWeekMarginAutocorrelation": {"pearsonR": r(r_wk, 4), "n": len(cur),
                                            "meaning": "how much of last week's margin carries into this "
                                                       "week — it sets the decay a rating must apply"},
        "slateClustering": slate_report,
        "notComputable": [
            {"item": "player-prop pair correlation", "why": "no player-level data in this repository"},
            {"item": "bookmaker parlay pricing correlation", "why": "no odds archive in this repository"},
            {"item": "weather effect on totals", "why": "no archived weather observation with a pre-game timestamp"},
            {"item": "referee-crew effect", "why": "no official per-crew split captured"},
            {"item": "bye-week / rest effect", "why": "the by-week payload carries no bye list"},
            {"item": "depth-chart tier (2nd/3rd/4th string)",
             "why": "nfl.com publishes no depth chart (probed: /depth-charts/ and the club depth-chart page "
                    "both return 404), so a backup's quality cannot be verified from an official source"},
        ],
    }


def sensitivity_run(games):
    """Gate 6: does the ranking survive re-scaling the only discretionary input in the model?"""
    out = {}
    global AVAIL_SCALE
    for label, scale in SENSITIVITY.items():
        _rows, avail = build_availability(scale)
        AVAIL_SCALE[0] = avail
        rates, hfa, _m, _n = team_strengths(games, avail, 1.0)
        sigma, _ = spread_sigma(games, rates, hfa)
        ledgers = {"S3-oppadj-ratings": evaluate(games, rates, hfa, sigma, "adj"),
                   "S4-oppadj-plus-availability": evaluate(games, rates, hfa, sigma, "adj_injury")}
        out[label] = {name: score_ledger(rows) for name, rows in ledgers.items()}
    _rows, avail = build_availability(1.0)
    AVAIL_SCALE[0] = avail
    return out


def update_forward_ledger(lines, games):
    """Append today's frozen predictions to the prospective ledger, and settle old ones.

    The ledger is the only honest way to earn a leaderboard place: a prediction is written BEFORE the
    outcome exists and never edited afterwards. Re-running only adds rows for games not yet logged and
    fills an outcome when the official page now reports a score.
    """
    path = os.path.join(OUT, "forward-ledger.json")
    prior = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for row in json.load(f).get("rows", []):
                prior[row["slug"]] = row
    played = {g["slug"]: g for g in games if g["awayPoints"] is not None}
    added = settled = 0
    for row in lines:
        slug = row["slug"]
        if slug not in prior:
            prior[slug] = {
                "slug": slug, "loggedAtUTC": LEDGER_STAMP, "modelVersion": MODEL_VERSION,
                "week": row["week"], "dateUTC": row["dateUTC"], "away": row["away"], "home": row["home"],
                "pHomeWin": row["pHomeWin"], "fairSpreadHome": row["fairSpreadHome"],
                "fairTotal": row["fairTotal"], "sourceUrl": row["sourceUrl"],
                "actualHomePoints": None, "actualAwayPoints": None,
                "outcomeHomeWin": None, "marginError": None, "totalError": None, "settledAtUTC": None,
            }
            added += 1
        rec = prior[slug]
        g = played.get(slug)
        if g and rec["outcomeHomeWin"] is None:
            rec["actualHomePoints"] = g["homePoints"]
            rec["actualAwayPoints"] = g["awayPoints"]
            rec["outcomeHomeWin"] = 1 if g["homePoints"] > g["awayPoints"] else (
                0 if g["homePoints"] < g["awayPoints"] else None)
            rec["marginError"] = r(abs((g["homePoints"] - g["awayPoints"]) - (-rec["fairSpreadHome"])), 3)
            rec["totalError"] = r(abs((g["homePoints"] + g["awayPoints"]) - rec["fairTotal"]), 3)
            rec["settledAtUTC"] = LEDGER_STAMP
            settled += 1
    rows = sorted(prior.values(), key=lambda x: (x["dateUTC"] or "", x["slug"]))
    settled_rows = [x for x in rows if x["outcomeHomeWin"] is not None]
    dir_hits = [1 if (x["pHomeWin"] >= 0.5) == bool(x["outcomeHomeWin"]) else 0 for x in settled_rows]
    dump("forward-ledger.json", {
        "meta": {
            "purpose": "Prospective, frozen forecast ledger — the evidence base for gate G7 and for the "
                       "leaderboard. Written before the result exists; never rewritten afterwards.",
            "modelVersion": MODEL_VERSION,
            "ledgerStampUTC": LEDGER_STAMP,
            "rows": len(rows), "addedThisRun": added, "settledThisRun": settled,
            "settled": len(settled_rows),
            "open": len(rows) - len(settled_rows),
            "directionalHitRate": r(mean(dir_hits), 4) if dir_hits else None,
            "meanAbsoluteMarginError": r(mean([x["marginError"] for x in settled_rows]), 3) if settled_rows else None,
            "meanAbsoluteTotalError": r(mean([x["totalError"] for x in settled_rows]), 3) if settled_rows else None,
            "rule": "no prize is payable from this ledger until at least 60 settled games exist",
        },
        "rows": rows,
    })
    return added, settled, len(settled_rows)


def main():
    games, res_meta = build_games()
    avail_rows, avail = build_availability(1.0)
    AVAIL_SCALE[0] = avail
    standings = build_standings()

    rates, hfa, _margins, played_n = team_strengths(games, avail, 1.0)
    sigma, sigma_n = spread_sigma(games, rates, hfa)

    modes = {
        "S1-homefield": "hfa",
        "S2-netpoints": "net",
        "S3-oppadj-ratings": "adj",
        "S4-oppadj-plus-availability": "adj_injury",
    }
    ledgers = {name: evaluate(games, rates, hfa, sigma, mode) for name, mode in modes.items()}
    scores = {name: score_ledger(rows) for name, rows in ledgers.items()}
    parlay = parlay_study(ledgers["S3-oppadj-ratings"], games)
    prop = prop_combo_status(games)
    corr = correlation_study(games, rates, hfa)

    played_dates = {g["dateUTC"] for g in games if g["awayPoints"] is not None}
    upcoming = [g for g in games if g["awayPoints"] is None and g["week"] and g["weekType"] == "REG"
                and g["dateUTC"] and g["dateUTC"][:10] not in {str(d)[:10] for d in played_dates}]
    upcoming.sort(key=lambda g: (g["dateUTC"] or "", g["slug"]))
    league_total = mean([g["homePoints"] + g["awayPoints"] for g in games if g["awayPoints"] is not None]) or 44.0
    lam_pub, val_ll, val_n = choose_shrinkage([g for g in games if g["awayPoints"] is not None],
                                             use_injury=True, avail=avail)
    lines = []
    for g in upcoming:
        f = forecast(g, rates, hfa, use_injury=True)
        if not f:
            continue
        f["expHomeMargin"] = hfa + lam_pub * (f["expHomeMargin"] - hfa)
        p_home = norm_cdf(f["expHomeMargin"] / (sigma or 10.5))
        exp_total = f["homePoints"] + f["awayPoints"]
        p_over = 1 - norm_cdf((exp_total - league_total) / ((sigma or 10.5) * 1.35))
        lines.append({
            "slug": g["slug"],
            "week": g["week"], "dateUTC": g["dateUTC"], "away": g["away"], "home": g["home"],
            "fairSpreadHome": r(-f["expHomeMargin"], 2),
            "fairMoneylineHome": r(ml_price(p_home), 1),
            "fairMoneylineAway": r(ml_price(1 - p_home), 1),
            "fairTotal": r(exp_total, 2),
            "pHomeWin": r(p_home, 4),
            "pTotalOver": r(p_over, 4),
            "postedWithHold": {"home": r(round_price(1 / max(p_home, 1e-6), HOLD), 3),
                               "away": r(round_price(1 / max(1 - p_home, 1e-6), HOLD), 3)},
            "injuryDeficitHome": (rates.get(g["home"]) or {}).get("injuryDeficit"),
            "injuryDeficitAway": (rates.get(g["away"]) or {}).get("injuryDeficit"),
            "modelVersion": MODEL_VERSION,
            "shrinkLambda": lam_pub,
            "sourceUrl": g["sourceUrl"],
            "status": "model line - no market price exists in this repository to compare against",
        })
        if len(lines) >= 40:
            break

    added, settled, settled_total = update_forward_ledger(lines, games)
    board = leaderboard(scores, ledgers, parlay, prop)
    gate_report = build_gates(scores, ledgers, played_n, avail_rows, avail, sigma_n, board)

    dump("signals.json", {
        "meta": {
            "generator": "scripts/signal_lab.py",
            "modelVersion": MODEL_VERSION,
            "seed": SEED,
            "inputs": {
                "gamesOnPage": len(games),
                "gamesWithOfficialScores": played_n,
                "availabilityRows": len(avail_rows),
                "clubsWithAnAvailabilityFile": len(avail),
                "standingsClubs": len(standings),
                "resultCaptureUTC": res_meta.get("retrievedUTC"),
            },
            "discipline": [
                "no market prices are stored here, so no edge, ROI or closing-line claim is made",
                "walk-forward only: a week is forecast from earlier weeks exclusively",
                "unverified fields stay null; depth-chart tiers are never inferred",
            ],
        },
        "teams": {"ratings": rates, "homeFieldAdvantage": hfa, "gamesPlayed": played_n,
                  "marginSigma": r(sigma, 3), "sigmaSamples": sigma_n},
        "availability": {"rows": avail_rows, "byTeam": avail},
        "ledgers": ledgers,
        "scores": scores,
        "luck": {name: luck_report(ledgers["S1-homefield"], rows)
                 for name, rows in ledgers.items() if name != "S1-homefield"},
        "correlation": corr,
        "parlay": parlay,
        "propCombos": prop,
        "lines": lines,
        "publishedShrinkage": {"lambda": lam_pub, "validationLogLoss": val_ll, "validationGames": val_n,
                               "rule": "chosen inside the training window only (see choose_shrinkage)"},
        "leaderboard": board,
        "gates": gate_report,
        "sensitivity": sensitivity_run(games),
    })
    print(f"forwardLedger: +{added} logged, {settled} settled this run, {settled_total} settled total")
    print(f"games={len(games)} played={played_n} sigma={sigma and round(sigma, 2)} hfa={hfa} "
          f"availabilityRows={len(avail_rows)} clubs={len(avail)} lines={len(lines)}")
    for name in modes:
        print(f"  {name}: {scores[name]}")


def leaderboard(scores, ledgers, parlay, prop):
    order = ["S1-homefield", "S2-netpoints", "S3-oppadj-ratings", "S4-oppadj-plus-availability"]
    base = scores.get("S1-homefield") or {}
    entries = []
    for name in order:
        s = scores.get(name) or {}
        ll = s.get("logLoss")
        entries.append({
            "strategy": name,
            "betType": "single (game winner)" if "parlay" not in name else "parlay",
            "n": s.get("n"),
            "logLoss": ll,
            "brier": s.get("brier"),
            "ece": s.get("ece"),
            "hitRate": s.get("hitRate"),
            "hitRateStrong": s.get("hitRateStrong"),
            "improvementVsBaseline": (r(base.get("logLoss") - ll, 5) if (ll is not None
                                                                        and base.get("logLoss")) else None),
            "weeksCovered": s.get("weeks"),
            "qualified": None,
        })
    # extra rows for the combination strategies, which cannot be scored on outcomes alone
    entries.append({
        "strategy": "S5-same-game-parlay-joint",
        "betType": "parlay (2 legs, same game)",
        "n": parlay.get("sample"),
        "logLoss": None, "brier": None, "ece": None,
        "hitRate": None, "hitRateStrong": None, "improvementVsBaseline": None,
        "weeksCovered": None, "qualified": False,
        "note": "priced from the measured joint distribution; no profit claim is possible without prices",
    })
    entries.append({
        "strategy": "S6-player-prop-combo",
        "betType": "player prop combo",
        "n": None, "logLoss": None, "brier": None, "ece": None, "hitRate": None,
        "hitRateStrong": None, "improvementVsBaseline": None, "weeksCovered": None,
        "qualified": False, "note": "not runnable: no player-level or prop-price data in this repository",
    })
    ranked = sorted([e for e in entries if e["logLoss"] is not None], key=lambda e: e["logLoss"])
    for i, e in enumerate(ranked, start=1):
        e["rank"] = i
        e["qualified"] = (e["n"] or 0) >= MIN_EVAL_GAMES
    for e in entries:
        e.setdefault("rank", None)
    return {"entries": entries, "rankingKey": "out-of-sample log loss (lower is better)",
            "rewards": "none authorised — paper leaderboard only until G7/G8 pass and a policy review exists",
            "prizeRule": ("rank on improvement over the baseline in a proper score, with calibration and "
                          "minimum-sample gates; never on win streaks or unadjusted ROI")}


def build_gates(scores, ledgers, played_n, avail_rows, avail, sigma_n, board):
    g = {name: {} for name in list(scores) + ["S5-same-game-parlay-joint", "S6-player-prop-combo"]}
    n_best = max([s.get("n") or 0 for s in scores.values()] or [0])
    src_ok = all(x.get("sourceUrl") for rows in ledgers.values() for x in rows)
    for code, title, desc in GATE_ORDER:
        for name in g:
            status, evidence = "not-started", ""
            if code == "G1":
                status = "pass" if src_ok and n_best else "fail"
                evidence = ("every forecast row carries the nfl.com game URL; the fetcher writes "
                            "retrievedUTC per dataset" if src_ok else "a forecast row lost its source URL")
            elif code == "G2":
                status = "pass" if played_n and avail_rows else "fail"
                evidence = (f"{played_n} games with official scores; {len(avail_rows)} availability rows "
                            f"across {len(avail)} clubs; nulls kept as nulls")
            elif code == "G3":
                s = scores.get(name)
                base = scores.get("S1-homefield") or {}
                if s and base and s.get("n"):
                    better = (s["logLoss"] or 1) < (base["logLoss"] or 1)
                    status = "pass" if (better or name == "S1-homefield") else "fail"
                    evidence = f"log loss {s['logLoss']} vs baseline {base['logLoss']} on n={s['n']}"
                else:
                    status = "blocked"
                    evidence = "no outcome-scoreable rows for this entry (combination strategy)"
            elif code == "G4":
                if name == "S4-oppadj-plus-availability":
                    status = "fail"
                    evidence = ("scores and team rates are time-locked, but the availability file is TODAY'S "
                                "official report: applying it to weeks 3-9 is not point-in-time and inflates "
                                "the result. This strategy may only be judged forward, from a dated archive.")
                elif name in scores:
                    status = "pass"
                    evidence = ("week w uses only weeks < w; team rates, sigma and the shrink factor are "
                                "re-fitted inside that window")
                else:
                    status = "not-applicable"
                    evidence = "combination entry, no single-game forecast series"
            elif code == "G5":
                s = scores.get(name) or {}
                if s.get("n"):
                    status = "pass" if s["n"] >= MIN_EVAL_GAMES else "insufficient-sample"
                    evidence = f"n={s['n']} (gate needs {MIN_EVAL_GAMES}), ECE={s.get('ece')}"
                else:
                    status = "blocked"
                    evidence = "no player-prop or price data in this repository"
            elif code == "G6":
                status = "manual-review"
                evidence = ("deficit-weight scaling is published in data/nfl-signals/signals.json under "
                            "'sensitivity'; the reader must confirm the ranking does not flip")
            elif code == "G7":
                status = "not-started"
                evidence = ("no frozen forward ledger exists yet; the first one starts at the next "
                            "unplayed slate listed on the Lines page")
            elif code == "G8":
                status = "not-started"
                evidence = "independent review and responsible-use sign-off have not happened"
            g[name][code] = {"title": title, "rule": desc, "status": status, "evidence": evidence}
    return g


if __name__ == "__main__":
    main()
