#!/usr/bin/env python3
"""Generate the NFL Lines Lab section of the site.

Reads:
  curated/nfl-lab.json          — the curated specification (questions, strategies,
                                   gates, leaderboard rules, depth rules, suggestions, flags)
  data/lab/*.json               — official-source records and the computed analysis
  data/lab/analysis.json        — dispersion, correlations and sample-size tables

Writes:
  lab/index.html                — landing page
  lab/questions.html            — decision register
  lab/strategies.html           — strategy catalogue and validation gates
  lab/correlations.html         — dispersion, correlations and sample-size analysis
  lab/injuries.html             — injury report and lineup-depth tracker
  lab/leaderboard.html          — strategy competition
  lab/suggestions.html          — suggestions register
  lab/flags.html                — Flagged for Review (lab)
  nfl-strategy.html             — retained entry point that now points into the lab

Every row that states a fact links to the official source it came from. A value that
could not be confirmed is rendered blank and listed on the flagged page.
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

LAB = "lab"
ASSETS = os.path.join(LAB, "assets")
os.makedirs(ASSETS, exist_ok=True)

SITE = "Free Time Vacation Planner"
LAB_NAME = "NFL Lines Lab"

ROOT_NAV = [
    ("../index.html", "Dashboard"),
    ("../calendar.html", "Calendar"),
    ("../vacation.html", "Vacation windows"),
    ("../mlb.html", "MLB"),
    ("../nfl.html", "NFL &amp; 49ers"),
    ("../radio.html", "Radio"),
    ("../sources.html", "Sources"),
    ("../flagged.html", "Flagged"),
    ("../method.html", "Method"),
    ("../extra/index.html", "Official feeds"),
]
LAB_NAV = [
    ("index.html", "Lab home"),
    ("questions.html", "Questions"),
    ("strategies.html", "Strategies"),
    ("correlations.html", "Correlations"),
    ("injuries.html", "Injuries &amp; depth"),
    ("leaderboard.html", "Leaderboard"),
    ("suggestions.html", "Suggestions"),
    ("flags.html", "Flagged for Review"),
]


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


SPEC = load("curated/nfl-lab.json", {})
INJ = load("data/lab/injuries-week10-2026.json", {})
LOGS = load("data/lab/player-logs-2026.json", {})
BOOK = load("data/lab/gamebook-bills-vikings-2026-w9.json", {})
ANA = load("data/lab/analysis.json", {})


def esc(v):
    return html.escape("" if v is None else str(v))


def src(url, label="official source"):
    if not url:
        return '<span class="small">—</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def srcs(urls, label="official source"):
    if not urls:
        return '<span class="small">—</span>'
    return " ".join(src(u, label) for u in urls)


def tag(text, cls="tag"):
    return f'<span class="{cls}">{esc(text)}</span>'


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def nav(active, root=False):
    parts = [f'<a href="{u if not root else u[3:]}">{n}</a>' for u, n in ROOT_NAV]
    parts.append('<span class="nav-sep">|</span>')
    parts += [f'<a href="{u if not root else "lab/" + u}" class="{"active" if u == active else ""}">{n}</a>'
              for u, n in LAB_NAV]
    return "".join(parts)


def page(title, active, body, desc="", root=False):
    css = "assets/style.css" if root else "../assets/style.css"
    lab_css = "lab/assets/lab.css" if root else "assets/lab.css"
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {LAB_NAME} · {SITE}</title>
<meta name="description" content="{esc(desc or 'NFL lines, strategy research, injury and depth tracking, decision register and suggestions.')}">
<link rel="stylesheet" href="{css}">
<link rel="stylesheet" href="{lab_css}">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> NFL LINES LAB</div>
  <nav class="main">{nav(active, root)}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
  <p><strong>{LAB_NAME}</strong> · part of the {SITE} · Pacific time · lab records retrieved 2026-11-13</p>
  <p>Every table row links to the official source it came from. Values that could not be confirmed are blank and listed on
  <a href="{"lab/flags.html" if root else "flags.html"}">Flagged for Review</a>. No strategy on this site is validated: this repository holds no market price,
  no settlement record and no forecast log, so no win rate, yield, edge or fair price is published anywhere.</p>
</div></footer></body></html>"""


def write(name, content):
    with open(name, "w", encoding="utf-8") as fh:
        fh.write(content)


def source_table():
    rows = [[esc(s["name"]), esc(s["provides"]), src(s["url"]), esc(s["verifiedOn"])]
            for s in SPEC.get("officialSources", [])]
    return table(["Official source", "What it provides", "Link", "Checked"], rows)


