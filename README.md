# Free Time / Vacation Planner — MLB, NFL, Stanford, Cal, Westwood One radio

A year-round answer to one question: **when is there nothing on the radio worth staying home for?**
Coverage runs from 2026-11-02 to 2030-02-28, computed in Pacific time for San Francisco 94122.

**Live site:** https://karagemop466-tech.github.io/Korea5/

## Headline finding

**No 7-, 14- or 21-day conflict-free vacation is certified for 2027–2029.**
This means unknown, not impossible: schedules, exact end times and local AM/FM carriage
are incomplete. Rankings describe provisional model gaps, not verified booking windows.
See [the certainty audit](certainty.html).
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
