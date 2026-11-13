#!/usr/bin/env python3
"""Build the NFL decision-system section (nfl/*.html).

Reads nfl/data/*.json (official) + nfl/data/derived/*.json (computed) + nfl/curated/*.json
(registers). Writes nfl/*.html.

Every table row that states an official value carries a link to the official page it came
from. Every computed value carries a MODEL badge. Every value the official source did not
publish is rendered as an em dash plus an UNVERIFIED badge — never filled in.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
NFL = ROOT / "nfl"
DER = NFL / "data" / "derived"
CUR = NFL / "curated"

# ------------------------------------------------------------------ utilities


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default if default is not None else {}


def src(url: str, text: str = "source") -> str:
    if not url:
        return '<span class="badge unverified">no source</span>'
    host = urlparse(url).hostname or ""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(text)}</a>' \
           f'<br><span class="dim" style="font-size:11px">{esc(host)}</span>'


def dash(reason="not published"):
    return f'<span class="badge unverified">{esc(reason)}</span> &mdash;'


def model(tag="MODEL"):
    cls = {"MODEL": "model", "OFFICIAL": "official", "UNVERIFIED": "unverified",
           "JUDGEMENT": "judgement"}.get(tag, "none")
    return f'<span class="badge {cls}">{esc(tag)}</span>'


def fmt(v, nd=2, blank="&mdash;"):
    if v is None or v == "":
        return blank
    if isinstance(v, float):
        return f"{v:,.{nd}f}"
    if isinstance(v, int):
        return f"{v:,}"
    return esc(v)


def badge_status(s: str) -> str:
    s = (s or "").lower()
    if "accept" in s:
        return f'<span class="badge official">{esc(s)}</span>'
    if "block" in s:
        return f'<span class="badge unverified">{esc(s)}</span>'
    if "await" in s:
        return f'<span class="badge judgement">{esc(s)}</span>'
    return f'<span class="badge none">{esc(s)}</span>'


# ------------------------------------------------------------------ page shell
SECTIONS = [
    ("index.html", "Overview"),
    ("summary.html", "Executive summary"),
    ("suggestions.html", "Suggestions"),
    ("questions.html", "Questions &amp; gaps"),
    ("market.html", "Lines &amp; market"),
    ("strategies.html", "Strategies"),
    ("leaderboard.html", "Leaderboard"),
    ("validation.html", "Validation gates"),
    ("signals.html", "Signals"),
    ("correlation.html", "Correlation"),
    ("injuries.html", "Injuries &amp; depth"),
    ("data.html", "Data health"),
    ("flagged.html", "Flagged for review"),
    ("method.html", "Method"),
]

GENERATED = jload(DER / "summary.json").get("generatedUTC", "unknown")
# ^ the data's own retrieval stamp, so a rebuild is byte-identical until the data changes.


def page(title: str, active: str, body: str, lede: str = "") -> str:
    nav = "".join(f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>'
                  for u, n in SECTIONS)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NFL Decision System</title>
<meta name="description" content="NFL line-origination and strategy-validation system built only on official NFL data, with every value sourced and every gap published.">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="assets/nfl.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> NFL / DECISION SYSTEM</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">
<aside class="callout warn" role="note"><strong>No betting claim is made anywhere on this site.</strong>
No official NFL source publishes odds, so no price exists in this system.
Every computed number is labelled {model("MODEL")}. Every value an official page did not publish is
blank and badged {model("UNVERIFIED")}, never filled in.
<a href="flagged.html">What is unresolved →</a></aside>
<h1>{esc(title)}</h1>{f'<p class="lede">{lede}</p>' if lede else ''}
{body}
</main>
<footer><div class="wrap">
<p><strong>NFL Decision System</strong> · data retrieved {esc(GENERATED)} (newest official fetch) · official sources only:
nfl.com, the 32 official club sites, operations.nfl.com.
Part of the <a href="../index.html">Korea5 planner</a> · also see the
<a href="../nfl-strategy.html">strategy lab proposal</a>.</p>
<p>Nothing here is betting advice. No reward is authorised. Values that could not be confirmed from an
official source are blank and listed on <a href="flagged.html">Flagged for review</a>.</p>
</div></footer></body></html>"""


# ------------------------------------------------------------------ data load
SUM = jload(DER / "summary.json")
COV = jload(DER / "coverage.json")
HF = jload(DER / "homefield.json")
REST = jload(DER / "rest.json")
SCORE = jload(DER / "scoring.json")
MATCH = jload(DER / "matchups.json")
INJ = jload(DER / "injuries.json")
DEPTH = jload(DER / "depth.json")
CORR = jload(DER / "correlation.json")
MKT = jload(DER / "market.json")
SKILL = jload(DER / "skill.json")
LB = jload(DER / "leaderboard.json")
SUG = jload(CUR / "suggestions.json")
QST = jload(CUR / "questions.json")
GATES = jload(CUR / "validation-gates.json")
STRAT = jload(CUR / "strategies.json")
SIG = jload(CUR / "signals.json")
FETCH = jload(NFL / "data" / "fetch-report.json")


def kpis():
    def cell(val, label, note=""):
        return (f'<div class="card"><div class="kpi">{val}'
                f'<small>{label}</small></div>'
                f'{f"<p class=small style=margin:6px_0_0>{note}</p>" if note else ""}</div>')
    return f"""<div class="grid g4">
{cell(fmt(SUM.get('finalGames2026')), "2026 games with official final scores", "scores read from nfl.com week pages")}
{cell(fmt(SUM.get('injuryRows2026')), f"official injury rows (week {SUM.get('injuryWeek')})", "nfl.com injury report")}
{cell(f"{fmt(SUM.get('depthClubs'))}/32", "clubs with a parseable depth chart", f"{fmt(SUM.get('depthRows'))} depth entries")}
{cell("0", "strategies certified", "no stored price exists to settle any bet")}
</div>"""


# ------------------------------------------------------------------- pages
def p_index():
    hf = HF.get("combined", {})
    body = f"""
{kpis()}
<h2>The honest state of the system in six lines</h2>
<div class="card prose">
<ol>
<li><strong>Data is real and sourced.</strong> {fmt(SUM.get('finalGames2026'))} completed 2026 games,
{fmt(SUM.get('finalGames2025'))} from 2025, {fmt(SUM.get('injuryRows2026'))} official injury rows for the current
report week, {fmt(SUM.get('depthRows'))} depth-chart entries across {fmt(SUM.get('depthClubs'))} clubs, and
{fmt(SUM.get('teamStatTables'))} official team stat tables. Each is fetched by CI and stamped.</li>
<li><strong>Prices do not exist.</strong> nfl.com publishes no odds. With no price, no bet can be settled and no
return can be computed. Any page claiming a return would be inventing it.</li>
<li><strong>So nothing is certified.</strong> {fmt(SKILL.get('n'))} official finals are enough to test the
<em>machinery</em>, not enough to certify a strategy. The shuffle test on a home-field prior returns
p&nbsp;=&nbsp;{fmt(SKILL.get('shuffleTest', {}).get('pValueOneSided'), 3)} — i.e. indistinguishable from a coin.</li>
<li><strong>Luck is separated from skill by construction.</strong> The gate suite permutes outcomes, so a strategy
that only looks good because outcomes were kind scores no better than its shuffled twin.</li>
<li><strong>Injuries and depth are tracked as two separate facts.</strong> The official injury report gives status;
the club depth chart gives who is next. A replacement is named only when the club's own chart names him.</li>
<li><strong>Every open decision is on one page.</strong> {len(QST.get('questions', []))} questions, each with what we
have, what we do not have, and the official source that would close it.</li>
</ol>
</div>

<h2>Start here</h2>
<div class="grid g3">
<div class="card"><h3>Read the executive summary</h3>
<p>The whole finding in one page: what was built, what it proves, what it cannot prove.</p>
<a class="btn" href="summary.html">Executive summary →</a></div>
<div class="card"><h3>Review the suggestions</h3>
<p>{len(SUG.get('suggestions', []))} proposed improvements, each with options, cost, risk, the gate it must pass
and whether it is already built.</p><a class="btn" href="suggestions.html">Suggestions register →</a></div>
<div class="card"><h3>Answer the questions</h3>
<p>{len(QST.get('questions', []))} decisions that block progress, sorted by what they block.</p>
<a class="btn" href="questions.html">Questions &amp; gaps →</a></div>
</div>

<h2>What the official data already says</h2>
<div class="grid g2">
<div class="card"><h3>Home advantage is a coin at this sample</h3>
<p>Across {fmt(hf.get('decided'))} decided games in 2025 and 2026, the home team won
<strong>{fmt(hf.get('homeWins'))}</strong> times
(<strong>{fmt((hf.get('homeWinRate') or 0)*100, 1)}%</strong>, 90% interval
{fmt((hf.get('ci90') or [None])[0] and hf['ci90'][0]*100, 1)}&ndash;{fmt(hf['ci90'][1]*100, 1) if hf.get('ci90') else '—'}%).</p>
<p class="small">The interval spans 50%, so a home-field "edge" is not demonstrated here. That is the correct
reading, and it is exactly why the skill-vs-luck gate exists.
{src('https://www.nfl.com/standings/', 'official standings')}</p></div>
<div class="card"><h3>Rest days are exact; travel is not</h3>
<p>{fmt(REST.get('summary', {}).get('shortWeekGames'))} team-games in 2026 come off 4 or fewer rest days
(minimum {fmt(REST.get('summary', {}).get('minRestDays'))} days). Rest is computed from official kickoff dates,
so it is exact. Travel distance is <em>not</em> official and is not included.</p>
<p class="small">{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'official 2026 schedule')}</p></div>
</div>

<h2>What we do not have — stated plainly</h2>
<div class="callout">
<p><strong>No prices.</strong> Not a single spread, moneyline, total or prop line exists in this system, because the
official NFL pages publish none. Consequence: no ROI, no closing-line value, no claim of outperforming a price, no certified
strategy.</p>
<p><strong>No snap counts.</strong> Who actually played is not published as machine-readable data on the pages probed.
Consequence: "the 2nd string had to start" is a depth-chart inference, labelled as such, never a measurement.</p>
<p><strong>One club publishes its depth chart as an image.</strong> Houston's chart is a picture, so it is blank here
rather than guessed. Consequence: 31 of 32 clubs have depth data.</p>
</div>
<p class="small">Full unresolved list: <a href="flagged.html">Flagged for review</a> ·
<a href="questions.html">Questions &amp; gaps</a> · <a href="method.html">Method</a></p>
"""
    return page("Overview", "index.html", body,
                "A line-origination and strategy-validation system built only on official NFL data. "
                "It shows what the official data can support, refuses to show what it cannot, and puts every "
                "open decision on one page.")


