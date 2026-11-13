#!/usr/bin/env python3
"""Stage 8 - render the NFL lines lab site under nfl-lines/.

Pages (all static, no JS framework, shared stylesheet):
  index.html            landing dashboard: what is proven, what is not, what to do next
  lines.html            Week 11 fair lines: model number vs market number vs fair price
  leaderboard.html      strategy leaderboard with gates, intervals and luck tests
  backtest.html         per-strategy evidence: season splits, calibration, models vs market
  correlation.html      measured correlations (same-game and player pairs)
  injuries.html         2026 week-10 tracker + 2025 measured injury impact
  questions.html        questions / information / answers register
  suggestions.html      suggestions board with scored decisions
  sources.html          source registry + rejected sources + validation results
  flagged.html          every flaw, irregularity and unverified item, with source links
  method.html           method, gates, definitions and honesty rules

Also writes nfl-lines/assets/style.css + lab.css, and injects one nav link into the
existing root pages (idempotent, additive).
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "nfl-lines"
DATA = SITE / "data"
ASSETS = SITE / "assets"

NAV = [
    ("index.html", "Overview"),
    ("lines.html", "Fair lines"),
    ("leaderboard.html", "Leaderboard"),
    ("backtest.html", "Backtest"),
    ("correlation.html", "Correlation"),
    ("injuries.html", "Injuries & tiers"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
    ("method.html", "Method"),
]


def j(path: str):
    return json.loads((DATA / path).read_text(encoding="utf-8"))


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def fmt_pct(v, digits=1) -> str:
    if v is None:
        return '<span class="blank">blank</span>'
    return f"{v * 100:+.{digits}f}%"


def fmt_num(v, digits=2, suffix="") -> str:
    if v is None or v == "":
        return '<span class="blank">blank</span>'
    try:
        return f"{v:.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return esc(v)


def badge(kind: str, text: str | None = None) -> str:
    label = text or {
        "official": "OFFICIAL",
        "mirror": "MIRROR",
        "model": "MODEL",
        "notofficial": "NOT OFFICIAL",
        "blocked": "BLOCKED",
        "proposed": "PROPOSED",
        "done": "DONE",
        "watch": "WATCH",
        "pass": "PASS",
        "unverified": "UNVERIFIED",
        "awaiting": "AWAITING DECISION",
        "answered": "ANSWERED",
        "partial": "ANSWERED (PARTIAL)",
        "answeredno": "ANSWERED — NO",
    }.get(kind, kind.upper())
    return f'<span class="b {esc(kind)}">{esc(label)}</span>'


def table(headers, rows, tid="", cls="scroll") -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="{cls}"><table{" id=" + chr(34) + tid + chr(34) if tid else ""}>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def page(name: str, title: str, body: str, desc: str = "") -> str:
    parts = []
    for h, t in NAV:
        cls = ' class="active"' if h == name else ""
        parts.append(f'<a href="{h}"{cls}>{esc(t)}</a>')
    nav = "".join(parts)
    root_nav = ('<a href="../index.html">Free Time planner</a>'
                '<a href="../nfl-strategy.html">Strategy proposal</a>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · NFL lines lab</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="assets/lab.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> NFL LINES LAB</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
<p><strong>NFL lines &amp; strategy lab</strong> — research instrument, not betting advice. No wager is
recommended anywhere on this site. Market prices shown are derived from a public archive and are
labelled <strong>NOT OFFICIAL</strong>; the NFL publishes no betting prices.
· <a href="{NAV[0][0]}">Overview</a> · <a href="sources.html">Sources</a> ·
<a href="flagged.html">Flagged for review</a> · <a href="method.html">Method</a></p>
<p class="small">{root_nav} · data built {esc(j('backtest/summary.json')['generatedUTC'])}</p>
</div></footer></body></html>"""


