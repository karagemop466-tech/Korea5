#!/usr/bin/env python3
"""Fail the build if any local link or asset referenced by the site is missing.

Every HTML page in the site is scanned — the root pages and each section directory —
and each relative link is resolved against the directory of the page that contains it.
"""
import json
import os
import re
import sys

HREF = re.compile(r'(?:href|src)="([^"]+)"')
LOCAL_OK = re.compile(r'^(?:[a-z]+:|#|mailto:)', re.I)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pages():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in ('.git', 'node_modules', '__pycache__')]
        for name in filenames:
            if name.endswith('.html'):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def main():
    os.chdir(ROOT)
    missing, checked, external = [], 0, set()
    page_files = pages()
    for path in page_files:
        base = os.path.dirname(path)
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        for link in HREF.findall(html):
            if LOCAL_OK.match(link):
                if link.startswith(("http://", "https://")):
                    external.add(link.split("#")[0])
                continue
            target = link.split("#")[0]
            if not target:
                continue
            checked += 1
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                missing.append({"page": os.path.relpath(path, ROOT), "link": link})
    data_files = ["data/derived/analysis.json", "assets/style.css", "assets/app.js",
                  "data/lab/analysis.json", "data/lab/injuries-week10-2026.json",
                  "data/lab/player-logs-2026.json", "data/lab/gamebook-bills-vikings-2026-w9.json",
                  "curated/nfl-lab.json"] + [f"data/events-{y}.json" for y in (2026, 2027, 2028, 2029, 2030)]
    for f in data_files:
        if not os.path.exists(f):
            missing.append({"page": "(runtime)", "link": f})
    out = {"pages": len(page_files), "localLinksChecked": checked, "missing": missing,
           "uniqueExternalLinks": len(external), "externalLinks": sorted(external)}
    os.makedirs("verification", exist_ok=True)
    with open("verification/links.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"pages={len(page_files)} localLinks={checked} external={len(external)} missing={len(missing)}")
    for m in missing:
        print("MISSING", m)
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
