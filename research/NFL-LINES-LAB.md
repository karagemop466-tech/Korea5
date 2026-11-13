# NFL Lines Lab — research notes

**Session:** `arena-c6eea73d` · **Compiled:** 2026-11-13 · **Site section:** <https://karagemop466-tech.github.io/Korea5/lab/index.html>

These notes are the written record behind the NFL Lines Lab section of the site. Everything numeric below was computed from
official NFL records that are committed under `data/lab/`, and every one of them can be recomputed with
`python3 scripts/analyze_lab.py`.

---

## 1. The short version

This repository is a **schedule planner**. It held no line-making, no forecasting, no validation and no injury tracking before
this work. It still holds **no market price, no settlement record and no forecast log** — so this work publishes **no win
rate, no yield, no edge, no fair price and no profitable strategy**. What it does publish is the machinery needed to get
there without fooling yourself:

1. a **decision register** naming what is known, what is missing and what blocks each decision (15 items);
2. a **strategy catalogue** of 12 candidate signals (singles, player props, prop combinations, parlays, injury overlay) each
   bound to **9 validation gates**;
3. **measured** dispersion and **measured** correlations from official game data, with confidence intervals and the sample
   size each estimate would need;
4. an **injury and depth tracker** built on three official sources with a rule that keeps unsupported cells blank;
5. a **leaderboard design** whose table is empty on purpose;
6. a **suggestions register** with a recommended path, so decisions are made before code is written.

## 2. What was verified, and how

| Source | Used for | Retrieved |
|---|---|---|
| <https://www.nfl.com/injuries/> | Week 10 (2026) official injury report: practice status and game status per club | 2026-11-13 |
| <https://www.nfl.com/news/nfl-week-10-injury-report-2026-season> | Published Week 10 game-status designations for the week's 14 games | 2026-11-13 |
| <https://www.nfl.com/players/justin-jefferson/stats/logs/> (and four more players) | Official 2026 per-game statistics | 2026-11-13 |
| <https://www.nfl.com/games/bills-at-vikings-2026-reg-9> + the official Game Book PDF it links | Starting lineups, Did Not Play, substitutions, final individual statistics | 2026-11-13 |
| <https://operations.nfl.com/> | Official rules and policies (2026 NFL Rulebook) | 2026-11-13 |

**Cross-check performed.** Every Week 9 row in the player logs was compared with the official Game Book for Bills at Vikings
on November 9, 2026 and matched exactly on attempts, completions, yards, touchdowns, interceptions, rating and rushing.
Where two official pages disagreed (the Washington and New York records) both readings are published and the difference is
flagged rather than reconciled.

**Outbound access note.** Shell access in this sandbox reaches `github.com`, `pypi` and `npm` only. Official sports hosts
were reached through the sandbox fetch tool, and the records were committed to `data/lab/` with their source URLs so the
analysis is reproducible without that tool.

## 3. The numbers

### 3.1 Dispersion — how wide each outcome is

| Outcome | n | Mean | Std dev | Median | Min | Max |
|---|---|---|---|---|---|---|
| Justin Jefferson receiving yards | 7 | 56.14 | 22.65 | 55 | 32 | 92 |
| Jordan Addison receiving yards | 7 | 39.57 | 31.15 | 28 | 0 | 90 |
| Aaron Jones rushing yards | 8 | 59.25 | 39.51 | 49 | 16 | 113 |
| Josh Allen passing yards | 8 | 253.38 | 42.25 | 250.5 | 204 | 334 |
| Minnesota Vikings team points | 8 | 18.25 | 10.26 | 15.5 | 6 | 39 |
| Buffalo Bills team points | 8 | 32.00 | 6.76 | 34.5 | 23 | 41 |

A strategy that claims to predict a player's yardage has to predict inside a 23-to-42 yard spread, game after game. To see a
**3-yard** modelling advantage at all, a player needs **58 to 199 games** of their own history (n ≥ (σ ÷ edge)²). That is the
arithmetic behind refusing to call a nine-game sample a signal.

### 3.2 Dependence — the legs of a parlay are not independent

