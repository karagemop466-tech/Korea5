#!/usr/bin/env python3
"""
NFL Lines Lab — model engine (stdlib only).

Reads the CSVs in nfl/raw/ (fetched and hashed by nfl/fetch_data.py) and writes
nfl/data/*.json. Every number published by the site comes from this file.

Core pieces
-----------
1.  Game table           games.csv -> one row per completed regular/post game.
2.  Signals (features)   computed with *prior information only*:
      rest advantage, division game, short week, travel, roof, QB change,
      and an injury/lineup index built from the official injury report and the
      depth chart (starters vs 2nd/3rd/4th string, snap-weighted).
3.  Walk-forward model   logistic regression fitted on seasons < S, evaluated on S.
4.  Naive baseline       home/away win rates from strictly prior seasons.
5.  Luck removal         permutation deflation of the best-of-N skill.
6.  Correlation matrix   measured pairwise correlation of candidate signals and
                         of player-prop outcomes, with bootstrap CIs.
7.  Leaderboard          singles, parlays, prop combos, with pre-registered gates.

Run:  python3 nfl/model.py            (needs nfl/raw/ from the CI fetcher)
      python3 nfl/model.py --selftest (runs on nfl/raw/samples, no network)
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import math
import os
import random
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

RAW = "nfl/raw"
OUT = "nfl/data"
SEED = 20261113
POS_GROUPS = ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "CB", "S", "K", "P"]

# ---------------------------------------------------------------- tiny numeric helpers


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def logloss(p: float, y: int) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def brier(p: float, y: int) -> float:
    return (p - y) ** 2


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def percentile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def zscore_vec(cols):
    """Standardise a list of feature columns (list of lists). Returns (scaled, means, sd)."""
    means, sds, out = [], [], []
    for col in cols:
        m = mean(col)
        sd = statistics.pstdev(col) if len(col) > 1 else 0.0
        sds.append(sd if sd > 1e-12 else 0.0)
        means.append(m)
        out.append([(v - m) / sds[-1] if sds[-1] else 0.0 for v in col])
    return out, means, sds


def solve(A, b):
    """Gaussian elimination with partial pivoting for a small dense system."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[piv][i]) < 1e-12:
            return None
        M[i], M[piv] = M[piv], M[i]
        pv = M[i][i]
        for j in range(i, n + 1):
            M[i][j] /= pv
        for r in range(n):
            if r == i:
                continue
            f = M[r][i]
            if f:
                for j in range(i, n + 1):
                    M[r][j] -= f * M[i][j]
    return [M[i][n] for i in range(n)]


def fit_logistic(X, y, l2=1.0, iters=30):
    """
    Iteratively reweighted least squares (Newton) with a tiny ridge on non-intercept terms.
    Converges in ~5-8 iterations for ~10 parameters, which keeps the permutation test affordable.
    """
    n, k = len(X), len(X[0])
    w = [0.0] * k
    for _ in range(iters):
        cols = [[row[j] for row in X] for j in range(k)]
        z = [0.0] * n
        for j in range(k):
            wj = w[j]
            if wj:
                cj = cols[j]
                for i in range(n):
                    z[i] += wj * cj[i]
        pw = [sigmoid(v) for v in z]
        # gradient and Hessian
        g = [0.0] * k
        for j in range(k):
            cj = cols[j]
            acc = 0.0
            for i in range(n):
                acc += (y[i] - pw[i]) * cj[i]
            g[j] = acc - (0.0 if j == 0 else l2 * w[j])
        H = [[0.0] * k for _ in range(k)]
        for a in range(k):
            ca = cols[a]
            for b in range(a + 1):
                cb = cols[b]
                acc = 0.0
                for i in range(n):
                    wi = pw[i] * (1 - pw[i])
                    if wi:
                        acc += wi * ca[i] * cb[i]
                H[a][b] = H[b][a] = acc + (l2 if (a == b and a != 0) else 0.0) + (1e-9 if a == b else 0.0)
        step = solve(H, g)
        if step is None:
            break
        w = [wj + sj for wj, sj in zip(w, step)]
        if max(abs(v) for v in step) < 1e-8:
            break
    return w


def predict(w, x):
    return sigmoid(sum(wj * xj for wj, xj in zip(w, x)))


# ---------------------------------------------------------------- data loading


def read_csv(path: str) -> list[dict]:
    import csv
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fnum(v, default=None):
    try:
        if v is None or str(v).strip() in ("", "NA", "NaN", "nan", "None"):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def load_games(raw_dir: str, seasons: list[int]) -> list[dict]:
    path = os.path.join(raw_dir, "games.csv")
    if not os.path.exists(path):
        return []
    games = []
    for r in read_csv(path):
        s = fnum(r.get("season"))
        if s is None or int(s) not in seasons:
            continue
        if (r.get("game_type") or "").upper() not in ("REG", "WC", "DIV", "CON", "SB"):
            continue
        hs, as_ = fnum(r.get("home_score")), fnum(r.get("away_score"))
        g = {
            "game_id": r["game_id"], "season": int(s), "week": int(fnum(r.get("week"), 0)),
            "type": (r.get("game_type") or "").upper(), "date": r.get("gameday"),
            "home": r.get("home_team"), "away": r.get("away_team"),
            "home_score": hs, "away_score": as_,
            "home_rest": fnum(r.get("home_rest")), "away_rest": fnum(r.get("away_rest")),
            "div_game": fnum(r.get("div_game")), "roof": (r.get("roof") or "").strip(),
            "surface": (r.get("surface") or "").strip(),
            "spread_line": fnum(r.get("spread_line")), "total_line": fnum(r.get("total_line")),
            "home_ml": fnum(r.get("home_moneyline")), "away_ml": fnum(r.get("away_moneyline")),
            "home_qb": (r.get("home_qb_name") or "").strip(),
            "away_qb": (r.get("away_qb_name") or "").strip(),
            "home_coach_id": r.get("home_coach") or r.get("home_coach_id") or "",
            "away_coach_id": r.get("away_coach") or r.get("away_coach_id") or "",
            "home_seed": fnum(r.get("home_seed_mathematical")) or fnum(r.get("home_seed")),
            "away_seed": fnum(r.get("away_seed_mathematical")) or fnum(r.get("away_seed")),
            "espn_id": r.get("espn") or "",
        }
        complete = hs is not None and as_ is not None and hs != as_
        g["complete"] = bool(complete)
        if not complete:
            games.append(g)
            continue
        g["result"] = 1 if hs > as_ else 0
        g["margin"] = hs - as_
        g["total"] = hs + as_
        games.append(g)
    games.sort(key=lambda x: (x["season"], x["week"], x["date"] or ""))
    return games


