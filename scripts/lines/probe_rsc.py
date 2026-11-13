#!/usr/bin/env python3
"""Probe the official pages the NFL-lines workstream depends on and record their structure.

Runs on GitHub Actions (runners have outbound internet; the sandbox does not). For each
official URL it downloads the raw bytes exactly as served and, for NFL.com pages,
decompresses the React Server Component payloads that carry the structured data.

Outputs (uploaded as a workflow artifact, not committed):
  research/lines-raw/<slug>.html.gz          raw bytes exactly as served
  research/lines-raw/payloads/<slug>__<key>.json.gz   full dehydrated react-query payloads
  research/lines-raw/schema-map.json         query keys + payload shapes (no sports values)

This script derives no sports fact. It records page structure so the parser can be written
against the real markup instead of a guess.
"""
import concurrent.futures
import gzip
import json
import os
import re
import time
import traceback
import urllib.request

RAW = "research/lines-raw"
PAYLOADS = os.path.join(RAW, "payloads")
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5NFLLines/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = [
    ("schedule-2026-w9", "https://www.nfl.com/schedules/2026/by-week/week-9"),
    ("schedule-2025-w1", "https://www.nfl.com/schedules/2025/by-week/week-1"),
    ("game-stats-2026-w10", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=stats"),
    ("game-stats-2026-w9", "https://www.nfl.com/games/commanders-at-giants-2026-reg-9?tab=stats"),
    ("game-overview-2026-w10", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=overview"),
    ("player-stats-2026", "https://www.nfl.com/players/amon-ra-st-brown/stats"),
    ("player-logs-2026", "https://www.nfl.com/players/amon-ra-st-brown/stats/logs/"),
    ("player-stats-2025", "https://www.nfl.com/players/amon-ra-st-brown/stats/?season=2025"),
    ("injuries", "https://www.nfl.com/injuries/"),
    ("injuries-week9", "https://www.nfl.com/injuries/?week=9"),
    ("inactives", "https://www.nfl.com/inactives/"),
    ("standings-2026", "https://www.nfl.com/standings/league/2026/REG"),
    ("team-page-lions", "https://www.nfl.com/teams/detroit-lions/"),
    ("stats-team", "https://www.nfl.com/stats/team-stats/"),
    ("stats-player", "https://www.nfl.com/stats/player-stats/"),
    ("depth-chart-49ers", "https://www.49ers.com/team/depth-chart/"),
    ("depth-chart-lions", "https://www.detroitlions.com/team/depth-chart/"),
    ("depth-chart-chiefs", "https://www.chiefs.com/team/depth-chart/"),
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
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def shape(obj, depth=0, maxdepth=4):
    """Structural summary of a JSON value: keys and container lengths, no values."""
    if depth > maxdepth:
        return "..."
    if isinstance(obj, dict):
        return {k: shape(obj[k], depth + 1, maxdepth) for k in list(obj)[:40]}
    if isinstance(obj, list):
        if not obj:
            return []
        return [shape(obj[0], depth + 1, maxdepth), f"len={len(obj)}"]
    return type(obj).__name__


def safe_slug(text):
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(text))[:120]


def probe(item):
    slug, url = item
    try:
        page = get(url)
        if page is None:
            return {"slug": slug, "url": url, "ok": False, "error": "fetch failed", "queryKeys": []}
        os.makedirs(PAYLOADS, exist_ok=True)
        with gzip.open(os.path.join(RAW, f"{slug}.html.gz"), "wt", encoding="utf-8") as f:
            f.write(page)

        info = {"slug": slug, "url": url, "ok": True, "bytes": len(page), "queryKeys": []}
        seen = set()
        for q in rsc_objects(page):
            key = q.get("queryKey")
            if not isinstance(key, list) or not key:
                continue
            # dedupe on the first element only: later elements may be unhashable objects
            name = key[0] if isinstance(key[0], str) else json.dumps(key[0], default=str)
            if name in seen:
                continue
            seen.add(name)
            state = q.get("state") or {}
            data = state.get("data")
            fn = os.path.join(PAYLOADS, f"{slug}__{safe_slug(name)}.json.gz")
            try:
                with gzip.open(fn, "wt", encoding="utf-8") as f:
                    json.dump(q, f, indent=1, default=str)
            except Exception as e:  # noqa: BLE001
                print(f"    payload write failed {slug}/{name}: {e}")
            info["queryKeys"].append({
                "queryKey": [name] + [str(k)[:80] for k in key[1:6]],
                "status": state.get("status"),
                "dataShape": shape(data),
            })
        return info
    except Exception:  # noqa: BLE001 - never fail the probe run
        return {"slug": slug, "url": url, "ok": False, "error": traceback.format_exc()[-1500:], "queryKeys": []}


def main():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for info in ex.map(probe, TARGETS):
            results.append(info)
            print(f"  {info['slug']}: ok={info.get('ok')} keys={len(info.get('queryKeys') or [])}")
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, "schema-map.json"), "w") as f:
        json.dump(results, f, indent=1, default=str)
    print("wrote", os.path.join(RAW, "schema-map.json"))


if __name__ == "__main__":
    main()
