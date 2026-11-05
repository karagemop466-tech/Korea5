# Executive summary — Free Time Vacation

**Review date: 2026-11-05 · San Francisco 94122 · America/Los_Angeles (PST/PDT)**
**Site:** https://karagemop466-tech.github.io/Korea5/

> **Supersedes** the earlier summary (`research/EXECUTIVE-SUMMARY-ef8b5b30.md`). That version recommended Feb 1–13, 2027
> (13 nights) and counted Jan 24–30, 2027 as free. Both are corrected here: the Pro Bowl Games date is not published, so the 13-night run
> depends on it, and NFL.com lists the Divisional Playoffs on Jan 23–24, 2027.

## The answer

**No 7-night stretch in 2027, 2028 or 2029 is free of every listed game.** The longest free run is **6 nights** each year. Winter is the only
season with a free gap; MLB is busy almost every other day.

| Year | Longest free run (base case) | If the Pro Bowl is Tue Feb 9 only | If there is no Pro Bowl that week | What is official behind it | Evidence status |
|---|---|---|---|---|---|
| **2027** | **Mon Jan 25 – Sat Jan 30** or **Mon Feb 1 – Sat Feb 6** (6 nights each) | Mon Feb 1 – Mon Feb 8 (8 nights) | Mon Feb 1 – Sat Feb 13 (13 nights) | MLB 2027 season (Opening Night Mar 24, final day Sep 26) and the NFL playoff round windows (Jan 16–18, Jan 23–24, Jan 31) are official; Super Bowl LXI is Sun Feb 14 | Round windows **official**; game-day splits and the Pro Bowl date **unverified** |
| **2028** | Mon Jan 24 – Sat Jan 29 or Mon Jan 31 – Sat Feb 5 (6 nights each) | Mon Jan 31 – Mon Feb 7 (8 nights) | Mon Jan 31 – Sat Feb 12 (13 nights) | Same calendar pattern | **ESTIMATION** — MLB 2028 and NFL 2027 schedules not released |
| **2029** | Mon Jan 22 – Sat Jan 27 or Mon Jan 29 – Sat Feb 3 (6 nights each) | Mon Jan 29 – Mon Feb 5 (8 nights) | Mon Jan 29 – Sat Feb 10 (13 nights) | Same calendar pattern | **ESTIMATION** — neither schedule released |

Every year the free windows fall between the **Divisional / Conference playoff weekends** and the **Super Bowl**. The 6-night runs
exist in both the all-games and radio-only views. Those two views differ elsewhere in the year (for example, many more free
days in the radio view), but in these winter windows they agree.

### Multi-week trips

| Trip length | Best 2027 window (ranked by fewest busy days) | Free days / length | Busy days | Verdict |
|---|---|---|---|---|
| 1 week (7 days) | Mon Feb 1 – Sun Feb 7 | 6 / 7 | Feb 7 (Pro Bowl candidate A, about 3 h) | Does not fit fully free |
| 2 weeks (14 days) | Mon Jan 25 – Sun Feb 7 | 12 / 14 | Jan 31 (Conference Championship), Feb 7 | Does not fit |
| 3 weeks (21 days) | Sun Jan 24 – Sat Feb 13 | 17 / 21 | Jan 24, Jan 31, Feb 7, Feb 9 | Does not fit |

No 7-, 14- or 21-day window is fully free in 2027–2029. A "fits" result requires a window with zero busy days.

### The Pro Bowl assumption

The NFL's 2026–27 calendar does not list a Pro Bowl Games date. Secondary sources conflict: Tue Feb 9, 2027 and Sun Feb 7, 2027 are both
named, and neither is official. The planner blocks both candidate days in the base case, so the base answer does not depend on either
guess. Westwood One carried the 2026 Pro Bowl Games (Tue Feb 3, 2026, 4:30–7:30 PM PT), so the Pro Bowl is in the radio tier too.

| Scenario (2027) | Result |
|---|---|
| Both candidate days blocked (base) | 6 nights (Jan 25–30 or Feb 1–6) |
| Only Feb 7 blocked | 6 nights (Jan 25–30, Feb 1–6 or Feb 8–13) |
| Only Feb 9 blocked | 8 nights, Feb 1–8 |
| No Pro Bowl that week | 13 nights, Feb 1–13 |

Free-day totals (all games / radio): 2027 77 / 95, 2028 74 / 85, 2029 70 / 81. The longest run is 6 nights in all three years.

## What "free" means here

A minute is free when none of these is on the air:

* **MLB** — every game, all 30 clubs; **Giants** and **Athletics** flagged high priority.
* **NFL** — every game, preseason, regular season and postseason; **49ers** flagged high priority. The Wild Card round window is Jan 16–18,
  2027, and a Monday game inside it is modelled.
* **NCAAF** — **Stanford** and **Cal**, flagged high priority. Bowl games are not modelled (see below).
* **Westwood One** national NFL windows (Thursday, Sunday and Monday night, Thanksgiving, Christmas, playoffs, Super Bowl), and the
  Pro Bowl Games.

Two scopes are shown everywhere. **Radio** = only events tagged Giants, Athletics, 49ers, Stanford, Cal, Westwood One or the Pro Bowl.
**All games** = additionally every other MLB and NFL row in the model.

Durations used for busy time: MLB 165 min (195 postseason), NFL 185 min (195 postseason), Pro Bowl 180 min, NCAAF 200 min. These are
planning estimates. The official MLB 2025 average game time is 2:38 (158 min); the rest are labelled **ESTIMATION**.

## Evidence and limits

