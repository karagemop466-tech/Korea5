# Free Time / Vacation Planner — MLB, NFL, Stanford, Cal, Westwood One radio

A year-round answer to one question: **when is there nothing on the radio worth staying home for?**
Coverage runs from 2026-11-02 to 2030-02-28, computed in Pacific time for San Francisco 94122.

**Live site:** https://karagemop466-tech.github.io/Korea5/

## Headline finding (updated 2026-11-05)

**No 7-day stretch in 2027, 2028 or 2029 is free of every listed game.** The longest run with nothing on air is
**6 calendar days** in each year, in January–February between the NFL playoff rounds and the Super Bowl:

* **2027:** Mon Jan 25 – Sat Jan 30, or Mon Feb 1 – Sat Feb 6 (both 6 calendar days). If the Pro Bowl Games are on Tue Feb 9
  only, Feb 1–8 (8 calendar days) opens. If there is no Pro Bowl that week, Feb 1–13 (13 calendar days) opens.
* **2028** (ESTIMATION): Jan 24–29 or Jan 31 – Feb 5 (6 calendar days each).
* **2029** (ESTIMATION): Jan 22–27 or Jan 29 – Feb 3 (6 calendar days each).

The NFL has not published a 2027 Pro Bowl Games date; the two candidate days are unverified and both are blocked in the
base case. Westwood One carried the 2026 Pro Bowl, so it is in the radio tier. MLB's 2027 season is officially released;
2028 and 2029 MLB and 2027+ NFL schedules are not, so those rows are labelled **ESTIMATION**.

The earlier headline (Feb 1–13, 2027, 13 calendar days) is superseded. It assumed no Pro Bowl that week. The corrected
January 24 date is a Divisional playoff day, not a free day.

See [`research/EXECUTIVE-SUMMARY.md`](research/EXECUTIVE-SUMMARY.md) for the full write-up,
[Flagged for Review](flagged.html) for open items, and [the certainty audit](certainty.html) for what is still unverified.

## NFL lines, strategies and the injury tracker (2026-11-13)

Two companion sections work on the same question from opposite ends, and are meant to be read together:

