# Executive summary — NFL intelligence (2026 season)

Date: 2026-11-13 (Pacific) · Section: [nfl-intel](../nfl-intel.html) · Mirror: [nfl-executive.html](../nfl-executive.html)

Everything below is either **verified** (transcribed from an official page, link given), **computed** from
verified inputs (formula given), or **unverified** (blank and flagged). Nothing is inferred.

## 1. What was built

| Deliverable | Where | Label |
|---|---|---|
| Verified 2026 results, weeks 1–10 (137 finals) | `data/nfl-intel/results-2026.json` | verified |
| Official league standings (cross-check) | `data/nfl-intel/standings-2026.json` | verified |
| Week-10 injury report + starter/backup news | `data/nfl-intel/injuries-week10.json` | verified |
| Ratings, our lines, backtest, signal correlations | `data/nfl-intel/model.json` | computed |
| Strategy library, gates, correlation policy | `data/nfl-intel/strategies.json` | design |
| Suggestions register (review-and-choose) | [suggestions.html](../suggestions.html) | process |
| Questions register (have / missing / discovery) | [questions.html](../questions.html) | process |

## 2. Verification story (how we know the data is right)

- All 137 finals transcribed from official nfl.com score pages ([scores 2026](https://www.nfl.com/scores/2026/week-9) …week-10), each row carries its source URL.
- Reconciled team-by-team against the official league standings: **32 of 32 teams match exactly** on wins, losses, ties, points-for and points-against (totals 6,291 = 6,291). One point clarified in that reconciliation: the standings snapshot includes the Week-10 Thursday game (WAS 24 @ NYG 21), which is why it shows 137 games.
- Injury rows transcribed verbatim from the official [Week-10 report](https://www.nfl.com/injuries/); blank Game Status means "not yet published", never an inference.

## 3. Model and lines (computed from verified results)

- Rating model: opponent-adjusted margin, least squares, mean(rating) = 0. Spread = R_home − R_away + HFA; total = average of the two team paces; P(home) = Φ(margin/σ), σ = 13.18 pts.
- **HFA in 2026 is −0.02 pts/game** — effectively zero this season. We still use the computed value, never a league-average assumption.
- Walk-forward backtest, weeks 5–9 (each week fit strictly on earlier weeks only):
  - S1: spread MAE 10.56 vs 11.32 baseline · Brier 0.216 vs 0.255 · side hit 66.2% · corr(predicted, actual) 0.314
  - S2 (recency λ=0.9): MAE 10.54 · Brier 0.215 · hit 63.4% · corr 0.318
  - Gates G1 (skill over baseline) → G4 (holdout) **PASS** for both; G5 (ATS vs closing line) and G6 (bootstrap certainty) are **not evaluable** — no verified odds source exists (Q-ODDS).
- 26 originated lines published (13 remaining Week 10 + all Week 11) on [nfl-lines.html](../nfl-lines.html). Market columns are blank and flagged by design.

## 4. Signals and correlation values (computed)

Correlation with actual game margin (n = 74 walk-forward games): **rest-days difference 0.438** (strongest),
rating difference 0.325, streak difference 0.281, scoring-pace difference 0.194. Home is a constant in the sample
(undefined correlation; HFA ≈ 0). Parlay-leg and player-prop pair correlations are **blank and flagged** —
no graded market or prop data exists to measure them (Q-ODDS, Q-PROPS); the frameworks use conservative
Fréchet bounds in the meantime.

## 5. Injuries and deficiencies (verified)

Week-10 snapshot: 296 reportable rows across all 14 games; the LAC @ BAL Monday game carries an official
"No Injuries Reported" designation. Verified deficiency chains (official sources only):

- **Baltimore QB — 3rd/4th string**: Lamar Jackson (starter) placed on IR, out 6–9 weeks; backup Tyler Huntley is also out for the season (turf toe).
- **Seattle QB**: starter Sam Darnold ruled out; named backup Drew Lock expected to start.
- **Miami QB**: starter Malik Willis placed on IR; Kyle McCord in line for first career start.
- **Green Bay RB**: starter Josh Jacobs finger surgery, return TBD.
- **Rams WR**: Puka Nacua "likely" IR (knee) — reported by NFL.com, not yet official; labelled accordingly.
- **Cleveland / Arizona QBs**: Watson and Beck are the officially named starters.

Depth tiers for every other row are **blank and flagged** (Q-DEPTH): the league report does not publish
string designations, and we do not infer them.

## 6. Strategy system and leaderboard (design + computed metrics)

Six strategies cover singles, same-game parlays and player-prop combos; every strategy must pass gates
G1–G8 before its results count. Luck is removed by: sample floors (100 graded picks), baseline-relative
skill, out-of-time holdouts, multiple-testing correction, bootstrap confidence intervals, and closing-line
grading. The leaderboard scores skill with Brier/log-loss improvement over baseline — **not profit** — and
rewards are non-monetary (Awards page badge, recognition) until the legal question (Q-LEGAL) is answered.
Full rules: [nfl-strategies.html](../nfl-strategies.html).

## 7. What blocks decisions (see [questions.html](../questions.html))

1. **No verified market odds source (Q-ODDS)** — blocks monetary grading, CLV (G5), realistic parlay pricing. Single biggest gap.
2. **Depth tiers unverified (Q-DEPTH)** — blocks systematic 2nd/3rd/4th-string deficiency scoring.
3. **One week of injury history (Q-INJ-HIST)** — the injury signal cannot be correlated with outcomes yet.
4. **Legal/compliance answer (Q-LEGAL)** — needed before the 2027 external competition opens.
5. **HFA ≈ 0 this season (Q-HFA)** — unknown whether it will regress; model keeps using the computed value.

## 8. Sources

- [nfl.com scores 2026](https://www.nfl.com/scores/2026/week-9) … [week-10](https://www.nfl.com/scores/2026/week-10)
- [nfl.com standings 2026](https://www.nfl.com/standings/league/2026/REG)
- [nfl.com Week-10 injury report](https://www.nfl.com/injuries/)
- [nfl.com Week-11 schedule](https://www.nfl.com/schedules/2026/by-week/week-11)
- [Sam Darnold ruled out; Lock to start](https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-week-10-game-vs-raiders-drew-lock-expected-to-start-again)
- [Week-9 top stories: Jackson IR, Willis IR, Nacua, Watson/Beck starters](https://www.nfl.com/news/top-stories-from-week-9-of-the-2026-nfl-season)
- [Ravens lose Tyler Huntley for the season](https://www.nfl.com/news/ravens-qb-tyler-huntley-out-for-season-after-suffering-turf-toe-injury)
- Model code: `scripts/nfl_intel.py` · Page generator: `scripts/build_nfl_intel.py`
