# NFL lines & strategy lab — executive summary

**Session** `arena-6b0481c7-korea5` · built 2026-11-13 · branch `arena/6b0481c7-korea5`
**Live section** `nfl-lines/index.html` (linked from every page of the existing planner site)
**Rebuild** `python3 scripts/nfl_lines/stage1_official.py` … `stage8_site.py`, then `verify.py`

---

## 1. The one-paragraph answer

You can originate your own NFL lines with what is publicly reachable, and this build does it: it publishes a
model fair spread, fair total, fair moneyline and break-even price for every 2026 Week 11 game that has a market
number. But the honest headline is that **the market is better than the model**: on 7,413 graded games the
model's mean absolute error on the home margin is 10.52 points against 10.48 for the closing number, and its
Brier signal is 0.101 against the market's 0.143. Across eight backtested strategies on 300–4,000 bets each,
**none demonstrated skill rather than luck** — every 95% interval includes zero, and no p-value survives
correction across the eight hypotheses tested. Player props and same-game parlays are **blocked**, not tested,
because no prop prices exist anywhere in the reachable archive. Injury and backup-tier effects measured on 414
club-weeks **are indistinguishable from zero**, which is itself the most decision-relevant number on the site.

---

## 2. What was built

| Area | Deliverable | Where |
|---|---|---|
| Line origination | Week 11 fair spread / total / moneyline / break-even price per game, with the fitted constants printed | `nfl-lines/lines.html` |
| Strategy competition | 10 strategies declared, 8 tested, 8-gate validation, evidence-weighted leaderboard | `nfl-lines/leaderboard.html` |
| Backtest evidence | Walk-forward 1999–2026, per-season splits, calibration, no-model benchmarks | `nfl-lines/backtest.html` |
| Correlation engine | Same-game and same-team player dependence, measured φ with intervals | `nfl-lines/correlation.html` |
| Injury + tier tracker | 65 official 2026 Week 10 rows, computed tiers, measured 2025 impact | `nfl-lines/injuries.html` |
| Decision support | 24 questions (known / unknown / missing / what it would change) | `nfl-lines/questions.html` |
| Suggestions board | 12 scored proposals with the decision you have to make | `nfl-lines/suggestions.html` |
| Provenance | 13 registered datasets, 3 rejected sources, line-by-line official validation | `nfl-lines/sources.html` |
| Irregularities | 32 flagged items with sources and severity | `nfl-lines/flagged.html` |
| Method | Definitions, the eight gates, and the correction described in §6 | `nfl-lines/method.html` |

---

## 3. The numbers that matter

### 3.1 Model versus market (the fundamental result)

| Scored on the same games | Signal (1 − Brier/base) | Brier | Log loss | Games |
|---|---|---|---|---|
| Ratings model (Elo) | 0.101 | 0.2213 | 0.6326 | 7,413 |
| De-vigged closing market (NOT OFFICIAL) | **0.143** | **0.2115** | **0.6105** | 5,432 |

The market's advantage is 0.042 of signal. Any strategy that claims to beat the closing number has to
overcome that gap first, and none of the strategies here do.

### 3.2 Leaderboard

| Strategy | Bets | ROI | 95% interval | p vs market | p corrected (m=8) | Gates |
|---|---|---|---|---|---|---|
| Dome/closed-roof over | 1,436 | +0.4% | −2.7% … +4.0% | 0.103 | 0.824 | 5/8 |
| Own fair total (scoring rates) | 4,044 | −1.5% | −3.5% … +0.5% | 0.199 | 1.000 | 5/8 |
| Division-game under | 1,888 | +1.2% | −3.6% … +5.8% | 0.036 | 0.289 | 6/8 |
| Elo spread value | 3,690 | −2.7% | −4.9% … −0.5% | 0.502 | 1.000 | 5/8 |
| Elo moneyline value | 4,424 | −2.2% | −6.5% … +2.0% | 0.391 | 1.000 | 5/8 |
| Rest-advantage fade | 549 | −4.3% | −13.4% … +4.5% | 0.657 | 1.000 | 5/8 |
| Three-leg parlay | 384 | +10.0% | −30.9% … +57.3% | 0.218 | 1.000 | 5/8 |
| Two-leg parlay | 403 | −9.0% | −33.5% … +19.3% | 0.607 | 1.000 | 5/8 |
| Player-prop combo | — | **blocked** | — | — | — | 3/8 |
| Injury-adjusted spread | — | **blocked** | — | — | — | 3/8 |

**Reward-eligible strategies: 0.** Gate 7 (a frozen prospective trial with predictions logged before outcomes)
has not been run for any strategy, and gate 8 (human release review) cannot be self-certified. So nothing earns
a reward no matter how good a backtest looks. Gate 7 is deliberately hard-coded to fail until a trial exists.

### 3.3 Line origination constants (so the numbers are reproducible)

