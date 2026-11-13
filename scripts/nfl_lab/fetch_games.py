#!/usr/bin/env python3
"""Download the NFL games file (scores, rest, QB ids, spread/total lines) from
the nfldata repository on GitHub and write a provenance manifest.

Source: https://github.com/nflverse/nfldata (archive via codeload.github.com)
Data dictionary: https://github.com/nflverse/nfldata/blob/master/DATASETS.md#games

The file's own documentation does not name the source of spread_line / total_line.
That gap is recorded as an irregularity, not filled in.
Raw files go to /tmp/nfl-lab-raw (not committed). The manifest is committed.
"""
import hashlib
import io
import json
import os
import tarfile
import urllib.request
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.environ.get("NFL_LAB_RAW", "/tmp/nfl-lab-raw")
URL = "https://codeload.github.com/nflverse/nfldata/tar.gz/refs/heads/master"


def main():
    os.makedirs(RAW, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "nfl-lab/1.0"}), timeout=300) as r:
        blob = r.read()
    tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    out = {}
    for name in ("data/games.csv", "DATASETS.md", "README.md"):
        member = next(m for m in tf.getmembers() if m.name.endswith("/" + name))
        data = tf.extractfile(member).read()
        with open(os.path.join(RAW, os.path.basename(name)), "wb") as f:
            f.write(data)
        out[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                     "path_in_archive": member.name}
    manifest = {
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive_url": URL,
        "archive_sha256": hashlib.sha256(blob).hexdigest(),
        "repo": "https://github.com/nflverse/nfldata",
        "data_dictionary": "https://github.com/nflverse/nfldata/blob/master/DATASETS.md",
        "files": out,
        "provenance_note": "DATASETS.md documents spread_line and total_line but does not name their upstream source. Treated as UNVERIFIED third-party input.",
    }
    os.makedirs(os.path.join(REPO, "data", "nfl-lab"), exist_ok=True)
    with open(os.path.join(REPO, "data", "nfl-lab", "games-source.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
