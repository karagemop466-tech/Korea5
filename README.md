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

---

# NFL lines lab (added 2026-11-13)

A separate section under `nfl-lines/` that answers the NFL question directly: *can I originate my own lines, and
are the strategies any good?* It is a research instrument, not betting advice, and it is linked from every page of
the planner above.

**Start here:** [`nfl-lines/index.html`](nfl-lines/index.html) ·
[executive summary](research/NFL-LINES-EXECUTIVE-SUMMARY.md) ·
[repo review](verification/nfl-lines-review-6b0481c7.md)

## What it says in one line

Fair lines are produced for all 13 priced 2026 Week 11 games, and **none of the 8 backtested strategies has
demonstrated skill rather than luck** — every 95% interval includes zero and no p-value survives correction across
the family. Player props and same-game parlays are **blocked** because no prop prices exist anywhere reachable.
Measured injury / backup-tier effects are indistinguishable from zero.

## Pages

| Page | What it holds |
|---|---|
| `nfl-lines/index.html` | Dashboard: model vs market signal, the three answers, what is missing |
| `nfl-lines/lines.html` | Week 11 fair spread / total / moneyline / break-even price vs the market number |
| `nfl-lines/leaderboard.html` | 8-gate validation, evidence-weighted rank, luck test, reward eligibility |
| `nfl-lines/backtest.html` | Walk-forward 1999–2026, per-season splits, calibration, no-model benchmarks |
| `nfl-lines/correlation.html` | Measured φ for market pairs and player pairs, with the pricing consequence |
| `nfl-lines/injuries.html` | Official 2026 Week 10 tracker (65 rows) + measured 2025 injury impact |
| `nfl-lines/questions.html` | 23 questions: known / unknown / missing / what it would change / how to settle it |
| `nfl-lines/suggestions.html` | 12 scored suggestions, each naming the decision you have to make |
| `nfl-lines/sources.html` | 13 registered datasets, 3 rejected sources, 32/32-club official validation |
| `nfl-lines/flagged.html` | 30 flagged irregularities and unverified values, with sources |
| `nfl-lines/method.html` | Definitions, the eight gates, and the one statistical correction |

## Data and provenance rules

* Market prices **are not official** — the NFL publishes none. Every price-derived figure is labelled
  `NOT OFFICIAL` and links the public archive it came from.
* Archive vs official: all **32/32** 2026 club records and points match `nfl.com/standings`; both recent Super Bowl
  results match their official game pages; 0 internal arithmetic errors across 7,548 games.
* Official depth charts return **HTTP 404**, so 1st/2nd/3rd/4th-string tiers are computed from production and
  labelled as computed everywhere. A player with no production record gets a blank tier.
* Blank is not zero: a blocked strategy shows `BLOCKED` and a blank profit, never `0`.

## Rebuild

```bash
python3 scripts/nfl_lines/stage1_official.py     # official captures (injury report, cross-checks)
python3 scripts/nfl_lines/stage2_validate.py     # archive vs nfl.com/standings and Super Bowls
python3 scripts/nfl_lines/stage3_engine.py       # strategies, gates, leaderboard, luck tests
python3 scripts/nfl_lines/stage4_correlation.py  # measured correlations
python3 scripts/nfl_lines/stage5_injuries.py     # 2026 tracker + 2025 impact
python3 scripts/nfl_lines/stage6_lines.py        # Week 11 fair lines
python3 scripts/nfl_lines/stage7_decision.py     # questions + suggestions registers
python3 scripts/nfl_lines/sources.py             # source registry
python3 scripts/nfl_lines/stage8_site.py         # the 11 pages
python3 scripts/nfl_lines/verify.py              # 12 structural checks, exits non-zero on failure
```

The seed is fixed (`20261113`), so a rebuild reproduces the numbers byte for byte unless an input file changes.
`.github/workflows/nfl-lines-lab.yml` runs exactly this sequence on every push and pull request, and can
optionally re-fetch the official pages from a runner, which can reach hosts this sandbox cannot.