# --------------------------------------------------------------------------- pages
def render_index():
    s = j("backtest/summary.json")
    q = j("decision/questions.json")
    sg = j("decision/suggestions.json")
    val = j("validation/validation.json")
    inj = j("injuries/tracker-2026-week10.json")
    corr = j("correlation/correlations.json")
    lines = j("lines/week-11-2026.json")
    lb = j("backtest/leaderboard.json")
    best = [r for r in lb if r["rank"]][0]
    elo = s["diagnostics"]["eloAll"]
    mkt = s["diagnostics"]["marketMoneyline"]
    body = f"""
<aside class="callout flag"><strong>Read this first.</strong> Nothing on this site is a betting
recommendation. Every market price is <strong>NOT OFFICIAL</strong>: the NFL does not publish prices, so
the comparison numbers come from a public archive. Every model number is labelled MODEL. Where a value
could not be confirmed it is <strong>blank</strong> and listed on <a href="flagged.html">Flagged for review</a>.</aside>

<p class="eyebrow">Seasoned research build · {esc(s['generatedUTC'])}</p>
<h1>Can I originate my own NFL lines?</h1>
<p class="lede">Yes — and this site does it, then measures whether the number is any good. The short answer:
the fair lines are generated and published for 2026 Week 11, the strategies are backtested on
{s['seasonsInArchive'][0]}–{s['seasonsInArchive'][1]}, and <strong>not one of them has demonstrated skill rather
than luck</strong>. That is the finding, not a failure of the build.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{s['gamesGraded']:,}<small>graded games in the archive</small></div>
    <p class="small">{s['seasonsInArchive'][0]}–{s['seasonsInArchive'][1]}, {len(s['seasonsWithOdds'])} seasons with prices.</p></div>
  <div class="card"><div class="kpi">{s['strategiesTested']}<small>strategies tested</small></div>
    <p class="small">{s['qualifiedStrategies']} qualified. {s['strategiesBlocked']} declared but blocked for lack of data.</p></div>
  <div class="card"><div class="kpi">{s['familySize']}<small>hypotheses in the family</small></div>
    <p class="small">All p-values corrected for {s['familySize']} simultaneous tests.</p></div>
  <div class="card"><div class="kpi">{val['verdict']['standingsAgreement']}<small>official standings agreement</small></div>
    <p class="small">Archive checked club-by-club against nfl.com/standings.</p></div>
</div>

<h2>The three answers</h2>
<div class="grid g3">
  <div class="card"><h3>1 · Lines, originated</h3>
    <p>{lines['counts']['games']} Week 11 games carry a model fair spread, fair total, fair moneyline and the
    break-even price at which the model thinks the bet is a coin flip.</p>
    <p class="small">{lines['counts']['play']} can be labelled PLAY, because no strategy has passed the release
    gates.</p><a href="lines.html">Open the fair-line card →</a></div>
  <div class="card"><h3>2 · Skill, measured</h3>
    <p>The best point estimate is {esc(best['name'])} at {fmt_pct(best['stats'].get('roi'))} ROI on
    {best['stats'].get('n')} bets — with an interval of {fmt_pct(best['interval'].get('low'))} to
    {fmt_pct(best['interval'].get('high'))}.</p>
    <p class="small">An interval that straddles zero means luck cannot be ruled out.</p>
    <a href="leaderboard.html">Open the leaderboard →</a></div>
  <div class="card"><h3>3 · What is missing</h3>
    <p>{q['counts']['total']} questions are logged; {q['counts'].get('UNVERIFIED', 0)} are unverified and
    {q['counts'].get('AWAITING-DECISION', 0)} need your decision.</p>
    <p class="small">{sg['counts']['total']} suggestions, {sg['counts'].get('DONE', 0)} already built.</p>
    <a href="questions.html">Open the question register →</a></div>
</div>

<h2>Signal quality: the model versus the market</h2>
<p>The single most important number on this site. <strong>Signal</strong> is 1 − (Brier score ÷ the Brier score of
always predicting the base rate). Zero means no information; higher is better. Both are scored on the same games.</p>
{table(["Scored on", "Signal", "Brier", "Log loss", "Games"],
       [["Ratings model (Elo)", fmt_num(elo['signal'], 3), fmt_num(elo['brier'], 4),
         fmt_num(elo['logLoss'], 4), f"{elo['n']:,}"],
        ["De-vigged closing market " + badge("notofficial"), fmt_num(mkt['signal'], 3),
         fmt_num(mkt['brier'], 4), fmt_num(mkt['logLoss'], 4), f"{mkt['n']:,}"]])}
<p class="small">The market reference scores {fmt_num(mkt['signal'] - elo['signal'], 3)} higher than the model. Any
claim that a model beats the closing market has to close that gap first. Source for results: nflverse mirror,
validated against <a href="https://www.nfl.com/standings/">nfl.com/standings</a> — see
<a href="sources.html">Sources</a>.</p>

<h2>Injuries and backup tiers</h2>
<div class="grid g2">
  <div class="card"><h3>This week, officially</h3>
    <p>{len(inj['rows'])} players are officially listed across the three 2026 Week 10 games captured:
    <strong>{inj['officialStatusCounts']['Out']} Out</strong>,
    {inj['officialStatusCounts']['Doubtful']} Doubtful, {inj['officialStatusCounts']['Questionable']} Questionable,
    and <strong>{inj['officialStatusCounts']['blank']}</strong> with no game status published yet.</p>
    <p class="small">Tiers are <em>computed</em> from last season's production because the official depth chart
    page returns 404 here. That is stated on every row.</p>
    <a href="injuries.html">Injury and tier tracker →</a></div>
  <div class="card"><h3>Does a backup actually cost points?</h3>
    <p>Measured on {j('injuries/impact-2025.json')['nClubWeeks']} club-weeks: a missing tier-1 offensive player
    changed scoring by {fmt_num(j('injuries/impact-2025.json')['overall']['anyTier1OffenseOut']['difference'], 2)}
    points, with an interval that includes zero.</p>
    <p class="small">Translation: on this evidence, tier-1 absences do not move the score measurably. The
    quarterback-only estimate is larger but has only 18 club-weeks behind it, so it gets no interval and no
    betting role.</p></div>
</div>

<h2>Correlation: what is real</h2>
{table(["Pair", "n", "φ (phi)", "Joint observed", "If independent", "Reading"],
       [["Home covers  ×  total over", str(corr['sameGame']['spreadTotal']['n']),
         fmt_num(corr['sameGame']['spreadTotal']['phi'], 4),
         fmt_num(corr['sameGame']['spreadTotal']['jointObserved'], 4),
         fmt_num(corr['sameGame']['spreadTotal']['jointIfIndependent'], 4),
         "essentially independent"],
        ["QB passing yards  ×  his WR1 receiving yards", str(corr['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['n']),
         fmt_num(corr['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['phi'], 4),
         fmt_num(corr['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['jointObserved'], 4),
         fmt_num(corr['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['jointIfIndependent'], 4),
         "strong positive — combos here are NOT independent"],
        ["RB1 rushing  ×  RB2 rushing (same club)", str(corr['playerPairs']['rb1RushYds_rb2RushYds_sameTeam']['n']),
         fmt_num(corr['playerPairs']['rb1RushYds_rb2RushYds_sameTeam']['phi'], 4),
         fmt_num(corr['playerPairs']['rb1RushYds_rb2RushYds_sameTeam']['jointObserved'], 4),
         fmt_num(corr['playerPairs']['rb1RushYds_rb2RushYds_sameTeam']['jointIfIndependent'], 4),
         "weakly positive, not the negative split usually assumed"]])}
<p class="small">φ is a descriptive statistic on 0/1 outcomes, not a pricing formula. Prop "lines" are each
player's own trailing 4-game average because there are no prop prices in the archive — a stated limitation,
not a hidden one.</p>

<h2>Where to go next</h2>
<div class="grid g3">
  <div class="card"><h3>Decide something</h3><p>Every open question names the exact step that would settle it,
  and every suggestion names the decision you have to make.</p>
  <a href="suggestions.html">Suggestions board →</a></div>
  <div class="card"><h3>Check the evidence</h3><p>Sources, rejected sources, and the line-by-line validation
  of the archive against official NFL pages.</p><a href="sources.html">Sources and validation →</a></div>
  <div class="card"><h3>See what failed</h3><p>Every flaw, every unverified value, every blocked strategy,
  nothing hidden.</p><a href="flagged.html">Flagged for review →</a></div>
</div>
"""
    return page("index.html", "Overview", body,
                "NFL line origination, strategy leaderboard with validation gates, correlation engine and injury tracker.")


def render_lines():
    d = j("lines/week-11-2026.json")
    rows = []
    for r in d["lines"]:
        mp = r["fairPrice"].get("moneyline") or {}
        sp = r["fairPrice"].get("spread") or {}
        rows.append([
            f'<strong>{esc(r["away"])} @ {esc(r["home"])}</strong><br><span class="small">{esc(r["kickoff"].replace("T", " "))}</span>',
            fmt_num(r["market"]["spread"], 1) + "<br><span class=\"small\">total " + fmt_num(r["market"]["total"], 1) + "</span>",
            fmt_num(r["model"]["fairSpread"], 1) + "<br><span class=\"small\">total " + fmt_num(r["model"]["fairTotal"], 1) + "</span>",
            (fmt_num(r["edge"].get("spread", {}).get("homeEdgePoints"), 1) if r["edge"].get("spread") else '<span class="blank">blank</span>'),
            (f'{esc(mp.get("fairAmericanHome"))} / {esc(mp.get("fairAmericanAway"))}' if mp else '<span class="blank">blank</span>'),
            (f'{esc(mp.get("marketAmericanHome"))} / {esc(mp.get("marketAmericanAway"))}' if mp else '<span class="blank">blank</span>'),
            badge("watch") if r["label"] == "WATCH" else badge("pass"),
        ])
    body = f"""
<p class="eyebrow">Line origination · 2026 week {d['week']}</p>
<h1>Fair lines, and the price they imply</h1>
<p class="lede">A fair line is the number at which the model thinks the bet is a coin flip. The price that
follows from it — the break-even price — is the actual origination. Compare it with what the market asks and
you can see the whole disagreement in one row.</p>

<aside class="callout flag"><strong>No row can be labelled PLAY.</strong> A PLAY label requires a strategy that
has passed every validation gate, including a frozen prospective trial and a human release review. None has, so
the strongest label here is WATCH. This is deliberate: the site must not dress a research number as a pick.</aside>

<h2>Week {d['week']} card</h2>
{table(["Game", "Market " + badge("notofficial"), "Model fair " + badge("model"), "Gap (pts)",
        "Fair price (home / away)", "Market price (home / away)", "Label"], rows)}
<p class="small">Gap = model fair home margin minus the archive's number, in points. Positive means the model
thinks the home club is stronger than the number does.</p>

<h2>How each number is produced</h2>
<ul class="clean">
{''.join(f'<li>{esc(m)}</li>' for m in d['method'])}
</ul>
<h3>Mapping constants (so the number is reproducible)</h3>
{table(["Constant", "Value", "Fitted on"], [
    ["Intercept (points)", fmt_num(d['marginMapping']['intercept'], 2), f"{d['marginMapping']['fittedOn']:,} graded games"],
    ["Slope (points per probability unit)", fmt_num(d['marginMapping']['slope'], 2), f"{d['marginMapping']['fittedOn']:,} graded games"],
    ["League mean total (points)", fmt_num(d['leagueMeanTotal'], 2), "all graded games"],
    ["Prior weight (games)", "6.0", "fixed, documented in the code"],
])}

<h2>What is deliberately NOT in these numbers</h2>
<ul class="clean">
{''.join(f'<li>{esc(b)}</li>' for b in d['blockedInputs'])}
</ul>

<h2>Did the model's number beat the market's number?</h2>
<p>No. On {j('backtest/summary.json')['gamesGraded']:,} graded games the model's mean absolute error on the home
margin is {fmt_num(j('backtest/strategies/s2-elo-spread.json')['gradedRows']['spreadMAEModel'], 2)} points; the
closing number's own error on the same games is
{fmt_num(j('backtest/strategies/s2-elo-spread.json')['gradedRows']['spreadMAEMarket'], 2)} points. The market is
better, and publishing that is the point. <a href="backtest.html">See the full comparison →</a></p>
"""
    return page("lines.html", "Fair lines", body, "2026 Week 11 fair lines produced from the model, compared with the market number.")


