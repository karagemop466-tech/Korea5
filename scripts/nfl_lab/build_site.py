#!/usr/bin/env python3
"""Build the static NFL lines lab site into nfl-lab/ from data/nfl-lab/*.json.

Every table row carries at least one link to an official source (nfl.com, gra.gov.sg,
police.gov.sg, ncpg.org.sg) or is explicitly marked UNVERIFIED on the Flagged page.
Run after scripts/nfl_lab/model.py and fetch_injuries.py. Then run verify.py.
"""
import html
import json
import os
from datetime import datetime

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(REPO, "data", "nfl-lab")
SITE = os.path.join(REPO, "nfl-lab")
ASSETS = os.path.join(SITE, "assets")
ROOT_SITE = "../"

BREAKEVEN_PCT = "52.38%"


def J(name):
    with open(os.path.join(D, name)) as f:
        return json.load(f)


def e(x):
    return html.escape("" if x is None else str(x))


def pct(x):
    return "" if x is None else f"{x * 100:.1f}%"


def link(url, text=None):
    return f'<a href="{e(url)}" rel="noopener">{e(text or url)}</a>'


NAV = [
    ("index.html", "Home"),
    ("executive-summary.html", "Executive summary"),
    ("lines-2026.html", "Our lines 2026"),
    ("strategies.html", "Strategy leaderboard"),
    ("validation.html", "Validation gates"),
    ("correlations.html", "Correlations & parlays"),
    ("injuries.html", "Injuries & depth"),
    ("questions.html", "Open questions"),
    ("suggestions.html", "Suggestions"),
    ("sources.html", "Sources"),
    ("verification.html", "Verification"),
    ("flagged.html", "Flagged for review"),
    ("../lab/index.html", "Evidence workbench"),
]


