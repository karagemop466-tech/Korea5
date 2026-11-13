# Suggestions Register — NFL decision support

**Status:** proposal register for review. Nothing here is implemented or authorized. Each suggestion exists so a
reviewer can choose a path **before** implementation. No suggestion asserts a betting edge, correlation value, ROI,
or reward outcome.

**Review date:** 2026-11-13 · **Scope:** NFL line origination, strategy validation, leaderboard, injury/lineup tracking.
**Companion pages:** [Suggestions](../suggestions.html) · [Decision registry](../decisions.html) ·
[NFL Lines & Strategy Lab](../nfl-strategy.html) · [Injury & lineup-depth tracking](../injury-tracking.html).

## How to review and choose a path

1. **Read the decision it serves.** Every suggestion is tied to a decision in `DECISIONS.md`. A suggestion that does
   not close a decision, or close missing information, is not ready to implement.
2. **Check the dependency.** If a suggestion depends on data that is not licensed/available (for example timestamped
   odds, settlement records, or a historical depth-chart series), it is **blocked** until that dependency is resolved.
3. **Choose one path per decision.** Options are listed for each suggestion. Pick one and record the reason; do not
   implement two competing paths for the same decision until one is measured.
4. **Change the status, do not delete.** Statuses: `proposed` → `in review` → `approved` → `in progress` → `done`, or
   `declined` (with reason). Approved means the path is chosen, not that it is built.
5. **Re-verify before and after.** Any suggestion that adds data or a model must pass the validation gates in
   [NFL-STRATEGY.md](NFL-STRATEGY.md) before it can feed the leaderboard. Nothing enters the leaderboard unqualified.

## Suggestions

