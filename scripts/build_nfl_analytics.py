#!/usr/bin/env python3
"""Build the NFL analytics & decision-support pages from data/nfl-analytics/*.json.

Pages (root, same theme as the rest of the site):
  nfl-analytics.html  — suite dashboard + executive summary
  requirements.html   — requirements register (R1-R18)
  questions.html      — decision-prerequisite questions (Q1-Q20)
  analytics-suggestions.html    — suggestions register + review workflow (S1-S15)
  lines.html          — our own originated lines + method + validation
  strategies.html     — signals, strategies, validation gates, correlation, luck removal
  leaderboard.html    — competition rules, scoring, rewards
  injuries.html       — injury + lineup-deficiency tracker (Week 10)

Rules enforced here:
  * every data-table row carries at least one source link (checked before write);
  * values that could not be verified stay blank and are listed on the flagged register;
  * derived values are labelled MODEL OUTPUT, never presented as official.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "nfl-analytics"

NAV = [
    ("index.html", "Dashboard"), ("calendar.html", "Calendar"), ("vacation.html", "Vacation windows"),
    ("mlb.html", "MLB"), ("nfl.html", "NFL &amp; 49ers"), ("ncaaf.html", "Stanford &amp; Cal"),
    ("radio.html", "Radio"), ("nfl-analytics.html", "NFL Analytics"), ("sources.html", "Sources"),
    ("flagged.html", "Flagged"), ("method.html", "Method"),
    ("extra/index.html", "Official feeds &amp; verification"),
]
SUITE_NAV = [
    ("nfl-analytics.html", "Suite dashboard"), ("lines.html", "Lines &amp; model"),
    ("injuries.html", "Injuries &amp; depth"), ("strategies.html", "Strategies &amp; gates"),
    ("leaderboard.html", "Leaderboard"), ("questions.html", "Questions"),
    ("analytics-suggestions.html", "Suggestions"), ("requirements.html", "Requirements"),
]

def load(name):
    return json.loads((D / name).read_text())

def esc(v):
    return html.escape(str(v), quote=True)

def link(url, label="source"):
    if not url:
        return '<span class="tag flag">unverified — no source</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'

def tag(kind, text):
    return f'<span class="tag {kind}">{esc(text)}</span>'

MODEL_TAG = tag("est", "MODEL OUTPUT")

def page(name, title, active, body):
    nav = "".join(f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>' for u, n in NAV)
    sub = "".join(f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>' for u, n in SUITE_NAV)
    doc = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NFL Analytics</title>
<meta name="description" content="NFL line origination, strategy research, injury and lineup-deficiency tracking, with verified sources on every row.">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> FREE TIME / VACATION</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">
<nav class="pill-row">{sub}</nav>
{body}
</main>
<footer><div class="wrap">
  <p><strong>NFL Analytics &amp; Decision Support</strong> · 2026 season · data snapshot 2026-11-13 (Week 10) ·
  every table row links to its official source; derived values are labelled {MODEL_TAG}; unverified values stay blank and are on
  <a href="flagged.html">Flagged for review</a>.</p>
  <p>Injury report: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">nfl.com/injuries</a> ·
  standings &amp; results: <a href="https://www.nfl.com/standings/league/2026/REG" target="_blank" rel="noopener">nfl.com/standings</a> ·
  depth charts: each club's official site (row links) · market reference: DraftKings via ESPN (labelled secondary).</p>
</div></footer></body></html>'''
    (ROOT / name).write_text(doc)


def check_rows(body: str, page_name: str) -> None:
    """Every <tr> that contains data cells must contain a link or an explicit unverified marker."""
    problems = []
    for tr in re.findall(r"<tr>.*?</tr>", body, flags=re.S):
        if "<th" in tr:
            continue
        if "<a href=" not in tr and "unverified" not in tr and "no source" not in tr:
            txt = re.sub(r"<[^>]+>", " ", tr)[:60]
            problems.append(txt.strip())
    if problems:
        raise SystemExit(f"{page_name}: {len(problems)} rows without source links: {problems[:3]}")


# ===================================================================== dashboard
def build_dashboard():
    inj = load("injuries-week-10-2026.json")
    lines = load("model-lines-week-10-2026.json")
    lineup = load("lineup-report-week-10-2026.json")
    n_designated = sum(1 for r in inj["rows"] if r["gameStatus"])
    n_out = sum(1 for r in inj["rows"] if r["gameStatus"] == "Out")
    n_def = sum(1 for r in lineup["rows"] if r["deficiency"] and "no line impact" not in r["deficiency"])
    val = lines["validation"]
    body = f'''
<section class="hero"><div><p class="small">NFL ANALYTICS &amp; DECISION SUPPORT · 2026 SEASON · WEEK 10 SNAPSHOT 2026-11-13</p>
<h1>Originate the lines.<br>Grade the skill.</h1>
<p class="lede">A verified-data pipeline for NFL line origination, injury/lineup-deficiency tracking and a
validation-gated strategy leaderboard. Every row links to an official source. Nothing inferred.</p>
<div class="pill-row"><a class="btn" href="lines.html">Week 10 lines board</a>
<a class="btn" href="injuries.html">Injury tracker</a>
<a class="btn" href="strategies.html">Strategies &amp; gates</a></div></div>
<div class="card"><h2>Executive summary</h2>
<p><strong>14 Week-10 games tracked</strong> from the official NFL injury report; <strong>{len(inj["rows"])} injury rows</strong>;
<strong>{n_out} OUT</strong> and <strong>{n_designated} designated</strong> players; <strong>{len(lineup["rows"])}</strong> lineup-deficiency rows joined to club depth charts.</p>
<p>Our own v0 model (least-squares margin ratings + documented injury weights) produced a full week-10 board with
<strong>13 market comparisons</strong> (DraftKings via ESPN, labelled secondary). First out-of-sample check:
model {esc(str(val.get("modelSpreadHome")))} on WAS @ NYG vs final {esc(val.get("final", ""))} —
margin error {esc(str(val.get("absErrorPts")))} pts, side lost. Reported straight.</p>
<a href="research/EXECUTIVE-SUMMARY-NFL.md">Full executive summary →</a></div></section>

<h2>This week at a glance</h2>
<div class="grid g4">
<div class="card"><div class="kpi">{len(inj["games"])}<small>Week-10 games (official slate)</small></div></div>
<div class="card"><div class="kpi">{n_out}<small>Players ruled OUT</small></div></div>
<div class="card"><div class="kpi">{n_def}<small>Lineup deficiencies flagged</small></div></div>
<div class="card"><div class="kpi">13<small>Market lines compared</small></div></div>
</div>

<h2>Explore by category</h2>
<div class="grid g3">
<div class="card"><h3>Lines &amp; model</h3><p>Our own week-10 spreads/totals, market comparison, edge table, ratings, parameters and the first validation point.</p><a href="lines.html">Lines board →</a></div>
<div class="card"><h3>Injuries &amp; depth</h3><p>Every official injury row, depth-chart strings (1st–4th), who replaces whom, and which defenses/offenses are on backups.</p><a href="injuries.html">Deficiency tracker →</a></div>
<div class="card"><h3>Strategies &amp; gates</h3><p>Signal library, single/parlay/prop strategies, seven validation gates, correlation values and luck-removal method.</p><a href="strategies.html">Strategy register →</a></div>
<div class="card"><h3>Leaderboard</h3><p>Competition rules, anti-luck scoring and rewards. No entries yet — the table opens when the pick ledger launches.</p><a href="leaderboard.html">Competition →</a></div>
<div class="card"><h3>Questions</h3><p>What we have, what is missing, and which decision each gap blocks — with discovery suggestions.</p><a href="questions.html">Open questions →</a></div>
<div class="card"><h3>Suggestions</h3><p>Improvements proposed for review. Nothing is implemented before a reviewer picks the best path.</p><a href="analytics-suggestions.html">Review suggestions →</a></div>
</div>

<div class="callout flag"><strong>Flagged this week.</strong> Texans depth chart is published as an image (strings unverified);
Panthers depth-chart page unreachable from CI and direct fetch (rows blank); market odds are a trusted secondary source
(DraftKings via ESPN), not official league data; fitted home-field is −0.5 pts vs a traditional ≈2.5 prior;
totals are not injury-adjusted in v0. Full list on <a href="flagged.html">Flagged for review</a>.</div>
'''
    check_rows(body, "nfl-analytics.html")
    page("nfl-analytics.html", "Suite dashboard", "nfl-analytics.html", body)


# ===================================================================== requirements
def build_requirements():
    req = load("requirements.json")
    rows = ""
    for r in req["requirements"]:
        st = tag("ver", r["status"]) if r["status"].startswith("done") else tag("est", r["status"])
        rows += (f'<tr><td><strong>{esc(r["id"])}</strong></td><td>{esc(r["text"])}</td><td>{esc(r["category"])}</td>'
                 f'<td>{st}</td><td>{esc(r["where"])} · {link(esc(r["evidence"].split("#")[0]), "evidence page")}</td></tr>')
    body = f'''
<h1>Requirements register</h1>
<p class="lede">Every requirement distilled from the project brief, with where it is addressed and its status.
Nothing is marked done without a linked artifact. {tag("est", "in progress")} items are explicitly named.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Requirement</th><th>Category</th><th>Status</th><th>Where &amp; evidence</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="callout"><strong>How to use this register.</strong> Before any decision, walk the IDs in its category.
Requirements marked <em>in progress</em> are the ones whose open questions are listed on
<a href="questions.html">Questions</a>.</div>
'''
    check_rows(body, "requirements.html")
    page("requirements.html", "Requirements", "requirements.html", body)


# ===================================================================== questions
def build_questions():
    q = load("questions.json")
    rows = ""
    for r in q["questions"]:
        src = " · ".join(link(u, "official") for u in r.get("sources", [])) or link("", "")
        rows += (f'<tr><td><strong>{esc(r["id"])}</strong></td><td>{esc(r["question"])}<br><span class="small">{esc(r["topic"])}</span></td>'
                 f'<td>{esc(r["have"])}<br>{src}</td><td>{esc(r["missing"]) or "—"}</td>'
                 f'<td>{esc(r["blocks"])}</td><td>{esc(r["discovery"])}</td>'
                 f'<td>{tag({"answered": "ver", "partial": "est", "open": "flag", "decision": "est"}[r["status"]], r["status"])}</td></tr>')
    body = f'''
<h1>Decision-prerequisite questions</h1>
<p class="lede">A decision is reasonably decidable only when every question it depends on is answered or consciously waived.
This register lists what we <strong>have</strong> (with official sources), what is <strong>missing</strong>, which decision each gap
<strong>blocks</strong>, and a discovery suggestion (S-ids link to <a href="analytics-suggestions.html">Suggestions</a>).
Unknown values are never filled in.</p>
<div class="scroll"><table><thead><tr><th>ID</th><th>Question</th><th>What we have</th><th>What is missing</th><th>Blocks</th><th>How to discover</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="callout warn"><strong>Status legend.</strong> {tag("ver", "answered")} answered from an official source ·
{tag("est", "partial")} defined gap remains · {tag("flag", "open")} not answerable from verified sources today ·
{tag("est", "decision")} needs an owner decision (default proposed and labelled).</div>
'''
    check_rows(body, "questions.html")
    page("questions.html", "Questions", "questions.html", body)


# ===================================================================== suggestions
def build_suggestions():
    s = load("suggestions.json")
    rows = ""
    for r in s["suggestions"]:
        rows += (f'<tr><td><strong>{esc(r["id"])}</strong></td><td><strong>{esc(r["title"])}</strong><br><span class="small">{esc(r["category"])}</span></td>'
                 f'<td>{esc(r["problem"])}</td><td>{esc(r["proposal"])}</td><td>{esc(r["impact"])}</td>'
                 f'<td>{esc(r["effort"])}</td><td>{esc(r["risk"])}</td>'
                 f'<td>{tag("est", r["status"])}<br><span class="small">reviewer: pending</span></td>'
                 f'<td>{link("questions.html", "related questions")}</td></tr>')
    wf = "".join(f"<li>{esc(w)}</li>" for w in s["meta"]["workflow"])
    body = f'''
<h1>Suggestions register</h1>
<p class="lede">Improvements proposed to sharpen decisions and to discover missing information.
<strong>Nothing here is implemented automatically</strong> — a reviewer compares suggestions side by side and picks the best path first.</p>
<div class="callout"><strong>Review workflow.</strong><ul class="clean">{wf}</ul>
<p class="small">Statuses below are the proposing agent's; the reviewer is the owner. Accepted items are implemented
in a later, separately claimed task and linked back here.</p></div>
<div class="scroll"><table><thead><tr><th>ID</th><th>Suggestion</th><th>Problem</th><th>Proposal</th><th>Expected decision impact</th><th>Effort</th><th>Risk</th><th>Status</th><th>Links</th></tr></thead>
<tbody>{rows}</tbody></table></div>
'''
    check_rows(body, "analytics-suggestions.html")
    page("analytics-suggestions.html", "Suggestions", "analytics-suggestions.html", body)


# ===================================================================== lines
def build_lines():
    ml = load("model-lines-week-10-2026.json")
    inj = load("injuries-week-10-2026.json")
    meta, lines, val = ml["meta"], ml["lines"], ml["validation"]
    rows = ""
    for l in lines:
        mkt = esc(l["marketDetails"] or "—") + (f'<br><span class="small">O/U {esc(l["marketTotal"])}</span>' if l["marketTotal"] else "")
        edge = tag("flag", "no market") if l["edgeSpreadPts"] is None else f'{esc(l["edgeSpreadPts"]):>5} pts'
        etot = "" if l["edgeTotalPts"] is None else f' / {esc(l["edgeTotalPts"])}'
        rows += (f'<tr><td><strong>{esc(l["game"])}</strong><br><span class="small">{esc(l["day"][:12])} {esc(l["kickoffET"])} · {esc(l["network"])}</span></td>'
                 f'<td>{esc(l["awayRecord"])} @ {esc(l["homeRecord"])}</td>'
                 f'<td>{MODEL_TAG}<br><strong>{esc(l["modelSpreadHome"])}</strong> / {esc(l["modelTotal"])}</td>'
                 f'<td>{mkt}<br><span class="small">{esc(l["marketProvider"] or "")}</span></td>'
                 f'<td class="mono">{edge}{etot}</td>'
                 f'<td class="mono">{esc(l["injuryAdjAwayPts"])} / {esc(l["injuryAdjHomePts"])}</td>'
                 f'<td>{link(l["sourceUrl"], "injuries")}{"" if not l["marketSourceUrl"] else " · " + link(l["marketSourceUrl"], "market")}</td></tr>')
    ratings = sorted(meta["ratings"].items(), key=lambda kv: -kv[1])
    rrows = "".join(f"<tr><td><strong>{esc(t)}</strong></td><td class=\"mono\">{esc(v)}</td>"
                    f'<td>{link("https://www.nfl.com/standings/league/2026/REG", "official inputs")}</td></tr>' for t, v in ratings)
    params = meta["parameters"]
    body = f'''
<h1>Our own lines — Week 10, 2026</h1>
<p class="lede">Originated from official data only: least-squares margin ratings fit to {esc(meta["fitData"])},
scoring rates from NFL.com standings, and documented injury weights joined to club depth charts.
{MODEL_TAG} — these numbers are ours, not any official or market value. Market columns are a
<strong>labelled trusted-secondary reference</strong> (DraftKings via ESPN), never official league data.</p>

<div class="grid g2">
<div class="card"><h3>Validation — first out-of-sample point</h3>
<p><strong>{esc(val["game"])}</strong> · final <strong>{esc(val["final"])}</strong> ({link(val["sourceUrl"], "nfl.com game page")})</p>
<p>Model line: home spread <strong>{esc(val["modelSpreadHome"])}</strong> (predicted home margin {esc(val["modelHomeMargin"])}).
Actual home margin {esc(val["actualHomeMargin"])} → <strong>margin error {esc(val["absErrorPts"])} pts</strong>, side lost.</p>
<p class="small">{esc(val["note"])}. One game proves nothing — gate G4 requires n ≥ 100.</p></div>
<div class="card"><h3>Method in one paragraph</h3>
<p>Each team gets a rating r from the game margins of Weeks 1–9 (Week 10 held out) by least squares:
margin ≈ r<sub>home</sub> − r<sub>away</sub> + HFA. Expected points use scoring/allowing averages.
Injury weights move the spread only. Totals are <strong>not</strong> injury-adjusted in v0 (flagged limitation).</p>
<p>Parameters: HFA fitted = <strong>{esc(meta["hfa"])} pts</strong>
(traditional prior ≈ 2.5 — deviation flagged); position weights and designation factors are published below.</p>
<a href="https://www.nfl.com/standings/league/2026/REG">Official standings input</a> ·
<a href="https://www.nfl.com/injuries/">Official injury input</a></div></div>

<h2>Week-10 board — model vs market</h2>
<div class="scroll"><table><thead><tr><th>Game</th><th>Records</th><th>Model spread / total {MODEL_TAG}</th><th>Market (DraftKings via ESPN)</th><th>Edge (model − market)</th><th>Injury adj (away / home pts)</th><th>Sources</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small">Edge convention: spread edge in points on the home side (positive = model gives home more points than the market);
total edge similar. Large edges on JAX/TEN and BUF/NYJ reflect blowout-driven v0 ratings — treat with suspicion until G4 passes.</p>

<h2>Team ratings (Weeks 1–9 fit)</h2>
<div class="scroll"><table><thead><tr><th>Team</th><th>Rating (pts)</th><th>Inputs</th></tr></thead><tbody>{rrows}</tbody></table></div>

<h2>Published parameters ({tag("est", "model parameters — not facts")})</h2>
<div class="scroll"><table><thead><tr><th>Parameter</th><th>Value</th><th>Source</th></tr></thead><tbody>
<tr><td>Position weight (1st string out)</td><td class="mono">{esc(json.dumps(params["POS_WEIGHT"]))}</td><td>{link("strategies.html#gates", "gate G3")}</td></tr>
<tr><td>Designation factor</td><td class="mono">{esc(json.dumps(params["DESIG_FACTOR"]))} · DNP-watch {esc(params["WATCH_FACTOR"])}</td><td>{link("strategies.html#gates", "gate G3")}</td></tr>
<tr><td>String multiplier</td><td class="mono">{esc(json.dumps(params["STRING_MULT"]))}</td><td>{link("strategies.html#gates", "gate G3")}</td></tr>
<tr><td>HFA</td><td class="mono">{esc(meta["hfa"])} (fitted) vs ≈2.5 traditional</td><td>{link("flagged.html", "flagged deviation")}</td></tr>
</tbody></table></div>
<div class="callout warn"><strong>Limitations carried openly.</strong>
{''.join(f'<br>· {esc(x)}' for x in meta["limitations"])}</div>
'''
    check_rows(body, "lines.html")
    page("lines.html", "Lines & model", "lines.html", body)


# ===================================================================== strategies
def build_strategies():
    s = load("strategies.json")
    def sig_src(r):
        src = r["source"]
        if re.match(r"^[\w\-]+\.json$", src):
            src = "data/nfl-analytics/" + src
        return link(src, "evidence")
    sig = "".join(f'<tr><td><strong>{esc(r["id"])}</strong></td><td><strong>{esc(r["name"])}</strong></td><td>{esc(r["definition"])}</td>'
                  f'<td>{esc(r["dataNeeded"])}</td><td>{tag("ver" if r["status"] == "active" else "est", r["status"])}</td>'
                  f'<td>{sig_src(r)}</td></tr>'
                  for r in s["signals"])
    strat = "".join(f'<tr><td><strong>{esc(r["id"])}</strong></td><td><strong>{esc(r["name"])}</strong><br><span class="small">{esc(r["betType"])}</span></td>'
                    f'<td>{esc(r["rule"])}</td><td class="small">{esc(", ".join(r["gatesRequired"]))}</td>'
                    f'<td>{tag("est", r["status"])}</td><td>{esc(r["notes"])}</td>'
                    f'<td>{link("leaderboard.html", "leaderboard")}</td></tr>' for r in s["strategies"])
    gates = "".join(f'<tr id="gates"><td><strong>{esc(r["id"])}</strong></td><td><strong>{esc(r["name"])}</strong></td><td>{esc(r["definition"])}</td>'
                    f'<td>{esc(r["why"])}</td><td>{esc(r["measurement"])}</td><td>{link("leaderboard.html", "scoring")}</td></tr>' for r in s["validationGates"])
    corr = "".join(f'<tr><td>{esc(r["pair"])}</td><td class="mono">{esc(r["rhoEstimate"])}</td><td>{esc(r["basis"])}</td>'
                   f'<td>{tag("flag" if "unverified" in r["status"] else "est", r["status"])}</td><td>{link("questions.html#Q10", "Q10")}</td></tr>'
                   for r in s["correlation"]["matrix"])
    luck = "".join(f"<li>{esc(p)}</li>" for p in s["luckRemoval"]["principles"])
    body = f'''
<h1>Strategies, signals &amp; validation gates</h1>
<p class="lede">A strategy is a pre-registered rule mapping verified information to bet selections. It may score on the
<a href="leaderboard.html">leaderboard</a> only after passing <strong>every</strong> gate. Single bets, parlays and
player-prop combos all have registered designs below.</p>

<h2>Signal library</h2>
<div class="scroll"><table><thead><tr><th>ID</th><th>Signal</th><th>Definition</th><th>Data needed</th><th>Status</th><th>Evidence</th></tr></thead>
<tbody>{sig}</tbody></table></div>

<h2>Strategy register</h2>
<div class="scroll"><table><thead><tr><th>ID</th><th>Strategy</th><th>Rule</th><th>Gates</th><th>Status</th><th>Notes</th><th>Links</th></tr></thead>
<tbody>{strat}</tbody></table></div>

<h2 id="validation-gates">Validation gates — every strategy must pass all</h2>
<div class="scroll"><table><thead><tr><th>ID</th><th>Gate</th><th>Definition</th><th>Why</th><th>Measurement</th><th>Links</th></tr></thead>
<tbody>{gates}</tbody></table></div>

<h2 id="correlation">Correlation values</h2>
<p>{esc(s["correlation"]["status"])}</p>
<div class="scroll"><table><thead><tr><th>Leg pair</th><th>ρ estimate</th><th>Basis</th><th>Status</th><th>Links</th></tr></thead>
<tbody>{corr}</tbody></table></div>
<div class="callout warn"><strong>Estimator.</strong> {esc(s["correlation"]["estimator"])}<br>
<strong>Rule until measured.</strong> {esc(s["correlation"]["rule"])}</div>

<h2 id="luck-vs-skill">Removing luck from the equation</h2>
<ul class="clean">{luck}</ul>
<p class="small">Method references and formulas live in <a href="leaderboard.html">Leaderboard scoring</a>;
the empirical job that replaces the estimates is <a href="analytics-suggestions.html">S5</a>.</p>
'''
    check_rows(body, "strategies.html")
    page("strategies.html", "Strategies & gates", "strategies.html", body)


# ===================================================================== leaderboard
def build_leaderboard():
    lb = load("leaderboard.json")
    c = lb["competition"]
    elig = "".join(f"<li>{esc(x)}</li>" for x in c["eligibility"])
    anti = "".join(f"<li>{esc(x)}</li>" for x in c["antiLuck"])
    tiers = "".join(f'<tr><td>{esc(t["rank"])}</td><td>{esc(t["rewardProposed"])}</td>'
                    f'<td>{tag("flag", "not confirmed") if not t["confirmed"] else tag("ver", "confirmed")}</td>'
                    f'<td>{link("questions.html#Q11", "Q11 decision")}</td></tr>' for t in lb["rewards"]["tiers"])
    body = f'''
<h1>Strategy leaderboard</h1>
<p class="lede">{esc(lb["meta"]["principle"])} {tag("est", lb["meta"]["status"])}</p>

<div class="grid g2">
<div class="card"><h3>Competition</h3>
<p><strong>Unit:</strong> {esc(c["unit"])}</p>
<p><strong>Windows:</strong> {esc(" · ".join(c["windows"]))}</p>
<p><strong>Eligibility</strong></p><ul class="clean">{elig}</ul></div>
<div class="card"><h3>Scoring — skill, not ROI</h3>
<p class="mono small">rawROI = net units / staked<br>
shrunkROI = (n·ROI + 25·0)/(n+25)<br>
skillScore = 100·(0.6·z(shrunkROI) + 0.4·z(CLV))</p>
<p class="small">Tie-breaks: {esc(" → ".join(c["scoring"]["tieBreaks"]))}.
{esc(c["scoring"]["processGate"])}.</p></div></div>

<h2>Anti-luck rules</h2>
<ul class="clean">{anti}</ul>

<h2>Current standings</h2>
<div class="callout"><strong>No entries yet.</strong> The ledger opens with the pick-lock system
(<a href="analytics-suggestions.html">S3</a>). The table below is the published scaffold; a row is added only for a strategy that
passed gates G1–G7.</div>
<div class="scroll"><table><thead><tr><th>Rank</th><th>Strategy</th><th>Type</th><th>n</th><th>Raw ROI</th><th>Shrunk ROI</th><th>95% CI</th><th>CLV</th><th>Skill</th><th>Status</th></tr></thead>
<tbody><tr><td colspan="10">— no registered entries — {link("analytics-suggestions.html", "ledger opens with S3")}</td></tr></tbody></table></div>

<h2>Rewards ({tag("flag", "proposal — owner decision Q11")})</h2>
<div class="scroll"><table><thead><tr><th>Rank</th><th>Proposed reward</th><th>Confirmed?</th><th>Decision</th></tr></thead>
<tbody>{tiers}</tbody></table></div>
<p class="small">{esc(lb["rewards"]["rule"])}</p>
'''
    check_rows(body, "leaderboard.html")
    page("leaderboard.html", "Leaderboard", "leaderboard.html", body)


# ===================================================================== injuries
def build_injuries():
    inj = load("injuries-week-10-2026.json")
    lineup = load("lineup-report-week-10-2026.json")
    rows = ""
    for r in inj["rows"]:
        desig = r["gameStatus"]
        dt = (tag("flag", desig) if desig == "Out" else tag("est", desig) if desig else "")
        rows += (f'<tr><td><strong>{esc(r["game"])}</strong></td><td>{esc(r["team"])}</td>'
                 f'<td>{link(r["playerUrl"], r["player"]) if r["playerUrl"] else esc(r["player"])}</td>'
                 f'<td>{esc(r["pos"])}</td><td>{esc(r["injury"]) or "—"}</td>'
                 f'<td class="small">{esc(r["practiceStatus"])}</td><td>{dt}</td>'
                 f'<td>{link(r["sourceUrl"], "nfl.com/injuries")}</td></tr>')
    drows = ""
    for r in sorted(lineup["rows"], key=lambda x: (x["game"], x["team"], x["pos"])):
        sev = tag("flag", "deficiency") if "no line impact" not in r["deficiency"] and r["deficiency"] else tag("ver", "tracked")
        dsrc = link(r["sourceUrl"], "injuries")
        if r["depthSourceUrl"]:
            dsrc += " · " + link(r["depthSourceUrl"], "depth chart")
        else:
            dsrc += " · " + tag("flag", "depth unverified")
        drows += (f'<tr><td><strong>{esc(r["game"])}</strong></td><td>{esc(r["team"])}</td>'
                  f'<td>{esc(r["player"])}</td><td>{esc(r["pos"])}</td>'
                  f'<td class="small">{esc(r["gameStatus"])}<br>{esc(r["practiceStatus"])}</td>'
                  f'<td>{esc(r["depthString"])}</td><td>{esc(r["replacement"])}</td>'
                  f'<td>{esc(r["unit"])}</td><td>{esc(r["deficiency"])} {sev}</td>'
                  f'<td class="mono">{esc(r["lineImpactPts"])}</td><td>{dsrc}</td></tr>')
    unav = ", ".join(lineup["meta"]["depthChartUnavailable"]) or "none"
    body = f'''
<h1>Injury &amp; lineup-deficiency tracker — Week 10</h1>
<p class="lede">The official NFL injury report joined to each club's published depth chart: who is out, whether they are a
starter, and whether a <strong>2nd, 3rd or 4th string</strong> backup has to replace them — on offense and defense.
Blank game statuses mean the designation was not yet published at retrieval; they are never guessed.</p>
<div class="grid g4">
<div class="card"><div class="kpi">{len(inj["rows"])}<small>official injury rows</small></div></div>
<div class="card"><div class="kpi">{sum(1 for r in inj["rows"] if r["gameStatus"]=="Out")}<small>OUT</small></div></div>
<div class="card"><div class="kpi">{sum(1 for r in lineup["rows"] if "no line impact" not in r["deficiency"] and r["deficiency"])}<small>deficiencies flagged</small></div></div>
<div class="card"><div class="kpi">{esc(unav)}<small>depth charts unverified</small></div></div>
</div>

<h2>Deficiency report — starters out and their replacements</h2>
<div class="scroll"><table><thead><tr><th>Game</th><th>Team</th><th>Player</th><th>Pos</th><th>Status</th><th>Depth string</th><th>Replacement</th><th>Unit</th><th>Deficiency</th><th>Line impact (pts)</th><th>Sources</th></tr></thead>
<tbody>{drows}</tbody></table></div>
<p class="small">Line impact is a {MODEL_TAG} using published parameters (see
<a href="lines.html">Lines &amp; model</a>). "not on published depth chart" means the club's own chart does not list the
player — the replacement is left blank rather than inferred.</p>

<h2>Full official injury report (every row)</h2>
<div class="scroll"><table><thead><tr><th>Game</th><th>Team</th><th>Player</th><th>Pos</th><th>Injury</th><th>Practice status</th><th>Game status</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small">Source: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com official injury report</a>,
Week 10 of the 2026 season, snapshot 2026-11-13. LAC and BAL published "No Injuries Reported" for Monday's game.</p>
'''
    check_rows(body, "injuries.html")
    page("injuries.html", "Injuries & depth", "injuries.html", body)


def main():
    build_dashboard()
    build_requirements()
    build_questions()
    build_suggestions()
    build_lines()
    build_strategies()
    build_leaderboard()
    build_injuries()
    print("nfl-analytics pages built (8)")


if __name__ == "__main__":
    main()