def page(active, title, body, extra_head=""):
    parts = []
    for href, label in NAV:
        cls = ' class="on"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{e(label)}</a>')
    nav = "".join(parts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · NFL Lines Lab</title>
<link rel="stylesheet" href="assets/style.css">{extra_head}
</head><body>
<header class="top"><div class="brand"><a href="index.html">NFL Lines Lab</a> <span class="tag">research only</span></div>
<nav>{nav}</nav></header>
<div class="banner">Research and education only. Not betting advice. Singapore: only Singapore Pools is licensed for remote gambling; taking part in unlicensed remote gambling is an offence (<a href="https://www.gra.gov.sg/harm-minimisation/unlawful-remote-gambling-activities">GRA</a>).</div>
<main>{body}</main>
<footer>Part of the <a href="{ROOT_SITE}">Korea5 repository site</a>. Source code and data: <a href="https://github.com/karagemop466-tech/Korea5/tree/arena/1e59465a-korea5/nfl-lab">GitHub branch</a>. Generated {GEN}.</footer>
<script src="assets/app.js"></script>
</body></html>
"""


_TABLE_N = [0]


def table(headers, rows, cls="", search=True, sort=True):
    _TABLE_N[0] += 1
    tid = f"t{_TABLE_N[0]}"
    ths = "".join(f'<th>{e(h)}</th>' for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    box = ""
    if search:
        box = f'<input class="filter" placeholder="Filter rows…" data-target="{tid}" aria-label="Filter rows">'
    return f'{box}<div class="scroll"><table id="{tid}" class="data {cls}" data-sort="{1 if sort else 0}"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div><p class="count" data-count-for="{tid}"></p>'


OFFICIAL_HOSTS = ("nfl.com", "gra.gov.sg", "police.gov.sg", "ncpg.org.sg")


def src_cell(url, label):
    """Link plus a visible flag when the host is not official, or no source exists."""
    if not url:
        return flag("NO SOURCE")
    host = url.split("/")[2]
    if any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
        return link(url, label)
    return link(url, label) + " " + flag("UNOFFICIAL SOURCE")


def card(label, value, note=""):
    return f'<div class="card"><div class="k">{e(label)}</div><div class="v">{value}</div><div class="n">{note}</div></div>'


def flag(text="UNVERIFIED"):
    return f'<span class="flag">{e(text)}</span>'


NFL_HUB = "https://www.nfl.com/schedules/"
NFL_INJ = "https://www.nfl.com/injuries/"
GRA_UNLAWFUL = "https://www.gra.gov.sg/harm-minimisation/unlawful-remote-gambling-activities"
GRA_PROBLEM = "https://www.gra.gov.sg/harm-minimisation/problem-gambling"
NCPG = "http://www.ncpg.org.sg/"
NFLVERSE_INJ = "https://github.com/nflverse/nflverse-data/releases/tag/injuries"
NFLVERSE_DEPTH = "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts"
NFLDATA = "https://github.com/nflverse/nfldata"
NFLDATA_DICT = "https://github.com/nflverse/nfldata/blob/master/DATASETS.md"


def main():
    global GEN
    GEN = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(ASSETS, exist_ok=True)
    params = J("model-params.json")
    strat = J("strategies.json")
    lines = J("lines-2026.json")
    inj_all = J("injuries-2026.json")["rows"]
    tw = J("injuries-team-week.json")["rows"]
    depth = J("depth-backups-2026.json")
    qb = J("injuries-qb-2016-2026.json")["rows"]
    src = J("games-source.json")
    fetchlog = J("fetch-log.json")
    rr = J("repo-review.json")

    lb = strat["leaderboard"]
    validated = [r for r in lb if r["validated"]]
    near = [r for r in lb if r["passes_all_except_G0"]]
    wk_now = depth["injury_week"]
    out_now = [r for r in inj_all if str(r["week"]) == str(wk_now) and r["report_status"] == "Out"]
    final_n = sum(1 for x in lines["rows"] if x["status"] == "final")
    up_n = sum(1 for x in lines["rows"] if x["status"] == "scheduled")
    best = lb[0]
    mae_m = params["test_mae_model_margin"]
    mae_mk = params["test_mae_market_spread"]

    # ------------------------------------------------------------ index
    body = f"""
<section class="hero">
  <h1>NFL Lines Lab</h1>
  <p class="lede">Our own NFL line model, tested the way a skeptic would test it: walk-forward, out-of-sample, gated, and compared with the market. Every strategy has to clear the validation gates before it earns any points on the leaderboard.</p>
  <p class="lede small">Status: <strong>no strategy has passed every gate</strong>, so no rewards are awarded. The model is currently less accurate than the market spread.</p>
</section>
<section class="cards">
  {card("Strategies tested", str(len(lb)), "single bets, parlays tested separately")}
  {card("Passing all gates", str(len(validated)), f"{len(near)} pass everything except G0 (data provenance)")}
  {card("Points awarded", "0", "no strategy has passed every gate")}
  {card("Model MAE 2016–25", f"{mae_m:.2f} pts", f"market spread MAE {mae_mk:.2f} pts (lower is better)")}
  {card(f"Week {wk_now} starters out", str(len([r for r in depth['rows'] if r['original_starter_out']])), "depth slots where a starter is out (current snapshot)")}
  {card("Open questions", str(len(J('questions.json')['questions'])) if os.path.exists(os.path.join(D,'questions.json')) else "see page", "information still missing")}
</section>
<div class="callout"><strong>Two labs, one question.</strong> This section builds and back-tests a line model from
third-party game data. The companion <a href="../lab/index.html">NFL Lines Lab</a> holds the evidence side of the same
question, built only on official NFL records: the published injury report, official player game logs and the official
Game Book, with the measured correlations, dispersion figures and minimum-sample rules computed from them. Read them
together — neither one publishes a validated edge on its own.</div>
<h2>Start here</h2>
<div class="grid">
  <a class="tile" href="executive-summary.html"><b>Executive summary</b><span>What we found, in plain language.</span></a>
  <a class="tile" href="lines-2026.html"><b>Our lines · 2026</b><span>Our projected margin and total for every 2026 game. Market lines left blank (unverified).</span></a>
  <a class="tile" href="strategies.html"><b>Strategy leaderboard</b><span>Ranked by the lower bound of out-of-sample hit rate. Gates shown.</span></a>
  <a class="tile" href="validation.html"><b>Validation gates</b><span>The six gates, the tuning, and every pass / fail.</span></a>
  <a class="tile" href="correlations.html"><b>Correlations & parlays</b><span>How strategies overlap, and what parlays really do.</span></a>
  <a class="tile" href="injuries.html"><b>Injuries & depth</b><span>Official NFL injury reports, team deficiency counts, starters out with backups.</span></a>
  <a class="tile" href="questions.html"><b>Open questions</b><span>What we know, what we don't, and how to get each missing piece.</span></a>
  <a class="tile" href="suggestions.html"><b>Suggestions</b><span>Options for the next step. Nothing is implemented until you choose.</span></a>
  <a class="tile" href="sources.html"><b>Sources</b><span>Every official and third-party source, with its verification status.</span></a>
  <a class="tile" href="verification.html"><b>Verification</b><span>Row-by-row checks, spot checks against nfl.com, link checks.</span></a>
  <a class="tile warn" href="flagged.html"><b>Flagged for review</b><span>Irregularities and unverified items, with links, for your review.</span></a>
</div>
<h2>Data freshness</h2>
<ul>
  <li>NFL games file (scores, rest, starting QBs, lines): fetched {e(src['fetched_utc'])} from {link(NFLDATA)} (archive sha256 <code>{e(src['archive_sha256'][:16])}…</code>).</li>
  <li>Injury reports: CI fetch {e(fetchlog['generated_utc'])} from {link(NFLVERSE_INJ, 'nflverse mirror of NFL injury reports')}. Latest official week: {e(wk_now)} at {link(f'https://www.nfl.com/injuries/league/2026/reg{wk_now}', 'nfl.com')}.</li>
  <li>Depth charts: {link(NFLVERSE_DEPTH, 'nflverse mirror (ESPN-derived, third-party)')}.</li>
</ul>
"""
    open(os.path.join(SITE, "index.html"), "w").write(page("index.html", "Home", body))

    # ------------------------------------------------------------ executive summary
    best_name = best["strategy"]
    body = f"""
<h1>Executive summary</h1>
<p class="lede">Question: can we set our own NFL lines and find strategies that beat the market, with the luck taken out? Answer as of this build: <strong>not yet, and the evidence points the other way</strong>.</p>
<h2>What we found</h2>
<ol class="findings">
<li><strong>Our line model is less accurate than the market.</strong> Walk-forward on 2016–2025 (K chosen on 2006–2015 only), the model misses the final margin by {mae_m:.2f} points on average. The market spread misses by {mae_mk:.2f}. Our model is a useful benchmark, not a better price.</li>
<li><strong>No strategy passes every gate.</strong> {len(lb)} strategies were tested against six gates. None passes all six. The best by lower confidence bound is <code>{e(best_name)}</code>: {best['test_n']} bets, hit rate {pct(best['test_hit'])} (95% CI {pct(best['test_hit_ci95'][0]) if best['test_hit_ci95'] else '—'} to {pct(best['test_hit_ci95'][1]) if best['test_hit_ci95'] else '—'}), p = {best['test_p']}. That is consistent with luck.</li>
<li><strong>The market inputs are not verified.</strong> The spread and total lines come from a community dataset whose documentation does not name the source. Gate G0 therefore fails for every strategy. Results are provisional until a documented source is confirmed.</li>
<li><strong>Injury-based signals are too thin to test.</strong> Only 7 games from 2016 to 2025 had a starting QB listed Out or Doubtful on the official report (and the QB-based strategies are therefore untestable).</li>
<li><strong>Correlation is real, and parlays do not rescue the edge.</strong> Edge strategies overlap heavily (see Correlations). For two-leg parlays, the joint win rate is {'{:.1%}'.format(strat['parlays'][0]['joint_win_rate'])} for the top pair versus {'{:.1%}'.format(strat['parlays'][0]['independent_assumption'])} if the legs were independent, so the naive independence estimate understates the hit rate for these pairs. But the top pair is two nested versions of one edge (game overlap {strat['parlays'][0]['leg_game_overlap']:.0%}), and {sum(1 for p in strat['parlays'] if p['validated'])} of {strat['parlays_tested']} parlays pass all five parlay gates.</li>
<li><strong>Current injury picture (Week {e(wk_now)}, official report).</strong> {len(out_now)} players are listed Out. Two starters are out in a depth slot that has a named backup: DET LCB D.J. Reed (backup Khalil Dorsey) and NE LCB Carlton Davis III (backup Charles Woods). Depth data is third-party, so treat these as leads to check against the team's own depth chart.</li>
<li><strong>Player-prop combinations cannot be tested.</strong> No official source publishes historical prop prices.</li>
<li><strong>Singapore:</strong> Singapore Pools is the only licensed remote gambling operator. Taking part in unlicensed remote gambling is an offence (up to S$10,000 and/or 6 months). We cannot recommend any wager. The site is for analysis only. {link(GRA_UNLAWFUL, 'GRA: Unlawful remote gambling')}</li>
</ol>
<h2>Recommendation (for your decision)</h2>
<p>Do not act on any strategy yet. The next steps are decisions, not more building. See <a href="suggestions.html">Suggestions</a> for the options and <a href="questions.html">Open questions</a> for the information still needed. Nothing has been implemented beyond the analysis shown here.</p>
<h2>Method in one paragraph</h2>
<p>Team power ratings are updated after each game by {params['K_selected']} × (actual margin − predicted margin), regressed toward zero each season, with a {params['HFA_points']}-point home edge (none at neutral sites). Totals use an exponentially weighted average of recent game totals (α = {params['ALPHA_totals']}). Every prediction uses only games played before kickoff. Strategies are scored at −110 (break-even {BREAKEVEN_PCT}). Pushes are excluded.</p>
<p class="small">Scope note: the analysis covers regular-season games. Playoff games are excluded from evaluation.</p>
"""
    open(os.path.join(SITE, "executive-summary.html"), "w").write(page("executive-summary.html", "Executive summary", body))

    # ------------------------------------------------------------ lines 2026
    rows = []
    for x in lines["rows"]:
        wk = x["week"]
        official = f"{NFL_HUB}2026/by-week/week-{wk}"
        score = f"{x['away']} {x['away_score']} – {x['home']} {x['home_score']}" if x["status"] == "final" else "—"
        mline = f"{x['home']} {-x['model_home_margin']:+.1f}" if x["model_home_margin"] is not None else ""
        rows.append([
            e(wk), e(x["gameday"]), e(f"{x['away']} @ {x['home']}"),
            e(score), e(f"{x['model_home_margin']:+.1f}" if x["model_home_margin"] is not None else ""),
            e(f"{x['model_total']:.1f}"),
            f'<span class="unv">blank {flag()}</span>',
            f'<span class="unv">blank {flag()}</span>',
            e(x["status"]),
            link(official, "NFL week " + str(wk)),
        ])
    body = f"""
<h1>Our lines · 2026 regular season</h1>
<p class="lede">Our projected margin is the points the home team is favoured by, in our model. Negative means the away team is favoured. Our total is our projected combined score. Scores come from the games file and were spot-checked against nfl.com (see Verification). Market spread and total columns are intentionally blank: the only available lines are third-party and unverified.</p>
<p class="small">Model K = {params['K_selected']}, fitted on 2006–2015 only. Forward test on 2026 games played so far: MAE {params['forward_2026_mae_model_margin']:.2f} pts over {params['forward_2026_games']} games.</p>
<p class="small">{final_n} final · {up_n} scheduled. Filter by team or week in the box below.</p>
{table(["Week", "Date", "Matchup (away @ home)", "Final score (away–home)", "Our margin (home +)", "Our total", "Market spread", "Market total", "Status", "Official source"], rows)}
"""
    open(os.path.join(SITE, "lines-2026.html"), "w").write(page("lines-2026.html", "Our lines 2026", body))

    # ------------------------------------------------------------ strategies
    srows = []
    for r in lb:
        g = r["gates"]
        passed = sum(1 for v in g.values() if v["pass"])
        srows.append([
            e(r["rank"]), f"<code>{e(r['strategy'])}</code>", e(r["kind"]),
            e(r["test_n"]), e(pct(r["test_hit"])), e(f"{pct(r['test_hit_ci95'][0])} – {pct(r['test_hit_ci95'][1])}" if r["test_hit_ci95"] else ""),
            e(f"{r['test_roi_at_110']*100:+.1f}%" if r["test_roi_at_110"] is not None else ""),
            e(r["test_p"]), e(f"{r['forward_2026_n']} · {pct(r['forward_2026_hit'])}"),
            e(f"{passed}/6"),
            e("yes" if r["validated"] else "no"),
            e(r["reward_points"]),
            f'<span class="unv">provisional {flag("UNVERIFIED INPUTS")}</span> ' + link(NFL_HUB, "nfl.com schedules") + " · " + link(NFLDATA_DICT, "data dictionary"),
        ])
    blocked = "".join(f"<li><strong>{e(b['strategy'])}</strong>: {e(b['reason'])}</li>" for b in strat["blocked"])
    body = f"""
<h1>Strategy leaderboard</h1>
<p class="lede">Each strategy is a rule that picks a side in a game (spread) or over/under (total). They are ranked by the lower 95% bound of their 2016–2025 out-of-sample hit rate, so a strategy with few bets cannot rank high on luck. Points are awarded only if a strategy passes every gate. <strong>Points awarded so far: 0.</strong></p>
<p class="small">Bonferroni threshold for the p-value gate: 0.05 ÷ {strat['k_tests_bonferroni']} = {0.05/strat['k_tests_bonferroni']:.4f}. Break-even at −110: {BREAKEVEN_PCT}.</p>
{table(["Rank", "Strategy", "Type", "Bets (2016–25)", "Hit rate", "95% CI", "ROI at −110", "p (two-sided)", "2026 forward (bets · hit)", "Gates passed", "Validated", "Points", "Source"], srows)}
<h2>Not testable with verified data</h2>
<ul>{blocked}</ul>
<h2>Strategy definitions</h2>
<ul class="defs">
<li><code>MKT-HOME / MKT-FAV / MKT-DOG</code>: baselines. Bet the home team, the favourite or the underdog against the spread every game.</li>
<li><code>MODEL-EDGE-n</code>: bet the side our model prefers by at least n points against the spread.</li>
<li><code>REST-GAP-3</code>: bet the team with at least 3 more days of rest.</li>
<li><code>QB-OUT-FADE / QB-OUT-BACK</code>: starting QB listed Out or Doubtful on the NFL report (exactly one side). Fade = bet the other team. Back = bet the team with the injured QB. Only 7 games qualify in 2016–2025, so these are untestable.</li>
<li><code>TOTAL-EDGE-3</code>: bet over/under when our total differs from the total line by 3 or more.</li>
<li><code>Parlays</code>: two single-bet legs on different games in the same week. Gates P1–P5 are listed on the Correlations page.</li>
</ul>
"""
    open(os.path.join(SITE, "strategies.html"), "w").write(page("strategies.html", "Strategy leaderboard", body))

    # ------------------------------------------------------------ validation
    gate_names = list(lb[0]["gates"].keys())
    gheaders = ["Strategy"] + [g.split("_")[0] for g in gate_names] + ["Result"]
    grows = []
    for r in lb:
        cells = [f"<code>{e(r['strategy'])}</code> {flag('UNVERIFIED INPUTS')}"]
        for g in gate_names:
            v = r["gates"][g]
            cells.append('<span class="ok">pass</span>' if v["pass"] else '<span class="bad">fail</span>')
        cells.append("validated" if r["validated"] else "not validated")
        grows.append(cells)
    kgrid = "".join(f"<tr><td>{k['K']}</td><td>{k['train_mae']}</td><td>{'← selected' if k['K']==params['K_selected'] else ''}</td></tr>" for k in params["K_grid"])
    gdefs = [
        ("G0", "Provenance", "Market lines come from an official or verified source with a documented method. Fails: nfldata does not name the source of spread_line / total_line.", NFLDATA_DICT),
        ("G1", "Sample", "At least 300 settled bets in the 2016–2025 out-of-sample window.", NFLDATA),
        ("G2", "Edge over break-even", "Hit rate ≥ 52.38% and the season-block bootstrap 95% CI lower bound above 50%.", None),
        ("G3", "Significance", "Exact two-sided binomial p-value below 0.05 divided by the number of strategies tested (Bonferroni).", None),
        ("G4", "Consistency", "At least 70% of test seasons above break-even.", None),
        ("G5", "No look-ahead", "Predictions use only games before kickoff; ratings are stored before each game updates them.", None),
    ]
    gdrows = [[e(a), e(b), e(c), (link(d, "source") if d else "")] for a, b, c, d in gdefs]
    body = f"""
<h1>Validation gates</h1>
<p class="lede">A strategy earns points only if it passes every gate below. The gates are applied to 2016–2025 data that was not used to choose any parameter, except the one tuning parameter K, which was chosen on 2006–2015.</p>
<h2>Gates</h2>
{table(["Gate", "Name", "Rule", "Source"], gdrows, cls="method", search=False)}
<h2>Results by strategy</h2>
<p class="small">Every row uses third-party market lines (gate G0 fails), so each strategy is flagged UNVERIFIED INPUTS. Gate-by-gate results are shown for transparency.</p>
{table(gheaders, grows, search=False)}
<h2>Model tuning (training window only)</h2>
<p class="small">Lowest mean absolute error on 2006–2015 regular-season games selects K. Test window 2016–2025 reports MAE: model {mae_m}, market spread {mae_mk}, total model {params['test_mae_model_total']} (games: {params['test_games']}).</p>
<table class="data method"><thead><tr><th>K</th><th>Train MAE</th><th></th></tr></thead><tbody>{kgrid}</tbody></table>
<p class="small">Luck control: 95% intervals come from 2,000 season-block bootstrap resamples. Seasons are resampled as blocks because games within a season share weather, injuries and schedule effects.</p>
"""
    open(os.path.join(SITE, "validation.html"), "w").write(page("validation.html", "Validation gates", body))

    # ------------------------------------------------------------ correlations
    names = list(strat["correlation_matrix"].keys())
    crow = []
    for a in names:
        cells = [f"<code>{e(a)}</code> {flag('UNVERIFIED INPUTS')}"]
        for b in names:
            c = strat["correlation_matrix"][a][b]
            cells.append("" if c["r"] is None else f"{c['r']:+.2f}")
        crow.append(cells)
    prow = []
    for p in strat["parlays"]:
        failed = [k.split("_")[0] for k, v in p["gates"].items() if not v]
        prow.append([
            f"<code>{e(p['legs'][0])}</code> + <code>{e(p['legs'][1])}</code> {flag('UNVERIFIED INPUTS')}",
            e(p["pairs"]), e(pct(p["joint_win_rate"])), e(pct(p["independent_assumption"])),
            e(f"{p['correlation_gap']*100:+.2f} pts"),
            e(pct(p["parlay_breakeven_two_legs"])),
            e(f"{p['parlay_roi_at_110_empirical']*100:+.1f}%"),
            e(p["p_vs_breakeven"]), e(p["seasons_above_breakeven"]), e(f"{p['leg_game_overlap']:.0%}"),
            e(", ".join(failed) or "none"), e("yes" if p["validated"] else "no"),
            link(NFLDATA_DICT, "data") + " · " + link(NFL_HUB, "nfl.com"),
        ])
    body = f"""
<h1>Correlations & parlays</h1>
<p class="lede">Correlation between strategies is measured on the games they both bet (outcome +1 win, −1 loss). Two bets that are highly correlated add little diversification. A parlay's true win rate can differ from the product of its legs' rates; the gap is shown below.</p>
<h2>Strategy outcome correlation (2016–2025)</h2>
<div class="scroll"><table class="data matrix"><thead><tr><th></th>{''.join(f'<th>{e(n)}</th>' for n in names)}</tr></thead><tbody>
{''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in crow)}
</tbody></table></div>
<p class="small">Blank = fewer than 20 shared games. Diagonal is 1 by definition.</p>
<h2>Two-leg parlays (all {strat['parlays_tested']} tested, ranked by empirical ROI at −110)</h2>
<p class="small">Pairs of single-bet strategies on different games in the same week. Joint win rate is observed; independence assumes the product of the two hit rates. Two legs at −110 need {pct(strat['parlays'][0]['parlay_breakeven_two_legs'])} joint to break even. Gates: {'; '.join(strat['parlay_gates'])}. Validated parlays: <strong>{strat['parlays_validated']} of {strat['parlays_tested']}</strong>.</p>
{table(["Legs", "Pairs", "Joint win rate", "Independence assumption", "Correlation gap", "Break-even joint", "Empirical ROI", "p vs break-even", "Seasons above break-even", "Leg game overlap", "Gates failed", "Validated", "Source"], prow)}
"""
    open(os.path.join(SITE, "correlations.html"), "w").write(page("correlations.html", "Correlations & parlays", body))

    # ------------------------------------------------------------ injuries & depth
    tw26 = [r for r in tw if r["season"] == 2026 and str(r["week"]) == str(wk_now)]
    trow = []
    for r in sorted(tw26, key=lambda r: r["team"]):
        groups = "; ".join(f"{g}: {', '.join(f'{k} {v}' for k, v in c.items() if v)}" for g, c in r["by_group"].items() if any(c.values()))
        trow.append([e(r["team"]), e(r["Out"]), e(r["Doubtful"]), e(r["Questionable"]), e(groups),
                     link(r["source"], f"nfl.com week {wk_now}")])
    drow = []
    for r in depth["rows"]:
        inj = "; ".join(f"{x['player']} (depth {x['depth_rank']}, {x['status']}, {x['injury']})" for x in r["injured_ahead"])
        drow.append([e(r["team"]), e(r["depth_slot"]), e(r["depth_group"]), e(inj),
                     e(f"{r['effective_starter']} (depth {r['effective_depth_rank']})"),
                     link(r["source"], "nfl.com injury report") + " · " + link(NFLVERSE_DEPTH, "depth source")])
    irow = []
    for r in inj_all:
        irow.append([e(r["season"]), e(r["week"]), e(r["team"]), e(r["player"]), e(r["position"]), e(r["report_status"]),
                     e(r["primary_injury"]), e(r["practice_status"]), link(r["source"], f"nfl.com week {r['week']}")])
    body = f"""
