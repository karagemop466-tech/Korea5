# Session review — `arena/0fb8732b-korea5` (2026-11-03)

Branch fixed by Arena: `arena/0fb8732b-korea5` (tip of `main` at start: `f9b5a7f`, PR #15 merged).
No other branch was created or pushed. Scope: full-repo line-by-line review, local verification,
one defect fix, PR + merge + Pages deploy confirmation.

## What was reviewed

All 11 root pages + 15 `extra/` pages, `assets/`, `extra/assets/`, all `data/*.json`,
`data/curated/`, `data/upstream/`, `official/`, `curated/`, `scripts/`, `tools/`,
`tests/`, `verification/`, `research/`, `.github/workflows/`.

## Checks run locally (2026-11-03, sandbox)

| Check | Result |
|---|---|
| `python3 scripts/check_links.py` | 11 pages, 179 local links, 519 external links, **0 missing** |
| `python3 tools/verify_extra.py` | **31/31 checks passed**, 0 broken local links, 0 table rows missing a source link |
| `python3 scripts/audit_certainty.py` | passed — no certified future 7/14/21-day window; every page discloses incomplete coverage |
| `python3 -m unittest discover -s tests` | 5/5 passed |
| `node --check assets/app.js extra/assets/extra.js` | both OK |
| `python3 -m compileall scripts tools` | OK |
| JSON validity of all committed data files | all valid |
| Source-link audit (all feeds) | 8,554 source-bearing rows, **0 blank source URLs**, 1 third-party research link (`profootballnetwork.com` in `curated/durations.json`) which is already labelled "Research (not official)" and flagged — not used as verified data |
| High-priority flag audit (Giants/A's/49ers/Stanford/Cal rows must be `priority=high`) | **0 misses** across 7,203 event rows (2026–2030) |
| Event counts per year | 2026: 3,227 · 2027: 3,102 · 2028: 427 (estimate layer) · 2029: 432 (estimate layer) · 2030: 15 |
| MLB official feed counts (`data/mlb-summary.json`) | 2026: 2,430 regular + spring/all-star/postseason types; 2027: 2,430 regular; 2028/2029: 0 released → labelled ESTIMATION |
| 49ers curated rows vs committed official-page snapshot (`research/text/49ers-2026.txt`) | **21/21 verifyTokens matched** |
| Westwood One curated rows vs `research/text/westwoodone-nfl.txt` | snapshot is only the JS shell (508 B) — token check **not possible locally**; CI fetch report (`official/fetch-report.json`, 2026-11-02) records 580 W1 events fetched with **0 failures**; rows remain linked to official event pages |
| Combined calendar (`extra/data/calendar.json`) | 1,215 days, 2026-11-02 → 2030-02-28, includes today 2026-11-03 |
| Vacation ranking (`extra/data/vacation.json`) | 1/2/3-week windows ranked for 2027, 2028, 2029; every window `fullyFree=false`, `status=estimated` |

## Defect found and fixed this session

**Stale "Today" on the extra day scoreboard.** `extra/assets/extra.js` hardcoded
`today='2026-11-02'` ("compiled date"), so the Prev/Next/Today scoreboard's Today button and
default day were one day behind on 2026-11-03. The root calendar (`assets/app.js`) already
computed today dynamically in `America/Los_Angeles`. Fixed both the generated asset and its
generator (`tools/build_extra.py`) to compute the current Pacific date via
`Intl.DateTimeFormat('en-CA', {timeZone:'America/Los_Angeles', …})`. Verified with `node -e`
(today PT = 2026-11-03) and `node --check`; regenerated asset is byte-identical to the
generator template line.

## What could NOT be verified from this sandbox (published, nonblocking)

Outbound access here is restricted to github.com / npm / pypi hosts. Official sports sites
(mlb.com, statsapi.mlb.com, nfl.com, 49ers.com, gostanford.com, calbears.com,
westwoodonesports.com) are **not reachable**, so no live re-verification of schedule facts was
possible in-session. This is already disclosed on `certainty.html` and the Flagged pages;
historical reports keep their original timestamps; CI (`.github/workflows/`) performs the live
fetches. Nothing was relabelled as freshly verified.

## Irregularities

No new irregularities found this session. The previously flagged items (2028/2029 unreleased
MLB, 2027 TBD first pitches, W1 vs 49ers kickoff conflicts, station-carriage gaps, etc.)
remain published on `flagged.html` / `extra/flagged.html` with official source links.