# ---------------------------------------------------------------- landing
def build_index():
    ana = ANA.get("correlations", [])
    pair = next((c for c in ana if "Jordan Addison" in c["b"]), None)
    pair_ci = "" if not pair else f"{pair['ci95'][0]} to {pair['ci95'][1]}"
    # The -110 rows are selected by their price label, not by comparing the
    # rounded break-even probability to 110/210: the stored value is rounded to
    # four decimals, so a tolerance comparison silently matched nothing.
    ss = [s for s in ANA.get("sampleSize", []) if "-110" in s["priceBasis"]]
    if not ss:
        raise SystemExit("build_lab: no -110 sample-size rows in analysis.json")
    n5 = next((s["observationsNeeded"] for s in ss if s["edgeOverBreakEven"] == 0.05), None)
    n3 = next((s["observationsNeeded"] for s in ss if s["edgeOverBreakEven"] == 0.03), None)
    if n5 is None or n3 is None:
        raise SystemExit("build_lab: the +5 or +3 point sample-size row is missing")
    inj_status = len(INJ.get("gameStatus", []))
    teams = len(INJ.get("practice", {}))
    rows = len([r for t in INJ.get("practice", {}).values() for r in t["rows"]])

    body = f"""
<h1>NFL Lines Lab</h1>
<p class="lede">A workbench for originating your own NFL lines: the questions that have to be answered first, the strategies
that could be tested, the validation gates each one has to pass, the measured dependence between legs, the injury and depth
tracker that feeds the signals, and a suggestions register where every improvement is listed with a recommended path.
<strong>Nothing here is a validated betting edge.</strong> This repository holds no market price, no settlement record and no
forecast log, so no win rate, yield, edge or fair price is published anywhere on this site.</p>

<div class="callout"><strong>What this lab is.</strong> A decision-support system built on official NFL records:
the weekly injury report, official player game logs, and the official Game Book. <strong>What it is not.</strong> A betting
service, a price feed, or a validated strategy. The leaderboard is published empty on purpose.</div>

<h2>Headline findings from the official data</h2>
<div class="scroll"><table><thead><tr><th>#</th><th>Finding</th><th>Value</th><th>What it means</th><th>Source</th></tr></thead><tbody>
<tr><td>1</td><td>Two same-team receivers are not independent</td>
<td>r = {esc(pair['r']) if pair else '—'} (n = {esc(pair['n']) if pair else '—'}, 95% CI {esc(pair_ci) if pair_ci else '—'})</td>
<td>On the matched official games the two Vikings receivers' yardage moved in opposite directions. Pricing a two-leg receiver
parlay as the product of two marginal probabilities would be wrong, in the direction that favours the book.</td>
<td>{srcs([pair['sourceA'], pair['sourceB']] if pair else [])}</td></tr>
<tr><td>2</td><td>A small edge cannot be told apart from luck without a large sample</td>
<td>{esc(f"{n5:,}")} bets for a +5 point edge; {esc(f"{n3:,}")} for +3 points at -110</td>
<td>This is the number that decides whether a strategy is skill or luck. It is now a hard entry condition on the leaderboard.</td>
<td>{src('https://www.nfl.com/players/justin-jefferson/stats/logs/')}</td></tr>
<tr><td>3</td><td>Player props are noisy</td>
<td>Standard deviation 22.7 to 42.3 yards across the four tracked props</td>
<td>A 3-yard modelling advantage needs 58 to 199 games of the same player's history before it is visible at all.</td>
<td>{src('https://www.nfl.com/players/justin-jefferson/stats/logs/')}</td></tr>
<tr><td>4</td><td>Depth replacement is documentable from official sources</td>
<td>3-deep quarterback chain, Week 9</td>
<td>The Vikings' first listed quarterback did not play, the second started, and the third also threw for 58 yards in the same
game. That is the official Game Book, not an inference.</td>
<td>{src('https://static.www.nfl.com/image/upload/v1794311318/gamecenter/ab5825a7-4feb-11f1-abca-2c54536568a9.pdf')}</td></tr>
<tr><td>5</td><td>The official injury report is a live, structured feed</td>
<td>{esc(inj_status)} published game-status designations; {esc(teams)} clubs and {esc(rows)} practice rows transcribed</td>
<td>Availability, who starts and who absorbs the work are three separate official facts. The tracker keeps them apart.</td>
<td>{src('https://www.nfl.com/injuries/')}</td></tr>
</tbody></table></div>

<h2>Where to go</h2><div class="grid g3">
<div class="card"><h3>Questions first</h3><p>Every decision that has to be made, what is already known, what is missing, why it
blocks, and the exact step that closes it.</p><a href="questions.html">Decision register →</a></div>
<div class="card"><h3>Strategies and gates</h3><p>Twelve candidate signals — singles, parlays and prop combinations — each with
the gates it must pass before it may be ranked.</p><a href="strategies.html">Catalogue →</a></div>
<div class="card"><h3>Correlations</h3><p>Measured dependence between legs, dispersion of each outcome, and the sample size
needed before any of it means something.</p><a href="correlations.html">Numbers →</a></div>
<div class="card"><h3>Injuries and depth</h3><p>The official weekly report, the official Game Book, and the rule that keeps a
blank cell blank.</p><a href="injuries.html">Tracker →</a></div>
<div class="card"><h3>Leaderboard</h3><p>The competition design: what is scored, what is refused, and why it is empty today.</p>
<a href="leaderboard.html">Competition →</a></div>
<div class="card"><h3>Suggestions</h3><p>Every improvement to this site and this system, with impact, effort, risk and a
recommended order — so a decision can be made before any code is written.</p><a href="suggestions.html">Suggestions →</a></div>
</div>

<h2>Official sources used</h2>
{source_table()}
<div class="callout"><strong>Two labs, one question.</strong> This lab is the <em>evidence</em> side: official NFL records
only — the published injury report, official player game logs, the official Game Book — and every correlation, dispersion
figure and minimum-sample rule is computed from them by <code>scripts/analyze_lab.py</code>. The companion
<a href="../nfl-lab/index.html">NFL Lines Lab</a> is the <em>model</em> side: it builds and back-tests a line model
against third-party game data and reports how it compares with the market spread. Neither lab publishes a validated
edge, and each says so on its own landing page.</div>
<p class="small">Checklist of what was verified and how: see <a href="flags.html">Flagged for Review</a> and
<a href="../research/NFL-LINES-LAB.md">the research notes</a>. The parallel line-origination design memo is kept at
<a href="../research/NFL-LINES.md">research/NFL-LINES.md</a>, with the earlier strategy notes at
<a href="../research/NFL-STRATEGY.md">research/NFL-STRATEGY.md</a>.</p>
"""
    write(os.path.join(LAB, "index.html"), page("NFL Lines Lab", "index.html", body))


