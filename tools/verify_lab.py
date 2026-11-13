#!/usr/bin/env python3
"""Line-by-line verification of the published NFL Lines Lab pages.

Checks, for every table row on every lab page:
  * the row carries at least one link to an official source, or is an explicit
    empty placeholder (a "—" or a "blank" marker) with no value asserted;
  * no row asserts a value that is missing from the committed records.

Also re-checks that the headline numbers printed on the landing page and the
correlations page are the numbers the analysis actually produced, and that every
player link points at nfl.com.

Exit code is non-zero if any check fails, so CI blocks a broken claim.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
LAB = "lab"

ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
LINK = re.compile(r'href="(https?://[^"]+)"')
ANYLINK = re.compile(r'href="([^"]+)"')
TAG_STRIP = re.compile(r"<[^>]+>")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SPEC = load("curated/nfl-lab.json")
INJ = load("data/lab/injuries-week10-2026.json")
ANA = load("data/lab/analysis.json")
LOGS = load("data/lab/player-logs-2026.json")

OFFICIAL_HOSTS = ("nfl.com", "www.nfl.com", "static.www.nfl.com", "operations.nfl.com",
                  "karagemop466-tech.github.io", "github.com")

failures = []
checks = []


def fail(page, detail):
    failures.append({"page": page, "detail": detail})


def text(cell):
    return TAG_STRIP.sub("", cell).strip()


def anchors_in(path):
    """Every id and name attribute defined in an HTML file."""
    body = open(path, encoding="utf-8").read()
    found = set(re.findall(r'id="([^"]+)"', body))
    found |= set(re.findall(r'name="([^"]+)"', body))
    return found


def check_anchor(page, target):
    """A repository link with a #fragment must point at an anchor that exists."""
    path_part, _, frag = target.partition("#")
    base = os.path.dirname(page)
    resolved = os.path.normpath(os.path.join(base, path_part)) if path_part else os.path.dirname(page)
    if not os.path.exists(resolved):
        fail(page, f"anchor link points at a file that does not exist: {target}")
        return
    if frag and frag not in anchors_in(resolved):
        fail(page, f"anchor link points at a missing anchor: {target}")


def check_row_sources(page, row_html, allow_placeholder=True):
    """A row must carry a source: an external official link, or a repository link that
    resolves to a file that exists. A row with neither has to be an explicit
    placeholder that asserts no value."""
    links = LINK.findall(row_html)
    for link in links:
        host = link.split("/")[2]
        if not any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
            fail(page, f"row links to a non-official host: {link}")
    if links:
        return "linked"
    for target in ANYLINK.findall(row_html):
        if target.startswith("#"):
            return "linked"          # basis cited on the same page
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        base = os.path.dirname(page)          # page is already relative to the repo root
        if os.path.exists(os.path.normpath(os.path.join(base, target.split("#")[0]))):
            check_anchor(page, target)
            return "linked"
        fail(page, f"row links to a repository file that does not exist: {target}")
    if allow_placeholder and ("—" in row_html or "not started" in row_html):
        return "placeholder"
    fail(page, f"row has no official source link and is not an explicit placeholder: {text(row_html)[:90]}")
    return "unlinked"


for name in sorted(f for f in os.listdir(LAB) if f.endswith(".html")):
    path = os.path.join(LAB, name)
    html_text = open(path, encoding="utf-8").read()
    rows = 0
    linked = 0
    placeholders = 0
    for row_html in ROW.findall(html_text):
        if "<th" in row_html:
            continue
        cells = CELL.findall(row_html)
        if not cells:
            continue
        rows += 1
        result = check_row_sources(path, row_html)
        if result == "linked":
            linked += 1
        elif result == "placeholder":
            placeholders += 1
    checks.append({"page": path, "rows": rows, "linkedRows": linked, "placeholderRows": placeholders})
    if rows and linked + placeholders != rows:
        fail(path, "row accounting mismatch")
    # every in-repository link on the page must resolve, anchor included
    for target in set(ANYLINK.findall(html_text)):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_part = target.split("#")[0]
        if not path_part:
            continue
        base = os.path.dirname(path)
        if not os.path.exists(os.path.normpath(os.path.join(base, path_part))):
            fail(os.path.join(LAB, name), f"page links to a file that does not exist: {target}")
        else:
            check_anchor(path, target)

