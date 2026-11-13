#!/usr/bin/env python3
"""NFL Lines Lab — quantitative layer.

Reads only the committed official-source records in ``data/lab/`` and computes:

* dispersion of each tracked player/game outcome (the “luck” width),
* same-game correlations between outcomes, with a Fisher-z confidence interval,
* the number of observations needed before an apparent edge can be told apart from luck.

Nothing here is a claim about a betting edge: no market price, no line and no
settlement record exists in this repository, so no win rate, yield or edge is
computed or asserted. Every number is a property of the official game data.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- statistics
def mean(xs):
    return sum(xs) / len(xs)


def stdev(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n % 2:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    if den == 0:
        return None
    return num / den


def _betacf(a, b, x):
    tiny, eps, maxit = 1e-30, 3e-16, 300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t, df):
    if df <= 0:
        return None
    x = df / (df + t * t)
    return betai(df / 2.0, 0.5, x)


def fisher_ci(r, n, z=1.959963985):
    """95% confidence interval for a Pearson r using Fisher's z transform."""
    if r is None or n < 4:
        return None
    se = 1.0 / math.sqrt(n - 3)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    lo = math.tanh(zr - z * se)
    hi = math.tanh(zr + z * se)
    return [lo, hi]


def r_p_value(r, n):
    if r is None or n < 4:
        return None
    df = n - 2
    t = r * math.sqrt(df / (1 - r * r))
    return t_two_sided_p(abs(t), df)


def norm_ppf(p):
    """Acklam-style inverse normal CDF, adequate for reporting."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    elif p <= ph:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    # one Newton refinement
    e = 0.5 * math.erfc(-x / math.sqrt(2)) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def sample_size_for_edge(p0, p1, alpha=0.05, power=0.80):
    """Observations needed to separate p1 from p0 (one-proportion z test)."""
    if p1 <= p0:
        return None
    za = norm_ppf(1 - alpha / 2.0)
    zb = norm_ppf(power)
    num = (za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) ** 2
    return num / ((p1 - p0) ** 2)


# ---------------------------------------------------------------- inputs
logs = load("data/lab/player-logs-2026.json")
book = load("data/lab/gamebook-bills-vikings-2026-w9.json")
players = {p["name"]: p for p in logs["players"]}


def games_for(name, field):
    """Ordered (week, value) pairs for one player's played games."""
    out = []
    for g in players[name]["games"]:
        if not g["played"]:
            continue
        v = g.get(field)
        if v is None:
            continue
        out.append((g["week"], v, g))
    return out


PROPS = [
    ("Justin Jefferson receiving yards", "Justin Jefferson", "yds", "receiving yards"),
    ("Jordan Addison receiving yards", "Jordan Addison", "yds", "receiving yards"),
    ("Aaron Jones rushing yards", "Aaron Jones", "rushYds", "rushing yards"),
    ("Josh Allen passing yards", "Josh Allen", "passYds", "passing yards"),
]

dispersion = []
for label, name, field, unit in PROPS:
    vals = [v for _, v, _ in games_for(name, field)]
    sd = stdev(vals)
    dispersion.append({
        "prop": label,
        "unit": unit,
        "n": len(vals),
        "mean": round(mean(vals), 2),
        "stdev": round(sd, 2),
        "median": round(median(vals), 2),
        "min": min(vals),
        "max": max(vals),
        "range": max(vals) - min(vals),
        "cv": round(sd / mean(vals), 3),
        "source": players[name]["url"],
    })

# team points for the Vikings and Bills from the same official logs
for team, name in (("Minnesota Vikings team points", "Justin Jefferson"),
                   ("Buffalo Bills team points", "Josh Allen")):
    vals = [g["teamPts"] for g in players[name]["games"]]
    dispersion.append({
        "prop": team, "unit": "points", "n": len(vals),
        "mean": round(mean(vals), 2), "stdev": round(stdev(vals), 2),
        "median": round(median(vals), 2), "min": min(vals), "max": max(vals),
        "range": max(vals) - min(vals), "cv": round(stdev(vals) / mean(vals), 3),
        "source": players[name]["url"],
    })


