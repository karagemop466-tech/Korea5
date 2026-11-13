# Week 10, 2026 — line-by-line verification record (NFL analytics suite)

Session: `arena-65332583` · snapshot date **2026-11-13** · every claim below names the official page it was checked against.

## Sources fetched (raw snapshots in `research/nfl-analytics-raw/`, sha256 in `fetch-report.json`)

| Source | URL | What it provided | Trust level |
|---|---|---|---|
| NFL.com official injury report | https://www.nfl.com/injuries/ | 296 player rows across 26 team tables, 14 game blocks (Week 10), records, kickoffs, networks | Official league |
| NFL.com league standings | https://www.nfl.com/standings/league/2026/REG | 32 teams: W-L-T, PF, PA, net, splits, streak | Official league |
| NFL.com schedules by-week | https://www.nfl.com/schedules/2026/by-week/week-N (N=1..10) | 137 finals with per-game official URLs | Official league |
| Club depth charts (30 clubs) | each club's official site (row links in `depth-charts-2026.json`) | 869 position rows with 1st–5th strings | Club-official (clubs label them "unofficial depth chart compiled by … Football Communications") |
| ESPN scoreboard API | https://www.espn.com/nfl/odds | DraftKings spread/total/ML blocks for 13 of 14 games | Trusted secondary (NFL official partner) — NOT official league data |

## Cross-checks performed

1. **Slate integrity** — the 14 games parsed from the injury page match the independently stored NFL.com schedule
   (`data/upstream/nfl-2026.json`, fetched 2026-11-02 by session `ef8b5b30`) **14/14**, including TV windows **14/14**.
2. **Results integrity** — Week 9 finals parsed from `schedules/2026/by-week/week-9` match the page's own game cards
   (e.g., "Jaguars 33, Ravens 10, FINAL" → `jaguars-at-ravens-2026-reg-9`) with the game URL on every row.
3. **Standings vs game pages** — PIT points-for 180 over 8 games = 22.5 PPG, matching the PPG printed on the official
   `steelers-at-bengals-2026-reg-10` game page; CIN 240/8 = 30.0, also matching.
4. **Depth charts** — DET rows parsed from the raw snapshot were compared cell-by-cell against a rendered fetch of
   https://www.detroitlions.com/team/depth-chart/ (spot check: C = Cade Mays / Juice Scruggs, CB1 = D.J. Reed /
   Rock Ya-Sin, QB = Jared Goff / Joshua Dobbs) — all match.
5. **Records** — team records on the injury page match the standings (e.g., WAS 3-5-1, BUF 7-1, LAC 0-8).
6. **Model input isolation** — the Week-10 TNF result is excluded from the ratings fit; WAS @ NYG is graded
   out-of-sample (result: side loss, 5.2-pt margin error — reported on lines.html and flagged F42).

## What is verified row by row

* Every injury row (296) carries `sourceUrl = https://www.nfl.com/injuries/` and the player profile URL.
* Every depth row (869) carries its club's depth-chart URL.
* Every standings row (32) carries `https://www.nfl.com/standings/league/2026/REG`.
* Every result row (137) carries its official NFL.com game-page URL.
* Every market row carries its ESPN game-page URL and is labelled trusted-secondary.
* Model outputs are labelled `MODEL OUTPUT` on every published table; parameters are published as parameters.

## Irregularities (published on Flagged for Review, F33–F42)

| ID | Issue | Handling |
|---|---|---|
| F33 | Texans publish their depth chart as an image | HOU replacement strings blank + flagged; image linked for manual review |
| F34 | Panthers depth page refused CI connections (×2) and 500s on direct fetch | CAR rows blank + flagged; no substitute source used |
| F35 | Market odds are DraftKings via ESPN, not official league data | labelled trusted-secondary everywhere |
| F36 | Fitted HFA = −0.5 vs traditional ≈2.5 | published + flagged for reviewer decision |
| F37 | Totals not injury-adjusted in v0 | documented limitation on lines.html |
| F38 | DET S Kerby Joseph (Out) absent from the club's depth chart | replacement blank + flagged |
| F39 | Sunday/Monday game statuses not yet designated at retrieval | blank cells left blank; re-pull proposed (S2/S7) |
| F40 | No verifiable player-prop market | prop strategies registered but blocked (Q5) |
| F41 | Correlation values are literature estimates, not computed | flagged; estimator + rho floor published |
| F42 | Model v0 first test was a side loss (WAS @ NYG) | reported straight; gate G4 requires n ≥ 100 |

## Not verified / deliberately left blank

* Player prop markets (books do not publish on official domains).
* Snap counts / route participation (no official table found).
* Stadium dome/open classification and forecasts (no official data table).
* CAR and HOU depth strings (see F33/F34).
* 2027+ seasons (out of scope for this suite's Week-10 snapshot).
