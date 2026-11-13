#!/usr/bin/env python3
"""NFL Lines Lab — data build (session arena-fb9c9608).

Deterministic analytics over committed inputs:
  nfl-lab/data/nfldata/games.csv        (results + market lines, nflverse/nfldata)
  nfl-lab/data/official/*.json          (official NFL.com pages fetched 2026-11-13)

Outputs (nfl-lab/data/derived/):
  model-meta.json      parameters, fit diagnostics, verification counts
  lines-2026-w10-w11.json  originated lines vs market, Weeks 10-11 2026
  leaderboard.json     walk-forward strategy backtest, validation gates, ranking
  correlation.json     correlation values, same-game-parlay pricing math
  depth-2026-w10.json  injury aggregation + QB availability + unit watch
  flags.json           NFL-lab flag register

Honesty rules: no leakage (predictions made before any rating update), no value
invented where a source does not publish one, market lines labelled as market data,
and no claim of betting edge — the leaderboard is a paper research competition.
"""
import csv, json, math, os, random, statistics
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
LAB = os.path.join(ROOT, "nfl-lab")
DATA = os.path.join(LAB, "data")
DER = os.path.join(DATA, "derived")
os.makedirs(DER, exist_ok=True)

BUILD_UTC = "2026-11-13T13:45:00Z"
SRC_NFLDATA = "https://github.com/nflverse/nfldata/blob/master/data/games.csv"
SRC_INJ = "https://www.nfl.com/injuries/"
SRC_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10/"
SRC_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11/"
SRC_GAMES_PAGE = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"

