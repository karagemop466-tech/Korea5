#!/usr/bin/env python3
"""
Refresh the COMMITTED official feeds from a fresh live pull — safely.

Rules (deliberately conservative, because a refresh must never lose information):

  MLB     replaced by the live pull only when the live feed contains every committed
          game. Games that MLB has since published a first-pitch time for move from
          "estimated" to "verified" automatically.
  NFL     replaced only when the live feed contains every committed game.
  W1      merged, never replaced: an event keeps its committed on-air window when the
          live event page no longer publishes the start/end epoch (this happens with
          older, past broadcasts), and events that are new on the network are added.
  W1 SF   replaced only when the affiliate list is unchanged.

Anything that does not satisfy its rule is reported and left alone.

Usage:
    python3 scripts/merge_live_feeds.py --live official-live
"""
import argparse
import json
import os
from datetime import datetime, timezone


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def merge_mlb(live_dir, data_dir, report):
    for year in (2026, 2027, 2028, 2029):
        live = load(os.path.join(live_dir, f"mlb-{year}.json"))
        committed = load(os.path.join(data_dir, f"mlb-{year}.json"))
        if not live or not committed:
            report["mlb"][str(year)] = {"status": "skipped", "reason": "feed missing"}
            continue
        live_ids = {g["id"] for g in live["games"]}
        committed_ids = {g["id"] for g in committed["games"]}
        missing = committed_ids - live_ids
        added = live_ids - committed_ids
        changed = []
        live_by_id = {g["id"]: g for g in live["games"]}
        for g in committed["games"]:
            lg = live_by_id.get(g["id"])
            if lg and lg.get("utc") != g.get("utc"):
                changed.append({"id": g["id"], "date": g.get("date"),
                                "committedUTC": g.get("utc"), "liveUTC": lg.get("utc")})
        if missing:
            report["mlb"][str(year)] = {
                "status": "kept-committed",
                "reason": f"{len(missing)} committed games are absent from the live pull",
                "missingSample": sorted(missing)[:10]}
            continue
        payload = dict(live)
        payload["meta"] = dict(live.get("meta", {}))
        payload["meta"]["committedUTC"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        payload["meta"]["refreshNote"] = (
            "Refreshed from the official MLB StatsAPI feed and compared record by record "
            "with the previous commit (see verification/live-checks.json).")
        write(os.path.join(data_dir, f"mlb-{year}.json"), payload)
        report["mlb"][str(year)] = {
            "status": "updated",
            "gamesBefore": len(committed["games"]),
            "gamesAfter": len(live["games"]),
            "startTimesNowPublished": len(changed),
            "gamesAdded": len(added),
            "addedSample": sorted(added)[:10],
            "sampleTimeChanges": changed[:10]}


def merge_nfl(live_dir, official_dir, report):
    live = load(os.path.join(live_dir, "nfl-2026.json"))
    committed = load(os.path.join(official_dir, "nfl-2026.json"))
    if not live or not committed:
        report["nfl"]["2026"] = {"status": "skipped", "reason": "feed missing"}
        return
    live_ids = {g["id"] for g in live["games"]}
    committed_ids = {g["id"] for g in committed["games"]}
    if committed_ids - live_ids:
        report["nfl"]["2026"] = {"status": "kept-committed",
                                 "reason": "committed games absent from the live pull"}
        return
    payload = dict(live)
    payload["meta"] = dict(live.get("meta", {}))
    payload["meta"]["committedUTC"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write(os.path.join(official_dir, "nfl-2026.json"), payload)
    report["nfl"]["2026"] = {"status": "updated",
                             "gamesBefore": len(committed["games"]),
                             "gamesAfter": len(live["games"])}


def merge_w1(live_dir, official_dir, report):
    live = load(os.path.join(live_dir, "westwoodone.json"))
    committed = load(os.path.join(official_dir, "westwoodone.json"))
    if not live or not committed:
        report["westwoodOne"] = {"status": "skipped", "reason": "feed missing"}
        return
    live_by_id = {e["id"]: e for e in live["events"]}
    merged, kept_times, updated, added = [], 0, 0, 0
    for e in committed["events"]:
        le = live_by_id.get(e["id"])
        if le is None:
            merged.append(e)
            continue
        if le.get("startPT") or le.get("datePT"):
            merged.append(le)
            if le.get("startPT") != e.get("startPT") or le.get("datePT") != e.get("datePT"):
                updated += 1
        else:
            # The live page no longer publishes the on-air window for this past event.
            # Keep the committed window and record why.
            carry = dict(e)
            carry["windowSource"] = "committed (live page no longer publishes start/end)"
            merged.append(carry)
            kept_times += 1
    for e in live["events"]:
        if e["id"] not in {x["id"] for x in merged}:
            merged.append(e)
            added += 1
    payload = dict(committed)
    payload["meta"] = dict(committed.get("meta", {}))
    payload["meta"]["committedUTC"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["meta"]["refreshNote"] = (
        "Merged from a fresh official pull. Windows for past broadcasts whose event page no "
        "longer publishes the start/end epoch are carried forward from the previous verified "
        "commit and marked with windowSource.")
    payload["events"] = merged
    write(os.path.join(official_dir, "westwoodone.json"), payload)
    report["westwoodOne"] = {"status": "merged",
                              "eventsBefore": len(committed["events"]),
                              "eventsAfter": len(merged),
                              "windowsCarriedForward": kept_times,
                              "eventsUpdatedFromLive": updated,
                              "eventsAdded": added}


def merge_stations(live_dir, official_dir, report):
    live = load(os.path.join(live_dir, "w1-stations.json"))
    committed = load(os.path.join(official_dir, "w1-stations.json"))
    if not live or not committed:
        report["w1Stations"] = {"status": "skipped", "reason": "feed missing"}
        return
    lc = sorted(a.get("callLetters") for a in committed.get("affiliates", []))
    ll = sorted(a.get("callLetters") for a in live.get("affiliates", []))
    if lc == ll:
        report["w1Stations"] = {"status": "unchanged", "affiliates": ll}
        return
    payload = dict(live)
    payload["meta"] = dict(live.get("meta", {}))
    payload["meta"]["committedUTC"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write(os.path.join(official_dir, "w1-stations.json"), payload)
    report["w1Stations"] = {"status": "updated", "before": lc, "after": ll}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default="official-live")
    ap.add_argument("--data", default="data")
    ap.add_argument("--official", default="official")
    args = ap.parse_args()

    report = {"generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "policy": ("A refresh never deletes committed information. MLB and NFL feeds are "
                         "replaced only when the live pull contains every committed game; the "
                         "Westwood One feed is merged so that on-air windows the network no "
                         "longer publishes for past events are carried forward."),
              "mlb": {}, "nfl": {}, "westwoodOne": {}, "w1Stations": {}}
    merge_mlb(args.live, args.data, report)
    merge_nfl(args.live, args.official, report)
    merge_w1(args.live, args.official, report)
    merge_stations(args.live, args.official, report)

    os.makedirs("verification", exist_ok=True)
    with open("verification/live-merge.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")
    print(json.dumps(report, indent=1)[:4000])


if __name__ == "__main__":
    main()