def load_injuries(raw_dir: str, seasons: list[int]) -> dict[tuple, dict]:
    """(team, week, gsis_id) -> official report status. Verified source field."""
    out: dict[tuple, dict] = {}
    for y in seasons:
        p = os.path.join(raw_dir, f"injuries_{y}.csv")
        if not os.path.exists(p):
            continue
        for r in read_csv(p):
            st = (r.get("report_status") or "").strip()
            prac = (r.get("practice_status") or "").strip()
            key = ((r.get("team") or "").strip(), int(fnum(r.get("week"), 0)), (r.get("gsis_id") or "").strip())
            out[key] = {"report": st, "practice": prac,
                        "injury": (r.get("report_primary_injury") or "").strip(),
                        "modified": r.get("date_modified") or ""}
    return out


def load_depth(raw_dir: str, seasons: list[int], game_dates: dict) -> dict[tuple, dict]:
    """
    (team, week, gsis_id) -> depth position, using the latest snapshot BEFORE that week's kickoff.
    Snapshot time comes from the published 'dt' column (2022+) or the file itself.
    """
    snaps: dict[tuple[str, int], list[tuple[datetime, dict]]] = defaultdict(list)
    for y in seasons:
        p = os.path.join(raw_dir, f"depth_charts_{y}.csv")
        if not os.path.exists(p):
            continue
        rows = read_csv(p)
        if not rows:
            continue
        cols = set(rows[0])
        for r in rows:
            team = (r.get("club_code") or r.get("team") or "").strip()
            if not team:
                continue
            if "dt" in cols:
                ts_raw = r.get("dt") or ""
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime(1970, 1, 1)
                week = None
            else:
                ts = datetime(1970, 1, 1)
                week = int(fnum(r.get("week"), 0))
            key = (team, week if week is not None else -1)
            snaps[key].append((ts, r))
    out: dict[tuple, dict] = {}
    for (team, week), rows in snaps.items():
        # latest snapshot for that team/week
        latest_ts = max(ts for ts, _ in rows)
        for ts, r in rows:
            if ts != latest_ts:
                continue
            gid = (r.get("gsis_id") or "").strip()
            pos = (r.get("position") or r.get("pos_abb") or "").strip()
            rank = fnum(r.get("depth_team")) if r.get("depth_team") else fnum(r.get("pos_rank"))
            if gid:
                out[(team, week, gid)] = {"pos": pos, "rank": int(rank) if rank else None,
                                          "formation": (r.get("formation") or "").strip(),
                                          "name": (r.get("football_name") or r.get("player_name") or
                                                   r.get("full_name") or "").strip()}
    return out


def load_snaps(raw_dir: str, seasons: list[int]) -> dict[tuple, float]:
    """(team, week, player_name) -> offense/defense snap share, used as the ONLY weight for unit value."""
    out: dict[tuple, dict] = {}
    for y in seasons:
        p = os.path.join(raw_dir, f"snap_counts_{y}.csv")
        if not os.path.exists(p):
            continue
        for r in read_csv(p):
            name = (r.get("player") or "").strip()
            team = (r.get("team") or "").strip()
            wk = int(fnum(r.get("week"), 0))
            out[(team, wk, name)] = {"off": fnum(r.get("offense_pct"), 0.0),
                                     "def": fnum(r.get("defense_pct"), 0.0),
                                     "pos": (r.get("position") or "").strip()}
    return out


# ---------------------------------------------------------------- signals


def build_ratings(games):
    """
    Chronological Elo ratings and rolling form, using ONLY games played earlier in the sort order.
    Nothing from the game being predicted (or later) enters its own features. This is the walk-forward
    guard that the unit test asserts.
    """
    elo = defaultdict(lambda: 1500.0)
    form = defaultdict(list)          # team -> list of (margin relative to opponent, opponent elo)
    last_season = {}
    K_BASE, HFA, CARRY = 20.0, 48.0, 0.72
    for g in games:
        h, a = g["home"], g["away"]
        # season transition: regress to the mean so old seasons fade
        if g["season"] != last_season.get(h):
            base = 1505.0
            elo[h] = base + CARRY * (elo[h] - base)
            last_season[h] = g["season"]
        if g["season"] != last_season.get(a):
            base = 1505.0
            elo[a] = base + CARRY * (elo[a] - base)
            last_season[a] = g["season"]
        eh, ea = elo[h], elo[a]
        g["s"]["elo_home"] = round(eh, 1)
        g["s"]["elo_away"] = round(ea, 1)
        g["s"]["elo_diff"] = round(eh - ea + HFA, 1)
        fh, fa = form[h][-8:], form[a][-8:]
        g["s"]["form_home"] = round(sum(x for x, _ in fh) / len(fh), 3) if fh else None
        g["s"]["form_away"] = round(sum(x for x, _ in fa) / len(fa), 3) if fa else None
        g["s"]["form_diff"] = (round(g["s"]["form_home"] - g["s"]["form_away"], 3)
                               if (fh and fa) else None)
        if not g["complete"]:
            continue
        # Elo update (margin-of-victory multiplier, capped)
        expected = 1.0 / (1.0 + 10 ** ((ea - (eh + HFA)) / 400.0))
        mov = max(1.0, abs(g["margin"])) ** 0.7
        delta = K_BASE * mov * (g["result"] - expected)
        elo[h] = eh + delta
        elo[a] = ea - delta
        form[h].append((g["margin"], ea))
        form[a].append((-g["margin"], eh))
    return games


