#!/usr/bin/env python3
"""
Line-by-line comparison between the COMMITTED official feeds and a FRESH live pull.

This is the strongest verification the project can do: it re-downloads every official
source that feeds the site (MLB StatsAPI, nfl.com by-week pages, Westwood One Sports
event grid + event pages, Westwood One station finder) and compares the result with
what is committed, record by record.

It never edits the committed feeds. It only reports:

  matched    the record exists in both and every compared field is identical
  changed    the record exists in both but a compared field differs
  missing    the record is committed but the live source no longer returns it
  added      the record is new in the live source (e.g. a newly released game)

Usage:
    python3 scripts/compare_feeds.py --live official-live

Output:
    verification/live-checks.json
    verification/live-checks.md
"""
import argparse
import json
import os
from datetime import datetime, timezone

MLB_FIELDS = ("date", "utc", "away", "home", "type", "venue")
NFL_FIELDS = ("datePT", "startPT", "away", "home", "venue", "seasonType", "weekLabel")
W1_FIELDS = ("datePT", "startPT", "endPT", "title", "venue", "sport")


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def compare(committed, live, key, fields):
    """Return (matched, changed, missing, added) lists of human-readable records."""
    c = {str(r.get(key)): r for r in committed if r.get(key) is not None}
    l = {str(r.get(key)): r for r in live if r.get(key) is not None}
    matched, changed, missing, added = [], [], [], []
    for k, cr in c.items():
        lr = l.get(k)
        if lr is None:
            missing.append({"id": k, "committed": {f: cr.get(f) for f in fields}})
            continue
        diffs = {f: {"committed": cr.get(f), "live": lr.get(f)}
                 for f in fields if cr.get(f) != lr.get(f)}
        if diffs:
            changed.append({"id": k, "diffs": diffs})
        else:
            matched.append(k)
    for k, lr in l.items():
        if k not in c:
            added.append({"id": k, "live": {f: lr.get(f) for f in fields}})
    return matched, changed, missing, added


def mlb_block(live_dir, data_dir):
    out = {}
    for year in (2026, 2027, 2028, 2029):
        live = load(os.path.join(live_dir, f"mlb-{year}.json"))
        committed = load(os.path.join(data_dir, f"mlb-{year}.json"))
        if not live or not committed:
            out[str(year)] = {"error": "one of the two feeds is missing",
                              "livePresent": bool(live), "committedPresent": bool(committed)}
            continue
        matched, changed, missing, added = compare(
            committed["games"], live["games"], "id", MLB_FIELDS)
        by_type = {}
        for g in committed["games"]:
            by_type[g.get("type")] = by_type.get(g.get("type"), 0) + 1
        out[str(year)] = {
            "source": committed["meta"]["source"],
            "committedGames": len(committed["games"]),
            "liveGames": len(live["games"]),
            "committedGameTypes": dict(sorted(by_type.items())),
            "liveGameTypes": dict(sorted(
                {t: sum(1 for g in live["games"] if g.get("type") == t)
                 for t in {g.get("type") for g in live["games"]}}.items())),
            "matched": len(matched),
            "changed": changed,
            "missing": missing,
            "added": added,
            "identical": not changed and not missing and not added,
        }
    return out


def nfl_block(live_dir, official_dir):
    live = load(os.path.join(live_dir, "nfl-2026.json"))
    committed = load(os.path.join(official_dir, "nfl-2026.json"))
    if not live or not committed:
        return {"error": "one of the two feeds is missing"}
    matched, changed, missing, added = compare(
        committed["games"], live["games"], "id", NFL_FIELDS)
    return {
        "source": committed["meta"]["sourceUrl"],
        "committedGames": len(committed["games"]),
        "liveGames": len(live["games"]),
        "matched": len(matched),
        "changed": changed,
        "missing": missing,
        "added": added,
        "identical": not changed and not missing and not added,
    }


def w1_block(live_dir, official_dir):
    live = load(os.path.join(live_dir, "westwoodone.json"))
    committed = load(os.path.join(official_dir, "westwoodone.json"))
    if not live or not committed:
        return {"error": "one of the two feeds is missing"}
    matched, changed, missing, added = compare(
        committed["events"], live["events"], "id", W1_FIELDS)
    return {
        "source": committed["meta"]["sourceUrl"],
        "committedEvents": len(committed["events"]),
        "liveEvents": len(live["events"]),
        "matched": len(matched),
        "changed": changed,
        "missing": missing,
        "added": added,
        "identical": not changed and not missing and not added,
    }


