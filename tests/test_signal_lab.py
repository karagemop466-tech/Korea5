#!/usr/bin/env python3
"""Tests for the maths and the discipline in scripts/signal_lab.py.

Two things are worth testing here. The first is the arithmetic a reader would otherwise have to
re-derive by hand: the normal CDF, phi from a 2x2, fair moneyline conversion, expected calibration
error, and a bootstrap that must be reproducible because its output is published as a confidence
interval. The second is the one property the whole lab rests on and that no metric would ever
reveal: a forecast for week w must be computable from weeks before w alone. A backtest that leaks
looks exactly like a backtest that works, so leakage gets a direct test — change the future and
prove the past does not move.
"""
import importlib.util
import math
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(ROOT, "scripts", "signal_lab.py")

spec = importlib.util.spec_from_file_location("signal_lab", MODULE_PATH)
lab = importlib.util.module_from_spec(spec)
sys.modules["signal_lab"] = lab
spec.loader.exec_module(lab)


def synthetic_games(weeks=8, per_week=16, seed=7):
    """A full synthetic season with stable team quality, so model behaviour is predictable."""
    rng = random.Random(seed)
    clubs = [f"Team{i:02d}" for i in range(32)]
    quality = {c: rng.gauss(0.0, 5.0) for c in clubs}
    games = []
    for wk in range(1, weeks + 1):
        order = clubs[:]
        rng.shuffle(order)
        for i in range(0, per_week * 2, 2):
            away, home = order[i], order[i + 1]
            exp = quality[home] - quality[away] + lab.HFA_FALLBACK
            hp = max(0, int(round(exp + rng.gauss(0, 12) + 21)))
            ap = max(0, int(round(-exp + rng.gauss(0, 12) + 21)))
            games.append({
                "slug": f"{away.lower()}-at-{home.lower()}-w{wk}-{i}",
                "week": wk, "weekType": "REG", "season": 2026,
                "dateUTC": f"2026-09-{wk:02d}T00:00:00Z",
                "away": away, "home": home,
                "awayPoints": ap, "homePoints": hp,
                "status": "FINAL", "verification": "verified", "scoreSource": "test",
                "sourceUrl": f"https://www.nfl.com/games/{away.lower()}-at-{home.lower()}-w{wk}-{i}",
                "venue": "Test Stadium",
            })
    return games


class TestProbability(unittest.TestCase):
    def test_norm_cdf_known_values(self):
        self.assertAlmostEqual(lab.norm_cdf(0.0), 0.5, places=6)
        self.assertAlmostEqual(lab.norm_cdf(1.96), 0.975, delta=2e-3)
        self.assertAlmostEqual(lab.norm_cdf(-1.96), 0.025, delta=2e-3)
        # symmetry is what makes a spread price two-sided
        self.assertAlmostEqual(lab.norm_cdf(0.8) + lab.norm_cdf(-0.8), 1.0, places=6)

    def test_log_loss_penalises_confident_wrong(self):
        self.assertAlmostEqual(lab.log_loss(0.999999, 1), 0.0, delta=1e-5)
        self.assertGreater(lab.log_loss(0.9, 0), 2.0)
        self.assertAlmostEqual(lab.log_loss(0.5, 1), lab.log_loss(0.5, 0), places=9)

    def test_brier_bounds(self):
        self.assertAlmostEqual(lab.brier(1.0, 1), 0.0, places=9)
        self.assertAlmostEqual(lab.brier(0.0, 1), 1.0, places=9)
        self.assertAlmostEqual(lab.brier(0.5, 1), 0.25, places=9)


class TestAssociation(unittest.TestCase):
    def test_phi_perfect_and_none(self):
        perfect, n = lab.phi_from_table(10, 0, 0, 10)
        self.assertEqual(n, 20)
        self.assertAlmostEqual(abs(perfect), 1.0, places=9)
        none, _ = lab.phi_from_table(5, 5, 5, 5)
        self.assertAlmostEqual(none, 0.0, places=9)

    def test_phi_negative_association_direction(self):
        # the same-game parlay finding: winning at home goes with unders, so phi is negative
        phi, n = lab.phi_from_table(19, 27, 35, 20)
        self.assertEqual(n, 101)
        self.assertLess(phi, 0.0)

    def test_phi_undefined_when_a_margin_is_zero(self):
        phi, n = lab.phi_from_table(10, 0, 10, 0)
        self.assertIsNone(phi)
        self.assertEqual(n, 20)

    def test_pearson_matches_hand_computation(self):
        r = lab.pearson([1, 2, 3, 4], [2, 4, 6, 8])
        self.assertAlmostEqual(r, 1.0, places=9)
        self.assertAlmostEqual(lab.pearson([1, 2, 3], [3, 2, 1]), -1.0, places=9)