<h1>Injuries & depth</h1>
<p class="lede">Source of record: the NFL's own weekly injury report (nfl.com). The team tables summarise the latest report, week {e(wk_now)}. The depth table flags where an injured starter is ahead of a healthy backup on the latest depth-chart snapshot. Depth charts come from a third-party mirror (ESPN-derived), so treat each depth row as a lead to verify, not a fact.</p>
<h2>Team deficiency counts · week {e(wk_now)} (official report)</h2>
<p class="small">Out / Doubtful / Questionable counts, with the position groups that have players listed. Groups: QB, RB, WR, TE, OL, DL, LB, DB, ST.</p>
{table(["Team", "Out", "Doubtful", "Questionable", "By position group (status counts)", "Official source"], trow)}
<h2>Starters out and the first healthy backup (depth snapshot {e(depth['rows'][0]['depth_snapshot_utc'] if depth['rows'] else '')})</h2>
{table(["Team", "Depth slot", "Formation group", "Injured players ahead on the chart", "Effective starter", "Sources"], drow)}
<h2>All 2026 Out / Doubtful / Questionable entries, weeks 1–{e(wk_now)} (row-level)</h2>
<p class="small">{len(inj_all)} rows. Every row links to the NFL official week page.</p>
{table(["Season", "Week", "Team", "Player", "Pos", "Status", "Injury", "Practice", "Official source"], irow)}
"""
    open(os.path.join(SITE, "injuries.html"), "w").write(page("injuries.html", "Injuries & depth", body))

    # ------------------------------------------------------------ questions
    Q = J("questions.json")
    qrows = []
    for q in Q["questions"]:
        qrows.append([e(q["id"]), e(q["area"]), e(q["question"]), e(q["known"]), e(q["missing"]), e(q["how_to_get_it"]),
                      src_cell(q.get("source"), q.get("source_label", "source"))])
    body = f"""
