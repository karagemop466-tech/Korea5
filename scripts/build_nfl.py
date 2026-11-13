#!/usr/bin/env python3
"""Generate the NFL Lines & Strategy hub (nfl/*.html) from nfl/data/*.json.

Self-contained: reads only nfl/data, writes only nfl/*.html and nfl/assets.
Every table row that carries a fact traces to a source link rendered from
nfl/data/sources.json. Blank / unverified values render as "—" and are
published on the Flagged for Review page.
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
    ("executive-summary.html", "Executive Summary"),
    ("requirements.html", "Requirements"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("strategies.html", "Strategies"),
    ("method.html", "Method"),
    ("leaderboard.html", "Leaderboard"),
    ("injuries.html", "Injuries & Roster"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
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
<title>{esc(title)} · NFL Lines &amp; Strategy</title>
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
<p>Built from <code>nfl/data/*.json</code> by <code>scripts/build_nfl.py</code>. Values that cannot be confirmed from an official source are left blank and flagged on the Flagged page.</p>
</footer>
</main>
<script src="assets/app.js"></script>
</body>
</html>
"""


def badge(status):
    return f'<span class="badge">{esc(status)}</span>'


# ---- pages ---------------------------------------------------------------

def build_index():
    ex = load("executive-summary")
    cards = []
    for a in ex["verifiedAnchors"]:
        cards.append(
            f'<div class="card"><h3>Verified anchor</h3>'
            f'<p>{esc(a["anchor"])}</p>'
            f'<p class="src">Source: {src_link(a["source"])}</p></div>'
        )
    nav_cards = "".join(
        f'<a class="card nav-card" href="{href}"><h3>{esc(label)}</h3>'
        f'<p>{esc(DASH[label])}</p></a>'
        for href, label in NAV if label != "Dashboard"
    )
    body = (
        '<section class="cards">' + "".join(cards) + "</section>"
        '<h2>Sections</h2>'
        '<section class="cards">' + nav_cards + "</section>"
    )
    return page("Dashboard", "index.html", body, "NFL Lines & Strategy — a decision-support hub")


DASH = {
    "Executive Summary": "Important details, verified anchors and open gaps in one page.",
    "Requirements": "The full list of requirements (R1–R29) decomposed from the brief.",
    "Questions": "Open questions with a clear have / don't-have inventory.",
    "Suggestions": "Suggestions to improve decisions and discover missing information, for review.",
    "Strategies": "Single bet, parlay and player-prop combination strategy frameworks.",
    "Method": "Validation gates, correlation, luck removal and ranking methodology.",
    "Leaderboard": "Ranking metric, eligibility and reward tiers.",
    "Injuries & Roster": "Starter/backup tracking and defense-deficiency signals.",
    "Sources": "Official, verified source registry.",
    "Flagged": "Irregularities and unverified items, published for review.",
}


def build_executive():
    ex = load("executive-summary")
    anchors = table(
        ["Verified anchor", "Source"],
        [[td(a["anchor"]), td_raw(src_link(a["source"]))] for a in ex["verifiedAnchors"]],
    )
    have = "\n".join(f"<li>{esc(x)}</li>" for x in ex["whatWeHave"])
    dont = "\n".join(f"<li>{esc(x)}</li>" for x in ex["whatWeDontHave"])
    decisions = "\n".join(f"<li>{esc(x)}</li>" for x in ex["keyDecisionsNeeded"])
    body = f"""
<p>{esc(ex["purpose"])}</p>
<h2>Verified anchors</h2>{anchors}
<div class="twocol">
<section><h2>What we have</h2><ul>{have}</ul></section>
<section><h2>What we don't have</h2><ul>{dont}</ul></section>
</div>
<h2>Key decisions needed</h2><ul>{decisions}</ul>
<h2>Method summary</h2><p>{esc(ex["methodSummary"])}</p>
<p class="disclaimer">{esc(ex["disclaimer"])}</p>
"""
    return page("Executive Summary", "executive-summary.html", body)


def build_requirements():
    reqs = load("requirements")["requirements"]
    rows = [
        [td(r["id"]), td(r["requirement"]), td(r["category"]),
         td_raw(badge(r["priority"])), td_raw(badge(r["status"])), td_raw(src_link(r["source"]))]
        for r in reqs
    ]
    body = "<p>The full list of requirements extracted from the brief, decomposed into testable items. Status reflects the current state of the build.</p>" + table(
        ["ID", "Requirement", "Category", "Priority", "Status", "Source"], rows
    )
    return page("Requirements", "requirements.html", body)


def build_questions():
    qs = load("questions")["questions"]
    rows = []
    for q in qs:
        rows.append([
            td(q["id"]), td(q["question"]), td(q["category"]),
            td(q["whatWeHave"]), td(q["whatWeDontHave"]),
            td(q["whyItMatters"]), td(q["suggestedAction"]),
            td_raw(badge(q["priority"])), td_raw(src_link(q["source"])),
        ])
    body = ("<p>Questions that must be answered before any decision, with an explicit inventory of what we "
            "already have and what we do not have. The Suggestions page lists actions to discover the missing "
            "information.</p>") + table(
        ["ID", "Question", "Category", "What we have", "What we don't have", "Why it matters", "Suggested action", "Priority", "Source"],
        rows,
    )
    return page("Questions", "questions.html", body)