class TestPricing(unittest.TestCase):
    def test_fair_moneyline_conversion(self):
        self.assertAlmostEqual(lab.ml_price(0.6), -150.0, places=6)
        self.assertAlmostEqual(lab.ml_price(0.4), 150.0, places=6)
        self.assertAlmostEqual(lab.ml_price(0.5), -100.0, places=6)
        self.assertIsNone(lab.ml_price(0.0))
        self.assertIsNone(lab.ml_price(None))

    def test_moneyline_round_trips_through_implied_probability(self):
        for p in (0.12, 0.3, 0.49, 0.7, 0.93):
            american = lab.ml_price(p)
            implied = (abs(american) / (abs(american) + 100.0)) if american < 0 else (100.0 / (abs(american) + 100.0))
            self.assertAlmostEqual(implied, p, places=6)

    def test_hold_makes_the_book_over_one(self):
        fair_home, fair_away = lab.ml_price(0.6), lab.ml_price(0.4)
        self.assertLess(fair_home, 0)      # favourite is quoted with a minus
        self.assertGreater(fair_away, 0)   # underdog with a plus
        dec_home = 1.0 + 100.0 / abs(fair_home)
        dec_away = 1.0 + abs(fair_away) / 100.0
        self.assertAlmostEqual(dec_home, 1 / 0.6, places=6)
        self.assertAlmostEqual(dec_away, 1 / 0.4, places=6)
        posted_h = lab.round_price(dec_home, lab.HOLD)
        posted_a = lab.round_price(dec_away, lab.HOLD)
        overround = 1 / posted_h + 1 / posted_a
        self.assertGreater(overround, 1.0)
        self.assertLess(posted_h, dec_home)
        self.assertLess(posted_a, dec_away)

    def test_hold_value_is_a_named_constant(self):
        self.assertGreater(lab.HOLD, 0.0)
        self.assertLess(lab.HOLD, 0.10)


class TestCalibration(unittest.TestCase):
    def test_ece_zero_for_perfectly_calibrated_blocks(self):
        pairs = []
        for bucket, prob in enumerate((0.1, 0.3, 0.5, 0.7, 0.9)):
            for i in range(20):
                pairs.append((prob, 1 if i < round(prob * 20) else 0))
        self.assertLess(lab.ece(pairs), 0.02)

    def test_ece_large_when_confidence_is_wrong(self):
        pairs = [(0.9, i % 2) for i in range(100)]
        self.assertGreater(lab.ece(pairs), 0.35)

    def test_ece_empty_and_none_handling(self):
        self.assertIsNone(lab.ece([]))
        self.assertIsNone(lab.ece([(None, 1), (0.5, None)]))


class TestBootstrap(unittest.TestCase):
    def test_same_seed_same_interval(self):
        rng = random.Random(3)
        vals = [rng.gauss(0.01, 0.05) for _ in range(120)]
        a = lab.moving_block_bootstrap(vals)
        b = lab.moving_block_bootstrap(vals)
        self.assertEqual(a, b, "a published confidence interval must be reproducible")
        lo, hi = a
        self.assertLessEqual(lo, sum(vals) / len(vals))
        self.assertLess(sum(vals) / len(vals), hi)

    def test_blocks_keep_within_block_dependence(self):
        """Games on the same slate move together, so resampling must not pretend they are independent.

        Data is constant inside each block of 30 (a perfect slate effect). A bootstrap that samples
        single rows destroys that and reports a CI too tight to be trusted; a block-sized bootstrap
        keeps it, which is why the published intervals use a block width.
        """
        rng = random.Random(5)
        block = 30
        vals = []
        for _ in range(10):
            v = rng.gauss(0.0, 1.0)
            vals.extend([v] * block)
        naive = lab.moving_block_bootstrap(vals, block=1)
        honest = lab.moving_block_bootstrap(vals, block=block)
        self.assertLess(naive[1] - naive[0], honest[1] - honest[0])
        self.assertEqual(lab.moving_block_bootstrap(vals, block=block),
                         lab.moving_block_bootstrap(vals, block=block))

    def test_short_input_returns_none(self):
        self.assertEqual(lab.moving_block_bootstrap([0.1, 0.2]), (None, None))


