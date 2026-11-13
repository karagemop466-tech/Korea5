#!/usr/bin/env python3
"""NFL intelligence model — originate our own lines from verified results.

Inputs (all verified against official NFL.com pages; see data/nfl-intel/*.json meta):
  data/nfl-intel/results-2026.json    137 final scores, weeks 1-10 (each row links nfl.com)
  data/nfl-intel/standings-2026.json  official W-L-T / PF / PA (cross-check 32/32 exact)
  data/upstream/nfl-2026.json         official 2026 schedule (week 11+ fixtures)

Output: data/nfl-intel/model.json — every value COMPUTED from the verified inputs.
Formulas are documented in the output meta and on nfl-lines.html. No market odds are
used anywhere (no official odds source is available; see questions register Q-ODDS).

Model
  Spread:  margin_model  m = R_home - R_away + HFA      (least squares over verified scores)
           R solved by iterative opponent adjustment; variant R^0.9 uses recency weights
           w = 0.9 ** (latest_week - game_week).
  Total:   total_model = (pace_home + pace_away) / 2,  pace_t = (PF_t + PA_t) / games_t
           computed on the same window (recency weighted in the variant).
  Win prob: P(home) = Phi(m / sigma), sigma = population SD of verified home margins.
  Backtest: walk-forward. For each target week W in 5..9, fit on games before W, predict W.
            Gates G1..G4 below are evaluated on the aggregate.
"""
import json, math, os, statistics
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

RESULTS = json.load(open("data/nfl-intel/results-2026.json"))["games"]
STANDINGS = json.load(open("data/nfl-intel/standings-2026.json"))["teams"]
SCHEDULE = json.load(open("data/upstream/nfl-2026.json"))["games"]

# name -> abbreviation, derived from the schedule rows and nfl.com score pages
NAME2ABBR = {}
for g in RESULTS:
    pass
for g in SCHEDULE:
    pass
# build from results: schedule slug gives full names, results give abbrs (verified equal)
slug2res = {g["slug"]: g for g in RESULTS}
for g in SCHEDULE:
    slug = g["sourceUrl"].rsplit("/", 1)[-1]
    r = slug2res.get(slug)
    if r:
        NAME2ABBR[g["away"]] = r["away"]
        NAME2ABBR[g["home"]] = r["home"]

TEAMS = sorted(NAME2ABBR.values())
LATEST_WEEK = max(g["week"] for g in RESULTS)


def parse_d(s):
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


for g in RESULTS:
    g["d"] = parse_d(g["datePT"])
    g["hm"] = g["homeScore"] - g["awayScore"]  # home margin

# ----------------------------------------------------------------- ratings
def fit_ratings(games, ref_week, lam=None):
    """Least-squares team ratings: home margin = R_h - R_a + HFA.

    Iterative opponent adjustment; optional recency weight lam**(ref_week-week).
    Returns (ratings dict, HFA). Gauge: mean(ratings)=0.
    """
    wts = {}
    for g in games:
        wts[id(g)] = (lam ** (ref_week - g["week"])) if lam else 1.0
    n = len(games)
    # HFA = weighted mean home margin
    hfa = sum(g["hm"] * wts[id(g)] for g in games) / sum(wts.values())
    R = {t: 0.0 for t in TEAMS}
    for _ in range(200):
        num = {t: 0.0 for t in TEAMS}
        den = {t: 0.0 for t in TEAMS}
        for g in games:
            w = wts[id(g)]
            a, h = g["away"], g["home"]
            num[h] += w * ((g["hm"] - hfa) + R[a])
            den[h] += w
            num[a] += w * ((-(g["hm"]) + hfa) + R[h])
            den[a] += w
        R = {t: (num[t] / den[t] if den[t] else 0.0) for t in TEAMS}
        mean = sum(R.values()) / len(R)
        R = {t: v - mean for t, v in R.items()}
    return R, hfa


def pace_table(games, ref_week, lam=None):
    """Weighted per-team combined-points involvement per game: (PF+PA)/gp."""
    s = {t: [0.0, 0.0] for t in TEAMS}  # points, weight
    for g in games:
        w = (lam ** (ref_week - g["week"])) if lam else 1.0
        for t, pts, opp in ((g["away"], g["awayScore"], g["homeScore"]),
                            (g["home"], g["homeScore"], g["awayScore"])):
            s[t][0] += w * (pts + opp)
            s[t][1] += w
    return {t: (s[t][0] / s[t][1] if s[t][1] else None) for t in TEAMS}


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


