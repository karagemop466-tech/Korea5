#!/usr/bin/env python3
"""Fetch NFL injury reports and depth charts (nflverse mirror) and derive
team-level tracker data for the NFL lines lab.

Runs in GitHub Actions (the sandbox cannot reach release-asset hosts).

Sources (all names are as published by nflverse-data; the underlying injury
reports are the NFL's own weekly reports at https://www.nfl.com/injuries/league/<season>/reg<week>):
  https://github.com/nflverse/nflverse-data/releases/tag/injuries
  https://github.com/nflverse/nflverse-data/releases/tag/depth_charts

Outputs (committed; raw downloads are NOT committed):
  data/nfl-lab/injuries-team-week.json   per season/week/team counts, 2016-2026
  data/nfl-lab/injuries-2026.json        row-level 2026 Out/Doubtful/Questionable entries
  data/nfl-lab/depth-backups-2026.json   starters reported Out/Doubtful and the first healthy backup
  data/nfl-lab/fetch-log.json            what was downloaded, sizes, row counts, headers seen

Usage: python3 scripts/nfl_lab/fetch_injuries.py [--raw DIR]
"""
import argparse
import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "data", "nfl-lab")
INJ_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{y}.csv"
DEPTH_URL = "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_{y}.csv.gz"
INJ_SEASONS = range(2016, 2027)
DEPTH_SEASONS = [2025, 2026]
STATUSES = ["Out", "Doubtful", "Questionable"]
GROUPS = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    "T": "OL", "G": "OL", "C": "OL", "OT": "OL", "OG": "OL", "OL": "OL", "LS": "ST",
    "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "EDGE": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "DB": "DB",
    "K": "ST", "P": "ST",
}


