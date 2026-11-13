#!/usr/bin/env python3
"""Own NFL line model, strategy backtests, validation gates, correlations and
parlay checks for the NFL lines lab.

Inputs (not committed, fetched by scripts/nfl_lab/fetch_games.py):
  /tmp/nfl-lab-raw/games.csv     nfldata games file (scores, rest, QB ids, lines)
Input (committed):
  data/nfl-lab/injuries-qb-2016-2026.json   QB injury rows from the NFL official reports (nflverse mirror)

Method (walk-forward; no game uses its own result or any later game):
  * Power rating per team, updated after each game by K * (actual margin - predicted margin).
    Ratings regress toward 0 at each season start (factor REGRESS). Home edge HFA points unless neutral site.
  * K is chosen on 2006-2015 only (lowest MAE). 2016-2025 is the out-of-sample test window.
    2026 is reported as a forward (season-to-date) check.
  * Totals: exponentially weighted average of each team's recent game totals (alpha ALPHA).

Strategies are scored at the -110 price (break-even 52.38%). Pushes are excluded.
Gates: see GATES below. Market spread/total lines are third-party, unverified inputs.
Gate G0 (provenance) therefore FAILS for every strategy, and the report says so.

Usage: python3 scripts/nfl_lab/model.py
"""
import csv
import json
import math
import os
import random
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.environ.get("NFL_LAB_RAW", "/tmp/nfl-lab-raw")
OUT = os.path.join(REPO, "data", "nfl-lab")

K_GRID = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
REGRESS = 0.6
HFA = 2.0
ALPHA = 0.15
TOT_EDGE = 3.0
MODEL_EDGES = [2.0, 3.0, 4.0]
TRAIN = (2006, 2015)
TEST = (2016, 2025)
FORWARD = 2026
BREAKEVEN = 1 / 1.9091  # 52.38% at -110
PAYOUT = 100 / 110
N_BOOT = 2000
RNG = random.Random(20261113)


def num(x):
    try:
        return float(x) if x not in ("", None) else None
    except ValueError:
        return None


def load_games():
    rows = []
    with open(os.path.join(RAW, "games.csv"), newline="") as f:
        for r in csv.DictReader(f):
            g = {
                "game_id": r["game_id"], "season": int(r["season"]), "game_type": r["game_type"],
                "week": int(r["week"]), "gameday": r["gameday"], "gametime": r["gametime"],
                "home": r["home_team"], "away": r["away_team"],
                "home_score": num(r["home_score"]), "away_score": num(r["away_score"]),
                "result": num(r["result"]), "total": num(r["total"]),
                "spread": num(r["spread_line"]), "total_line": num(r["total_line"]),
                "home_rest": num(r["home_rest"]), "away_rest": num(r["away_rest"]),
                "neutral": r["location"] == "Neutral",
                "home_qb_id": r["home_qb_id"], "away_qb_id": r["away_qb_id"],
                "home_qb_name": r["home_qb_name"], "away_qb_name": r["away_qb_name"],
                "stadium": r["stadium"],
                "pfr": r["pfr"],
            }
            rows.append(g)
    rows.sort(key=lambda g: (g["gameday"], g["game_id"]))
    return rows


def run_model(games, K):
    """Walk-forward ratings and totals. Stores each game's prediction BEFORE the update."""
    R = defaultdict(float)
    E = defaultdict(lambda: None)
    league_prev = 44.0
    cur = None
    season_totals = defaultdict(list)
    for g in games:
        if g["season"] != cur:
            if cur is not None:
                league_prev = (sum(season_totals[cur]) / len(season_totals[cur])) if season_totals[cur] else league_prev
            cur = g["season"]
            for t in list(R):
                R[t] *= REGRESS
            for t in list(E):
                if E[t] is not None:
                    E[t] = 0.6 * E[t] + 0.4 * league_prev
        h, a = g["home"], g["away"]
        hfa = 0.0 if g["neutral"] else HFA
        g["model_margin"] = R[h] - R[a] + hfa  # positive = home favoured
        eh = E[h] if E[h] is not None else league_prev
        ea = E[a] if E[a] is not None else league_prev
        g["model_total"] = (eh + ea) / 2.0
        if g["result"] is not None:
            err = g["result"] - g["model_margin"]
            R[h] += K * err
            R[a] -= K * err
            tot = g["total"]
            season_totals[g["season"]].append(tot)
            for t in (h, a):
                E[t] = tot if E[t] is None else (1 - ALPHA) * E[t] + ALPHA * tot
    return games


