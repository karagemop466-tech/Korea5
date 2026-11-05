# Executive summary — FREE TIME VACATION (combined integration)

## What this is

A GitHub Pages dashboard that answers one question for a listener in San Francisco / Outer Sunset 94122:
**when is there nothing I want to hear live on AM/FM radio?** A minute is free when none of the covered
broadcasts are on air. Coverage: all MLB games (all 30 clubs; Giants and Athletics high priority), MLB
preseason / regular / postseason / All-Star / special / TBD; all NFL games preseason / regular / postseason /
All-Star / TBD (49ers high priority); Stanford and California (Cal) NCAAF (high priority); Westwood One Sports
national NFL radio (TNF / MNF / SNF / international / postseason / Super Bowl); and other sports broadcast live
over AM/FM radio in the Bay Area (NCAA basketball, soccer, golf, hockey, lacrosse, MCWS, WCWS).

All times are Pacific (America/Los_Angeles, PST/PDT). The site has a dashboard, calendar with Prev / Next /
Today, day scoreboard with exact free and busy intervals, category pages, an analysis page, a sources page,
and a clearly labelled **Flagged for Review** page. Every table row links to an official source.

## Headline finding

In the strict verified view there is **no fully free 7-day window in 2027**. MLB's official 2027 schedule runs
from Spring Training opening Feb 19 through the regular-season finale Sep 26, with games on almost every day;
NFL and college football then fill the winter weekends. The best verified gaps are the Monday–Saturday runs
between NFL playoff weekends and the four days immediately after Super Bowl LXI (Sun Feb 14 2027):
**Mon Feb 15 – Thu Feb 18 2027**, before Spring Training opens Feb 19.

For **2028 and 2029 MLB and the NFL have released no schedules**. Those seasons are published only as
**ESTIMATION — not a real verified released schedule**, with blank official date/time fields and flags. The
root dashboard's six-day streaks for those years come from a modelled estimate layer, not from a released
league schedule.

## Verified 2026 / 2027 structure

- **MLB 2026**: Spring Training Feb 20 – Mar 24; regular season Mar 25 – Sep 27 (2,430 games, all 30 clubs);
  postseason Sep 29 – Oct 28; World Series Oct 23 – 28 (Rays at Brewers). Source: MLB StatsAPI and MLB.com.
- **MLB 2027**: Spring Training opens Feb 19; Opening Night Wed Mar 24 (Netflix, TBD); traditional Opening Day
  Thu Mar 25; 97th All-Star Game Tue Jul 13 at Wrigley Field; regular season ends Sun Sep 26; 2,430 games with
  published dates and matchups, but **2,015 records carry `startTimeTBD=true`** — those first-pitch times are
  left blank, not inferred. Source: MLB 2027 schedule release and MLB StatsAPI.
- **NFL 2026**: Hall of Fame Game Aug 6 2026 (PT); preseason Aug 13–29; 272 regular-season games Sep 9 2026
  – Jan 10 2027; Wild Card Jan 16–18 2027; Divisional Jan 23–24; Championships Jan 31; Super Bowl LXI
  Sun Feb 14 2027 at SoFi Stadium. The NFL.com by-week feed yielded **321 games**; 24 have no published
  kickoff time and 72 carry the Westwood One national radio flag. Sources: NFL.com by-week pages and NFL
  Football Operations important dates / kickoff guide.
- **NCAAF 2026**: Stanford and Cal seasons Aug 29 – Nov 28 2026; 129th Big Game Nov 21 2026 (time TBA).
  CFP first round Dec 18–19 2026, quarterfinals Dec 30 / Jan 1 2027, semifinals Jan 14–15 2027,
  national championship Mon Jan 25 2027. Sources: GoStanford.com, CalBears.com, CollegeFootballPlayoff.com.

## Westwood One Sports and 94122 AM/FM radio

The official Westwood One event-grid and event-detail pages supply **exact network on-air windows**
(start_time / end_time Unix epoch) converted to Pacific time. The feed covers NFL plus NCAA football and
basketball, U.S. Soccer, golf, hockey, lacrosse, MCWS and WCWS. Westwood One national NFL broadcasts are high
priority. The official Station Finder lists four San Francisco affiliates — KNBR-AM, KNBR-F2, KNBR-FM,
KTCT-AM — and warns: "Because of local blackouts and/or programming conflicts, not every affiliate can air
every Westwood One Sports broadcast." Station-level carriage of any specific game is therefore not guaranteed.

Bay Area stations confirmed on official pages: KNBR 680 AM / 104.5 FM (Giants English flagship, 49ers
flagship), KSAN 107.7 FM (49ers), KSFO 810 AM (49ers network and Cal football), KSFN 1510 AM / 99.3 FM
(Giants Spanish flagship), KNEW 960 AM (Athletics Bay Area), KSTE 650 AM and KVMX 92.1/105.5 FM (Athletics,
Sacramento market; 94122 reception unverified), KTCT-AM 1050 (ESPN Radio / KNBR 1050 / Stanford football),
KNBR 1050 with three hours of Stanford pregame.

## Durations and halftime

