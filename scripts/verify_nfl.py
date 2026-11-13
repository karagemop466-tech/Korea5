#!/usr/bin/env python3
"""Verify the NFL Lines & Strategy hub line by line.

Checks:
  1. All nfl/data/*.json are valid and every source id referenced resolves.
  2. Every table row that carries a "Source" column has either an official
     source link or an explicit blank/flagged cell (never a silently inferred
     value).
  3. Every external link points to an official, trusted domain.
  4. Every local link resolves to an existing file (no broken links).

Exits non-zero if any hard check fails.
"""
import json
import pathlib
import re
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
NFL = ROOT / "nfl"
DATA = NFL / "data"

OFFICIAL_SUFFIXES = ("nfl.com", "gaming.ny.gov", "sbg.colorado.gov", "gaming.nv.gov")


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def host(url):
    return urlparse(url).netloc.lower()


def is_official(url):
    h = host(url)
    return any(h == s or h.endswith("." + s) for s in OFFICIAL_SUFFIXES)


def main():
    failures = []
    notes = []

    # 1. JSON validity + source id resolution --------------------------------
    sources = load("sources")["sources"]
    src_ids = {s["id"] for s in sources}
    referenced = set()
    for jf in sorted(DATA.glob("*.json")):
        try:
            obj = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            failures.append(f"{jf.name}: invalid JSON ({e})")
            continue

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k == "source" and isinstance(v, str) and v:
                        referenced.add(v)
                    walk(v)
            elif isinstance(x, list):
                for it in x:
                    walk(it)
        walk(obj)
    unresolved = referenced - src_ids
    if unresolved:
        failures.append(f"unresolved source ids referenced in data: {sorted(unresolved)}")
    notes.append(f"data files valid; {len(referenced)} source refs checked; unresolved: {len(unresolved)}")

    # 2-4. Per-page checks ---------------------------------------------------
    total_rows = 0
    rows_missing_source = 0
    local_links = 0
    missing_local = []
    bad_external = []
    table_count = 0

    link_re = re.compile(r'href="([^"]+)"')
    for htmlf in sorted(NFL.glob("*.html")):
        text = htmlf.read_text(encoding="utf-8")

        # local + external link resolution
        for href in link_re.findall(text):
            if href.startswith("http"):
                if not is_official(href):
                    bad_external.append((htmlf.name, href))
            else:
                local_links += 1
                target = (NFL / href).resolve()
                if not target.exists():
                    missing_local.append((htmlf.name, href))

        # tables with a Source column
        for table_m in re.finditer(r"<table\b.*?</table>", text, re.S):
            table = table_m.group(0)
            table_count += 1
            header = re.search(r"<thead>.*?</thead>", table, re.S)
            if not header:
                continue
            ths = re.findall(r"<th[^>]*>(.*?)</th>", header.group(0), re.S)
            if not any("Source" in h for h in ths):
                continue
            src_idx = next(i for i, h in enumerate(ths) if "Source" in h)
            for row in re.finditer(r"<tr>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", table, re.S).group(1), re.S):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(1), re.S)
                if len(cells) <= src_idx:
                    continue
                total_rows += 1
                src_cell = cells[src_idx]
                # A row is compliant if its source cell carries an official link,
                # OR the source cell is an explicit blank/flag, OR any cell in the
                # row carries an official external link (e.g. the Sources registry
                # puts the link in a dedicated URL column).
                has_link = bool(re.search(r'<a[^>]+href="http', src_cell))
                if not has_link:
                    row_links = re.findall(r'<a[^>]+href="(http[^"]+)"', row.group(1))
                    has_link = any(is_official(u) for u in row_links)
                if has_link:
                    continue
                if "blank" in src_cell or "—" in src_cell or "unresolved" in src_cell:
                    continue  # explicit blank / flagged, allowed
                rows_missing_source += 1
                failures.append(f"{htmlf.name}: table row without a source link or flagged blank")

    if missing_local:
        failures.append(f"broken local links: {missing_local}")
    if bad_external:
        failures.append(f"non-official external links: {bad_external}")

    notes.append(f"tables checked: {table_count}; source-bearing rows: {total_rows}; missing source: {rows_missing_source}")
    notes.append(f"local links: {local_links}; missing: {len(missing_local)}; non-official external: {len(bad_external)}")

    print("NFL hub verification")
    for n in notes:
        print("  -", n)
    if failures:
        print("\nFAILURES")
        for f in failures:
            print("  -", f)
        return 1
    print("\nPASS: all checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