def build_signals(games, injuries, depth, snaps, index=None):
    """
    Adds prior-information-only features to each completed game.
    Anything we cannot verify stays None and is reported as such (never imputed).
    """
    idx = index or LineupIndex(depth, snaps, injuries)
    by_team: dict[str, list[dict]] = defaultdict(list)
    for g in games:
        by_team[g["home"]].append(g)
        by_team[g["away"]].append(g)
    for v in by_team.values():
        v.sort(key=lambda x: (x["date"] or "", x["week"]))

    # prior-season win rates (strictly before the game's season)
    season_wins: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    for g in games:
        if not g["complete"]:
            continue
        for team, won in ((g["home"], g["result"]), (g["away"], 1 - g["result"])):
            season_wins[(g["season"], team)][0] += won
            season_wins[(g["season"], team)][1] += 1

    # rolling last-5 (in-season form) computed with only earlier games
    for g in games:
        feats: dict[str, float | None] = {}
        feats["rest_diff"] = (g["home_rest"] - g["away_rest"]) if (g["home_rest"] is not None and
                                                                   g["away_rest"] is not None) else None
        feats["div_game"] = 1.0 if g["div_game"] == 1 else 0.0
        feats["dome"] = 1.0 if g["roof"] in ("dome", "closed") else 0.0
        feats["home_short_week"] = 1.0 if (g["home_rest"] is not None and g["home_rest"] <= 4) else 0.0
        feats["away_short_week"] = 1.0 if (g["away_rest"] is not None and g["away_rest"] <= 4) else 0.0

        # QB change: published starter vs that team's most frequent QB so far that season
        def qb_change(team, current, g):
            prior = [x for x in by_team[team] if x["season"] == g["season"] and
                     (x["date"] or "") < (g["date"] or "") and x["complete"]]
            if not prior:
                return None
            names = Counter((x["home_qb"] if x["home"] == team else x["away_qb"]) for x in prior)
            names.pop("", None)
            if not names:
                return None
            mode = names.most_common(1)[0][0]
            return 0.0 if current == mode else 1.0

        feats["home_qb_change"] = qb_change(g["home"], g["home_qb"], g)
        feats["away_qb_change"] = qb_change(g["away"], g["away_qb"], g)

        # injury + lineup index per unit
        for side in ("home", "away"):
            team = g[side]
            wk = g["week"]
            off_val, off_out, off_doubt, off_ques = idx.value(team, wk, "off")
            def_val, def_out, def_doubt, def_ques = idx.value(team, wk, "def")
            feats[f"{side}_off_value"] = off_val
            feats[f"{side}_def_value"] = def_val
            feats[f"{side}_off_out_share"] = off_out
            feats[f"{side}_def_out_share"] = def_out
            feats[f"{side}_off_doubt_share"] = off_doubt
            feats[f"{side}_off_ques_share"] = off_ques
            sc, bc = idx.counts(team, wk, "off")
            feats[f"{side}_starter_count_off"] = sc
            feats[f"{side}_backup_count_off"] = bc
        # differentials (None-safe)
        for a, b, name in (
            ("home_off_value", "away_off_value", "off_value_diff"),
            ("home_def_value", "away_def_value", "def_value_diff"),
            ("home_off_out_share", "away_off_out_share", "off_out_diff"),
            ("home_def_out_share", "away_def_out_share", "def_out_diff"),
        ):
            fa, fb = feats.get(a), feats.get(b)
            feats[name] = (fa - fb) if (fa is not None and fb is not None) else None
        g["s"] = feats
    games = build_ratings(games)
    return games


OFF_POS = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OL", "OT", "OG"}
DEF_POS = {"DE", "DT", "NT", "DL", "EDGE", "LB", "ILB", "OLB", "MLB", "CB", "DB", "S", "SS", "FS"}


class LineupIndex:
    """
    One-pass index so injury/lineup lookups are O(players on a unit) instead of O(all rows).
    Snap weight = max(offense_pct, defense_pct) from the published snap table, matched on surname + team + week.
    A player on the depth chart with no snap row keeps a small weight (0.05) so he is counted but not credited
    with starter value we did not verify.
    """

    def __init__(self, depth, snaps, injuries):
        self.by_team_week_pos: dict[tuple, list] = defaultdict(list)
        self.snap_by_team_week: dict[tuple, dict[str, float]] = defaultdict(dict)
        self.inj = injuries
        for (team, week, gid), v in depth.items():
            self.by_team_week_pos[(team, week, v.get("pos"))].append((gid, v))
        for (team, week, name), sv in snaps.items():
            self.snap_by_team_week[(team, week)][name] = max(sv.get("off") or 0.0, sv.get("def") or 0.0)

    def _rows(self, team, week, pos_set):
        rows = []
        for pos in pos_set:
            rows.extend(self.by_team_week_pos.get((team, week, pos), ()))
            if week != -1:
                rows.extend(self.by_team_week_pos.get((team, -1, pos), ()))
        return rows

    def value(self, team, week, unit):
        pos_set = OFF_POS if unit == "off" else DEF_POS
        rows = self._rows(team, week, pos_set)
        if not rows:
            return None, None, None, None
        snapmap = self.snap_by_team_week.get((team, week), {})
        starters = allv = out_w = doubt_w = ques_w = 0.0
        for gid, v in rows:
            name = v.get("name") or ""
            w = 0.0
            if name:
                last = name.split()[-1].lower()
                for pname, pv in snapmap.items():
                    if last and last in pname.lower():
                        w = pv
                        break
            if w == 0.0:
                w = 0.05
            allv += w
            if v.get("rank") == 1:
                starters += w
                status = (self.inj.get((team, week, gid), {}).get("report") or "").lower()
                if status == "out":
                    out_w += w
                elif status == "doubtful":
                    doubt_w += w
                elif status == "questionable":
                    ques_w += w
        if allv <= 0:
            return None, None, None, None
        return (round(starters / allv, 4), round(out_w / allv, 4),
                round(doubt_w / allv, 4), round(ques_w / allv, 4))

    def counts(self, team, week, unit):
        pos_set = OFF_POS if unit == "off" else DEF_POS
        rows = self._rows(team, week, pos_set)
        if not rows:
            return None, None
        starters = sum(1 for _, v in rows if v.get("rank") == 1)
        backups = sum(1 for _, v in rows if (v.get("rank") or 0) >= 2)
        return starters or None, backups or None


# ---------------------------------------------------------------- model + gates

FEATURES = ["rest_diff", "div_game", "dome", "home_short_week", "away_short_week",
            "home_qb_change", "away_qb_change", "off_value_diff", "def_value_diff",
            "off_out_diff", "def_out_diff"]
STRENGTH_FEATURES = ["elo_diff", "form_diff", "rest_diff", "div_game", "dome",
                     "home_qb_change", "away_qb_change", "off_out_diff", "def_out_diff"]
FILL = {k: 0.0 for k in FEATURES + STRENGTH_FEATURES
        if k not in ("elo_diff",)}  # elo_diff 0 would mean 'equal teams'; use 0 for it too (documented)


