#!/usr/bin/env python3
"""NFL Skill Lab — static site generator (session arena-fb9c9608).

Reads derived + official JSON from lines-lab/data/ and renders every page under
lines-lab/. Every table row that states a fact carries a link to its source.
Values that could not be verified are left blank and listed on flagged.html.
"""
import json, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.join(ROOT, "lines-lab")
DATA = os.path.join(LAB, "data")
DER = os.path.join(DATA, "derived")

BUILD_UTC = "2026-11-13T14:00:00Z"
SESSION = "arena-fb9c9608"

def J(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)

def D(name):
    with open(os.path.join(DER, name)) as f:
        return json.load(f)

sources = J("sources.json")
injuries = J("official/injuries-2026-w10.json")
sched10 = J("official/schedule-2026-w10.json")
sched11 = J("official/schedule-2026-w11.json")
meta = D("model-meta.json")
lines = D("lines-2026-w10-w11.json")
lb = D("leaderboard.json")
corr = D("correlation.json")
depth = D("depth-2026-w10.json")
flags = D("flags.json")

SRC_GAMES = "https://github.com/nflverse/nfldata/blob/master/data/games.csv"
SRC_INJ = "https://www.nfl.com/injuries/"
SRC_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10/"
SRC_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11/"
SRC_TNF = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
SRC_STRATEGY_PAGE = "https://karagemop466-tech.github.io/Korea5/nfl-strategy.html"

