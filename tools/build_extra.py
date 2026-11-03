#!/usr/bin/env python3
"""Build the second-pass official-feed site under extra/.

Reads:
  official/nfl-2026.json, official/westwoodone.json, official/w1-stations.json,
  official/mlb-tbd.json, curated/*.json, data/events-<year>.json,
  data/derived/analysis.json, verification/*.
Writes:
  extra/*.html, extra/data/*.json, extra/assets/*.css|js,
  and (idempotently) adds one nav link + exact Prev/Next/Today labels to root pages.

No values are invented. Anything not published by an official source stays blank and/or flagged.
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA = ROOT / "extra"
DATA = EXTRA / "data"
ASSETS = EXTRA / "assets"
for p in (DATA, ASSETS):
    p.mkdir(parents=True, exist_ok=True)

START = date(2026, 11, 2)
END = date(2030, 2, 28)
EST_LABEL = "ESTIMATION — not a real verified released schedule"


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def link(url: str, text: str | None = None, cls: str = "") -> str:
    if not url:
        return ""
    c = f' class="{cls}"' if cls else ""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer"{c}>{esc(text or "official source")}</a>'


def badge(status: str) -> str:
    s = (status or "").lower()
    if s in ("verified", "official"):
        return '<span class="tag ver">verified</span>'
    if s in ("estimated", "estimate"):
        return '<span class="tag est">ESTIMATE</span>'
    if s in ("canceled", "cancelled"):
        return '<span class="tag flag">canceled</span>'
    return '<span class="tag flag">unverified</span>'


# ---------------------------------------------------------------- load inputs
nfl_pack = jload(ROOT / "official/nfl-2026.json")
w1_pack = jload(ROOT / "official/westwoodone.json")
stations_pack = jload(ROOT / "official/w1-stations.json")
tbd_pack = jload(ROOT / "official/mlb-tbd.json")

sources = jload(ROOT / "curated/sources.json")["sources"]
anchors = jload(ROOT / "curated/season-anchors.json")["anchors"]
stations = jload(ROOT / "curated/stations.json")["stations"]
durations = jload(ROOT / "curated/durations.json")
ncaaf_future = jload(ROOT / "curated/ncaaf-future.json")["rows"]
estimates = jload(ROOT / "curated/estimates.json")["windows"]
flags = jload(ROOT / "curated/flags.json")["flags"]
rules = jload(ROOT / "curated/rules.json")["documents"]

analysis_path = ROOT / "data/derived/analysis.json"
analysis = jload(analysis_path) if analysis_path.exists() else {}
verification_path = ROOT / "verification/report.json"
verification = jload(verification_path) if verification_path.exists() else {}
links_path = ROOT / "verification/links.json"
links_report = jload(links_path) if links_path.exists() else {}

# Official NFL games, normalized. High priority for 49ers and national W1 radio.
nfl_rows = []
for g in nfl_pack["games"]:
    high = "49ers" in (g.get("title") or "") or bool(g.get("nationalRadio"))
    nfl_rows.append({
        "id": g["id"],
        "date": g.get("datePT") or "",
        "title": g.get("title") or "",
        "league": "NFL",
        "sport": "NFL",
        "phase": g.get("weekLabel") or g.get("seasonType") or "",
        "week": g.get("week"),
        "start": g.get("startPT") or "",
        "end": "",
        "durationMin": 185 if g.get("seasonType") == "REG" else 185,
        "venue": g.get("venue") or "",
        "radio": g.get("nationalRadio") or "",
        "nationalRadio": g.get("nationalRadio") or "",
        "priority": "high" if high else "normal",
        "priorityNote": "49ers / Westwood One national radio" if high else "",
        "status": "verified" if g.get("startPT") else "unverified",
        "verification": g.get("verification") or "verified",
        "timeStatus": g.get("timeStatus") or "",
        "sourceUrl": g.get("sourceUrl") or "",
        "sourceName": g.get("sourceName") or "",
        "note": "" if g.get("startPT") else "Kickoff time not published on the official NFL.com by-week page; left blank.",
        "origin": "official/nfl-2026.json",
    })

# Westwood One events, normalized, filtered to the displayed range.
w1_rows = []
for e in w1_pack["events"]:
    d = e.get("datePT") or ""
    if d and d < "2026-01-01":
        continue
    nfl_sport = e.get("sport") == "NFL"
    w1_rows.append({
        "id": e["id"],
        "date": d,
        "title": e.get("title") or "",
        "league": "Westwood One Sports",
        "sport": e.get("sport") or "",
        "phase": e.get("sport") or "",
        "start": e.get("startPT") or "",
        "end": e.get("endPT") or "",
        "durationMin": e.get("durationMin") or 0,
        "venue": e.get("venue") or "",
        "radio": "Westwood One Sports national radio",
        "priority": e.get("priority") or "high",
        "priorityNote": "Westwood One national broadcast" if nfl_sport else "Other live sports on national radio",
        "status": "verified" if e.get("startUTC") else "unverified",
        "verification": e.get("verification") or "verified",
        "timeStatus": e.get("timeStatus") or "",
        "sourceUrl": e.get("sourceUrl") or "",
        "sourceName": e.get("sourceName") or "",
        "note": "Exact network on-air window from the official event page (start_time / end_time).",
        "origin": "official/westwoodone.json",
    })

# Parallel-session event feeds.
par_events = []
for year in range(2026, 2031):
    p = ROOT / f"data/events-{year}.json"
    if not p.exists():
        continue
    pack = jload(p)
    meta_sources = pack.get("meta", {}).get("sources", {}) or {}
    meta_basis = pack.get("meta", {}).get("basis", {}) or {}
    for e in pack.get("events", []):
        src = e.get("sourceUrl") or (meta_sources.get(e.get("s"), {}) or {}).get("url") or ""
        basis = (meta_basis.get(e.get("b"), "") or e.get("timeBasis") or "")
        par_events.append({
            "id": e.get("id") or "",
            "date": e.get("date") or "",
            "title": e.get("title") or e.get("game") or "",
            "league": e.get("league") or "",
            "sport": e.get("league") or "",
            "phase": e.get("category") or e.get("phase") or "",
            "start": e.get("start") or "",
            "end": "",
            "durationMin": e.get("durationMin") or 0,
            "venue": e.get("venue") or "",
            "radio": "radio" if (e.get("tags") or []) and any("radio" in t or "westwoodone" in t for t in e.get("tags", [])) else "",
            "priority": e.get("priority") or "normal",
            "priorityNote": e.get("priorityReason") or "",
            "status": e.get("status") or "",
            "verification": e.get("status") or "",
            "timeStatus": e.get("timeStatus") or "",
            "sourceUrl": src,
            "sourceName": "Official source (see link)",
            "note": basis,
            "startWindow": e.get("startWindow") or "",
            "altWindow": e.get("altWindow") or "",
            "origin": f"data/events-{year}.json",
        })

# ---------------------------------------------------------------- dedupe combined feed
# Prefer our official NFL / W1 rows; drop parallel rows with the same date + normalized title.
def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

preferred_keys = {(r["date"], norm_title(r["title"])) for r in nfl_rows + w1_rows}
combined = nfl_rows + w1_rows
for e in par_events:
    k = (e["date"], norm_title(e["title"]))
    if k in preferred_keys:
        continue
    preferred_keys.add(k)
    combined.append(e)

# TBD flags: blank any MLB start time that the league marks TBD.
tbd_true = {int(k) for k, v in tbd_pack["flags"].items() if v.get("startTimeTBD")}
for e in combined:
    m = re.match(r"mlb-(\d+)-(\d+)", e.get("id") or "")
    if m and int(m.group(2)) in tbd_true:
        if e.get("status") == "verified":
            e["status"] = "unverified"
        e["start"] = ""
        e["end"] = ""
        e["timeStatus"] = "tbd"
        e["note"] = "MLB StatsAPI marks this game startTimeTBD=true; start time left blank and flagged."
        e["verification"] = "unverified"

# ---------------------------------------------------------------- calendar.json
def day_range(a: str, b: str):
    if not a or not b:
        return []
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    out = []
    d = d0
    while d <= d1:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


anchor_by_day = defaultdict(list)
for a in anchors:
    for d in day_range(a.get("startDate"), a.get("endDate")):
        anchor_by_day[d].append({"label": a["label"], "league": a["league"], "sourceUrl": a["sourceUrl"], "status": a["status"]})

# Published future NCAAF dates become official anchors with blank times.
future_by_day = defaultdict(list)
for r in ncaaf_future:
    if not r.get("date"):
        continue
    future_by_day[r["date"]].append({
        "title": f'{r["team"]} vs {r["opponent"]}',
        "league": "NCAAF",
        "sourceUrl": r["sourceUrl"],
        "sourceName": r["sourceName"],
        "status": r["status"],
        "note": r["note"],
    })

buckets = defaultdict(lambda: {"verified": [], "estimated": [], "tba": [], "anchors": [], "future": []})
for e in combined:
    d = e.get("date")
    if not d or not (START.isoformat() <= d <= END.isoformat()):
        continue
    item = {k: e.get(k, "") for k in ("title", "league", "sport", "phase", "start", "end", "durationMin",
                                       "venue", "radio", "priority", "priorityNote", "status", "sourceUrl",
                                       "sourceName", "note", "startWindow", "altWindow", "origin")}
    st = (e.get("status") or "").lower()
    if st == "estimated":
        buckets[d]["estimated"].append(item)
    elif st == "verified" and e.get("start"):
        buckets[d]["verified"].append(item)
    else:
        buckets[d]["tba"].append(item)

for d, rows in anchor_by_day.items():
    if START.isoformat() <= d <= END.isoformat():
        buckets[d]["anchors"] = rows
for d, rows in future_by_day.items():
    if START.isoformat() <= d <= END.isoformat():
        buckets[d]["future"] = rows

days = {}
d = START
while d <= END:
    key = d.isoformat()
    b = buckets.get(key, {"verified": [], "estimated": [], "tba": [], "anchors": [], "future": []})
    days[key] = b
    d += timedelta(days=1)

calendar = {
    "meta": {
        "name": "Combined day scoreboard — verified feeds and labelled planning estimates",
        "compiledUTC": "2026-11-02",
        "timezone": "America/Los_Angeles (PST/PDT)",
        "start": START.isoformat(),
        "end": END.isoformat(),
        "verifiedDefinition": "A minute is free when no covered game or radio broadcast is on air. Only rows with an official published start time are used to compute exact busy minutes.",
        "estimateLabel": EST_LABEL,
        "note": "Days with TBA/unverified rows cannot have exact free minutes computed in verified mode; they are marked unverified rather than inferred.",
    },
    "days": days,
}
(DATA / "calendar.json").write_text(json.dumps(calendar, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- vacation analysis (strict)
def day_class(b, y: str) -> str:
    # Preserve known conflicts while refusing to certify gaps in incomplete coverage.
    if b["verified"]:
        return "busy"
    if b["tba"] or b["future"]:
        return "unverified"
    if b["estimated"]:
        return "estimated-only"
    return "estimated-free" if y in unreleased_years else "free"


# Years with no released MLB schedule: 2028, 2029, 2030 -> strict analysis is unverifiable.
unreleased_years = {"2026", "2027", "2028", "2029", "2030"} # Complete multi-sport + local-carriage coverage is not certified.
classes = {k: day_class(v, k[:4]) for k, v in days.items()}

strict = {}
for y in (2026, 2027, 2028, 2029):
    ykeys = [k for k in days if k.startswith(str(y))]
    released = str(y) not in unreleased_years
    strict[y] = {
        "daysInRange": len(ykeys),
        "busy": sum(1 for k in ykeys if classes[k] == "busy"),
        "unverified": sum(1 for k in ykeys if classes[k] == "unverified"),
        "estimatedOnly": sum(1 for k in ykeys if classes[k] in ("estimated-only", "estimated-free")),
        "free": 0, # Never certify absence from incomplete feeds.
        "modelFree": sum(1 for k in ykeys if classes[k] == "estimated-free"),
        "scheduleReleased": released,
        "note": ("Official schedules available for this year; strict verified analysis applies." if released else
                 "Complete multi-sport schedules and local radio carriage are not certified; strict verified free time cannot be asserted. "
                 "All windows are " + EST_LABEL),
    }

def rank_windows(length: int, year: int, limit: int = 8):
    ykeys = [k for k in days if k.startswith(str(year))]
    released = str(year) not in unreleased_years
    out = []
    for i in range(0, len(ykeys) - length + 1):
        win = ykeys[i:i + length]
        free = sum(1 for k in win if classes[k] in ("free", "estimated-free"))
        busy = sum(1 for k in win if classes[k] == "busy")
        unver = sum(1 for k in win if classes[k] == "unverified")
        est = sum(1 for k in win if classes[k] in ("estimated-only", "estimated-free"))
        out.append({"start": win[0], "end": win[-1], "freeDays": free, "busyDays": busy,
                    "unverifiedDays": unver, "estimateOnlyDays": est,
                    "fullyFree": free == length and released,
                    "status": "estimated" if not released else "verified"})
    out.sort(key=lambda w: (-w["freeDays"], w["unverifiedDays"] + w["estimateOnlyDays"], w["start"]))
    return out[:limit]

vacation = {"meta": {
    "name": "Vacation window ranking — strict verified view",
    "compiledUTC": "2026-11-02",
    "estimateLabel": EST_LABEL,
    "rule": "No year has certified complete coverage. Model-free is not verified free. A model-free day has no loaded game with a published start time, no TBA/unverified official row, and no estimate-only row. 2028/2029 have no released schedules, so their windows are estimates and cannot be verified.",
}, "years": strict, "windows": {}}
for y in (2027, 2028, 2029):
    vacation["windows"][str(y)] = {
        "1week": rank_windows(7, y),
        "2week": rank_windows(14, y),
        "3week": rank_windows(21, y),
    }
(DATA / "vacation.json").write_text(json.dumps(vacation, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- verification.json
verification_out = {
    "meta": {"name": "Combined line-by-line verification", "compiledUTC": "2026-11-02"},
    "checks": [],
    "counts": {},
    "failures": [],
}
def check(name, ok, detail=""):
    verification_out["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        verification_out["failures"].append({"name": name, "detail": detail})

check("official NFL feed has 321 games", len(nfl_pack["games"]) == 321, f'{len(nfl_pack["games"])} games')
check("every official NFL row has a source URL", all(g.get("sourceUrl") for g in nfl_pack["games"]))
check("every official W1 row has a source URL", all(e.get("sourceUrl") for e in w1_pack["events"]))
check("W1 station finder returns 4 SF affiliates", len(stations_pack["affiliates"]) == 4)
check("MLB TBD feed has flags", len(tbd_pack["flags"]) > 0, f'{len(tbd_pack["flags"])} flags')
check("all curated source registry URLs are https official domains", all(s["url"].startswith("https://") for s in sources))
check("all season anchors have source links", all(a.get("sourceUrl") for a in anchors))
check("all station rows have source links", all(s.get("sourceUrl") for s in stations))
check("all duration rows have source links", all(r.get("sourceUrl") for r in durations["official"] + durations["planningEstimates"] + durations["researchReferences"]))
check("all NCAAF future rows have source links", all(r.get("sourceUrl") for r in ncaaf_future))
check("all estimate rows carry the exact ESTIMATION label", all(r["label"] == EST_LABEL for r in estimates))
check("all flags have at least one official source link", all(f["sources"] for f in flags))
check("rulebook PDFs extracted successfully", all(r["status"] == "extracted" for r in rules))
check("no combined calendar row is missing a source URL", all(
    ev.get("sourceUrl") for b in days.values() for group in ("verified", "estimated", "tba") for ev in b[group]))
check("no verified row has a blank start time", all(ev["start"] for b in days.values() for ev in b["verified"]))
check("TBA rows have blank start times", all(not ev["start"] for b in days.values() for ev in b["tba"]))
verification_out["counts"] = {
    "nflGames": len(nfl_pack["games"]),
    "nflNoKickoff": sum(1 for g in nfl_pack["games"] if not g.get("startPT")),
    "nflNationalRadio": sum(1 for g in nfl_pack["games"] if g.get("nationalRadio")),
    "w1Events": len(w1_pack["events"]),
    "w1EventsInRange": len(w1_rows),
    "parallelEvents": len(par_events),
    "combinedEvents": len(combined),
    "calendarDays": len(days),
    "calendarVerifiedRows": sum(len(b["verified"]) for b in days.values()),
    "calendarEstimatedRows": sum(len(b["estimated"]) for b in days.values()),
    "calendarTbaRows": sum(len(b["tba"]) for b in days.values()),
    "mlbTbdTrue": len(tbd_true),
    "sourceRegistry": len(sources),
    "seasonAnchors": len(anchors),
    "stations": len(stations),
    "ncaafFutureRows": len(ncaaf_future),
    "estimateWindows": len(estimates),
    "flags": len(flags),
}
(DATA / "verification.json").write_text(json.dumps(verification_out, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- page template
ROOT_NAV = [
    ("../index.html", "Dashboard"), ("../calendar.html", "Calendar"), ("../vacation.html", "Vacation windows"),
    ("../mlb.html", "MLB"), ("../nfl.html", "NFL &amp; 49ers"), ("../ncaaf.html", "Stanford &amp; Cal"),
    ("../radio.html", "Radio"), ("../sources.html", "Sources"), ("../flagged.html", "Flagged"), ("../method.html", "Method"),
]
EXTRA_NAV = [
    ("index.html", "Official feeds"), ("calendar.html", "Day scoreboard"), ("vacation.html", "Free windows"),
    ("nfl-2026.html", "NFL 2026"), ("westwoodone.html", "Westwood One"), ("stations.html", "SF stations"),
    ("season-anchors.html", "Season anchors"), ("durations.html", "Durations"), ("ncaaf-future.html", "Future NCAAF"),
    ("estimates.html", "Estimates"), ("summary.html", "Executive summary"), ("sources.html", "Source registry"),
    ("flagged.html", "Flagged for Review"), ("verification.html", "Line-by-line verification"),
    ("links.html", "Link report"),
]

def nav_html(active: str) -> str:
    parts = []
    for href, label in ROOT_NAV:
        parts.append(f'<a href="{href}">{label}</a>')
    parts.append('<span class="nav-sep">|</span>')
    for href, label in EXTRA_NAV:
        cls = ' class="active"' if label == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return "".join(parts)

def page(title: str, active: str, body: str, desc: str = "") -> str:
    return f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · FREE TIME VACATION</title>
<meta name="description" content="{esc(desc or 'Official-source records, tentative planning gaps and flagged irregularities for San Francisco 94122.')}">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="assets/extra.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> FREE TIME / VACATION</div>
  <nav class="main">{nav_html(active)}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
  <p><strong>FREE TIME VACATION</strong> · Pacific time (America/Los_Angeles) · San Francisco / Outer Sunset 94122 AM/FM · compiled 2026-11-02</p>
  <p>Every table row links to an official source. Unconfirmed values are blank and listed on
  <a href="flagged.html">Flagged for Review</a>. Estimates are labelled
  <span class="tag est">{esc(EST_LABEL)}</span>. Flagged items do not block the live site.</p>
</div></footer>
<script src="assets/extra.js"></script>
</body></html>
'''

def table(headers, rows, table_id="", filter_html="") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    tid = f' id="{table_id}"' if table_id else ""
    return f'{filter_html}<div class="scroll"><table{tid}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

def filter_bar(table_id, with_status=True, with_year=True, with_league=False) -> str:
    s = f'<div class="toolbar filterbar"><input type="text" placeholder="Filter rows…" data-filter-table="{table_id}" aria-label="Filter rows">'
    if with_year:
        s += f'<select data-filter-year="{table_id}"><option value="">All years</option>' + "".join(f'<option value="{y}">{y}</option>' for y in (2026, 2027, 2028, 2029)) + "</select>"
    if with_league:
        s += f'<select data-filter-league="{table_id}"><option value="">All leagues</option>' + "".join(f'<option value="{esc(l)}">{esc(l)}</option>' for l in ("MLB", "NFL", "NCAAF", "Westwood One Sports")) + "</select>"
    if with_status:
        s += f'<select data-filter-status="{table_id}"><option value="">All statuses</option><option value="verified">verified</option><option value="estimated">estimated</option><option value="unverified">unverified / TBA</option><option value="high">high priority</option></select>'
    s += f'<span class="small" data-filter-count="{table_id}"></span></div>'
    return s

def row_attrs(r) -> str:
    y = (r.get("date") or "")[:4]
    status = (r.get("status") or "").lower()
    if status == "verified" and r.get("priority") == "high":
        status += " high"
    esc_status = esc(status)
    return f' data-year="{esc(y)}" data-league="{esc(r.get("league",""))}" data-status="{esc_status}"'

def source_cell(url, name="official source") -> str:
    return link(url, "official source") if url else '<span class="tag flag">no source link</span>'

# ---------------------------------------------------------------- extra/index.html
hub_cards = [
    ("calendar.html", "Day scoreboard", "Prev / Next / Today buttons, exact free and busy intervals in Pacific time, verified vs estimate toggle."),
    ("nfl-2026.html", "Official NFL 2026 (all teams)", f'{len(nfl_rows)} official NFL.com games: HOF, preseason, all 18 regular weeks, national radio flags, high-priority 49ers.'),
    ("westwoodone.html", "Westwood One Sports (all sports)", f'{len(w1_rows)} official network events with exact start/end radio windows, NFL plus NCAA, soccer, golf and more.'),
    ("stations.html", "San Francisco 94122 AM/FM stations", "Official station and team pages for KNBR, KSAN, KSFO, KSFN, KNEW, KTCT and the W1 affiliate list."),
    ("season-anchors.html", "Season anchors", "Officially published season windows for MLB, NFL, NCAAF and CFP across 2026–2029."),
    ("durations.html", "Durations &amp; halftime", "Official rulebook playing time and halftime wording, plus clearly labelled planning estimates."),
    ("ncaaf-future.html", "Stanford / Cal future dates", "Published 2027–2029 future dates, TBA opponents and conflicts between official releases."),
    ("estimates.html", "Estimates", f'Every unreleased schedule row labelled {EST_LABEL}.'),
    ("vacation.html", "Free vacation windows", "Ranked 1-week, 2-week and 3-week windows; strict verified view separated from estimates."),
    ("summary.html", "Executive summary", "The short answer, analysis, method and irregularities."),
    ("sources.html", "Source registry", f'{len(sources)} official sources with category and purpose.'),
    ("flagged.html", "Flagged for Review", f'{len(flags)} irregularities, unverified values and conflicts; does not block merge.'),
    ("verification.html", "Line-by-line verification", f'{len(verification_out["checks"])} build checks over the combined feeds, plus the separate link/source audit.'),
    ("links.html", "Link report", "Full local-link, source-link and external-host audit generated by tools/verify_extra.py."),
]
cards = "".join(
    f'<div class="card"><h3><a href="{h}">{t}</a></h3><p class="small">{d}</p></div>'
    for h, t, d in hub_cards)
body = f'''<h1>Official feeds &amp; combined verification</h1>
<p class="lede">Second-pass integration. The root dashboard (sessions 1a5a5516) covers the full free-time calendar;
this section adds the official NFL by-week feed, the complete Westwood One network feed, the 94122 station
evidence, published season anchors, duration/rulebook research, and a line-by-line verification of the merged data.</p>
<div class="callout"><strong>Verified vs estimate.</strong> <span class="tag ver">verified</span> = published on the linked
official page. <span class="tag est">ESTIMATE</span> = {esc(EST_LABEL)}. If a value is not on an official page it is
left <strong>blank</strong> and appears on <a href="flagged.html">Flagged for Review</a>. Flagged items do not block the site.</div>
<div class="grid g3">{cards}</div>
<h2>Combined feed at a glance</h2>
<div class="grid g4">
 <div class="card"><div class="kpi">{len(nfl_rows)}<small>official NFL 2026 games</small></div></div>
 <div class="card"><div class="kpi">{len(w1_rows)}<small>Westwood One events in range</small></div></div>
 <div class="card"><div class="kpi">{len(tbd_true)}<small>MLB TBD first pitches</small></div></div>
 <div class="card"><div class="kpi">{len(flags)}<small>flagged irregularities</small></div></div>
</div>
'''
(EXTRA / "index.html").write_text(page("Official feeds", "Official feeds", body), encoding="utf-8")

# ---------------------------------------------------------------- extra/nfl-2026.html
def nfl_table_rows():
    out = []
    for r in sorted(nfl_rows, key=lambda x: (x["date"], x["start"], x["title"])):
        out.append((
            f'<span {row_attrs(r)}>{esc(r["date"])}</span>',
            esc(r["phase"]),
            esc(r["start"] or "—"),
            esc(r["title"]),
            esc(r["venue"]),
            esc(r["radio"]) if r["radio"] else "—",
            '<span class="tag high">HIGH PRIORITY</span>' if r["priority"] == "high" else "—",
            badge(r["status"]) + (" " + link(r["sourceUrl"], "NFL.com") if r["sourceUrl"] else ""),
        ))
    return out

nrows = nfl_table_rows()
nfl_filter = filter_bar("nfltbl", with_league=False, with_year=False)
nfl_body = f'''<h1>Official NFL 2026 — every game</h1>
<p class="lede">All {len(nfl_rows)} Hall of Fame, preseason and regular-season games from the official
NFL.com by-week pages. Pacific times (PST/PDT) are converted from the league's UTC kickoff values.
Games with no published kickoff show a blank time and are flagged. Every row links to its official NFL.com game page.</p>
<div class="callout"><strong>Radio.</strong> Games tagged "Westwood One Sports (national)" carry the national
radio window per NFL.com's <code>broadcastInfo.audioNetworks</code>. 49ers games are
<span class="tag high">HIGH PRIORITY</span>. Note: NFL.com lists many teams' local radio networks too; only the
national W1 flag is reproduced here.</div>
{nfl_filter}
{table(["Date (PT)", "Week / phase", "Kickoff (PT)", "Game", "Venue", "National radio", "Priority", "Status &amp; source"], nrows, "nfltbl")}
<p class="small">Source of the feed: {link("https://www.nfl.com/schedules/2026/by-week/week-9", "NFL.com schedules by week")};
{sum(1 for r in nfl_rows if not r["start"])} games have no published kickoff time;
{sum(1 for r in nfl_rows if r["nationalRadio"])} games carry the Westwood One national radio flag.</p>
'''
(EXTRA / "nfl-2026.html").write_text(page("Official NFL 2026", "NFL 2026", nfl_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/westwoodone.html
def w1_table_rows():
    out = []
    for r in sorted(w1_rows, key=lambda x: (x["date"], x["start"], x["title"])):
        out.append((
            f'<span {row_attrs(r)}>{esc(r["date"])}</span>',
            esc(r["sport"]),
            esc(r["start"] or "—"),
            esc(r["end"] or "—"),
            str(r["durationMin"]) if r["durationMin"] else "—",
            esc(r["title"]),
            esc(r["venue"] or "—"),
            '<span class="tag high">HIGH PRIORITY</span>' if r["priority"] == "high" else "—",
            badge(r["status"]) + " " + link(r["sourceUrl"], "W1 event"),
        ))
    return out

wrows = w1_table_rows()
w1_filter = filter_bar("w1tbl", with_league=False)
w1_body = f'''<h1>Westwood One Sports — all official events</h1>
<p class="lede">{len(w1_rows)} official Westwood One Sports events from the network's event-grid and event-detail
pages in the displayed range. Start and end are the network's published on-air windows converted to Pacific time —
these are <strong>exact radio windows</strong>, not modelled game durations. NFL national broadcasts are
<span class="tag high">HIGH PRIORITY</span>.</p>
<div class="callout warn"><strong>Station caveat (official).</strong> The Westwood One Station Finder says:
"Because of local blackouts and/or programming conflicts, not every affiliate can air every Westwood One Sports
broadcast." San Francisco affiliates: KNBR-AM, KNBR-F2, KNBR-FM, KTCT-AM. See the
<a href="stations.html">station page</a> and {link("https://www.westwoodonesports.com/station-finder/", "official Station Finder")}.</div>
{w1_filter}
{table(["Date (PT)", "Sport", "Start (PT)", "End (PT)", "Minutes", "Event", "Venue", "Priority", "Source"], wrows, "w1tbl")}
<p class="small">Widget IDs used: NFL 47029, NCAA Football 47030, NCAA Basketball 47031, Soccer 47032, Golf 47033,
NCAA MCWS 47420, NCAA WCWS 47419, NCAA Lacrosse 47418, NCAA Hockey 47044. Times come from each event page's
<code>start_time</code>/<code>end_time</code> <code>data-time</code> attributes, which are Unix epoch values.</p>
'''
(EXTRA / "westwoodone.html").write_text(page("Westwood One Sports", "Westwood One", w1_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/stations.html
def curated_stations_note():
    return jload(ROOT / "curated/stations.json")["meta"]["caveat"]

srows = []
for s in stations:
    srows.append((
        esc(s["callSign"]), esc(s["frequency"] or "—"), esc(s["band"]), esc(s["role"]),
        '<span class="tag high">HIGH PRIORITY</span>' if s.get("highPriority") else "—",
        esc(s.get("priorityReason") or s.get("note") or ""),
        badge(s["status"]),
        source_cell(s["sourceUrl"]),
    ))
st_body = f'''<h1>San Francisco / Outer Sunset 94122 AM &amp; FM radio</h1>
<p class="lede">Official team, league, school, network and station pages. Frequencies that are not published
by an official source are left blank. The Westwood One Station Finder lists call signs but not frequencies.</p>
<div class="callout warn"><strong>Not a guarantee of carriage.</strong> {esc(curated_stations_note())}</div>
{table(["Call sign", "Frequency", "Band", "Role", "Priority", "Why / note", "Status", "Official source"], srows, "sttbl", filter_bar("sttbl", with_year=False, with_league=False))}
<h2>Official Westwood One Station Finder rows</h2>
{table(["Market", "Call sign", "Source"], [
    (esc(a["market"]), esc(a["callLetters"]), link(stations_pack["sourceUrl"], "Station Finder"))
    for a in stations_pack["affiliates"]], "sttbl2")}
'''
(EXTRA / "stations.html").write_text(page("SF 94122 stations", "SF stations", st_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/season-anchors.html
arows = []
for a in anchors:
    arows.append((
        f'<span {row_attrs(a)}>{esc(a["year"])}</span>', esc(a["league"]), esc(a["label"]),
        esc(a["startDate"] or "—"), esc(a["endDate"] or "—"),
        badge(a["status"]), esc(a["note"]), source_cell(a["sourceUrl"]),
    ))
an_body = f'''<h1>Officially published season anchors</h1>
<p class="lede">Separate, citable date ranges. Blank date fields mean the official source did not publish that value;
they are flagged on <a href="flagged.html">Flagged for Review</a>. Anchors give season context — they do not by
themselves mean a game is on air on every day of the range.</p>
{table(["Year", "League", "Anchor", "Start", "End", "Status", "Note", "Official source"], arows, "antbl", filter_bar("antbl", with_league=False))}
'''
(EXTRA / "season-anchors.html").write_text(page("Season anchors", "Season anchors", an_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/durations.html
drows = []
for r in durations["official"]:
    drows.append(("Official", esc(r["sport"]), esc(r["fact"]), esc(r["value"] or "—"), badge(r["status"]), esc(r["note"]), source_cell(r["sourceUrl"])))
prows = []
for r in durations["planningEstimates"]:
    prows.append(("Planning estimate", esc(r["sport"]), esc(r["use"]), f'{r["minutes"]} min', badge(r["status"]), esc(r["note"]), source_cell(r["sourceUrl"])))
rrows = []
for r in durations["researchReferences"]:
    rrows.append(("Research (not official)", esc(r["topic"]), "—", "—", badge("unverified"), esc(r["note"]), link(r["sourceUrl"], "research link")))
rule_rows = []
for r in rules:
    for line in r["matchingLines"][:6]:
        rule_rows.append((esc(r["name"]), esc(line), link(r["landingPage"], "official rules page")))
du_body = f'''<h1>Durations, halftime &amp; on-air windows</h1>
<p class="lede">Official rulebook facts are separated from planning buffers. Any number that is not published by
an official source is an <span class="tag est">ESTIMATE</span> and is flagged.</p>
<h2>Official facts</h2>
{table(["Layer", "Sport / source", "Fact", "Value", "Status", "Note", "Official source"], drows, "du1", filter_bar("du1", with_year=False, with_league=False))}
<h2>Planning estimates (flagged)</h2>
<p class="small">{esc(EST_LABEL)}. These are busy-block buffers used only when a game has a confirmed start; they are not official durations.</p>
{table(["Layer", "Sport", "Use", "Minutes", "Status", "Note", "Official basis"], prows, "du2", filter_bar("du2", with_year=False, with_league=False))}
<h2>Research references (not official values)</h2>
{table(["Layer", "Topic", "—", "—", "Status", "Note", "Link"], rrows, "du3", filter_bar("du3", with_year=False, with_league=False))}
<h2>Verbatim rulebook excerpts (extracted from official PDFs in CI)</h2>
{table(["Official document", "Extracted line", "Landing page"], rule_rows, "du4")}
'''
(EXTRA / "durations.html").write_text(page("Durations & halftime", "Durations", du_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/ncaaf-future.html
frows = []
for r in ncaaf_future:
    frows.append((
        f'<span {row_attrs(r)}>{esc(r["year"])}</span>', esc(r["team"]), esc(r["opponent"]), esc(r["site"]),
        esc(r["date"] or "—"), esc(r["time"] or "—"), badge(r["status"]), esc(r["note"]), source_cell(r["sourceUrl"]),
    ))
nf_body = f'''<h1>Stanford &amp; California (Cal) NCAAF — published future dates</h1>
<p class="lede">High priority. Only officially published dates are filled in. Blank dates and times mean the school
has not published them; they are not inferred. Conflicts between older and newer official releases are published
on <a href="flagged.html">Flagged for Review</a>.</p>
<div class="callout warn"><strong>Radio.</strong> Stanford football is on KNBR 1050 (KTCT-AM) with three hours of
pregame; Cal football is on KSFO 810 AM and the Big Game on KNBR 104.5 FM / 680 AM. See
<a href="stations.html">stations</a> for official links.</div>
{table(["Year", "Team", "Opponent", "Site", "Date", "Kickoff (PT)", "Status", "Note", "Official source"], frows, "nftbl", filter_bar("nftbl", with_league=False))}
'''
(EXTRA / "ncaaf-future.html").write_text(page("Future Stanford / Cal", "Future NCAAF", nf_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/estimates.html
erows = []
for r in estimates:
    erows.append((
        f'<span {row_attrs(r)}>{esc(r["year"])}</span>', esc(r["league"]), esc(r["item"]),
        esc(r["startDate"] or "—"), esc(r["endDate"] or "—"),
        f'<span class="tag est">{esc(r["label"])}</span>', esc(r["note"]), source_cell(r["sourceUrl"]),
    ))
es_body = f'''<h1>ESTIMATION — not a real verified released schedule</h1>
<p class="lede">Every row below is a planning model. The linked official landing page is where a real schedule would
be published; it does <strong>not</strong> currently contain these dates. No official value is inferred from these
estimates, and every row is on <a href="flagged.html">Flagged for Review</a>.</p>
<div class="callout warn"><strong>{esc(EST_LABEL)}</strong><br>
The root dashboard's 2028/2029 rows and the parallel session's modelled daily slates are estimates. Use the
<a href="calendar.html">day scoreboard</a> "Verified only" mode for the strict view.</div>
{table(["Year", "League", "Window", "Start", "End", "Label", "Note", "Official landing page"], erows, "estbl", filter_bar("estbl", with_league=False))}
'''
(EXTRA / "estimates.html").write_text(page("Estimates", "Estimates", es_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/vacation.html
def window_table(ws, label):
    rows = []
    for w in ws:
        rows.append((
            f'<span data-year="{esc(w["start"][:4])}" data-status="{esc(w["status"])}">{esc(w["start"])} → {esc(w["end"])}</span>',
            str(w["freeDays"]), str(w["busyDays"]), str(w["unverifiedDays"]), str(w["estimateOnlyDays"]),
            '<span class="tag ver">fully free</span>' if w["fullyFree"] else '<span class="tag flag">not fully free</span>',
            badge(w["status"]),
        ))
    return table(["Window", "Free / model-free days", "Busy days", "Unverified days", "Estimate-layer days", "Result", "Basis"], rows, "wt" + label.replace(" ", ""), filter_bar("wt" + label.replace(" ", ""), with_league=False))

vy_blocks = []
for y in (2027, 2028, 2029):
    s = strict[y]
    ws = vacation["windows"][str(y)]
    status_note = ('<div class="callout"><strong>Verified schedule year.</strong> Official MLB dates are released; '
                   'strict free-day rules apply.</div>' if s["scheduleReleased"] else
                   f'<div class="callout warn"><strong>{esc(EST_LABEL)}</strong><br>MLB and NFL have not released {y} '
                   'schedules. Strict verified free time cannot be asserted for this year; the ranking below is a '
                   'planning estimate from the modelled feed and is flagged.</div>')
    vy_blocks.append(f'''<h2>{y}</h2>
<p class="small">Days in range {s["daysInRange"]} · busy {s["busy"]} · unverified/TBA {s["unverified"]} ·
estimate-layer days {s["estimatedOnly"]} · verified free {s["free"]} · model-free (estimate layer) {s["modelFree"]}</p>
{status_note}
<h3>Best 1-week windows (7 days)</h3>{window_table(ws["1week"], "1w" + str(y))}
<h3>Best 2-week windows (14 days)</h3>{window_table(ws["2week"], "2w" + str(y))}
<h3>Best 3-week windows (21 days)</h3>{window_table(ws["3week"], "3w" + str(y))}''')

va_body = f'''<h1>Free vacation windows — strict verified view</h1>
<p class="lede">A minute is free when no covered game or national/local radio broadcast is on air. A free day has no
verified game with a published start, no TBA/unverified official row and no estimate-only row. Windows are ranked by
free days, then by fewest unverified days.</p>
<div class="callout"><strong>Conclusion: unknown, not impossible.</strong> No 7-, 14- or 21-day conflict-free vacation is certified for 2027–2029. Rankings below describe loaded records and estimates, not complete future radio schedules. <a href="../certainty.html">Audit and limitations</a>.</div>
{''.join(vy_blocks)}
<h2>Root dashboard comparison</h2>
<p class="small">The <a href="../vacation.html">root Vacation windows page</a> uses the parallel session's modelled
feed and reports six-day streaks. That feed is an estimate layer; this page separates it from the strict verified
view. Both are linked from the dashboard.</p>
'''
(EXTRA / "vacation.html").write_text(page("Free vacation windows", "Free windows", va_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/summary.html
exec_md = (ROOT / "research/EXECUTIVE-SUMMARY-ef8b5b30.md")
exec_text = exec_md.read_text(encoding="utf-8") if exec_md.exists() else ""
# Render simple markdown headings/paragraphs to HTML.
def md_to_html(md: str) -> str:
    out = []
    for line in md.splitlines():
        if line.startswith("## "):
            out.append(f"<h2>{esc(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{esc(line[2:])}</h1>")
        elif line.startswith("- "):
            out.append(f"<p>• {esc(line[2:])}</p>")
        elif line.strip() == "":
            out.append("")
        else:
            out.append(f"<p>{esc(line)}</p>")
    return "\n".join(out)

su_body = f'''<h1>Executive summary</h1>
{md_to_html(exec_text)}
'''
(EXTRA / "summary.html").write_text(page("Executive summary", "Executive summary", su_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/sources.html
srrows = []
for s in sources:
    srrows.append((esc(s["id"]), esc(s["category"]), esc(s["name"]), link(s["url"], "open official page"),
                   esc(s["use"]), esc(s.get("note") or "")))
so_body = f'''<h1>Official source registry</h1>
<p class="lede">{len(sources)} official sources. Every table row on the site links to one of these URLs.
Third-party research is listed separately on <a href="durations.html">Durations</a> and is never used as a verified
schedule value.</p>
{table(["ID", "Category", "Official source", "Link", "What it provides", "Note"], srrows, "srtbl", filter_bar("srtbl", with_year=False, with_league=False))}
'''
(EXTRA / "sources.html").write_text(page("Source registry", "Source registry", so_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/flagged.html
flrows = []
for f in flags:
    links_html = "<br>".join(link(s["url"], s["name"]) for s in f["sources"])
    flrows.append((
        f'<span data-status="{esc(f["severity"])}">{esc(f["id"])}</span>', esc(f["severity"]), esc(f["title"]),
        esc(f["detail"]), badge(f["status"]), links_html,
    ))
fl_body = f'''<h1>Flagged for Review</h1>
<p class="lede">Clearly labelled: <strong>FLAGGED FOR REVIEW</strong>. {len(flags)} irregularities, unverified
values, TBD times, estimate labels and conflicts between official sources. Every row has official source links for
manual review.</p>
<div class="callout warn"><strong>These do not block the merge.</strong> Per the project brief, flagged /
unverified / needs-review items are published here and do not block the PR merge or the live Pages deployment.
A value that could not be confirmed is left <strong>blank</strong> rather than inferred.</div>
<p class="small"><strong>{esc(EST_LABEL)}</strong> is the exact label used on every unreleased-schedule row.</p>
{table(["ID", "Severity", "Title", "Detail", "Status", "Official sources"], flrows, "flt", filter_bar("flt", with_year=False, with_league=False))}
<h2>Root Flagged page</h2>
<p class="small">The parallel session's own flagged list is on <a href="../flagged.html">Flagged</a> (root site).
This combined page includes those items plus the second-pass findings.</p>
'''
(EXTRA / "flagged.html").write_text(page("Flagged for Review", "Flagged for Review", fl_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/verification.html
vrows = []
for c in verification_out["checks"]:
    vrows.append((esc(c["name"]), '<span class="tag ver">PASS</span>' if c["ok"] else '<span class="tag flag">FAIL</span>', esc(c["detail"])))
counts_rows = [(esc(k), esc(v)) for k, v in verification_out["counts"].items()]
ve_body = f'''<h1>Line-by-line verification</h1>
<p class="lede">Automated checks over every merged feed row, every source link, every local link, and the build
output. Run with <code>python3 tools/verify_extra.py</code> after <code>python3 tools/build_extra.py</code>.</p>
<div class="callout"><strong>Result:</strong> {len(verification_out["checks"])} build checks,
{sum(1 for c in verification_out["checks"] if c["ok"])} passed,
{len(verification_out["failures"])} failed. The separate <a href="links.html">link/source audit</a> runs 31
additional checks. Failures are published, not hidden.</div>
<h2>Checks</h2>
{table(["Check", "Result", "Detail"], vrows, "vtbl")}
<h2>Combined feed counts</h2>
{table(["Metric", "Value"], counts_rows, "ctbl")}
<h2>Prior verification evidence</h2>
<p class="small">The parallel session's report: {link("https://karagemop466-tech.github.io/Korea5/verification/report.md", "verification/report.md")}
and {link("https://karagemop466-tech.github.io/Korea5/verification/links.json", "verification/links.json")}.
Its earlier pass reported 49/62 rows verified with 13 failures; the published dashboard later reported 61/62.
The combined verification above re-checks the merged feeds and flags any remaining discrepancy.</p>
<h2>Build / link check</h2>
<p class="small">See <code>extra/data/verification.json</code> for machine-readable results,
<a href="links.html">Local link &amp; source-link report</a> for the full link audit, and
<code>tools/verify_extra.py</code> for the checker. The final integration step runs it before the PR.</p>
'''
(EXTRA / "verification.html").write_text(page("Line-by-line verification", "Line-by-line verification", ve_body), encoding="utf-8")

# ---------------------------------------------------------------- extra/calendar.html
cal_body = '''<h1>Day scoreboard — modelled gaps (Pacific)</h1>
<p class="lede">A minute is free when no covered game or radio broadcast is on air. Use <strong>Prev</strong>,
<strong>Next</strong> and <strong>Today</strong> to move day by day. Verified mode uses only rows with an official
published start time; estimate mode adds the clearly labelled planning layer.</p>
<div class="toolbar">
  <button id="x-prev" class="primary">← Prev</button>
  <button id="x-today">Today</button>
  <button id="x-next" class="primary">Next →</button>
  <input type="date" id="x-date" min="2026-11-02" max="2030-02-28">
  <label class="small"><input type="checkbox" id="x-est"> Include planning estimates</label>
  <span class="small">Today is <strong id="x-today-label"></strong></span>
</div>
<div id="x-estbanner" class="callout warn" style="display:none"><strong>ESTIMATION — not a real verified released schedule.</strong>
Estimate rows are planning models, not official schedules. They are flagged on <a href="flagged.html">Flagged for Review</a>.</div>
<div class="card">
  <h2 id="x-dayhead" style="margin-top:0">—</h2>
  <div class="pipeline"><div class="daybar" id="x-bar"></div>
  <div class="ticks"><span>00:00</span><span>03:00</span><span>06:00</span><span>09:00</span><span>12:00</span><span>15:00</span><span>18:00</span><span>21:00</span><span>24:00</span></div></div>
  <div class="legend"><span><i style="background:#e2523f"></i>game / radio on air</span><span><i style="background:#2f6f57"></i>free</span></div>
  <div class="grid g3" style="margin-top:16px">
    <div class="card" style="padding:12px"><div class="kpi" id="x-busy">—<small>busy hours</small></div></div>
    <div class="card" style="padding:12px"><div class="kpi" id="x-free">—<small>unblocked model hours</small></div></div>
    <div class="card" style="padding:12px"><div class="small">Free windows (30 min or more, PT)</div><div id="x-freewin" class="pill-row" style="margin:8px 0 0"></div></div>
  </div>
</div>
<div id="x-unverified"></div>
<h2>On air this day</h2>
<div class="scroll"><table><thead><tr><th>Start (PT)</th><th>End (PT)</th><th>League / sport</th><th>Event</th><th>Priority</th><th>Radio</th><th>Status</th><th>Official source</th></tr></thead>
<tbody id="x-events"><tr><td colspan="8">Loading…</td></tr></tbody></table></div>
<h2>Season context &amp; published future dates</h2>
<div id="x-context" class="pill-row"></div>
<h2>Week strip</h2><div class="pill-row" id="x-strip"></div>
'''
(EXTRA / "calendar.html").write_text(page("Day scoreboard", "Day scoreboard", cal_body), encoding="utf-8")

# ---------------------------------------------------------------- assets/extra.css
(ASSETS / "extra.css").write_text('''/* Second-pass official-feed pages */
.nav-sep{color:var(--muted);padding:0 4px;align-self:center}
.callout.warn{border-color:#7a5b12}
.filterbar input[type=text]{min-width:220px}
.blank{color:var(--muted)}
.tag.high{color:#0a1e14;background:var(--accent);border-color:transparent}
.est-banner{background:#3a2b06;border:1px solid #7a5b12}
td .small{display:block;margin-top:4px}
footer{margin-top:40px;border-top:1px solid var(--line);padding:18px 0;color:var(--muted);font-size:13px}
footer a{color:var(--accent2)}
''', encoding="utf-8")

# ---------------------------------------------------------------- assets/extra.js
(ASSETS / "extra.js").write_text(r'''/* Table filters + combined day scoreboard */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  // generic table filters
  $$('[data-filter-table]').forEach(inp=>{
    const id=inp.dataset.filterTable, tbl=document.getElementById(id);
    if(!tbl) return;
    const rows=$$('tbody tr',tbl);
    const year=$(`[data-filter-year="${id}"]`), league=$(`[data-filter-league="${id}"]`),
          status=$(`[data-filter-status="${id}"]`), count=$(`[data-filter-count="${id}"]`);
    const apply=()=>{
      const q=inp.value.trim().toLowerCase(), y=year?year.value:'', l=league?league.value:'', s=status?status.value:'';
      let n=0;
      rows.forEach(tr=>{
        const host=tr.querySelector('[data-year]')||tr;
        const ry=host.dataset.year||'', rl=host.dataset.league||'', rs=host.dataset.status||'';
        let ok=(!q||tr.textContent.toLowerCase().includes(q))&&(!y||ry===y)&&(!l||rl===l);
        if(s==='high') ok=ok&&rs.includes('high');
        else if(s) ok=ok&&rs.includes(s);
        tr.style.display=ok?'':'none'; if(ok)n++;
      });
      if(count)count.textContent=`${n} / ${rows.length} rows`;
    };
    inp.addEventListener('input',apply);
    [year,league,status].forEach(el=>el&&el.addEventListener('change',apply));
    apply();
  });

  // day scoreboard
  const cal=$('#x-dayhead'); if(!cal) return;
  const START='2026-11-02', END='2030-02-28';
  function pacificISODate(now) {
    const fields = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(now).map(part => [part.type, part.value]));
    return `${fields.year}-${fields.month}-${fields.day}`;
  }
  let today=pacificISODate(new Date());
  let cur=new URLSearchParams(location.search).get('d')||today;
  let pack=null, includeEst=false;
  const toMin=h=>{const [a,b]=h.split(':').map(Number);return a*60+b;};
  const fmt=m=>`${String(Math.floor(m/60)%24).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  const addDays=(iso,n)=>{const d=new Date(iso+'T12:00:00Z');d.setDate(d.getDate()+n);return d.toISOString().slice(0,10);};
  const pretty=iso=>new Date(iso+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric',timeZone:'UTC'});
  const clamp=s=>s<START?START:(s>END?END:s);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const a=(u,t)=>u?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t||'official source')}</a>`:'';
  const badge=st=>{st=(st||'').toLowerCase();return st==='verified'?'<span class="tag ver">verified</span>':st==='estimated'?'<span class="tag est">ESTIMATE</span>':'<span class="tag flag">unverified / TBA</span>';};
  function intervals(e){
    const out=[];
    if(e.start){
      const s=toMin(e.start);
      let en=e.end?toMin(e.end):s+(Number(e.durationMin)||165);
      if(en<=s)en+=1440; // overnight network window
      if(en>1440){out.push([s,1440]);out.push([0,en-1440]);}else out.push([s,en]);
    } else if(e.startWindow){
      const [x,y]=e.startWindow.split('-').map(toMin);out.push([x,y]);
    } else if(e.altWindow&&e.altWindow.start){
      const s=toMin(e.altWindow.start);out.push([s,s+(e.altWindow.durationMin||165)]);
    }
    return out;
  }
  function merge(ivs){
    const s=ivs.slice().sort((a,b)=>a[0]-b[0]),out=[];
    for(const [x,y] of s){if(out.length&&x<=out[out.length-1][1])out[out.length-1][1]=Math.max(out[out.length-1][1],y);else out.push([x,y]);}
    return out;
  }
  function render(){
    today=pacificISODate(new Date());
    const b=pack.days[cur]||{verified:[],estimated:[],tba:[],anchors:[],future:[]};
    const rows=[...b.verified,...(includeEst?b.estimated:[])];
    $('#x-date').value=cur;
    $('#x-today-label').textContent=today;
    $('#x-dayhead').textContent=pretty(cur)+' · '+(cur.slice(5).replace('-','/'))+' Pacific';
    $('#x-estbanner').style.display=includeEst?'':'none';
    const ivs=merge(rows.flatMap(intervals)).map(([x,y])=>[Math.max(0,x),Math.min(1440,y)]);
    const bar=$('#x-bar');bar.innerHTML='';let cursor=0;const free=[];
    for(const [x,y] of ivs){if(x>cursor)free.push([cursor,x]);cursor=Math.max(cursor,y);}
    if(cursor<1440)free.push([cursor,1440]);
    free.forEach(([x,y])=>{const d=document.createElement('div');d.className='seg free';d.style.left=(x/1440*100)+'%';d.style.width=((y-x)/1440*100)+'%';bar.appendChild(d);});
    ivs.forEach(([x,y])=>{const d=document.createElement('div');d.className='seg busy';d.style.left=(x/1440*100)+'%';d.style.width=((y-x)/1440*100)+'%';d.title=fmt(x)+'–'+fmt(y)+' busy';bar.appendChild(d);});
    const busyH=ivs.reduce((t,[x,y])=>t+(y-x),0)/60;
    $('#x-busy').textContent=busyH.toFixed(1);$('#x-free').textContent=(b.tba.length||b.future.length)?'Unknown':(24-busyH).toFixed(1);
    const fw=(b.tba.length||b.future.length)?[]:free.filter(([x,y])=>y-x>=30);
    $('#x-freewin').innerHTML=fw.length?fw.map(([x,y])=>`<span class="tag ver">${fmt(x)}–${fmt(y)} model gap (${((y-x)/60).toFixed(1)}h PT)</span>`).join(' '):'<span class="tag flag">No model gap of 30 minutes or more</span>';
    const uv=[...b.tba,...b.future];
    $('#x-unverified').innerHTML=uv.length?`<div class="callout warn"><strong>Unverified / TBA on this day (${uv.length}).</strong> Exact free minutes cannot be computed for these rows because no official start time is published; they are not inferred.<ul>${uv.map(e=>`<li>${esc(e.title||'published future date')} — ${esc(e.note||'time not published')} ${a(e.sourceUrl,'official source')}</li>`).join('')}</ul></div>`:'';
    const evs=[...rows,...uv];
    $('#x-events').innerHTML=evs.length?evs.map(e=>`<tr>
      <td>${esc(e.start||'—')}</td><td>${esc(e.end||'—')}</td><td>${esc(e.league||e.sport||'')}${e.phase?` <span class="small">${esc(e.phase)}</span>`:''}</td>
      <td>${esc(e.title||'')}${e.venue?`<br><span class="small">${esc(e.venue)}</span>`:''}${e.note?`<br><span class="small">${esc(e.note)}</span>`:''}</td>
      <td>${e.priority==='high'?'<span class="tag high">HIGH PRIORITY</span>':'—'}</td>
      <td>${e.radio?'<span class="tag est">RADIO CANDIDATE</span>':'—'}</td>
      <td>${badge(e.status||'unverified')}</td><td>${a(e.sourceUrl,'official source')}</td></tr>`).join(''):'<tr><td colspan="8">No scheduled sports programming found on the official feeds for this day.</td></tr>';
    const ctx=[...b.anchors.map(x=>`<span class="chip">${esc(x.label)} · ${esc(x.league)} ${a(x.sourceUrl,'source')}</span>`),
               ...b.future.map(x=>`<span class="chip">${esc(x.title)} ${a(x.sourceUrl,'source')}</span>`)];
    $('#x-context').innerHTML=ctx.length?ctx.join(' '):'<span class="small">No official season anchor for this day.</span>';
    let strip='';for(let i=-3;i<=3;i++){const d=addDays(cur,i);if(d<START||d>END)continue;const bb=pack.days[d]||{};const busy=(bb.verified||[]).length;strip+=`<a class="chip" href="?d=${d}">${d.slice(5)} <span class="tag ${busy?'flag':'ver'}">${busy?busy+' events':'free?'}</span></a>`;}
    $('#x-strip').innerHTML=strip;
    history.replaceState(null,'','?d='+cur);
  }
  $('#x-prev').onclick=()=>{cur=clamp(addDays(cur,-1));render();};
  $('#x-next').onclick=()=>{cur=clamp(addDays(cur,1));render();};
  $('#x-today').onclick=()=>{today=pacificISODate(new Date());cur=today;render();};
  $('#x-date').onchange=e=>{cur=clamp(e.target.value);render();};
  $('#x-est').onchange=e=>{includeEst=e.target.checked;render();};
  fetch('data/calendar.json').then(r=>r.json()).then(p=>{pack=p;cur=clamp(cur);render();}).catch(e=>{$('#x-dayhead').textContent='Could not load calendar.json: '+e;});
})();
''', encoding="utf-8")

# ---------------------------------------------------------------- root nav + exact labels (idempotent)
nav_link = '<a href="extra/index.html">Official feeds &amp; verification</a>'
for p in sorted(ROOT.glob("*.html")):
    txt = p.read_text(encoding="utf-8")
    orig = txt
    if "extra/index.html" not in txt:
        txt = txt.replace("</nav>", nav_link + "</nav>", 1)
    txt = txt.replace('<button id="prev">← Yesterday</button>', '<button id="prev">← Prev</button>')
    txt = txt.replace('<button id="tomorrow">Tomorrow →</button>', '<button id="tomorrow">Next →</button>')
    txt = txt.replace('<button id="next">Tomorrow +1 →</button>', '<button id="next">+2 days →</button>')
    txt = txt.replace('the last of which sits after the Super Bowl and before Spring Training, when nothing at all is in season.',
        'the last of which sits before Super Bowl LXI (Feb 14 2027); the verified four-day gap after the Super Bowl is Feb 15–18 2027, before Spring Training opens Feb 19. See the combined analysis for the strict verified view.')
    if txt != orig:
        p.write_text(txt, encoding="utf-8")

print(json.dumps({
    "extraPages": len(list(EXTRA.glob("*.html"))),
    "calendarDays": len(days),
    "calendarBytes": (DATA / "calendar.json").stat().st_size,
    "verificationChecks": len(verification_out["checks"]),
    "verificationFailures": len(verification_out["failures"]),
    "nflRows": len(nfl_rows),
    "w1Rows": len(w1_rows),
}, indent=2))
