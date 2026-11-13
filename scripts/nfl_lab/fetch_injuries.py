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

    # ---- depth charts: starters reported out and first healthy backup ----
    backups = []
    for y in DEPTH_SEASONS:
        try:
            b = fetch(DEPTH_URL.format(y=y))
        except Exception as e:  # noqa: BLE001
            log["errors"].append(str(e))
            continue
        text = gzip.decompress(b)
        rows = list(csv.DictReader(io.StringIO(text.decode("utf-8-sig"))))
        log["depth"][str(y)] = {"rows": len(rows), "headers": list(rows[0].keys()) if rows else []}
        if y != 2026:
            continue
        # latest-week depth chart per team/position group, and injuries for the same week
        weeks = sorted({int(r["week"]) for r in rows if str(r.get("week", "")).isdigit()})
        log["depth"][str(y)]["weeks"] = weeks
        inj_by_gsis = {}
        for r in rows_2026:
            if r["gsis_id"]:
                inj_by_gsis[(int(r["week"]) if str(r["week"]).isdigit() else -1, r["gsis_id"])] = r
        for wk in weeks:
            wk_rows = [r for r in rows if str(r.get("week")) == str(wk) and (r.get("game_type") or "REG") == "REG"]
            chart = defaultdict(list)
            for r in wk_rows:
                chart[(r.get("club_code", ""), r.get("depth_position", "") or r.get("position", ""))].append(r)
            for (team, dpos), players in chart.items():
                players.sort(key=lambda r: int(r.get("depth_team") or 99) if str(r.get("depth_team", "")).isdigit() else 99)
                for idx, p in enumerate(players):
                    inj = inj_by_gsis.get((wk, p.get("gsis_id", "")))
                    if not inj or inj["report_status"] not in ("Out", "Doubtful"):
                        continue
                    if not str(p.get("depth_team", "")).isdigit() or int(p["depth_team"]) > 1:
                        continue  # only starters (depth 1) are tracked
                    # first healthy backup on the same depth list
                    rank = None
                    replacement = None
                    for q in players[idx + 1:]:
                        qi = inj_by_gsis.get((wk, q.get("gsis_id", "")))
                        if qi and qi["report_status"] in ("Out", "Doubtful"):
                            continue
                        rank = q.get("depth_team")
                        replacement = q.get("full_name") or q.get("football_name")
                        break
                    backups.append({
                        "season": y, "week": wk, "team": team, "depth_position": dpos,
                        "starter": inj["player"], "starter_status": inj["report_status"],
                        "starter_group": inj["group"],
                        "starter_injury": inj["primary_injury"],
                        "first_healthy_backup": replacement,
                        "backup_depth_rank": rank,
                        "source": inj["source"],
                        "depth_source": "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts",
                    })
    with open(os.path.join(OUT, "depth-backups-2026.json"), "w") as f:
        json.dump({"description": "2026 regular-season starters (depth_team 1) listed Out or Doubtful on the NFL weekly injury report, with the first healthy player further down the same depth list. Depth charts are the nflverse mirror, not an NFL-published chart; treat as third-party until checked.",
                   "upstream_injuries": "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
                   "upstream_depth": "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts",
                   "rows": backups}, f, indent=1)

    with open(os.path.join(OUT, "fetch-log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps({k: (v if k != "injuries" else {y: d["rows"] for y, d in v.items()}) for k, v in log.items()}, indent=1))
    print("team-week rows:", len(tw_out), "2026 rows:", len(rows_2026), "backup rows:", len(backups))
    if not tw_out:
        sys.exit("no injury data fetched")


if __name__ == "__main__":
    main()