def series(name, field):
    return {g["week"]: g[field] for g in players[name]["games"] if g["played"] and g.get(field) is not None}


def team_points(name):
    return {g["week"]: g["teamPts"] for g in players[name]["games"]}


def game_total(name):
    return {g["week"]: g["teamPts"] + g["oppPts"] for g in players[name]["games"]}


PAIRS = [
    ("Justin Jefferson receiving yards", "Justin Jefferson", "yds",
     "Jordan Addison receiving yards", "Jordan Addison", "yds",
     "Two same-team wide receivers in the same game — the most common two-leg prop structure."),
    ("Justin Jefferson receiving yards", "Justin Jefferson", "yds",
     "Aaron Jones rushing yards", "Aaron Jones", "rushYds",
     "Same-team skill positions: a receiving yard prop and a rushing yard prop in one game."),
    ("Jordan Addison receiving yards", "Jordan Addison", "yds",
     "Aaron Jones rushing yards", "Aaron Jones", "rushYds",
     "Same-team skill positions: second receiving yard prop against a rushing yard prop."),
    ("Justin Jefferson receiving yards", "Justin Jefferson", "yds",
     "Minnesota Vikings team points", None, None,
     "Player prop against the team scoring prop — the structure of a player-plus-team-total parlay."),
    ("Aaron Jones rushing yards", "Aaron Jones", "rushYds",
     "Minnesota Vikings team points", None, None,
     "Rushing yard prop against the team scoring prop."),
    ("Justin Jefferson receiving yards", "Justin Jefferson", "yds",
     "Minnesota Vikings game total", None, None,
     "Player prop against the over/under total for the same game."),
    ("Minnesota Vikings team points", None, None,
     "Minnesota Vikings game total", None, None,
     "Team scoring against the full game total — the dependence inside a single over/under market."),
    ("Josh Allen passing yards", "Josh Allen", "passYds",
     "Buffalo Bills team points", None, None,
     "Passing yard prop against the team scoring prop."),
]

PAIRS_DATA = {}


def get_series(spec_label, spec_name, field):
    if spec_label.endswith("team points"):
        return team_points("Justin Jefferson" if "Minnesota" in spec_label else "Josh Allen")
    if spec_label.endswith("game total"):
        return game_total("Justin Jefferson")
    return series(spec_name, field)


correlations = []
for a_label, a_name, a_field, b_label, b_name, b_field, why in PAIRS:
    sa = get_series(a_label, a_name, a_field)
    sb = get_series(b_label, b_name, b_field)
    weeks = sorted(set(sa) & set(sb))
    xs = [sa[w] for w in weeks]
    ys = [sb[w] for w in weeks]
    r = pearson(xs, ys)
    ci = fisher_ci(r, len(xs))
    p = r_p_value(r, len(xs))
    correlations.append({
        "a": a_label, "b": b_label, "n": len(xs),
        "weeks": weeks,
        "r": None if r is None else round(r, 4),
        "ci95": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        "pValue": None if p is None else round(p, 4),
        "ciIncludesZero": None if ci is None else bool(ci[0] <= 0 <= ci[1]),
        "pairNote": why,
        "sourceA": players[a_name]["url"] if a_name else players["Justin Jefferson"]["url"],
        "sourceB": players[b_name]["url"] if b_name else players["Josh Allen"]["url"],
    })