# ---------------------------------------------------------------- questions
def build_questions():
    rows = []
    for q in SPEC.get("questions", []):
        rows.append([
            esc(q["id"]),
            f"<strong>{esc(q['decision'])}</strong>",
            esc(q["known"]),
            esc(q["missing"]),
            esc(q["blocks"]),
            esc(q["discovery"]),
            esc(q["owner"]),
            tag(q["status"], "tag flag" if "open" in q["status"] else "tag ver"),
            srcs(q.get("sources", [])),
        ])
    body = f"""
<h1>Decision register — what must be answered before any decision is reasonable</h1>
<p class="lede">Fifteen decisions stand between this repository and a defensible line. For each one: what is already known,
what is missing, why the missing part blocks the decision, and the exact discovery step that closes it. A question is only
closed when its information exists, not when an assumption is made.</p>

<div class="callout warn"><strong>Two questions block everything.</strong> Q01 and Q05 — which prices are legally accessible,
and where historical lines come from — have no answer in this repository. Until they do, no strategy can be scored, no
leaderboard row can be filled, and no yield can be quoted anywhere on this site.</div>

{table(["ID", "Decision", "What we already know", "What is missing", "Why it blocks the decision",
        "Discovery step", "Owner", "Status", "Source"], rows)}
<p class="small">Sources are official league pages. Where a row states that no official price source exists, the link points to
the league's own statistics and schedule portals, which are the pages that confirm what the league does and does not publish.</p>
"""
    write(os.path.join(LAB, "questions.html"), page("Decision register", "questions.html", body))


# ---------------------------------------------------------------- strategies
def build_strategies():
    rows = []
    for s in SPEC.get("strategies", []):
        rows.append([
            esc(s["id"]),
            f"<strong>{esc(s['name'])}</strong>",
            tag(s["kind"], "tag nfl"),
            esc(s["signal"]),
            esc(s["inputs"]),
            esc(s["officialInputsToday"]),
            esc(", ".join(s["gates"])),
            tag(s["status"], "tag flag"),
            esc(s["note"]),
            srcs(s.get("sources", [])),
        ])
    gate_rows = [[esc(g["id"]), f"<strong>{esc(g['name'])}</strong>", esc(g["requirement"]), esc(g["why"]),
                  esc(g["failureAction"]), esc(g["evidence"]), src(g.get("basisUrl"), "basis")] for g in SPEC.get("gates", [])]
    body = f"""
<h1>Strategy catalogue and validation gates</h1>
<p class="lede">Twelve candidate signals: single bets, player props, prop combinations and parlays, plus the injury overlay
that feeds all of them. Every one is a proposal. None has been traded, none has a price, and none may be ranked until it has
passed the gates below.</p>

<h2>Candidate strategies</h2>
{table(["ID", "Strategy", "Type", "Signal definition", "Inputs required", "What official inputs exist today",
        "Gates", "Status", "Note", "Source"], rows)}

<h2>Validation gates — each one must pass, in order</h2>
{table(["ID", "Gate", "What it requires", "Why it exists", "What happens on failure", "Evidence in this repository", "Basis"], gate_rows)}

<div class="callout flag"><strong>Gate G3 is currently unpassable.</strong> A strategy must beat the market on the same bets,
and there is no market reference in this repository yet. That is not a defect in the strategy; it is the missing artefact
recorded as Q05, and it is the critical path for the whole line-making track.</div>

<p class="small">Related: <a href="correlations.html">measured correlations and sample sizes</a> ·
<a href="injuries.html">the injury and depth tracker</a> · <a href="leaderboard.html">the competition rules</a></p>
"""
    write(os.path.join(LAB, "strategies.html"), page("Strategies", "strategies.html", body))


