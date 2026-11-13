#!/usr/bin/env python3
"""NFL Skill Lab — upstream data fetcher (stdlib only).

Downloads the nflverse release-asset datasets that unlock the currently-blank
research areas (player injuries history, depth charts, snap counts) and refreshes
the results/market table. Designed to run in GitHub Actions (unrestricted network);
the build sandbox cannot reach release assets, so nothing here runs at build time.

Outputs land in lines-lab/data/upstream/ with a manifest recording source URL,
etag/sha and fetch timestamp. Nothing in lines-lab/data/official/ or derived/ is
touched — upstream files are an evidence layer for manual review and future
modeling, never auto-published as page rows without their own provenance pass.
"""
import csv, gzip, hashlib, io, json, os, sys, time, urllib.request

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.join(LAB, "data", "upstream")
os.makedirs(UP, exist_ok=True)

SEASON = os.environ.get("NFL_LAB_SEASON", "2026")
TARGETS = [
    ("injuries-2026.csv.gz",
     f"https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{SEASON}.csv"),
    ("depth-charts-2026.csv.gz",
     f"https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_{SEASON}.csv"),
    ("snap-counts-2026.csv.gz",
     f"https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{SEASON}.csv"),
    ("nfldata-games.csv.gz",
     "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"),
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "korea5-lines-lab/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def main():
    manifest = {"fetchedUTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "season": SEASON, "files": []}
    for name, url in TARGETS:
        try:
            raw = fetch(url)
            gz = gzip.compress(raw, mtime=0)
            dst = os.path.join(UP, name)
            with open(dst, "wb") as f:
                f.write(gz)
            sha = hashlib.sha256(raw).hexdigest()[:16]
            n_rows = sum(1 for _ in io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")) - 1
            manifest["files"].append({"file": name, "source": url, "sha256_16": sha,
                                      "bytesRaw": len(raw), "rows": n_rows})
            print(f"ok  {name}: {n_rows} rows from {url}")
        except Exception as e:
            manifest["files"].append({"file": name, "source": url, "error": str(e)})
            print(f"ERR {name}: {e}")
    with open(os.path.join(UP, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return 0 if all("error" not in x for x in manifest["files"]) else 1

if __name__ == "__main__":
    sys.exit(main())
