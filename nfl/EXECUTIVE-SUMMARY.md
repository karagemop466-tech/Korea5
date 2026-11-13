# NFL Lines Lab — Executive Summary

*All figures below are produced by the repository pipeline (`nfl/fetch_data.py` → `nfl/model.py` →
`nfl/analyze.py` → `nfl/leaderboard.py`) from hashed public files, on the full 2016–2026 dataset.
Generated for CI run `nfl-lines-model` on branch `arena/02f4d067-korea5`; the live, self-updating version
of this document is the site's [Executive summary](nfl-lines/executive.html) page, which renders every
number from `nfl/data/*.json` at build time.*

## 1. What exists today

- **Data pipeline** — weekly NFL data (schedules, scores, rosters, injuries, depth charts, snap counts,
  player stats, play-by-play) fetched from the nflverse-data GitHub releases, plus ESPN scoreboard
  cross-checks; every file stored with a SHA-256 hash in `nfl/data/provenance.json`.
- **Own-line model** — an Elo/form strength engine producing team ratings and a walk-forward logistic
  model that outputs a home-win probability per game. This *is* the lab's own line: no published market
  number is used as an input to the prediction.
- **Validation gates** — walk-forward evaluation (no lookahead), luck deflation via a best-of-K
  permutation null, calibration slope, per-season stability, and sample-size floors. Gates G1–G8 are
  preregistered in `nfl/PREREGISTRATION.md`; nothing is promoted without passing them.
- **Leaderboard competition** — strategies (single-game models, prop markets, parlay families,
  same-game prop combos) are scored and ranked; reward tiers A/C/D with lab points 1000/300/50
  (non-monetary) for top performers. Entry rules and scoring formulas are published on the
  [Leaderboard](nfl-lines/leaderboard.html) page.
- **Injuries and depth** — weekly injury reports plus depth charts with 1st/2nd/3rd/4th-string tiers per
  position unit, snap-weighted replacement values, and explicit chart-snapshot dates on
  [Injuries & lineups](nfl-lines/injuries.html).
- **Verification** — a second publisher (ESPN) checked game-by-game against nflverse results.

## 2. Headline result (out-of-sample, 2017–2022 seasons)

| Measure | Value |
|---|---|
| Games evaluated out of sample | **1,632** |
| Accuracy (higher-probability side) | **0.636** |
| Log loss | **0.63924** vs baseline 0.68848 |
| **Log-loss skill vs baseline** | **+0.07152** |
| Brier skill vs baseline | +0.09291 (0.22381 vs 0.24673) |
| Luck deflation (best-of-K null) | N=200 permutations, K=9, null p95 = **0.02863**, 22 season-blocks |
| Deflation verdict | **passed** — observed skill exceeds the 95th percentile of the luck null |

The skill is **selective**: it comes entirely from the *strength* family (Elo-style ratings + recent form).

| Family | Skill | Null p95 | Deflation verdict |
|---|---|---|---|
| Strength (Elo + form) | 0.07152 | 0.02863 | **passed** |
| Context (rest, dome, QB change, injuries out) | 0.0006 | 0.05157 | **failed** — not distinguishable from luck |

## 3. Strategy competition status

Leaderboard (top rows; full board on [Leaderboard](nfl-lines/leaderboard.html)):

| # | Tier | Score | Strategy | Sample |
|---|---|---|---|---|
| 1 | A | 4.289 | Single-game model — strength features (9 signals) | 1,632 games |
| 2 | C | 1.79 | WR receptions over 4.5 | 1,573 |
| 3 | C | 1.68 | RB rushing yards over 55.0 | 1,011 |
| 4 | C | 1.34 | WR receiving yards over 45.0 | 1,573 |
| 5 | C | 0.68 | RB rushing touchdowns over 0.5 | 1,011 |
| … | C | — | QB, TD and parlay/prop-combo families (reference only) | — |

- **Singles**: the strength model is the only Tier-A strategy (all gates passed).
- **Parlays**: 2-leg and 3-leg cross-game families are published as *reference rows* with expected vs
  realised joint hit rates (one construction per season, n=6). No payout is claimed — see GAP-1.
- **Player-prop combos**: same-game combos are only constructed where the measured correlation excludes
  zero (best-of-K bootstrapped). The published quantity is the *gap* between the copula joint probability
  and the naive product — i.e. how wrong multiplying marginals would be — not a price.