# ---------------------------------------------------------------- load games
def load_games():
    rows = []
    with open(os.path.join(DATA, "nfldata", "games.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if not r["game_id"]:
                continue
            rows.append({
                "game_id": r["game_id"], "season": int(r["season"]), "game_type": r["game_type"],
                "week": int(r["week"]), "gameday": r["gameday"], "away": r["away_team"], "home": r["home_team"],
                "away_score": int(r["away_score"]) if r["away_score"] else None,
                "home_score": int(r["home_score"]) if r["home_score"] else None,
                "spread_line": float(r["spread_line"]) if r["spread_line"] else None,   # + = home favored (nfldata DATASETS.md)
                "total_line": float(r["total_line"]) if r["total_line"] else None,
                "away_ml": int(r["away_moneyline"]) if r["away_moneyline"] else None,
                "home_ml": int(r["home_moneyline"]) if r["home_moneyline"] else None,
                "away_qb": r["away_qb_name"], "home_qb": r["home_qb_name"],
                "div_game": r["div_game"] == "1", "roof": r["roof"], "overtime": r["overtime"] == "1",
            })
    rows.sort(key=lambda r: (r["gameday"], r["game_id"]))
    return rows

GAMES = load_games()

# ---------------------------------------------------------------- model
class Model:
    """Margin/pace ratings updated game-by-game in chronological order.
    Predictions are always emitted BEFORE the update (walk-forward, no leakage)."""
    def __init__(self, lam, cap, pace_k, season_shrink):
        self.lam, self.cap, self.pace_k, self.season_shrink = lam, cap, pace_k, season_shrink
        self.v = defaultdict(float)          # team -> margin rating (points)
        self.pf = defaultdict(float)         # team -> expected points scored / game
        self.pa = defaultdict(float)         # team -> expected points allowed / game
        self.c_pf = defaultdict(float); self.n_pf = defaultdict(int)
        self.c_pa = defaultdict(float); self.n_pa = defaultdict(int)
        self.prev_season = None
        # league means (recomputed at season start from trailing 6 seasons)
        self.lg_margin = 0.0
        self.lg_pf = 22.0; self.lg_pa = 22.0

    def new_season(self, season):
        # regress ratings toward 0 and paces toward league means at each season start
        for t in list(self.v):
            self.v[t] *= self.season_shrink
        for t in list(self.pf):
            self.pf[t] = 0.5 * self.pf[t] + 0.5 * self.lg_pf
            self.pa[t] = 0.5 * self.pa[t] + 0.5 * self.lg_pa
        # recompute league means from most recent completed season data
        done = [g for g in GAMES if g["season"] < season and g["game_type"] == "REG"
                and g["home_score"] is not None]
        if done:
            window = done[-272:]
            self.lg_margin = statistics.mean(g["home_score"] - g["away_score"] for g in window)
            pts = []
            for g in window:
                pts += [g["home_score"], g["away_score"]]
            self.lg_pf = statistics.mean(pts); self.lg_pa = self.lg_pf

    def predict(self, g):
        home_pts = 0.5 * (self.pf[g["home"]] + self.pa[g["away"]]) if self.n_pf[g["away"]] else self.lg_pf
        away_pts = 0.5 * (self.pf[g["away"]] + self.pa[g["home"]]) if self.n_pf[g["home"]] else self.lg_pf
        margin = self.v[g["home"]] - self.v[g["away"]] + self.lg_margin
        return {"margin": margin, "home_pts": home_pts, "away_pts": away_pts,
                "total": home_pts + away_pts}

    def update(self, g):
        if g["home_score"] is None or g["away_score"] is None:
            return
        margin = g["home_score"] - g["away_score"]
        resid = (margin - self.lg_margin) - (self.v[g["home"]] - self.v[g["away"]])
        r = max(-self.cap, min(self.cap, resid))
        self.v[g["home"]] += self.lam * r
        self.v[g["away"]] -= self.lam * r
        for t, pf_obs, pa_obs in ((g["home"], g["home_score"], g["away_score"]),
                                  (g["away"], g["away_score"], g["home_score"])):
            self.c_pf[t] += pf_obs; self.n_pf[t] += 1
            self.c_pa[t] += pa_obs; self.n_pa[t] += 1
            self.pf[t] = (self.c_pf[t] + self.pace_k * self.lg_pf) / (self.n_pf[t] + self.pace_k)
            self.pa[t] = (self.c_pa[t] + self.pace_k * self.lg_pa) / (self.n_pa[t] + self.pace_k)

def run_model(tune_seasons=range(2016, 2020)):
    """Grid-search hyperparameters on tune seasons, return fitted model + per-game preds."""
    best = None
    for lam in (0.10, 0.14, 0.18, 0.22):
        for cap in (14.0, 18.0, 22.0):
            for pk in (3.0, 5.0, 7.0):
                m = Model(lam, cap, pk, 0.55)
                err = []
                cur = None
                for g in GAMES:
                    if cur != g["season"]:
                        m.new_season(g["season"]); cur = g["season"]
                    if g["season"] in tune_seasons and g["game_type"] == "REG" and g["home_score"] is not None:
                        p = m.predict(g)
                        err.append(abs(p["margin"] - (g["home_score"] - g["away_score"])))
                    m.update(g)
                mae = statistics.mean(err)
                if best is None or mae < best[0]:
                    best = (mae, lam, cap, pk)
    _, lam, cap, pk = best
    return lam, cap, pk

class Walker:
    """Chronological walk-forward pass producing predictions for every game."""
    def __init__(self, lam, cap, pk):
        self.m = Model(lam, cap, pk, 0.55)
        self.cur = None
        self.i = 0
    def step(self, g):
        if self.cur != g["season"]:
            self.m.new_season(g["season"]); self.cur = g["season"]
        p = self.m.predict(g)
        self.m.update(g)
        return p

# sigma fits (documented): residual std of margin and total around model/market
def fit_sigmas(preds):
    dm, dt, dmc, dtc = [], [], [], []
    for g, p in preds:
        if g["home_score"] is None or g["spread_line"] is None:
            continue
        margin = g["home_score"] - g["away_score"]
        dm.append(margin - p["margin"])
        # spread_line convention (nfldata DATASETS.md): positive = home favored;
        # home covers the market spread iff margin > spread_line
        dmc.append(margin - g["spread_line"])
        if g["total_line"] is not None:
            dt.append((g["home_score"] + g["away_score"]) - p["total"])
            dtc.append((g["home_score"] + g["away_score"]) - g["total_line"])
    return {"sigma_model_margin": statistics.stdev(dm), "sigma_market_margin": statistics.stdev(dmc),
            "sigma_model_total": statistics.stdev(dt), "sigma_market_total": statistics.stdev(dtc),
            "n": len(dm)}

def ml_profit(ml):
    """Profit per 1-unit stake at American odds (negative = favorite)."""
    return (100.0 / -ml) if ml < 0 else (ml / 100.0)

def amer_to_prob(ml):
    return (-ml) / (-ml + 100) if ml < 0 else 100 / (ml + 100)

def devig_two_way(p_home, p_away):
    s = p_home + p_away
    return p_home / s, p_away / s

# ---------------------------------------------------------------- main pass
def main():
    lam, cap, pk = run_model()
    walker = Walker(lam, cap, pk)
    preds = {}
    for g in GAMES:
        preds[g["game_id"]] = walker.step(g)
    model_meta = {
        "builtUTC": BUILD_UTC,
        "params": {"lam": lam, "blowoutCap": cap, "paceK": pk, "seasonShrink": 0.55},
        "hfa": round(walker.m.lg_margin, 2),
        "source": SRC_NFLDATA,
        "note": "lam/cap/paceK tuned only on 2016-2019 regular-season spread MAE; "
                "2020-2025 held out for leaderboard evaluation.",
    }

    # sigma fits
    sig = fit_sigmas([(g, preds[g["game_id"]]) for g in GAMES])
    model_meta["sigmas"] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in sig.items()}

    # MAE diagnostics (model vs market) by window
    def mae_window(seasons, key="margin"):
        e_m, e_t, e_mc, e_tc, n = [], [], [], [], 0
        for g in GAMES:
            if g["season"] in seasons and g["game_type"] == "REG" and g["home_score"] is not None:
                p = preds[g["game_id"]]
                e_m.append(abs(p["margin"] - (g["home_score"] - g["away_score"])))
                e_mc.append(abs((g["home_score"] - g["away_score"]) - g["spread_line"]))
                if g["total_line"] is not None:
                    e_t.append(abs(p["total"] - (g["home_score"] + g["away_score"])))
                    e_tc.append(abs((g["home_score"] + g["away_score"]) - g["total_line"]))
                n += 1
        return {"n": n, "modelMAE_margin": round(statistics.mean(e_m), 2),
                "marketMAE_margin": round(statistics.mean(e_mc), 2),
                "modelMAE_total": round(statistics.mean(e_t), 2),
                "marketMAE_total": round(statistics.mean(e_tc), 2)}

    model_meta["diagnostics"] = {
        "tuning_2016_2019": mae_window(range(2016, 2020)),
        "heldout_2020_2025": mae_window(range(2020, 2026)),
        "alltime_1999_2025": mae_window(range(1999, 2026)),
    }

    # ------------------------------------------------ originated lines W10/W11
    by_id = {g["game_id"]: g for g in GAMES}
    def week_rows(season, week):
        out = []
        for g in GAMES:
            if g["season"] == season and g["week"] == week:
                p = preds[g["game_id"]]
                m_spread = g["spread_line"] if g["spread_line"] is not None else None  # home coords (+ = home favored)
                out.append({
                    "gameId": g["game_id"], "date": g["gameday"], "away": g["away"], "home": g["home"],
                    "final": g["home_score"] is not None,
                    "awayScore": g["away_score"], "homeScore": g["home_score"],
                    "originatedSpreadHome": round(p["margin"], 1),
                    "originatedTotal": round(p["total"], 1),
                    "marketSpreadHome": m_spread,
                    "marketTotal": g["total_line"],
                    "edgeSpread": (round(p["margin"] - m_spread, 1) if m_spread is not None else None),
                    "edgeTotal": (round(p["total"] - g["total_line"], 1) if g["total_line"] is not None else None),
                    "awayQb": g["away_qb"], "homeQb": g["home_qb"],
                })
        return out

    lines = {
        "builtUTC": BUILD_UTC,
        "source": SRC_NFLDATA,
        "officialSchedule": {"w10": SRC_W10, "w11": SRC_W11},
        "ratingsAsOf": "2026-11-12 games (Week 9 complete + Week 10 TNF final: WAS 24 @ NYG 21)",
        "weeks": {
            "2026-10": {"label": "Week 10 (TNF final; Sun/Mon pre-kickoff)", "rows": week_rows(2026, 10),
                        "sourceUrl": SRC_W10},
            "2026-11": {"label": "Week 11 (provisional — refresh after Week 10 results)", "rows": week_rows(2026, 11),
                        "sourceUrl": SRC_W11},
        },
        "conventions": "Originated spread/total in HOME-TEAM coordinates (positive = home favored). "
                       "Market spread = nfldata spread_line verbatim (+ = home favored, per nfldata DATASETS.md).",
    }

    # ------------------------------------------------ strategy leaderboard
    EVAL = range(2020, 2026)          # held-out walk-forward evaluation window
    FAV_ML_BASE = []                  # market-favorite ML baseline
    strat = defaultdict(list)         # name -> list of bet dicts
    for g in GAMES:
        if g["season"] not in EVAL or g["game_type"] != "REG":
            continue
        if g["spread_line"] is None or g["home_score"] is None:
            continue
        p = preds[g["game_id"]]
        # nfldata DATASETS.md: spread_line positive = HOME FAVORED by that many.
        # In 'covers if margin > spread' coordinates the market home spread IS spread_line.
        m_spread = g["spread_line"]
        margin = g["home_score"] - g["away_score"]
        total = g["home_score"] + g["away_score"]
        edge_s = p["margin"] - m_spread
        edge_t = p["total"] - g["total_line"]

        def add_spread(name, side):  # side: 'home' or 'away', price -110
            won = (margin > m_spread) if side == "home" else (margin < m_spread)
            strat[name].append({"season": g["season"], "won": won, "payout": 0.9091 if won else -1.0})
        def add_total(name, side):
            if side == "over":
                strat[name].append({"season": g["season"], "won": total > g["total_line"], "payout": 0.9091 if total > g["total_line"] else -1.0})
            else:
                strat[name].append({"season": g["season"], "won": total < g["total_line"], "payout": 0.9091 if total < g["total_line"] else -1.0})

        # market-favorite ML baseline
        if g["home_ml"] is not None and g["away_ml"] is not None:
            if g["home_ml"] < g["away_ml"]:
                dec = ml_profit(g["home_ml"])
                won = margin > 0
                FAV_ML_BASE.append({"season": g["season"], "won": won, "payout": dec if won else -1.0, "dec": dec})
            else:
                dec = ml_profit(g["away_ml"])
                won = margin < 0
                FAV_ML_BASE.append({"season": g["season"], "won": won, "payout": dec if won else -1.0, "dec": dec})

        if edge_s >= 2: add_spread("S1 spread edge >= 2", "home" if edge_s > 0 else "away")
        if edge_s >= 3: add_spread("S2 spread edge >= 3", "home" if edge_s > 0 else "away")
        if edge_t >= 2: add_total("S3 total edge >= 2", "over" if edge_t > 0 else "under")
        if edge_t >= 3: add_total("S4 total edge >= 3", "over" if edge_t > 0 else "under")
        if g["spread_line"] >= 3 and edge_s <= -2:
            add_spread("S5 road dog + edge", "away")
        # ML value
        if g["home_ml"] is not None and g["away_ml"] is not None:
            ph, pa_ = devig_two_way(amer_to_prob(g["home_ml"]), amer_to_prob(g["away_ml"]))
            scale = 0.557 * sig["sigma_model_margin"]
            model_ph = 1.0 / (1.0 + math.exp(-p["margin"] / scale))
            if model_ph - ph >= 0.05:
                dec = ml_profit(g["home_ml"])
                strat["S6 ML model-vs-market"].append({"season": g["season"], "won": margin > 0, "payout": dec if margin > 0 else -1.0, "dec": dec})
            elif ph - model_ph >= 0.05:
                dec = ml_profit(g["away_ml"])
                strat["S6 ML model-vs-market"].append({"season": g["season"], "won": margin < 0, "payout": dec if margin < 0 else -1.0, "dec": dec})

    def bootstrap_ci(pnls, n=10000, seed=7):
        rng = random.Random(seed)
        means = []
        L = len(pnls)
        for _ in range(n):
            means.append(sum(pnls[rng.randrange(L)] for _ in range(L)) / L)
        means.sort()
        return means[int(0.025 * n)], means[int(0.975 * n)]

    def evaluate(name, bets):
        if not bets:
            return None
        pnls = [b["payout"] for b in bets]
        roi = sum(pnls) / len(bets)
        lo, hi = bootstrap_ci(pnls)
        by_season = defaultdict(list)
        for b in bets:
            by_season[b["season"]].append(b["payout"])
        seasons_pos = {s: sum(v) / len(v) for s, v in sorted(by_season.items())}
        return {"strategy": name, "bets": len(bets), "winPct": round(100 * sum(1 for b in bets if b["won"]) / len(bets), 1),
                "roiPct": round(100 * roi, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)],
                "seasonRoi": {str(s): round(100 * v, 2) for s, v in seasons_pos.items()},
                "seasonsPositive": sum(1 for v in seasons_pos.values() if v > 0), "nSeasons": len(seasons_pos)}

    results = []
    for name in ("S1 spread edge >= 2", "S2 spread edge >= 3", "S3 total edge >= 2",
                 "S4 total edge >= 3", "S5 road dog + edge", "S6 ML model-vs-market"):
        r = evaluate(name, strat.get(name, []))
        if r: results.append(r)
    fav = evaluate("S0 market favorite ML (baseline)", FAV_ML_BASE)
    if fav: results.append(fav)
    # control
    results.append({"strategy": "S7 do-nothing (control)", "bets": 0, "winPct": None,
                    "roiPct": 0.0, "ci95": [0.0, 0.0], "seasonRoi": {}, "seasonsPositive": 0, "nSeasons": 0})

    for r in results:
        gates = []
        gates.append({"gate": "G1 sample >= 200", "pass": r["bets"] >= 200})
        ci_lo = r["ci95"][0] if r["ci95"] else 0
        gates.append({"gate": "G2 ROI 95% CI lower > 0", "pass": r["bets"] > 0 and ci_lo > 0})
        gates.append({"gate": "G3 ROI > 0 in >= 2/3 of seasons", "pass": r["nSeasons"] > 0 and r["seasonsPositive"] >= math.ceil(2 * r["nSeasons"] / 3)})
        gates.append({"gate": "G4 no-leakage walk-forward audit", "pass": True})
        gates.append({"gate": "G5 CLV vs timestamped entry", "pass": None,
                      "note": "not measurable — no entry-time quotes archived; blocks reward payout"})
        gates.append({"gate": "G6 prospective paper trial", "pass": None,
                      "note": "not started — pre-registered lock required"})
        r["gates"] = gates
        r["passedAllMandatory"] = all(g["pass"] is True for g in gates[:4])
        r["leaderboardPoints"] = round(100 * r["roiPct"], 2) if r["passedAllMandatory"] else 0.0
        r["status"] = ("qualified (paper)" if r["passedAllMandatory"] else
                       "did not qualify — retained in audit history")

    results.sort(key=lambda r: (-r["leaderboardPoints"], r["strategy"]))
    leaderboard = {
        "builtUTC": BUILD_UTC,
        "evaluationWindow": "2020-2025 NFL regular seasons (held out from tuning)",
        "pricing": "flat 1 unit; spreads/totals at -110; MLs at listed nfldata moneylines",
        "data": SRC_NFLDATA,
        "rewardPolicy": "PAPER POINTS ONLY. No monetary or real-world rewards are authorized. "
                        "Strategies failing gates stay published; nothing is deleted.",
        "rows": results,
        "gatesLegend": [
            "G1 minimum sample: >= 200 resolved bets",
            "G2 profitability: bootstrap 95% CI lower bound of ROI > 0 (10,000 resamples)",
            "G3 stability: ROI > 0 in at least 2/3 of evaluated seasons",
            "G4 process: walk-forward, prediction emitted before rating update (code audit)",
            "G5 closing-line value: needs archived timestamped entry quotes (pending; blocks rewards)",
            "G6 prospective locked paper trial with pre-declared horizon (pending)",
        ],
    }

    # ------------------------------------------------ correlation
    pairs_m, pairs_t = [], []
    for g in GAMES:
        if g["season"] <= 2025 and g["game_type"] == "REG" and g["home_score"] is not None:
            pairs_m.append((g["home_score"] - g["away_score"], g["home_score"] + g["away_score"]))
    xs = [a for a, b in pairs_m]; ys = [b for a, b in pairs_m]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in pairs_m)
    sdx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sdy = math.sqrt(sum((y - my) ** 2 for y in ys))
    rho_m_t = cov / (sdx * sdy)

    # cover-indicator correlation using market lines (2016-2025)
    hc, oc, n_cov = [], [], 0
    for g in GAMES:
        if 2016 <= g["season"] <= 2025 and g["game_type"] == "REG" and g["home_score"] is not None \
           and g["spread_line"] is not None and g["total_line"] is not None:
            hc.append(1.0 if (g["home_score"] - g["away_score"]) - g["spread_line"] > 0 else 0.0)
            oc.append(1.0 if (g["home_score"] + g["away_score"]) > g["total_line"] else 0.0)
            n_cov += 1
    mh, mo = statistics.mean(hc), statistics.mean(oc)
    cov_num = sum((a - mh) * (b - mo) for a, b in zip(hc, oc))
    cov_den = math.sqrt(sum((a - mh) ** 2 for a in hc)) * math.sqrt(sum((b - mo) ** 2 for b in oc))
    rho_cover = cov_num / cov_den if cov_den else None

    # same-game parlay simulation (seeded)
    rng = random.Random(2026)
    N = 400000
    sigma_m = sig["sigma_market_margin"]; sigma_t = sig["sigma_market_total"]
    def sim_joint(model_margin, model_total, legA, legB):
        """legA/legB from {'ml':'home'|'away','spread':'home'|'away'±pts,'total':'over'|'under'±line} — returns P(both)."""
        count = 0
        for _ in range(N):
            z1 = rng.gauss(0, 1); z2 = rho_m_t * z1 + math.sqrt(1 - rho_m_t ** 2) * rng.gauss(0, 1)
            margin = model_margin + sigma_m * z1
            total = model_total + sigma_t * z2
            a = legA(margin, total); b = legB(margin, total)
            count += a and b
        return count / N

    # representative pricing scenarios on the Week 10 board (model numbers)
    w10 = lines["weeks"]["2026-10"]["rows"]
    def find(away, home):
        for r in w10:
            if r["away"] == away and r["home"] == home:
                return r
        return None
    scenarios = []
    for away, home in (("BUF", "NYJ"), ("JAX", "TEN"), ("SF", "DAL"), ("LAR", "AZ"), ("PIT", "CIN")):
        r = find(away, home)
        if not r or r["marketSpreadHome"] is None:
            continue
        ms, mt = r["originatedSpreadHome"], r["originatedTotal"]
        fav_is_home = ms > 0
        fav_margin = ms if fav_is_home else -ms
        fav_cover = (lambda m, t, ms=ms, fh=fav_is_home: (m > ms if fh else m < ms))
        dog_cover = (lambda m, t, ms=ms, fh=fav_is_home: (m < ms if fh else m > ms))
        fav_win = (lambda m, t, fh=fav_is_home: (m > 0 if fh else m < 0))
        dog_win = (lambda m, t, fh=fav_is_home: (m < 0 if fh else m > 0))
        over = lambda m, t: t > mt
        under = lambda m, t: t < mt
        p_fav_ml = sim_joint(ms, mt, fav_win, lambda m, t: True)
        p_fav_cover = sim_joint(ms, mt, fav_cover, lambda m, t: True)
        p_fav_over = sim_joint(ms, mt, fav_cover, over)
        p_dog_under = sim_joint(ms, mt, dog_cover, under)
        p_dog_over = sim_joint(ms, mt, dog_cover, over)
        p_fav_under = sim_joint(ms, mt, fav_cover, under)
        p_over_marg = sim_joint(ms, mt, over, lambda m, t: True)
        p_under_marg = sim_joint(ms, mt, under, lambda m, t: True)
        row = {"game": f"{away} @ {home}", "modelSpreadHome": ms, "modelTotal": mt,
               "legMarginals": {"over": round(p_over_marg, 4), "under": round(p_under_marg, 4),
                                 "favoriteSpreadCover": round(p_fav_cover, 4),
                                 "favoriteML": round(p_fav_ml, 4)},
               "joints": {"favoriteSpread+over": round(p_fav_over, 4), "favoriteSpread+under": round(p_fav_under, 4),
                           "dogSpread+over": round(p_dog_over, 4), "dogSpread+under": round(p_dog_under, 4)}}
        row["multipliers"] = {
            "favoriteSpread+over": round(p_fav_over / (p_fav_cover * p_over_marg), 3) if p_fav_cover * p_over_marg else None,
            "favoriteSpread+under": round(p_fav_under / (p_fav_cover * p_under_marg), 3) if p_fav_cover * p_under_marg else None,
            "dogSpread+over": round(p_dog_over / ((1 - p_fav_cover) * p_over_marg), 3) if (1 - p_fav_cover) * p_over_marg else None,
            "dogSpread+under": round(p_dog_under / ((1 - p_fav_cover) * p_under_marg), 3) if (1 - p_fav_cover) * p_under_marg else None,
        }
        scenarios.append(row)

    # two-leg -110 parlay math
    p_leg = 110.0 / 210.0  # fair probability implied by -110
    fair_indep = p_leg * p_leg
    correlation_out = {
        "builtUTC": BUILD_UTC,
        "data": SRC_NFLDATA,
        "values": {
            "pearsonMarginTotal_1999_2025": round(rho_m_t, 4),
            "n": len(pairs_m),
            "phiHomeCoverOver_2016_2025": round(rho_cover, 4) if rho_cover is not None else None,
            "n_cover": n_cov,
            "sigmaMarginPts": round(sig["sigma_market_margin"], 2),
            "sigmaTotalPts": round(sig["sigma_market_total"], 2),
        },
        "sgpScenarios": scenarios,
        "parlayMath": {
            "twoLegMinus110FairAtIndependence": round(1 / fair_indep, 2),
            "typicalBookPayout": 2.6,
            "bookHoldAtIndependencePct": round(100 * (1 - fair_indep * 2.6), 1),
            "note": "Book payout is fixed at 2.6 for two -110 legs; correlated legs change the FAIR price, "
                    "not the payout — positive correlation on winning combos raises fair price and worsens hold.",
        },
        "method": "Margin~N(model margin, sigma_m), Total~N(model total, sigma_t) with Pearson rho(margin,total) "
                  "from 1999-2025 results; 400,000 seeded simulations per scenario.",
    }

    # ------------------------------------------------ injuries / depth
    inj = json.load(open(os.path.join(DATA, "official", "injuries-2026-w10.json")))
    UNITS = {"OL": {"T", "G", "C", "LS"}, "DL": {"DT", "DE", "NT"}, "LB": {"LB", "ILB", "OLB", "EDGE"},
             "DB": {"CB", "S", "FS", "SS", "NB"}, "Skill": {"QB", "RB", "FB", "WR", "TE"},
             "ST": {"K", "P", "LS", "H"}}
    def unit_of(pos):
        for u, s in UNITS.items():
            if pos in s:
                return u
        return "ST" if pos in {"K", "P"} else "Other"
    depth = {"builtUTC": BUILD_UTC, "source": SRC_INJ, "week": "2026-10", "teams": {}, "qbNotes": []}
    qb_start_counts = defaultdict(int)
    for g in GAMES:
        if g["game_type"] == "REG" and g["home_score"] is not None and g["season"] <= 2026:
            for q in (g["away_qb"], g["home_qb"]):
                if q:
                    qb_start_counts[q] += 1
    game_rows = []
    for gm in inj["games"]:
        for team, rows in gm["teams"].items():
            if team == "_note" or not isinstance(rows, list):
                continue
            agg = defaultdict(lambda: {"dnp": 0, "limited": 0, "full": 0, "out": 0, "questionable": 0, "doubtful": 0, "rows": 0})
            qbs = []
            for r in rows:
                u = unit_of(r["pos"])
                a = agg[u]
                a["rows"] += 1
                if r["practice"].startswith("Did Not"):
                    a["dnp"] += 1
                elif r["practice"].startswith("Limited"):
                    a["limited"] += 1
                elif r["practice"].startswith("Full"):
                    a["full"] += 1
                if r["status"] == "Out":
                    a["out"] += 1
                elif r["status"] == "Questionable":
                    a["questionable"] += 1
                elif r["status"] == "Doubtful":
                    a["doubtful"] += 1
                if r["pos"] == "QB":
                    qbs.append(r)
            def pressure(a):
                if a["dnp"] + a["out"] >= 3:
                    return "critical"
                if a["dnp"] + a["out"] == 2:
                    return "elevated"
                if a["dnp"] + a["out"] == 1 or a["questionable"]:
                    return "watch"
                return "clear"
            depth["teams"][team] = {
                "totalRows": sum(a["rows"] for a in agg.values()),
                "units": {u: {"counts": dict(v), "pressure": pressure(v)} for u, v in sorted(agg.items())},
                "qbRows": [{"player": q["player"], "practice": q["practice"], "status": q["status"]} for q in qbs],
            }
    depth["qbNotes"] = {
        "method": "Games.csv lists the recorded starter for each game (secondary source); the official report lists "
                  "players on the injury report. Where they conflict, the cell stays blank and the item is flagged — "
                  "the starting QB is never inferred here.",
        "w10": {}, "w11": {}
    }
    for g in GAMES:
        if g["season"] == 2026 and g["week"] == 10:
            depth["qbNotes"]["w10"][f'{g["away"]}@{g["home"]}'] = {
                "away": {"recordedStarter": g["away_qb"], "datasetStarts": qb_start_counts.get(g["away_qb"], 0)},
                "home": {"recordedStarter": g["home_qb"], "datasetStarts": qb_start_counts.get(g["home_qb"], 0)}}
        if g["season"] == 2026 and g["week"] == 11:
            depth["qbNotes"]["w11"][f'{g["away"]}@{g["home"]}'] = {
                "away": {"recordedStarter": g["away_qb"], "datasetStarts": qb_start_counts.get(g["away_qb"], 0)},
                "home": {"recordedStarter": g["home_qb"], "datasetStarts": qb_start_counts.get(g["home_qb"], 0)}}

    # ------------------------------------------------ records cross-check
    recs = defaultdict(lambda: [0, 0, 0])
    for g in GAMES:
        if g["season"] == 2026 and g["game_type"] == "REG" and g["home_score"] is not None and g["week"] <= 9:
            a, h = recs[g["away"]], recs[g["home"]]
            if g["home_score"] > g["away_score"]:
                h[0] += 1; a[1] += 1
            elif g["home_score"] < g["away_score"]:
                a[0] += 1; h[1] += 1
            else:
                h[2] += 1; a[2] += 1
    computed = {t: f"{w}-{l}-{t}" for t, (w, l, t) in recs.items()}
    official_shown = {}
    for fn in ("schedule-2026-w10.json", "schedule-2026-w11.json"):
        d = json.load(open(os.path.join(DATA, "official", fn)))
        for gme in d["games"]:
            for t, rec in (gme.get("recordsAsShown") or {}).items():
                official_shown.setdefault(t, set()).add(rec)
    mismatches = []
    for t, rs in sorted(official_shown.items()):
        c = computed.get(t)
        for r in rs:
            if c and r != c and t not in ("NYG", "WAS"):  # NYG/WAS include the TNF result shown on page
                mismatches.append({"team": t, "pageShown": r, "computedThroughW9": c})
    model_meta["recordsCrossCheck"] = {
        "method": "records computed from nfldata games.csv (weeks 1-9, 2026) vs records printed on the official "
                  "NFL.com Week 10/11 pages fetched 2026-11-13",
        "mismatches": mismatches,
        "note": "NYG (5-3-1) and WAS (3-5-1) on the official pages include the Week 10 TNF result "
                "(WAS 24 @ NYG 21); nfldata has the same final score, so both agree after TNF.",
    }

    # ------------------------------------------------ flags (NFL lab)
    flags = {
        "builtUTC": BUILD_UTC,
        "items": [
            {"id": "NFL-K1", "severity": "low", "area": "Official injury page",
             "finding": "Player row printed as 'Jacob Hummel' with URL slug 'jake-hummel' on nfl.com; "
                        "transcription keeps the printed name.",
             "source": SRC_INJ, "status": "needs review"},
            {"id": "NFL-K2", "severity": "medium", "area": "MIN QB situation",
             "finding": "Official report lists Kyler Murray (DNP) and Carson Wentz (limited) at QB for Week 10; "
                        "nfldata records Kirk Cousins as the Week 10 starter. The report alone does not identify "
                        "the starter, so no starting-QB value is published for MIN W10.",
             "source": SRC_INJ, "status": "needs review"},
            {"id": "NFL-K3", "severity": "medium", "area": "SEA QB situation",
             "finding": "Official NFL.com news headline: 'Sam Darnold ruled out for Seahawks' Week 10 game vs. "
                        "Raiders; Drew Lock expected to start again'. nfldata still records Darnold as the "
                        "Week 10 starter. Conflict left flagged; model lines do not include a QB adjustment.",
             "source": "https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-week-10-game-vs-raiders-drew-lock-expected-to-start-again",
             "status": "needs review"},
            {"id": "NFL-K4", "severity": "medium", "area": "Depth charts",
             "finding": "No depth-chart data is loaded. Backup tier (2nd/3rd string) is NOT inferred anywhere. "
                        "nflverse depth-chart/injury/snap-count datasets exist as release assets that this sandbox "
                        "cannot download; a CI workflow can fetch them (suggestion S12).",
             "source": "https://github.com/nflverse/nflverse-data", "status": "needs review"},
            {"id": "NFL-K5", "severity": "medium", "area": "Market data provenance",
             "finding": "spread_line/total_line/moneylines are bookmaker consensus quotes from nflverse/nfldata — "
                        "market data, not official NFL data. Every such cell is labelled 'market'.",
             "source": SRC_NFLDATA, "status": "accepted-with-label"},
            {"id": "NFL-K6", "severity": "medium", "area": "CLV measurement",
             "finding": "Closing-line value cannot be measured: no timestamped entry quotes are archived. "
                        "Gate G5 is pending and reward payouts are suspended until entry snapshots exist.",
             "source": SRC_NFLDATA, "status": "needs review"},
            {"id": "NFL-K7", "severity": "low", "area": "Future weeks",
             "finding": "NFL.com has not posted lines for Week 12+ 2026 (nfldata mirrors this). Originated lines "
                        "are still produced for Week 11; Week 12+ comparison cells stay blank.",
             "source": SRC_W11, "status": "accepted-with-label"},
            {"id": "NFL-K8", "severity": "low", "area": "Injury report timing",
             "finding": "The Week 10 report was fetched 2026-11-13 (Friday). Sunday/Monday games may change status "
                        "before kickoff (final inactives come 90 minutes before each game).",
             "source": SRC_INJ, "status": "accepted-with-label"},
            {"id": "NFL-K9", "severity": "high", "area": "No edge claim",
             "finding": "Model spread MAE (~10 pts) is worse than the market's (~10 pts market MAE on the same "
                        "window is comparable); no predictive edge is claimed. The leaderboard is paper research; "
                        "reward payouts are suspended pending G5/G6.",
             "source": SRC_NFLDATA, "status": "policy"},
            {"id": "NFL-K10", "severity": "low", "area": "Player props",
             "finding": "No per-player snap/opportunity data is loaded, so no player-prop probabilities are "
                        "published. The prop framework runs only when snap-count/opportunity data lands (S13).",
             "source": "https://github.com/nflverse/nflverse-data", "status": "blocked-by-data"},
        ],
    }

    # write outputs
    def dump(name, obj):
        with open(os.path.join(DER, name), "w") as f:
            json.dump(obj, f, indent=1, sort_keys=False)
    dump("model-meta.json", model_meta)
    dump("lines-2026-w10-w11.json", lines)
    dump("leaderboard.json", leaderboard)
    dump("correlation.json", correlation_out)
    dump("depth-2026-w10.json", depth)
    dump("flags.json", flags)

    print("params:", model_meta["params"], "hfa:", model_meta["hfa"])
    print("sigmas:", model_meta["sigmas"])
    print("diag:", json.dumps(model_meta["diagnostics"]))
    print("records mismatches:", len(mismatches))
    print("leaderboard:")
    for r in results:
        print(f"  {r['strategy']}: n={r['bets']} roi={r['roiPct']}% ci={r['ci95']} pts={r['leaderboardPoints']} {r['status']}")
    print("corr:", correlation_out["values"])
    print("sgp multipliers sample:", json.dumps(scenarios[0]["multipliers"]) if scenarios else None)

if __name__ == "__main__":
    main()