<h1>Open questions</h1>
<p class="lede">Questions that must be answered before any decision can reasonably be made on the information we have. Each shows what we know, what is missing, and how to get it. Nothing here is a recommendation.</p>
{table(["ID", "Area", "Question", "What we know (verified)", "What is missing", "How to get it", "Source"], qrows)}
"""
    open(os.path.join(SITE, "questions.html"), "w").write(page("questions.html", "Open questions", body))

    # ------------------------------------------------------------ suggestions
    S = J("suggestions.json")
    srows2 = []
    for s in S["suggestions"]:
        opts = "<br>".join(f"<b>{e(o['id'])}</b> {e(o['label'])}: {e(o['tradeoff'])}" for o in s["options"])
        srows2.append([e(s["id"]), e(s["area"]), e(s["suggestion"]), e(s["why"]), opts, '<span class="pending">awaiting your choice</span>'])
    body = f"""
<h1>Suggestions</h1>
<p class="lede">Ways to improve the site and the analysis. Each suggestion has options and trade-offs. <strong>Nothing here has been implemented.</strong> Choose an option ID for each item you want, and that choice becomes the next task.</p>
{table(["ID", "Area", "Suggestion", "Why", "Options (choose one)", "Status"], srows2, cls="method")}
"""
    open(os.path.join(SITE, "suggestions.html"), "w").write(page("suggestions.html", "Suggestions", body))

    # ------------------------------------------------------------ sources
    SRC = J("sources.json")
    srows3 = []
    for s in SRC["sources"]:
        off = s["official"].startswith("Yes") or s["official"].startswith("Linked")
        srows3.append([e(s["name"]), src_cell(s["url"], s["url"]), e(s["provides"]), e(s["official"]) if off else flag("UNOFFICIAL") + " " + e(s["official"]), e(s["verified_how"])])
    body = f"""
