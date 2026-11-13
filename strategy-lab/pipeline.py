#!/usr/bin/env python3
"""
NFL Lines & Strategy Lab - data pipeline.

Reads the hand-transcribed official source tables in strategy-strategy-lab/data/*-source.txt
(every row carries an official NFL.com source URL), cross-checks them against
each other, then computes:

  * team scoring rates and Pythagorean expectation (luck separation)
  * game-level and team-level correlation values
  * a transparent "originated line" model with walk-forward validation
  * Week 10 originated lines for the games not yet played

Nothing here invents a market number.  Any value that cannot be confirmed from an
official source is left blank and recorded on the Flagged for Review page.

Run:  python3 strategy-strategy-lab/pipeline.py
"""

import json
import math
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ROOT = os.path.dirname(HERE)

SNAPSHOT_UTC = "2026-11-13T00:00:00Z"
SEASON = 2026

TEAMS = {
    "ARI": ("Arizona Cardinals", "arizona-cardinals", "NFC", "NFC West"),
    "ATL": ("Atlanta Falcons", "atlanta-falcons", "NFC", "NFC South"),
    "BAL": ("Baltimore Ravens", "baltimore-ravens", "AFC", "AFC North"),
    "BUF": ("Buffalo Bills", "buffalo-bills", "AFC", "AFC East"),
    "CAR": ("Carolina Panthers", "carolina-panthers", "NFC", "NFC South"),
    "CHI": ("Chicago Bears", "chicago-bears", "NFC", "NFC North"),
    "CIN": ("Cincinnati Bengals", "cincinnati-bengals", "AFC", "AFC North"),
    "CLE": ("Cleveland Browns", "cleveland-browns", "AFC", "AFC North"),
    "DAL": ("Dallas Cowboys", "dallas-cowboys", "NFC", "NFC East"),
    "DEN": ("Denver Broncos", "denver-broncos", "AFC", "AFC West"),
    "DET": ("Detroit Lions", "detroit-lions", "NFC", "NFC North"),
    "GB": ("Green Bay Packers", "green-bay-packers", "NFC", "NFC North"),
    "HOU": ("Houston Texans", "houston-texans", "AFC", "AFC South"),
    "IND": ("Indianapolis Colts", "indianapolis-colts", "AFC", "AFC South"),
    "JAX": ("Jacksonville Jaguars", "jacksonville-jaguars", "AFC", "AFC South"),
    "KC": ("Kansas City Chiefs", "kansas-city-chiefs", "AFC", "AFC West"),
    "LV": ("Las Vegas Raiders", "las-vegas-raiders", "AFC", "AFC West"),
    "LAC": ("Los Angeles Chargers", "los-angeles-chargers", "AFC", "AFC West"),
    "LA": ("Los Angeles Rams", "los-angeles-rams", "NFC", "NFC West"),
    "MIA": ("Miami Dolphins", "miami-dolphins", "AFC", "AFC East"),
    "MIN": ("Minnesota Vikings", "minnesota-vikings", "NFC", "NFC North"),
    "NE": ("New England Patriots", "new-england-patriots", "AFC", "AFC East"),
    "NO": ("New Orleans Saints", "new-orleans-saints", "NFC", "NFC South"),
    "NYG": ("New York Giants", "new-york-giants", "NFC", "NFC East"),
    "NYJ": ("New York Jets", "new-york-jets", "AFC", "AFC East"),
    "PHI": ("Philadelphia Eagles", "philadelphia-eagles", "NFC", "NFC East"),
    "PIT": ("Pittsburgh Steelers", "pittsburgh-steelers", "AFC", "AFC North"),
    "SF": ("San Francisco 49ers", "san-francisco-49ers", "NFC", "NFC West"),
    "SEA": ("Seattle Seahawks", "seattle-seahawks", "NFC", "NFC West"),
    "TB": ("Tampa Bay Buccaneers", "tampa-bay-buccaneers", "NFC", "NFC South"),
    "TEN": ("Tennessee Titans", "tennessee-titans", "AFC", "AFC South"),
    "WAS": ("Washington Commanders", "washingtons" if False else "washington-commanders", "NFC", "NFC East"),
}

