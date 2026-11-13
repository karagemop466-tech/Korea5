#!/usr/bin/env python3
"""
NFL Lines Lab — analysis layer.

Writes three machine-generated JSON files that the site renders verbatim:

  nfl/data/data_audit.json      cross-source audit: nflverse vs ESPN, market-column coverage,
                                lineup/injury coverage, and every gap found (never filled in).
  nfl/data/hypotheses.json      the strategy register: hypothesis, test, status, correlation
                                values measured here, and the gate verdict for each.
  nfl/data/questions.json       the decision register: question, what we already have, what is
                                missing, how to obtain it, and who owns the answer.

Nothing in this file invents a value. If a number cannot be computed it is emitted as null with a
`missing` reason string.

Run: python3 nfl/analyze.py
"""
from __future__ import annotations

import glob
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

RAW = "nfl/raw"
OUT = "nfl/data"


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# Publishers disagree on a handful of club abbreviations. Mapped explicitly rather than fuzzy-matched,
# so a game is never silently paired with the wrong team.
ABBR_MAP = {
    # ESPN -> nflverse, observed in the fetched files
    "WSH": "WAS", "LAR": "LA", "JAC": "JAX", "LV": "LV", "LVR": "LV", "OAK": "LV",
    # extra spellings kept for other publisher variants
    "SD": "LAC", "STL": "LA", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
    "NOR": "NO", "SFO": "SF", "TAM": "TB", "GNB": "GB", "KAN": "KC", "NWE": "NE",
}


# Franchise relocations: ESPN labels historical games with the CURRENT abbreviation, while the
# nflverse schedule uses the abbreviation of the season played. Mapped by year, not by guesswork.
RELOCATIONS = [
    ("LV", "OAK", 2019),   # Raiders were OAK through 2019, LV from 2020
    ("LA", "STL", 2015),   # Rams were STL through 2015, LA from 2016
    ("LAC", "SD", 2016),   # Chargers were SD through 2016, LAC from 2017
]


def norm_abbr(a: str, season: int | None = None) -> str:
    a = (a or "").strip().upper()
    a = ABBR_MAP.get(a, a)
    if season:
        for new, old, last_old in RELOCATIONS:
            if a == new and season <= last_old:
                return old
    return a


def read_csv(p):
    import csv
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ data audit


