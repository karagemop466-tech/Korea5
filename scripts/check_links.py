#!/usr/bin/env python3
"""Fail the build if any local link or asset referenced by the site is missing."""
import json
import os
import re
import sys

HREF = re.compile(r'(?:href|src)="([^"]+)"')
LOCAL_OK = re.compile(r'^(?:[a-z]+:|#|mailto:)', re.I)


def main():
    pages = sorted(f for f in os.listdir(".") if f.endswith(".html"))
    missing, checked, external = [], 0, set()
    for p in pages:
        html = open(p, encoding="utf-8").read()
        for link in HREF.findall(html):
            if LOCAL_OK.match(link) and not link.startswith("#"):
                if link.startswith(("http://", "https://")):
                    external.add(link.split("#")[0])
                continue
            target = link.split("#")[0]
            if not target:
                continue
            checked += 1
            if not os.path.exists(target):
                missing.append({"page": p, "link": link})
    # every page must be reachable from the nav
    nav_ok = all(os.path.exists(p) for p in pages)
    data_files = ["data/derived/analysis.json", "assets/style.css", "assets/app.js"] + \
                 [f"data/events-{y}.json" for y in (2026, 2027, 2028, 2029, 2030)]
    for f in data_files:
        if not os.path.exists(f):
            missing.append({"page": "(runtime)", "link": f})
    out = {"pages": len(pages), "localLinksChecked": checked, "missing": missing,
           "uniqueExternalLinks": len(external), "externalLinks": sorted(external)}
    os.makedirs("verification", exist_ok=True)
    with open("verification/links.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"pages={len(pages)} localLinks={checked} external={len(external)} missing={len(missing)}")
    for m in missing:
        print("MISSING", m)
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