| Section | What it is |
|---|---|
| [NFL Lines Lab](https://karagemop466-tech.github.io/Korea5/lab/index.html) | The **evidence** side, built only on official NFL records — the published injury report, official player game logs, the official Game Book — with measured correlations, dispersion figures and minimum-sample rules computed from them. |
| [NFL Lines Lab — model](https://karagemop466-tech.github.io/Korea5/nfl-lab/index.html) | The **model** side — a line model built and back-tested against third-party game data, reporting how it compares with the market spread. Market lines are left blank and flagged unverified. |
| [NFL Decision Support](https://karagemop466-tech.github.io/Korea5/nfl/index.html) | The **structured** side — the requirements list, the method and validation-gate reference, the leaderboard reward design and the source registry. |

None of the three publishes a validated edge, a win rate or a yield. Each says so on its own landing page, and each
keeps the leaderboard empty until a strategy passes every gate. The pages cross-link, so it is clear which side of the
question each one covers.

The [NFL Lines Lab](https://karagemop466-tech.github.io/Korea5/lab/index.html) is a new section for originating your own
NFL lines. It holds a **decision register** (15 open decisions with what is known, what is missing and how to close it),
a **catalogue of 12 candidate strategies** (singles, player props, prop combinations, parlays) each bound to **9 validation
gates**, **measured correlations and dispersion** computed from official NFL game data, an **injury and lineup-depth
tracker** built on the official weekly injury report and the official Game Book, a **paper-only leaderboard design**, and a
**suggestions register** with a recommended path so changes are decided before they are built.

Two measured results drive the design: two same-team receivers are **not independent** (r = -0.82 on the six matched
official games, 95% CI -0.98 to -0.02), and a +5 point edge at a -110 price needs **779** bets before it can be told apart
from luck. The repository holds **no market price, no settlement record and no forecast log**, so no win rate, yield, edge
or fair price is published anywhere, and the leaderboard is published empty on purpose.


### The data-backed NFL section (`nfl/system/`)

The **[NFL decision system](https://karagemop466-tech.github.io/Korea5/nfl/system/index.html)** is the part of this
repository that ingests official data rather than curating excerpts. It pulls, in CI, every completed final score
(**185** from 2026, **272** from 2025), the **full official injury report** (3,117 rows for 2026 weeks 1–10 and
5,783 for 2025), **all 32 club depth charts** (1,762 entries; 31 clubs parse — Houston publishes its chart as an
image and is left blank rather than guessed), **7 official team-stat tables**, player-stat leaders and all 32
rosters, then computes rest days, scoring rates, de-vig arithmetic and a shuffle test from those files.

Three findings worth reading first:

1. **The home-field "edge" is a coin at this sample.** 232 of 453 decided games went to the home team in 2025–26
   (51.2%, 90% CI 47.4–55.1%), and the shuffle test returns p = 1.000. That is the correct reading and the reason
   the skill-vs-luck gate exists.
2. **No price exists, so nothing is certified.** The official NFL week, game and stat pages were probed by exact
   regex for odds fields: **zero hits**. With no price no bet can be settled, so the leaderboard ranks nobody and
   says so on every row instead of printing a zero.
3. **Two facts are kept apart on purpose.** Injury status is not a lineup and a depth chart is not a snap count.
   The "next man up" table names a replacement only when the club's own chart names the next tier — verified live
   against Detroit's chart (Cade Mays → Juice Scruggs, D.J. Reed → Rock Ya-Sin).

Start with the [executive summary](https://karagemop466-tech.github.io/Korea5/nfl/system/summary.html), then the
[questions and gaps](https://karagemop466-tech.github.io/Korea5/nfl/system/questions.html) (18 decisions, each with what we
have, what we lack and the official source that would close it), the
[suggestions register](https://karagemop466-tech.github.io/Korea5/nfl/system/suggestions.html) (22 proposals with options,
cost, risk and gate), and the [flagged page](https://karagemop466-tech.github.io/Korea5/nfl/system/flagged.html) for what
remains unresolved.

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
| `lab/` | **NFL Lines Lab** — decision register, strategy catalogue and gates, measured correlations, injury & depth tracker, leaderboard design, suggestions |
| `data/lab/` | Official NFL records behind the lab (Week 10 injury report, player game logs, official Game Book) and the computed analysis |
| `curated/nfl-lab.json` | The curated lab specification: questions, strategies, gates, depth rules, leaderboard rules, suggestions, flags |

## Rebuild

```bash
python3 scripts/analyze_lab.py    # NFL lab: dispersion, correlations, minimum-observation rules
python3 tools/build_lab.py        # regenerate lab/ pages from curated/nfl-lab.json + data/lab/
python3 tools/verify_lab.py       # every published lab row carries a source or is an explicit blank
python3 scripts/fetch_mlb.py      # official MLB feed (2026-2029; 2028/29 return nothing, by design)
python3 scripts/build_events.py   # normalize + add the labelled estimate layer
python3 scripts/analyze.py        # free/busy windows, free streaks, vacation ranking
python3 scripts/build_site.py     # regenerate the HTML
python3 tools/build_extra.py      # regenerate extra/ pages (calendar, stations, flagged, summary)
python3 scripts/check_links.py    # fail if any local link is broken
python3 tools/verify_extra.py     # 31 link, schema and UI checks
python3 scripts/verify.py         # re-check every curated row against its official page (needs network)
python3 nfl/system/tools/analyze_market.py   # recompute the NFL section's numbers
python3 nfl/system/tools/build_nfl.py        # regenerate nfl/system/*.html
python3 nfl/system/tools/verify_nfl.py       # 99 link, source, badge and no-false-claim checks
```

Data acquisition and verification run in GitHub Actions (`.github/workflows/`), because the schedule sources are only
reachable from a normal network. Everything the site needs is committed, so Pages can serve it statically.

## Honesty rules used throughout

* Every table row links to an official source.
* Where an official source has not published a value, the cell is blank and the row is listed on the Flagged page.
* Estimated rows are labelled and never invent matchups.

## Second-pass integration (session `arena/ef8b5b30-korea5`)

The `extra/` section adds official feeds that the first site did not include, with its own navigation, a
Prev/Next/Today day scoreboard and a clearly labelled **Flagged for Review** page:

| Path | What it is |
|---|---|
| `extra/*.html` | Official-feed hub, day scoreboard, NFL 2026 (all 321 games), Westwood One all-sport events, SF 94122 stations, season anchors, durations/halftime, future Stanford/Cal dates, estimates, free-window ranking, executive summary, source registry, flagged register, verification and link report |
| `official/` | CI-fetched official NFL by-week feed, Westwood One event-grid/event-detail feed, station finder, and MLB StatsAPI `startTimeTBD` flags |
| `curated/` | Source registry, season anchors, station table, durations, future NCAAF dates, estimate windows, flagged irregularities, verbatim rulebook excerpts |
| `extra/data/` | Generated combined calendar, vacation ranking and verification/link reports |
| `tools/*-ef8b5b30.yml` / `tools/fetch_official.py` / `tools/extract_rules.py` | CI fetchers (GitHub Actions has outbound internet; the sandbox does not) |
| `tools/build_extra.py` / `tools/verify_extra.py` | Generate the extra pages and re-verify every row, source link and local link line by line |
|  `nfl/system/` | The data-backed NFL decision system: 14 pages, curated registers, 96+ checked assertions |
|  `nfl/system/tools/` | `probe.py` (what each official page really returns), `fetch_official.py` (CI ingest), `analyze_market.py` (every published number), `build_nfl.py` (pages), `verify_nfl.py` (99 checks) |
|  `nfl/system/data/` | Official feeds (`official-*.json`) + the committed fetch report |
|  `nfl/system/data/derived/` | Every computed value, each with its n, interval and label |

Rebuild the second pass after the first-pass scripts:

```bash
python3 tools/build_extra.py       # regenerate extra/*.html + extra/data/*.json and update root nav
python3 tools/verify_extra.py      # 31 checks: local links, source links, JSON integrity, labels, nav
```

The exact label **ESTIMATION — not a real verified released schedule** appears on every row whose schedule has
not been officially released (2028/2029 MLB, 2027 NFL, 2027–2029 Westwood One postseason). Flagged items are
published and do **not** block the Pages deployment.

## Certainty audit (2026-11-03)

After either generator runs, publish the certainty policy and disclosure banners:

```bash
python3 scripts/audit_certainty.py
python3 scripts/check_links.py
python3 tools/verify_extra.py
```

Local tests check structure and links, not complete source-fact verification. Historical
verification reports are preserved with their original timestamps. All future vacation
windows remain provisional. `certainty.html` lists the outstanding evidence limits.