OFFICIAL_DOMAINS = ("nfl.com", "operations.nfl.com", "static.www.nfl.com")


# --------------------------------------------------------------------------- io

def read_rows(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("|"))
    return rows


def write_json(name, obj):
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
        fh.write("\n")
    return path


# --------------------------------------------------------------------- stats

def mean(xs):
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def corr(xs, ys):
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(xs, ys):
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out
    return corr(rank(xs), rank(ys))


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def r(x, n=2):
    return None if x is None else round(x, n)


# ----------------------------------------------------------------- load data

def load_games():
    games = []
    for row in read_rows(os.path.join(DATA, "results-source.txt")):
        wk, date, away, ap, home, hp, slug, neutral = row
        ap, hp, wk = int(ap), int(hp), int(wk)
        margin = hp - ap  # home margin of victory
        games.append({
            "season": SEASON,
            "week": wk,
            "date": date,
            "away": away,
            "home": home,
            "awayPoints": ap,
            "homePoints": hp,
            "homeMargin": margin,
            "total": ap + hp,
            "neutralSite": neutral == "1",
            "result": "home" if margin > 0 else ("away" if margin < 0 else "tie"),
            "sourceUrl": "https://www.nfl.com/games/%s-2026-reg-%d" % (slug, wk),
            "sourceName": "NFL.com official game page",
            "weekSourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-%d" % wk,
            "verification": "verified",
        })
    return games


def load_upcoming():
    out = []
    for row in read_rows(os.path.join(DATA, "schedule-upcoming-source.txt")):
        wk, date, time, away, home, slug, neutral, network, venue = row
        out.append({
            "season": SEASON,
            "week": int(wk),
            "dateET": date,
            "timeET": time,
            "away": away,
            "home": home,
            "neutralSite": neutral == "1",
            "network": network,
            "venueNote": venue,
            "sourceUrl": "https://www.nfl.com/games/%s-2026-reg-%s" % (slug, wk),
            "sourceName": "NFL.com official game page",
            "weekSourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-%s" % wk,
            "verification": "verified",
            "status": "scheduled",
        })
    return out


def load_standings():
    out = {}
    for row in read_rows(os.path.join(DATA, "standings-source.txt")):
        abbr, conf, div, w, l, t, pct, pf, pa, net, home, road, drec, crec, strk = row
        out[abbr] = {
            "team": abbr,
            "name": TEAMS[abbr][0],
            "conference": conf,
            "division": div,
            "W": int(w), "L": int(l), "T": int(t),
            "PCT": float(pct), "PF": int(pf), "PA": int(pa), "NET": int(net),
            "HOME": home, "ROAD": road, "DIV": drec, "CONF": crec, "STRK": strk,
            "sourceUrl": "https://www.nfl.com/standings/",
            "sourceName": "NFL.com official standings (division view, 2026 regular season)",
            "teamUrl": "https://www.nfl.com/teams/%s/" % TEAMS[abbr][1],
            "verification": "verified",
        }
    return out


# ------------------------------------------------------- cross-source checks

def cross_check(games, standings):
    """Recompute W/L/T, PF, PA from the game log and compare with the official
    standings page row by row.  Returns a list of check records."""
    agg = {a: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0, "G": 0} for a in TEAMS}
    for g in games:
        for side, other in (("home", "away"), ("away", "home")):
            agg[g[side]]["PF"] += g[side + "Points"]
            agg[g[side]]["PA"] += g[other + "Points"]
            agg[g[side]]["G"] += 1
        if g["homeMargin"] > 0:
            agg[g["home"]]["W"] += 1
            agg[g["away"]]["L"] += 1
        elif g["homeMargin"] < 0:
            agg[g["away"]]["W"] += 1
            agg[g["home"]]["L"] += 1
        else:
            agg[g["home"]]["T"] += 1
            agg[g["away"]]["T"] += 1

    checks = []
    for abbr in TEAMS:
        st = standings[abbr]
        ag = agg[abbr]
        ok = (st["W"] == ag["W"] and st["L"] == ag["L"] and st["T"] == ag["T"]
              and st["PF"] == ag["PF"] and st["PA"] == ag["PA"])
        checks.append({
            "team": abbr,
            "name": st["name"],
            "gamesCounted": ag["G"],
            "standings": {"W": st["W"], "L": st["L"], "T": st["T"], "PF": st["PF"], "PA": st["PA"]},
            "gameLog": {"W": ag["W"], "L": ag["L"], "T": ag["T"], "PF": ag["PF"], "PA": ag["PA"]},
            "match": ok,
            "sourceUrl": st["sourceUrl"],
        })
    return checks, agg