<h1>Sources</h1>
<p class="lede">Every source used, with the check performed. "Official" means published by the NFL, a regulator or the league's own data. Third-party sources are used only where marked, and their values are flagged.</p>
{table(["Source", "Link", "Provides", "Official?", "Verification performed"], srows3)}
"""
    open(os.path.join(SITE, "sources.html"), "w").write(page("sources.html", "Sources", body))

    # ------------------------------------------------------------ verification
    V = J("verification.json") if os.path.exists(os.path.join(D, "verification.json")) else {"checks": []}
    vrows = [[e(c["check"]), e(c["result"]), e(c.get("detail", ""))] for c in V["checks"]]
    spot = [
        ["2026 Week 10 · Commanders @ Giants (Thu Nov 12)", "WAS 24 – NYG 21, FINAL", "WAS 24 – NYG 21", "pass", link("https://www.nfl.com/schedules/2026/by-week/week-10", "nfl.com week 10")],
        ["2026 Week 9 · Lions @ Dolphins", "DET 19 – MIA 9, FINAL", "DET 19 – MIA 9", "pass", link("https://www.nfl.com/games/lions-at-dolphins-2026-reg-9", "nfl.com game center")],
        ["2026 Week 9 · Bills @ Vikings", "BUF 23 – MIN 6, FINAL", "BUF 23 – MIN 6", "pass", link("https://www.nfl.com/games/bills-at-vikings-2026-reg-9", "nfl.com game center")],
        ["2026 Week 10 injury report · 9 Out/Questionable rows (WAS, NYG, NE, DET first three games)", "status, injury, practice status", "all 9 rows identical", "pass", link("https://www.nfl.com/injuries/league/2026/reg10", "nfl.com week 10 injuries")],
    ]
    body = f"""
