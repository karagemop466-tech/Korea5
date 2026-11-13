# NFL Lines Origination — research notes

**Status: research design only.** No measured edge, correlation value, ROI, fair line or top-performing strategy is claimed. No betting lines or odds are invented anywhere in this repository. Every value not published by an official source is left blank and flagged unverified. This is not betting advice.

## 1. Originating a line — method, not values

Independent line origination means estimating outcome probabilities first, then converting to fair prices, then comparing with an archived, timestamped offered price after vig. The repository currently contains none of the inputs required to do this:

* no timestamped historical market odds;
* no player-prop prices;
* no forecast ledger;
* no settled bet records;
* no validated injury-to-performance panel.

Suggested operating steps (none implemented):

1. **Forecast.** Build a probability estimate for each outcome (side, total, team total, player prop outcome) using only point-in-time data available before the decision cutoff.
2. **Convert to fair odds.** Convert probabilities to no-vig fair prices (methodology only; no sample values are shown).
3. **Compare.** Compare the fair price with the contemporaneous, archived offered price after vig. Record the decision, the quote, the timestamp and the source.
4. **Log.** Immutable prediction ledger: event ID, market, selection, forecast probability, fair price, offered price, vig, timestamp, source, outcome when known.

**Blocking fact:** NFL.com does not publish betting lines, odds or player-prop prices. Any line or price table on this site is therefore blank and flagged unverified until a lawful odds feed is chosen (see `decisions.html` rows 1–2, `suggestions.html` S1).

## 2. Bet types covered

| Bet type | What it is | How it is evaluated | Key risk | Official reference |
|---|---|---|---|---|
| Single bet | One selection on one market (spread, moneyline or total). | Forecast probability vs vig-adjusted offered price; proper scoring on outcomes. | Small samples; market efficiency; stale quotes. | https://www.nfl.com/stats/ |
| Parlay | Multiple selections combined; payout only if every leg wins. | Joint probability of all legs winning vs exact offered parlay price; settlement and void rules applied. | Same-game correlation; shared game script; book-specific rules. | https://operations.nfl.com/ |
| Player-prop combo | Multiple player props (same or different games). | Joint distribution of player outcomes; conditional modelling for teammates and shared game script. | Role uncertainty; participation vs active status; prop line movement. | https://www.nfl.com/stats/player-stats/ |

Marginal probability multiplication is invalid when legs are dependent. Joint probabilities are estimated directly or from a calibrated joint model; pairwise and higher-order dependencies are tracked where evidence exists. Correlation estimates are left blank and unverified when evidence is insufficient (section 4).

## 3. Candidate signal families (hypotheses, not established edges)

* **Team spread / moneyline** — possession-level expected points, efficiency, turnovers and special-teams estimates; home/venue and rest only when sourced and timestamped. Benchmark: vig-adjusted market probability where a timestamped quote exists; otherwise no comparison is made.
* **Game total / team total** — joint pace and scoring distribution from offensive/defensive play outcomes and expected possessions. Evaluate distribution calibration and total-line error on unseen weeks.
* **Player props** — player opportunity × per-opportunity production, adjusted for role, opponent and teammate availability. Active/injured status is not expected workload.
* **Injury / replacement adjustment** — estimated change from baseline conditional on official status, role, evidenced replacement and position-group dependencies. Track offence and defence symmetrically: offensive line combinations, quarterback, skill positions, defensive front and secondary.
* **Combinations** — joint event probabilities (simulation or calibrated conditional model); report dependence diagnostics and uncertainty. Never assume independence by default.

No candidate above is asserted to be profitable or validated.

## 4. Correlation values — measured, not assumed

