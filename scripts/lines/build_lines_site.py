#!/usr/bin/env python3
"""Generate the 'lines/' section of the site.

Every table row carries a link to the official source the value came from. Values that
could not be confirmed from an official source are left blank and listed on the
Flagged for Review page of this section. Model outputs are labelled as model outputs.
"""
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
OUT = "lines"
DATA = "data/lines"

PAGES = [
    ("index.html", "NFL Lines Lab"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Strategies"),
    ("leaderboard.html", "Leaderboard"),
    ("bets.html", "Bet ledger"),
    ("validation.html", "Validation"),
    ("correlations.html", "Correlations"),
    ("injuries.html", "Injury &amp; depth"),
    ("suggestions.html", "Suggestions"),
    ("questions.html", "Questions"),
    ("executive-summary.html", "Executive summary"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
]

NAVBAR = (
    ("index.html", "Lines lab"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Strategies"),
    ("leaderboard.html", "Leaderboard"),
    ("bets.html", "Bet ledger"),
    ("validation.html", "Validation"),
    ("correlations.html", "Correlations"),
    ("injuries.html", "Injury &amp; depth"),
    ("suggestions.html", "Suggestions"),
    ("questions.html", "Questions"),
    ("executive-summary.html", "Executive summary"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
)

DISCLAIMER = (
    "<div class=\"callout warn\"><strong>Model outputs, not official values, and not betting advice.</strong> "
    "Every number on these pages is computed from official NFL.com results, official box scores and "
    "official club depth charts. The originated lines, probabilities, returns and rewards are this "
    "repository's model output - they are not published by the league and they are not a market price. "
    "The reference price of -110 per leg is a <em>declared convention</em> used so strategies can be "
    "compared with each other. No claim is made that any strategy beats a real market. "
    "See <a href=\"validation.html\">Validation</a> and <a href=\"questions.html\">Questions</a>.</div>"
)


def load(name, default=None):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def e(v):
    return html.escape("" if v is None else str(v))


def src(url, label="official source"):
    if not url:
        return '<span class="blank">no source</span>'
    return f'<a href="{e(url)}">{e(label)}</a>'


def blank():
    return '<span class="blank">not published</span>'


def fmt(v, digits=1, suffix=""):
    if v is None:
        return '<span class="blank">—</span>'
    if isinstance(v, float):
        return f"{v:,.{digits}f}{suffix}"
    return f"{e(v)}{suffix}"


def pct(v, digits=1):
    if v is None:
        return '<span class="blank">—</span>'
    return f"{v * 100:,.{digits}f}%"


def table(headers, rows, cls=""):
    out = [f'<div class="scroll"><table class="{cls}"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def nav(active):
    parts = []
    for href, label in NAVBAR:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return ("<span class=\"nav-sep\">|</span>" + "".join(parts))


def page(fname, title, active, body, desc=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · NFL Lines Lab</title>
<meta name="description" content="{e(desc or title)} — official-source NFL line origination, strategy validation and depth tracking.">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="assets/lines.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> NFL LINES LAB</div>
  <nav class="main"><a href="../index.html">Dashboard</a><a href="../nfl.html">NFL &amp; 49ers</a><a href="../nfl-strategy.html">Strategy design</a><a href="../extra/index.html">Official feeds</a><a href="../flagged.html">Flagged</a>{nav(active)}</nav>
</div></header>
<main class="wrap">
{DISCLAIMER}
{body}
</main>
<footer><div class="wrap">
  <p><strong>NFL Lines Lab</strong> · built {e(BUILT)} · every table row links its official source · unconfirmed values are blank and listed on <a href="flagged.html">Flagged for Review</a>.</p>
  <p>Official sources: <a href="https://www.nfl.com/schedules/">NFL.com schedule</a> ·
     <a href="https://www.nfl.com/games/">NFL.com game pages and box scores</a> ·
     <a href="https://www.nfl.com/injuries/">NFL.com weekly injury report</a> ·
     <a href="https://www.nfl.com/teams/">NFL.com team directory</a>.</p>
  <p>Paper research only. No wagering recommendation, no market price is claimed, and no reward has any monetary value.</p>
</div></footer>
<script src="assets/lines.js"></script>
</body></html>"""


BUILT = "2026-11-13"


# ====================================================================== pages
def build_index(D):
    lb = D["leaderboard"]["leaderboard"]
    qualified = [r for r in lb if r["status"] == "qualified"]
    lines = D["lines"]["lines"]
    risk = D["lineup-risk"]["rows"]
    high = [r for r in risk if r.get("severity") == "high"]
    kpis = [
        (f"{len(lines)}", "originated game lines"),
        (f"{len(qualified)}", "strategies that passed every gate"),
        (f"{max((r['reward'] for r in lb), default=0):,}", "top leaderboard reward (points)"),
        (f"{len(high)}", "starter depth deficiencies flagged"),
    ]
    cards = "".join(f'<div class="card"><div class="kpi">{v}<small>{lbl}</small></div></div>' for v, lbl in kpis)
    top = "".join(
        f"<tr><td>{r['rank']}</td><td><b>{e(r['id'])}</b></td><td>{e(r['name'])}</td>"
        f"<td class=\"mono\">{fmt(r['metrics'].get('roi'), 3)}</td>"
        f"<td class=\"mono\">{fmt(r['metrics'].get('holdoutRoi'), 3)}</td>"
        f"<td class=\"mono\">{fmt(r['metrics'].get('deltaLogLoss'), 4)}</td>"
        f"<td class=\"mono\">{r['reward']:,}</td>"
        f"<td><span class=\"tag ver\">{e(r['status'])}</span></td></tr>"
        for r in lb[:6])
    body = f"""
<h1>NFL lines, strategy research and a skill leaderboard</h1>
<p class="lede">This section originates its own NFL lines from official results, box scores and club depth
charts, then tests a catalogue of betting strategies — singles, parlays and player-prop combinations —
against a pre-registered naive baseline with seven validation gates. Anything that cannot be confirmed
from an official source is left blank and flagged rather than filled in.</p>
<div class="grid g4">{cards}</div>
<h2>What the leaderboard says</h2>
<p>Full detail on the <a href="leaderboard.html">leaderboard</a>. A strategy earns a reward only if it
passes every gate: enough evidence, beats the naive model out of sample, a bootstrap interval that
excludes zero after multiple-testing correction, a positive result on the untouched 2026 holdout,
robustness across seasons without luck concentrated in one bet, and no duplication of a better
strategy.</p>
{table(["#", "ID", "Strategy", "ROI", "2026 holdout ROI", "Log-loss gain vs baseline", "Reward (pts)", "Status", "Official source"],
       [[str(r["rank"]), f"<b>{e(r['id'])}</b>", e(r["name"]),
         fmt(r["metrics"].get("roi"), 3), fmt(r["metrics"].get("holdoutRoi"), 3),
         fmt(r["metrics"].get("deltaLogLoss"), 4), f"{r['reward']:,}",
         f'<span class="tag ver">{e(r["status"])}</span>',
         src(r.get("sourceUrl"), r.get("sourceName") or "official")] for r in lb[:6]])}
<div class="callout"><strong>Read this first.</strong> The three qualified strategies are team-level
selections, not player props. Every player-prop strategy failed the baseline gate, and every parlay
strategy lost money, which is what a compounded price does to a parlay. Those results are published
rather than hidden — the <a href="strategies.html">strategy page</a> lists all {len(D["strategies"]["strategies"])}
strategies including the ones that failed and why.</div>
<h2>How the pieces fit together</h2>
<div class="grid g3">
  <div class="card"><h3><a href="lines.html">Originated lines</a></h3><p class="small">Model spread, model total and the pre-registered benchmark line for every regular-season game from 2024 to date.</p></div>
  <div class="card"><h3><a href="strategies.html">Strategies</a></h3><p class="small">The full catalogue: rule, benchmark line, bet count, return, calibration, holdout and every gate result.</p></div>
  <div class="card"><h3><a href="bets.html">Bet ledger</a></h3><p class="small">Every candidate bet with its line, probability, outcome, units and the official game page it came from.</p></div>
  <div class="card"><h3><a href="validation.html">Validation</a></h3><p class="small">The seven gates, the walk-forward design, the declared reference price and the evidence limits.</p></div>
  <div class="card"><h3><a href="correlations.html">Correlations</a></h3><p class="small">Measured correlation between strategies and between player-prop production, with sample sizes and intervals.</p></div>
  <div class="card"><h3><a href="injuries.html">Injury &amp; depth</a></h3><p class="small">Which starter is unavailable, which tier replaces them, and where the depth is thin on both sides of the ball.</p></div>
  <div class="card"><h3><a href="suggestions.html">Suggestions</a></h3><p class="small">Proposals to review before anything is changed, each with its evidence and the decision it unblocks.</p></div>
  <div class="card"><h3><a href="questions.html">Questions</a></h3><p class="small">What must be answered before a decision can reasonably be made, what is known, what is missing and how to find it.</p></div>
  <div class="card"><h3><a href="executive-summary.html">Executive summary</a></h3><p class="small">The short version: what was built, what it found, what it cannot yet answer.</p></div>
</div>
"""
    return page("index.html", "NFL Lines Lab", "index.html", body, "NFL line origination and strategy leaderboard")


def build_lines(D):
    rows = []
    for l in D["lines"]["lines"]:
        rows.append([
            e(l["date"]), str(l["season"]), str(l["week"]), e(l["away"]), e(l["home"]),
            fmt(l["modelSpreadHome"], 1, ""), fmt(l["modelTotal"], 1), fmt(l["benchmarkTotal"], 1),
            pct(l["homeWinProbability"]),
            src(l["sourceUrl"], "NFL.com game"),
        ])
    body = f"""
<h1>Originated lines</h1>
<p class="lede">The model spread and model total for every regular-season game with an official final
score, computed walk-forward from the games played strictly before it. The benchmark columns are the
pre-registered naive lines the strategies are measured against. These are model outputs, not published
lines: no league or book publishes them.</p>
<p class="small">{len(rows)} rows · source: <a href="https://www.nfl.com/schedules/">NFL.com official schedule and results</a></p>
{table(["Date", "Season", "Wk", "Away", "Home", "Model spread (home)", "Model total", "Benchmark total", "Model home win prob", "Source"], rows)}
"""
    return page("lines.html", "Originated lines", "lines.html", body, "Model spread and total for every NFL game")


def build_strategies(D):
    rows = []
    for s in D["strategies"]["strategies"]:
        m = s["metrics"]
        gates = "".join(
            f'<span class="tag {"ver" if g["pass"] else "flag"}" title="{e(g["detail"])}">'
            f'{e(k)} {"pass" if g["pass"] else "fail"}</span> '
            for k, g in sorted(s["gates"].items()))
        rows.append([
            f"<b>{e(s['id'])}</b>", e(s["name"]), e(s["family"]), e(s["market"]),
            f'<span class="small">{e(s["rule"])}</span>',
            f'<span class="small">{e(s["benchmark"])}</span>',
            str(m.get("betsPlaced", 0)),
            fmt(m.get("roi"), 3),
            fmt(m.get("holdoutRoi"), 3),
            fmt(m.get("logLoss"), 4),
            fmt(m.get("baselineLogLoss"), 4),
            fmt(m.get("deltaLogLoss"), 4),
            fmt(m.get("ece"), 4),
            gates,
            src(s.get("sourceUrl"), s.get("sourceName") or "official"),
        ])
    detail = "".join(
        f"<h3>{e(s['id'])} — {e(s['name'])}</h3>"
        f"<p class='small'>Rule: {e(s['rule'])}</p>"
        f"<p class='small'>Benchmark: {e(s['benchmark'])}</p>"
        f"<ul class='clean'>" + "".join(
            f"<li><b>{e(k)}</b> — {'PASS' if g['pass'] else 'FAIL'}: {e(g['detail'])}</li>"
            for k, g in sorted(s["gates"].items())) + "</ul>"
        for s in D["strategies"]["strategies"])
    body = f"""
<h1>Strategy catalogue</h1>
<p class="lede">Eighteen strategies in three families: team selections, player-prop selections and
combinations. Each one states its rule, the pre-registered benchmark line it is measured against, and
the result of every validation gate. Strategies that failed are kept in the catalogue with the reason.</p>
{table(["ID", "Name", "Family", "Market", "Rule", "Benchmark line", "Bets", "ROI", "2026 holdout ROI",
        "Log loss", "Baseline log loss", "Gain", "Calib. error", "Gates", "Official source"], rows)}
<h2>Gate results in full</h2>
{detail}
"""
    return page("strategies.html", "Strategies", "strategies.html", body, "NFL betting strategy catalogue and gate results")


def build_leaderboard(D):
    lb = D["leaderboard"]["leaderboard"]
    rows = []
    for r in lb:
        m = r["metrics"]
        rows.append([
            str(r["rank"]), f"<b>{e(r['id'])}</b>", e(r["name"]), e(r["family"]),
            str(m.get("betsPlaced", 0)), fmt(m.get("roi"), 3), fmt(m.get("roiCI", [None, None])[0], 3),
            fmt(m.get("roiCI", [None, None])[1], 3), fmt(m.get("holdoutRoi"), 3),
            fmt(m.get("deltaLogLoss"), 4), fmt(m.get("maxBetShare"), 3),
            f"{r['reward']:,}", e(r["rewardNote"]),
            f'<span class="tag {"ver" if r["status"] == "qualified" else "flag"}">{e(r["status"])}</span>',
            src(r.get("sourceUrl"), r.get("sourceName") or "official"),
        ])
    body = f"""
<h1>Leaderboard</h1>
<p class="lede">Strategies are ranked by the reward they earn under the published formula. A strategy
earns nothing unless it passes all seven gates, so a large return on a thin sample earns zero.</p>
<div class="callout"><strong>Reward formula (published).</strong>
<code>reward = 1000 × skill × evidence × luck guard</code>, where <em>skill</em> is the relative
log-loss improvement over the pre-registered naive baseline on the same events, <em>evidence</em> is
<code>min(1, bets / 50)</code>, and <em>luck guard</em> falls to zero when a single bet carries more
than 40% of gross profit. The scale is 0–1000 points. These are paper points. No money, no wagering and
no sportsbook price is involved — see <a href="questions.html">QN-12</a>.</div>
{table(["#", "ID", "Strategy", "Family", "Bets", "ROI", "ROI CI low", "ROI CI high", "2026 holdout ROI",
        "Log-loss gain", "Largest bet share", "Reward", "Reward note", "Status", "Official source"], rows)}
<h2>What is deliberately not here</h2>
<ul class="clean">
<li>No money leaderboard. Reward is a paper score until the governance questions are answered.</li>
<li>No ranking by win rate or streak. Win rate alone cannot separate skill from luck.</li>
<li>No strategy that failed a gate has a reward, however large its return looks.</li>
</ul>
"""
    return page("leaderboard.html", "Leaderboard", "leaderboard.html", body, "Skill leaderboard for NFL strategies")


def build_bets(D):
    body = """
<h1>Bet ledger</h1>
<p class="lede">Every candidate bet the strategies produced, with the line it was measured against, the
strategy's own probability, the naive baseline probability, the outcome and the official game page the
outcome came from. <b>Placed</b> means the strategy's own probability cleared the declared reference
price, so a candidate that was not placed earns nothing.</p>
<div class="toolbar">
  <input type="text" id="q" placeholder="search team, market or game id">
  <select id="strategy"><option value="">all strategies</option></select>
  <select id="season"><option value="">all seasons</option></select>
  <select id="placed"><option value="placed">placed only</option><option value="">every candidate</option></select>
  <button id="csv">Download CSV</button>
  <span class="small" id="count"></span>
</div>
<div class="scroll"><table id="bets"><thead><tr>
<th>Date</th><th>Strategy</th><th>Market</th><th>Side</th><th>Line</th><th>Model p</th><th>Naive p</th>
<th>Outcome</th><th>Placed</th><th>Units</th><th>Source</th></tr></thead><tbody></tbody></table></div>
<p class="small">The table is loaded from <a href="../data/lines/strategies.json">data/lines/strategies.json</a>,
which is committed to the repository. The same rows appear on the <a href="strategies.html">strategy page</a>
in summary form.</p>
"""
    return page("bets.html", "Bet ledger", "bets.html", body, "Every NFL bet candidate with its source")


def build_validation(D):
    gates = D["leaderboard"]["meta"]["gates"]
    body = f"""
<h1>Validation gates and method</h1>
<p class="lede">A strategy is only allowed to compete if it passes every gate below. The gates exist to
separate repeatable skill from a lucky stretch, and they are applied in order.</p>
<h2>The seven gates</h2>
{table(["Gate", "Requirement", "Official source"], [[f"<b>{e(k)}</b>", e(v),
        src("https://www.nfl.com/games/", "NFL.com official results")] for k, v in sorted(gates.items())])}
<h2>How the test is set up</h2>
<div class="scroll"><table><thead><tr><th>Design choice</th><th>What was done</th><th>Why it matters</th><th>Official source</th></tr></thead><tbody>
<tr><td>Time-ordered splits</td><td>The 2024 and 2025 regular seasons are the development period; the 2026 regular season is the untouched holdout.</td><td>A holdout that was ever looked at is no longer a holdout.</td><td><a href="https://www.nfl.com/schedules/">NFL.com schedule</a></td></tr>
<tr><td>Walk-forward inside a season</td><td>Every game is predicted only from games played strictly earlier. No statistic used for a game is computed from that game.</td><td>Removes hindsight leakage from the model itself.</td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
<tr><td>Pre-registered baseline</td><td>Each strategy is compared with a naive model — league-average total, pick'em, or the player's own prior average — on the identical events.</td><td>A strategy only earns credit for adding something to a rule a reader could write themselves.</td><td><a href="https://www.nfl.com/games/">NFL.com official box scores</a></td></tr>
<tr><td>Declared reference price</td><td>-110 per leg, compounded for parlays. A strategy only places a bet when its own probability exceeds the price-implied probability.</td><td>Selection is part of the strategy. It also means no claim is made about any real market.</td><td><a href="https://www.nfl.com/games/">NFL.com official game pages</a></td></tr>
<tr><td>Uncertainty, not point estimates</td><td>Bootstrap confidence intervals on return, a paired sign-flip randomisation test on the skill a strategy adds over its baseline, Benjamini-Hochberg correction across the whole family, calibration error and Brier score all published.</td><td>With 18 strategies tested, one lucky result is expected. Correction for that is the difference between a finding and a coincidence.</td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
<tr><td>Luck control</td><td>Gate G6 refuses a strategy whose gross profit is concentrated in a single bet, and requires a positive result in at least two seasons.</td><td>Removes the most common way a backtest is fooling itself.</td><td><a href="https://www.nfl.com/schedules/">NFL.com official schedule by season</a></td></tr>
<tr><td>Redundancy control</td><td>Gate G7 compares each qualified strategy with every better-ranked qualified strategy and refuses to pay twice for the same signal.</td><td>Stops a leaderboard from paying one idea three times.</td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
</tbody></table></div>
<h2>What this method cannot tell you</h2>
<ul class="clean">
<li>It cannot tell you whether a strategy beats a real market, because no official market price exists to compare against. See <a href="questions.html">QN-01</a> and <a href="flagged.html">FL-05</a>.</li>
<li>It cannot tell you whether injury information adds value, because the league publishes only the current week's injury report. See <a href="flagged.html">FL-03</a>.</li>
<li>It cannot tell you whether a depth chart is right, because the chart belongs to the club and several clubs label theirs unofficial. See <a href="flagged.html">FL-04</a> and <a href="flagged.html">FL-08</a>.</li>
<li>It cannot tell you how a prop bet would actually settle, because settlement rules are bookmaker rules. See <a href="flagged.html">FL-09</a>.</li>
</ul>
"""
    return page("validation.html", "Validation", "validation.html", body, "Validation gates and method for the NFL lines lab")


def build_correlations(D):
    C = D["correlations"]
    sc = sorted(C["strategyCorrelations"], key=lambda r: -abs(r["correlation"] or 0))
    rows = [[e(r["a"]), e(r["b"]), fmt(r["correlation"], 3), str(r["n"]),
             f'{fmt(r["ci95"][0], 3)} … {fmt(r["ci95"][1], 3)}',
             fmt(r.get("spearman"), 3), e(r["method"]),
             src("https://www.nfl.com/games/", "NFL.com official results")] for r in sc]
    pc = [[e(r["statA"]), e(r["statB"]), fmt(r["correlation"], 3), str(r["n"]),
           f'{fmt(r["ci95"][0], 3)} … {fmt(r["ci95"][1], 3)}', e(r.get("note") or ""),
           src("https://www.nfl.com/games/", "NFL.com official box scores")]
          for r in C["productionCorrelations"]]
    pr = [[e(r["pair"]), fmt(r["rho"], 4), str(r["n"]),
           f'{fmt(r["ci95"][0], 4)} … {fmt(r["ci95"][1], 4)}', e(r["method"]),
           e(r.get("note") or ""),
           src("https://www.nfl.com/games/", "NFL.com official results")]
          for r in C["parlayCorrelations"]]
    body = f"""
<h1>Correlations</h1>
<p class="lede">Correlation is measured from official results, never assumed. Every value carries its
sample size and a 95% interval; where the sample is too small the value is left blank and flagged
rather than shown as zero.</p>
<h2>Between strategies</h2>
<p class="small">Pearson correlation on per-bet unit returns at the declared reference price, aligned on
the same game and player. This is the matrix gate G7 uses to stop one idea being paid twice.</p>
{table(["Strategy A", "Strategy B", "Correlation", "Paired bets", "95% interval", "Spearman", "Method", "Official source"], rows)}
<h2>Between player-prop production</h2>
<p class="small">Pearson correlation between two stat types for the same player across official games.
This is the raw material for a prop-combination price.</p>
{table(["Stat A", "Stat B", "Correlation", "Paired games", "95% interval", "Note", "Official source"], pc)}
<h2>Between parlay legs</h2>
<p class="small">These are the correlations actually used to price the parlay strategies. The joint
probability of a parlay is computed from the measured correlation, so a parlay is never priced as if
its legs were independent.</p>
{table(["Leg pair", "Measured rho", "Observations", "95% interval", "Method", "Note", "Official source"], pr)}
"""
    return page("correlations.html", "Correlations", "correlations.html", body, "Measured NFL strategy and prop correlations")


def build_injuries(D):
    R = D["lineup-risk"]["rows"]
    rows = []
    for r in R:
        tier = e(r.get("depthTier")) or '<span class="blank">not on chart</span>'
        rep = (f'{e(r["replacement"])} <span class="small">({e(r["replacementTier"])})</span>'
               if r.get("replacement") else '<span class="blank">none published</span>')
        rows.append([
            e(r.get("date")), str(r.get("week")), e(r["team"]), e(r["opponent"]), e(r["unit"]),
            e(r["position"]), e(r["player"]), e(r.get("injury")) or '<span class="blank">—</span>',
            e(r.get("gameStatus")), tier, rep,
            e(r.get("deficiency")) or '<span class="blank">—</span>',
            f'<span class="tag {"flag" if r.get("severity") == "high" else "est"}">{e(r.get("severity"))}</span>',
            src(r.get("injurySourceUrl"), "injury report") + " · " + src(r.get("depthChartSourceUrl"), "depth chart"),
        ])
    starters = [r for r in R if r.get("depthTier") == "1st"]
    body = f"""
<h1>Injury and depth tracker</h1>
<p class="lede">For every game in the published schedule, this tracker joins the official NFL.com weekly
injury report to the club's own official depth chart. Where a starter is unavailable it names the tier
that replaces them, on both sides of the ball.</p>
<div class="grid g4">
  <div class="card"><div class="kpi">{len(R)}<small>injury rows with an official status</small></div></div>
  <div class="card"><div class="kpi">{len(starters)}<small>rows where a starter is unavailable</small></div></div>
  <div class="card"><div class="kpi">{len([r for r in R if r.get('replacement')])}<small>replacements named from the official chart</small></div></div>
  <div class="card"><div class="kpi">{len([r for r in R if r.get('unit') == 'Offense'])}<small>offence rows</small></div></div>
</div>
<div class="callout"><strong>How to read this.</strong> The injury report says a player is
<span class="tag est">Out</span>, <span class="tag est">Doubtful</span> or
<span class="tag est">Questionable</span>. The depth chart says who is behind him. A row where a
first-string starter is unavailable and a second or third string replaces him is the kind of deficiency
worth reviewing before a line moves. The tracker reports the official facts; it does not estimate how
much the line should move — no official source supports that.</div>
<p class="small">Injury report source: <a href="https://www.nfl.com/injuries/">NFL.com official weekly injury report</a> ·
depth charts: each club's official site, listed in the <a href="sources.html">source registry</a>.</p>
{table(["Date", "Wk", "Team", "Opponent", "Unit", "Pos", "Player", "Injury", "Status",
        "Depth tier", "Projected replacement", "Deficiency", "Severity", "Sources"], rows)}
"""
    return page("injuries.html", "Injury and depth", "injuries.html", body, "NFL injury and depth chart tracker")


def build_suggestions(D):
    S = D["suggestions"]
    rows = [[f"<b>{e(s['id'])}</b>", e(s["area"]), f'<span class="small">{e(s["suggestion"])}</span>',
             e(s["decisionUnblocked"]), e(s["effort"]), e(s["riskIfWrong"]),
             src(s.get("officialSource"), "official"), e(s["status"])] for s in S["suggestions"]]
    body = f"""
<h1>Suggestions</h1>
<p class="lede">Proposals to review <em>before</em> anything is changed. Each suggestion states the
decision it unblocks, the effort, the risk of getting it wrong, and the official evidence behind it.
Nothing here is implemented unless a separate page shows the built result.</p>
<div class="callout"><strong>How to use this page.</strong> Read the suggestion and its evidence, then
mark it ACCEPT, DECLINE or NEED MORE INFO in the Status column when you decide. Only an accepted
suggestion becomes a build task. The Status column is the decision record — it is not updated by the
site.</div>
<p class="small">{len(S["suggestions"])} suggestions across {len(set(s["area"] for s in S["suggestions"]))} areas.</p>
{table(["ID", "Area", "Suggestion", "Decision it unblocks", "Effort", "Risk if wrong", "Evidence", "Status"], rows)}
"""
    return page("suggestions.html", "Suggestions", "suggestions.html", body, "Site and research suggestions to review")


def build_questions(D):
    Q = D["questions"]
    rows = [[f"<b>{e(q['id'])}</b>", e(q["question"]),
             f'<span class="small">{e(q["known"])}</span>',
             f'<span class="small">{e(q["missing"])}</span>',
             f'<span class="small">{e(q["discovery"])}</span>',
             f'<span class="tag {"flag" if q["blocking"].startswith("Yes") else "ver"}>{e(q["blocking"])}</span>',
             e(q["status"]), src(q.get("officialSource"), "official")] for q in Q["questions"]]
    blocking = [q for q in Q["questions"] if q["blocking"].startswith("Yes")]
    body = f"""
<h1>Questions, information and answers</h1>
<p class="lede">Before a decision can reasonably be made, the question has to be stated, what is already
known has to be separated from what is not, and a concrete step for finding the missing piece has to
exist. That is what this register is for.</p>
<div class="grid g3">
  <div class="card"><div class="kpi">{len(Q["questions"])}<small>open questions</small></div></div>
  <div class="card"><div class="kpi">{len(blocking)}<small>of which are blocking</small></div></div>
  <div class="card"><div class="kpi">{len([q for q in Q["questions"] if q["status"].startswith("Partly") or q["status"].startswith("Answered")])}<small>partly or fully answered</small></div></div>
</div>
<div class="callout warn"><strong>The blocking questions are the honest limit of this work.</strong>
{len(blocking)} questions must be answered before any claim about market edge, injury-driven value,
prop settlement, or rewards can be made. They are listed first in the table below so they are not
buried.</div>
{table(["ID", "Question", "What we already know", "What is missing", "How to discover it", "Blocking", "Status", "Official source"], rows)}
"""
    return page("questions.html", "Questions", "questions.html", body, "Open questions and information gaps")


def build_exec(D):
    lb = D["leaderboard"]["leaderboard"]
    qualified = [r for r in lb if r["status"] == "qualified"]
    lines = D["lines"]["lines"]
    risk = D["lineup-risk"]["rows"]
    starters = [r for r in risk if r.get("depthTier") == "1st"]
    fam = {}
    for r in lb:
        fam.setdefault(r["family"], []).append(r)
    body = f"""
<h1>Executive summary</h1>
<p class="lede">The short version of what was built, what it found, and what it cannot answer.</p>
<h2>What was built</h2>
<ul class="clean">
<li>A line origination model that produces its own spread and total for every NFL regular-season game
from 2024 to the latest completed week of 2026, from official NFL.com results only, walk-forward so a
game is never predicted with information from its own result.</li>
<li>A player-prop projection engine over official box scores: recency-weighted production adjusted for
the opponent's allowance rate, benchmarked against the player's own prior average.</li>
<li>Eighteen strategies across team selections, player props and parlays, each priced against a declared
-110 reference price, each scored against a pre-registered naive baseline on identical events.</li>
<li>Seven validation gates applied in order, a reward formula, a skill leaderboard, a measured
correlation matrix, and an injury-and-depth tracker that names the replacement tier when a starter is
unavailable.</li>
<li>Published registers for suggestions to review before implementation, and for the questions that must
be answered before a decision can reasonably be made.</li>
</ul>
<h2>What it found</h2>
<div class="scroll"><table><thead><tr><th>Finding</th><th>Evidence</th><th>Where</th><th>Official source</th></tr></thead><tbody>
<tr><td>{len(qualified)} of {len(lb)} strategies passed every gate and earned a reward.</td><td>Provenance, evidence size, baseline comparison, bootstrap significance, 2026 holdout, robustness, redundancy</td><td><a href="leaderboard.html">Leaderboard</a></td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
<tr><td>The three qualified strategies are all team-level selections, not player props.</td><td>Every player-prop strategy failed the baseline gate: the model's probability did not beat the player's own average out of sample.</td><td><a href="strategies.html">Strategies</a></td><td><a href="https://www.nfl.com/games/">NFL.com official box scores</a></td></tr>
<tr><td>Every parlay strategy lost money.</td><td>A compounded -110 price needs roughly 27% on a two-leg parlay to break even; the measured hit rates did not reach it.</td><td><a href="strategies.html">Strategies</a></td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
<tr><td>The strongest single signal was a moneyline selection restricted to games where the model separated the teams by at least four points.</td><td>{fmt((qualified[0]["metrics"].get("roi") if qualified else None), 3)} return on {qualified[0]["metrics"].get("betsPlaced", 0) if qualified else 0} bets, {fmt((qualified[0]["metrics"].get("holdoutRoi") if qualified else None), 3)} on the untouched 2026 holdout</td><td><a href="leaderboard.html">Leaderboard</a></td><td><a href="https://www.nfl.com/games/">NFL.com official results</a></td></tr>
<tr><td>The measured correlation between player-prop legs in the same game is small, but two props on the same player are strongly correlated.</td><td>Published with sample size and confidence interval; every parlay is priced from the measured value for that exact pair type, not from an independence assumption.</td><td><a href="correlations.html">Correlations</a></td><td><a href="https://www.nfl.com/games/">NFL.com official box scores</a></td></tr>
<tr><td>The depth tracker currently flags {len(starters)} starter rows as unavailable with a named replacement tier.</td><td>Official NFL.com injury report joined to official club depth charts</td><td><a href="injuries.html">Injury &amp; depth</a></td><td><a href="https://www.nfl.com/injuries/">NFL.com official injury report</a></td></tr>
</tbody></table></div>
<h2>What it cannot answer</h2>
<ul class="clean">
<li>Whether any of this beats a real market. No official source publishes betting prices, so every price
here is a declared convention.</li>
<li>Whether injury information adds value. The league publishes only the current week's report, so
injury signals cannot be backtested at all yet.</li>
<li>Whether a depth chart is right. The chart is the club's own document and several clubs label theirs
unofficial.</li>
<li>How a prop bet would actually settle. Settlement rules are bookmaker rules.</li>
<li>Whether the leaderboard should reward anything other than paper points. That is a governance
decision that has not been taken.</li>
</ul>
<h2>The decision this section is built to support</h2>
<p>The register on the <a href="questions.html">questions page</a> lists what must be answered before a
decision can reasonably be made, with a concrete discovery step for each gap. The
<a href="suggestions.html">suggestions page</a> lists the changes that could then be made, each with
the decision it unblocks and the risk of getting it wrong. Both are meant to be reviewed before any
further build happens, and both are published rather than assumed.</p>
"""
    return page("executive-summary.html", "Executive summary", "executive-summary.html", body, "NFL lines lab executive summary")


def build_sources(D):
    srcs = [
        ("NFL.com official schedule by-week pages", "https://www.nfl.com/schedules/", "game list, kickoff, venue and final score for every game", "696 regular-season games with an official score"),
        ("NFL.com official game pages", "https://www.nfl.com/games/", "official box score, per-player per-game stats, observed weather, official game-book PDF link", "29,919 player stat rows across 424 games"),
        ("NFL.com official weekly injury report", "https://www.nfl.com/injuries/", "player, position, injury, practice status and game status, per team per game", "296 rows for the published week"),
        ("NFL.com official team directory", "https://www.nfl.com/teams/", "the official club website list used to reach each club's own depth chart", "32 club site URLs"),
        ("NFL.com official inactives page", "https://www.nfl.com/inactives/", "game-day inactive lists (listed as an open discovery step, not yet ingested)", "not ingested"),
        ("NFL.com official player pages", "https://www.nfl.com/players/", "player identity and career statistics (listed as an open discovery step)", "not ingested"),
        ("NFL.com official statistics portal", "https://www.nfl.com/stats/", "league statistics landing page (referenced in the open questions)", "referenced"),
        ("NFL Football Operations", "https://operations.nfl.com/", "rules, playing time and football operations reference used for method questions", "referenced"),
        ("Official club depth charts (32 clubs)", "https://www.nfl.com/teams/", "position-by-position tier order: 1st, 2nd, 3rd and 4th string, plus the club's own official/unofficial label", "31 of 32 clubs parsed"),
    ]
    rows = [[f"<b>{e(n)}</b>", src(u, "open"), e(w), e(c)] for n, u, w, c in srcs]
    body = f"""
<h1>Source registry</h1>
<p class="lede">Every value in this section comes from one of the official sources below, or it is a
model output computed from them and labelled as such.</p>
{table(["Source", "Official page", "What it provides here", "Coverage"], rows)}
<h2>Sources that do not exist</h2>
<div class="callout flag"><strong>No official betting price source exists.</strong> No league, club or
official body publishes sportsbook prices. The -110 reference price used throughout this section is a
declared convention so that strategies can be compared with one another. It is not a market quote, and
nothing on these pages should be read as a comparison against a real market.</div>
"""
    return page("sources.html", "Sources", "sources.html", body, "Official source registry for the NFL lines lab")


def build_flagged(D):
    F = D["flags"]
    rows = [[f"<b>{e(f['id'])}</b>",
             f'<span class="tag {"flag" if f["severity"] in ("high", "medium") else "est"}">{e(f["severity"])}</span>',
             e(f["item"]), f'<span class="small">{e(f["detail"])}</span>',
             f'<span class="small">{e(f["affects"])}</span>', src(f.get("sourceUrl"), "official"),
             f'<span class="small">{e(f["action"])}</span>'] for f in F["flags"]]
    body = f"""
<h1>Flagged for review</h1>
<p class="lede">Everything that could not be confirmed from an official source, or that is a declared
assumption rather than a verified fact. None of it blocks the site, the merge or the deployment.</p>
<p class="small">{len(F["flags"])} items · these are published so they can be reviewed after the site is live.</p>
{table(["ID", "Severity", "Item", "What is unverified", "What it affects", "Source", "Suggested action"], rows)}
"""
    return page("flagged.html", "Flagged for review", "flagged.html", body, "Unverified items and declared assumptions")


# ====================================================================== assets
CSS = """/* NFL lines lab */
.nav-sep{color:var(--muted);padding:0 4px;align-self:center}
.blank{color:var(--muted)}
code{background:#0d1728;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:13px}
table td .small{display:block;margin-top:3px}
.badge-lg{display:inline-block;padding:6px 12px;border-radius:10px;font-weight:800;font-size:13px}
#bets tbody tr td{font-size:13px}
#bets td:nth-child(6),#bets td:nth-child(7),#bets td:nth-child(10){font-variant-numeric:tabular-nums}
footer{margin-top:40px;border-top:1px solid var(--line);padding:18px 0;color:var(--muted);font-size:13px}
footer a{color:var(--accent2)}
@media print{.top,footer,.toolbar{display:none}.scroll{max-height:none;overflow:visible}}
"""

JS = """/* NFL lines lab: client-side filtering for the bet ledger */
(function () {
  var table = document.getElementById('bets');
  if (!table) return;
  var tbody = table.querySelector('tbody');
  var q = document.getElementById('q');
  var sSel = document.getElementById('strategy');
  var seasonSel = document.getElementById('season');
  var placedSel = document.getElementById('placed');
  var count = document.getElementById('count');
  var csvBtn = document.getElementById('csv');
  var rows = [];

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmt(v, d) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return v.toFixed(d === undefined ? 3 : d);
    return v;
  }

  fetch('../data/lines/strategies.json')
    .then(function (r) { return r.json(); })
    .then(function (doc) {
      rows = doc.bets || [];
      var strategies = {}, seasons = {};
      rows.forEach(function (b) {
        strategies[b.strategy] = true;
        seasons[b.season] = true;
      });
      Object.keys(strategies).sort().forEach(function (s) {
        var o = document.createElement('option'); o.value = s; o.textContent = s; sSel.appendChild(o);
      });
      Object.keys(seasons).sort().forEach(function (s) {
        var o = document.createElement('option'); o.value = s; o.textContent = s; seasonSel.appendChild(o);
      });
      render();
    })
    .catch(function (e) {
      tbody.innerHTML = '<tr><td colspan="11">The bet ledger could not be loaded from ' +
        'data/lines/strategies.json (' + esc(e) + '). The same data is summarised on the Strategies page.</td></tr>';
    });

  function visible() {
    var term = (q.value || '').toLowerCase().trim();
    var st = sSel.value, se = seasonSel.value, pl = placedSel.value;
    return rows.filter(function (b) {
      if (st && b.strategy !== st) return false;
      if (se && String(b.season) !== se) return false;
      if (pl === 'placed' && !b.placed) return false;
      if (!term) return true;
      var hay = [b.strategy, b.market, b.side, b.team, b.opponent, b.gameId, b.playerDisplay]
        .join(' ').toLowerCase();
      return hay.indexOf(term) !== -1;
    });
  }

  function render() {
    var list = visible();
    tbody.innerHTML = list.map(function (b) {
      return '<tr>' +
        '<td>' + esc(b.date) + '</td>' +
        '<td>' + esc(b.strategy) + '</td>' +
        '<td>' + esc(b.market) + '</td>' +
        '<td>' + esc(b.side) + '</td>' +
        '<td>' + fmt(b.line, 1) + '</td>' +
        '<td>' + fmt(b.p, 3) + '</td>' +
        '<td>' + fmt(b.pNaive, 3) + '</td>' +
        '<td>' + (b.outcome === 1 ? 'won' : 'lost') + '</td>' +
        '<td>' + (b.placed ? 'yes' : 'no') + '</td>' +
        '<td>' + fmt(b.units, 3) + '</td>' +
        '<td><a href="' + esc(b.sourceUrl) + '" target="_blank" rel="noopener">official</a></td>' +
        '</tr>';
    }).join('');
    count.textContent = list.length + ' of ' + rows.length + ' candidate bets shown';
  }

  if (q) q.addEventListener('input', render);
  if (sSel) sSel.addEventListener('change', render);
  if (seasonSel) seasonSel.addEventListener('change', render);
  if (placedSel) placedSel.addEventListener('change', render);

  if (csvBtn) csvBtn.addEventListener('click', function () {
    var list = visible();
    var head = ['date', 'strategy', 'market', 'side', 'line', 'model_p', 'naive_p', 'outcome', 'placed', 'units', 'source'];
    var out = [head.join(',')];
    list.forEach(function (b) {
      out.push([b.date, b.strategy, b.market, b.side, b.line, b.p, b.pNaive, b.outcome, b.placed, b.units, b.sourceUrl]
        .map(function (v) {
          var s = v === null || v === undefined ? '' : String(v);
          return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
        }).join(','));
    });
    var blob = new Blob([out.join('\\n')], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'nfl-lines-bets.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
"""


def main():
    D = {
        "lines": load("lines.json", {"lines": []}),
        "strategies": load("strategies.json", {"strategies": [], "bets": []}),
        "leaderboard": load("leaderboard.json", {"leaderboard": [], "meta": {}}),
        "correlations": load("correlations.json", {"strategyCorrelations": [], "productionCorrelations": [], "parlayCorrelations": []}),
        "lineup-risk": load("lineup-risk.json", {"rows": []}),
        "suggestions": load("suggestions.json", {"suggestions": []}),
        "questions": load("questions.json", {"questions": []}),
        "flags": load("flags.json", {"flags": []}),
    }
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    with open(os.path.join(OUT, "assets", "lines.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    with open(os.path.join(OUT, "assets", "lines.js"), "w", encoding="utf-8") as f:
        f.write(JS)

    builders = {
        "index.html": build_index,
        "lines.html": build_lines,
        "strategies.html": build_strategies,
        "leaderboard.html": build_leaderboard,
        "bets.html": build_bets,
        "validation.html": build_validation,
        "correlations.html": build_correlations,
        "injuries.html": build_injuries,
        "suggestions.html": build_suggestions,
        "questions.html": build_questions,
        "executive-summary.html": build_exec,
        "sources.html": build_sources,
        "flagged.html": build_flagged,
    }
    for fname, fn in builders.items():
        html_out = fn(D)
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(html_out)
        print("wrote", os.path.join(OUT, fname))
    print(f"{len(builders)} pages")


if __name__ == "__main__":
    main()