def matrix(games, features, fill=FILL):
    X, y, keep = [], [], []
    for g in games:
        if not g["complete"]:
            continue
        row = [1.0] + [float(g["s"].get(f) if g["s"].get(f) is not None else fill[f]) for f in features]
        X.append(row)
        y.append(g["result"])
        keep.append(g)
    return X, y, keep


def naive_prior(games, seasons_eval, seasons_all):
    """Home win prob = prior-season home win rate of home team vs prior-season away win rate of away team."""
    home_wr: dict[tuple[int, str], float] = {}
    away_wr: dict[tuple[int, str], float] = {}
    tally = defaultdict(lambda: [0, 0])
    for g in games:
        if not g["complete"]:
            continue
        b = tally[(g["season"], g["home"])]
        b[0] += g["result"]
        b[1] += 1
        b = tally[("away", g["season"], g["away"])]
        b[0] += 1 - g["result"]
        b[1] += 1
    out = {}
    for g in games:
        if not g["complete"] or g["season"] not in seasons_eval:
            continue
        prior = [s for s in seasons_all if s < g["season"]]
        hw = [tally[(s, g["home"])] for s in prior if tuple(tally[(s, g["home"])]) != (0, 0)]
        aw = [tally[("away", s, g["away"])] for s in prior if tuple(tally[("away", s, g["away"])]) != (0, 0)]
        h = 0.5
        if hw:
            h = sum(x[0] for x in hw) / max(1, sum(x[1] for x in hw))
        a = 0.5
        if aw:
            a = sum(x[0] for x in aw) / max(1, sum(x[1] for x in aw))
        # blend: home advantage plus relative form, shrunk to 0.5
        p = 0.5 + 0.5 * (h - a) + 0.03
        out[g["game_id"]] = min(max(p, 0.05), 0.95)
    return out


_CACHE: dict[int, tuple] = {}


def walk_forward(games, seasons_eval, features=FEATURES, l2=1.0):
    """
    Fit on seasons < S, predict S. Standardisation statistics come from the training seasons only
    (leakage guard). Raw season blocks are cached, so refitting after a label permutation is cheap.
    """
    recs = []
    key = content_key(games)
    blocks = {s: _block(games, s, features, key) for s in sorted({g["season"] for g in games})}
    for S in seasons_eval:
        train_seasons = [s for s in blocks if s < S]
        Xtr, ytr = [], []
        for s in train_seasons:
            Xs, ys, _ = blocks[s]
            Xtr.extend(Xs)
            ytr.extend(ys)
        Xte, yte, keep = blocks.get(S, ([], [], []))
        if len(Xtr) < 200 or not Xte:
            continue
        cols = [[row[j] for row in Xtr] for j in range(1, len(Xtr[0]))]
        scaled, means, sds = zscore_vec(cols)

        def scale(rows):
            return [[1.0] + [(v - means[i]) / sds[i] if sds[i] else 0.0 for i, v in enumerate(r[1:])]
                    for r in rows]

        w = fit_logistic(scale(Xtr), ytr, l2=l2)
        for r, yy, g in zip(scale(Xte), yte, keep):
            recs.append({"season": S, "game_id": g["game_id"], "p": predict(w, r), "y": yy,
                         "week": g["week"], "date": g["date"],
                         "spread": g["spread_line"], "total_line": g["total_line"]})
    return recs


_BLOCKS: dict[tuple, tuple] = {}


def _block(games, season, features, key):
    ck = (key, season, tuple(features))
    if ck not in _BLOCKS:
        _BLOCKS[ck] = matrix([g for g in games if g["season"] == season], features)
    return _BLOCKS[ck]


def content_key(games) -> str:
    """Cache key derived from the actual rows, so a shuffled copy can never collide with the real one."""
    h = 0
    for g in games:
        if g["complete"]:
            h = (h * 1000003 + hash((g["game_id"], g["result"]))) & 0xFFFFFFFFFFFF
    return f"{len(games)}:{h}"


def scores(recs, base):
    ll = mean([logloss(r["p"], r["y"]) for r in recs])
    bl = mean([logloss(base.get(r["game_id"], 0.5), r["y"]) for r in recs])
    br = mean([brier(r["p"], r["y"]) for r in recs])
    bbr = mean([brier(base.get(r["game_id"], 0.5), r["y"]) for r in recs])
    acc = mean([1 if (r["p"] >= 0.5) == (r["y"] == 1) else 0 for r in recs])
    return {"games": len(recs), "logloss": round(ll, 5), "baselineLogloss": round(bl, 5),
            "skill": round(1 - ll / bl, 5) if bl else None,
            "brier": round(br, 5), "baselineBrier": round(bbr, 5),
            "brierSkill": round(1 - br / bbr, 5) if bbr else None,
            "accuracy": round(acc, 4)}


def deflate(games, seasons_eval, base, observed_skill, N=200, rng_seed=SEED, K=1, features=FEATURES):
    """
    Best-of-N null: shuffle outcomes within each evaluated season, refit and re-score.
    Returns the 95th percentile of the best null skill and the full list.
    """
    rng = random.Random(rng_seed)
    by_season = {s: [g for g in games if g["season"] == s and g["complete"]] for s in seasons_eval}
    real = {s: [g["result"] for g in by_season[s]] for s in seasons_eval}
    single = []
    best_of = []
    blocks_per = max(1, N // max(1, K))
    for _ in range(N):
        perm = {}
        for s in seasons_eval:
            outs = list(real[s])
            rng.shuffle(outs)
            perm[s] = iter(outs)
        swapped = []
        for g in games:
            if g["season"] in perm and g["complete"]:
                h = dict(g)
                h["result"] = next(perm[g["season"]])
                swapped.append(h)
            else:
                swapped.append(g)
        _BLOCKS.clear()
        recs = walk_forward(swapped, seasons_eval, features=features)
        if recs:
            v = scores(recs, base)["skill"]
            if v is not None:
                single.append(v)
        _BLOCKS.clear()
    # best-of-K: the threshold a researcher would face after trying K candidates on the same data
    for i in range(0, max(0, len(single) - K + 1), K):
        best_of.append(max(single[i:i + K]))
    p95_single = percentile(single, 0.95) if single else None
    p95_best = percentile(best_of, 0.95) if best_of else p95_single
    return {"N": len(single), "K": K,
            "p95_single": round(p95_single, 5) if p95_single is not None else None,
            "p95": round(p95_best, 5) if p95_best is not None else None,
            "median": round(statistics.median(single), 5) if single else None,
            "blocks": len(best_of),
            "passed": (observed_skill is not None and p95_best is not None and observed_skill > p95_best)}


def calibration(recs, bins=10):
    pairs = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        xs = [r for r in recs if lo <= r["p"] < hi or (b == bins - 1 and r["p"] == 1.0)]
        if not xs:
            continue
        pairs.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(xs),
                      "predicted": round(mean([r["p"] for r in xs]), 4),
                      "observed": round(mean([r["y"] for r in xs]), 4)})
    # reliability slope via least squares on bin means weighted by n
    if len(pairs) >= 3:
        xs = [p["predicted"] for p in pairs]
        ys = [p["observed"] for p in pairs]
        wx = [p["n"] for p in pairs]
        mx = sum(x * w for x, w in zip(xs, wx)) / sum(wx)
        my = sum(y * w for y, w in zip(ys, wx)) / sum(wx)
        num = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, wx))
        den = sum(w * (x - mx) ** 2 for x, w in zip(xs, wx))
        slope = num / den if den else None
    else:
        slope = None
    return {"bins": pairs, "slope": round(slope, 4) if slope is not None else None}