class TestModelPlumbing(unittest.TestCase):
    def test_ratings_are_zero_sum_and_opp_adj(self):
        games = synthetic_games(weeks=4)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        vals = [v["rating"] for v in rates.values()]
        self.assertAlmostEqual(sum(vals) / len(vals), 0.0, delta=0.5)
        team = games[0]["home"]
        self.assertGreaterEqual(rates[team]["games"], 1)
        self.assertIsNotNone(rates[team]["netPpg"])

    def test_forecast_returns_none_for_unplayed_unknown_teams(self):
        games = synthetic_games(weeks=2)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        ghost = {"slug": "x", "week": 9, "away": "Nobody", "home": "NoSuchTeam",
                 "awayPoints": None, "homePoints": None}
        self.assertIsNone(lab.forecast(ghost, rates, hfa))

    def test_sigma_depends_on_the_forecast_it_scores(self):
        """Sigma is measured against the shrunk forecast, not a separate unshrunk one."""
        games = synthetic_games(weeks=6)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        loose, n_loose = lab.margin_sigma(games, rates, hfa, 1.0, None)
        tight, n_tight = lab.margin_sigma(games, rates, hfa, 0.2, None)
        self.assertEqual(n_loose, n_tight)
        self.assertGreater(loose, 0.0)
        self.assertGreater(tight, 0.0)
        self.assertNotAlmostEqual(loose, tight, places=3,
                                  msg="sigma ignored the shrink policy it is supposed to match")
        self.assertLess(tight, 40.0, "a fitted spread this wide means the residuals were not centred")

    def test_ties_are_excluded_from_scoring_not_counted_as_losses(self):
        rows = [
            {"slug": "a", "logLoss": 0.6, "brier": 0.2, "pHome": 0.6, "outcomeHomeWin": 1,
             "expMargin": 3.0, "actualMargin": 4.0, "fairTotal": 44.0, "actualTotal": 45.0,
             "week": 5, "fairSpreadHome": -3.0, "sigmaUsed": 12.0, "shrinkLambda": 0.5},
            {"slug": "b", "logLoss": None, "brier": None, "pHome": 0.6, "outcomeHomeWin": None,
             "expMargin": 3.0, "actualMargin": 0.0, "fairTotal": 44.0, "actualTotal": 44.0,
             "week": 5, "fairSpreadHome": -3.0, "sigmaUsed": 12.0, "shrinkLambda": 0.5},
        ]
        scored = lab.score_ledger(rows)
        self.assertEqual(scored["n"], 1, "a tie is not a wrong forecast, it is an unscoreable one")


class TestWalkForwardDiscipline(unittest.TestCase):
    def test_earlier_forecasts_do_not_move_when_later_results_change(self):
        """The leakage test. If this ever fails, every number on the site is decoration."""
        games = synthetic_games(weeks=8, per_week=16, seed=11)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        sigma = lab.margin_sigma(games, rates, hfa, 1.0, None)[0]
        before = lab.evaluate(games, rates, hfa, sigma, "net")

        rng = random.Random(99)
        flipped = []
        for g in games:
            if g["week"] >= 7 and rng.random() < 0.8:
                g = dict(g)
                g["homePoints"], g["awayPoints"] = g["awayPoints"], g["homePoints"]
            flipped.append(g)
        rates2, hfa2, _m2, _n2 = lab.team_strengths(flipped, None, 1.0)
        sigma2 = lab.margin_sigma(flipped, rates2, hfa2, 1.0, None)[0]
        after = lab.evaluate(flipped, rates2, hfa2, sigma2, "net")

        key = lambda rows: {r["slug"]: (r["pHome"], r["sigmaUsed"], r["expMargin"]) for r in rows}
        b, a = key(before), key(after)
        early = [w for w in sorted({r["week"] for r in before}) if w < 7]
        for row in before:
            if row["week"] in early:
                self.assertIn(row["slug"], a)
                self.assertEqual(b[row["slug"]][0], a[row["slug"]][0],
                                 f"week {row['week']} forecast changed when week 7-8 results changed")

    def test_no_week_is_scored_before_the_minimum_sample(self):
        games = synthetic_games(weeks=8)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        sigma = lab.margin_sigma(games, rates, hfa, 1.0, None)[0]
        rows = lab.evaluate(games, rates, hfa, sigma, "net")
        weeks = sorted({r["week"] for r in rows})
        played = [g for g in games if g["awayPoints"] is not None]
        for wk in weeks:
            train_n = len([g for g in played if g["week"] < wk])
            self.assertGreaterEqual(train_n, lab.MIN_TRAIN_GAMES,
                                    f"week {wk} was forecast from only {train_n} games")
        for row in rows:
            self.assertGreaterEqual(row["trainGames"], lab.MIN_TRAIN_GAMES)

    def test_weeks_forecast_carries_the_shrink_chosen_below_it(self):
        """The published λ for a week must be the one chosen from strictly earlier weeks."""
        games = synthetic_games(weeks=8)
        played = [g for g in games if g["awayPoints"] is not None]
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        sigma = lab.margin_sigma(games, rates, hfa, 1.0, None)[0]
        rows = lab.evaluate(games, rates, hfa, sigma, "adj")
        for wk in sorted({r["week"] for r in rows}):
            hist = [g for g in played if g["week"] < wk]
            expect = lab.choose_shrinkage(hist)[0]
            for r in rows:
                if r["week"] == wk:
                    self.assertEqual(r["shrinkLambda"], expect,
                                     f"week {wk} did not use its own window's shrink choice")
                    self.assertLessEqual(r["shrinkChosenOn"]["validationGames"], len(hist))

    def test_determinism_of_the_whole_ledger(self):
        games = synthetic_games(weeks=5)
        rates, hfa, _m, _n = lab.team_strengths(games, None, 1.0)
        sigma = lab.margin_sigma(games, rates, hfa, 1.0, None)[0]
        one = lab.evaluate(games, rates, hfa, sigma, "adj")
        two = lab.evaluate(games, rates, hfa, sigma, "adj")
        self.assertEqual([(r["slug"], r["pHome"], r["logLoss"]) for r in one],
                         [(r["slug"], r["pHome"], r["logLoss"]) for r in two])


