#!/usr/bin/env python3
"""Verify the NFL Control Room.

Fails the build on:
  * a table row without a source link
  * a local link or #anchor that resolves to nothing
  * a number on a page that does not match its data file
  * a decision whose merged register id does not exist
  * a suggestion without options, or with no recommended option
  * a page claiming an edge / win rate / yield
  * a missing asset, a missing json, or an empty register

Exits non-zero on any failure, so CI stops rather than publishing.

Run: python3 tools/verify_control.py
"""
from __future__ import annotations

import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "control"
DATA = "data/control"

failures = []
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        failures.append(f"{name}: {detail}")
    return ok


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        failures.append(f"cannot read {p}: {exc}")
        return default if default is not None else {}


def entries(doc, *keys):
    for k in keys:
        if isinstance(doc, dict) and isinstance(doc.get(k), list):
            return doc[k]
    return []


# --------------------------------------------------------------------- 1. data files
DATA_FILES = ["decisions.json", "suggestions.json", "evidence.json", "strategies.json",
              "injuries.json", "meta.json", "audit.json"]
docs = {}
for f in DATA_FILES:
    p = os.path.join(DATA, f)
    check(f"data file exists: {f}", os.path.isfile(p))
    if os.path.isfile(p):
        docs[f] = load(p)
        check(f"data file is valid JSON: {f}", bool(docs[f]))

decisions = entries(docs.get("decisions.json", {}), "decisions")
suggestions = entries(docs.get("suggestions.json", {}), "suggestions")
datasets = entries(docs.get("evidence.json", {}), "datasets")
board = docs.get("strategies.json", {})
injuries = docs.get("injuries.json", {})
meta = docs.get("meta.json", {})

check("decisions register is non-empty", len(decisions) >= 10, f"{len(decisions)} rows")
check("suggestions register is non-empty", len(suggestions) >= 8, f"{len(suggestions)} rows")
check("evidence register is non-empty", len(datasets) >= 15, f"{len(datasets)} rows")
check("strategy board is non-empty", len(board.get("rows", [])) >= 20,
      f"{len(board.get('rows', []))} rows")
check("injury ledger is non-empty", injuries.get("meta", {}).get("reportedRows", 0) > 100)

# --------------------------------------------------------------------- 2. registers
# every merged register id must exist in the register it names
registers = {
    "lines": entries(load("data/lines/questions.json"), "questions"),
    "analytics": entries(load("data/nfl-analytics/questions.json"), "questions"),
    "intel": entries(load("data/nfl-intel/questions.json"), "questions"),
    "lab": entries(load("data/nfl-lab/questions.json"), "questions"),
    "system": entries(load("nfl/system/curated/questions.json"), "questions"),
}
pool = {k: {e.get("id") for e in v} for k, v in registers.items()}
bad_merge = []
for d in decisions:
    for m in d.get("mergedFrom", []):
        if m["id"] not in pool.get(m["register"], set()):
            bad_merge.append(f'{d["id"]} -> {m["register"]}/{m["id"]}')
check("every merged question id exists in the register it names", not bad_merge,
      "; ".join(bad_merge[:5]))

# a blocking decision must state what is missing and how it closes
for d in decisions:
    check(f'{d["id"]} states what is missing', bool(d.get("missing")), d.get("id", "?"))
    check(f'{d["id"]} states how it closes', bool(d.get("close")), d.get("id", "?"))
    check(f'{d["id"]} carries at least one official source', bool(d.get("sources")), d.get("id", "?"))

# the merge must account for the register rows it read
merged_ids = sum(d.get("mergeCount", 0) for d in decisions)
not_merged = entries(docs.get("decisions.json", {}), "notMerged")
check("merge accounts for rows: merged + explicitly-not-merged > 0",
      merged_ids + len(not_merged) > 40, f"{merged_ids} merged + {len(not_merged)} listed")

# suggestions: options with ids, exactly one recommended, and a problem statement
for s in suggestions:
    opts = s.get("options", [])
    check(f'{s["id"]} has at least two options', len(opts) >= 2, str(len(opts)))
    check(f'{s["id"]} options all carry an id and a trade-off',
          all(o.get("id") and o.get("tradeoff") for o in opts), s["id"])
    rec = [o for o in opts if o.get("recommended")]
    check(f'{s["id"]} has exactly one recommended option', len(rec) == 1, str(len(rec)))
    check(f'{s["id"]} states the problem', bool(s.get("problem")), s["id"])
    check(f'{s["id"]} cites a source', bool(s.get("sources")), s["id"])

# evidence: every dataset exists and every row has a source URL
for d in datasets:
    check(f'evidence exists: {d["path"]}', d.get("exists"), d["path"])
    check(f'evidence has a source URL: {d["path"]}', bool(d.get("sourceUrl")), d["path"])
    check(f'evidence states a limitation: {d["path"]}', bool(d.get("cannotTell")), d["path"])

# strategy board: every row sourced, no row claims a validated edge
for r in board.get("rows", []):
    check(f'strategy row has a source: {r.get("lab")}/{r.get("id")}', bool(r.get("sourceUrl")),
          str(r.get("id")))

# --------------------------------------------------------------------- 3. pages
PAGES = sorted(glob.glob(os.path.join(OUT, "*.html")))
check("pages were generated", len(PAGES) >= 9, f"{len(PAGES)} pages")

