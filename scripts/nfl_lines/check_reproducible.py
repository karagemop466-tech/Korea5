#!/usr/bin/env python3
"""Reproducibility check for the NFL lines lab.

The lab is deterministic: same inputs, same numbers. But every artefact carries a
`generatedUTC` stamp, and every page carries a build timestamp, so a naive byte-for-byte
`git diff` fails on every run and proves nothing. This script compares each tracked JSON
artefact with its committed version after removing the timestamp fields, which is the claim
that actually matters: *the numbers reproduce*.

Exit code 0 if every artefact reproduces, 1 otherwise. Used by
`.github/workflows/nfl-lines-lab.yml`; also runnable locally:

    python3 scripts/nfl_lines/check_reproducible.py

HTML pages are deliberately excluded: they embed a build timestamp by design, and their
content is covered by verify.py (structure, labels, links) instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "nfl-lines" / "data"

# Keys whose value is a build stamp, not a result. Removed before comparing.
TIME_KEYS = {"generatedUTC", "generatedUtc", "generated", "builtUTC", "capturedUTC", "retrievedUTC",
             "timestamp", "asOf"}


def strip_times(node):
    """Recursively drop timestamp keys so only results are compared."""
    if isinstance(node, dict):
        return {k: strip_times(v) for k, v in node.items() if k not in TIME_KEYS}
    if isinstance(node, list):
        return [strip_times(v) for v in node]
    return node


def committed(path: Path) -> dict | list | None:
    """Read the committed version of a file via git, so the check works on a fresh checkout."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        raw = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def main() -> int:
    tracked = subprocess.run(["git", "ls-files", "nfl-lines/data"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    json_files = [ROOT / p for p in tracked if p.endswith(".json")]
    if not json_files:
        print("no tracked JSON artefacts found - is this a git checkout?", file=sys.stderr)
        return 1

    changed, missing, ok = [], [], 0
    for path in json_files:
        if not path.exists():
            missing.append(path.relative_to(ROOT).as_posix())
            continue
        fresh = json.loads(path.read_text(encoding="utf-8"))
        head = committed(path)
        if head is None:
            missing.append(path.relative_to(ROOT).as_posix() + " (not in HEAD)")
            continue
        if strip_times(fresh) == strip_times(head):
            ok += 1
        else:
            changed.append(path.relative_to(ROOT).as_posix())

    for m in missing:
        print(f"MISSING  {m}")
    for c in changed:
        print(f"CHANGED  {c}")
    print(f"\n{ok}/{len(json_files)} tracked JSON artefacts reproduce exactly (timestamps excluded)")
    if changed or missing:
        print("\nThis is not automatically a bug: a fresh input file will change outputs. But a rebuild from "
              "unchanged inputs must reproduce every number, so investigate before merging.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