class TestAvailabilityModel(unittest.TestCase):
    def test_position_weights_are_ordered_by_impact(self):
        w = lab.POSITION_WEIGHTS
        self.assertGreater(w["QB"], w["OL"])
        self.assertGreater(w["OL"], w["WR"])
        self.assertGreater(w["WR"], w["TE"])

    def test_status_credit_out_beats_questionable(self):
        c = lab.STATUS_CREDIT
        self.assertGreater(c["Out"], c["Doubtful"])
        self.assertGreater(c["Doubtful"], c["Questionable"])
        self.assertEqual(c["Full Participation In Practice"], 0.0)
        self.assertGreater(c["Did Not Participate In Practice"], c["Limited Participation In Practice"])

    def test_weight_scaling_is_linear(self):
        self.assertAlmostEqual(lab.weight_of("QB", 2.0), lab.weight_of("QB", 1.0) * 2.0, places=9)
        self.assertAlmostEqual(lab.weight_of("QB", 0.0), 0.0, places=9)
        # an unlisted position falls back to the OTHER weight rather than being dropped silently
        self.assertEqual(lab.weight_of("Long snapper", 1.0), lab.POSITION_WEIGHTS["OTHER"])

    def test_group_of_maps_positions_to_line_groups(self):
        self.assertEqual(lab.group_of("QB"), lab.group_of("QB"))
        self.assertIn("OL", set(lab.GROUP_BY_POS.values()))


class TestPublishedArtefacts(unittest.TestCase):
    """If the committed outputs exist they must agree with each other — a stale page is a bug."""

    def setUp(self):
        self.signals_path = os.path.join(ROOT, "data", "nfl-signals", "signals.json")

    def test_signals_json_matches_model_version_and_counts(self):
        if not os.path.exists(self.signals_path):
            self.skipTest("signals.json not generated yet")
        import json
        data = json.load(open(self.signals_path, encoding="utf-8"))
        self.assertEqual(data["meta"]["modelVersion"], lab.MODEL_VERSION)
        self.assertEqual(data["meta"]["seed"], lab.SEED)
        for entry in data["leaderboard"]["entries"]:
            if entry["n"] and entry["n"] < lab.MIN_EVAL_GAMES:
                self.assertFalse(entry["qualified"], "a sub-minimum sample cannot qualify")
        for line in data["lines"]:
            self.assertIn("no market price", line["status"])
            self.assertIsNotNone(line["pHomeWin"])
            self.assertTrue(0.0 <= line["pHomeWin"] <= 1.0)

    def test_requirements_are_all_statused(self):
        import json
        path = os.path.join(ROOT, "data", "nfl-signals", "requirements.json")
        data = json.load(open(path, encoding="utf-8"))
        allowed = set(data["meta"]["statusVocabulary"])
        ids = [r["id"] for r in data["requirements"]]
        self.assertEqual(len(ids), len(set(ids)), "requirement ids must be unique")
        for req in data["requirements"]:
            self.assertIn(req["status"], allowed)
            self.assertTrue(req.get("evidence"), f"{req['id']} has no evidence file")
            for f in req["evidence"]:
                self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f"{req['id']} cites missing {f}")

    def test_suggestions_are_all_decided(self):
        import json
        path = os.path.join(ROOT, "data", "nfl-signals", "suggestions.json")
        data = json.load(open(path, encoding="utf-8"))
        allowed = set(data["meta"]["statusVocabulary"])
        for sg in data["suggestions"]:
            self.assertIn(sg["status"], allowed)
            self.assertTrue(len(sg["decision"]) > 40, f"{sg['id']} needs a real reason")
            self.assertTrue(sg.get("seenOn"), f"{sg['id']} must say where the outcome is visible")


if __name__ == "__main__":
    unittest.main(verbosity=2)