| Outcome A | Outcome B | n | r | 95% interval | p |
|---|---|---|---|---|---|
| Jefferson receiving yards | Addison receiving yards (same team) | 6 | **-0.8192** | -0.9795 to -0.0227 | 0.0461 |
| Jefferson receiving yards | Aaron Jones rushing yards | 7 | 0.3139 | -0.5751 to 0.8630 | 0.4930 |
| Addison receiving yards | Aaron Jones rushing yards | 7 | 0.0672 | -0.7224 to 0.7807 | 0.8862 |
| Jefferson receiving yards | Vikings team points | 7 | 0.5542 | -0.3413 to 0.9223 | 0.1967 |
| Aaron Jones rushing yards | Vikings team points | 8 | 0.0139 | -0.6976 to 0.7116 | 0.9739 |
| Jefferson receiving yards | Vikings game total | 7 | 0.4970 | -0.4092 to 0.9096 | 0.2564 |
| Vikings team points | Vikings game total | 8 | **0.8913** | 0.5018 to 0.9803 | 0.0030 |
| Josh Allen passing yards | Bills team points | 8 | 0.3866 | -0.4372 to 0.8576 | 0.3442 |

The two finding that matter:

* **Two same-team receivers move in opposite directions** (r = -0.82, n = 6). Targets are a shared, finite resource: what one
  receiver gains, the other tends to lose. Pricing a two-leg receiver parlay as the product of two marginal probabilities
  would overstate the joint probability, and the error runs in the book's favour. The interval is wide (-0.98 to -0.02) and
  only just excludes zero, so this is a **demonstration of the structure**, not an estimate to trade on.
* **Team points and game total move together** (r = 0.89, n = 8). A team-total leg inside a game-total parlay is not an
  independent second opinion; it is nearly the same number.

### 3.3 The cost of luck

Two-sided one-proportion z test, α = 0.05, power = 0.80, normal approximation. The break-even rate already contains the vig.

| Price basis | Break-even | True win rate | Edge | Observations needed |
|---|---|---|---|---|
| -110 | 0.5238 | 0.5738 | +5.0 pts | **779** |
| -110 | 0.5238 | 0.5538 | +3.0 pts | **2,170** |
| -110 | 0.5238 | 0.5338 | +1.0 pt | **19,565** |
| -105 | 0.5122 | 0.5622 | +5.0 pts | 815 |
| 50/50 | 0.5000 | 0.5500 | +5.0 pts | 783 |

And for dependence: a true correlation of **0.3** needs roughly **100 games** to be detected with 80% power (8 games: 11%;
17 games: 21%; 33 games: 40%). At nine games of one season, a real relationship would be found roughly one time in ten.

**This is the single most important number in the project.** It is now a hard entry condition (gate G0) rather than a footnote.

## 4. Injuries, depth and replacement

Three official facts that are often conflated:

* **Availability** — the weekly official injury report: practice status (Full / Limited / Did Not Participate) and game status
  (Out / Questionable / Doubtful). Recorded for 25 clubs and 275 rows for Week 10.
* **Who started and who played** — the official Game Book: starting lineups for both teams, the Did Not Play block,
  substitutions and final individual statistics.
* **Depth tier** — this project's own label. It is written **only** where the Game Book supports it, and it is never inferred
  from an injury status. Where the evidence is missing the cell stays blank and the item is flagged.

Worked example from the official Game Book for Bills at Vikings, November 9, 2026:

* Vikings: listed quarterback **K. Murray is in the Did Not Play block**; **C. Wentz started**; substitute **M. Brosmer also
  threw for 58 yards** in the same game — a documented three-deep replacement chain.
* Vikings receiving: **J. Jennings is in the Did Not Play block**; **J. Addison started**; **M. Price started** in the third
  wide receiver slot.
* Vikings defensive line: **C. Banks is in the Did Not Play block**, with **B. Richter** and **E. Williams** recorded as
  defensive-line substitutes.

Every one of those statements is read from the official PDF. None of it is a depth-chart guess, and the lab does not publish
club depth charts because the league does not publish them (the nfl.com team depth-chart address returned a 404 page during
this pass).

