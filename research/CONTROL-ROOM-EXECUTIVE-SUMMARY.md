# Executive summary — NFL research programme

**Session `arena-827c3da2` · 2026-11-13 · branch `arena/827c3da2-korea5`**

Scope: every NFL surface in this repository (`lines/`, `lab/`, `nfl-lab/`, `nfl/`, `nfl/system/`, `lines-lab/`,
`strategy-lab/`, `nfl-intel*`, `nfl-analytics*`), reviewed line by line against official sources, with the results
merged into one decision register, one suggestion review board and one evidence ledger at `control/`.

Live site: <https://karagemop466-tech.github.io/Korea5/control/index.html>

---

## 1. The one-paragraph answer

The programme can measure things and cannot yet bet on them. It holds **457 official NFL finals** (272 from 2025,
185 from 2026), the **complete official Week 10 injury report** (296 rows across 26 clubs), **32 club depth charts**
(31 parse), and **1,170 official game records** with box scores. It holds **no market price and no settled bet**, so
**no win rate, yield, edge or fair price is published anywhere**, and every leaderboard is deliberately empty. The
strongest positive result in the whole programme is a model that is **not distinguishable from luck**
(log-loss improvement over its baseline t = 1.48, 95% bootstrap interval −0.005 to +0.073, ~182 paired games needed).
That is the correct finding, and it is the reason the gate design exists.

## 2. What was found in the review — three published defects

All three had passed every existing verifier. Each is now fixed, tested, and published on the audit page and the
combined flag register. Naming them is the point: a verifier that cannot fail is not a verifier.

| ID | Defect | How it was found | Impact |
|---|---|---|---|
| **A01** | Every one of the 296 injury rows was attributed to *Dallas Cowboys* | Counting distinct clubs in `data/lines/injuries.json`: 296 rows, 1 club | The lineup-risk table named one club's players against every fixture |
| **A02** | `leaderboard.json` and `strategies.json` disagreed: S03 showed reward 72 in one file and 0 in the other | Comparing the two published files field by field | Ranks were computed before the redundancy gate ran |
| **A03** | The published shuffle test could only return p = 1.000 | Re-deriving the statistic from the committed outcomes | Permuting outcomes cannot change the home-win count; the comparison tied on every draw |

**Fixes.** A01: each club table is bound to its own club title element; the rebuilt file now matches an independently
written parser on all 296 rows. A02: leaderboard rows are the same objects as the strategy rows, with a build-time
assertion against drift. A03: replaced with a two-sided bootstrap (0.5121 observed, 95% CI 0.4702–0.5607, p = 0.6657)
that reaches the same conclusion with a test that can fail.

**Enforcement.** `tests/test_lines_integrity.py` (12 tests) fails the build on all three. Each was negative-tested:
reintroducing the defect produces a named failure. `tools/verify_control.py` adds 349 checks over the new pages.

## 3. What was verified live, this session

| Check | Rows | Result |
|---|---|---|
| Official 2026 standings on nfl.com, club by club (W, L, T, PF, PA) | 32 | **32/32 matched** |
| Official game page (Jaguars at Ravens, 2026 Week 9) | 1 | **JAX 33 – BAL 10 matched** |
| Official player log (Justin Jefferson, 8 games) | 8 | **8/8 matched**, including the week with no statistics |
| Official depth-chart tiers (Detroit) | 2 | **Cade Mays → Juice Scruggs, D.J. Reed → Rock Ya-Sin confirmed** |
| Week 10 injury report, two independent parsers | 296 | **identical** on club, player, position, injury, practice, game status |
| Four independent 2026 result captures, game by game | 137 | **all four agree** on both scores for all 137 completed games |
| Bets needed at −110 recomputed from first principles | 5 | **19,565 / 4,887 / 2,170 / 779 / 345 reproduced exactly** |
| Prop dispersion behind the noise gates | 2 | **22.65 yards and 31.15 yards reproduced** |
| Home-field win count from official finals | 453 | **232 of 453 (51.21%) reproduced** |

## 4. Decisions that block progress — six, and one dominates

Sixteen decisions were merged from **107 question rows across five registers**. Six are blocking. Eight register rows
were deliberately *not* promoted to a decision; they are listed with the reason, so the merge can be audited.

| ID | Decision | Registers | What is missing |
|---|---|---|---|
| **D-PRICE** | Which market price do we compare against, and may we cite it? | 11 | A licensed, timestamped feed. **No official NFL page publishes odds** (regex probe: zero hits) |
| **D-SKILL** | How many settled bets before "skill", and what correction? | 7 | Settled bets. Zero strategies have 100 settled bets against a stored price |
| **D-REWARD** | Money, honour scoreboard, or paper points — and is it lawful in BC? | 6 | A written owner decision and a legal check |
| **D-TESTS** | Which closing-line archive is legitimate for back-testing? | 5 | The provenance of the only archive present |
| **D-PROPS** | Which source supplies prop lines, and how is a dead leg settled? | 6 | Any prop price |
| **D-DEPTH** | Where do verified 1st/2nd/3rd/4th string charts come from? | 11 | Snap counts, to prove who actually replaced whom |

**Why D-PRICE dominates.** Without a price there is no settlement; without settlement there is no win rate, no yield
and no closing-line value. Every monetary claim on every one of the nine sections is blocked by this single row.

## 5. Strategies — 55 rows, 6 labs, 0 validated

The brief asks for singles, parlays and player-prop combinations, each passing validation gates, with luck removed.
The honest state:

* **55 strategy rows** exist across six labs, using six different gate vocabularies (G1–G7, G0–G9, G1–G10, and three
  one-off sets). A strategy can pass in one lab and fail in another for reasons unrelated to the strategy.
