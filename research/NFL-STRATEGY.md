# NFL Lines & Strategy Lab — research notes

> **Superseded and expanded (2026-11-13).** This document is the first pass on NFL lines and strategy work and is kept for
> the record. The live version is the **NFL Lines Lab** section of the site, which adds a decision register, a measured
> correlation and dispersion analysis, an injury and depth tracker built on the official injury report and the official Game
> Book, and a suggestions register: <https://karagemop466-tech.github.io/Korea5/lab/index.html> ·
> [research/NFL-LINES-LAB.md](NFL-LINES-LAB.md). Every statement below still holds; none of it claimed a validated edge and
> none of it does now.

## Executive summary

The repository previously held schedules, not a line-making or betting research system. It has no timestamped historical market odds, player prop prices, forecast ledger, settled bet records, or validated injury-to-performance panel. Accordingly, this work makes **no** claim of predictive edge, correlation magnitude, return, fair price, or top-performing strategy. It creates a proposal and explicit stop-gates rather than fabricate findings.

Build sequence: (1) source-attributed point-in-time data archive; (2) transparent baseline forecasts; (3) chronological, walk-forward evaluation against a vig-adjusted market reference; (4) calibration and uncertainty analysis; (5) locked prospective paper trial; (6) gated leaderboard. Singles and player props should be evaluated individually. Parlays require joint outcome probabilities and exact settlement/payout rules; marginal probability multiplication is not valid under dependence.

Injury analysis should preserve report timestamps, official status, game-day inactive status, actual participation, and evidence for role/replacement. “Starter” and backup order are not to be inferred from a team injury report. The proposed tracker explicitly separates official observations from model-estimated opportunity share and leaves unsupported values blank.

## Questions requiring answers before implementation

| Decision | Information currently available | Missing | Discovery step |
|---|---|---|---|
| Target markets | 2026 schedule pages, no odds | Markets/books/jurisdictions | Inventory legally accessible historical and prospective quote feed |
| Forecast timing | None specified | Cutoff and quote timestamp rules | Fix UTC decision cutoff and retain immutable snapshots |
| Injury source policy | Official NFL injury report link | Longitudinal availability, role/depth-chart proof, replacement order | Archive source pages/reports with capture and publication time |
| Skill criterion | No model evaluation | Minimum sample, scoring, uncertainty, selection correction | Pre-register gates and use an untouched temporal holdout |
| Parlay pricing | No props/payouts | Joint outcomes, book rules, pushes/voids | Store exact leg quotes and settlement rules; build joint model |
| Competition/rewards | None exists | Reward basis, eligibility, legal/privacy/governance | Begin paper-only; complete policy review before rewards |

## Candidate signals — hypotheses only

- Team spread/moneyline: possession-level scoring expectation, offense/defense and special teams; compare calibrated probabilities with de-vigged market probabilities.
- Total/team total: expected possession and scoring distributions; evaluate distribution calibration, overtime and regime changes.
- Player props: opportunity and per-opportunity production conditioned on role, teammate availability and opponent; do not equate active status with expected workload.
- Injury adjustment: estimate incremental value conditional on timestamped status and evidenced replacement/role; separate missingness and uncertainty.
- Combinations: estimate joint event probabilities (simulation or calibrated conditional model); report dependence diagnostics and uncertainty. Never assume independence by default.

No candidate above is asserted to be profitable or validated. The website includes a row-by-row market, risk and evaluation table.

## Validation gates

1. Provenance and point-in-time data; immutable IDs, timestamps, source and definitions.
2. Coverage and reconciliation, including corrections and missingness; no silent fills.
3. Baselines, including market reference where contemporaneous prices exist.
4. Leakage audit and time-ordered splits; fit transformations inside training folds.
5. Out-of-sample proper scoring, calibration, uncertainty, and ROI only when actual quotes/settlement are captured.
6. Robustness across seasons and defined subgroups; vig, pushes, voids, stale quotes and multiple testing.
7. Locked prospective paper trial with predeclared horizon.
8. Independent release review; failed strategies remain in audit history.

Leaderboard proposal: paper-only first; rank by predeclared improvement in out-of-sample probability score over a common market baseline, with calibration and minimum-evidence qualification. Show uncertainty and coverage. Do not rank by streaks or raw win rate. No rewards are authorized by this proposal.

## Official starting references

- [NFL statistics](https://www.nfl.com/stats/) — official league statistics portal; availability and historical completeness of a particular field must still be checked.
- [NFL team statistics](https://www.nfl.com/stats/team-stats/) — team statistics landing page.
- [NFL player statistics](https://www.nfl.com/stats/player-stats/) — player statistics landing page.
- [NFL injury report](https://www.nfl.com/injuries/) — official injury information starting point; not a complete historical role dataset.
- [NFL transactions](https://www.nfl.com/transactions/) — official transaction information starting point.
- [NFL Football Operations](https://operations.nfl.com/) — rules and football operations reference.

The links above are official-source starting points, not a claim that every proposed feature, archived version, depth chart, or bookmaker quote is available there. Any absent value remains blank/unverified until checked.
