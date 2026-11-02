# COORDINATION.md — Shared Task Board

Repository: `karagemop466-tech/Korea5`
Purpose: Free-time / vacation planner covering **MLB (all 30 clubs), NFL (all games), 49ers, Stanford NCAAF, Cal NCAAF, Westwood One national NFL radio**, for 2026–2029, with radio availability for San Francisco 94122.

> This board is the single source of truth for task ownership. Read it before starting work.
> Shared outputs (`index.html`, navigation, `data/` integration) are written only by the integration session.

## Session registry

| Session ID | Branch | Role | Status |
|---|---|---|---|
| `arena-1a5a5516` | `arena/1a5a5516-korea5` | Sole active session — research, data, build, verification, integration | active |

**Note on branch naming:** The standing Arena session rule fixes this session's branch to `arena/1a5a5516-korea5`
(no `session-<id>/<task>` branches may be created or pushed). All work therefore happens on that branch, and the
integration step is performed in-session on it before the pull request to `main`. This is a deliberate, logged deviation
from the generic `session-<id>/<task>` convention, not an unclaimed-task conflict.

**Parallel-session protocol status:** At the time of writing, this is the only session with commits on this repository.
No other session has claimed a task. Claims below are therefore non-overlapping by construction.

## Task board

| # | Task | Owner | Status | Files owned |
|---|---|---|---|---|
| T1 | Research: official season structure, start/end dates, radio affiliates, average game durations | arena-1a5a5516 | done | `research/` |
| T2 | Data: official MLB schedules (all 30 clubs) via MLB StatsAPI, 2026 + 2027 | arena-1a5a5516 | in progress | `scripts/fetch_mlb.py`, `data/mlb-*.json` |
| T3 | Data: MLB 2028–2029 estimated schedules (clearly labelled) | arena-1a5a5516 | unclaimed | `scripts/build_estimates.py`, `data/mlb-*.json` |
| T4 | Data: NFL schedules (2026 verified where sourced; 2027–2029 estimated) + 49ers | arena-1a5a5516 | unclaimed | `scripts/fetch_nfl.py`, `data/nfl-*.json` |
| T5 | Data: Stanford + Cal NCAAF schedules (2026 verified; 2027–2029 estimated) | arena-1a5a5516 | unclaimed | `scripts/fetch_ncaaf.py`, `data/ncaaf-*.json` |
| T6 | Data: Westwood One Sports national NFL (+ NCAA) radio broadcasts | arena-1a5a5516 | unclaimed | `scripts/fetch_w1.py`, `data/westwoodone-*.json` |
| T7 | Build: free/busy engine (PT), average game durations, vacation-window ranking | arena-1a5a5516 | unclaimed | `scripts/free_time.py`, `data/derived/` |
| T8 | Site: landing dashboard + calendar/scoreboard + category pages + sources + flagged | arena-1a5a5516 | unclaimed | `*.html`, `assets/` |
| T9 | Verification: line-by-line source audit, link check, JSON schema check | arena-1a5a5516 | unclaimed | `scripts/verify.py`, `verification/` |
| T10 | Integration: merge, re-verify combined data, publish to `main`, GitHub Pages deploy, PR | arena-1a5a5516 | unclaimed | `main` merge commit |

## Change log

- **2026-11-02** — Board created. `arena-1a5a5516` claims T1–T10. Working branch `arena/1a5a5516-korea5`.
- **2026-11-02** — Confirmed: GitHub Actions executes in this repo; runners have outbound internet and can reach
  `statsapi.mlb.com` (official MLB data service). Data acquisition therefore uses CI, not manual transcription.
  GitHub Pages is enabled on `main` (legacy build, `/`), published at https://karagemop466-tech.github.io/Korea5/.

## Pending requests to other sessions

None.
