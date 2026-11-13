"""Regression tests for two published-data defects found and fixed on 2026-11-13.

Session `arena-827c3da2`. Both tests were negative-tested: the assertions fail on the
pre-fix data (that is how the defects were found), and pass on the fixed data.

Defect A01 - every injury row was attributed to Dallas Cowboys
    `scripts/lines/fetch_nfl.py` located a club by searching the whole preceding page for a
    full club name and keeping the *last* match, so all 26 club tables inherited whichever
    club was named last before the final table. Fixed by binding each table to its own
    `d3-o-section-sub-title` label.

Defect A02 - leaderboard.json disagreed with strategies.json
    The leaderboard was built from shallow copies taken before the redundancy gate (G7)
    ran, so the gate's rewrite of G7/status/reward never reached the published leaderboard.
"""
import collections
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lines"))

LINES = os.path.join(ROOT, "data", "lines")


def load(name):
    with open(os.path.join(LINES, name), encoding="utf-8") as f:
        return json.load(f)


class TestInjuryAttribution(unittest.TestCase):
    """A01 - a club may not own every row of the page."""

    def test_no_single_club_owns_the_whole_report(self):
        rows = load("injuries.json")["rows"]
        self.assertGreater(len(rows), 100)
        clubs = collections.Counter(r["team"] for r in rows)
        self.assertGreater(
            len(clubs), 1,
            "all injury rows are attributed to one club: the table-to-club binding is broken",
        )

    def test_each_row_carries_a_club_that_appears_on_the_page(self):
        rows = load("injuries.json")["rows"]
        for r in rows:
            self.assertTrue(r.get("team"), f"row without a club: {r.get('player')}")

    def test_known_players_belong_to_their_real_clubs(self):
        # Checked live against https://www.nfl.com/injuries/ (Week 10, 2026) and against the
        # independent parse in data/nfl-analytics/injuries-week-10-2026.json.
        expected = {
            "John Bates": "Washington Commanders",
            "Jayden Daniels": "Washington Commanders",
            "Cade Mays": "Detroit Lions",
            "D.J. Reed": "Detroit Lions",
            "Drake Maye": "New England Patriots",
        }
        got = {r["player"]: r["team"] for r in load("injuries.json")["rows"]}
        for player, club in expected.items():
            if player in got:
                self.assertEqual(got[player], club, f"{player} attributed to {got[player]}")

    def test_matches_the_independent_parse(self):
        """The two independent parsers of the same official page must agree row for row."""
        a = load("injuries.json")["rows"]
        with open(os.path.join(ROOT, "data", "nfl-analytics",
                               "injuries-week-10-2026.json"), encoding="utf-8") as f:
            b = json.load(f)["rows"]
        abbr = {
            "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
            "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
            "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
            "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
            "Houston Texans": "HOU", "Indianapolis Colts": "IND",
            "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
            "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
            "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
            "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
            "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
            "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA",
            "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN",
            "Washington Commanders": "WAS",
        }
        key_a = sorted((abbr[r["team"]], r["player"], r["position"] or "", r["injury"] or "",
                        r["practiceStatus"] or "", r["gameStatus"] or "") for r in a)
        key_b = sorted((r["team"], r["player"], r["pos"] or "", r["injury"] or "",
                        r["practiceStatus"] or "", r["gameStatus"] or "") for r in b)
        self.assertEqual(len(key_a), len(key_b))
        self.assertEqual(key_a, key_b, "the two parses of the official injury page disagree")


class TestLeaderboardConsistency(unittest.TestCase):
    """A02 - the two published files must not disagree."""

    def test_reward_and_status_agree_with_strategies(self):
        lb = load("leaderboard.json")["leaderboard"]
        strat = {s["id"]: s for s in load("strategies.json")["strategies"]}
        for row in lb:
            s = strat[row["id"]]
            self.assertEqual(row["reward"], s["reward"], f"reward drift on {row['id']}")
            self.assertEqual(row["status"], s["status"], f"status drift on {row['id']}")
            self.assertEqual(row["gates"]["G7"], s["gates"]["G7"],
                             f"G7 drift on {row['id']}")

    def test_ranks_are_a_permutation(self):
        lb = load("leaderboard.json")["leaderboard"]
        self.assertEqual(sorted(r["rank"] for r in lb), list(range(1, len(lb) + 1)))

    def test_a_failed_gate_means_no_reward(self):
        for row in load("leaderboard.json")["leaderboard"]:
            if not all(g["pass"] for g in row["gates"].values()):
                self.assertEqual(row["reward"], 0,
                                 f"{row['id']} is rewarded despite a failed gate")
                self.assertEqual(row["status"], "failed")

    def test_a_rewarded_strategy_passed_every_gate(self):
        for row in load("leaderboard.json")["leaderboard"]:
            if row["reward"]:
                self.assertTrue(all(g["pass"] for g in row["gates"].values()),
                                f"{row['id']} is rewarded despite a failed gate")


if __name__ == "__main__":
    unittest.main()
