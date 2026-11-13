"""Shared statistics and modelling helpers for the NFL lines workstream.

Pure standard library: no numpy/scipy dependency, so every number in the published
outputs can be reproduced from the committed inputs on any machine.
"""
import math
import random

# ---------------------------------------------------------------- basic stats
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def norm_cdf(z):
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def percentile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None, n
    return sxy / math.sqrt(sxx * syy), n


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None, len(pairs)
    rx = ranks([p[0] for p in pairs])
    ry = ranks([p[1] for p in pairs])
    return pearson(rx, ry)


def fisher_ci(r, n, z=1.959963985):
    """95% confidence interval for a correlation coefficient (Fisher z)."""
    if r is None or n is None or n < 4 or abs(r) >= 1:
        return None, None
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo = math.tanh(zr - z * se)
    hi = math.tanh(zr + z * se)
    return lo, hi


# ---------------------------------------------------------------- scoring
def log_loss(probs, outcomes):
    """Binary log loss. outcomes: 1 = win, 0 = loss. Pushes excluded upstream."""
    if not probs:
        return None
    eps = 1e-6
    tot = 0.0
    for p, o in zip(probs, outcomes):
        p = min(max(p, eps), 1 - eps)
        tot += -(o * math.log(p) + (1 - o) * math.log(1 - p))
    return tot / len(probs)


def brier(probs, outcomes):
    if not probs:
        return None
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def expected_calibration_error(probs, outcomes, bins=10):
    """Equal-width binned ECE."""
    if not probs:
        return None
    buckets = [[] for _ in range(bins)]
    for p, o in zip(probs, outcomes):
        idx = min(bins - 1, max(0, int(p * bins)))
        buckets[idx].append((p, o))
    ece = 0.0
    n = len(probs)
    for b in buckets:
        if not b:
            continue
        mp = sum(x[0] for x in b) / len(b)
        mo = sum(x[1] for x in b) / len(b)
        ece += (len(b) / n) * abs(mp - mo)
    return ece


# ---------------------------------------------------------------- resampling
def bootstrap_ci(values, stat=mean, reps=2000, seed=20261113, alpha=0.05):
    """Percentile bootstrap confidence interval. Deterministic for a given seed."""
    vals = [v for v in values if v is not None]
    if len(vals) < 5:
        return None, None, None
    rng = random.Random(seed)
    n = len(vals)
    stats = []
    for _ in range(reps):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        s = stat(sample)
        if s is not None:
            stats.append(s)
    if not stats:
        return None, None, None
    lo = percentile(stats, alpha / 2)
    hi = percentile(stats, 1 - alpha / 2)
    return lo, hi, percentile(stats, 0.5)


def bootstrap_diff_ci(a, b, reps=2000, seed=20261113, alpha=0.05):
    """Bootstrap CI for mean(a) - mean(b) using paired resampling of the same indices."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 5:
        return None, None, None
    rng = random.Random(seed)
    n = len(pairs)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        ma = mean([pairs[i][0] for i in idx])
        mb = mean([pairs[i][1] for i in idx])
        if ma is not None and mb is not None:
            diffs.append(ma - mb)
    if not diffs:
        return None, None, None
    return (percentile(diffs, alpha / 2), percentile(diffs, 1 - alpha / 2),
            percentile(diffs, 0.5))


def benjamini_hochberg(pvalues):
    """Return BH-adjusted p-values (q-values), preserving input order."""
    items = [(p, i) for i, p in enumerate(pvalues) if p is not None]
    if not items:
        return [None] * len(pvalues)
    items.sort()
    m = len(items)
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        p, _idx = items[rank - 1]
        val = min(prev, p * m / rank)
        q[rank - 1] = val
        prev = val
    out = [None] * len(pvalues)
    for (p, i), val in zip(items, q):
        out[i] = val
    return out


def two_sided_p_from_bootstrap_ci(lo, hi):
    """A conservative p-value surrogate: 0 when the CI excludes zero."""
    if lo is None or hi is None:
        return None
    if lo > 0 or hi < 0:
        return 0.0
    return None


def sign_flip_test(diffs, reps=20000, seed=20261113):
    """Paired sign-flip (randomisation) test on the mean of `diffs`.

    Null hypothesis: the per-bet differences are symmetric about zero, i.e. the
    strategy carries no information the pre-registered baseline does not already
    carry. Under that null, flipping the sign of any subset of the differences
    leaves the distribution unchanged, so the p-value is read off the sign-flip
    distribution of the mean statistic.

    Returns (p_value, observed_mean, replicates_used). A positive difference
    means the strategy is better than the baseline.
    """
    import random as _random

    vals = [float(d) for d in diffs if d is not None]
    n = len(vals)
    if n < 5:
        return None, (sum(vals) / n if n else None), 0
    obs = sum(vals) / n
    rng = _random.Random(seed)
    total = 0.0
    count = 0
    for _ in range(reps):
        s = 0.0
        for v in vals:
            s += v if rng.random() < 0.5 else -v
        if abs(s / n) >= abs(obs) - 1e-15:
            count += 1
    # add-one correction keeps the p-value strictly positive
    p = (count + 1) / (reps + 1)
    return p, obs, reps


# ---------------------------------------------------------------- betting maths
def american_to_decimal(odds):
    """American odds (-110) to decimal (1.909)."""
    if odds is None:
        return None
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)
    return 1.0 + odds / 100.0


def decimal_to_implied(decimal):
    return 1.0 / decimal if decimal else None


def american_to_implied(odds):
    d = american_to_decimal(odds)
    return decimal_to_implied(d) if d else None
