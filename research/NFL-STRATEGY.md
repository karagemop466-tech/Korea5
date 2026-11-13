# NFL Lines & Strategy Lab — research notes

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

## Skill versus luck: removing chance

Luck is short-run variance that is not repeatable. A strategy is treated as skill only when its measured performance is
distinguishable from a no-skill reference on unseen data, with the sample and uncertainty stated. Raw win rate and streaks
are not evidence of skill.

| Concept | Definition / rule | How it is applied | Measured value | Official source |
|---|---|---|---|---|
| Chance baseline | A no-skill reference the strategy must beat (de-vigged market, league-average, or always-favorite). | Scored on identical eligible events. | blank — no baseline data stored | [NFL statistics](https://www.nfl.com/stats/) |
| Proper scoring rule | Brier score and log loss penalise over-confidence and miscalibration. | Applied to every forecast probability, out-of-sample. | blank — no forecasts stored | [NFL statistics](https://www.nfl.com/stats/) |
| Calibration | Predicted probability versus observed frequency; calibration + refinement. | Checked by prop type, market and injury-certainty stratum. | blank — no forecasts stored | [NFL statistics](https://www.nfl.com/stats/) |
| Skill versus chance | Skill = measured − chance, with a bootstrap confidence interval. | Qualifies only if the interval excludes zero or the predeclared threshold. | blank — no prices/outcomes stored | [NFL team statistics](https://www.nfl.com/stats/team-stats/) |
| Minimum sample | A predeclared minimum number of eligible events. | Set before evaluation; below it, strategies are not ranked. | blank — not yet predeclared | [NFL Football Operations](https://operations.nfl.com/) |
| Multiple testing | Correct for many tried variants so one lucky variant does not look like skill. | All variants published; corrections applied before ranking. | blank — no variant history | [NFL Football Operations](https://operations.nfl.com/) |
| Selective deployment | Only gate-passing strategies are eligible for the leaderboard or reward. | Failed strategies stay in the audit log. | not yet implemented | [NFL official site](https://www.nfl.com/) |

## Correlation measurement plan

Correlation is measured from historical joint outcomes using only data available before the forecast timestamp. Pearson
correlation of binary outcomes is a descriptive phi coefficient, not a universal parlay adjustment; joint probabilities are
used for payout valuation. Values are blank until a verified joint-outcome panel exists.

| Combination | Method | Inputs | Output metric | Current value | Official source |
|---|---|---|---|---|---|
| Same-game parlay legs | Empirical joint outcomes with bootstrap intervals. | Official team and player stats, point-in-time. | Joint probability and phi coefficient with interval. | blank — unverified | [NFL team statistics](https://www.nfl.com/stats/team-stats/) |
| Player-prop same-game legs | Calibrated conditional model of one leg given the other. | Official player stats, role and availability. | Conditional probability with interval. | blank — unverified | [NFL player statistics](https://www.nfl.com/stats/player-stats/) |
| Cross-game parlay legs | Empirical joint outcomes, shrunk toward a training-only prior. | Official team stats, point-in-time. | Correlation with interval; unshrunk also published. | blank — unverified | [NFL team statistics](https://www.nfl.com/stats/team-stats/) |
| Higher-order combinations | Joint simulation or calibrated joint model. | Official stats and game context. | Joint settlement probability with diagnostics. | blank — unverified | [NFL statistics](https://www.nfl.com/stats/) |

## Bet-type evaluation rules

| Bet type | Pricing rule | Dependence handling | Evaluation metric | Measured value | Official source |
|---|---|---|---|---|---|
| Single bet — spread / moneyline / total | Compare model probability with a de-vigged market probability at the same timestamp. | None within the bet. | Proper score, calibration, ROI with exact prices and settlement. | blank — no timestamped prices stored | [NFL statistics](https://www.nfl.com/stats/) |
| Parlay — multi-game | Estimate joint outcome probability directly; never multiply marginals under dependence. | Pairwise and higher-order dependence. | Joint calibration and realized payout log loss. | blank — no joint outcomes stored | [NFL Football Operations](https://operations.nfl.com/) |
| Player-prop combination | Opportunity × per-opportunity production per leg, conditioned on role and availability. | Same-game correlation between player legs. | Calibration by prop type and role certainty, plus joint payout score. | blank — no prop prices stored | [NFL player statistics](https://www.nfl.com/stats/player-stats/) |
| Injury-adjusted single bet | Adjust baseline by timestamped official status and evidenced replacement. | Position-group dependencies; missingness separate. | Pre-news vs post-news improvement. | blank — no injury panel stored | [NFL injury report](https://www.nfl.com/injuries/) |

## Lineup and injury tracking schema (offense and defense)

The same schema applies to both offense and defense. A replacement tier is recorded only when an official source supports
it; otherwise it stays blank and flagged.

| Unit | Fields tracked | Official source | Verified status |
|---|---|---|---|
| Offensive line (OT, G, C) | Player, position, status, report time, practice participation, game-day inactive, transaction event, role evidence, replacement tier (if sourced), expected snap share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL transactions](https://www.nfl.com/transactions/) | source official; depth/role value unverified |
| Quarterback | Player, status, report time, practice participation, game-day inactive, replacement tier (if sourced), actual participation and stat outcome | [NFL injury report](https://www.nfl.com/injuries/) · [NFL player statistics](https://www.nfl.com/stats/player-stats/) | source official; depth/role value unverified |
| Running back / fullback | Player, status, report time, practice participation, game-day inactive, role evidence, expected share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL player statistics](https://www.nfl.com/stats/player-stats/) | source official; depth/role value unverified |
| Wide receiver / tight end | Player, status, report time, practice participation, game-day inactive, role evidence, expected share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL player statistics](https://www.nfl.com/stats/player-stats/) | source official; depth/role value unverified |
| Defensive line | Player, position, status, report time, practice participation, game-day inactive, transaction event, role evidence, replacement tier (if sourced), expected snap share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL transactions](https://www.nfl.com/transactions/) | source official; depth/role value unverified |
| Linebacker | Player, status, report time, practice participation, game-day inactive, role evidence, replacement tier (if sourced), expected snap share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL player statistics](https://www.nfl.com/stats/player-stats/) | source official; depth/role value unverified |
| Defensive back (CB, S) | Player, status, report time, practice participation, game-day inactive, role evidence, replacement tier (if sourced), expected snap share (estimate), actual participation | [NFL injury report](https://www.nfl.com/injuries/) · [NFL player statistics](https://www.nfl.com/stats/player-stats/) | source official; depth/role value unverified |

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
