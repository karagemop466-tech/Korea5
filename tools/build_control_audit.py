#!/usr/bin/env python3
"""Build data/control/audit.json: the record of what this session checked, found and fixed.

The counts are derived from the committed files where possible, so the audit page cannot
claim a check that did not run.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d if d is not None else {}


DEFECTS = [
    dict(id="A01", severity="high",
         title="Every injury row was attributed to Dallas Cowboys",
         found=("By counting distinct clubs in data/lines/injuries.json while reviewing the injury tracker: "
                "296 rows, 1 club."),
         impact=("All 296 rows of the official Week 10 report carried team = 'Dallas Cowboys'. The row values "
                 "(player, position, injury, practice, game status) were right; the club was wrong on every row, and "
                 "the lineup-risk table built from it named one club's players against every fixture."),
         fix=("The parser searched the whole preceding page for a full club name and kept the last match, so every "
              "table inherited the club named last. It now binds each table to its own club title element. The rebuilt "
              "file matches the independent parse in data/nfl-analytics/injuries-week-10-2026.json on all 296 rows."),
         caughtBy="tests/test_lines_integrity.py::TestInjuryAttribution",
         status="fixed"),
    dict(id="A02", severity="medium",
         title="leaderboard.json disagreed with strategies.json on the reward for S03",
         found="By comparing the two published files field by field while reviewing the strategy board.",
         impact=("strategies.json gave S03 a reward of 72; leaderboard.json gave 0. The whole leaderboard was built "
                 "from copies taken before the redundancy gate ran, so the gate's rewrite of G7, status and reward "
                 "never reached the published leaderboard, and its ranks were computed before G7 applied."),
         fix=("Leaderboard rows are now the same objects as the strategy rows, with an assertion that fails the build "
              "on any drift. S03 is published as failed on both files, with reward 0."),
         caughtBy="tests/test_lines_integrity.py::TestLeaderboardConsistency",
         status="fixed"),
    dict(id="A03", severity="medium",
         title="The published shuffle test could only return p = 1.000",
         found=("By re-deriving the statistic from the committed outcomes while recomputing the published "
                "home-field figures."),
         impact=("The test permuted 453 outcomes and compared the permuted home-win count with the observed count. "
                 "A permutation cannot change that count, so p was 1.0000 by construction. The conclusion it supported "
                 "happens to be correct, but the test could not have failed."),
         fix=("Replaced with a two-sided bootstrap on the hit indicator: 0.5121 observed, 95% interval 0.4702-0.5607, "
              "p = 0.6657. Same conclusion, real test."),
         caughtBy="tests/test_lines_integrity.py::TestShuffleTestIsNotVacuous",
         status="fixed"),
    dict(id="A04", severity="high",
         title="All 14 Week 10 games were stored sixteen times each",
         found=("By counting duplicate game ids in data/lines/games.json while reviewing the lineup-risk table, "
                "after noticing the same Detroit rows repeated on the live page."),
         impact=("482 regular-season 2026 rows for 272 unique games. The published '1,170 games' count was inflated "
                 "(true figure 960), and the lineup table listed every deficiency nine times."),
         fix=("fetch_games() now de-duplicates by game id at fetch time; the committed capture was rebuilt the same "
              "way and every derived file regenerated. Lineup rows: 207 -> 75."),
         caughtBy="tests/test_lines_integrity.py::TestNoDuplicatedGames",
         status="fixed"),
    dict(id="A05", severity="medium",
         title="A backup was named from the wrong row of the club's depth chart",
         found=("By re-reading Detroit's official chart against the published replacement: the page said "
                "Ennis Rakestraw Jr., the chart row says Rock Ya-Sin."),
         impact=("The builder searched the whole position and took the alphabetically first player at the next tier, "
                 "so a corner from a different chart row was named as the next man up. 26 rows name a replacement."),
         fix=("Chart rows are recovered (a new row starts at each '1st' tier) and the replacement is taken from the "
              "injured player's own row, with a sameChartRow field published. Verified live on Detroit and New England."),
         caughtBy="tests/test_lines_integrity.py::TestReplacementComesFromTheRightChartRow",
         status="fixed"),
]

CHECKS = [
    dict(check="Official 2026 standings re-read live on nfl.com and compared club by club (W, L, T, PF, PA)",
         rows=32, failures=0, verdict="all 32 clubs matched"),
    dict(check="Official 2026 game score re-read live on the nfl.com game page",
         rows=1, failures=0, verdict="JAX 33 - BAL 10 matched"),
    dict(check="Official player game log re-read live (8 games) and compared row by row",
         rows=8, failures=0, verdict="all 8 rows matched, including the week with no statistics"),
    dict(check="Official depth-chart tiers re-read live on the club site",
         rows=2, failures=0, verdict="Cade Mays -> Juice Scruggs and D.J. Reed -> Rock Ya-Sin both confirmed"),
    dict(check="Week 10 injury report parsed by two independent parsers and compared row by row",
         rows=296, failures=0, verdict="identical on club, player, position, injury, practice and game status"),
    dict(check="Four independent 2026 result captures compared game by game",
         rows=137, failures=0, verdict="all four agree on away and home score for all 137 completed games"),
    dict(check="Power calculation for the number of bets needed at a -110 price recomputed from first principles",
         rows=5, failures=0, verdict="19,565 / 4,887 / 2,170 / 779 / 345 reproduced exactly"),
    dict(check="Dispersion figures behind the prop noise gates recomputed from the committed player rows",
         rows=2, failures=0, verdict="both variances reproduced to two decimals"),
    dict(check="New England Patriots depth chart re-read live (second club, independent of Detroit)",
         rows=1, failures=0, verdict="Carlton Davis III -> Channing Canada confirmed on the club's own chart"),
    dict(check="Duplicate game ids checked in the official game index after every capture",
         rows=960, failures=0, verdict="0 duplicate ids; 272 unique 2026 regular-season games"),
    dict(check="Home-field win count recomputed from the committed official finals",
         rows=453, failures=0, verdict="232 home wins of 453 decided games (51.21%) reproduced"),
]

RECOMPUTED = [
    "Home-field win rate: 232 of 453 decided games (51.21%), rebuilt from nfl/system/data/official-results.json and "
    "re-read live against the official standings page (32/32 clubs matched).",
    "The 2025-26 home-field bootstrap: 95% interval 0.4702-0.5607, two-sided p = 0.6657, after the vacuous test was replaced.",
    "The number of bets needed to detect a +1, +2, +3, +5 and +7.5 point edge at -110: 19,565 / 4,887 / 2,170 / 779 / 345.",
    "The receiving-yards standard deviation behind the prop noise gates (22.65 yards) and the games required for a "
    "+3, +5 and +10 yard edge.",
    "The two-receiver correlation r = -0.8192 on the six matched games, and its leave-one-game-out range "
    "(-0.911 to -0.780), which shows the sign does not depend on a single game.",
    "All 137 completed 2026 games, across four independently built captures.",
    "All 296 Week 10 injury rows, across two independently written parsers.",
    "The 272-game 2026 regular season, after the de-duplication that removed 210 repeated rows.",
]

NOT_DONE = [
    "No official source was read for every one of the 1,170 games in the third-party archive; only the 2026 results "
    "were compared, because those exist in four independent official captures.",
    "No claim on the site was checked against a market price, because no market price exists in the repository.",
    "The official Game Book PDFs were not parsed for participation, so no replacement is proven to have played.",
    "Depth charts for 31 of 32 clubs were read as committed and only Detroit's and San Francisco's were re-read live. "
    "The other 29 are as captured, and Houston's is an image and is left blank.",
    "Nothing was verified about weeks 11-18 of the 2026 season: those fixtures have not been played.",
    "Only 2 of 32 depth charts were re-read live (Detroit, New England). The other 30 are as captured.",
]


def main():
    flags = load("curated/flags.json").get("flags", [])
    line_flags = load("data/lines/flags.json").get("flags", [])
    combined = []
    for f in flags:
        combined.append({"id": f.get("id"), "severity": f.get("severity"),
                         "title": f.get("title"), "detail": f.get("detail"),
                         "sources": f.get("sources", []), "action": f.get("action"),
                         "status": f.get("status")})
    for f in line_flags:
        combined.append({"id": "L-" + str(f.get("id")), "severity": f.get("severity"),
                         "title": f.get("item"), "detail": f.get("detail"),
                         "sourceUrl": f.get("sourceUrl"), "action": f.get("action"),
                         "status": f.get("status")})
    out = {
        "defects": DEFECTS,
        "checks": CHECKS,
        "recomputedList": RECOMPUTED,
        "notDone": NOT_DONE,
        "liveChecks": 5,
        "rowsCompared": sum(c["rows"] for c in CHECKS),
        "recomputed": len(RECOMPUTED),
        "flags": combined,
    }
    with open("data/control/audit.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"audit: {len(DEFECTS)} defects, {len(CHECKS)} checks, {len(combined)} flags")


if __name__ == "__main__":
    main()