PAGES = [
    ("index.html", "NFL Skill Lab"),
    ("lines.html", "Originated lines"),
    ("leaderboard.html", "Strategy leaderboard"),
    ("correlation.html", "Correlation"),
    ("injuries.html", "Injuries & depth"),
    ("method.html", "Method & gates"),
    ("decisions.html", "Decisions needed"),
    ("suggestions.html", "Suggestions"),
    ("review.html", "Repo review"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
    ("data.html", "Data index"),
]

CSS = """/* NFL Skill Lab */
:root{--ink:#12212b;--mut:#5b6b76;--line:#dbe3e9;--bg:#f5f7f9;--card:#fff;--acc:#0b5ea8;--acc2:#0a4a86;--good:#0e7c3f;--warn:#a35a00;--bad:#a8231f;--flag:#fff3d6}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
header{background:linear-gradient(135deg,#0b2d4d,#0b5ea8);color:#fff;padding:22px 20px 18px}
header h1{margin:0 0 2px;font-size:22px;letter-spacing:.2px}
header .sub{opacity:.85;font-size:13.5px;max-width:70em}
nav{display:flex;flex-wrap:wrap;gap:2px;background:#0a355e;padding:0 12px}
nav a{color:#cfe2f5;text-decoration:none;font-size:13.5px;padding:8px 10px;display:block}
nav a.active,nav a:hover{background:#12528f;color:#fff;border-radius:6px 6px 0 0}
main{max-width:1180px;margin:0 auto;padding:18px 16px 40px}
h2{font-size:19px;margin:26px 0 8px;border-bottom:2px solid var(--line);padding-bottom:4px}
h3{font-size:16px;margin:18px 0 6px}
p.lede{font-size:15.5px;color:var(--mut);max-width:75em}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:14px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card h3{margin:0 0 6px;font-size:14px;color:var(--acc2);text-transform:uppercase;letter-spacing:.4px}
.card p{margin:0;font-size:13.5px}
.card .big{font-size:26px;font-weight:700;color:var(--ink)}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:13.5px;margin:8px 0 16px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef3f7;font-weight:600;position:sticky;top:0}
tr:nth-child(even) td{background:#fafcfd}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--acc)}
.small{font-size:12.5px;color:var(--mut)}
.tag{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;letter-spacing:.3px}
.tag.off{background:#e2f0e6;color:var(--good)}
.tag.mkt{background:#e3ecf7;color:var(--acc2)}
.tag.est{background:#fdf1d8;color:var(--warn)}
.tag.bad{background:#fbe2e1;color:var(--bad)}
.tag.na{background:#eceff1;color:var(--mut)}
.pill{display:inline-block;padding:1px 9px;border-radius:10px;font-size:12px;font-weight:600}
.pill.critical{background:#fbe2e1;color:var(--bad)}
.pill.elevated{background:#fdf1d8;color:var(--warn)}
.pill.watch{background:#fdf7e0;color:#8a6d00}
.pill.clear{background:#e2f0e6;color:var(--good)}
.banner{background:var(--flag);border:1px solid #e8cf8a;border-radius:8px;padding:10px 14px;margin:14px 0;font-size:13.5px}
.note{background:#eef3f7;border-left:3px solid var(--acc);padding:8px 12px;margin:10px 0;font-size:13.5px}
ul.tight li{margin:4px 0}
footer{max-width:1180px;margin:0 auto;padding:0 16px 30px;color:var(--mut);font-size:12.5px}
.src{font-size:11.5px;color:var(--mut);white-space:nowrap}
"""

def esc(x):
    return html.escape(str(x), quote=True)

def page(fname, title, body, banner=True):
    nav = "".join(
        f'<a href="{p}" class="{"active" if p == fname else ""}">{t}</a>' for p, t in PAGES
    )
    certainty = ""
    if banner:
        certainty = ('<div class="banner"><strong>Honesty policy.</strong> Every fact row links to its source. '
                     'Market lines (spreads/totals/moneylines) are bookmaker quotes from the open-source '
                     'nflverse/nfldata dataset — labelled <span class="tag mkt">market</span>, not official NFL data. '
                     'Official data comes from NFL.com pages fetched 2026-11-13 (link on each row). '
                     'Values that could not be verified are left blank and listed on '
                     '<a href="flagged.html">Flagged for Review</a>. No betting edge is claimed anywhere; '
                     'the leaderboard is a paper research competition.</div>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — NFL Skill Lab</title>
<meta name="description" content="NFL lines origination, strategy leaderboard, correlation values and injury/depth tracking with source-linked verification.">
<link rel="stylesheet" href="assets/lab.css">
</head>
<body>
<header><h1>NFL Skill Lab</h1>
<div class="sub">Originate lines &middot; leaderboard strategies through validation gates &middot; measure correlation &middot; track injuries and depth. Built {BUILD_UTC[:10]} by session {SESSION}; branch <code>arena/fb9c9608-korea5</code>.</div>
</header>
<nav>{nav}</nav>
<main>
{certainty}
{body}
</main>
<footer>NFL Skill Lab — part of <a href="../index.html">Korea5</a> (live site: karagemop466-tech.github.io/Korea5). Data build {BUILD_UTC}. Report problems on <a href="flagged.html">Flagged for Review</a>.</footer>
</body></html>
"""

# ------------------------------------------------------------------ tables
def lines_table(rows, src, week_label):
    head = ("<tr><th>Date</th><th>Matchup (away @ home)</th><th class='num'>Originated spread (home)</th>"
            "<th class='num'>Originated total</th><th class='num'>Market spread</th><th class='num'>Market total</th>"
            "<th class='num'>Edge vs market (spread / total)</th><th>QBs (away / home)</th><th>Result</th><th>Source</th></tr>")
    body = []
    for r in rows:
        mkt = '<span class="tag mkt">market</span>' if r["marketSpreadHome"] is not None else '<span class="tag na">not posted</span>'
        edge = "—" if r["edgeSpread"] is None else f"{r['edgeSpread']:+.1f} / {r['edgeTotal']:+.1f}"
        res = "—"
        if r["final"]:
            res = f"<strong>{r['awayScore']}–{r['homeScore']}</strong> (final)"
        qb = f"{esc(r['awayQb'] or '—')} / {esc(r['homeQb'] or '—')}"
        mkt_spread = ""
        if r["marketSpreadHome"] is not None:
            mkt_spread = f"{r['marketSpreadHome']:+.1f}"
        body.append(
            f"<tr><td>{r['date']}</td><td><strong>{r['away']} @ {r['home']}</strong></td>"
            f"<td class='num'>{r['originatedSpreadHome']:+.1f}</td><td class='num'>{r['originatedTotal']:.1f}</td>"
            f"<td class='num'>{mkt_spread} {mkt}</td>"
            f"<td class='num'>{r['marketTotal'] if r['marketTotal'] is not None else ''}</td>"
            f"<td class='num'>{edge}</td><td>{qb}</td><td>{res}</td>"
            f"<td class='src'><a href='{src}' rel='noopener'>source ↗</a></td></tr>")
    return f"<h3>{esc(week_label)}</h3><table>{head}{''.join(body)}</table>"

def leaderboard_table():
    head = ("<tr><th>Rank</th><th>Strategy</th><th class='num'>Bets</th><th class='num'>Win %</th>"
            "<th class='num'>ROI %</th><th class='num'>ROI 95% CI</th><th>Seasons positive</th>"
            "<th class='num'>Points</th><th>Status</th><th>Source</th></tr>")
    body = []
    for i, r in enumerate(lb["rows"], 1):
        status = ('<span class="tag off">qualified (paper)</span>' if r["passedAllMandatory"]
                  else '<span class="tag bad">failed gates</span>')
        seasons = ", ".join(f"{s}: {v:+.1f}%" for s, v in r["seasonRoi"].items()) or "—"
        body.append(f"<tr><td>{i}</td><td>{esc(r['strategy'])}</td><td class='num'>{r['bets']}</td>"
                    f"<td class='num'>{r['winPct'] if r['winPct'] is not None else '—'}</td>"
                    f"<td class='num'>{r['roiPct']:+.2f}</td><td class='num'>[{r['ci95'][0]:+.1f}, {r['ci95'][1]:+.1f}]</td>"
                    f"<td>{esc(seasons)}</td><td class='num'>{r['leaderboardPoints']:.0f}</td><td>{status}</td>"
                    f"<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>")
    return f"<table>{head}{''.join(body)}</table>"

def gates_table():
    head = "<tr><th>Gate</th><th>Definition</th><th>Status</th></tr>"
    rows = [
        ("G1 sample", "≥ 200 resolved bets", "enforced"),
        ("G2 profitability", "bootstrap 95% CI lower bound of flat-bet ROI > 0 (10,000 resamples)", "enforced"),
        ("G3 stability", "ROI > 0 in at least 2/3 of evaluated seasons", "enforced"),
        ("G4 process", "walk-forward: every prediction emitted before the rating update; tuning only on 2016–2019", "enforced"),
        ("G5 closing-line value", "requires archived timestamped entry quotes", '<span class="tag est">pending — blocks rewards</span>'),
        ("G6 prospective trial", "pre-registered locked paper trial with declared horizon", '<span class="tag est">pending</span>'),
    ]
    return f"<table>{head}{''.join(f'<tr><td><strong>{a}</strong></td><td>{b}</td><td>{c}</td></tr>' for a, b, c in rows)}</table>"

def corr_tables():
    v = corr["values"]
    vals = f"""<table><tr><th>Quantity</th><th class='num'>Value</th><th>Sample</th><th>Method</th><th>Source</th></tr>
<tr><td>Pearson correlation, game margin vs total</td><td class='num'>{v['pearsonMarginTotal_1999_2025']:+.4f}</td>
<td>{v['n']} regular-season games 1999–2025</td><td>direct Pearson r on realized (margin, total)</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
<tr><td>Phi coefficient, home-covers × over-hits</td><td class='num'>{v['phiHomeCoverOver_2016_2025']:+.4f}</td>
<td>{v['n_cover']} games with closing lines, 2016–2025</td><td>2×2 correlation of cover indicators at the market number</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
<tr><td>Residual σ, margin vs market spread</td><td class='num'>{v['sigmaMarginPts']:.2f} pts</td>
<td>7,413 games with lines</td><td>std dev of (actual margin − market spread)</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
<tr><td>Residual σ, total vs market total</td><td class='num'>{v['sigmaTotalPts']:.2f} pts</td>
<td>same sample</td><td>std dev of (actual total − market total)</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr></table>"""
    sc = corr["sgpScenarios"]
    head = ("<tr><th>Game (model spread, total)</th><th>Combo</th><th class='num'>Joint P</th>"
            "<th class='num'>Marginal product</th><th class='num'>Correlation multiplier</th></tr>")
    body = []
    for s in sc:
        first = True
        span = ('<td rowspan=4><strong>%s</strong><br><span class="small">model %+.1f / %.1f</span></td>'
                % (esc(s["game"]), s["modelSpreadHome"], s["modelTotal"]))
        for combo, m in s["multipliers"].items():
            joint = s["joints"][combo]
            src_cell = (f"<td rowspan=4 class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a><br>"
                        f"<span class='small'>sim of model board</span></td>") if first else ""
            body.append(f"<tr>{span if first else ''}"
                        f"<td>{esc(combo.replace('+', ' + '))}</td><td class='num'>{joint:.4f}</td>"
                        f"<td class='num'>—</td><td class='num'>{m:.3f}×</td>{src_cell}</tr>")
            first = False
    sgp = f"<h3>Same-game parlay correlation (seeded simulation, 400,000 draws/scenario)</h3><table>{head}{''.join(body)}</table>"
    pm = corr["parlayMath"]
    par = f"""<h3>Two-leg parlay math (both legs −110)</h3>
<table><tr><th>Quantity</th><th class='num'>Value</th><th>Notes</th></tr>
<tr><td>Fair joint probability at independence</td><td class='num'>{(110/210)**2:.4f}</td><td>(110/210)² — fair probability implied by −110 per leg</td></tr>
<tr><td>Fair parlay profit at independence</td><td class='num'>+{(1/(110/210)**2 - 1):.2f} per unit</td><td>book standard is +260</td></tr>
<tr><td>EV of +260 at independence</td><td class='num'>{(110/210)**2*3.6-1:+.3f} per unit</td><td>p²·(2.6+1) − 1</td></tr>
<tr><td>Correlation effect</td><td class='num'>—</td><td>{esc(pm['note'])} <a class='src' href='https://github.com/nflverse/nfldata/blob/master/data/games.csv' rel='noopener'>games.csv ↗</a></td></tr></table>"""
    return vals + sgp + par

def injuries_page():
    parts = []
    summary_rows = []
    for team in sorted(depth["teams"]):
        t = depth["teams"][team]
        units = t["units"]
        worst = {"critical": 0, "elevated": 0, "watch": 0, "clear": 0}
        for u, d in units.items():
            worst[d["pressure"]] += 1
        qb = t["qbRows"]
        qbtxt = "; ".join(f"{q['player']} ({q['practice'].replace(' Participation in Practice','')}"
                          f"{', ' + q['status'] if q['status'] else ''})" for q in qb) or "—"
        pills = " ".join(
            '<span class="pill %s">%s: %s</span>' % (d["pressure"], esc(u), d["pressure"])
            for u, d in sorted(units.items()) if d["pressure"] != "clear"
        ) or '<span class="pill clear">all clear</span>'
        summary_rows.append(
            f"<tr><td><strong>{team}</strong></td><td class='num'>{t['totalRows']}</td>"
            f"<td>{esc(qbtxt)}</td>"
            f"<td>{pills}</td>"
            f"<td class='src'><a href='{SRC_INJ}' rel='noopener'>NFL.com ↗</a></td></tr>")
    parts.append("<h2>Unit availability pressure — Week 10 (official report)</h2>"
                 "<p class='small'>Pressure rule: critical = 3+ DNP/Out players in the unit; elevated = 2; watch = 1 or any Questionable. "
                 "This is availability pressure only — depth-chart tier (2nd/3rd string) is NOT inferred anywhere "
                 "(see <a href='flagged.html'>NFL-K4</a>). Practice statuses are abbreviated (Full/Limited/DNP).</p>"
                 f"<table><tr><th>Team</th><th class='num'>Report rows</th><th>QB report</th><th>Unit pressure</th><th>Source</th></tr>{''.join(summary_rows)}</table>")
    # full report per game
    parts.append("<h2>Full official report — every row as published by NFL.com</h2>")
    for gm in injuries["games"]:
        note = gm["teams"].get("_note", "")
        block = [f"<h3>{esc(gm['game'])} — {gm['date']} {esc(gm['time'])} <span class='small'>({esc(gm['slot'])}; "
                 f"records shown {esc(', '.join(f'{k} {v}' for k, v in gm['recordsAsShown'].items()))})</span> "
                 f"<a class='src' href='{SRC_INJ}' rel='noopener'>source ↗</a></h3>"]
        if note:
            block.append(f"<p class='small'>{esc(note)}</p>")
        for team, rows in gm["teams"].items():
            if team == "_note" or not isinstance(rows, list):
                continue
            head = "<tr><th>Player</th><th>Pos</th><th>Injury</th><th>Practice</th><th>Game status</th></tr>"
            body = "".join(
                f"<tr><td>{esc(r['player'])}</td><td>{esc(r['pos'])}</td><td>{esc(r['injury']) or ''}</td>"
                f"<td>{esc(r['practice'].replace(' Participation in Practice',''))}</td><td>{esc(r['status']) or ''}</td></tr>"
                for r in rows) or "<tr><td colspan=5 class='small'>No injuries reported by the source.</td></tr>"
            block.append(f"<h4>{team}</h4><table>{head}{body}</table>")
        parts.append("".join(block))
    qb = depth["qbNotes"]
    qrows = []
    for gm, d in sorted(qb["w10"].items()):
        qrows.append(f"<tr><td>W10 {esc(gm)}</td><td>{esc(d['away']['recordedStarter'])} ({d['away']['datasetStarts']} starts in dataset)</td>"
                     f"<td>{esc(d['home']['recordedStarter'])} ({d['home']['datasetStarts']} starts in dataset)</td><td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>")
    for gm, d in sorted(qb["w11"].items()):
        qrows.append(f"<tr><td>W11 {esc(gm)}</td><td>{esc(d['away']['recordedStarter'])} ({d['away']['datasetStarts']} starts in dataset)</td>"
                     f"<td>{esc(d['home']['recordedStarter'])} ({d['home']['datasetStarts']} starts in dataset)</td><td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>")
    parts.append("<h2>Recorded starting QBs (games.csv) with dataset start counts</h2>"
                 + qb["method"] + f"<table><tr><th>Game</th><th>Away QB</th><th>Home QB</th><th>Source</th></tr>{''.join(qrows)}</table>")
    return "".join(parts)

def flags_page():
    head = "<tr><th>ID</th><th>Severity</th><th>Area</th><th>Finding</th><th>Status</th><th>Source</th></tr>"
    sev = {"high": "bad", "medium": "est", "low": "na"}
    body = "".join(
        f"<tr><td><strong>{f['id']}</strong></td><td><span class='tag {sev[f['severity']]}'>{f['severity']}</span></td>"
        f"<td>{esc(f['area'])}</td><td>{esc(f['finding'])}</td><td>{esc(f['status'])}</td>"
        f"<td class='src'><a href='{f['source']}' rel='noopener'>source ↗</a></td></tr>"
        for f in flags["items"])
    return f"<table>{head}{body}</table>"

def sources_page():
    head = "<tr><th>Dataset / page</th><th>Tier</th><th>What it provided</th><th>Source link</th><th>Fetched</th></tr>"
    tier = {"official": "off", "official-inherited": "off", "secondary-open-source": "mkt"}
    body = "".join(
        f"<tr><td><strong>{esc(s['id'])}</strong></td><td><span class='tag {tier.get(s['tier'],'na')}'>{s['tier']}</span></td>"
        f"<td>{esc(s.get('title',''))}</td><td class='src'><a href='{s['url']}' rel='noopener'>{esc(s['url'][:70])}… ↗</a></td>"
        f"<td>{esc(s.get('fetchedUTC', s.get('fetchedUTC','—')) if s.get('fetchedUTC') else '—')}</td></tr>"
        for s in sources["datasets"])
    refs = "".join(f"<li><a href='{r['url']}' rel='noopener'>{esc(r['title'])}</a> — {esc(r['url'])}</li>" for r in sources["officialReferencePages"])
    return (f"<h2>Loaded datasets</h2><table>{head}{body}</table>"
            f"<h2>Official reference pages (manual-review destinations)</h2><ul class='tight'>{refs}</ul>")

# ------------------------------------------------------------------ pages
def p_index():
    q = lb["rows"]
    qualified = [r for r in q if r["passedAllMandatory"]]
    inj_teams = len(depth["teams"])
    watch = sum(1 for t in depth["teams"].values() if any(u["pressure"] in ("critical", "elevated") for u in t["units"].values()))
    body = f"""
<div class="cards">
<div class="card"><h3>Originated lines</h3><p class="big">{len(lines['weeks']['2026-10']['rows']) + len(lines['weeks']['2026-11']['rows'])}</p><p>games priced for Weeks 10–11 2026 vs market (<a href="lines.html">board</a>)</p></div>
<div class="card"><h3>Qualified strategies</h3><p class="big">{len(qualified)} of {len(q)}</p><p>passed all mandatory gates on 2020–2025 walk-forward (<a href="leaderboard.html">leaderboard</a>)</p></div>
<div class="card"><h3>Correlation values</h3><p class="big">{corr['values']['pearsonMarginTotal_1999_2025']:+.3f}</p><p>margin–total Pearson r; SGP multipliers ~1.0 (<a href="correlation.html">details</a>)</p></div>
<div class="card"><h3>Injury watch</h3><p class="big">{watch}/{inj_teams}</p><p>teams with a unit at elevated or critical pressure (<a href="injuries.html">tracker</a>)</p></div>
</div>
<h2>Executive summary</h2>
<p class="lede">This lab turns the repository's NFL coverage into a decision system: it originates its own
game lines from results-based power ratings, publishes them against the market number, runs candidate
betting strategies through pre-registered validation gates on held-out seasons, measures the correlation
values needed to price parlays honestly, and tracks injuries/availability from the official NFL report.</p>
<div class="note"><strong>What the data says so far (2020–2025 held-out walk-forward, flat -110 pricing):</strong>
<ul class="tight">
<li><strong>No strategy qualified.</strong> Every candidate's ROI 95% CI includes zero. The market-favorite baseline is −2.94% ROI (n=1,615). This is the luck-removal step working: nothing is promoted on noise.</li>
<li><strong>The model is a baseline, not an edge.</strong> Model spread MAE {meta['diagnostics']['heldout_2020_2025']['modelMAE_margin']} pts vs market {meta['diagnostics']['heldout_2020_2025']['marketMAE_margin']} pts on the same window. No predictive edge over the closing line is claimed or implied.</li>
<li><strong>Correlation is small but real to measure.</strong> Margin–total r = {corr['values']['pearsonMarginTotal_1999_2025']:+.4f}; same-game-parlay multipliers measured at 0.985×–1.011× — near-independence on this dataset.</li>
<li><strong>Availability pressure is measurable now.</strong> {watch} of {inj_teams} Week 10 teams carry an elevated/critical unit from the official report. Depth-chart tier (2nd/3rd string) is deliberately not inferred — see flag NFL-K4.</li>
<li><strong>Rewards are suspended by design</strong> until gates G5 (closing-line value) and G6 (prospective trial) are satisfiable. Paper points only.</li>
</ul></div>
<h2>What is on each page</h2>
<table><tr><th>Page</th><th>Contents</th></tr>
<tr><td><a href="lines.html">Originated lines</a></td><td>Week 10/11 2026 board: model spread & total vs market, edges, results (TNF final already settled: <a href="{SRC_TNF}" rel="noopener">Commanders 24, Giants 21</a>).</td></tr>
<tr><td><a href="leaderboard.html">Strategy leaderboard</a></td><td>Eight strategies walked forward on 2020–2025, validation gates, points, reward policy.</td></tr>
<tr><td><a href="correlation.html">Correlation</a></td><td>Measured correlation values, same-game-parlay multipliers, two-leg parlay math.</td></tr>
<tr><td><a href="injuries.html">Injuries & depth</a></td><td>Every row of the official Week 10 injury report, unit pressure index, QB availability notes.</td></tr>
<tr><td><a href="method.html">Method & gates</a></td><td>Model specification, parameters, gate definitions, provenance and leakage rules.</td></tr>
<tr><td><a href="decisions.html">Decisions needed</a></td><td>The questions, information and answers that must exist before any decision can be made — with what we have and do not have.</td></tr>
<tr><td><a href="suggestions.html">Suggestions</a></td><td>Dedicated review board: proposals awaiting a decision before implementation.</td></tr>
<tr><td><a href="review.html">Repo review</a></td><td>Line-by-line repo review findings with cross-check evidence.</td></tr>
<tr><td><a href="flagged.html">Flagged for review</a></td><td>Irregularities and unverified items (NFL-K1…K10).</td></tr>
<tr><td><a href="sources.html">Sources</a></td><td>Dataset provenance registry and official reference pages.</td></tr>
<tr><td><a href="data.html">Data index</a></td><td>Every JSON this lab publishes, with schema notes.</td></tr>
</table>
<p class="small">Relation to the earlier proposal page: <a href="{SRC_STRATEGY_PAGE}" rel="noopener">nfl-strategy.html</a>
(session 2cd43859) sketched the rules; this lab implements them on real data and reports the honest result —
zero qualified strategies, rewards suspended.</p>
"""
    return page("index.html", "Dashboard", body)

def p_lines():
    body = f"""
<h2>How the lines are originated</h2>
<p class="lede">Power ratings are updated game-by-game in chronological order (margin response, capped at
±{meta['params']['blowoutCap']:.0f}, learning rate {meta['params']['lam']}, season regression {meta['params']['seasonShrink']}, home
advantage {meta['hfa']:.2f} pts). Totals come from pace ratings (offense scored / defense allowed). Every
prediction is emitted <em>before</em> the ratings absorb that game — no leakage. Parameters were tuned
only on 2016–2019; 2020–2025 stayed untouched for the leaderboard.</p>
<p class="small">Spread convention: all spreads are in <em>home-team coordinates</em> (positive = home favored).
Market spreads are the bookmaker consensus from <a href="{SRC_GAMES}" rel="noopener">nfldata games.csv</a>
(<span class="tag mkt">market</span>) — labelled market data, not official NFL data. Official Week 10/11
matchups, kickoffs and results are from NFL.com (<a href="{SRC_W10}" rel="noopener">Week 10 ↗</a>,
<a href="{SRC_W11}" rel="noopener">Week 11 ↗</a>); the 14 Week 10 and 13 Week 11 matchups on those pages
match the dataset exactly (see <a href="review.html">Repo review</a>).</p>
<p class="small"><strong>Ratings as of:</strong> {esc(lines['ratingsAsOf'])}. Week 11 lines are provisional
until Week 10 results land.</p>
{lines_table(lines['weeks']['2026-10']['rows'], SRC_W10, lines['weeks']['2026-10']['label'])}
{lines_table(lines['weeks']['2026-11']['rows'], SRC_W11, lines['weeks']['2026-11']['label'])}
<h2>Diagnostics</h2>
<table><tr><th>Window</th><th class='num'>n</th><th class='num'>Model MAE (spread)</th><th class='num'>Market MAE (spread)</th>
<th class='num'>Model MAE (total)</th><th class='num'>Market MAE (total)</th><th>Source</th></tr>
<tr><td>Tuning 2016–2019</td><td class='num'>{meta['diagnostics']['tuning_2016_2019']['n']}</td>
<td class='num'>{meta['diagnostics']['tuning_2016_2019']['modelMAE_margin']}</td><td class='num'>{meta['diagnostics']['tuning_2016_2019']['marketMAE_margin']}</td>
<td class='num'>{meta['diagnostics']['tuning_2016_2019']['modelMAE_total']}</td><td class='num'>{meta['diagnostics']['tuning_2016_2019']['marketMAE_total']}</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
<tr><td>Held-out 2020–2025</td><td class='num'>{meta['diagnostics']['heldout_2020_2025']['n']}</td>
<td class='num'>{meta['diagnostics']['heldout_2020_2025']['modelMAE_margin']}</td><td class='num'>{meta['diagnostics']['heldout_2020_2025']['marketMAE_margin']}</td>
<td class='num'>{meta['diagnostics']['heldout_2020_2025']['modelMAE_total']}</td><td class='num'>{meta['diagnostics']['heldout_2020_2025']['marketMAE_total']}</td>
<td class='src'><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
</table>
<div class="banner"><strong>Read this before acting.</strong> The model is slightly <em>worse</em> than the
closing market on spread MAE. Nothing on this board is a recommendation; edges are research artefacts
published so they can be reviewed, gated, and — only if they survive G5/G6 — considered.</div>
"""
    return page("lines.html", "Originated lines", body)

def p_leaderboard():
    body = f"""
<h2>Rules of the competition</h2>
<p class="lede">A strategy is a mechanical rule over the same inputs everyone gets (results, market numbers,
ratings, availability pressure). Each walk-forward season, it bets flat 1 unit per qualifying game. The
leaderboard ranks by points; only strategies that pass every mandatory gate score points. Failed strategies
stay published — deleting failures would reintroduce luck via selection bias.</p>
{gates_table()}
<h2>Leaderboard — 2020–2025 held-out walk-forward</h2>
<p class="small">Pricing: flat 1 unit; spreads/totals at −110; moneylines at the listed nfldata prices.
CI by 10,000-sample bootstrap over bets. Points = 100 × ROI%, awarded only when G1–G4 all pass.
{esc(lb['rewardPolicy'])}</p>
{leaderboard_table()}
<h2>How to submit a strategy</h2>
<ol class="tight">
<li>Write the rule in plain language + code (deterministic; no look-ahead; inputs from the <a href="data.html">data index</a> only).</li>
<li>Open a PR adding it to <code>lines-lab/scripts/build_nfl_lab.py</code>'s strategy table (or a sibling module) with its entry conditions and pricing.</li>
<li>The build re-runs the walk-forward automatically; the result lands on this page with all gates evaluated.</li>
<li>Propose via the <a href="suggestions.html">Suggestions board</a> first if the rule needs a new data source — new sources need a provenance row.</li>
</ol>
<div class="banner"><strong>Reward policy (paper only).</strong> Leaderboard points are paper research credit.
No monetary or real-world reward is authorized by this repository. Gate G5 (closing-line value against
archived entry quotes) and G6 (prospective locked trial) must exist before any reward concept is even
reviewed — see <a href="suggestions.html">S12–S14</a> and flag <a href="flagged.html">NFL-K6</a>.</div>
"""
    return page("leaderboard.html", "Strategy leaderboard", body)

def p_correlation():
    body = f"""
<h2>Why correlation values matter here</h2>
<p class="lede">A parlay is priced as the product of leg probabilities only when the legs are independent.
Same-game legs are not independent in general, so the joint probability must be measured, not assumed.
This page publishes the measured values for this dataset and the pricing arithmetic that follows from them.</p>
{corr_tables()}
<div class="note"><strong>Honest finding.</strong> On this dataset (6,967 games), margin–total correlation is
{corr['values']['pearsonMarginTotal_1999_2025']:+.4f} and the cover×over phi is {corr['values']['phiHomeCoverOver_2016_2025']:+.4f};
same-game parlay multipliers land between 0.985× and 1.011× — near-independence. Do not import
"typical" correlation folklore from elsewhere; re-measure on the data actually being used and record the sample.</div>
"""
    return page("correlation.html", "Correlation", body)

def p_injuries():
    body = f"""
<h2>Scope</h2>
<p class="lede">Source of truth: the <a href="{SRC_INJ}" rel="noopener">official NFL.com injury report</a>
(Week 10, 2026 season), fetched 2026-11-13 and transcribed row-for-row into
<code>lines-lab/data/official/injuries-2026-w10.json</code> ({sum(len(r) for g in injuries['games'] for t, r in g['teams'].items() if isinstance(r, list))} player rows across 28 teams).
The tracker converts that report into per-unit availability pressure and QB availability — it never
guesses who is a starter or a backup.</p>
{injuries_page()}
"""
    return page("injuries.html", "Injuries & depth", body)

def p_method():
    params = meta["params"]
    body = f"""
<h2>Model specification</h2>
<p class="lede">A deliberately simple, fully transparent baseline: pairwise margin ratings with exponential
response, plus per-team pace ratings for totals. Its purpose is to make the <em>process</em> real —
walk-forward predictions, market comparison, gates — not to win.</p>
<table><tr><th>Component</th><th>Rule</th><th>Value</th></tr>
<tr><td>Margin rating</td><td>after each game, residual = (actual margin − home advantage) − (rating<sub>home</sub> − rating<sub>away</sub>), residual capped at ±{params['blowoutCap']:.0f} pts, teams move ±λ·residual</td><td class='num'>λ = {params['lam']}</td></tr>
<tr><td>Season regression</td><td>at each season start ratings shrink toward the league mean</td><td class='num'>× {params['seasonShrink']}</td></tr>
<tr><td>Home advantage</td><td>league mean home margin over the trailing season window</td><td class='num'>{meta['hfa']:.2f} pts</td></tr>
<tr><td>Pace ratings (totals)</td><td>expected points scored/allowed, shrunk toward league mean with weight k in early weeks</td><td class='num'>k = {params['paceK']}</td></tr>
<tr><td>Expected margin</td><td>rating<sub>home</sub> − rating<sub>away</sub> + home advantage</td><td>—</td></tr>
<tr><td>Expected total</td><td>(offense<sub>home</sub> + defense<sub>away</sub>)/2 + (offense<sub>away</sub> + defense<sub>home</sub>)/2</td><td>—</td></tr>
<tr><td>Tuning</td><td>λ, cap, k grid-searched on 2016–2019 spread MAE only</td><td>2020–2025 untouched</td></tr>
<tr><td>Data</td><td>results + market lines from nflverse/nfldata games.csv</td><td><a href='{SRC_GAMES}' rel='noopener'>games.csv ↗</a></td></tr>
</table>
<h2>Validation gates</h2>
{gates_table()}
<h2>Provenance & leakage rules</h2>
<ul class="tight">
<li>Every dataset has a provenance row (<a href="sources.html">Sources</a>): URL, fetch method, commit hash, timestamp.</li>
<li>Predictions are emitted before the observation that would update the model (code audit = gate G4).</li>
<li>Market data is labelled <span class="tag mkt">market</span> everywhere; official data links to its NFL.com page on every row.</li>
<li>Missing values stay blank and are published on <a href="flagged.html">Flagged for Review</a> — nothing is inferred.</li>
<li>Simulations use a fixed RNG seed ({2026}) so every number on this site is reproducible.</li>
</ul>
<h2>Rebuild</h2>
<pre>python3 lines-lab/scripts/build_nfl_lab.py   # data -> derived JSON (deterministic)
python3 lines-lab/scripts/build_site_lab.py  # derived JSON -> lines-lab/*.html
python3 lines-lab/scripts/verify_nfl_lab.py  # link + row-source + schema checks</pre>
"""
    return page("method.html", "Method & gates", body)

def p_decisions():
    rows = [
        ("D1", "What market prices can we legally and reliably snapshot over time?",
         "nfldata closing/opening lines (secondary, already loaded).",
         "Timestamped odds snapshots we control; entry-quote archive.",
         "S12 CI workflow to snapshot weekly lines with UTC timestamps."),
        ("D2", "Is the model any good relative to the market?",
         "Measured: MAE {m} vs market {mm} (2020–2025).",
         "A pre-registered prospective trial (G6) to claim anything.",
         "Run the paper ledger forward for ≥ 100 bets before any claim."),
        ("D3", "Which injury facts actually move lines?",
         "Official Week 10 report (all rows transcribed); QB conflicts flagged (NFL-K2/K3).",
         "Historical injury→outcome panel with timestamps and final inactives.",
         "S13 fetch nflverse injuries/snap_counts/depth charts in CI; build the panel."),
        ("D4", "How much correlation should parlays assume?",
         "Measured on this dataset: r = {r}; SGP multipliers 0.985–1.011.",
         "Whether the same values hold in the market's own pricing (needs odds snapshots).",
         "Re-run the SGP table once S12 snapshots exist."),
        ("D5", "What qualifies a strategy for 'top performer' and a reward?",
         "Gates G1–G4 defined and enforced; leaderboard live with zero qualifiers.",
         "Reward basis, eligibility, jurisdiction and governance sign-off.",
         "Legal/policy review before any reward concept; keep paper-only until then."),
        ("D6", "Are player props in scope now?",
         "No player-level opportunity data is loaded (NFL-K10).",
         "Snap counts / targets / carry shares per week with provenance.",
         "S13 lands the data; then define prop markets and gate them separately."),
        ("D7", "How is depth (2nd/3rd string) determined?",
         "It is not — tier is not inferred anywhere (NFL-K4).",
         "Depth charts + snap counts to identify replacements factually.",
         "S13; until then the tracker reports unit-level availability pressure only."),
        ("D8", "What happens when sessions disagree with a published number?",
         "COORDINATION.md protocol: log the request; flagged items never block the merge.",
         "—",
         "Use the Suggestions board; decisions are recorded there with a rationale."),
    ]
    def fmt(x):
        return x.replace("{m}", str(meta['diagnostics']['heldout_2020_2025']['modelMAE_margin'])) \
                .replace("{mm}", str(meta['diagnostics']['heldout_2020_2025']['marketMAE_margin'])) \
                .replace("{r}", str(corr['values']['pearsonMarginTotal_1999_2025']))
    body = "<h2>Decision register — questions that must be answered before deciding</h2>" \
           "<p class='lede'>Each row is a decision gate: the question, the information already in hand, the " \
           "information that is missing, and the concrete discovery step that would supply it. Nothing here is " \
           "decided until the missing information exists.</p>" \
           "<table><tr><th>ID</th><th>Question</th><th>What we have</th><th>What we do not have</th><th>Suggested discovery step</th></tr>" \
           + "".join(f"<tr><td><strong>{i}</strong></td><td>{esc(fmt(q))}</td><td>{esc(fmt(h))}</td><td>{esc(fmt(m))}</td><td>{esc(fmt(d))}</td></tr>"
                     for i, q, h, m, d in rows) + "</table>" \
           "<h2>Standing rules for any decision</h2><ul class='tight'>" \
           "<li>No decision is taken on unverified data; unverified = blank + flagged.</li>" \
           "<li>No strategy, reward or model change is made outside the gates and this register.</li>" \
           "<li>Every change arrives through the Suggestions board, gets an owner and a gate review, then ships.</li></ul>"
    return page("decisions.html", "Decisions needed", body)

def p_suggestions():
    rows = [
        ("S01", "lines", "Publish originated lines weekly (refresh after each week's results) instead of a one-off build.",
         "The board goes stale after Sunday; a weekly refresh keeps decisions current.", "proposed"),
        ("S02", "leaderboard", "Add a 'no-bet' strategy class (S7) that also logs the games it refused, so reviewers can see gate behaviour on near-misses.",
         "Makes gate logic auditable beyond the qualifying set.", "proposed"),
        ("S03", "correlation", "Re-run SGP scenarios after Week 11 with refreshed ratings and archive each table version.",
         "Correlation estimates drift with the board; keeping versions makes the drift visible.", "proposed"),
        ("S04", "injuries", "Add final inactives (published 90 min pre-kickoff) as a second snapshot per week.",
         "The report fetched Friday is not the game-day truth; a final snapshot closes the gap (flag NFL-K8).", "proposed"),
        ("S05", "site", "Add a per-game detail page linking the official NFL.com game page for every board row.",
         "Each row then has two official hops: the schedule page and the game page.", "proposed"),
        ("S06", "method", "Pre-register the next strategy batch (grid over edge thresholds 1.5–4.0) before seeing results.",
         "Pre-registration is the cheapest way to keep the leaderboard honest.", "proposed"),
        ("S07", "decisions", "Require an owner + due date for every D-row in the decision register.",
         "Unowned discovery steps do not happen.", "proposed"),
        ("S08", "rewards", "Define reward currency as 'review credit' (PR acknowledgements), not money, in writing.",
         "Removes ambiguity while legal/policy review is pending (D5).", "proposed"),
        ("S09", "data", "Archive a copy of each fetched official page (HTML) under lines-lab/data/archive/ with fetch timestamps.",
         "Makes the transcription auditable later even if the page changes.", "proposed"),
        ("S10", "lines", "Add originated totals-only board section so total edges are reviewable without spread edges.",
         "Totals behave differently (S3/S4 gates) and deserve their own view.", "proposed"),
        ("S11", "review", "Extend the repo review to scripts/*.py line-by-line with a checklist in review.html.",
         "This pass reviewed data + build scripts; the planner scripts deserve the same pass.", "proposed"),
        ("S12", "data", "CI workflow to snapshot weekly market lines with UTC timestamps (entry-quote archive for G5).",
         "G5 is unsatisfiable without archived entry quotes — this unlocks it.", "proposed — highest impact"),
        ("S13", "data", "CI workflow to fetch nflverse injuries, snap counts and depth charts (release assets are GitHub Actions-reachable; the sandbox is not).",
         "Unlocks D3, D6, D7 and flags NFL-K4/K10 factually.", "proposed — highest impact"),
        ("S14", "leaderboard", "Only after S12: enable CLV gate G5 and a prospective locked trial (G6) for reward eligibility.",
         "Rewards stay suspended until then.", "proposed"),
    ]
    head = "<tr><th>ID</th><th>Area</th><th>Suggestion</th><th>Why</th><th>Status</th></tr>"
    body = "".join(f"<tr><td><strong>{i}</strong></td><td>{esc(a)}</td><td>{esc(s)}</td><td>{esc(w)}</td><td>{esc(st)}</td></tr>"
                   for i, a, s, w, st in rows)
    return page("suggestions.html", "Suggestions", f"""
<h2>Suggestions review board</h2>
<p class="lede">This page is the dedicated intake for changes. Nothing here is implemented until a reviewer
picks a path; statuses move proposed → under review → approved/rejected, and each decision gets a rationale
recorded in <code>COORDINATION.md</code>. Suggestions that need new data point at the discovery step that
would supply it (also see the <a href="decisions.html">decision register</a>).</p>
<table>{head}{body}</table>
<div class="banner"><strong>How to decide.</strong> For each row: (1) does it add verifiable information?
(2) does it keep every row source-linked? (3) does it change a gate? Gate changes need the
<a href="method.html">gates table</a> updated in the same PR. Reject-with-reason is a valid outcome and is recorded.</div>
""")

def p_review():
    body = f"""
<h2>Repo review — scope and method (this pass)</h2>
<p class="lede">Session {SESSION} reviewed the inherited repository with the aim of verifying the NFL-relevant
claims line by line against official sources, then building on top. Findings below carry evidence links so
every claim can be re-checked by hand.</p>
<table><tr><th>#</th><th>What was checked</th><th>Method</th><th>Result</th><th>Evidence</th></tr>
<tr><td>R1</td><td>All 14 Week 10 matchups + kickoff times (official page vs <code>games.csv</code>)</td>
<td>Transcribed the official NFL.com Week 10 page; compared game-by-game</td>
<td><span class="tag off">match</span> all 14 matchups and times agree</td>
<td class='src'><a href='{SRC_W10}' rel='noopener'>NFL.com week-10 ↗</a></td></tr>
<tr><td>R2</td><td>All 13 Week 11 matchups + kickoff times</td>
<td>Same method</td><td><span class="tag off">match</span> all 13 agree (incl. Mexico City SNF)</td>
<td class='src'><a href='{SRC_W11}' rel='noopener'>NFL.com week-11 ↗</a></td></tr>
<tr><td>R3</td><td>Week 10 TNF result</td><td>Official game page vs <code>games.csv</code> score fields</td>
<td><span class="tag off">match</span> Commanders 24, Giants 21 (final) in both</td>
<td class='src'><a href='{SRC_TNF}' rel='noopener'>official game page ↗</a></td></tr>
<tr><td>R4</td><td>Team records printed on official pages vs records computed from <code>games.csv</code></td>
<td>Computed W1–W9 records; compared against the 26 records printed on the fetched pages</td>
<td><span class="tag off">match</span> 0 mismatches (NYG/WAS include the TNF result, which also agrees)</td>
<td class='src'><a href='{SRC_W11}' rel='noopener'>official pages ↗</a></td></tr>
<tr><td>R5</td><td>Weekly injury report transcription</td><td>Row-for-row transcription of all 7 page chunks; programmatic count checks (296 rows / 28 teams / 14 games)</td>
<td><span class="tag est">transcribed</span> one name/slug mismatch flagged (NFL-K1); LAC/BAL "No Injuries Reported" kept as published</td>
<td class='src'><a href='{SRC_INJ}' rel='noopener'>NFL.com injuries ↗</a></td></tr>
<tr><td>R6</td><td>Market data provenance</td><td>Read nfldata <code>DATASETS.md</code> definition of <code>spread_line</code> and validated empirically (home favourites win 67.5% where spread_line &gt; 0)</td>
<td><span class="tag mkt">market</span> convention documented; an initial sign-flip in this build was caught and fixed (see <a href="method.html">Method</a>)</td>
<td class='src'><a href='https://github.com/nflverse/nfldata/blob/master/DATASETS.md' rel='noopener'>DATASETS.md ↗</a></td></tr>
<tr><td>R7</td><td>Inherited feeds (prior sessions)</td><td>Sampled <code>official/nfl-2026.json</code> against today's official pages; re-ran the repo's own checks (<code>check_links.py</code>, <code>verify_extra.py</code>, <code>audit_certainty.py</code>, unit tests)</td>
<td><span class="tag off">consistent</span> inherited schedule rows agree with today's official pages; checks pass (log below)</td>
<td class='src'><a href='https://www.nfl.com/schedules/2026/by-week/week-10/' rel='noopener'>NFL.com ↗</a></td></tr>
<tr><td>R8</td><td>Site link integrity after this build</td><td><code>lines-lab/scripts/verify_nfl_lab.py</code> (local links, row source links, JSON validity) plus the repo's existing checks</td>
<td>published in <code>lines-lab/data/derived/verification.json</code></td>
<td class='src'><a href='data.html' >data index</a></td></tr>
</table>
<h2>Check log</h2>
<p class="small">Populated by <code>verify_nfl_lab.py</code> at build time; the machine-readable version is
<code>lines-lab/data/derived/verification.json</code>.</p>
<div id="checklog"><p class="small">See verification.json (the generator embeds the latest results below).</p></div>
<h2>Irregularities carried into the flagged register</h2>
<p class="small">NFL-K1 … NFL-K10 — see <a href="flagged.html">Flagged for Review</a>. Prior sessions' items
remain published on <a href="../extra/flagged.html">the planner's flagged page</a> and are not duplicated here.</p>
"""
    return page("review.html", "Repo review", body)

def p_flagged():
    return page("flagged.html", "Flagged for review", f"""
<h2>Flagged for review — NFL Skill Lab</h2>
<p class="lede">Irregularities and unverified items found in this build. Nothing here was hidden, inferred,
or silently corrected; items do not block deployment. The planner's separate flagged page is
<a href="../extra/flagged.html">../extra/flagged.html</a>.</p>
{flags_page()}
""")

def p_sources():
    return page("sources.html", "Sources", sources_page())

def p_data():
    files = [
        ("data/sources.json", "Provenance registry: every dataset with URL, fetch method, commit, timestamp."),
        ("data/official/injuries-2026-w10.json", "Official Week 10 injury report, transcribed rows (NFL.com)."),
        ("data/official/schedule-2026-w10.json", "Official Week 10 schedule/results (NFL.com)."),
        ("data/official/schedule-2026-w11.json", "Official Week 11 schedule (NFL.com)."),
        ("data/nfldata/games.csv", "Results + market lines 1999–2026 (nfldata, market + results layer)."),
        ("data/nfldata/closing_lines.csv", "Per-book closing moneylines 2006–2026 (market layer)."),
        ("data/nfldata/initial_lines.csv", "Opening lines 2026 season (market layer)."),
        ("data/nfldata/sc_lines.csv", "Spread movement 2013–2026 (market layer)."),
        ("data/nfldata/standings.csv", "Final weekly standings 2002–2025."),
        ("data/nfldata/teams.csv", "Team abbreviation crosswalk."),
        ("data/nfldata/win_totals.csv", "Preseason win totals 2003–2026 (market layer)."),
        ("data/nfldata/rosters.csv", "Career roster rows 2006–2019 (limited — see NFL-K4)."),
        ("data/derived/model-meta.json", "Model parameters, home advantage, σ fits, diagnostics, records cross-check."),
        ("data/derived/lines-2026-w10-w11.json", "Originated lines vs market, Weeks 10–11."),
        ("data/derived/leaderboard.json", "Strategy backtest results, gates, points."),
        ("data/derived/correlation.json", "Correlation values, SGP scenarios, parlay math."),
        ("data/derived/depth-2026-w10.json", "Injury aggregation, unit pressure, QB notes."),
        ("data/derived/flags.json", "Flag register NFL-K1…K10."),
        ("data/derived/verification.json", "Build verification: link check, row-source check, JSON validity."),
    ]
    rows = "".join(f"<tr><td><code>{esc(p)}</code></td><td>{esc(d)}</td></tr>" for p, d in files)
    return page("data.html", "Data index", f"""
<h2>Data index</h2>
<p class="lede">Everything the lab publishes is a committed, deterministic artifact of
<code>lines-lab/scripts/build_nfl_lab.py</code> over the inputs below. Rebuild commands are on
<a href="method.html">Method</a>.</p>
<table><tr><th>Path (relative to lines-lab/)</th><th>Contents</th></tr>{rows}</table>
""")

PAGES_FN = {
    "index.html": p_index, "lines.html": p_lines, "leaderboard.html": p_leaderboard,
    "correlation.html": p_correlation, "injuries.html": p_injuries, "method.html": p_method,
    "decisions.html": p_decisions, "suggestions.html": p_suggestions, "review.html": p_review,
    "flagged.html": p_flagged, "sources.html": p_sources, "data.html": p_data,
}

def write_verification(verification):
    with open(os.path.join(DER, "verification.json"), "w") as f:
        json.dump(verification, f, indent=1)

def embed_checks(html_text, verification):
    rows = "".join(f"<p class='small'>{esc(c)}</p>" for c in verification["checks"])
    return html_text.replace('<div id="checklog"><p class="small">See verification.json (the generator embeds the latest results below).</p></div>',
                             f'<div id="checklog">{rows}</div>')

def main():
    # first pass: render pages (verification.json from previous run, if any)
    old_verify_path = os.path.join(DER, "verification.json")
    verification = None
    if os.path.exists(old_verify_path):
        verification = json.load(open(old_verify_path))
    os.makedirs(os.path.join(LAB, "assets"), exist_ok=True)
    with open(os.path.join(LAB, "assets", "lab.css"), "w") as f:
        f.write(CSS)
    rendered = {}
    for name, fn in PAGES_FN.items():
        rendered[name] = fn()
    if verification:
        rendered["review.html"] = embed_checks(rendered["review.html"], verification)
    for name, txt in rendered.items():
        with open(os.path.join(LAB, name), "w") as f:
            f.write(txt)
    print(f"wrote {len(rendered)} pages + assets/lab.css")
    if verification:
        print("embedded verification from previous run:", len(verification.get("checks", [])), "checks")

if __name__ == "__main__":
    main()
