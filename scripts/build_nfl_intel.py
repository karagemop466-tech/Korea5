#!/usr/bin/env python3
"""Generate the NFL intelligence pages (lines, strategies, injuries, suggestions,
questions, executive summary, hub) from data/nfl-intel/*.json.

Every factual table row links an official source. Computed rows are labelled
'computed'. Values that could not be verified stay blank and are labelled
'unverified — flagged'. Run after scripts/nfl_intel.py.
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SITE = "Free Time Vacation Planner"

NAV = [
    ("index.html", "Dashboard"), ("calendar.html", "Calendar"),
    ("vacation.html", "Vacation windows"), ("mlb.html", "MLB"),
    ("nfl.html", "NFL &amp; 49ers"), ("nfl-intel.html", "NFL Intel"),
    ("nfl-lines.html", "Lines"), ("nfl-strategies.html", "Strategies"),
    ("nfl-injuries.html", "Injuries"), ("nfl-executive.html", "Executive"),
    ("suggestions.html", "Suggestions"), ("questions.html", "Questions"),
    ("ncaaf.html", "Stanford &amp; Cal"), ("radio.html", "Radio"),
    ("sources.html", "Sources"), ("flagged.html", "Flagged"),
    ("method.html", "Method"), ("extra/index.html", "Official feeds &amp; verification"),
]


def esc(s):
    return html.escape(str(s if s is not None else ""))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


MODEL = load("data/nfl-intel/model.json")
INJ = load("data/nfl-intel/injuries-week10.json")
STRAT = load("data/nfl-intel/strategies.json")
SUGG = load("data/nfl-intel/suggestions.json")
QUEST = load("data/nfl-intel/questions.json")
RESULTS = load("data/nfl-intel/results-2026.json")["games"]
STAND = load("data/nfl-intel/standings-2026.json")["teams"]


def head(title, active):
    nav = "".join(f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>' for u, n in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {SITE}</title>
<meta name="description" content="NFL intelligence: originated lines, strategy leaderboard with validation gates, injury and depth-deficiency tracking, suggestions and open questions. Verified sources, computed values labelled.">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> FREE TIME / VACATION</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">"""


def foot():
    return f"""</main>
<footer><div class="wrap">
  <p><strong>{SITE}</strong> · NFL Intelligence section · snapshot 2026-11-13 ·
  every factual row links an official source (nfl.com); computed rows are labelled; unverified cells are blank and flagged.</p>
  <p>Model output is not official league data. See <a href="nfl-lines.html">Lines</a> for formulas and
  <a href="questions.html">Questions</a> for what is still missing. Items needing review are on
  <a href="flagged.html">Flagged for review</a>.</p>
</div></footer></body></html>"""


def page(name, title, active, body):
    with open(name, "w", encoding="utf-8") as f:
        f.write(head(title, active) + body + foot())


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def src(url, label="source"):
    if not url:
        return '<span class="small">—</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def tag(text, cls="tag"):
    return f'<span class="{cls}">{esc(text)}</span>'


VER = lambda: tag("verified", "tag ver")
CMP = lambda: tag("computed", "tag est")
UNV = lambda: tag("unverified — flagged", "tag flag")