home_margins = [g["hm"] for g in RESULTS]
SIGMA = statistics.pstdev(home_margins)

# ----------------------------------------------------------------- backtest
def backtest(target_weeks, lam):
    preds = []
    for W in target_weeks:
        train = [g for g in RESULTS if g["week"] < W]
        test = [g for g in RESULTS if g["week"] == W]
        R, hfa = fit_ratings(train, W, lam)
        P = pace_table(train, W, lam)
        for g in test:
            pm = R[g["home"]] - R[g["away"]] + hfa
            tot = (P[g["home"]] + P[g["away"]]) / 2.0
            preds.append({
                "week": W, "slug": g["slug"], "home": g["home"], "away": g["away"],
                "predMargin": pm, "predTotal": tot, "actualMargin": g["hm"],
                "actualTotal": g["homeScore"] + g["awayScore"],
                "winProb": norm_cdf(pm / SIGMA),
                "actualHomeWin": 1.0 if g["hm"] > 0 else (0.5 if g["hm"] == 0 else 0.0),
                "sourceUrl": g["sourceUrl"],
            })
    return preds


def metrics(preds):
    n = len(preds)
    mae = sum(abs(p["predMargin"] - p["actualMargin"]) for p in preds) / n
    mae_tot = sum(abs(p["predTotal"] - p["actualTotal"]) for p in preds) / n
    # Brier on home win probability (ties count as 0.5 outcome)
    brier = sum((p["winProb"] - p["actualHomeWin"]) ** 2 for p in preds) / n
    # directional hit: did the model's favoured side win?
    hits = 0
    decided = 0
    for p in preds:
        if p["actualHomeWin"] == 0.5:
            continue
        decided += 1
        fav_home = p["predMargin"] > 0
        if (fav_home and p["actualHomeWin"] == 1.0) or ((not fav_home) and p["actualHomeWin"] == 0.0):
            hits += 1
    hit_rate = hits / decided if decided else None
    # Pearson correlation pred vs actual margin
    xs = [p["predMargin"] for p in preds]
    ys = [p["actualMargin"] for p in preds]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    corr = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None
    # naive baselines
    mae_base = sum(abs(2.5 - p["actualMargin"]) for p in preds) / n  # flat home -2.5
    brier_base = sum((0.55 - p["actualHomeWin"]) ** 2 for p in preds) / n  # flat home 0.55
    return {"n": n, "maeSpread": mae, "maeTotal": mae_tot, "brier": brier,
            "hitRate": hit_rate, "corrPredActual": corr,
            "baseline": {"flatHomeMinus2.5_maeSpread": mae_base,
                         "flatHome0.55_brier": brier_base}}


BT_FULL = backtest(range(5, 10), None)
BT_REC = backtest(range(5, 10), 0.9)
M_FULL = metrics(BT_FULL)
M_REC = metrics(BT_REC)

# ---- validation gates (documented thresholds; PASS/FAIL/NOT-EVALUABLE)
def gates(m, label):
    g = []
    g.append({"id": "G1", "rule": "Backtest sample >= 60 games across >= 4 walk-forward weeks",
              "value": m["n"], "status": "PASS" if m["n"] >= 60 else "FAIL"})
    g.append({"id": "G2", "rule": "Spread MAE beats flat-home baseline MAE",
              "value": "%.2f vs %.2f" % (m["maeSpread"], m["baseline"]["flatHomeMinus2.5_maeSpread"]),
              "status": "PASS" if m["maeSpread"] < m["baseline"]["flatHomeMinus2.5_maeSpread"] else "FAIL"})
    g.append({"id": "G3", "rule": "Brier score beats flat-0.55 baseline",
              "value": "%.3f vs %.3f" % (m["brier"], m["baseline"]["flatHome0.55_brier"]),
              "status": "PASS" if m["brier"] < m["baseline"]["flatHome0.55_brier"] else "FAIL"})
    g.append({"id": "G4", "rule": "Prediction/outcome correlation > 0 (skill sign)",
              "value": "%.3f" % m["corrPredActual"],
              "status": "PASS" if m["corrPredActual"] > 0 else "FAIL"})
    g.append({"id": "G5", "rule": "ATS record vs market closing line >= 52.4% over >= 200 graded picks",
              "value": "not evaluated — no verified market line source (see Q-ODDS)",
              "status": "NOT EVALUABLE"})
    g.append({"id": "G6", "rule": "Bootstrap 95% CI of edge excludes zero (10k resamples)",
              "value": "not evaluated — requires market lines for a monetary edge",
              "status": "NOT EVALUABLE"})
    g.append({"id": "G7", "rule": "Deflated Sharpe / multiple-testing correction across submitted strategies",
              "value": "competition gate — applies at leaderboard scoring time",
              "status": "DEFERRED"})
    g.append({"id": "G8", "rule": "Out-of-time holdout (weeks 14-18) untouched until season end",
              "value": "holdout not yet played",
              "status": "DEFERRED"})
    return {"label": label, "gates": g}