# ---------------------------------------------------------------- correlations
def build_correlations():
    disp_rows = [[esc(d["prop"]), esc(d["unit"]), esc(d["n"]), esc(d["mean"]), esc(d["stdev"]), esc(d["median"]),
                  esc(d["min"]), esc(d["max"]), esc(d["range"]), esc(d["cv"]), src(d["source"], "logs")]
                 for d in ANA.get("dispersion", [])]
    corr_rows = []
    for c in ANA.get("correlations", []):
        ci = c.get("ci95")
        ci_txt = "—" if not ci else f"{ci[0]} to {ci[1]}"
        verdict = ("interval includes zero" if c.get("ciIncludesZero")
                   else "interval excludes zero on this small sample")
        corr_rows.append([
            esc(c["a"]), esc(c["b"]), esc(c["n"]), esc(c["r"]), esc(ci_txt), esc(c.get("pValue")), esc(verdict),
            esc(c["pairNote"]), f"{src(c['sourceA'], 'logs A')} {src(c['sourceB'], 'logs B')}",
        ])
    basis_link = '<a href="#method">Derived — method below</a>'
    ss_rows = [[esc(s["priceBasis"]), esc(s["breakEven"]), esc(s["trueWinRate"]), esc(s["edgeOverBreakEven"]),
                esc(s["observationsNeeded"]), esc(s["note"]), basis_link] for s in ANA.get("sampleSize", [])]
    noise_rows = [[esc(n["prop"]), esc(n["stdev"]), esc(n["gamesNeededForPlus3YardEdge"]),
                   esc(n["gamesNeededForPlus5YardEdge"]), esc(n["gamesNeededForPlus10YardEdge"]), esc(n["note"]),
                   basis_link] for n in ANA.get("noiseGates", [])]
    power_rows = []
    for rho in (0.2, 0.3, 0.4, 0.5, 0.7):
        row = [esc(rho)]
        for n in (8, 17, 33, 65, 100, 200):
            hit = next((c for c in ANA.get("correlationPower", [])
                        if c["trueCorrelation"] == rho and c["n"] == n), None)
            row.append(esc(hit["powerVsZero"]) if hit else "—")
        power_rows.append(row + [basis_link])

    body = f"""
<h1>Correlation, dispersion and the cost of luck</h1>
<p class="lede">Everything on this page is computed from official NFL records committed under <code>data/lab/</code>:
player game logs for the 2026 regular season and the official Game Book for Bills at Vikings on November 9, 2026. These are
properties of the game data. They are not probabilities of winning, they are not prices, and they are not evidence of an edge.</p>

<div class="callout warn"><strong>Sample sizes are small and the intervals are wide.</strong> Every correlation below rests on
6 to 8 matched games. They are published with their intervals precisely so that nobody reads a point estimate as a fact.
The purpose is to show that the legs of a parlay are <em>not</em> independent, and to set the sample size that any future
claim has to meet.</div>

<h2>How wide each outcome is — the “luck” width of a prop</h2>
<p class="small">Standard deviation of the official game-level outcomes. A strategy that claims to predict a player's yardage
has to predict inside this spread, game after game.</p>
{table(["Outcome", "Unit", "n", "Mean", "Std dev", "Median", "Min", "Max", "Range", "Coefficient of variation", "Source"], disp_rows)}

<h2>Measured dependence between candidate legs</h2>
<p class="small">Pearson r on matched game-level observations, 95% interval from the Fisher z transform, two-sided p-value from
the t distribution. The last column says what the interval means; it is the honest reading of each number.</p>
{table(["Outcome A", "Outcome B", "n", "r", "95% interval", "p", "Reading", "Why this pair matters", "Sources"], corr_rows)}

<div class="callout flag"><strong>The two-receiver pair is the important one.</strong> r = -0.82 on six matched games, with an
interval of -0.98 to -0.02. The point estimate says the two receivers' yardage moved in opposite directions, which is what a
target split looks like. The interval is wide and only just excludes zero, so this is a demonstration of the structure rather
than a usable estimate. Either way, independence is the wrong model, and the direction of the error favours the book.</div>

<h2>How many observations before an edge can be told apart from luck</h2>
<p class="small">Two-sided one-proportion z test, alpha 0.05, power 0.80, normal approximation. The break-even rate already
contains the book margin.</p>
{table(["Price basis", "Break-even rate", "True win rate", "Edge over break-even", "Observations needed", "Method", "Basis"], ss_rows)}

<h2>How many games of one player's own history before a modelled edge is visible</h2>
<p class="small">n ≥ (standard deviation ÷ modelled edge)², so that the standard error of the mean falls below the edge being
claimed.</p>
{table(["Outcome", "Std dev", "Games for a 3-yard edge", "Games for a 5-yard edge", "Games for a 10-yard edge", "Method", "Basis"], noise_rows)}

<h2>How many games before a correlation estimate means anything</h2>
<p class="small">Power of a two-sided Fisher-z test against a true correlation of zero, alpha 0.05.</p>
{table(["True correlation", "n = 8", "n = 17", "n = 33", "n = 65", "n = 100", "n = 200", "Basis"], power_rows)}
<p class="small">Read this as: with nine games of a single season, a real correlation of 0.3 would be detected only about
one time in ten. Any strategy that claims to have found a dependable relationship from one season of data is reading noise.</p>

<h2 id="method">Method and limits</h2>
<ul class="clean">
<li>Inputs: <code>data/lab/player-logs-2026.json</code> and <code>data/lab/gamebook-bills-vikings-2026-w9.json</code>; the code is <code>scripts/analyze_lab.py</code> and is re-run in CI.</li>
<li>Every Week 9 row was cross-checked against the official Game Book PDF and matched exactly on attempts, completions, yards, touchdowns, interceptions, rating and rushing.</li>
<li>Only the 2026 season was transcribed, and only for five players on two teams. A production system needs several seasons and a much wider player set before any of these coefficients could be traded on.</li>
<li>No price, no settlement and no forecast record exists here, so nothing on this page is an expected value, a yield or a fair price.</li>
</ul>
"""
    write(os.path.join(LAB, "correlations.html"), page("Correlations", "correlations.html", body))