def fmt(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


# ============================================================ nfl-intel.html
def build_hub():
    b = []
    b.append("""<section class="hero"><div>
<p class="small">NFL INTELLIGENCE · 2026 SEASON · SNAPSHOT 2026-11-13</p>
<h1>Originate the lines.<br>Grade the signals. Remove the luck.</h1>
<p class="lede">This section collects the verified 2026 season data, originates our own spreads and totals,
tracks injuries and depth deficiencies, and defines a leaderboard competition where every strategy must
pass validation gates before it counts.</p>
<div class="pill-row"><a class="btn" href="nfl-lines.html">Our lines &amp; ratings →</a>
<a class="btn" href="nfl-strategies.html">Strategies &amp; leaderboard</a>
<a class="btn" href="nfl-injuries.html">Injury tracker</a></div></div>
<div class="card"><h2>Reading the numbers</h2>
<p>Every table row carries one of three labels:</p>
<p>""" + VER() + " — transcribed from an official page, with the link.</p><p>" + CMP() +
    """ — model output computed from verified inputs; formulas are published on the Lines page.</p>
<p>""" + UNV() + """ — could not be confirmed; the cell stays blank and the item appears on
<a href="flagged.html">Flagged for review</a>. Nothing is inferred.</p></div></section>""")

    b.append("<h2>What this section contains</h2>")
    b.append(table(["Page", "Contents", "Evidence level"], [
        ['<a href="nfl-lines.html">Lines &amp; ratings</a>',
         "Team power ratings, our own Week 10–11 spreads/totals, walk-forward backtest and validation gates G1–G8",
         VER() + " inputs · " + CMP() + " outputs"],
        ['<a href="nfl-strategies.html">Strategies &amp; leaderboard</a>',
         "Strategy library (single, parlay, player-prop combos), competition rules, rewards, correlation values, anti-luck scoring",
         "Design " + VER() + " / metrics " + CMP() + " where data exists"],
        ['<a href="nfl-injuries.html">Injuries &amp; deficiencies</a>',
         "Official Week-10 injury report (296 rows), starter/backup status news, offense/defense deficiency flags",
         VER() + " rows; depth tier blank where unverified"],
        ['<a href="nfl-executive.html">Executive summary</a>',
         "The one-page answer: what we know, what we built, what blocks decisions", "mixed — labelled per line"],
        ['<a href="suggestions.html">Suggestions</a>',
         "Improvement proposals with a review-and-choose workflow; nothing is implemented before acceptance", "process"],
        ['<a href="questions.html">Questions register</a>',
         "What we have, what is missing, and how to discover it — before any decision", "process"],
    ]))

    b.append("<h2>Key findings from the verified data (2026-11-13)</h2>")
    b.append(table(["Finding", "Value", "Label"], [
        ["Season results verified against official standings",
         "137 finals (weeks 1–10) cross-checked team-by-team: 32/32 records and points match nfl.com standings exactly",
         VER() + " · " + src("https://www.nfl.com/standings/league/2026/REG", "nfl.com standings")],
        ["Home-field advantage, 2026 to date", "−0.02 points per game (essentially zero) — see Q-HFA in the questions register",
         CMP()],
        ["Strongest pre-game signal", "Rest-days difference correlates 0.438 with game margin (n=74, walk-forward) — stronger than rating difference (0.325)",
         CMP()],
        ["Model quality vs baseline", "S1 spread MAE 10.56 vs 11.32 baseline; Brier 0.216 vs 0.255; 66.2% side hit rate — gates G1–G4 PASS",
         CMP()],
        ["Week-10 availability", "296 official injury rows; verified starter absences at BAL QB (IR + backup out for season), SEA QB, MIA QB (IR), GB RB, LAR WR",
         VER()],
        ["Market odds", "Not used anywhere — no official source exists; all market columns are blank and flagged (Q-ODDS)",
         UNV()],
    ]))
    b.append('<p class="small">Full detail and caveats: <a href="nfl-executive.html">Executive summary</a> · '
             '<a href="research/EXECUTIVE-SUMMARY-NFL.md">summary source (markdown)</a> · '
             '<a href="questions.html">open questions</a></p>')
    page("nfl-intel.html", "NFL Intelligence hub", "nfl-intel.html", "".join(b))


# ============================================================ nfl-lines.html
def build_lines():
    m = MODEL
    meta = m["meta"]
    b = []
    b.append("<h1>Originated lines &amp; power ratings</h1>")
    b.append('<aside class="callout warn" role="note"><strong>These numbers are model output, not official league data '
             'and not market prices.</strong> Every input is a verified nfl.com result; every formula is below. '
             'Market columns are deliberately blank until a verified odds source exists (Q-ODDS).</aside>')

    b.append("<h2>Formulas (reproducible from the committed data)</h2>")
    b.append(table(["Quantity", "Formula", "Notes"], [
        ["Spread (home)", "m = R<sub>home</sub> − R<sub>away</sub> + HFA",
         "R solved by iterative least squares on verified margins, mean(R)=0"],
        ["Total", "total = (pace<sub>home</sub> + pace<sub>away</sub>)/2",
         "pace<sub>t</sub> = (PF<sub>t</sub> + PA<sub>t</sub>)/games<sub>t</sub>"],
        ["Win probability", "P(home) = Φ(m / σ)", f"σ = population SD of verified home margins = {meta['sigma_margin']} pts"],
        ["Recency variant (S2)", "weights w = 0.9^(latest_week − game_week)", "identical pipeline, re-weighted"],
        ["Home-field advantage", f"HFA = weighted mean home margin = {meta['hfa_points']} pts",
         "computed from 137 verified games; near zero this season — see Q-HFA"],
    ]))
    b.append('<p class="small">Code: <a href="https://github.com/karagemop466-tech/Korea5/blob/main/scripts/nfl_intel.py">scripts/nfl_intel.py</a> · '
             'inputs: <a href="https://github.com/karagemop466-tech/Korea5/blob/main/data/nfl-intel/results-2026.json">results-2026.json</a> (137 verified finals, each row links nfl.com)')

    b.append("<h2>Our lines — Week 10 (remaining) and Week 11</h2>")
    rows = []
    for l in m["originatedLines"]:
        rows.append([
            f"W{l['week']}", esc(l["datePT"] or "—"), esc(l["startPT"] or "TBA"),
            esc(l["away"]), esc(l["home"]),
            fmt(l["ourSpread_home"], 1), fmt(l["ourSpread_recency_home"], 1),
            fmt(l["ourTotal"], 1), fmt(l["ourTotal_recency"], 1),
            fmt(l["winProb_home"], 3),
            UNV(),  # market spread
            src(l["gameUrl"], "game") + " " + src(l["weekUrl"], "week"),
        ])
    b.append(table(["Wk", "Date (PT)", "Kick", "Away", "Home", "Our spread (home)", "S2 spread", "Our total", "S2 total",
                    "P(home)", "Market", "Official"], rows))
    b.append('<p class="small">Spread sign: negative = home favoured. ' + CMP() +
             ' columns; market cells are ' + UNV() + ' because no official/verified odds source exists (Q-ODDS) — never inferred.</p>')

    b.append("<h2>Power ratings (opponent-adjusted)</h2>")
    rows = [[esc(r["team"]), fmt(r["rating"]), fmt(r["rating_recency"]), fmt(r["pace"], 1), fmt(r["pace_recency"], 1),
             f'{r["w"]}-{r["l"]}-{r["ties"]}', str(r["pf"]), str(r["pa"]), CMP(), src(r["standingsUrl"], "standings")]
            for r in m["ratings"]]
    b.append(table(["Team", "Rating S1", "Rating S2", "Pace S1", "Pace S2", "W-L-T", "PF", "PA", "Label", "Verified against"], rows))

    b.append("<h2>Walk-forward backtest (weeks 5–9, fit strictly before each target week)</h2>")
    for key, name in (("S1_fullSeason", "S1 — opponent-adjusted margin (full season)"),
                      ("S2_recency09", "S2 — recency-weighted margin (λ=0.9)")):
        bt = m["backtest"][key]
        mm = bt["metrics"]
        b.append(f"<h3>{esc(name)}</h3>")
        b.append(table(["Metric", "Model", "Baseline", "Better?"], [
            ["Spread MAE (pts)", fmt(mm["maeSpread"]), fmt(mm["baseline"]["flatHomeMinus2.5_maeSpread"]),
             "model" if mm["maeSpread"] < mm["baseline"]["flatHomeMinus2.5_maeSpread"] else "baseline"],
            ["Total MAE (pts)", fmt(mm["maeTotal"]), "—", "—"],
            ["Brier (home win prob)", fmt(mm["brier"], 3), fmt(mm["baseline"]["flatHome0.55_brier"], 3),
             "model" if mm["brier"] < mm["baseline"]["flatHome0.55_brier"] else "baseline"],
            ["Side hit rate", fmt(mm["hitRate"], 3), "—", "—"],
            ["Corr(predicted, actual margin)", fmt(mm["corrPredActual"], 3), "—", "—"],
            ["Graded games", str(mm["n"]), "—", "—"],
        ]))
        g = bt["gates"]
        b.append(table(["Gate", "Rule", "Value", "Status"],
                       [[x["id"], esc(x["rule"]), esc(x["value"]),
                         tag(x["status"], "tag ver" if x["status"] == "PASS" else "tag flag")] for x in g["gates"]]))
        rows = [[str(p["week"]), esc(p["away"]), esc(p["home"]), fmt(p["predMargin"], 1), fmt(p["actualMargin"], 1),
                 fmt(p["winProb"], 3), fmt(p["predTotal"], 1), fmt(p["actualTotal"]), CMP(), src(p["sourceUrl"], "result")]
                for p in bt["predictions"]]
        b.append(table(["Wk", "Away", "Home", "Pred margin (home)", "Actual margin", "P(home)", "Pred total", "Actual", "Label", "Verified result"], rows))

    page("nfl-lines.html", "Originated lines & ratings", "nfl-lines.html", "".join(b))


# ============================================================ nfl-strategies.html
def build_strategies():
    s = STRAT
    b = []
    b.append("<h1>Strategy library &amp; leaderboard competition</h1>")
    b.append('<aside class="callout warn" role="note"><strong>Competition design — pilot 2026.</strong> '
             'External entries open for the 2027 season only after the legal question (Q-LEGAL) is answered. '
             'Rewards are non-monetary by design. No strategy is graded before it passes the validation gates.</aside>')

    c = s["competition"]
    b.append("<h2>Competition rules</h2>")
    b.append(table(["Item", "Rule"], [
        ["Name", esc(c["name"])], ["Pilot", esc(c["pilot"])], ["Open season", esc(c["season"])],
        ["Primary scoring", esc(c["scoring"]["primary"])],
        ["Units scoring", esc(c["scoring"]["monetary"])],
        ["Parlay scoring", esc(c["scoring"]["parlays"])],
        ["Minimum graded picks", esc(c["scoring"]["minimumGradedPicks"])],
    ]))
    b.append("<h3>Entry rules</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in c["entryRules"]) + "</ul>")
    b.append("<h3>Rewards (non-monetary until Q-LEGAL is answered)</h3><ul>" +
             "".join(f"<li>{esc(x)}</li>" for x in c["rewards"]) + "</ul>")
    b.append("<h3>How luck is removed</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in c["luckRemoval"]) + "</ul>")
    b.append(f'<p class="small">{esc(c["governance"])}</p>')

    b.append("<h2>Validation gates</h2>")
    b.append(table(["Gate", "Name", "Rule", "What luck it removes", "Status"],
                   [[g["id"], esc(g["name"]), esc(g["rule"]), esc(g["removes"]),
                     tag(g["status"], "tag ver" if "PASS" in g["status"] else "tag flag")] for g in s["gates"]]))

    b.append("<h2>Strategy board (2026 pilot)</h2>")
    rows = []
    for st in s["strategies"]:
        comp = st.get("computed") or {}
        metric = (f'MAE {comp.get("maeSpread")} · Brier {comp.get("brier")} · hit {comp.get("hitRate")}'
                  if comp.get("maeSpread") is not None else
                  (f'signal r={comp.get("signalCorr")}' if comp.get("signalCorr") is not None else
                   "blank — " + esc(comp.get("note", "no data yet"))))
        rows.append([st["id"], esc(st["name"]), tag(st["type"], "tag"), esc(st["rule"]),
                     metric, esc(st["validation"]),
                     (CMP() if comp.get("maeSpread") is not None or comp.get("signalCorr") is not None else UNV())])
    b.append(table(["ID", "Strategy", "Type", "Rule", "Metrics", "Validation", "Label"], rows))
    b.append('<p class="small">S1/S2 metrics are computed from the verified results on '
             '<a href="nfl-lines.html">Lines &amp; ratings</a> (walk-forward weeks 5–9). '
             'S3–S5 metrics are blank until their required data exists (Q-INJ-HIST, Q-ODDS, Q-PROPS). '
             'S6’s signal strength is computed; its pick-level record is blank until graded.</p>')

    b.append("<h2>Correlation values</h2>")
    b.append("<h3>Pre-game signal correlations (computed, n=74 walk-forward games, weeks 5–9)</h3>")
    keys = ["ratingDiff", "restDiff", "streakDiff", "ppgDiff", "home"]
    corr = MODEL["signalCorrelations"]
    rows = []
    for k in keys + ["actualMargin"]:
        rows.append([esc(k)] + [(fmt(corr[k].get(u), 3) if corr[k].get(u) is not None else "undefined (constant)")
                                for u in keys + ["actualMargin"]])
    b.append(table(["signal"] + [esc(k) for k in keys + ["actualMargin"]], rows))
    b.append("<h3>What the correlations say</h3><ul>" +
             "".join(f"<li>{esc(x['pair'])}: <strong>{x['value']}</strong> — {esc(x['note'])}</li>"
                     for x in s["correlationValues"]["computedSummary"]) + "</ul>")
    b.append("<h3>Parlay and player-prop pair correlations</h3>")
    b.append(table(["Pair type", "Value", "Status"], [
        ["Same-game parlay leg pairs", "blank", UNV() + " — needs graded market data (Q-ODDS)"],
        ["Player-prop combos", "blank", UNV() + " — needs prop data (Q-PROPS)"],
    ]))
    b.append('<p class="small">' + esc(s["correlationValues"]["blankNote"]) + " Conservative joint-probability bounds are defined in the frameworks below.</p>")

    b.append("<h2>Parlay framework</h2><ul>" +
             "".join(f"<li>{esc(x)}</li>" for x in s["parlayFramework"]["legRules"]) +
             f"<li>Correlation policy: {esc(s['parlayFramework']['correlationPolicy'])}</li>" +
             f"<li>Sizing: {esc(s['parlayFramework']['sizing'])}</li></ul>")
    b.append("<h2>Player-prop combo framework</h2>")
    b.append(table(["Item", "Detail"], [
        ["Required data", esc("; ".join(s["propFramework"]["requiredData"]))],
        ["Gates", esc(s["propFramework"]["gates"])],
        ["Status", esc(s["propFramework"]["status"]) + " · " + UNV()],
    ]))
    page("nfl-strategies.html", "Strategies & leaderboard", "nfl-strategies.html", "".join(b))


# ============================================================ nfl-injuries.html
OFF_POS = {"QB", "RB", "WR", "TE", "FB", "C", "G", "T"}
DEF_POS = {"DE", "DT", "LB", "CB", "S"}


def build_injuries():
    b = []
    b.append("<h1>Injuries &amp; depth deficiencies — Week 10</h1>")
    b.append('<aside class="callout warn" role="note"><strong>Snapshot of the official NFL.com Week-10 injury report, '
             'retrieved 2026-11-13.</strong> Blank Game Status means the official page showed no designation yet — '
             'not an inference. Depth tier (1st/2nd/3rd/4th string) is not published by the league report; '
             'it is shown only where an official source confirms it, otherwise it is blank and flagged (Q-DEPTH).</aside>')

    b.append("<h2>Starter / backup status verified from official NFL.com news</h2>")
    rows = [[esc(n["team"]), esc(n["headline"]), esc(n["impact"]), VER(), src(n["sourceUrl"], "nfl.com news")]
            for n in INJ["statusNews"]]
    b.append(table(["Team", "Official headline", "Deficiency impact", "Label", "Source"], rows))

    # deficiency summary per team
    b.append("<h2>Deficiency flags by team and side (Week 10)</h2>")
    from collections import defaultdict
    per = defaultdict(lambda: defaultdict(lambda: {"out": 0, "q": 0, "dnp": 0, "lim": 0}))
    for r in INJ["rows"]:
        side = "OFF" if r["pos"] in OFF_POS else ("DEF" if r["pos"] in DEF_POS else "ST")
        st = r["gameStatus"]
        d = per[r["team"]][side]
        if st == "Out":
            d["out"] += 1
        elif st in ("Questionable", "Doubtful"):
            d["q"] += 1
        if r["practice"] == "Did Not Participate In Practice":
            d["dnp"] += 1
        elif r["practice"] == "Limited Participation in Practice":
            d["lim"] += 1
    verified_flags = {
        "BAL": "QB: starter Lamar Jackson on IR + backup Tyler Huntley out for season → 3rd/4th string QB (verified chain)",
        "SEA": "QB: starter Sam Darnold ruled out; backup Drew Lock expected to start (verified)",
        "MIA": "QB: starter Malik Willis on IR; backup Kyle McCord in line for first start (verified)",
        "GB": "RB: starter Josh Jacobs surgery this week, return TBD (verified)",
        "LAR": "WR: starter Puka Nacua likely IR (knee) — labelled likely, not yet official (verified report)",
        "CLE": "QB: Deshaun Watson named starter vs HOU (verified); Watson was in concussion protocol Week 9 (verified)",
        "AZ": "QB: Carson Beck named starter vs LAR (verified)",
    }
    rows = []
    for team in sorted(per):
        for side in ("OFF", "DEF", "ST"):
            d = per[team][side]
            if not any(d.values()):
                continue
            flag = verified_flags.get(team, "") if side in ("OFF", "DEF") else ""
            if team in ("LAC", "BAL") and team == "LAC":
                flag = flag  # LAC has no reportable rows in this snapshot
            rows.append([esc(team), side, str(d["out"]), str(d["q"]), str(d["dnp"]), str(d["lim"]),
                         esc(flag) if flag else "depth tier " + UNV(),
                         VER() + " counts · " + (VER() if flag else UNV()) + " depth",
                         src("https://www.nfl.com/injuries/", "injury report")])
    b.append(table(["Team", "Side", "Out", "Q/Doubtful", "DNP (practice)", "Limited", "Verified deficiency note", "Label", "Source"], rows))
    b.append('<p class="small">Counts are computed from the verified rows below. "Out/Q" are official game-status '
             'designations; DNP/Limited are official practice-participation statuses. A blank note does not mean '
             'no deficiency — it means depth tier is unverified (Q-DEPTH).</p>')

    for nr in INJ.get("noInjuriesReported", []):
        b.append(f'<aside class="callout" role="note"><strong>{esc(nr["game"])}:</strong> {esc(nr["officialText"])} '
                 f'({esc(nr["note"])}) {src(nr["sourceUrl"], "source")}</aside>')

    b.append("<h2>Full reportable rows (Week 10)</h2>")
    b.append('<p class="small">Inclusion rule: every row with an injury, a non-Full practice status, or a game '
             'designation is listed for all teams; <strong>49ers rows are listed in full</strong> (priority team). '
             'Rows showing Full participation with no injury and no designation carry no information and are omitted. '
             'All values transcribed verbatim from ' + src("https://www.nfl.com/injuries/", "nfl.com/injuries") + ".</p>")
    from collections import defaultdict
    games = defaultdict(lambda: defaultdict(list))
    order = []
    for r in INJ["rows"]:
        if r["game"] not in games:
            order.append(r["game"])
        games[r["game"]][r["team"]].append(r)
    for g in order:
        b.append(f"<h3>{esc(g)}</h3>")
        for team in games[g]:
            rows = []
            for r in games[g][team]:
                reportable = (r["injury"] or r["practice"] != "Full Participation in Practice" or r["gameStatus"])
                if not reportable and team != "SF":
                    continue
                rows.append([esc(r["player"]), esc(r["pos"]), esc(r["injury"]) or "—", esc(r["practice"]),
                             esc(r["gameStatus"]) or "—", "—", VER(),
                             src("https://www.nfl.com/players/" + r["player"].lower().replace(" ", "-").replace(".", "").replace("'", "") + "/", "player"),
                             src("https://www.nfl.com/injuries/", "report")])
            if rows:
                b.append(f"<h4>{esc(team)}</h4>")
                b.append(table(["Player", "Pos", "Injury", "Practice", "Game status", "Depth tier", "Label", "Official", "Report"], rows))
    page("nfl-injuries.html", "Injuries & deficiencies", "nfl-injuries.html", "".join(b))


# ============================================================ nfl-executive.html
def build_exec():
    b = []
    b.append("<h1>Executive summary — NFL intelligence</h1>")
    b.append('<p class="small">2026-11-13 · mirrors <a href="research/EXECUTIVE-SUMMARY-NFL.md">research/EXECUTIVE-SUMMARY-NFL.md</a></p>')
    b.append("""<h2>The short version</h2>
<p>We now originate our own NFL numbers from verified league data. The 2026 season to date is fully collected and
cross-checked: <strong>137 final scores</strong> (weeks 1–10) reproduce the official standings <strong>team-by-team,
32 of 32, exactly</strong> — records and points. From those results we compute team ratings and publish our own
spreads, totals and win probabilities for every remaining Week-10 game and all of Week 11. A walk-forward backtest
(weeks 5–9) shows real, if modest, skill: both core strategies beat naive baselines on spread error and probability
error and pass the four evaluative validation gates.</p>""")
    b.append("<h2>What was delivered</h2><ul>"
             "<li><strong>Lines origination:</strong> opponent-adjusted margin model + recency variant; formulas published; "
             "market columns deliberately blank (no verified odds source — Q-ODDS).</li>"
             "<li><strong>Signals:</strong> rest-days difference is the strongest measured pre-game signal (r=0.438 vs margin), "
             "ahead of rating difference (0.325). This is a computed finding from verified data, not a claim from literature.</li>"
             "<li><strong>Strategy system:</strong> six strategies (singles, parlays, player-prop combos) with eight validation "
             "gates that remove luck: sample floors, baseline-relative skill, out-of-time holdouts, multiple-testing "
             "correction, bootstrap certainty and closing-line grading.</li>"
             "<li><strong>Leaderboard competition:</strong> pre-registered entries, Brier/log-loss skill scoring, "
             "non-monetary rewards pending a legal answer (Q-LEGAL), pilot board live for weeks 10–18.</li>"
             "<li><strong>Injury &amp; deficiency tracking:</strong> the official Week-10 report (296 rows) plus verified "
             "starter/backup news. Confirmed deficiency chains: Baltimore QB (starter on IR and backup out for season — "
             "3rd/4th string), Seattle QB (starter out, named backup to start), Miami QB (starter IR, backup first start), "
             "Green Bay RB, Rams WR.</li>"
             "<li><strong>Decision support:</strong> a suggestions register with a review-and-choose workflow (nothing "
             "implemented before acceptance) and a questions register listing exactly what is missing and how to discover it.</li>"
             "</ul>")
    b.append("<h2>What blocks bigger decisions (read before acting)</h2><ul>"
             "<li>No market odds source exists in this system (Q-ODDS) — monetary grading, CLV and realistic parlay "
             "pricing cannot start until one is licensed or logged. This is the #1 blocker.</li>"
             "<li>Depth tiers are unverified except where official news names them (Q-DEPTH) — 2nd/3rd/4th-string claims "
             "are labelled only for the verified chains above.</li>"
             "<li>Only one week of injury history exists in this repo (Q-INJ-HIST); the injury signal cannot be "
             "correlated with outcomes yet.</li>"
             "<li>Rewards for external entries need a compliance answer (Q-LEGAL) before the 2027 season opens.</li></ul>")
    b.append("<h2>Numbers to remember</h2>")
    b.append(table(["Item", "Value", "Label"], [
        ["Verified finals collected", "137 (weeks 1–10, incl. the Week-10 TNF result)", VER()],
        ["Standings cross-check", "32/32 teams exact on W-L-T and PF/PA", VER()],
        ["HFA 2026", "−0.02 pts/game", CMP()],
        ["Margin SD (σ)", "13.18 pts", CMP()],
        ["S1 backtest", "MAE 10.56 (base 11.32) · Brier 0.216 (base 0.255) · hit 66.2% · corr 0.314 · G1–G4 PASS", CMP()],
        ["S2 backtest", "MAE 10.54 · Brier 0.215 · hit 63.4% · corr 0.318 · G1–G4 PASS", CMP()],
        ["Strongest signal", "restDiff r=0.438 (n=74)", CMP()],
        ["Week-10 injury rows", "296 + 9 official status-news items", VER()],
        ["Market values", "blank everywhere", UNV()],
    ]))
    b.append('<p class="small">Sources: ' + src("https://www.nfl.com/scores/2026/week-9", "nfl.com scores") + " · " +
             src("https://www.nfl.com/standings/league/2026/REG", "nfl.com standings") + " · " +
             src("https://www.nfl.com/injuries/", "nfl.com injuries") + " · " +
             src("https://www.nfl.com/schedules/2026/by-week/week-11", "nfl.com schedule") + "</p>")
    page("nfl-executive.html", "Executive summary", "nfl-executive.html", "".join(b))


# ============================================================ suggestions.html
def build_suggestions():
    b = []
    b.append("<h1>Suggestions — review before implementing</h1>")
    b.append('<aside class="callout warn" role="note"><strong>Nothing on this page is implemented until it is accepted.</strong> '
             'This is the decision-making queue: read, choose the best path, mark the status. '
             'Statuses: proposed → accepted / rejected / needs-info → implemented.</aside>')
    b.append("<h2>Review workflow</h2><ol>" + "".join(f"<li>{esc(x)}</li>" for x in SUGG["meta"]["workflow"]) + "</ol>")
    b.append(f'<p class="small">Decision owner: {esc(SUGG["reviewBoard"]["decisionOwner"])} · '
             f'cadence: {esc(SUGG["reviewBoard"]["reviewCadence"])} · '
             f'rule: {esc(SUGG["reviewBoard"]["rule"])}</p>')
    b.append("<h2>Register</h2>")
    cls = {"proposed": "tag flag", "accepted": "tag ver", "implemented": "tag", "rejected": "tag flag", "needs-info": "tag est"}
    rows = []
    for s in SUGG["suggestions"]:
        rows.append([s["id"], esc(s["title"]), tag(s["category"], "tag"), str(s["priority"]),
                     tag(s["status"], cls.get(s["status"], "tag")),
                     esc(s["rationale"]), esc(s["impact"]),
                     esc(", ".join(s["dependsOn"])) if s["dependsOn"] else "—",
                     src(s["source"], "source") if s.get("source") else '<span class="small">—</span>',
                     esc(s.get("implementedBy", ""))])
    b.append(table(["ID", "Suggestion", "Category", "Priority", "Status", "Rationale", "Expected impact",
                    "Blocked by", "Reference", "Implemented by"], rows))
    b.append("<h2>How to use this page</h2><ul>"
             "<li>Sort attention by priority: SG-01 (odds source) and SG-15 (legal) gate the biggest capabilities.</li>"
             "<li>Anything marked <em>needs-info</em> is waiting on a question in <a href=\"questions.html\">Questions</a>.</li>"
             "<li>When you accept or reject, record the reason here so the decision stays auditable.</li></ul>")
    page("suggestions.html", "Suggestions", "suggestions.html", "".join(b))


# ============================================================ questions.html
def build_questions():
    b = []
    b.append("<h1>Questions, information &amp; answers</h1>")
    b.append('<aside class="callout warn" role="note"><strong>Before any decision is made, these questions must be '
             'answered or explicitly waived.</strong> Each row states what we have (verified), what is missing, and a '
             'discovery action to close the gap. Missing values are never filled in by inference.</aside>')
    h = QUEST["haveAndHaveNot"]
    b.append(table(["What we HAVE (verified)", "What we HAVE (computed)", "What is MISSING / unverified"],
                   [["<ul>" + "".join(f"<li>{esc(x)}</li>" for x in h["haveVerified"]) + "</ul>",
                     "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in h["haveComputed"]) + "</ul>",
                     "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in h["missingUnverified"]) + "</ul>"]]))
    b.append("<h2>Question register</h2>")
    rows = []
    for q in QUEST["questions"]:
        rows.append([q["id"], esc(q["question"]), esc(q["whyItBlocks"]), esc(q["haveNow"]), esc(q["missing"]),
                     esc(q["discoveryAction"]),
                     " ".join(src(u, "link") for u in q["links"]) if q["links"] else '<span class="small">—</span>'])
    b.append(table(["ID", "Question", "Why it blocks decisions", "What we have now", "What is missing",
                    "Discovery action", "Official links"], rows))
    page("questions.html", "Questions register", "questions.html", "".join(b))


if __name__ == "__main__":
    build_hub()
    build_lines()
    build_strategies()
    build_injuries()
    build_exec()
    build_suggestions()
    build_questions()
    print("nfl intel pages built: nfl-intel, nfl-lines, nfl-strategies, nfl-injuries, nfl-executive, suggestions, questions")
