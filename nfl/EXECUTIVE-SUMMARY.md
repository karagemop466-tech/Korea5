# NFL Lines Lab — executive summary

**Repository:** `karagemop466-tech/Korea5` · **Section:** `nfl-lines/` · **Branch:** `arena/02f4d067-korea5`
**Generated:** 2026-11-13 · **Every figure below is computed by `nfl/model.py` and written to
`nfl/data/model_results.json`; nothing in this document is transcribed from memory or from another site.**

Live page: <https://karagemop466-tech.github.io/Korea5/nfl-lines/index.html>

---

## 1. What was asked, and what exists now

The request had five parts. Each is answered by something that runs, not by a proposal.

| Asked for | Delivered | Where |
|---|---|---|
| Improve decision making; a reviewable section of suggestions | 10 numbered suggestions, each with a test and a cost, plus a suggested reading order for a decision | `nfl-lines/suggestions.html` |
| A clear list of questions, information and answers needed before a decision | 12 numbered decision blockers: what is known, what is missing, why it matters, how to get it, who owns it, what it blocks | `nfl-lines/questions.html` |
| Suggest ways to discover missing information | Coverage counting, null-and-flag, two-publisher cross-check, and a six-item gap register with the exact acquisition step for each | `nfl-lines/questions.html`, `nfl-lines/data.html` |
| Originate lines; research signals; leaderboard; singles, parlays, prop combos; validation gates; correlations; luck removal; skill-based selection | A walk-forward model with pre-registered gates, best-of-K permutation deflation, measured correlation matrix with bootstrap intervals, a correlation-aware copula pricer, and a tiered leaderboard | `nfl-lines/lines.html`, `signals.html`, `leaderboard.html`, `parlays.html` |
| Track injuries and know when 2nd/3rd/4th-string players replace starters, on offense and defense | Official report status separated from depth-chart tiering, per unit (offense / defense), with the snapshot date published on every row | `nfl-lines/injuries.html` |

## 2. The headline results (computed, with gates)

* **Out-of-sample record:** 1,632 games across evaluated seasons 2017–2022, walk-forward: the model for
  each season is fitted only on earlier seasons.
* **Skill vs a naive baseline:** log loss **0.6382** against a prior-season win-rate baseline of **0.6885**,
  i.e. **7.30% skill**. Winner accuracy is **63.5%** — reported, but deliberately *not* used as a gate,
  because accuracy is the metric that most rewards luck.
* **Luck filter (deflation):** 200 shuffled-label refits. The best-of-9 permutation null has a 95th
  percentile of **1.52%** skill; the model's 7.30% clears it. **Verdict: passes deflation.**
* **The honest negative:** the *context* family (rest, division, roof, quarterback change, injury shares)
  scored only **0.53%** skill and **failed** deflation — its null threshold was 5.34%. Almost all of the
  skill comes from team strength (chronological Elo plus recent form), not from the situational angles
  most betting discussion focuses on.
* **Correlation:** 55 signal pairs measured; 11 have a bootstrap interval that excludes zero. The largest
  real relationship is between the two "short week" flags (r = 1.00 — they are the same information twice),
  then offense-vs-defense starter value (r = 0.21) and dome-vs-defense value (r = 0.21).
* **Cross-source verification:** **2,086 of 2,776** completed games match ESPN exactly, with **0
  disagreements**; the remainder are unmatched joins, reported rather than hidden.

## 3. What is *not* claimed, and why

This is the most important section, because the fastest way to produce an attractive NFL dashboard is to
claim an edge the data cannot support.

1. **No profit, ROI or closing-line-value claim.** The only market data available is one spread/total
   snapshot per game with no timestamp, and the moneyline columns are empty. A return cannot be computed
   from a price whose timing is unknown. This is gap **GAP-1**.
2. **No player-prop edge.** No prop price exists in any reachable source. Props are scored as *forecast
   accuracy* against a published league base rate, and every prop row is Tier C at best by construction.
   This is gap **GAP-2**.
3. **No claim that the injury index measures talent.** It weights players by snap share, which is usage,
   not ability. A high-usage, low-impact player lost moves the index more than he should. Question **Q6**.
4. **No claim that a Questionable player will miss the game.** The injury report is a pre-game
   designation; the inactive list at kickoff is not in the dataset. Question **Q5**.
