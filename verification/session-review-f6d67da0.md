# Session review — `arena/f6d67da0-korea5` (2026-11-13)

Branch fixed by Arena: `arena/f6d67da0-korea5` (base of `main`: `13854fe`, PR #31 merged).
No other branch was created or pushed. Scope: NFL intelligence section — verified data
collection, line origination + strategy/validation framework, injury & deficiency tracking,
suggestions + questions registers, executive summary, seven new site pages.

## What was reviewed

`README.md`, `scripts/build_site.py`, `data/upstream/nfl-2026.json`, `curated/flags.json`,
`research/EXECUTIVE-SUMMARY.md`, `verification/` prior records, `.github/workflows/`,
`assets/`, `extra/` structure; all nfl.com pages listed under Sources below.

## Data collected and verified

| Dataset | Rows | Verification |
|---|---|---|
| `data/nfl-intel/results-2026.json` | 137 finals, weeks 1–10 | Reconciled team-by-team against official standings: **32/32 exact** on W-L-T and PF/PA (totals 6,291 = 6,291); every row carries its nfl.com scores source URL |
| `data/nfl-intel/standings-2026.json` | 32 teams | Transcribed from official league standings page |
| `data/nfl-intel/injuries-week10.json` | 296 rows + 1 "No Injuries Reported" game + 9 status-news items | Verbatim from the official Week-10 injury report (retrieved 2026-11-13); blank Game Status semantics documented |
| `data/nfl-intel/model.json` | 32 ratings, 26 originated lines, 74 backtest predictions, signal correlations | Computed by `scripts/nfl_intel.py` from the verified rows above; formulas published on the Lines page |

## Model & gates

Walk-forward weeks 5–9 (fit strictly before each target week), two variants (S1 full-season,
S2 recency λ=0.9). S1: MAE 10.56 vs 11.32 baseline, Brier 0.216 vs 0.255, hit 66.2%, corr 0.314.
S2: MAE 10.54, Brier 0.215, hit 63.4%, corr 0.318. **G1–G4 PASS both. G5/G6 not evaluable**
(no verified odds source — flagged, Q-ODDS). G7/G8 deferred. Signal correlations vs margin
(n=74): restDiff 0.438, ratingDiff 0.325, streakDiff 0.281, ppgDiff 0.194; home constant
(undefined; HFA −0.02 pts). Parlay/prop pair correlations blank + flagged.

## Irregularities found (flags F33–F41 appended to `curated/flags.json`)

| Flag | Summary | Status |
|---|---|---|
| F33 | nfl.com Week-1 listing labels NE@SEA "SNF, September 9th" — Sept 9, 2026 is a Wednesday | needs-review |
| F34 | Scores pages can serve "Hidden Score" placeholders (spoiler state); canonical re-fetch used | resolved |
| F35 | **No verified market odds source** — market columns blank; G5/G6, CLV, parlay pricing blocked | needs-review |
| F36 | Week-10 Game Status blank for Sun/Mon games as of 2026-11-13 ("not yet published") | needs-review |
| F37 | 2026 HFA computes to −0.02 pts/game (essentially zero) | needs-review |
| F38 | restDiff signal (0.438) partially schedule-confounded; causal claim unverified | needs-review |
| F39 | BAL QB "3rd string" verified by news chain, "4th string" unverified | needs-review |
| F40 | TNF WAS@NYG result postdates original snapshot ("137 vs 136" reconciliation clarified) | resolved |
| F41 | Parlay-leg / prop-pair correlations blank (no graded market data) | needs-review |

## Checks run (fill on final run — see pipeline step below)

| Check | Result |
|---|---|
| `python3 scripts/build_events.py` → `analyze.py` → `build_site.py` → `nfl_intel.py` → `build_nfl_intel.py` → `build_extra.py` | all ran clean; 18 pages built |
| `python3 scripts/check_links.py` | 18 pages, 426 local links, 751 external links, **0 missing** |
| `python3 tools/verify_extra.py` | all checks passed, `rowsMissingSource: 0` |
| `python3 -m unittest discover -s tests` | 5/5 passed |
| `node --check assets/app.js extra/assets/extra.js` · `python3 -m compileall scripts tools` | OK |
| `python3 scripts/audit_certainty.py` | passed — no certified future windows; all published pages disclose incomplete coverage |
| Reconciliation: results vs standings | 32/32 exact on W-L-T/PF/PA (totals 6,291 = 6,291) |

## Sources

- https://www.nfl.com/scores/2026/REG1 … REG8, week-1 … week-10 (finals)
- https://www.nfl.com/standings/league/2026/REG (cross-check)
- https://www.nfl.com/injuries/ (Week-10 report, 2026-11-13)
- https://www.nfl.com/schedules/2026/by-week/week-11 (Week-11 schedule)
- https://www.nfl.com/news/top-stories-from-week-9-of-the-2026-nfl-season
- https://www.nfl.com/news/ravens-qb-tyler-huntley-out-for-season-after-suffering-turf-toe-injury
- https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-week-10-game-vs-raiders-drew-lock-expected-to-start-again

## Deliverables

`nfl-intel.html`, `nfl-lines.html`, `nfl-strategies.html`, `nfl-injuries.html`,
`nfl-executive.html`, `suggestions.html`, `questions.html`; `scripts/build_nfl_intel.py`;
`scripts/nfl_intel.py`; `research/EXECUTIVE-SUMMARY-NFL.md`; data files above; flags F33–F41;
README + dashboard section; COORDINATION.md completion log.