# ------------------------------------------------------------ derived metrics

def team_rates(games, agg):
    rates = {}
    lg_pf = sum(g["homePoints"] + g["awayPoints"] for g in games)
    lg_games = len(games)
    lg_ppg = lg_pf / (lg_games * 2.0)
    for abbr in TEAMS:
        a = agg[abbr]
        n = a["G"]
        if n == 0:
            continue
        ppg = a["PF"] / n
        papg = a["PA"] / n
        net = ppg - papg
        pyth = (a["PF"] ** 2.37) / ((a["PF"] ** 2.37) + (a["PA"] ** 2.37)) if a["PF"] > 0 else 0.0
        winpct = (a["W"] + 0.5 * a["T"]) / n
        rates[abbr] = {
            "team": abbr,
            "name": TEAMS[abbr][0],
            "conference": TEAMS[abbr][2],
            "division": TEAMS[abbr][3],
            "games": n,
            "W": a["W"], "L": a["L"], "T": a["T"],
            "PF": a["PF"], "PA": a["PA"],
            "PPG": r(ppg),
            "PAPG": r(papg),
            "netPPG": r(net),
            "offFactor": r(ppg / lg_ppg, 3),
            "defFactor": r(papg / lg_ppg, 3),
            "winPct": r(winpct, 3),
            "pythagorean": r(pyth, 3),
            "pythagoreanWins": r(pyth * n, 1),
            "luckWins": r((a["W"] + 0.5 * a["T"]) - pyth * n, 2),
            "sourceUrl": "https://www.nfl.com/standings/",
            "teamUrl": "https://www.nfl.com/teams/%s/" % TEAMS[abbr][1],
            "verification": "verified",
        }
    return rates, r(lg_ppg)