def build_suggestions():
    sg = load("suggestions")["suggestions"]
    rows = []
    for s in sg:
        rows.append([
            td(s["id"]), td(s["suggestion"]), td(s["category"]), td(s["rationale"]),
            td(s["expectedOutcome"]), td_raw(badge(s["effort"])), td_raw(badge(s["priority"])),
            td(s["status"]), td(s["relatedQuestions"][0] if s["relatedQuestions"] else ""),
            td_raw(src_link(s["source"])),
        ])
    body = ("<p>Suggestions to improve decision-making and to discover missing information. Each item is "
            "<strong>proposed</strong> for review: a reviewer can approve, reject or choose a path before any "
            "change is implemented.</p>") + table(
        ["ID", "Suggestion", "Category", "Rationale", "Expected outcome", "Effort", "Priority", "Status", "See also", "Source"],
        rows,
    )
    return page("Suggestions", "suggestions.html", body)


def build_strategies():
    st = load("strategies")["strategies"]
    rows = []
    for s in st:
        rows.append([
            td(s["id"]), td(s["name"]), td_raw(badge(s["type"])), td(s["description"]),
            td("; ".join(s["signalsUsed"])), td("; ".join(s["validationGates"])),
            td(s["correlationMethod"]), td(s["skillVsLuck"]), td_raw(badge(s["status"])),
            td_raw(src_link(s["source"])),
        ])
    body = ("<p>Strategy frameworks across single bet, parlay and player-prop combinations. Every strategy must "
            "pass the validation gates before it is eligible. No performance is reported until a strategy passes "
            "validation; those cells are intentionally blank and flagged.</p>") + table(
        ["ID", "Strategy", "Type", "Description", "Signals used", "Validation gates", "Correlation method", "Skill vs luck", "Status", "Source"],
        rows,
    )
    return page("Strategies", "strategies.html", body)


def build_method():
    m = load("method")["method"]
    rows = [
        [td(x["id"]), td(x["name"]), td(x["detail"]), td_raw(src_link(x["source"]))]
        for x in m
    ]
    body = "<p>Methodology: validation gates, correlation, luck removal, ranking and the honesty rules.</p>" + table(
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
<p class="note">Performance is not published until a strategy passes validation gates; ranking cells are intentionally blank and flagged.</p>
"""
    return page("Leaderboard", "leaderboard.html", body, "Competition design")


def build_injuries():
    inj = load("injuries")
    model = table(
        ["ID", "Signal", "Detail", "Source"],
        [[td(x["id"]), td(x["name"]), td(x["detail"]), td_raw(src_link(x["source"]))] for x in inj["signalModel"]],
    )
    rows = []
    for r in inj["exampleRows"]:
        rows.append([
            td(r["team"]), td(r["player"]), td(r["position"]), td(r["injury"]),
            td(r["practiceStatus"]), td(r["gameStatus"]), td(r["depthNote"]),
            td_raw("verified"), td_raw(src_link(r["source"])),
        ])
    body = ("<p>Starter/backup tracking for offense and defense, plus verified example rows from the official "
            "NFL Injury Report (Week 10, 2026). Depth strings must be confirmed against official team/league "
            "sources; third-party aggregators are leads only.</p>") + model + "<h2>Verified example rows (Week 10, 2026)</h2>" + table(
        ["Team", "Player", "Position", "Injury", "Practice status", "Game status", "Depth note", "Verification", "Source"],
        rows,
    )
    return page("Injuries & Roster", "injuries.html", body)


def build_sources():
    srcs = load("sources")["sources"]
    rows = [
        [td(s["id"]), td(s["name"]), td(s["publisher"]), td(s["type"]),
         td(s["provides"]), td_raw("verified" if s["verified"] else "unverified"),
         td(s["verifiedDate"]),
         td_raw(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["url"])}</a>')]
        for s in srcs
    ]
    body = ("<p>Official, verified source registry. Every value on the site traces to one of these sources. "
            "A value with no matching source is left blank and flagged.</p>") + table(
        ["ID", "Source", "Publisher", "Type", "Provides", "Verification", "Verified", "URL"], rows
    )
    return page("Sources", "sources.html", body)


def build_flagged():
    fl = load("flags")["flags"]
    rows = [
        [td(f["id"]), td(f["item"]), td(f["category"]), td(f["detail"]),
         td_raw(badge(f["status"])), td_raw(src_link(f["source"])), td(f["note"])]
        for f in fl
    ]
    body = ("<p>Irregularities and unverified items, published for review. These do not block deployment. "
            "Every flag carries the relevant source link where one exists.</p>") + table(
        ["ID", "Item", "Category", "Detail", "Status", "Source", "Note"], rows
    )
    return page("Flagged", "flagged.html", body)


def main():
    builders = {
        "index.html": build_index,
        "executive-summary.html": build_executive,
        "requirements.html": build_requirements,
        "questions.html": build_questions,
        "suggestions.html": build_suggestions,
        "strategies.html": build_strategies,
        "method.html": build_method,
        "leaderboard.html": build_leaderboard,
        "injuries.html": build_injuries,
        "sources.html": build_sources,
        "flagged.html": build_flagged,
    }
    for name, fn in builders.items():
        (NFL / name).write_text(fn(), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
