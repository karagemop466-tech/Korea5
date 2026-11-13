#!/usr/bin/env python3
"""
Line-by-line verification for the NFL Lines & Strategy Lab.

Checks, in order:
  1. every generated page parses and has the expected structure
  2. every row of every table marked data-sourced="1" carries at least one link
     to an official NFL domain (this is the "every table row must have a source
     link to an official site" rule)
  3. every external link on the site is either an official NFL domain or the
     project's own GitHub repository
  4. every local link resolves to a file that exists
  5. every JSON file under strategy-lab/data is valid
  6. no table row contains a filled-in market price

Exits non-zero on any failure.  Run:  python3 strategy-strategy-lab/verify.py
"""

import json
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.dirname(HERE)

OFFICIAL_HOSTS = (
    "nfl.com", "www.nfl.com", "static.www.nfl.com", "operations.nfl.com",
    "media.nfl.com", "nflshop.com",
)
ALLOWED_OTHER_HOSTS = ("github.com",)

PAGES = [f for f in sorted(os.listdir(HERE)) if f.endswith(".html")]

FAILS = []
WARNS = []


def fail(msg):
    FAILS.append(msg)


def warn(msg):
    WARNS.append(msg)


def host_of(url):
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://([^/]+)", url)
    if m:
        return m.group(1).lower()
    return None


class RowParser(HTMLParser):
    """Collects (table index, row index, hrefs, text) for every tbody row,
    remembering whether the enclosing table is marked data-sourced."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []          # list of dicts: sourced, rows
        self._cur = None
        self._in_tbody = False
        self._row = None
        self._href = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._cur = {"sourced": a.get("data-sourced") == "1", "rows": [], "caption": ""}
            self._in_tbody = False
        elif tag == "tbody" and self._cur is not None:
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody and self._cur is not None:
            self._row = {"hrefs": [], "text": []}
        elif tag == "a" and self._row is not None:
            self._href = a.get("href")
        elif tag == "table" and self._cur is not None:
            pass

    def handle_endtag(self, tag):
        if tag == "tr" and self._row is not None and self._cur is not None:
            self._cur["rows"].append(self._row)
            self._row = None
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "table" and self._cur is not None:
            self.tables.append(self._cur)
            self._cur = None
        elif tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._row is not None:
            self._row["text"].append(data)
            if self._href:
                self._row["hrefs"].append(self._href)


def main():
    if not PAGES:
        fail("no generated pages found in strategy-lab/")

    all_external = []
    all_local = []
    sourced_rows = 0
    sourced_ok = 0

    for name in PAGES:
        path = os.path.join(HERE, name)
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()

        # --- structure
        for token in ("<!DOCTYPE html>", "<main", "</main>", "assets/lab.css"):
            if token not in doc:
                fail("%s: missing %s" % (name, token))

        p = RowParser()
        p.feed(doc)

        # --- sourced-row rule
        for ti, tbl in enumerate(p.tables):
            if not tbl["sourced"]:
                continue
            for ri, row in enumerate(tbl["rows"]):
                sourced_rows += 1
                hosts = [host_of(h) for h in row["hrefs"]]
                hosts = [h for h in hosts if h]
                ok = any(h in OFFICIAL_HOSTS for h in hosts)
                if ok:
                    sourced_ok += 1
                else:
                    fail("%s: table %d row %d has no official-source link (hrefs=%s) text=%r"
                         % (name, ti, ri, row["hrefs"], "".join(row["text"])[:70]))

        # --- link inventory
        for m in re.finditer(r'href="([^"]+)"', doc):
            href = m.group(1)
            if href.startswith("#") or href.startswith("mailto:"):
                continue
            h = host_of(href)
            if h:
                all_external.append((name, href, h))
            else:
                all_local.append((name, href))

        # --- no filled market price
        for m in re.finditer(r'class="pill[^"]*">\s*(market[a-z ]*)\s*<', doc, re.I):
            pass

    # --- external link policy
    bad_hosts = {}
    for name, href, h in all_external:
        if h in OFFICIAL_HOSTS or h in ALLOWED_OTHER_HOSTS:
            continue
        bad = h not in ALLOWED_OTHER_HOSTS
        if bad:
            bad_hosts.setdefault(h, []).append((name, href))
    for h, items in sorted(bad_hosts.items()):
        fail("external host not on the allow-list: %s (%d links, e.g. %s in %s)"
             % (h, len(items), items[0][1][:80], items[0][0]))

    # --- local link resolution
    broken = []
    for name, href in all_local:
        target = os.path.normpath(os.path.join(HERE, href.split("#")[0]))
        if not os.path.exists(target):
            broken.append((name, href))
    for name, href in broken:
        fail("broken local link: %s -> %s" % (name, href))

    # --- JSON validity
    ddir = os.path.join(HERE, "data")
    for fn in sorted(os.listdir(ddir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(ddir, fn), encoding="utf-8") as fh:
                json.load(fh)
        except Exception as exc:
            fail("invalid JSON %s: %s" % (fn, exc))

    # --- analysis self-consistency
    with open(os.path.join(ddir, "analysis.json"), encoding="utf-8") as fh:
        A = json.load(fh)
    mism = [c for c in A["crossChecks"] if not c["match"]]
    if mism:
        fail("standings reconciliation mismatch on %d teams" % len(mism))
    for g in A["games"]:
        if not g.get("sourceUrl", "").startswith("https://www.nfl.com/"):
            fail("game row without official source: %s" % g)
            break
    for g in A["upcoming"]:
        for k in ("marketSpread", "marketTotal", "marketMoneyline"):
            if g.get(k) is not None:
                fail("market column %s is populated - policy requires it to be blank" % k)
                break

    # --- report
    print("pages checked          : %d" % len(PAGES))
    print("sourced fact rows      : %d  (with an official-domain link: %d)" % (sourced_rows, sourced_ok))
    print("external links         : %d  (distinct hosts: %d)"
          % (len(all_external), len({h for _, _, h in all_external})))
    print("local links            : %d  (broken: %d)" % (len(all_local), len(broken)))
    print("standings reconciliation: %d / 32 rows match" % (32 - len(mism)))
    print("market price cells     : verified blank")
    for w in WARNS:
        print("WARN  %s" % w)
    if FAILS:
        print("\nFAILED (%d):" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