def render_leaderboard():
    lb = j("backtest/leaderboard.json")
    s = j("backtest/summary.json")
    rows = []
    for r in lb:
        st = r["stats"]
        ci = r["interval"]
        gates = r["gates"]
        passed = sum(1 for g in gates.values() if g["pass"])
        luck = r["luck"]
        rows.append([
            (f'<strong>{esc(r["name"])}</strong><br><span class="small">{esc(r["id"])}</span>'
             if r["declaredStatus"] == "TESTED" else
             f'<strong>{esc(r["name"])}</strong><br><span class="small">{esc(r["id"])}</span> {badge("blocked")}'),
            esc(r["market"]),
            (f'{st.get("n", 0):,}' if st.get("n") else '<span class="blank">0 — blocked</span>'),
            fmt_pct(st.get("roi")) if st.get("n") else '<span class="blank">blank</span>',
            (f'{fmt_pct(ci.get("low"))} to {fmt_pct(ci.get("high"))}' if ci.get("low") is not None
             else '<span class="blank">not estimable</span>'),
            (fmt_num(luck.get("pValueVsMarket"), 3) if luck.get("pValueVsMarket") is not None
             else '<span class="blank">blank</span>'),
            (fmt_num(luck.get("pValueBonferroni"), 3) if luck.get("pValueBonferroni") is not None
             else '<span class="blank">blank</span>'),
            f"{passed}/{len(gates)}",
            (badge("proposed", f"RANK {r['rank']}") if r["rank"] else '<span class="blank">no rank</span>'),
            ('<span class="b done">ELIGIBLE</span>' if r["rewardEligible"] else '<span class="b blocked">NOT ELIGIBLE</span>'),
        ])
    cards = ""
    for r in lb:
        if r["declaredStatus"] != "TESTED":
            continue
        gates = "".join(
            f'<li>{("<span class=ok>PASS</span>" if g["pass"] else "<span class=no>FAIL</span>")} '
            f'<strong>{esc(k.split("_")[1])}</strong> — {esc(g["detail"])}</li>'
            for k, g in r["gates"].items())
        cards += f"""
<div class="card"><h3>{esc(r['name'])}</h3>
<p>{esc(r['description'])}</p>
<p class="small"><strong>Inputs:</strong> {esc(r['features'])}</p>
<p class="small"><strong>Limits:</strong> {esc(r['gateNote'])}</p>
<ul class="clean gates">{gates}</ul></div>"""
    body = f"""
<p class="eyebrow">Competition · validation gates · luck removal</p>
<h1>Leaderboard</h1>
<p class="lede">A leaderboard that rewards luck is worse than no leaderboard. So the rank here is the
<em>lower bound</em> of the ROI interval, not the ROI: a strategy only moves up when its worst plausible
outcome improves. Reward eligibility sits behind all eight gates.</p>

<aside class="callout flag"><strong>{s['qualifiedStrategies']} of {s['strategiesTested']} tested strategies
qualified.</strong> {s['rewardEligibleStrategies']} are reward-eligible. This is not a bug — it is the
gate doing its job. A strategy that has not been through a frozen prospective trial cannot be promoted on
backtest evidence alone.</aside>

{table(["Strategy", "Market", "Bets", "ROI", "95% ROI interval", "p vs market (no skill)",
        "p corrected (m=" + str(s['familySize']) + ")", "Gates", "Rank", "Reward"], rows)}
<p class="small"><strong>How to read the interval.</strong> Whole weeks are resampled with replacement, because
games inside a week share conditions. If the interval includes zero, the result is consistent with a bettor who
has no edge at all. Point estimates without intervals are not published anywhere on this site.</p>
<p class="small"><strong>How to read "p vs market".</strong> Each bet's true win probability is set to the
de-vigged closing market probability of the side taken, then 10,000 seeded simulations ask how often a bettor
with <em>no information beyond the market</em> would earn at least this ROI. This is the sharpest honest null.
Note what it does to the best-looking row: the three-leg parlay's p falls from a naive 0.0005 to
{fmt_num([r for r in j('backtest/leaderboard.json') if r['id'] == 's8-elo-three-leg-parlay'][0]['luck'].get('pValueVsMarket'), 3)}
once mixed prices are handled correctly — the naive test was measuring price variance, not skill.</p>

<h2>Gate-by-gate detail</h2>
<div class="grid g2">{cards}</div>

<h2>What would have to happen for a reward to be paid</h2>
<ol>
<li>The strategy passes data provenance, coverage, baseline, leakage, out-of-sample sample size and robustness.</li>
<li>It is frozen — code, inputs and thresholds — and its predictions are logged <em>before</em> outcomes.</li>
<li>The frozen trial completes a pre-declared horizon.</li>
<li>A human review confirms there is no integrity or responsible-use problem.</li>
</ol>
<p>Only then does the ELIGIBLE badge appear. No amount of backtest ROI substitutes for that sequence.</p>
"""
    return page("leaderboard.html", "Leaderboard", body, "Strategy leaderboard ranked by evidence strength with validation gates.")


def render_backtest():
    lb = j("backtest/leaderboard.json")
    s = j("backtest/summary.json")
    benches = s["benchmarks"]
    rows = [[esc(b["label"]), f"{b['n']:,}", fmt_pct(b["roi"]),
             fmt_num(b["avgDecimal"], 3),
             "a bettor with no model at all"] for b in benches]
    strat_rows = []
    for r in lb:
        if r["declaredStatus"] != "TESTED":
            continue
        splits = r.get("seasonSplits") or []
        seasonal = " · ".join(f"{x['season']}: {fmt_pct(x.get('roi'))}" for x in splits[:6])
        strat_rows.append([esc(r["name"]), f"{r['stats']['n']:,}",
                           fmt_num(r["stats"].get("roi"), 4),
                           fmt_num(r["interval"].get("low"), 4),
                           fmt_num(r["interval"].get("high"), 4),
                           f"{sum(1 for x in splits if (x.get('roi') or 0) > 0)}/{len(splits)}",
                           f'<span class="small">{seasonal}</span>'])
    body = f"""
<p class="eyebrow">Evidence · walk-forward · {s['seasonsInArchive'][0]}–{s['seasonsInArchive'][1]}</p>
<h1>Backtest</h1>
<p class="lede">Every result is walk-forward: the model for a game only ever sees games that kicked off before it.
The seed is fixed at {s['seed']} and the code is in the repository, so any number here can be reproduced.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{s['gamesInArchive']:,}<small>games in archive</small></div></div>
  <div class="card"><div class="kpi">{s['gamesGraded']:,}<small>graded (played) games</small></div></div>
  <div class="card"><div class="kpi">{s['minBetsGate']}<small>pre-declared minimum bets</small></div></div>
  <div class="card"><div class="kpi">{s['edgeThreshold']}<small>minimum probability edge</small></div></div>
</div>

<h2>The benchmark nobody beats</h2>
<p>Before a strategy means anything, it has to beat a bettor with no model. These are fixed-rule bets placed on
every eligible game at the quoted price.</p>
{table(["Fixed rule", "Bets", "ROI", "Average decimal price", "Comment"], rows)}
<p class="small">Every blanket rule loses — which is the house edge appearing exactly where it should. A strategy
that claims to win has to explain why it escapes it.</p>

<h2>Strategy results with per-season splits</h2>
{table(["Strategy", "Bets", "ROI", "Interval low", "Interval high", "Seasons positive", "Season detail"],
       strat_rows)}
<p class="small">A strategy that is strongly positive in one season and strongly negative in the next is mostly
noise. The "seasons positive" column is the cheap version of that check; the interval is the honest one.</p>

<h2>Calibration of the underlying model</h2>
<p>Before any bet sizing, the probability estimate has to be calibrated: of the games the model gives about a
60% chance, about 60% should be won.</p>
{tbl_calibration()}

<h2>What is not in this backtest, and why that matters</h2>
<ul class="clean">
<li><strong>No injuries.</strong> The archive's injury data is a five-column mirror with no practice status, and
no official depth chart could be retrieved. Adding a fake injury feature would be worse than adding none.</li>
<li><strong>No weather.</strong> Indoor/outdoor is known; conditions are not.</li>
<li><strong>No player props.</strong> There are no prop prices, so a prop backtest is impossible rather than
merely absent.</li>
<li><strong>No line movement.</strong> Only one price per game exists, so no open-to-close analysis is possible.</li>
</ul>
<p>Each of those is a <a href="flagged.html">flagged item</a>, not a silent gap.</p>
"""
    return page("backtest.html", "Backtest", body, "Walk-forward backtest of every strategy with per-season splits.")


