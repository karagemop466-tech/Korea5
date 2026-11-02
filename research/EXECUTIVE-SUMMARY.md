# Executive summary — when to take a vacation (2027, 2028, 2029)

**Prepared for:** a listener in San Francisco (94122) who wants to travel when nothing he follows is live on the radio.

**Live site:** https://karagemop466-tech.github.io/Korea5/  ·  **Data rebuilt:** 2026-11-02T17:45:08Z  ·  **Verification report:** `verification/report.json` (61/62 curated rows re-verified)

## 1. Bottom line

**There is no fully free 7-day window in 2027, 2028 or 2029.** In all three years the longest stretch with nothing on air is exactly **six days**, and it recurs in January and February — the Monday-to-Saturday gaps between NFL playoff weekends — plus the gap between the Super Bowl and the first Spring Training game.

Every year has several six-day gaps, all equivalent in length. They are:

- **2027** — **Jan 25 – Jan 30, 2027**; **Feb 1 – Feb 6, 2027**; **Feb 8 – Feb 13, 2027** (6 days each)
- **2028** — **Jan 24 – Jan 29, 2028**; **Jan 31 – Feb 5, 2028**; **Feb 7 – Feb 12, 2028** (6 days each)
- **2029** — **Jan 22 – Jan 27, 2029**; **Jan 29 – Feb 3, 2029**; **Feb 5 – Feb 10, 2029** (6 days each)

Of those, the one after the Super Bowl and before Spring Training is usually the easiest to travel in: the baseball season has not started, and the only adjacent event is the Super Bowl itself.

If the trip can only be two weeks or longer, the honest trade-off is one NFL Sunday (about three hours of radio) or the Pro Bowl; the best 14-day windows are listed in section 4.

## 2. Why a whole week never clears

* **MLB plays almost every day.** The 2027 season is officially released: **2,430 regular-season games**, 8 Spring Training games and the All-Star Game (2027-07-13, Wrigley Field). It runs 2027-03-25 → 2027-09-26. Between mid-February and early October there are only a handful of days without a Major League game, and they are the All-Star break.
* **The NFL owns the winter weekends.** Sunday, Monday and Thursday windows from September to early January, then the playoffs into February.
* **College football owns the autumn Saturdays**, and Stanford and Cal both play twelve of them.
* The two sports overlap in September–October, which closes the only gap the baseball season leaves.

## 3. The verified 2027 MLB picture

- 2,430 regular-season games across all 30 clubs, from MLB's own StatsAPI.
- 8 Spring Training games; first regular-season day 2027-03-25, last 2027-09-26.
- **1,631 of the 2,430 regular-season games have a placeholder start time** in the league feed (every one shows `:33`). Dates and matchups are official; the first-pitch time is not published yet. Those rows are labelled *estimated* and their start time is taken from the home club's most common start time on that weekday in the released 2026 season.

## 4. Ranked vacation windows

Ranking rule: fewest whole days that contain any game first, then fewest hours of live coverage. Full tables on the site.

| Year | Trip length | Best window | Free days | Busy hours |
|---|---|---|---|---|
| 2027 | 7 days | Jan 24 – Jan 30, 2027 | 6 / 7 | 3.2 |
| 2027 | 14 days | Jan 24 – Feb 6, 2027 | 12 / 14 | 6.5 |
| 2027 | 21 days | Jan 24 – Feb 13, 2027 | 18 / 21 | 9.8 |
| 2028 | 7 days | Jan 23 – Jan 29, 2028 | 6 / 7 | 3.2 |
| 2028 | 14 days | Jan 23 – Feb 5, 2028 | 12 / 14 | 6.5 |
| 2028 | 21 days | Jan 23 – Feb 12, 2028 | 18 / 21 | 9.8 |
| 2029 | 14 days | Jan 21 – Feb 3, 2029 | 12 / 14 | 6.5 |
| 2029 | 21 days | Jan 21 – Feb 10, 2029 | 18 / 21 | 9.8 |

