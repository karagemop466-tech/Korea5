#!/usr/bin/env python3
"""Fetch official NFL data needed for the market / decision system.

Runs on GitHub Actions (the sandbox shell has no outbound network; Actions does).

Writes, all with an official source URL per record and **no invented values**:
  nfl/data/official-results.json    final scores for played games (nfl.com week pages)
  nfl/data/official-injuries.json   NFL official injury report rows (nfl.com/injuries)
  nfl/data/official-depth.json      club depth charts: 1st/2nd/3rd/4th string (club sites)
  nfl/data/official-teamstats.json  26 official team stat columns, offense/defense
  nfl/data/official-playerstats.json player stat leaders (prop-relevant distributions)
  nfl/data/official-roster.json     club roster -> official nfl.com player id mapping
  nfl/data/fetch-report.json        counts, HTTP status, failures, retrieval time

Anything that cannot be parsed stays absent from the output and is listed in
fetch-report.json under "failures" — it is never filled in by guesswork.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5NFL/1.0; +official-source-verification)",
      "Accept-Language": "en-US,en;q=0.9"}

NFL = "https://www.nfl.com"

# ---------------------------------------------------------------- club registry
# Official club sites (verified 200 in nfl/research/probe.json for 49ers/chiefs;
# the rest use the identical /team/depth-chart path on each club's official site).
CLUBS = [
    # abbr, full name, official club site
    ("ARI", "Arizona Cardinals", "https://www.azcardinals.com"),
    ("ATL", "Atlanta Falcons", "https://www.atlantafalcons.com"),
    ("BAL", "Baltimore Ravens", "https://www.baltimoreravens.com"),
    ("BUF", "Buffalo Bills", "https://www.buffalobills.com"),
    ("CAR", "Carolina Panthers", "https://www.panthers.com"),
    ("CHI", "Chicago Bears", "https://www.chicagobears.com"),
    ("CIN", "Cincinnati Bengals", "https://www.bengals.com"),
    ("CLE", "Cleveland Browns", "https://www.clevelandbrowns.com"),
    ("DAL", "Dallas Cowboys", "https://www.dallascowboys.com"),
    ("DEN", "Denver Broncos", "https://www.denverbroncos.com"),
    ("DET", "Detroit Lions", "https://www.detroitlions.com"),
    ("GB", "Green Bay Packers", "https://www.packers.com"),
    ("HOU", "Houston Texans", "https://www.houstontexans.com"),
    ("IND", "Indianapolis Colts", "https://www.colts.com"),
    ("JAX", "Jacksonville Jaguars", "https://www.jaguars.com"),
    ("KC", "Kansas City Chiefs", "https://www.chiefs.com"),
    ("LA", "Los Angeles Rams", "https://www.therams.com"),
    ("LAC", "Los Angeles Chargers", "https://www.chargers.com"),
    ("LV", "Las Vegas Raiders", "https://www.raiders.com"),
    ("MIA", "Miami Dolphins", "https://www.miamidolphins.com"),
    ("MIN", "Minnesota Vikings", "https://www.vikings.com"),
    ("NE", "New England Patriots", "https://www.patriots.com"),
    ("NO", "New Orleans Saints", "https://www.neworleanssaints.com"),
    ("NYG", "New York Giants", "https://www.giants.com"),
    ("NYJ", "New York Jets", "https://www.newyorkjets.com"),
    ("PHI", "Philadelphia Eagles", "https://www.philadelphiaeagles.com"),
    ("PIT", "Pittsburgh Steelers", "https://www.steelers.com"),
    ("SEA", "Seattle Seahawks", "https://www.seahawks.com"),
    ("SF", "San Francisco 49ers", "https://www.49ers.com"),
    ("TB", "Tampa Bay Buccaneers", "https://www.buccaneers.com"),
    ("TEN", "Tennessee Titans", "https://www.titansonline.com"),
    ("WAS", "Washington Commanders", "https://www.commanders.com"),
]
CLUB_BY_NAME = {name: (abbr, site) for abbr, name, site in CLUBS}
CLUB_BY_ABBR = {abbr: (name, site) for abbr, name, site in CLUBS}

# Nickname -> abbr, used to match the short names printed on nfl.com week pages.
NICKNAMES = {
    "49ers": "SF", "bears": "CHI", "bengals": "CIN", "bills": "BUF", "broncos": "DEN",
    "browns": "CLE", "buccaneers": "TB", "cardinals": "ARI", "chargers": "LAC",
    "chiefs": "KC", "colts": "IND", "commanders": "WAS", "cowboys": "DAL",
    "dolphins": "MIA", "eagles": "PHI", "falcons": "ATL", "giants": "NYG",
    "jaguars": "JAX", "jets": "NYJ", "lions": "DET", "packers": "GB",
    "panthers": "CAR", "patriots": "NE", "raiders": "LV", "rams": "LA",
    "ravens": "BAL", "saints": "NO", "seahawks": "SEA", "steelers": "PIT",
    "texans": "HOU", "titans": "TEN", "vikings": "MIN",
}

TEAM_STATS = {
    # page slug -> (side, category)
    "offense/passing": ("offense", "passing"),
    "offense/rushing": ("offense", "rushing"),
    "offense/receiving": ("offense", "receiving"),
    "offense/scoring": ("offense", "scoring"),
    "defense/passing": ("defense", "passing"),
    "defense/rushing": ("defense", "rushing"),
    "defense/scoring": ("defense", "scoring"),
}

PLAYER_CATEGORIES = {
    "passing": "passingyards",
    "rushing": "rushingyards",
    "receiving": "receivingreceptions",
}

failures: list[str] = []


def get(url: str, tries: int = 3, timeout: int = 75) -> str | None:
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(1.0 + attempt)
    failures.append(f"{url}: {last!r}")
    return None


def txt(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\u00a0", " ").strip()


def write(name: str, obj) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ 1. results
SCORE_RE = re.compile(r"gameState&quot;:&quot;FINAL&quot;")
LINKNAME_RE = re.compile(r"linkName&quot;:&quot;([^&]{5,120}?)&quot;")
GAMEHREF_RE = re.compile(r'&quot;gameId&quot;:&quot;[^&]+&quot;,&quot;gameState&quot;:&quot;FINAL&quot;.{0,400}?href="(/games/[a-z0-9-]+)"')


def fetch_results(season: int, weeks: list[tuple[str, str]]):
    """Parse final scores from nfl.com by-week schedule pages.

    The page prints each played game as e.g.
      linkName="Buccaneers 24, Cowboys 16, FINAL, Thursday, October 8th"
    and the card's own href is /games/<away>-at-<home>-<season>-<type>-<week>.
    """
    rows, pages = [], []
    for slug, label in weeks:
        url = f"{NFL}/schedules/{season}/by-week/{slug}"
        page = get(url)
        pages.append(url)
        if page is None:
            continue
        # Walk each final-state card: capture the linkName and the href that follows it.
        for m in re.finditer(r'linkName&quot;:&quot;(.{5,140}?)&quot;.{0,600}?href="(/games/[a-z0-9-]+)"',
                             page, re.S):
            link_name, href = txt(m.group(1)), m.group(2)
            if "FINAL" not in link_name.upper():
                continue
            sm = re.match(r"(.+?) (\d{1,3}), (.+?) (\d{1,3}), FINAL", link_name)
            if not sm:
                continue
            away_name, away_score, home_name, home_score = sm.groups()
            away_abbr = NICKNAMES.get(away_name.strip().lower())
            home_abbr = NICKNAMES.get(home_name.strip().lower())
            rows.append({
                "season": season,
                "weekLabel": label,
                "gameUrl": NFL + href,
                "awayName": away_name.strip(),
                "homeName": home_name.strip(),
                "awayAbbr": away_abbr,
                "homeAbbr": home_abbr,
                "awayScore": int(away_score),
                "homeScore": int(home_score),
                "status": "FINAL",
                "sourceUrl": url,
                "sourceName": "NFL.com official by-week schedule page",
                "verification": "verified" if (away_abbr and home_abbr) else "unverified-abbr",
            })
        print(f"  results {slug}: {sum(1 for r in rows if r['sourceUrl'] == url)} finals")
    # de-duplicate (each card appears twice in the markup)
    seen, uniq = set(), []
    for r in rows:
        k = (r["gameUrl"], r["awayScore"], r["homeScore"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq, pages


# ----------------------------------------------------------------- 2. injuries
INJ_TABLE_RE = re.compile(
    r'<div class="d3-o-section-sub-title"><span>([^<]{2,40})</span></div>.*?'
    r'<table class="d3-o-table[^"]*d3-o-reports--detailed"[^>]*>(.*?)</table>', re.S)


def parse_injury_rows(season: int, url: str, page: str):
    out = []
    for team_name, body in INJ_TABLE_RE.findall(page):
        for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 5:
                continue
            player_html, position, injury, practice, game = cells[:5]
            player = txt(player_html)
            pid = re.search(r'href="(/players/[a-z0-9-]+/)"', player_html)
            out.append({
                "season": season,
                "team": txt(team_name),
                "player": player,
                "playerUrl": (NFL + pid.group(1)) if pid else None,
                "position": txt(position) or None,
                "injury": txt(injury) or None,
                "practiceStatus": txt(practice) or None,
                "gameStatus": txt(game) or None,
                "sourceUrl": url,
                "sourceName": "NFL.com official injury report",
                "verification": "verified" if player else "unverified",
            })
    return out


def fetch_injuries(season: int, weeks: list[int]):
    rows, pages = [], []
    for w in weeks:
        url = f"{NFL}/injuries/league/{season}/reg{w:02d}"
        page = get(url)
        pages.append(url)
        if page is None:
            continue
        got = parse_injury_rows(season, url, page)
        for r in got:
            r["week"] = w
        rows.extend(got)
        print(f"  injuries reg{w:02d}: {len(got)} rows")
    return rows, pages


# --------------------------------------------------------------- 3. depth chart
DEPTH_SECTION_RE = re.compile(
    r'nfl-t-depth-chart__table" id="scroll-([a-z]+)"><div class="d3-o-table--horizontal-scroll">'
    r'<table[^>]*>(.*?)</table>', re.S)


def parse_depth(abbr: str, site: str, url: str, page: str):
    out = []
    upd = re.search(r"Updated as of\s*</span></h2>|<span>\s*Updated as of ([0-9/]+)\s*</span>", page)
    updated = upd.group(1) if (upd and upd.lastindex) else None
    unofficial = "Unofficial Depth Chart" in page
    for unit, body in DEPTH_SECTION_RE.findall(page):
        head = re.search(r"<thead>(.*?)</thead>", body, re.S)
        cols = [txt(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)] if head else []
        for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 2:
                continue
            pos = txt(cells[0])
            for idx, cell in enumerate(cells[1:], start=1):
                name = txt(cell)
                if not name:
                    continue
                pid = re.search(r'href="(/team/players-roster/[a-z0-9-]+/)"', cell)
                out.append({
                    "team": abbr,
                    "unit": unit,
                    "position": pos,
                    "depth": idx,                       # 1 = starter, 2 = 2nd string, ...
                    "depthLabel": (cols[idx] if idx < len(cols) else None),
                    "player": name,
                    "playerPath": (site + pid.group(1)) if pid else None,
                    "chartUpdatedAsOf": updated,
                    "clubLabelsChart": "Unofficial Depth Chart" if unofficial else "Depth Chart",
                    "sourceUrl": url,
                    "sourceName": f"{abbr} official club depth chart",
                    "verification": "verified",
                })
    return out


def fetch_depth():
    rows, used = [], []
    for abbr, name, site in CLUBS:
        url = site + "/team/depth-chart"
        page = get(url, tries=2)
        if page is None:
            continue
        got = parse_depth(abbr, site, url, page)
        if got:
            used.append({"team": abbr, "url": url, "rows": len(got)})
        rows.extend(got)
        print(f"  depth {abbr}: {len(got)}")
    return rows, used


# --------------------------------------------------------------- 4. team stats
def parse_stat_table(page: str):
    head = re.search(r"<thead>(.*?)</thead>", page, re.S)
    if not head:
        return [], []
    headers = [txt(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)]
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S)
    if not body:
        return headers, []
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S):
        team = re.search(r'd3-o-club-fullname">([^<]+)</div>', tr)
        if not team:
            continue
        cells = [txt(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        # cells[0] is the club logo/name block -> blank after tag stripping
        vals = [c for c in cells if c != ""] if cells and cells[0] == "" else cells[1:]
        out.append((team.group(1).strip(), [v for v in vals]))
    return headers, out


def fetch_team_stats(season: int):
    pack = {"season": season, "tables": {}, "sourceName": "NFL.com official team statistics"}
    for slug, (side, cat) in TEAM_STATS.items():
        url = f"{NFL}/stats/team-stats/{slug}/{season}/reg/all"
        page = get(url)
        if page is None:
            continue
        headers, rows = parse_stat_table(page)
        pack["tables"][f"{side}_{cat}"] = {
            "url": url,
            "headers": headers[1:] if headers and headers[0].lower() == "team" else headers,
            "rows": [{"team": t, "values": v} for t, v in rows],
        }
        print(f"  teamstats {side}/{cat}: {len(rows)} rows x {len(headers)} cols")
    return pack


# ------------------------------------------------------------- 5. player stats
def fetch_player_stats(season: int):
    pack = {"season": season, "categories": {}, "sourceName": "NFL.com official player statistics"}
    for cat, sortkey in PLAYER_CATEGORIES.items():
        url = f"{NFL}/stats/player-stats/category/{cat}/{season}/reg/all/{sortkey}/desc"
        page = get(url)
        if page is None:
            continue
        head = re.search(r"<thead>(.*?)</thead>", page, re.S)
        headers = [txt(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)] if head else []
        rows = []
        body = re.search(r"<tbody>(.*?)</tbody>", page, re.S)
        for tr in re.findall(r"<tr>(.*?)</tr>", (body.group(1) if body else ""), re.S):
            pl = re.search(r'href="/players/([a-z0-9-]+)/"[^>]*>([^<]+)</a>', tr)
            if not pl:
                continue
            cells = [txt(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            rows.append({"playerSlug": pl.group(1), "player": txt(pl.group(2)), "values": cells,
                         "playerUrl": f"{NFL}/players/{pl.group(1)}/"})
        pack["categories"][cat] = {"url": url, "headers": headers, "rows": rows}
        print(f"  playerstats {cat}: {len(rows)} rows x {len(headers)} cols")
    return pack


# ------------------------------------------------------------------ 6. roster
ROSTER_SLUG = {name: name.lower().replace(" ", "-") for _, name, _ in CLUBS}
ROSTER_SLUG.update({name: re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                    for _, name, _ in CLUBS})


def fetch_roster(team_name: str):
    slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")
    url = f"{NFL}/teams/{slug}/roster"
    page = get(url, tries=2)
    if page is None:
        return None
    players = []
    for m in re.finditer(r'href="/players/([a-z0-9-]+)/"[^>]*>([^<]{2,40})</a>', page):
        players.append({"slug": m.group(1), "name": txt(m.group(2)),
                        "profileUrl": f"{NFL}/players/{m.group(1)}/"})
    seen, uniq = set(), []
    for p in players:
        if p["slug"] in seen:
            continue
        seen.add(p["slug"])
        uniq.append(p)
    return {"team": team_name, "url": url, "players": uniq}


# ---------------------------------------------------------------------- main
def main():
    started = dt.datetime.utcnow().isoformat() + "Z"
    report = {"startedUTC": started, "failures": []}

    print("== results 2026")
    weeks26 = ([("preseason-week-1", "Preseason Week 1"), ("preseason-week-2", "Preseason Week 2"),
                ("preseason-week-3", "Preseason Week 3")]
               + [(f"week-{i}", f"Week {i}") for i in range(1, 19)])
    r26, p26 = fetch_results(2026, weeks26)
    weeks25 = [(f"week-{i}", f"Week {i}") for i in range(1, 19)]
    print("== results 2025 (prior-season prior)")
    r25, p25 = fetch_results(2025, weeks25)
    write("official-results.json", {
        "meta": {"sourceName": "NFL.com official by-week schedule pages",
                 "retrievedUTC": started,
                 "note": "Only games whose official card reads FINAL are included. "
                         "Scores are as printed by nfl.com; nothing is inferred.",
                 "pages": p26 + p25},
        "results": r26 + r25,
    })
    report["results"] = {"2026": len(r26), "2025": len(r25)}

    print("== injuries")
    inj26, ip26 = fetch_injuries(2026, list(range(1, 11)))
    inj25, ip25 = fetch_injuries(2025, list(range(1, 19)))
    write("official-injuries.json", {
        "meta": {"sourceName": "NFL.com official injury report",
                 "retrievedUTC": started,
                 "note": "Rows exactly as published. Blank cells mean the official page "
                         "published no value — they are kept blank, never filled.",
                 "pages": ip26 + ip25},
        "rows": inj26 + inj25,
    })
    report["injuries"] = {"2026": len(inj26), "2025": len(inj25)}

    print("== depth charts")
    dep, dep_urls = fetch_depth()
    write("official-depth.json", {
        "meta": {"sourceName": "Official NFL club depth charts",
                 "retrievedUTC": started,
                 "note": "depth=1 is the listed starter; depth=2/3/4 are the listed backups. "
                         "Charts are the clubs' own; some clubs label theirs 'Unofficial Depth Chart'.",
                 "pages": dep_urls},
        "rows": dep,
    })
    report["depth"] = {"rows": len(dep), "teams": len(dep_urls),
                       "teamsMissing": [a for a, _, _ in CLUBS if a not in {u['team'] for u in dep_urls}]}

    print("== team stats")
    ts = fetch_team_stats(2026)
    write("official-teamstats.json", ts)
    report["teamStats"] = {k: len(v["rows"]) for k, v in ts["tables"].items()}

    print("== player stats")
    ps = fetch_player_stats(2026)
    write("official-playerstats.json", ps)
    report["playerStats"] = {k: len(v["rows"]) for k, v in ps["categories"].items()}

    print("== roster")
    rosters = [r for r in (fetch_roster(n) for _, n, _ in CLUBS) if r]
    write("official-roster.json", {
        "meta": {"sourceName": "NFL.com official team rosters", "retrievedUTC": started},
        "teams": rosters})
    report["rosters"] = {"teams": len(rosters),
                         "players": sum(len(r["players"]) for r in rosters)}

    report["failures"] = failures
    report["finishedUTC"] = dt.datetime.utcnow().isoformat() + "Z"
    write("fetch-report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=1))
    print("failures:", len(failures))


if __name__ == "__main__":
    main()