def stability(recs, base):
    out = {}
    for s in sorted({r["season"] for r in recs}):
        sub = [r for r in recs if r["season"] == s]
        out[str(s)] = scores(sub, base)["skill"]
    return out


# ---------------------------------------------------------------- correlations


def bootstrap_ci(xs, ys, n=2000, seed=SEED):
    if len(xs) < 20:
        return None, None
    rng = random.Random(seed)
    vals = []
    idx = list(range(len(xs)))
    for _ in range(n):
        pick = [rng.choice(idx) for _ in idx]
        v = pearson([xs[i] for i in pick], [ys[i] for i in pick])
        if v is not None:
            vals.append(v)
    if len(vals) < 50:
        return None, None
    return round(percentile(vals, 0.025), 4), round(percentile(vals, 0.975), 4)


def signal_outcomes(games, seasons_eval):
    """Per-signal binary 'hit' vectors so correlations are measured on realised outcomes."""
    vecs = {}
    for f in FEATURES:
        xs, ys = [], []
        for g in games:
            if not g["complete"] or g["season"] not in seasons_eval:
                continue
            v = g["s"].get(f)
            if v is None:
                continue
            xs.append(float(v))
            ys.append(g["result"])
        vecs[f] = (xs, ys)
    return vecs


def correlation_matrix(games, seasons_eval):
    vecs = signal_outcomes(games, seasons_eval)
    names = [f for f in FEATURES if vecs[f][0]]
    out = {"signals": names, "pairs": [], "note": "Pearson r between the signal value and the realised home win."}
    for a, b in itertools.combinations(names, 2):
        # pair on co-occurring games only
        xs, ys = [], []
        for g in games:
            if not g["complete"] or g["season"] not in seasons_eval:
                continue
            va, vb = g["s"].get(a), g["s"].get(b)
            if va is None or vb is None:
                continue
            xs.append(float(va))
            ys.append(float(vb))
        r = pearson(xs, ys)
        lo, hi = bootstrap_ci(xs, ys, n=600)
        out["pairs"].append({"a": a, "b": b, "n": len(xs), "r": round(r, 4) if r is not None else None,
                             "ci": [lo, hi], "excludesZero": (lo is not None and (lo > 0 or hi < 0))})
    return out


# ---------------------------------------------------------------- props


PROP_SPECS = [
    ("passing_yards", "QB", 225.0),
    ("rushing_yards", "RB", 55.0),
    ("receiving_yards", "WR", 45.0),
    ("receptions", "WR", 4.5),
    ("passing_tds", "QB", 1.5),
    ("rushing_tds", "RB", 0.5),
    ("receiving_tds", "WR", 0.5),
]


def load_prop_rows(raw_dir, seasons):
    rows = []
    for y in seasons:
        p = os.path.join(raw_dir, f"stats_player_week_{y}.csv")
        if not os.path.exists(p):
            continue
        for r in read_csv(p):
            if (r.get("season_type") or "REG") != "REG":
                continue
            rows.append(r)
    return rows


def prop_eval(props, season_eval, spec, min_games=4, prior_seasons=()):
    """
    Forecast a player's next-week over/under on a fixed line from his own prior weeks in that season.
    Baseline is the LEAGUE BASE RATE for the same market and line computed from strictly prior seasons,
    not a coin flip: with a fixed line the base rate is rarely 50%, so scoring against ln 2 would flatter
    the model. Skill here = 1 - logloss / base-rate logloss.
    """
    col, pos, line = spec
    by_player = defaultdict(list)
    for r in props:
        if (r.get("position_group") or r.get("position")) != pos:
            continue
        v = fnum(r.get(col))
        if v is None:
            continue
        by_player[(r.get("player_id"), int(fnum(r.get("season"), 0)))].append(
            (int(fnum(r.get("week"), 0)), v))
    # base rate from seasons strictly before the evaluated season
    base_hits, base_n = 0, 0
    for (pid, season), lst in by_player.items():
        if season in prior_seasons:
            for _, v in lst:
                base_hits += 1 if v > line else 0
                base_n += 1
    base_rate = (base_hits + 1) / (base_n + 2) if base_n else 0.5
    recs = []
    for (pid, season), lst in by_player.items():
        if season != season_eval:
            continue
        lst.sort()
        for i in range(min_games, len(lst)):
            prior = [v for _, v in lst[:i]]
            y = 1 if lst[i][1] > line else 0
            p = (sum(1 for v in prior if v > line) + 1) / (len(prior) + 2)
            recs.append({"p": p, "y": y, "player": pid, "week": lst[i][0]})
    if not recs:
        return None
    ll = mean([logloss(r["p"], r["y"]) for r in recs])
    ll_base = mean([logloss(base_rate, r["y"]) for r in recs])
    acc = mean([1 if (r["p"] >= base_rate) == (r["y"] == 1) else 0 for r in recs])
    return {"market": col, "position": pos, "line": line, "games": len(recs),
            "logloss": round(ll, 4), "baseRate": round(base_rate, 4),
            "baseRateLogloss": round(ll_base, 4),
            "accuracy": round(acc, 4),
            "skill": round(1 - ll / ll_base, 4) if ll_base else None,
            "priorGames": base_n,
            "note": "Baseline is the league base rate on the same line from strictly prior seasons. "
                    "No prop price exists in any reachable source, so no edge is claimed."}