Lightest-schedule view (same windows ranked by hours of live sport rather than whole days):

| Year | Trip length | Lightest window | Busy hours |
|---|---|---|---|
| 2027 | 7 days | Jan 24 – Jan 30, 2027 | 3.2 |
| 2027 | 14 days | Jan 24 – Feb 6, 2027 | 6.5 |
| 2028 | 14 days | Jan 23 – Feb 5, 2028 | 6.5 |
| 2029 | 14 days | Jan 21 – Feb 3, 2029 | 6.5 |

## 5. What is verified, and what is not

| Layer | Status | Source |
|---|---|---|
| MLB 2026 + 2027 fixtures | **Verified** | MLB StatsAPI (league's own data service) |
| 2027 MLB start times | Partly verified / estimated | MLB StatsAPI placeholder time; estimated per club history |
| 49ers 2026 dates, times, TV, radio | **Verified** | 49ers.com |
| Stanford, Cal 2026 | **Verified** | gostanford.com, calbears.com |
| Westwood One national NFL 2026–27 | **Verified** | westwoodonesports.com |
| NFL 2027–2029 | **Estimated** (structure only) | Modelled on the league calendar |
| NCAAF 2027–2029 | **Estimated** (structure only) | Modelled on the schools' usual Saturdays |
| MLB 2028–2029 | **Estimated** (structure only) | Modelled on the league calendar |

## 6. Irregularities flagged for review

1. **Big Game date conflict.** calbears.com lists the 129th Big Game on **Sat Nov 14, 2026, 12:30 PM**; gostanford.com lists it on **Sat Nov 21, 2026, TBA**. Both dates are blocked; the conflict is unresolved.
2. **Mexico City kickoff conflict.** 49ers.com lists the Nov 22, 2026 game at **5:20 PM PST**; Westwood One lists **7:30 PM ET (4:30 PM PST)**. Both windows are blocked.
3. **Westwood One, Dec 27, 2026 (JAX at DAL)** — kickoff time was not retrievable from the page; left blank and marked unverified.
4. **Cal Nov 28, 2026** — the official page shows the date but no opponent; left blank.
5. **Athletics radio flagship** — no official confirmation found for 2026; A's games are still blocked as high priority.
6. **Westwood One's San Francisco affiliate** — not published on the pages verified.
7. **Cal's early-season 2026 games** — the official page's card order could not be parsed unambiguously, so those rows are omitted rather than guessed.

## 7. Sources

| Source | Used for |
|---|---|
| https://statsapi.mlb.com/api/v1/schedule | All MLB fixtures and times |
| https://www.mlb.com/schedule/2027-04-01 | Human-readable per-date view |
| https://www.49ers.com/schedule/2026/ | 49ers dates, times, TV, radio |
| https://gostanford.com/sports/football/schedule | Stanford 2026 |
| https://calbears.com/sports/football/schedule | Cal 2026, Cal radio network |
| https://www.westwoodonesports.com/nfl-schedule/ | National NFL radio windows |
| https://www.nfl.com/schedules/ | Weekly window structure used for estimates |

## 8. How to use the site

* **Dashboard** — the headline answer, the next 14 days, and the best windows.
* **Calendar** — a scoreboard-style day view with yesterday / today / tomorrow, a 24-hour free/busy bar, and the games on that day.
* **Vacation windows** — every 7/14/21-day window ranked, plus the longest continuous free stretches.
* **MLB / NFL & 49ers / Stanford & Cal** — the underlying tables, each row linking to its official source.
* **Radio** — which station carries what, and what is unconfirmed.
* **Flagged** — everything unresolved, with source links.
* **Method** — definitions, game-length assumptions and how estimates are produced.

## 9. Verification

- 62 curated rows are re-checked in CI against the official page that publishes them: 61 passed, 1 failed.
- 9/10 MLB API spot checks matched game-for-game.
- 0 feed integrity problems (missing source links, malformed dates or times).
- Failures are published on the Flagged page, not hidden.