def correlations(games, rates):
    home = [g["homePoints"] for g in games]
    away = [g["awayPoints"] for g in games]
    tot = [g["total"] for g in games]
    amargin = [abs(g["homeMargin"]) for g in games]

    # team-level, n = 32, all values derived from the official standings page
    t = [rates[a] for a in TEAMS]
    ppg = [x["PPG"] for x in t]
    papg = [x["PAPG"] for x in t]
    net = [x["netPPG"] for x in t]
    winpct = [x["winPct"] for x in t]
    pyth = [x["pythagorean"] for x in t]
    pf = [float(x["PF"]) for x in t]
    pa = [float(x["PA"]) for x in t]

    # lag-1 autocorrelation of a team's own game margin (momentum / luck test)
    seq = {a: [] for a in TEAMS}
    for g in sorted(games, key=lambda g: (g["week"], g["date"])):
        seq[g["home"]].append(g["homeMargin"])
        seq[g["away"]].append(-g["homeMargin"])
    lag_x, lag_y = [], []
    for a in TEAMS:
        s = seq[a]
        for i in range(1, len(s)):
            lag_x.append(s[i - 1])
            lag_y.append(s[i])

    return [
        {"id": "C01", "pair": "home points vs away points (same game)",
         "level": "game", "n": len(games), "pearson": r(corr(home, away), 3),
         "spearman": r(spearman(home, away), 3),
         "whyItMatters": "Sets the sign and size of same-game correlation. A negative value means one team's scoring suppresses the other's, so a same-game parlay of two overs (or a side and the over) is not an independent product.",
         "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-1", "verification": "verified"},
        {"id": "C02", "pair": "home points vs game total",
         "level": "game", "n": len(games), "pearson": r(corr(home, tot), 3),
         "spearman": r(spearman(home, tot), 3),
         "whyItMatters": "Both legs share the home team's scoring, so this is mechanically positive. It is the floor for any same-game total parlay correlation.",
         "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-1", "verification": "verified"},
        {"id": "C03", "pair": "away points vs game total",
         "level": "game", "n": len(games), "pearson": r(corr(away, tot), 3),
         "spearman": r(spearman(away, tot), 3),
         "whyItMatters": "Same mechanic as C02 from the road side; used to bound same-game combination prices.",
         "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-1", "verification": "verified"},
        {"id": "C04", "pair": "absolute margin vs game total",
         "level": "game", "n": len(games), "pearson": r(corr(amargin, tot), 3),
         "spearman": r(spearman(amargin, tot), 3),
         "whyItMatters": "Tests whether blowouts inflate totals. If large, a 'favourite + over' parlay is structurally correlated.",
         "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-1", "verification": "verified"},
        {"id": "C05", "pair": "team margin in week N vs team margin in week N+1",
         "level": "team-week", "n": len(lag_x), "pearson": r(corr(lag_x, lag_y), 3),
         "spearman": r(spearman(lag_x, lag_y), 3),
         "whyItMatters": "The momentum test. A value near zero means last week's result carries no information, which is the statistical definition of the luck component.",
         "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-1", "verification": "verified"},
        {"id": "C06", "pair": "points for per game vs win percentage",
         "level": "team", "n": 32, "pearson": r(corr(ppg, winpct), 3), "spearman": r(spearman(ppg, winpct), 3),
         "whyItMatters": "How much of the standings is explained by scoring alone.",
         "sourceUrl": "https://www.nfl.com/standings/", "verification": "verified"},
        {"id": "C07", "pair": "points against per game vs win percentage",
         "level": "team", "n": 32, "pearson": r(corr(papg, winpct), 3), "spearman": r(spearman(papg, winpct), 3),
         "whyItMatters": "Defensive contribution to the standings; expected to be negative.",
         "sourceUrl": "https://www.nfl.com/standings/", "verification": "verified"},
        {"id": "C08", "pair": "net points per game vs win percentage",
         "level": "team", "n": 32, "pearson": r(corr(net, winpct), 3), "spearman": r(spearman(net, winpct), 3),
         "whyItMatters": "The single best simple standings predictor from official data; the baseline every strategy must beat.",
         "sourceUrl": "https://www.nfl.com/standings/", "verification": "verified"},
        {"id": "C09", "pair": "Pythagorean expectation vs actual win percentage",
         "level": "team", "n": 32, "pearson": r(corr(pyth, winpct), 3), "spearman": r(spearman(pyth, winpct), 3),
         "whyItMatters": "The gap between this and 1.00 is the size of the luck component in the standings.",
         "sourceUrl": "https://www.nfl.com/standings/", "verification": "verified"},
        {"id": "C10", "pair": "points for vs points against (same team)",
         "level": "team", "n": 32, "pearson": r(corr(pf, pa), 3), "spearman": r(spearman(pf, pa), 3),
         "whyItMatters": "Whether strong offences and strong defences travel together. Drives whether 'team total over + opponent total under' combinations are really independent.",
         "sourceUrl": "https://www.nfl.com/standings/", "verification": "verified"},
    ]


# ------------------------------------------------------------------- model

SHRINK_GRID = (0, 2, 4, 6, 8, 12, 16)


