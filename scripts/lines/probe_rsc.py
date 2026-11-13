#!/usr/bin/env python3
"""Probe the official pages the NFL-lines workstream depends on and record their structure.

Runs on GitHub Actions (runners have outbound internet; the sandbox does not). For each
official URL it downloads the raw bytes exactly as served and records the structure of
whatever structured payload the page carries:

  * NFL.com Next.js RSC payloads (both react-query objects and plain embedded JSON)
  * server-rendered HTML tables (club depth charts, player stat pages, injury pages)

Committed output (small, reviewable):
  research/lines-probe/schema-map.json   query keys, deep payload shapes, sample records
  research/lines-probe/html-samples.json trimmed HTML table samples per page

Raw HTML is deliberately NOT committed: it is bulky and carries no sports facts.

This script derives no sports fact. It records page structure only.
"""
import concurrent.futures
import json
import os
import re
import time
import traceback
import urllib.request

RAW = "research/lines-raw"          # raw bytes, kept out of git
OUT = "research/lines-probe"        # committed structural maps
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5NFLLines/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = [
    ("schedule-2026-w9", "https://www.nfl.com/schedules/2026/by-week/week-9"),
    ("game-stats-2026-w10", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=stats"),
    ("player-stats-2026", "https://www.nfl.com/players/amon-ra-st-brown/stats"),
    ("injuries", "https://www.nfl.com/injuries/"),
    ("inactives", "https://www.nfl.com/inactives/"),
    ("standings-2026", "https://www.nfl.com/standings/league/2026/REG"),
    ("depth-chart-49ers", "https://www.49ers.com/team/depth-chart/"),
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


def rsc_payloads(page):
    """Yield every JSON object embedded in the Next.js RSC push payloads."""
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
            yield json.loads(payload.split(":", 1)[1])
        except Exception:
            continue


def rsc_query_objects(page):
    for obj in rsc_payloads(page):
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    yield cur
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def shape(obj, depth=0, maxdepth=9):
    """Structural summary of a JSON value: keys and container lengths, no values."""
    if depth > maxdepth:
        return "..."
    if isinstance(obj, dict):
        return {k: shape(obj[k], depth + 1, maxdepth) for k in list(obj)[:60]}
    if isinstance(obj, list):
        if not obj:
            return []
        return [shape(obj[0], depth + 1, maxdepth), f"len={len(obj)}"]
    return type(obj).__name__


def first_record(data):
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v[0]
        return data
    return data


def trim(obj, depth=0, maxdepth=9):
    if depth > maxdepth:
        return "..."
    if isinstance(obj, dict):
        return {k: trim(v, depth + 1, maxdepth) for k, v in list(obj.items())[:60]}
    if isinstance(obj, list):
        out = [trim(v, depth + 1, maxdepth) for v in obj[:2]]
        if len(obj) > 2:
            out.append(f"...len={len(obj)}")
        return out
    if isinstance(obj, str) and len(obj) > 200:
        return obj[:200] + "...[truncated]"
    return obj


def html_table_samples(page, limit=3, maxlen=2200):
    """Trimmed outer HTML of the first few <table> elements."""
    out = []
    for m in re.finditer(r"<table\b.*?</table>", page, re.S | re.I):
        block = m.group(0)
        if len(block) > maxlen:
            block = block[:maxlen] + "...[truncated]"
        out.append(block)
        if len(out) >= limit:
            break
    return out


def html_text_windows(page, needles, width=1400, limit=8):
    """Text windows around each needle, for pages whose data is server-rendered text."""
    out = []
    for needle in needles:
        for m in re.finditer(re.escape(needle), page):
            start = max(0, m.start() - 200)
            out.append(page[start:start + width])
            if len(out) >= limit:
                return out
    return out


def probe(item):
    slug, url = item
    try:
        page = get(url)
        if page is None:
            return {"slug": slug, "url": url, "ok": False, "error": "fetch failed", "queryKeys": []}, []
        os.makedirs(RAW, exist_ok=True)
        with open(os.path.join(RAW, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(page)

        info = {"slug": slug, "url": url, "ok": True, "bytes": len(page), "queryKeys": [], "rscShapes": []}
        seen = set()
        for q in rsc_query_objects(page):
            key = q.get("queryKey")
            if not isinstance(key, list) or not key:
                continue
            name = key[0] if isinstance(key[0], str) else json.dumps(key[0], default=str)
            if name in seen:
                continue
            seen.add(name)
            state = q.get("state") or {}
            data = state.get("data")
            info["queryKeys"].append({
                "queryKey": [name] + [str(k)[:100] for k in key[1:6]],
                "status": state.get("status"),
                "dataShape": shape(data),
                "sampleRecord": trim(first_record(data)),
            })

        # whole-page RSC tree (covers payloads that are not react-query)
        tree = []
        for obj in rsc_payloads(page):
            tree.append(shape(obj))
            if len(tree) >= 12:
                break
        info["rscShapes"] = tree

        samples = html_table_samples(page)
        windows = html_text_windows(page, ["Injuries - WEEK", "Out</", "Did Not Participate"])
        return info, {"slug": slug, "tables": samples, "windows": windows}
    except Exception:  # noqa: BLE001 - never fail the probe run
        return ({"slug": slug, "url": url, "ok": False, "error": traceback.format_exc()[-1500:],
                 "queryKeys": [], "rscShapes": []}, [])


def main():
    results = []
    samples = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for info, smp in ex.map(probe, TARGETS):
            results.append(info)
            samples.append(smp)
            print(f"  {info['slug']}: ok={info.get('ok')} keys={len(info.get('queryKeys') or [])}")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "schema-map.json"), "w") as f:
        json.dump(results, f, indent=1, default=str)
    with open(os.path.join(OUT, "html-samples.json"), "w") as f:
        json.dump(samples, f, indent=1, default=str)
    print("wrote", os.path.join(OUT, "schema-map.json"))


if __name__ == "__main__":
    main()
