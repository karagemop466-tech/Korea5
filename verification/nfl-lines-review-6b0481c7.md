# Repository review — NFL lines lab session `arena-6b0481c7-korea5`

Reviewed 2026-11-13 against base commit `e826658` (PR #35). Every claim below is either (a) a command whose
output is reproduced here, (b) a value read from a file in the repository with its path shown, or (c) a value
read from an official page whose exact URL is given. Nothing is inferred.

---

## 1. What this repository actually contains

The repository is **not** an NFL betting system at base. It is a **free-time / vacation planner** built around
MLB, NFL, Stanford, Cal and Westwood One radio schedules in Pacific time, plus one static research page
(`nfl-strategy.html`, `research/NFL-STRATEGY.md`) that correctly stated the repository held *no* odds, props or
injury datasets. That statement was checked and confirmed (§2.1), so the prior session's honesty claim holds.

| Area | Files at base | Verified by |
|---|---|---|
| Published site (12 pages) | `*.html` root, `extra/*.html` | `scripts/check_links.py` |
| Schedule data | `data/`, `data/curated/`, `data/upstream/`, `official/`, `curated/` | JSON parse + registry check |
| Pipeline | `scripts/*.py`, `tools/*.py`, 15 GitHub workflows | reading the files |
| Verification evidence | `verification/*`, `extra/data/verification.json` | re-ran the scripts |
| Prior NFL research page | `nfl-strategy.html`, `research/NFL-STRATEGY.md` | read line by line |

### 1.1 Irregularities found in the inherited repository

| # | Finding | Evidence | Severity | Disposition |
|---|---|---|---|---|
| R1 | `README.md` says the second pass added `tools/*-ef8b5b30.yml` "CI fetchers" in `tools/`; the workflows are actually in `.github/workflows/`. | `ls tools/` → `build_extra.py verify_extra.py extract_rules.py probe.py fetch_official.py`; workflows in `.github/workflows/` | low | documentation only, flagged |
| R2 | `COORDINATION.md` records page counts (10, then 11, then 12) that drift from the tree. At this commit there are **12 root pages** plus **16 pages under `extra/`**, and this session adds **12 more under `nfl-lines/`** (11 pages + 1 stylesheet). | `ls *.html` → `calendar certainty flagged index method mlb ncaaf nfl-strategy nfl radio sources vacation`; `ls nfl-lines/*.html` → 11 | low | flagged for the next coordination pass; the lab keeps its own count on its Method page |
| R3 | 7 of the 8 workflow files in `.github/workflows/` still trigger only on old session branches (`arena/1a5a5516-korea5`, `arena/ef8b5b30-korea5`). They therefore never run on `main`. Only `certainty.yml` runs on `main` and on every pull request. | `.github/workflows/`: `certainty.yml` (`branches: [main, arena/f9e705a1-korea5]`), and `data.yml`, `data-ef8b5b30.yml`, `extract.yml`, `probe.yml`, `probe-ef8b5b30.yml`, `rules-ef8b5b30.yml`, `verify.yml` which do not list `main`. Note: workflows created by parallel sessions (`nfl-data.yml`, `nfl-probe.yml`, `lines-probe.yml`, `nfl-lab-injuries.yml`) exist only on their own branches, not here. | medium | NOT changed here (outside this session's scope); flagged so an integration session can decide |
| R4 | `certainty.html` embeds a hard-coded "Reviewed 2026-11-03" narrative inside `scripts/audit_certainty.py`, so the page's prose ages independently of the data. | `scripts/audit_certainty.py` line with `Reviewed 2026-11-03` | low | flagged |
| R5 | The prior NFL research page states no edge is claimed and no historical odds exist — **correct at base**. After this session, an odds archive does exist (from a public mirror), so the page is now incomplete rather than wrong. | `research/NFL-STRATEGY.md` vs `nfl-lines/data/games.csv` | low | this session adds a new section rather than rewriting the old page |

No fabricated schedule value, broken link or malformed JSON was found in the inherited data (§2.2).

---

## 2. Verification actually run

### 2.1 Confirm the base repository had no market or prop data

```
$ ls data data/curated data/upstream official
data/events-2026.json ... data/derived/analysis.json     # schedules only
official/nfl-2026.json ...                                # schedules only
$ grep -rl "spread_line\|moneyline\|prop" --include=*.json data official curated | wc -l
0
```

The prior session's statement is confirmed: at base there are **no betting prices, no prop prices and no
injury history**.

### 2.2 Inherited integrity suite (re-run on this branch)

| Command | Result |
|---|---|
| `python3 scripts/check_links.py` | `pages=12 localLinks=202 external=528 missing=0` |
| `python3 tools/verify_extra.py` | 31/31 checks, `rowsMissingSource: 0`, `failedNames: []` |
| `python3 scripts/audit_certainty.py` | passed |
| `python3 -m unittest discover -s tests` | 5 tests, OK |
| `node --check assets/app.js`, `node tests/test_calendar.js` | passed |
| `python3 -m compileall -q scripts tools` | no syntax errors |

### 2.3 Official sources reached from this environment

Reachable: `github.com`, `api.github.com`, `codeload.github.com`, `registry.npmjs.org`, `pypi.org`,
`files.pythonhosted.org`. Unreachable: every sports host via `curl` (and
`release-assets.githubusercontent.com`, which is where GitHub release binaries live).
The **page-fetch tool** can read public sports pages, so official cross-checks were done by fetch + transcription
with the exact URL recorded per value in `nfl-lines/data/official/official-crosschecks.json`.

| Official page | URL | What was taken |
|---|---|---|
| Injury report, 2026 week 10 | https://www.nfl.com/injuries/league/2026/reg10 | 65 rows across 3 games, verbatim |
| Division standings, 2026 | https://www.nfl.com/standings/ | 32 clubs' W-L-T, PF, PA |
| Rushing leaders, 2026 | https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all/rushingyards/desc | 5 players' season totals |
| Game center, NE @ DET week 10 | https://www.nfl.com/games/patriots-at-lions-2026-reg-10 | venue (Munich), records, injury cards, jersey numbers |
| Team roster, DET | https://www.nfl.com/teams/detroit-lions/roster | position + ACT status only |
| Depth chart, DET | https://www.nfl.com/teams/detroit-lions/depth-chart | **HTTP 404** — recorded as a finding |
| Rules | https://operations.nfl.com/the-rules/ | definitions only |

### 2.4 Archive validation (new in this session)

`nfl-lines/data/validation/validation.json`:

| Check | Result |
|---|---|
| 2026 standings, club by club (W-L-T, PF, PA) | **32/32 match** |
| Super Bowl LIX (`https://www.nfl.com/games/chiefs-at-eagles-2024-post-22`) | PHI 40 – KC 22, 2025-02-09 — match |
| Super Bowl LX (`https://www.nfl.com/games/seahawks-at-patriots-2025-post-22`) | SEA 29 – NE 13, 2026-02-08 — match |
| Internal arithmetic and duplicate ids over 7,548 games | **0 errors** |
| Club count per season | 32 for 2002+, **31 for 1999–2001 because the Houston Texans did not exist yet** — expected, documented |

Two corrections were needed to reach 32/32 and are recorded rather than hidden:

1. The official standings page prints **`AZ`** where the archive uses **`ARI`**. An explicit alias map
   (`CLUB_ALIAS = {"AZ": "ARI"}`) is applied so a rename can never silently mask a real disagreement.
2. The 1999–2001 seasons legitimately contain 31 clubs. The check now expects
   `{1999: 31, 2000: 31, 2001: 31}` instead of 32.

---

## 3. Data acquisition: what was and was not possible

| Dataset | Route used | Why | Label |
|---|---|---|---|
| Closing lines 2006–2018 | `https://codeload.github.com/nflverse/nfldata/tar.gz/refs/heads/master` | `raw.githubusercontent.com` unreachable; release assets unreachable | MIRROR |
| Games + results + lines 1999–2026 | same tarball | same | MIRROR |
| Player-week 2025 | `api.github.com` contents API on `mgiancola9/nfl-predictions` | release assets unreachable | MIRROR |
| Injury reports 2025 | same mirror | same | MIRROR (5 columns only) |
| Injury report 2026 week 10 | official page, transcribed | official page is fetchable | OFFICIAL |
| Depth charts | official URL returns 404 | — | **NOT OBTAINED** |
| Player props | no source reachable or official | — | **DOES NOT EXIST** |

Every one of these is in `nfl-lines/data/sources.json` with its access URL, upstream, licence statement and
"cannot establish" list, and the three rejected routes are in `rejectedSources` with their evidence.

---

## 4. Line-by-line review of the new lab

The lab is new code, so "review" here means: was every number it publishes derived from a file, and does the
file trace to a source?

| Published value | Derived from | Traces to |
|---|---|---|
| 7,413 graded games, 7,548 rows | `nfl-lines/data/games.csv` | MIRROR (`nfldata`) |
| Model signal 0.101, market signal 0.143 | same, de-vigged moneylines | MIRROR — labelled NOT OFFICIAL |
| Week 11 fair spread/total/price | same archive + fitted constants | MODEL |
| 65 official injury rows | `official/injury-report-2026-week10.json` | OFFICIAL page URL on every row |
| Computed tiers | 2025 player-week production, ranked by club and position group | MIRROR, labelled as computed |
| Injury impact −0.97 / +0.80 points | 414 club-weeks, `impact-2025.json` | MIRROR + official status values |
| Correlation φ values | joint outcomes in the two tables above | MIRROR, one season for player pairs |
| 23 questions, 12 suggestions | `nfl-lines/data/decision/*.json` | each row carries its own source or states none exists |
| 30 flagged items | compiled from the checks above | each row carries a source or states none exists |

### 4.1 Statistical review of the lab's own methods

| Method | Reviewed | Outcome |
|---|---|---|
| Walk-forward discipline | Models updated only after grading | Pass — inputs are strictly prior games |
| De-vig | Multiplicative normalisation of both sides | Pass — the market is not penalised for its margin |
| Probability → margin mapping | OLS fitted on all graded games for the Week 11 card; refitted point-in-time inside the backtest | Pass — constants published (`0.34 + 31.71 × Δp`) |
| Spread sign convention | Checked against outcomes before use | Pass — home covers 47.6% under the correct convention vs 38.9% under the inverted one |
| ROI interval | Week-block bootstrap, 2,000 draws | Pass — blocks respect within-week correlation |
| Luck test | **Originally pooled break-even win rate → rejected** | **Corrected** to a per-bet de-vigged null with 10,000 seeded simulations; the three-leg parlay moved from p = 0.0005 to p = 0.218 |
| Multiple testing | Bonferroni over the family of 8 | Pass — reported next to the raw p |
| Blocked vs zero | Blocked strategies carry no bets and blank profit | Pass — enforced by `verify.py` check V07 |
| Gate 7 | Hard-coded to fail until a prospective trial exists | Pass — no strategy can be reward-eligible |

The luck-test correction is the single most important review outcome of this session: the first version would
have published a false positive.

---

## 5. Flagged for review (also published on `nfl-lines/flagged.html`)

**High**: prices are non-official (F01); `nfldata` has no licence file (F02); release CDN blocked, mirror used
(F03); depth charts 404 (F04); no prop prices (F08); parlay prices are a product bound (F09); the model loses to
the market (F11); no price timestamps (F13); zero strategies qualified (F14); the withdrawn significance
finding (F15); every Week 11 row is WATCH not PLAY (F19); the rejected statistical test (F30).

**Medium**: 56 blank game-status cells on the official page (F05); 3-game injury coverage (F06); null injury
effects (F07); proxy prop lines (F10); no weather/rest/injury inputs (F12); no prices past Week 18 (F16); 2026
player totals not archive-checked (F21); 5-column injury mirror (F22); one-season correlation samples (F24);
fair totals ignore weather (F27); Week 11 prices may move (F28); concurrent sessions (F29).

**Low**: 163 of 272 scheduled 2026 games carry prices (F16 variant); club label alias (F17); 31 clubs in
1999–2001 (F18); fixed prior weight (F23); fixed Elo constants (F25); neutral-site detection (F26); repository
documentation drift (R1, R4); stale workflow branches (R3).

---

## 6. Reproduce this review

```bash
python3 scripts/check_links.py          # inherited site links
python3 tools/verify_extra.py           # inherited extra pages
python3 scripts/audit_certainty.py      # inherited certainty policy
python3 -m unittest discover -s tests   # inherited unit tests
python3 scripts/nfl_lines/stage1_official.py
python3 scripts/nfl_lines/stage2_validate.py     # prints 32/32, 2/2, 0
python3 scripts/nfl_lines/stage3_engine.py
python3 scripts/nfl_lines/stage4_correlation.py
python3 scripts/nfl_lines/stage5_injuries.py
python3 scripts/nfl_lines/stage6_lines.py
python3 scripts/nfl_lines/stage7_decision.py
python3 scripts/nfl_lines/sources.py
python3 scripts/nfl_lines/stage8_site.py
python3 scripts/nfl_lines/verify.py              # 12/12 checks
```
