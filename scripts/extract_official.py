#!/usr/bin/env python3
"""Download official schedule pages and dump compact, human-auditable text slices.

Purpose: turn JS-heavy official pages into small text files that can be read, curated
into data/*.json and then re-verified automatically by scripts/verify.py.

Writes research/text/<slug>.txt (compact text) and research/extract.json (status report).
"""
import html
import json
import os
import re
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5-free-time-planner/1.0)"}

PAGES = [
    ("49ers-2026", "https://www.49ers.com/schedule/2026/"),
    ("stanford-2026", "https://gostanford.com/sports/football/schedule"),
    ("cal-2026", "https://calbears.com/sports/football/schedule"),
    ("westwoodone-nfl", "https://www.westwoodonesports.com/nfl-schedule/"),
    ("nfl-week-9", "https://www.nfl.com/schedules/2026/by-week/week-9"),
]

TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
ANY_TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"[ \t\r\f\v]+")


def to_text(raw):
    t = TAG_RE.sub(" ", raw)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</(tr|div|li|p|h\d|section|article)>", "\n", t, flags=re.I)
    t = ANY_TAG.sub(" ", t)
    t = html.unescape(t)
    lines = [WS.sub(" ", ln).strip() for ln in t.split("\n")]
    out, prev, blank = [], None, 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        if ln == prev:
            continue
        out.append(ln)
        prev = ln
    return "\n".join(out)


def main():
    os.makedirs("research/text", exist_ok=True)
    report = {}
    for slug, url in PAGES:
        rec = {"url": url}
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", "replace")
            txt = to_text(raw)
            path = f"research/text/{slug}.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt + "\n")
            rec.update({"status": r.status, "chars": len(txt), "path": path})
        except Exception as e:  # noqa: BLE001
            rec["error"] = repr(e)
        report[slug] = rec
        print(slug, rec.get("status"), rec.get("chars"), rec.get("error", ""))
    with open("research/extract.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
