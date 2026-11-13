# NFL Lines Lab — Executive Summary

*Session `arena-fb9c9608`, branch `arena/fb9c9608-korea5`, built 2026-11-13. Companion to
`research/NFL-STRATEGY.md` (the earlier proposal by session `arena-2cd43859`), which this build implements
on real data. Live pages: `nfl-lab/index.html` on the site.*

## What was built

| Piece | Status | Where |
|---|---|---|
| Official data layer | **done** | Official NFL.com Week 10 injury report (296 player rows / 28 teams / 14 games), Week 10 schedule with the TNF final (Commanders 24, Giants 21), Week 11 schedule — all fetched 2026-11-13 and transcribed with provenance (`nfl-lab/data/official/`) |
| Results & market data | **done** | nflverse/nfldata `games.csv` (7,548 games, 1999–2026), closing/initial lines, standings, teams crosswalk (`nfl-lab/data/nfldata/`) — market data labelled as market, never presented as official |
| Lines origination | **done** | Walk-forward margin/pace ratings (tuned on 2016–2019 only) originate spread + total for every Week 10/11 2026 game, published against the market number with edges (`nfl-lab/lines.html`) |
| Strategy leaderboard + validation gates | **done** | 8 strategies walked forward on held-out 2020–2025 at flat −110/ML pricing through 6 gates (`nfl-lab/leaderboard.html`) |
| Correlation values | **done** | Measured margin–total Pearson r, cover×over phi, same-game-parlay multipliers (400k seeded sims/scenario), two-leg parlay arithmetic (`nfl-lab/correlation.html`) |
| Injury & depth tracking | **done** | Official-report transcription + per-unit availability-pressure index + QB availability notes with start counts (`nfl-lab/injuries.html`) |
| Suggestions review board | **done** | 14 proposals awaiting review before implementation (`nfl-lab/suggestions.html`) |
| Decision register | **done** | 8 decision questions with have/don't-have/discovery-step columns (`nfl-lab/decisions.html`) |
| Repo review | **done** | 8 cross-check classes with evidence links; repo checks re-run (`nfl-lab/review.html`) |
| Missing-information discovery | **implemented** | CI workflow snapshots nflverse injuries/depth-charts/snap-counts + market lines weekly (`.github/workflows/nfl-lab-data.yml`) — unblocks the currently blank areas |

## Headline findings (honest, measured)

1. **No strategy qualifies yet.** On 2020–2025 held-out walk-forward, every candidate strategy's flat-bet ROI
   95% CI includes zero (favorites-ML baseline: −2.94%, n=1,615; best spread-edge rule −1.98%). The
   leaderboard correctly contains zero qualified entries — this is what "remove luck from the equation"
   looks like in practice. Failed strategies stay published.
2. **The rating model is a baseline, not an edge.** Held-out spread MAE 10.18 pts vs market 9.76 pts; total
   MAE 10.92 vs 10.28. Nothing on the lines board is a recommendation.
3. **Same-game correlation on this dataset is near-independence.** Margin–total r = +0.0201 (n=6,967);
   home-cover × over phi = +0.0219; SGP multipliers 0.985×–1.011×. Correlation folklore is not imported;
   values are measured and reproducible (fixed RNG seed).
4. **Availability pressure is measurable now.** From the official Week 10 report, teams with an
   elevated/critical unit are highlighted on the tracker; depth-chart tier (2nd/3rd string) is deliberately
   **not** inferred anywhere (no depth-chart data yet — flag NFL-K4, discovery step S13).
5. **Rewards are suspended by design.** Gates G5 (closing-line value vs archived entry quotes) and G6
   (prospective locked trial) cannot be satisfied with current data; leaderboard points are paper research
   credit only, and no monetary reward is authorized.

## Verification performed

- 27/27 Week 10 + Week 11 matchups and kickoffs agree between the official NFL.com pages (fetched
  2026-11-13) and the committed dataset; TNF result and the 26 printed team records also agree (0 mismatches).
- The injury report transcription passes programmatic checks (296 rows, 28 teams, 14 games; every row
  published on `nfl-lab/injuries.html` with its source link).
- `nfl-lab/scripts/verify_nfl_lab.py`: 20/20 checks (JSON validity, local links, per-row source links,
  content spot checks, no placeholder leakage).
- Repo checks re-run: `check_links.py`, `verify_extra.py`, `audit_certainty.py`, unit tests (results in the
  COORDINATION.md session log).
- An early build bug — a spread-sign convention flip — was caught by impossible leaderboard numbers and fixed
  against the dataset's own `DATASETS.md` documentation before publication.

## Irregularities flagged (non-blocking, published on `nfl-lab/flagged.html`)

NFL-K1 player name/slug mismatch on NFL.com; NFL-K2/K3 conflicting QB information (MIN, SEA) left unpublished
rather than guessed; NFL-K4 depth charts unavailable in-sandbox (CI fetch added); NFL-K5 market data
provenance; NFL-K6 CLV not measurable without entry-quote archive; NFL-K7 Week 12+ lines unposted; NFL-K8
report is a Friday snapshot, not game-day; NFL-K9 no-edge policy banner; NFL-K10 player props blocked by
missing opportunity data.

## What must happen before any decision

See `nfl-lab/decisions.html` (the decision register) and `nfl-lab/suggestions.html` (the review board).
Highest-impact items: archive timestamped market quotes (S12 → unblocks CLV gate G5) and land the nflverse
injury/depth/snap data through CI (S13 → unblocks the injury→outcome panel, depth facts, and player props).