| Area | What was verified on 2026-11-05 | Official link |
|---|---|---|
| 2027 MLB season | Opening Night Wed Mar 24; Opening Day Thu Mar 25; All-Star Game Tue Jul 13 at Wrigley Field; final regular-season day Sun Sep 26 | https://www.mlb.com/news/mlb-2027-schedule-released |
| 2027 MLB fixtures | The league feed carries the 2027 regular season; first 2027 Spring Training game Feb 19 | https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2027&gameType=R |
| 2028 / 2029 MLB | The same feed returns **0 games**: not released. Rows are modelled and labelled ESTIMATION | https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2028&gameType=R |
| NFL 2026–27 calendar | Week 18 Jan 9–10, 2027; Wild Card Jan 16–18; Divisional Jan 23–24; Conference Championships Jan 31; Super Bowl LXI Feb 14, 2027. No Pro Bowl date | https://www.nfl.com/news/2026-27-national-football-league-important-dates |
| 2027 NFL schedule | nfl.com/schedules/2027 returned the 2026 season page: 2027 games are not published | https://www.nfl.com/schedules/2027/ |
| Westwood One 2026 Pro Bowl | Tue Feb 3, 2026, 7:30–10:30 PM ET (4:30–7:30 PM PT) | https://www.westwoodonesports.com/events/527138/ |
| Westwood One NFL windows | National windows published through Week 18 (Jan 9–10, 2027) | https://www.westwoodonesports.com/nfl-schedule/ |
| Nov 5 2026 Thursday game | Westwood One lists 7:30 PM ET; NFL.com game centre lists 8:15 PM (Prime Video) | https://www.nfl.com/games/jaguars-at-ravens-2026-reg-9 |

The full anchor list is in `curated/anchors-2026-11-05.json`; the open items are in `curated/flags.json` (F21–F32).

**Not verified, and not claimed:** the 2027 Pro Bowl date; individual future kickoff times that the source has not published; actual game end
times; flex scheduling; and whether each event can be received on a standard AM/FM radio at an Outer Sunset address. Those gaps are
published on the [Flagged for Review](../flagged.html) page and set the confidence of the recommendation without blocking it.

## Included interests

All 30 MLB clubs and all NFL teams are visible; Giants, Athletics, 49ers, Stanford football and Cal football carry the high-priority
flag. Westwood One national windows are included. An all-games conflict is a personal-interest restriction, not evidence that every game airs
on Bay Area AM/FM.

## How the numbers were produced

* `scripts/fetch_mlb.py` — official MLB StatsAPI, 2026–2027.
* `scripts/build_events.py` — normalises each source, marks every row `verified` or `estimated`, and records the reason for each estimate in a `timeBasis` field. The NFL playoff rounds use the official windows; Wild Card Monday is an estimate.
* `scripts/analyze.py` — builds per-day busy/free intervals in Pacific time, free-run tables, the 7/14/21-day ranking, and the Pro Bowl scenarios. Nothing in the recommendation is typed in by hand.
* `scripts/build_site.py`, `tools/build_extra.py` — the published pages.
* `scripts/check_links.py`, `tools/verify_extra.py` (31 checks), `scripts/audit_certainty.py`, `tests/` — all passing on this review date.

`scripts/build_docs.py` is no longer in the rebuild chain. It would overwrite the README sections that other sessions added by hand (flag F30).

## Irregularities flagged for review

Published, with sources, on the Flagged for Review pages. They do not block publication:

1. **2027 Pro Bowl Games date** — not published. Both candidate days are blocked; the answer changes if one is removed (F21, F23).
2. **Wild Card Monday, Jan 18, 2027** — inside the official Jan 16–18 window; the day and kickoff are estimates (F24).
3. **Stanford and Cal bowl games 2026–27** — not modelled; a bowl would block its date (F25).
4. **Jan 24 2027** — a Divisional playoff day, not a free day. The earlier summary got this wrong (F26).
5. **Nov 5 2026 Jaguars at Ravens** — Westwood One 7:30 PM ET vs NFL.com 8:15 PM (F27).
6. **Fetch metadata mismatch** — two official MLB pages returned unrelated URLs in tool metadata; the content matched (F28).
7. **2027 NFL schedule** not published on nfl.com as of 2026-11-05 (F29).
8. **High-priority scope correction** — the earlier 'high' scope undercounted estimated 2028–2029 games (293 free days / 194-day run was a defect). Corrected (F31).
9. **Big Game date conflict** between calbears.com (Nov 14, 2026) and gostanford.com (Nov 21, 2026). Both days blocked.
10. **Mexico City kickoff discrepancy** between 49ers.com and Westwood One. Both windows blocked.
11. **Westwood One Dec 27, 2026 kickoff** not retrievable — left blank.
12. **Cal Nov 28, 2026 opponent** not shown on the official page — left blank.
13. **Athletics flagship station** not confirmed by an official page; A's games still blocked.
14. **Westwood One San Francisco affiliate** not published on the pages reviewed.
15. **Cal 2026 games before Nov 14** omitted rather than guessed.
16. **2027 MLB first-pitch times** — MLB states that times are not final; any time not published by MLB is shown as an estimate.
17. **2028 and 2029 windows** are model output. They will move when MLB and the NFL release those schedules.

## Bottom line

**Book Mon Jan 25 – Sat Jan 30, 2027, or Mon Feb 1 – Sat Feb 6, 2027.** Both are 6 nights, and both are the longest runs that are free of every
listed game in the base case. A 13-night trip (Feb 1–13) exists only if the Pro Bowl Games are not held that week. No 1-, 2- or 3-week trip is
fully free in any year. The 2028 and 2029 equivalents are ESTIMATION only, and should be re-checked when those schedules are released.
