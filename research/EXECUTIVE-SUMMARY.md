# Executive summary — Free Time Vacation

**Review date: 2026-11-03 · San Francisco 94122 · America/Los_Angeles (PST/PDT)**
**Site:** https://karagemop466-tech.github.io/Korea5/

## The answer

| Year | Best window | Length | What is official behind it | Evidence status |
|---|---|---|---|---|
| **2027** | **Mon Feb 1 – Sat Feb 13, 2027** | **13 calendar days** | MLB's 2027 season (Opening Night Mar 24, Opening Day Mar 25, final day Sep 26) is released and loaded from the league feed; Super Bowl LXI is Sun Feb 14, 2027; MLB Spring Training 2027 begins Fri Feb 19 | Dates **official**; NFL playoff round dates **modelled** |
| **2028** | Sun Jan 31 – Sat Feb 12, 2028 | 13 calendar days | Same calendar structure | **ESTIMATION** — MLB 2028 and NFL 2027 schedules not released |
| **2029** | Mon Jan 29 – Sat Feb 10, 2029 | 13 calendar days | Same calendar structure | **ESTIMATION** — neither schedule released |

**Lengths count inclusive calendar days, not hotel nights.**

Every year the same pocket opens between **conference-championship Sunday** and the **Super Bowl**. It is the only
multi-week stretch in which no MLB, NFL, Stanford, Cal or Westwood One game is on the air, because:

* MLB plays a slate almost every day from late February to early October, and your scope counts **all 30 clubs**;
* NFL and college football cover every weekend from late August to mid-February;
* the two weeks after the conference championships are the one point where both leagues are dormant.

A **full 14-day** vacation does not quite fit: the day before the window is a conference championship and the day after
is the Super Bowl. **13 consecutive calendar days is the maximum.** Three weeks fits nowhere in any year.

### The stricter variant

If the **Pro Bowl Games** also counts as an event to avoid, the longest fully free run falls to **six calendar days** in each
year (2027: Jan 25–30, Feb 1–6, Feb 8–13). The Pro Bowl is an all-star exhibition, not a league game, and Westwood
One's published 2026-27 NFL schedule does not list it, so the planner counts it in the *all games* view and excludes it
from the *radio* view. That distinction is the only difference between the two answers and it is printed on the site.

## What "free" means here

A minute is free when none of these is on the air:

* **MLB** — every game, all 30 clubs; **Giants** and **Athletics** flagged high priority
* **NFL** — every game, preseason, regular season and postseason; **49ers** flagged high priority
* **NCAAF** — **Stanford** and **Cal**, flagged high priority
* **Westwood One Sports** national NFL windows (Thursday, Sunday and Monday night, Thanksgiving, Christmas, playoffs,
  Super Bowl)

Two scopes are shown everywhere. **Radio** = only events tagged Giants, Athletics, 49ers, Stanford, Cal or Westwood One.
**All games** = additionally every other MLB/NFL row in the model.

## Evidence and limits

| Area | What was verified this session | Official link |
|---|---|---|
| 2027 MLB season | Opening Night Wed Mar 24; Opening Day Thu Mar 25 (14 games); All-Star Game Tue Jul 13 at Wrigley Field; final regular-season day Sun Sep 26 — all read on MLB.com | https://www.mlb.com/news/mlb-2027-schedule-released |
| 2027 MLB fixtures | The league feed returns 15 games on 2027-03-25 with first-pitch times and `startTimeTBD` flags, i.e. the schedule is live | https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2027&gameType=R |
| 2028 / 2029 MLB | The same feed returns **0 games**: those seasons are not released, so the rows are modelled and labelled ESTIMATION | https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2028&gameType=R |
| Super Bowl LXI | Sun Feb 14, 2027, SoFi Stadium | https://www.sofistadium.com/news/detail/los-angeles-region-to-host-super-bowl-lxi-in-2027-welcoming-the-nfls-biggest-stage-for-the-second-time-this-decade-to-sofi-stadium |
| 2027 NFL season | nfl.com/schedules/2027 redirects to the 2026 season page: no 2027 NFL schedule exists yet | https://www.nfl.com/schedules/2027/ |
| Westwood One 2026-27 | National windows are published through Week 18 (Jan 9-10, 2027); no Pro Bowl entry | https://www.westwoodonesports.com/nfl-schedule/ |

**Not verified, and not claimed:** individual future kickoff times that the source has not published, actual game end
times, flex scheduling, flexed playoff slots, and whether each event is receivable on a standard AM/FM radio at an Outer
Sunset address. Those gaps are published on the [Flagged for Review](../certainty.html) page and do not block the
recommendation — they set its confidence.

## Included interests

All 30 MLB clubs and all NFL teams are visible; Giants, Athletics, 49ers, Stanford football and Cal football carry the
high-priority flag. Westwood One national windows are included, including the one published NCAA Football window.
An all-games conflict is a personal-interest restriction, not evidence that every game airs on Bay Area AM/FM.

## How the numbers were produced

* `scripts/fetch_mlb.py` — official MLB StatsAPI, 2026 and 2027 (confirmed live this session).
* `scripts/build_events.py` — normalises every source, marks each row `verified` or `estimated`, and carries the
  reason for every estimate in a `timeBasis` field.
* `scripts/analyze.py` — builds per-day busy/free intervals in Pacific time and the consecutive-free-run table the
  recommendation is read from. Nothing in the recommendation is typed in by hand.
* Durations: MLB 165 min (195 postseason), NFL 185 min (195 postseason), NCAAF 200 min, with halftime inside the game,
  not free time.
* `scripts/build_site.py`, `tools/build_extra.py` — the published pages.
* `scripts/check_links.py`, `tools/verify_extra.py`, `scripts/audit_certainty.py`, `tests/` — 31 link/schema/UI checks,
  30 build checks, the certainty audit and unit tests, all passing.

## Irregularities flagged for review

Published, with sources, on the Flagged for Review pages. They do not block publication:

1. Big Game date conflict between calbears.com (Nov 14, 2026) and gostanford.com (Nov 21, 2026). Both days blocked.
2. Mexico City kickoff discrepancy between 49ers.com and Westwood One (both windows blocked).
3. Westwood One Dec 27, 2026 kickoff time not retrievable — left blank.
4. Cal Nov 28, 2026 opponent not shown on the official page — left blank.
5. Athletics flagship station not confirmed by an official page; A's games still blocked.
6. Westwood One San Francisco affiliate not published on the pages reviewed.
7. Cal 2026 games before Nov 14 omitted rather than guessed.
8. 2027 MLB placeholder first-pitch times (1,631 of 2,430) estimated from each club's modal 2026 start.
9. **New this session:** the Pro Bowl Games date for 2027 is modelled, not published; it is excluded from the radio scope
   and remains in the all-games scope.
10. **New this session:** 2028 and 2029 windows are model output. The dates will move when MLB and the NFL release those
    schedules, and the pages say so on every affected row.

## Bottom line

**Book Feb 1 – Feb 13, 2027** if you want the trip that is backed by the most official dates today. Treat the 2028 and
2029 equivalents as the same shape, one week earlier on the calendar, and re-check them when those schedules are
released.