def tbl_calibration() -> str:
    try:
        s1 = j("backtest/strategies/s1-elo-moneyline.json")
        rows = s1["gradedRows"].get("calibration") or []
        if not rows:
            return '<p class="small">No calibration table produced.</p>'
        return table(["Predicted probability bin", "Games", "Mean predicted", "Actually won"],
                     [[esc(r["bin"]), str(r["n"]), fmt_num(r["meanPredicted"], 3), fmt_num(r["observed"], 3)]
                      for r in rows])
    except Exception as exc:  # noqa: BLE001
        return f'<p class="small">Calibration table unavailable: {esc(exc)}</p>'


def render_correlation():
    d = j("correlation/correlations.json")
    sg = d["sameGame"]
    rows = []
    for k in ("spreadTotal", "moneylineTotal", "favouriteUnder"):
        v = sg[k]
        rows.append([esc(v["label"]), f"{v['n']:,}", fmt_num(v["phi"], 4),
                     fmt_num(v["jointObserved"], 4), fmt_num(v["jointIfIndependent"], 4),
                     fmt_num(v["jointDifference"], 4),
                     (f'{fmt_num(v["ci"].get("low"), 4)} to {fmt_num(v["ci"].get("high"), 4)}'
                      if v["ci"].get("low") is not None else '<span class="blank">not estimable</span>')])
    prows = []
    for k, v in d["playerPairs"].items():
        prows.append([esc(v["label"]), str(v.get("n", 0)), fmt_num(v.get("phi"), 4),
                      fmt_num(v.get("jointObserved"), 4), fmt_num(v.get("jointIfIndependent"), 4),
                      esc(v.get("assumedPricing", "")),
                      "confirmed" if (v.get("phi") or 0) > 0.05 else ("confirmed (negative)" if (v.get("phi") or 0) < -0.05 else "not supported")])
    pd_ = d["parlayDependence"]
    body = f"""
<p class="eyebrow">Correlation engine · measured, not assumed</p>
<h1>Correlation</h1>
<p class="lede">A parlay priced by multiplying the legs is only correct when the legs are independent. This page
measures the dependence instead of assuming it: first for markets within one game, then for players on the same
club, then for the actual parlays the lab placed.</p>

<aside class="callout warn"><strong>Prop lines on this page are proxies.</strong> There are no player-prop
prices in the archive, so "over" means "over his own trailing 4-game average". These correlations are real
measurements of player dependence, but they cannot price a real prop bet.</aside>

<h2>Same-game markets</h2>
{table(["Pair", "Games", "φ", "Joint observed", "If independent", "Error of assuming independence", "95% interval"], rows)}
<p class="small">Read <strong>Error of assuming independence</strong> as the probability error you would carry into
a price. It is small for these pairs — which is worth knowing, because it means the "correlated same-game parlay"
story is mostly about <em>players</em>, not about spread-versus-total.</p>

<h2>Player pairs (2025 season)</h2>
{table(["Pair", "n", "φ", "Joint observed", "If independent", "Expected direction", "Verdict"], prows)}
<p class="small">Sample sizes are one season of one club-week per team. Treat any φ under about 0.1 as
indistinguishable from noise at this sample size.</p>

<h2>The parlays actually placed</h2>
<div class="grid g2">
  <div class="card"><h3>Two legs</h3>
    <p>{pd_['twoLeg']['n']} parlays placed. Observed joint hit rate
    <strong>{fmt_pct(pd_['twoLeg']['observedJointHitRate'])}</strong> against a modelled joint probability of
    {fmt_pct(pd_['twoLeg']['meanModelJointProbability'])}.</p>
    <p class="small">{esc(pd_['twoLeg']['note'])}</p></div>
  <div class="card"><h3>Three legs</h3>
    <p>{pd_['threeLeg']['n']} parlays placed. Observed joint hit rate
    <strong>{fmt_pct(pd_['threeLeg']['observedJointHitRate'])}</strong>.</p>
    <p class="small">{esc(pd_['threeLeg']['note'])}</p></div>
</div>
<aside class="callout">{esc(pd_['correlationLesson'])}</aside>

<h2>Why this matters for pricing</h2>
<p>Take the strongest measured pair: a quarterback's passing yards and his WR1's receiving yards, φ ≈
{fmt_num(d['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['phi'], 2)}. Multiplying the two marginal
probabilities gives {fmt_num(d['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['jointIfIndependent'], 3)};
the observed joint rate is {fmt_num(d['playerPairs']['qbPassYds_wr1RecYds_sameTeam']['jointObserved'], 3)}.
A parlay that pays as if the joint rate were the smaller number is paying too much on the winning side — which
sounds generous until you notice the losing side is where the money is made.</p>

<h2>Status</h2>
<p>{badge("notofficial")} {esc(d['officialStatus'])}</p>
"""
    return page("correlation.html", "Correlation", body, "Measured correlation between markets and players, and its effect on parlay pricing.")