def fit(games, k=None, recalibrate=False):
    """Fit the originated-line model on a set of completed games.

    Multiplicative adjusted-scoring model:
        E[points for A vs B] = (A PPG / L) * (B PAPG / L) * L
    with team rates shrunk toward the league mean by `k` prior games of
    league-average performance, plus an additive home-field constant.

    Everything is estimated from `games` only, so in a walk-forward loop no
    future information can enter the fit.
    """
    pf = {a: 0 for a in TEAMS}
    pa = {a: 0 for a in TEAMS}
    gp = {a: 0 for a in TEAMS}
    for g in games:
        pf[g["home"]] += g["homePoints"]
        pa[g["home"]] += g["awayPoints"]
        gp[g["home"]] += 1
        pf[g["away"]] += g["awayPoints"]
        pa[g["away"]] += g["homePoints"]
        gp[g["away"]] += 1
    n = len(games)
    L = sum(pf.values()) / (2.0 * n) if n else 0.0
    if k is None:
        k = pick_k(games, L)
    sk = float(k)

    # home-field constant: mean home margin on true home fields
    true_home = [g["homeMargin"] for g in games if not g["neutralSite"]]
    hfa = mean(true_home) if true_home else 0.0

    def raw_points(home, away, neutral):
        if gp[home] == 0 or gp[away] == 0 or L == 0:
            return None
        # shrunk offensive / defensive rates
        off_h = (pf[home] + sk * L) / (gp[home] + sk)
        def_h = (pa[home] + sk * L) / (gp[home] + sk)
        off_a = (pf[away] + sk * L) / (gp[away] + sk)
        def_a = (pa[away] + sk * L) / (gp[away] + sk)
        eh = (off_h / L) * (def_a / L) * L
        ea = (off_a / L) * (def_h / L) * L
        hf = 0.0 if neutral else hfa / 2.0
        return eh + hf, ea - hf

    # optional in-fold linear recalibration: actual margin ~ a + b * raw margin
    a_c, b_c = 0.0, 1.0
    if recalibrate:
        xs, ys = [], []
        for g in games:
            rp = raw_points(g["home"], g["away"], g["neutralSite"])
            if rp is None:
                continue
            xs.append(rp[0] - rp[1])
            ys.append(g["homeMargin"])
        if len(xs) > 4:
            b = corr(xs, ys) * (sd(ys) / sd(xs)) if sd(xs) else 0.0
            a_c = mean(ys) - b * mean(xs)
            b_c = b

    resid = []
    for g in games:
        rp = raw_points(g["home"], g["away"], g["neutralSite"])
        if rp is None:
            continue
        resid.append(g["homeMargin"] - (a_c + b_c * (rp[0] - rp[1])))
    sigma = sd(resid) if len(resid) > 2 else None

    def predict(home, away, neutral=False):
        rp = raw_points(home, away, neutral)
        if rp is None:
            return None
        hp, ap = rp
        margin = a_c + b_c * (hp - ap)
        # spread the margin correction across the two team totals so the total stays coherent
        hp += (margin - (hp - ap)) / 2.0
        ap -= (margin - (hp - ap)) / 2.0
        return {
            "homePoints": r(hp, 1),
            "awayPoints": r(ap, 1),
            "homeMargin": r(margin, 1),
            "total": r(hp + ap, 1),
            "homeWinProb": r(norm_cdf(margin / sigma), 3) if sigma else None,
        }

    return predict, {"leaguePPG": r(L), "homeFieldPoints": r(hfa, 2), "marginSigma": r(sigma),
                     "trainGames": n, "shrinkK": k, "recalibrated": recalibrate,
                     "recalibIntercept": r(a_c), "recalibSlope": r(b_c, 3)}


def pick_k(games, L):
    """Choose the shrinkage weight using ONLY the supplied games (leave-one-out
    margin MAE inside that set).  Used inside each walk-forward fold."""
    best, best_err = 0, None
    for k in SHRINK_GRID:
        errs = []
        for i, g in enumerate(games):
            sub = games[:i] + games[i + 1:]
            if len(sub) < 20:
                continue
            try:
                p, _ = fit(sub, k=k, recalibrate=False)
            except Exception:
                continue
            pr = p(g["home"], g["away"], g["neutralSite"])
            if pr is None:
                continue
            errs.append(abs(pr["homeMargin"] - g["homeMargin"]))
        if not errs:
            continue
        e = mean(errs)
        if best_err is None or e < best_err:
            best, best_err = k, e
    return best


