# NFL Signals Lab — method review and open decisions

Written as the adversarial read of the build described in
[`NFL-SIGNALS-EXEC-SUMMARY.md`](NFL-SIGNALS-EXEC-SUMMARY.md). Its purpose is to say what a reader
should not conclude, and to list the decisions that need an owner rather than another commit.

Written against model signal-lab-1.1.0, capture 2026-11-13. The pages render the latest committed run; the figures quoted here are that run's.

## What is solid

| Claim | Why it can be trusted |
|---|---|
| The scores are the league's own | A score is bound only to its own `/games/<slug>` link, and only when both club nicknames in the label agree with the row. 132/137 played games carry `scoreSource: pageScoreLink`; `scoreLabelMismatches` is empty and would be printed if not. |
| No week sees its own result | `evaluate()` builds each week's rates, spread and shrink factor from `week < w` rows only; `tests/test_signal_lab.py` flips weeks 7–8 outcomes and asserts earlier probabilities do not move. |
| The sample is too small, and says so | Paired log-loss differences, a week-block bootstrap, and the total n needed to clear two standard errors are published on the backtest page; the verdict string is computed, not typed. |
| The ranking is not a knife-edge artifact of one constant | Three defensible shrink policies and ×0.5/×2.0 deficit-weight scaling are each run end to end; the naive leader stays first under all of them. |
| Ties and gaps are handled by subtraction, not imagination | Ties get `logLoss: null` and are excluded from the mean; five unlabelled games and 32 point-less standings rows are counted in the report and left null in the data. |

## What a reader must not conclude

1. **Not** that net-points is a good betting model. It is the *least wrong* probability set on 100
   games, and its 0.6681 log loss is only marginally under the 0.6931 a coin flip scores. That it beats
   richer models is evidence the richer models are over-parameterised for this sample, not evidence
   the naive one generalises.
2. **Not** that injuries do not matter. The availability adjustment changes log loss by ~0.001, but it
   is applied from a *today* snapshot to *past* weeks — its own gate is failed for exactly that
   reason, so the null result is uninformative. The signal may well exist; this design cannot see it.
3. **Not** that the parlay φ (−0.22) is a market fact. Both legs come from the same model on the same
   game; it measures the model's internal dependence, which is the right thing to know before someone
   multiplies prices, and the wrong thing to present as bettor-relevant correlation.
4. **Not** that the forward ledger has any evidence in it yet. 41 rows logged, 0 settled, 1 voided
   under the "past-dated row is voided, never deleted" rule.
5. **Not** that 291 games were *won* by the model's teams in the standings sense — `gamesOnPage` counts
   scheduled fixtures; only 132 have results at all.

## Method critiques worth acting on

- **Shrink selection on 15 validation games is noise.** The published λ moves between 0.2 and 1.0
  depending on which two weeks are the most recent. Fix: select λ once per month of games (or
  isotonic-recalibrate) and log the choice as an *event* in the forward ledger, so the choice itself
  becomes out-of-sample.
- **Availability deficits are linear by construction.** Weight × count has no interaction (two
  backups out ≠ one starter out) and no fatigue/return-from-IR dimension. Acceptable while the sample
  is small, but it must not be described as a "player-value" model.
- **One season, one rule era.** 2026 rule changes (6-1-3, 6-1-5, 6-1-6, 19-2) mean special-teams and
  roster features cannot be pooled with prior years; any cross-season model needs a rule-era split,
  and the capture carries no pre-2026 data to build one on.
- **Sigma is a global constant per window.** A 11.3-point margin spread applies equally to a
  blowout-prone and a low-scoring matchup; per-matchup variance (weather, pace, venue) is the obvious
  upgrade, and none of it is capturable from the pages used here.
- **`injuriesWithoutTeam` is 0/296 only because club identity comes from the table's own link.** If the
  page changes its table markup, the join silently degrades; the count is exposed in
  `fetch-report.json` for exactly that reason and should be a CI alarm, not a human habit.

## Decisions an owner has to make (blocking, not technical)

| # | Question | Default if nobody answers |
|---|---|---|
| D1 | Does the lab run weekly on a schedule, so the ledger settles without being asked? | Stays manual; the ledger grows only when dispatched (SG-06). |
| D2 | Is a licensed odds/prop price feed in scope for this repository at all? | No pricing claims, ever, and S5/S6 stay unscored. |
| D3 | Are `official/lab/*.json` captures a permanent, committed dataset, or a scratch cache? | Committed (they are the only reproducible history the engine has). |
| D4 | Who may promote a strategy once 60 rows settle, and against which metric — log loss or calibration error? | No promotion; `rewards: none authorised`. |
| D5 | Should voided ledger rows be excluded from *all* published rates (they currently are), and should the void rule be widened to any row logged after kick-off? | Current narrow rule. |

## Flags raised by this build

F52 no market prices ⇒ no edge/ROI/CLV · F53 availability is a snapshot, leakage gate failed on purpose ·
F54 five 2026 games unlabelled · F55 no official depth chart · F56 sample cannot separate models from
luck · F57 standings carry no points · F58 inactives only via articles · F59 prop combos uncomputed.
See [`curated/flags.json`](../curated/flags.json) and the site's
[Flagged for review](../flagged.html) page.

## Reproduction and verification actually performed

```
python3 scripts/signal_lab.py            # games=272 played=132 sigma=12.0 hfa=-0.515 lines=40
python3 scripts/build_signals.py         # 7 pages
python3 -m unittest discover tests -v    # maths + leakage + artefact-consistency tests
python3 scripts/check_links.py           # every local link resolves; every page reachable
python3 tools/verify_extra.py            # site-wide verification
```
