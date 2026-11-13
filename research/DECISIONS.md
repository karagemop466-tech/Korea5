# Decision Registry — NFL decision support

**Purpose:** the list of questions, the information we have, the information we do **not** have, and the answer needed
before any decision can reasonably be made. Each row names the suggestion that would discover the missing information.
Nothing here is a resolved decision unless its status says so.

**Review date:** 2026-11-13 · **Companion:** [Suggestions](SUGGESTIONS.md) · [Suggestions page](../suggestions.html) ·
[NFL Lines & Strategy Lab](NFL-STRATEGY.md).

## How to read this registry

* **What we know (verified)** — facts confirmed against an official source in this repository, with the source link.
* **What we do not have** — the missing information. If it is missing, the decision is **blocked**; it is not guessed.
* **Answer needed to proceed** — the specific decision or value required to move forward.
* **Suggestion** — the suggestion (S-xx) that would discover the missing information.

## Decisions

| ID | Decision / question | What we know (verified) | What we do not have | Answer needed to proceed | Suggestion | Status |
|---|---|---|---|---|---|---|
| D-01 | Which markets and odds data can we lawfully use to originate lines? | The repo holds NFL schedules and official stats sources but **no odds feed**. Official stats (player/team) and schedule pages are live and verified. | Legal market scope, authorized odds-data provider, supported markets, timestamp fidelity, cost, jurisdiction. | Choose the lawful data provider, books, markets and the decision cutoff for quote capture. | S-01 | **Blocked** — data rights not chosen |
| D-02 | What exactly does "originate a line" mean operationally here? | No line-making workflow exists in the repo. Forecasts and prices are distinct: estimate outcome probabilities, then convert to fair odds. | Definition of decision cutoff, vig-removal method, snapshot frequency, stale-line policy, market/selection IDs. | Freeze a written definition: cutoff, market universe, vig method, snapshot cadence, stale policy. | S-01, S-11 | **Blocked** — definition not frozen |
| D-03 | How is model skill separated from luck? | No historical bets, odds, forecasts, or model evaluation exist in the repo. Skill must be judged out of sample, not by short-run outcomes. | Minimum sample, scoring rule, calibration tolerance, uncertainty policy, multiple-testing policy, temporal holdout. | Pre-register the scoring rule, minimum evidence, holdout, and the policy for reporting all tried variants. | S-03, S-04, S-07, S-10 | **Blocked** — no evaluation harness |
| D-04 | Which injury and availability inputs can be verified, and at what cadence? | The official NFL injury report publishes player, position, injury, practice status and game status by week. The official transactions page publishes roster moves by month. | Longitudinal history, capture/publication timestamps, role/replacement evidence, inactive-list confirmation, update cadence. | Confirm the source hierarchy, capture method and update cadence for injury + inactives. | S-02, S-11 | **Partially known** — live sources exist, history/cadence not confirmed |
| D-05 | Can singles, parlays and player-prop combos be fairly evaluated? | No prop odds, joint outcomes, or settlement records exist in the repo. Parlay value requires joint probabilities, not marginal multiplication under dependence. | Leg quotes, book payout/void/push rules, joint outcome history, correlation data. | Obtain exact leg quotes and settlement rules; build a joint model; measure dependence. | S-05, S-12 | **Blocked** — no quotes or settlement data |
| D-06 | How are lineup tiers (1st/2nd/3rd/4th string) established for offense and defense? | A club's **official depth chart** publishes 1st/2nd/3rd/4th string for offense, defense and special teams (verified on 49ers.com, updated 11/10/26). Injury status alone does **not** establish tier. | Depth-chart history, role/replacement proof, projected workload, confirmation that the tier matches actual snaps. | Confirm the depth-chart source and cadence; define when a tier may be used as an input. | S-02, S-06 | **Partially known** — official tier source verified, history/workload not |
| D-07 | How is the leaderboard scored and who qualifies? | No competition exists. Ranking by streak or raw win rate rewards luck; rank by predeclared out-of-sample score improvement over a common baseline. | Scoring rule, eligibility, minimum evidence, calibration gate, coverage display, versioning. | Freeze the scoring rule, eligibility and minimum-evidence gates in writing. | S-04, S-10 | **Blocked** — no scoring rule frozen |
| D-08 | What rewards and governance controls are acceptable? | No competition, accounts, rewards, or governance exist. Rewards must not conflate skill with capital or variance. | Reward basis, eligibility, responsible-play controls, privacy, anti-gaming, legal review. | Complete legal/responsible-play/privacy/anti-gaming review; decide whether any reward is authorized. | S-08 | **Blocked** — governance not reviewed |
| D-09 | How are correlation values determined for parlay/prop legs? | Correlation must be measured from historical joint outcomes available **before** the forecast timestamp; a phi coefficient of binary outcomes is descriptive, not a universal pricing adjustment. | Historical joint-outcome data, sample size, uncertainty, season range, conditional context. | Obtain the joint-outcome history and the predeclared estimation method; report sample size and uncertainty. | S-05 | **Blocked** — no joint-outcome data |
| D-10 | How do we track defensive (and offensive) deficiencies when backups replace starters? | Official depth charts expose tier depth; official injury reports expose who is out/limited/questionable. A deficiency exists only when a sourced tier change is tied to a sourced availability change. | A validated link from tier change → expected performance change; replacement-quality history. | Define the rule that a "deficiency" requires both a sourced tier change and a sourced availability change; leave the performance effect unmodeled until data exists. | S-02, S-06 | **Partially known** — source data verified, performance link not |

## Decisions already resolved by this work (no further action needed)

| ID | Decision | Resolution | Evidence |
|---|---|---|---|
| R-01 | Create a dedicated suggestions section for review | Done — `suggestions.html` + this register, with a review workflow and statuses. | [Suggestions page](../suggestions.html) |
| R-02 | Provide a clear list of questions/info/answers before decisions | Done — this registry, with known/missing/answer-needed and a discovery suggestion per decision. | This page |
| R-03 | Propose a leaderboard with rewards for top strategies | Proposed — paper-first design, gated; no rewards authorized. | [NFL-STRATEGY.md](NFL-STRATEGY.md), [nfl-strategy.html](../nfl-strategy.html) |
| R-04 | Propose validation gates each strategy must pass | Proposed — eight ordered gates, plus bet-type-specific gates. | [NFL-STRATEGY.md](NFL-STRATEGY.md) |
| R-05 | Propose injury + lineup-depth tracking (starter/backup tiers) | Proposed — schema + official sources; tiers only from official depth charts. | [INJURY-TRACKING.md](INJURY-TRACKING.md) |

## Irregularities / evidence limits (do not block, but must be known)

1. **No market odds, prop prices, settlement, or forecast data exist in this repository.** No edge, correlation value,
   ROI, or leaderboard result is claimed. All leaderboard rows are `not qualified`.
2. **No historical depth-chart or injury series exists.** The 49ers depth chart is a live official snapshot
   (updated 11/10/26), not a history. Tier changes cannot be backfilled from injury status alone.
3. **Injury status ≠ workload.** "Out/questionable/limited" does not imply a backup's expected snaps. Projected
   opportunity share would be a model estimate and is not asserted here.
4. **Depth-chart URL on NFL.com.** `nfl.com/teams/.../roster/depth-chart` returned 404 in this check; the verified
   official tier source used here is the club's own depth-chart page (e.g. 49ers.com). This is logged for review.
5. **Rulebook URL normalization.** The NFL Football Operations rulebook returned content when requested; the tool's
   reported canonical URL differed from the requested one. The verified landing reference is
   https://operations.nfl.com/ . Logged for review.
