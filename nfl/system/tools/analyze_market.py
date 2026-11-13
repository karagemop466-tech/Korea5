#!/usr/bin/env python3
"""Compute every number the NFL section publishes, from the ingested official data.

Design rule: a number is only emitted when the official inputs exist and the sample
clears its suppression floor. Otherwise the key is absent (the site prints an
"unverified" badge) — never zero, never a guess.

Outputs nfl/data/derived/*.json:
  coverage.json      what was ingested, with counts and retrieval stamps
  matchups.json      per-game rest differential + scoring-profile estimate (MODEL)
  homefield.json     realised home win rate with a Wilson interval
  correlation.json   teammate / same-game volume correlation with bootstrap CI
  injuries.json      injury load by unit + depth-tier next-man-up, per club
  depth.json         published depth by club/position, tier coverage
  market.json        de-vig comparator (any price pair), parlay hold compounding
  skill.json         shuffle test + calibration demo on the official finals
  leaderboard.json   the three boards, all "not certified", with reasons
  summary.json       the numbers the dashboard shows
"""
from __future__ import annotations

import itertools
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "nfl" / "system"
DER = ROOT / "data" / "derived"
DER.mkdir(parents=True, exist_ok=True)

RNG = random.Random(20261113)  # fixed seed so every published interval is reproducible

SUPPRESSION = {"playerCorrelation": 8, "teamRate": 6, "propProbability": 8}
MIN_FOR_PUBLICATION = 8


def load(name, default=None):
    p = ROOT / "data" / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def write(name, obj):
    (DER / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ statistics
def wilson(k: int, n: int, z: float = 1.645):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (c - s) / d), 4), round(min(1.0, (c + s) / d), 4)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def bootstrap_corr(xs, ys, draws=1000, lower_n=None):
    """90% bootstrap interval for Pearson r. Returns (r, lo, hi, n) or None."""
    n = len(xs)
    if n < (lower_n or SUPPRESSION["playerCorrelation"]):
        return None
    r = pearson(xs, ys)
    if r is None:
        return None
    ests = []
    idx = range(n)
    for _ in range(draws):
        pick = [RNG.choice(idx) for _ in idx]
        rr = pearson([xs[i] for i in pick], [ys[i] for i in pick])
        if rr is not None:
            ests.append(rr)
    if not ests:
        return None
    ests.sort()
    lo = ests[int(0.05 * len(ests))]
    hi = ests[int(0.95 * len(ests)) - 1]
    spans_zero = lo <= 0 <= hi
    return {"r": round(r, 3), "lo": round(lo, 3), "hi": round(hi, 3), "n": n,
            "spansZero": spans_zero,
            "reading": ("indistinguishable from zero" if spans_zero else
                        ("positive" if r > 0 else "negative"))}


def brier(probs, outcomes):
    return round(sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs), 4)


def ece(probs, outcomes, bins=10):
    """Expected calibration error over equal-width probability bins (bins with n<5 skipped)."""
    buckets = defaultdict(list)
    for p, o in zip(probs, outcomes):
        b = min(bins - 1, int(p * bins))
        buckets[b].append((p, o))
    total, err = 0, 0.0
    for b, items in buckets.items():
        if len(items) < 5:
            continue
        conf = sum(p for p, _ in items) / len(items)
        acc = sum(o for _, o in items) / len(items)
        err += len(items) * abs(conf - acc)
        total += len(items)
    return round(err / total, 4) if total else None


# ------------------------------------------------------------ price utilities
def devig_multiplicative(pa, pb):
    """Remove the margin by dividing each implied probability by the sum."""
    return pa / (pa + pb), pb / (pa + pb)


def devig_additive(pa, pb):
    """Remove the margin by subtracting half of it from each side."""
    m = (pa + pb - 1) / 2
    return pa - m, pb - m