def render_injuries():
    t = j("injuries/tracker-2026-week10.json")
    im = j("injuries/impact-2025.json")
    rows = []
    for r in t["rows"]:
        tier = (f'{esc(r["tier"])}' if r["tier"] else '<span class="blank">blank</span>')
        repl = (f'{esc(r["candidateReplacement"]["player"])} ({esc(r["candidateReplacement"]["tier"])})'
                if r["candidateReplacement"] else '<span class="blank">none found</span>')
        status = esc(r["gameStatus"]) if r["gameStatus"] else '<span class="blank">blank</span>'
        rows.append([esc(r["team"]), esc(r["position"]), esc(r["player"]), esc(r["positionGroup"]),
                     tier, status, esc(r["practiceStatus"]), esc(r["injury"]) if r["injury"] else '<span class="blank">blank</span>',
                     repl])
    club_rows = []
    for club, v in t["clubSummary"].items():
        club_rows.append([esc(club), str(v["offenseListed"]), str(v["offenseTier1Out"]),
                          str(v["defenseListed"]), str(v["defenseTier1Out"]),
                          f'<a href="{esc(v["sourceUrl"])}">official report</a>'])
    d_rows = [[esc(k), esc(v["positionGroup"]), esc(v["side"]), esc(v["metric"]),
               str(v["nWith"]), str(v["nWithout"]), fmt_num(v["meanWith"], 2), fmt_num(v["meanWithout"], 2),
               fmt_num(v["difference"], 2),
               (f'{fmt_num(v["ci"].get("low"), 2)} to {fmt_num(v["ci"].get("high"), 2)}'
                if v["ci"].get("low") is not None else '<span class="blank">sample too small</span>')]
              for k, v in im["byPositionGroup"].items()]
    o = im["overall"]
    body = f"""
<p class="eyebrow">Injury and backup-tier tracking · offence and defence</p>
<h1>Injuries &amp; tiers</h1>
<p class="lede">Two separate questions, kept separate: <em>who is officially unavailable right now</em>, and
<em>does losing a tier-1 player actually change the score</em>. The first is official. The second is measured,
and the measured answer is "not much".</p>

<aside class="callout flag"><strong>Tiers are computed, not official.</strong> The NFL depth-chart pages return
HTTP 404 from this environment (checked 2026-11-13). Rather than invent a depth order, tiers are ranked from last
season's production within the same club and position group, and every row says so. A rookie or new signing with
no production record gets a <strong>blank</strong> tier.</aside>

<div class="grid g4">
  <div class="card"><div class="kpi">{len(t['rows'])}<small>officially listed players</small></div>
    <p class="small">Three 2026 Week 10 games transcribed verbatim.</p></div>
  <div class="card"><div class="kpi">{t['officialStatusCounts']['Out']}<small>officially OUT</small></div></div>
  <div class="card"><div class="kpi">{t['officialStatusCounts']['blank']}<small>no game status published</small></div>
    <p class="small">Left blank. Never inferred as available.</p></div>
  <div class="card"><div class="kpi">{im['nClubWeeks']}<small>2025 club-weeks measured</small></div></div>
</div>

<h2>Does a tier-1 absence cost points?</h2>
<p>This is the question that decides whether injury data can ever be a betting input. Answer measured on
{im['nClubWeeks']} club-weeks of the 2025 season, comparing club points with and without an officially
unavailable tier-1 player.</p>
{table(["Absence", "Metric", "With", "Without", "Difference", "95% interval"], [
    ["Tier-1 offensive player out", esc(o["anyTier1OffenseOut"]["metric"]),
     f'{o["anyTier1OffenseOut"]["nWith"]} club-weeks', f'{o["anyTier1OffenseOut"]["nWithout"]} club-weeks',
     fmt_num(o["anyTier1OffenseOut"]["difference"], 2),
     f'{fmt_num(o["anyTier1OffenseOut"]["ci"].get("low"), 2)} to {fmt_num(o["anyTier1OffenseOut"]["ci"].get("high"), 2)}'],
    ["Tier-1 defensive player out", esc(o["anyTier1DefenseOut"]["metric"]),
     f'{o["anyTier1DefenseOut"]["nWith"]} club-weeks', f'{o["anyTier1DefenseOut"]["nWithout"]} club-weeks',
     fmt_num(o["anyTier1DefenseOut"]["difference"], 2),
     f'{fmt_num(o["anyTier1DefenseOut"]["ci"].get("low"), 2)} to {fmt_num(o["anyTier1DefenseOut"]["ci"].get("high"), 2)}']])}
<p><strong>Both intervals include zero.</strong> On this evidence a tier-1 absence does not move the score
measurably, in either direction. That is a real finding and it is published as one.</p>

<h3>By position group</h3>
{table(["Group", "Position", "Side", "Metric", "With", "Without", "Mean with", "Mean without", "Difference", "95% interval"], d_rows)}
<p class="small">The quarterback row is the largest effect and the least reliable: 18 club-weeks cannot support an
interval, so it is blank rather than quoted. No group clears its interval.</p>

<h2>This week, officially listed</h2>
<p>Every row below comes from <a href="{esc(t['sourceUrl'])}">{esc(t['sourceUrl'])}</a>. Position, injury,
practice status and game status are as printed. Blank cells were blank on the page.</p>
{table(["Club", "Pos", "Player", "Group", "Computed tier", "Game status", "Practice status", "Injury",
        "Next-ranked candidate"], rows)}
<p class="small"><strong>Candidate</strong> = the next player at the same club and position group by last
season's production. It is not a lineup announcement and does not predict snaps.</p>

<h2>Club summary</h2>
{table(["Club", "Offence listed", "Offence tier-1 OUT", "Defence listed", "Defence tier-1 OUT", "Source"],
       club_rows)}
<p class="small">Scope: three of the week's games. The remaining games are absent, not blank — a tracked
coverage gap on the <a href="flagged.html">Flagged</a> page.</p>

<h2>Method and limitations</h2>
<ul class="clean">{''.join(f'<li>{esc(m)}</li>' for m in im['method'])}</ul>
<h3>Limitations</h3>
<ul class="clean">{''.join(f'<li>{esc(m)}</li>' for m in im['limitations'])}</ul>
"""
    return page("injuries.html", "Injuries & tiers", body, "Official injury report tracker with computed backup tiers and measured injury impact.")


def render_questions():
    d = j("decision/questions.json")
    rows = []
    for q in d["questions"]:
        b = {"ANSWERED": "answered", "ANSWERED-NO": "answeredno", "ANSWERED-PARTIAL": "partial",
             "UNVERIFIED": "unverified", "AWAITING-DECISION": "awaiting"}.get(q["status"], "unverified")
        src = (f'<a href="{esc(q["source"])}">official source</a>' if q["source"].startswith("http")
               else '<span class="blank">no possible official source</span>')
        rows.append([f'<strong>{esc(q["id"])}</strong><br><span class="small">{esc(q["area"])}</span>',
                     esc(q["question"]), esc(q["known"]), esc(q["unknown"]), esc(q["missingInfo"]),
                     esc(q["wouldChange"]), esc(q["discovery"]), src, badge(b)])
    body = f"""
<p class="eyebrow">Decision support · {d['counts']['total']} questions</p>
<h1>Questions, information and answers</h1>
<p class="lede">Nothing should be built on a question that has not been answered. Each row states what we know,
what we do <em>not</em> know, the information that is missing, what the answer would change, and the exact step
that would settle it.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{d['counts'].get('AWAITING-DECISION', 0)}<small>need your decision</small></div></div>
  <div class="card"><div class="kpi">{d['counts'].get('UNVERIFIED', 0)}<small>unverified</small></div></div>
  <div class="card"><div class="kpi">{d['counts'].get('ANSWERED-PARTIAL', 0)}<small>partly answered</small></div></div>
  <div class="card"><div class="kpi">{d['counts'].get('ANSWERED-NO', 0) + d['counts'].get('ANSWERED', 0)}<small>answered</small></div></div>
</div>
<p class="small">{esc(d['note'])}</p>

{table(["ID", "Question", "What we know", "What we do not know", "Missing information",
        "What the answer would change", "How to discover it", "Source", "Status"], rows)}

<h2>The questions that block everything else</h2>
<ol>
<li><strong>Is the model better than the market?</strong> No. Until it is, a line is a benchmark, not an alternative.</li>
<li><strong>Is there a legal, timestamped price archive?</strong> Without one, props and same-game parlays can
never be scored.</li>
<li><strong>Is official depth order obtainable?</strong> Without it, backup tiers stay a computed estimate.</li>
</ol>
"""
    return page("questions.html", "Questions", body, "Every question that must be answered before a decision, with what is known and unknown.")