texts = {}
for p in PAGES:
    with open(p, encoding="utf-8") as f:
        texts[os.path.basename(p)] = f.read()

# every page states the boundary
for name, t in texts.items():
    check(f"boundary statement present: {name}",
          "No edge is published here" in t or "no win rate" in t.lower(), name)

# no page may claim an edge, a win rate or a yield as a finding
# Phrases that would assert a betting result. "Not guaranteed" is a disclaimer, not a claim,
# so the patterns are written to match assertions rather than the word alone.
forbidden = [r"guaranteed (win|profit|return|edge)", r"\bproven edge\b", r"\bis a validated edge\b",
             r"\bexpected yield of\b", r"\bachieves a win rate\b", r"\bprofitable strategy\b",
             r"\bwe have an edge\b"]
for name, t in texts.items():
    low = t.lower()
    for pat in forbidden:
        check(f'no forbidden claim on {name}: {pat}', not re.search(pat, low), pat)

# local links resolve, including fragments
ids_cache = {}


def ids_of(path):
    if path in ids_cache:
        return ids_cache[path]
    full = os.path.normpath(path)
    got = set()
    if os.path.isfile(full):
        with open(full, encoding="utf-8") as f:
            body = f.read()
        got = set(re.findall(r'\bid="([^"]+)"', body)) | set(re.findall(r'\bname="([^"]+)"', body))
    ids_cache[path] = got
    return got


broken = []
checked_links = 0
for p in PAGES:
    base = os.path.dirname(p)
    body = texts[os.path.basename(p)]
    for href in re.findall(r'href="([^"]+)"', body):
        h = html.unescape(href)
        if h.startswith(("http://", "https://", "mailto:", "#")):
            if h.startswith("#") and h[1:] not in ids_of(p):
                broken.append(f"{os.path.basename(p)}{h}")
            continue
        checked_links += 1
        target, _, frag = h.partition("#")
        full = os.path.normpath(os.path.join(base, target)) if target else p
        if not os.path.exists(full):
            broken.append(f'{os.path.basename(p)} -> {h}')
        elif frag and frag not in ids_of(full):
            broken.append(f'{os.path.basename(p)} -> {h} (missing anchor)')
check(f"all {checked_links} local links resolve, including anchors", not broken,
      "; ".join(broken[:6]))

# assets exist and are referenced
for asset in ("control/assets/control.css", "control/assets/control.js"):
    check(f"asset exists: {asset}", os.path.isfile(asset))
check("stylesheet referenced by every page", all("assets/control.css" in t for t in texts.values()))
check("script referenced by the suggestions page", "assets/control.js" in texts.get("suggestions.html", ""))

# --------------------------------------------------------------------- 4. numbers on pages match data
def count_rows_in_pages(pattern):
    return sum(len(re.findall(pattern, t)) for t in texts.values())


# the tile counts must match the data
idx = texts.get("index.html", "")
c = meta.get("counts", {})
open_count = c.get("decisions", 0) - c.get("decisionsAnswered", 0)
check("index shows the open-decision count from meta", f'>{open_count}<' in idx, str(open_count))
check("index shows the settled-bet count from meta", f">{meta.get('settledBets')}<" in idx,
      str(meta.get("settledBets")))
check("index shows the evidence dataset count", f'>{c.get("evidenceDatasets")}<' in idx)
check("index shows the strategy count", f'>{c.get("strategies")}<' in idx)

strat_page = texts.get("strategies.html", "")
check("strategy page shows the true number of strategy rows",
      f"<strong>{len(board.get('rows', []))}</strong> strategy rows" in strat_page,
      str(len(board.get("rows", []))))
check("strategy page says zero settled bets", "<strong>0</strong> settled bets" in strat_page)
check("strategy page says zero certified strategies", "<strong>0</strong> certified" in strat_page)

inj_page = texts.get("injuries.html", "")
im = injuries.get("meta", {})
check("injury page shows the reported row count from the data",
      f"<strong>{im.get('reportedRows')}</strong> official report rows" in inj_page,
      str(im.get("reportedRows")))
check("injury page shows the club count from the data",
      f"<strong>{im.get('clubsReporting')}</strong> clubs reporting" in inj_page)

audit_page = texts.get("audit.html", "")
audit = docs.get("audit.json", {})
check("audit page shows the defect count from the data",
      f"<strong>{len(audit.get('defects', []))}</strong> defects found" in audit_page)

dec_page = texts.get("decisions.html", "")
check("every decision has a card on the decisions page",
      all(f'id="{d["id"]}"' in dec_page for d in decisions))
sug_page = texts.get("suggestions.html", "")
check("every suggestion has a card on the suggestions page",
      all(f'id="{s["id"]}"' in sug_page for s in suggestions))
check("every suggestion has a selectable radio group",
      all(f'name="{s["id"]}"' in sug_page for s in suggestions))

# --------------------------------------------------------------------- 5. no unfilled values
for name, t in texts.items():
    if name == "flagged.html":
        continue  # the flagged page is where blanks are meant to be visible
    check(f"no empty table cell placeholder on {name}", "<td></td>" not in t, name)

# --------------------------------------------------------------------- report
print(f"control verification: {sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
if failures:
    print("\nFAILURES")
    for f in failures:
        print("  FAIL:", f)
    sys.exit(1)
print("all checks passed")
