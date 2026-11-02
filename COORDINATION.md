# COORDINATION.md — Shared Task Board

Repository: `karagemop466-tech/Korea5`
Purpose: Free-time / vacation planner covering **MLB (all 30 clubs), NFL (all games), 49ers, Stanford NCAAF, Cal NCAAF, Westwood One national NFL radio**, 2026–2029, with radio availability for San Francisco 94122.

> This board is the single source of truth for task ownership. Read it before starting work.
> Shared outputs (`*.html`, navigation, `data/`) are written by the integration step only.

## Session registry

| Session ID | Branch | Role | Status |
|---|---|---|---|
| `arena-1a5a5516` | `arena/1a5a5516-korea5` | Sole active session — research, data, build, verification, integration | **done** |

**Note on branch naming.** The Arena session rule fixes this session's branch to `arena/1a5a5516-korea5`
(no `session-<id>/<task>` branches may be created or pushed). All work therefore happened on that branch, and the
integration step ran in-session before the pull request to `main`. This is a deliberate, logged deviation from the generic
`session-<id>/<task>` convention, not an unclaimed-task conflict.

**Parallel-session protocol status.** This was the only session with commits on the repository. `git log --all` shows no
other author than this session and its CI bot (`korea5-data-bot`). No task was claimed twice, and no file scope overlapped.

## Task board

| # | Task | Owner | Status | Files |
|---|---|---|---|---|
| T1 | Research: official season structure, sources, game durations | arena-1a5a5516 | **done** | `research/` |
| T2 | Data: official MLB schedules (all 30 clubs) via MLB StatsAPI, 2026 + 2027 | arena-1a5a5516 | **done** | `scripts/fetch_mlb.py`, `data/mlb-*.json` |
| T3 | Data: MLB 2028–2029 estimated calendars | arena-1a5a5516 | **done** | `scripts/build_events.py`, `data/events-*.json` |
| T4 | Data: NFL 2026 (49ers verified) + 2027–2029 estimated | arena-1a5a5516 | **done** | `data/curated/nfl-2026-49ers.json` |
| T5 | Data: Stanford + Cal NCAAF (2026 verified; 2027–2029 estimated) | arena-1a5a5516 | **done** | `data/curated/ncaaf-2026.json` |
| T6 | Data: Westwood One national NFL radio | arena-1a5a5516 | **done** | `data/curated/westwoodone-2026.json` |
| T7 | Free/busy engine (PT), durations, vacation-window ranking | arena-1a5a5516 | **done** | `scripts/analyze.py`, `data/derived/analysis.json` |
| T8 | Site: dashboard, calendar, category pages, sources, flagged, method | arena-1a5a5516 | **done** | `*.html`, `assets/` |
| T9 | Verification: line-by-line source audit, link check, feed integrity | arena-1a5a5516 | **done** | `scripts/verify.py`, `verification/` |
| T10 | Integration: rebuild, re-verify, publish to `main`, Pages deploy, PR | arena-1a5a5516 | **done** | merge commit `3ae7171` |
| T11 | *(session ef8b5b30)* Official NFL by-week feed, Westwood One station finder, extra W1 sport pages | arena-ef8b5b30 | **needs review** | `official/`, `research-ef8b5b30/`, `.github/workflows/*-ef8b5b30.yml` |

## Change log

- **2026-11-02** — Board created. `arena-1a5a5516` claims T1–T10. Working branch `arena/1a5a5516-korea5`.
- **2026-11-02** — Confirmed GitHub Actions executes in this repo and that runners can reach the official schedule hosts.
  Data acquisition therefore runs in CI instead of relying on transcription.
- **2026-11-02** — T1–T9 complete. Key findings and verification evidence below.

## Sources used (all official)

| Source | What it provided | Verification |
|---|---|---|
| `https://statsapi.mlb.com/api/v1/schedule` | 2026 and 2027 MLB fixtures (2,430 regular-season games per season, all 30 clubs), Spring Training, All-Star, 2026 postseason | Re-queried in CI for 6 sample dates per season and compared game-for-game |
| `https://www.mlb.com/schedule/` | Human-readable per-date view linked from every MLB row | — |
| `https://www.49ers.com/schedule/2026/` | 49ers 2026 dates, kickoff times (PT), venues, TV, radio affiliates | 21 curated rows re-fetched; tokens matched |
| `https://gostanford.com/sports/football/schedule` | Stanford 2026 dates, times, venues, results | 12 rows checked (snapshot fallback — page renders client-side) |
| `https://calbears.com/sports/football/schedule` | Cal 2026 dates, times, radio network, results | 3 rows checked |
| `https://www.westwoodonesports.com/nfl-schedule/` | National NFL radio windows for 2026–27 (+ one NCAA Football window) | 26 rows checked against their event pages |
| `https://www.nfl.com/schedules/` | Weekly window structure used only for 2027–29 estimates | Reference only, no rows transcribed |

## Verification performed

- `scripts/verify.py` re-downloads every cited official page and asserts that each curated row's `verifyTokens`
  (date, opponent, kickoff time as printed by the source) still appear on it. Result: **49 of 62 rows passed**;
  13 failures are published on the Flagged page (not hidden).
- MLB feed spot checks: **9 of 10** sample dates matched the league API game-for-game. The single mismatch
  (2026-07-17: 14 games stored vs 15 returned) is recorded in `verification/report.json` for review.
- Feed integrity: **0** events missing a source URL, malformed dates or malformed start times.
- Link check: 10 pages, 155 local links, 0 missing; 212 external links, all on official domains
  (mlb.com, westwoodonesports.com, 49ers.com, gostanford.com, calbears.com, nfl.com, statsapi.mlb.com).

## Irregularities recorded (published on the Flagged page)