def mae(rows, key, target="result"):
    errs = [abs(g[target] - g[key]) for g in rows if g[target] is not None and g[key] is not None]
    return sum(errs) / len(errs) if errs else None


def binom_two_sided(k, n, p=0.5):
    """Exact two-sided binomial p-value (computed in log space)."""
    if n == 0:
        return 1.0
    lp = math.log(p)
    lq = math.log(1 - p)

    def logpmf(i):
        return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                + i * lp + (n - i) * lq)
    lk = logpmf(k)
    total = 0.0
    for i in range(n + 1):
        li = logpmf(i)
        if li <= lk + 1e-9:
            total += math.exp(li)
    return min(1.0, total)


def pick_outcome(side, g, kind):
    """Return +1 win, -1 loss, 0 push, None no bet for a side choice on game g."""
    if side is None:
        return None
    if kind == "spread":
        if g["result"] is None or g["spread"] is None:
            return None
        diff = g["result"] - g["spread"]  # >0 home covers
        if diff == 0:
            return 0
        home_cover = diff > 0
        win = home_cover if side == "home" else (not home_cover)
        return 1 if win else -1
    if kind == "total":
        if g["total"] is None or g["total_line"] is None:
            return None
        if g["total"] == g["total_line"]:
            return 0
        over = g["total"] > g["total_line"]
        win = over if side == "over" else (not over)
        return 1 if win else -1
    raise ValueError(kind)


def qb_out_index():
    path = os.path.join(OUT, "injuries-qb-2016-2026.json")
    with open(path) as f:
        rows = json.load(f)["rows"]
    idx = {}
    for r in rows:
        if r["report_status"] in ("Out", "Doubtful"):
            idx[(int(r["season"]), int(r["week"]), r["gsis_id"])] = r
    return idx


def build_strategies(games, qb_idx):
    """Each strategy maps a game to a side ('home','away','over','under') or None."""
    S = {}

    S["MKT-HOME"] = ("spread", lambda g: "home")
    S["MKT-FAV"] = ("spread", lambda g: None if g["spread"] in (None, 0) else ("home" if g["spread"] > 0 else "away"))
    S["MKT-DOG"] = ("spread", lambda g: None if g["spread"] in (None, 0) else ("away" if g["spread"] > 0 else "home"))
    for T in MODEL_EDGES:
        def mk(T=T):
            def fn(g):
                if g["spread"] is None:
                    return None
                edge = g["model_margin"] - g["spread"]
                if edge >= T:
                    return "home"
                if edge <= -T:
                    return "away"
                return None
            return fn
        S[f"MODEL-EDGE-{int(T)}"] = ("spread", mk())

    def rest(g):
        if g["home_rest"] is None or g["away_rest"] is None:
            return None
        d = g["home_rest"] - g["away_rest"]
        if d >= 3:
            return "home"
        if d <= -3:
            return "away"
        return None
    S["REST-GAP-3"] = ("spread", rest)

    def qb_fade(g):
        if g["season"] < 2016:
            return None
        hq = qb_idx.get((g["season"], g["week"], g["home_qb_id"]))
        aq = qb_idx.get((g["season"], g["week"], g["away_qb_id"]))
        if hq and not aq:
            return "away"  # fade the home team whose starting QB is out
        if aq and not hq:
            return "home"
        return None

    def qb_back(g):
        f = qb_fade(g)
        return {"home": "away", "away": "home"}.get(f)
    S["QB-OUT-FADE"] = ("spread", qb_fade)
    S["QB-OUT-BACK"] = ("spread", qb_back)

    for T in (TOT_EDGE,):
        def tot(g, T=T):
            if g["total_line"] is None:
                return None
            edge = g["model_total"] - g["total_line"]
            if edge >= T:
                return "over"
            if edge <= -T:
                return "under"
            return None
        S[f"TOTAL-EDGE-{int(T)}"] = ("total", tot)
    return S