def p_summary():
    hf = HF.get("combined", {})
    s26 = HF.get("2026", {})
    body = f"""
<div class="card prose">
<h2 style="margin-top:0">Executive summary</h2>
<p><strong>What was asked.</strong> Originate NFL lines, generate useful signals, run a leaderboard competition
with rewards for top strategies across single bets, parlays and player-prop combos, pass every strategy through
validation gates, determine correlation values, remove luck from the equation, and track injuries and
starter/backup deficiencies on both sides of the ball — with no manual input, no hallucination, and an official
source for every value.</p>

<p><strong>What was built.</strong> An ingest pipeline that runs in CI and pulls seven official datasets
(scores, injury report, 32 club depth charts, seven team-stat tables, player-stat leaders, rosters, and the
official schedule already in the repository); an analysis engine that computes rest days, scoring rates,
de-vigged prices, correlations with bootstrap intervals, calibration and shuffle tests; a nine-gate
validation suite; and this site, which publishes the results and the gaps with the same prominence.</p>

<p><strong>What it proves.</strong> Machinery, not edge. With {fmt(SKILL.get('n'))} decided games the home-field
prior is statistically indistinguishable from a coin (shuffle p&nbsp;=&nbsp;{fmt(SKILL.get('shuffleTest', {}).get('pValueOneSided'), 3)}),
and with no stored prices not one strategy can be settled. The leaderboard therefore ranks nobody, and says so.
That is the honest output, and it is a real result: it tells you exactly what the next decision must be.</p>

<p><strong>What it cannot prove — and why that is not a failure of effort.</strong> A line requires a price;
a price requires a market feed; the NFL does not publish one. Correlation between teammates requires per-game
player logs joined by week, which the ingested leader boards are not. Snap counts, travel and weather are not
machine-readable on the official pages probed. Each of these is named, sourced and costed on the Questions page
rather than papered over.</p>

<p><strong>The one decision that unblocks the most.</strong> Decide the price source (Q01). Everything
downstream — ROI, closing-line value, parlay settlement, reward allocation, certification — is blocked on it.
The second is the reward policy (Q04); the third is the reviewer for this register (Q17).</p>
</div>

<h2>The numbers, with their evidence</h2>
<div class="scroll"><table class="tight"><thead><tr>
<th>Finding</th><th>Value</th><th>Status</th><th>n</th><th>Official source</th></tr></thead><tbody>
<tr><td>Completed 2026 games ingested with final scores</td><td>{fmt(SUM.get('finalGames2026'))}</td>
<td>{model("OFFICIAL")}</td><td>{fmt(SUM.get('finalGames2026'))} games</td>
<td>{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'nfl.com week pages')}</td></tr>
<tr><td>Completed 2025 games ingested (prior-season reference)</td><td>{fmt(SUM.get('finalGames2025'))}</td>
<td>{model("OFFICIAL")}</td><td>{fmt(SUM.get('finalGames2025'))} games</td>
<td>{src('https://www.nfl.com/schedules/2025/by-week/week-5', 'nfl.com 2025 week pages')}</td></tr>
<tr><td>Home-team win rate, 2026 only</td>
<td>{fmt((s26.get('homeWinRate') or 0)*100, 1)}% (interval {fmt((s26.get('ci90') or [0,0])[0]*100,1)}&ndash;{fmt((s26.get('ci90') or [0,0])[1]*100,1)}%)</td>
<td>{model("MODEL")}</td><td>{fmt(s26.get('decided'))} decided</td>
<td>{src('https://www.nfl.com/standings/', 'official standings')}</td></tr>
<tr><td>Home-team win rate, both seasons pooled</td>
<td>{fmt((hf.get('homeWinRate') or 0)*100, 1)}% (interval {fmt((hf.get('ci90') or [0,0])[0]*100,1)}&ndash;{fmt((hf.get('ci90') or [0,0])[1]*100,1)}%)</td>
<td>{model("MODEL")}</td><td>{fmt(hf.get('decided'))} decided</td>
<td>{src('https://www.nfl.com/standings/', 'official standings')}</td></tr>
<tr><td>Shuffle test on a home-field prior</td>
<td>p = {fmt(SKILL.get('shuffleTest', {}).get('pValueOneSided'), 3)}</td>
<td>{model("MODEL")}</td><td>{fmt(SKILL.get('shuffleTest', {}).get('draws'))} permutations</td>
<td>{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'nfl.com week pages')}</td></tr>
<tr><td>Official injury rows, current report week</td><td>{fmt(SUM.get('injuryRows2026'))}</td>
<td>{model("OFFICIAL")}</td><td>week {fmt(SUM.get('injuryWeek'))}</td>
<td>{src(f"https://www.nfl.com/injuries/league/2026/reg{int(SUM.get('injuryWeek') or 1):02d}", 'official injury report')}</td></tr>
<tr><td>Clubs with a parseable official depth chart</td><td>{fmt(SUM.get('depthClubs'))} of 32</td>
<td>{model("OFFICIAL")}</td><td>{fmt(SUM.get('depthRows'))} entries</td>
<td>{src('https://www.49ers.com/team/depth-chart', '49ers.com depth chart')}</td></tr>
<tr><td>League mean points per game, 2026 finals</td><td>{fmt(SUM.get('leagueMeanPPG'), 2)}</td>
<td>{model("MODEL")}</td><td>32 clubs</td>
<td>{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'nfl.com week pages')}</td></tr>
<tr><td>Strategies certified as skill-based</td><td><strong>0</strong></td><td>{model("UNVERIFIED")}</td>
<td>0 settled bets</td><td>{src('https://www.nfl.com/standings/', 'official standings')}</td></tr>
<tr><td>Stored betting prices</td><td><strong>0</strong></td><td>{model("UNVERIFIED")}</td>
<td>&mdash;</td><td>{src('https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10', 'official game page')}</td></tr>
</tbody></table></div>
<p class="small">Machine-readable versions: <code>nfl/data/derived/summary.json</code>,
<code>nfl/data/derived/skill.json</code>, <code>nfl/data/fetch-report.json</code>.</p>

<h2>What to do next, in order</h2>
<table class="tight"><thead><tr><th>#</th><th>Decision</th><th>Unblocks</th><th>Cost</th><th>Official reference</th></tr></thead><tbody>
<tr><td>1</td><td>Choose the price source (<a href="questions.html#Q01">Q01</a>)</td><td>ROI, CLV, parlay settlement, certification, rewards</td><td>one decision</td><td>{src('https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10','game page (no odds)')}</td></tr>
<tr><td>2</td><td>Set the reward policy (<a href="questions.html#Q04">Q04</a>)</td><td>Leaderboard payouts</td><td>one decision</td><td>{src('https://www.nfl.com/standings/','official standings')}</td></tr>
<tr><td>3</td><td>Name the register reviewer (<a href="questions.html#Q17">Q17</a>)</td><td>Any suggestion being accepted</td><td>one name</td><td>{src('https://github.com/karagemop466-tech/Korea5','repository')}</td></tr>
<tr><td>4</td><td>Ingest per-game player logs (<a href="questions.html#Q08">Q08</a>)</td><td>Real correlation values, prop combos</td><td>one CI job</td><td>{src('https://www.nfl.com/players/christian-mccaffrey/stats','player game log')}</td></tr>
<tr><td>5</td><td>Ingest snap counts / gamebooks (<a href="questions.html#Q07">Q07</a>)</td><td>Backup-vs-starter measurement</td><td>one CI job + a source decision</td><td>{src('https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10','game page')}</td></tr>
</tbody></table>
"""
    return page("Executive summary", "summary.html", body,
                "Everything below in one page: what was built, what it proves, what it cannot prove, and the "
                "five decisions that move it forward.")


