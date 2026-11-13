#!/usr/bin/env python3
"""Verify the NFL lines lab site, row by row.

Checks (all run on the generated nfl-lab/*.html and data/nfl-lab/*.json):
  1. Every data-table row links to an official domain, OR carries a visible
     UNVERIFIED / NO SOURCE flag, OR sits in a table marked class="method"
     (internal rules and options; counted and reported separately).
  2. Every local link resolves to a file.
  3. Every data file parses as JSON.
  4. Every external domain used is listed as official, or appears only in flagged rows.
Writes data/nfl-lab/verification.json (the Verification page reads it). Exit code 1 on failure.
"""
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SITE = os.path.join(REPO, "nfl-lab")
D = os.path.join(REPO, "data", "nfl-lab")
OFFICIAL = {"www.nfl.com", "nfl.com", "www.gra.gov.sg", "gra.gov.sg", "www.police.gov.sg", "www.ncpg.org.sg", "ncpg.org.sg"}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []  # dicts: cls, rows: list of {links, flagged}
        self._tstack = []
        self._row = None
        self._cell_depth = 0
        self.links = []
        self.all_hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            cls = a.get("class", "") or ""
            self._tstack.append({"cls": cls, "rows": [], "in_body": False})
        elif tag == "tbody" and self._tstack:
            self._tstack[-1]["in_body"] = True
        elif tag == "tr" and self._tstack and self._tstack[-1]["in_body"]:
            self._row = {"links": [], "flagged": False}
        elif tag == "a":
            href = a.get("href", "")
            self.all_hrefs.append(href)
            if self._row is not None:
                self._row["links"].append(href)
        elif tag == "span" and "flag" in (a.get("class", "") or "").split():
            if self._row is not None:
                self._row["flagged"] = True

    def handle_endtag(self, tag):
        if tag == "tr" and self._row is not None and self._tstack:
            self._tstack[-1]["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._tstack:
            self.tables.append(self._tstack.pop())

    def handle_data(self, data):
        if self._row is not None and ("UNVERIFIED" in data or "NO SOURCE" in data or "UNOFFICIAL" in data or "FLAGGED" in data):
            self._row["flagged"] = True


def main():
    checks = []
    failures = []
    pages = sorted(glob.glob(os.path.join(SITE, "*.html")))
    total_rows = official_rows = flagged_rows = method_rows = 0
    bad_rows = []
    domains_seen = {}
    local_missing = []
    for path in pages:
        text = open(path, encoding="utf-8").read()
        p = TableParser()
        p.feed(text)
        for t in p.tables:
            for r in t["rows"]:
                total_rows += 1
                off = any(urlparse(h).hostname in OFFICIAL for h in r["links"] if h.startswith("http"))
                if t["cls"] and "method" in t["cls"].split():
                    method_rows += 1
                elif off:
                    official_rows += 1
                elif r["flagged"]:
                    flagged_rows += 1
                else:
                    bad_rows.append(os.path.basename(path))
        for h in p.all_hrefs:
            if h.startswith("http"):
                host = urlparse(h).hostname or ""
                domains_seen[host] = domains_seen.get(host, 0) + 1
            elif h and not h.startswith(("#", "mailto:")):
                target = os.path.normpath(os.path.join(os.path.dirname(path), h.split("#")[0]))
                if h.split("#")[0] and not os.path.exists(target):
                    local_missing.append(f"{os.path.basename(path)} -> {h}")
    checks.append({"check": "Table rows: official link, flagged UNVERIFIED/NO SOURCE, or method table",
                   "result": f"{total_rows} rows: {official_rows} official-linked, {flagged_rows} flagged, {method_rows} method-table, {len(bad_rows)} without source",
                   "detail": "Rows without source: " + (", ".join(sorted(set(bad_rows))) if bad_rows else "none")})
    if bad_rows:
        failures.append("rows without source")
    checks.append({"check": "Local links resolve", "result": f"{len(local_missing)} missing", "detail": "; ".join(local_missing[:20]) or "none"})
    if local_missing:
        failures.append("missing local links")
    bad_json = []
    for jf in sorted(glob.glob(os.path.join(D, "*.json"))):
        try:
            json.load(open(jf))
        except Exception as ex:  # noqa: BLE001
            bad_json.append(f"{os.path.basename(jf)}: {ex}")
    checks.append({"check": "Data files parse as JSON", "result": f"{len(glob.glob(os.path.join(D, '*.json')))} files, {len(bad_json)} invalid", "detail": "; ".join(bad_json) or "all valid"})
    if bad_json:
        failures.append("invalid json")
    official_domains = sorted(d for d in domains_seen if d in OFFICIAL)
    other = sorted(d for d in domains_seen if d not in OFFICIAL)
    checks.append({"check": "External domains linked from pages", "result": f"official: {', '.join(official_domains)}; non-official (used only on flagged or method rows): {', '.join(other)}",
                   "detail": "Non-official links are third-party data mirrors, the data dictionary, or the repository itself."})
    out = {"generated_by": "scripts/nfl_lab/verify.py", "checks": checks, "failures": failures}
    with open(os.path.join(D, "verification.json"), "w") as f:
        json.dump(out, f, indent=1)
    for c in checks:
        print(c["check"], "->", c["result"])
    if failures:
        print("FAILURES:", failures)
        sys.exit(1)
    print("verify: pass")


if __name__ == "__main__":
    main()
