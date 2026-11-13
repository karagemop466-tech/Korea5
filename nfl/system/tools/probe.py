#!/usr/bin/env python3
"""Probe official NFL sources and dump raw bytes + a diagnostics report.

Runs on GitHub Actions (the sandbox shell has no outbound internet; the Actions
runner does). Nothing here interprets a value — it only records what each
official page actually returns, so the parsers in fetch_official.py are written
against real bytes instead of assumptions.

Writes:
  nfl/research/raw/<slug>.txt      first N bytes of each fetched page
  nfl/research/probe.json          status, size, http code, and grep diagnostics
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5NFLResearch/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}

SOURCES = {
    # schedule / results (regular season weeks)
    "nfl_week5": "https://www.nfl.com/schedules/2026/by-week/week-5",
    "nfl_week10": "https://www.nfl.com/schedules/2026/by-week/week-10",
    # injuries
    "injuries_reg10": "https://www.nfl.com/injuries/league/2026/reg10",
    # depth charts (club official sites)
    "depth_49ers": "https://www.49ers.com/team/depth-chart",
    "depth_chiefs": "https://www.chiefs.com/team/depth-chart",
    # team stats
    "stats_off_passing": "https://www.nfl.com/stats/team-stats/offense/passing/2026/reg/all",
    "stats_def_passing": "https://www.nfl.com/stats/team-stats/defense/passing/2026/reg/all",
    "stats_off_scoring": "https://www.nfl.com/stats/team-stats/offense/scoring/2026/reg/all",
    "stats_def_scoring": "https://www.nfl.com/stats/team-stats/defense/scoring/2026/reg/all",
    # a game page: does it publish odds?
    "game_sf_dal": "https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10",
    # player stats page (prop-relevant official distribution)
    "player_cmc": "https://www.nfl.com/players/christian-mccaffrey/stats",
    # rules / injury policy (for gate definitions, not values)
    "nfl_rulebook": "https://operations.nfl.com/the-rules/2026-nfl-rulebook/",
}

# Diagnostics: regexes whose match counts tell us whether a field is machine-readable.
DIAGNOSTICS = {
    "nfl_week5": [
        ("rsc_push_blocks", r"self\.__next_f\.push"),
        ("weeklyGameDetails", r"useFetchFootballWeeklyGameDetails"),
        ("score_field", r'"score"\s*:'),
        ("home_score", r'"homeTeam".{0,400}?"score"'),
        ("final_status", r'"status"\s*:\s*"?FINAL'),
        ("odds_field", r'"(?:odds|spread|moneyline|pointSpread)"'),
    ],
    "nfl_week10": [
        ("rsc_push_blocks", r"self\.__next_f\.push"),
        ("weeklyGameDetails", r"useFetchFootballWeeklyGameDetails"),
        ("score_field", r'"score"\s*:'),
        ("odds_field", r'"(?:odds|spread|moneyline|pointSpread)"'),
    ],
    "injuries_reg10": [
        ("injury_row_json", r'"injuryStatus"|"practiceStatus"'),
        ("table_headers", r"<th[^>]*>\s*(?:Player|Position|Injuries|Practice Status|Game Status)"),
        ("rsc_push_blocks", r"self\.__next_f\.push"),
    ],
    "depth_49ers": [
        ("depth_rows", r"team/players-roster/"),
        ("updated_as_of", r"Updated as of"),
    ],
    "depth_chiefs": [
        ("depth_rows", r"team/players-roster/"),
        ("unofficial_note", r"Unofficial Depth Chart"),
    ],
    "stats_off_passing": [
        ("stat_rows", r"team-stats/offense/passing"),
        ("table_cells", r"<td"),
    ],
    "stats_def_passing": [("stat_rows", r"<td"), ("rsc_push_blocks", r"self\.__next_f\.push")],
    "stats_off_scoring": [("stat_rows", r"<td")],
    "stats_def_scoring": [("stat_rows", r"<td")],
    "game_sf_dal": [
        ("odds_field", r'"(?:odds|spread|moneyline|pointSpread|overUnder)"'),
        ("odds_word", r"[Oo]dds"),
        ("injury_list", r"Did not participate|Full participation|Limited participation"),
    ],
    "player_cmc": [
        ("game_log", r"[Gg]ame [Ll]og"),
        ("stat_table", r"<td"),
        ("rsc_push_blocks", r"self\.__next_f\.push"),
    ],
    "nfl_rulebook": [("injury_report_section", r"[Ii]njury [Rr]eport")],
}


def get(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - diagnostics only
        return None, f"ERROR: {e!r}"


def main():
    report = {"generatedUTC": __import__("datetime").datetime.utcnow().isoformat() + "Z",
              "note": "Raw probe only. No value in this file is published on the site; "
                      "it exists to prove which official fields are machine-readable.",
              "sources": {}}
    for slug, url in SOURCES.items():
        status, body = get(url)
        entry = {"url": url, "httpStatus": status, "bytes": len(body), "diagnostics": {}}
        text = body if isinstance(body, str) else ""
        for name, pattern in DIAGNOSTICS.get(slug, []):
            entry["diagnostics"][name] = len(re.findall(pattern, text))
        # keep a bounded sample so the repo does not balloon
        sample = text[:400_000]
        (RAW / f"{slug}.txt").write_text(sample, encoding="utf-8")
        entry["sampleBytes"] = len(sample)
        report["sources"][slug] = entry
        print(f"{slug:24s} http={status} bytes={len(body)} "
              f"{ {k: v for k, v in entry['diagnostics'].items()} }")
    (ROOT / "research" / "probe.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
