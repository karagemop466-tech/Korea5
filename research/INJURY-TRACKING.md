# Injury & Lineup-Depth Tracking — design

**Purpose:** track injuries and lineup deficiencies so a strategy can know when a **2nd, 3rd or 4th string** player is
replacing a starter — on **defense and offense alike** — and what that means. This is a **design**, not a validated
predictive model. It defines what is verified, what is estimated, and what stays blank.

**Review date:** 2026-11-13 · **Companion:** [Injury & lineup-depth tracking page](../injury-tracking.html) ·
[NFL Lines & Strategy Lab](NFL-STRATEGY.md).

## Core rules

1. **Tier comes from an official depth chart, never from injury status.** "Out", "limited" or "questionable" does not
   tell you who is the 2nd string. Tier is read from the club's official depth chart (1st/2nd/3rd/4th string).
2. **Availability comes from an official injury report / inactive list.** Official status and actual participation are
   separate observations and are stored separately.
3. **A "lineup deficiency" requires both a sourced tier change and a sourced availability change.** If either link is
   missing, the deficiency is **unverified**, not asserted.
4. **Missing values stay blank and are flagged.** No backup tier is inferred, no workload is invented, no performance
   effect is claimed without data.
5. **Offense and defense are tracked symmetrically.** The same fields and rules apply to both.

## Verified official sources

| Source | What it provides | Field/selection | Link |
|---|---|---|---|
| NFL injury report | Player, position, injury, practice status, game status | Season + week selector | https://www.nfl.com/injuries/ |
| Club official depth chart (e.g. 49ers) | 1st/2nd/3rd/4th string by position, offense/defense/special teams | Updated date shown on page | https://www.49ers.com/team/depth-chart |
| NFL transactions | Trades, signings, waivers, reserve list, terminations | Year + month selector | https://www.nfl.com/transactions/ |
| NFL player statistics | Per-player production by category | Category + year selector | https://www.nfl.com/stats/player-stats/ |
| NFL team statistics | Offense/defense/special-teams team categories | Category + year selector | https://www.nfl.com/stats/team-stats/ |
| NFL schedules / game pages | Game metadata; gamebooks/play-by-play for actual participation | By week / by team | https://www.nfl.com/schedules/ |

Verified as live on 2026-11-13. These are starting points; a particular historical field must still be checked before
it is used.

## Record schema

Every injury/lineup record carries the same provenance fields (see `NFL-STRATEGY.md`, gate 1):

| Field | Meaning | Source | Status |
|---|---|---|---|
| `gameId`, `playerId`, `teamId`, `position` | Identifiers | Official roster/schedule | Verified where resolvable |
| `tier` | 1st / 2nd / 3rd / 4th string at the position | Club official depth chart | **Verified only from official depth chart** |
| `tierUpdated` | Timestamp the depth chart was published/updated | Club depth chart page | Verified (page shows "Updated as of …") |
| `injury`, `practiceStatus`, `gameStatus` | Official status as published | NFL injury report | Verified as published |
| `reportPublished` | Publication time of the injury report | NFL injury report | Verified as published |
| `inactiveConfirmed` | Game-day inactive/active confirmation | Official inactive list | Verified where published |
| `transaction` | Roster move that changes depth | NFL transactions | Verified where published |
| `replacementPlayer` | Who moves up when a starter is unavailable | Depth chart order | Verified from depth chart only |
| `expectedOpportunityShare` | Modelled share of snaps/targets | Model estimate | **Estimate — labelled, never asserted as fact** |
| `actualParticipation` | Real snaps/targets from gamebook | Official gamebook/play-by-play | Verified where available |
| `sourceUrl`, `capturedAt`, `revision` | Provenance and immutability | Capture pipeline | Verified |

## Tier logic (offense and defense)

For each position, read the depth chart columns **1st, 2nd, 3rd, 4th**:

* **1st string** = projected starter at that position.
* **2nd string** = first backup; steps in for a full-time starter absence.
* **3rd string** = second backup; steps in when 1st and 2nd are both unavailable.
* **4th string** = third backup; depth-thin situations.

A **deficiency flag** is raised for a team/position when **all** of the following hold:

1. The depth chart shows a **lower tier** (2nd/3rd/4th) listed as the top available name for that position — i.e. the
   1st string is unavailable; **and**
2. An official injury report or inactive list confirms the 1st string is **out** (or otherwise confirmed unavailable);
   **and**
3. The record ties the two with timestamps so the tier change is point-in-time.

If (1) or (2) is not confirmed, the deficiency is **unverified** and the cell stays blank.

### Position groups tracked

| Side | Position groups |
|---|---|
| Offense | QB; RB/FB; WR; TE; OL (LT/LG/C/RG/RT) |
| Defense | Defensive line (LDE/LDT/RDT/RDE); LB (SAM/MIKE/WILL); CB (LCB/RCB/NB); S (FS/SS) |
| Special teams | P; K; H; PR; KOR; LS |

## Worked example — source data shape (verified snapshot, not a prediction)

The table below is the **shape** of the data an official depth chart provides. It is a verbatim snapshot of the
San Francisco 49ers official depth chart, **Updated as of 11/10/26**, cited to the official page. It is shown to make
the schema concrete; it is **not** a line, a signal, or a performance claim. No tier is inferred beyond what the chart
prints, and blanks are left blank.

| Side | Position | 1st string | 2nd string | 3rd string | 4th string | Source |
|---|---|---|---|---|---|---|
| Offense | WR | Mike Evans | Jordan Watkins | Brandin Cooks | (blank) | https://www.49ers.com/team/depth-chart |
| Offense | LT | Trent Williams | Vederian Lowe | Enrique Cruz Jr. | (blank) | https://www.49ers.com/team/depth-chart |
| Offense | QB | Brock Purdy | Mac Jones | Kurtis Rourke | (blank) | https://www.49ers.com/team/depth-chart |
| Offense | RB | Christian McCaffrey | Kaelon Black | Jordan James | (blank) | https://www.49ers.com/team/depth-chart |
| Defense | LDE | Keion White | Mykel Williams | Khalid Kareem | (blank) | https://www.49ers.com/team/depth-chart |
| Defense | RDE | Nick Bosa | Romello Height | (blank) | (blank) | https://www.49ers.com/team/depth-chart |
| Defense | MIKE | Fred Warner | Tatum Bethune | (blank) | (blank) | https://www.49ers.com/team/depth-chart |
| Defense | RCB | Deommodore Lenoir | Ephesians Prysock | (blank) | (blank) | https://www.49ers.com/team/depth-chart |
| Defense | SS | Malik Mustapha | Marques Sigle | Ashtyn Davis | (blank) | https://www.49ers.com/team/depth-chart |

Note how depth is **uneven**: e.g. the 49ers list a 3rd string at WR and LT but only a 2nd string at RDE and MIKE. That
is the kind of sourced deficiency the tracker is built to expose — without claiming any expected performance effect.

## What is NOT established

* **No historical depth-chart or injury series** exists in this repository. The worked example is a single live
  snapshot, not a time series. Tier changes cannot be backfilled from injury status.
* **Injury status does not imply workload.** A "questionable" starter does not mean a backup will take a fixed share of
  snaps. `expectedOpportunityShare` is a model estimate that is **not** asserted here.
* **No performance link is validated.** The effect of a 2nd/3rd/4th string replacing a starter on scoring, yardage or
  prop outcomes is **not measured** and is **not claimed**. It requires a validated injury-to-performance panel that
  does not exist yet (decision D-10).
* **Official source availability may vary by team/week.** The NFL.com team depth-chart URL pattern returned 404 in this
  check; the verified tier source used here is the club's own depth-chart page. This is flagged for review.
