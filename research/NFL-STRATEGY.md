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

## Leaderboard and rewards (proposal)

Treat strategy development as a **leaderboard competition that rewards repeatable predictive skill, not short-run luck**.
This is a proposal only. **No strategy has been backtested here and no reward is authorized.**

**Entry rules (all must hold):**

* Each entry is a **versioned strategy** with a frozen methodology and a frozen decision cutoff.
* Every prediction is logged **before** its outcome, with market/selection, price, source and UTC timestamp
  (immutable ledger).
* The strategy covers a **fixed eligible market set** defined in advance.
* The strategy passes **all eight validation gates** above (and the bet-type gates below) before it can appear on the board.

**Scoring (do not rank by luck):**

* Rank by **predeclared out-of-sample improvement in a proper probability score** (e.g. Brier score / log loss) over a
  **common baseline** evaluated on the same eligible events.
* Show **calibration** and **coverage** beside the rank, plus the uncertainty interval.
* **Never** rank by winning streak, raw win rate, or unadjusted ROI. Those reward variance and luck.
* A strategy that fails any gate is **"not qualified"** and stays in the audit log — it is not silently removed.

**Rewards (gated):**

* Start **paper-only**. No real-money stake, no prize, no eligibility of capital.
* Any reward decision waits on decision **D-08** — legal, responsible-play, privacy and anti-gaming review. This
  proposal authorizes **no** reward.
* Reward the **validated score improvement**, not dollars wagered, not streaks, and not high-variance outcomes.

**Leaderboard state today:** no qualified entries. The repository has no timestamped odds, prop prices, settlement
records, or validated model, so no strategy can be scored or ranked. Every row is `not qualified`.

## Correlation values (measure; never invent)

For each pair of legs in a parlay or player-prop combination, correlation must be **measured from historical joint
outcomes** available before the forecast timestamp, and reported with sample size and uncertainty. A Pearson
correlation of binary outcomes is a descriptive **phi coefficient**, not a universal parlay-pricing adjustment; use
**conditional/joint probabilities** for payout valuation.

**Values table (all currently unverified — no joint-outcome data exists in this repository):**

| Leg pair | Correlation value | Sample size | Uncertainty | Status |
|---|---|---|---|---|
| Spread ↔ Total (same game) | (blank) | (blank) | (blank) | unverified — no data |
| Spread ↔ Spread (different games) | (blank) | (blank) | (blank) | unverified — no data |
| Player prop A ↔ Player prop B (same game) | (blank) | (blank) | (blank) | unverified — no data |
| Player prop ↔ Team total (same game) | (blank) | (blank) | (blank) | unverified — no data |
| Any leg pair (parlay) | (blank) | (blank) | (blank) | unverified — no data |

If there is not enough evidence, display **unverified / blank**, not zero. Shrink noisy estimates toward zero or a
pooled prior selected using training data only, and publish the unshrunk estimate and its uncertainty too. Multiplying
marginal probabilities to price a parlay is **invalid** under dependence; model joint settlement probabilities directly.

## Bet-type validation gates

Every strategy must pass the eight general gates above. In addition, each **bet type** carries its own gates:

| Bet type | Additional gates a strategy must pass |
|---|---|
| **Single bet** (spread / moneyline / total / team total) | (1) Probability forecast produced before the cutoff with a source and timestamp; (2) de-vigged market comparison on identical events; (3) proper scoring + calibration out of sample; (4) ROI only with exact historical prices; (5) robustness across seasons and subgroups. |
| **Parlay** (multi-leg) | (1) Joint probability model (simulation or calibrated conditional model), not marginal multiplication; (2) dependence/correlation measured with sample size + uncertainty; (3) exact leg quotes and book payout/void/push rules captured; (4) joint calibration and realized payout scoring against the exact quote; (5) coverage of leg dependence reported. |
| **Player prop combination** | (1) Opportunity × per-opportunity production model with role/opponent/teammate-availability inputs; (2) active status **not** equated with workload; (3) prop-type and role-certainty stratified calibration; (4) evaluated only against timestamped prop prices; (5) selection-bias and line-movement diagnostics. |

A strategy that cannot satisfy its bet-type gates is **not qualified** for that bet type, regardless of any other result.

## Injury and lineup-depth tracking

See [INJURY-TRACKING.md](INJURY-TRACKING.md). Track injuries and lineup deficiencies for **offense and defense**,
including when a **2nd, 3rd or 4th string** player replaces a starter. Tier is read **only** from an official depth
chart; availability is read **only** from an official injury report / inactive list; a "deficiency" requires both a
sourced tier change and a sourced availability change. Missing values stay blank and flagged. No workload or performance
effect is asserted without a validated panel.

## Companion pages

* [Suggestions](../suggestions.html) — review/choose workflow and the suggestion register (`research/SUGGESTIONS.md`).
* [Decision registry](../decisions.html) — questions, known/missing information, answers needed, discovery steps
  (`research/DECISIONS.md`).
* [Injury & lineup-depth tracking](../injury-tracking.html) — schema, tier logic and official sources
  (`research/INJURY-TRACKING.md`).
