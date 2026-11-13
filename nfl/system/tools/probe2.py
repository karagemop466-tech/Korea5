#!/usr/bin/env python3
"""Second probe: confirm remaining official endpoints needed for the market system.

  * 2026 club roster page  -> gives official nfl.com /players/<slug>/ ids
  * player-stat leaderboards (candidate URL shapes, which one returns 200)
  * 2025 week page         -> same score markup as 2026? (multi-season sample)
  * depth-chart section headings (Offense / Defense / Special Teams) markup
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5NFLResearch/1.0)"}

CANDIDATES = {
    "roster_49ers": ["https://www.nfl.com/teams/san-francisco-49ers/roster"],
    "leaders_passing": [
        "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all",
        "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all?sort=passingYards",
        "https://www.nfl.com/stats/2026/reg/passing",
    ],
    "leaders_rushing": [
        "https://www.nfl.com/stats/player-stats/category/rushing/2026/reg/all",
    ],
    "leaders_receiving": [
        "https://www.nfl.com/stats/player-stats/category/receiving/2026/reg/all",
    ],
    "week2025": ["https://www.nfl.com/schedules/2025/by-week/week-5"],
    "injuries_2025": ["https://www.nfl.com/injuries/league/2025/reg01"],
    "depth_2025_packers": ["https://www.packers.com/team/depth-chart"],
}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return None, f"ERR {e!r}"


def main():
    out = {"results": {}}
    lines = []
    for key, urls in CANDIDATES.items():
        for u in urls:
            st, body = get(u)
            info = {"url": u, "http": st, "bytes": len(body)}
            if key.startswith("leaders"):
                info["playerLinks"] = len(re.findall(r'href="/players/[a-z0-9-]+/"', body))
                m = re.search(r"<thead>.*?</thead>", body, re.S)
                info["thead"] = re.sub(r"<[^>]+>", "|", m.group(0))[:300] if m else None
                info["jsonPlayerId"] = len(re.findall(r'"playerId"', body))
            if key == "roster_49ers":
                info["playerLinks"] = len(re.findall(r'href="/players/[a-z0-9-]+/"', body))
                slugs = re.findall(r'href="/players/([a-z0-9-]+)/"', body)
                info["sampleSlugs"] = slugs[:6]
            if key.startswith("week"):
                info["finalLinks"] = len(re.findall(r"gameState&quot;:&quot;FINAL", body))
                m = re.search(r"linkName&quot;:&quot;([^&]*)&quot;", body)
                info["sampleLinkName"] = m.group(1) if m else None
            if key.startswith("injuries"):
                info["tables"] = len(re.findall(r"<table", body))
            if key.startswith("depth"):
                info["rosterRows"] = len(re.findall(r"players-roster/", body))
                secs = re.findall(r'd3-o-section-sub-title"><span>([^<]{2,20})</span>', body)
                info["sectionTitles"] = secs[:12]
                m = re.search(r"(Offense|Defense|Special Teams)", body)
                if m:
                    p = m.start()
                    lines.append("\n### depth section context (" + key + ")\n" + body[max(0, p - 600):p + 400])
            out["results"][key + ":" + u] = info
            print(key, st, info)
    dest = ROOT / "research"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "probe2.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (dest / "dig2.txt").write_text("".join(lines)[:200_000], encoding="utf-8")


if __name__ == "__main__":
    main()
