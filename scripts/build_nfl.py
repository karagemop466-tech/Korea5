#!/usr/bin/env python3
"""Generate the NFL Decision Support hub (nfl/*.html) from nfl/data/*.json.

This is the structured, data-driven decision-support layer for the NFL Lines
work. It is deliberately non-duplicative: the companion "NFL Lines
(origination)" pages (nfl-lines.html, nfl-strategies.html, nfl-correlation.html,
nfl-injuries.html, nfl-questions.html, nfl-suggestions.html,
nfl-executive-summary.html, nfl-flagged.html) already cover strategy,
correlation, injury, questions, suggestions, executive summary and flagged
detail. This hub adds the full requirements list, the method/validation-gate
reference, the leaderboard reward design, and a machine-readable source registry
with a line-by-line verifier.

Self-contained: reads only nfl/data, writes only nfl/*.html.
Every fact-bearing row traces to a source link rendered from
nfl/data/sources.json. Blank / unverified values render as "—" and are
published on the companion Flagged page.
"""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
NFL = ROOT / "nfl"
DATA = NFL / "data"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def esc(x):
    return html.escape("" if x is None else str(x))


SOURCES = {s["id"]: s for s in load("sources")["sources"]}
VERIFIED_DATE = load("sources")["verifiedDate"]


def src_link(sid):
    if not sid:
        return '<span class="blank">—</span>'
    s = SOURCES.get(sid)
    if not s:
        return f'<span class="blank">{esc(sid)} (unresolved)</span>'
    return (
        f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">'
        f'{esc(s["id"])} · {esc(s["name"])}</a>'
    )


def td(value, cls=""):
    if value is None or value == "":
        return f'<td class="{cls} blank">—</td>'
    return f'<td class="{cls}">{esc(value)}</td>'


def td_raw(raw, cls=""):
    return f'<td class="{cls}">{raw}</td>'


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(r) + "</tr>" for r in rows)
    return f'<table class="grid">\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody>\n</table>'


NAV = [
    ("index.html", "Dashboard"),
    ("requirements.html", "Requirements"),
    ("method.html", "Method"),
    ("leaderboard.html", "Leaderboard"),
    ("sources.html", "Sources"),
]

# Companion origination pages (built by the parallel session, live on main).
COMPANION = [
    ("../nfl-lines.html", "NFL Lines (origination)", "Lines origination dashboard, signal library and leaderboard snapshot."),
    ("../nfl-strategies.html", "Strategies & gates", "Single bet, parlay and player-prop strategy frameworks with validation gates."),
    ("../nfl-correlation.html", "Correlation", "Correlation method and value disclosure."),
    ("../nfl-injuries.html", "Injuries & depth", "Injury designations and starter/backup depth tracking."),
    ("../nfl-questions.html", "Questions", "Pre-decision questions with a have / don't-have inventory."),
    ("../nfl-suggestions.html", "Suggestions", "Suggestions for review and choosing a path."),
    ("../nfl-executive-summary.html", "Executive summary", "Executive summary of the NFL Lines work."),
    ("../nfl-flagged.html", "Flagged", "Irregularities and unverified items."),
]


def nav(active):
    items = []
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        items.append(f'<a href="{href}"{cls}>{esc(label)}</a>')
    return '<nav class="topnav">' + "".join(items) + "</nav>"