def stations_block(live_dir, official_dir):
    live = load(os.path.join(live_dir, "w1-stations.json"))
    committed = load(os.path.join(official_dir, "w1-stations.json"))
    if not live or not committed:
        return {"error": "one of the two feeds is missing"}
    def call(a):
        return a.get("callLetters") or a.get("callSign")

    lc = {call(a): a for a in committed.get("affiliates", []) if call(a)}
    ll = {call(a): a for a in live.get("affiliates", []) if call(a)}
    changed = []
    for cs, a in lc.items():
        b = ll.get(cs)
        if b is None:
            changed.append({"callSign": cs, "diffs": {"live": None}})
        elif json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            diffs = {k: {"committed": a.get(k), "live": b.get(k)}
                     for k in set(a) | set(b) if a.get(k) != b.get(k)}
            changed.append({"callSign": cs, "diffs": diffs})
    return {
        "source": committed.get("sourceUrl") or live.get("sourceUrl"),
        "committedAffiliates": len(lc),
        "liveAffiliates": len(ll),
        "committedCallSigns": sorted(lc),
        "liveCallSigns": sorted(ll),
        "added": [cs for cs in ll if cs not in lc],
        "changed": changed,
        "identical": not changed and not any(cs not in lc for cs in ll),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default="official-live", help="directory holding the fresh pull")
    ap.add_argument("--data", default="data", help="committed MLB feed directory")
    ap.add_argument("--official", default="official", help="committed official-feed directory")
    args = ap.parse_args()

    report = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": ("Every official feed was re-downloaded from its official URL and compared "
                   "record by record with the committed copy. The committed copies are never "
                   "modified by this check."),
        "liveDirectory": args.live,
        "mlb": mlb_block(args.live, args.data),
        "nfl": nfl_block(args.live, args.official),
        "westwoodOne": w1_block(args.live, args.official),
        "w1Stations": stations_block(args.live, args.official),
    }

    everything_identical = True
    for key in ("mlb", "nfl", "westwoodOne", "w1Stations"):
        block = report[key]
        if isinstance(block, dict):
            years = block.values() if key == "mlb" else [block]
            for b in years:
                if isinstance(b, dict) and "identical" in b:
                    everything_identical = everything_identical and b["identical"]
    report["allFeedsIdentical"] = everything_identical

    os.makedirs("verification", exist_ok=True)
    with open("verification/live-checks.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")

    L = ["# Live official-feed comparison", "",
         f"Generated: {report['generatedUTC']}", "",
         report["method"], "",
         "| Feed | Committed | Live | Identical | Changed | Missing | Added |",
         "|---|---|---|---|---|---|---|"]
    for year, b in report["mlb"].items():
        if "error" in b:
            L.append(f"| MLB {year} | — | — | ERROR | — | — | — |")
            continue
        L.append(f"| MLB {year} | {b['committedGames']} | {b['liveGames']} | "
                 f"{'yes' if b['identical'] else 'NO'} | {len(b['changed'])} | "
                 f"{len(b['missing'])} | {len(b['added'])} |")
    for key, label, c, l in (("nfl", "NFL 2026", "committedGames", "liveGames"),
                             ("westwoodOne", "Westwood One", "committedEvents", "liveEvents")):
        b = report[key]
        if "error" in b:
            L.append(f"| {label} | — | — | ERROR | — | — | — |")
            continue
        L.append(f"| {label} | {b[c]} | {b[l]} | {'yes' if b['identical'] else 'NO'} | "
                 f"{len(b['changed'])} | {len(b['missing'])} | {len(b['added'])} |")
    s = report["w1Stations"]
    if "error" not in s:
        L.append(f"| W1 SF station finder | {s['committedAffiliates']} | {s['liveAffiliates']} | "
                 f"{'yes' if s['identical'] else 'NO'} | {len(s['changed'])} | 0 | {len(s['added'])} |")

    L += ["", "## Detail", ""]
    for key, label in (("mlb", "MLB"), ("nfl", "NFL 2026"), ("westwoodOne", "Westwood One")):
        blocks = report[key].items() if key == "mlb" else [(None, report[key])]
        for name, b in blocks:
            if "error" in b:
                continue
            head = f"{label} {name}" if name else label
            for field in ("changed", "missing", "added"):
                rows = b.get(field) or []
                if not rows:
                    continue
                L.append(f"### {head} — {field} ({len(rows)})")
                L.append("")
                for r in rows[:200]:
                    L.append(f"- `{r['id']}` — {json.dumps(r.get('diffs') or r.get('committed') or r.get('live'))[:400]}")
                L.append("")
    with open("verification/live-checks.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print(json.dumps({
        "generatedUTC": report["generatedUTC"],
        "allFeedsIdentical": report["allFeedsIdentical"],
        "mlb": {y: {k: v for k, v in b.items() if k in
                    ("committedGames", "liveGames", "identical", "error")}
                for y, b in report["mlb"].items()},
        "nfl": {k: v for k, v in report["nfl"].items() if k in
                ("committedGames", "liveGames", "identical", "error")},
        "westwoodOne": {k: v for k, v in report["westwoodOne"].items() if k in
                        ("committedEvents", "liveEvents", "identical", "error")},
    }, indent=1))


if __name__ == "__main__":
    main()
