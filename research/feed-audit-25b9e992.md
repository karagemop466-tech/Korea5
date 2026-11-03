# Official-feed reliability audit

**Review date:** 2026-11-03. This is an acquisition and interpretation audit, not a certification that every game, station, or vacation interval has been checked. The official pages below were inspected individually through the web page retrieval tool. Previously committed raw HTML was used only to exercise parsers; it is a historical snapshot, not a new live verification. Sports websites cannot be fetched directly from the workspace shell, so the full refresh is tested separately on GitHub Actions.

## Executive summary

- A league game, a national-network event listing, an affiliate listing, a broadcast actually carried on a specific local station, and reception at a particular address are **different claims**. The available sources do not establish every individual AM/FM broadcast in Outer Sunset.
- An absent or failed feed is not evidence that a schedule is empty, a season has not been released, or a minute is free. The refreshed fetcher refuses to replace its saved official snapshots when a required request or parse fails.
- The old data workflow operated on an earlier session branch and did not update the published site automatically. This change proposes a scheduled, checked Pages build with no bot pushes to another branch. A successful live deployment and scheduled refresh must be confirmed separately.
- The NFL collector checks the requested season and week, handles available postseason pages, and leaves unknown times blank. The currently integrated NFL source feed remains limited to the 2026 season; future NFL seasons and school schedules require additional integration as they are released.
- MLB 2028–2029, 2027–2029 NFL, event-level local carriage, and exact future game/broadcast ends remain unverified wherever official data is not available. Model gaps are provisional, never guaranteed vacation windows.

## Direct official-source checks

| Item checked | What the source actually says | Limitation / review flag | Official source |
|---|---|---|---|
| NFL example | Jacksonville at Baltimore is listed for November 5, 2026 at 8:15 p.m. on the NFL game page; the NFL weekly schedule supplies the game. | Source start is a kickoff, not a guaranteed end or proof of a local AM/FM station. | [NFL game](https://www.nfl.com/games/jaguars-at-ravens-2026-reg-9), [NFL week 9](https://www.nfl.com/schedules/2026/by-week/week-9) |
| Westwood One example | The network lists Jacksonville at Baltimore from 7:30 p.m. to 11:59 p.m. Eastern on November 5, 2026. | This is the event listing; the earlier network start is not necessarily a kickoff conflict, and the listed end is not verified as the actual end of live audio. A local affiliate may not air it. | [Westwood One event](https://www.westwoodonesports.com/events/548561/) |
| Unnamed Week 16 event | Westwood One lists an event on December 26, 2026 at 8:00 p.m. Eastern as “Week 16 Saturday Doubleheader TBA”. | Do not attach a specific matchup without an official source identifying it. | [Westwood One event](https://www.westwoodonesports.com/events/548520/) |
| MLB TBD values | In the April 1, 2027 API response, some records explicitly contain `startTimeTBD: true` despite having a `gameDate`, including game IDs 854204 and 852345. | Those timestamp fields must not be presented as confirmed first-pitch times. A missing TBD flag is also unknown, not `false`. | [MLB StatsAPI day query](https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate=2027-04-01&endDate=2027-04-01) |
| Station-list provenance | The network's station finder separates NFL, NCAA Football, NCAA Basketball, and Soccer, and labels the currently displayed lists with 2025 season captions. | A list's vintage and sport must be retained. It also warns that local blackouts or conflicts can prevent an affiliate from airing an event; no list establishes reception at 94122. | [Westwood One Station Finder](https://www.westwoodonesports.com/station-finder/) |
| Digital vs standard analog | The FCC explains that FM digital radio can provide additional channels and that a digital receiver is needed for digital signals. | Westwood One lists `KNBR-F2`; its present availability and any analog rebroadcast are not established by the network list. Do not treat it as ordinary analog FM without separate evidence. | [FCC digital-radio guide](https://www.fcc.gov/sites/default/files/digital_radio.pdf), [Westwood One Station Finder](https://www.westwoodonesports.com/station-finder/) |
| Baseball duration context | MLB reports an average 2025 nine-inning regular-season game time of 2 hours 38 minutes. | An average is not a guaranteed future game or radio-broadcast end. Extra innings, delays, pregame and postgame coverage can extend the interval. | [MLB game-time report](https://www.mlb.com/news/mlb-average-game-time-under-three-hours-third-straight-year) |
| Postseason source | NFL.com provides dedicated by-week postseason pages, such as the 2025 Wild Card Weekend. | An empty or unavailable future postseason query does not prove that no postseason games will occur. | [NFL Wild Card Weekend](https://www.nfl.com/schedules/2025/by-week/wild-card-weekend) |

## Implemented safeguards

1. Reject a returned NFL query or game that identifies the wrong season, season type, or week; this prevents a website fallback from being mislabeled as the requested future schedule. A timezone-free or invalid timestamp is left blank and flagged instead of being assumed UTC.
2. Query NFL postseason weeks alongside preseason and regular season. An empty offseason playoff query is not a prediction; unavailable sources are recorded as warnings or failures according to timing.
3. Parse the actual Westwood One event grid rather than similarly marked sidebar cards, follow pagination until its end, and fail on a reached safety limit or malformed grid. Handle a missing start, missing end, invalid epoch, and an end before a start without manufacturing a duration.
4. Preserve station-list sport and caption, including a clear analog-reception caveat, rather than silently merging sport lists into a current universal affiliate claim.
5. Require a literal boolean `startTimeTBD`; do not turn a missing flag or the string `false` into an apparently confirmed time. A malformed API response is a failure, not an empty season.
6. Prepare all required snapshots before writing any of them. A failed fetch does not replace the saved snapshots with partial data. A scheduled site refresh similarly stops before deployment if a required feed or structural check fails.

## Verification scope

`tests/test_fetch_official.py` uses synthetic fixtures to test parser behavior, daylight-saving transitions, missing data, pagination, and failure handling. Those tests do **not** verify the truth of live schedules. The official pages listed above were manually inspected as examples, not exhaustively line by line. Full source-data verification, future-season coverage, station-specific carriage, 94122 signal reception, and guaranteed free intervals remain open review items.