Official facts: MLB's 2025 average nine-inning game was **2:38** (MLB.com press release). The 2026 NFL
Rulebook gives a 60-minute game (four 15-minute quarters) and a **13-minute halftime**; the 2026 NCAA Football
Rules give a 60-minute game and a **20-minute halftime**. Westwood One publishes exact per-event start/end
windows rather than a game length. The 165 / 185 / 195 / 200-minute busy blocks used by the free-time engine
are **planning buffers**, labelled ESTIMATE and flagged; they are not official durations.

## Free vacation windows

The combined analysis ranks 1-week, 2-week and 3-week windows for 2027, 2028 and 2029. A free day is one with
no verified game with a published start, no TBA/unverified official row and no estimate-only row.

- **2027 (verified schedule year):** no 7-day window is fully free. The best 1-week window is
  **Jan 24–30 2027** (six verified free days, one estimate-layer day); the best 2-week and 3-week windows are
  **Jan 24 – Feb 6** and **Jan 24 – Feb 13 2027** (12 and 18 free days). The cleanest post-Super-Bowl gap is
  **Mon Feb 15 – Thu Feb 18 2027**.
- **2028 / 2029:** strict verified free time cannot be asserted because no schedules are released. The ranking
  is a planning model, labelled **ESTIMATION — not a real verified released schedule**; the best modelled
  windows fall in late January / early February.

See the **Free windows** page for the full ranking and the root **Vacation windows** page for the parallel
session's modelled view.

## Combined data counts

- 321 official NFL 2026 games (24 without a published kickoff, 72 with the Westwood One national radio flag).
- 580 official Westwood One Sports events in the feed, 311 in the 2026-01-01+ range shown on the site.
- 2,015 MLB game records with `startTimeTBD=true`; their start times are blank.
- 7,221 parallel-session event rows merged with our official feeds; 7,529 combined rows after de-duplication.
- 1,215 calendar days (2026-11-02 → 2030-02-28) with 988 verified, 3,075 estimate-layer and 88 TBA rows.
- 41 official sources, 39 season anchors, 16 station rows, 26 future-NCAAF rows, 11 estimate windows,
  20 flagged irregularities.
- 16 build checks and 31 link/verification checks, all passing; 0 broken local links and 0 table rows missing
  an official source link.

## Flagged for Review

Unverified / TBD / irregular items are published, not hidden, and do not block the merge. Examples: 2028/2029
unreleased MLB schedules; 2027 TBD first pitches (2,015); 24 NFL games without kickoff times; Super Bowl LXII /
LXIII dates TBA; the Westwood One vs 49ers kickoff conflict on 2026-11-22; conflicting older Stanford/Cal
future-schedule releases; the CFP radio partner not stated on the official broadcast page; the Westwood One
station-frequency gap; and the prior 404 sites. The exact label **ESTIMATION — not a real verified released
schedule** appears on every unreleased-schedule row.

## Verification

The second-pass build runs a line-by-line check over the merged feeds: source-URL presence, blank-value rules,
TBD blanks, exact estimation labels, official-domain links, rulebook extraction, and local-link integrity.
Results are on the **Line-by-line verification** page and in `extra/data/verification.json`. The combined
calendar, NFL feed, Westwood One feed, source registry, station table, season anchors, duration table,
future-NCAAF table, estimate table and flag register are all generated from committed data files, so the site
can be rebuilt and re-checked deterministically.

## Sources

Every source is official: MLB StatsAPI / MLB.com, NFL.com / NFL Football Operations, 49ers.com,
GoStanford.com, CalBears.com, CollegeFootballPlayoff.com, WestwoodOneSports.com, TheSportsLeader.com (KNBR),
ESPN.com affiliate list, NCAA.org and operations.nfl.com rulebooks. The full registry with per-row purpose is
on the **Source registry** page.

## Update 2026-11-05 (session arena-57f0338e — appended, original text above unchanged)

Two of the items listed above as "TBA" have moved:

- **Super Bowl LXII (2028) date is now official.** The Mercedes-Benz Stadium event page publishes
  **Sunday, February 13, 2028** (https://www.mercedesbenzstadium.com/events/super-bowl-lxii). The planner's
  modelled 2028 Super Bowl date already matched; the row is now anchored to that page (kickoff time still
  unpublished, so the 15:30 PT start remains a planning estimate). The 2028 season anchor row is verified.
- **Super Bowl LXI (2027) date re-verified live** on the NFL's 2026 Kickoff Guide page: "Super Bowl LXI …
  Sunday, February 14, 2027, at SoFi Stadium" (https://media.nfl.com/football-information/2026/news/2026-kickoff-guide).
- **Super Bowl LXIII (2029) exact date is still not on an official page.** NFL.com and media.nfl.com confirm
  Las Vegas / Allegiant Stadium in 2029; On Location's official page says only "February 2029". Press reports
  of the NFL's social announcement give Sunday, February 11, 2029, and the planner's modelled date matches,
  but per the no-inference rule the 2029 date fields stay blank and the block stays labelled ESTIMATION —
  not a real verified released schedule.

Still true and unchanged: MLB 2028/2029 schedules are not released; the 2027 NFL schedule is not released
(expected May 2027); 2027 MLB first-pitch times are largely TBD; Westwood One 2027–29 postseason radio
schedules are not published. All recommended windows remain: 2027 anchored (radio view Feb 1–13 free of any
loaded radio game), 2028 (Jan 23 – Feb 12 best 3-week) and 2029 (Jan 21 – Feb 10 best 3-week) model output —
re-check before booking.