# ---------------------------------------------------------------- injuries
def build_injuries():
    status_rows = []
    for r in INJ.get("gameStatus", []):
        team, abbr, name, pos, injury, gs, slug = r
        status_rows.append([
            esc(team), esc(abbr), f'<a href="https://www.nfl.com/players/{esc(slug)}/" target="_blank" rel="noopener">{esc(name)}</a>',
            esc(pos), esc(injury), esc(gs) if gs else '<span class="small">—</span>',
            src("https://www.nfl.com/injuries/", "weekly report"),
        ])
    prac_rows = []
    for abbr, t in INJ.get("practice", {}).items():
        counts = {"Full": 0, "Limited": 0, "DNP": 0, "blank": 0}
        for row in t["rows"]:
            ps = row[3]
            if ps.startswith("Full"):
                counts["Full"] += 1
            elif ps.startswith("Limited"):
                counts["Limited"] += 1
            elif ps.startswith("Did Not"):
                counts["DNP"] += 1
            else:
                counts["blank"] += 1
        prac_rows.append([
            esc(t["club"]), esc(abbr), esc(len(t["rows"])), esc(counts["Full"]), esc(counts["Limited"]),
            esc(counts["DNP"]), esc(counts["blank"]),
            tag(t["coverage"], "tag est" if t["coverage"] != "complete" else "tag ver"),
            src(t["gameUrl"], "game page"),
        ])
    detail_rows = []
    for abbr, t in INJ.get("practice", {}).items():
        for row in t["rows"]:
            name, pos, injury, ps, gs, slug = row
            detail_rows.append([
                esc(t["club"]), esc(abbr),
                f'<a href="https://www.nfl.com/players/{esc(slug)}/" target="_blank" rel="noopener">{esc(name)}</a>',
                esc(pos), esc(injury) if injury else '<span class="small">—</span>',
                esc(ps) if ps else '<span class="small">—</span>',
                esc(gs) if gs else '<span class="small">—</span>',
                src("https://www.nfl.com/injuries/", "weekly report"),
            ])
    partial_rows = []
    for p in INJ.get("partialTables", []):
        obs = "; ".join(f"{r[0]} ({r[1]}, {r[3] or 'status not printed'})" for r in p["rowsObserved"]) or "none read"
        partial_rows.append([esc(p["club"]), esc(p["reason"]), esc(obs), src("https://www.nfl.com/injuries/", "weekly report")])

    # depth evidence from the official Game Book
    b = BOOK
    depth_rows = []
    if b:
        for team, label in (("MIN", "Minnesota Vikings"), ("BUF", "Buffalo Bills")):
            dnp = b["didNotPlay"].get(team, [])
            subs = b["substitutions"].get(team, [])
            depth_rows.append([
                esc(label),
                esc(", ".join(f"{p[0]} {p[2]}" for p in b["starters"][team]["offense"])),
                esc(", ".join(f"{p[0]} {p[2]}" for p in b["starters"][team]["defense"])),
                esc(", ".join(f"{p[0]} {p[2]}" for p in dnp) if dnp else '<span class="small">not printed</span>'),
                esc(f"{len(subs)} players listed as substitutions"),
                src(b["meta"]["gamePageUrl"], "official Game Book"),
            ])
    stat_rows = []
    if b:
        for team, label in (("MIN", "Minnesota Vikings"), ("BUF", "Buffalo Bills")):
            st = b["individualStats"][team]
            for cat, cols in (("rushing", "rushing"), ("passing", "passing"), ("receiving", "receiving")):
                for row in st.get(cat, []):
                    stat_rows.append([esc(label), esc(cat), " · ".join(esc(x) for x in row),
                                      esc(", ".join(b["statColumns"][cols])), src(b["meta"]["gamePageUrl"], "Game Book")])
    rules = [[esc(r["tier"]), f"<strong>{esc(r['definition'])}</strong>", esc(r["evidenceRequired"]), esc(r["note"]),
              src(r.get("basisUrl"), "official Game Book")] for r in SPEC.get("depthRules", [])]

    body = f"""
<h1>Injuries and lineup depth</h1>
<p class="lede">Three separate official facts, kept separate on purpose: <strong>availability</strong> (the weekly injury
report), <strong>who actually started</strong> and <strong>who absorbed the work</strong> (the official Game Book), and
<strong>the tier label</strong>, which is this project's own model output and is only written when the Game Book supports it.
Anything without that support stays blank and is listed on the flagged page.</p>

<div class="callout"><strong>Why the layers are not merged.</strong> An injury report says a player is doubtful. It never says
who will start in his place, and it never says what that replacement is worth. A claim that a second- or third-string player
replaced a starter is only supportable from a game record that names the starters and the participants — which is what the
official Game Book provides.</div>

<h2>Layer A — official game-status designations, Week 10 (2026)</h2>
<p class="small">Retrieved 2026-11-13 from the official Week 10 injury report article and the weekly injury report page.
{esc(INJ.get("meta", {}).get("gameStatusNote", ""))}</p>
{table(["Club", "Abbr", "Player", "Pos", "Injury", "Game status", "Source"], status_rows)}

<h2>Layer A — practice participation summary, Week 10 (2026)</h2>
<p class="small">Every club whose table could be transcribed without guessing. A club marked as partial is listed with the
reason in the partial-tables table below.</p>
{table(["Club", "Abbr", "Rows", "Full", "Limited", "Did not participate", "Blank", "Coverage", "Source"], prac_rows)}

<h2>Layer A — practice participation, row by row</h2>
{table(["Club", "Abbr", "Player", "Pos", "Injury", "Practice status", "Game status", "Source"], detail_rows)}

<h2>Tables that could not be transcribed without guessing</h2>
{table(["Club", "Why the table is incomplete", "Rows that were read", "Source"], partial_rows)}

<h2>Layer B — official Game Book evidence: starters, non-participation and substitutes</h2>
<p class="small">{esc(b.get("meta", {}).get("title", ""))}. {esc(b.get("meta", {}).get("extractionNote", ""))}</p>
{table(["Club", "Offensive starters (official)", "Defensive starters (official)", "Did not play (official)",
        "Substitutions", "Source"], depth_rows) if depth_rows else '<p class="small">—</p>'}

<h2>Layer B — final individual statistics from the same Game Book</h2>
{table(["Club", "Category", "Official row", "Column order", "Source"], stat_rows)}

<h2>Layer C — depth-tier rules</h2>
{table(["Tier", "Definition", "Evidence required", "Note", "Basis"], rules)}

<div class="callout flag"><strong>The documented three-deep replacement.</strong> In the November 9, 2026 Game Book the Vikings'
listed quarterback K. Murray is in the Did Not Play block, the listed starting quarterback C. Wentz started, and the listed
substitute quarterback M. Brosmer also threw for 58 yards in the same game. The same structure is visible on the receiving
side: J. Jennings is in the Did Not Play block, J. Addison started, and M. Price started in the third wide receiver slot.
Every one of those statements is read from the official Game Book — none of it is a depth-chart guess.</div>

<h2>Design of the tracker</h2>
<ul class="clean">
<li><strong>Capture.</strong> Fetch the weekly injury report and the Game Book for every completed game; store each with its own retrieval timestamp and its source URL. The records behind this page are in <code>data/lab/</code> in that shape.</li>
<li><strong>Reconcile.</strong> Where two official pages disagree, publish both readings and flag the difference. Never reconcile silently.</li>
<li><strong>Label.</strong> Apply the layer C rules to the Game Book evidence only. A tier is never inferred from an injury status.</li>
<li><strong>Feed.</strong> The output is a per-position availability and depth table with the official source on every row, ready to be joined with a price feed when one exists.</li>
<li><strong>Refresh.</strong> Automation of this refresh is the open suggestion P12; the records on this page were captured by hand from the official pages on 2026-11-13.</li>
</ul>
"""
    write(os.path.join(LAB, "injuries.html"), page("Injuries and depth", "injuries.html", body))


