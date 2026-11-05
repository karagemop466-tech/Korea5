# Session review — `arena/57f0338e-korea5` (2026-11-05)

Independent audit of the repository at `main` tip `25f0273` (PR #23), plus live re-verification of the
key official anchors and one verified fact update. Everything below was executed in this session.

## A1 — Local verification suite (all pass)

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests` | 5/5 OK |
| `python3 scripts/check_links.py` | 11 pages, 181 local + 519 external links, **0 missing** |
| `python3 tools/verify_extra.py` | **31/31 checks passed** (0 broken local links, 0 data-table rows missing an official source link, ESTIMATION labels intact, all flag IDs published) |
| `python3 scripts/audit_certainty.py` | passed — no certified future 7/14/21-day window; every page discloses incomplete coverage |
| `node --check assets/app.js` / `extra/assets/extra.js` | OK |
| JSON validity (`data/`, `curated/`, `official/`, `extra/data/`, `verification/`) | 0 malformed |
| `git diff --check` | clean |
| Local static server smoke test | HTTP 200 on 12 tested pages (root + extra) |

## A2 — Live anchor re-verification (page-fetch, 2026-11-05)

| Fact | Official source (fetched live this session) | Finding |
|---|---|---|
| Super Bowl LXI | https://media.nfl.com/football-information/2026/news/2026-kickoff-guide | "Super Bowl LXI … Sunday, February 14, 2027, at SoFi Stadium" — matches planner |
| Super Bowl LXII | https://www.mercedesbenzstadium.com/events/super-bowl-lxii | Official event page states **February 13, 2028** (a Sunday); "Event Start: TBA" — matches the modelled date; kickoff time still unpublished |
| Super Bowl LXIII | https://www.nfl.com/news/las-vegas-to-host-super-bowl-lxiii-in-2029 and https://media.nfl.com/news-and-releases/events/super-bowl-returns-to-las-vegas-in-2029- | Official release confirms **host only** (Las Vegas / Allegiant Stadium, 2029). No date. On Location's official page (https://onlocationexp.com/nfl/2029-super-bowl-tickets) says only "February 2029". Press reports (8 News Now/KLAS, NewsNation, 2026-03-30) give Sunday, Feb 11, 2029 from the NFL's social post — **non-official, date left blank per the no-inference rule** |
| Pro Bowl Games 2027 | Web search | Only conflicting unofficial dates found (Feb 6 vs Feb 9 vs Jan 31 claims on non-official sites). No official NFL page found → flag F21 stays; modelled 2027-02-07 unchanged |
| 2027 NFL schedule | Web search | Not released; next release expected May 2027 → flag F02 stands |
| MLB 2028 schedule | https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2028&gameType=R (0 games, per prior CI) + search | Still unreleased → flag F01 stands |

## A3 — Verified fact update applied (no invented values)

- **`scripts/build_events.py`** — added `official_superbowl()`: when an official page publishes a Super Bowl
  date, the postseason model anchors its date to that page (`dateStatus: "verified"`, `dateSource`,
  `dateSourceLabel`, and a timeBasis note that the kickoff time remains an estimate). LXI and LXII carry a
  date; **LXIII deliberately carries none**, so its 2029-02-11 block stays `dateStatus: "estimated"`.
  Super Bowl row titles now carry the officially announced designations: "Super Bowl LXI at SoFi Stadium,
  Inglewood (participants TBD)", "Super Bowl LXII at Mercedes-Benz Stadium, Atlanta (participants TBD)",
  "Super Bowl LXIII at Allegiant Stadium, Las Vegas (participants TBD)".
- **`curated/season-anchors.json`** — 2028 SB LXII anchor filled (2028-02-13, verified, stadium source);
  2029 SB LXIII anchor note updated (host official; press-reported date recorded in prose; date fields stay blank).
- **`curated/flags.json`** — F05 rewritten (LXII date now verified with official source; LXIII exact date still
  unofficial; official-only source links retained); F22 detail extended (2028 window's right edge now anchored
  by the official LXII date; all other 2028/2029 inputs remain model output).
- **`research/EXECUTIVE-SUMMARY-ef8b5b30.md`** — appended a dated "Update 2026-11-05" section (original text
  untouched, per the append-not-overwrite convention); flows through `tools/build_extra.py` onto
  `extra/summary.html`.
- **`tools/verify_extra.py`** — `mercedesbenzstadium.com` (official venue) added to `APPROVED_DOMAINS`.
- **`scripts/build_site.py`** — repaired two generator drifts found during regeneration: the root nav was
  missing the "Official feeds & verification" (`extra/index.html`) link, and the calendar toolbar labels had
  drifted from the shipped "← Prev / Today / Next → / +2 days →" buttons. The generator now reproduces the
  merged site exactly.
- **Rebuilt:** `data/events-2027/2028/2029.json` (3 Super Bowl rows + basis-index renumbering only; verified/
  estimated counts unchanged), `data/derived/analysis.json` (unchanged values — the modelled dates already
  matched the official ones), `extra/data/calendar.json` (**exactly 3 changed days**: the three Super Bowls),
  `extra/data/vacation.json` (unchanged), `extra/flagged.html`, `extra/season-anchors.html`,
  `extra/summary.html`, root pages (nav/toolbar consistency + DATA_VERSION).
- **Recommendations unchanged and re-checked:** 2027 radio view best windows (Feb 1–13, 13 nights) unchanged;
  2028 best 3-week 2028-01-23..2028-02-12 (ends the day before the now-officially-dated Super Bowl LXII);
  2029 best 3-week 2029-01-21..2029-02-10.

## Irregularities / notes for review

1. Super Bowl LXIII (2029) exact date: announced (Feb 11, 2029) only via the NFL's social post as reported by
   press; no official page states it. Recorded in flag F05 and the 2029 anchor note; not entered as a date value.
2. Pro Bowl Games 2027 date: unofficial sources conflict (Feb 6 / Feb 9 / Jan 31); no official page found.
   Flag F21 unchanged.
3. Generator drift (nav link, toolbar labels) existed between `scripts/build_site.py` and the shipped root
   pages — earlier sessions had patched pages but not the template. Now aligned; flagged here for the record.
4. Outbound restrictions of earlier sessions prevented live checks; this session could reach official hosts via
   page fetch, so the LXI/LXII dates above are **freshly verified 2026-11-05**. No other inherited snapshot
   labels were changed.
