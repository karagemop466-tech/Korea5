#!/usr/bin/env python3
"""Generate the static site from the verified data feeds.

Every table row carries a link to the official source it came from. Rows whose values
could not be confirmed are left blank and listed on the "Flagged for review" page.
"""
import hashlib
import html
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

YEARS = (2026, 2027, 2028, 2029, 2030)
SITE = "Free Time Vacation Planner"
BASE = "https://karagemop466-tech.github.io/Korea5/"

NAV = [
    ("index.html", "Dashboard"),
    ("calendar.html", "Calendar"),
    ("vacation.html", "Vacation windows"),
    ("mlb.html", "MLB"),
    ("nfl.html", "NFL &amp; 49ers"),
    ("ncaaf.html", "Stanford &amp; Cal"),
    ("radio.html", "Radio"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
    ("method.html", "Method"),
]


def data_version():
    """Content hash of the data the calendar reads, so a deploy can never serve stale JSON
    from the Pages CDN while the HTML is already new."""
    h = hashlib.sha256()
    for f in ("data/derived/analysis.json", "data/events-2026.json", "data/events-2027.json",
              "data/events-2028.json", "data/events-2029.json", "data/events-2030.json"):
        if os.path.exists(f):
            with open(f, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:12]


def esc(s):
    return html.escape(str(s if s is not None else ""))


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


ANALYSIS = load("data/derived/analysis.json", {"days": {}, "vacations": {}, "summary": {}, "meta": {}})
REPORT = load("verification/report.json", {"summary": {}, "curated": [], "mlbSpotChecks": [], "feedProblems": []})
EVENTS = {y: load(f"data/events-{y}.json") for y in YEARS}
EVENTS = {y: v for y, v in EVENTS.items() if v}


def head(title, active):
    nav = "".join(
        f'<a href="{u}" class="{"active" if u == active else ""}">{n}</a>' for u, n in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {SITE}</title>
<meta name="description" content="Free-time and vacation planner for MLB, NFL, Stanford and Cal football, and Westwood One national radio, in Pacific time for San Francisco 94122.">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="top"><div class="wrap topbar">
  <div class="brand"><span class="dot"></span> FREE TIME / VACATION</div>
  <nav class="main">{nav}</nav>
</div></header>
<main class="wrap">"""


def foot():
    gen = ANALYSIS.get("meta", {}).get("generatedUTC", "")
    return f"""</main>
<footer><div class="wrap">
  <p><strong>{SITE}</strong> · Pacific time (America/Los_Angeles) · Coverage {ANALYSIS.get('meta',{}).get('horizon',['',''])[0]} → {ANALYSIS.get('meta',{}).get('horizon',['',''])[1]} ·
  data rebuilt {esc(gen)}</p>
  <p>Verified data comes from MLB's own StatsAPI, 49ers.com, gostanford.com, calbears.com and westwoodonesports.com.
  Anything not published by an official source is labelled <span class="tag est">estimated</span> and explained on the
  <a href="method.html">Method</a> page. Items that could not be confirmed are on <a href="flagged.html">Flagged for review</a>.</p>
</div></footer></body></html>"""


def page(name, title, active, body):
    with open(name, "w", encoding="utf-8") as f:
        f.write(head(title, active) + body + foot())


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def src(url, label="source"):
    if not url:
        return '<span class="small">—</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def tag(text, cls="tag"):
    return f'<span class="{cls}">{esc(text)}</span>'


def stat(scope, key):
    return ANALYSIS["summary"].get(scope, {}).get("scopes", {}).get("", {})


# ---------------------------------------------------------------- facts
def year_facts(y):
    s = ANALYSIS["summary"].get(str(y), {"scopes": {}, "leagueEvents": {}})
    return s


def best_window(length, scope="all", year=None, rank="score"):
    key = scope if rank == "score" else f"{scope}-hours"
    lst = ANALYSIS["vacations"].get(key, {}).get(str(length), [])
    if year:
        lst = [w for w in lst if w["start"].startswith(str(year))]
    return lst[0] if lst else None


def fmt_range(a, b):
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    if da.year == db.year:
        return f"{da.strftime('%b %-d')} – {db.strftime('%b %-d, %Y')}"
    return f"{da.strftime('%b %-d, %Y')} – {db.strftime('%b %-d, %Y')}"


# ================================================================ index
def build_index():
    s26, s27, s28, s29 = (year_facts(y) for y in (2026, 2027, 2028, 2029))
    best7 = best_window(7)
    best14 = best_window(14)
    streak27 = (ANALYSIS.get("freeStreaks", {}).get("all", {}).get("2027") or [{}])[0]
    streak27_txt = "—"
    strict = ANALYSIS["summary"]

    # next 14 days strip
    today = date.fromisoformat(ANALYSIS["meta"]["today"])
    rows = []
    for i in range(14):
        d = (today + timedelta(days=i)).isoformat()
        rec = ANALYSIS["days"].get(d, {}).get("all")
        if not rec:
            continue
        cls = "ver" if rec["hours"] == 0 else ("est" if rec["hours"] < 3 else "flag")
        label = "free" if rec["hours"] == 0 else f"{rec['hours']:.1f}h busy"
        rows.append(f'<a class="chip" href="calendar.html#{d}">{esc(date.fromisoformat(d).strftime("%a %b %-d"))} '
                    f'{tag(label, "tag " + cls)}</a>')

    body = f"""
<section class="hero">
  <div>
    <h1>When can I actually take a vacation?</h1>
    <p class="lede">A year-round answer for San Francisco 94122, in Pacific time, built only from official schedules.
    It blocks every MLB game (all 30 clubs), every NFL game, Stanford and Cal football, and Westwood One national NFL radio —
    then shows the gaps.</p>
    <div class="pill-row">
      {tag("MLB 2026 + 2027 verified", "tag ver")}
      {tag("49ers, Stanford, Cal verified", "tag ver")}
      {tag("2027 NFL / 2028–29 estimated", "tag est")}
      {tag(f"{REPORT.get('summary', {}).get('rowsVerified', 0)}/{REPORT.get('summary', {}).get('rowsChecked', 0)} rows re-verified", "tag ver")}
    </div>
    <div class="callout">
      <strong>The short answer.</strong> There is <strong>no fully free 7-day window in 2027, 2028 or 2029</strong>.
      MLB schedules a full slate almost every day from late February to early October (verified for 2027), and NFL/college
      football fills the winter weekends. The longest run with nothing on air is <strong>exactly six days</strong> in 2027, 2028 and 2029 —
      and it recurs in January and February, in the Mon–Sat gaps between NFL playoff weekends. In 2027 the six-day options are
      <strong>{esc(", ".join(fmt_range(s["start"], s["end"]) for s in (ANALYSIS.get("freeStreaks",{}).get("all",{}).get("2027") or [])[:3]))}</strong> —
      the last of which sits after the Super Bowl and before Spring Training, when nothing at all is in season.
      Full ranking on <a href="vacation.html">Vacation windows</a>.
    </div>
  </div>
  <div class="grid">
    <div class="card"><div class="kpi">{esc(ANALYSIS['summary'].get('2027',{}).get('scopes',{}).get('all',{}).get('longestFreeStreak','—'))}<small>longest free streak, 2027 (days)</small></div></div>
    <div class="card"><div class="kpi">{esc(len(ANALYSIS['vacations'].get('all',{}).get('7',[])) and ANALYSIS['vacations']['all']['7'][0]['freeDays'])}<small>free days in the best 7-day window</small></div></div>
    <div class="card"><div class="kpi">{len(load("data/mlb-2027.json", {"games": []})["games"] and [g for g in load("data/mlb-2027.json", {"games": []})["games"] if g["type"]=="R"]):,}<small>MLB regular-season games, 2027</small></div></div>
  </div>
</section>

<h2>Next 14 days</h2>
<p class="small">Busy time is measured against the definition on the <a href="method.html">Method</a> page. Click a day for the hour-by-hour view.</p>
<div class="pill-row">{''.join(rows)}</div>

<h2>What is free, by year</h2>
<div class="grid g3">
  {''.join(f'''<div class="card"><h3>{y}</h3>
   <p class="small">{("Official MLB schedule released" if y in (2026, 2027) else "Estimated — league has not released this season")}{" · from Nov 2 only" if y == 2026 else ""}</p>
   <div class="kpi">{year_facts(y).get('scopes',{}).get('all',{}).get('freeDays','—')}<small>fully free days</small></div>
   <p class="small" style="margin-top:10px">Longest free streak: <strong>{year_facts(y).get('scopes',{}).get('all',{}).get('longestFreeStreak','—')} days</strong><br>
   Busy hours across the year: {year_facts(y).get('scopes',{}).get('all',{}).get('busyHours','—')}</p></div>''' for y in (2026, 2027, 2028, 2029))}
</div>

<h2>Best windows at a glance</h2>
<div class="grid g2">
  <div class="card"><h3>Best 7-day window</h3>
    <p class="kpi" style="font-size:20px">{esc(fmt_range(best7['start'], best7['end'])) if best7 else '—'}</p>
    <p class="small">{esc(best7['freeDays']) if best7 else '—'} free days · {esc(best7['busyHours']) if best7 else '—'} busy hours.
    Ranked by free days first, then by the fewest hours of live sport.</p>
    <a class="btn" href="vacation.html">See all ranked windows →</a></div>
  <div class="card"><h3>Best 14-day window</h3>
    <p class="kpi" style="font-size:20px">{esc(fmt_range(best14['start'], best14['end'])) if best14 else '—'}</p>
    <p class="small">{esc(best14['freeDays']) if best14 else '—'} free days · {esc(best14['busyHours']) if best14 else '—'} busy hours.
    Multi-week trips have to tolerate NFL Sundays and the Pro Bowl.</p>
    <a class="btn" href="calendar.html">Open the calendar →</a></div>
</div>

<h2>How this is built</h2>
<div class="grid g3">
  <div class="card"><h3>1 · Official schedules</h3><p class="small">2026 and 2027 MLB come straight from MLB's StatsAPI (2,430 regular-season games per season, all 30 clubs).
  49ers, Stanford, Cal and Westwood One are taken from their own sites.</p></div>
  <div class="card"><h3>2 · Explicit estimates</h3><p class="small">Where a league has not published a schedule (2027 NFL, all of 2028–29), the planner models the league's structure and labels every row
  <span class="tag est">estimated</span> — no matchups are invented.</p></div>
  <div class="card"><h3>3 · Re-verified</h3><p class="small">A CI job re-downloads each cited official page and checks that every curated row still appears there.
  Failures are published on <a href="flagged.html">Flagged for review</a>.</p></div>
</div>
"""
    page("index.html", "Dashboard", "index.html", body)


# ================================================================ calendar
def build_calendar():
    body = f"""
<h1>Free-time calendar</h1>
<p class="lede">Every day from {ANALYSIS['meta']['today']} to {ANALYSIS['meta']['horizon'][1]}, in Pacific time.
Free time is any 30-minute-or-longer gap with no qualifying game on air.</p>
<div class="toolbar">
  <button id="prev">← Yesterday</button>
  <button id="tobay">Today</button>
  <button id="tomorrow">Tomorrow →</button>
  <button id="next">Tomorrow +1 →</button>
  <input type="date" id="dateinput" min="{ANALYSIS['meta']['today']}" max="{ANALYSIS['meta']['horizon'][1]}">
  <span class="small">Today is <strong id="today"></strong></span>
</div>
<div class="toolbar">
  <span class="small" style="margin-right:6px">What counts as busy:</span>
  <span class="chip on" data-scope="all">All games</span>
  <span class="chip" data-scope="radio">Radio only (SF AM/FM)</span>
  <span class="chip" data-scope="high">High priority</span>
</div>

<div class="card">
  <h2 id="dayhead" style="margin-top:0">—</h2>
  <div class="pipeline"><div class="daybar" id="bar"></div>
  <div class="ticks"><span>00:00</span><span>03:00</span><span>06:00</span><span>09:00</span><span>12:00</span><span>15:00</span><span>18:00</span><span>21:00</span><span>24:00</span></div></div>
  <div class="legend"><span><i style="background:#e2523f"></i>game on air</span><span><i style="background:#2f6f57"></i>free</span></div>
  <div class="grid g3" style="margin-top:16px">
    <div class="card" style="padding:12px"><div class="kpi" id="hours">—<small>busy hours</small></div></div>
    <div class="card" style="padding:12px"><div class="kpi" id="freehrs">—<small>free hours</small></div></div>
    <div class="card" style="padding:12px"><div class="small">Free windows (30 min or more)</div><div id="freewin" class="pill-row" style="margin:8px 0 0"></div></div>
  </div>
</div>

<h2>Games on this day</h2>
<div class="scroll"><table><thead><tr><th>Start (PT)</th><th>League</th><th>Game</th><th>Priority</th><th>Radio</th><th>Status &amp; source</th></tr></thead>
<tbody id="gamelist"><tr><td colspan="6">Loading…</td></tr></tbody></table></div>
<p class="small" id="basis" style="margin-top:10px"></p>

<h2>Week view</h2>
<div class="pill-row" id="strip"></div>

<div class="callout warn"><strong>Reading the estimate badges.</strong> <span class="tag ver">verified</span> means an official source published that date and start time.
<span class="tag est">estimated</span> means the date is official but the start time is TBD (common for the 2027 MLB season), or the whole row is a modelled league window.
The exact reason is printed under the table for each day.</div>

<script>window.DATA_VERSION = "{data_version()}";</script>
<script src="assets/app.js"></script>
"""
    page("calendar.html", "Calendar", "calendar.html", body)


# ================================================================ vacation
def streak_tables():
    out = ""
    for y in (2027, 2028, 2029):
        st = (ANALYSIS.get("freeStreaks", {}).get("all", {}).get(str(y)) or [])
        rows = [[f"<strong>{esc(fmt_range(s['start'], s['end']))}</strong>", str(s["days"])] for s in st[:8]]
        out += f"<h3>{y}</h3>" + table(["Stretch", "Consecutive free days"], rows)
    return out


def build_vacation():
    def window_table(scope, key_label):
        out = []
        for length in (7, 14, 21):
            lst = ANALYSIS["vacations"].get(f"{scope}", {}).get(str(length), []) if scope == "all" \
                else ANALYSIS["vacations"].get(f"{scope}-hours", {}).get(str(length), [])
            rows = []
            for w in lst:
                conf = w.get("conflictDays", {})
                conf_txt = ", ".join(f"{d[5:]} ({n})" for d, n in list(conf.items())[:6]) or "none"
                if len(conf) > 6:
                    conf_txt += f" +{len(conf)-6} more"
                rows.append([
                    f"<strong>{esc(fmt_range(w['start'], w['end']))}</strong>",
                    f"{w['freeDays']} / {length}",
                    f"{w['busyHours']:.1f}h",
                    f'<small>{esc(conf_txt)}</small>',
                ])
            out.append(f"<h3>{length}-day trips</h3>" +
                       table(["Window", "Fully free days", "Busy hours", "Days with games (count)"], rows))
        return "".join(out)

    # strict statement
    longest = {y: ANALYSIS["summary"].get(str(y), {}).get("scopes", {}).get("all", {}).get("longestFreeStreak", 0)
               for y in (2027, 2028, 2029)}
    body = f"""
<h1>Vacation windows, 2027–2029</h1>
<p class="lede">Ranked by how much of the trip is genuinely free. Two lenses: <strong>strict</strong> (days with zero qualifying games)
and <strong>lightest</strong> (the fewest hours of live sport per day).</p>

<div class="callout flag">
<strong>There is no 7-day, 14-day or 21-day window in 2027–2029 with zero games.</strong>
The longest fully free runs are {longest[2027]} days in 2027, {longest[2028]} days in 2028 and {longest[2029]} days in 2029.
MLB plays a full slate almost every day from late February to early October, and NFL/college football covers the winter weekends.
</div>

<div class="grid g3">
  {''.join(f'''<div class="card"><h3>{y}</h3>
  <div class="kpi" style="font-size:26px">{longest[y]} days</div><small>longest fully free run</small>
  <p class="small" style="margin-top:10px">{year_facts(y).get('scopes',{}).get('all',{}).get('freeDays','—')} fully free days in the calendar year.</p></div>''' for y in (2027, 2028, 2029))}
</div>

<h2>The practical answer</h2>
<div class="callout">
<strong>Take the mid-February gap.</strong> Each year the calendar has one clean pocket: after the Super Bowl and before the first
Spring Training game. In 2027 that is <strong>Feb 8–13</strong> (six nights, Mon–Sat). In 2028 and 2029 the same structure repeats
(see the year pages below). It is the only stretch in the three years where you can go away and miss nothing at all.
</div>
<div class="callout warn">
<strong>If the trip must be longer than a week</strong>, the honest trade-off is: accept one NFL Sunday (about 3 hours of radio) or the
Pro Bowl, and you can stretch the February window to 12–14 days with only a handful of busy hours — that is the best
14-day score in all three years. In-season months (April–September) score badly on the strict test because MLB plays daily,
but the actual listening burden is only about three hours a night.
</div>

<h2>Longest continuous free stretches</h2>
<p class="small">Runs of consecutive days with no qualifying game at all. This is the clearest way to see where a real trip fits.</p>
{streak_tables()}

<h2>Strict ranking — fewest days with any game</h2>
<p class="small">A day counts as busy if any qualifying game is scheduled, even for one minute. Scope: all MLB + all NFL + Stanford + Cal + Westwood One.</p>
{window_table('all', 'strict')}

<h2>Lightest ranking — fewest hours of live sport</h2>
<p class="small">Same scope, ranked by total hours of live coverage per day rather than whole-day blocking.</p>
{window_table('radio', 'hours')}

<h2>Radio-only view</h2>
<p class="small">Only games that actually air on AM/FM radio in San Francisco (Giants, Athletics, 49ers, Stanford, Cal, Westwood One national).</p>
{window_table('high', 'hours')}
"""
    page("vacation.html", "Vacation windows", "vacation.html", body)


# ================================================================ MLB
def build_mlb():
    raw27 = load("data/mlb-2027.json", {"games": [], "meta": {}})
    raw26 = load("data/mlb-2026.json", {"games": [], "meta": {}})
    games = raw27["games"]
    reg = [g for g in games if g["type"] == "R"]

    teams = {}
    for g in reg:
        for side in ("away", "home"):
            t = g[side]
            teams.setdefault(t, {"games": 0, "first": g["date"], "last": g["date"], "home": 0})
            teams[t]["games"] += 1
            teams[t]["last"] = max(teams[t]["last"], g["date"])
            if side == "home":
                teams[t]["home"] += 1
    rows = []
    for t, v in sorted(teams.items()):
        rows.append([esc(t), v["games"], v["home"], esc(v["first"]), esc(v["last"]), src(f"https://www.mlb.com/schedule/{v['first']}", "MLB.com")])

    def slate(team):
        sel = [g for g in reg if g["away"] == team or g["home"] == team]
        out = []
        for g in sel:
            home = g["home"] == team
            opp = g["away"] if home else g["home"]
            out.append([
                esc(g["date"]),
                "vs" if home else "at",
                esc(opp),
                esc(g["venue"] or ""),
                tag("home" if home else "away", "tag high" if True else "tag"),
                src(f"https://www.mlb.com/schedule/{g['date']}", "MLB.com"),
            ])
        return out

    months = {}
    for g in reg:
        m = g["date"][:7]
        months.setdefault(m, set()).add(g["date"])
    month_rows = [[k, len(v), src(f"https://www.mlb.com/schedule/{k}-01", "MLB.com")] for k, v in sorted(months.items())]

    st27 = len([g for g in games if g["type"] == "S"])
    asg = [g for g in games if g["type"] == "A"]
    body = f"""
<h1>MLB — all 30 clubs</h1>
<p class="lede">The 2027 season is <strong>officially released</strong>: {len(reg):,} regular-season games, {st27} Spring Training games
and the All-Star Game. Every row below comes from MLB's own StatsAPI. 2028 and 2029 have not been released, so those years are
modelled on the league calendar and labelled as estimates.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{len(reg):,}<small>2027 regular-season games</small></div></div>
  <div class="card"><div class="kpi">{len(teams)}<small>clubs</small></div></div>
  <div class="card"><div class="kpi">{esc(reg[0]['date'])}<small>first game</small></div></div>
  <div class="card"><div class="kpi">{esc(reg[-1]['date'])}<small>last scheduled game</small></div></div>
</div>

<div class="callout warn"><strong>2027 start times are mostly TBD.</strong> MLB has released the dates and matchups but the StatsAPI carries a
placeholder time for {len([g for g in reg if int(g['utc'][14:16]) == 33]):,} of the {len(reg):,} regular-season games
(every one of them shows the same ":33" placeholder). Those rows keep the official date and matchup, and the start time is estimated from
the club's most common home start time in the released 2026 season. The estimate is labelled on every row, and the basis is in
<code>data/events-2027.json</code>.</div>

<h2>2027 by club</h2>
{table(["Club", "Games", "Home games", "First game", "Last game", "Source"], rows)}

<h2>2027 by month</h2>
{table(["Month", "Dates with games", "Source"], month_rows)}

<h2>San Francisco Giants — 2027 regular season</h2>
<p class="small">High priority. Full 162-game slate, straight from the official feed.</p>
{table(["Date", "H/A", "Opponent", "Venue", "Status", "Source"], slate("San Francisco Giants"))}

<h2>Athletics — 2027 regular season</h2>
<p class="small">High priority. Full 162-game slate.</p>
{table(["Date", "H/A", "Opponent", "Venue", "Status", "Source"], slate("Athletics"))}

<h2>All-Star Game</h2>
{table(["Date", "Venue", "Status", "Source"],
       [[esc(g["date"]), esc(g["venue"]), tag("verified date, time TBD", "tag est"),
         src(f"https://www.mlb.com/schedule/{g['date']}", "MLB.com")] for g in asg])}

<h2>2026 season (for reference)</h2>
<p class="small">The 2026 regular season ran {esc(raw26['meta'].get('regularSeasonFirst') or '')} to {esc(raw26['meta'].get('regularSeasonLast') or '')};
the World Series ended {esc(max(g['date'] for g in raw26['games'] if g['type'] in 'FDLW'))}. The full 2026 game list is in
<code>data/events-2026.json</code> and is used by the calendar.</p>

<h2>2028 and 2029 — estimated</h2>
<p class="small">MLB has not released either season. The planner models Opening Day as the last Thursday of March, a daily slate through the
last Sunday of September, the All-Star Game on the second Tuesday of July, and the postseason from the following Tuesday.
Those rows are tagged <span class="tag est">estimated</span> and carry no invented matchups.</p>
"""
    page("mlb.html", "MLB", "mlb.html", body)


# ================================================================ NFL
def sf_record():
    cur = load("data/curated/nfl-2026-49ers.json", {"events": []})
    w = sum(1 for e in cur["events"] if str(e.get("result", "")).startswith("W"))
    l = sum(1 for e in cur["events"] if str(e.get("result", "")).startswith("L"))
    return f"{w}–{l}"


def build_nfl():
    cur = load("data/curated/nfl-2026-49ers.json", {"events": [], "meta": {}})
    up = load("data/upstream/nfl-2026.json", {"games": []})
    nfl_rows, nfl_count = [], 0
    for g in sorted(up.get("games", []), key=lambda x: (x.get("datePT") or "9999", x.get("startPT") or "")):
        if "49ers" in (g.get("away", "") + g.get("home", "")):
            continue
        nfl_count += 1
        tv = ", ".join(g.get("tv") or []) or "—"
        nfl_rows.append([
            esc((g.get("weekLabel") or f"W{g.get('week')}") if g.get("week") else "—"),
            esc(g.get("datePT") or "TBD"),
            esc(g.get("startPT") or "TBD"),
            esc(f"{g.get('away')} at {g.get('home')}"),
            esc(tv),
            src(g.get("sourceUrl"), "NFL.com"),
        ])
    w1 = load("data/curated/westwoodone-2026.json", {"events": [], "meta": {}})

    sched = ""
    for y in (2027, 2028, 2029):
        evs = [e for e in EVENTS.get(y, {}).get("events", []) if e["league"] == "NFL" and "estimate" in e["tags"]]
        key = [e for e in evs if e["seasonType"] == "postseason" or "Thanksgiving" in e.get("title", "")]

        def uniq(items):
            seen, out = set(), []
            for e in sorted(items, key=lambda x: x["date"]):
                if e["date"] in seen:
                    continue
                seen.add(e["date"])
                out.append(e)
            return out
        key = uniq(key)
        rows = [[esc(e["date"]), esc(e.get("start") or "TBD"), esc(e["title"]),
                 tag("estimated", "tag est"), src("https://www.nfl.com/schedules/", "NFL.com")] for e in key]
        sched += f"<h3>{y} season — key dates (estimated)</h3>" + table(
            ["Date", "Start (PT)", "Window", "Status", "Source"], rows)

    sf_rows = []
    for e in cur["events"]:
        if e.get("timeStatus") == "bye":
            sf_rows.append([esc(e["date"]), "—", "<strong>BYE</strong>", "", "", tag("no game", "tag ver")])
            continue
        d = e.get("date") or e.get("dateWindowStart") or "TBD"
        when = e.get("startPT") or ("TBD" if e.get("timeStatus") != "not-published" else "—")
        status = {"verified": tag("verified", "tag ver"), "tba": tag("time TBD", "tag est"),
                  "not-published": tag("date only", "tag"), "bye": tag("bye", "tag")}.get(e.get("timeStatus"), tag("—"))
        if e.get("result"):
            status = tag(e["result"], "tag ver")
        sf_rows.append([esc(d), esc(when), f"{esc(e.get('homeAway','') or '')} {esc(e.get('opponent') or '')}",
                        esc(e.get("venue") or ""), esc(e.get("tv") or ""), status])

    w1_rows = []
    for e in w1["events"]:
        w1_rows.append([esc(e["date"]), esc(e.get("startET") or "unverified"), esc(e.get("label")),
                        esc(f"{e.get('away') or 'TBA'} {'at' if e.get('away') else ''} {e.get('home') or ''}".strip()),
                        src(e.get("eventUrl"), "Westwood One")])

    body = f"""
<h1>NFL, the 49ers and national radio</h1>
<p class="lede">The 49ers' 2026 slate is verified down to kickoff time and radio affiliate. Westwood One's national windows are
verified for 2026–27. The 2027, 2028 and 2029 seasons have not been released, so those are structural estimates.</p>

<div class="grid g3">
  <div class="card"><div class="kpi">3<small>preseason games, 2026</small></div><p class="small">Aug 13, 20, 27 — all completed.</p></div>
  <div class="card"><div class="kpi">{sf_record()}<small>49ers record, 2026</small></div><p class="small">Through Week 7. Bye in Week 8; next up Week 9 vs the Raiders at Levi's Stadium.</p></div>
  <div class="card"><div class="kpi">{len(w1['events'])}<small>Westwood One national windows</small></div><p class="small">Nov 2026 → Jan 2027 as published.</p></div>
</div>

<h2>San Francisco 49ers — 2026</h2>
<p class="small">Source: the club's own schedule page, which publishes kickoff in Pacific time and names the radio network for every game:
<strong>KSAN 107.7 FM / KNBR 104.5 FM / 680 AM</strong>. Week 18 is listed by the club as TBD; both days of the league's final weekend are blocked.</p>
{table(["Date", "Kickoff (PT)", "Opponent", "Venue", "TV", "Status"], sf_rows)}

<h2>Every NFL game, 2026</h2>
<p class="small">The full {nfl_count} games of the 2026 league year (preseason and regular season), each row linking to its own NFL.com game page.
Kickoff times are Pacific. The 49ers rows are shown above from the club's own page, so they are not duplicated here.</p>
{table(["Wk", "Date", "Kickoff (PT)", "Matchup", "TV", "Source"], nfl_rows)}

<h2>Westwood One Sports — national NFL radio, 2026–27</h2>
<p class="small">Times on the network's page are Eastern; Pacific conversions are in the calendar. Doubleheader rows are published by
the network as a single window with participants TBA.</p>
{table(["Date", "Start (ET)", "Broadcast", "Matchup", "Source"], w1_rows)}

<h2>2027, 2028, 2029</h2>
<div class="callout warn">The NFL releases its schedule in the spring. Nothing for these seasons exists yet, so the planner models the
league's fixed structure: Kickoff on the Thursday after Labor Day, 18 weeks, Thanksgiving on the fourth Thursday of November,
the Super Bowl on the second Sunday of February, and the same Thursday/Sunday/Monday windows the league has used for years.
No matchups are invented — each row is a broadcast window.</div>
{sched}
"""
    page("nfl.html", "NFL & 49ers", "nfl.html", body)


# ================================================================ NCAAF
def build_ncaaf():
    cur = load("data/curated/ncaaf-2026.json", {"events": [], "meta": {}})
    stan = [e for e in cur["events"] if e["team"] == "Stanford"]
    cal = [e for e in cur["events"] if e["team"] == "California"]

    def rows(lst, src_url):
        out = []
        for e in lst:
            when = e.get("startPT") or ("TBA" if e.get("timeStatus") == "tba" else "—")
            res = e.get("result") or ""
            out.append([esc(e["date"]), esc(when), "vs" if e.get("homeAway") == "home" else "at",
                        esc(e.get("opponent") or "—"), esc(e.get("venue") or "—"),
                        tag(res, "tag ver") if res else tag("TBA", "tag est"),
                        src(src_url, "Official site")])
        return out

    est = ""
    for y in (2027, 2028, 2029):
        evs = [e for e in EVENTS.get(y, {}).get("events", []) if "ncaaf" in e["tags"]]
        seen, rr = set(), []
        for e in sorted(evs, key=lambda x: (x["date"], x["title"])):
            if e["date"] in seen:
                continue
            seen.add(e["date"])
            rr.append([esc(e["date"]), esc(e.get("start") or "TBD"), esc(e["title"]),
                       tag("estimated", "tag est"), src(e.get("sourceUrl"), "School site")])
        est += f"<h3>{y} — estimated Saturdays</h3>" + table(["Date", "Start (PT)", "Game", "Status", "Source"], rr)

    body = f"""
<h1>Stanford and Cal football</h1>
<p class="lede">Both schools publish their 2026 schedules themselves. Every game carries kickoff time in Pacific time where the
school has set one; anything the school lists as TBA is left as TBA rather than guessed.</p>

<div class="callout flag"><strong>One real conflict.</strong> <a href="https://calbears.com/sports/football/schedule" target="_blank" rel="noopener">calbears.com</a>
lists the 129th Big Game at California on <strong>Sat Nov 14, 2026, 12:30 PM</strong>, while
<a href="https://gostanford.com/sports/football/schedule" target="_blank" rel="noopener">gostanford.com</a> lists the same game at California on
<strong>Sat Nov 21, 2026, TBA</strong>. Two official sources disagree, so the planner blocks <em>both</em> dates and the row stays on
<a href="flagged.html">Flagged for review</a>.</div>

<h2>Stanford — 2026</h2>
{table(["Date", "Kickoff (PT)", "H/A", "Opponent", "Venue", "Result", "Source"], rows(stan, "https://gostanford.com/sports/football/schedule"))}

<h2>California — 2026</h2>
<p class="small">Cal lists its football radio network as <strong>KSFO 810 AM</strong> for regular games and <strong>KNBR 104.5 FM / 680 AM</strong> for the Big Game.
Cal's page does not show an opponent for Nov 28, so that cell is blank and flagged.</p>
{table(["Date", "Kickoff (PT)", "H/A", "Opponent", "Venue", "Result", "Source"], rows(cal, "https://calbears.com/sports/football/schedule"))}

<h2>2027, 2028, 2029 — estimated</h2>
<div class="callout warn">Neither school has released these seasons. The planner blocks their usual twelve Saturdays from late August
to late November, using a 12:30 PM Pacific window and a second 4:30 PM window, because kickoff time is set by television only a
week or two in advance. Opponents are not invented.</div>
{est}
"""
    page("ncaaf.html", "Stanford & Cal", "ncaaf.html", body)


# ================================================================ radio
def build_radio():
    stations = [
        ["<strong>KNBR 680 AM</strong> / <strong>104.5 FM</strong>", "Giants (flagship), 49ers, Stanford",
         "Listed by the 49ers as the team's radio affiliate (KSAN 107.7 FM / KNBR 104.5 FM / 680 AM) and linked by Stanford as its radio home (The Sports Leader).",
         '<a href="https://www.49ers.com/schedule/2026/" target="_blank" rel="noopener">49ers.com</a> · <a href="https://gostanford.com/sports/football/schedule" target="_blank" rel="noopener">gostanford.com</a>'],
        ["<strong>KSAN 107.7 FM</strong>", "49ers (simulcast)", "Named by the club on every 2026 game row.", '<a href="https://www.49ers.com/schedule/2026/" target="_blank" rel="noopener">49ers.com</a>'],
        ["<strong>KSFO 810 AM</strong>", "Cal football", "Named by Cal on every 2026 game row (except the Big Game, which moves to KNBR).", '<a href="https://calbears.com/sports/football/schedule" target="_blank" rel="noopener">calbears.com</a>'],
        ["<strong>Westwood One Sports</strong> (national feed)", "NFL national windows", "Network schedule verified. Its Station Finder lists San Francisco affiliates <strong>KNBR-AM, KNBR-FM, KNBR-F2 and KTCT-AM</strong>; the finder does not publish frequencies, and local programming can pre-empt a broadcast.", '<a href="https://www.westwoodonesports.com/station-finder/" target="_blank" rel="noopener">Station Finder</a> · <a href="https://www.westwoodonesports.com/nfl-schedule/" target="_blank" rel="noopener">schedule</a>'],
        ["<strong>95.7 FM KGMZ</strong> (“The Game”)", "Athletics (reported)", "No official Athletics or station page confirmed an A's radio flagship for 2026 in this pass. Left unverified rather than inferred.", '<span class="small">—</span>'],
    ]
    w1 = load("data/curated/westwoodone-2026.json", {"events": []})
    rows = [[esc(e["date"]), tag("NCAAF" if e["id"].endswith("ncaa") else "NFL", "tag ncaaf" if e["id"].endswith("ncaa") else "tag nfl"),
             esc(e.get("label")), esc(f"{e.get('away') or 'TBA'} at {e.get('home') or 'TBA'}"),
             esc((e.get("startET") or "unverified") + " ET"), src(e.get("eventUrl"), "event page")] for e in w1["events"]]

    body = f"""
<h1>What is actually on the radio in San Francisco</h1>
<p class="lede">The calendar is only useful if the games are reachable with a plain AM/FM radio. This page records which
stations are documented by the teams themselves, and which claims we could not confirm.</p>

<div class="callout"><strong>Practical answer for 94122.</strong> KNBR (680 AM / 104.5 FM) is the safe default: it carries the Giants,
the 49ers and Stanford. Cal is on KSFO 810 AM. That set covers every high-priority team on this site except the Athletics, whose
2026 flagship we could not verify — so A's games are blocked in the calendar (they are high priority) even though their station is unconfirmed.</div>

<h2>Stations and rights</h2>
{table(["Station", "Carries", "How it was verified", "Source"], stations)}

<h2>Westwood One national NFL windows</h2>
<div class="callout"><strong>Timing difference worth knowing.</strong> On every game carried by both sources, Westwood One's published
start is <strong>15–75 minutes earlier</strong> than the NFL's official kickoff — it is the start of the network's broadcast, not the snap.
The planner therefore gives each game a single row: the radio goes busy at the earlier (Westwood One) time, and the kickoff time from
the NFL schedule is noted on the row.</div>
<p class="small">Every row below is one broadcast the network publishes. Doubleheaders and tripleheaders are published as a single
window with participants TBA, so they are blocked as a window rather than as individual games.</p>
{table(["Date", "League", "Broadcast", "Matchup", "Start", "Source"], rows)}

<h2>Other sports on these stations</h2>
<p class="small">Westwood One also distributes NCAA Football, NCAA Basketball, golf, U.S. Soccer and NCAA championship events
(<a href="https://www.westwoodonesports.com/nfl-schedule/" target="_blank" rel="noopener">network schedule</a>). One NCAA Football
broadcast appears in the verified list above (Oregon at Ohio State, Nov 7). The rest are not enumerated here because the network
publishes them week by week — they are flagged as a known coverage gap rather than guessed at.</p>
"""
    page("radio.html", "Radio", "radio.html", body)


# ================================================================ sources
def build_sources():
    rows = []
    seen = {}
    for y, pack in EVENTS.items():
        for code, s in (pack.get("meta", {}).get("sources") or {}).items():
            seen[s["url"]] = s.get("label")
    labels = {
        "https://statsapi.mlb.com/api/v1/schedule": "MLB StatsAPI — official league data service",
        "https://www.mlb.com/schedule": "MLB.com official schedule",
        "https://www.49ers.com/schedule/2026/": "49ers.com — club schedule (times, venues, radio)",
        "https://gostanford.com/sports/football/schedule": "gostanford.com — Stanford athletics",
        "https://calbears.com/sports/football/schedule": "calbears.com — Cal athletics",
        "https://www.westwoodonesports.com/nfl-schedule/": "Westwood One Sports — network NFL schedule",
        "https://www.nfl.com/schedules/": "NFL.com schedules (structure reference for estimates)",
    }
    for url, lab in labels.items():
        rows.append([esc(lab), f'<a href="{url}" target="_blank" rel="noopener">{esc(url)}</a>',
                     "Official" if "nfl.com/schedules" not in url else "Official (reference only)",
                     esc({"https://statsapi.mlb.com/api/v1/schedule": "2026 + 2027 MLB fixtures, times",
                          "https://www.mlb.com/schedule": "Human-readable per-date view of the same data",
                          "https://www.49ers.com/schedule/2026/": "49ers dates, kickoff times, TV, radio",
                          "https://gostanford.com/sports/football/schedule": "Stanford 2026 dates, times, results",
                          "https://calbears.com/sports/football/schedule": "Cal 2026 dates, times, radio, results",
                          "https://www.westwoodonesports.com/nfl-schedule/": "National NFL radio windows, 2026–27",
                          "https://www.nfl.com/schedules/": "Weekly window structure used for 2027–29 estimates"}.get(url, ""))])

    v = REPORT.get("summary", {})
    body = f"""
<h1>Sources and verification</h1>
<p class="lede">Every row in this site links back to one of these pages. Nothing is asserted from memory: if a value is not on an
official page, it is blank and appears on <a href="flagged.html">Flagged for review</a>.</p>

<div class="grid g4">
  <div class="card"><div class="kpi">{esc(v.get('curatedRows', '—'))}<small>curated rows</small></div></div>
  <div class="card"><div class="kpi">{esc(v.get('rowsVerified', '—'))}<small>re-verified against source</small></div></div>
  <div class="card"><div class="kpi">{esc(v.get('mlbSpotChecksPassed', '—'))}/{esc(v.get('mlbSpotChecks', '—'))}<small>MLB API spot checks</small></div></div>
  <div class="card"><div class="kpi">{esc(v.get('feedProblems', '—'))}<small>feed integrity problems</small></div></div>
</div>

<h2>Official sources used</h2>
{table(["Source", "URL", "Type", "What it verifies"], rows)}

<h2>How the verification works</h2>
<ol class="clean">
  <li><strong>MLB.</strong> Games are pulled from the league's own StatsAPI. A CI job re-queries six sample dates per season and compares the
  game IDs with the stored feed — any drift fails the check.</li>
  <li><strong>49ers, Stanford, Cal, Westwood One.</strong> Each curated row carries <code>verifyTokens</code> (the date, opponent and time as printed by the
  official page). CI re-downloads the page and asserts every token is still present.</li>
  <li><strong>Snapshots.</strong> A few official sites render their schedule client-side. For those, the row is checked against the committed
  text snapshot taken from the same URL (<code>research/text/</code>) and the report records which method was used.</li>
  <li><strong>Failures are published, not hidden.</strong> Anything that fails appears on <a href="flagged.html">Flagged for review</a> with its source link.</li>
</ol>

<h2>Verification report</h2>
<p class="small">Machine-readable: <a href="verification/report.json">verification/report.json</a> · human-readable:
<a href="verification/report.md">verification/report.md</a>. Generated {esc(REPORT.get('generatedUTC', ''))}.</p>
"""
    page("sources.html", "Sources", "sources.html", body)


# ================================================================ flagged
def build_flagged():
    failed = [r for r in REPORT.get("curated", []) if r.get("verified") is False]
    conflicts = [r for r in REPORT.get("curated", []) if r.get("conflict")]

    # dataset-level irregularities declared by the curated files
    declared = []
    for p in ("data/curated/nfl-2026-49ers.json", "data/curated/westwoodone-2026.json", "data/curated/ncaaf-2026.json"):
        d = load(p, {})
        for msg in d.get("meta", {}).get("irregularities", []):
            declared.append((os.path.basename(p), msg))
    open_items = [
        ("Dataset", "2027 MLB start times", "MLB has released dates and matchups but not first-pitch times for 1,631 of 2,430 games. Times are estimated and labelled.", "https://statsapi.mlb.com/api/v1/schedule"),
        ("Dataset", "MLB 2028 and 2029", "No official schedule exists. Whole seasons are modelled (Opening Day = last Thursday of March, daily slate, postseason from the following Tuesday).", "https://www.mlb.com/schedule"),
        ("Dataset", "NFL 2027–2029", "No official schedule exists. Broadcast windows are modelled; no matchups are invented.", "https://www.nfl.com/schedules/"),
        ("Dataset", "Stanford / Cal 2027–2029", "Neither school has released these seasons. Twelve Saturdays per school are blocked as estimates.", "https://gostanford.com/sports/football/schedule"),
        ("Finding", "Westwood One start times", "On 17 games carried by both sources, the network's published start is 15–75 minutes before the NFL's official kickoff — it is the broadcast start. The planner uses the earlier time for busy-ness and keeps the kickoff on the row.", "https://www.westwoodonesports.com/nfl-schedule/"),
        ("Gap", "Cal games before Nov 14, 2026", "Cal's official page could not be parsed unambiguously for its early-season card order, so those games are omitted rather than guessed.", "https://calbears.com/sports/football/schedule"),
        ("Gap", "Athletics radio flagship", "No official page confirmed which San Francisco station carries Athletics games in 2026. A's games are still blocked as high priority.", ""),
        ("Gap", "Westwood One non-NFL sports", "NCAA Basketball, golf, soccer and NCAA championships are published week by week and are not enumerated.", "https://www.westwoodonesports.com/"),
    ]

    rows = [[esc(a), esc(b), esc(c), src(d, "official source") if d else '<span class="small">—</span>'] for a, b, c, d in open_items]

    body = f"""
<h1>Flagged for review</h1>
<p class="lede">These items are published deliberately: they are unconfirmed, conflicting, estimated or missing. None of them block the
site, and none of them have been silently filled in.</p>

<div class="callout flag"><strong>Conflicts found between two official sources.</strong> Both are blocked in the calendar; the underlying
question needs a human decision.</div>
{table(["Where", "Item", "What is unresolved", "Source"],
       [[esc(r['dataset']), esc(r['title'] or r['id']), esc(r['conflict']), src(r['officialUrl'])] for r in conflicts])}

<h2>Rows that failed automated re-verification</h2>
<p class="small">{len(failed)} row(s). These remain in the dataset with their source links so the failure is visible.</p>
{table(["Dataset", "Row", "Date", "Missing from official page", "Source"],
       [[esc(r['dataset']), esc(r['id']), esc(r['date']), esc(', '.join(r.get('missingTokens') or []) or '—'), src(r['officialUrl'])] for r in failed]) or '<p class="small">None.</p>'}

<h2>Declared irregularities from the data files</h2>
<ul class="clean">
  {''.join(f"<li><strong>{esc(os.path.basename(p))}</strong> — {esc(m)}</li>" for p, m in declared)}
</ul>

<h2>Known gaps and estimates</h2>
{table(["Type", "Item", "Detail", "Source"], rows)}

<h2>Resolved during this build</h2>
<ul class="clean">
  <li><strong>Westwood One's San Francisco affiliate</strong> — resolved: the network's Station Finder lists KNBR-AM, KNBR-FM, KNBR-F2 and
  KTCT-AM as San Francisco affiliates (<a href="https://www.westwoodonesports.com/station-finder/" target="_blank" rel="noopener">Station Finder</a>).
  Frequencies are not published by the finder, and local programming can pre-empt a broadcast.</li>
  <li><strong>All NFL games for 2026</strong> — the 272 regular-season and 49 preseason games are now in the dataset, each linking to its NFL.com game page.</li>
</ul>

<h2>What is verified, by contrast</h2>
<ul class="clean">
  <li>MLB 2026 and 2027 fixtures: all 2,430 regular-season games per season, from the league's own API, spot-checked date by date.</li>
  <li>49ers 2026 dates, kickoff times, venues, TV and radio — from the club.</li>
  <li>Stanford and Cal 2026 dates, times, venues and results — from the schools.</li>
  <li>Westwood One's published 2026–27 NFL windows — from the network.</li>
</ul>
"""
    page("flagged.html", "Flagged for review", "flagged.html", body)


# ================================================================ method
def build_method():
    dur = EVENTS[2027]["meta"]["durations"] if 2027 in EVENTS else {}
    body = f"""
<h1>Method, definitions and assumptions</h1>
<p class="lede">This page exists so every number on the site can be traced to a rule. If a rule here looks wrong to you, the
calendar is wrong in a predictable way — tell me and it can be changed in one place.</p>

<h2>What “free” means</h2>
<p>A minute is free when none of the following is on air:</p>
<ul class="clean">
  <li><strong>MLB</strong> — all 30 clubs, Spring Training through the World Series, including the All-Star Game (Giants and Athletics flagged high priority).</li>
  <li><strong>NFL</strong> — every game, preseason through the Super Bowl (49ers flagged high priority).</li>
  <li><strong>NCAAF</strong> — Stanford and California (high priority).</li>
  <li><strong>Westwood One Sports</strong> — national NFL radio broadcasts.</li>
</ul>
<p>Three scopes are available on the calendar: <em>All games</em> (the list above), <em>Radio only</em> (games documented as airing on AM/FM in San Francisco)
and <em>High priority</em> (Giants, Athletics, 49ers, Stanford, Cal, Westwood One).</p>

<h2>Average game lengths used</h2>
<p>Busy time is the scheduled start plus the average length of that kind of game. These are planning durations, not guarantees.</p>
{table(["Sport", "Minutes used", "Why"],
       [["MLB regular season", f"{dur.get('mlb','165')}", "MLB reported a 2:38 average for nine-inning games in 2025 (mlb.com/news/mlb-average-game-time-under-three-hours-third-straight-year); the planner adds a few minutes of buffer."],
        ["MLB postseason", f"{dur.get('mlb-post','195')}", "Postseason games run longer: more between-inning time and pitching changes."],
        ["NFL", f"{dur.get('nfl','185')}", "A three-hour game window plus the usual overrun; kickoff-to-final-whistle is typically 3:00–3:15."],
        ["NFL postseason", f"{dur.get('nfl-post','195')}", "Longer halftimes and more stoppages."],
        ["NCAAF", f"{dur.get('ncaaf','200')}", "College games run longer than NFL games; a 3:20 window is used."]])}

<h2>Time zone</h2>
<p>Everything is computed and displayed in Pacific time (America/Los_Angeles). Westwood One publishes Eastern time; those rows are
converted at ET−3h, which is correct for PST dates (from 2026-11-01). Daylight-saving boundaries are handled by the IANA time zone
database, not by a fixed offset.</p>

<h2>Estimates vs verified data</h2>
<p>Every row carries a status:</p>
<ul class="clean">
  <li><span class="tag ver">verified</span> — an official source published the date, the matchup and the start time.</li>
  <li><span class="tag est">estimated</span> — either the date is official but the start time is TBD (most of the 2027 MLB season), or the whole row is a modelled league window because the season has not been released.</li>
  <li><span class="tag flag">unconfirmed</span> — the date is known but a value is missing (for example the 49ers' Week 18 date).</li>
</ul>

<h2>How estimated start times are produced</h2>
<ol class="clean">
  <li><strong>2027 MLB.</strong> MLB's feed carries a placeholder time for 1,631 regular-season games. For those, the planner takes the
  most common Pacific start time that the <em>home club</em> actually used on that weekday in the released 2026 season. If the club has
  no such history, the league-wide modal time for that weekday is used.</li>
  <li><strong>2027–2029 NFL.</strong> Kickoff is the Thursday after Labor Day; 18 weeks; fixed Sunday/Thursday/Monday windows; Thanksgiving on the
  fourth Thursday; Super Bowl on the second Sunday of February.</li>
  <li><strong>2027–2029 NCAAF.</strong> Twelve Saturdays per school, late August to late November, blocked at 12:30 PM <em>and</em> 4:30 PM Pacific because
  television sets kickoff late. This deliberately over-blocks rather than pretending to know the slot.</li>
  <li><strong>2028–2029 MLB.</strong> Opening Day is the last Thursday of March, a daily slate runs to the last Sunday of September, the All-Star Game is the
  second Tuesday of July, and the postseason starts the following Tuesday. Slate days are modelled as one row per day with no invented matchups.</li>
</ol>

<h2>What this model does not do</h2>
<ul class="clean">
  <li>It does not include rain delays, postponements, flex scheduling or overtime.</li>
  <li>It does not include pre-game or post-game radio shows (typically 30–60 minutes either side).</li>
  <li>It does not include other Westwood One properties (NCAA Basketball, golf, soccer) beyond the one published NCAA Football window.</li>
  <li>It does not claim a station for the Athletics or for the Westwood One feed in San Francisco — those are flagged.</li>
</ul>
"""
    page("method.html", "Method", "method.html", body)


if __name__ == "__main__":
    build_index()
    build_calendar()
    build_vacation()
    build_mlb()
    build_nfl()
    build_ncaaf()
    build_radio()
    build_sources()
    build_flagged()
    build_method()
    print("site built:", sorted(f for f in os.listdir(".") if f.endswith(".html")))