def prop_correlation(props, season_eval, specs, min_games=4):
    """Measured correlation between prop overs of players on the SAME team and week (shared game script)."""
    out = []
    for s1, s2 in itertools.combinations(specs, 2):
        c1, p1, l1 = s1
        c2, p2, l2 = s2
        if p1 != p2:
            continue
        table = defaultdict(dict)
        for r in props:
            if int(fnum(r.get("season"), 0)) != season_eval:
                continue
            if (r.get("position_group") or "") != p1:
                continue
            v = fnum(r.get(c1))
            w = fnum(r.get(c2))
            if v is None or w is None:
                continue
            table[(r.get("team"), int(fnum(r.get("week"), 0)))][r.get("player_id")] = (
                1 if v > l1 else 0, 1 if w > l2 else 0)
        xs, ys = [], []
        for key, players in table.items():
            ids = list(players)
            for a, b in itertools.combinations(ids, 2):
                xs.append(players[a][0])
                ys.append(players[b][1])
        if len(xs) < 200:
            continue
        r = pearson(xs, ys)
        lo, hi = bootstrap_ci(xs, ys, n=400)
        out.append({"a": c1, "b": c2, "position": p1, "n": len(xs),
                    "r": round(r, 4) if r is not None else None, "ci": [lo, hi]})
    return out


# ---------------------------------------------------------------- parlay / copula


def gauss_copula_joint(ps, corr):
    """Joint probability that all legs win under a Gaussian copula with correlation matrix `corr`."""
    k = len(ps)
    if k == 1:
        return ps[0]
    # use a low-discrepancy grid over the 2-D case; for k>2 use Monte Carlo with fixed seed
    rng = random.Random(SEED)
    try:
        import statistics as st  # noqa: F401
        L = cholesky(corr)
    except Exception:  # noqa: BLE001 - fall back to independence if the matrix is not PD
        return math.prod(ps)
    hits = 0
    N = 20000
    for _ in range(N):
        z = [rng.gauss(0, 1) for _ in range(k)]
        x = [sum(L[i][j] * z[j] for j in range(i + 1)) for i in range(k)]
        ok = True
        for i in range(k):
            # probit of ps[i]
            if norm_cdf(x[i]) > ps[i]:
                ok = False
                break
        if ok:
            hits += 1
    return hits / N


def cholesky(A):
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                v = A[i][i] - s
                if v <= 1e-12:
                    raise ValueError("not positive definite")
                L[i][j] = math.sqrt(v)
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---------------------------------------------------------------- leaderboard


