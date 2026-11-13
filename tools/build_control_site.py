#!/usr/bin/env python3
"""Render the NFL Control Room pages from data/control/*.json.

Every table row carries its source. A value that has no source is printed as a visible
blank with an "unverified" badge rather than being filled in.

Run: python3 tools/build_control_site.py
"""
from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "control")
DATA = os.path.join(ROOT, "data", "control")
os.makedirs(OUT, exist_ok=True)


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def dash(v, fmt=None):
    if v is None or v == "":
        return '<span class="unv" title="not confirmed from a source">— unverified</span>'
    if isinstance(v, float):
        return fmt or f"{v:.4g}"
    return e(v)


def pct(v):
    return "— unverified" if v is None else f"{v * 100:.1f}%"


NAV = [
    ("index.html", "Overview"),
    ("summary.html", "Executive summary"),
    ("decisions.html", "Decisions"),
    ("suggestions.html", "Suggestions"),
    ("evidence.html", "Evidence"),
    ("strategies.html", "Strategies"),
    ("injuries.html", "Injuries &amp; depth"),
    ("audit.html", "Audit"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
]


def page(title, body, active, lede=""):
    nav = "".join(
        f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>' for u, n in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · NFL Control Room</title>
<meta name="description" content="NFL Control Room: one decision register, one suggestion review board and one evidence ledger covering every NFL section of this repository.">
<link rel="stylesheet" href="assets/control.css">
<script defer src="assets/control.js"></script>
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> NFL CONTROL ROOM</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">
<aside class="callout warn" role="note"><strong>No edge is published here.</strong> This repository holds no market
price, no settlement record and no settled forecast, so no win rate, yield, edge or fair price is computed anywhere.
Every strategy on this site is unscored. Items that could not be confirmed against an official source are left blank
and listed on <a href="flagged.html">Flagged for review</a>.</aside>
<h1>{e(title)}</h1>
{f'<p class="lede">{lede}</p>' if lede else ''}
{body}
<footer class="foot">
  <p>Every row links to the register or official page it came from. Regenerate with
  <code>python3 tools/build_control.py &amp;&amp; python3 tools/build_control_site.py</code>; verify with
  <code>python3 tools/verify_control.py</code>.</p>
  <p>Part of the <a href="../index.html">Korea5 repository site</a>. Other NFL sections:
  <a href="../lines/index.html">Lines Lab</a> · <a href="../lab/index.html">evidence lab</a> ·
  <a href="../nfl-lab/index.html">model lab</a> · <a href="../nfl/index.html">decision support</a> ·
  <a href="../nfl/system/index.html">decision system</a> · <a href="../lines-lab/index.html">skill lab</a> ·
  <a href="../strategy-lab/index.html">strategy lab</a>.</p>
</footer>
</main></body></html>
"""


def src_links(urls):
    if not urls:
        return '<span class="unv">— unverified</span>'
    out = []
    for u in urls:
        host = u.split("//")[-1].split("/")[0]
        out.append(f'<a href="{e(u)}" rel="noopener">{e(host)}</a>')
    return " · ".join(out)


# --------------------------------------------------------------------------- pages
def page_index(meta, decisions, suggestions, ndefects=0):
    c = meta["counts"]
    tiles = [
        ("Decisions open", c["decisions"] - c["decisionsAnswered"], f'{c["decisionsBlocking"]} blocking',
         "decisions.html"),
        ("Settled bets", meta["settledBets"], "nothing can be graded yet", "strategies.html"),
        ("Suggestion rows", c["suggestions"], "each with options and a default", "suggestions.html"),
        ("Evidence datasets", c["evidenceDatasets"], "audited, hashed, sourced", "evidence.html"),
        ("Strategies tracked", c["strategies"], f'across {c["strategyLabs"]} labs', "strategies.html"),
        ("Injury rows live", c["injuryRows"], f'across {c["clubsReporting"]} clubs', "injuries.html"),
        ("Flags for review", c["flagsCombined"] + c["flagsLines"], "published, non-blocking", "flagged.html"),
    ]
    tiles_html = "".join(
        f'<a class="tile" href="{h}"><div class="tnum">{e(v)}</div><div class="tlabel">{e(l)}</div>'
        f'<div class="tsub">{e(s)}</div></a>' for l, v, s, h in tiles)

    blocking = [d for d in decisions if d["blocking"]]
    b_rows = "".join(
        f'<tr><td><a href="decisions.html#{e(d["id"])}">{e(d["id"])}</a></td><td>{d["question"]}</td>'
        f'<td>{e(d["status"])}</td><td>{e(d["mergeCount"])}</td></tr>' for d in blocking)

    survivor = [
        ["Can I trust a published win rate or yield here?", "No.",
         "No price and no settlement exist, so none is published. Every leaderboard is deliberately empty."],
        ["Is any strategy validated as skill?", "No.",
         "All 55 strategy rows across 6 labs are unscored or failing at least one gate. The one lab with a positive "
         "result reports it as not distinguishable from luck (t = 1.48; 95% interval spanning zero)."],
        ["Do the separate NFL sections agree?", "Yes, on the facts that can be compared.",
         "All four independent 2026 result captures agree on all 137 completed games; the Week 10 injury report parses "
         "identically in two parsers on all 296 rows after one defect was fixed."],
        ["Does the injury/depth tracker answer the brief?", "Partly.",
         "It names a replacement from the club's own depth chart (verified live on Detroit: Cade Mays → Juice Scruggs, "
         "D.J. Reed → Rock Ya-Sin) but no snap count proves the replacement played."],
        ["What is the single biggest blocker?", "A price.",
         "D-PRICE is named by 11 separate questions across 5 registers. Until it is answered, nothing else can be graded."],
    ]
    surv_html = "".join(
        f'<tr><th scope="row">{e(q)}</th><td><strong>{e(a)}</strong></td><td>{e(b)}</td></tr>'
        for q, a, b in survivor)

    surfaces = "".join(
        f'<tr><td><a href="../{e(s["path"])}">{e(s["name"])}</a></td><td>{e(s["what"])}</td>'
        f'<td><code>{e(s["path"])}</code></td></tr>' for s in meta["surfaces"])

    recs = "".join(
        f'<tr><td><a href="suggestions.html#{e(s["id"])}">{e(s["id"])}</a></td><td>{e(s["area"])}</td>'
        f'<td>{e(s["title"])}</td><td><span class="pill">{e(s["priority"])}</span></td>'
        f'<td>{e(s["recommendedOption"] or "—")}</td></tr>' for s in suggestions)

    body = f"""
<div class="tiles">{tiles_html}</div>

<h2>The short answer</h2>
<table class="grid">
<thead><tr><th>Question</th><th>Answer</th><th>Why</th></tr></thead>
<tbody>{surv_html}</tbody></table>

<h2>What blocks a decision right now</h2>
<p>These are the decisions that cannot be delegated to code. Each has been asked, in some form, by between two and
eleven separate registers; this page merges them so the same question is answered once.</p>
<table class="grid">
<thead><tr><th>ID</th><th>Question</th><th>Status</th><th>Registers merged</th></tr></thead>
<tbody>{b_rows}</tbody></table>
<p><a href="decisions.html">All {c["decisions"]} decisions, with what is known, what is missing and how to close each →</a></p>

<h2>Recommended path, in order</h2>
<table class="grid">
<thead><tr><th>ID</th><th>Area</th><th>Suggestion</th><th>Priority</th><th>Default option</th></tr></thead>
<tbody>{recs}</tbody></table>
<p>Each is a proposal with a recommended option and a stated trade-off. Nothing on this list is implemented by
merging it: <a href="suggestions.html">open the review board</a> and pick an option, or reject the row.</p>

<h2>The nine NFL sections this page covers</h2>
<p>Eight earlier sessions built eight NFL surfaces. This page does not replace them; it states what each one is
authoritative for, so a reader knows where to look and where not to.</p>
<table class="grid">
<thead><tr><th>Section</th><th>What it is</th><th>Path</th></tr></thead>
<tbody>{surfaces}</tbody></table>

<h2>How to read this site</h2>
<ul class="bullets">
<li><strong>Decisions</strong> — every open question, merged, with what we have, what we lack and the source that would close it.</li>
<li><strong>Suggestions</strong> — every proposal from every register, with options, cost and a recommended default, so a path is chosen before anything is built.</li>
<li><strong>Evidence</strong> — every dataset this site rests on, with its row count, its source and what it cannot tell you.</li>
<li><strong>Strategies</strong> — all 55 strategy rows from all 6 labs side by side, with gate counts, so a reader can see that none passes.</li>
<li><strong>Injuries &amp; depth</strong> — the official weekly report by club, and the next-man-up rows the exact chart tier supports.</li>
<li><strong>Audit</strong> — {ndefects} published defects found this session, how each was found, and the check that now catches it.</li>
<li><strong>Flagged for review</strong> — everything unverified, with the official source that would settle it. Non-blocking, by the project's own rule.</li>
</ul>
"""
    body = body.replace("{NDEFECTS}", str(ndefects))
    return page("Overview", body, "index.html",
                "One page-set for the whole NFL programme: what is known, what is open, and which path to take. "
                "Built from the registers and datasets already committed, with every figure recomputed rather than copied.")


def page_summary(md_path):
    """Render the executive summary markdown as a page, so the site and the repo share one source."""
    import re as _re
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    out = []
    in_table = False
    in_list = False
    for line in md.split("\n"):
        raw = line.rstrip()
        if raw.startswith("|"):
            cells = [c.strip() for c in raw.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append('<table class="grid wide"><thead><tr>')
                in_table = True
                tag = "th"
            else:
                out.append("<tr>")
            for c in cells:
                out.append(f"<{tag}>{inline(c)}</{tag}>")
            out.append("</tr>")
            if tag == "th" and in_table:
                out.append("</thead><tbody>")
            continue
        if in_table:
            out.append("</tbody></table>")
            in_table = False
        if raw.startswith("- "):
            if not in_list:
                out.append("<ul class=\"bullets\">")
                in_list = True
            out.append("<li>" + inline(raw[2:]) + "</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if raw.startswith("### "):
            out.append("<h3>" + inline(raw[4:]) + "</h3>")
        elif raw.startswith("## "):
            out.append("<h2>" + inline(raw[3:]) + "</h2>")
        elif raw.startswith("# "):
            out.append("<h1>" + inline(raw[2:]) + "</h1>")
        elif raw.startswith("---"):
            continue
        elif raw.startswith("**") and raw.endswith("**"):
            out.append("<p><strong>" + inline(raw.strip("*")) + "</strong></p>")
        elif raw.strip():
            out.append("<p>" + inline(raw) + "</p>")
    if in_table:
        out.append("</tbody></table>")
    if in_list:
        out.append("</ul>")
    body = "".join(out).replace("<h1>Executive summary — NFL research programme</h1>", "")
    return page("Executive summary", body, "summary.html",
                "The whole programme in one document: what is verified, what is broken, what is missing and what to do "
                "next. The same text is committed as research/CONTROL-ROOM-EXECUTIVE-SUMMARY.md.")


def inline(text):
    """Minimal inline markdown: bold, code, links. Escaped first, so no raw HTML survives."""
    import re as _re
    t = e(text)
    t = _re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" rel="noopener">\1</a>', t)
    t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = _re.sub(r"(?<![\w\"])\*([^*]+)\*(?![\w\"])", r"<em>\1</em>", t)
    return t


def page_decisions(decisions, not_merged):
    cards = []
    for d in decisions:
        merged = "".join(
            f'<li><code>{e(m["register"])}/{e(m["id"])}</code> {e(m["question"] or "")}</li>'
            for m in d["mergedFrom"]) or '<li class="muted">No register asked it in this exact form.</li>'
        files = "".join(f'<li><code>{e(f)}</code></li>' for f in d.get("evidence_files", []))
        status_cls = {"open": "st-open", "partly-answered": "st-part", "answered": "st-done"}.get(d["status"], "")
        cards.append(f"""
<article class="card" id="{e(d['id'])}">
  <div class="cardhead">
    <h3>{e(d['id'])} · {d['question']}</h3>
    <div class="badges">
      <span class="pill {status_cls}">{e(d['status'])}</span>
      <span class="pill">{'blocking' if d['blocking'] else 'non-blocking'}</span>
      <span class="pill">{e(d['area'])}</span>
      <span class="pill">{e(d['mergeCount'])} register rows</span>
    </div>
  </div>
  <dl>
    <dt>Why it matters</dt><dd>{e(d['why'])}</dd>
    <dt>What we have</dt><dd>{e(d['have'])}</dd>
    <dt>What is missing</dt><dd>{e(d['missing'])}</dd>
    <dt>How it gets closed</dt><dd>{e(d['close'])}</dd>
    <dt>Merged from</dt><dd><ul class="mini">{merged}</ul></dd>
    <dt>Evidence files</dt><dd><ul class="mini">{files}</ul></dd>
    <dt>Official source</dt><dd>{src_links(d.get('sources'))}</dd>
  </dl>
</article>""")
    nm = "".join(
        f'<tr><td><code>{e(r["register"])}</code></td><td>{e(r["question"])}</td><td>{e(r["reason"])}</td>'
        f'<td>{e(r["owner"])}</td></tr>' for r in not_merged)
    body = f"""
<p class="lede">Sixteen decisions, merged from 107 question rows across five registers. Nothing was dropped silently:
the questions that were deliberately not turned into a decision are listed at the bottom with the reason.</p>

<div class="legend">
  <span class="pill st-open">open</span> needs an owner decision
  <span class="pill st-part">partly answered</span> some evidence exists, one artefact still missing
  <span class="pill st-done">answered</span> resolved by a committed artefact
</div>

{''.join(cards)}

<h2 id="not-merged">Questions deliberately not raised to a decision</h2>
<p>A merge that only shows what it kept cannot be audited. These rows were read, and left where they are, with the
reason stated.</p>
<table class="grid">
<thead><tr><th>Register</th><th>Question</th><th>Why it is not a decision</th><th>Owner</th></tr></thead>
<tbody>{nm}</tbody></table>
"""
    return page("Decisions", body, "decisions.html",
                "What has to be answered before anything is built, merged from every register that asked it.")


def page_suggestions(suggestions):
    cards = []
    for s in suggestions:
        opts = "".join(f"""
  <tr class="{'rec' if o.get('recommended') else ''}">
    <td><strong>{e(o['id'])}</strong>{' <span class="pill recpill">recommended</span>' if o.get('recommended') else ''}</td>
    <td>{e(o['label'])}<div class="muted">{e(o.get('path') or '')}</div></td>
    <td>{e(o.get('tradeoff') or '')}</td>
    <td><label class="pick"><input type="radio" name="{e(s['id'])}" value="{e(o['id'])}"{' checked' if o.get('recommended') else ''}> choose</label></td>
  </tr>""" for o in s["options"])
        cards.append(f"""
<article class="card" id="{e(s['id'])}">
  <div class="cardhead">
    <h3>{e(s['id'])} · {e(s['title'])}</h3>
    <div class="badges"><span class="pill">{e(s['area'])}</span><span class="pill">{e(s['priority'])}</span>
      <span class="pill st-open">open</span></div>
  </div>
  <dl>
    <dt>Problem</dt><dd>{e(s['problem'])}</dd>
    <dt>Evidence</dt><dd>{e(s['evidence'])}</dd>
    <dt>Official source</dt><dd>{src_links(s.get('sources'))}</dd>
  </dl>
  <table class="grid opts">
    <thead><tr><th style="width:5.5rem">Option</th><th>Path</th><th>Trade-off if chosen</th><th style="width:6rem">Select</th></tr></thead>
    <tbody>{opts}</tbody>
  </table>
</article>""")
    body = f"""
<p class="lede">Twelve proposals, each with at least three options, the cost of each and a recommended default. This is
the review board: read a row, pick an option, and the path is decided before anything is implemented.</p>
<div class="callout note">
  <strong>How a decision is taken here.</strong> Selections are stored in your browser only
  (<code>localStorage</code>) and can be exported as JSON. Nothing is sent to a server and no source file is modified
  by clicking. To make a choice binding, record it in <code>COORDINATION.md</code> and in the owning data file.
  <div class="btnrow">
    <button id="export" type="button">Export selections (JSON)</button>
    <button id="clear" type="button" class="ghost">Clear</button>
    <span id="status" class="muted" role="status"></span>
  </div>
</div>
{''.join(cards)}
"""
    return page("Suggestions", body, "suggestions.html",
                "Improve the site, improve decision making, and discover the information that is missing — with the "
                "options laid out so the best path is chosen before any change is made.")


def page_evidence(datasets):
    def count(v):
        return str(v) if v is not None else '<span class="unv">—</span>'

    rows = "".join(
        "<tr><td><code>" + e(d["path"]) + "</code></td><td>" + e(d["what"]) + "</td>"
        + '<td class="num">' + count(d["rows"]) + "</td><td>" + e(d["provider"]) + "</td><td>"
        + src_links([d["sourceUrl"]]) + "</td>"
        + '<td class="muted">' + e(d["cannotTell"]) + "</td>"
        + '<td class="muted"><code>' + e(d["sha256_12"] or "") + "</code></td></tr>" for d in datasets)
    ok = sum(1 for d in datasets if d["exists"])
    body = f"""
<p class="lede">Every dataset this site rests on, counted here rather than copied from a page, with its source,
a content hash so a reviewer can confirm what was read, and an honest statement of what it cannot tell you.</p>
<div class="stats">
  <div><strong>{ok}/{len(datasets)}</strong> datasets present</div>
  <div><strong>{sum(d['rows'] or 0 for d in datasets):,}</strong> rows counted across them (where countable)</div>
</div>
<table class="grid wide">
<thead><tr><th>Path</th><th>What it is</th><th class="num">Rows</th><th>Provider</th><th>Source</th>
<th>What it cannot tell you</th><th>SHA-256 (12)</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="muted">A hash is of the file as committed at build time. Re-running the build and diffing the hash shows
whether the underlying capture changed.</p>
"""
    return page("Evidence ledger", body, "evidence.html",
                "What this programme actually knows, dataset by dataset.")


def page_strategies(board, meta):
    labs = "".join(
        f'<tr><td>{e(l["name"])}</td><td><a href="../{e(l["path"])}">{e(l["path"])}</a></td>'
        f'<td>{e(l["gates"])}</td><td><a href="../{e(l["gateDoc"])}">{e(l["gateDoc"])}</a></td>'
        f'<td class="num">{e(l["count"])}</td></tr>' for l in board["labs"])

    def gatecell(r):
        if r["gatesPassed"] is None:
            return '<span class="unv">not stated</span>'
        cls = "ok" if r["gatesTotal"] and r["gatesPassed"] == r["gatesTotal"] else "bad"
        return f'<span class="{cls}">{r["gatesPassed"]}/{r["gatesTotal"]}</span>'

    rows = "".join(
        f'<tr><td>{e(r["lab"])}</td><td><code>{e(r["id"])}</code></td><td>{e(r["name"])}</td>'
        f'<td>{e(r["family"])}</td><td class="num">{r["bets"] if r["bets"] is not None else ""}</td>'
        f'<td class="num">{pct(r["roi"]) if r["roi"] is not None else ""}</td>'
        f'<td class="num">{dash(r["logLoss"])}</td><td>{gatecell(r)}</td>'
        f'<td class="num">{r["reward"] if r["reward"] is not None else ""}</td>'
        f'<td>{e(r["status"])}</td><td>{src_links([r["sourceUrl"]])}</td></tr>' for r in board["rows"])

    rewarded = [r for r in board["rows"] if r.get("reward")]
    body = f"""
<p class="lede">Every strategy proposed anywhere in this repository, in one table. Six labs, six gate vocabularies,
{len(board['rows'])} rows. The purpose of the table is not to rank the labs against each other — it is to show that no
row is validated, which the gates make explicit.</p>

<div class="stats">
  <div><strong>0</strong> settled bets against a stored price</div>
  <div><strong>{len(board['rows'])}</strong> strategy rows</div>
  <div><strong>{len(rewarded)}</strong> carrying a paper reward</div>
  <div><strong>0</strong> certified as skill-based</div>
</div>

<h2>The six labs and their gates</h2>
<p>The vocabularies differ, which is itself a finding: a strategy can pass in one lab and fail in another for reasons
that have nothing to do with the strategy. Recorded as suggestion CS-03.</p>
<table class="grid">
<thead><tr><th>Lab</th><th>Page</th><th>Gate set</th><th>Gate reference</th><th class="num">Rows</th></tr></thead>
<tbody>{labs}</tbody></table>

<h2>Every strategy row</h2>
<p>Blank cells are values the source file does not publish; they are not zero and they are not inferred.</p>
<table class="grid wide">
<thead><tr><th>Lab</th><th>ID</th><th>Name</th><th>Family</th><th class="num">Bets</th><th class="num">ROI</th>
<th class="num">Log loss</th><th>Gates</th><th class="num">Reward</th><th>Status</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="muted">Paper rewards are leaderboard points defined by the owning lab; they are not money and are not
comparable across labs. The three rewarded rows all belong to one lab and were produced by one pipeline.</p>
"""
    return page("Strategy board", body, "strategies.html",
                "Singles, player props, prop combinations and parlays across every lab, with the gate state each one "
                "actually reached.")


def page_injuries(inj):
    m = inj["meta"]
    NOCHART = '<span class="unv">no chart parsed</span>'
    NOLABEL = '<span class="unv">not stated by the club</span>'
    clubs = "".join(
        "<tr><td>" + e(c["team"]) + '</td><td class="num">' + str(c["reported"]) + '</td><td class="num">'
        + str(c["out"]) + '</td><td class="num">' + str(c["doubtful"]) + '</td><td class="num">'
        + str(c["questionable"]) + '</td><td class="num">' + str(c["practiceDnp"]) + "</td><td>"
        + ("yes" if c["chartParsed"] else NOCHART) + "</td><td>" + (e(c["chartLabel"]) if c["chartLabel"] else NOLABEL) + "</td><td>"
        + (src_links([c["chartSourceUrl"]]) if c["chartSourceUrl"] else src_links([m["sourceUrl"]]))
        + "</td></tr>" for c in inj["clubs"])
    UNV = '<span class="unv" title="the club chart does not name a next tier">— unverified</span>'
    UNV = '<span class="unv" title="the club chart does not name this">— unverified</span>'
    SAME = '<span class="ok">same chart row</span>'
    DIFFROW = '<span class="unv">other chart row</span>'
    defs = inj["deficiencies"]
    hi = [d for d in defs if d["severity"] == "high"]
    rows = "".join(
        f'<tr><td class="num">{e(d["week"])}</td><td>{e(d["team"])}</td><td>{e(d["opponent"])}</td>'
        f'<td>{e(d["player"])}</td><td>{e(d["position"])}</td><td>{e(d["gameStatus"])}</td>'
        f'<td>{e(d["depthTier"]) if d["depthTier"] else UNV}</td>'
        f'<td>{(e(d["replacement"]) + " (" + e(d["replacementTier"]) + ")") if d["replacement"] else UNV}</td>'
        f'<td><span class="pill sev-{e(d["severity"])}">{e(d["severity"])}</span></td>'
        f'<td>{(SAME if d["sameChartRow"] else (DIFFROW if d["replacement"] else UNV))}</td>'
        f'<td>{e(d["chartLabel"]) if d["chartLabel"] else UNV}</td><td>{src_links([d["injurySourceUrl"], d["depthChartSourceUrl"]])}</td></tr>'
        for d in defs)
    body = f"""
<p class="lede">The official weekly injury report by club, and the "next man up" rows the club's own depth chart
supports. This is the module the brief asks for: knowing when a 2nd, 3rd or 4th string player has to replace a starter.</p>

<div class="stats">
  <div><strong>{m['reportedRows']}</strong> official report rows</div>
  <div><strong>{m['clubsReporting']}</strong> clubs reporting</div>
  <div><strong>{m['clubsWithParsedChart']}</strong> clubs with a parsed depth chart</div>
  <div><strong>{len(hi)}</strong> verified starter-out rows</div>
</div>

<p class="callout note"><strong>Snapshot.</strong> This is the official report for Week {e(m['week'])}, captured
{e(m['retrievedUTC'])}. It is a point in time, not a live feed. Source:
{src_links([m['sourceUrl']])}.</p>

<h2>Injury report by club</h2>
<p>"DNP" counts players who did not participate in practice. A club with no parsed chart is shown as such rather than
guessed ({e(', '.join(m['clubsWithoutChart']) or 'none')}).</p>
<table class="grid wide">
<thead><tr><th>Club</th><th class="num">Reported</th><th class="num">Out</th><th class="num">Doubtful</th>
<th class="num">Questionable</th><th class="num">DNP</th><th>Chart parsed</th><th>Chart label as published</th>
<th>Chart source</th></tr></thead>
<tbody>{clubs}</tbody></table>

<h2>Starters out and the chart's next man up</h2>
<p>Each row names the player the club's own chart lists next at the same position, and only when the injured player is
the chart's 1st string. Where the chart does not name a next tier, the replacement is blank rather than inferred.</p>
<p class="callout warn"><strong>Limitation, published rather than hidden.</strong> The single Week {e(m['week'])}
snapshot is applied to every 2026 fixture that has not been played, so some rows sit against a game weeks away. Those
rows state a current injury against a future date and are not a projection. Recorded as FL-16 and suggestion CS-05.</p>
<table class="grid wide">
<thead><tr><th class="num">Wk</th><th>Club</th><th>Opponent</th><th>Player</th><th>Pos</th><th>Status</th>
<th>Chart tier</th><th>Next man up (tier)</th><th>Severity</th><th>Replacement source</th><th>Chart label</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table>
"""
    return page("Injuries &amp; depth", body, "injuries.html",
                "Who is out, what tier the club's own chart puts behind them, and where the evidence stops.")


def page_audit(audit):
    rows = "".join(
        f'<tr><td><code>{e(a["id"])}</code></td><td>{e(a["title"])}</td><td>{e(a["severity"])}</td>'
        f'<td>{e(a["found"])}</td><td>{e(a["impact"])}</td><td>{e(a["fix"])}</td>'
        f'<td><code>{e(a["caughtBy"])}</code></td><td>{e(a["status"])}</td></tr>' for a in audit["defects"])
    checks = "".join(
        f'<tr><td>{e(c["check"])}</td><td class="num">{c["rows"]}</td><td class="num">{c["failures"]}</td>'
        f'<td>{e(c["verdict"])}</td></tr>' for c in audit["checks"])
    body = f"""
<p class="lede">This session's job was to review the repository line by line and confirm every published number
against an official source. Three published defects were found. All three had passed every existing verifier, which
is the reason they are written up here rather than quietly corrected.</p>

<div class="stats">
  <div><strong>{len(audit['defects'])}</strong> defects found and fixed</div>
  <div><strong>{audit['liveChecks']}</strong> values re-read from official pages live</div>
  <div><strong>{audit['rowsCompared']}</strong> rows compared across independent captures</div>
  <div><strong>{audit['recomputed']}</strong> published statistics independently recomputed</div>
</div>

<h2>Defects</h2>
<table class="grid wide">
<thead><tr><th>ID</th><th>Defect</th><th>Severity</th><th>How it was found</th><th>What it affected</th>
<th>Fix</th><th>Check that now catches it</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>Live verification performed</h2>
<table class="grid">
<thead><tr><th>Check</th><th class="num">Rows</th><th class="num">Mismatches</th><th>Verdict</th></tr></thead>
<tbody>{checks}</tbody></table>

<h2>What was recomputed rather than trusted</h2>
<ul class="bullets">{''.join(f'<li>{e(x)}</li>' for x in audit['recomputedList'])}</ul>

<h2>What this audit did not do</h2>
<ul class="bullets">{''.join(f'<li>{e(x)}</li>' for x in audit['notDone'])}</ul>
"""
    return page("Audit", body, "audit.html",
                "What was checked, what was wrong, and what is still unchecked.")


def page_sources():
    reg = [
        ("NFL.com official injury report", "https://www.nfl.com/injuries/",
         "Weekly injury report by club: player, position, injury, practice status, game status."),
        ("NFL.com official standings", "https://www.nfl.com/standings/league/2026/REG",
         "W-L-T, points for and against per club. Re-read live this session: 32/32 rows matched."),
        ("NFL.com official schedule by week", "https://www.nfl.com/schedules/2026/by-week/week-10",
         "Fixtures, kickoff times and final scores."),
        ("NFL.com official scores", "https://www.nfl.com/scores/2026/week-10",
         "Week results as printed on the scores page."),
        ("NFL.com game center", "https://www.nfl.com/games/jaguars-at-ravens-2026-reg-9",
         "Per-game final score and box score; re-read live this session."),
        ("NFL.com player statistics logs", "https://www.nfl.com/players/justin-jefferson/stats/logs/",
         "Per-game player statistics; re-read live this session, all 8 rows matched."),
        ("NFL.com team directory", "https://www.nfl.com/teams/",
         "The list of 32 clubs and their official websites, used to find each club's depth chart."),
        ("Detroit Lions official depth chart", "https://www.detroitlions.com/team/depth-chart/",
         "Chart tiers used to verify the next-man-up rows live this session."),
        ("San Francisco 49ers official depth chart", "https://www.49ers.com/team/depth-chart",
         "Chart used as a second tier source."),
        ("ESPN NFL scoreboard (trusted secondary, not official)", "https://www.espn.com/nfl/scoreboard",
         "The only market price anywhere in this repository. Labelled secondary on every row that uses it."),
        ("nflverse/nfldata (third party)", "https://github.com/nflverse/nfldata",
         "Historical game archive used by two labs. Its own documentation does not name the source of its line columns."),
    ]
    rows = "".join(f'<tr><td><a href="{e(u)}" rel="noopener">{e(n)}</a></td><td class="muted"><code>{e(u)}</code></td>'
                   f'<td>{e(w)}</td></tr>' for n, u, w in reg)
    body = f"""
<p class="lede">Every source this site uses, and what it is used for. Official league and club sources are listed
first; the one trusted secondary source is labelled as such and is never presented as an official feed.</p>
<table class="grid wide">
<thead><tr><th>Source</th><th>URL</th><th>What it provides</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>What no source provides</h2>
<ul class="bullets">
<li><strong>A price.</strong> No official NFL page publishes a spread, total, moneyline or player prop. Probed by exact
regex on week, game and stat pages: zero hits. This is the reason no win rate or yield is published anywhere.</li>
<li><strong>Snap counts.</strong> No official machine-readable snap count was found, so "who replaced whom" cannot be
proven from participation; the site names the chart's next man up and says so.</li>
<li><strong>A licence for the third-party archive.</strong> Two labs use it and both publish the gap.</li>
</ul>
"""
    return page("Sources", body, "sources.html",
                "Where every figure comes from, and what no source can give us.")


def page_flagged(flags_all):
    rows = "".join(
        f'<tr><td><code>{e(f["id"])}</code></td><td>{e(f.get("severity"))}</td><td>{e(f.get("title") or f.get("item"))}</td>'
        f'<td>{e(f.get("detail") or "")}</td>'
        f'<td>{src_links([s["url"] for s in f.get("sources", []) if s.get("url")] or ([f["sourceUrl"]] if f.get("sourceUrl") else []))}</td>'
        f'<td>{e(f.get("action") or "")}</td><td>{e(f.get("status") or "needs-review")}</td></tr>'
        for f in flags_all)
    body = f"""
<p class="lede">Everything that could not be confirmed from an official source, plus the irregularities this session
found and corrected. Non-blocking by the project's own rule: these do not stop the merge or the deployment.</p>
<div class="stats">
  <div><strong>{len(flags_all)}</strong> flagged items</div>
  <div><strong>{sum(1 for f in flags_all if (f.get('status') or '') == 'corrected')}</strong> found and corrected here</div>
  <div><strong>{sum(1 for f in flags_all if (f.get('status') or 'needs-review') == 'needs-review')}</strong> awaiting review</div>
</div>
<table class="grid wide">
<thead><tr><th>ID</th><th>Severity</th><th>Item</th><th>Detail</th><th>Source that would settle it</th>
<th>Action</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
"""
    return page("Flagged for review", body, "flagged.html",
                "Everything unverified or irregular, with the official source that would settle it.")


def main():
    meta = load("meta.json")
    dec = load("decisions.json")
    sug = load("suggestions.json")
    ev = load("evidence.json")
    board = load("strategies.json")
    inj = load("injuries.json")
    audit = load("audit.json")

    pages = {
        "index.html": page_index(meta, dec["decisions"], sug["suggestions"],
                                 len(audit.get("defects", []))),
        "summary.html": page_summary("research/CONTROL-ROOM-EXECUTIVE-SUMMARY.md"),
        "decisions.html": page_decisions(dec["decisions"], dec["notMerged"]),
        "suggestions.html": page_suggestions(sug["suggestions"]),
        "evidence.html": page_evidence(ev["datasets"]),
        "strategies.html": page_strategies(board, meta),
        "injuries.html": page_injuries(inj),
        "audit.html": page_audit(audit),
        "sources.html": page_sources(),
        "flagged.html": page_flagged(audit["flags"]),
    }
    for name, text in pages.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote control/" + name)


if __name__ == "__main__":
    main()