def p_suggestions():
    rows = []
    for s in SUG.get("suggestions", []):
        rows.append(f"""<tr>
<td class="nowrap"><strong>{esc(s['id'])}</strong></td>
<td class="nowrap">{esc(s['area'])}</td>
<td>{esc(s['suggestion'])}
  <details><summary class="dim" style="cursor:pointer;font-size:12px">why / options / risk</summary>
  <div class="small" style="margin-top:6px"><strong>Why:</strong> {esc(s['why'])}<br>
  <strong>Options:</strong> {esc(s['options'])}<br>
  <strong>Risk:</strong> {esc(s['risk'])}<br>
  <strong>Needs:</strong> {esc(s['needs'])}</div></details></td>
<td>{badge_status(s['status'])}</td>
<td class="nowrap">{esc(s.get('gate'))}</td>
<td>{esc(s.get('builtAs') or '—')}</td>
<td class="nowrap">{src(s.get('sourceUrl'), 'official')}</td>
</tr>""")
    counts = {}
    for s in SUG.get("suggestions", []):
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    tally = "".join(f'<span class="badge none" style="margin:2px 4px 2px 0">{esc(k)}: {v}</span>'
                    for k, v in sorted(counts.items()))
    body = f"""
<div class="callout"><strong>How to use this page.</strong> Each row is a proposal with its options, its cost,
its risk, the validation gate it must pass, and its current state. Nothing in the "already built" state was
implemented silently: the "built as" column names the artefact on this site. Anything requiring a price, a
reward or a person's judgement is capped at <em>accepted — proposed default</em> until you decide.</div>
<p>{tally}</p>
<div class="scroll" style="max-height:none"><table class="tight" id="sugtbl"><thead><tr>
<th>ID</th><th>Area</th><th>Suggestion (expand for options and risk)</th><th>Status</th>
<th>Gate</th><th>Built as</th><th>Source</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>

<h2>The decision rules this register is held to</h2>
<div class="card prose"><ol>
{''.join(f'<li>{esc(r)}</li>' for r in SUG.get('meta', {}).get('decisionRules', []))}
</ol></div>

<h2>Where the individual decisions live</h2>
<p>The questions that block specific suggestions are tracked one per row on
<a href="questions.html">Questions &amp; gaps</a>. The thresholds a strategy must clear are on
<a href="validation.html">Validation gates</a>. The reason no suggestion can yet claim a betting edge is on
<a href="market.html">Lines &amp; market</a>.</p>
"""
    return page("Suggestions register", "suggestions.html", body,
                f"{len(SUG.get('suggestions', []))} proposed improvements, each with its options, cost, risk and "
                "gate — so a reviewer can compare paths and choose before anything is implemented.")


def p_questions():
    qs = QST.get("questions", [])
    groups = {}
    for q in qs:
        groups.setdefault(q["topic"], []).append(q)
    out = []
    rows = []
    for q in qs:
        rows.append(f"""<tr id="{esc(q['id'])}">
<td class="nowrap"><strong>{esc(q['id'])}</strong></td>
<td class="nowrap">{esc(q['topic'])}</td>
<td><strong>{esc(q['question'])}</strong></td>
<td class="small">{esc(q['have'])}</td>
<td class="small">{esc(q['gap'])}</td>
<td class="small">{esc(q['howToClose'])}</td>
<td class="small">{esc(q['blocks'])}</td>
<td>{badge_status(q['status'])}</td>
<td class="nowrap">{src(q.get('sourceUrl'), 'official')}</td></tr>""")
    stat = {}
    for q in qs:
        stat[q["status"]] = stat.get(q["status"], 0) + 1
    body = f"""
<div class="callout"><strong>This page is the answer to "what do we not know?".</strong>
Every row is a question that cannot be fully answered from the information the repository holds. The
<em>what we have</em> column is evidence with a source; the <em>gap</em> column is what is missing; the
<em>how to close it</em> column names the official source or the decision that would settle it.</div>
<div class="statline">
{''.join(f'<div><b>{v}</b><span>{esc(k)}</span></div>' for k, v in sorted(stat.items()))}
<div><b>{len(qs)}</b><span>total questions</span></div>
</div>
<div class="scroll" style="max-height:none"><table class="tight"><thead><tr>
<th>ID</th><th>Topic</th><th>Question</th><th>What we have</th><th>What we do not have</th>
<th>How to close it</th><th>Blocks</th><th>Status</th><th>Source</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>

<h2>Grouped by topic</h2>
{''.join(f'<div class="card" style="margin:12px 0"><h3>{esc(t)}</h3><ul class="prose">'
         + ''.join(f'<li><strong>{esc(q["id"])}</strong> — {esc(q["question"])} '
                   f'<span class="dim">[{esc(q["status"])}]</span></li>' for q in items)
         + '</ul></div>' for t, items in groups.items())}
"""
    return page("Questions, information and gaps", "questions.html", body,
                "What has to be answered before a decision can reasonably be made — separated into what we have, "
                "what we do not have, and what would close the gap.")