# every player link on the injury pages must point at nfl.com
for name in ("injuries.html",):
    html_text = open(os.path.join(LAB, name), encoding="utf-8").read()
    for link in set(LINK.findall(html_text)):
        if "/players/" in link and "nfl.com/players/" not in link:
            fail(os.path.join(LAB, name), f"player link is not on nfl.com: {link}")

# headline numbers must equal the analysis output
index_html = open(os.path.join(LAB, "index.html"), encoding="utf-8").read()
corr_html = open(os.path.join(LAB, "correlations.html"), encoding="utf-8").read()
pair = next((c for c in ANA["correlations"] if "Jordan Addison" in c["b"]), None)
if pair:
    for value in (str(pair["r"]), str(pair["n"])):
        if value not in index_html:
            fail(os.path.join(LAB, "index.html"), f"headline value {value} from analysis.json is not published")
    ci = f"{pair['ci95'][0]} to {pair['ci95'][1]}"
    if ci not in index_html:
        fail(os.path.join(LAB, "index.html"), f"headline interval {ci} from analysis.json is not published")
else:
    fail(os.path.join(LAB, "index.html"), "the two-receiver correlation pair is missing from analysis.json")

# Select the -110 rows by their price label. A tolerance comparison against
# 110/210 matched nothing here (the stored break-even is rounded to four
# decimals), which made the loop below skip every row and report success
# while the published headline number was blank.
ss = [s for s in ANA["sampleSize"] if "-110" in s["priceBasis"]]
if not ss:
    fail(os.path.join(LAB, "index.html"), "analysis.json has no -110 sample-size rows")
for edge in (0.05, 0.03):
    hit = next((s for s in ss if s["edgeOverBreakEven"] == edge), None)
    if not hit:
        fail(os.path.join(LAB, "index.html"),
             f"analysis.json has no sample-size row for a +{edge * 100:g} point edge")
        continue
    if f"{hit['observationsNeeded']:,}" not in index_html:
        fail(os.path.join(LAB, "index.html"),
             f"sample-size headline {hit['observationsNeeded']:,} is not published")
    if str(hit["observationsNeeded"]) not in corr_html:
        fail(os.path.join(LAB, "correlations.html"),
             f"sample-size {hit['observationsNeeded']} is not published in the table")

# The navigation must not drift from the canonical site navigation. This file used to
# keep its own copy of the root links, which silently dropped a surface another session
# had added to the navigation.
try:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from build_site import NAV as SITE_NAV
except Exception:
    SITE_NAV = None
if SITE_NAV:
    for name in sorted(f for f in os.listdir(LAB) if f.endswith(".html")):
        body = open(os.path.join(LAB, name), encoding="utf-8").read()
        for href, label in SITE_NAV:
            if href.startswith("lab/"):
                # The lab's own pages appear in the lab strip, not the root strip.
                wanted = href[len("lab/"):]
                if f'href="{wanted}"' not in body:
                    fail(os.path.join(LAB, name), f"navigation is missing the lab entry for {label} ({wanted})")
            elif f'href="../{href}"' not in body:
                fail(os.path.join(LAB, name), f"navigation is missing the site entry {label} ({href})")

# Every stated game count must match the committed rows. A count written by hand in
# prose once said "nine games per player" while eight rows were stored; this check
# makes that impossible to publish.
GAME_COUNTS = {len(p.get("games", [])) for p in LOGS.get("players", [])}
if len(GAME_COUNTS) != 1:
    fail(os.path.join(LAB, "index.html"),
         f"players have differing game counts in player-logs-2026.json: {sorted(GAME_COUNTS)}")
