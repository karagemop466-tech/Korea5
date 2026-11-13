# NFL Signals Lab — executive summary (build of 2026-11-13)

Pages: [`nfl-signals.html`](../nfl-signals.html) ·
[requirements](../nfl-signals-requirements.html) ·
[data pipeline](../nfl-signals-data.html) ·
[availability](../nfl-signals-injuries.html) ·
[backtest](../nfl-signals-backtest.html) ·
[lines](../nfl-signals-lines.html) ·
[review board](../nfl-signals-suggestions.html)

## What was built

A working, reproducible NFL signal pipeline where none existed. Before this build the repository had
321 schedule rows with **no scores at all**, so nothing could be backtested. Now:

1. **Official-source capture in CI.** `tools/fetch_nfl_lab.py` (stdlib only) reads nfl.com's by-week
   schedule pages, the standings payload, the 32 per-club injury tables, and official news/inactives
   articles. It writes `official/lab/*.json` with a source URL and a capture timestamp on every row.
   Current capture: **291 games, 132 with official FINAL scores, 296 injury players across 32 club tables, 281 article rows from 10 pages, 32 standings rows.**
2. **A scoring engine with no leakage.** `scripts/signal_lab.py` forecasts each week from strictly
   earlier weeks, re-fitting team ratings, the margin spread and the rating-shrink factor inside each
   window. Four strategies are scored against two naive baselines on out-of-sample log loss, Brier and
   calibration error, with paired differences and moving-block bootstrap intervals.
3. **Availability as a measured input, not a story.** Injury rows become a per-club deficit (position
   weight × status credit) that shifts the expected margin; the weights are re-scaled ×0.5 and ×2.0 in
   a published sensitivity run.
4. **Dependence, measured.** Same-game parlay legs are compared to independence from the actual 2×2
   (φ = -0.22 on 101 rows, joint 22.8% *below* independence), and slate-day home-win clustering is
   reported as an observed-over-independent variance ratio. Player-prop combinations are specified but
   left uncomputed, because there is no player-level or price data here.
5. **A prospective ledger that starts today.** `data/nfl-signals/forward-ledger.json` freezes the
   model's lines before the result exists, appends only unseen games, settles rows when the official
   page reports a score, and voids (never deletes) a mis-logged row. 41 rows, 0 settled.

## What the numbers say

| | |
|---|---|
| Best out-of-sample record | **S2-netpoints**, log loss 0.6681 over 100 games |
| Home-field baseline | 0.6979 |
| Opponent-adjusted ratings | 0.7201 |
| Ratings + availability | 0.7202 |
| Is the leader real? | t = 1.48, 95% bootstrap interval [-0.005, 0.073] straddles zero → **not distinguishable from luck**; ≈182 paired games needed at this effect size |

**The headline is negative and useful:** the sophisticated models lose to a naive net-points model on
this sample, and the injury adjustment changes log loss by about a thousandth of a nat. That is what
100 games of official data supports — no more, and no less.

**Nothing on the site claims edge, ROI or closing-line value.** The repository holds no market prices,
so the lines page publishes model lines only, each labelled as such, and the parlay work prices a combo
off the measured joint rather than off multiplied prices.

## What would change the answer

| Need | Why it is the binding constraint | Unblocks |
|---|---|---|
| Several more weeks of settled forward ledger | 100 games cannot separate 0.6681 from 0.6979 | a leaderboard anyone should act on |
| Dated weekly availability archives | today's injury page is a snapshot, so the availability strategy fails its own leakage gate | an honest injury number (currently the single largest self-inflicted caveat) |
| Licensed timestamped odds / prop prices | no price ⇒ no edge, ROI, CLV, and no real parlay price | pricing claims, and S5 as a scoreable strategy |
| Player-level snap data | props and replacements are unforecastable without it | S6, replacement quality |

## Decisions taken (see the [review board](../nfl-signals-suggestions.html))

Ranking on proper scoring rules rather than hit rate; a failing gate left failing instead of being
reworded; missing scores left null rather than back-filled from a neighbouring card; no payout while
the sample is under the pre-registered minimum; no depth-chart tier asserted, because
`nfl.com/depth-charts/` returns 404 and the alternative was guessing.

## Reproduce

```
gh workflow run nfl-lab.yml        # capture (the sandbox has no outbound HTTP)
python3 scripts/signal_lab.py      # scores, gates, lines, forward ledger
python3 scripts/build_signals.py   # pages
python3 -m unittest discover tests -v
python3 scripts/check_links.py
```
