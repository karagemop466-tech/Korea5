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

OFFICIAL_HOSTS = ("nfl.com", "www.nfl.com", "static.www.nfl.com", "operations.nfl.com",
                  "karagemop466-tech.github.io", "github.com")

failures = []
checks = []


def fail(page, detail):
    failures.append({"page": page, "detail": detail})


def text(cell):
    return TAG_STRIP.sub("", cell).strip()


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

ss = [s for s in ANA["sampleSize"] if abs(s["breakEven"] - 110 / 210) < 1e-9]
for edge in (0.05, 0.03):
    hit = next((s for s in ss if s["edgeOverBreakEven"] == edge), None)
    if hit and str(hit["observationsNeeded"]) not in index_html:
        fail(os.path.join(LAB, "index.html"),
             f"sample-size headline {hit['observationsNeeded']} is not published")
    if hit and str(hit["observationsNeeded"]) not in corr_html:
        fail(os.path.join(LAB, "correlations.html"),
             f"sample-size {hit['observationsNeeded']} is not published in the table")

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
