import json, os, urllib.request, socket
UA = {"User-Agent": "Korea5-nfl-lines-lab/0.1 (+https://github.com/karagemop466-tech/Korea5)"}
URLS = {
 "nflverse_games_csv": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
 "nflverse_roster": "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv",
 "nflverse_depth": "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv",
 "nflverse_injuries": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
 "nflverse_pbp": "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.csv.gz",
 "mlb_statsapi": "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-04-01",
 "nfl_teams": "https://api.nfl.com/v1/teams",
 "espn_scoreboard": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
 "pro_football_ref": "https://www.pro-football-reference.com/years/2025/",
 "nflcom_schedule": "https://www.nfl.com/schedules/2026/",
 "nfl_ops": "https://operations.nfl.com/",
 "pypi_nfl_data_py": "https://pypi.org/simple/nfl-data-py/",
}
out = {"checked": [], "dns": {}}
os.makedirs("nfl/probe", exist_ok=True)
for name, url in URLS.items():
    rec = {"name": name, "url": url}
    try:
        host = url.split("/")[2]
        rec["dns"] = socket.gethostbyname(host)
    except Exception as e:
        rec["dns_error"] = str(e)[:120]
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            head = r.read(2000)
            rec["status"] = r.status
            rec["content_length"] = r.headers.get("Content-Length")
            rec["content_type"] = r.headers.get("Content-Type")
            rec["first_bytes"] = head[:200].decode("utf-8", "replace")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    out["checked"].append(rec)
json.dump(out, open("nfl/probe/reachability.json", "w"), indent=1)
print(json.dumps([{k: v for k, v in r.items() if k != "first_bytes"} for r in out["checked"]], indent=1)[:6000])