GATES = [gates(M_FULL, "S1 Opponent-adjusted margin (full season)"),
         gates(M_REC, "S2 Recency-weighted margin (lambda=0.9)")]

# ----------------------------------------------------------------- signal correlations (pre-game signals, weeks 5-9)
def team_streak_map():
    """For each game, pre-game streak (last-5 W-L differential) per team."""
    out = []
    by_team = {t: [] for t in TEAMS}
    for g in sorted(RESULTS, key=lambda x: (x["week"], x["datePT"])):
        rec = {}
        for t in (g["away"], g["home"]):
            hist = by_team[t][-5:]
            rec[t] = sum(1 for x in hist if x == "W") - sum(1 for x in hist if x == "L")
        out.append((g, rec))
        if g["hm"] > 0:
            by_team[g["home"]].append("W"); by_team[g["away"]].append("L")
        elif g["hm"] < 0:
            by_team[g["home"]].append("L"); by_team[g["away"]].append("W")
        else:
            by_team[g["home"]].append("T"); by_team[g["away"]].append("T")
    return out


def rest_days_map():
    last = {}
    out = {}
    for g in sorted(RESULTS, key=lambda x: (x["d"],)):
        rec = {}
        for t in (g["away"], g["home"]):
            rec[t] = (g["d"] - last[t]).days if t in last else 14
        out[id(g)] = rec
        last[g["away"]] = g["d"]
        last[g["home"]] = g["d"]
    return out


STREAKS = {id(g): rec for g, rec in team_streak_map()}
REST = rest_days_map()

# pre-game points-per-game diff uses expanding window
sig_rows = []
for W in range(5, 10):
    train = [g for g in RESULTS if g["week"] < W]
    R, hfa = fit_ratings(train, W, None)
    pf = {t: [0.0, 0] for t in TEAMS}
    for g in train:
        pf[g["away"]][0] += g["awayScore"]; pf[g["away"]][1] += 1
        pf[g["home"]][0] += g["homeScore"]; pf[g["home"]][1] += 1
    for g in [x for x in RESULTS if x["week"] == W]:
        ppg = {t: (pf[t][0] / pf[t][1] if pf[t][1] else 20.0) for t in (g["away"], g["home"])}
        sig_rows.append({
            "week": W, "slug": g["slug"],
            "ratingDiff": R[g["home"]] - R[g["away"]],          # pre-game
            "restDiff": REST[id(g)][g["home"]] - REST[id(g)][g["away"]],
            "streakDiff": STREAKS[id(g)][g["home"]] - STREAKS[id(g)][g["away"]],
            "ppgDiff": ppg[g["home"]] - ppg[g["away"]],
            "home": 1.0,
            "actualMargin": g["hm"],
        })


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


SIGS = ["ratingDiff", "restDiff", "streakDiff", "ppgDiff", "home"]
CORR = {}
for s in SIGS:
    CORR[s] = {u: pearson([r[s] for r in sig_rows], [r[u] for r in sig_rows]) for u in SIGS}
CORR["actualMargin"] = {s: pearson([r[s] for r in sig_rows], [r["actualMargin"] for r in sig_rows]) for s in SIGS}
CORR["actualMargin"]["actualMargin"] = 1.0

# ----------------------------------------------------------------- originated lines for upcoming weeks
upcoming = [g for g in SCHEDULE
            if g["seasonType"] == "REG" and g["week"] in (10, 11)
            and g["sourceUrl"].rsplit("/", 1)[-1] not in slug2res]
R_NOW, HFA_NOW = fit_ratings(RESULTS, LATEST_WEEK, None)
R_REC, HFA_REC = fit_ratings(RESULTS, LATEST_WEEK, 0.9)
PACE_NOW = pace_table(RESULTS, LATEST_WEEK, None)
PACE_REC = pace_table(RESULTS, LATEST_WEEK, 0.9)