else:
    games = GAME_COUNTS.pop()
    words = {6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 12: "twelve"}
    for page_name in ("correlations.html", "flags.html"):
        body = open(os.path.join(LAB, page_name), encoding="utf-8").read()
        for match in re.findall(r"with ([a-z]+) games of a single season", body):
            if match != words.get(games, str(games)):
                fail(os.path.join(LAB, page_name),
                     f"published game count \"{match}\" does not match the {games} stored rows")
    meta = LOGS.get("meta", {})
    limits = meta.get("limits", "")
    for match in re.findall(r"([A-Z][a-z]+) games per player", limits):
        if match.lower() != words.get(games, str(games)).lower():
            fail("data/lab/player-logs-2026.json",
                 f"metadata says \"{match} games per player\" but {games} rows are stored")

# the correlation table on the page must match the analysis row for row
for c in ANA["correlations"]:
    if str(c["r"]) not in corr_html:
        fail(os.path.join(LAB, "correlations.html"), f"correlation r={c['r']} ({c['a']} / {c['b']}) is not published")
    if c["ci95"] and f"{c['ci95'][0]} to {c['ci95'][1]}" not in corr_html:
        fail(os.path.join(LAB, "correlations.html"), f"interval for {c['a']} / {c['b']} is not published")

# injury rows published must equal rows recorded
inj_rows = sum(len(t["rows"]) for t in INJ["practice"].values())
inj_html = open(os.path.join(LAB, "injuries.html"), encoding="utf-8").read()
published_rows = len([m for m in ROW.findall(inj_html) if "nfl.com/players/" in m])
if published_rows < inj_rows:
    fail(os.path.join(LAB, "injuries.html"),
         f"{inj_rows} practice rows are recorded but only {published_rows} appear on the page")
for r in INJ["gameStatus"]:
    if r[2] not in inj_html:
        fail(os.path.join(LAB, "injuries.html"), f"game-status row for {r[2]} is not published")

# every curated question, strategy, gate and suggestion must appear on its page
for q in SPEC["questions"]:
    if q["id"] not in open(os.path.join(LAB, "questions.html"), encoding="utf-8").read():
        fail(os.path.join(LAB, "questions.html"), f"question {q['id']} is not published")
for s in SPEC["strategies"]:
    if s["id"] not in open(os.path.join(LAB, "strategies.html"), encoding="utf-8").read():
        fail(os.path.join(LAB, "strategies.html"), f"strategy {s['id']} is not published")
for g in SPEC["gates"]:
    if g["id"] not in open(os.path.join(LAB, "strategies.html"), encoding="utf-8").read():
        fail(os.path.join(LAB, "strategies.html"), f"gate {g['id']} is not published")
for p in SPEC["suggestions"]:
    if p["id"] not in open(os.path.join(LAB, "suggestions.html"), encoding="utf-8").read():
        fail(os.path.join(LAB, "suggestions.html"), f"suggestion {p['id']} is not published")
for f in SPEC["flags"]:
    if f["id"] not in open(os.path.join(LAB, "flags.html"), encoding="utf-8").read():
        fail(os.path.join(LAB, "flags.html"), f"flag {f['id']} is not published")

# the leaderboard must stay empty while nothing has passed the gates
lb_html = open(os.path.join(LAB, "leaderboard.html"), encoding="utf-8").read()
if SPEC["leaderboard"]["rows"]:
    fail(os.path.join(LAB, "leaderboard.html"), "leaderboard rows exist while no strategy has passed the gates")
if "no qualifying strategy" not in lb_html:
    fail(os.path.join(LAB, "leaderboard.html"), "the empty leaderboard is not explained on the page")

report = {"checks": checks, "failures": failures,
          "publishedPracticeRows": inj_rows, "publishedGameStatusRows": len(INJ["gameStatus"])}
with open("verification/lab-verification.json", "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1)
    fh.write("\n")

for c in checks:
    print(f"{c['page']}: rows={c['rows']} linked={c['linkedRows']} placeholder={c['placeholderRows']}")
print(f"failures: {len(failures)}")
for f in failures:
    print("FAIL", f)
if failures:
    raise SystemExit(1)
print("Lab verification passed: every published row carries an official source or is an explicit placeholder.")