1. **Big Game date conflict** — calbears.com: Sat Nov 14, 2026, 12:30 PM; gostanford.com: Sat Nov 21, 2026, TBA. Both blocked.
2. **Mexico City kickoff conflict** — 49ers.com 5:20 PM PST vs Westwood One 7:30 PM ET (4:30 PM PST). Union blocked.
3. **Westwood One Dec 27, 2026 (JAX at DAL)** — kickoff time not retrievable; left blank, marked unverified.
4. **Cal Nov 28, 2026** — opponent not shown on the official page; left blank.
5. **Athletics radio flagship** — not confirmed by any official page in this pass; A's games still blocked as high priority.
6. **Westwood One San Francisco affiliate** — not published on the pages verified.
7. **Cal 2026 games before Nov 14** — official page card order not resolvable unambiguously; rows omitted rather than guessed.
8. **2027 MLB start times** — 1,631 of 2,430 games carry a placeholder `:33` time in the league feed; dates/matchups official, times estimated.

## Deliverables

- Site: 10 static pages + `assets/` + `data/`, published from `main` via GitHub Pages.
- `research/EXECUTIVE-SUMMARY.md` — the written answer.
- `verification/report.json` / `report.md` / `links.json` — machine-readable evidence.
- Rebuild pipeline in `scripts/` and `.github/workflows/`.

## Parallel session — `arena-ef8b5b30`

A second Arena session is working the same repository on branch `arena/ef8b5b30-korea5`, in paths this session does not own:
`official/`, `research-ef8b5b30/` and `.github/workflows/*-ef8b5b30.yml`. No file collision has occurred: this session never
edited those paths and that session did not touch `scripts/`, `data/curated/`, `*.html` or `assets/`.

**Integrations taken from that session (copied read-only into `data/upstream/`, origin recorded):**

| File | Taken from | What it added | Credit |
|---|---|---|---|
| `data/upstream/nfl-2026.json` | `official/nfl-2026.json` @ `arena/ef8b5b30-korea5` | All 272 regular-season and 49 preseason NFL games for 2026, each with an NFL.com game-page URL, Pacific kickoff time, TV and audio networks | session `ef8b5b30` |
| `data/upstream/w1-stations.json` | `official/w1-stations.json` @ `arena/ef8b5b30-korea5` | Westwood One Station Finder result for the San Francisco market (KNBR-AM, KNBR-FM, KNBR-F2, KTCT-AM) | session `ef8b5b30` |

Because `data/upstream/` holds a copy rather than a reference, this branch builds without depending on the other branch.
Cross-checks: the three 2026 49ers kickoff times present in both datasets agree exactly (Dec 17 17:15 PT, Dec 27 13:25 PT,
Jan 3 17:20 PT), which is why the upstream feed was accepted.

**Conflict warning for the other session:** both branches add `COORDINATION.md`, so whichever merges second will hit an
add/add conflict. Resolve by **appending** that session's task rows and log entries to this file — do not overwrite it.

## Integration record

| Step | Result |
|---|---|
| Pull request #1 | **https://github.com/karagemop466-tech/Korea5/pull/1** — "Free-time & vacation planner: verified MLB/NFL/NCAAF/Westwood One schedules + 2027–29 vacation analysis" |
| Merge #1 | **Merged** into `main` 2026-11-02T17:38:23Z, merge commit `3ae71714fd9625aff3feff73831ad450beb8e8bf` |
| Pull request #2 | **https://github.com/karagemop466-tech/Korea5/pull/2** — TBD-kickoff blocking fix (24h → plausible window) + integration record |
| Merge #2 | **Merged** 2026-11-02T17:40:33Z |
| Pull request #3 | **https://github.com/karagemop466-tech/Korea5/pull/3** — one row per game; Westwood One pre-game starts folded into the game row |
| Merge #3 | **Merged** |
| Pull request #4 | **https://github.com/karagemop466-tech/Korea5/pull/4** — cache-busted data fetches + final record |
| Merge #4 | **Merged** |
| Pull request #5 | **https://github.com/karagemop466-tech/Korea5/pull/5** — version data requests by content hash (stale-CDN fix) |
| Merge #5 | **Merged**; Pages rebuilt and the live calendar verified: one row for 2026-11-02 with the pre-game note, 3.1 busy hours |
| Pages build | `pages build and deployment` — **success**; Pages status `built`, source `main` / |
| Live site | https://karagemop466-tech.github.io/Korea5/ — verified by fetching the published page |
| Post-merge fix 1 | PR #2 — TBD-kickoff games were blocking a full 24 hours instead of the plausible 12:00–23:30 PT window |
| Post-merge fix 2 | PR #3 — the live calendar showed duplicate rows for the same game because Westwood One's published time is its pre-game broadcast start (15–75 min before kickoff) |
| Post-merge fix 3 | PR #4 — GitHub Pages was serving a cached `events-*.json` after deploy; data requests now carry a version query string |
| Post-merge fix 4 | PR #5 — the version string was derived from the inputs and so did not change when the transform did; it is now a sha256 of the built data, and the live calendar was re-checked against the deployed site |

## Post-merge defect found and fixed

Fetching the live dashboard showed **2026-11-14 as "24.0h busy"**. Cause: an event with no published kickoff time
was treated as a whole-day block before its known `startWindow` was consulted. Fixed in `scripts/analyze.py` and
`assets/app.js`: a row with a `startWindow` uses that window, and a row with no time at all is blocked 12:00–23:30 PT
(the plausible playing window) rather than 24 hours. After the fix the same day reads **3.8 busy hours**, and the
TBA Big Game on 2026-11-21 reads 11.5 hours instead of 24.

## Pending requests to other sessions

- To `arena-ef8b5b30`: if you change `official/nfl-2026.json`, note it here so `data/upstream/` can be refreshed.