| ID | Suggestion | Decision it serves | Options | Recommended path | Priority | Status | Depends on |
|---|---|---|---|---|---|---|---|
| S-01 | Build a timestamped, source-attributed **market/odds archive** for eligible singles and player props. | D-01, D-02 | (a) License a commercial odds feed; (b) capture only closing lines from an authorized source; (c) delay until a lawful provider is chosen. | (b) Start with closing-line capture from an authorized, timestamped source; add intraday snapshots only if coverage is proven. | High | Proposed — blocked pending data rights | Lawful odds-data access (D-01) |
| S-02 | Build an **official injury / inactive snapshot and depth-chart evidence** pipeline. | D-04, D-06 | (a) Club injury report + NFL injury page + game-day inactives; (b) add team-site depth charts as the tier source; (c) defer depth order to a single vendor. | (a) + (b): use the official NFL injury report and each club's official depth chart, each with capture time and source URL. | High | Proposed — evidence incomplete | Confirmed update cadence and role/replacement proof (D-04) |
| S-03 | Implement a **walk-forward research harness** and an **immutable prediction ledger**. | D-03, D-05 | (a) Run all models in CI with frozen timestamps; (b) manual ledger; (c) defer until data exists. | (a): freeze forecast cutoffs, fit inside training folds, log every prediction before outcomes. | High | Proposed — no model has passed | Historical data + settlement definitions (D-05) |
| S-04 | Define **leaderboard scoring and minimum-evidence gates** (paper-first, no rewards yet). | D-07, D-08 | (a) Proper probability score improvement over a common baseline; (b) rank by accuracy; (c) rank by ROI. | (a): rank by predeclared out-of-sample score improvement over the same baseline, with calibration and coverage shown. Never rank by streak or raw win rate. | High | Proposed — no rewards authorized | Scoring rule, eligibility, governance (D-07, D-08) |
| S-05 | Build a **parlay / player-prop-combo joint-probability and correlation** pipeline. | D-05 | (a) Simulation / calibrated joint model; (b) assume independence; (c) defer. | (a): model joint settlement probabilities directly; measure dependence; never multiply marginals by default. | High | Proposed — blocked pending joint outcomes | Leg quotes, book rules, correlation data (D-05) |
| S-06 | Build a **lineup-depth tracker** (1st/2nd/3rd/4th string, offense and defense). | D-06 | (a) Club depth chart as the tier source; (b) infer tiers from injury status; (c) defer. | (a): read tiers only from an official depth chart; leave unsourced tiers blank and flagged. Never infer tier from injury status. | High | Proposed — incomplete evidence | Official depth-chart availability (D-06) |
| S-07 | Establish **transparent baseline models** (market-implied, league-average, team/player historical). | D-03 | (a) Market-implied baseline where prices exist; (b) league-average baseline; (c) both. | (c): both, evaluated on identical eligible events, as the hurdle every strategy must beat out of sample. | Medium | Proposed | Timestamped prices (S-01) |
| S-08 | Complete **legal, responsible-play, privacy and anti-gaming review** before any rewards. | D-08 | (a) Paper-only, no rewards; (b) restricted rewards after review; (c) no rewards ever. | (a): run paper-only first; no reward, eligibility or leaderboard prize is authorized by this proposal. | High | Proposed — blocking | Governance decision (D-08) |
| S-09 | Add a **decision dashboard** that lists every open question, its missing information and the suggestion that closes it. | All | (a) This suggestions/decisions page set; (b) a generated dashboard; (c) defer. | (a): this register plus the decision registry, kept current as statuses change. | Medium | Done (this page set) | None |
| S-10 | Automate the **validation gates in CI** so a strategy fails closed if any gate fails. | D-03, D-07 | (a) Gate script in the existing workflow; (b) manual gate checklist; (c) defer. | (a): encode gates as an automated check that blocks leaderboard entry on failure. | Medium | Proposed | Gate definitions frozen (D-03) |
| S-11 | Build a **data-provenance and point-in-time snapshot** system (immutable IDs, timestamps, revision history). | D-02, D-04 | (a) Append-only snapshot store keyed by source + capture time; (b) CSV dumps; (c) defer. | (a): append-only, with source, capture time and definition for every field; no silent overwrites. | High | Proposed | Data model (D-02) |
| S-12 | Build an **outcome / settlement ledger** recording pushes, voids, and exact payout rules per book. | D-05 | (a) Store exact leg quotes and settlement rules; (b) approximate settlement; (c) defer. | (a): store exact quotes and rules; approximate settlement is never used to settle a leaderboard score. | High | Proposed — blocked | Book rules and settlement data (D-05) |

## What this register does not do

* It does not select a data provider, book, or jurisdiction — that is decision D-01 and must be made deliberately.
* It does not rank strategies, because no strategy has passed a validation gate.
* It does not authorize rewards. Any reward decision waits on D-08.
* It does not fill missing values. Where an official source has not published a value, the cell stays blank and the row
  is flagged on the [Flagged for Review](../flagged.html) page.

## Official sources reviewed for these suggestions

| Source | What it provides | Link |
|---|---|---|
| NFL injury report | Player, position, injury, practice status, game status, by week | https://www.nfl.com/injuries/ |
| NFL transactions | Trades, signings, waivers, reserve list, terminations, by month/year | https://www.nfl.com/transactions/ |
| NFL player statistics | Passing/rushing/receiving/tackles/etc., category + year selectors | https://www.nfl.com/stats/player-stats/ |
| NFL team statistics | Offense/defense/special-teams team categories | https://www.nfl.com/stats/team-stats/ |
| NFL standings | Division/conference/league standings | https://www.nfl.com/standings/ |
| NFL schedules | By week, by team, prime time | https://www.nfl.com/schedules/ |
| 49ers official depth chart | Offense/defense/special-teams, 1st/2nd/3rd/4th string | https://www.49ers.com/team/depth-chart |
| NFL Football Operations | Official rules and officiating reference | https://operations.nfl.com/ |

These are verified official starting points, not proof that every historical field, market quote, or depth-chart
version is available there. Absent values remain blank/unverified.