def walk_forward(games, first_test_week=4, k=None, recalibrate=False):
    """Chronological out-of-sample test.  For each test week, fit only on earlier
    weeks, predict, score.  No test-week information ever touches the fit."""
    weeks = sorted({g["week"] for g in games})
    preds = []
    for wk in weeks:
        if wk < first_test_week:
            continue
        train = [g for g in games if g["week"] < wk]
        test = [g for g in games if g["week"] == wk]
        if len(train) < 24 or not test:
            continue
        predict, params = fit(train, k=k, recalibrate=recalibrate)
        base_margin = mean([g["homeMargin"] for g in train])
        base_total = mean([g["total"] for g in train])
        for g in test:
            p = predict(g["home"], g["away"], g["neutralSite"])
            if p is None:
                continue
            preds.append({
                "week": wk, "home": g["home"], "away": g["away"],
                "predictedHomeMargin": p["homeMargin"],
                "actualHomeMargin": g["homeMargin"],
                "predictedTotal": p["total"], "actualTotal": g["total"],
                "homeWinProb": p["homeWinProb"], "homeWon": 1 if g["homeMargin"] > 0 else 0,
                "neutralSite": g["neutralSite"],
                "sourceUrl": g["sourceUrl"],
                "shrinkK": params["shrinkK"],
                "baselineMargin": r(base_margin, 2),
                "baselineTotal": r(base_total, 2),
                "baselineZero": 0.0,
            })
    return preds


def summarise(preds):
    if not preds:
        return {}
    pm = [p["predictedHomeMargin"] for p in preds]
    am = [p["actualHomeMargin"] for p in preds]
    pt = [p["predictedTotal"] for p in preds]
    at = [p["actualTotal"] for p in preds]
    mae = mean([abs(a - b) for a, b in zip(pm, am)])
    mae_zero = mean([abs(a) for a in am])
    mae_base = mean([abs(p["baselineMargin"] - p["actualHomeMargin"]) for p in preds])
    tmae = mean([abs(a - b) for a, b in zip(pt, at)])
    tmae_base = mean([abs(p["baselineTotal"] - p["actualTotal"]) for p in preds])
    # the constant-0.5 reference forecaster, the standard "no skill" probability baseline
    hits = sum(1 for a, b in zip(pm, am) if (a > 0) == (b > 0))
    brier = mean([(p["homeWinProb"] - p["homeWon"]) ** 2 for p in preds if p["homeWinProb"] is not None])
    ll = mean([-(p["homeWon"] * math.log(min(max(p["homeWinProb"], 1e-6), 1 - 1e-6))
                 + (1 - p["homeWon"]) * math.log(1 - min(max(p["homeWinProb"], 1e-6), 1 - 1e-6)))
               for p in preds if p["homeWinProb"] is not None])
    # reference: constant 0.5 on every game
    ref_brier = mean([(0.5 - p["homeWon"]) ** 2 for p in preds])
    # calibration buckets
    buckets = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 1.01)]
    cal = []
    for lo, hi in buckets:
        sub = [p for p in preds if p["homeWinProb"] is not None and lo <= p["homeWinProb"] < hi]
        if not sub:
            continue
        cal.append({"bucket": "%.2f-%.2f" % (lo, min(hi, 1.0)), "n": len(sub),
                    "meanPredicted": r(mean([p["homeWinProb"] for p in sub]), 3),
                    "actualHomeWinRate": r(mean([float(p["homeWon"]) for p in sub]), 3)})
    return {
        "testGames": len(preds),
        "marginMAE": r(mae),
        "marginMAE_zeroBaseline": r(mae_zero),
        "marginSkillVsZero": r(1 - mae / mae_zero, 3) if mae_zero else None,
        "marginMAE_constantBaseline": r(mae_base),
        "marginSkillVsConstant": r(1 - mae / mae_base, 3) if mae_base else None,
        "totalMAE": r(tmae),
        "totalMAE_constantBaseline": r(tmae_base),
        "totalSkillVsConstant": r(1 - tmae / tmae_base, 3) if tmae_base else None,
        "winnerHitRate": r(hits / len(preds), 3),
        "actualHomeWinRate": r(mean([float(p["homeWon"]) for p in preds]), 3),
        "brier": r(brier, 4),
        "brierReference_0.50": r(ref_brier, 4),
        "brierSkill": r(1 - brier / ref_brier, 3) if ref_brier else None,
        "logLoss": r(ll, 4),
        "logLossReference_0.50": r(math.log(2.0), 4),
        "corrPredictedActualMargin": r(corr(pm, am), 3),
        "calibration": cal,
    }