# ---------------------------------------------------------------- leaderboard
def build_leaderboard():
    lb = SPEC.get("leaderboard", {})
    head = ["Rank", "Strategy", "Type", "Bets resolved", "Log loss vs market", "Brier vs market", "Calibration",
            "Evidence gate", "Last updated", "Notes"]
    empty_rows = []
    for i in range(3):
        empty_rows.append([esc(i + 1), '<span class="small">—</span>', '<span class="small">—</span>',
                           '<span class="small">—</span>', '<span class="small">—</span>', '<span class="small">—</span>',
                           '<span class="small">—</span>', tag("not started", "tag est"), '<span class="small">—</span>',
                           '<span class="small">no qualifying strategy</span>'])
    body = f"""
<h1>Strategy leaderboard</h1>
<p class="lede">The competition design, and the reason its table is empty. The rules are fixed before any strategy is traded,
so that the board measures skill rather than the order in which variants were tried.</p>

<div class="callout flag"><strong>Mode: {esc(lb.get('mode', 'paper only'))}.</strong>
{esc(lb.get('modeReason', ''))}</div>

<h2>Eligibility</h2>
<ul class="clean">{''.join(f"<li>{esc(x)}</li>" for x in lb.get('eligibility', []))}</ul>

<h2>What is scored</h2>
<p><strong>Primary metric:</strong> {esc(lb.get('primaryMetric', ''))}</p>
<p><strong>Secondary metrics:</strong> {esc(", ".join(lb.get('secondaryMetrics', [])))}</p>

<h2>How luck is kept out</h2>
<ul class="clean">{''.join(f"<li>{esc(x)}</li>" for x in lb.get('antiLuckRules', []))}</ul>

<h2>Rewards</h2>
<p>{esc(lb.get('rewardBasis', ''))}</p>

<h2>Audit rules</h2>
<ul class="clean">{''.join(f"<li>{esc(x)}</li>" for x in lb.get('auditRules', []))}</ul>

<h2>The board</h2>
{table(head, empty_rows)}
<div class="callout">{esc(lb.get('rowsNote', ''))}</div>

<h2>Minimum evidence that each row would have to clear</h2>
<p class="small">Computed on the <a href="correlations.html">correlations page</a>: at a -110 price a true win rate of 57.38%
needs 779 resolved bets to be distinguishable from luck at 95% confidence and 80% power; 55.38% needs 2,170. A strategy
claiming a smaller edge needs proportionally more bets, and the row would say so.</p>

<h2>Where the entry conditions come from</h2>
{table(["ID", "Gate", "What it requires", "Why it exists", "Failure action", "Evidence", "Basis"], [
    [esc(g["id"]), f"<strong>{esc(g['name'])}</strong>", esc(g["requirement"]), esc(g["why"]), esc(g["failureAction"]),
     esc(g["evidence"]), src(g.get("basisUrl"), "basis")] for g in SPEC.get("gates", [])])}
"""
    write(os.path.join(LAB, "leaderboard.html"), page("Leaderboard", "leaderboard.html", body))


