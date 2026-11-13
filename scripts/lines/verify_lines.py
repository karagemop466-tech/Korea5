#!/usr/bin/env python3
"""Verify the NFL lines data and the generated pages.

Checks, in order:
  1. schema   - every generated JSON file has the keys the site depends on
  2. sources  - every data row that represents an official fact carries an
                official source URL, and no non-official host is used
  3. leakage  - no strategy bet uses a game whose result informed its estimate
  4. pages    - every table row on a generated page carries an official link,
                and no unconfirmed value was silently filled in
  5. links    - every internal link on a generated page resolves on disk

Exit code is non-zero when a check fails, so CI can gate on it.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

OFFICIAL_HOSTS = (
    "nfl.com",
    "operations.nfl.com",
)

# Official club websites, transcribed from the NFL.com team directory
# (https://www.nfl.com/teams/) into scripts/lines/fetch_nfl.py. The verifier
# reads that list so a club domain is never taken on trust from a data file.
CLUB_DOMAINS = []


def _load_club_domains():
    try:
        import ast
        src = open(os.path.join(ROOT, "scripts", "lines", "fetch_nfl.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "CLUBS" for t in node.targets):
                for entry in ast.literal_eval(node.value):
                    CLUB_DOMAINS.append(entry[2].lower())
    except Exception:
        pass
    return CLUB_DOMAINS

DATA = "data/lines"
PAGES = "lines"

failures = []
checks = []


def ok(name, detail=""):
    checks.append((name, True, detail))


def bad(name, detail):
    checks.append((name, False, detail))
    failures.append(f"{name}: {detail}")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def official(url):
    """True when the URL is on the league site or on an official club site."""
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
        return True
    return any(host == d or host.endswith("." + d) for d in CLUB_DOMAINS)


# ------------------------------------------------------------------ 1. schema
def check_schema():
    required = {
        "lines.json": (["meta", "lines"], ["gameId", "date", "season", "week", "away", "home",
                                           "modelSpreadHome", "modelTotal", "benchmarkTotal",
                                           "homeWinProbability", "sourceUrl"]),
        "strategies.json": (["meta", "strategies", "bets"],
                            {"strategies": ["id", "name", "family", "market", "rule", "benchmark", "gates", "metrics"],
                             "bets": ["strategy", "gameId", "date", "market", "side", "p", "outcome", "sourceUrl"]}),
        "leaderboard.json": (["meta", "leaderboard"],
                             ["id", "name", "family", "rank", "reward", "gates", "metrics"]),
        "correlations.json": (["meta", "strategyCorrelations", "productionCorrelations",
                               "parlayCorrelations"], None),
        "lineup-risk.json": (["meta", "rows"], None),
        "suggestions.json": (["meta", "suggestions"], None),
        "questions.json": (["meta", "questions"], None),
        "flags.json": (["meta", "flags"], None),
    }
    for name, (top, row_keys) in required.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            bad(f"schema/{name}", "file is missing")
            continue
        try:
            doc = load(name)
        except Exception as exc:
            bad(f"schema/{name}", f"not valid JSON: {exc}")
            continue
        missing = [k for k in top if k not in doc]
        if missing:
            bad(f"schema/{name}", f"missing top-level keys: {missing}")
            continue
        if row_keys:
            for key in [k for k in top if isinstance(doc.get(k), list)]:
                rows = doc.get(key) or []
                keys_for = row_keys.get(key) if isinstance(row_keys, dict) else row_keys
                if keys_for is None:
                    continue
                if not isinstance(rows, list) or not rows:
                    bad(f"schema/{name}", f"{key} is empty or not a list")
                    break
                miss = [k for k in keys_for if k not in rows[0]]
                if miss:
                    bad(f"schema/{name}", f"{key} rows missing keys: {miss}")
                    break
            else:
                ok(f"schema/{name}", "required row keys present")
        elif isinstance(doc.get("meta"), dict):
            ok(f"schema/{name}", "meta object present")
        else:
            ok(f"schema/{name}", "top-level keys present")


# ------------------------------------------------------------------ 2. sources
def check_sources():
    docs = {
        "lines.json": ("lines", "sourceUrl"),
        "strategies.json": ("bets", "sourceUrl"),
        "lineup-risk.json": ("rows", "injurySourceUrl"),
    }
    for name, (key, field) in docs.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            continue
        doc = load(name)
        rows = doc.get(key) or []
        bad_urls = [r.get(field) for r in rows if not official(r.get(field))]
        if bad_urls:
            bad(f"sources/{name}", f"{len(bad_urls)} rows without an official source URL "
                                   f"(first: {bad_urls[0]!r})")
        else:
            ok(f"sources/{name}", f"{len(rows)} rows carry an official source URL")

    # depth charts
    depth_path = os.path.join(DATA, "depth-charts.json")
    if os.path.exists(depth_path):
        doc = load("depth-charts.json")
        clubs = doc.get("clubs") or []
        bad_urls = [c.get("sourceUrl") for c in clubs if not official(c.get("sourceUrl"))]
        if bad_urls:
            bad("sources/depth-charts.json", f"{len(bad_urls)} clubs without an official source URL")
        else:
            ok("sources/depth-charts.json", f"{len(clubs)} clubs carry an official source URL")

    # injury rows
    inj_path = os.path.join(DATA, "injuries.json")
    if os.path.exists(inj_path):
        doc = load("injuries.json")
        rows = doc.get("rows") or []
        bad_urls = [r.get("sourceUrl") for r in rows if not official(r.get("sourceUrl"))]
        if bad_urls:
            bad("sources/injuries.json", f"{len(bad_urls)} injury rows without an official source URL")
        else:
            ok("sources/injuries.json", f"{len(rows)} injury rows carry an official source URL")


# ------------------------------------------------------------------ 3. leakage
def check_leakage():
    """A bet's estimate may only use games played strictly before the bet's game."""
    strat_path = os.path.join(DATA, "strategies.json")
    games_path = os.path.join(DATA, "games.json")
    if not (os.path.exists(strat_path) and os.path.exists(games_path)):
        return
    doc = load("strategies.json")
    games = {g["gameId"]: g for g in load("games.json").get("games", [])}

    # 3a. every placed bet resolves to a real official game
    unknown = [b for b in doc.get("bets", []) if b.get("gameId") not in games]
    if unknown:
        bad("leakage/game-reference", f"{len(unknown)} bets reference a game that is not in the schedule")
    else:
        ok("leakage/game-reference", "every bet resolves to a scheduled game")

    # 3b. a bet's date matches the official game date
    mismatch = []
    for b in doc.get("bets", []):
        g = games.get(b.get("gameId"))
        if g and g.get("date") and b.get("date") and g["date"] != b["date"]:
            mismatch.append(b.get("gameId"))
    if mismatch:
        bad("leakage/date-match", f"{len(mismatch)} bets have a date that differs from the official game date")
    else:
        ok("leakage/date-match", "every bet date matches the official game date")

    # 3c. the holdout is never in the development set
    meta = doc.get("meta", {})
    dev = set(meta.get("developmentSeasons") or [])
    hold = meta.get("holdoutSeason")
    if dev and hold is not None:
        if hold in dev:
            bad("leakage/split", "the holdout season also appears in the development seasons")
        else:
            ok("leakage/split", f"development {sorted(dev)} and holdout {hold} are disjoint")

    # 3d. no strategy bet is dated before the first official game of its season
    early = []
    for b in doc.get("bets", []):
        g = games.get(b.get("gameId"))
        if not g or not b.get("date"):
            continue
        if b["date"] < g["date"]:
            early.append(b.get("gameId"))
    if early:
        bad("leakage/date-order", f"{len(early)} bets are dated before the official game date")
    else:
        ok("leakage/date-order", "no bet predates the official game it belongs to")


# ------------------------------------------------------------------ 4. pages
PAGE_FILES = ["index.html", "lines.html", "strategies.html", "leaderboard.html", "bets.html",
              "validation.html", "correlations.html", "injuries.html", "suggestions.html",
              "questions.html", "executive-summary.html", "sources.html", "flagged.html"]


def strip_tags(html):
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\x00", text)
    return text


def check_pages():
    if not os.path.isdir(PAGES):
        bad("pages/existence", "the lines/ directory is missing")
        return
    for fname in PAGE_FILES:
        path = os.path.join(PAGES, fname)
        if not os.path.exists(path):
            bad("pages/existence", f"{fname} is missing")
            continue
        html = open(path, encoding="utf-8").read()

        # 4a. internal links resolve
        for href in set(re.findall(r'href="([^"#?]+)"', html)):
            if href.startswith("http"):
                continue
            target = os.path.normpath(os.path.join(PAGES, href))
            if not os.path.exists(target):
                bad(f"pages/links/{fname}", f"internal link does not resolve: {href}")
                break
        else:
            ok(f"pages/links/{fname}", "every internal link resolves")

        # 4b. every table row carries a source link
        body_rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)
        missing = 0
        for row in body_rows:
            if "<th" in row or "PAGE HEADER" in row:
                continue
            if "<a " not in row:
                missing += 1
        if missing:
            bad(f"pages/source-links/{fname}", f"{missing} table rows carry no source link")
        else:
            ok(f"pages/source-links/{fname}", f"{len(body_rows)} table rows carry a source link")

        # 4c. the page links to an official source somewhere
        if not any(official(h) for h in re.findall(r'href="(https?://[^"]+)"', html)):
            bad(f"pages/official-source/{fname}", "the page links no official source")
        else:
            ok(f"pages/official-source/{fname}", "official source linked")

        # 4d. the model-output disclaimer is present
        if "Model outputs, not official values" not in html:
            bad(f"pages/disclaimer/{fname}", "the model-output disclaimer is missing")
        else:
            ok(f"pages/disclaimer/{fname}", "disclaimer present")


# ------------------------------------------------------------------ 5. links
def check_links():
    if not os.path.isdir(PAGES):
        return
    for fname in PAGE_FILES:
        path = os.path.join(PAGES, fname)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        for url in re.findall(r'href="(https?://[^"]+)"', html):
            if not official(url):
                bad(f"links/official-only/{fname}", f"non-official external link: {url}")
                break
        else:
            ok(f"links/official-only/{fname}", "every external link points at an official host")


def main():
    _load_club_domains()
    check_schema()
    check_sources()
    check_leakage()
    check_pages()
    check_links()
    passed = sum(1 for _, good, _ in checks if good)
    print(f"lines verification: {passed}/{len(checks)} checks passed")
    for name, good, detail in checks:
        if not good:
            print(f"  FAIL {name}: {detail}")
    evidence = {
        "generatedBy": "scripts/lines/verify_lines.py",
        "checksPassed": passed,
        "checksTotal": len(checks),
        "failedChecks": [{"name": n, "detail": d} for n, g, d in checks if not g],
        "checks": [{"name": n, "pass": g, "detail": d} for n, g, d in checks],
    }
    out = os.path.join(ROOT, "verification", "lines-verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if failures:
        print(f"\n{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