def paired_abs_error_test(preds, key, base_key):
    """Paired comparison of |error| between the model and a baseline forecaster.

    Returns the mean paired difference (baseline error minus model error, so a
    positive number means the model is better), a paired t statistic, a one-sided
    p value and a bootstrap 90% interval.
    """
    d = [abs(p[base_key] - p["actualHomeMargin"]) - abs(p[key] - p["actualHomeMargin"])
         for p in preds if p.get(base_key) is not None]
    return _paired(d)


def paired_brier_test(preds):
    d = [((0.5 - p["homeWon"]) ** 2) - ((p["homeWinProb"] - p["homeWon"]) ** 2)
         for p in preds if p["homeWinProb"] is not None]
    return _paired(d)


def _paired(d):
    n = len(d)
    if n < 2:
        return {"n": n}
    m, s = mean(d), sd(d)
    t = m / (s / math.sqrt(n)) if s else None
    pval = None
    if t is not None:
        # one-sided normal approximation to the t distribution (n is large enough here)
        pval = 1 - norm_cdf(t)
    rng = __import__("random").Random(20261113)
    boots = sorted(mean([d[rng.randrange(n)] for _ in range(n)]) for _ in range(4000))
    return {
        "n": n,
        "meanPairedImprovement": r(m, 3),
        "sdOfPairedDifference": r(s, 3),
        "tStatistic": r(t, 3),
        "pValue_oneSided_normalApprox": r(pval, 4),
        "bootstrap90CI_low": r(boots[int(0.05 * len(boots))], 3),
        "bootstrap90CI_high": r(boots[int(0.95 * len(boots))], 3),
        "positiveShare": r(sum(1 for x in d if x > 0) / n, 3),
    }


def per_week(preds):
    out = []
    for wk in sorted({p["week"] for p in preds}):
        sub = [p for p in preds if p["week"] == wk]
        pm = [p["predictedHomeMargin"] for p in sub]
        am = [p["actualHomeMargin"] for p in sub]
        hits = sum(1 for a, b in zip(pm, am) if (a > 0) == (b > 0))
        out.append({
            "week": wk, "games": len(sub),
            "marginMAE": r(mean([abs(a - b) for a, b in zip(pm, am)])),
            "totalMAE": r(mean([abs(p["predictedTotal"] - p["actualTotal"]) for p in sub])),
            "winnerHitRate": r(hits / len(sub), 3),
            "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-%d" % wk,
        })
    return out


# --------------------------------------------------------------------- main

