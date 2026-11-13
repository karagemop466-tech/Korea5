# Executive Summary — NFL Line Origination, Strategy & Decision-Support Suite

**As of 2026-11-13 (Week 10 of the 2026 NFL season)** · session `arena-65332583` · every number below is sourced on the site; derived numbers are labelled MODEL OUTPUT.

## The important details

1. **The data pipeline is live and verified.** Official NFL.com injury report (296 rows / 14 games), standings (32 teams), and 137 game results are parsed from committed source snapshots (sha256-tracked) into row-level tables where **every row links to its official page**. Club depth charts (869 rows, 1st–5th strings) come from 30 of 32 club sites. Two gaps are blank and flagged, never inferred: **Texans publish their depth chart as an image (F33)** and **Panthers' depth page is unreachable (F34)**.

2. **We originate our own lines.** A transparent least-squares margin model (fit on Weeks 1–9, Week 10 held out) plus documented injury weights produced a full Week-10 board. Its first out-of-sample test — **WAS @ NYG: model NYG −2.2, final Commanders 24–21** — was a wrong-side, 5.2-point error (F42). One game proves nothing; validation gate G4 requires 100+ graded picks before rewards.

3. **Market comparison exists but is labelled honestly.** 13 of 14 games have DraftKings spread/total/moneyline via ESPN's partner feed (trusted secondary, **not** official league data — F35). Largest model-vs-market edges: JAX/TEN (+12.8 pts on the home side), SF/DAL (+6.7), CAR/NO (+6.1). The biggest edges are blowout-driven and should be treated with suspicion until calibrated.

4. **Injury/deficiency tracking answers the depth question.** The Week-10 tracker names every unavailable player, their depth string, and the named replacement where the club chart allows: e.g., DET loses **C1 Cade Mays → 2nd-string Juice Scruggs** and **CB1 D.J. Reed → 2nd-string Rock Ya-Sin**; NE loses **C1 Ben Brown, CB1 Carlton Davis III, RB1 TreVeyon Henderson**; SEA plays without **QB1 Sam Darnold (named out by NFL.com news)**. 96 deficiency rows, with 2nd/3rd/4th-string replacements called out on offense and defense.

5. **Strategy research is registered, gated and honest about what it does not know.** Seven signals, five strategies (singles, cross-game parlays, same-game parlays, player-prop combos), and **seven validation gates** (pre-registration lock, verified-inputs-only, parameter disclosure, n≥100 calibration, bootstrap CI + CLV skill test, exposure caps, correlation audit). Correlation values are published as **flagged estimates** (Q10/F41) with an explicit estimator and a conservative rho floor until measured.

6. **Luck is removed by construction.** The leaderboard scores shrunk ROI (k=25), 95% bootstrap intervals, winsorized outliers, CLV blend, and process gates — never raw ROI. Rewards are proposals pending an owner decision (Q11) and cannot be paid to strategies whose skill CI includes zero.

7. **Decision support is first-class.** 18 requirements (R1–R18), 20 decision-prerequisite questions (Q1–Q20, with have/missing/blocks/discovery), and 15 reviewable suggestions (S1–S15) with a choose-before-implementing workflow. No suggestion is executed automatically.

## Open items that block sharp decisions

| Blocker | Question | Discovery path |
|---|---|---|
| No verified player-prop market | Q5 | S4 (odds snapshots incl. props) |
| No empirical correlation values | Q10 | S5 (correlation job, needs ≥50 samples) |
| No closing-line history | Q17 | S4 |
| Reward budget/eligibility unset | Q11 | owner decision (defaults proposed) |
| CAR/HOU depth strings unverified | Q8 | F33/F34 — manual review links published |

## Where things live

* Site: `nfl-analytics.html` (dashboard) → `lines.html`, `injuries.html`, `strategies.html`, `leaderboard.html`, `questions.html`, `suggestions.html`, `requirements.html`.
* Data: `data/nfl-analytics/*.json` (row-level, source-linked). Snapshots: `research/nfl-analytics-raw/` (sha256 in `fetch-report.json`).
* Verification: `research/nfl-week10-verification.md`. Flags: F33–F42 on the Flagged for Review pages.
* Reproduce: `scripts/fetch_nfl_analytics.py` (CI) → `scripts/parse_nfl_analytics.py` → `scripts/originate_lines.py` → `scripts/build_nfl_analytics.py`.