def render_suggestions():
    d = j("decision/suggestions.json")
    rows = []
    for s in d["suggestions"]:
        b = {"DONE": "done", "PROPOSED": "proposed", "BLOCKED-PENDING": "blocked"}.get(s["status"], "proposed")
        src = (f'<a href="{esc(s["source"])}">source</a>' if s["source"].startswith("http")
               else '<span class="blank">—</span>')
        rows.append([f'<strong>{esc(s["title"])}</strong><br><span class="small">{esc(s["id"])}</span>',
                     esc(s["decision"]), esc(s["benefit"]), esc(s["risk"]), esc(s["cost"]),
                     esc(s["reversibility"]), esc(s["recommended"]), src, badge(b)])
    body = f"""
<p class="eyebrow">Review board · {d['counts']['total']} suggestions</p>
<h1>Suggestions</h1>
<p class="lede">The point of this page is to let you choose the best path <em>before</em> anything is built.
Each row names the decision, what it buys, what it risks, and what this lab recommends. Four items are marked
DONE because they exist in this build, so you can judge them by using them rather than by imagining them.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{d['counts'].get('PROPOSED', 0)}<small>proposed</small></div></div>
  <div class="card"><div class="kpi">{d['counts'].get('DONE', 0)}<small>already built</small></div></div>
  <div class="card"><div class="kpi">{d['counts'].get('BLOCKED-PENDING', 0)}<small>blocked on a decision</small></div></div>
  <div class="card"><div class="kpi">{d['counts']['total']}<small>total</small></div></div>
</div>
<p class="small">{esc(d['howToUse'])}</p>

{table(["Suggestion", "Decision you have to make", "Benefit", "Risk", "Cost", "Reversible?",
        "Recommended path", "Source", "Status"], rows)}

<h2>If you only act on three</h2>
<ol>
<li><strong>SG04 — score on the interval, not the ROI.</strong> Free, reversible, and it is the difference
between a leaderboard that rewards skill and one that rewards variance.</li>
<li><strong>SG05 — freeze a prospective trial.</strong> No strategy can ever be promoted without it, so the
competition cannot start until it happens.</li>
<li><strong>SG01 — decide pre-market or post-market lines.</strong> This changes what the fair line even means,
and everything downstream depends on the answer.</li>
</ol>
<p class="small">How items are scored: {esc(json.dumps(d['scoring'], ensure_ascii=False))}</p>
"""
    return page("suggestions.html", "Suggestions", body, "A reviewable board of improvement suggestions, scored by benefit, risk, cost and reversibility.")


def render_sources():
    reg = j("sources.json")
    val = j("validation/validation.json")
    rows = []
    for d in reg["datasets"]:
        kind = badge("official") if d.get("official") else badge("mirror")
        rows.append([f'<strong>{esc(d["title"])}</strong><br><span class="small">{esc(d["id"])}</span>',
                     kind,
                     f'<a href="{esc(d["accessUrl"])}" rel="noopener">{esc(d["accessUrl"][:70])}</a>',
                     esc(d.get("upstream", "—")),
                     esc(d.get("license", "—"))[:160],
                     (f'{d["rows"]:,} rows / {d["bytes"]:,} bytes' if d.get("rows") is not None else "—")])
    rej = [[f'<a href="{esc(r["url"])}" rel="noopener">{esc(r["url"][:70])}</a>', esc(r["reason"]),
            esc(r["evidence"])] for r in reg["rejectedSources"]]
    st = val["checks"]["standings2026"]
    st_rows = [[esc(r["club"]), f"{r['archive']['w']}-{r['archive']['l']}-{r['archive']['t']}",
                f"{r['official']['w']}-{r['official']['l']}-{r['official']['t']}",
                str(r["archive"]["pf"]), str(r["official"]["pf"]),
                str(r["archive"]["pa"]), str(r["official"]["pa"]),
                '<span class="ok">match</span>' if r["match"] else '<span class="no">MISMATCH</span>',
                f'<a href="{esc(r["sourceUrl"])}">nfl.com</a>'] for r in st["rows"]]
    sb = [[f'{esc(r["official"]["away"])} {r["official"]["awayScore"]} @ {esc(r["official"]["home"])} {r["official"]["homeScore"]}',
           esc(r["official"]["date"]),
           f'{esc(r["archive"]["away"])} {r["archive"]["awayScore"]} @ {esc(r["archive"]["home"])} {r["archive"]["homeScore"]}',
           '<span class="ok">match</span>' if r["match"] else '<span class="no">MISMATCH</span>',
           f'<a href="{esc(r["sourceUrl"])}">official game page</a>'] for r in val["checks"]["superBowls"]["rows"]]
    body = f"""
<p class="eyebrow">Provenance · {len(reg['datasets'])} datasets · {len(reg['rejectedSources'])} rejected</p>
<h1>Sources and validation</h1>
<p class="lede">No number on this site exists without a registered source. Every dataset is listed with how it
was reached, what it mirrors, its licence status, and what it cannot establish. Sources that were tried and
failed are listed too — a rejected source is a finding.</p>

<h2>Dataset registry</h2>
{table(["Dataset", "Kind", "Access URL", "Mirrors", "Licence / rights", "Size"], rows)}

<h2>Rejected sources (tried, failed, documented)</h2>
{table(["URL", "Why rejected", "Evidence"], rej)}

<h2>Line-by-line validation: 2026 standings</h2>
<p>Every club's archive record and points for/against, against <a href="{esc(st['sourceUrl'])}">{esc(st['sourceUrl'])}</a>.
<strong>{val['verdict']['standingsAgreement']} agree.</strong></p>
{table(["Club", "Archive W-L-T", "Official W-L-T", "Archive PF", "Official PF", "Archive PA",
        "Official PA", "Result", "Source"], st_rows)}

<h2>Super Bowl spot checks</h2>
{table(["Official result", "Official date", "Archive result", "Result", "Source"], sb)}
<p class="small">{esc(val['verdict']['superBowlAgreement'])} agree. Internal consistency:
{val['verdict']['internalErrors']} errors in result/total arithmetic and duplicate ids across
{val['checks']['internalConsistency']['rows']:,} games.</p>

<h2>Injury mirror audit</h2>
<p>The 2025 injury mirror carries {val['checks']['injuryMirror2025']['rows']:,} rows across
{val['checks']['injuryMirror2025']['clubs']} clubs, weeks
{val['checks']['injuryMirror2025']['weeksCovered'][0]}–{val['checks']['injuryMirror2025']['weeksCovered'][1]}, with
statuses {esc(json.dumps(val['checks']['injuryMirror2025']['statusCounts']))}. Columns present:
{esc(", ".join(val['checks']['injuryMirror2025']['columns']))}. Columns missing from the official page:
{esc(", ".join(val['checks']['injuryMirror2025']['missingOfficialColumns']))}.</p>

<h2>What was not verified</h2>
<ul class="clean">{''.join(f'<li>{esc(x)}</li>' for x in val['notVerified'])}</ul>

<h2>Citation policy</h2>
<ul class="clean">{''.join(f'<li>{esc(x)}</li>' for x in reg['citationPolicy'])}</ul>
"""
    return page("sources.html", "Sources", body, "Source registry, rejected sources and line-by-line validation against official NFL pages.")