## 5. The gates and the leaderboard

Nine gates, in order: minimum evidence (G0), provenance and point-in-time capture (G1), coverage and reconciliation (G2),
market baseline (G3), leakage audit and time-ordered splits (G4), out-of-sample scoring with uncertainty (G5), robustness and
multiple testing (G6), locked prospective trial (G7), independent review and audit history (G8).

**Gate G3 is currently unpassable**, because there is no market reference in this repository. That is not a defect in a
strategy — it is the missing artefact (questions Q01, Q04, Q05 and Q10) and the critical path for the whole line-making
track.

The leaderboard is **paper only**. It scores predeclared out-of-sample log-loss improvement against the de-vigged market,
reports the interval and the observation count, never ranks by win rate or streak, shrinks toward the baseline, discloses how
many variants were tried, and keeps failed strategies in the audit history. Its table is published **empty**, because no
strategy has passed the gates and filling it would be a fabricated result.

## 6. The suggestions register

Fifteen suggestions across two areas — site and analytics — each with the problem, the proposal, the evidence, impact, effort,
risk, dependencies, priority and a recommendation. The full register with the review sheet is on
<https://karagemop466-tech.github.io/Korea5/lab/suggestions.html>.

Recommended build order:

1. **Decide the two blockers** — which prices are legally accessible, and where historical lines come from (Q01, Q05).
2. **Ship the cheap site wins** — decision headers, a reachable flagged page, one filter box, per-table freshness, a vacation
   comparison view, JSON beside every table (P01–P05, P13).
3. **Automate the tracker** — extend the existing CI fetchers to the injury report and Game Books (P12).
4. **Build the measurement layer** — quote and settlement archive, then backtests under the published gates, then the paper
   trial (P11).
5. **Only then open the board.**

## 7. Irregularities and limits

Fifteen items are published on the lab's Flagged for Review page with their sources, and are not hidden. The material ones:

* no price, settlement or forecast data anywhere (L01) — this is why the leaderboard is empty and no strategy is claimed;
* the official Week 10 report had published designations for only 3 of 14 games at retrieval (L02);
* three club tables on the official injury page could not be transcribed without guessing and are listed as partial (L03–L06);
* two official pages print different records for the Thursday teams (L07);
* the Bills' Did Not Play block was not in the retrieved Game Book portion (L08);
* every correlation rests on 6–8 games with wide intervals (L11) — published with every coefficient for that reason;
* no snap counts were extracted, so opportunity share is described only through published individual statistics (L13);
* the league does not publish depth charts on the pages checked (L14);
* no legal, privacy or tax review exists, and no reward policy has been written (L15).

## 8. Reproducing this

```bash
python3 scripts/analyze_lab.py     # recomputes every number in section 3 from data/lab/
python3 tools/build_lab.py         # regenerates lab/*.html from curated/nfl-lab.json + data/lab/
python3 scripts/build_site.py      # regenerates the root pages (navigation includes the lab)
python3 scripts/audit_certainty.py # publishes the certainty banner on every page
python3 scripts/check_links.py     # fails the build on any missing local link
```

## 9. Source links for manual review

- NFL official injury report: <https://www.nfl.com/injuries/>
- NFL Week 10 injury report article: <https://www.nfl.com/news/nfl-week-10-injury-report-2026-season>
- NFL official player statistics: <https://www.nfl.com/stats/player-stats/>
- NFL official schedules: <https://www.nfl.com/schedules/>
- NFL official transactions: <https://www.nfl.com/transactions/>
- NFL Football Operations (rules): <https://operations.nfl.com/>
- NFL important dates: <https://operations.nfl.com/calendar-events/nfl-important-dates>
- Game page (stable citation): <https://www.nfl.com/games/bills-at-vikings-2026-reg-9>
- Official Game Book PDF (versioned CDN path, retrieved 2026-11-13):
  <https://static.www.nfl.com/image/upload/v1794311318/gamecenter/ab5825a7-4feb-11f1-abca-2c54536568a9.pdf>