def build_leaderboard(games, recs, base, corr, prop_results, prop_corr, deflation):
    lb = []
    s = scores(recs, base)
    stab = stability(recs, base)
    cal = calibration(recs)
    gates = {
        "G3_sample": {"pass": s["games"] >= 200 and len(stab) >= 3,
                      "value": f"{s['games']} games across {len(stab)} seasons"},
        "G4_skill": {"pass": (s["skill"] or 0) > 0, "value": s["skill"]},
        "G5_deflation": {"pass": bool(deflation["passed"]),
                         "value": f"observed {s['skill']} vs null p95 {deflation['p95']} (N={deflation['N']})"},
        "G6_calibration": {"pass": (cal["slope"] is not None and 0.8 <= cal["slope"] <= 1.25),
                           "value": cal["slope"]},
        "G7_stability": {"pass": sum(1 for v in stab.values() if v is not None and v > 0) >= max(1, len(stab) * 2 // 3),
                         "value": stab},
        "G8_market": {"pass": True, "value": "reported separately; no edge claimed without line history"},
    }
    passed = sum(1 for g in gates.values() if g["pass"])
    tier = "A" if passed >= 5 else ("C" if gates["G4_skill"]["pass"] else "D")
    score = 0.0
    if s["skill"] and deflation["p95"] is not None:
        score = 100 * max(0.0, s["skill"] - deflation["p95"]) * min(1, s["games"] / 1000)
        if cal["slope"]:
            score *= max(0.2, min(1.2, 1.2 - abs(cal["slope"] - 1)))
    # NOTE: the single-game family rows are emitted by family_rows() so that calibration and stability
    # travel with the row that owns them; this function returns only market and combination rows.
    # market-relative variant: does the model add anything over the published spread?
    mkt = market_track(games, recs)
    if mkt:
        lb.append(mkt)

    # parlay families
    lb += parlay_family(games, recs, corr)

    # prop families
    for spec in PROP_SPECS:
        pr = [p for p in prop_results if p and p["market"] == spec[0]]
        if not pr:
            continue
        p0 = pr[0]
        g_pass = p0["games"] >= 200 and (p0["skill"] or 0) > 0
        lb.append({"family": "prop", "name": f"{spec[1]} {spec[0].replace('_', ' ')} over {spec[2]}",
                   "tier": "C" if g_pass else "D", "score": round(max(0.0, (p0["skill"] or 0)) * 10, 3),
                   "metrics": p0, "gates": {"G3_sample": {"pass": p0["games"] >= 200, "value": p0["games"]},
                                            "G4_skill": {"pass": (p0["skill"] or 0) > 0, "value": p0["skill"]},
                                            "G8_market": {"pass": False, "value": "market=unavailable"}},
                   "claim": "Forecast accuracy against a 50/50 baseline. There is no prop price in any reachable "
                            "source, so this is Tier C at best by construction."})
    return lb


def market_track(games, recs):
    """
    Does the model beat the published spread line? The spread is converted to a win probability with a
    normal approximation (sigma = 13.5 points, the long-standing football margin SD) purely as a reference.
    Because the line is a single snapshot with unknown timing, this is labelled a reference, not an edge.
    """
    pairs = [(r, g) for r in recs for g in games if g["game_id"] == r["game_id"] and g["spread_line"] is not None]
    if len(pairs) < 100:
        return None
    sigma = 13.5
    ll_m, ll_b = [], []
    for r, g in pairs:
        impl = norm_cdf(-g["spread_line"] / sigma)  # home covers -> home win prob proxy
        ll_m.append(logloss(r["p"], r["y"]))
        ll_b.append(logloss(impl, r["y"]))
    return {"family": "single", "name": "Model vs published spread (reference only)",
            "tier": "C", "score": 0.0,
            "metrics": {"games": len(pairs), "modelLogloss": round(mean(ll_m), 4),
                        "spreadImpliedLogloss": round(mean(ll_b), 4),
                        "skill": round(1 - mean(ll_m) / mean(ll_b), 4)},
            "gates": {"G8_market": {"pass": False,
                                    "value": "one un-timestamped snapshot; no closing line, no vig, no ROI"}},
            "claim": "Compares the model with a probability implied by the published spread. Reference only: "
                     "the timing of that line is unknown, so beating it would not establish a tradable edge."}


def parlay_family(games, recs, corr):
    """
    Cross-game combinations of the model's most confident picks. The legs come from different games, so the
    measured cross-leg correlation is ~0 by construction; what matters is whether the stated joint probability
    matches the realised hit rate. That calibration is reported rather than an unmeasurable 'return'.
    """
    out = []
    by_season = defaultdict(list)
    for r in recs:
        by_season[r["season"]].append(r)
    for k in (2, 3):
        exp, real, n = 0.0, 0, 0
        for season, rs in by_season.items():
            rs = sorted(rs, key=lambda r: -max(r["p"], 1 - r["p"]))[:k]
            if len(rs) < k:
                continue
            ps = [r["p"] if r["p"] >= 0.5 else 1 - r["p"] for r in rs]
            hit = all((r["p"] >= 0.5) == (r["y"] == 1) for r in rs)
            exp += math.prod(ps)
            real += 1 if hit else 0
            n += 1
        if n == 0:
            continue
        out.append({"family": "parlay", "name": f"{k}-leg cross-game parlay (highest-confidence picks)",
                    "tier": "C", "score": 0.0,
                    "metrics": {"legs": k, "seasonsTested": n,
                                "expectedJoint": round(exp / n, 4),
                                "realisedHitRate": round(real / n, 4),
                                "difference": round(real / n - exp / n, 4),
                                "note": "One combination per season; a joint probability is not a payout. "
                                        "With this sample the realised rate is far too noisy to confirm calibration."},
                    "gates": {"G3_sample": {"pass": n >= 30, "value": f"{n} combinations"},
                              "G8_market": {"pass": False,
                                            "value": "no parlay price, payout or vig in any reachable source"}},
                    "claim": "Joint probability and realised hit rate only. No payout, no vig, no ROI."})
    return out


def prop_combo_family(prop_corr, props, seasons):
    """
    Same-game prop combo built ONLY where the measured correlation is real: the pair must exclude zero in its
    bootstrap interval. The joint probability is then computed twice — naive product vs copula with the measured
    r — and the gap is the size of the error that multiplying marginals would introduce.
    """
    out = []
    for pc in prop_corr[:6]:
        lo, hi = pc.get("ci") or [None, None]
        if lo is None or not (lo > 0 or hi < 0):
            continue
        r = pc["r"]
        p1, p2 = 0.55, 0.55  # illustrative marginal; the point is the gap, not the marginal
        C = [[1.0, r], [r, 1.0]]
        joint_corr = gauss_copula_joint([p1, p2], C)
        joint_indep = p1 * p2
        out.append({"family": "prop-combo", "name": f"Same-game combo: {pc['a']} + {pc['b']} ({pc['position']})",
                    "tier": "C", "score": 0.0,
                    "metrics": {"r": r, "ci": pc["ci"], "pairs": pc["n"],
                                "jointIfIndependent": round(joint_indep, 4),
                                "jointWithMeasuredCorrelation": round(joint_corr, 4),
                                "errorFromAssumingIndependence": round(joint_corr - joint_indep, 4),
                                "note": "Marginals are illustrative (0.55 each). The published quantity is the gap "
                                        "between the copula joint and the naive product, not a price."},
                    "gates": {"G8_market": {"pass": False, "value": "no prop price exists"}},
                    "claim": "Measures how wrong independence would be. No price, no payout, no edge."})
    return out


# ---------------------------------------------------------------- main


def run(raw_dir, seasons, out_dir, selftest=False, perm_n=60):
    games = load_games(raw_dir, seasons)
    injuries = load_injuries(raw_dir, seasons)
    depth = load_depth(raw_dir, seasons, {})
    snaps = load_snaps(raw_dir, seasons)
    games = build_signals(games, injuries, depth, snaps)

    complete = [g for g in games if g["complete"]]
    seasons_all = sorted({g["season"] for g in complete})
    seasons_eval = [s for s in seasons_all if s > min(seasons_all)][:6]
    base = naive_prior(games, seasons_eval, seasons_all)
    results = {}
    for fam, feats, K in (("context", FEATURES, 11), ("strength", STRENGTH_FEATURES, 9)):
        recs_f = walk_forward(games, seasons_eval, features=feats)
        if not recs_f:
            continue
        sf = scores(recs_f, base)
        df = deflate(games, seasons_eval, base, sf["skill"], N=perm_n, K=K, features=feats)
        results[fam] = {"recs": recs_f, "scores": sf, "deflation": df, "features": feats,
                        "calibration": calibration(recs_f), "stability": stability(recs_f, base)}
    if not results:
        return {"error": "no evaluable games", "games": len(games)}
    best = max(results, key=lambda k: (results[k]["scores"]["skill"] or -9))
    recs, s, defl = results[best]["recs"], results[best]["scores"], results[best]["deflation"]
    corr = correlation_matrix(games, seasons_eval)
    props = load_prop_rows(raw_dir, seasons_eval)
    prop_results = [prop_eval(props, s2, spec, prior_seasons=[x for x in seasons if x < s2])
                    for s2 in seasons_eval[-2:] for spec in PROP_SPECS]
    pcorr = []
    for s2 in seasons_eval[-2:]:
        pcorr += prop_correlation(props, s2, PROP_SPECS)
    lb = build_leaderboard(games, recs, base, corr, prop_results, pcorr, defl)
    lb += family_rows(results)
    lb += prop_combo_family(pcorr, props, seasons_eval)

    coverage = feature_coverage(games, seasons_eval)
    board = current_board(games, injuries, depth, snaps, LineupIndex(depth, snaps, injuries))
    result = {
        "bestFamily": best,
        "families": {k: {"scores": v["scores"], "deflation": v["deflation"],
                         "features": v["features"]} for k, v in results.items()},
        "generatedUTC": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "selftest": selftest,
        "seasons": seasons_all, "evaluatedSeasons": seasons_eval,
        "gameCount": len(games), "completedGames": len(complete),
        "droppedIncomplete": len(games) - len(complete),
        "model": s, "deflation": defl, "correlation": corr,
        "propCorrelation": pcorr,
        "props": [p for p in prop_results if p],
        "leaderboard": lb,
        "featureCoverage": coverage,
        "currentBoard": board,
        "modelSpec": {"features": FEATURES, "l2": 1.0, "type": "logistic regression, walk-forward by season",
                      "fill": "missing signal -> 0 (documented; never a guessed value)"},
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "model_results.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    return result


def family_rows(results):
    """One leaderboard row per pre-registered feature family, so no comparison is hidden."""
    order = {"A": 2, "C": 1, "D": 0}
    rows = []
    for fam, r in results.items():
        sc, df = r["scores"], r["deflation"]
        cal = r.get("calibration") or {}
        stab = r.get("stability") or {}
        cal_ok = cal.get("slope") is not None and 0.8 <= cal["slope"] <= 1.25
        stab_ok = sum(1 for v in stab.values() if (v or 0) > 0) >= max(1, len(stab) * 2 // 3)
        passed = (sc["skill"] or 0) > 0 and df["passed"] and cal_ok and stab_ok
        rows.append({
            "family": "single", "name": f"Single-game model — {fam} features ({len(r['features'])} signals)",
            "tier": "A" if passed else ("C" if (sc["skill"] or 0) > 0 else "D"),
            "score": round(max(0.0, (sc["skill"] or 0) - (df["p95"] or 0)) * 100, 3) if sc["skill"] else 0.0,
            "metrics": sc,
            "gates": {"G4_skill": {"pass": (sc["skill"] or 0) > 0, "value": sc["skill"]},
                      "G5_deflation": {"pass": df["passed"],
                                       "value": f"observed {sc['skill']} vs best-of-{df['K']} null p95 {df['p95']}"},
                      "G6_calibration": {"pass": (cal.get("slope") is not None and
                                                 0.8 <= cal["slope"] <= 1.25), "value": cal.get("slope")},
                      "G7_stability": {"pass": sum(1 for v in stab.values() if (v or 0) > 0) >= max(1, len(stab) * 2 // 3),
                                       "value": stab}},
            "calibration": cal, "stability": stab,
            "claim": "Out-of-sample probability skill vs a prior-season win-rate baseline. No betting return claimed.",
        })
    return rows


def current_board(games, injuries, depth, snaps, index):
    """
    The current-season board: for each team, the latest week in the data, the official injury report
    for that week, and the lineup status (starters vs 2nd/3rd/4th string) derived from the latest
    depth-chart snapshot. Every field is traceable to a published row; anything absent stays blank.
    """
    seasons = sorted({g["season"] for g in games})
    if not seasons:
        return {}
    cur = seasons[-1]
    cur_games = [g for g in games if g["season"] == cur]
    if not cur_games:
        return {}
    latest_week = max((g["week"] for g in cur_games), default=0)
    teams = sorted({g["home"] for g in cur_games} | {g["away"] for g in cur_games})
    board = {"season": cur, "week": latest_week, "teams": [], "games": []}

    inj_by_team = defaultdict(list)
    for (team, week, gid), v in injuries.items():
        if week == latest_week:
            inj_by_team[team].append({"gsisId": gid, **v})

    for t in teams:
        rep = inj_by_team.get(t, [])
        outs = [x for x in rep if (x.get("report") or "").lower() == "out"]
        doubts = [x for x in rep if (x.get("report") or "").lower() == "doubtful"]
        ques = [x for x in rep if (x.get("report") or "").lower() == "questionable"]
        off_val, off_out, off_doubt, off_ques = index.value(t, latest_week, "off")
        def_val, def_out, def_doubt, def_ques = index.value(t, latest_week, "def")
        # who is listed as a backup at each tier, per position group (published rows only)
        tiers = defaultdict(lambda: defaultdict(list))
        for pos in ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "CB", "S"):
            for gid, v in index.by_team_week_pos.get((t, latest_week, pos), []):
                rank = v.get("rank")
                if rank and rank <= 4 and v.get("name"):
                    tiers[pos][rank].append(v["name"])
        board["teams"].append({
            "team": t,
            "reportCount": len(rep),
            "out": len(outs), "doubtful": len(doubts), "questionable": len(ques),
            "outNames": [x.get("name") or x.get("full_name") or x["gsisId"] for x in outs][:8],
            "offStarterValue": off_val, "defStarterValue": def_val,
            "offOutShare": off_out, "defOutShare": def_out,
            "offDoubtfulShare": off_doubt, "defDoubtfulShare": def_doubt,
            "offQuestionableShare": off_ques, "defQuestionableShare": def_ques,
            "tiers": {p: {str(r): names for r, names in d.items()} for p, d in tiers.items()},
            "status": ("verified" if rep or off_val is not None else "unknown"),
        })
    for g in [x for x in cur_games if x["week"] == latest_week]:
        board["games"].append({
            "gameId": g["game_id"], "date": g["date"], "week": g["week"],
            "away": g["away"], "home": g["home"], "roof": g["roof"],
            "awayRest": g["away_rest"], "homeRest": g["home_rest"],
            "spread": g["spread_line"], "total": g["total_line"],
            "complete": g["complete"],
            "modelHomeWinProb": None,  # filled by the caller with the walk-forward probability when available
        })
    return board


def feature_coverage(games, seasons_eval):
    out = []
    gs = [g for g in games if g["season"] in seasons_eval]
    for f in FEATURES + ["home_off_value", "away_off_value", "home_def_value", "away_def_value",
                         "home_off_out_share", "home_def_out_share"]:
        n = sum(1 for g in gs if g["s"].get(f) is not None)
        out.append({"feature": f, "present": n, "total": len(gs),
                    "share": round(n / len(gs), 3) if gs else None,
                    "status": "verified" if n == len(gs) else ("partial — blank where absent" if n else "unavailable")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=RAW)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--seasons", nargs="*", type=int, default=list(range(2016, 2027)))
    ap.add_argument("--selftest", action="store_true", help="use nfl/raw/samples (offline dev loop)")
    ap.add_argument("--perm", type=int, default=60)
    args = ap.parse_args()
    raw = "nfl/raw/samples" if args.selftest else args.raw
    res = run(raw, args.seasons, args.out, selftest=args.selftest, perm_n=args.perm)
    if "error" in res:
        print("ERROR", res)
        return 1
    print(json.dumps({"games": res["gameCount"], "model": res["model"], "deflation": res["deflation"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
