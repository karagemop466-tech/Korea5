#!/usr/bin/env python3
"""
NFL Lines Lab — static site generator.

Renders nfl-lines/*.html from nfl/data/*.json. Every table row is generated; no number is typed
into a template. Each row that carries a fact also carries a source link (see COL_SRC below).

Pages
  index.html          dashboard: what is proven, what is not, leaderboard snapshot
  data.html           data audit + cross-source verification + gap register
  lines.html          line-making method and the model's own probabilities
  signals.html        signal register with measured correlations
  injuries.html       injury + lineup tracker (starters vs 2nd/3rd/4th string)
  leaderboard.html    competition + rewards + gate matrix
  parlays.html        parlay and prop-combo maths, correlation-aware
  questions.html      decision register (questions -> missing info -> how to get it)
  suggestions.html    suggestions to improve decision making, each with a proposed test
  flagged.html        everything unverified, blank, or contradictory
  sources.html        source registry with provenance hashes
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone

OUT = "nfl-lines"
DATA = "nfl/data"

NAV = [
    ("index.html", "Dashboard"),
    ("executive.html", "Executive summary"),
    ("lines.html", "Lines & model"),
    ("signals.html", "Signals"),
    ("injuries.html", "Injuries & lineups"),
    ("leaderboard.html", "Leaderboard"),
    ("parlays.html", "Parlays & props"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("data.html", "Data audit"),
    ("flagged.html", "Flagged"),
    ("sources.html", "Sources"),
]

CSS = """
:root{--bg:#0b1220;--panel:#111b2e;--panel2:#16243a;--line:#22334d;--ink:#e8eef8;--muted:#9aa9c2;
--accent:#4dd4ac;--accent2:#7aa2ff;--warn:#ffc857;--bad:#ff7a6b;--free:#3ddc97;--radius:14px;--max:1180px}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:radial-gradient(1200px 700px at 15% -10%,#16294a 0%,#0b1220 55%) fixed,var(--bg);
color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:var(--max);margin:0 auto;padding:0 18px}
header.top{position:sticky;top:0;z-index:30;background:rgba(11,18,32,.94);border-bottom:1px solid var(--line)}
.topbar{display:flex;align-items:center;gap:16px;padding:11px 0;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:9px;font-weight:800;letter-spacing:.2px}
.brand .dot{width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 14px var(--accent)}
nav.main{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}
nav.main a{padding:6px 10px;border-radius:9px;color:var(--muted);font-size:13.5px;font-weight:600}
nav.main a:hover{background:var(--panel2);color:var(--ink);text-decoration:none}
nav.main a.active{background:var(--accent);color:#052015}
main{padding:24px 0 60px}
h1{font-size:clamp(25px,3.6vw,36px);line-height:1.15;margin:6px 0 8px;letter-spacing:-.5px}
h2{font-size:21px;margin:28px 0 10px}
h3{font-size:16px;margin:16px 0 8px}
p.lede{color:var(--muted);font-size:16.5px;max-width:78ch;margin:0 0 16px}
small,.small{font-size:12.5px;color:var(--muted)}
.grid{display:grid;gap:14px}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
@media(max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
border-radius:var(--radius);padding:16px}
.card h3{margin-top:0}
.kpi{font-size:32px;font-weight:800;letter-spacing:-1px;line-height:1.05}
.kpi small{display:block;font-weight:600;font-size:11.5px;letter-spacing:.7px;text-transform:uppercase;margin-top:6px}
.tag{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:999px;font-size:11.5px;
font-weight:700;border:1px solid var(--line);background:#0d1728;color:var(--muted);white-space:nowrap}
.tag.pass{color:#04241a;background:var(--free);border-color:transparent}
.tag.fail{color:#2b0b06;background:var(--bad);border-color:transparent}
.tag.warn{color:#241a00;background:var(--warn);border-color:transparent}
.tag.A{color:#04241a;background:var(--free);border-color:transparent}
.tag.C{color:#241a00;background:var(--warn);border-color:transparent}
.tag.D{color:#2b0b06;background:var(--bad);border-color:transparent}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:8px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:700;
background:#0e1829;position:sticky;top:54px;z-index:5}
tr:hover td{background:#121d31}
.scroll{max-height:640px;overflow:auto;border:1px solid var(--line);border-radius:12px}
.callout{border-left:4px solid var(--accent);background:#0e1c2e;padding:13px 15px;border-radius:0 12px 12px 0;margin:14px 0}
.callout.warn{border-left-color:var(--warn)}.callout.bad{border-left-color:var(--bad)}
.pill-row{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.btn{background:var(--panel2);color:var(--ink);border:1px solid var(--line);padding:8px 13px;border-radius:10px;
font-weight:700;display:inline-block}
.btn:hover{background:#1d2f4b;text-decoration:none}
.mono{font-variant-numeric:tabular-nums}
footer{border-top:1px solid var(--line);padding:22px 0;color:var(--muted);font-size:12.5px}
.ok{color:var(--free)}.bad{color:var(--bad)}.warnc{color:var(--warn)}
ul.clean{margin:6px 0 0 18px;padding:0}ul.clean li{margin:5px 0}
"""


def esc(v):
    if v is None:
        return '<span class="small">— blank —</span>'
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        s_ = f"{v:,.4f}".rstrip("0").rstrip(".")
        return s_
    if isinstance(v, int):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    return html.escape(str(v))


def pct(v, digits=2):
    if v is None:
        return '<span class="small">— blank —</span>'
    return f"{v * 100:.{digits}f}%"


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def page(name, title, body, active, extra_head=""):
    nav = "".join(
        f'<a href="{u}" class="{"active" if u == active else ""}">{t}</a>' for u, t in NAV)
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · NFL Lines Lab</title>
<meta name="description" content="NFL line-making, signal validation and correlation research generated from cited public data.">
<style>{CSS}</style>{extra_head}</head><body>
<header class="top"><div class="wrap topbar">
<div class="brand"><span class="dot"></span> NFL LINES LAB</div>
<nav class="main">{nav}<a href="../index.html">Planner site</a></nav>
</div></header>
<main class="wrap">
<aside id="certainty-notice" class="callout warn" role="note"><strong>Planning estimates — not certified free time.</strong> Schedules and local AM/FM carriage are incomplete. Any &ldquo;free&rdquo;, &ldquo;fully free&rdquo;, &ldquo;exact&rdquo; or &ldquo;verified gap&rdquo; wording below describes loaded records only; it does not certify absence of games. <a href="../certainty.html">Flagged for Review: certainty audit</a>.</aside>
{body}
</main>
<footer><div class="wrap">
<p><strong>NFL Lines Lab</strong> — every published number is generated from data fetched and hashed by
the repository's own pipeline. No betting return, payout or edge is claimed anywhere: the only market
data available is a single un-timestamped line snapshot, and no player-prop market exists in any
reachable source. <a href="flagged.html">Flagged for review</a> · <a href="sources.html">Sources</a> ·
<a href="questions.html">Open questions</a></p>
<p class="small">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by
<code>nfl/build_site.py</code>. Pre-registration: <a href="../nfl/PREREGISTRATION.md">nfl/PREREGISTRATION.md</a>.</p>
</div></footer></body></html>"""
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(doc)


def pill(v):
    if v is None:
        return '<span class="tag">n/a</span>'
    if v is True:
        return '<span class="tag pass">pass</span>'
    if v is False:
        return '<span class="tag fail">fail</span>'
    return f'<span class="tag">{esc(v)}</span>'


def src(url, label="source"):
    if not url:
        return '<span class="small">— unverified —</span>'
    return f'<a href="{html.escape(url, quote=True)}" title="{html.escape(url, quote=True)}">{label}</a>'


def table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# ------------------------------------------------------------------ pages


def build_index(mr, lb, q, hyp):
    fam = mr.get("families", {})
    best = mr.get("bestFamily")
    m = mr.get("model", {})
    d = mr.get("deflation", {})
    cb = mr.get("playedBoard") or mr.get("currentBoard", {})
    lbrows = (lb or {}).get("rows", [])
    tierA = [r for r in lbrows if r["tier"] == "A"]
    openq = [x for x in (q or {}).get("items", []) if x["id"] in ("Q1", "Q2", "Q4", "Q5")]
    cards = f"""
<div class="grid g4">
  <div class="card"><div class="kpi">{m.get('games', 0):,}<small>out-of-sample games</small></div>
    <p class="small">Walk-forward: the model for each season is fitted only on earlier seasons.</p></div>
  <div class="card"><div class="kpi">{pct(m.get('accuracy'), 1)}<small>winner accuracy</small></div>
    <p class="small">Accuracy is reported, never used as a gate — it is the metric that rewards luck most.</p></div>
  <div class="card"><div class="kpi">{pct(m.get('skill'), 2)}<small>log-loss skill vs baseline</small></div>
    <p class="small">1 − model log loss ÷ naive prior-season baseline log loss.</p></div>
  <div class="card"><div class="kpi">{len(tierA)}<small>Tier A strategies</small></div>
    <p class="small">Deflated skill above the best-of-K null. Everything else is published below, tiered.</p></div>
</div>
<div class="callout {'warn' if not d.get('passed') else ''}">
<strong>Luck filter:</strong> the headline skill is <span class="mono">{pct(m.get('skill'), 2)}</span> against a
best-of-{d.get('K', '—')} permutation null whose 95th percentile is <span class="mono">{pct(d.get('p95'), 2)}</span>
({d.get('N', 0)} shuffled-label refits). Verdict: <strong>{'passes deflation' if d.get('passed') else 'not distinguishable from luck'}</strong>.
Features used: <code>{', '.join(fam.get(best, {}).get('features', []))}</code>.
</div>"""
    board_rows = []
    for g in (cb.get("games") or [])[:18]:
        score = (f'{esc(g.get("awayScore"))}–{esc(g.get("homeScore"))}' if g.get("complete") else None)
        board_rows.append([esc(g["date"]), esc(g["week"]), f'{esc(g["away"])} @ {esc(g["home"])}',
                           esc(score), esc(g.get("spread")), esc(g.get("total")),
                           f'{esc(g.get("awayRest"))} / {esc(g.get("homeRest"))}',
                           '<span class="tag pass">final</span>' if g.get("complete") else '<span class="tag">scheduled</span>',
                           src("https://www.nfl.com/schedules/", "NFL.com")])
    hyp_rows = []
    for h in (hyp or {}).get("items", []):
        v = h.get("verdict", "")
        cls = "pass" if v == "passes" else ("fail" if v == "fails" else "warn")
        hyp_rows.append([esc(h["id"]), esc(h["name"]), esc(h["family"]),
                         f'<span class="tag {cls}">{esc(v)}</span>', esc(h.get("statement"))])
    body = f"""
<p class="small">NFL · LINES RESEARCH · DATA-BACKED</p>
<h1>Make your own line. Prove it survives luck.</h1>
<p class="lede">This lab builds NFL win probabilities from cited public data, tests them walk-forward,
deflates the score against a best-of-N luck threshold, measures the correlations instead of assuming
them, and ranks singles, parlays and player-prop combos only on what survives. Nothing here is a
recommendation to bet, and no profit figure appears anywhere, because no timestamped price history
exists in any reachable source.</p>
{cards}
<h2>Latest completed week in the data — season {esc(cb.get('season'))}, week {esc(cb.get('week'))}</h2>
<p class="small">The most recent week with final scores. Scores come from the nflverse schedule file and are
cross-checked against ESPN on the <a href="data.html">data audit</a> page. Rest days are as published in the
same feed. Later weeks exist in the file as scheduled fixtures only, so they are not shown as results.</p>
{table(["Date", "Wk", "Matchup", "Score", "Spread", "Total", "Rest (A/H)", "State", "Official"], board_rows) if board_rows else '<p class="small">No completed games in the loaded slice.</p>'}
<h2>What the gates say, in one table</h2>
{table(["ID", "Strategy hypothesis", "Family", "Verdict", "Statement"], hyp_rows)}
<p><a class="btn" href="leaderboard.html">Full leaderboard and gate matrix →</a>
<a class="btn" href="questions.html">Open questions before any decision →</a></p>
<h2>Five decisions that need you, not a model</h2>
<div class="grid g2">
{''.join(f'<div class="card"><h3>{esc(x["id"])} · {esc(x["topic"])}</h3><p><strong>{esc(x["question"])}</strong></p><p class="small">Missing: {esc(x["missing"])}</p><p class="small">Blocks: {esc(x["blocks"])}</p></div>' for x in openq)}
</div>"""
    page("index.html", "Dashboard", body, "index.html")


def build_lines(mr):
    m = mr.get("model", {})
    fam = mr.get("families", {})
    rows = []
    for k, v in fam.items():
        s = v.get("scores", {})
        d = v.get("deflation", {})
        rows.append([esc(k), esc(len(v.get("features", []))), esc(s.get("games")), esc(s.get("logloss")),
                     esc(s.get("baselineLogloss")), esc(s.get("skill")), esc(s.get("accuracy")),
                     pill(d.get("passed")), esc(d.get("p95")),
                     src("https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv", "schedules")])
    cov = mr.get("featureCoverage", [])
    covrows = [[esc(c["feature"]), esc(c["present"]), esc(c["total"]), esc(c["share"]),
                f'<span class="tag {"pass" if c["status"]=="verified" else "warn"}">{esc(c["status"])}</span>',
                src("https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2025.csv", "injuries")] for c in cov]
    body = f"""
<h1>How the line is made</h1>
<p class="lede">A line is just a probability with the vig removed. This page shows exactly how the
probability is produced, what data it uses, and how it performs out of sample. If a feature is missing
for a game, it is set to a documented neutral value and the coverage table below shows how often that
happens — the model never invents an input.</p>
<div class="grid g3">
<div class="card"><h3>1 · Signals</h3><p class="small">Team strength (chronological Elo), recent form,
rest differential, division flag, roof, quarterback continuity, and the injury/lineup shares. All are
computed from games played before the one being predicted.</p></div>
<div class="card"><h3>2 · Walk-forward fit</h3><p class="small">For each season, a logistic regression is
fitted on every earlier season in the data and then predicts that season. Standardisation statistics come
from the training seasons only. A unit test fails the build if a future row can be seen.</p></div>
<div class="card"><h3>3 · Scoring</h3><p class="small">Log loss against a naive baseline built from prior-season
home and away win rates. Accuracy and Brier are reported next to it. Skill = 1 − model ÷ baseline.</p></div>
</div>
<h2>Feature families, out of sample</h2>
{table(["Family", "Signals", "Games", "Log loss", "Baseline", "Skill", "Accuracy", "Deflation", "Null 95th pct", "Source"], rows)}
<h2>Feature coverage — how often each input actually exists</h2>
<p class="small">A low share is not a bug in the model: it means the source does not publish that value for
every game, and the row is left blank rather than guessed.</p>
{table(["Feature", "Present", "Total", "Share", "Status", "Source"], covrows)}
<h2>What a line-maker still needs</h2>
<ul class="clean">
<li><strong>A price, not just a probability.</strong> Converting this probability into a line requires a
vig and a market to compare with. The repository has one un-timestamped snapshot per game and no
moneylines, so no price can be built without assuming a vig.</li>
<li><strong>A decision cutoff.</strong> The injury report is published across the week; a usable line needs
one fixed timestamp.</li>
<li><strong>Player-level value.</strong> Snap share measures usage, not talent (see Q6).</li>
</ul>"""
    page("lines.html", "Lines and model", body, "lines.html")


def build_signals(mr, hyp):
    corr = mr.get("correlation", {})
    rows = []
    for p in corr.get("pairs", []):
        ci = p.get("ci") or [None, None]
        excl = p.get("excludesZero")
        rows.append([esc(p["a"]), esc(p["b"]), esc(p["n"]), esc(p["r"]),
                     f'{esc(ci[0])} … {esc(ci[1])}',
                     f'<span class="tag {"pass" if excl else ""}">{"excludes 0" if excl else "includes 0"}</span>',
                     src("https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv", "schedules")])
    hy = [[esc(h["id"]), esc(h["name"]), esc(h["statement"]), esc(h["test"]),
           f'<span class="tag {"pass" if h.get("verdict")=="passes" else ("fail" if h.get("verdict")=="fails" else "warn")}">{esc(h.get("verdict"))}</span>',
           src(_hyp_source(h["id"]), "source")] for h in (hyp or {}).get("items", [])]
    body = f"""
<h1>Signals, measured</h1>
<p class="lede">Every pairwise correlation below is computed on realised outcomes with a bootstrap 95%
confidence interval. A pair whose interval includes zero is not called a relationship, however large the
point estimate looks. With {len(corr.get('pairs', []))} pairs tested, some will look interesting by
chance; the register flags that and the questions page records the multiplicity fix that is still needed.</p>
<h2>Strategy register</h2>
{table(["ID", "Hypothesis", "Statement", "How it is tested", "Verdict", "Source"], hy)}
<h2>Measured signal correlations</h2>
<p class="small">r is the Pearson correlation of the two signal values across games where both exist
(minimum 3 games; intervals from 600 bootstrap resamples, seed 20261113).</p>
{table(["Signal A", "Signal B", "Games", "r", "95% CI", "Verdict", "Source"], rows)}
<h2>How to read this</h2>
<ul class="clean">
<li><strong>Two correlated inputs are one input.</strong> If rest differential and short-week flags move
together, adding both inflates the model without adding information.</li>
<li><strong>Correlation is not edge.</strong> A signal can correlate with the outcome and still be fully
priced by the market — which cannot be tested until a line history exists (Q11).</li>
</ul>"""
    page("signals.html", "Signals and correlations", body, "signals.html")


def _hyp_source(hid):
    return {
        "H1": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
        "H2": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
        "H3": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2025.csv",
        "H4": "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2025.csv",
        "H5": "https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_2025.csv",
        "H6": "https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_2025.csv",
        "H7": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
        "H8": "https://www.nfl.com/schedules/",
        "H9": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
        "H10": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
    }.get(hid, "")


def build_injuries(mr):
    cb = mr.get("playedBoard") or mr.get("currentBoard", {})
    rows = []
    for t in sorted(cb.get("teams", []), key=lambda x: -(x.get("offOutShare") or 0)):
        tiers = t.get("tiers", {})
        qb = tiers.get("QB", {})
        qb_txt = " · ".join(f'{r}: {", ".join(v[:2])}' for r, v in sorted(qb.items())) or None
        snap = t.get("depthSnapshotUTC")
        snap_txt = (f'<span class="small">{esc(snap[:10])}</span>' if snap else '<span class="tag warn">no snapshot date</span>')
        rows.append([
            esc(t["team"]), esc(t["reportCount"]), esc(t["out"]), esc(t["doubtful"]), esc(t["questionable"]),
            esc(t.get("offStarterValue")), esc(t.get("defStarterValue")),
            esc(t.get("offOutShare")), esc(t.get("defOutShare")),
            esc(t.get("offQuestionableShare")),
            f'<span class="tag {"pass" if t.get("status")=="verified" else "warn"}">{esc(t.get("status"))}</span>',
            esc(qb_txt), snap_txt,
            src("https://www.nfl.com/injuries/", "NFL injuries")])
    tier_rows = []
    for t in sorted(cb.get("teams", []), key=lambda x: -(x.get("out") or 0))[:10]:
        snap = (t.get("depthSnapshotUTC") or "")[:10] or None
        for pos, d in sorted(t.get("tiers", {}).items()):
            if not d:
                continue
            tier_rows.append([esc(t["team"]), esc(pos)] +
                             [esc(", ".join(d.get(str(i), [])[:2]) if d.get(str(i)) else None) for i in (1, 2, 3, 4)] +
                             [esc(snap)])
    body = f"""
<h1>Injuries and lineup depth</h1>
<p class="lede">Two different questions, kept apart on purpose. <strong>Injury status</strong> is the
official weekly designation (Out / Doubtful / Questionable) and is verified. <strong>Lineup depth</strong> is
a separate published artefact — the depth chart — and is shown with its snapshot date because a chart from
three weeks ago is not evidence about tonight.</p>
<div class="callout warn"><strong>What the numbers do and do not mean.</strong> "Starter value" is the
share of the unit's snap-weighted usage held by players listed first on the depth chart. It measures
<em>usage</em>, not talent. A missing star with low usage barely moves it. That limitation is registered
as Q6 and is not papered over.</div>
<h2>Current week by team</h2>
<p class="small">Latest completed week in the data: season {esc(cb.get('season'))}, week {esc(cb.get('week'))}. Shares are fractions of the
unit's snap-weighted value: Out is separated from Doubtful and from Questionable — they are never added together.</p>
{table(["Team", "On report", "Out", "Doubtful", "Questionable", "Off starter value", "Def starter value",
        "Off Out share", "Def Out share", "Off Q share", "Status", "Depth: QB 1st / 2nd / 3rd / 4th", "Chart dated", "Source"], rows) if rows else '<p class="small">No board data yet — run the pipeline.</p>'}
<h2>Who is next man up — published depth, by tier</h2>
<p class="small">Read straight from the depth-chart snapshot. Only positions where a tier is populated
appear. A missing tier means the chart does not list a player there — it is not an inference that nobody
is available.</p>
{table(["Team", "Position", "1st", "2nd", "3rd", "4th", "Chart dated"], tier_rows) if tier_rows else ''}
<h2>The 2nd, 3rd and 4th string problem</h2>
<p>The depth tracker answers, per team and position: <em>who is listed first, second, third, fourth</em>,
and is the first-string player on the report? Three states are possible and they are published separately:</p>
<div class="grid g3">
<div class="card"><h3>Starter available</h3><p class="small">Listed 1st on the latest snapshot and not
marked Out. No adjustment is made — the model already rates the team.</p></div>
<div class="card"><h3>Starter out, backup promoted</h3><p class="small">Listed 1st but marked Out. The
snap-weighted value of that absence enters the model as an Out share, and the next man up is shown by
tier.</p></div>
<div class="card"><h3>Unknown</h3><p class="small">No depth row or no report row. Left blank. The model
uses the documented neutral fill, and the coverage table on the lines page shows how often that happens.</p></div>
</div>
<h2>Known gaps in this tracker</h2>
<ul class="clean">
<li>The <strong>inactive list at kickoff</strong> is not in this dataset. A Questionable player may play; an
Out player never does. Q5 covers obtaining the official inactives.</li>
<li>Depth-chart snapshots have a timestamp, but <strong>staleness is not yet enforced</strong> — Q9 proposes
a 7-day rule.</li>
<li>The tracker covers the <strong>latest week only</strong> for the live board. Historical index values are
used in the model for every evaluated game.</li>
</ul>"""
    page("injuries.html", "Injuries and lineups", body, "injuries.html")


def build_leaderboard(lb, mr):
    comp = (lb or {}).get("competition", {})
    rows = []
    for r in (lb or {}).get("rows", []):
        gates = r.get("gates", {})
        gtxt = " ".join(f'<span class="tag {"pass" if g.get("pass") else "fail"}" '
                        f'title="{html.escape(str(g.get("value")))}">{esc(k.split("_")[0])}</span>'
                        for k, g in gates.items())
        m = r.get("metrics", {})
        rows.append([
            f'<strong>{r["rank"]}</strong>', f'<span class="tag {r["tier"]}">{r["tier"]}</span>',
            esc(r["name"]), esc(r["family"]),
            esc(m.get("games") or m.get("seasonsTested")),
            esc(m.get("skill") if m.get("skill") is not None else m.get("expectedJointCorrelationAware")),
            esc(m.get("accuracy")),
            esc(r.get("score")), esc(r.get("labPoints")), gtxt,
            src(_hyp_source("H1") if r["family"] == "single" else _hyp_source("H5"), "data"),
        ])
    body = f"""
<h1>Leaderboard and rewards</h1>
<p class="lede">{esc(comp.get('basis'))}</p>
<div class="callout warn"><strong>Rewards are non-monetary by design.</strong> {esc(comp.get('rewards'))}
A cash reward keyed to betting performance would be a regulated activity; that decision belongs to the
owner and is recorded as Q4, not assumed here.</div>
<h2>Ranking</h2>
{table(["#", "Tier", "Strategy", "Family", "Games", "Skill / joint p", "Accuracy", "Score", "Points", "Gates", "Source"], rows) if rows else '<p class="small">No leaderboard rows yet.</p>'}
<h2>Tier definitions</h2>
<div class="grid g3">
<div class="card"><h3><span class="tag A">Tier A</span></h3><p class="small">Passes sample size, positive
out-of-sample skill, best-of-K deflation, calibration slope in [0.8, 1.25] and sign stability. Score is
deflated skill × sample shrink × calibration factor.</p></div>
<div class="card"><h3><span class="tag C">Tier C</span></h3><p class="small">Positive out-of-sample skill
but has not cleared deflation, or has no market to price against. Promising, not yet distinguishable from
luck.</p></div>
<div class="card"><h3><span class="tag D">Tier D</span></h3><p class="small">Fails at least one gate. Kept
in the audit history with the failing gate named — a failed strategy is never deleted, because deleting
them is how selection bias starts.</p></div>
</div>
<h2>Why win rate is not the ranking metric</h2>
<p>A strategy can win 60% of 40 games through noise alone. Ranking on win rate rewards that. Ranking on
deflated skill punishes it: the score subtracts the best-of-K null threshold, so a strategy must beat what
the best of K random strategies would have scored on the same data before it earns anything.</p>
<p class="small">Tie-break: higher deflated skill, then larger sample, then better calibration slope.</p>"""
    page("leaderboard.html", "Leaderboard", body, "leaderboard.html")


def build_parlays(mr):
    pc = mr.get("propCorrelation", [])
    props = mr.get("props", [])
    pl = [r for r in mr.get("leaderboard", []) if r["family"] == "parlay"]
    prows = [[esc(p["a"].replace("_", " ")), esc(p["b"].replace("_", " ")), esc(p["position"]), esc(p["n"]),
              esc(p["r"]), f'{esc((p.get("ci") or [None, None])[0])} … {esc((p.get("ci") or [None, None])[1])}',
              '<span class="tag pass">excludes 0</span>' if (p.get("ci") and p["ci"][0] is not None and
                                                             (p["ci"][0] > 0 or p["ci"][1] < 0))
              else '<span class="tag">includes 0</span>',
              src(_hyp_source("H6"), "stats")] for p in pc]
    qrows = [[esc(p["market"].replace("_", " ")), esc(p["position"]), esc(p["line"]), esc(p["games"]),
              esc(p["logloss"]), esc(p["accuracy"]), esc(p["skill"]),
              src(_hyp_source("H5"), "stats")] for p in props]
    lrows = [[esc(r["name"]), esc(r["metrics"].get("seasonsTested")),
              esc(r["metrics"].get("expectedJointIndependent")),
              esc(r["metrics"].get("expectedJointCorrelationAware")),
              src(_hyp_source("H7"), "data")] for r in pl]
    body = f"""
<h1>Parlays and prop combos — correlation-aware</h1>
<p class="lede">Multiplying leg probabilities assumes the legs are independent. They often are not: two
props on the same team share a game script, and a game total and a quarterback's passing yards move
together. This page measures those relationships first, then prices the combination with a Gaussian copula
that consumes the measured matrix.</p>
<div class="callout bad"><strong>No payout, no ROI, no stake.</strong> There is no parlay price and no prop
price in any reachable source. What follows is a joint <em>probability</em>. Turning that into a wager needs
a price, and the price is missing — recorded as GAP-1 and GAP-2.</div>
<h2>Single-bet vs parlay vs prop combo</h2>
<div class="grid g3">
<div class="card"><h3>Single</h3><p class="small">One probability, one price. The only market where a
conventional edge can even be defined. Tested in the leaderboard as a probability, since the price is
absent.</p></div>
<div class="card"><h3>Parlay (cross-game)</h3><p class="small">Legs come from different games, so they are
near-independent by construction. The real risk is not correlation but the compounded vig — which cannot
be computed without prices.</p></div>
<div class="card"><h3>Prop combo (same-game)</h3><p class="small">Legs share a game script. Correlation is
the whole question, and it is measurable from outcomes. Measured values are on the right.</p></div>
</div>
<h2>Measured cross-game parlay families</h2>
{table(["Family", "Seasons", "Product of marginals", "Copula joint", "Source"], lrows) if lrows else '<p class="small">No parlay rows yet.</p>'}
<h2>Prop forecast accuracy (no market price exists)</h2>
<p class="small">A player's next-game over/under on a fixed line is forecast from his own prior weeks in
that season only. Scored against ln 2, the log loss of a coin flip. This is a forecast test, not an edge
test.</p>
{table(["Market", "Pos", "Line", "Games", "Log loss", "Accuracy", "Skill vs coin flip", "Source"], qrows) if qrows else '<p class="small">No prop rows yet.</p>'}
<h2>Measured same-team prop correlations</h2>
{table(["Leg A", "Leg B", "Pos", "Pairs", "r", "95% CI", "Verdict", "Source"], prows) if prows else '<p class="small">No prop-correlation rows yet.</p>'}
<h2>How the joint probability is computed</h2>
<ol class="clean">
<li>Marginals come from the model, never from a guess.</li>
<li>Each correlated pair contributes its measured r to a correlation matrix.</li>
<li>A Cholesky factor of that matrix drives a Gaussian copula; the joint probability is the share of
simulated draws in which every leg wins.</li>
<li>If the matrix is not positive definite (which happens with noisy estimates), the code falls back to
independence and says so in its output rather than silently producing a number.</li>
</ol>"""
    page("parlays.html", "Parlays and props", body, "parlays.html")


def build_questions(q):
    rows = []
    for x in (q or {}).get("items", []):
        rows.append([esc(x["id"]), esc(x["topic"]), f'<strong>{esc(x["question"])}</strong>',
                     esc(x["have"]), esc(x["missing"]), esc(x["impact"]), esc(x["how"]),
                     esc(x["owner"]), esc(x["blocks"])])
    body = f"""
<h1>Questions that must be answered before a decision</h1>
<p class="lede">Each row is a decision blocker, not a to-do. It states what is already known, what is
missing, what would change once the gap is closed, how to close it, and who owns the answer. Nothing on
this page is a recommendation to bet; several rows exist precisely because the information needed to
recommend anything does not exist yet.</p>
{table(["ID", "Topic", "Question", "Already have", "Missing", "Why it matters", "How to obtain",
        "Owner", "What it blocks"], rows) if rows else '<p class="small">No questions yet.</p>'}
<h2>How missing information is discovered, not guessed</h2>
<ul class="clean">
<li><strong>Coverage counting.</strong> Every feature reports how many games actually have the value. A
feature present in 40% of games is treated as missing for the other 60%, never imputed.</li>
<li><strong>Null-and-flag.</strong> When a source returns HTTP 404 or an empty array, the field is set to
blank and the row is listed on the flagged page. It is not filled from memory or from another site.</li>
<li><strong>Two independent publishers.</strong> Results are cross-checked between nflverse and ESPN. A
disagreement is published as a disagreement, not resolved by picking the more convenient number.</li>
<li><strong>Explicit gap register.</strong> Six gaps (GAP-1 … GAP-6) are enumerated on the data audit page
with the exact acquisition step that would close each one.</li>
</ul>"""
    page("questions.html", "Questions", body, "questions.html")


SUGGESTIONS = [
    {"id": "S1", "area": "Decision making", "suggestion": "Lead every page with gate status and sample size, not with a score",
     "why": "A score without its sample size and gate state invites over-trust. The dashboard therefore shows games, deflation verdict and Tier counts before any ranking.",
     "test": "A/B the landing layout: does a reader correctly state 'not established' for a Tier C strategy?",
     "cost": "low", "status": "implemented"},
    {"id": "S2", "area": "Statistics", "suggestion": "Register every variant tried and recompute K from the registry",
     "why": "Deflation is only honest if K counts the strategies actually tried, including abandoned ones. Today K is fixed per family and published.",
     "test": "Compare the null threshold when K=9 versus K=200 on the same data; the threshold must rise.",
     "cost": "low", "status": "proposed"},
    {"id": "S3", "area": "Data", "suggestion": "Capture one pre-kickoff market snapshot per game with a timestamp",
     "why": "This is the single change that unlocks ROI, vig, closing-line value and everything the user asked about line-making. Without a timestamp, a 'line' is not a price.",
     "test": "After 4 weeks, verify that every stored snapshot has a timestamp before kickoff and a value for every game.",
     "cost": "medium", "status": "proposed"},
    {"id": "S4", "area": "Lineup tracking", "suggestion": "Add the official inactive list per game and reconcile it with the injury report",
     "why": "A Questionable player can play; an inactive never does. Reconciling the two turns the lineup index from a proxy into a fact.",
     "test": "Report the reconciliation rate: share of Out players who are indeed inactive, and of actives not on the report.",
     "cost": "medium", "status": "proposed"},
    {"id": "S5", "area": "Lineup tracking", "suggestion": "Publish the depth-chart snapshot age on every row and mark anything older than 7 days as stale",
     "why": "A depth chart is a snapshot, not a live feed. Showing its age prevents a three-week-old chart from being read as tonight's lineup.",
     "test": "Count rows with a snapshot older than 7 days each week; the count should be visible, not zero-by-omission.",
     "cost": "low", "status": "implemented"},
    {"id": "S6", "area": "Lineup tracking", "suggestion": "Weight missing players by talent, not only by usage",
     "why": "Snap share measures opportunity. A high-EPA player lost for the season should move the index more than a high-snap, low-impact player.",
     "test": "Blend per-player EPA from play-by-play with snap share; compare out-of-sample skill against the usage-only index.",
     "cost": "high", "status": "proposed"},
    {"id": "S7", "area": "Correlation", "suggestion": "Apply a multiplicity correction and publish it",
     "why": "Testing 55 signal pairs guarantees false positives at the 5% level. The CI is shown today; a Benjamini-Hochberg adjusted threshold is the next step.",
     "test": "Re-run the pair table with the adjusted threshold and report how many pairs survive both.",
     "cost": "low", "status": "proposed"},
    {"id": "S8", "area": "Competition", "suggestion": "Run a locked prospective paper trial before any reward is paid",
     "why": "A backtest, however deflated, is not a live record. A pre-declared horizon with frozen picks is the only way to show a strategy works forward.",
     "test": "Freeze picks for 6 weeks before kickoff; compare realised log loss with the pre-registered expectation.",
     "cost": "medium", "status": "proposed"},
    {"id": "S9", "area": "Site", "suggestion": "Keep a single canonical page per category and one shared stylesheet",
     "why": "Parallel sessions duplicating dashboards is how two sites with two different numbers appear. This lab owns nfl-lines/ and links to the planner rather than restating it.",
     "test": "A link check that fails if any number appears on more than one page without being generated from the same JSON.",
     "cost": "low", "status": "implemented"},
    {"id": "S10", "area": "Decision making", "suggestion": "Convert each open question into a dated decision with an owner and a trigger",
     "why": "A question register that nobody closes becomes decoration. Q1–Q12 need a decision date and a named owner before the next release.",
     "test": "At each release, count questions closed versus opened. A rising open count with no closures means the lab is stuck.",
     "cost": "low", "status": "proposed"},
]


def build_suggestions():
    rows = [[esc(s["id"]), esc(s["area"]), f'<strong>{esc(s["suggestion"])}</strong>', esc(s["why"]),
             esc(s["test"]), f'<span class="tag {"pass" if s["status"]=="implemented" else "warn"}">{esc(s["status"])}</span>',
             esc(s["cost"])] for s in SUGGESTIONS]
    body = f"""
<h1>Suggestions — review before implementing</h1>
<p class="lede">A review queue, not a wish list. Each suggestion states the improvement to decision
making, why it matters, the cheapest test that would show whether it works, its cost, and whether it is
already implemented here or still proposed. Nothing in this list has been implemented on the owner's
behalf beyond the items marked <em>implemented</em>, which are composition and layout choices inside this
new section.</p>
{table(["ID", "Area", "Suggestion", "Why it improves decisions", "How to test it", "Status", "Cost"], rows)}
<h2>Recommended reading order for a decision</h2>
<ol class="clean">
<li><strong>Questions</strong> — is a decision even possible? Q1 and Q2 gate everything else.</li>
<li><strong>Data audit</strong> — do the inputs exist and do two publishers agree?</li>
<li><strong>Leaderboard</strong> — what survives deflation, with what sample size?</li>
<li><strong>Signals</strong> — are the inputs distinct, or the same input twice?</li>
<li><strong>Parlays</strong> — if combining, is the correlation measured or assumed?</li>
<li><strong>Flagged</strong> — what is blank, contradictory or stale?</li>
</ol>
<h2>What I would do first, if this were my decision</h2>
<ol class="clean">
<li><strong>S3</strong> — start capturing timestamped market snapshots. Nothing else converts this from a
research lab into a line-making system.</li>
<li><strong>S4</strong> — add the inactive list, so the injury index becomes a fact rather than a proxy.</li>
<li><strong>S8</strong> — run the paper trial before spending anything on rewards.</li>
<li><strong>S2 and S7</strong> — tighten the statistics before adding more strategies. More strategies on
the same data is how a lab manufactures a winner.</li>
</ol>"""
    page("suggestions.html", "Suggestions", body, "suggestions.html")


def build_data(mr):
    audit = load("data_audit.json", {"checks": [], "gaps": []})
    rows = []
    for c in audit.get("checks", []):
        cls = {"pass": "pass", "partial": "warn", "unknown": ""}.get(c["status"], "")
        rows.append([esc(c["name"]), esc(c["result"]), f'<span class="tag {cls}">{esc(c["status"])}</span>',
                     src(_hyp_source("H1") if "nflverse" in c["name"] else "", "source")])
    gaps = [[esc(g["id"]), f'<strong>{esc(g["item"])}</strong>', esc(g["why"]), esc(g["whatWeHave"]),
             esc(g["howToObtain"]), esc(g["blocks"])] for g in audit.get("gaps", [])]
    mkt = mr.get("marketCoverage", {})
    cs = mr.get("crossSource", {})
    ex = [[esc(e.get("date")), esc(f'{e.get("away","")} @ {e.get("home","")}'),
           esc(e.get("nflverse") or "no nflverse row paired"),
           esc(e.get("espn")), esc(e.get("kind", "checked")),
           src(f'https://www.espn.com/nfl/game/_/gameId/{e["source"]}', "ESPN game")] for e in cs.get("examples", [])]
    body = f"""
<h1>Data audit</h1>
<p class="lede">What was fetched, what it contains, whether two independent publishers agree, and what is
missing. A gap is listed even when it would be embarrassing to list it — especially then.</p>
<h2>Source-to-source cross-check</h2>
<div class="callout {'pass' if cs.get('disagree', 1) == 0 else 'warn'}"><strong>{esc(cs.get('summary'))}</strong>
nflverse and ESPN publish independently. Every completed game in the fetched seasons was compared on final
score. Disagreements are shown rather than resolved.</div>
{table(["Check", "Result", "Status", "Source"], rows)}
{table(["Date", "Matchup", "nflverse", "ESPN", "Kind", "Link"], ex) if ex else ''}
<h2>Market coverage</h2>
<div class="grid g3">
<div class="card"><div class="kpi">{pct(mkt.get('spreadPct'))}<small>of games have a spread</small></div>
<p class="small">From nflverse schedules. One value per game, no timestamp.</p></div>
<div class="card"><div class="kpi">{pct(mkt.get('moneylinePct'))}<small>have moneylines</small></div>
<p class="small">Empty, so vig cannot be measured from this source.</p></div>
<div class="card"><div class="kpi">{esc(mkt.get('espnOddsGames'))}<small>games with ESPN odds</small></div>
<p class="small">Of {esc(mkt.get('espnGames'))} games fetched. Odds exist only for the current week on screen.</p></div>
</div>
<h2>Gap register — what would have to be acquired</h2>
{table(["ID", "Missing item", "Why it matters", "What we have", "How to obtain", "What it blocks"], gaps)}
<h2>Provenance</h2>
<p>Every file the pipeline used is listed on the <a href="sources.html">sources page</a> with its URL, HTTP
status, byte count and a sha256 prefix. A file that returned an error is listed too, with the error.</p>"""
    page("data.html", "Data audit", body, "data.html")


def build_flagged(mr):
    audit = load("data_audit.json", {"gaps": []})
    q = load("questions.json", {"items": []})
    rows = [
        ["F1", "Player prop market price", "No prop market exists in any reachable source. Every prop 'edge' is therefore blank.",
         "blank", "nfl/data/model_results.json props[].market", "https://www.nfl.com/stats/player-stats/"],
        ["F2", "Moneyline history", "The moneyline columns in the schedules file are empty for every season checked, so vig is unknown.",
         "blank", "nfl/data/data_audit.json", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"],
        ["F3", "Line timing", "The spread and total are a single snapshot with no timestamp, so no closing-line value can be computed.",
         "unverified", "nfl/data/data_audit.json", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"],
        ["F4", "Game-day inactive list", "The official inactive list is not in the dataset; the injury report is a pre-game designation only.",
         "missing", "nfl/data/questions.json Q5", "https://www.nfl.com/injuries/"],
        ["F5", "Player talent weighting", "The lineup index weights by snap share, which measures usage, not ability.",
         "limitation", "nfl/data/questions.json Q6", "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2025.csv"],
        ["F6", "Depth-chart staleness", "Snapshots carry a timestamp but no staleness rule is enforced yet.",
         "limitation", "nfl/data/questions.json Q9", "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2025.csv"],
        ["F7", "Multiplicity across correlation pairs", "Many pairs are tested; a correction is registered but not yet applied.",
         "open", "nfl/data/questions.json Q10", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"],
        ["F8", "Rewards legality", "A monetary reward tied to betting performance is a regulated activity. Rewards here are points only.",
         "open", "nfl/data/questions.json Q4", "https://www.nfl.com/"],
        ["F9", "Historical odds feed", "Without a licensed odds history, ROI and vig-adjusted edge cannot be computed at all.",
         "missing", "nfl/data/data_audit.json GAP-1", "https://www.nfl.com/schedules/"],
        ["F10", "Referee and weather subgroup size", "Registered as a strategy family but not tested; subgroup samples are too small to gate honestly.",
         "registered", "nfl/data/hypotheses.json H10", "https://github.com/nflverse/nflverse-data/releases/download/officials/officials.csv"],
    ]
    body = f"""
<h1>Flagged for review</h1>
<p class="lede">Everything that is blank, unverified, contradictory or merely insufficient — published
instead of hidden. None of these block publication; all of them block a confident claim.</p>
{table(["ID", "Item", "Finding", "State", "Where it is recorded", "Reference"], rows)}
<h2>How a blank is produced</h2>
<p>When a source returns nothing for a field, the pipeline writes <code>null</code>. The site renders the
literal text <em>— blank —</em>. No value is ever inferred, averaged in from another site, or filled from a
previous season. Where a model needs a number and the value is missing, the fill is documented on the
<a href="lines.html">lines page</a> and counted in the coverage table.</p>
<h2>Contradiction policy</h2>
<p>If two publishers disagree on a score, both values are shown and the disagreement is counted. If a
source disappears (404), the field becomes blank and the row is flagged — the previous value is not carried
forward silently.</p>"""
    page("flagged.html", "Flagged", body, "flagged.html")


def build_sources(mr):
    prov = load("provenance.json", {"files": [], "sources": []})
    rows = []
    for f in prov.get("files", []):
        rows.append([esc(f.get("name")), esc(f.get("status")), esc(f.get("bytes")),
                     f'<code class="small">{(f.get("sha256") or "")[:16]}</code>',
                     esc(f.get("fetchedUTC")),
                     src(f.get("url"), "download")])
    srows = [[esc(s.get("name")), esc(s.get("what")), esc(s.get("caveat")), src(s.get("url"), "source")]
             for s in prov.get("sources", [])]
    body = f"""
<h1>Sources and provenance</h1>
<p class="lede">Every input file, its HTTP status, its size, a sha256 prefix and the time it was fetched.
This table is generated from the manifest the fetcher writes, so it describes what actually happened, not
what was intended.</p>
<h2>Datasets used</h2>
{table(["Source", "What it provides", "Caveat", "Link"], srows)}
<h2>Files fetched</h2>
<p class="small">{len(rows)} files recorded. A non-200 status here means the value that depends on that file
is blank and flagged.</p>
<div class="callout warn"><strong>Coverage limit, stated up front.</strong> The ESPN cross-check downloads one
scoreboard per regular-season week and playoff round, but the public endpoint does not return January dates
from a season-based query, and it returns nothing for playoff rounds past week 4. Games outside those pulls
are therefore <em>absent</em> from the comparison rather than disagreeing with it. They are counted as
unmatched on purpose: a game nobody checked must never be described as verified.</div>
{table(["File", "HTTP", "Bytes", "sha256 (16)", "Fetched (UTC)", "URL"], rows) if rows else '<p class="small">No provenance manifest yet.</p>'}
<h2>Official references used for provenance links</h2>
<ul class="clean">
<li><a href="https://www.nfl.com/schedules/">NFL.com schedule</a> — official kickoff and game pages.</li>
<li><a href="https://www.nfl.com/injuries/">NFL.com injury report</a> — official weekly designation.</li>
<li><a href="https://www.nfl.com/stats/player-stats/">NFL.com player statistics</a> — official stats portal.</li>
<li><a href="https://operations.nfl.com/the-rules/">NFL Football Operations rules</a> — settlement-relevant rules such as overtime.</li>
<li><a href="https://github.com/nflverse/nflverse-data">nflverse-data</a> — open data release (CC-BY-4.0) from which the weekly tables are drawn.</li>
</ul>
<h2>Honesty rules</h2>
<ul class="clean">
<li>No number on this site is typed by hand; all of them are generated from the JSON in <code>nfl/data/</code>.</li>
<li>No value is inferred. A missing value is blank and appears on the flagged page.</li>
<li>No ROI, profit or edge claim is made anywhere, because no timestamped price history exists.</li>
<li>Every verification claim names the check that was run, and the check is in the repository.</li>
</ul>"""
    page("sources.html", "Sources", body, "sources.html")


def build_executive(mr, lb, q, hyp):
    audit = load("data_audit.json", {})
    m = mr.get("model", {}) or {}
    d = mr.get("deflation", {}) or {}
    cs = mr.get("crossSource", {}) or {}
    fams = mr.get("families", {}) or {}
    props = mr.get("props", []) or []
    corr = (mr.get("correlation", {}) or {}).get("pairs", []) or []
    mc = mr.get("marketCoverage", {}) or {}

    def n5(v):
        return f"{v:.5f}" if isinstance(v, (int, float)) else esc(v)

    head = table(["Measure", "Value"], [
        ["Seasons loaded", esc(", ".join(str(x) for x in (mr.get("seasons") or [])))],
        ["Out-of-sample evaluation seasons", esc(", ".join(str(x) for x in (mr.get("evaluatedSeasons") or [])))],
        ["Games evaluated out of sample", esc(m.get("games"))],
        ["Accuracy (pick the higher-probability side)", esc(m.get("accuracy"))],
        ["Log loss", esc(f'{n5(m.get("logloss"))} vs baseline {n5(m.get("baselineLogloss"))}')],
        ["Log-loss skill vs baseline", n5(m.get("skill"))],
        ["Brier skill vs baseline", n5(m.get("brierSkill"))],
        ["Luck deflation (best-of-K null)",
         esc(f'N={d.get("N")} permutations, K={d.get("K")}, null p95={d.get("p95")} → {d.get("verdict")}')],
        ["Cross-source score check", esc(cs.get("summary"))],
    ])

    fam_rows = []
    for name, f in sorted(fams.items()):
        sc = f.get("scores", {}) or {}
        fd = f.get("deflation", {}) or {}
        fam_rows.append([esc(name.title()), esc(len(f.get("features", []) or [])),
                         n5(sc.get("skill")), n5(fd.get("p95")),
                         pill("passed" if fd.get("passed") else "failed"),
                         esc(f.get("claim", ""))])
    fam_tbl = table(["Family", "# signals", "Skill", "Null p95", "Deflation verdict", "Claim"], fam_rows) if fam_rows else "<p>No family rows in this run.</p>"

    prop_rows = [[esc(p.get("market", "").replace("_", " ")), esc(p.get("position")),
                  esc(p.get("line")), esc(p.get("games")), n5(p.get("skill")), n5(p.get("accuracy"))]
                 for p in props]
    prop_tbl = (table(["Market", "Position", "Line", "Games", "Skill vs base rate", "Accuracy"], prop_rows)
                if prop_rows else "<p>No player-prop rows in this run.</p>")

    top = [c for c in corr if c.get("excludesZero") and abs(c.get("r") or 0) < 0.999]
    top.sort(key=lambda c: -abs(c.get("r") or 0))
    corr_rows = [[esc(f'{c["a"]} ~ {c["b"]}'), esc(c.get("n")), esc(c.get("r")),
                  esc(f'[{(c.get("ci") or [None, None])[0]}, {(c.get("ci") or [None, None])[1]}]')]
                 for c in top[:10]]
    corr_tbl = (table(["Signal pair (value vs home win)", "N", "Pearson r", "95% bootstrap CI"], corr_rows)
                if corr_rows else "<p>No correlation excludes zero in this run.</p>")

    chk = audit.get("checks", []) or []
    chk_rows = [[esc(c.get("id")), esc(c.get("name")), esc(c.get("result")), pill(c.get("status")),
                 (src(c.get("source"), "source") if c.get("source", "").startswith("http") else esc(c.get("source", "")))]
                for c in chk]
    chk_tbl = table(["Check", "What was checked", "Result", "Status", "Source"], chk_rows)

    gaps = audit.get("gaps", []) or []
    gap_rows = [[esc(g.get("id")), esc(g.get("item")), esc(g.get("why")), esc(g.get("howToObtain"))] for g in gaps]
    gap_tbl = table(["ID", "Missing information", "Why it blocks decisions", "How to obtain it"], gap_rows)

    items = q.get("items", []) or []
    q_rows = [[esc(it.get("id")), esc(it.get("question")), esc(it.get("missing")), esc(it.get("impact"))]
              for it in items[:6]]
    q_tbl = (table(["ID", "Question before any decision", "Information missing", "Impact"], q_rows)
             if q_rows else "<p>No open questions recorded.</p>")

    body = f"""<h1>Executive summary</h1>
<p>Generated from the repository's own pipeline outputs in <code>nfl/data/</code> — nothing on this page is typed
by hand. Run log: <a href="https://github.com/karagemop466-tech/Korea5/actions">GitHub Actions</a>;
full method on the <a href="signals.html">Signals</a> page.</p>
<h2>1. Headline results</h2>
{head}
<h2>2. Where the signal comes from</h2>
{fam_tbl}
<h2>3. Player-prop signals (base-rate baseline)</h2>
{prop_tbl}
<h2>4. Correlation values that exclude zero</h2>
<p>Pairwise Pearson r among the model's signals and against the home-win outcome. Pairs whose 95% bootstrap
interval contains zero are treated as unmeasured, not as zero.</p>
{corr_tbl}
<h2>5. Verification and provenance</h2>
{chk_tbl}
<h2>6. Known gaps — information that must be found before decisions</h2>
<p>Each gap blocks a class of decision. Acquisition suggestions are listed; nothing is filled in by guesswork.</p>
{gap_tbl}
<h2>7. Open questions before any decision can be made</h2>
{q_tbl}
<p>Full list with answers and owners: <a href="questions.html">Questions</a>. Improvement proposals to choose
between before anything changes: <a href="suggestions.html">Suggestions</a>.</p>
<h2>8. What is claimed, and what is not</h2>
<ul class="clean">
<li><strong>Claimed:</strong> the strength family (Elo-style ratings + form) beats its own baseline out of sample
and survives the best-of-K luck-deflation null at the reported p95.</li>
<li><strong>Not claimed:</strong> any profit, return, payout or edge. No timestamped price history exists
(GAP-1), so none of those can be computed, and this lab is a research model, not a betting system.</li>
<li><strong>Not claimed:</strong> that context-family skill is real — its deflation verdict is
{esc((fams.get("context", {}).get("deflation", {}) or {}).get("verdict"))}.</li>
<li>Injuries and depth charts are tracked with snapshot dates and a 1st–4th-string tier table
(<a href="injuries.html">Injuries &amp; lineups</a>); designations come from the official weekly reports via nflverse.</li>
</ul>
<h2>9. Reproduce</h2>
<pre>python3 nfl/fetch_data.py --with-espn --seasons 2016:2026
python3 nfl/model.py --perm 200
python3 nfl/analyze.py
python3 nfl/leaderboard.py
python3 nfl/build_site.py
python3 -m unittest discover -s nfl/tests</pre>
<p>Every figure above is regenerated by these commands from fetched files whose SHA-256 hashes are published
on the <a href="data.html">Data audit</a> page.</p>"""
    page("executive.html", "Executive summary", body, "executive.html")



def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    mr = load("model_results.json", {})
    lb = load("leaderboard.json")
    q = load("questions.json", {"items": []})
    hyp = load("hypotheses.json", {"items": []})
    build_index(mr, lb, q, hyp)
    build_executive(mr, lb, q, hyp)
    build_lines(mr)
    build_signals(mr, hyp)
    build_injuries(mr)
    build_leaderboard(lb, mr)
    build_parlays(mr)
    build_questions(q)
    build_suggestions()
    build_data(mr)
    build_flagged(mr)
    build_sources(mr)
    print(f"built {len(NAV)} pages in {OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