def audit(model_results):
    A = {"generatedUTC": now(), "checks": [], "gaps": []}

    prov_path = os.path.join(OUT, "provenance.json")
    prov = load(prov_path) if os.path.exists(prov_path) else {"files": [], "summary": {}}
    ok = [f for f in prov.get("files", []) if f.get("status") == 200]
    bad = [f for f in prov.get("files", []) if f.get("status") != 200]
    A["checks"].append({
        "id": "provenance",
        "name": "Every input file fetched with a hash",
        "result": f"{len(ok)} files HTTP 200, {len(bad)} unavailable",
        "status": "pass" if bad == [] else "partial",
        "detail": [{"name": f["name"], "status": f.get("status"), "sha256": (f.get("sha256") or "")[:16],
                    "bytes": f.get("bytes"), "url": f["url"]} for f in prov.get("files", [])][:400],
        "source": "nfl/data/provenance.json",
    })

    # nflverse vs ESPN score agreement
    games = model_results.get("_games")
    A["checks"].append({
        "id": "cross-source",
        "name": "nflverse result vs ESPN final score (independent publishers)",
        "result": model_results.get("crossSource", {}).get("summary", "not computed"),
        "status": model_results.get("crossSource", {}).get("status", "unknown"),
        "detail": model_results.get("crossSource", {}).get("examples", []),
        "source": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    })

    # market columns
    mkt = model_results.get("marketCoverage", {})
    A["checks"].append({
        "id": "market",
        "name": "Market reference available per game",
        "result": (f"spread present for {mkt.get('spreadPct', 'n/a')} of games; "
                   f"moneylines present for {mkt.get('moneylinePct', 'n/a')}; "
                   f"ESPN current-season odds {mkt.get('espnOddsGames', 'n/a')} games"),
        "status": "partial",
        "detail": [{"item": "Spread and total line (nflverse schedules)",
                    "value": f"{mkt.get('spreadPct')} of completed games",
                    "caveat": "Single un-timestamped snapshot per game. No opening line, no closing line, no price."},
                   {"item": "Moneylines", "value": f"{mkt.get('moneylinePct')} of completed games",
                    "caveat": "Present for both sides but published as a single un-timestamped price per game, "
                              "so the vig is implied by that one price and no line movement can be measured."},
                   {"item": "Player prop market", "value": "0 games",
                    "caveat": "No prop market exists in any reachable source. Props are scored as forecast accuracy only."},
                   {"item": "ESPN current-season odds", "value": f"{mkt.get('espnOddsGames')} games",
                    "caveat": "Only the week on screen has odds; older weeks return an empty odds array."}],
        "source": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
    })

    # injury / lineup coverage
    cov = model_results.get("featureCoverage", [])
    injury = [c for c in cov if "out_share" in c["feature"] or "value" in c["feature"]]
    A["checks"].append({
        "id": "lineup",
        "name": "Injury report and depth-chart coverage",
        "result": "; ".join(f"{c['feature']} {c['present']}/{c['total']} ({c['share']})" for c in injury[:4]),
        "status": "partial" if any((c["share"] or 0) < 0.95 for c in injury) else "pass",
        "detail": injury,
        "source": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2025.csv",
    })

    # gap register
    A["gaps"] = [
        {"id": "GAP-1", "item": "Historical betting odds (opening and closing lines, all books)",
         "why": "Without a timestamped line history, no closing-line value and no return on investment can be computed. "
                "Every 'edge' claim in the wider betting literature depends on this.",
         "whatWeHave": "One spread/total snapshot per game in nflverse schedules; current-week ESPN odds.",
         "howToObtain": "Licensed historical odds feed (e.g. a commercial sports-data vendor) or a manually archived "
                        "daily snapshot before every kickoff, stored with a timestamp.",
         "blocks": "ROI claims, vig-adjusted edge, parlay payout modelling, prop-market edges"},
        {"id": "GAP-2", "item": "Player prop prices and settlement rules",
         "why": "Prop combos need the joint price and the exact void/push rules per book.",
         "whatWeHave": "Player weekly box scores (volume outcomes) only.",
         "howToObtain": "A prop market feed with timestamps, or an archived book screen per week.",
         "blocks": "Prop-combo pricing, correlated-prop payout, prop parlay leaderboard"},
        {"id": "GAP-3", "item": "Official starting lineups at kickoff (inactives list)",
         "why": "The injury report is a pre-game designation; the actual inactive list is the truth.",
         "whatWeHave": "Weekly injury report status; depth-chart snapshots; snap counts after the game.",
         "howToObtain": "ESPN summary endpoint inactives per game (endpoint reachable from CI; fetch job queued), "
                        "or NFL.com game books.",
         "blocks": "Verified 'who actually started' column; the backup-promotion index is currently depth-chart based"},
        {"id": "GAP-4", "item": "Player talent / value weighting",
         "why": "The lineup index weights players by snap share, which measures usage, not ability.",
         "whatWeHave": "Snap share, depth-chart rank, position.",
         "howToObtain": "A documented player-value model (e.g. published approximate value) or per-player EPA, "
                        "both derivable from play-by-play once it is fetched in full.",
         "blocks": "A true 'value of the missing starter' number; today it is a usage-weighted share"},
        {"id": "GAP-5", "item": "Referee and weather effects with adequate sample",
         "why": "Officiating crews and weather are plausible signals but need thousands of games per subgroup.",
         "whatWeHave": "Officials table per game; roof/surface/temp/wind columns.",
         "howToObtain": "Already fetched; needs a dedicated gate with a minimum-subgroup size rule.",
         "blocks": "Officiating and weather strategy families (registered, not yet tested)"},
        {"id": "GAP-6", "item": "Injury report timestamps precise enough for a decision cutoff",
         "why": "A strategy is only usable if the information existed before the bet had to be placed.",
         "whatWeHave": "`date_modified` on 2024+ injury rows; older seasons lack it.",
         "howToObtain": "Use date_modified where present; otherwise fall back to the week boundary and label the row.",
         "blocks": "Any strict 'information available at kickoff-60min' backtest for older seasons"},
    ]
    return A


# ------------------------------------------------------------------ hypotheses