`fair_home_margin = 0.34 + 31.71 × (elo_home_probability − 0.5)`, fitted on 7,413 graded games.
League mean total = 44.29 points; team scoring rates shrunk with a 6-game prior.

**Gap to the market = fair home handicap − market home handicap.** The archive's `spread_line` *is* the home
handicap (positive = home favoured), proven on all 7,413 graded rows: regressing the actual home margin on it
gives slope **1.045**, intercept −0.04, and the home club covers `(margin − line) > 0` on **47.6%** of games.
The mirrored form covers 59.2%, which is the tell that it is wrong. Corrected Week 11 gaps run from 0.3 to 4.2
points, against a model whose own margin error is 10.5 points, so **no Week 11 game carries a gap worth acting
on**.

### 3.4 Correlation, measured

| Pair | n | φ | Joint observed | If independent | Verdict |
|---|---|---|---|---|---|
| Home covers × total over | 7,109 | +0.014 | 0.2456 | 0.2420 | effectively independent |
| Home wins × total over | 5,220 | +0.005 | 0.2762 | 0.2750 | effectively independent |
| QB passing yards × his WR1 receiving yards | 307 | **+0.293** | 0.2606 | 0.1895 | **strong positive** |
| RB1 rushing × RB2 rushing (same club) | 311 | +0.067 | 0.2444 | 0.2278 | weakly positive |
| WR1 receiving × WR2 receiving | 321 | +0.003 | 0.1682 | 0.1675 | independent |
| QB passing × opposing WR1 receiving | 307 | −0.042 | 0.2215 | 0.2320 | not supported |

The practical consequence: same-game **market** combos are close to independent, but **player** combos on the
same club are not — a quarterback and his WR1 hit together roughly 26% of the time where independent pricing
would say 19%. That is the single most valuable correlation number in this build.

### 3.5 Injuries and backup tiers

| Absence | Metric | With | Without | Difference | 95% interval |
|---|---|---|---|---|---|
| Tier-1 offensive player out | own points scored | 22.01 (88 club-weeks) | 22.98 (326) | −0.97 | −3.22 … +1.38 |
| Tier-1 defensive player out | points allowed | 23.42 (81 club-weeks) | 22.62 (333) | +0.80 | −1.58 … +3.14 |

Both intervals include zero. Position-by-position results are the same story; the quarterback-only estimate
(−4.99 points over 18 club-weeks) is the largest but has too small a sample to interval and is given no
betting role. **On this evidence, a backup replacing a starter does not measurably move the score.**

---

## 4. Questions that block a decision

24 questions are logged with what is known, what is unknown, the missing information, what the answer would
change, and the exact discovery step. The three that gate everything:

1. **Is the model better than the market?** No (see §3.1). Until it is, a published fair line is a benchmark,
   not an alternative to the price.
2. **Is there a legal, timestamped price archive?** No. Without one, props and same-game parlays can never be
   scored, and no parlay price is a real book price.
3. **Is official depth order obtainable?** Not from here — `nfl.com/teams/<club>/depth-chart` returns 404.
   Tiers are therefore computed from production and labelled as computed everywhere.

Full register: `nfl-lines/questions.html`.

---

## 5. Suggestions, ranked for review

| # | Suggestion | Decision required | Recommendation | Status |
|---|---|---|---|---|
| SG04 | Score strategies on the interval lower bound, not ROI | Confirm scoring policy | Adopt — free, reversible, already default | done |
| SG05 | Freeze a prospective paper trial | Pick horizon | Freeze the own-fair-total strategy for the rest of 2026 | proposed |
| SG01 | Pre-market or post-market lines? | Choose the purpose | Start post-market (today), add a frozen T-24h snapshot later | proposed |
| SG02 | Licence a timestamped prop/SGP price archive | Approve spend or accept props stay blocked | Do not build prop models before the price history exists | blocked pending |
| SG03 | Recover an official depth-chart feed | Computed tiers or a real source | Keep computed tiers; probe from CI where the 404 may not reproduce | proposed |
| SG06 | Extend the injury tracker to the whole week | Approve the build | Parse the official page instead of transcribing | proposed |
| SG07 | Add snap counts and participation data | Approve the source | Do it before any injury-adjusted line is published | blocked pending |
| SG10 | Monthly re-verification job | Approve CI cadence | Run the validator monthly, fail loudly on mismatch | proposed |
| SG11 | Publish the licence status of the price archive | Decide if price-derived figures may be public | Ask in writing; keep NOT OFFICIAL labels until answered | proposed |

Full board: `nfl-lines/suggestions.html`.

---

## 6. Corrections made during this build

1. **Luck test was wrong.** A pooled break-even win-rate test was used first. With mixed prices a win-count
   test and a profit test disagree, so it could claim significance the money does not support. Replaced with a
   per-bet null using the de-vigged market probability of the side taken and 10,000 seeded simulations. The
   three-leg parlay moved from p = 0.0005 to **p = 0.218**. The old figure was withdrawn, not hidden; both are
   on the Method page.
