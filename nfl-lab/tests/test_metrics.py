import importlib.util
import math
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "metrics.py"
SPEC = importlib.util.spec_from_file_location("nfl_metrics", MODULE)
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


class MetricsTests(unittest.TestCase):
    def test_american_conversions(self):
        self.assertAlmostEqual(metrics.american_to_probability(-110), 110 / 210)
        self.assertAlmostEqual(metrics.american_to_probability(150), 0.4)
        self.assertAlmostEqual(metrics.american_to_decimal(-110), 1 + 100 / 110)
        self.assertAlmostEqual(metrics.american_to_decimal(150), 2.5)
        with self.assertRaises(ValueError):
            metrics.american_to_probability(0)

    def test_fair_decimal_odds_require_interior_probability(self):
        self.assertAlmostEqual(metrics.fair_decimal_odds(0.4), 2.5)
        with self.assertRaises(ValueError):
            metrics.fair_decimal_odds(0.0)
        with self.assertRaises(ValueError):
            metrics.fair_decimal_odds(1.0)

    def test_proportional_devig_is_explicit_normalization(self):
        probabilities = metrics.proportional_devig([-110, -110])
        self.assertEqual(len(probabilities), 2)
        self.assertAlmostEqual(sum(probabilities), 1.0)
        self.assertAlmostEqual(probabilities[0], 0.5)
        with self.assertRaises(ValueError):
            metrics.proportional_devig([-110])

    def test_expected_profit_handles_push(self):
        self.assertAlmostEqual(metrics.expected_profit_per_unit(2.0, 0.5), 0.0)
        self.assertAlmostEqual(metrics.expected_profit_per_unit(2.0, 0.4, 0.2), 0.0)
        with self.assertRaises(ValueError):
            metrics.expected_profit_per_unit(2.0, 0.8, 0.3)

    def test_probability_scores(self):
        self.assertAlmostEqual(metrics.brier_score([0.8, 0.2], [1, 0]), 0.04)
        self.assertGreater(metrics.brier_score([0.8, 0.2], [1, 0]), 0.0)
        self.assertGreater(metrics.log_loss([0.8, 0.2], [1, 0]), 0.0)
        self.assertTrue(math.isfinite(metrics.log_loss([1.0, 0.0], [1, 0])))
        with self.assertRaises(ValueError):
            metrics.brier_score([1.2], [1])

    def test_binary_phi_and_joint_probability(self):
        a = [1, 1, 0, 0]
        b = [1, 0, 1, 0]
        self.assertAlmostEqual(metrics.phi_correlation(a, b), 0.0)
        self.assertAlmostEqual(metrics.joint_probability(a, b), 0.25)
        self.assertIsNone(metrics.phi_correlation([1, 1], [0, 1]))
        self.assertIsNone(metrics.pearson_correlation([1], [1]))

    def test_correlation_known_values(self):
        self.assertAlmostEqual(metrics.pearson_correlation([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(metrics.pearson_correlation([1, 2, 3], [6, 4, 2]), -1.0)
        self.assertIsNone(metrics.pearson_correlation([2, 2, 2], [1, 2, 3]))

    def test_bootstrap_is_reproducible_and_clustered(self):
        interval = metrics.bootstrap_mean_interval([0.0, 1.0, 1.0, 0.0], replicates=500, seed=7)
        self.assertIsNotNone(interval)
        self.assertEqual(interval, metrics.bootstrap_mean_interval([0.0, 1.0, 1.0, 0.0], replicates=500, seed=7))
        clustered = metrics.bootstrap_mean_interval(
            [0.0, 1.0, 0.5], replicates=500, seed=1, clusters=["g1", "g1", "g2"]
        )
        self.assertIsNotNone(clustered)
        self.assertIsNone(metrics.bootstrap_mean_interval([1.0, 2.0], clusters=["one", "one"]))


if __name__ == "__main__":
    unittest.main()
