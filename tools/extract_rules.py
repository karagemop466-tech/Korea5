#!/usr/bin/env python3
"""Extract exact halftime/game-timing wording from official rulebook PDFs.

Runs in GitHub Actions (the sandbox itself has no direct outbound internet).
Only text excerpts are committed; the PDFs are not stored in the repo.
"""
import io
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "curated" / "rules.json"

DOCS = [
    {
        "id": "nfl-2026-rulebook-pdf",
        "name": "Official 2026 NFL Rulebook (PDF)",
        "url": "https://static.www.nfl.com/image/upload/fl_attachment/league/tqivdkzt9mu6wdgsh1ku.pdf",
        "landingPage": "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook",
        "official": True,
    },
    {
        "id": "ncaa-2026-football-rules-pdf",
        "name": "2026 NCAA Football Rules and Interpretations (PDF)",
        "url": "https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/PRMFB_RulesBook.pdf",
        "landingPage": "https://www.ncaa.org/championships/playing-rules/football-playing-rules/",
        "official": True,
    },
]

PATTERN = re.compile(
    r"halftime|intermission|13 minutes|20 minutes|sixty minutes|60 minutes|game clock|length of periods",
    re.I,
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Korea5 official-rulebook verifier)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    result = {
        "meta": {
            "name": "Exact timing wording from official rulebooks",
            "compiledUTC": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": "Text is extracted verbatim from the linked official PDFs. Only matching lines are stored; nothing is inferred.",
        },
        "documents": [],
    }
    for doc in DOCS:
        entry = dict(doc)
        try:
            data = fetch(doc["url"])
            reader = PdfReader(io.BytesIO(data))
            lines = []
            for page in reader.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    line = " ".join(line.split())
                    if line and PATTERN.search(line):
                        lines.append(line)
            # de-duplicate while preserving order
            lines = list(dict.fromkeys(lines))
            entry["pdfBytes"] = len(data)
            entry["pages"] = len(reader.pages)
            entry["matchingLines"] = lines[:80]
            entry["status"] = "extracted"
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "failed"
            entry["error"] = repr(exc)
            entry["matchingLines"] = []
        result["documents"].append(entry)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "docs": [(d["id"], d["status"], len(d["matchingLines"])) for d in result["documents"]]}))


if __name__ == "__main__":
    main()