2. **A sign error in the Week 11 card, found and fixed after it was published to this branch.** The first build
   computed the model-versus-market gap as `fair_margin + spread_line` and printed gaps of 18.6 and 29.6 points.
   The archive's `spread_line` *is* the home handicap, so the gap is a subtraction. Corrected gaps run 0.3–4.2
   points. The convention is now **tested in the pipeline** (slope 1.045, correct cover rate 47.6% against a
   mirrored 59.2%) and asserted by verifier check **V13**, which re-derives every published gap from its two
   inputs — I confirmed V13 fails when the old formula is restored. The backtest engine already subtracted the
   line, so the leaderboard, ROI figures and luck tests are unaffected; only the Week 11 origination card was
   wrong. This is the second wrong number found in this build and it is recorded rather than quietly replaced.
3. **Fair total rebuilt.** An initial shrink-toward-even market fade produced zero bets; it was replaced with a
   point-in-time scoring-rate model that produces 4,044 graded bets.
4. **Club alias made explicit.** The official standings page prints `AZ` where the archive uses `ARI`. An
   explicit alias map is applied so a rename can never silently hide a disagreement. With it, 32/32 clubs match.

---

## 7. Flagged irregularities (see `nfl-lines/flagged.html` for all 31)

**High severity**

- **F01** Betting prices are not official values; the NFL publishes none. No official verification is possible.
- **F02** The `nfldata` repository has no licence file at the commit used, and derived figures are published.
- **F03** GitHub release binaries are unreachable from this environment; a third-party mirror was used for the
  2025 player and injury files and is labelled MIRROR.
- **F04** Official depth-chart pages return 404, so tiers are computed, not official.
- **F08** No player-prop prices exist → prop and parlay strategies are declared but blocked.
- **F09** Parlays are priced at the product of leg decimals — an upper bound, not a book's correlated price.
- **F11** The model loses to the closing market.
- **F13** Prices carry no capture timestamp; open/close is unknown.
- **F14** Zero strategies qualified.
- **F15** The three-leg parlay's apparent significance was an artefact of the wrong test.
- **F19** All 13 Week 11 rows are WATCH, none PLAY, and a WATCH row is at least as likely to be the model's
  error as the market's.
- **F30** The rejected statistical test, documented rather than deleted.

**Medium**: blank game-status cells on the official injury page (F05), three-game injury coverage (F06), null
injury effects (F07), proxy prop lines (F10), no weather/rest/injury inputs (F12), no prices past Week 18
(F16), 2026 player totals checked only against the official page, not the archive (F21), five-column injury
mirror (F22), one-season correlation samples (F24), fair totals ignore weather (F27), Week 11 prices may move
(F28), concurrent sessions (F29).

---

## 8. Verification performed

| Check | Result |
|---|---|
| 2026 standings, club by club, archive vs `nfl.com/standings` | **32/32 match** (W-L-T, points for, points against) |
| Super Bowl LIX and LX results vs official game pages | **2/2 match** |
| Internal arithmetic (result = home − away, total = home + away), duplicate ids | **0 errors** across 7,548 games |
| Lab structural checks (`scripts/nfl_lines/verify.py`) | **14/14 pass** — local links, allow-listed external domains, registry files, JSON parse, no template artefacts, honesty labels, no reward eligibility, intervals published, no PLAY label, register completeness, nav both ways, V13 which re-derives every Week 11 spread gap from its inputs, and V14 which fails any page that promises a value the data deliberately withholds |
| Existing repository checks | `check_links.py` 12 pages / 202 local links / 0 missing; `verify_extra.py` 31/31; `audit_certainty.py` passed; 5/5 unit tests; calendar Node tests passed |
| Live page fetch | All 11 lab pages returned HTTP 200 from a local server |

**Not verified, and stated as such:** every market price (no official source exists), the 2026 player-level
archive (not reachable), every depth-chart tier (source returns 404), every prop line (does not exist), and the
remaining Week 10 injury games (not transcribed).

---

## 9. What would change the conclusion

1. A **timestamped prop and SGP price archive** — unlocks the two families the owner asked for, and is the only
   way to price combos honestly.
2. **Snap counts and participation** — the only way to measure what a backup actually did rather than infer it.
3. **A real injury signal.** Today's measured effect is zero. Either a better severity measure (practice
   participation, snap share lost) or an acceptance that injury adjustment is not a source of edge here.
4. **A frozen prospective trial.** The competition cannot produce a winner without it, and it costs nothing but
   discipline to start.

---

## 10. Honesty statement

Every market price on the site is labelled **NOT OFFICIAL**; the NFL publishes no betting prices. Every model
value is labelled **MODEL**. Every official value links the exact page it came from. Every value that could not
be confirmed is **blank** and appears on the Flagged page. No strategy is reward-eligible. No row on the Week 11
card is labelled PLAY. The site does not recommend a wager, and the research is a decision-support instrument.
