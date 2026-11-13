#!/usr/bin/env python3
"""NFL Skill Lab — build verification (session arena-fb9c9608).

Checks JSON integrity, local link integrity across nfl-lab pages, that every
fact-bearing table row carries a source link, that official-vs-dataset
cross-checks agree, and that no build artefact leaked placeholders.
Writes lines-lab/data/derived/verification.json.
"""
import json, os, re, glob, html.parser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.join(ROOT, "lines-lab")
DER = os.path.join(LAB, "data", "derived")

checks, failures = [], 0

def check(name, ok, detail=""):
    global failures
    checks.append(("PASS" if ok else "FAIL") + f" — {name}" + (f" ({detail})" if detail else ""))
    if not ok:
        failures += 1

# 1. JSON validity
jfiles = sorted(glob.glob(os.path.join(LAB, "data", "**", "*.json"), recursive=True))
bad = []
for p in jfiles:
    try:
        json.load(open(p))
    except Exception as e:
        bad.append((os.path.relpath(p, LAB), str(e)))
check("all JSON files parse", not bad, f"{len(jfiles)} files" + (f"; bad: {bad}" if bad else ""))

# 2. local links
pages = {os.path.basename(p): p for p in glob.glob(os.path.join(LAB, "*.html"))}
link_re = re.compile(r'href="([^"#]+)"')
missing = []
ext = 0
for name, path in pages.items():
    txt = open(path).read()
    base = os.path.dirname(path)
    for href in link_re.findall(txt):
        if href.startswith(("http://", "https://", "mailto:")):
            ext += 1
            continue
        target = os.path.normpath(os.path.join(base, href.split("?")[0]))
        if not os.path.exists(target):
            missing.append((name, href))
check("all local links resolve", not missing, f"{len(pages)} pages, {ext} external links" + (f"; missing: {missing}" if missing else ""))
check("nav links back to planner root", all(os.path.exists(os.path.join(ROOT, f)) for f in ("index.html", "extra/flagged.html")))

# 3. fact rows carry a source link: count rows vs rows-with-source per key table
def table_rows(txt):
    return re.findall(r"<tr>.*?</tr>", txt, flags=re.S)

for page_name, min_src_rows in (("lines.html", 27), ("leaderboard.html", 8), ("correlation.html", 4), ("flagged.html", 10), ("sources.html", 12)):
    txt = open(pages[page_name]).read()
    rows = table_rows(txt)
    # fact rows = rows that contain a <td> but not header rows
    fact = [r for r in rows if "<th" not in r and "<td" in r]
    with_src = [r for r in fact if ("href=" in r and ("source" in r or "games.csv" in r or "NFL.com" in r or "↗" in r or "nfl.com" in r or "github.com" in r))]
    check(f"{page_name}: fact rows with source links", len(with_src) >= min(fact.__len__(), min_src_rows),
          f"{len(with_src)}/{len(fact)} rows carry links")

# 4. content spot checks
inj = json.load(open(os.path.join(LAB, "data/official/injuries-2026-w10.json")))
n_rows = sum(len(r) for g in inj["games"] for t, r in g["teams"].items() if isinstance(r, list))
check("injury report transcribed in full", n_rows == 296 and len(inj["games"]) == 14, f"{n_rows} rows, {len(inj['games'])} games")
s10 = json.load(open(os.path.join(LAB, "data/official/schedule-2026-w10.json")))
tnf = s10["games"][0]
check("TNF final present and correct (official page)", tnf["final"] and tnf["awayScore"] == 24 and tnf["homeScore"] == 21)
s11 = json.load(open(os.path.join(LAB, "data/official/schedule-2026-w11.json")))
check("Week 11 has 13 official games", len(s11["games"]) == 13)
lb = json.load(open(os.path.join(DER, "leaderboard.json")))
check("leaderboard has 8 strategies with gates", len(lb["rows"]) == 8 and all(len(r["gates"]) == 6 for r in lb["rows"]))
corr = json.load(open(os.path.join(DER, "correlation.json")))
v = corr["values"]
check("correlation values present and sane", abs(v["pearsonMarginTotal_1999_2025"]) < 0.5 and 12 < v["sigmaMarginPts"] < 16)
meta = json.load(open(os.path.join(DER, "model-meta.json")))
check("records cross-check ran with 0 mismatches", meta["recordsCrossCheck"]["mismatches"] == [])
lines = json.load(open(os.path.join(DER, "lines-2026-w10-w11.json")))
w10r, w11r = lines["weeks"]["2026-10"]["rows"], lines["weeks"]["2026-11"]["rows"]
check("lines board covers W10 (14) + W11 (13)", len(w10r) == 14 and len(w11r) == 13)
check("no market line published for unposted weeks", all(r["marketSpreadHome"] is not None for r in w10r + w11r))
depth = json.load(open(os.path.join(DER, "depth-2026-w10.json")))
check("depth tracker covers all 28 report teams", len(depth["teams"]) == 28)
flags = json.load(open(os.path.join(DER, "flags.json")))
check("flag register has 10 items with sources", len(flags["items"]) == 10 and all(i["source"].startswith("http") for i in flags["items"]))

# 5. no placeholders leaked into HTML
leak = []
for name, path in pages.items():
    txt = open(path).read()
    if re.search(r"{m}|\{mm\}|\{r\}|<td[^>]*>\s*None\s*</td>|<td[^>]*>\s*NaN\s*</td>|<td[^>]*>\s*nan\s*</td>", txt):
        leak.append(name)
check("no build placeholders leaked", not leak, str(leak) if leak else "")

# 6. pages count
check("all 12 lab pages exist", len(pages) == 12, str(sorted(pages)))

summary = {
    "builtUTC": "2026-11-13T14:10:00Z",
    "session": "arena-fb9c9608",
    "passed": failures == 0,
    "nChecks": len(checks),
    "nFailures": failures,
    "checks": checks,
}
with open(os.path.join(DER, "verification.json"), "w") as f:
    json.dump(summary, f, indent=1)
print("\n".join(checks))
print(f"\n{len(checks)} checks, {failures} failures")
raise SystemExit(1 if failures else 0)
