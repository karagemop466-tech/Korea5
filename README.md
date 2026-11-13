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

## What is in here

| Path | What it is |
|---|---|
| `*.html` | The published site (static, no build step at deploy time) |
| `assets/` | Stylesheet and the calendar JavaScript |
| `data/mlb-2026.json`, `data/mlb-2027.json` | Official MLB schedules pulled from the MLB StatsAPI |
| `data/curated/` | Hand-checked NFL, Westwood One and NCAAF rows, each with `verifyTokens` and a source URL |
| `data/nfl-intel/` | NFL intelligence dataset: 137 verified 2026 finals, standings, Week-10 injuries, model output (ratings, originated lines, backtest), strategies, suggestions, questions |
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
python3 scripts/nfl_intel.py      # NFL ratings, originated lines, walk-forward backtest (writes data/nfl-intel/model.json)
python3 scripts/build_nfl_intel.py # regenerate the NFL intelligence pages
python3 tools/build_extra.py      # regenerate extra/ pages (calendar, stations, flagged, summary)
python3 scripts/check_links.py    # fail if any local link is broken
python3 tools/verify_extra.py     # 31 link, schema and UI checks
python3 scripts/verify.py         # re-check every curated row against its official page (needs network)
```

Data acquisition and verification run in GitHub Actions (`.github/workflows/`), because the schedule sources are only
reachable from a normal network. Everything the site needs is committed, so Pages can serve it statically.

## Honesty rules used throughout

* Every table row links to an official source.
* Where an official source has not published a value, the cell is blank and the row is listed on the Flagged page.
* Estimated rows are labelled and never invent matchups.

## NFL intelligence section (session `arena/f6d67da0-korea5`, 2026-11-13)

Seven new pages: [`nfl-intel.html`](nfl-intel.html) (hub), [`nfl-lines.html`](nfl-lines.html)
(originated spreads/totals, ratings, backtest), [`nfl-strategies.html`](nfl-strategies.html)
(strategy library, leaderboard rules, validation gates, correlation values),
[`nfl-injuries.html`](nfl-injuries.html) (Week-10 report + starter/backup deficiency flags),
[`nfl-executive.html`](nfl-executive.html) (mirror of
[`research/EXECUTIVE-SUMMARY-NFL.md`](research/EXECUTIVE-SUMMARY-NFL.md)),
[`suggestions.html`](suggestions.html) (review-before-implement register) and
[`questions.html`](questions.html) (information-gap register).

The model originates its own lines from verified results (opponent-adjusted margins; formulas
published on the Lines page) and is graded by a strictly walk-forward backtest — never by copying
market numbers. Market columns are deliberately blank and flagged: no verified odds source exists
(Q-ODDS). Validation gates G1–G4 pass for both core strategies; gates that need market data are
marked not-evaluable rather than assumed. Injury depth tiers are shown only where an official
source confirms them (see flags F33–F41 in `curated/flags.json`).

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