# ---------------------------------------------------------------- suggestions
def build_suggestions():
    rows = []
    for p in SPEC.get("suggestions", []):
        rows.append([
            esc(p["id"]),
            f"<strong>{esc(p['title'])}</strong>",
            tag(p["area"], "tag nfl" if p["area"] == "analytics" else "tag"),
            esc(p["problem"]),
            esc(p["proposal"]),
            esc(p["impact"]), esc(p["effort"]), esc(p["risk"]), esc(p["dependencies"]),
            esc(p["priority"]),
            tag(p["recommendation"], "tag ver" if p["recommendation"].startswith("accept") else "tag est"),
            srcs(p.get("sources", [])),
        ])
    body = f"""
<h1>Suggestions — what to change, and in what order</h1>
<p class="lede">Every improvement to this site and to this system, in one place, with the problem it solves, the evidence
behind it, the cost, the risk and the recommendation. The point of this page is that a decision can be made <em>before</em>
any code is written: read the list, tick the rows you want, and the build order follows.</p>

<div class="callout"><strong>How to use this page.</strong> The <em>Recommendation</em> column is this session's suggested
path, not a decision. The <em>Decision</em> column in the review sheet below is where a reviewer records Accept, Defer or
Reject with a note. Rows marked “already implemented in this release” need no decision — they are live on this site and can
be reviewed on the page they point to.</div>

<h2>Review sheet</h2>
<p class="small">Print or copy this table into your own notes. A row with a decision recorded is ready to build; a row with no
decision is still open. Nothing here blocks the site.</p>
{table(["ID", "Suggestion", "Area", "Impact", "Effort", "Risk", "Priority", "Recommendation", "Decision (Accept / Defer / Reject)", "Reviewer note"], [
    [esc(p["id"]), f"<strong>{esc(p['title'])}</strong>", esc(p["area"]), esc(p["impact"]), esc(p["effort"]), esc(p["risk"]),
     esc(p["priority"]), esc(p["recommendation"]), '<span class="small">—</span>', '<span class="small">—</span>']
    for p in SPEC.get("suggestions", [])])}

<h2>Full register</h2>
{table(["ID", "Suggestion", "Area", "Problem it solves", "Proposal", "Impact", "Effort", "Risk", "Dependencies", "Priority",
        "Recommendation", "Sources"], rows)}

<h2>Recommended build order</h2>
<ol class="clean">
<li><strong>Decide the two blockers.</strong> Q01 and Q05 on the <a href="questions.html">decision register</a>: which prices
are legally accessible, and where historical lines come from. Nothing measurable can happen before these are answered.</li>
<li><strong>Ship the cheap site wins.</strong> P01 to P05, P13 — decision headers, a reachable flagged page, one filter box,
per-table freshness, a vacation comparison view, and JSON beside every table.</li>
<li><strong>Automate the tracker.</strong> P12 — the injury and depth records are only useful if they refresh; the repository
already refreshes schedule feeds from official endpoints in CI.</li>
<li><strong>Build the measurement layer.</strong> P11 — the quote and settlement archive, then backtests with the published
gates, then the paper trial.</li>
<li><strong>Only then open the board.</strong> A strategy enters the leaderboard when it has cleared G0 to G8. Not before.</li>
</ol>
"""
    write(os.path.join(LAB, "suggestions.html"), page("Suggestions", "suggestions.html", body))


# ---------------------------------------------------------------- flags
def build_flags():
    rows = [[esc(f["id"]), tag(f["severity"], "tag high" if f["severity"] == "high" else "tag flag"), esc(f["area"]),
             esc(f["finding"]), esc(f["action"]), srcs(f.get("sources", []))]
            for f in SPEC.get("flags", [])]
    body = f"""
<h1>Flagged for Review — NFL Lines Lab</h1>
<p class="lede">Everything in this section is published on purpose. These are the unconfirmed, the incomplete, the
contradictory and the not-yet-known. None of it blocks the site, and none of it has been silently filled in. The planner's
own register of earlier irregularities is on the <a href="../flagged.html">main flagged page</a>.</p>
{table(["ID", "Severity", "Area", "Finding", "How it is handled on this site", "Sources"], rows)}
<p class="small">Flagged items do not block the merge or the deployment. They are listed so that they can be reviewed and
corrected later.</p>
"""
    write(os.path.join(LAB, "flags.html"), page("Flagged for Review", "flags.html", body))


# ---------------------------------------------------------------- retained entry points
# The NFL lines surface was published in parallel by two earlier sessions
# (arena/8602d76f and arena/c9041d2a). Their pages are kept as addresses so no
# link breaks, and each one now points at the lab page that carries the same
# content plus the official records and the measured numbers.
LEGACY_PAGES = [
    ("nfl-lines.html", "NFL Lines Origination", "The landing page for the NFL lines work.",
     "lab/index.html", "NFL Lines Lab"),
    ("nfl-strategies.html", "NFL Strategies", "The strategy catalogue and its validation gates.",
     "lab/strategies.html", "Strategies and gates"),
    ("nfl-correlation.html", "NFL Correlation", "Dependence between candidate legs.",
     "lab/correlations.html", "Correlations"),
    ("nfl-injuries.html", "NFL Injuries", "Injury and depth tracking.",
     "lab/injuries.html", "Injuries and depth"),
    ("nfl-questions.html", "NFL Questions", "The pre-decision question register.",
     "lab/questions.html", "Decision register"),
    ("nfl-suggestions.html", "NFL Suggestions", "The improvement register.",
     "lab/suggestions.html", "Suggestions"),
    ("nfl-executive-summary.html", "NFL Executive Summary", "The written summary of the lines work.",
     "research/NFL-LINES.md", "Line-origination research notes"),
    ("nfl-flagged.html", "NFL Flagged for Review", "The lines-work irregularities register.",
     "lab/flags.html", "Flagged for Review"),
    ("decisions.html", "Decisions", "The decisions that have to be answered first.",
     "lab/questions.html", "Decision register"),
    ("suggestions.html", "Suggestions", "The improvement register.",
     "lab/suggestions.html", "Suggestions"),
]