def summarize(rows_bets, seasons):
    """rows_bets: list of dicts with season, outcome (+1/-1/0), game_id."""
    settled = [b for b in rows_bets if b["outcome"] in (1, -1)]
    wins = sum(1 for b in settled if b["outcome"] == 1)
    losses = len(settled) - wins
    n = len(settled)
    hit = wins / n if n else None
    roi = (wins * PAYOUT - losses) / n if n else None
    p = binom_two_sided(wins, n) if n else None
    # season-block bootstrap of hit rate
    by_s = defaultdict(list)
    for b in settled:
        by_s[b["season"]].append(1 if b["outcome"] == 1 else 0)
    sl = list(by_s.values())
    ci = None
    if sl:
        boots = []
        for _ in range(N_BOOT):
            samp = [RNG.choice(sl) for _ in sl]
            tot = sum(len(s) for s in samp)
            if tot:
                boots.append(sum(sum(s) for s in samp) / tot)
        boots.sort()
        ci = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1])
    per_season = {}
    for s in seasons:
        ss = [b for b in settled if b["season"] == s]
        if ss:
            w = sum(1 for b in ss if b["outcome"] == 1)
            per_season[s] = {"n": len(ss), "wins": w, "hit": round(w / len(ss), 4)}
    pos = sum(1 for v in per_season.values() if v["hit"] > BREAKEVEN)
    return {
        "n": n, "wins": wins, "losses": losses,
        "pushes": sum(1 for b in rows_bets if b["outcome"] == 0),
        "hit": round(hit, 4) if hit is not None else None,
        "roi_at_110": round(roi, 4) if roi is not None else None,
        "hit_ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
        "p_two_sided": round(p, 4) if p is not None else None,
        "seasons_with_bets": len(per_season),
        "seasons_above_breakeven": pos,
        "per_season": per_season,
    }