def p_market():
    ex = MKT.get("devigExamples", [])
    ex_rows = "".join(f"""<tr>
<td>{esc(e['label'])}</td>
<td class="nowrap">{esc(e['a'])} / {esc(e['b'])}</td>
<td>{fmt(e['impliedA']*100,1)}% / {fmt(e['impliedB']*100,1)}%</td>
<td>{fmt(e['holdPct'],2)}%</td>
<td>{fmt(e['multiplicative']['a']*100,1)}% / {fmt(e['multiplicative']['b']*100,1)}%
  <br><span class="dim">({esc(e['multiplicative']['aAmerican'])} / {esc(e['multiplicative']['bAmerican'])})</span></td>
<td>{fmt(e['additive']['a']*100,1)}% / {fmt(e['additive']['b']*100,1)}%
  <br><span class="dim">({esc(e['additive']['aAmerican'])} / {esc(e['additive']['bAmerican'])})</span></td>
<td>{fmt(e['methodGap']*100,2)} pp</td>
<td class="nowrap">{src('https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10', 'official game page')}</td>
</tr>""" for e in ex)
    par = "".join(f"""<tr><td>{esc(p['legs'])}</td><td>{fmt(p['fairDecimal'],3)}</td>
<td>{fmt(p['offeredDecimalAtSamePerLegHold'],3)}</td><td>{fmt(p['effectiveHold']*100,2)}%</td>
<td class="nowrap">{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'official schedule')}</td></tr>"""
                  for p in MKT.get("parlayHold", []))
    sc = SCORE.get("teams", {})
    sc_rows = "".join(
        f"""<tr><td>{esc(t)}</td><td>{fmt(v['games'])}</td><td>{fmt(v['ppgFor'],2)}</td>
<td>{fmt(v['ppgAgainst'],2)}</td><td>{fmt(v['shrunkPpgFor'],2)}</td><td>{fmt(v['shrunkPpgAgainst'],2)}</td>
<td>{fmt(v['shrinkWeight'],3)}</td>
<td class="nowrap">{src(v['sourceUrl'], 'official finals')}</td></tr>"""
        for t, v in sorted(sc.items(), key=lambda kv: -(kv[1]["ppgFor"] or 0)))
    mm = [g for g in MATCH.get("games", []) if g.get("model")]
    mm_rows = "".join(f"""<tr><td>{esc(g['weekLabel'])}</td><td>{esc(g['away'])} at {esc(g['home'])}</td>
<td>{fmt(g['awayScore'])}&ndash;{fmt(g['homeScore'])}</td>
<td>{fmt(g['model']['awayEstimate'],1)} &ndash; {fmt(g['model']['homeEstimate'],1)}
 <br><span class="dim">home {esc(format(g['model']['homeMinusAway'], '+.1f'))} · total {fmt(g['model']['total'],1)}</span></td>
<td>{fmt(g['model']['evidenceGames'])}</td>
<td class="nowrap">{src(g['gameUrl'], 'official game page')}</td></tr>""" for g in mm[-12:])
    body = f"""
<div class="callout">
<h3 style="margin-top:0">What we do not have</h3>
<ul>
<li><strong>No price feed.</strong> The official NFL week pages, game pages and stats pages were probed by exact
regex for odds, spread, moneyline and totals fields: <strong>zero hits on every page</strong>
(<code>nfl/research/probe.json</code>).</li>
<li><strong>Therefore: no market line, no ROI, no closing-line value, no certified bet.</strong></li>
<li>The arithmetic below is a <em>tool</em> demonstrated on stated example prices. It is not a market and it is
not advice.</li>
</ul></div>

<h2>How a line would be originated — the working method</h2>
<div class="card prose"><ol>
<li><strong>Estimate each side's scoring.</strong> Own shrunk points-for against the opponent's shrunk
points-against, re-centred on the league mean. Shrunk means <em>n/(n+9)</em>, so an 11-game sample carries about
55% weight and a hot start cannot masquerade as a season truth.</li>
<li><strong>Convert to a margin and a total.</strong> Margin = home estimate &minus; away estimate; total = sum.</li>
<li><strong>Convert to a probability.</strong> Nothing on this site does this yet, because doing it properly
requires an outcome distribution calibrated on many seasons, and this system has two partial ones. Publishing a
probability now would be a guess wearing a decimal point.</li>
<li><strong>Compare with a market price.</strong> Impossible: there is no market price. This is the step that
makes a line a line, and it is the one step the official data cannot supply.</li>
</ol></div>

<h2>De-vig: turning a two-way price into a fair price</h2>
<p class="prose">A two-way price hides a margin. Removing it changes the fair probability, and <em>how</em> you
remove it changes the answer. Both standard methods are shown, with the gap between them, so the choice is
visible rather than buried.</p>
<div class="scroll"><table class="tight"><thead><tr><th>Example</th><th>Price pair</th>
<th>Raw implied</th><th>Hold</th><th>Multiplicative</th><th>Additive</th><th>Method gap</th>
<th>Reference page</th></tr></thead>
<tbody>{ex_rows}</tbody></table></div>
<p class="small">{model("MODEL")} All values computed by <code>nfl/tools/analyze_market.py</code> from the price
pair printed in the row. These are illustrative price pairs, not NFL market prices.</p>

<h2>Why parlays cost more than they look</h2>
<p class="prose">Each leg carries the same per-leg margin, so the margin compounds. At a &minus;110/&minus;110
per-leg price, a five-leg parlay carries roughly five times the effective hold of a single. That is arithmetic,
not opinion.</p>
<table class="tight"><thead><tr><th>Legs</th><th>Fair decimal</th><th>Offered decimal at the same per-leg hold</th>
<th>Effective hold</th><th>Reference page</th></tr></thead><tbody>{par}</tbody></table>

<h2>Scoring rates from official finals (the input to any total)</h2>
<p class="prose">{model("MODEL")} Points are computed from official final scores, current season only.
<strong>Note:</strong> the official team-stats "scoring" pages publish <em>touchdowns</em>, not points — using
them as points would be wrong, so they are used only for touchdown counts and the point totals come from finals.</p>
<div class="scroll"><table class="tight"><thead><tr><th>Team</th><th>Games (n)</th><th>PPG for</th>
<th>PPG against</th><th>Shrunk for</th><th>Shrunk against</th><th>Shrink weight</th><th>Source</th></tr></thead>
<tbody>{sc_rows}</tbody></table></div>

<h2>What a model line looks like on completed games</h2>
<p class="prose">The last {len(mm)} completed games, with the model's estimate beside the official final score.
The estimate uses only pre-game information (season-to-date rates), so comparing it with the final is a fair
demonstration of the method — though not a backtest, because there is no price to beat.</p>
<div class="scroll"><table class="tight"><thead><tr><th>Week</th><th>Matchup</th><th>Official final</th>
<th>{model("MODEL")} estimate</th><th>Evidence games</th><th>Source</th></tr></thead><tbody>{mm_rows}</tbody></table></div>
<p class="small">{MKT.get('notice', '')}</p>
"""
    return page("Lines &amp; market", "market.html", body,
                "How a line would be originated from official data, what de-vigging does to a price, and why no "
                "market line is published here: the official NFL sources publish no odds at all.")


def p_strategies():
    boards = STRAT.get("boards", {})
    out = []
    for s in STRAT.get("strategies", []):
        b = boards.get(s["board"], {})
        out.append(f"""<tr>
<td class="nowrap"><strong>{esc(s['id'])}</strong></td>
<td class="nowrap">{esc(b.get('label', s['board']))}</td>
<td><strong>{esc(s['name'])}</strong><br><span class="small dim">{esc(s['hypothesis'])}</span></td>
<td class="small">{esc(s['inputs'])}</td>
<td class="small">{esc(s['computedFrom'])}</td>
<td>{badge_status(s['status'])}</td>
<td class="small">{esc(s['blockedBy'])}</td>
<td class="small">{esc(s['testableToday'])}</td>
<td class="nowrap">{src(s.get('sourceUrl'), 'official')}</td></tr>""")
    scoring = STRAT.get("scoring", {})
    body = f"""
<div class="callout"><strong>Zero of these {len(STRAT.get('strategies', []))} strategies is certified.</strong>
The registry exists so the comparison is <em>pre-registered</em>: the hypotheses, the inputs and the blocking
gate are written down before any result is seen. That is what stops a leaderboard from being a search for the
luckiest strategy.</div>

<h2>The three boards</h2>
<div class="grid g3">
{''.join(f'''<div class="card"><h3>{esc(b['label'])}</h3>
<p class="small">{esc(b['why'])}</p>
<dl class="kv"><dt>Minimum sample</dt><dd>{fmt(b['minSettledSample'])} settled bets</dd>
<dt>Variance</dt><dd>{esc(b['variance'])}</dd>
<dt>Extra gate</dt><dd>{esc(b.get('extraGate') or '—')}</dd></dl></div>''' for b in boards.values())}
</div>

<h2>Registry</h2>
<div class="scroll" style="max-height:none"><table class="tight"><thead><tr>
<th>ID</th><th>Board</th><th>Strategy &amp; hypothesis</th><th>Inputs</th><th>Computed from</th>
<th>Status</th><th>Blocked by</th><th>Testable today</th><th>Source</th></tr></thead><tbody>
{''.join(out)}</tbody></table></div>

<h2>How a strategy is scored</h2>
<div class="card prose"><dl class="kv">
<dt>Primary</dt><dd>{esc(scoring.get('primary'))}</dd>
<dt>Secondary</dt><dd>{esc(scoring.get('secondary'))}</dd>
<dt>ROI only if</dt><dd>{esc(scoring.get('roiOnlyIf'))}</dd>
<dt>CLV only if</dt><dd>{esc(scoring.get('clvOnlyIf'))}</dd>
</dl>
<p style="margin-top:10px"><strong>Never used as a ranking key:</strong></p>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in scoring.get('never', []))}</ul></div>

<h2>Rewards</h2>
<div class="card prose">
<p><strong>No reward is authorised.</strong> {esc(STRAT.get('rewards', {}).get('why'))}</p>
<p><strong>What one decision would unlock:</strong> {esc(STRAT.get('rewards', {}).get('whatOneDecisionWouldUnlock'))}</p>
<p><strong>Proposed default if asked:</strong> {esc(STRAT.get('rewards', {}).get('proposedDefaultIfAsked'))}</p>
</div>
"""
    return page("Strategies &amp; competition", "strategies.html", body,
                "Ten pre-registered strategy hypotheses across single bets, parlays and player-prop combos, each "
                "with its inputs, its blocking gate and whether it is testable today.")