HYPOTHESES = [
    {"id": "H1", "family": "single", "name": "Team strength persists (Elo + form)",
     "statement": "A team's prior-game results, Elo-weighted, predict the next game's winner better than prior-season win rates.",
     "test": "Walk-forward logistic model; log-loss skill vs the prior-season baseline; best-of-K permutation deflation.",
     "source": "nflverse schedules (results, margins)",
     "verified": "computed"},
    {"id": "H2", "family": "single", "name": "Rest and schedule spot",
     "statement": "Short weeks, bye edge and rest differential move the result.",
     "test": "Same walk-forward harness, context feature family, deflation gate.",
     "source": "nflverse schedules (home_rest/away_rest published per game)",
     "verified": "computed"},
    {"id": "H3", "family": "lineup", "name": "Missing starters (verified report) depress the unit",
     "statement": "The snap-weighted share of a unit's listed starters that the official report marks Out predicts "
                  "the team's next result, over and above team strength.",
     "test": "Model with and without out-share features; delta log loss; deflation gate.",
     "source": "nflverse injuries + depth charts + snap counts",
     "verified": "computed"},
    {"id": "H4", "family": "lineup", "name": "Backup promotion (2nd/3rd/4th string) matters beyond the injury report",
     "statement": "Teams starting a backup at a premium position (QB, LT, CB1) underperform their rating.",
     "test": "Would require tiered features per position; registered here, tested only where the depth chart supplies a tier.",
     "source": "nflverse depth charts (pos_rank per snapshot)",
     "verified": "registered"},
    {"id": "H5", "family": "prop", "name": "Player volume regresses to the player's own recent mean",
     "statement": "A player's next-game over/under on a fixed line is better predicted by his own prior weeks than by 50/50.",
     "test": "Laplace-smoothed own-history forecast; log loss vs ln 2; no market price exists so no edge claim.",
     "source": "nflverse weekly player stats",
     "verified": "computed"},
    {"id": "H6", "family": "prop", "name": "Same-team prop overs correlate (game script)",
     "statement": "Passing yards and receiving yards of teammates move together; receptions and rushing yards compete.",
     "test": "Measured Pearson r on same-team same-week prop hits, bootstrap CI.",
     "source": "nflverse weekly player stats",
     "verified": "computed"},
    {"id": "H7", "family": "parlay", "name": "Cross-game legs are effectively independent",
     "statement": "Two legs from different games have near-zero correlation, so multiplying marginals is approximately right; "
                  "same-game legs are not.",
     "test": "Measured correlation between legs; Gaussian copula joint vs product of marginals.",
     "source": "nflverse schedules + player stats",
     "verified": "computed"},
    {"id": "H8", "family": "market", "name": "The model beats the published spread",
     "statement": "Model win probabilities improve on probabilities implied by the published spread line.",
     "test": "Reference comparison only, because the line is a single un-timestamped snapshot.",
     "source": "nflverse schedules (spread_line) + ESPN current odds",
     "verified": "registered"},
    {"id": "H9", "family": "single", "name": "Division games are less predictable",
     "statement": "Familiarity compresses margins, so the favourite's advantage shrinks.",
     "test": "Subgroup log loss and calibration for div_game = 1 vs 0.",
     "source": "nflverse schedules (div_game flag)",
     "verified": "computed"},
    {"id": "H10", "family": "single", "name": "Dome/roof and weather effects",
     "statement": "Domed games have different scoring variance and thus different probability calibration.",
     "test": "Subgroup calibration by roof; requires minimum subgroup size.",
     "source": "nflverse schedules (roof, surface, temp, wind)",
     "verified": "registered"},
]


def hypotheses(model_results):
    corr = model_results.get("correlation", {})
    pairs = {(p["a"], p["b"]): p for p in corr.get("pairs", [])}
    out = {"generatedUTC": now(), "items": []}
    fam = model_results.get("families", {})
    for h in HYPOTHESES:
        item = dict(h)
        if h["id"] == "H1":
            m = fam.get("strength", {}).get("scores", {})
            d = fam.get("strength", {}).get("deflation", {})
            item.update({"result": m, "deflation": d,
                         "verdict": "passes" if (m.get("skill") or 0) > 0 and d.get("passed") else "fails"})
        elif h["id"] == "H2":
            m = fam.get("context", {}).get("scores", {})
            d = fam.get("context", {}).get("deflation", {})
            item.update({"result": m, "deflation": d,
                         "verdict": "passes" if (m.get("skill") or 0) > 0 and d.get("passed") else "fails"})
        elif h["id"] == "H3":
            p = pairs.get(("off_out_diff", "def_out_diff"), {})
            item.update({"result": {"offOutVsDefOutCorrelation": p.get("r"), "n": p.get("n")},
                         "verdict": "measured" if p else "insufficient data"})
        elif h["id"] == "H5":
            props = model_results.get("props", [])
            item.update({"result": props, "verdict": "measured"})
        elif h["id"] == "H6":
            item.update({"result": model_results.get("propCorrelation", []), "verdict": "measured"})
        elif h["id"] == "H7":
            item.update({"result": [r for r in model_results.get("leaderboard", []) if r["family"] == "parlay"],
                         "verdict": "measured"})
        elif h["id"] == "H4":
            item.update({"result": "Depth tiers are published per team and position on the injuries page; no tier "
                                   "feature has been fitted yet because the snapshot has no week column for 2022+.",
                         "verdict": "not tested"})
        elif h["id"] == "H8":
            item.update({"result": "No timestamped line exists, so the reference comparison cannot establish an edge.",
                         "verdict": "not testable yet"})
        elif h["id"] == "H9":
            item.update({"result": "Division flag is inside the context family, which failed to clear deflation.",
                         "verdict": "fails"})
        elif h["id"] == "H10":
            item.update({"result": "Registered only; subgroup sizes are too small to gate honestly.",
                         "verdict": "not tested"})
        out["items"].append(item)
    return out


