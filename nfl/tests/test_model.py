#!/usr/bin/env python3
"""
NFL Lines Lab — tests. These enforce the pre-registered gates, not just the code.

Run: python3 -m unittest discover -s nfl/tests -v     (from the repository root)
"""
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from nfl import model as M  # noqa: E402


class TestNoLeakage(unittest.TestCase):
    """G2: a game's features must never contain information from that game or later."""

    def setUp(self):
        self.games = M.load_games("nfl/raw/samples", list(range(2016, 2027)))
        self.assertGreater(len(self.games), 100, "sample games missing")
        inj = M.load_injuries("nfl/raw/samples", list(range(2016, 2027)))
        dep = M.load_depth("nfl/raw/samples", list(range(2016, 2027)), {})
        sn = M.load_snaps("nfl/raw/samples", list(range(2016, 2027)))
        self.games = M.build_signals(self.games, inj, dep, sn, M.LineupIndex(dep, sn, inj))

    def test_elo_is_pregame(self):
        """Truncating later games must not change any earlier game's Elo features."""
        full = {g["game_id"]: dict(g["s"]) for g in self.games}
        cut = self.games[: len(self.games) // 2]
        inj = M.load_injuries("nfl/raw/samples", list(range(2016, 2027)))
        dep = M.load_depth("nfl/raw/samples", list(range(2016, 2027)), {})
        sn = M.load_snaps("nfl/raw/samples", list(range(2016, 2027)))
        part = M.build_signals([dict(g) for g in cut], inj, dep, sn, M.LineupIndex(dep, sn, inj))
        for g in part:
            for k in ("elo_home", "elo_away", "elo_diff", "form_home", "form_away"):
                self.assertEqual(g["s"].get(k), full[g["game_id"]].get(k),
                                 f"{k} changed for {g['game_id']} when future games were removed")

    def test_result_not_a_feature(self):
        feats = M.FEATURES + M.STRENGTH_FEATURES
        for bad in ("result", "home_score", "away_score", "margin"):
            self.assertNotIn(bad, feats)

    def test_walk_forward_ignores_future_seasons(self):
        recs = M.walk_forward(self.games, [self.games[-1]["season"]])
        self.assertTrue(recs, "no walk-forward records produced")
        last = max(r["season"] for r in recs)
        for r in recs:
            self.assertEqual(r["season"], last)


class TestGates(unittest.TestCase):
    def test_logloss_and_skill(self):
        self.assertAlmostEqual(M.logloss(0.5, 1), 0.6931, places=3)
        recs = [{"p": 0.5, "y": 1, "game_id": "a"}, {"p": 0.5, "y": 0, "game_id": "b"}]
        base = {"a": 0.5, "b": 0.5}
        s = M.scores(recs, base)
        self.assertEqual(s["skill"], 0.0)

    def test_cholesky_and_copula(self):
        I2 = [[1.0, 0.0], [0.0, 1.0]]
        joint = M.gauss_copula_joint([0.5, 0.5], I2)
        self.assertAlmostEqual(joint, 0.25, delta=0.02)
        C = [[1.0, 0.6], [0.6, 1.0]]
        self.assertGreater(M.gauss_copula_joint([0.6, 0.6], C), M.gauss_copula_joint([0.6, 0.6], I2),
                           "positive correlation must raise the joint probability")

    def test_pearson_and_ci(self):
        xs = list(range(50))
        ys = [x * 2 for x in xs]
        self.assertAlmostEqual(M.pearson(xs, ys), 1.0, places=6)
        self.assertIsNone(M.pearson([1, 1, 1], [1, 2, 3]))

    def test_deflation_rejects_pure_noise(self):
        """A model fitted on shuffled labels must not clear the null."""
        games = M.load_games("nfl/raw/samples", list(range(2016, 2027)))
        inj = M.load_injuries("nfl/raw/samples", list(range(2016, 2027)))
        dep = M.load_depth("nfl/raw/samples", list(range(2016, 2027)), {})
        sn = M.load_snaps("nfl/raw/samples", list(range(2016, 2027)))
        games = M.build_signals(games, inj, dep, sn, M.LineupIndex(dep, sn, inj))
        seasons = sorted({g["season"] for g in games if g["complete"]})[1:]
        base = M.naive_prior(games, seasons, seasons)
        rng = random.Random(7)
        for g in games:
            if g["complete"]:
                g["result"] = rng.randint(0, 1)
        recs = M.walk_forward(games, seasons)
        obs = M.scores(recs, base)["skill"]
        d = M.deflate(games, seasons, base, obs, N=8, K=5)
        self.assertFalse(d["passed"], f"noise cleared deflation (obs={obs}, p95={d['p95']})")


class TestLabels(unittest.TestCase):
    def test_every_field_has_a_rule_and_status(self):
        cat = json.load(open("nfl/labels.json", encoding="utf-8"))
        for f in cat["fields"]:
            self.assertIn(f["status"], ("verified", "derived", "unknown"), f["id"])
            self.assertTrue(f["rule"], f["id"])
            if f["status"] in ("verified", "derived"):
                self.assertIn(f["source"], cat["meta"]["sources"], f["id"])
            else:
                self.assertIsNone(f["source"], f["id"])


class TestQuestions(unittest.TestCase):
    def test_questions_have_all_resolution_fields(self):
        sys.path.insert(0, "nfl")
        import analyze
        for q in analyze.QUESTIONS:
            for k in ("id", "question", "have", "missing", "impact", "how", "owner", "blocks"):
                self.assertTrue(q.get(k), f"{q['id']} missing {k}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