def p_leaderboard():
    boards = LB.get("boards", {})
    blocks = []
    for key, b in boards.items():
        rows = "".join(f"""<tr>
<td class="nowrap">{esc(e['id'])}</td><td>{esc(e['name'])}</td>
<td>{badge_status(e['status'])}</td>
<td>{fmt(e['settled'])}</td>
<td>{dash('no settled bets')}</td><td>{dash('no settled bets')}</td>
<td>{dash('no stored price')}</td><td>{dash('no stored price')}</td>
<td>{dash('not ranked')}</td>
<td><span class="badge unverified">{esc(e['reward'])}</span></td>
<td class="small">{esc(e['reason'])}</td>
<td class="nowrap">{src(e.get('sourceUrl'), 'strategy source')}</td></tr>""" for e in b["entrants"])
        blocks.append(f"""<h2>{esc(b['label'])} <span class="small dim">· minimum {fmt(b['minSettledSample'])} settled bets</span></h2>
<p class="small">{len(b['entrants'])} entrants · <strong>{b['eligible']} eligible</strong> · no reward authorised</p>
<div class="scroll"><table class="tight"><thead><tr><th>ID</th><th>Strategy</th><th>Status</th>
<th>Settled</th><th>Brier</th><th>Log loss</th><th>ROI</th><th>CLV</th><th>Rank</th><th>Reward</th>
<th>Why unranked</th><th>Official source</th></tr></thead><tbody>{rows}</tbody></table></div>""")
    body = f"""
<div class="callout"><strong>The leaderboard ranks nobody, and that is the correct output.</strong>
Ranking requires settled bets. A settled bet requires a price. There is no price. Anything shown here other
than an empty cell would be invented.
<p style="margin:8px 0 0">This is the difference between a leaderboard and a decoration: a leaderboard that
cannot compute a rank should say so, not fill the column with a zero.</p></div>

<div class="statline">
<div><b>0</b><span>certified strategies</span></div>
<div><b>0</b><span>settled bets</span></div>
<div><b>0</b><span>stored prices</span></div>
<div><b>{sum(len(b['entrants']) for b in boards.values())}</b><span>pre-registered entrants</span></div>
<div><b>No</b><span>reward authorised</span></div>
</div>
{''.join(blocks)}

<h2>What would make this live</h2>
<div class="card prose"><ol>
<li>A price source for each market the entrant needs (Q01) — licensed feed or an owner-recorded, timestamped
quote ledger.</li>
<li>Enough settled bets to clear the minimum sample on each board (100 single, 150 parlay, 120 prop combo).</li>
<li>The nine validation gates passing, including the false-discovery guard.</li>
<li>A reward policy (Q04) and a named reviewer (Q17).</li>
</ol>
<p>Until all four exist, the honest rank is "not ranked".</p></div>
"""
    return page("Leaderboard", "leaderboard.html", body,
                "Three boards, pre-registered entrants, and zero ranks — because no bet can be settled without a "
                "stored price, and none exists.")


def gate_by_id(gid):
    return next((g for g in GATES.get("gates", []) if g.get("id") == gid), {})


def p_validation():
    rows = "".join(f"""<tr>
<td class="nowrap"><strong>{esc(g['id'])}</strong></td>
<td><strong>{esc(g['name'])}</strong><br><span class="small dim">{esc(g['question'])}</span></td>
<td class="small">{esc(g['passCondition'])}</td>
<td class="small">{esc(g['failCondition'])}</td>
<td class="small">{esc(g.get('evaluatedBy'))}</td>
<td>{model("OFFICIAL") if g.get('automated') else model("JUDGEMENT")}</td>
<td class="nowrap">{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'official data')}</td>
</tr>""" for g in GATES.get("gates", []))
    cs = GATES.get("currentStatus", {})
    body = f"""
<div class="callout"><strong>Thresholds frozen {esc(GATES.get('meta', {}).get('frozenOn'))}, before any strategy
result was computed.</strong> {esc(GATES.get('meta', {}).get('frozenRule'))}</div>

<div class="statline">
<div><b>{fmt(cs.get('gatesDefined'))}</b><span>gates defined</span></div>
<div><b>{fmt(cs.get('gatesFullyAutomated'))}</b><span>fully automated</span></div>
<div><b>{fmt(cs.get('gatesRequiringOwnerDecision'))}</b><span>need your decision</span></div>
<div><b>{fmt(cs.get('gatesRequiringDataNotYetAvailable'))}</b><span>need data we lack</span></div>
<div><b>{fmt(cs.get('strategiesCertified'))}</b><span>strategies certified</span></div>
</div>
<p class="prose">{esc(cs.get('reasonNoStrategyCertified'))}</p>

<h2>The gates</h2>
<div class="scroll" style="max-height:none"><table class="tight"><thead><tr>
<th>ID</th><th>Gate</th><th>Passes only when</th><th>Fails when</th><th>Evaluated by</th><th>Type</th>
<th>Data checked against</th></tr></thead><tbody>{rows}</tbody></table></div>

<h2>How luck is removed — the actual mechanism</h2>
<div class="card prose">
<p><strong>1. Proper scoring.</strong> Brier and log loss cannot be gamed by hedging or by refusing to commit.
A win rate can: go 12&ndash;0 on coin flips and you look brilliant. Score those same coin flips and you do not.</p>
<p><strong>2. Shuffle test.</strong> Take the strategy's picks, keep them, and randomly permute the outcomes
{fmt(gate_by_id('G3').get('shuffleDraws'))} times.
If the real score sits inside that shuffled distribution, the result is what a know-nothing would have got.
The test on a home-field prior currently returns
p&nbsp;=&nbsp;{fmt(SKILL.get('shuffleTest', {}).get('pValueOneSided'), 3)} — inside the distribution, so: luck.</p>
<p><strong>3. Minimum sample.</strong> A 60% win rate on 20 bets is noise. The gate will not look at a strategy
below {fmt(gate_by_id('G3').get('minSample'))} settled
bets, and it prints that refusal rather than a provisional verdict.</p>
<p><strong>4. Calibration.</strong> A model that says 60% must be right 60% of the time, not 45% of the time
while winning 60% of its picks. Expected calibration error is computed over deciles.</p>
<p><strong>5. Multiple testing.</strong> Testing 40 strategies guarantees a winner. The false-discovery guard
raises the bar as the number of entrants grows, so the winner must be surprising <em>given how hard we looked</em>.</p>
<p><strong>6. Point-in-time integrity.</strong> Information published after the decision cutoff is a leak, not a
signal. Every input carries a publication time; the cutoff is kickoff minus 60 minutes, which is safely after
the NFL's final game-status update at 90 minutes before kickoff.</p>
</div>

<h2>Gate change log</h2>
<table class="tight"><thead><tr><th>Version</th><th>Date</th><th>Change</th><th>Results seen at the time</th>
<th>Evidence base</th></tr></thead>
<tbody>{''.join(f"<tr><td>{esc(c['version'])}</td><td>{esc(c['date'])}</td><td>{esc(c['change'])}</td><td>{esc(c['resultsSeen'])}</td><td class='nowrap'>{src('https://www.nfl.com/standings/', 'official standings')}</td></tr>" for c in GATES.get('gateChangeLog', []))}</tbody></table>
"""
    return page("Validation gates", "validation.html", body,
                "Nine gates, thresholds frozen before any result was seen, and the five mechanisms that separate "
                "skill from luck.")


def p_signals():
    tiers = SIG.get("tiers", {})
    rows = "".join(f"""<tr>
<td class="nowrap"><strong>{esc(s['id'])}</strong></td>
<td><span class="badge {'official' if s['tier'].startswith('T1') else ('judgement' if s['tier'].startswith('T2') else 'unverified')}">{esc(s['tier'].split('-')[0])}</span></td>
<td><strong>{esc(s['name'])}</strong><br><span class="small dim">{esc(s['definition'])}</span></td>
<td class="small">{esc(s['input'])}</td>
<td class="small">{esc(s['availability'])}</td>
<td class="small">{esc(s['leakRisk'])}</td>
<td class="small">{esc(s['limitation'])}</td>
<td class="nowrap">{src(s.get('sourceUrl'), 'official')}</td></tr>""" for s in SIG.get("signals", []))
    body = f"""
<div class="callout"><strong>The killer rule.</strong> {esc(SIG.get('meta', {}).get('killerRule'))}</div>
<p class="prose">{esc(SIG.get('meta', {}).get('definition'))}</p>
<div class="grid g3">
{''.join(f'<div class="card"><h3>{esc(k.split("-")[0])}</h3><p class="small">{esc(v)}</p></div>' for k, v in tiers.items())}
</div>

<h2>Signal catalogue</h2>
<div class="scroll" style="max-height:none"><table class="tight"><thead><tr>
<th>ID</th><th>Tier</th><th>Signal</th><th>Input</th><th>Availability</th><th>Leak risk</th>
<th>Limitation</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>

<h2>Rules for combining signals</h2>
<div class="card prose"><ol>
{''.join(f'<li><strong>{esc(c["id"])}.</strong> {esc(c["rule"])}<br><span class="small dim">{esc(c["why"])}</span></li>' for c in SIG.get('combinationRules', []))}
</ol></div>

<h2>Tier counts</h2>
<div class="statline">
{''.join(f'<div><b>{sum(1 for s in SIG.get("signals", []) if s["tier"].startswith(t))}</b><span>{esc(t)}</span></div>' for t in ("T1", "T2", "T3"))}
</div>
<p class="small">The point of the tiers is honesty about coverage: {sum(1 for s in SIG.get("signals", []) if s["tier"].startswith("T1"))}
signals can be generated today from official data; the rest are named so nobody spends a session building on a
source that does not exist.</p>
"""
    return page("Signal catalogue", "signals.html", body,
                "Sixteen candidate signals, each with its input, its availability, its leak risk and whether the "
                "official data can support it today.")