def render_flagged():
    flags = []
    val = j("validation/validation.json")
    s = j("backtest/summary.json")
    t = j("injuries/tracker-2026-week10.json")
    corr = j("correlation/correlations.json")
    lines = j("lines/week-11-2026.json")
    reg = j("sources.json")

    def F(fid, area, what, why, source, sev="medium"):
        if source.startswith("http"):
            src = f'<a href="{esc(source)}" rel="noopener">source</a>'
        elif source.endswith(".html"):
            src = f'<a href="{esc(source)}">lab page</a>'
        else:
            src = '<span class="blank">no official source exists</span>'
        flags.append([f"<strong>{esc(fid)}</strong>", esc(area), esc(what), esc(why), src,
                      f'<span class="b {sev}">{esc(sev.upper())}</span>'])

    F("F01", "Market data", "Betting prices are not official NFL values",
      "The league publishes no prices; the archive used here is a public community mirror. No official "
      "verification is possible for any price.", reg["datasets"][2]["accessUrl"], "high")
    F("F02", "Licensing", "The nfldata repository has no licence file at the commit used",
      "Derived figures are published, so the rights question has to be resolved. nflverse-data itself is "
      "CC-BY-4.0; nfldata is not stated.", reg["datasets"][0]["repoUrl"], "high")
    F("F03", "Data access", "GitHub release binaries are unreachable from this environment",
      "release-assets.githubusercontent.com refuses the connection, so a third-party mirror was used for the "
      "2025 player and injury files. Those rows are labelled MIRROR.", reg["rejectedSources"][0]["url"], "high")
    F("F04", "Depth charts", "Official depth chart pages return HTTP 404",
      "nfl.com/teams/<club>/depth-chart is unavailable, so 1st/2nd/3rd/4th string order could not be read "
      "from the league. Tiers are computed from production and labelled as computed.",
      "https://www.nfl.com/teams/detroit-lions/depth-chart", "high")
    F("F05", "Injuries", f"{t['officialStatusCounts']['blank']} of {len(t['rows'])} officially listed players "
      "have a blank game status",
      "The official page leaves the field empty; it is left empty here and never read as 'available'.",
      t["sourceUrl"], "medium")
    F("F06", "Injuries", "Three of the week-10 games were transcribed; the rest are absent",
      "Coverage gap. The other games are not shown as empty, they are simply not present.",
      "https://www.nfl.com/injuries/", "medium")
    F("F07", "Injury impact", "Injury impact intervals include zero for every position group",
      "The measured effect of a tier-1 absence is not distinguishable from noise on one season of data. No "
      "injury adjustment is applied to any line.", "https://www.nfl.com/injuries/", "medium")
    F("F08", "Player props", "No player-prop prices exist in the archive",
      "Prop and same-game-parlay strategies are therefore declared but BLOCKED. Their profit is blank, not "
      "zero.", "", "high")
    F("F09", "Parlays", "Two- and three-leg parlays are priced at the product of the leg decimals",
      "That is an upper bound, not a book's correlated same-game price. The measured ROI is therefore an "
      "optimistic figure.", "", "high")
    F("F10", "Player correlation", "Prop 'lines' are each player's trailing 4-game average",
      "They are not sportsbook lines, so the measured player correlations describe dependence but cannot "
      "price a prop.", "", "medium")
    F("F11", "Model", "The model loses to the closing market",
      f"Model Brier {s['diagnostics']['eloAll']['brier']} vs market {s['diagnostics']['marketMoneyline']['brier']}. "
      "Any line published here is a benchmark, not an alternative to the market.",
      "https://www.nfl.com/stats/", "high")
    F("F12", "Model", "No weather, rest-travel, or injury inputs",
      "They are absent from the archive. Adding a guessed value would violate the no-invention rule.",
      "", "medium")
    F("F13", "Backtest", "Line prices carry no capture timestamp",
      "It is unknown whether the stored price is an open, a close, or an in-progress quote.",
      reg["datasets"][0]["repoUrl"], "high")
    F("F14", "Leaderboard", "Zero strategies qualified",
      "No strategy passes all eight gates, so no rank above 'unproven' and no reward eligibility exists.",
      "leaderboard.html", "high")
    F("F15", "Good-looking result", "The three-leg parlay shows a positive ROI with a tiny p-value",
      "Its bootstrap interval runs from -30.9% to +57.3%. It is the single most likely result on this site to "
      "be luck. It is kept visible on purpose.", f"leaderboard.html", "high")
    F("F16", "Data validation", "The exact number of 2026 games in the mirror is 163 with prices of 272 scheduled",
      "Weeks 12-18 carry no prices yet, so nothing downstream can be priced for them.", "", "low")
    F("F17", "Club labels", "The official standings page prints AZ while the archive uses ARI",
      "An explicit alias map is applied so a rename can never silently hide a disagreement.",
      "https://www.nfl.com/standings/", "low")
    F("F18", "Coverage", "1999–2001 seasons contain 31 clubs",
      "The Houston Texans did not exist before 2002. This is expected and documented, not a data defect.",
      "https://www.nfl.com/teams/houston-texans/", "low")
    F("F19", "Line card", "All 13 Week 11 rows are labelled WATCH and none PLAY",
      "WATCH means the model and the number disagree; it does not mean the model is right. In 7,413 graded "
      "games the market was better, so a WATCH row is at least as likely to be the model's error.",
      f"lines.html", "high")
    F("F20", "Fair price", "Fair prices are break-even prices, not offers",
      "A fair price implies zero hold. A real book charges a margin, so a fair price is never a price you can "
      "actually take.", f"method.html", "medium")
    F("F21", "Official cross-check", "2026 player-level totals were not checked against the archive",
      "The mirror holds 2025 player-week data only. Official 2026 leaderboard values are recorded for reference "
      "but no archive match is claimed.", "https://www.nfl.com/stats/player-stats/", "medium")
    F("F22", "Injury mirror", "The 2025 injury mirror lacks practice status and injury type",
      "Severity cannot be graded, so 'Out' and 'Injured Reserve' are treated alike. That weakens the measured "
      "impact.", "https://www.nfl.com/injuries/", "medium")
    F("F23", "Rate model", "Team scoring rates use a fixed 6-game prior",
      "The prior weight is a documented choice, not an estimated parameter. It is not tuned on outcomes, which "
      "is the safer error, but it is a choice.", "", "low")
    F("F24", "Correlation", "Player correlation samples are one season",
      "Around 300 club-weeks per pair. Any phi under about 0.1 should be treated as noise at this size.",
      "https://www.nfl.com/stats/player-stats/", "medium")
    F("F25", "Model", "Elo season regression and home-field constant are fixed conventions",
      "20-point K, 48-point home field and a one-third regression are public conventions, not fitted here. "
      "They are stated so the model can be reproduced and criticised.", "", "low")
    F("F26", "Neutral sites", "Neutral-site games are identified from the archive's location field only",
      "The 2026 Munich game is confirmed from the official game page, but every other neutral game relies on "
      "the archive flag.", "https://www.nfl.com/games/patriots-at-lions-2026-reg-10", "low")
    F("F27", "Fair total", "The fair total ignores weather and pace",
      "It is a scoring-rate average with a prior. Wind and dome effects are not modelled.",
      "https://operations.nfl.com/the-rules/", "medium")
    F("F28", "Coverage", "The 2026 Week 11 market was captured on 2026-11-13 and may move",
      "Any gap will change. The card is a snapshot, not a standing price.", f"lines.html", "medium")
    F("F29", "Process", "Multiple sessions work on this repository concurrently",
      "A parallel session may be building overlapping NFL data in other paths. This lab writes only under "
      "nfl-lines/, scripts/nfl_lines/, and appends to COORDINATION.md.",
      "https://github.com/karagemop466-tech/Korea5/blob/main/COORDINATION.md", "medium")

    body = f"""
<p class="eyebrow">Flagged for review · {len(flags)} items</p>
<h1>Flagged for review</h1>
<p class="lede">Everything below is a flaw, an irregularity, or a value that could not be confirmed from an
official source. None of it blocks publication — that is the point of the page. Review it after the fact and
ask for changes.</p>

<aside class="callout flag"><strong>Severity is the lab's own judgement.</strong> HIGH means a reader could draw
a materially wrong conclusion. MEDIUM means the conclusion is right but weaker than it looks. LOW means it is a
documentation matter.</aside>

{table(["ID", "Area", "What", "Why it matters", "Source", "Severity"], flags)}

<h2>Unverified values, listed explicitly</h2>
<ul class="clean">
<li>Every market price: no official source exists. <span class="blank">unverified by definition</span>.</li>
<li>{t['officialStatusCounts']['blank']} game-status cells in the 2026 week-10 injury tracker:
<span class="blank">blank on the official page</span>.</li>
<li>All 2026 player-level season totals in the archive: <span class="blank">not checked</span> (see F21).</li>
<li>Every depth-chart tier: <span class="blank">computed, not official</span> (see F04).</li>
<li>Every player-prop line: <span class="blank">does not exist</span> (see F08).</li>
</ul>
"""
    return page("flagged.html", "Flagged for review", body, "Every flaw, irregularity and unverified value, with sources.")