def build_legacy():
    for name, title, what, target, target_label in LEGACY_PAGES:
        body = f"""
<h1>{esc(title)}</h1>
<p class="lede">{esc(what)} This page is now part of the <strong>NFL Lines Lab</strong>. The content lives in one place,
with the official records behind it and every row linked to its source.</p>
<div class="callout"><strong>Where it moved.</strong> The live version of this material is on the
<a href="{esc(target)}">{esc(target_label)}</a> page. The lab version adds the official NFL records the earlier pages
could only describe: the published Week 10 injury report, official player game logs, and the official Game Book, plus the
measured correlations, dispersion figures and minimum-sample rules computed from them.</div>
<div class="grid g3">
<div class="card"><h3>Lab home</h3><p>Headline findings and the official sources behind them.</p>
<a href="lab/index.html">Open →</a></div>
<div class="card"><h3>Decision register</h3><p>What is known, what is missing, what blocks each decision, how to close it.</p>
<a href="lab/questions.html">Open →</a></div>
<div class="card"><h3>Strategies and gates</h3><p>Twelve candidate signals and the nine gates each must pass.</p>
<a href="lab/strategies.html">Open →</a></div>
<div class="card"><h3>Correlations</h3><p>Measured dependence between legs, with intervals and sample sizes.</p>
<a href="lab/correlations.html">Open →</a></div>
<div class="card"><h3>Injuries and depth</h3><p>The official injury report, the official Game Book and the tier rules.</p>
<a href="lab/injuries.html">Open →</a></div>
<div class="card"><h3>Suggestions and flags</h3><p>What to change and in what order; everything that is still unverified.</p>
<a href="lab/suggestions.html">Suggestions →</a> · <a href="lab/flags.html">Flagged →</a></div>
</div>
<p class="small">Written research: <a href="research/NFL-LINES.md">line-origination notes</a> ·
<a href="research/NFL-LINES-LAB.md">NFL Lines Lab notes</a> · <a href="research/NFL-STRATEGY.md">strategy notes</a> ·
<a href="research/EXECUTIVE-SUMMARY.md">executive summary</a></p>
"""
        write(name, page(title, "", body, root=True))

# ---------------------------------------------------------------- retained entry point
def build_stub():
    body = f"""
<h1>NFL Lines Lab</h1>
<p class="lede">This page now points into the <strong>NFL Lines Lab</strong>, a full section of the site rather than a single
page. The research notes it was built from are kept, and the work it described now has a home with tables, sources and a
flagged register.</p>
<div class="grid g3">
<div class="card"><h3>Lab home</h3><p>Headline findings, what the lab is and is not, and the official sources behind it.</p>
<a href="lab/index.html">Open the lab →</a></div>
<div class="card"><h3>Decision register</h3><p>What is known, what is missing, why it blocks, and how to close it.</p>
<a href="lab/questions.html">Questions →</a></div>
<div class="card"><h3>Strategies and gates</h3><p>Twelve candidate signals and the gates each must pass.</p>
<a href="lab/strategies.html">Strategies →</a></div>
<div class="card"><h3>Correlations</h3><p>Measured dependence, dispersion and the sample size luck demands.</p>
<a href="lab/correlations.html">Correlations →</a></div>
<div class="card"><h3>Injuries and depth</h3><p>The official weekly report and the Game Book, with the tier rules.</p>
<a href="lab/injuries.html">Tracker →</a></div>
<div class="card"><h3>Leaderboard and suggestions</h3><p>The competition rules and the improvement register.</p>
<a href="lab/leaderboard.html">Leaderboard →</a> · <a href="lab/suggestions.html">Suggestions →</a></div>
</div>
<p class="small">Earlier notes: <a href="research/NFL-STRATEGY.md">NFL strategy research</a> ·
<a href="research/NFL-LINES-LAB.md">NFL Lines Lab research notes</a> · <a href="research/EXECUTIVE-SUMMARY.md">Executive summary</a>
· <a href="lab/flags.html">Flagged for Review</a></p>
"""
    write("nfl-strategy.html", page("NFL Lines Lab", "", body, root=True))


CSS = """/* NFL Lines Lab — additions on top of assets/style.css */
.nav-sep{color:var(--muted);padding:0 4px;align-self:center}
.lab-nav{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:0 0 18px}
.lab-nav a{display:inline-block;padding:4px 8px;border-radius:8px;font-size:13px;font-weight:600;color:var(--ink);text-decoration:none}
.lab-nav a:hover{background:var(--accent);color:#052015}
td code{font-size:12px}
table td{vertical-align:top}
.reco-accept{background:rgba(60,200,120,.08)}
"""

with open(os.path.join(ASSETS, "lab.css"), "w", encoding="utf-8") as fh:
    fh.write(CSS)

build_index()
build_questions()
build_strategies()
build_correlations()
build_injuries()
build_leaderboard()
build_suggestions()
build_flags()
build_stub()
build_legacy()

print(json.dumps({
    "labPages": len([f for f in os.listdir(LAB) if f.endswith(".html")]),
    "questions": len(SPEC.get("questions", [])),
    "strategies": len(SPEC.get("strategies", [])),
    "gates": len(SPEC.get("gates", [])),
    "suggestions": len(SPEC.get("suggestions", [])),
    "labFlags": len(SPEC.get("flags", [])),
    "injuryRows": sum(len(t["rows"]) for t in INJ.get("practice", {}).values()),
    "gameStatusRows": len(INJ.get("gameStatus", [])),
    "correlations": len(ANA.get("correlations", [])),
    "legacyPointerPages": len(LEGACY_PAGES),
}, indent=1))