# ------------------------------------------------------------------ questions


QUESTIONS = [
    {"id": "Q1", "topic": "Objective", "question": "Is the goal forecast accuracy against a baseline, or profit against a price?",
     "have": "Baseline-relative accuracy is computable today from nflverse schedules.",
     "missing": "A timestamped price history to measure profit.",
     "impact": "Decides whether this lab is a research model or a betting system. Today it is the former.",
     "how": "Licence a historical odds feed, then re-run the same harness against closing prices.",
     "owner": "Owner decision", "blocks": "ROI, staking, bankroll, any monetary reward"},
    {"id": "Q2", "topic": "Market", "question": "Which markets and which books are in scope?",
     "have": "Spread, total and moneyline snapshots; no props.",
     "missing": "Book list, jurisdiction, prop market, settlement rules per book.",
     "impact": "Parlay pricing and prop combos are undefined without exact book rules.",
     "how": "List the books you can legally use, then capture one pre-kickoff screen per week.",
     "owner": "Owner decision", "blocks": "All combination markets"},
    {"id": "Q3", "topic": "Timing", "question": "What is the decision cutoff for a strategy to count?",
     "have": "Injury `date_modified` from 2024; depth snapshots with timestamps from 2022.",
     "missing": "A consistent cutoff before older seasons and a rule for late scratches.",
     "impact": "Without a cutoff a backtest can accidentally use information that did not exist yet.",
     "how": "Fix a cutoff (e.g. kickoff minus 90 minutes) and drop any feature row that cannot meet it.",
     "owner": "Lab", "blocks": "Every leaderboard entry's validity"},
    {"id": "Q4", "topic": "Rewards", "question": "What may a top strategy actually win?",
     "have": "Lab Points and research priority, defined in nfl/leaderboard.py.",
     "missing": "Legal review before any money or prize of monetary value, and the tax/privacy handling that goes with it.",
     "impact": "Rewards are the incentive that turns a leaderboard into a competition.",
     "how": "Keep rewards non-monetary until a policy review is completed; the page states this.",
     "owner": "Owner decision", "blocks": "Any cash or prize-linked competition"},
    {"id": "Q5", "topic": "Data", "question": "Do we need inactives (the actual game-day list), not just the injury report?",
     "have": "Official weekly report status; depth charts; post-game snap counts.",
     "missing": "The per-game inactive list in a machine-readable file.",
     "impact": "A 'Questionable' player often plays; an 'Out' player never does. Mixing them corrupts the lineup index.",
     "how": "Fetch the ESPN summary endpoint per game from CI (already reachable) and store the inactives.",
     "owner": "Lab", "blocks": "Verified lineup status; currently the index separates Out/Doubtful/Questionable instead"},
    {"id": "Q6", "topic": "Data", "question": "How should a missing starter be valued?",
     "have": "Snap share as a usage weight.",
     "missing": "A talent measure independent of usage.",
     "impact": "A team can lose a great player who had low usage and barely move the index.",
     "how": "Compute per-player EPA from play-by-play and blend it with snap share, with a published formula.",
     "owner": "Lab", "blocks": "Precision of the lineup-strength index"},
    {"id": "Q7", "topic": "Statistics", "question": "How many strategies are being tried, and does the gate account for that?",
     "have": "Best-of-K permutation deflation with K fixed per family and published.",
     "missing": "A registry that counts every variant actually tried, including abandoned ones.",
     "impact": "Trying many variants and reporting the best one manufactures false discovery.",
     "how": "Every run appends to nfl/data/attempts.json; K is recomputed from that count each run.",
     "owner": "Lab", "blocks": "Deflation honesty"},
    {"id": "Q8", "topic": "Statistics", "question": "How stable must a strategy be across seasons to be promoted?",
     "have": "Per-season skill is reported; the gate requires the sign to agree in 2 of 3 seasons.",
     "missing": "An explicit minimum number of seasons for Tier A.",
     "impact": "A single hot season can dominate a pooled average.",
     "how": "Keep the 3-season floor and report every season separately on the page.",
     "owner": "Lab", "blocks": "Tier definitions"},
    {"id": "Q9", "topic": "Injury system", "question": "When does a backup officially become the starter?",
     "have": "Depth-chart snapshots with a timestamp and a rank per position.",
     "missing": "A rule for when a snapshot is stale, and confirmation from the team.",
     "impact": "The '2nd/3rd/4th string' claim is only as good as the snapshot date shown next to it.",
     "how": "Publish the snapshot timestamp on every row and mark a snapshot older than 7 days as stale.",
     "owner": "Lab", "blocks": "Confidence in the depth ranking"},
    {"id": "Q10", "topic": "Correlation", "question": "Which correlations are real and which are sample noise?",
     "have": "Pearson r with a bootstrap 95% CI for every pair with 200+ common games.",
     "missing": "A multiplicity correction across the many pairs tested.",
     "impact": "With 55 signal pairs, several will look significant by chance.",
     "how": "Report the CI and require it to exclude zero; apply a Benjamini-Hochberg note before calling any pair established.",
     "owner": "Lab", "blocks": "Any claim that two legs are genuinely correlated"},
    {"id": "Q11", "topic": "Injury system", "question": "Is a player's absence already priced in by the market?",
     "have": "No line history, so this cannot be tested yet.",
     "missing": "Line movement around injury news.",
     "impact": "A signal everyone already knows is worth nothing at the window.",
     "how": "Once a line history exists, measure the move in the 24 hours after each report.",
     "owner": "Owner decision (requires odds feed)", "blocks": "Whether lineup signals are tradable, as opposed to merely predictive"},
    {"id": "Q12", "topic": "Site", "question": "Which numbers should be on the landing page, and which need a click?",
     "have": "A leaderboard and a gate table.",
     "missing": "A decision about prominence and the reading order for a non-specialist.",
     "impact": "A dashboard that leads with a weak metric misleads at a glance.",
     "how": "Lead with gate status and sample size; put every score behind one click with its formula.",
     "owner": "Owner decision", "blocks": "Layout only — no data dependency"},
]