lines = []
for g in sorted(upcoming, key=lambda x: (x["week"], x["startUTC"] or "")):
    a, h = NAME2ABBR.get(g["away"]), NAME2ABBR.get(g["home"])
    if not a or not h:
        continue
    pm = R_NOW[h] - R_NOW[a] + HFA_NOW
    pmr = R_REC[h] - R_REC[a] + HFA_REC
    tot = (PACE_NOW[h] + PACE_NOW[a]) / 2.0
    totr = (PACE_REC[h] + PACE_REC[a]) / 2.0
    lines.append({
        "week": g["week"], "datePT": g["datePT"], "startPT": g["startPT"],
        "away": a, "home": h, "title": g["title"],
        "ourSpread_home": round(pm, 1), "ourSpread_recency_home": round(pmr, 1),
        "ourTotal": round(tot, 1), "ourTotal_recency": round(totr, 1),
        "winProb_home": round(norm_cdf(pm / SIGMA), 3),
        "marketSpread": None, "marketTotal": None,
        "marketNote": "blank — no official/verified odds source available (Q-ODDS)",
        "gameUrl": g["sourceUrl"], "weekUrl": "https://www.nfl.com/scores/2026/week-%d" % g["week"],
    })

# ----------------------------------------------------------------- ratings table
ratings_tbl = []
stmap = {t["team"]: t for t in STANDINGS}
for t in sorted(TEAMS, key=lambda x: -R_NOW[x]):
    ratings_tbl.append({
        "team": t, "rating": round(R_NOW[t], 2), "rating_recency": round(R_REC[t], 2),
        "pace": round(PACE_NOW[t], 1), "pace_recency": round(PACE_REC[t], 1),
        "w": stmap[t]["w"], "l": stmap[t]["l"], "ties": stmap[t]["ties"],
        "pf": stmap[t]["pf"], "pa": stmap[t]["pa"],
        "standingsUrl": "https://www.nfl.com/standings/league/2026/REG",
    })

out = {
    "meta": {
        "generatedUTC": "2026-11-13",
        "inputs": ["data/nfl-intel/results-2026.json (137 verified finals, nfl.com)",
                   "data/nfl-intel/standings-2026.json (official standings, 32/32 exact match)",
                   "data/upstream/nfl-2026.json (official schedule)"],
        "formulas": {
            "spread": "m = R_home - R_away + HFA; R solved by iterative least squares on verified margins (mean R = 0)",
            "total": "total = (pace_home + pace_away)/2; pace_t = (PF_t + PA_t)/games_t",
            "winProb": "Phi(m / sigma); sigma = population SD of verified home margins",
            "recency": "weights w = 0.9^(latest_week - game_week) in the S2 variant",
        },
        "hfa_points": round(HFA_NOW, 2), "hfa_recency": round(HFA_REC, 2),
        "sigma_margin": round(SIGMA, 2),
        "backtestWeeks": "5-9 walk-forward (fit strictly before each target week)",
        "marketOdds": "NOT USED — no official source; rows leave market columns blank (Q-ODDS)",
        "label": "ALL VALUES ON THIS PAGE ARE MODEL OUTPUT computed from verified results; they are not official league numbers.",
    },
    "ratings": ratings_tbl,
    "backtest": {"S1_fullSeason": {"metrics": M_FULL, "predictions": BT_FULL, "gates": GATES[0]},
                 "S2_recency09": {"metrics": M_REC, "predictions": BT_REC, "gates": GATES[1]}},
    "signalCorrelations": CORR,
    "signalRows": sig_rows,
    "originatedLines": lines,
}
json.dump(out, open("data/nfl-intel/model.json", "w"), indent=1)
print("HFA %.2f  sigma %.2f" % (HFA_NOW, SIGMA))
print("S1 MAE %.2f (base %.2f)  Brier %.3f (base %.3f)  hit %.3f  corr %.3f" % (
    M_FULL["maeSpread"], M_FULL["baseline"]["flatHomeMinus2.5_maeSpread"],
    M_FULL["brier"], M_FULL["baseline"]["flatHome0.55_brier"], M_FULL["hitRate"], M_FULL["corrPredActual"]))
print("S2 MAE %.2f  Brier %.3f  hit %.3f  corr %.3f" % (
    M_REC["maeSpread"], M_REC["brier"], M_REC["hitRate"], M_REC["corrPredActual"]))
print("lines rows:", len(lines))
print("corr vs actual margin:", {k: (round(v, 3) if v is not None else None) for k, v in CORR["actualMargin"].items()})