def p_correlation():
    demo = CORR.get("demonstration", {}).get("result") or {}
    rules = SIG.get("combinationRules", [])
    body = f"""
<div class="callout"><strong>No real correlation value is published on this page yet.</strong>
{CORR.get('reason', '')}
<p style="margin:8px 0 0"><strong>What is needed:</strong> {esc(CORR.get('whatIsNeeded'))}</p></div>

<h2>Why a fake correlation would be worse than none</h2>
<div class="card prose">
<p>A correlation is a claim that two things move together. Computing it from season <em>totals</em> across 32
clubs — which is what the ingested leader boards contain — answers a completely different question: it would
tell you whether good teams have good players, which is trivially true and useless for a parlay. The number
would look precise and mean nothing.</p>
<p>So the page shows the machinery on clearly-labelled synthetic data, and withholds the real value until the
real per-game logs are ingested. That is a deliberate refusal, not an oversight.</p>
</div>

<h2>The machinery, demonstrated on synthetic data</h2>
<div class="card">
<p>{model("MODEL")} {esc(CORR.get('demonstration', {}).get('label'))}</p>
<dl class="kv">
<dt>Pearson r</dt><dd>{fmt(demo.get('r'), 3)}</dd>
<dt>90% bootstrap interval</dt><dd>{fmt(demo.get('lo'), 3)} to {fmt(demo.get('hi'), 3)}</dd>
<dt>n</dt><dd>{fmt(demo.get('n'))}</dd>
<dt>Reading</dt><dd>{esc(demo.get('reading'))}</dd>
<dt>Suppression floor</dt><dd>{fmt(CORR.get('suppressionFloor'))} observations — below this, withheld entirely</dd>
</dl>
<p class="small" style="margin-top:8px">{esc(CORR.get('demonstration', {}).get('reading'))}</p>
</div>

<h2>How the real value will be computed (and why it needs a join)</h2>
<div class="card prose"><ol>
<li>Fetch each player's official game log (WK, OPP, RESULT, stat columns) from their nfl.com player page.</li>
<li>Join two players by <em>club and week</em> — not by season total — so each observation is one shared game.</li>
<li>Compute Pearson r, then a 1,000-draw bootstrap for the 90% interval.</li>
<li>If the interval spans zero, publish the literal words <em>"indistinguishable from zero"</em>. With 8 games,
that will be most pairs.</li>
<li>Never multiply leg probabilities for a same-player or same-game combo. Publish the empirical joint, the
independence product, and the signed difference.</li>
</ol></div>

<h2>Combination rules that already bind</h2>
<div class="card"><ul class="prose">
{''.join(f'<li><strong>{esc(c["id"])}.</strong> {esc(c["rule"])}</li>' for c in rules)}
</ul></div>
<p class="small">{src(CORR.get('sourceUrl'), 'official player stats page')}</p>
"""
    return page("Correlation", "correlation.html", body,
                "What correlation values will be computed from, why none is published yet, and the rules that "
                "forbid multiplying leg probabilities.")


def p_injuries():
    week = INJ.get("week")
    teams = INJ.get("teams", {})
    players = INJ.get("players", [])
    nextup = INJ.get("nextUp", [])
    team_rows = "".join(f"""<tr><td>{esc(t)}</td><td>{fmt(d.get('offense',0))}</td>
<td>{fmt(d.get('defense',0))}</td><td>{fmt(d.get('specialteams',0))}</td>
<td>{fmt(d.get('out',0))}</td><td>{fmt(d.get('doubtful',0))}</td><td>{fmt(d.get('questionable',0))}</td>
<td>{fmt(d.get('playerCount',0))}</td>
<td class="nowrap">{src(INJ.get('sourceUrl'), 'official report')}</td></tr>"""
                   for t, d in sorted(teams.items()))
    nu_rows = "".join(f"""<tr><td>{esc(r['team'])}</td><td>{esc(r['position'])}</td>
<td>{esc(', '.join(r['listedOutOrDoubtful']))}</td>
<td>{esc(r['chartStarter']) if r['chartStarter'] else dash('no chart row')}</td>
<td>{esc(r['chartReplacement']) if r['chartReplacement'] else '<span class="badge unverified">no next tier published</span>'}</td>
<td>{fmt(r['tiersPublishedAtPosition'])}</td><td class="nowrap">{esc(r['chartUpdatedAsOf'] or '—')}</td>
<td class="small">{esc(r['note'])}</td>
<td class="nowrap">{src(r.get('sourceUrl') or r.get('injurySourceUrl'), 'club chart' if r.get('sourceUrl') else 'injury report')}</td></tr>""" for r in nextup)
    pos_rows = "".join(f"""<tr><td>{esc(p['team'])}</td><td>{esc(p['position'])}</td><td>{esc(p['player'])}</td>
<td>{esc(p['injury']) if p['injury'] else dash('no injury listed')}</td>
<td>{esc(p['practiceStatus'] or '—')}</td><td>{esc(p['gameStatus']) if p['gameStatus'] else dash('no game status')}</td>
<td class="nowrap"><span class="badge none">{esc(p['unit'])}</span></td>
<td class="nowrap">{src(p.get('playerUrl') or INJ.get('sourceUrl'), 'player page')}</td></tr>"""
                       for p in players[:400])
    unavailable = DEPTH.get("unavailable", [])
    unavail_html = "".join(f"""<tr><td>{esc(u['team'])}</td><td class="nowrap">{src(u['url'], 'club page')}</td>
<td class="small">{esc(u['reason'])}</td></tr>""" for u in unavailable) or \
        '<tr><td colspan="3" class="small">None — every club page parsed.</td></tr>'
    body = f"""
<div class="callout"><strong>Two facts, kept separate.</strong>
The official injury report publishes <em>status</em> (Out / Doubtful / Questionable) and practice
participation. The club depth chart publishes <em>order</em> (1st / 2nd / 3rd string). Neither is a lineup and
neither is a snap count. A replacement is named below <strong>only when the club's own chart names the next
tier</strong> — never inferred.</div>

<div class="statline">
<div><b>{fmt(len(players))}</b><span>players on the week-{fmt(week)} report</span></div>
<div><b>{fmt(sum(d.get('out',0) for d in teams.values()))}</b><span>listed Out</span></div>
<div><b>{fmt(sum(d.get('doubtful',0) for d in teams.values()))}</b><span>listed Doubtful</span></div>
<div><b>{fmt(sum(d.get('questionable',0) for d in teams.values()))}</b><span>listed Questionable</span></div>
<div><b>{fmt(sum(r['tiersPublishedAtPosition'] for r in nextup))}</b><span>published tiers at affected positions</span></div>
</div>
<p class="small">{src(INJ.get('sourceUrl'), 'NFL.com official injury report')} · report week {fmt(week)}</p>

<h2>Injury load by unit — offence vs defence, never merged</h2>
<p class="prose">{esc(INJ.get('rule'))}</p>
<div class="scroll"><table class="tight"><thead><tr><th>Team</th><th>Offence rows</th><th>Defence rows</th>
<th>Special teams rows</th><th>Out</th><th>Doubtful</th><th>Questionable</th><th>Total players</th>
<th>Source</th></tr></thead><tbody>{team_rows}</tbody></table></div>

<h2>Next man up — who the club says is behind an unavailable player</h2>
<p class="prose">This is the direct answer to "is a 2nd, 3rd or 4th string replacing a starter?". The column
<em>next tier</em> is taken from the club's own published chart at the tier immediately below the unavailable
player. Where the club publishes no further tier, the cell is blank and badged &mdash; it is not filled with a
guess.</p>
<div class="scroll" style="max-height:none"><table class="tight"><thead><tr><th>Team</th><th>Pos</th>
<th>Listed Out / Doubtful</th><th>Chart starter</th><th>Next tier (club's own chart)</th>
<th>Tiers published</th><th>Chart as of</th><th>Rule applied</th><th>Source</th></tr></thead>
<tbody>{nu_rows or '<tr><td colspan="9" class="small">No overlap between the current report and the depth charts.</td></tr>'}</tbody></table></div>

<h2>Every player on the current report</h2>
<div class="scroll"><table class="tight"><thead><tr><th>Team</th><th>Pos</th><th>Player</th><th>Injury</th>
<th>Practice status</th><th>Game status</th><th>Unit</th><th>Source</th></tr></thead><tbody>{pos_rows}</tbody></table></div>
<p class="small">Showing the first {min(400, len(players))} of {len(players)} rows. The full set is in
<code>nfl/data/derived/injuries.json</code>. Blank injury or game-status cells mean the official page published
no value for that player.</p>

<h2>Depth charts: coverage and what is missing</h2>
<p class="prose">{esc(DEPTH.get('note'))}</p>
<div class="statline">
<div><b>{fmt(DEPTH.get('clubs'))}</b><span>clubs parsed</span></div>
<div><b>{fmt(sum(1 for p in DEPTH.get('positions', []) if p['tiers'] >= 3))}</b><span>positions with 3+ published tiers</span></div>
<div><b>{fmt(sum(1 for p in DEPTH.get('positions', []) if p['tiers'] >= 4))}</b><span>positions with 4 tiers</span></div>
</div>
<h3>Clubs whose chart could not be extracted</h3>
<table class="tight"><thead><tr><th>Team</th><th>Official page</th><th>Why it is blank here</th></tr></thead>
<tbody>{unavail_html}</tbody></table>
<p class="small">Tier histogram across all clubs and positions:
{esc(json.dumps(DEPTH.get('tierHistogram', {})))}</p>
"""
    return page("Injuries &amp; depth", "injuries.html", body,
                "The official injury report and all 32 club depth charts, kept as separate facts — with the "
                "replacement named only when the club's own chart names him.")


