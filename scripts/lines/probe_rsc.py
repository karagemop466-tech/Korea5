#!/usr/bin/env python3
"""Probe the official pages the NFL-lines workstream depends on and record their structure.

Runs on GitHub Actions (runners have outbound internet; the sandbox does not). For each
official URL it downloads the raw bytes and, for NFL.com pages, decompresses the React
Server Component payloads that carry the structured data. The output is a *schema map*
(not data), so the parser can be written against the real structure instead of a guess.

Outputs (uploaded as a workflow artifact, not committed):
  research/lines-raw/<slug>.html.gz   raw bytes exactly as served
  research/lines-raw/schema-map.json  query keys, payload shapes, field names

Nothing here is a sports fact. No schedule, score, injury or player value is derived or
invented by this script.
"""
import concurrent.futures
import gzip
import json
import os
import re
import time
import urllib.request

RAW = "research/lines-raw"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5NFLLines/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = [
    ("schedule-week-9", "https://www.nfl.com/schedules/2026/by-week/week-9"),
    ("game-stats-reg10", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=stats"),
    ("game-overview-reg10", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=overview"),
    ("player-stats", "https://www.nfl.com/players/amon-ra-st-brown/stats"),
    ("player-logs", "https://www.nfl.com/players/amon-ra-st-brown/stats/logs/"),
    ("injuries", "https://www.nfl.com/injuries/"),
    ("inactives", "https://www.nfl.com/inactives/"),
    ("standings", "https://www.nfl.com/standings/league/2026/REG"),
    ("team-page", "https://www.nfl.com/teams/detroit-lions/"),
    ("depth-chart-49ers", "https://www.49ers.com/team/depth-chart/"),
    ("depth-chart-lions", "https://www.detroitlions.com/team/depth-chart/"),
]


def get(url, tries=3, timeout=90):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(1.5 + attempt)
    print(f"  ! failed {url}: {last}")
    return None


def rsc_objects(page):
    """Yield dehydrated react-query objects from NFL.com RSC payloads."""
    n = 0
    for raw in re.findall(r"self\.__next_f\.push\((\[.*?\])\)</script>", page, re.S):
        try:
            arr = json.loads(raw)
        except Exception:
            continue
        if not isinstance(arr, list) or len(arr) < 2 or not isinstance(arr[1], str):
            continue
        payload = arr[1]
        if ":" not in payload:
            continue
        try:
            obj = json.loads(payload.split(":", 1)[1])
        except Exception:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    yield cur
                    n += 1
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def shape(obj, depth=0, maxdepth=4):
    """Structural summary of a JSON value: keys and container lengths, no values."""
    if depth > maxdepth:
        return "..."
    if isinstance(obj, dict):
        out = {}
        for k in list(obj)[:40]:
            out[k] = shape(obj[k], depth + 1, maxdepth)
        return out
    if isinstance(obj, list):
        if not obj:
            return []
        return [shape(obj[0], depth + 1, maxdepth), f"len={len(obj)}"]
    return type(obj).__name__


def probe(item):
    slug, url = item
    page = get(url)
    if page is None:
        return slug, url, {"ok": False, "error": "fetch failed"}, None
    os.makedirs(RAW, exist_ok=True)
    with gzip.open(os.path.join(RAW, f"{slug}.html.gz"), "wt", encoding="utf-8") as f:
        f.write(page)

    info = {"ok": True, "bytes": len(page), "queryKeys": []}
    seen = set()
    for q in rsc_objects(page):
        key = tuple(q.get("queryKey") or [])
        if key in seen:
            continue
        seen.add(key)
        state = q.get("state") or {}
        data = state.get("data")
        info["queryKeys"].append({
            "queryKey": list(key),
            "status": state.get("status"),
            "dataShape": shape(data),
        })
    return slug, url, info, page


def main():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for slug, url, info, _page in ex.map(probe, TARGETS):
            results.append({"slug": slug, "url": url, "info": info})
            print(f"  {slug}: {info.get('ok')} keys={len(info.get('queryKeys') or [])}")
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, "schema-map.json"), "w") as f:
        json.dump(results, f, indent=1)
    print("wrote", os.path.join(RAW, "schema-map.json"))


if __name__ == "__main__":
    main()
