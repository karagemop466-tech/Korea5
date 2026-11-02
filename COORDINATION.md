# COORDINATION.md — Shared Task Board

**Repository:** `karagemop466-tech/Korea5`
**Session ID:** `arena/ef8b5b30-korea5` (fixed by Arena; abbreviated `ef8b5b30`)
**Session started:** 2026-11-02 (UTC)

## Branch-policy note (environment constraint)

The Arena environment fixes this session to the single branch `arena/ef8b5b30-korea5` and does not
permit creating, switching to, or pushing any other branch. Therefore the `session-<id>/<task>`
branch convention requested in the brief cannot be used here. This session works **only** on
`arena/ef8b5b30-korea5`, uses non-overlapping file scopes listed below, runs
`git pull --rebase` before each push, and records the handoff/log here. Because no other session
has claimed any work in this repository at the time of writing, this session also performs the
final integration step (data re-verification, link check, build check, PR, merge, Pages deploy
confirmation) on the same branch. Any other session that starts later must add its own claim below
and avoid the files already claimed here.

## Status values

`unclaimed` | `in progress` | `done` | `needs review`

## Task board

| # | Task | Status | Owner (session ID) | Files touched | Sources / verification / irregularities |
|---|------|--------|--------------------|---------------|------------------------------------------|
| T1 | Coordination board + repo inventory | in progress | ef8b5b30 | `COORDINATION.md`, `README.md` | Repo contained only `README.md` (`# Korea5`) at commit `2e82b8f`. Pages already enabled on `main:/` per `GET /repos/karagemop466-tech/Korea5/pages`. Branch constraint logged above. |
| T2 | Source registry & verification rules (official sources, station coverage, average game durations) | unclaimed | ef8b5b30 | `data/sources.md`, `data/methodology.md` | |
| T3 | Verified 2026 schedules (MLB, NFL/49ers, Stanford, Cal, Westwood One NFL radio) | unclaimed | ef8b5b30 | `data/verified-2026.json`, `data/verified-2026.md` | |
| T4 | 2027–2029 free-window analysis (verified vs estimated, clearly separated) | unclaimed | ef8b5b30 | `data/estimates.json`, `data/free-windows.md` | |
| T5 | Flagged-for-review register (all unverified/estimated/irregular items) | unclaimed | ef8b5b30 | `data/flags.json`, `site/flagged.html` | |
| T6 | Site: landing dashboard, day scoreboard/calendar, schedules, free windows, analysis, sources, flagged pages | unclaimed | ef8b5b30 | `site/index.html`, `site/*.html`, `site/assets/*`, `site/data/*` | |
| T7 | Line-by-line verification, link check, build check | unclaimed | ef8b5b30 | `tools/verify.mjs`, `VERIFICATION.md` | |
| T8 | PR from `arena/ef8b5b30-korea5` to `main`, merge, Pages deploy confirmation, log results | unclaimed | ef8b5b30 | `COORDINATION.md` (log only) | |

## Claim log / handoff log

- 2026-11-02 — `ef8b5b30` claimed T1–T8 for this session with the file scopes above. No other
  claims existed in the repo. Commit + push of this claim follows immediately.
- Shared outputs (`site/index.html` navigation and the combined table data) are owned by this
  session acting as final integrator; no other session should edit them without adding a claim
  and a request in this log.
- 2026-11-02 — **Parallel session discovered**: `arena/1a5a5516-korea5` exists with commits. Its
  `COORDINATION.md` claims research, MLB StatsAPI fetcher (`scripts/fetch_mlb.py`) and
  `data/mlb-{2026,2027,2028,2029}.json`, `data/mlb-summary.json`, plus a CI workflow
  `.github/workflows/data.yml`. Its MLB data are verified (2,430 regular-season games in each of
  2026 and 2027; 2028/2029 empty and marked unverified because MLB has not released them).
  **Coordination decision:** this session will NOT re-fetch or edit those files. It will consume
  that MLB data at integration (copy/merge with attribution), and will keep its own work in
  non-overlapping scopes (`site/`, `research-ef8b5b30/`, `tools/`, `official/nfl/`,
  `official/ncaaf/`, `official/westwoodone/`, `VERIFICATION-ef8b5b30.md`). This session covers
  NFL, Stanford/Cal NCAAF, Westwood One national radio, SF 94122 AM/FM station verification,
  durations, free-time engine, site, verification, PR/merge. Request logged: integration should
  merge `arena/1a5a5516-korea5` (or copy its `data/mlb-*.json`) before publishing so the MLB
  half of the scoreboard is populated. No conflicting edits were made to that session's files.
- 2026-11-02 — The three previously-worked-on sites
  (`buffedlizard55-lab.github.io/VacationSchedule/site/`, `/ScheduleFreeTime/`, `/RADIOSF/`)
  all returned GitHub Pages 404 during review. Logged as an irregularity for the Flagged for
  Review page; this project therefore builds a new self-contained site rather than relying on
  those pages.
- If another session crashes or a claim is >60 min old with no commits, any session may take over
  the task and note the handoff here.

## Completion log

_(filled in as tasks complete: sources used, verification performed, irregularities)_