def page(title, active, body, subtitle=None):
    sub = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NFL Decision Support</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
{nav(active)}
<main class="wrap">
<header class="hero">
<h1>{esc(title)}</h1>
{sub}
<p class="meta">Sources verified {esc(VERIFIED_DATE)} · every fact-bearing row links to an official source</p>
</header>
{body}
<footer class="foot">
<p><strong>Responsible gaming:</strong> this is decision-support research, not a wagering service. No real-money wagers are placed. Betting carries risk; please gamble responsibly.</p>
<p>Built from <code>nfl/data/*.json</code> by <code>scripts/build_nfl.py</code>. Values that cannot be confirmed from an official source are left blank and flagged on the companion Flagged page.</p>
</footer>
</main>
<script src="assets/app.js"></script>
</body>
</html>
"""


def badge(status):
    return f'<span class="badge">{esc(status)}</span>'


def build_index():
    ex = load("executive-summary")
    reqs = load("requirements")["requirements"]
    m = load("method")["method"]
    lb = load("leaderboard")["leaderboard"]

    anchors = "".join(
        f'<div class="card"><h3>Verified anchor</h3><p>{esc(a["anchor"])}</p>'
        f'<p class="src">Source: {src_link(a["source"])}</p></div>'
        for a in ex["verifiedAnchors"]
    )
    status_counts = {}
    for r in reqs:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    status_cards = "".join(
        f'<div class="card"><h3>{esc(k)}</h3><p>{v} requirements</p></div>'
        for k, v in sorted(status_counts.items())
    )
    method_cards = "".join(
        f'<div class="card"><h3>{esc(x["name"])}</h3><p>{esc(x["detail"])}</p>'
        f'<p class="src">Source: {src_link(x["source"])}</p></div>'
        for x in m
    )
    companion = "".join(
        f'<a class="card nav-card" href="{href}"><h3>{esc(label)}</h3><p>{esc(desc)}</p></a>'
        for href, label, desc in COMPANION
    )
    body = f"""
<p>{esc(ex["purpose"])} This structured layer holds the full requirements list, the
method / validation-gate reference, the leaderboard reward design and the source
registry. The companion origination pages hold strategy, correlation, injury,
questions, suggestions, executive summary and flagged detail.</p>
<h2>Verified anchors</h2>
<section class="cards">{anchors}</section>
<h2>Requirements coverage</h2>
<section class="cards">{status_cards}</section>
<p>See the <a href="requirements.html">Requirements</a> page for the full R1–R{len(reqs)} list.</p>
<h2>Method</h2>
<section class="cards">{method_cards}</section>
<h2>Leaderboard</h2>
<p>{esc(lb["rankingMetric"])} Eligibility: {esc(lb["eligibility"])}. See the
<a href="leaderboard.html">Leaderboard</a> page for reward tiers.</p>
<h2>Companion: NFL Lines (origination)</h2>
<p class="note">Built by a parallel session and live on <code>main</code>. This hub links to it so the
NFL Lines area is one coherent section with no duplicated pages.</p>
<section class="cards">{companion}</section>
"""
    return page("NFL Decision Support", "index.html", body,
                "Structured requirements, method, leaderboard design and sources for the NFL Lines work")


def build_requirements():
    reqs = load("requirements")["requirements"]
    rows = [
        [td(r["id"]), td(r["requirement"]), td(r["category"]),
         td_raw(badge(r["priority"])), td_raw(badge(r["status"])), td_raw(src_link(r["source"]))]
        for r in reqs
    ]
    body = ("<p>The full list of requirements extracted from the brief, decomposed into testable items. "
            "Status reflects the current state of the build. Where a requirement rests on a fact, the source "
            "is linked.</p>") + table(
        ["ID", "Requirement", "Category", "Priority", "Status", "Source"], rows
    )
    return page("Requirements", "requirements.html", body)


def build_method():
    m = load("method")["method"]
    rows = [
        [td(x["id"]), td(x["name"]), td(x["detail"]), td_raw(src_link(x["source"]))]
        for x in m
    ]
    body = ("<p>Methodology: validation gates, correlation, luck removal, ranking, line origination, the "
            "injury/roster signal model and the honesty rules. This is the reference the strategies must satisfy.</p>") + table(
        ["ID", "Method", "Detail", "Source"], rows
    )
    return page("Method", "method.html", body)


def build_leaderboard():
    lb = load("leaderboard")["leaderboard"]
    tiers = table(
        ["Tier", "Name", "Criteria"],
        [[td(t["tier"]), td(t["name"]), td(t["criteria"])] for t in lb["rewardTiers"]],
    )

    def kv(label, value):
        return f'<div class="kv"><span class="k">{esc(label)}</span><span class="v">{esc(value)}</span></div>'
    body = f"""
<p>{esc(lb["disclaimer"])}</p>
<div class="kvwrap">
{kv("Ranking metric", lb["rankingMetric"])}
{kv("Eligibility", lb["eligibility"])}
{kv("Tie-break", lb["tieBreak"])}
{kv("Evaluation window", lb["evaluationWindow"])}
</div>
<h2>Reward tiers</h2>{tiers}
<p class="note">Performance is not published until a strategy passes validation gates; ranking cells are intentionally blank and flagged on the companion Flagged page.</p>
"""
    return page("Leaderboard", "leaderboard.html", body, "Competition design")


def build_sources():
    srcs = load("sources")["sources"]
    rows = [
        [td(s["id"]), td(s["name"]), td(s["publisher"]), td(s["type"]),
         td(s["provides"]), td_raw("verified" if s["verified"] else "unverified"),
         td(s["verifiedDate"]),
         td_raw(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["url"])}</a>')]
        for s in srcs
    ]
    body = ("<p>Official, verified source registry. Every value in the NFL Lines area traces to one of these "
            "sources. A value with no matching source is left blank and flagged.</p>") + table(
        ["ID", "Source", "Publisher", "Type", "Provides", "Verification", "Verified", "URL"], rows
    )
    return page("Sources", "sources.html", body)


def main():
    builders = {
        "index.html": build_index,
        "requirements.html": build_requirements,
        "method.html": build_method,
        "leaderboard.html": build_leaderboard,
        "sources.html": build_sources,
    }
    for name, fn in builders.items():
        (NFL / name).write_text(fn(), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