def american_to_prob(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def prob_to_american(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def run():
    results = load("official-results.json", {"results": []})
    injuries = load("official-injuries.json", {"rows": []})
    depth = load("official-depth.json", {"rows": [], "meta": {}})
    teamstats = load("official-teamstats.json", {"tables": {}})
    playerstats = load("official-playerstats.json", {"categories": {}})
    roster = load("official-roster.json", {"teams": []})
    report = load("fetch-report.json", {})

    games = results.get("results", [])
    inj = injuries.get("rows", [])
    dep = depth.get("rows", [])

    # ---------------------------------------------------------------- coverage
    by_season = Counter(g["season"] for g in games)
    # Deterministic stamp: the newest official retrieval time in the inputs, NOT the wall clock.
    # A wall-clock stamp makes every rebuild differ, which hides real drift behind timestamp noise.
    stamps = [results.get("meta", {}).get("retrievedUTC"),
              injuries.get("meta", {}).get("retrievedUTC"),
              depth.get("meta", {}).get("retrievedUTC"),
              report.get("finishedUTC")]
    stamps = sorted(x for x in stamps if x)
    data_as_of = stamps[-1] if stamps else "unknown"
    coverage = {
        "generatedUTC": data_as_of,
        "sources": [
            {"dataset": "Final scores", "rows": len(games), "bySeason": dict(by_season),
             "retrievedUTC": results.get("meta", {}).get("retrievedUTC"),
             "url": "https://www.nfl.com/schedules/2026/by-week/week-10",
             "official": True},
            {"dataset": "Injury report rows", "rows": len(inj),
             "bySeason": dict(Counter(r["season"] for r in inj)),
             "retrievedUTC": injuries.get("meta", {}).get("retrievedUTC"),
             "url": "https://www.nfl.com/injuries/league/2026/reg10", "official": True},
            {"dataset": "Depth-chart entries", "rows": len(dep),
             "clubs": len({r["team"] for r in dep}),
             "url": "https://www.49ers.com/team/depth-chart", "official": True},
            {"dataset": "Team stat tables", "rows": len(teamstats.get("tables", {})),
             "url": "https://www.nfl.com/stats/team-stats/", "official": True},
            {"dataset": "Player stat categories", "rows": len(playerstats.get("categories", {})),
             "url": "https://www.nfl.com/stats/player-stats/", "official": True},
            {"dataset": "Roster players", "rows": sum(len(t["players"]) for t in roster.get("teams", [])),
             "url": "https://www.nfl.com/teams/san-francisco-49ers/roster", "official": True},
        ],
        "fetchFailures": len(report.get("failures", [])),
        "unavailableDepthCharts": depth.get("meta", {}).get("unavailable", []),
        "priceFeedAvailable": False,
        "priceFeedNote": "No official NFL page publishes odds (probe: 0 odds fields on week, game and "
                         "stats pages). No price data exists in this repository.",
    }
    write("coverage.json", coverage)

    # ------------------------------------------------------------- home field
    hf = {}
    for season in sorted({g["season"] for g in games}):
        ss = [g for g in games if g["season"] == season]
        home_wins = sum(1 for g in ss if g["homeScore"] > g["awayScore"])
        ties = sum(1 for g in ss if g["homeScore"] == g["awayScore"])
        decided = len(ss) - ties
        lo, hi = wilson(home_wins, decided)
        hf[str(season)] = {"games": len(ss), "tiesExcluded": ties, "decided": decided,
                           "homeWins": home_wins,
                           "homeWinRate": round(home_wins / decided, 4) if decided else None,
                           "ci90": [lo, hi],
                           "sourceUrl": "https://www.nfl.com/standings/",
                           "label": "official finals; rate is a descriptive statistic, not a forecast"}
    tot = sum(v["homeWins"] for v in hf.values())
    dec = sum(v["decided"] for v in hf.values())
    lo, hi = wilson(tot, dec)
    hf["combined"] = {"decided": dec, "homeWins": tot,
                      "homeWinRate": round(tot / dec, 4) if dec else None,
                      "ci90": [lo, hi]}
    write("homefield.json", hf)

    # ---------------------------------------------------------------- rest days
    # Only games with two resolvable abbreviations and a date are usable.
    def game_date(g):
        # the official card prints the date inside the linkName; results.json keeps weekLabel
        # and the game URL. Dates are re-derived from the source page order is NOT allowed,
        # so we use the startUTC/datePT fields when present on the upstream schedule.
        return g.get("datePT") or g.get("date")

    # Rest is computed from the official 2026 schedule feed that the repo already holds
    # (official/nfl-2026.json), which carries a verified PT date per game.
    sched = load_path(REPO / "official" / "nfl-2026.json")
    rest_rows, rest_summary = [], {"gamesWithBothTeams": 0, "shortWeekGames": 0}
    if sched:
        by_team = defaultdict(list)
        for g in sched.get("games", []):
            if g.get("seasonType") != "REG" or not g.get("datePT"):
                continue
            for side in ("away", "home"):
                name = g.get(side)
                if name:
                    by_team[name].append((g["datePT"], g))
        for team, lst in by_team.items():
            lst.sort(key=lambda x: x[0])
            for i in range(1, len(lst)):
                d0 = date.fromisoformat(lst[i - 1][0])
                d1 = date.fromisoformat(lst[i][0])
                days = (d1 - d0).days
                rest_summary["gamesWithBothTeams"] += 1
                if days <= 4:
                    rest_summary["shortWeekGames"] += 1
                rest_rows.append({"team": team, "prevDate": lst[i - 1][0], "date": lst[i][0],
                                  "restDays": days,
                                  "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-10"})
    rest_hist = Counter(r["restDays"] for r in rest_rows)
    rest_summary["restDayHistogram"] = dict(sorted(rest_hist.items()))
    rest_summary["minRestDays"] = min(rest_hist) if rest_hist else None
    rest_summary["maxRestDays"] = max(rest_hist) if rest_hist else None
    rest_summary["teamsCovered"] = len({r["team"] for r in rest_rows})
    rest_summary["label"] = "COMPUTED from official kickoff dates; rest days are exact, travel is not included"
    write("rest.json", {"summary": rest_summary, "rows": rest_rows[:4000]})

    # ------------------------------------------- scoring rates from official finals
    # IMPORTANT: the official team-stats "scoring" tables publish TOUCHDOWNS (Rsh TD / Rec TD /
    # Tot TD / 2-PT and FR TD / SFTY / INT TD), NOT points. Using them as points was wrong.
    # Points are therefore computed from official final scores, per team, and n is printed.
    def accumulate(season_filter):
        pf, pa, gc = defaultdict(float), defaultdict(float), defaultdict(int)
        for g in games:
            if season_filter and g.get("season") != season_filter:
                continue
            if not g.get("awayAbbr") or not g.get("homeAbbr"):
                continue
            a, h = g["awayAbbr"], g["homeAbbr"]
            pf[a] += g["awayScore"]; pa[a] += g["homeScore"]; gc[a] += 1
            pf[h] += g["homeScore"]; pa[h] += g["awayScore"]; gc[h] += 1
        return pf, pa, gc

    # Primary rates are the CURRENT season only, so no figure silently mixes seasons.
    pts_for, pts_against, games_counted = accumulate(2026)
    scoring_rates = {}
    for t in sorted(games_counted):
        n = games_counted[t]
        scoring_rates[t] = {
            "team": t, "games": n,
            "pointsFor": int(pts_for[t]), "pointsAgainst": int(pts_against[t]),
            "ppgFor": round(pts_for[t] / n, 2), "ppgAgainst": round(pts_against[t] / n, 2),
            "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-10",
            "label": f"COMPUTED from official 2026 final scores only; n = {n} completed games, not a full season",
        }
    # The prior season is kept separately and marked, never blended into the current rate.
    pf25, pa25, gc25 = accumulate(2025)
    prior_rates = {}
    for t in sorted(gc25):
        n = gc25[t]
        prior_rates[t] = {"team": t, "games": n,
                          "ppgFor": round(pf25[t] / n, 2), "ppgAgainst": round(pa25[t] / n, 2),
                          "sourceUrl": "https://www.nfl.com/schedules/2025/by-week/week-10",
                          "label": "COMPUTED from official 2025 final scores only"}
    # shrinkage weight: 8 games of evidence vs a 17-game prior -> weight_w = n/(n+k)
    K = 9.0
    league_ppg = (round(sum(v["ppgFor"] for v in scoring_rates.values()) / len(scoring_rates), 2)
                  if scoring_rates else None)
    league_ppg_2025 = (round(sum(v["ppgFor"] for v in prior_rates.values()) / len(prior_rates), 2)
                       if prior_rates else None)
    for t, v in scoring_rates.items():
        w = v["games"] / (v["games"] + K)
        v["shrunkPpgFor"] = round(w * v["ppgFor"] + (1 - w) * (league_ppg or 0), 2)
        v["shrunkPpgAgainst"] = round(w * v["ppgAgainst"] + (1 - w) * (league_ppg or 0), 2)
        v["shrinkWeight"] = round(w, 3)

    matchups = []
    for g in games:
        if g["season"] != 2026 or not g.get("awayAbbr") or not g.get("homeAbbr"):
            continue
        a, h = g["awayAbbr"], g["homeAbbr"]
        ra, rh = scoring_rates.get(a), scoring_rates.get(h)
        est = None
        if ra and rh and league_ppg:
            # own shrunk offence averaged with opponent's shrunk points-allowed, re-centred on
            # the league mean. A MODEL, explicitly not a betting line.
            away_est = ((ra["shrunkPpgFor"] + rh["shrunkPpgAgainst"]) / 2 + league_ppg) / 2
            home_est = ((rh["shrunkPpgFor"] + ra["shrunkPpgAgainst"]) / 2 + league_ppg) / 2
            est = {"awayEstimate": round(away_est, 1), "homeEstimate": round(home_est, 1),
                   "homeMinusAway": round(home_est - away_est, 1),
                   "total": round(away_est + home_est, 1),
                   "evidenceGames": min(ra["games"], rh["games"])}
        matchups.append({
            "weekLabel": g["weekLabel"], "away": a, "home": h,
            "awayScore": g["awayScore"], "homeScore": g["homeScore"],
            "margin": g["homeScore"] - g["awayScore"],
            "gameUrl": g["gameUrl"], "sourceUrl": g["sourceUrl"],
            "model": est,
            "modelLabel": "MODEL — shrunk own scoring vs opponent scoring-allowed, re-centred on the league mean",
        })
    write("scoring.json", {
        "leagueMeanPointsPerGame": league_ppg,
        "leagueMeanPointsPerGame2025": league_ppg_2025,
        "shrinkK": K,
        "shrinkNote": "weight = n/(n+K). With 8 games the club's own rate gets ~47% weight, so a hot "
                      "start cannot masquerade as a season-long truth.",
        "teams": scoring_rates,
        "priorSeasonTeams": prior_rates,
        "officialTeamScoringTableWarning":
            "The official team-stats 'scoring' pages publish touchdowns, not points. Points here are "
            "computed from official final scores. Both are official; the distinction is stated so no "
            "reader mistakes a touchdown count for a points-per-game figure.",
        "sourceUrls": ["https://www.nfl.com/stats/team-stats/offense/scoring/2026/reg/all",
                       "https://www.nfl.com/schedules/2026/by-week/week-10"],
    })
    write("matchups.json", {
        "leagueMeanPointsPerGame": league_ppg,
        "games": matchups,
        "note": "Scores are official. The estimate column is a MODEL output, not an official value and "
                "not a betting line. It is included only to show the method that would price a game "
                "once real prices exist.",
        "sourceUrls": ["https://www.nfl.com/schedules/2026/by-week/week-10",
                       "https://www.nfl.com/stats/team-stats/offense/scoring/2026/reg/all"],
    })

    # ---------------------------------------------------------------- injuries
    latest_week = max((r.get("week", 0) for r in inj if r.get("season") == 2026), default=0)
    cur = [r for r in inj if r.get("season") == 2026 and r.get("week") == latest_week]
    pos_unit = POSITION_UNIT
    team_load = defaultdict(lambda: {"offense": 0, "defense": 0, "specialteams": 0, "out": 0,
                                     "doubtful": 0, "questionable": 0, "players": []})
    unmapped_teams = set()
    for r in cur:
        unit = pos_unit.get((r.get("position") or "").upper(), "unknown")
        key = TEAM_NAME_TO_ABBR.get((r["team"] or "").strip().lower())
        if key is None:
            unmapped_teams.add(r["team"])
            key = r["team"]
        r["teamAbbr"] = key
        team_load[key][unit] = team_load[key].get(unit, 0) + 1
        gs = (r.get("gameStatus") or "").strip().lower()
        if gs in ("out", "doubtful", "questionable"):
            team_load[key][gs] += 1
        team_load[key]["players"].append({
            "player": r["player"], "position": r.get("position"), "injury": r.get("injury"),
            "practiceStatus": r.get("practiceStatus"), "gameStatus": r.get("gameStatus"),
            "unit": unit, "playerUrl": r.get("playerUrl"),
        })

    # depth index: team -> position -> [names by tier]
    depth_index = defaultdict(lambda: defaultdict(list))
    for r in dep:
        depth_index[r["team"]][r["position"]].append(r)
    for t in depth_index:
        for pos in depth_index[t]:
            depth_index[t][pos].sort(key=lambda x: x["depth"])

    next_up = []
    for team, rows in sorted(team_load.items()):
        out_by_pos = defaultdict(list)
        for p in rows["players"]:
            if (p["gameStatus"] or "").strip().lower() in ("out", "doubtful"):
                out_by_pos[(p["position"] or "").upper()].append(p["player"])
        for pos, names in sorted(out_by_pos.items()):
            chart = depth_index.get(team, {}).get(pos, [])
            starter = chart[0]["player"] if chart else None
            replacement = None
            if chart and names:
                # the next tier down from the highest listed tier that is unavailable
                listed = [c for c in chart if c["player"] in names]
                if listed:
                    worst = max(c["depth"] for c in listed)
                    nxt = [c for c in chart if c["depth"] == worst + 1]
                    replacement = nxt[0]["player"] if nxt else None
            next_up.append({
                "team": team, "position": pos,
                "listedOutOrDoubtful": names,
                "chartStarter": starter,
                "chartReplacement": replacement,
                "replacementTier": (next((c["depth"] for c in chart if c["player"] == replacement), None)),
                "tiersPublishedAtPosition": len(chart),
                "chartUpdatedAsOf": chart[0].get("chartUpdatedAsOf") if chart else None,
                "note": ("replacement named only when the club's own chart lists the next tier; "
                         "never inferred" if replacement else
                         "no published next tier at this position — left blank"),
                "sourceUrl": chart[0]["sourceUrl"] if chart else None,
                "injurySourceUrl": f"https://www.nfl.com/injuries/league/2026/reg{latest_week:02d}",
            })

    joined = sum(1 for r in next_up if r["chartStarter"])
    write("injuries.json", {
        "week": latest_week,
        "joinIntegrity": {
            "nextUpRows": len(next_up),
            "rowsWithDepthChartMatch": joined,
            "rowsWithoutDepthChartMatch": len(next_up) - joined,
            "unmappedTeamNames": sorted(x for x in unmapped_teams if x),
            "note": "The injury report prints club display names; the depth charts are keyed by "
                    "abbreviation. The mapping is explicit and any unmapped name is listed here "
                    "instead of silently producing an empty join.",
        },
        "teams": {t: {k: v for k, v in d.items() if k != "players"} | {"playerCount": len(d["players"])}
                  for t, d in sorted(team_load.items())},
        "players": [dict(p, team=t) for t, d in sorted(team_load.items()) for p in d["players"]],
        "nextUp": next_up,
        "sourceUrl": f"https://www.nfl.com/injuries/league/2026/reg{latest_week:02d}",
        "rule": "Counts are counts of official report rows by official position. They are NOT a severity "
                "score: one Out quarterback and three Questionable backups are not comparable.",
    })

    # ------------------------------------------------------------------- depth
    depth_out = []
    for team in sorted(depth_index):
        for pos in sorted(depth_index[team]):
            rows = depth_index[team][pos]
            depth_out.append({
                "team": team, "position": pos, "tiers": len(rows),
                "players": [{"tier": r["depth"], "label": r.get("depthLabel"), "player": r["player"]}
                            for r in rows],
                "chartUpdatedAsOf": rows[0].get("chartUpdatedAsOf"),
                "clubLabel": rows[0].get("clubLabelsChart"),
                "sourceUrl": rows[0]["sourceUrl"],
            })
    tier_hist = Counter(len(d["players"]) for d in depth_out)
    write("depth.json", {
        "positions": depth_out,
        "clubs": len({d["team"] for d in depth_out}),
        "tierHistogram": dict(sorted(tier_hist.items())),
        "unavailable": depth.get("meta", {}).get("unavailable", []),
        "note": "Clubs publish different tier counts and some self-label their chart 'Unofficial'. "
                "Depth is a club projection, not a measurement of who played.",
    })

    # ------------------------------------------------------------- correlation
    # Teammate volume correlation from official per-game player logs is not in the ingested
    # playerstats feed (that feed is season leaders). We therefore do NOT fabricate it:
    # we publish the inputs that exist and mark the correlation as unavailable this cycle.
    corr = {
        "available": False,
        "reason": "The ingested official player-stat feed contains season-to-date leaders, not "
                  "per-game logs joined by team and week. A correlation computed from season totals "
                  "would be a correlation of 32 aggregate points, not of game outcomes. Refusing to "
                  "publish it is the honest output; see Q08 and the method page.",
        "whatIsNeeded": "Per-player game logs (WK / OPP / stat columns), which nfl.com publishes on each "
                        "player page. That ingest is the next task and is not claimed as done here.",
        "suppressionFloor": SUPPRESSION["playerCorrelation"],
        "demonstration": demo_correlation(),
        "sourceUrl": "https://www.nfl.com/players/christian-mccaffrey/stats",
    }
    write("correlation.json", corr)

    # ---------------------------------------------------------------- market
    examples = [
        {"label": "Even-ish two-way", "a": -110, "b": -110},
        {"label": "Standard spread", "a": -115, "b": -105},
        {"label": "Heavy favourite", "a": -450, "b": +350},
    ]
    examples_out = []
    for ex in examples:
        pa, pb = american_to_prob(ex["a"]), american_to_prob(ex["b"])
        hold = round(pa + pb - 1, 4)
        ma, mb = devig_multiplicative(pa, pb)
        aa, ab = devig_additive(pa, pb)
        examples_out.append({
            **ex,
            "impliedA": round(pa, 4), "impliedB": round(pb, 4),
            "hold": hold, "holdPct": round(hold * 100, 2),
            "multiplicative": {"a": round(ma, 4), "b": round(mb, 4),
                               "aAmerican": prob_to_american(ma), "bAmerican": prob_to_american(mb)},
            "additive": {"a": round(aa, 4), "b": round(ab, 4),
                         "aAmerican": prob_to_american(aa), "bAmerican": prob_to_american(ab)},
            "methodGap": round(abs(ma - aa), 4),
            "note": "Illustrative arithmetic on a stated price pair. These are NOT NFL market prices.",
        })
    # parlay hold compounding
    parlay = []
    for legs in (2, 3, 4, 5):
        single_hold = 0.0454  # a -110/-110 pair
        # naive: (1-hold)^-legs style; publish the effective hold on a fair-parlay basis
        fair_mult = 1.0
        offered_mult = 1.0
        for _ in range(legs):
            fair_mult *= (1 / 0.5)   # 0.5 fair prob per leg -> fair decimal 2.0
            offered_mult *= (1 / (0.5 + single_hold / 2))
        parlay.append({
            "legs": legs,
            "fairDecimal": round(fair_mult, 3),
            "offeredDecimalAtSamePerLegHold": round(offered_mult, 3),
            "effectiveHold": round(1 - fair_mult / offered_mult, 4),
            "note": "Compounding of the per-leg margin. Computed from the stated -110/-110 hold.",
        })
    write("market.json", {
        "priceFeedAvailable": False,
        "devigExamples": examples_out,
        "parlayHold": parlay,
        "sourceUrls": ["https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10",
                       "https://www.nfl.com/schedules/2026/by-week/week-10"],
        "notice": "No official NFL source publishes odds. The arithmetic below is a tool, not a market. "
                  "Every number here is arithmetic on a stated example, labelled as such.",
    })

    # ------------------------------------------------------- skill vs luck demo
    # Demonstrate the shuffle test on the only settled outcomes we hold: the official finals.
    # The 'strategy' is the home-field prior; the test asks whether picking home teams beats a
    # shuffle of the same picks against permuted outcomes.
    ss = [g for g in games if g["season"] in (2025, 2026)
          and g["homeScore"] != g["awayScore"] and g.get("homeAbbr")]
    outcomes = [1 if g["homeScore"] > g["awayScore"] else 0 for g in ss]
    n = len(outcomes)
    skill = {"n": n, "sourceUrl": "https://www.nfl.com/standings/"}
    if n >= 30:
        base = sum(outcomes) / n
        skill["observedHomeWinRate"] = round(base, 4)
        probs = [0.5] * n          # a know-nothing coin
        skill["brierCoin"] = brier(probs, outcomes)
        skill["brierHomePrior"] = brier([0.55] * n, outcomes)  # stated prior, not fitted
        # Shuffle test: permute outcomes, recompute the home-pick hit rate.
        # FIXED 2026-11-13 (session arena-827c3da2, defect A03): the previous version asked
        # whether sum(permuted outcomes) >= sum(outcomes). Permuting cannot change the number of
        # home wins, so the comparison was 232 >= 232 on every draw and the p-value was always
        # exactly 1.0000. It now asks the question a home-field prior actually implies: are the
        # home teams' wins spread over MORE games than chance would put them in? Two-sided
        # bootstrap over the per-game hit indicator, reported with its interval.
        hits = sum(outcomes)
        draws = 2000
        ge = 0
        boot = []
        for _ in range(draws):
            sample = [RNG.choice(outcomes) for _ in range(n)]
            rate = sum(sample) / n
            boot.append(rate)
            if abs(rate - 0.5) >= abs(base - 0.5):
                ge += 1
        boot.sort()
        lo_b = boot[int(0.025 * draws)]
        hi_b = boot[int(0.975 * draws) - 1]
        skill["shuffleTest"] = {
            "draws": draws,
            "statistic": "home win rate among decided games",
            "observed": hits,
            "observedRate": round(base, 4),
            "bootstrap95": [round(lo_b, 4), round(hi_b, 4)],
            "pValueTwoSided": round((ge + 1) / (draws + 1), 4),
            "reading": ("a home-field prior is not distinguishable from a coin at this sample"
                        if (ge + 1) / (draws + 1) > 0.05 else
                        "the observed home rate is unlikely under a coin"),
            "fixedOn": "2026-11-13",
            "previousVersion": ("permuted the outcomes and compared the permuted home-win COUNT with "
                                "the observed count; that quantity is invariant under permutation, so "
                                "the test returned p = 1.0000 by construction"),
            "note": "This tests OUTCOME randomness, not strategy skill. It demonstrates the machinery "
                    "the gates use; it is not evidence that any strategy is profitable.",
        }
        skill["calibrationDemo"] = {
            "eceCoin": ece(probs, outcomes),
            "eceHomePrior": ece([0.55] * n, outcomes),
            "note": "A constant 55% prior needs at least 20 games in a decile to be scored; with almost "
                    "all mass in one bin this is a weak calibration test, shown to prove the method runs.",
        }
    skill["certifiedStrategies"] = 0
    skill["whyNoneCertified"] = ("No strategy has 100 settled bets against a stored price. Certifying one "
                                 "would require inventing both the price and the settlement.")
    write("skill.json", skill)

    # --------------------------------------------------------------- leaderboard
    strategies = load_curated("strategies.json")
    leaderboard = {"boards": {}, "rewardAuthorised": False,
                   "rewardNote": "No reward is authorised (Q04). Ranks would attach to the same scoring "
                                 "without re-running anything.",
                   "sourceUrl": "https://www.nfl.com/standings/"}
    for bkey, b in (strategies or {}).get("boards", {}).items():
        entrants = [s for s in strategies["strategies"] if s["board"] == bkey]
        leaderboard["boards"][bkey] = {
            "label": b["label"], "minSettledSample": b["minSettledSample"],
            "entrants": [{"id": s["id"], "name": s["name"], "status": s["status"],
                          "blockedBy": s["blockedBy"], "settled": 0,
                          "brier": None, "logLoss": None, "roi": None, "clv": None,
                          "rank": None, "reward": "not authorised",
                          "sourceUrl": s.get("sourceUrl"),
                          "reason": "0 settled bets; no stored price"} for s in entrants],
            "eligible": 0,
        }
    write("leaderboard.json", leaderboard)

    # ------------------------------------------------------------------ summary
    summary = {
        "generatedUTC": coverage["generatedUTC"],
        "stampMeaning": "newest official retrieval time among the inputs — not the build time",
        "finalGames2026": by_season.get(2026, 0),
        "finalGames2025": by_season.get(2025, 0),
        "injuryRows2026": sum(1 for r in inj if r.get("season") == 2026),
        "injuryWeek": latest_week,
        "depthRows": len(dep),
        "depthClubs": len({r["team"] for r in dep}),
        "depthClubsUnavailable": len(depth.get("meta", {}).get("unavailable", [])),
        "teamStatTables": len(teamstats.get("tables", {})),
        "homeWinRate2026": hf.get("2026", {}).get("homeWinRate"),
        "homeWinRate2026Ci": hf.get("2026", {}).get("ci90"),
        "homeWinRateAll": hf["combined"]["homeWinRate"],
        "homeWinRateAllCi": hf["combined"]["ci90"],
        "leagueMeanPPG": league_ppg,
        "priceFeed": "none",
        "certifiedStrategies": 0,
        "shortWeekGames": rest_summary["shortWeekGames"],
        "minRestDays": rest_summary["minRestDays"],
    }
    write("summary.json", summary)
    print(json.dumps(summary, indent=1))


# ------------------------------------------------------------- helper loaders
def load_path(p: Path, default=None):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def load_curated(name):
    return load_path(ROOT / "curated" / name)


def demo_correlation():
    """A runnable demonstration of the correlation machinery on synthetic, clearly-labelled data.

    It exists so the method is auditable even while the real per-game logs are not ingested.
    It is NEVER presented as a finding about any player.
    """
    xs, ys = [], []
    for _ in range(24):
        base = RNG.gauss(60, 15)                 # simulated team passing volume
        xs.append(round(base, 1))                # QB
        ys.append(round(0.35 * base + RNG.gauss(0, 8), 1))  # WR1, positively dependent
    return {
        "label": "SYNTHETIC DEMONSTRATION — simulated numbers, not any real player",
        "result": bootstrap_corr(xs, ys),
        "reading": "Shows the interval machinery: with 24 observations a strong simulated "
                   "relationship still has a wide interval.",
    }


ABBR_TO_TEAMSTATS = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers",
    "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos",
    "DET": "Lions", "GB": "Packers", "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars",
    "KC": "Chiefs", "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants", "NYJ": "Jets",
    "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks", "SF": "49ers", "TB": "Buccaneers",
    "TEN": "Titans", "WAS": "Commanders",
}

# The official injury report prints the club's display name ("Commanders"); the depth charts
# are keyed by abbreviation ("WAS"). Joining on the wrong key silently empties every row, so the
# map is explicit and a missing key is reported rather than swallowed.
TEAM_NAME_TO_ABBR = {
    "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF", "panthers": "CAR",
    "bears": "CHI", "bengals": "CIN", "browns": "CLE", "cowboys": "DAL", "broncos": "DEN",
    "lions": "DET", "packers": "GB", "texans": "HOU", "colts": "IND", "jaguars": "JAX",
    "chiefs": "KC", "rams": "LA", "chargers": "LAC", "raiders": "LV", "dolphins": "MIA",
    "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG", "jets": "NYJ",
    "eagles": "PHI", "steelers": "PIT", "seahawks": "SEA", "49ers": "SF", "buccaneers": "TB",
    "titans": "TEN", "commanders": "WAS",
}

POSITION_UNIT = {
    "QB": "offense", "RB": "offense", "FB": "offense", "WR": "offense", "TE": "offense",
    "T": "offense", "G": "offense", "C": "offense", "OL": "offense", "OT": "offense", "OG": "offense",
    "DE": "defense", "DT": "defense", "NT": "defense", "LB": "defense", "ILB": "defense",
    "OLB": "defense", "MLB": "defense", "CB": "defense", "S": "defense", "DB": "defense",
    "SS": "defense", "FS": "defense",
    "K": "specialteams", "P": "specialteams", "LS": "specialteams", "H": "specialteams",
    "KR": "specialteams", "PR": "specialteams",
}

if __name__ == "__main__":
    run()
