#!/usr/bin/env python3
"""Generate README.md and research/EXECUTIVE-SUMMARY.md from the computed data."""
import json
from datetime import date


def load(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


A = load("data/derived/analysis.json", {})
R = load("verification/report.json", {})
M27 = load("data/mlb-2027.json", {"games": [], "meta": {}})


def fmt_range(a, b):
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    return (f"{da.strftime('%b %-d')} – {db.strftime('%b %-d, %Y')}" if da.year == db.year
            else f"{da.strftime('%b %-d, %Y')} – {db.strftime('%b %-d, %Y')}")


def streak(y):
    st = (A.get("freeStreaks", {}).get("all", {}).get(str(y)) or [])
    return st[0] if st else None


def win(scope, key, length, year):
    lst = A.get("vacations", {}).get(key, {}).get(str(length), [])
    for w in lst:
        if w["start"].startswith(str(year)):
            return w
    return None


reg = [g for g in M27["games"] if g["type"] == "R"]
st = [g for g in M27["games"] if g["type"] == "S"]
asg = [g for g in M27["games"] if g["type"] == "A"]
ph = [g for g in reg if int(g["utc"][14:16]) == 33]
summ = R.get("summary", {})

lines = []
add = lines.append
add("# Executive summary — when to take a vacation (2027, 2028, 2029)")
add("")
add("**Prepared for:** a listener in San Francisco (94122) who wants to travel when nothing he follows is live on the radio.")
add("")
add("**Live site:** https://karagemop466-tech.github.io/Korea5/  ·  **Data rebuilt:** "
    f"{A.get('meta', {}).get('generatedUTC', '')}  ·  **Verification report:** "
    f"`verification/report.json` ({summ.get('rowsVerified')}/{summ.get('rowsChecked')} curated rows re-verified)")
add("")
add("## 1. Bottom line")
add("")
add("**There is no fully free 7-day window in 2027, 2028 or 2029.** In all three years the longest stretch with nothing on air is "
    "exactly **six days**, and it recurs in January and February — the Monday-to-Saturday gaps between NFL playoff weekends — "
    "plus the gap between the Super Bowl and the first Spring Training game.")
add("")
add("Every year has several six-day gaps, all equivalent in length. They are:")
add("")
for y in (2027, 2028, 2029):
    st = (A.get("freeStreaks", {}).get("all", {}).get(str(y)) or [])
    opts = [x for x in st if x["days"] == (st[0]["days"] if st else 0)][:4]
    if opts:
        joined = "; ".join(f"**{fmt_range(x['start'], x['end'])}**" for x in opts)
        add(f"- **{y}** — {joined} ({opts[0]['days']} days each)")
add("")
add("Of those, the one after the Super Bowl and before Spring Training is usually the easiest to travel in: "
    "the baseball season has not started, and the only adjacent event is the Super Bowl itself.")
add("")
add("If the trip can only be two weeks or longer, the honest trade-off is one NFL Sunday (about three hours of radio) or the "
    "Pro Bowl; the best 14-day windows are listed in section 4.")
add("")
add("## 2. Why a whole week never clears")
add("")
add(f"* **MLB plays almost every day.** The 2027 season is officially released: **{len(reg):,} regular-season games**, "
    f"{len(st)} Spring Training games and the All-Star Game ({asg[0]['date'] if asg else 'TBD'}, {asg[0]['venue'] if asg else ''}). "
    f"It runs {M27['meta']['regularSeasonFirst']} → {M27['meta']['regularSeasonLast']}. Between mid-February and early October there are only a "
    "handful of days without a Major League game, and they are the All-Star break.")
add("* **The NFL owns the winter weekends.** Sunday, Monday and Thursday windows from September to early January, then the playoffs into February.")
add("* **College football owns the autumn Saturdays**, and Stanford and Cal both play twelve of them.")
add("* The two sports overlap in September–October, which closes the only gap the baseball season leaves.")
add("")
add("## 3. The verified 2027 MLB picture")
add("")
add(f"- {len(reg):,} regular-season games across all 30 clubs, from MLB's own StatsAPI.")
add(f"- {len(st)} Spring Training games; first regular-season day {M27['meta']['regularSeasonFirst']}, last {M27['meta']['regularSeasonLast']}.")
add(f"- **{len(ph):,} of the {len(reg):,} regular-season games have a placeholder start time** in the league feed (every one shows `:33`). "
    "Dates and matchups are official; the first-pitch time is not published yet. Those rows are labelled *estimated* and their start "
    "time is taken from the home club's most common start time on that weekday in the released 2026 season.")
add("")
add("## 4. Ranked vacation windows")
add("")
add("Ranking rule: fewest whole days that contain any game first, then fewest hours of live coverage. Full tables on the site.")
add("")
add("| Year | Trip length | Best window | Free days | Busy hours |")
add("|---|---|---|---|---|")
for y in (2027, 2028, 2029):
    for L in (7, 14, 21):
        w = win("all", "all", L, y)
        if w:
            add(f"| {y} | {L} days | {fmt_range(w['start'], w['end'])} | {w['freeDays']} / {L} | {w['busyHours']} |")
add("")
add("Lightest-schedule view (same windows ranked by hours of live sport rather than whole days):")
add("")
add("| Year | Trip length | Lightest window | Busy hours |")
add("|---|---|---|---|")
for y in (2027, 2028, 2029):
    for L in (7, 14):
        w = win("all", "all-hours", L, y)
        if w:
            add(f"| {y} | {L} days | {fmt_range(w['start'], w['end'])} | {w['busyHours']} |")
add("")
add("## 5. What is verified, and what is not")
add("")
add("| Layer | Status | Source |")
add("|---|---|---|")
add("| MLB 2026 + 2027 fixtures | **Verified** | MLB StatsAPI (league's own data service) |")
add("| 2027 MLB start times | Partly verified / estimated | MLB StatsAPI placeholder time; estimated per club history |")
add("| 49ers 2026 dates, times, TV, radio | **Verified** | 49ers.com |")
add("| Stanford, Cal 2026 | **Verified** | gostanford.com, calbears.com |")
add("| Westwood One national NFL 2026–27 | **Verified** | westwoodonesports.com |")
add("| NFL 2027–2029 | **Estimated** (structure only) | Modelled on the league calendar |")
add("| NCAAF 2027–2029 | **Estimated** (structure only) | Modelled on the schools' usual Saturdays |")
add("| MLB 2028–2029 | **Estimated** (structure only) | Modelled on the league calendar |")
add("")
add("## 6. Irregularities flagged for review")
add("")
add("1. **Big Game date conflict.** calbears.com lists the 129th Big Game on **Sat Nov 14, 2026, 12:30 PM**; gostanford.com lists it on "
    "**Sat Nov 21, 2026, TBA**. Both dates are blocked; the conflict is unresolved.")
add("2. **Mexico City kickoff conflict.** 49ers.com lists the Nov 22, 2026 game at **5:20 PM PST**; Westwood One lists **7:30 PM ET (4:30 PM PST)**. "
    "Both windows are blocked.")
add("3. **Westwood One, Dec 27, 2026 (JAX at DAL)** — kickoff time was not retrievable from the page; left blank and marked unverified.")
add("4. **Cal Nov 28, 2026** — the official page shows the date but no opponent; left blank.")
add("5. **Athletics radio flagship** — no official confirmation found for 2026; A's games are still blocked as high priority.")
add("6. **Westwood One's San Francisco affiliate** — not published on the pages verified.")
add("7. **Cal's early-season 2026 games** — the official page's card order could not be parsed unambiguously, so those rows are omitted rather than guessed.")
add("")
add("## 7. Sources")
add("")
add("| Source | Used for |")
add("|---|---|")
add("| https://statsapi.mlb.com/api/v1/schedule | All MLB fixtures and times |")
add("| https://www.mlb.com/schedule/2027-04-01 | Human-readable per-date view |")
add("| https://www.49ers.com/schedule/2026/ | 49ers dates, times, TV, radio |")
add("| https://gostanford.com/sports/football/schedule | Stanford 2026 |")
add("| https://calbears.com/sports/football/schedule | Cal 2026, Cal radio network |")
add("| https://www.westwoodonesports.com/nfl-schedule/ | National NFL radio windows |")
add("| https://www.nfl.com/schedules/ | Weekly window structure used for estimates |")
add("")
add("## 8. How to use the site")
add("")
add("* **Dashboard** — the headline answer, the next 14 days, and the best windows.")
add("* **Calendar** — a scoreboard-style day view with yesterday / today / tomorrow, a 24-hour free/busy bar, and the games on that day.")
add("* **Vacation windows** — every 7/14/21-day window ranked, plus the longest continuous free stretches.")
add("* **MLB / NFL & 49ers / Stanford & Cal** — the underlying tables, each row linking to its official source.")
add("* **Radio** — which station carries what, and what is unconfirmed.")
add("* **Flagged** — everything unresolved, with source links.")
add("* **Method** — definitions, game-length assumptions and how estimates are produced.")
add("")
add("## 9. Verification")
add("")
add(f"- {summ.get('curatedRows')} curated rows are re-checked in CI against the official page that publishes them: "
    f"{summ.get('rowsVerified')} passed, {summ.get('rowsFailed')} failed.")
add(f"- {summ.get('mlbSpotChecksPassed')}/{summ.get('mlbSpotChecks')} MLB API spot checks matched game-for-game.")
add(f"- {summ.get('feedProblems')} feed integrity problems (missing source links, malformed dates or times).")
add("- Failures are published on the Flagged page, not hidden.")

open("research/EXECUTIVE-SUMMARY.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")

readme = f"""# Free Time / Vacation Planner — MLB, NFL, Stanford, Cal, Westwood One radio

A year-round answer to one question: **when is there nothing on the radio worth staying home for?**
Coverage runs from {A.get('meta', {}).get('horizon', ['', ''])[0]} to {A.get('meta', {}).get('horizon', ['', ''])[1]}, computed in Pacific time for San Francisco 94122.

**Live site:** https://karagemop466-tech.github.io/Korea5/

## Headline finding

No 7-day window in 2027, 2028 or 2029 is completely free of MLB, NFL, Stanford/Cal football and Westwood One national radio.
The longest run with nothing on air is six days, and it recurs in January–February between NFL playoff weekends.

See [`research/EXECUTIVE-SUMMARY.md`](research/EXECUTIVE-SUMMARY.md) for the full write-up.

## What is in here

| Path | What it is |
|---|---|
| `*.html` | The published site (static, no build step at deploy time) |
| `assets/` | Stylesheet and the calendar JavaScript |
| `data/mlb-2026.json`, `data/mlb-2027.json` | Official MLB schedules pulled from the MLB StatsAPI |
| `data/curated/` | Hand-checked NFL, Westwood One and NCAAF rows, each with `verifyTokens` and a source URL |
| `data/events-<year>.json` | Normalized event feed the site reads (verified + estimated layers) |
| `data/derived/analysis.json` | Per-day free/busy windows, free streaks and ranked vacation windows |
| `verification/` | Machine-readable verification report and link check |
| `research/` | Executive summary, probe results, and text snapshots of official pages |
| `scripts/` | Fetch, build, analyze, verify, site and docs generators |

## Rebuild

```bash
python3 scripts/fetch_mlb.py      # official MLB feed (2026-2029; 2028/29 return nothing, by design)
python3 scripts/build_events.py   # normalize + add the labelled estimate layer
python3 scripts/analyze.py        # free/busy windows, free streaks, vacation ranking
python3 scripts/build_site.py     # regenerate the HTML
python3 scripts/check_links.py    # fail if any local link is broken
python3 scripts/verify.py         # re-check every curated row against its official page (needs network)
```

Data acquisition and verification run in GitHub Actions (`.github/workflows/`), because the schedule sources are only
reachable from a normal network. Everything the site needs is committed, so Pages can serve it statically.

## Honesty rules used throughout

* Every table row links to an official source.
* Where an official source has not published a value, the cell is blank and the row is listed on the Flagged page.
* Estimated rows are labelled and never invent matchups.
"""
open("README.md", "w", encoding="utf-8").write(readme)
print("docs written")