5. **No claim that any parlay is a good bet.** The lab publishes a *joint probability*, computed with a
   copula over a measured correlation matrix. Without a payout it cannot become an expected value.

## 4. The competition and the rewards

Ranking is `deflated skill × sample-size shrink × calibration factor`. A strategy that wins 60% of 40 games
scores near zero, which is the intended behaviour. Tiers:

* **Tier A** — passes sample size, positive out-of-sample skill, best-of-K deflation, calibration slope in
  [0.8, 1.25], and sign stability across seasons.
* **Tier C** — positive skill but not yet distinguishable from luck, or no market to price against.
* **Tier D** — fails a gate; retained in the audit history with the failing gate named.

Rewards are **Lab Points and research priority only**. No money and no prize of monetary value is offered,
because paying out on betting performance is a regulated activity that this repository is not positioned to
satisfy. That decision is recorded as **Q4**, not assumed.

## 5. Injury and lineup tracking, stated precisely

Three separate facts are kept separate on the page and never multiplied into one unexplained score:

| Column | Status | Source |
|---|---|---|
| Out / Doubtful / Questionable count | **verified** — copied from the official weekly report | nflverse `injuries_<season>.csv`, built from the NFL report; official reference <https://www.nfl.com/injuries/> |
| Snap-weighted share of listed starters still listed first | **derived** — snap share × depth rank | nflverse depth charts + snap counts |
| Who is 1st / 2nd / 3rd / 4th string, per position | **published** — with the depth-chart snapshot date on every row | nflverse depth charts |

A missing depth row is **unknown**, never "backup". A missing report row is **unknown**, never "healthy".

## 6. Six gaps that block the next stage

| Gap | Blocks | What closes it |
|---|---|---|
| GAP-1 Timestamped odds history | ROI, vig, closing-line value, any betting claim | A licensed odds feed, or an archived pre-kickoff screenshot with a timestamp |
| GAP-2 Prop prices and settlement rules | Prop-combo pricing, correlated-prop payout | A prop market feed with timestamps |
| GAP-3 Game-day inactive list | Verified "who actually started" | ESPN summary endpoint per game (reachable from CI) |
| GAP-4 Player talent weighting | Precision of the lineup index | Per-player EPA from play-by-play, blended with snap share |
| GAP-5 Referee/weather subgroup size | Officiating and weather families | Minimum-subgroup gate; data already fetched |
| GAP-6 Exploitable injury timestamps | A strict pre-kickoff cutoff for older seasons | `date_modified` where present; labelled fallback otherwise |

## 7. What I would do first

1. **Start capturing timestamped market snapshots** (S3). This is the single change that turns a research
   model into a line-making system, and it cannot be recovered retroactively.
2. **Add the inactive list** (S4) so the lineup index becomes a fact rather than a proxy.
3. **Run the locked prospective paper trial** (S8) before spending anything on rewards.
4. **Tighten the statistics before adding strategies** (S2, S7). More strategies tested on the same data is
   how a lab manufactures a winner.

## 8. Verification performed for this summary

| Check | Result |
|---|---|
| Unit tests, including a leakage test and a "pure noise must fail deflation" test | 9 / 9 pass |
| Pre-registration committed before results | `nfl/PREREGISTRATION.md` (plus one dated amendment for the optimiser swap) |
| Every input hashed | `nfl/data/provenance.json` — 352 files HTTP 200, 3 unavailable, recorded |
| Cross-source score check | 2,086 exact matches, 0 disagreements, unmatched rows counted |
| Link check of the generated section | `scripts/check_links.py` covers `nfl-lines/` |
| Certainty banner on every page | `scripts/audit_certainty.py` injects the lab's own disclosure |

## 9. Reproducing it

```bash
python3 nfl/fetch_data.py --seasons 2016 ... 2026 --with-espn   # CI only: needs the open internet
python3 nfl/model.py --perm 200                                  # writes nfl/data/model_results.json
python3 nfl/analyze.py                                           # audit, hypotheses, questions
python3 nfl/leaderboard.py                                       # tiers, points
python3 nfl/build_site.py                                        # renders nfl-lines/*.html
python3 -m unittest discover -s nfl/tests -v                     # gates as tests
```

The authoring sandbox cannot reach the sports hosts, so the pipeline runs in
`.github/workflows/nfl-model.yml` and commits its derived JSON back to the branch. That is the same pattern
the repository already used for its MLB and NFL schedule feeds.