* **Three rows carry a paper reward**, all from one lab and one pipeline. Their rewards are leaderboard points defined
  by that lab; they are not money and are not comparable with anything else.
* **Zero rows are certified as skill-based.** The three rewarded rows belong to a lab that scores at a *declared*
  −110 reference price, which is a convention, not a market quote.
* **Pars and player props lose.** The measured prop combinations and parlays in the lines lab show negative ROI
  (−0.49, −0.71, −0.35) and fail 3–4 of the 7 gates, which is what a correlated parlays dataset should show if the
  correlation is priced badly by naive multiplication.

### Measured correlations (the numbers that do survive scrutiny)

| Relationship | Value | n | Interval |
|---|---|---|---|
| Two legs on the **same player**, one game | φ = **+0.575** | 11,446 | 0.563 – 0.587 |
| Two legs on **different players**, one game | φ = **+0.067** | 184,915 | 0.062 – 0.071 |
| Game total × model moneyline | ρ = **−0.047** | 681 | — |
| Margin × total (1999–2025) | r = **+0.020** | 6,967 | — |
| Receiving yards × receptions | r = **+0.817** | 4,468 | 0.807 – 0.827 |
| Two same-team receivers (2026, 6 matched games) | r = **−0.819** | 6 | −0.980 – −0.023 |

The last row is the cautionary one: on six games it reads as a strong *negative* relationship, and on 11,446 pairs the
same-player relationship reads strongly *positive*. They answer different questions. Quoting either alone would
mislead. Recorded as suggestion CS-10.

## 6. Injuries and depth deficiency — the brief's specific ask

The brief asks the system to know when a 2nd, 3rd or 4th string player must replace a starter, on both sides of the
ball. What exists:

* The **official weekly report**, by club: 296 rows, 26 clubs reporting, captured with its timestamp and a per-row
  source URL. Out / Doubtful / Questionable and practice participation are separated, because they are different facts.
* **32 club depth charts**, 31 parsing. Houston publishes an image and is left blank rather than transcribed.
* **165 next-man-up rows**, 71 of which name a specific replacement from the club's own chart, and 71 of which are
  verified starters marked out. Example, verified live on Detroit's official chart today:
  **Cade Mays (C, 1st) → Juice Scruggs (2nd)** and **D.J. Reed (CB, 1st) → Rock Ya-Sin (2nd)**.
* **What is missing:** a snap count. Nothing in the repository proves the replacement actually played. The site says
  "projected replacement" and flags the gap (F-series, D-DEPTH) rather than implying it was measured.
* **A published limitation:** the single Week 10 snapshot is applied to every unplayed 2026 fixture, so 69 of 165 rows
  sit against a game weeks away. Published with the label (FL-16, CS-05), not filtered away.

## 7. Suggestions — twelve proposals, each with options and a default

The brief asks for a dedicated section where someone can review suggestions and choose a path before anything is
built. Thirteen registers already held suggestions in six different review vocabularies; they are merged into
**12 proposals**, each with **three or more options**, the cost of each, and a recommended default. Nothing is
implemented by being listed.

The five that matter most, in order:

1. **CS-01** Make the Control Room the entry point and label the other nine sections as evidence stores. *(Recommended:
   publish and leave the rest intact. Cheap, reversible, discards no other session's work.)*
2. **CS-02** Either license a price feed or rename the pages so they cannot be read as a betting recommendation.
   *(Recommended: license. It is the only option that unlocks any gate.)*
3. **CS-03** Freeze one gate set across the three strategy labs. *(Recommended: adopt one, publish a crosswalk so no
   existing result is invalidated.)*
4. **CS-06** Run the cross-surface consistency checks on every commit. *(Recommended: yes — this is what would have
   caught A01–A03.)*
5. **CS-04** Publish an official snap-count join so "next man up" is measured, not inferred from a chart.

## 8. What the site now does

`control/` — nine pages, one dashboard, every table row carrying its source:

| Page | What it answers |
|---|---|
| Overview | The short answer to five questions, seven headline tiles, the six blocking decisions, the recommended path |
| Decisions | 16 decisions with what we have, what is missing, how it closes, and the exact register rows merged |
| Suggestions | 12 proposals × 3+ options, selectable in the browser and exportable as JSON; nothing is submitted |
| Evidence | 22 datasets, row counts counted at build time, content hashes, and what each cannot tell you |
| Strategies | All 55 rows from all 6 labs side by side, with gate counts; 0 settled bets, 0 certified |
| Injuries & depth | The official report by club plus the next-man-up ledger with the chart tier and label |
| Audit | The three defects, how each was found, the fix, and the check that now catches it |
| Sources | Every source, official first, the one secondary source labelled |
| Flagged | All 76 flagged items with the official source that would settle each |

## 9. What is still unverified, stated plainly

* **No price, no settlement.** Nothing anywhere is graded, and no monetary claim is made.
* **The third-party archive's line columns** have no documented upstream source. Two labs use it and both publish the gap.
* **29 of 32 depth charts** were not re-read live this session; only Detroit's and San Francisco's were. The rest stand
  as captured.
* **Weeks 11–18 of 2026** are unplayed, so nothing about them is verified.
* **The 2026 season is 137 games complete** at capture. Every correlation resting on one partial season is labelled as
  such.
* **Weather** has no cited official archive anywhere in the repository, so it is not modelled and is listed as
  deliberately not merged rather than quietly dropped.

## 10. Recommendation

Answer **D-REWARD** in one line (paper points is already implemented), then answer **D-PRICE**. Those two unblock
everything else. Until D-PRICE has an answer, the correct posture of this programme is what it already publishes: a
research ledger with a negative result stated first, an empty leaderboard, and a decision register that says why.
