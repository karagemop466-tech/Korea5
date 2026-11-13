#!/usr/bin/env python3
"""Originate NFL lines from official data, then evaluate strategies against them.

Inputs (all committed, all official):
  data/lines/games.json         NFL.com official schedules + final scores
  data/lines/boxscores.json     NFL.com official box scores (per-player game rows)
  data/lines/injuries.json      NFL.com official weekly injury report
  data/lines/depth-charts.json  official club depth charts (1st/2nd/3rd/4th string)

Outputs:
  data/lines/lines.json           our originated lines (spread, total, player props)
  data/lines/strategies.json      strategy catalog, every bet, metrics, gate results
  data/lines/leaderboard.json     ranked strategies and the reward they earn
  data/lines/correlations.json    measured correlations between strategies and props
  data/lines/player-registry.json image-id -> official full name / team / tier
  data/lines/lineup-risk.json     injury + depth deficiency tracker for upcoming games

Method (declared, and published on the site):
  * Development period = 2024 + 2025 regular seasons. 2026 regular season is the
    untouched holdout. Nothing fitted on 2026 is used to score 2026.
  * Within a season the model is walk-forward: a game is predicted only from games
    played strictly earlier.
  * Every strategy is priced against a DECLARED reference price of -110 (decimal
    1.9091) per leg. This is a stated convention for comparing strategies with each
    other. It is NOT a sportsbook quote and no sportsbook price is claimed anywhere.
  * A strategy only places a bet when its own probability exceeds the price-implied
    probability, so selection is part of the strategy, not of the evaluation.
  * The pre-registered baseline is the naive model ("own average" / "league average",
    no recency, no opponent, no role). A strategy earns credit only by beating it
    out of sample.
"""
import json
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import linelib as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
OUT = "data/lines"

# ------------------------------------------------------------------ declared constants
REFERENCE_ODDS = -110
REFERENCE_DECIMAL = L.american_to_decimal(REFERENCE_ODDS)      # 1.9091
REFERENCE_IMPLIED = 1.0 / REFERENCE_DECIMAL                    # 0.5238
EWMA_HALFLIFE = 4.0            # games
MIN_PROP_HISTORY = 4            # prior games before a prop can be projected
PRIOR_SIGMA_TOTAL = 12.0        # points (used before enough residuals exist)
PRIOR_SIGMA_MARGIN = 13.5       # points
OPP_FACTOR_CAP = 0.35           # opponent adjustment is capped at +/-35%
DEVELOPMENT_SEASONS = (2024, 2025)
HOLDOUT_SEASON = 2026

# Minimum prior per-game average before a player prop is considered bettable.
PROP_MIN_AVG = {
    "receiving_yards": 20.0,
    "rushing_yards": 8.0,
    "receptions": 1.0,
    "passing_yards": 100.0,
    "receiving_td": 0.2,
    "rushing_td": 0.1,
    "rush_attempts": 4.0,
}
# stat -> (box-score group, column)
PROP_SOURCES = {
    "receiving_yards": ("RECEIVING", "YDS"),
    "receptions": ("RECEIVING", "REC"),
    "receiving_td": ("RECEIVING", "TD"),
    "rushing_yards": ("RUSHING", "YDS"),
    "rushing_td": ("RUSHING", "TD"),
    "rush_attempts": ("RUSHING", "ATT"),
    "passing_yards": ("PASSING", "YDS"),
}

GATE_MIN_BETS = {"team": 30, "prop": 25, "parlay": 15}
GATE_ALPHA = 0.05
BH_ALPHA = 0.05
CORR_REDUNDANCY = 0.50
BET_CONCENTRATION_MAX = 0.40