def render_method():
    body = """
<p class="eyebrow">Method · definitions · gates</p>
<h1>Method</h1>
<p class="lede">The rules this lab follows, so that every number can be audited or attacked.</p>

<h2>The seven honesty rules</h2>
<ol>
<li><strong>No invented value.</strong> If an official source has not published it, the cell is blank and the
row is on <a href="flagged.html">Flagged</a>.</li>
<li><strong>Every row carries a source.</strong> Official where one exists; MIRROR where a documented public
mirror was used; MODEL where the lab computed it; NOT OFFICIAL where no source can exist (market prices).</li>
<li><strong>Walk-forward only.</strong> A model for a game may use only games that kicked off before it. No
random splits, no future information.</li>
<li><strong>No point estimate without an interval.</strong> Whole weeks are resampled, because games in a week
share conditions.</li>
<li><strong>Correct for the family.</strong> Every p-value is multiplied by the number of strategies tested.</li>
<li><strong>Blocked is not zero.</strong> A strategy with no data shows BLOCKED and a blank profit. Zero would
imply it was tested and lost.</li>
<li><strong>No reward without a prospective trial.</strong> Backtest evidence can never promote a strategy on
its own.</li>
</ol>

<h2>Definitions</h2>
<h3>Signal</h3>
<p>1 − (Brier score ÷ Brier score of always predicting the base rate). Zero means the forecast carries no
information; 1 would be perfect. It is computed on the same games for the model and the market, so the two are
comparable.</p>
<h3>De-vigged probability</h3>
<p>The implied probabilities of both sides of a price are normalised so they sum to one, removing the book's
margin. Without this, any comparison against the market would be biased in the model's favour.</p>
<h3>phi (φ)</h3>
<p>The Pearson correlation of two 0/1 outcomes. It describes dependence; it is not a pricing formula. Pricing
uses the observed joint probability.</p>
<h3>Fair price</h3>
<p>The reciprocal of the model probability, expressed as American odds. It is the price at which the model
thinks the bet is a coin flip — hold-free, and therefore never an offer you can take.</p>
<h3>Computed tier</h3>
<p>Rank by the previous full season's production within the same club and position group. A player with no
production record gets a blank tier. This is <em>not</em> an official depth chart.</p>

<h2>One correction worth reading</h2>
<p>An earlier build of this lab tested luck with a pooled break-even win rate: it assumed every bet needed the
same win probability, taken as the average implied by the prices. That is wrong whenever prices differ. A win on a
+900 long shot and a win on a -300 favourite count equally in a win count but not in the profit, so the test can
declare significance that the money does not support.</p>
<p>The test was replaced with a per-bet null: each bet's true win probability is the de-vigged closing market
probability of the side taken, which is the sharpest honest benchmark. The three-leg parlay moved from
p = 0.0005 to p = 0.218. Both the old and new numbers are recorded here rather than quietly overwritten — the
correction is part of the evidence.</p>

<h2>The eight validation gates</h2>
<ol>
<li><strong>Provenance</strong> — every input is in the source registry with an access route.</li>
<li><strong>Coverage</strong> — the strategy produced priced, graded bets.</li>
<li><strong>Baseline</strong> — the comparison is the de-vigged closing price, not a naive guess.</li>
<li><strong>Leakage</strong> — every input predates kickoff.</li>
<li><strong>Out-of-sample size</strong> — at least 300 graded bets, pre-declared.</li>
<li><strong>Robustness</strong> — positive in at least half of the seasons.</li>
<li><strong>Prospective trial</strong> — frozen version, predictions logged before outcomes.</li>
<li><strong>Release review</strong> — human sign-off. Never automated.</li>
</ol>
<p>Gates 7 and 8 cannot be self-certified by this lab, which is why nothing is reward-eligible.</p>

<h2>Reproduce it</h2>
<pre>python3 scripts/nfl_lines/stage1_official.py     # official captures
python3 scripts/nfl_lines/stage2_validate.py     # archive vs official
python3 scripts/nfl_lines/stage3_engine.py       # strategies, gates, leaderboard
python3 scripts/nfl_lines/stage4_correlation.py  # measured correlations
python3 scripts/nfl_lines/stage5_injuries.py     # tracker + impact
python3 scripts/nfl_lines/stage6_lines.py        # week-11 fair lines
python3 scripts/nfl_lines/stage7_decision.py     # questions + suggestions
python3 scripts/nfl_lines/sources.py             # source registry
python3 scripts/nfl_lines/stage8_site.py         # this site
python3 scripts/nfl_lines/verify.py              # build the verification report</pre>
<p class="small">The random seed is fixed, so re-running produces byte-identical numbers unless an input file
changes.</p>
"""
    return page("method.html", "Method", body, "Method, definitions, validation gates and rebuild instructions.")


CSS = """
:root{--ok:#3ddc97;--no:#ff7a6b}
.eyebrow{text-transform:uppercase;letter-spacing:1.4px;font-size:12px;color:var(--muted);font-weight:700;margin:0}
.b{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:.4px;border:1px solid var(--line);background:#0d1728;color:var(--muted);white-space:nowrap}
.b.official{background:#123024;color:#8ff0c2;border-color:#1e5c42}
.b.mirror{background:#1b2a4a;color:#a8c4ff;border-color:#2c4470}
.b.model{background:#2a2340;color:#cbb6ff;border-color:#453a66}
.b.notofficial{background:#3a2410;color:#ffc08a;border-color:#6a4020}
.b.blocked{background:#3a1512;color:#ffb0a6;border-color:#6a2a24}
.b.proposed{background:#12293a;color:#9fd8ff;border-color:#1f4a63}
.b.done{background:#123024;color:#8ff0c2;border-color:#1e5c42}
.b.watch{background:#3a3210;color:#ffe08a;border-color:#6a5c20}
.b.pass{background:#1a1f2e;color:#9aa9c2}
.b.unverified{background:#3a2410;color:#ffc08a;border-color:#6a4020}
.b.awaiting{background:#3a1a34;color:#ffb0e6;border-color:#6a3058}
.b.answered{background:#123024;color:#8ff0c2;border-color:#1e5c42}
.b.partial{background:#2a2a10;color:#e8e08a;border-color:#5a5a20}
.b.answeredno{background:#2a1a1a;color:#ffb0a6;border-color:#5a2a2a}
.b.high{background:#3a1512;color:#ffb0a6}
.b.medium{background:#3a3210;color:#ffe08a}
.b.low{background:#1a1f2e;color:#9aa9c2}
.blank{color:#6f7f99;font-style:italic}
.ok{color:var(--ok);font-weight:700}
.no{color:var(--no);font-weight:700}
table td,table th{font-size:13px}
.scroll{max-height:none}
ul.gates{list-style:none;margin:8px 0 0;padding:0;font-size:13px}
ul.gates li{padding:3px 0;border-bottom:1px dashed #1b2740}
pre{background:#0d1728;border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;font-size:12.5px;color:#b9c9e2}
.card .kpi{font-size:28px}
h1{font-size:clamp(24px,3.4vw,34px)}
"""


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "lab.css").write_text(CSS, encoding="utf-8")
    pages = {
        "index.html": render_index,
        "lines.html": render_lines,
        "leaderboard.html": render_leaderboard,
        "backtest.html": render_backtest,
        "correlation.html": render_correlation,
        "injuries.html": render_injuries,
        "questions.html": render_questions,
        "suggestions.html": render_suggestions,
        "sources.html": render_sources,
        "flagged.html": render_flagged,
        "method.html": render_method,
    }
    for name, fn in pages.items():
        (SITE / name).write_text(fn(), encoding="utf-8")

    # one additive nav link on the existing root pages (idempotent)
    link = '<a href="nfl-lines/index.html">NFL lines lab</a>'
    touched = []
    for p in sorted(ROOT.glob("*.html")):
        txt = p.read_text(encoding="utf-8")
        if link in txt:
            continue
        if "</nav>" in txt:
            p.write_text(txt.replace("</nav>", link + "</nav>", 1), encoding="utf-8")
            touched.append(p.name)
    print(f"pages written: {len(pages)}; root nav updated on: {touched if touched else 'already present'}")


if __name__ == "__main__":
    main()