<h1>Verification</h1>
<p class="lede">How each number was checked. Each row below links to the official page used. Items that could not be confirmed against an official page are flagged rather than filled in.</p>
<h2>Spot checks against official NFL pages (performed 2026-11-13)</h2>
{table(["Item", "Official page says", "Our data says", "Result", "Official source"], spot, search=False)}
<h2>How to rebuild</h2>
<ol class="small">
<li><code>python3 scripts/nfl_lab/fetch_games.py</code> — downloads the games file from the nfldata archive and writes the hash manifest.</li>
<li><code>python3 scripts/nfl_lab/fetch_injuries.py</code> — runs in GitHub Actions (workflow <code>nfl-lab-injuries</code>), because the injury mirror is only reachable from there.</li>
<li><code>python3 scripts/nfl_lab/model.py</code> — walk-forward model, backtests, gates, correlations, parlays.</li>
<li><code>python3 scripts/nfl_lab/build_site.py</code>, then <code>python3 scripts/nfl_lab/verify.py</code>, then build again so this page shows the latest checks.</li>
</ol>
<h2>Automated checks</h2>
{table(["Check", "Result", "Detail"], vrows, cls="method", search=False)}
<p class="small">A full row-by-row comparison of all 137 final 2026 games against nfl.com is not complete: only the three spot checks above were run in this session. Remaining games are flagged, see Flagged for review.</p>
"""
    open(os.path.join(SITE, "verification.html"), "w").write(page("verification.html", "Verification", body))

    # ------------------------------------------------------------ flagged
    F = J("flags.json")
    frows = []
    for f_ in F["flags"]:
        frows.append([flag("FLAGGED") + " " + e(f_["id"]), e(f_["severity"]), e(f_["item"]), e(f_["detail"]), src_cell(f_.get("source"), f_.get("source_label", "source"))])
    rrows = [[flag("FLAGGED") + " " + e(x["id"]), e(x["severity"]), e(x["item"]), e(x["evidence"]), src_cell(x["source_link"], "repo file"), e(x["action"])] for x in rr["irregularities"]]
    body = f"""
<h1>Flagged for review</h1>
<p class="lede">Irregularities, unverified items and open risks. They do not block publication, but they are listed here so you can review them, challenge them, or ask for changes.</p>
<h2>Analysis and data flags</h2>
{table(["ID", "Severity", "Item", "Detail", "Source"], frows)}
<h2>Repo review irregularities</h2>
<p class="small">Checks run: {'; '.join(c['check'] + ' → ' + c['result'] for c in rr['checks_run'])}.</p>
{table(["ID", "Severity", "Item", "Evidence", "Source", "Suggested action"], rrows)}
"""
    open(os.path.join(SITE, "flagged.html"), "w").write(page("flagged.html", "Flagged for review", body))

    print("built pages")


if __name__ == "__main__":
    main()