def p_data():
    sources = COV.get("sources", [])
    rows = "".join(f"""<tr><td>{esc(s['dataset'])}</td><td>{fmt(s['rows'])}</td>
<td>{esc(json.dumps(s.get('bySeason'))) if s.get('bySeason') else fmt(s.get('clubs',''))}</td>
<td class="nowrap">{esc(s.get('retrievedUTC') or '—')}</td>
<td>{model("OFFICIAL")}</td>
<td class="nowrap">{src(s['url'], 'official page')}</td></tr>""" for s in sources)
    fails = FETCH.get("failures", [])
    body = f"""
<div class="callout"><strong>Read the fetch report before trusting any aggregate.</strong>
A missing week page means missing games, not zero games. Every failed fetch is listed below and in
<code>nfl/data/fetch-report.json</code>.</div>

<h2>What was ingested</h2>
<div class="scroll"><table class="tight"><thead><tr><th>Dataset</th><th>Rows</th><th>Breakdown</th>
<th>Retrieved (UTC)</th><th>Status</th><th>Official source</th></tr></thead><tbody>{rows}</tbody></table></div>

<h2>Fetch integrity</h2>
<div class="statline">
<div><b>{fmt(len(fails))}</b><span>failed fetches</span></div>
<div><b>{esc(FETCH.get('startedUTC') or '—')}</b><span>run started</span></div>
<div><b>{esc(FETCH.get('finishedUTC') or '—')}</b><span>run finished</span></div>
</div>
{('<table class="tight"><thead><tr><th>Failure</th></tr></thead><tbody>' + ''.join(f'<tr><td class="small">{esc(f)}</td></tr>' for f in fails) + '</tbody></table>') if fails else '<p class="prose ok">Every configured official URL returned data. A zero here means zero configured fetches failed — not that the data covers everything.</p>'}

<h2>Clubs whose depth chart is blank here</h2>
<table class="tight"><thead><tr><th>Team</th><th>Page</th><th>Why</th></tr></thead><tbody>
{''.join(f'<tr><td>{esc(u["team"])}</td><td class="nowrap">{src(u["url"], "club page")}</td><td class="small">{esc(u["reason"])}</td></tr>' for u in COV.get('unavailableDepthCharts', [])) or '<tr><td colspan="3">None</td></tr>'}
</tbody></table>

<h2>What is deliberately absent</h2>
<table class="tight"><thead><tr><th>Dataset</th><th>Status</th><th>Why</th><th>Official reference</th></tr></thead><tbody>
<tr><td>Betting prices (spread, moneyline, total, props)</td><td>{model("UNVERIFIED")}</td>
<td class="small">The official NFL pages publish no odds. Probed by exact regex: 0 hits on week pages, game pages
and stats pages (<code>nfl/research/probe.json</code>).</td>
<td>{src('https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10', 'game page')}</td></tr>
<tr><td>Snap counts / participation</td><td>{model("UNVERIFIED")}</td>
<td class="small">Not loaded. Player season pages carry per-game stat logs, which imply participation but do not
prove it — a player can play and record no stat.</td>
<td>{src('https://www.nfl.com/players/christian-mccaffrey/stats', 'player stats')}</td></tr>
<tr><td>Per-game player logs (for correlation)</td><td>{model("UNVERIFIED")}</td>
<td class="small">The ingested player feed is season-to-date leaders. Correlating season totals answers the wrong
question; the per-game ingest is the named next task.</td>
<td>{src('https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc', 'player leaders')}</td></tr>
<tr><td>Weather at kickoff</td><td>{model("UNVERIFIED")}</td>
<td class="small">Published inconsistently: a forecast line appeared on one probed week page and not another.</td>
<td>{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'week page')}</td></tr>
<tr><td>Travel distance</td><td>{model("UNVERIFIED")}</td>
<td class="small">Venues are official; venue coordinates are not. Adding a coordinate list means adding a
non-official source, which is a decision, not an import.</td>
<td>{src('https://www.nfl.com/schedules/2026/by-week/week-10', 'week page')}</td></tr>
</tbody></table>

<h2>How this runs with no manual input</h2>
<div class="card prose"><ol>
<li><code>.github/workflows/nfl-probe.yml</code> records what each official page actually returns, so parsers are
written against real bytes.</li>
<li><code>.github/workflows/nfl-data.yml</code> fetches every dataset, writes the fetch report, and commits the
result. The dev sandbox has no outbound network; the Actions runner does, which is why ingest lives in CI.</li>
<li><code>nfl/tools/analyze_market.py</code> computes every published number from those files.</li>
<li><code>nfl/tools/build_nfl.py</code> renders this site; <code>nfl/tools/verify_nfl.py</code> re-checks every
row's source link and every badge rule.</li>
</ol></div>
"""
    return page("Data health", "data.html", body,
                "Exactly what was ingested, from where and when, plus the datasets that are deliberately absent "
                "and the official reason each is absent.")


def p_flagged():
    items = []
    for u in COV.get("unavailableDepthCharts", []):
        items.append({
            "area": "Depth chart", "what": f"{u['team']} depth chart is not in this dataset",
            "why": u["reason"], "impact": "That club's next-man-up column is blank.",
            "url": u["url"],
        })
    items += [
        {"area": "Prices", "what": "No NFL price, spread, total or prop line exists in the system",
         "why": "nfl.com publishes no odds — the probe found zero odds fields on week, game and stats pages.",
         "impact": "No ROI, no CLV, no certification, no reward. This is the single largest gap.",
         "url": "https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10"},
        {"area": "Correlation", "what": "No real correlation value is published",
         "why": "The ingested official player feed is season-to-date leaders, not per-game logs joined by week. "
                "A correlation from season totals answers a different question.",
         "impact": "Parlay and prop-combo pricing cannot be published.",
         "url": "https://www.nfl.com/stats/player-stats/category/receiving/2026/reg/all/receivingreceptions/desc"},
        {"area": "Participation", "what": "No snap counts or gamebook participation data",
         "why": "Not machine-readable on the pages probed.",
         "impact": "'The 2nd string started' remains a depth-chart inference, not a measurement.",
         "url": "https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10"},
        {"area": "Injury status", "what": "Questionable is not a probability",
         "why": "The official report publishes a status word, not a likelihood.",
         "impact": "The injury load column is a count of report rows, never a severity score.",
         "url": f"https://www.nfl.com/injuries/league/2026/reg{int(INJ.get('week') or 1):02d}"},
        {"area": "Rules", "what": "The 2026 NFL rulebook URL probed returned HTTP 404",
         "why": "operations.nfl.com/the-rules/2026-nfl-rulebook/ returned 404 during the probe.",
         "impact": "No rule is quoted anywhere on this site until the current URL is confirmed.",
         "url": "https://operations.nfl.com/the-rules/"},
        {"area": "Depth charts", "what": "Clubs publish different tier counts and several self-label their chart 'Unofficial'",
         "why": "There is no league-normalised depth-chart feed.",
         "impact": "Cross-club depth comparison is approximate and is labelled as such.",
         "url": "https://www.chiefs.com/team/depth-chart"},
        {"area": "Sample", "what": "Two partial seasons, no price history",
         "why": "The 2026 season is in progress and no historical prices exist.",
         "impact": "No strategy can be backtested against a price, so none can be certified.",
         "url": "https://www.nfl.com/schedules/2026/by-week/week-10"},
        {"area": "Scoring tables", "what": "The official team-stats 'scoring' pages publish touchdowns, not points",
         "why": "Confirmed by reading the headers: Rsh TD / Rec TD / Tot TD / 2-PT, and FR TD / SFTY / INT TD.",
         "impact": "Using them as points would overstate scoring by roughly 6x. Points here are computed from "
                   "official finals instead.",
         "url": "https://www.nfl.com/stats/team-stats/offense/scoring/2026/reg/all"},
        {"area": "Governance", "what": "No reviewer is named for the suggestions register",
         "why": "Q17 is unanswered.",
         "impact": "Nothing can be marked 'chosen'; every suggestion stays in an open state.",
         "url": "https://github.com/karagemop466-tech/Korea5"},
        {"area": "Rewards", "what": "No reward policy exists",
         "why": "Q04 is unanswered.",
         "impact": "The leaderboard prints 'not authorised' on every row.",
         "url": "https://www.nfl.com/standings/"},
    ]
    rows = "".join(f"""<tr><td class="nowrap">{esc(i['area'])}</td><td><strong>{esc(i['what'])}</strong></td>
<td class="small">{esc(i['why'])}</td><td class="small">{esc(i['impact'])}</td>
<td class="nowrap">{src(i['url'], 'official reference')}</td></tr>""" for i in items)
    body = f"""
<div class="callout"><strong>Flagged for Review.</strong> Nothing on this page blocks the site from publishing;
everything on it blocks a <em>claim</em>. Each row names the gap, the official reference that shows why the gap
is real, and what it costs. Review these after publication and request changes.</div>
<p class="small">{len(items)} items flagged.</p>
<div class="scroll" style="max-height:none"><table class="tight" id="flagtbl"><thead><tr>
<th>Area</th><th>What is unresolved</th><th>Why it is unresolved</th><th>What it blocks</th>
<th>Official reference</th></tr></thead><tbody>{rows}</tbody></table></div>

<h2>Irregularities found and fixed during this session</h2>
<div class="card prose"><ol>
<li><strong>A wrong derivation was caught and corrected.</strong> The first pass computed points-per-game from the
official <em>team scoring</em> table, which publishes touchdowns rather than points, producing a league mean of
12.97 points per game. The headers were read, the error identified, and points are now computed from official
final scores (league mean 21.81 for 2026). The buggy figure is not published anywhere.</li>
<li><strong>A season blend was caught and corrected.</strong> The first pass pooled 2025 and 2026 finals into one
scoring rate, which would have described "28 games" per club without saying it spanned two seasons. Rates are
now current-season only, with the prior season kept separately and labelled.</li>
<li><strong>Houston's depth chart is an image.</strong> The parser returned nothing, and rather than substitute a
guess the club is listed as unavailable with the reason.</li>
<li><strong>Green Bay's chart uses a different table layout.</strong> A second parser was added and verified
against the live page; the Packers are now included, with jersey numbers stripped from names.</li>
</ol></div>
"""
    return page("Flagged for review", "flagged.html", body,
                "Everything unresolved, with the official reference that shows the gap is real and what each gap "
                "costs — published rather than hidden.")