For each pair of legs: store the exact market and line; estimate association from historical joint outcomes using only data available before the forecast timestamp; report sample size, uncertainty interval, season range and conditional context. Pearson correlation of binary outcomes is a descriptive phi coefficient, not a universal parlay pricing adjustment. Use conditional or joint probabilities for payout valuation. Shrink noisy estimates toward zero or a pool prior selected with training data only; publish the unshrunk estimate and uncertainty too. If there is not enough evidence, display **blank / unverified**, not zero.

Illustrative table template (all cells blank until evidence exists):

| Leg A | Leg B | Sample | Phi | Uncertainty | Season range | Context | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | blank / unverified |

## 5. Validation gates (must pass, in order)

1. **Data provenance** — every feature and outcome has source, event ID, timestamp, definition and revision history; point-in-time snapshots avoid future information.
2. **Coverage and integrity** — reconcile with official gamebooks/stats; quantify missingness and late corrections; no silent imputation of unverified injury/role values.
3. **Baseline** — beat simple league/team/player baselines and a de-vigged market reference on identical eligible events.
4. **Leakage audit** — features frozen to decision time; splits by time, never random rows; preprocessing and feature selection fitted inside training folds only.
5. **Out-of-sample performance** — proper probability scores, calibration, line error, ROI only with exact historical prices and settlement rules, plus uncertainty intervals and sample size.
6. **Robustness** — performance across seasons, market types and injury-certainty strata; sensitivity to vig, stale quotes, pushes/voids and multiple testing.
7. **Prospective paper trial** — freeze strategy version and log predictions before outcomes for a predeclared horizon. No leaderboard prize until complete.
8. **Release review** — reproducible run, independent review, no disqualifying integrity or responsible-use concerns; failed candidates retained in audit logs.

A strategy that fails any gate is “not qualified,” not silently removed.

## 6. Injury and lineup tracking requirements

Suggested schema: game/player identifiers; position; official status as published; report publication time; practice participation; game-day inactive confirmation; transaction/roster event; role/depth-chart evidence URL and timestamp; replacement identity/tier only when an official source supports it; expected snap/opportunity share (clearly labelled as a model estimate); actual participation from the official gamebook; source revision and capture time.

Track offence and defence symmetrically, including 2nd, 3rd and 4th-string backups replacing starters due to lineup changes — on both sides of the ball. Missing values stay blank and flagged. The injury report page publishes player, position, injuries, practice status and game status by week; the transactions page publishes roster events by date. Neither establishes a dated 2nd/3rd/4th-string lineup ranking on its own.

Sources: https://www.nfl.com/injuries/ ; https://www.nfl.com/transactions/ ; https://operations.nfl.com/

## 7. Leaderboard design proposal

Initially paper-only. Versioned strategy entries; immutable, timestamped forecasts; fixed eligible market set; public methodology. Rank by predeclared out-of-sample proper-score improvement over the same market baseline, with calibration and minimum-evidence gates; display uncertainty and coverage beside rank. Do not rank by winning streak, raw accuracy or unadjusted ROI. Reserve any reward decision until legal, privacy, fairness, responsible-play and anti-manipulation review. No rewards are authorized by this proposal.

## 8. Official starting sources reviewed

* https://www.nfl.com/stats/ — official NFL statistics portal (2026 season visible; historical completeness of any particular field must still be checked).
* https://www.nfl.com/stats/team-stats/ — official team statistics.
* https://www.nfl.com/stats/player-stats/ — official player statistics, category/year selector.
* https://www.nfl.com/injuries/ — official injury report: player, position, injuries, practice status, game status by week. Not a complete historical role or depth-chart dataset.
* https://www.nfl.com/transactions/ — official transactions by date.
* https://operations.nfl.com/ — official NFL rules and football operations reference.
* https://www.nfl.com/schedules/ — official schedule reference; 2027–2029 seasons not released.
* https://www.nfl.com/news/2026-27-national-football-league-important-dates — official NFL calendar: playoff round windows and Super Bowl LXI date; no Pro Bowl date.

All links above are official-source starting points for manual review, not proof that every proposed field or archived version is available there.