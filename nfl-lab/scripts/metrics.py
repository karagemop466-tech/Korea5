"""Small, deterministic calculations for an authorized NFL research dataset.

This module deliberately performs no downloads and contains no NFL data. Callers must
provide an appropriately licensed, point-in-time dataset and preserve its provenance.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Sequence


def _probability(value: float, name: str = "probability") -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return value


def american_to_probability(odds: float) -> float:
    """Convert American odds to raw implied probability (still includes vig)."""
    odds = float(odds)
    if not math.isfinite(odds) or odds == 0:
        raise ValueError("American odds must be finite and non-zero")
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal return including returned stake."""
    odds = float(odds)
    if not math.isfinite(odds) or odds == 0:
        raise ValueError("American odds must be finite and non-zero")
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / -odds)


def fair_decimal_odds(probability: float) -> float:
    """Return no-margin decimal odds for a probability strictly between 0 and 1."""
    probability = _probability(probability)
    if probability in (0.0, 1.0):
        raise ValueError("fair decimal odds require a probability strictly between 0 and 1")
    return 1.0 / probability


def proportional_devig(american_prices: Sequence[float]) -> list[float]:
    """Normalize raw implied probabilities to sum to one (proportional method).

    This is one explicitly chosen de-vig method, not a claim that it is the unique
    fair-market estimator. Keep the original quotes and run sensitivity checks.
    """
    if len(american_prices) < 2:
        raise ValueError("at least two mutually exclusive outcomes are required")
    raw = [american_to_probability(price) for price in american_prices]
    total = sum(raw)
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("invalid implied-probability total")
    return [p / total for p in raw]


def expected_profit_per_unit(
    decimal_odds: float,
    probability_win: float,
    probability_push: float = 0.0,
) -> float:
    """Expected net profit for one unit staked, including push probability.

    A win returns ``decimal_odds`` units including the original stake, a loss loses
    one unit, and a push returns the stake (zero net profit). Voids and nonstandard
    parlay settlements need their own market-specific contract and are not inferred.
    """
    decimal_odds = float(decimal_odds)
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        raise ValueError("decimal odds must be finite and greater than 1")
    p_win = _probability(probability_win, "probability_win")
    p_push = _probability(probability_push, "probability_push")
    p_loss = 1.0 - p_win - p_push
    if p_loss < -1e-12:
        raise ValueError("win and push probabilities cannot sum above 1")
    p_loss = max(0.0, p_loss)
    return p_win * (decimal_odds - 1.0) - p_loss


def brier_score(predictions: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared probability error for binary outcomes; lower is better."""
    if len(predictions) != len(outcomes) or not predictions:
        raise ValueError("predictions and outcomes must have the same non-zero length")
    errors = []
    for prediction, outcome in zip(predictions, outcomes):
        p = _probability(prediction, "prediction")
        if outcome not in (0, 1, False, True):
            raise ValueError("binary outcomes must be 0 or 1")
        errors.append((p - int(outcome)) ** 2)
    return sum(errors) / len(errors)


def log_loss(predictions: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean binary log loss, clipping only exact 0/1 predictions for finite logs."""
    if len(predictions) != len(outcomes) or not predictions:
        raise ValueError("predictions and outcomes must have the same non-zero length")
    eps = 1e-15
    losses = []
    for prediction, outcome in zip(predictions, outcomes):
        p = min(1.0 - eps, max(eps, _probability(prediction, "prediction")))
        if outcome not in (0, 1, False, True):
            raise ValueError("binary outcomes must be 0 or 1")
        y = int(outcome)
        losses.append(-(y * math.log(p) + (1 - y) * math.log1p(-p)))
    return sum(losses) / len(losses)


def pearson_correlation(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Pearson correlation, or None when the paired data are insufficient/constant."""
    if len(x) != len(y) or len(x) < 2:
        return None
    xs = [float(v) for v in x]
    ys = [float(v) for v in y]
    if any(not math.isfinite(v) for v in xs + ys):
        raise ValueError("correlation inputs must be finite")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [v - mx for v in xs]
    dy = [v - my for v in ys]
    vx = sum(v * v for v in dx)
    vy = sum(v * v for v in dy)
    if vx <= 0.0 or vy <= 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(vx * vy)


def phi_correlation(outcomes_a: Sequence[int], outcomes_b: Sequence[int]) -> float | None:
    """Pearson/phi association between two paired binary settlement outcomes."""
    for value in list(outcomes_a) + list(outcomes_b):
        if value not in (0, 1, False, True):
            raise ValueError("binary outcomes must be 0 or 1")
    return pearson_correlation([int(v) for v in outcomes_a], [int(v) for v in outcomes_b])


def joint_probability(outcomes_a: Sequence[int], outcomes_b: Sequence[int]) -> float:
    """Observed probability that both paired binary events occur."""
    if len(outcomes_a) != len(outcomes_b) or not outcomes_a:
        raise ValueError("paired outcomes must have the same non-zero length")
    if any(v not in (0, 1, False, True) for v in list(outcomes_a) + list(outcomes_b)):
        raise ValueError("binary outcomes must be 0 or 1")
    return sum(bool(a) and bool(b) for a, b in zip(outcomes_a, outcomes_b)) / len(outcomes_a)


def bootstrap_mean_interval(
    values: Sequence[float],
    confidence: float = 0.95,
    replicates: int = 4000,
    seed: int = 0,
    clusters: Sequence[object] | None = None,
) -> tuple[float, float] | None:
    """Percentile bootstrap interval for a mean, optionally resampling whole clusters.

    Clustering by game or week is preferred when observations share an event. This is
    a descriptive interval helper, not a correction for model selection; the evaluation
    protocol must also account for multiple testing and use a locked out-of-sample set.
    Returns None when fewer than two independent observations/clusters exist.
    """
    vals = [float(v) for v in values]
    if any(not math.isfinite(v) for v in vals):
        raise ValueError("values must be finite")
    confidence = _probability(confidence, "confidence")
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")
    if replicates < 100:
        raise ValueError("replicates must be at least 100")
    if not vals:
        return None

    if clusters is None:
        units = [[v] for v in vals]
    else:
        if len(clusters) != len(vals):
            raise ValueError("clusters and values must have the same length")
        grouped: dict[object, list[float]] = defaultdict(list)
        for cluster, value in zip(clusters, vals):
            grouped[cluster].append(value)
        units = list(grouped.values())
    if len(units) < 2:
        return None

    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(replicates):
        chosen = [units[rng.randrange(len(units))] for _ in range(len(units))]
        sample = [value for unit in chosen for value in unit]
        samples.append(sum(sample) / len(sample))
    samples.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = samples[math.floor(alpha * (replicates - 1))]
    hi = samples[math.ceil((1.0 - alpha) * (replicates - 1))]
    return lo, hi