# ---------------------------------------------------------------- luck gates
BREAK_EVEN = {
    "-110 (standard moneyline price)": 110.0 / 210.0,
    "-105 (standard spread price)": 105.0 / 205.0,
    "50/50 (no vig)": 0.5,
}
sample_size = []
for label, p0 in BREAK_EVEN.items():
    for edge in (0.01, 0.02, 0.03, 0.05, 0.075):
        n = sample_size_for_edge(p0, p0 + edge)
        sample_size.append({
            "priceBasis": label,
            "breakEven": round(p0, 4),
            "trueWinRate": round(p0 + edge, 4),
            "edgeOverBreakEven": edge,
            "observationsNeeded": int(math.ceil(n)),
            "note": "Two-sided one-proportion z test, alpha = 0.05, power = 0.80, normal approximation.",
        })

# how many games of a player's own history are needed before a stated yardage
# advantage can be separated from the player's own week-to-week noise
noise_rows = []
for d in dispersion:
    if d["unit"] == "points" or d["n"] < 4:
        continue
    sd = d["stdev"]
    noise_rows.append({
        "prop": d["prop"],
        "stdev": d["stdev"],
        "gamesNeededForPlus3YardEdge": int(math.ceil((sd / 3.0) ** 2)),
        "gamesNeededForPlus5YardEdge": int(math.ceil((sd / 5.0) ** 2)),
        "gamesNeededForPlus10YardEdge": int(math.ceil((sd / 10.0) ** 2)),
        "note": "n >= (standard deviation / modelled edge)^2, so that the standard error of the mean falls below the modelled edge.",
    })

# how many games a correlation estimate needs before it can be distinguished
# from zero, for a range of true correlations
corr_power = []
for rho in (0.2, 0.3, 0.4, 0.5, 0.7):
    for n in (8, 17, 33, 65, 100, 200):
        z = 0.5 * math.log((1 + rho) / (1 - rho))
        se_null = 1.0 / math.sqrt(n - 3)
        # power of a two-sided Fisher-z test against rho = 0 at alpha = 0.05
        crit = 1.959963985
        ncp = z * math.sqrt(n - 3)
        power = (1.0 - 0.5 * (1 + math.erf((crit - ncp) / math.sqrt(2)))
                 + 0.5 * (1 + math.erf((-crit - ncp) / math.sqrt(2))))
        corr_power.append({
            "trueCorrelation": rho, "n": n,
            "powerVsZero": round(power, 3),
            "detectable": bool(power >= 0.80),
        })

analysis = {
    "meta": {
        "title": "NFL Lines Lab — dispersion, correlation and sample-size analysis",
        "inputs": ["data/lab/player-logs-2026.json", "data/lab/gamebook-bills-vikings-2026-w9.json"],
        "source": "All inputs are official NFL records committed under data/lab/ with their own source URLs.",
        "generatedUTC": "2026-11-13",
        "disclaimer": "These are properties of official game data. They are not probabilities of winning, not prices, and not evidence of an edge. No market or settlement data exists in this repository, so no win rate, yield, ROI or fair price is computed anywhere on this site.",
        "method": "Pearson r on matched game-level observations; 95% intervals from the Fisher z transform with se = 1/sqrt(n-3); two-sided p-values from the t distribution with n-2 degrees of freedom via the regularized incomplete beta function; sample sizes from the normal approximation to the one-proportion z test.",
    },
    "dispersion": dispersion,
    "correlations": correlations,
    "sampleSize": sample_size,
    "noiseGates": noise_rows,
    "correlationPower": corr_power,
}

with open("data/lab/analysis.json", "w", encoding="utf-8") as fh:
    json.dump(analysis, fh, indent=1)
    fh.write("\n")

print(f"dispersion rows: {len(dispersion)}")
print(f"correlation rows: {len(correlations)}")
for c in correlations:
    print(f"  r={c['r']} n={c['n']} ci={c['ci95']} p={c['pValue']} :: {c['a']} ~ {c['b']}")
print(f"sample-size rows: {len(sample_size)}; noise gates: {len(noise_rows)}")
for row in sample_size[:6]:
    print(f"  {row['priceBasis']} edge {row['edgeOverBreakEven']} -> n={row['observationsNeeded']}")
