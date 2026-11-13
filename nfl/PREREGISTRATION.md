# NFL Lines Lab — pre-registration (written before any result was computed)

This file is the contract for everything in `nfl/`. It is committed **before** the validation run so that
gates, baselines and scoring rules cannot be chosen after seeing the results. If a later change is needed it
must be appended here with a dated amendment and the reason; no gate may be relaxed retroactively.

## 1. Why this exists

The repository already contains schedules and a *proposal* for an NFL research programme
(`research/NFL-STRATEGY.md`, `nfl-strategy.html`). This lab is the executable half: it computes, from
cited public data, which candidate signals survive pre-registered statistical gates, what the measured
correlations are, and which combinations are supported by those correlations. It originates no fabricated
line: every published number is computed here and every input file is hashed in `nfl/data/provenance.json`.

## 2. Data policy

| Item | Rule |
|---|---|
| Inputs | Only files fetched by `nfl/fetch_data.py` in CI, recorded with URL, HTTP status, byte count and sha256 in `nfl/data/provenance.json`. |
| Nothing typed by hand | No result, score, injury status or odds value is entered manually anywhere in `nfl/`. |
| Market data | ESPN scoreboard `odds` only. It is a **single snapshot** of one provider's line. There is no opening/closing timestamp, no line history, no prop market. Therefore: no closing-line-value claim, no ROI claim, no prop-market edge claim. |
| Missing = missing | A player with no depth-chart row or no injury row is **unknown**, never "healthy" and never "backup". |
| Labels | Every published field carries `verified` (present in a named source), `derived` (computed here from verified fields) or `unknown` (left blank). |

## 3. Definitions (fixed now)

* **Outcome**: home win (1) / home loss (0). Pushes do not exist for moneyline. Games with no final score are dropped.
* **Skill**: improvement in *proper scoring* over a naive baseline. Log loss is the headline; Brier is reported alongside.
  Skill = `1 − model_logloss / baseline_logloss` (positive is better).
* **Naive baseline**: pre-game home win probability = home team's home win rate and away team's away win rate from
  **strictly prior seasons only** (no current-season information). This is deliberately strong in the sense that it
  encodes real home-field advantage, so beating it is not trivial.
* **Walk-forward**: the model for season *S* is fitted only on seasons `< S`. No shuffling, no k-fold across time,
  no target encoding computed from the evaluated season.
* **Luck removal** (the user's requirement, made precise — four independent filters):
  1. **Out-of-sample only.** In-sample fit is never reported as performance.
  2. **Proper scoring.** Accuracy/win-rate is reported but is never a gate, because it rewards luck.
  3. **Deflated skill.** For each strategy family we run `N` label permutations (the outcome vector is shuffled
     within season, destroying any signal but preserving base rates). Let `max_null` be the 95th percentile of the
     best-of-`N` skill obtained on permuted labels. A strategy passes only if `observed_skill > max_null`.
     This is the Bailey–López de Prado deflation logic applied to log-loss skill rather than a Sharpe ratio.
  4. **Minimum evidence.** `≥ 3` evaluated seasons and `≥ 200` games; otherwise the strategy is `insufficient evidence`,
     whatever its score.
* **Correlation**: measured on realised per-leg outcomes (1/0) with Pearson r; 95% CI by bootstrap (2,000 resamples,
  seed 20261113). Reported for every pair with `≥ 200` co-occurring games; below that, blank.
* **Parlay joint probability**: the optimiser never multiplies marginals. It uses the measured correlation matrix and
  a Gaussian copula (latent-normal) over the Bernoulli legs, estimated from the same observed outcomes. A parlay is
  **correlation-aware** only if it contains at least one pair whose CI excludes 0; otherwise it is labelled
  `independence-equivalent` and not promoted on its correlation claim.

## 4. Validation gates (all must pass; a failed gate is published, not hidden)

| Gate | Test | Pass condition |
|---|---|---|
| G1 Provenance | every input in the manifest with sha256 and HTTP 200 | all present |
| G2 No leakage | fitting code reads only seasons `< S`; asserted by a unit test that raises if a future row is visible | test passes |
| G3 Sample size | evaluated games, seasons | `≥ 200` games, `≥ 3` seasons |
| G4 Out-of-sample skill | log-loss vs naive baseline, pooled over evaluated seasons | `skill > 0` |
| G5 Deflation | permutation test (`N=200`) | `observed > 95th pct of best-of-N null` |
| G6 Calibration | reliability slope of predicted vs realised, 10 bins | slope in `[0.8, 1.25]` |
| G7 Stability | sign of skill identical in `≥ 2/3` of evaluated seasons | pass |
| G8 Market honesty | if market odds exist for the evaluated games, report model-vs-market; if not, publish `market=unavailable` | no edge claimed without odds |

Strategies that pass G1–G7 are ranked in Tier A. Strategies passing only G1–G4 are Tier C ("promising, not
distinguishable from luck after deflation"). Everything else is Tier D ("fails a gate") and stays listed with
the failing gate named.

## 5. Scoring for the leaderboard

`score = 100 × clip(skill − max_null_p95, 0) × min(1, games / 1000) × calibration_factor`

This deliberately rewards *surviving deflation* rather than raw win rate, and shrinks small samples. A strategy with
a spectacular record over 40 games scores near zero; that is the intended behaviour.

## 6. What is explicitly NOT claimed

* No profitability, ROI or "beat the book" claim anywhere, because the repo has no line history to measure against.
* No player-prop market price, therefore no prop edge; props are evaluated as *forecast accuracy* only.
* No claim that an injury index identifies the true "next man up" — depth-chart order is cited, not interpreted.
* No claim that any combination is a good bet; the optimiser reports joint probability and correlation, nothing more.

## 7. Amendment log

* *(none yet)*