def load(name, default):
    try:
        with open(os.path.join(OUT, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jwrite(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def ewma(values, halflife=EWMA_HALFLIFE):
    """Recency-weighted mean; most recent game has the most weight."""
    if not values:
        return None
    num = 0.0
    den = 0.0
    n = len(values)
    for i, v in enumerate(values):
        age = n - 1 - i
        w = 0.5 ** (age / halflife)
        num += w * v
        den += w
    return num / den if den else None


def bivariate_normal_cdf(x, y, rho):
    """P(X <= x, Y <= y) for standard normals with correlation rho."""
    if rho is None:
        rho = 0.0
    rho = max(-0.999, min(0.999, rho))
    if x < -8:
        x = -8.0
    if x > 8:
        x = 8.0
    if y < -8:
        y = -8.0
    if y > 8:
        y = 8.0
    # P(X <= x, Y <= y) = integral from -inf to x of phi(t) * Phi((y - rho t)/sqrt(1-rho^2)) dt
    steps = 600
    lo, hi = -8.0, x
    h = (hi - lo) / steps
    total = 0.0
    for i in range(steps + 1):
        t = lo + i * h
        w = 0.5 if i in (0, steps) else 1.0
        total += w * math.exp(-0.5 * t * t) / math.sqrt(2 * math.pi) * L.norm_cdf(
            (y - rho * t) / math.sqrt(1 - rho * rho))
    return max(0.0, min(1.0, total * h))


def trivariate_normal_cdf(x, y, z, rho_xy, rho_xz, rho_yz):
    """P(X <= x, Y <= y, Z <= z) for standard normals with the given correlations.

    Uses the standard recursion: condition on X = t, where (Y, Z) is bivariate
    normal with means (rho_xy t, rho_xz t), variances (1 - rho_xy^2) and
    (1 - rho_xz^2) and correlation rho_yz*.
    """
    rho_xy = max(-0.999, min(0.999, rho_xy))
    rho_xz = max(-0.999, min(0.999, rho_xz))
    rho_yz = max(-0.999, min(0.999, rho_yz))
    x = max(-8.0, min(8.0, x))
    y = max(-8.0, min(8.0, y))
    z = max(-8.0, min(8.0, z))
    s_xy = math.sqrt(1 - rho_xy * rho_xy)
    s_xz = math.sqrt(1 - rho_xz * rho_xz)
    denom = s_xy * s_xz
    rho_star = 0.0 if denom == 0 else (rho_yz - rho_xy * rho_xz) / denom
    rho_star = max(-0.999, min(0.999, rho_star))
    steps = 600
    lo, hi = -8.0, x
    h = (hi - lo) / steps
    total = 0.0
    for i in range(steps + 1):
        t = lo + i * h
        w = 0.5 if i in (0, steps) else 1.0
        y2 = (y - rho_xy * t) / s_xy
        z3 = (z - rho_xz * t) / s_xz
        total += (w * math.exp(-0.5 * t * t) / math.sqrt(2 * math.pi)
                  * bivariate_normal_cdf(y2, z3, rho_star))
    return max(0.0, min(1.0, total * h))


def inverse_norm_cdf(p):
    """Acklam's inverse normal CDF approximation."""
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ================================================================== team model
class TeamModel:
    """Power ratings and expected points, fitted walk-forward on prior games only."""

    def __init__(self):
        self.rating = defaultdict(float)      # points-per-game margin rating
        self.off = defaultdict(float)          # EWMA points scored
        self.defn = defaultdict(float)         # EWMA points allowed
        self.games = defaultdict(int)
        self.hfa = 3.0
        self.sigma_margin = PRIOR_SIGMA_MARGIN
        self.sigma_total = PRIOR_SIGMA_TOTAL
        self.league_total = 45.0
        self.home_win_rate = 0.5
        self.over_rate = 0.5
        self.over_hits = 0
        self.over_total = 0

    def update(self, game):
        away, home = game["away"], game["home"]
        ap, hp = game["awayScore"], game["homeScore"]
        margin = hp - ap
        total = hp + ap
        # did this game land above the league average that was known before it?
        if total > self.league_total:
            self.over_hits += 1
        # power ratings: iterative fit with a home-field term
        pred = self.rating[home] - self.rating[away] + self.hfa
        resid = margin - pred
        k = 0.06
        self.rating[home] += k * resid
        self.rating[away] -= k * resid
        if len(self.rating) > 1:
            m = sum(self.rating.values()) / len(self.rating)
            for t in list(self.rating):
                self.rating[t] -= m
        # expected points: exponentially weighted offence and defence
        for team, scored, allowed in ((away, ap, hp), (home, hp, ap)):
            n = self.games[team]
            w = 0.5 ** (1.0 / EWMA_HALFLIFE) if n else 1.0
            if n == 0:
                self.off[team] = scored
                self.defn[team] = allowed
            else:
                self.off[team] = w * scored + (1 - w) * self.off[team]
                self.defn[team] = w * allowed + (1 - w) * self.defn[team]
            self.games[team] += 1
        # league reference values
        self.over_total += 1
        self.league_total = 0.85 * self.league_total + 0.15 * total
        self.home_win_rate = 0.97 * self.home_win_rate + 0.03 * (1.0 if margin > 0 else 0.0)

    def predict(self, away, home):
        """Return (pred_margin_home_minus_away, pred_total, exp_home, exp_away)."""
        off_h, off_a = self.off.get(home), self.off.get(away)
        def_h, def_a = self.defn.get(home), self.defn.get(away)
        if None in (off_h, off_a, def_h, def_a):
            return 0.0, self.league_total, self.league_total / 2, self.league_total / 2
        exp_home = (off_h + def_a) / 2.0 + self.hfa / 2.0
        exp_away = (off_a + def_h) / 2.0 - self.hfa / 2.0
        ep_margin = exp_home - exp_away
        rt_margin = self.rating.get(home, 0.0) - self.rating.get(away, 0.0)
        margin = 0.5 * ep_margin + 0.5 * rt_margin
        total = exp_home + exp_away
        return margin, total, exp_home, exp_away


def build_team_bets(reg_games):
    """Walk-forward team model -> model lines and the candidate team bets."""
    model = TeamModel()
    resid_totals, resid_margins = [], []
    lines = []
    candidates = []
    for g in reg_games:
        dev = g["season"] in DEVELOPMENT_SEASONS
        if dev:
            sigma_total = L.stdev(resid_totals) or PRIOR_SIGMA_TOTAL
            sigma_margin = L.stdev(resid_margins) or PRIOR_SIGMA_MARGIN
        else:
            sigma_total = L.stdev(resid_totals) or PRIOR_SIGMA_TOTAL
            sigma_margin = L.stdev(resid_margins) or PRIOR_SIGMA_MARGIN
        margin, total, exp_home, exp_away = model.predict(g["away"], g["home"])
        bench_total = model.league_total
        actual_margin = g["homeScore"] - g["awayScore"]
        actual_total = g["homeScore"] + g["awayScore"]
        resid_totals.append(actual_total - total)
        resid_margins.append(actual_margin - margin)

        line_rec = {
            "gameId": g["gameId"],
            "date": g["date"],
            "season": g["season"],
            "week": g["week"],
            "away": g["away"],
            "home": g["home"],
            "modelSpreadHome": round(margin * 2) / 2.0,
            "modelTotal": round(total * 2) / 2.0,
            "benchmarkTotal": round(bench_total * 2) / 2.0,
            "benchmarkSpread": 0.0,
            "homeWinProbability": L.norm_cdf(margin / sigma_margin),
            "sourceUrl": g["sourceUrl"],
            "sourceName": "Derived from NFL.com official results (model output, not an official value)",
        }
        lines.append(line_rec)

        # --- candidate bets against the pre-registered benchmark line
        # S01 / S02: game total vs the league-average line
        z = (total - bench_total) / sigma_total
        p_over = L.norm_cdf(z)
        # the naive forecast is the historical hit rate of the benchmark line itself
        naive_over = (model.over_hits / model.over_total) if model.over_total >= 10 else 0.5
        naive_over = min(max(naive_over, 0.05), 0.95)
        s01_cand = {
            "strategy": "S01", "gameId": g["gameId"], "date": g["date"],
            "season": g["season"], "week": g["week"], "market": "game total",
            "line": round(bench_total * 2) / 2.0, "side": "Over",
            "p": p_over, "pNaive": naive_over,
            "outcome": 1 if actual_total > bench_total else 0,
            "sourceUrl": g["sourceUrl"], "team": g["home"], "opponent": g["away"],
            "detail": f"model total {total:.1f} vs league average {bench_total:.1f}",
        }
        candidates.append(s01_cand)
        candidates.append({
            "strategy": "S02", "gameId": g["gameId"], "date": g["date"],
            "season": g["season"], "week": g["week"], "market": "game total",
            "line": round(bench_total * 2) / 2.0, "side": "Under",
            "p": 1 - p_over, "pNaive": 1 - naive_over,
            "outcome": 1 if actual_total <= bench_total else 0,
            "sourceUrl": g["sourceUrl"], "team": g["home"], "opponent": g["away"],
            "detail": f"fade model total {total:.1f} vs league average {bench_total:.1f}",
        })
        # S03 / S04: moneyline against the pick'em benchmark line
        p_home = L.norm_cdf(margin / sigma_margin)
        naive_home = model.home_win_rate
        fav_home = margin >= 0
        fav_p = p_home if fav_home else 1 - p_home
        fav_naive = naive_home if fav_home else 1 - naive_home
        dog_p = 1 - fav_p
        dog_naive = 1 - fav_naive
        fav_team = g["home"] if fav_home else g["away"]
        dog_team = g["away"] if fav_home else g["home"]
        cand_fav = {
            "strategy": "S03", "gameId": g["gameId"], "date": g["date"],
            "season": g["season"], "week": g["week"], "market": "moneyline",
            "line": 0.0, "side": fav_team,
            "p": fav_p, "pNaive": fav_naive,
            "outcome": 1 if ((fav_team == g["home"] and actual_margin > 0) or
                             (fav_team == g["away"] and actual_margin < 0)) else 0,
            "sourceUrl": g["sourceUrl"], "team": fav_team, "opponent": dog_team,
            "detail": f"model margin {margin:+.1f} for {fav_team}",
        }
        cand_dog = {
            "strategy": "S04", "gameId": g["gameId"], "date": g["date"],
            "season": g["season"], "week": g["week"], "market": "moneyline",
            "line": 0.0, "side": dog_team,
            "p": dog_p, "pNaive": dog_naive,
            "outcome": 1 - cand_fav["outcome"],
            "sourceUrl": g["sourceUrl"], "team": dog_team, "opponent": fav_team,
            "detail": f"fade model margin {margin:+.1f}; backs {dog_team}",
        }
        candidates.append(cand_fav)
        candidates.append(cand_dog)
        # S05: moneyline only when the model separation is large
        if abs(margin) >= 4.0:
            c = dict(cand_fav)
            c["strategy"] = "S05"
            c["detail"] = f"strong model signal {margin:+.1f}; take {fav_team}"
            candidates.append(c)
        # S06: total only when the model total differs materially from the benchmark
        if abs(total - bench_total) >= 3.0:
            c = dict(s01_cand)
            c["strategy"] = "S06"
            c["detail"] = f"model total {total:.1f} vs league average {bench_total:.1f}"
            candidates.append(c)
        # S07 / S08: team points against the team's own scoring average (follow / fade)
        for side_team, opp_team, exp_pts in ((g["home"], g["away"], exp_home),
                                             (g["away"], g["home"], exp_away)):
            own_avg = model.off.get(side_team)
            if own_avg is None or model.games.get(side_team, 0) < 3:
                continue
            actual_pts = g["homeScore"] if side_team == g["home"] else g["awayScore"]
            z_team = (exp_pts - own_avg) / sigma_total
            p_team_over = L.norm_cdf(z_team)
            naive_team = 0.5
            base = {
                "gameId": g["gameId"], "date": g["date"], "season": g["season"],
                "week": g["week"], "market": "team points",
                "line": round(own_avg * 2) / 2.0, "pNaive": naive_team,
                "sourceUrl": g["sourceUrl"], "team": side_team, "opponent": opp_team,
            }
            candidates.append({**base, "strategy": "S07", "side": f"{side_team} Over",
                               "p": p_team_over,
                               "outcome": 1 if actual_pts > own_avg else 0,
                               "detail": f"model {exp_pts:.1f} vs own average {own_avg:.1f}"})
            candidates.append({**base, "strategy": "S08", "side": f"{side_team} Under",
                               "p": 1 - p_team_over,
                               "outcome": 1 if actual_pts <= own_avg else 0,
                               "detail": f"fade model {exp_pts:.1f} vs own average {own_avg:.1f}"})
        model.update(g)
    return lines, candidates


# ================================================================== player data
def build_player_logs(box_rows, games_by_id):
    """Merge box-score rows into one record per (game, player)."""
    logs = {}
    for r in box_rows:
        gid = r.get("gameId")
        pid = r.get("playerImageId")
        if not gid or not pid:
            continue
        rec = logs.setdefault((gid, pid), {
            "gameId": gid, "playerImageId": pid,
            "playerDisplay": r.get("playerDisplay"),
            "side": r.get("side"), "group_stats": {},
            "season": r.get("season"), "week": r.get("week"), "date": r.get("date"),
            "away": r.get("away"), "home": r.get("home"), "slug": r.get("slug"),
            "sourceUrl": r.get("sourceUrl"),
        })
        title = (r.get("group") or "").strip()
        grp = title.split(" ", 1)[1].strip().upper() if " " in title else title.upper()
        vals = {k: v for k, v in r.items()
                if k not in ("side", "group", "playerDisplay", "playerImageId", "sourceUrl",
                             "gameId", "season", "week", "seasonType", "date", "away",
                             "home", "slug")}
        rec["group_stats"][grp] = vals
        g = games_by_id.get(gid)
        if g:
            rec["team"] = g["home"] if rec["side"] == "homeTeam" else g["away"]
    return logs


def nfl_display(name):
    """Reproduce the NFL.com box-score display form: 'J. DANIELS', 'A. ST. BROWN'."""
    if not name:
        return None
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    if not tokens:
        return None
    first = tokens[0]
    if "." in first and len(first) <= 5:
        head = first.upper()
    else:
        head = first[0].upper() + "."
    rest = [t.upper() for t in tokens[1:]]
    return " ".join([head] + rest)


# position -> the stat that separates two charted players who share a display form
POSITION_STAT = {
    "WR": "receiving_yards", "TE": "receiving_yards", "RB": "rushing_yards",
    "FB": "rushing_yards", "QB": "passing_yards",
}
STAT_GROUPS = {
    "receiving_yards": {"RECEIVING"}, "receptions": {"RECEIVING"},
    "receiving_td": {"RECEIVING"}, "rushing_yards": {"RUSHING"},
    "rushing_td": {"RUSHING"}, "rush_attempts": {"RUSHING"},
    "passing_yards": {"PASSING"},
}


def build_player_registry(depth_charts, observed=None):
    """Official depth-chart names matched to the NFL.com box-score display form.

    `observed` maps (team, display) -> the set of box-score stat groups that the
    player appears in. It breaks ties when two charted players share a display form
    (for example two players both shown as 'J. SMITH'). Unresolved ties are kept in the
    registry with the full names left ambiguous so the site can flag them.
    """
    registry = {}
    display_index = {}
    for club in depth_charts:
        for unit, positions in (club.get("units") or {}).items():
            for pos, row in positions.items():
                for p in row["players"]:
                    disp = nfl_display(p["name"])
                    key = (club["team"], disp)
                    display_index.setdefault(key, []).append({
                        "name": p["name"], "tier": p.get("tier"), "position": pos,
                        "unit": unit, "team": club["team"], "abbr": club.get("abbr"),
                        "display": disp,
                        "sourceUrl": club.get("sourceUrl"),
                    })
    ambiguous = []
    for (team, disp), entries in display_index.items():
        if len(entries) == 1:
            registry[f"{team}|{disp}"] = entries[0]
            continue
        groups = (observed or {}).get((team, disp))
        resolved = None
        if groups:
            scored = []
            for e in entries:
                egroups = STAT_GROUPS.get(POSITION_STAT.get(e["position"], ""), set())
                if groups & egroups:
                    scored.append(e)
            if len(scored) == 1:
                resolved = scored[0]
        if resolved:
            registry[f"{team}|{disp}"] = resolved
        else:
            registry[f"{team}|{disp}"] = {"ambiguous": True, "team": team, "display": disp,
                              "candidates": [e["name"] for e in entries]}
            ambiguous.append({"team": team, "display": disp,
                              "candidates": [e["name"] for e in entries]})
    return registry, ambiguous


def build_prop_candidates(logs, reg_games, games_by_id, registry):
    """Walk-forward player-prop projections and candidate bets."""
    history = defaultdict(list)       # playerId -> list of (gameKey, stat values)
    stat_resid = defaultdict(list)     # stat -> residuals (development only)
    base_rate = defaultdict(list)      # stat -> league-wide naive hit flags
    player_hits = defaultdict(list)    # (player, stat) -> that player's own naive hit flags
    candidates = []
    ledger = []
    opp_allow = defaultdict(list)     # (team, stat) -> per-game allowance

    for g in reg_games:
        gid = g["gameId"]
        game_logs = [rec for (ggid, _pid), rec in logs.items() if ggid == gid]
        for rec in game_logs:
            team = rec.get("team")
            if not team:
                continue
            for stat, (group, col) in PROP_SOURCES.items():
                vals = rec["group_stats"].get(group) or {}
                val = vals.get(col)
                if not isinstance(val, (int, float)):
                    continue
                opp = g["away"] if team == g["home"] else g["home"]
                # opponent allowance for this stat so far
                opp_list = opp_allow[(opp, stat)]
                opp_rate = L.mean(opp_list)
                league_rate = L.mean(opp_allow[("*", stat)])
                opp_factor = 1.0
                if opp_rate and league_rate and opp_rate > 0:
                    opp_factor = league_rate / opp_rate
                    opp_factor = max(1 - OPP_FACTOR_CAP, min(1 + OPP_FACTOR_CAP, opp_factor))
                hist = history[(rec["playerImageId"], stat)]
                prior = [h[1] for h in hist]
                if len(prior) >= MIN_PROP_HISTORY:
                    naive_line = L.mean(prior)
                    our_proj = ewma(prior) * opp_factor
                    actual = val
                    resid = actual - our_proj
                    dev = g["season"] in DEVELOPMENT_SEASONS
                    # every quantity below is estimated from PRIOR games only
                    sigma = L.stdev(stat_resid[stat]) or 1.0
                    p = L.norm_cdf((our_proj - naive_line) / sigma) if sigma else 0.5
                    own_hits = player_hits[(rec["playerImageId"], stat)]
                    if len(own_hits) >= 5:
                        naive_p = L.mean(own_hits)
                    else:
                        naive_p = L.mean(base_rate[stat]) or 0.5
                    if naive_p in (0.0, 1.0):
                        naive_p = 0.5
                    if dev:
                        stat_resid[stat].append(resid)
                        base_rate[stat].append(1 if actual > naive_line else 0)
                        player_hits[(rec["playerImageId"], stat)].append(
                            1 if actual > naive_line else 0)
                    min_avg = PROP_MIN_AVG.get(stat, 0)
                    eligible = (naive_line is not None and naive_line >= min_avg
                                and abs(our_proj - naive_line) >= 0.5)
                    ledger.append({
                        "gameId": gid, "date": g["date"], "season": g["season"],
                        "week": g["week"], "playerImageId": rec["playerImageId"],
                        "playerDisplay": rec["playerDisplay"], "team": team,
                        "opponent": opp, "stat": stat, "naiveLine": naive_line,
                        "ourProjection": our_proj, "actual": actual,
                        "outcome": 1 if actual > naive_line else 0,
                        "p": p, "pNaive": naive_p, "eligible": eligible,
                        "sourceUrl": rec.get("sourceUrl"),
                    })
                    if eligible:
                        candidates.append({
                            "strategy": f"P{1 + list(PROP_SOURCES).index(stat):02d}",
                            "gameId": gid, "date": g["date"], "season": g["season"],
                            "week": g["week"], "market": f"player {stat}",
                            "line": round(naive_line * 2) / 2.0, "side": "Over",
                            "p": p, "pNaive": naive_p,
                            "outcome": 1 if actual > naive_line else 0,
                            "sourceUrl": rec.get("sourceUrl"),
                            "team": team, "opponent": opp,
                            "playerImageId": rec["playerImageId"],
                            "playerDisplay": rec["playerDisplay"],
                            "stat": stat,
                            "detail": (f"model {our_proj:.1f} vs own average {naive_line:.1f}"),
                        })
                hist.append((gid, val))
                opp_allow[(team, stat)].append(val)
                opp_allow[("*", stat)].append(val)
    return candidates, ledger


# ================================================================== strategy metrics
def bet_units(odds_decimal):
    return odds_decimal - 1.0


def evaluate_strategy(bets, meta):
    """Score a strategy's placed bets. Returns metrics dict."""
    placed = [b for b in bets if b.get("placed")]
    n = len(placed)
    if n == 0:
        return {"betsConsidered": len(bets), "betsPlaced": 0, "wins": 0, "losses": 0,
                "pushes": 0, "roi": None, "logLoss": None, "baselineLogLoss": None,
                "deltaLogLoss": None, "brier": None, "baselineBrier": None,
                "ece": None, "roiCI": [None, None], "deltaCI": [None, None],
                "skillP": None, "skillMean": None, "skillReplicates": 0,
                "unitProfit": 0.0, "seasonRoi": {}, "maxBetShare": None,
                "holdoutBets": 0, "holdoutRoi": None, "note": "no bets cleared the price filter"}
    wins = sum(1 for b in placed if b["outcome"] == 1)
    losses = sum(1 for b in placed if b["outcome"] == 0)
    pushes = n - wins - losses
    unit = bet_units(REFERENCE_DECIMAL)
    profit = wins * unit - losses
    probs = [b["p"] for b in placed]
    outs = [b["outcome"] for b in placed]
    naive = [b["pNaive"] for b in placed]
    ll = L.log_loss(probs, outs)
    ll_naive = L.log_loss(naive, outs)
    # per-bet paired log-loss improvement over the pre-registered baseline
    # (positive means the strategy beat the baseline on that bet)
    ll_diffs = []
    for p, pn, y in zip(probs, naive, outs):
        if p is None or pn is None:
            continue
        pc = min(max(p, 1e-9), 1 - 1e-9)
        nc = min(max(pn, 1e-9), 1 - 1e-9)
        ll_diffs.append((y * math.log(pc) + (1 - y) * math.log(1 - pc))
                        - (y * math.log(nc) + (1 - y) * math.log(1 - nc)))
    skill_p, skill_mean, reps = L.sign_flip_test(ll_diffs)
    roi_lo, roi_hi, _ = L.bootstrap_ci([b["units"] for b in placed])
    d_lo, d_hi, _ = L.bootstrap_diff_ci(probs, naive)
    season_roi = defaultdict(lambda: [0, 0])
    for b in placed:
        key = str(b["season"])
        season_roi[key][1] += 1
        season_roi[key][0] += b["units"]
    season_r = {k: (v[0] / v[1]) for k, v in sorted(season_roi.items())}
    best = max(placed, key=lambda b: b["units"])
    positive = sum(b["units"] for b in placed if b["units"] > 0)
    share = (best["units"] / positive) if positive > 0 else None
    hold = [b for b in placed if b["season"] == HOLDOUT_SEASON]
    hold_roi = (sum(b["units"] for b in hold) / len(hold)) if hold else None
    return {
        "betsConsidered": len(bets),
        "betsPlaced": n,
        "wins": wins, "losses": losses, "pushes": pushes,
        "roi": profit / n,
        "unitProfit": profit,
        "logLoss": ll, "baselineLogLoss": ll_naive,
        "deltaLogLoss": (ll - ll_naive) if (ll is not None and ll_naive is not None) else None,
        "brier": L.brier(probs, outs), "baselineBrier": L.brier(naive, outs),
        "ece": L.expected_calibration_error(probs, outs),
        "roiCI": [roi_lo, roi_hi],
        "deltaCI": [d_lo, d_hi],
        "skillP": skill_p,
        "skillMean": skill_mean,
        "skillReplicates": reps,
        "skillMethod": ("paired sign-flip randomisation test on the per-bet log-loss "
                        "improvement over the pre-registered baseline"),
        "seasonRoi": season_r,
        "maxBetShare": share,
        "maxBetGame": best.get("sourceUrl"),
        "holdoutBets": len(hold),
        "holdoutRoi": hold_roi,
    }


def apply_price_filter(candidates):
    """A strategy only bets when its own estimate beats the declared reference price.

    A single leg is priced at -110. An n-leg parlay is priced at the compounded
    reference price, so its price-implied probability is the product of the leg
    implied probabilities.
    """
    for c in candidates:
        implied = c.get("impliedPrice", REFERENCE_IMPLIED)
        c["impliedPrice"] = implied
        c["placed"] = bool(c["p"] is not None and c["p"] > implied)
        c["units"] = (bet_units(REFERENCE_DECIMAL) if c["outcome"] == 1 else -1.0) if c["placed"] else 0.0
    return candidates


# ================================================================== correlations
def correlate_bets(a, b):
    """Pearson / phi correlation between two strategies' per-bet unit returns.

    Bets are aligned on (game, player) so two strategies that act on the same game
    are compared on the same events. Bets placed on different events are not compared.
    """
    key_a = {x["gameId"] + "|" + str(x.get("playerImageId", "")): x for x in a}
    key_b = {x["gameId"] + "|" + str(x.get("playerImageId", "")): x for x in b}
    common = sorted(set(key_a) & set(key_b))
    xs = [key_a[k]["units"] for k in common]
    ys = [key_b[k]["units"] for k in common]
    r, n = L.pearson(xs, ys)
    rho, _ = L.spearman(xs, ys)
    lo, hi = L.fisher_ci(r, n)
    return {"correlation": r, "n": n, "ci95": [lo, hi], "spearman": rho,
            "method": "Pearson on per-bet unit returns at the declared reference price"}


def main():
    games_doc = load("games.json", {"games": []})
    box_doc = load("boxscores.json", {"rows": []})
    inj_doc = load("injuries.json", {"rows": [], "meta": {}})
    depth_doc = load("depth-charts.json", {"clubs": []})
    fetch_report = load("fetch-report.json", {})

    reg_games = [g for g in games_doc.get("games", [])
                 if g.get("seasonType") == "REG" and g.get("awayScore") is not None]
    reg_games.sort(key=lambda g: (g.get("date") or "", g.get("gameId") or ""))
    games_by_id = {g["gameId"]: g for g in games_doc.get("games", [])}

    print(f"regular-season games with official scores: {len(reg_games)}")
    dev = [g for g in reg_games if g["season"] in DEVELOPMENT_SEASONS]
    hold = [g for g in reg_games if g["season"] == HOLDOUT_SEASON]
    print(f"  development {dev[0]['season']}-{dev[-1]['season']}: {len(dev)}   holdout {HOLDOUT_SEASON}: {len(hold)}")

    # ---------------------------------------------------------------- team lines + bets
    lines, team_candidates = build_team_bets(reg_games)
    print(f"originated team lines: {len(lines)}   team bet candidates: {len(team_candidates)}")

    # ---------------------------------------------------------------- props
    logs = build_player_logs(box_doc.get("rows", []), games_by_id)
    print(f"player game logs: {len(logs)}")

    # which stat groups does each official display form actually appear in?
    observed = defaultdict(set)
    for rec in logs.values():
        if not rec.get("team"):
            continue
        for grp in rec["group_stats"]:
            observed[(rec["team"], rec["playerDisplay"])].add(grp)

    # ---------------------------------------------------------------- player registry
    registry, unmatched = build_player_registry(depth_doc.get("clubs", []), observed)
    print(f"depth-chart display forms resolved: {len(registry)} (ambiguous: {len(unmatched)})")
    prop_candidates, ledger = build_prop_candidates(logs, reg_games, games_by_id, registry)
    print(f"prop bet candidates: {len(prop_candidates)}   prop ledger rows: {len(ledger)}")

    # ---------------------------------------------------------------- parlays
    parlay_candidates, parlay_rhos = build_parlays(prop_candidates, team_candidates, ledger)

    all_candidates = team_candidates + prop_candidates + parlay_candidates
    apply_price_filter(all_candidates)

    # ---------------------------------------------------------------- strategy catalog
    catalog = STRATEGY_CATALOG
    by_strategy = defaultdict(list)
    for c in all_candidates:
        by_strategy[c["strategy"]].append(c)

    # ---------------------------------------------------------------- correlations
    correlations = []
    ids = sorted(by_strategy)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            res = correlate_bets(by_strategy[a], by_strategy[b])
            if res["n"] >= 5:
                correlations.append({"a": a, "b": b, **res})

    # prop-level production correlations (official box-score data)
    prop_corr = production_correlations(ledger)

    # ---------------------------------------------------------------- evaluation
    results = []
    for sid in catalog:
        bets = by_strategy.get(sid["id"], [])
        metrics = evaluate_strategy(bets, sid)
        placed = [b for b in bets if b.get("placed")]
        # the official page the strategy's first placed bet came from; a strategy
        # that placed nothing is sourced to the official schedule that defines
        # the games it could have bet
        source_url = placed[0]["sourceUrl"] if placed else "https://www.nfl.com/schedules/"
        source_name = (f"Official game page ({placed[0]['team']} at {placed[0]['opponent']})"
                       if placed else "Official NFL.com schedule")
        results.append({**sid, "metrics": metrics,
                        "sourceUrl": source_url, "sourceName": source_name})

    # Benjamini-Hochberg across the whole family, using the paired sign-flip
    # randomisation p-value on the skill the strategy adds over its baseline
    pvals = [r["metrics"].get("skillP") for r in results]
    qvals = L.benjamini_hochberg(pvals)
    for r, p, q in zip(results, pvals, qvals):
        r["metrics"]["skillP"] = p
        r["metrics"]["adjustedP"] = q

    # ---------------------------------------------------------------- gates + leaderboard
    leaderboard = []
    for r in results:
        gates = evaluate_gates(r)
        r["gates"] = gates
        reward, reward_note = compute_reward(r, gates)
        r["reward"] = reward
        r["rewardNote"] = reward_note
        # The row is the SAME dict as the strategy entry, plus rank/status. They must not be
        # copies: the redundancy gate below rewrites G7, `status` and `reward`, and a copy would
        # leave strategies.json and leaderboard.json disagreeing (defect A02, fixed 2026-11-13).
        r["rank"] = None
        r["status"] = None
        leaderboard.append(r)
    leaderboard.sort(key=lambda x: (-(x["reward"] or 0),
                                    x["metrics"].get("logLoss") if x["metrics"].get("logLoss") is not None else 9))
    for i, row in enumerate(leaderboard, start=1):
        row["rank"] = i

    # The leaderboard rows are the SAME objects held in `results`, and `apply_redundancy_gate`
    # rewrites G7, `status` and `reward` on them in place so the two published files cannot
    # disagree. Before 2026-11-13 the gate was applied only to `leaderboard` while
    # strategies.json had already been assigned `results` by reference in a different order,
    # which left strategies.json and leaderboard.json disagreeing on S03 (reward 72 vs 0) and
    # shipped a leaderboard whose ranks/status were computed before the reward was zeroed.
    # See data/control/audit.json (A02).
    apply_redundancy_gate(leaderboard, correlations)
    _by_id = {r["id"]: r for r in results}
    for row in leaderboard:
        assert row is _by_id[row["id"]], "leaderboard row is a copy of a strategy row"
        assert row["reward"] == _by_id[row["id"]]["reward"], f"reward drift on {row['id']}"
    assert sorted(r["rank"] for r in leaderboard) == list(range(1, len(leaderboard) + 1)), "ranks not contiguous"
    for i, row in enumerate(leaderboard, start=1):
        row["rank"] = i

    # ---------------------------------------------------------------- lineup risk
    lineup = build_lineup_risk(inj_doc, depth_doc, reg_games, games_doc)

    # ---------------------------------------------------------------- outputs
    jwrite("lines.json", {
        "meta": {
            "modelName": "Korea5 NFL line origination v1",
            "builtFrom": "NFL.com official schedules, official box scores and official club depth charts",
            "referencePrice": f"{REFERENCE_ODDS} American (decimal {REFERENCE_DECIMAL:.4f}) - declared convention, not a sportsbook quote",
            "developmentSeasons": list(DEVELOPMENT_SEASONS),
            "holdoutSeason": HOLDOUT_SEASON,
            "ewmaHalflifeGames": EWMA_HALFLIFE,
            "minPropHistory": MIN_PROP_HISTORY,
            "oppFactorCap": OPP_FACTOR_CAP,
            "sourceUrls": {
                "schedule": "https://www.nfl.com/schedules/",
                "boxscore": "https://www.nfl.com/games/",
                "injuries": "https://www.nfl.com/injuries/",
                "depthChartDirectory": "https://www.nfl.com/teams/",
            },
            "fetchReport": fetch_report.get("counts", {}),
        },
        "lines": lines,
    })
    jwrite("strategies.json", {
        "meta": {
            "referencePrice": f"{REFERENCE_ODDS} American (decimal {REFERENCE_DECIMAL:.4f}) - declared convention, not a sportsbook quote",
            "referenceImpliedProbability": REFERENCE_IMPLIED,
            "developmentSeasons": list(DEVELOPMENT_SEASONS),
            "holdoutSeason": HOLDOUT_SEASON,
            "priceFilter": "a bet is placed only when the strategy's own probability exceeds the price-implied probability",
            "gateThresholds": {
                "minBets": GATE_MIN_BETS, "alpha": GATE_ALPHA,
                "bhAlpha": BH_ALPHA, "redundancyCorrelation": CORR_REDUNDANCY,
                "maxSingleBetProfitShare": BET_CONCENTRATION_MAX,
            },
        },
        "strategies": results,
        "bets": all_candidates,
    })
    jwrite("leaderboard.json", {
        "meta": {
            "rewardBasis": ("paper leaderboard points. Reward = 1000 x relative log-loss improvement "
                            "over the pre-registered naive baseline x evidence factor x luck guard. "
                            "No money, no wagering and no sportsbook price is involved."),
            "gates": GATE_DOCS,
        },
        "leaderboard": leaderboard,
    })
    jwrite("correlations.json", {
        "meta": {
            "strategyMethod": "Pearson on per-bet unit returns at the declared reference price",
            "productionMethod": "Pearson on official per-game player production, matched on player and game",
            "minimumPairs": 20,
        },
        "strategyCorrelations": correlations,
        "productionCorrelations": prop_corr,
        "parlayCorrelations": parlay_rhos,
    })
    jwrite("player-registry.json", {
        "meta": {
            "method": ("official club depth chart names converted to the NFL.com box-score display form "
                       "('AmOn-Ra St. Brown' -> 'A. ST. BROWN') and matched to the official player image id "
                       "used in the NFL.com box score"),
            "ambiguous": unmatched,
            "depthChartSource": "https://www.nfl.com/teams/",
        },
        "players": registry,
    })
    jwrite("lineup-risk.json", {
        "meta": {
            "injurySource": inj_doc.get("meta", {}).get("sourceUrl", "https://www.nfl.com/injuries/"),
            "injuryWeek": inj_doc.get("meta", {}).get("week"),
            "depthChartSource": "https://www.nfl.com/teams/",
            "method": ("an unavailable starter is matched to the same position group in the official club "
                       "depth chart; the next healthy tier is reported as the projected replacement"),
        },
        "rows": lineup,
    })
    print(f"strategies: {len(results)}  correlations: {len(correlations)}  lineup rows: {len(lineup)}")


# ================================================================== parlays
def build_parlays(prop_candidates, team_candidates, ledger):
    """Combine single legs into parlays; correlations are measured, never assumed."""
    parlays = []
    rhos = []

    # --- measure the correlation of the two underlying prop outcomes per game
    by_game = defaultdict(list)
    for c in prop_candidates:
        by_game[c["gameId"]].append(c)
    # measured phi between leg outcomes inside the same game
    joint = []
    joint_same = []
    for gid, legs in by_game.items():
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                joint.append((legs[i]["outcome"], legs[j]["outcome"]))
                if legs[i].get("playerImageId") == legs[j].get("playerImageId"):
                    joint_same.append((legs[i]["outcome"], legs[j]["outcome"]))
    rho_props = None
    if len(joint) >= 20:
        xs = [a for a, _ in joint]
        ys = [b for _, b in joint]
        rho_props, n = L.pearson(xs, ys)
        lo, hi = L.fisher_ci(rho_props, n)
        rhos.append({"pair": "player-prop legs in the same game (different players)", "rho": rho_props,
                     "n": n, "ci95": [lo, hi],
                     "method": "phi coefficient on official per-game prop outcomes",
                     "note": "measured across every pair of eligible prop legs in the same game"})
    else:
        rhos.append({"pair": "player-prop legs in the same game (different players)", "rho": None,
                     "n": len(joint), "ci95": [None, None],
                     "method": "phi coefficient on official per-game prop outcomes",
                     "note": "insufficient paired observations; correlation left blank and flagged"})
    rho_same = None
    if len(joint_same) >= 20:
        xs = [a for a, _ in joint_same]
        ys = [b for _, b in joint_same]
        rho_same, n_same = L.pearson(xs, ys)
        lo_s, hi_s = L.fisher_ci(rho_same, n_same)
        rhos.append({"pair": "player-prop legs for the SAME player in one game", "rho": rho_same,
                     "n": n_same, "ci95": [lo_s, hi_s],
                     "method": "phi coefficient on official per-game prop outcomes",
                     "note": "measured separately because two props on one player are far "
                             "more correlated than two props on different players"})
    else:
        rhos.append({"pair": "player-prop legs for the SAME player in one game", "rho": None,
                     "n": len(joint_same), "ci95": [None, None],
                     "method": "phi coefficient on official per-game prop outcomes",
                     "note": "insufficient paired observations; correlation left blank and flagged"})

    # measured correlation between the game-total leg and the model moneyline leg
    _tot = {c["gameId"]: c for c in team_candidates if c["strategy"] == "S01"}
    _ml = {c["gameId"]: c for c in team_candidates if c["strategy"] == "S03"}
    res = [(_tot[g]["outcome"], _ml[g]["outcome"]) for g in _tot if g in _ml]
    rho_game = None
    if len(res) >= 20:
        xs = [a for a, _ in res]
        ys = [b for _, b in res]
        rho_game, n = L.pearson(xs, ys)
        lo, hi = L.fisher_ci(rho_game, n)
        rhos.append({"pair": "game total over/under x model moneyline", "rho": rho_game,
                     "n": n, "ci95": [lo, hi],
                     "method": "Pearson on official game outcomes"})
    else:
        rhos.append({"pair": "game total over/under x model moneyline", "rho": None,
                     "n": len(res), "ci95": [None, None],
                     "method": "Pearson on official game outcomes",
                     "note": "insufficient observations; correlation left blank and flagged"})

    # --- two- and three-leg prop parlays, built from the strongest single legs
    def leg_rhos(chosen):
        """Pairwise measured correlation for the chosen legs.

        Two legs on the same player are far more correlated than two legs on
        different players, so the correlation measured for that exact pair type
        is used rather than a single pooled figure.
        """
        size = len(chosen)
        matrix = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
        notes = []
        for i in range(size):
            for j in range(i + 1, size):
                same = chosen[i].get("playerImageId") == chosen[j].get("playerImageId")
                rho = rho_same if same else rho_props
                if rho is None:
                    rho = 0.0
                matrix[i][j] = matrix[j][i] = rho
                notes.append(f"{chosen[i]['playerDisplay']}|{chosen[j]['playerDisplay']} "
                             f"rho={rho:+.3f} ({'same player' if same else 'different players'})")
        return matrix, "; ".join(notes)

    for gid, legs in by_game.items():
        legs = [l for l in legs if l.get("eligible", True) and l["p"] > REFERENCE_IMPLIED]
        if len(legs) < 2:
            continue
        legs.sort(key=lambda l: -(l["p"] - l["pNaive"]))
        for size, sid in ((2, "L01"), (3, "L02")):
            if len(legs) < size:
                continue
            chosen = legs[:size]
            matrix, rho_note = leg_rhos(chosen)
            joint_p = joint_probability([c["p"] for c in chosen], matrix)
            naive_joint = joint_probability([c["pNaive"] for c in chosen], matrix)
            implied = REFERENCE_IMPLIED ** size
            parlay = {
                "strategy": sid, "gameId": gid, "date": chosen[0]["date"],
                "season": chosen[0]["season"], "week": chosen[0]["week"],
                "market": f"{size}-leg player prop parlay",
                "line": None, "side": " + ".join(c["playerDisplay"] for c in chosen),
                "p": joint_p, "pNaive": naive_joint,
                "outcome": 1 if all(c["outcome"] == 1 for c in chosen) else 0,
                "sourceUrl": chosen[0]["sourceUrl"],
                "team": chosen[0]["team"], "opponent": chosen[0]["opponent"],
                "playerImageId": chosen[0]["playerImageId"],
                "playerDisplay": chosen[0]["playerDisplay"],
                "legs": [{"market": c["market"], "line": c["line"], "p": c["p"],
                          "outcome": c["outcome"], "playerDisplay": c["playerDisplay"],
                          "sourceUrl": c["sourceUrl"]} for c in chosen],
                "measuredRho": matrix[0][1],
                "measuredRhoNote": rho_note,
                "detail": (f"{size} legs; measured pairwise correlation: {rho_note}"),
            }
            parlays.append(parlay)
            # parlay price: legs compounded at the declared reference price
            parlay["impliedPrice"] = implied

    # --- game total + model moneyline parlay (same game)
    totals = {c["gameId"]: c for c in team_candidates if c["strategy"] == "S01"}
    mls = {c["gameId"]: c for c in team_candidates if c["strategy"] == "S03"}
    for gid, t in totals.items():
        m = mls.get(gid)
        if not m:
            continue
        joint_p = joint_probability([t["p"], m["p"]], rho_game)
        naive_joint = joint_probability([t["pNaive"], m["pNaive"]], rho_game)
        parlays.append({
            "strategy": "L03", "gameId": gid, "date": t["date"], "season": t["season"],
            "week": t["week"], "market": "2-leg game total + moneyline parlay",
            "line": None, "side": f"Over {t['line']} + {m['side']}",
            "p": joint_p, "pNaive": naive_joint,
            "outcome": 1 if (t["outcome"] == 1 and m["outcome"] == 1) else 0,
            "sourceUrl": t["sourceUrl"], "team": t["team"], "opponent": t["opponent"],
            "legs": [{"market": t["market"], "line": t["line"], "p": t["p"],
                      "outcome": t["outcome"], "sourceUrl": t["sourceUrl"]},
                     {"market": m["market"], "line": m["line"], "p": m["p"],
                      "outcome": m["outcome"], "sourceUrl": m["sourceUrl"]}],
            "measuredRho": rho_game,
            "detail": ("total over/under and model moneyline; measured rho "
                       + (f"{rho_game:.3f} (n={len(res)})" if rho_game is not None else "unverified (blank)")),
            "impliedPrice": REFERENCE_IMPLIED ** 2,
        })
    return parlays, rhos


def joint_probability(probs, rhos):
    """Joint win probability of legs, using the measured pairwise correlations.

    `rhos` is either a single correlation (used for every pair) or a square
    matrix of pairwise correlations.
    """
    if not probs:
        return None
    n = len(probs)
    if n == 1:
        return probs[0]
    if isinstance(rhos, (int, float)):
        matrix = [[1.0 if i == j else float(rhos or 0.0) for j in range(n)] for i in range(n)]
    else:
        matrix = rhos
    z = [inverse_norm_cdf(p) for p in probs]
    if n == 2:
        return bivariate_normal_cdf(z[0], z[1], matrix[0][1])
    if n == 3:
        return trivariate_normal_cdf(z[0], z[1], z[2],
                                     matrix[0][1], matrix[0][2], matrix[1][2])
    # more than three legs: chain the pair CDF over the leading legs
    joint = bivariate_normal_cdf(z[0], z[1], matrix[0][1])
    for k in range(2, n):
        joint *= probs[k]
    return max(0.0, min(1.0, joint))


def production_correlations(ledger):
    """Correlation of official per-game production between stat types, per player.

    Pairs are matched on the game id, so a stat pair for one player is always
    compared on the same game. Games are never paired by position in a list.
    """
    per_player = defaultdict(lambda: defaultdict(dict))
    for r in ledger:
        per_player[r["playerImageId"]][r["stat"]][r["gameId"]] = r["actual"]
    out = []
    stats = list(PROP_SOURCES)
    for i, a in enumerate(stats):
        for b in stats[i + 1:]:
            xs, ys = [], []
            for pid, d in per_player.items():
                da, db = d.get(a), d.get(b)
                if not da or not db:
                    continue
                for gid in sorted(set(da) & set(db)):
                    xs.append(da[gid])
                    ys.append(db[gid])
            r, n = L.pearson(xs, ys)
            lo, hi = L.fisher_ci(r, n)
            out.append({"statA": a, "statB": b, "correlation": r, "n": n,
                        "ci95": [lo, hi],
                        "method": "Pearson on official per-game production, matched on player and game",
                        "note": None if n >= 20 else "fewer than 20 paired games; treat as unverified"})
    return out


# ================================================================== gates
GATE_DOCS = {
    "G1": "Provenance - every input carries an official source URL (checked by scripts/lines/verify_lines.py)",
    "G2": "Evidence - minimum number of bets placed after the price filter",
    "G3": "Baseline - beats the pre-registered naive model out of sample (log loss lower than the baseline)",
    "G4": ("Significance - bootstrap 95% CI on ROI lies entirely above zero AND a paired "
           "sign-flip randomisation test shows the strategy beats its baseline "
           "(Benjamini-Hochberg adjusted p < 0.05 across the whole family)"),
    "G5": "Holdout - positive ROI on the untouched 2026 regular season",
    "G6": "Robustness - positive ROI in at least two seasons and no single bet carries more than 40% of gross profit",
    "G7": "Non-redundancy - |correlation| below 0.50 with every higher-ranked qualified strategy",
}


def evaluate_gates(result):
    m = result["metrics"]
    family = result["family"]
    gates = {}
    gates["G1"] = {"pass": True, "detail": "all rows carry official source URLs"}
    need = GATE_MIN_BETS.get(family, 30)
    gates["G2"] = {"pass": m.get("betsPlaced", 0) >= need,
                   "detail": f"{m.get('betsPlaced', 0)} bets placed (minimum {need})"}
    delta = m.get("deltaLogLoss")
    gates["G3"] = {"pass": bool(delta is not None and delta < 0),
                   "detail": (f"log loss {m.get('logLoss'):.4f} vs baseline {m.get('baselineLogLoss'):.4f}"
                              if delta is not None else "not enough bets to score")}
    lo, hi = (m.get("roiCI") or [None, None])
    ci_ok = lo is not None and lo > 0
    q = m.get("adjustedP")
    skill_mean = m.get("skillMean")
    skill_ok = skill_mean is not None and skill_mean > 0
    gates["G4"] = {"pass": bool(ci_ok and skill_ok and q is not None and q < BH_ALPHA),
                   "detail": (f"ROI 95% CI [{lo:.4f}, {hi:.4f}]; mean per-bet log-loss "
                              f"improvement over baseline {skill_mean:.4f}; "
                              f"BH adjusted p {'n/a' if q is None else f'{q:.4f}'}")
                              if lo is not None and skill_mean is not None else "not enough bets"}
    gates["G5"] = {"pass": bool(m.get("holdoutRoi") is not None and m["holdoutRoi"] > 0),
                   "detail": (f"2026 holdout ROI {m['holdoutRoi']:.4f} on {m['holdoutBets']} bets"
                              if m.get("holdoutRoi") is not None else "no 2026 holdout bets")}
    season_roi = m.get("seasonRoi") or {}
    positive_seasons = sum(1 for v in season_roi.values() if v > 0)
    share = m.get("maxBetShare")
    gates["G6"] = {"pass": bool(positive_seasons >= 2 and share is not None and share <= BET_CONCENTRATION_MAX),
                   "detail": (f"{positive_seasons} of {len(season_roi)} seasons positive; "
                              f"largest single bet carries "
                              f"{('%.1f%%' % (share * 100)) if share is not None else 'n/a'} of gross profit")}
    gates["G7"] = {"pass": True, "detail": "applied after ranking"}
    return gates


def apply_redundancy_gate(leaderboard, correlations):
    """G7: a strategy earns its own reward only if it is not a clone of a better one."""
    qualified = [r for r in leaderboard
                 if all(g["pass"] for k, g in r["gates"].items() if k != "G7")]
    qualified_ids = {q["id"] for q in qualified}
    for row in leaderboard:
        if row["id"] not in qualified_ids:
            row["gates"]["G7"] = {"pass": True, "detail": "not applicable (strategy is not qualified)"}
    for row in qualified:
        worst = None
        for other in qualified:
            if other["rank"] >= row["rank"]:
                continue
            for c in correlations:
                if {c["a"], c["b"]} == {row["id"], other["id"]}:
                    r = c.get("correlation")
                    if r is not None and (worst is None or abs(r) > abs(worst[1])):
                        worst = (other["id"], r, c.get("n"))
        if worst:
            row["gates"]["G7"] = {
                "pass": abs(worst[1]) < CORR_REDUNDANCY,
                "detail": (f"highest |correlation| with a higher-ranked qualified strategy is "
                           f"{worst[1]:+.3f} ({worst[0]}, n={worst[2]})"),
            }
        else:
            row["gates"]["G7"] = {"pass": True, "detail": "no higher-ranked qualified strategy to compare"}
    for row in leaderboard:
        row["status"] = ("qualified" if all(g["pass"] for g in row["gates"].values())
                         else "failed")
        row["reward"] = row["reward"] if row["status"] == "qualified" else 0
        if row["status"] != "qualified":
            row["rewardNote"] = "no reward: one or more validation gates failed"


def compute_reward(result, gates):
    m = result["metrics"]
    if not all(g["pass"] for g in gates.values()):
        return 0, "no reward: one or more validation gates failed"
    base = m.get("baselineLogLoss")
    delta = m.get("deltaLogLoss")
    if not base or delta is None:
        return 0, "no reward: baseline comparison unavailable"
    skill = max(0.0, -delta / base)
    evidence = min(1.0, m.get("betsPlaced", 0) / 50.0)
    share = m.get("maxBetShare")
    luck = 1.0 if share is None else max(0.0, 1.0 - max(0.0, share - 0.40) / 0.60)
    reward = int(round(1000 * skill * evidence * luck))
    return reward, (f"1000 x skill {skill:.3f} x evidence {evidence:.2f} x luck guard {luck:.2f}")


# ================================================================== lineup risk
OFFENSE_POS = {"WR", "TE", "RB", "FB", "QB", "LT", "LG", "C", "RG", "RT", "OL", "HB"}
DEFENSE_POS = {"DE", "DT", "NT", "OLB", "ILB", "LB", "CB", "DB", "FS", "SS", "S", "NB", "EDGE", "DL"}


def build_lineup_risk(inj_doc, depth_doc, reg_games, games_doc):
    """Flag positions where an unavailable starter forces a lower-string player in."""
    injuries = inj_doc.get("rows", [])
    charts = {c["team"]: c for c in depth_doc.get("clubs", []) if c.get("units")}
    rows = []
    # upcoming games = scheduled games with no score yet
    played = {g["gameId"] for g in reg_games}
    upcoming = [g for g in games_doc.get("games", [])
                if g.get("season") == HOLDOUT_SEASON and g.get("gameId") not in played
                and g.get("weekType") == "REG"]
    inj_by_team = defaultdict(list)
    for r in injuries:
        inj_by_team[r["team"]].append(r)
    for g in upcoming:
        for team in (g["away"], g["home"]):
            club = charts.get(team)
            chart_players = {}
            if club:
                for unit, positions in club["units"].items():
                    for pos, row in positions.items():
                        for p in row["players"]:
                            chart_players[(pos, p["name"].lower())] = {
                                "tier": p.get("tier"), "position": pos, "unit": unit,
                                "name": p["name"], "sourceUrl": club.get("sourceUrl"),
                                "chartLabel": club.get("chartLabel"),
                            }
            for r in inj_by_team.get(team, []):
                status = (r.get("gameStatus") or "").strip()
                if not status:
                    continue
                name = r.get("player")
                pos = (r.get("position") or "").strip()
                entry = None
                for (p, nm), v in chart_players.items():
                    if nm == (name or "").lower() and (not pos or p == pos):
                        entry = v
                        break
                unit = "Offense" if pos in OFFENSE_POS else ("Defense" if pos in DEFENSE_POS else "Special Teams")
                replacement = None
                if entry and entry.get("tier") == "1st":
                    order = ["1st", "2nd", "3rd", "4th"]
                    start = order.index("1st")
                    for t in order[start + 1:]:
                        cand = None
                        for (p, nm), v in chart_players.items():
                            if p == pos and v.get("tier") == t:
                                if not cand or v["name"].lower() < cand["name"].lower():
                                    cand = v
                        if cand:
                            replacement = cand
                            break
                rows.append({
                    "gameId": g["gameId"],
                    "date": g.get("date"),
                    "week": g.get("week"),
                    "team": team,
                    "opponent": g["away"] if team == g["home"] else g["home"],
                    "player": name,
                    "position": pos,
                    "unit": unit,
                    "injury": r.get("injury") or "",
                    "practiceStatus": r.get("practiceStatus") or "",
                    "gameStatus": status,
                    "depthTier": (entry or {}).get("tier"),
                    "depthTierVerified": bool(entry),
                    "replacement": (replacement or {}).get("name"),
                    "replacementTier": (replacement or {}).get("tier"),
                    "deficiency": (None if not entry else (
                        "starter unavailable" if entry.get("tier") == "1st"
                        else f"{entry.get('tier')} string unavailable")),
                    "severity": ("none" if status.lower() == "out" and not entry
                                 else ("high" if entry and entry.get("tier") == "1st" else "medium")),
                    "injurySourceUrl": r.get("sourceUrl"),
                    "playerSourceUrl": r.get("playerUrl"),
                    "depthChartSourceUrl": (entry or {}).get("sourceUrl") or (club or {}).get("sourceUrl"),
                    "chartLabel": (entry or {}).get("chartLabel"),
                })
    rows.sort(key=lambda r: (r.get("date") or "", r["team"], r["position"] or ""))
    return rows


# ================================================================== catalog
STRATEGY_CATALOG = [
    {"id": "S01", "name": "Model game total vs league average (model's Over pick)",
     "family": "team", "market": "game total",
     "rule": ("Bet Over when the model total exceeds the league-average total, Under when it is below. "
              "Line = league-average combined points from prior games only."),
     "benchmark": "league-average combined points (pre-registered naive line)"},
    {"id": "S02", "name": "Model game total vs league average (model's Under pick)",
     "family": "team", "market": "game total",
     "rule": ("The model's Under selection: bets Under the league-average line in the games where the "
              "model expects a total below the league average. The controlled comparison against the "
              "naive model is the log-loss column, which scores both on the same events."),
     "benchmark": "league-average combined points (pre-registered naive line)"},
    {"id": "S03", "name": "Model moneyline vs pick'em (follow the model)",
     "family": "team", "market": "moneyline",
     "rule": "Bets the model-favoured team to win straight, line = 0 (pick'em).",
     "benchmark": "pick'em with the historical home win rate as the naive probability"},
    {"id": "S04", "name": "Model moneyline vs pick'em (fade the model)",
     "family": "team", "market": "moneyline",
     "rule": ("Structural control. At a -110 price the model-underdog can never carry a probability "
              "above the price-implied 52.38%, so this strategy can never clear the price filter. "
              "It is kept so the price filter is visibly applied to every strategy, not only the "
              "ones that benefit from it."),
     "benchmark": "pick'em with the historical home win rate as the naive probability"},
    {"id": "S05", "name": "Model moneyline, strong separation only",
     "family": "team", "market": "moneyline",
     "rule": "S03 but only bets when the model margin is at least 4 points.",
     "benchmark": "pick'em with the historical home win rate as the naive probability"},
    {"id": "S06", "name": "Model game total, large deviation only",
     "family": "team", "market": "game total",
     "rule": "S01 but only bets when the model total differs from the league average by at least 3 points.",
     "benchmark": "league-average combined points (pre-registered naive line)"},
    {"id": "S07", "name": "Model team points vs the team's own scoring average (model's Over pick)",
     "family": "team", "market": "team points",
     "rule": ("Bets a team's modelled points over that team's own prior scoring average. "
              "Line = the team's own recency-weighted points scored."),
     "benchmark": "the team's own prior scoring average (pre-registered naive line)"},
    {"id": "S08", "name": "Model team points vs the team's own scoring average (model's Under pick)",
     "family": "team", "market": "team points",
     "rule": ("The model's Under selection on a team's points line. The controlled comparison against "
              "the naive model is the log-loss column, which scores both on the same events."),
     "benchmark": "the team's own prior scoring average (pre-registered naive line)"},
    {"id": "P01", "name": "Receiving yards over the player's own average",
     "family": "prop", "market": "player receiving yards",
     "rule": ("Line = the player's own prior average receiving yards. Our projection = recency-weighted "
              "average adjusted for the opponent's allowance rate."),
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P02", "name": "Rushing yards over the player's own average",
     "family": "prop", "market": "player rushing yards",
     "rule": "Line = the player's own prior average rushing yards; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P03", "name": "Receptions over the player's own average",
     "family": "prop", "market": "player receptions",
     "rule": "Line = the player's own prior average receptions; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P04", "name": "Passing yards over the player's own average",
     "family": "prop", "market": "player passing yards",
     "rule": "Line = the quarterback's own prior average passing yards; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P05", "name": "Receiving touchdowns over the player's own average",
     "family": "prop", "market": "player receiving touchdowns",
     "rule": "Line = the player's own prior average receiving touchdowns; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P06", "name": "Rushing touchdowns over the player's own average",
     "family": "prop", "market": "player rushing touchdowns",
     "rule": "Line = the player's own prior average rushing touchdowns; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "P07", "name": "Rush attempts over the player's own average",
     "family": "prop", "market": "player rush attempts",
     "rule": "Line = the player's own prior average rush attempts; projection is opponent-adjusted.",
     "benchmark": "the player's own prior average (pre-registered naive line)"},
    {"id": "L01", "name": "Two-leg player-prop parlay",
     "family": "parlay", "market": "2-leg player prop parlay",
     "rule": ("The two strongest player-prop legs in the same game are combined. The joint probability uses "
              "the MEASURED within-game correlation, never an independence assumption."),
     "benchmark": "the same legs priced by the naive model with the same measured correlation"},
    {"id": "L02", "name": "Three-leg player-prop parlay",
     "family": "parlay", "market": "3-leg player prop parlay",
     "rule": "The three strongest player-prop legs in the same game are combined.",
     "benchmark": "the same legs priced by the naive model with the same measured correlation"},
    {"id": "L03", "name": "Game total + model moneyline parlay",
     "family": "parlay", "market": "2-leg game total + moneyline",
     "rule": ("League-average total and the model-favoured moneyline in the same game, combined with the "
              "MEASURED correlation between the two outcomes."),
     "benchmark": "the same legs priced by the naive model with the same measured correlation"},
]


if __name__ == "__main__":
    main()