def fetch(url, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nfl-lab-data/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - report any failure
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


def read_csv_bytes(b):
    return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(REPO, ".raw-nfl"))
    args = ap.parse_args()
    os.makedirs(args.raw, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    log = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "injuries": {}, "depth": {}, "errors": []}

    # ---- injuries -------------------------------------------------------
    team_week = defaultdict(lambda: {"Out": 0, "Doubtful": 0, "Questionable": 0,
                                     "by_group": defaultdict(lambda: {"Out": 0, "Doubtful": 0, "Questionable": 0})})
    rows_2026 = []
    headers_seen = None
    for y in INJ_SEASONS:
        try:
            b = fetch(INJ_URL.format(y=y))
        except Exception as e:  # noqa: BLE001
            log["errors"].append(str(e))
            continue
        with open(os.path.join(args.raw, f"injuries_{y}.csv"), "wb") as f:
            f.write(b)
        rows = read_csv_bytes(b)
        headers_seen = list(rows[0].keys()) if rows else []
        log["injuries"][str(y)] = {"rows": len(rows), "bytes": len(b), "headers": headers_seen}
        for r in rows:
            st = (r.get("report_status") or "").strip()
            if st not in STATUSES:
                continue
            team = (r.get("team") or "").strip()
            wk = (r.get("week") or "").strip()
            pos = (r.get("position") or "").strip().upper()
            grp = GROUPS.get(pos, "OTHER")
            key = (y, int(wk) if wk.isdigit() else wk, team)
            team_week[key][st] += 1
            team_week[key]["by_group"][grp][st] += 1
            if y == 2026:
                rows_2026.append({
                    "season": y, "week": wk, "team": team,
                    "player": (r.get("full_name") or "").strip(),
                    "gsis_id": (r.get("gsis_id") or "").strip(),
                    "position": pos, "group": grp,
                    "report_status": st,
                    "practice_status": (r.get("practice_status") or "").strip(),
                    "primary_injury": (r.get("report_primary_injury") or "").strip(),
                    "source": f"https://www.nfl.com/injuries/league/{y}/reg{wk}" if wk.isdigit() else "https://www.nfl.com/injuries/",
                })

    tw_out = []
    for (y, wk, team), v in sorted(team_week.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        tw_out.append({
            "season": y, "week": wk, "team": team,
            "Out": v["Out"], "Doubtful": v["Doubtful"], "Questionable": v["Questionable"],
            "by_group": {g: dict(c) for g, c in sorted(v["by_group"].items())},
            "source": f"https://www.nfl.com/injuries/league/{y}/reg{wk}" if isinstance(wk, int) else "https://www.nfl.com/injuries/",
        })
    with open(os.path.join(OUT, "injuries-team-week.json"), "w") as f:
        json.dump({"description": "Count of players listed Out/Doubtful/Questionable per team and week, by position group. Derived from nflverse mirror of NFL official weekly injury reports.",
                   "upstream": "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
                   "official_reference": "https://www.nfl.com/injuries/",
                   "rows": tw_out}, f, indent=1)
    rows_2026.sort(key=lambda r: (int(r["week"]) if str(r["week"]).isdigit() else 99, r["team"], r["position"]))
    with open(os.path.join(OUT, "injuries-2026.json"), "w") as f:
        json.dump({"description": "Row-level 2026 players listed Out, Doubtful or Questionable on the NFL official weekly injury report (via nflverse mirror).",
                   "upstream": "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
                   "rows": rows_2026}, f, indent=1)

    # ---- depth charts: latest snapshot vs latest official injury week -------
    # The nflverse depth file is a series of timestamped snapshots (column dt),
    # not week-keyed. The honest tracker therefore uses the most recent snapshot
    # per team against the most recent official injury report week.
    inj_week = max((int(r["week"]) for r in rows_2026 if str(r["week"]).isdigit()), default=None)
    inj_by_gsis = {r["gsis_id"]: r for r in rows_2026 if r["gsis_id"] and str(r["week"]) == str(inj_week)}
    backups = []
    starters_out = []
    depth_log = {}
    for y in DEPTH_SEASONS:
        try:
            b = fetch(DEPTH_URL.format(y=y))
        except Exception as e:  # noqa: BLE001
            log["errors"].append(str(e))
            continue
        rows = list(csv.DictReader(io.StringIO(gzip.decompress(b).decode("utf-8-sig"))))
        depth_log[str(y)] = {"rows": len(rows)}
        if y != DEPTH_SEASONS[-1]:
            continue
        latest_dt = {}
        for r in rows:
            t = r["team"]
            if r["dt"] > latest_dt.get(t, ""):
                latest_dt[t] = r["dt"]
        # default formation groups per team (most rows in the latest snapshot)
        from collections import Counter
        snap = {t: [r for r in rows if r["team"] == t and r["dt"] == latest_dt[t]] for t in latest_dt}
        depth_log["latest_dt_by_team"] = dict(sorted(latest_dt.items()))
        depth_log["groups_by_team"] = {t: dict(Counter(r["pos_grp"] for r in v).most_common(6)) for t, v in sorted(snap.items())}
        wk_inj = [r for r in rows_2026 if str(r["week"]) == str(inj_week)]
        diag = []
        for r in wk_inj:
            hits = [x for x in snap.get(r["team"], []) if x["gsis_id"] == r["gsis_id"]]
            diag.append({"team": r["team"], "player": r["player"], "gsis_id": r["gsis_id"], "status": r["report_status"],
                         "in_snapshot": [(h["pos_grp"], h["pos_abb"], h["pos_rank"]) for h in hits]})
        depth_log["match_diagnostics_week"] = diag
        for team, srows in sorted(snap.items()):
            grp_counts = Counter(r["pos_grp"] for r in srows)
            off_grp = "3WR 1TE" if "3WR 1TE" in grp_counts else None
            def_grp = max(["Base 4-3 D", "Base 3-4 D"], key=lambda g: grp_counts.get(g, 0))
            keep = [r for r in srows if r["pos_grp"] in {off_grp, def_grp, "Special Teams"}]
            by_slot = defaultdict(list)
            for r in keep:
                by_slot[r["pos_abb"]].append(r)
            for abb, players in by_slot.items():
                players.sort(key=lambda r: int(r["pos_rank"]) if str(r["pos_rank"]).isdigit() else 99)
                # dedupe by player within the slot list
                seen, ordered = set(), []
                for p in players:
                    if p["gsis_id"] in seen:
                        continue
                    seen.add(p["gsis_id"]); ordered.append(p)
                if not ordered:
                    continue
                injured_ahead = []
                eff_idx = None
                for idx, q in enumerate(ordered):
                    qi = inj_by_gsis.get(q["gsis_id"])
                    if qi and qi["report_status"] in ("Out", "Doubtful", "Questionable"):
                        injured_ahead.append({"player": q["player_name"], "depth_rank": q["pos_rank"],
                                              "status": qi["report_status"], "injury": qi["primary_injury"]})
                        continue
                    eff_idx = idx
                    break
                if not injured_ahead or eff_idx is None:
                    continue
                if not any(int(x["depth_rank"]) == 1 for x in injured_ahead) and eff_idx == 0:
                    continue
                eff = ordered[eff_idx]
                backups.append({
                    "team": team, "depth_slot": abb, "depth_group": eff["pos_grp"],
                    "original_starter": ordered[0]["player_name"],
                    "original_starter_out": any(x["depth_rank"] == "1" for x in injured_ahead),
                    "injured_ahead": injured_ahead,
                    "effective_starter": eff["player_name"],
                    "effective_depth_rank": eff["pos_rank"],
                    "effective_is_backup": eff_idx > 0,
                    "injury_week": inj_week,
                    "source": "https://www.nfl.com/injuries/league/2026/reg%s" % inj_week,
                    "depth_source": "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts",
                    "depth_snapshot_utc": latest_dt[team],
                })
    log["depth"] = depth_log
    with open(os.path.join(OUT, "depth-backups-2026.json"), "w") as f:
        json.dump({"description": "Latest depth chart snapshot (nflverse mirror of ESPN depth charts) per team, compared with the latest NFL official injury report week. For each depth slot where a player ahead on the chart is listed Out, Doubtful or Questionable, shows the injured players ahead and the first healthy player (the effective starter). Not week-keyed; a current tracker, not a historical record.",
                   "injury_week": inj_week,
                   "upstream_injuries": "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
                   "upstream_depth": "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts",
                   "official_reference": f"https://www.nfl.com/injuries/league/2026/reg{inj_week}",
                   "rows": backups}, f, indent=1)

    with open(os.path.join(OUT, "fetch-log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps({k: (v if k != "injuries" else {y: d["rows"] for y, d in v.items()}) for k, v in log.items()}, indent=1))
    print("team-week rows:", len(tw_out), "2026 rows:", len(rows_2026), "backup rows:", len(backups))
    log_path = os.path.join(OUT, "fetch-log.json")
    if not tw_out:
        sys.exit("no injury data fetched")


if __name__ == "__main__":
    main()