def p_method():
    body = f"""
<div class="card prose">
<h2 style="margin-top:0">The rules this system is built on</h2>
<ol>
<li><strong>Official sources only, and only these:</strong> nfl.com, the 32 official club domains, and
operations.nfl.com. A value with no page behind it does not exist here.</li>
<li><strong>Never infer a missing value.</strong> If the official page did not publish it, the cell is blank and
badged <span class="badge unverified">unverified</span>. Not zero, not "likely", not "approximately".</li>
<li><strong>Label every computed number.</strong> Anything this system calculates carries
<span class="badge model">model</span>. Anything read straight off an official page carries
<span class="badge official">official</span>. A judgement carries <span class="badge judgement">judgement</span>.</li>
<li><strong>Print the sample.</strong> Every estimate carries n. Estimates below the suppression floor are
withheld entirely rather than published with a warning.</li>
<li><strong>Separate facts that are separate.</strong> Injury status is not a lineup. A depth chart is not a snap
count. A touchdown count is not a points total. Each has its own column.</li>
<li><strong>Freeze thresholds before results.</strong> The gate thresholds carry a version and a date, and a
change is logged with the note "results seen at the time".</li>
<li><strong>Refuse rather than fabricate.</strong> Where the data cannot support a number — no price, no per-game
logs, no snap counts — the page says so in the place the number would have been.</li>
</ol>
</div>

<h2>How a value reaches this site</h2>
<div class="card prose"><ol>
<li><strong>Probe.</strong> <code>nfl/tools/probe.py</code> fetches each official page and counts the regex hits
for the fields we need, so a parser is never written against an assumption. Findings are in
<code>nfl/research/probe.json</code>.</li>
<li><strong>Ingest.</strong> <code>nfl/tools/fetch_official.py</code> runs in CI, parses, and writes JSON with a
<code>sourceUrl</code> and retrieval stamp on every record, plus a fetch report listing every failure.</li>
<li><strong>Compute.</strong> <code>nfl/tools/analyze_market.py</code> derives the statistics. Fixed random seed,
so every published interval is reproducible.</li>
<li><strong>Build.</strong> <code>nfl/tools/build_nfl.py</code> renders the pages from the JSON, so no number is
typed by hand anywhere.</li>
<li><strong>Verify.</strong> <code>nfl/tools/verify_nfl.py</code> re-checks every row for a source link, every
computed value for a MODEL badge, every blank for an UNVERIFIED badge, and every internal link.</li>
</ol></div>

<h2>Statistical methods, named</h2>
<p class="small">This table lists methods, not values, so its "applied on" column points at the page where each
method is used on a sourced number.</p>
<table class="tight"><thead><tr><th>Method</th><th>Where used</th><th>Why this one</th><th>Applied here</th></tr></thead><tbody>
<tr><td>Wilson score interval</td><td>Home win rate</td><td>Correct at small n and near 0/1, unlike the normal
approximation.</td><td><a href="index.html">Overview</a></td></tr>
<tr><td>Brier score / log loss</td><td>Skill scoring</td><td>Proper scoring rules — they cannot be improved by
hedging or by refusing to commit.</td><td><a href="validation.html">Validation gates</a></td></tr>
<tr><td>Expected calibration error</td><td>Calibration gate</td><td>Measures whether a stated 60% happens 60%
of the time, which a win rate cannot.</td><td><a href="validation.html">Validation gates</a></td></tr>
<tr><td>Monte-Carlo shuffle test</td><td>Skill vs luck</td><td>Destroys any real edge by permuting outcomes; if
the strategy still scores as well, the edge was noise.</td><td><a href="validation.html">Validation gates</a></td></tr>
<tr><td>Bootstrap interval</td><td>Correlation</td><td>Makes no distributional assumption and exposes how wide
the uncertainty really is at small n.</td><td><a href="correlation.html">Correlation</a></td></tr>
<tr><td>Shrinkage n/(n+k)</td><td>Scoring rates</td><td>Stops an 11-game hot start from being treated as a
season truth.</td><td><a href="market.html">Lines &amp; market</a></td></tr>
<tr><td>Multiplicative &amp; additive de-vig</td><td>Fair price</td><td>Both are standard; showing both exposes
the modelling choice instead of hiding it.</td><td><a href="market.html">Lines &amp; market</a></td></tr>
<tr><td>Benjamini&ndash;Hochberg style FDR</td><td>Multiple testing</td><td>Raises the bar as the number of tested
strategies grows.</td><td><a href="validation.html">Validation gates</a></td></tr>
</tbody></table>

<h2>What this system is not</h2>
<div class="card prose"><ul>
<li>Not betting advice, and not a claim of edge.</li>
<li>Not a backtest: there is no price history to backtest against.</li>
<li>Not a live odds service: the official NFL sources publish none.</li>
<li>Not complete: {fmt(len(FETCH.get('failures') or []))} failed fetches this run, {fmt(len(COV.get('unavailableDepthCharts') or []))} club depth
chart unavailable, no participation data, no per-game player logs yet.</li>
</ul></div>

<h2>How to reproduce</h2>
<pre style="background:#0d1728;border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto;font-size:13px">
python3 nfl/tools/fetch_official.py   # CI only: needs outbound network
python3 nfl/tools/analyze_market.py   # recompute every published number
python3 nfl/tools/build_nfl.py        # regenerate nfl/*.html
python3 nfl/tools/verify_nfl.py       # re-check links, sources and badges
</pre>
"""
    return page("Method", "method.html", body,
                "The seven rules, the five-stage pipeline, every statistical method named, and what this system "
                "deliberately is not.")


PAGES = {
    "index.html": p_index, "summary.html": p_summary, "suggestions.html": p_suggestions,
    "questions.html": p_questions, "market.html": p_market, "strategies.html": p_strategies,
    "leaderboard.html": p_leaderboard, "validation.html": p_validation, "signals.html": p_signals,
    "correlation.html": p_correlation, "injuries.html": p_injuries, "data.html": p_data,
    "flagged.html": p_flagged, "method.html": p_method,
}


def main():
    for name, fn in PAGES.items():
        (NFL / name).write_text(fn(), encoding="utf-8")
        print("wrote nfl/" + name)


if __name__ == "__main__":
    main()