## 4. Correlation values (measured, 55 signal pairs, 11 exclude zero)

| Pair | Pearson r | 95% bootstrap CI | N |
|---|---|---|---|
| off_value_diff ~ def_value_diff | 0.253 | [0.203, 0.300] | 1,632 |
| off_out_diff ~ def_out_diff | 0.205 | [0.162, 0.252] | 1,632 |
| dome ~ def_value_diff | 0.124 | [0.076, 0.172] | 1,632 |
| dome ~ off_value_diff | 0.105 | [0.053, 0.152] | 1,632 |
| away_qb_change ~ off_value_diff | 0.079 | [0.031, 0.123] | 1,535 |
| home_qb_change ~ off_value_diff | −0.076 | [−0.125, −0.022] | 1,537 |

Pairs whose interval contains zero are published as *unmeasured*, never as zero. Within-team same-week
prop correlations (shared game script) are negative or near zero once the best-of-K filter is applied
(e.g. RB rushing yards ~ rushing TDs r = −0.081 [−0.120, −0.038]).

## 5. Verification performed

| Check | Result |
|---|---|
| nflverse result vs ESPN final score (independent publishers) | **2,776 of 2,776** ESPN-sampled completed games match exactly; **0 differ, 0 unmatched** |
| Neutral-site games | joined on team pair, not on published home team |
| Kickoff-date skew (ESPN dates are UTC) | ±2-day pairing window verified 136/136 on local sample |
| Franchise relocations (OAK/LV, SD/LAC, STL/LA) | season-aware abbreviation table; residual unmatched count driven to zero |
| Provenance | every fetched file recorded with SHA-256 + source URL; 3 unavailable assets named on the [Data audit](nfl-lines/data.html) page |
| Market coverage | spread present for 100 %, total 100 %, moneyline 99.97 % of 2,898 completed games — but each is a **single un-timestamped snapshot** (GAP-1) |
| Unit tests | 9 model tests, root suites and link audit all green in CI |

## 6. What is NOT claimed

- **No profit, ROI, payout or edge claim.** No timestamped price history exists (GAP-1), so closing-line
  value and returns cannot be computed. This lab is a research model that originates its own lines; it is
  not, yet, a betting system.
- Context-family skill is **not** claimed — it fails the luck-deflation gate.
- Nothing on the site is hand-entered; unverifiable values stay blank and appear on
  [Flagged](nfl-lines/flagged.html).

## 7. Open gaps blocking decisions (details on [Data audit](nfl-lines/data.html))

| ID | Missing | Blocks |
|---|---|---|
| GAP-1 | Timestamped odds history (opening/closing, all books) | ROI, CLV, edge, parlay payouts |
| GAP-2 | Player-prop prices | Prop-market edge claims |
| GAP-3 | Official weekly inactive list (game-day) | Exact 1st–4th-string confirmation on game day |
| GAP-4 | Talent-weighted depth (draft/contract value) | Precise backup-quality discount |
| GAP-5 | Larger subgroup samples for combo props | Tighter combo-correlation intervals |
| GAP-6 | Injury-report timestamps | Intra-week designation movement analysis |

## 8. Open questions before decisions

Twelve questions ([Questions](nfl-lines/questions.html), Q1–Q12) are published with what is known, what is
missing, the impact, and a concrete suggestion to obtain the missing information. The pivotal one is Q1:
*forecast accuracy against a baseline, or profit against a price?* — today only the former is computable.
Ten hypotheses (H1–H10) carry explicit verdicts on [Signals](nfl-lines/signals.html).

## 9. Suggested paths (choose before anything changes)

Ten proposals (S1–S10) are listed on [Suggestions](nfl-lines/suggestions.html) — ranked by decision value,
each with what it needs and what it unblocks. Nothing is implemented from that list until a path is chosen.

## 10. Reproduce

```bash
python3 nfl/fetch_data.py --with-espn --seasons 2016:2026
python3 nfl/model.py --perm 200
python3 nfl/analyze.py
python3 nfl/leaderboard.py
python3 nfl/build_site.py
python3 -m unittest discover -s nfl/tests
```

Every number in this summary appears in `nfl/data/model_results.json` (CI-computed, committed with the
run log `nfl/data/last_run.log`) and is re-derived by the commands above.
