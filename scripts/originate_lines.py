#!/usr/bin/env python3
"""Originate our own NFL lines + build the lineup-deficiency report.

Inputs  (all produced by scripts/parse_nfl_analytics.py from official snapshots):
  data/nfl-analytics/results-2026.json           official finals (NFL.com by-week pages)
  data/nfl-analytics/standings-2026.json         official W-L-T / PF / PA (NFL.com standings)
  data/nfl-analytics/injuries-week-10-2026.json  official Week 10 injury report (NFL.com)
  data/nfl-analytics/depth-charts-2026.json      club-published depth charts
  data/nfl-analytics/market-odds-week-10-2026.json  DraftKings market reference via ESPN (labelled)

Outputs:
  data/nfl-analytics/model-lines-week-10-2026.json   our own lines (+ market comparison)
  data/nfl-analytics/lineup-report-week-10-2026.json deficiency report (2nd/3rd/4th string replacements)

Method (documented on lines.html — every parameter there is a MODEL PARAMETER, not a fact):
  * Team ratings r_i are least-squares fit to game margins (weeks 1-9 only):
        margin_g ~= r_home - r_away + HFA
    solved by deterministic alternating gradient descent, ratings centred at 0.
    HFA is estimated from the same data (mean residual), rounded to 0.1.
  * Expected points use the classic scoring/allowing average:
        E[home] = (PF_h/G_h + PA_a/G_a)/2,  E[away] = (PF_a/G_a + PA_h/G_h)/2
    (through week 9 only).
  * Injury adjustment: documented per-position weights x designation factor,
    applied to the SPREAD ONLY. Totals are deliberately NOT injury-adjusted in v0
    (known limitation, listed in the flagged register).
  * Week 10 games are excluded from the fit. WAS @ NYG (already final) is therefore
    an out-of-sample validation point computed from pre-kickoff inputs.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "nfl-analytics"

TEAM_NAMES = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
    "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN",
    "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "Chargers": "LAC", "Rams": "LAR", "Raiders": "LV", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT", "Seahawks": "SEA", "49ers": "SF", "Buccaneers": "TB",
    "Titans": "TEN", "Commanders": "WAS",
}

# ---- MODEL PARAMETERS (published on lines.html; candidates for validation gate G3) ----
POS_WEIGHT = {  # points lost when a 1st-string player at this position is unavailable
    "QB": 4.0, "RB": 0.8, "FB": 0.3, "WR": 0.7, "TE": 0.5,
    "T": 0.6, "G": 0.5, "C": 0.6,
    "DE": 0.5, "DT": 0.5, "EDGE": 0.6, "LB": 0.6, "CB": 0.7, "S": 0.5,
    "K": 0.3, "P": 0.1, "LS": 0.05,
}
DESIG_FACTOR = {"Out": 1.0, "Doubtful": 0.75, "Questionable": 0.5}
WATCH_FACTOR = 0.25  # DNP practice, no game designation yet (starter only)
STRING_FACTOR = {1: 1.0, 2: 1.25, 3: 1.5, 4: 1.6, 5: 1.6}  # deeper starter loss = larger gap


def load(name):
    return json.loads((D / name).read_text())


def abbr(display_name: str) -> str:
    if display_name in TEAM_NAMES:
        return TEAM_NAMES[display_name]
    for nick, a in TEAM_NAMES.items():
        if nick in display_name:
            return a
    raise KeyError(display_name)


def main() -> None:
    generated = datetime.now(timezone.utc).isoformat()
    results = load("results-2026.json")["results"]
    standings_rows = load("standings-2026.json")["rows"]
    injuries = load("injuries-week-10-2026.json")
    depth_rows = load("depth-charts-2026.json")["rows"]
    market = load("market-odds-week-10-2026.json")["entries"]

    # ---------------- ratings from weeks 1-9 (week 10 held out) ----------------
    games = []
    for r in results:
        if r["week"] >= 10:
            continue
        a, h = abbr(r["away"]), abbr(r["home"])
        games.append((a, h, r["homeScore"] - r["awayScore"]))
    teams = sorted({t for g in games for t in g[:2]})
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}
    r = [0.0] * n
    hfa = 2.5
    lr = 0.02
    for _ in range(4000):
        grad = [0.0] * n
        for a, h, margin in games:
            err = margin - (r[idx[h]] - r[idx[a]] + hfa)
            grad[idx[h]] += err
            grad[idx[a]] -= err
        for i in range(n):
            r[i] += lr * grad[i] / max(1, sum(1 for g in games if teams[i] in g[:2]))
        mean_r = sum(r) / n
        r = [x - mean_r for x in r]
        resid = [m - (r[idx[h]] - r[idx[a]]) for a, h, m in games]
        hfa = sum(resid) / len(resid)
    ratings = {t: round(x, 2) for t, x in zip(teams, r)}
    hfa = round(hfa, 1)

    # ---------------- scoring rates through week 9 ----------------
    # standings cells: [name, W, L, T, PCT, PF, PA, DIFF, ...]
    pf, pa, gp = {}, {}, {}
    for row in standings_rows:
        c = row["cells"]
        t = row["team"]
        gp[t] = int(c[1]) + int(c[2]) + int(c[3])
        pf[t] = int(c[5])
        pa[t] = int(c[6])

    # ---------------- depth chart index ----------------
    depth_idx = {}
    for row in depth_rows:
        for s in range(1, 6):
            name = row.get(f"s{s}", "")
            if name:
                depth_idx[(row["team"], name)] = (row["pos"], row["unit"], s, row.get("sourceUrl", ""))

    teams_with_depth = {row["team"] for row in depth_rows if row.get("s1")}
    # HOU publishes its chart as an image; CAR's site refused connections in CI and 500s on fetch.
    depth_unavailable = sorted(t for t in {g["away"] for g in injuries["games"]} | {g["home"] for g in injuries["games"]} if t not in teams_with_depth)

    # ---------------- lineup deficiency report ----------------
    lineup_rows = []
    team_adj = {t: 0.0 for t in set(ratings) | set(pf)}
    for row in injuries["rows"]:
        player = row["player"]
        desig = row["gameStatus"]
        watch = (not desig) and row["practiceStatus"].startswith("Did Not")
        if not (desig or watch):
            continue
        team = row["team"]
        hit = depth_idx.get((team, player))
        if hit:
            pos, unit, string, src = hit
            nxt = ""
            for dr in depth_rows:
                if dr["team"] == team and dr["pos"] == pos and dr["unit"] == unit:
                    nxt = dr.get(f"s{min(string + 1, 5)}", "")
                    break
        else:
            pos, unit, string, nxt, src = row["pos"], "", 0, "", ""
        w = POS_WEIGHT.get(pos, 0.4) * (1.0 if string == 1 else 0.5 if string == 2 else 0.25)
        if string in (1, 2):
            factor = DESIG_FACTOR.get(desig, WATCH_FACTOR if watch else 0.0)
            team_adj[team] = team_adj.get(team, 0.0) + w * factor
        deficiency = ""
        if desig == "Out" and string == 1 and nxt:
            deficiency = f"starter out — {nxt} (2nd string) steps in"
        elif desig == "Out" and string == 1:
            deficiency = "starter out — replacement string unverified"
        elif desig == "Out" and string:
            deficiency = f"{string}nd/rd/th string out"
        elif desig == "Questionable":
            deficiency = "starter questionable — 2nd string on standby"
        elif watch and string == 1:
            deficiency = "starter missed practice (DNP) — watch"
        lineup_rows.append({
            "game": row["game"], "team": team, "side": ("away" if row["team"] == row["game"].split(" @ ")[0] else "home"),
            "player": player, "pos": pos, "injury": row["injury"],
            "practiceStatus": row["practiceStatus"], "gameStatus": desig or "(not yet designated)",
            "depthString": (f"{string}st/nd/rd/th" if string else "not on published depth chart"),
            "replacement": nxt or ("unverified — depth chart unavailable" if team in depth_unavailable else "unverified — not on published depth chart"),
            "unit": unit or "unverified",
            "deficiency": deficiency or "tracked — no line impact",
            "lineImpactPts": round(POS_WEIGHT.get(pos, 0.4) * DESIG_FACTOR.get(desig, WATCH_FACTOR if watch else 0.0) * (1.0 if string == 1 else 0.5 if string == 2 else 0.25) if string in (1, 2) else 0.0, 2),
            "sourceUrl": row["sourceUrl"], "depthSourceUrl": src,
        })

    (D / "lineup-report-week-10-2026.json").write_text(json.dumps({
        "meta": {"generatedUTC": generated, "week": 10, "season": 2026,
                 "sources": {"injuries": "https://www.nfl.com/injuries/", "depthCharts": "club official sites per row"},
                 "depthChartUnavailable": depth_unavailable,
                 "rules": "gameStatus Out/Doubtful/Questionable rows plus starter DNP rows are tracked. Line impact uses published model parameters (POS_WEIGHT, DESIG_FACTOR) — model outputs, not official values."},
        "rows": lineup_rows}, indent=1) + "\n")

    # ---------------- market index ----------------
    mkt = {}
    for e in market:
        if not e["odds"]:
            continue
        o = e["odds"][0]
        names = e["name"].split(" at ")
        try:
            a, h = abbr(names[0]), abbr(names[1])
        except KeyError:
            continue
        spread_home = None
        dm = re.match(r"^([A-Z]{2,3})\s+([+-]?\d+(?:\.\d+)?)$", str(o.get("details", "")))
        if dm:
            fav, pts = dm.group(1), float(dm.group(2))
            spread_home = pts if fav == h else -pts
        mkt[f"{a} @ {h}"] = {
            "spreadHome": spread_home,
            "total": o.get("overUnder"), "details": o.get("details", ""),
            "provider": o.get("provider", {}).get("name", ""),
            "sourceUrl": e["sourceUrl"],
        }

    # ---------------- model lines for week 10 ----------------
    lines = []
    for g in injuries["games"]:
        key = f"{g['away']} @ {g['home']}"
        a, h = g["away"], g["home"]
        spread_home = (ratings.get(h, 0.0) - ratings.get(a, 0.0)) + hfa - team_adj.get(h, 0.0) + team_adj.get(a, 0.0)
        e_h = ((pf.get(h, 0) / max(gp.get(h, 1), 1)) + (pa.get(a, 0) / max(gp.get(a, 1), 1))) / 2
        e_a = ((pf.get(a, 0) / max(gp.get(a, 1), 1)) + (pa.get(h, 0) / max(gp.get(h, 1), 1))) / 2
        total = e_h + e_a
        m = mkt.get(key, {})
        pred_margin_home = spread_home
        model_spread_home = -pred_margin_home  # odds convention: positive = home receives points
        entry = {
            "game": key, "kickoffET": g["kickoffET"], "day": g["day"], "network": g["network"],
            "awayRecord": g["awayRecord"], "homeRecord": g["homeRecord"],
            "modelSpreadHome": round(model_spread_home, 1), "modelTotal": round(total, 1),
            "ratingAway": ratings.get(a), "ratingHome": ratings.get(h),
            "injuryAdjAwayPts": round(team_adj.get(a, 0.0), 2), "injuryAdjHomePts": round(team_adj.get(h, 0.0), 2),
            "marketSpreadHome": m.get("spreadHome"), "marketTotal": m.get("total"),
            "marketDetails": m.get("details", ""), "marketProvider": m.get("provider", ""),
            "edgeSpreadPts": (round(model_spread_home - m.get("spreadHome"), 1) if m.get("spreadHome") is not None else None),
            "edgeTotalPts": (round(total - m.get("total"), 1) if m.get("total") is not None else None),
            "sourceUrl": "https://www.nfl.com/injuries/", "marketSourceUrl": m.get("sourceUrl", ""),
            "label": "MODEL OUTPUT — derived from official inputs; not an official value",
        }
        lines.append(entry)

    # validation point: WAS @ NYG final (week 10 TNF)
    tnf = next((r for r in results if r["week"] == 10), None)
    validation = {}
    if tnf:
        line = next((l for l in lines if l["game"] == "WAS @ NYG"), None)
        if line:
            margin_home = tnf["homeScore"] - tnf["awayScore"]  # NYG - WAS
            model_home_margin = -line["modelSpreadHome"]  # convert spread back to predicted margin
            validation = {
                "game": "WAS @ NYG", "final": f"{tnf['away']} {tnf['awayScore']} - {tnf['home']} {tnf['homeScore']}",
                "actualHomeMargin": margin_home, "modelHomeMargin": round(model_home_margin, 1),
                "modelSpreadHome": line["modelSpreadHome"],
                "absErrorPts": round(abs(margin_home - model_home_margin), 1),
                "note": "out-of-sample: ratings fit weeks 1-9 only; pre-kickoff official injury inputs; computed post-game (labelled retrospective)",
                "sourceUrl": tnf["sourceUrl"],
            }

    (D / "model-lines-week-10-2026.json").write_text(json.dumps({
        "meta": {
            "generatedUTC": generated, "week": 10, "season": 2026,
            "label": "MODEL OUTPUT — our own originated lines. Market columns are a labelled trusted-secondary reference (DraftKings via ESPN), not official league data.",
            "fitData": f"{len(games)} official finals, weeks 1-9 (week 10 held out)",
            "hfa": hfa, "ratings": ratings,
            "parameters": {"POS_WEIGHT": POS_WEIGHT, "DESIG_FACTOR": DESIG_FACTOR,
                           "WATCH_FACTOR": WATCH_FACTOR, "STRING_MULT": {"1": 1.0, "2": 0.5, "3+": 0.25},
                           "note": "model parameters — candidates for validation gate G3, not claimed facts"},
            "limitations": ["totals are not injury-adjusted in v0", "no EPA/play efficiency input (not officially published)",
                            "HOU depth chart published as image; CAR depth site unreachable — replacement strings unverified"],
        },
        "lines": lines, "validation": validation}, indent=1) + "\n")

    print(f"fit games={len(games)} teams={n} HFA={hfa}")
    print("top ratings:", sorted(ratings.items(), key=lambda kv: -kv[1])[:5])
    print("lineup rows:", len(lineup_rows), "| depth unavailable:", depth_unavailable)
    for l in lines:
        print(f"  {l['game']:12s} model {l['modelSpreadHome']:+.1f} / {l['modelTotal']:.1f}   market {l['marketDetails'] or '-':8s} {l['marketTotal'] or '-'}   edge {l['edgeSpreadPts']}")
    print("validation:", validation)


if __name__ == "__main__":
    main()