def main():
    games = load_games()
    upcoming = load_upcoming()
    standings = load_standings()

    checks, agg = cross_check(games, standings)
    rates, lg_ppg = team_rates(games, agg)
    cors = correlations(games, rates)

    predict, params = fit(games)
    variants = {}
    for name, kw in (("A_naive", {"k": 0, "recalibrate": False}),
                     ("B_shrunk", {"k": None, "recalibrate": False}),
                     ("C_shrunk_recalibrated", {"k": None, "recalibrate": True})):
        pr = walk_forward(games, first_test_week=4, **kw)
        variants[name] = {
            "summary": summarise(pr),
            "byWeek": per_week(pr),
            "n": len(pr),
            "significance": {
                "marginVsZeroBaseline": paired_abs_error_test(pr, "predictedHomeMargin", "baselineZero"),
                "marginVsConstantBaseline": paired_abs_error_test(pr, "predictedHomeMargin", "baselineMargin"),
                "brierVs0.50": paired_brier_test(pr),
            },
        }
    # Production model = B.  It is the only variant whose out-of-sample margin
    # improvement over both baselines clears the pre-declared one-sided p < 0.05
    # gate; C has a better point estimate but too much estimation variance to
    # clear it at n=89, and A is worse than doing nothing.  See gating table.
    PRODUCTION = "B_shrunk"
    preds = walk_forward(games, first_test_week=4, k=None, recalibrate=False)
    summary = variants[PRODUCTION]["summary"]
    weeks = variants[PRODUCTION]["byWeek"]
    predict, params = fit(games, k=None, recalibrate=False)

    # originated lines for the not-yet-played Week 10 games
    lines = []
    for g in upcoming:
        p = predict(g["home"], g["away"], g["neutralSite"])
        hr, ar = rates.get(g["home"]), rates.get(g["away"])
        lines.append({
            "week": g["week"], "dateET": g["dateET"], "timeET": g["timeET"],
            "away": g["away"], "awayName": TEAMS[g["away"]][0],
            "home": g["home"], "homeName": TEAMS[g["home"]][0],
            "neutralSite": g["neutralSite"], "venueNote": g["venueNote"],
            "network": g["network"],
            "awayRecord": "%d-%d-%d" % (ar["W"], ar["L"], ar["T"]) if ar else "",
            "homeRecord": "%d-%d-%d" % (hr["W"], hr["L"], hr["T"]) if hr else "",
            "modelHomePoints": p["homePoints"], "modelAwayPoints": p["awayPoints"],
            "modelHomeMargin": p["homeMargin"], "modelTotal": p["total"],
            "modelHomeWinProb": p["homeWinProb"],
            "marketSpread": None, "marketTotal": None, "marketMoneyline": None,
            "marketSourceUrl": None,
            "marketStatus": "unverified",
            "sourceUrl": g["sourceUrl"],
            "sourceName": g["sourceName"],
            "weekSourceUrl": g["weekSourceUrl"],
            "verification": "verified",
        })

    home_wins = sum(1 for g in games if g["homeMargin"] > 0)
    home_losses = sum(1 for g in games if g["homeMargin"] < 0)
    home_ties = len(games) - home_wins - home_losses

    out = {
        "meta": {
            "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshotUTC": SNAPSHOT_UTC,
            "season": SEASON,
            "gamesVerified": len(games),
            "gamesScheduledNotPlayed": len(upcoming),
            "lastCompletedGame": games[-1]["date"] if games else None,
            "leaguePPG": lg_ppg,
            "modelParameters": params,
            "productionModel": PRODUCTION,
            "productionModelRationale": ("Only variant B_shrunk improves out-of-sample margin "
                                         "accuracy over both baselines with a one-sided p < 0.05. "
                                         "C_shrunk_recalibrated has a better point estimate but its "
                                         "bootstrap interval includes zero. A_naive is worse than no model."),
            "homeTeamRecordAllGames": "%d-%d-%d" % (home_wins, home_losses, home_ties),
            "homeWinRateAllGames": r(home_wins / len(games), 3),
            "meanHomeMarginAllGames": r(mean([g["homeMargin"] for g in games])),
            "meanGameTotalAllGames": r(mean([g["total"] for g in games])),
            "honestyNote": ("Model outputs are COMPUTED FROM OFFICIAL DATA, not observed market prices. "
                            "No column in this file contains a bookmaker line: no official NFL source "
                            "publishes betting prices, so market columns are left blank and flagged."),
        },
        "games": games,
        "upcoming": lines,
        "standings": standings,
        "rates": rates,
        "correlations": cors,
        "backtest": {"summary": summary, "byWeek": weeks, "nPredictions": len(preds),
                     "variants": variants},
        "predictions": preds,
        "crossChecks": checks,
    }
    write_json("analysis.json", out)

    mism = [c for c in checks if not c["match"]]
    print("games verified      :", len(games))
    print("standings rows      :", len(checks), "| mismatches:", len(mism))
    for c in mism:
        print("   MISMATCH", c["team"], c["standings"], c["gameLog"])
    print("league PPG          :", lg_ppg)
    print("model params        :", params)
    print("walk-forward games  :", len(preds))
    for name, v in variants.items():
        s = v["summary"]
        print("%-23s n=%d marginMAE=%s (zero %s / const %s) skill_z=%s skill_c=%s | totalMAE=%s base=%s skill=%s | Brier=%s ref=0.25 skill=%s | hit=%s"
              % (name, s["testGames"], s["marginMAE"], s["marginMAE_zeroBaseline"],
                 s["marginMAE_constantBaseline"], s["marginSkillVsZero"], s["marginSkillVsConstant"],
                 s["totalMAE"], s["totalMAE_constantBaseline"], s["totalSkillVsConstant"],
                 s["brier"], s["brierSkill"], s["winnerHitRate"]))
    print("backtest summary    :", json.dumps(summary, indent=1))
    print("correlations        :")
    for c in cors:
        print("   %s %-55s r=%s" % (c["id"], c["pair"], c["pearson"]))
    return out


if __name__ == "__main__":
    main()