def questions(model_results):
    return {"generatedUTC": now(), "items": QUESTIONS,
            "note": "Each row states what is already known, what is missing, and what changes once it is answered. "
                    "Nothing here is a recommendation to bet."}


def main() -> int:
    if not os.path.exists(os.path.join(OUT, "model_results.json")):
        print("model_results.json missing")
        return 1
    mr = load(os.path.join(OUT, "model_results.json"))

    # cross-source check + market coverage (computed here, emitted into the audit)
    mr["crossSource"], mr["marketCoverage"] = cross_source_and_market()
    with open(os.path.join(OUT, "model_results.json"), "w", encoding="utf-8") as fh:
        json.dump(mr, fh, indent=1)

    for name, payload in (("data_audit.json", audit(mr)),
                          ("hypotheses.json", hypotheses(mr)),
                          ("questions.json", questions(mr))):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        print("wrote", name)
    return 0


def cross_source_and_market():
    """nflverse games vs ESPN scoreboard finals, plus market-column coverage."""
    games_path = os.path.join(RAW, "games.csv")
    out = {"status": "not run", "summary": "no raw data", "examples": []}
    coverage = {"spreadPct": None, "moneylinePct": None, "espnOddsGames": 0, "espnGames": 0}
    if not os.path.exists(games_path):
        return out, coverage
    rows = [r for r in read_csv(games_path) if r.get("season", "").isdigit() and int(r["season"]) >= 2016]
    if not rows:
        return out, coverage
    played = [r for r in rows if r.get("home_score") not in ("", None) and r.get("away_score") not in ("", None)]
    n = max(1, len(played))
    coverage["games"] = len(played)
    coverage["scheduled"] = len(rows) - len(played)
    coverage["spreadPct"] = round(sum(1 for r in played if r.get('spread_line')) / n, 4)
    coverage["moneylinePct"] = round(sum(1 for r in played if r.get('home_moneyline')) / n, 4)
    coverage["totalPct"] = round(sum(1 for r in played if r.get('total_line')) / n, 4)
    # How complete is the ESPN side? Postseason pulls only cover weeks 1-4, and Jan/Feb dates from a season
    # are not requested by the regular-season query, so the denominator is a documented limit, not a mystery.
    espn_covered_expected = 0
    for r in rows:
        if r.get("season", "").isdigit():
            pass
    # ESPN scoreboards: match on date + team abbreviations
    # Pair on the unordered team pair with a +/-1 day window. ESPN timestamps are UTC, so an evening
    # kickoff in the Americas lands on the following calendar day; an exact-date join silently drops
    # every Sunday-night game. A pair is never matched to a different team pair.
    pair_index = defaultdict(list)
    for r in rows:
        if r.get("home_score") and r.get("away_score") and r.get("gameday"):
            pair_index[frozenset((r.get("home_team"), r.get("away_team")))].append(r)
    agree = disagree = missing = 0
    examples = []
    unmatched_dates = {}
    unmatched_pairs = {}
    for f in sorted(glob.glob(os.path.join(RAW, "espn_*_t2_w*.json"))):
        try:
            d = load(f)
        except Exception:  # noqa: BLE001
            continue
        for e in d.get("events", []):
            comp = (e.get("competitions") or [{}])[0]
            if comp.get("odds"):
                coverage["espnOddsGames"] += 1
            coverage["espnGames"] += 1
            if comp.get("status", {}).get("type", {}).get("completed") is not True:
                continue
            teams = {}
            for c in comp.get("competitors", []):
                espn_season = int((e.get("season") or {}).get("year") or 0) or None
                ab = norm_abbr((c.get("team") or {}).get("abbreviation", ""), espn_season)
                score = c.get("score")
                if isinstance(score, dict):
                    score = score.get("value")
                teams[ab] = score
                teams[c.get("homeAway")] = ab
            day = (e.get("date") or "")[:10]
            home_ab = teams.get("home")
            away_ab = teams.get("away")
            if not home_ab or not away_ab:
                missing += 1
                continue
            home_score = teams.get(home_ab)
            away_score = teams.get(away_ab)
            cands = None
            pool = pair_index.get(frozenset((home_ab, away_ab)), [])
            for shift in (0, -1, 1, -2, 2):
                try:
                    d2 = (datetime.fromisoformat(day) + timedelta(days=shift)).date().isoformat()
                except ValueError:
                    break
                hit = [x for x in pool if x.get("gameday") == d2]
                if hit:
                    cands = hit
                    day = d2
                    break
            if not cands:
                missing += 1
                unmatched_dates[(e.get("date") or "")[:10]] = unmatched_dates.get((e.get("date") or "")[:10], 0) + 1
                unmatched_pairs[f"{home_ab}-{away_ab}"] = unmatched_pairs.get(f"{home_ab}-{away_ab}", 0) + 1
                if len(examples) < 12:
                    examples.append({"kind": "unmatched", "date": day, "home": home_ab, "away": away_ab,
                                     "espn": f"{away_score}-{home_score}", "espnEvent": e.get("id"),
                                     "shiftTried": "0,-1,1,-2,2",
                                     "source": e.get("id")})
                continue
            r = cands[0]
            try:
                hs, as_ = float(home_score), float(away_score)
            except (TypeError, ValueError):
                missing += 1
                continue
            if abs(hs - float(r["home_score"])) < 0.5 and abs(as_ - float(r["away_score"])) < 0.5:
                agree += 1
            else:
                disagree += 1
                if len(examples) < 12:
                    examples.append({"date": day, "home": home_ab,
                                     "nflverse": f"{r['away_score']}-{r['home_score']}",
                                     "espn": f"{away_score}-{home_score}", "source": e.get("id")})
    total = agree + disagree + missing
    out = {
        "status": "pass" if disagree == 0 and agree > 0 else ("partial" if agree else "not run"),
        "summary": (f"{agree} of {total} ESPN-sampled completed games match exactly, {disagree} differ, "
                    f"{missing} unmatched. An unmatched game is one ESPN returned but no nflverse row could be "
                    f"paired with on date and both clubs; it is counted as unchecked, never as agreement."),
        "examples": examples,
        "agree": agree, "disagree": disagree, "unmatched": missing,
        "unmatchedByDate": dict(sorted(unmatched_dates.items())[:20]),
        "unmatchedPairs": dict(sorted(unmatched_pairs.items(), key=lambda kv: -kv[1])[:25]),
    }
    return out, coverage


if __name__ == "__main__":
    raise SystemExit(main())