def main():
    games = load_games()
    # --- tune K on training window only ----------------------------------
    tune = []
    for K in K_GRID:
        train_rows = [g for g in run_model([dict(g) for g in games], K)
                      if TRAIN[0] <= g["season"] <= TRAIN[1] and g["game_type"] == "REG"]
        tune.append({"K": K, "train_mae": round(mae(train_rows, "model_margin"), 4)})
    best = min(tune, key=lambda t: t["train_mae"])
    K = best["K"]
    games = run_model(games, K)

    reg = [g for g in games if g["game_type"] == "REG" and g["result"] is not None]
    test = [g for g in reg if TEST[0] <= g["season"] <= TEST[1]]
    fwd = [g for g in reg if g["season"] == FORWARD]
    spread_rows = [g for g in test if g["spread"] is not None]

    model_quality = {
        "train_window": f"{TRAIN[0]}-{TRAIN[1]}",
        "test_window": f"{TEST[0]}-{TEST[1]}",
        "K_selected": K,
        "K_grid": tune,
        "REGRESS": REGRESS, "HFA_points": HFA, "ALPHA_totals": ALPHA,
        "test_mae_model_margin": round(mae(test, "model_margin"), 3),
        "test_mae_market_spread": None,
        "test_games": len(test),
        "test_games_with_market_spread": len(spread_rows),
        "test_mae_model_total": round(mae(test, "model_total", target="total"), 3),
        "forward_2026_mae_model_margin": round(mae(fwd, "model_margin"), 3) if fwd else None,
        "forward_2026_games": len(fwd),
    }
    # market MAE: spread predicts margin as result vs spread (home-positive convention)
    if spread_rows:
        model_quality["test_mae_market_spread"] = round(
            sum(abs(g["result"] - g["spread"]) for g in spread_rows) / len(spread_rows), 3)

    # --- single-bet strategies --------------------------------------------
    qb_idx = qb_out_index()
    S = build_strategies(games, qb_idx)
    strat_results = {}
    bets_by_strategy = {}
    for name, (kind, fn) in S.items():
        bets = []
        for g in test + fwd:
            if g["game_type"] != "REG" or g["result"] is None:
                continue
            side = fn(g)
            if side is None:
                continue
            out = pick_outcome(side, g, kind)
            if out is None:
                continue
            bets.append({"game_id": g["game_id"], "season": g["season"], "week": g["week"],
                         "side": side, "outcome": out, "home": g["home"], "away": g["away"],
                         "gameday": g["gameday"]})
        bets_by_strategy[name] = bets
        test_bets = [b for b in bets if TEST[0] <= b["season"] <= TEST[1]]
        fwd_bets = [b for b in bets if b["season"] == FORWARD]
        strat_results[name] = {
            "kind": kind,
            "test": summarize(test_bets, range(TEST[0], TEST[1] + 1)),
            "forward_2026": summarize(fwd_bets, [FORWARD]),
        }

    k_tests = len(S)
    p_thresh = 0.05 / k_tests
    leaderboard = []
    for name, res in strat_results.items():
        t = res["test"]
        gates = {
            "G0_provenance_official_or_verified_lines": {"pass": False, "note": "Market lines (spread_line / total_line) are third-party and unverified. nfldata does not name their source."},
            "G1_sample_>=300_test_bets": {"pass": t["n"] >= 300, "value": t["n"]},
            "G2_hit_>=52.38pct_and_CI_low_>50": {"pass": bool(t["hit"] and t["hit"] >= BREAKEVEN and t["hit_ci95"] and t["hit_ci95"][0] > 0.5), "value": t["hit"], "ci95": t["hit_ci95"]},
            "G3_p_below_bonferroni": {"pass": bool(t["p_two_sided"] is not None and t["p_two_sided"] < p_thresh), "value": t["p_two_sided"], "threshold": round(p_thresh, 5), "k_tests": k_tests},
            "G4_70pct_of_seasons_above_breakeven": {"pass": bool(t["seasons_with_bets"] and t["seasons_above_breakeven"] / t["seasons_with_bets"] >= 0.7), "value": f"{t['seasons_above_breakeven']}/{t['seasons_with_bets']}"},
            "G5_no_lookahead": {"pass": True, "note": "Ratings and totals used for a game are stored before that game updates them; qb-injury lookup uses same-week report, which is public before kickoff."},
        }
        passes_all = all(v["pass"] for v in gates.values())
        passes_excl_g0 = all(v["pass"] for k, v in gates.items() if not k.startswith("G0"))
        leaderboard.append({
            "strategy": name, "kind": res["kind"],
            "test_n": t["n"], "test_hit": t["hit"], "test_roi_at_110": t["roi_at_110"],
            "test_hit_ci95": t["hit_ci95"], "test_p": t["p_two_sided"],
            "forward_2026_n": res["forward_2026"]["n"], "forward_2026_hit": res["forward_2026"]["hit"],
            "gates": gates, "validated": passes_all, "passes_all_except_G0": passes_excl_g0,
            "score_ci_low": t["hit_ci95"][0] if t["hit_ci95"] else None,
        })
    leaderboard.sort(key=lambda r: (-(r["score_ci_low"] or 0), r["strategy"]))
    for i, r in enumerate(leaderboard, 1):
        r["rank"] = i
        r["reward_points"] = 0  # no strategy has passed every gate; rewards are not awarded

    # --- correlations between strategies (outcomes on shared games) --------
    names = [n for n in strat_results if strat_results[n]["test"]["n"] > 0]
    by_game = {n: {b["game_id"]: b["outcome"] for b in bets_by_strategy[n] if TEST[0] <= b["season"] <= TEST[1] and b["outcome"] in (1, -1)} for n in names}
    corr = {}
    for a in names:
        corr[a] = {}
        for b in names:
            common = [gid for gid in by_game[a] if gid in by_game[b]]
            if len(common) < 20:
                corr[a][b] = {"r": None, "overlap": len(common)}
                continue
            xs = [by_game[a][gid] for gid in common]
            ys = [by_game[b][gid] for gid in common]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            vx = sum((x - mx) ** 2 for x in xs)
            vy = sum((y - my) ** 2 for y in ys)
            r = cov / math.sqrt(vx * vy) if vx and vy else None
            corr[a][b] = {"r": round(r, 3) if r is not None else None, "overlap": len(common)}

    # --- parlays: two legs on different games in the same week ----------------
    # Gates for parlays: P1 >= 300 pairs; P2 joint win rate above the two-leg break-even
    # with CI low > break-even; P3 p-value below the Bonferroni threshold for parlays tested;
    # P4 >= 70% of seasons above break-even; P5 legs not nested (overlap of games <= 50% of the smaller leg).
    PAR_BE = BREAKEVEN ** 2
    parlay_list = []
    single_names = [n for n in names if n not in ("MKT-HOME", "MKT-FAV", "MKT-DOG")]
    for i, a in enumerate(single_names):
        for b in single_names[i + 1:]:
            pa = [x for x in bets_by_strategy[a] if TEST[0] <= x["season"] <= TEST[1] and x["outcome"] in (1, -1)]
            pb = [x for x in bets_by_strategy[b] if TEST[0] <= x["season"] <= TEST[1] and x["outcome"] in (1, -1)]
            idx_b = defaultdict(list)
            for x in pb:
                idx_b[(x["season"], x["week"])].append(x)
            pairs = []
            for x in pa:
                for y in idx_b.get((x["season"], x["week"]), []):
                    if y["game_id"] != x["game_id"]:
                        pairs.append((x, y))
            if len(pairs) < 50:
                continue
            wins = [1 if (x["outcome"] == 1 and y["outcome"] == 1) else 0 for x, y in pairs]
            n = len(pairs)
            joint = sum(wins) / n
            ind = (sum(1 for x in pa if x["outcome"] == 1) / len(pa)) * (sum(1 for x in pb if x["outcome"] == 1) / len(pb))
            gids_a = {x["game_id"] for x in pa}
            gids_b = {x["game_id"] for x in pb}
            overlap = len(gids_a & gids_b) / min(len(gids_a), len(gids_b))
            # season-level results for the consistency gate (win = both legs won)
            by_season = defaultdict(list)
            for (x, y), w in zip(pairs, wins):
                by_season[x["season"]].append(w)
            seasons_pos = sum(1 for v in by_season.values() if sum(v) / len(v) > PAR_BE)
            p_val = binom_two_sided(sum(wins), n, p=PAR_BE)
            parlay_list.append({
                "legs": [a, b], "pairs": n,
                "joint_win_rate": round(joint, 4),
                "independent_assumption": round(ind, 4),
                "correlation_gap": round(joint - ind, 4),
                "parlay_breakeven_two_legs": round(PAR_BE, 4),
                "parlay_roi_at_110_empirical": round(joint * (1 + PAYOUT) ** 2 - 1, 4),
                "p_vs_breakeven": round(p_val, 4),
                "seasons_above_breakeven": f"{seasons_pos}/{len(by_season)}",
                "leg_game_overlap": round(overlap, 3),
                "_seasons_pos": seasons_pos, "_seasons": len(by_season),
            })
    k_par = len(parlay_list)
    for pl in parlay_list:
        gates = {
            "P1_>=300_pairs": pl["pairs"] >= 300,
            "P2_joint_above_breakeven": pl["joint_win_rate"] > pl["parlay_breakeven_two_legs"],
            "P3_p_below_bonferroni": pl["p_vs_breakeven"] < 0.05 / max(k_par, 1),
            "P4_70pct_seasons_above": pl["_seasons"] > 0 and pl["_seasons_pos"] / pl["_seasons"] >= 0.7,
            "P5_legs_not_nested": pl["leg_game_overlap"] <= 0.5,
        }
        pl["gates"] = gates
        pl["validated"] = all(gates.values())
        del pl["_seasons_pos"], pl["_seasons"]
    parlay_list.sort(key=lambda p: -p["parlay_roi_at_110_empirical"])
    parlays = parlay_list

    # --- lines for 2026 (own model vs market, market blanked on site) ----------
    lines = []
    for g in games:
        if g["season"] != FORWARD:
            continue
        played = g["result"] is not None
        lines.append({
            "game_id": g["game_id"], "week": g["week"], "gameday": g["gameday"], "gametime": g["gametime"],
            "away": g["away"], "home": g["home"], "stadium": g["stadium"],
            "status": "final" if played else "scheduled",
            "away_score": g["away_score"] if played else None,
            "home_score": g["home_score"] if played else None,
            "model_home_margin": round(g["model_margin"], 2),
            "model_total": round(g["model_total"], 2),
            "market_spread_home_unverified": g["spread"] if not played else g["spread"],
            "market_total_unverified": g["total_line"],
            "pfr_game_id": g["pfr"],
        })
    upcoming = [l for l in lines if l["status"] == "scheduled"]

    with open(os.path.join(OUT, "model-params.json"), "w") as f:
        json.dump(model_quality, f, indent=1)
    with open(os.path.join(OUT, "strategies.json"), "w") as f:
        json.dump({
            "description": "Single-bet, correlation and parlay results. Walk-forward. Gates applied in order. Market lines unverified (G0 fails for all).",
            "break_even_at_110": round(BREAKEVEN, 4),
            "k_tests_bonferroni": k_tests,
            "leaderboard": leaderboard,
            "per_strategy": strat_results,
            "correlation_matrix": corr,
            "parlays": parlays[:40],
            "parlays_tested": len(parlays),
            "parlays_validated": sum(1 for p in parlays if p["validated"]),
            "parlay_gates": ["P1 >= 300 pairs", "P2 joint win rate above two-leg break-even (27.4%)", "P3 p-value below 0.05 / parlays tested", "P4 >= 70% of seasons above break-even", "P5 legs not nested (game overlap <= 50%)"],
            "blocked": [
                {"strategy": "PLAYER-PROP-COMBOS", "reason": "No official NFL source publishes historical player prop prices. Not testable with verified data."},
                {"strategy": "STARTER-VS-BACKUP-DEPTH", "reason": "Historical depth-chart snapshots are not week-keyed in the available mirror; only the current snapshot is tracked (see injuries page)."},
            ],
        }, f, indent=1)
    with open(os.path.join(OUT, "lines-2026.json"), "w") as f:
        json.dump({"description": "2026 regular-season games. Model margin and total are our own walk-forward estimates. Market lines are third-party and unverified: the site leaves them blank.",
                   "model_K": K, "rows": lines, "upcoming_count": len(upcoming)}, f, indent=1)
    print("K", K, "test mae", model_quality["test_mae_model_margin"], "market mae", model_quality["test_mae_market_spread"])
    for r in leaderboard:
        print(r["rank"], r["strategy"], r["test_n"], r["test_hit"], r["test_p"], r["validated"], r["passes_all_except_G0"])
    print("parlays tested", len(parlays), "top", parlays[:3])


if __name__ == "__main__":
    main()
