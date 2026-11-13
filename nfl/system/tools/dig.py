#!/usr/bin/env python3
"""Print targeted markup excerpts from official NFL pages so parsers can be written
against the real bytes. Output goes to the Actions log only; nothing is committed.

Usage: python3 nfl/tools/dig.py [all|week|injuries|depth|stats|player|game]
"""
from __future__ import annotations

import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5NFLResearch/1.0)"}
URLS = {
    "week": "https://www.nfl.com/schedules/2026/by-week/week-5",
    "injuries": "https://www.nfl.com/injuries/league/2026/reg10",
    "depth": "https://www.49ers.com/team/depth-chart",
    "stats": "https://www.nfl.com/stats/team-stats/offense/passing/2026/reg/all",
    "defstats": "https://www.nfl.com/stats/team-stats/defense/scoring/2026/reg/all",
    "player": "https://www.nfl.com/players/christian-mccaffrey/stats",
    "game": "https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10",
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


OUT = []


def show(label, text, limit=1400):
    block = "\n" + "=" * 78 + "\n### " + label + "\n" + "=" * 78 + "\n" + text[:limit] + "\n"
    print(block)
    OUT.append(block)


def emit(msg):
    print(msg)
    OUT.append(str(msg) + "\n")


def dig_week(h):
    # final scores are rendered as "Away 24, Home 21, FINAL, Thursday, ..."
    pat = re.compile(r"([A-Z][A-Za-z0-9 .'&]{1,24}?) (\d{1,3}), ([A-Z][A-Za-z0-9 .'&]{1,24}?) (\d{1,3}), FINAL")
    hits = pat.findall(h)
    emit(f"score-pattern matches: {len(hits)}")
    for x in hits[:8]:
        emit("    " + repr(x))
    m = pat.search(h)
    if m:
        s = max(0, m.start() - 700)
        show("raw context around first FINAL score", h[s:m.end() + 700], 1600)


def dig_injuries(h):
    tables = [m.start() for m in re.finditer(r"<table", h)]
    emit(f"tables: {len(tables)}")
    for i, p in enumerate(tables[:2]):
        show(f"injuries table #{i} start", h[p:p + 1800], 1800)
    # team heading before the first table
    p = tables[0] if tables else 0
    show("context before first injuries table", h[max(0, p - 2200):p], 2200)


def dig_depth(h):
    i = h.find("Depth Chart")
    show("depth chart header area", h[max(0, i - 400):i + 900], 1300)
    m = re.search(r"(<table|class=\"[^\"]*depth[^\"]*\")", h)
    if m:
        p = m.start()
        show("first depth table/container", h[max(0, p - 300):p + 2600], 2900)


def dig_stats(h):
    for m in list(re.finditer(r"<thead", h))[:1]:
        show("stats thead", h[m.start():m.start() + 1600], 1600)
    for m in list(re.finditer(r"<tbody", h))[:1]:
        show("stats tbody first rows", h[m.start():m.start() + 2200], 2200)


def dig_player(h):
    for m in list(re.finditer(r"<table", h))[:2]:
        show("player table", h[max(0, m.start() - 200):m.start() + 1800], 2000)


def dig_game(h):
    for kw in ("odds", "Odds", "spread", "moneyline"):
        n = len(re.findall(kw, h))
        emit(f"{kw}: {n} hits")
        if n:
            p = h.find(kw)
            show(f"game page around '{kw}'", h[max(0, p - 400):p + 600], 1000)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    from pathlib import Path
    dest = Path(__file__).resolve().parent.parent / "research" / "dig.txt"
    for k, url in URLS.items():
        if which not in ("all", k if k in ("week", "injuries", "depth", "stats", "player", "game") else "stats"):
            continue
        print(f"\n\n*** FETCH {k}: {url}")
        try:
            h = get(url)
        except Exception as e:  # noqa: BLE001
            print("ERROR", e)
            continue
        print("bytes:", len(h))
        {"week": dig_week, "injuries": dig_injuries, "depth": dig_depth,
         "stats": dig_stats, "defstats": dig_stats, "player": dig_player,
         "game": dig_game}[k](h)
    dest.write_text("".join(OUT)[:400_000], encoding="utf-8")


if __name__ == "__main__":
    main()
