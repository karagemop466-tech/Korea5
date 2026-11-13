# NFL Lines & Strategy Lab - executive summary

Season 2026. Snapshot 2026-11-13. Generated 2026-11-13T13:36:05Z.

## State of the programme

- **137 completed games** transcribed from the official NFL.com by-week pages, plus 13 scheduled Week 10 games.
- **32 of 32** standings rows reconcile exactly with the game log on W, L, T, PF and PA.
- **89** out-of-sample predictions scored by chronological walk-forward (Weeks 4-10).
- **No market price of any kind** is held. No official NFL source publishes betting prices, so every market column is blank and flagged.

## What passes and what does not

| Strategy | Result | Verdict |
|---|---|---|
| STR-01 Shrunk adjusted-scoring spread (Model B) | Margin MAE 9.61 vs 10.21 (zero) and 10.33 (constant). Improvement +0.60 pts, t = 2.27, one-sided p = 0.012, bootstrap 90% CI 0.17 to 1.04. Brier 0.235 vs 0.250, p = 0.042. | passed-gate-3 |
| STR-02 Naive adjusted-scoring spread (Model A) | Margin MAE 10.55 - worse than both baselines (10.21 and 10.33). Improvement -0.34 pts, p = 0.68. Total MAE 12.23 vs 10.96 baseline. | failed |
| STR-03 Recalibrated spread (Model C) | Best point estimate (margin MAE 9.52, Brier 0.2244) but the paired improvement has a much wider spread (sd 0.211 vs 0.082); p = 0.125 and the 90% CI includes zero. | failed |
| STR-04 Game totals | Best total MAE 10.91 against a constant baseline of 10.96 - a 0.4% improvement, i.e. no measurable skill in any variant. | failed |
| STR-05 Pythagorean regression fade | Pythagorean expectation correlates 0.879 with actual win percentage across the 32 teams, so the residual (the luck term) is real but small and has not been tested for predictive value. | untested |
| STR-06 Momentum / streak following | Lag-1 autocorrelation of a team's own game margin is r = 0.086 across 274 team-week pairs - effectively zero. There is no momentum signal to harvest. | refuted |
| STR-07 Same-game parlay (side + total) | Home points vs away points r = 0.076; home vs total r = 0.681; away vs total r = 0.782; absolute margin vs total r = -0.016. The total legs share a team's scoring directly, so independence is clearly wrong. | blocked |
| STR-08 Player-prop combinations | No official NFL source publishes prop prices, lines or settlement rules, so no value can be estimated and nothing can be scored. | blocked |

## The one qualifying result

Model B (shrunk adjusted scoring):

- Margin MAE **9.61** against **10.21** for a constant zero forecast and **10.33** for a constant mean forecast.
- Paired improvement **+0.718 points per game**, t = 2.841, one-sided p = 0.0022, bootstrap 90% CI 0.31 to 1.14.
- Brier **0.235** against **0.250** for a constant 0.50 forecaster, p = 0.0418.
- Totals: **no skill**. Best total MAE 10.91 against a constant baseline of 10.96.

## Blockers

- **F01** (Injuries): No official NFL depth chart exists
- **F06** (Markets): No settlement rules are available
- **F07** (Markets): Every market price cell is blank

## Before any decision is made

- **D01** (Market data) - Which market prices will we compare our own lines against?
- **D02** (Market data) - What is the vig, and how do we remove it?
- **D05** (Model validity) - Is Model B's edge real, or is it a small-sample artefact?
- **D07** (Injuries) - How do we know who replaces an injured starter?
- **D08** (Injuries) - Do we have the injury report as a time series, or only as a snapshot?
- **D09** (Injuries) - Does 'Questionable' or 'Out' actually change a team's scoring?
- **D10** (Parlays) - How do we price a parlay correctly?
- **D11** (Competition) - Can the leaderboard offer rewards?
- **D14** (Rules) - Which settlement rules apply to the markets we would price?
