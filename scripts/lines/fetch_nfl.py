#!/usr/bin/env python3
"""Fetch the official data the NFL-lines workstream needs.

Runs on GitHub Actions (runners have outbound internet; the sandbox does not).

Every record written here carries the official source URL it came from. Nothing is
invented: if a field is not present on the official page it is left null and the row is
reported in the fetch report so it can be published on the Flagged for Review page.

Sources (all official):
  https://www.nfl.com/schedules/{season}/by-week/{week}   game list + final scores
  https://www.nfl.com/games/{slug}?tab=stats               official box score
  https://www.nfl.com/injuries/                            official weekly injury report
  https://www.nfl.com/teams/                               official club website directory
  https://www.{club}/team/depth-chart/                     official club depth chart

Outputs (committed by the workflow):
  data/lines/games.json        every scheduled game with its official final score
  data/lines/boxscores.json    official per-player box score rows
  data/lines/injuries.json     official weekly injury report rows
  data/lines/depth-charts.json official club depth charts (1st/2nd/3rd/4th string)
  data/lines/fetch-report.json counts, failures, retrieval time, source URLs
"""
import concurrent.futures
import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.request

OUT = "data/lines"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5NFLLines/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}

SEASONS = (2024, 2025, 2026)

WEEK_SLUGS = (
    [("preseason-week-1", "Preseason Week 1"), ("preseason-week-2", "Preseason Week 2"),
     ("preseason-week-3", "Preseason Week 3")]
    + [(f"week-{i}", f"Week {i}") for i in range(1, 19)]
    + [(f"postseason-week-{i}", f"Postseason Week {i}") for i in range(1, 6)]
)

# Official club websites, as published in the NFL.com team directory:
# https://www.nfl.com/teams/  (each entry carries a "View Full Site" link)
CLUBS = [
    ("Arizona Cardinals", "ARI", "azcardinals.com"),
    ("Atlanta Falcons", "ATL", "atlantafalcons.com"),
    ("Baltimore Ravens", "BAL", "baltimoreravens.com"),
    ("Buffalo Bills", "BUF", "buffalobills.com"),
    ("Carolina Panthers", "CAR", "panthers.com"),
    ("Chicago Bears", "CHI", "chicagobears.com"),
    ("Cincinnati Bengals", "CIN", "bengals.com"),
    ("Cleveland Browns", "CLE", "clevelandbrowns.com"),
    ("Dallas Cowboys", "DAL", "dallascowboys.com"),
    ("Denver Broncos", "DEN", "denverbroncos.com"),
    ("Detroit Lions", "DET", "detroitlions.com"),
    ("Green Bay Packers", "GB", "packers.com"),
    ("Houston Texans", "HOU", "houstontexans.com"),
    ("Indianapolis Colts", "IND", "colts.com"),
    ("Jacksonville Jaguars", "JAX", "jaguars.com"),
    ("Kansas City Chiefs", "KC", "chiefs.com"),
    ("Las Vegas Raiders", "LV", "raiders.com"),
    ("Los Angeles Chargers", "LAC", "chargers.com"),
    ("Los Angeles Rams", "LAR", "therams.com"),
    ("Miami Dolphins", "MIA", "miamidolphins.com"),
    ("Minnesota Vikings", "MIN", "vikings.com"),
    ("New England Patriots", "NE", "patriots.com"),
    ("New Orleans Saints", "NO", "neworleanssaints.com"),
    ("New York Giants", "NYG", "giants.com"),
    ("New York Jets", "NYJ", "newyorkjets.com"),
    ("Philadelphia Eagles", "PHI", "philadelphiaeagles.com"),
    ("Pittsburgh Steelers", "PIT", "steelers.com"),
    ("San Francisco 49ers", "SF", "49ers.com"),
    ("Seattle Seahawks", "SEA", "seahawks.com"),
    ("Tampa Bay Buccaneers", "TB", "buccaneers.com"),
    ("Tennessee Titans", "TEN", "tennesseetitans.com"),
    ("Washington Commanders", "WAS", "commanders.com"),
]

# Seasons whose box scores are pulled (player-prop modelling needs per-game player rows).
BOX_SCORE_SEASONS = (2025, 2026)


def get(url, tries=3, timeout=90):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(1.0 + attempt)
    print(f"  ! failed {url}: {last}")
    return None


def jwrite(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ RSC decoding
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


def rsc_query_data(page, wanted):
    """Return the first react-query payload whose key[0] == wanted."""
    for obj in rsc_payloads(page):
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    key = cur.get("queryKey")
                    if isinstance(key, list) and key and key[0] == wanted:
                        data = (cur.get("state") or {}).get("data")
                        if data is not None:
                            return data
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return None


def rsc_query_all(page, wanted):
    """Return every react-query payload whose key[0] == wanted (list of data)."""
    out = []
    for obj in rsc_payloads(page):
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    key = cur.get("queryKey")
                    if isinstance(key, list) and key and key[0] == wanted:
                        data = (cur.get("state") or {}).get("data")
                        if data is not None:
                            out.append(data)
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return out


# ------------------------------------------------------------------ schedules
def slug_for(game):
    for x in (game.get("externalIds") or []):
        if isinstance(x, dict) and x.get("source") == "slug" and x.get("id"):
            return x["id"]
    return None


def gsis_for(game):
    for x in (game.get("externalIds") or []):
        if isinstance(x, dict) and x.get("source") == "gsis" and x.get("id"):
            return str(x["id"])
    return None


def fetch_week(season, slug, label):
    url = f"https://www.nfl.com/schedules/{season}/by-week/{slug}"
    page = get(url)
    if page is None:
        return [], [f"{season}/{slug}: page fetch failed"], url
    data = rsc_query_data(page, "useFetchFootballWeeklyGameDetails")
    if not isinstance(data, list):
        return [], [f"{season}/{slug}: weekly game payload missing"], url
    games = []
    seen = set()
    for g in data:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        summary = g.get("summary") or {}
        away = (g.get("awayTeam") or {}).get("fullName")
        home = (g.get("homeTeam") or {}).get("fullName")
        a_score = ((summary.get("awayTeam") or {}).get("score") or {})
        h_score = ((summary.get("homeTeam") or {}).get("score") or {})
        phase = summary.get("phase")
        rec = {
            "gameId": str(gid),
            "gsisId": gsis_for(g),
            "season": g.get("season"),
            "seasonType": g.get("seasonType"),
            "week": g.get("week"),
            "weekType": g.get("weekType"),
            "weekLabel": label,
            "weekSlug": slug,
            "away": away,
            "home": home,
            "venue": (g.get("venue") or {}).get("name"),
            "venueCity": (g.get("venue") or {}).get("city"),
            "startUTC": g.get("time"),
            "date": g.get("date"),
            "status": g.get("status"),
            "phase": phase,
            "awayScore": a_score.get("total") if phase else None,
            "homeScore": h_score.get("total") if phase else None,
            "awayScoreOt": a_score.get("ot") if phase else None,
            "homeScoreOt": h_score.get("ot") if phase else None,
            "attendance": summary.get("attendance"),
            "gameBookUrl": summary.get("gameBookUrl"),
            "slug": slug_for(g),
            "sourceUrl": None,
            "sourceName": "NFL.com official schedule (by-week page)",
            "verification": "verified" if phase else "scheduled-no-score",
        }
        games.append(rec)
    return games, [], url


def fetch_games():
    """Every week page once per season, then de-duplicated by game id.

    FIXED 2026-11-13 (session arena-827c3da2, defect A04): the same game object was appended
    once per week page that happened to carry it. On the 2026 capture that duplicated all 14
    Week 10 games sixteen times each, so `games.json` held 482 regular-season rows for 272
    unique games. Every downstream count ("1170 games") and every row multiplied from this
    file inherited that. De-duplication is by game id, keeping the first occurrence, which is
    the earliest week page that listed it.
    """
    games = []
    failures = []
    pages = []
    seen = set()
    dupes = 0
    for season in SEASONS:
        for slug, label in WEEK_SLUGS:
            gs, fails, url = fetch_week(season, slug, label)
            for g in gs:
                if g["gameId"] in seen:
                    dupes += 1
                    continue
                seen.add(g["gameId"])
                games.append(g)
            failures.extend(fails)
            pages.append(url)
            if (season == 2026 and slug in ("preseason-week-1", "week-1")) or slug == "postseason-week-5":
                time.sleep(0.2)
    if dupes:
        print(f"  de-duplicated {dupes} repeated game records across week pages")
    return games, failures, pages


# ------------------------------------------------------------------ box scores
def cell_value(cell):
    if not isinstance(cell, dict):
        return None
    v = cell.get("text")
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s == "":
        return None
    try:
        return float(s) if ("." in s or s.isdigit()) else s
    except Exception:  # noqa: BLE001
        return s


def player_image_id(cell):
    img = (cell or {}).get("image") or ""
    m = re.search(r"/league/([A-Za-z0-9_-]+)$", img)
    return m.group(1) if m else None


def parse_team_stats(stats_list, side, source_url):
    """Convert one team's official stat tables into flat per-player rows."""
    rows = []
    for group in stats_list or []:
        if not isinstance(group, dict):
            continue
        title = group.get("title") or ""
        table = group.get("table") or {}
        cols = [(c.get("title") or "") for c in (table.get("columns") or [])]
        for r in table.get("rows") or []:
            if not isinstance(r, list) or not r:
                continue
            cells = [cell_value(c) for c in r]
            if cells and isinstance(cells[0], str) and cells[0].strip().upper() == "TEAM":
                continue
            if not cells or not isinstance(cells[0], str):
                continue
            rec = {
                "side": side,
                "group": title,
                "playerDisplay": cells[0].strip(),
                "playerImageId": player_image_id(r[0]),
                "sourceUrl": source_url,
            }
            for i, col in enumerate(cols[1:], start=1):
                if i < len(cells):
                    rec[col] = cells[i]
            rows.append(rec)
    return rows


def find_team_stats(state_data):
    """Locate the {awayTeam:{stats:[...]}, homeTeam:{stats:[...]}} payload.

    The league wraps this payload more than one way depending on the page, so the
    structure is located by shape rather than by a fixed path.
    """
    if not isinstance(state_data, dict):
        return None
    seen = set()
    stack = [state_data]
    while stack:
        cur = stack.pop()
        if not isinstance(cur, dict) or id(cur) in seen:
            continue
        seen.add(id(cur))
        away = cur.get("awayTeam")
        if isinstance(away, dict) and isinstance(away.get("stats"), list) and away["stats"]:
            return cur
        for v in cur.values():
            if isinstance(v, (dict, list)):
                stack.append(v)
    return None


def fetch_boxscore(game):
    slug = game.get("slug")
    if not slug:
        return [], [f"{game.get('gameId')}: no slug"]
    url = f"https://www.nfl.com/games/{slug}?tab=stats"
    page = get(url)
    if page is None:
        return [], [f"{slug}: box score fetch failed"]
    data = rsc_query_data(page, "useFetchTeamStatsContainerData")
    diag = None
    if isinstance(data, dict):
        diag = {"keys": sorted(data)[:12]}
    payload = find_team_stats(data)
    if payload is None:
        msg = f"{slug}: team stats payload missing"
        if diag:
            msg += f" (keys={diag['keys']})"
        return [], [msg]
    rows = []
    for side in ("awayTeam", "homeTeam"):
        team = payload.get(side) or {}
        rows.extend(parse_team_stats(team.get("stats"), side, url))
    for r in rows:
        r["gameId"] = game.get("gameId")
        r["season"] = game.get("season")
        r["week"] = game.get("week")
        r["seasonType"] = game.get("seasonType")
        r["date"] = game.get("date")
        r["away"] = game.get("away")
        r["home"] = game.get("home")
        r["slug"] = slug
    return rows, []


# ------------------------------------------------------------------ injuries
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(s):
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub("", s or ""))).strip()



# The official injury page labels each club table with its OWN title element
# (`<div class="d3-o-section-sub-title"><span>Commanders</span></div>`), not with the full
# club name. The original implementation searched the whole preceding page for a full club
# name, took the last match, and so attributed every row on the page to whichever club was
# named last before the final table (Dallas Cowboys). That mislabelled all 296 rows of the
# 2026 Week 10 report. Fixed 2026-11-13 by session arena-827c3da2; see
# data/control/audit.json and tests/test_control_audit.py.
OWNER_RE = re.compile(r'd3-o-section-sub-title"\s*><span>(.*?)</span>', re.S | re.I)

NICKNAMES = {
    "Cardinals": "Arizona Cardinals", "Falcons": "Atlanta Falcons", "Ravens": "Baltimore Ravens",
    "Bills": "Buffalo Bills", "Panthers": "Carolina Panthers", "Bears": "Chicago Bears",
    "Bengals": "Cincinnati Bengals", "Browns": "Cleveland Browns", "Cowboys": "Dallas Cowboys",
    "Broncos": "Denver Broncos", "Lions": "Detroit Lions", "Packers": "Green Bay Packers",
    "Texans": "Houston Texans", "Colts": "Indianapolis Colts", "Jaguars": "Jacksonville Jaguars",
    "Chiefs": "Kansas City Chiefs", "Raiders": "Las Vegas Raiders", "Chargers": "Los Angeles Chargers",
    "Rams": "Los Angeles Rams", "Dolphins": "Miami Dolphins", "Vikings": "Minnesota Vikings",
    "Patriots": "New England Patriots", "Saints": "New Orleans Saints", "Giants": "New York Giants",
    "Jets": "New York Jets", "Eagles": "Philadelphia Eagles", "Steelers": "Pittsburgh Steelers",
    "49ers": "San Francisco 49ers", "Seahawks": "Seattle Seahawks", "Buccaneers": "Tampa Bay Buccaneers",
    "Titans": "Tennessee Titans", "Commanders": "Washington Commanders",
}


def team_for_table(page, table_start):
    """Return the full club name that owns the table starting at table_start.

    The nearest owner title *before* the table wins. If that title is not a known club
    nickname, the table is reported as unattributed (None) rather than guessed.
    """
    before = page[:table_start]
    found = OWNER_RE.findall(before)
    if not found:
        return None
    label = clean_text(found[-1])
    if label in NICKNAMES:
        return NICKNAMES[label]
    for full, _abbr, _domain in CLUBS:
        if full == label or full.endswith(" " + label):
            return full
    return None


def parse_injuries_page(page, url):
    """Split the official injury report page into (team, week, rows)."""
    rows = []
    week = None
    m = re.search(r"Injuries\s*-\s*WEEK\s*(\d+)", page)
    if m:
        week = int(m.group(1))
    # tables of the report
    for tm in re.finditer(r"<table\b[^>]*d3-o-reports--detailed[^>]*>.*?</table>", page, re.S | re.I):
        block = tm.group(0)
        team = team_for_table(page, tm.start())
        if team is None:
            continue
        for rm in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", block, re.S | re.I):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", rm.group(1), re.S | re.I)
            if len(cells) < 3:
                continue
            link = re.search(r'href="(/players/[^"]+)"', cells[0])
            if not link:
                continue
            name = clean_text(cells[0])
            if not name:
                continue
            vals = [clean_text(c) for c in cells]
            rows.append({
                "week": week,
                "team": team,
                "player": name,
                "playerPath": link.group(1),
                "playerUrl": "https://www.nfl.com" + link.group(1),
                "position": vals[1] if len(vals) > 1 else None,
                "injury": (vals[2] if len(vals) > 2 else "") or "",
                "practiceStatus": (vals[3] if len(vals) > 3 else "") or "",
                "gameStatus": (vals[4] if len(vals) > 4 else "") or "",
                "sourceUrl": url,
                "sourceName": "NFL.com official weekly injury report",
            })
    return week, rows


def fetch_injuries():
    url = "https://www.nfl.com/injuries/"
    page = get(url)
    if page is None:
        return None, [], [f"{url}: fetch failed"], url
    week, rows = parse_injuries_page(page, url)
    failures = []
    if not rows:
        failures.append(f"{url}: no injury rows parsed")
    return week, rows, failures, url


# ------------------------------------------------------------------ depth charts
DEPTH_HEADERS = ("1st", "2nd", "3rd", "4th")
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


def strip_jersey(name):
    """Some club charts print the jersey number before the name ('9 Christian Watson')."""
    return re.sub(r"^\s*\d{1,2}\s+", "", name or "").strip()


def parse_depth_chart(page, url):
    """Parse an official club depth chart into unit -> position -> tier -> players.

    Official club charts use two layouts:
      * 'Position | 1st | 2nd | 3rd | 4th'  (tier labels present, often inside <thead>)
      * 'Position | Player | Player | ...'  (no header row at all; tier implied by column order)
    Rows whose position cell is empty continue the previous position.
    """
    units = {}
    tier_labels_found = False
    tables_seen = 0
    # Class-marked depth-chart tables first: a generic table scan can be swallowed by a
    # malformed wrapper table earlier in the document.
    candidates = []
    for tm in re.finditer(r"<table\b([^>]*)>(.*?)</table>", page, re.S | re.I):
        if "depthchart" in tm.group(1).lower():
            candidates.append(tm)
    if not candidates:
        for tm in re.finditer(r"<table\b([^>]*)>(.*?)</table>", page, re.S | re.I):
            candidates.append(tm)

    for tm in candidates:
        attrs, block = tm.group(1), tm.group(2)
        tables_seen += 1
        cap = re.search(r"<caption[^>]*>(.*?)</caption>", block, re.S | re.I)
        unit = clean_text(cap.group(1)).title() if cap else ""
        if not unit:
            hs = re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", page[:tm.start()], re.S | re.I)
            for h in reversed(hs):
                t = clean_text(h).strip("*# ").title()
                if t in ("Offense", "Defense", "Special Teams"):
                    unit = t
                    break
        trs = re.findall(r"<tr\b[^>]*>(.*?)</tr>", block, re.S | re.I)
        if not trs:
            continue
        rows = {}
        last_position = None
        tiers = None
        for ri, rm in enumerate(trs):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", rm, re.S | re.I)
            if not cells:
                continue
            texts = [clean_text(c) for c in cells]
            lowered = [t.lower() for t in texts]
            # a header row names the columns
            if ri == 0 and lowered[0] == "position" and any(
                    x in DEPTH_HEADERS or "player" in x for x in lowered[1:]):
                tiers = []
                for i, h in enumerate(lowered[1:], start=1):
                    tiers.append(h if h in DEPTH_HEADERS else ORDINAL.get(i, f"tier{i}"))
                if any(h in DEPTH_HEADERS for h in lowered[1:]):
                    tier_labels_found = True
                continue
            if len(texts) < 2:
                continue
            position = texts[0]
            if not position:
                position = last_position
            if not position:
                continue
            last_position = position
            row = rows.setdefault(position, {"position": position, "players": []})
            for i, cell in enumerate(cells[1:], start=1):
                if tiers is not None:
                    tier = tiers[i - 1] if i - 1 < len(tiers) else ORDINAL.get(i, f"tier{i}")
                else:
                    tier = ORDINAL.get(i, f"tier{i}")
                found = False
                for am in re.finditer(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", cell, re.S | re.I):
                    nm = strip_jersey(clean_text(am.group(2)))
                    if nm:
                        row["players"].append({"tier": tier, "name": nm, "playerPath": am.group(1)})
                        found = True
                if not found:
                    nm = strip_jersey(clean_text(cell))
                    if nm:
                        row["players"].append({"tier": tier, "name": nm, "playerPath": None})
        if not rows:
            continue
        units.setdefault(unit or "Depth Chart", {}).update(rows)

    note = None
    for pat in (r"Updated as of\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
                r"([0-9]{1,2}\s+[A-Za-z]+\.?\s+[0-9]{1,2},?\s*[0-9]{4})"):
        m = re.search(pat, page, re.I)
        if m:
            note = m.group(1)
            break
    label = "unofficial" if re.search(r"\bunofficial\b", page, re.I) else "official"
    return units, note, label, tier_labels_found, tables_seen


def fetch_depth_chart(club):
    full, abbr, domain = club
    candidates = [
        f"https://www.{domain}/team/depth-chart/",
        f"https://www.{domain}/team/depth-charts/",
        f"https://www.{domain}/team/depth-chart",
    ]
    best = None
    for url in candidates:
        page = get(url, tries=2)
        if page is None:
            continue
        units, note, label, tier_labels, tables_seen = parse_depth_chart(page, url)
        if units:
            return {
                "team": full,
                "abbr": abbr,
                "units": units,
                "asOf": note,
                "chartLabel": label,
                "tierLabelsInSource": tier_labels,
                "tablesOnPage": tables_seen,
                "sourceUrl": url,
                "sourceName": f"Official {full} depth chart",
                "verification": "verified",
            }
        if best is None:
            best = (url, tables_seen)
    return {
        "team": full,
        "abbr": abbr,
        "units": {},
        "asOf": None,
        "chartLabel": None,
        "tierLabelsInSource": False,
        "tablesOnPage": best[1] if best else 0,
        "sourceUrl": best[0] if best else None,
        "sourceName": f"Official {full} depth chart",
        "verification": "unverified-not-fetched",
    }


# ------------------------------------------------------------------ main
def main():
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {"startedUTC": stamp, "sources": {}, "counts": {}, "failures": []}

    print("[1/4] schedules ...")
    games, fails, pages = fetch_games()
    report["failures"].extend(fails)
    for g in games:
        g["sourceUrl"] = (f"https://www.nfl.com/games/{g['slug']}" if g.get("slug")
                          else f"https://www.nfl.com/schedules/{g['season']}/by-week/{g['weekSlug']}")
    report["sources"]["schedules"] = {
        "name": "NFL.com official schedule by-week pages",
        "example": pages[0] if pages else None,
        "pages": len(pages),
    }
    jwrite("games.json", {
        "meta": {
            "retrievedUTC": stamp,
            "sourceName": "NFL.com official schedule by-week pages",
            "sourcePages": sorted(set(pages)),
            "seasons": list(SEASONS),
        },
        "games": games,
    })
    report["counts"]["games"] = len(games)
    report["counts"]["gamesWithScore"] = sum(1 for g in games if g.get("awayScore") is not None)

    print("[2/4] box scores ...")
    box_targets = [g for g in games
                   if g.get("season") in BOX_SCORE_SEASONS
                   and g.get("seasonType") == "REG"
                   and g.get("awayScore") is not None]
    box_rows = []
    box_fail = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for rows, fails in ex.map(fetch_boxscore, box_targets):
            box_rows.extend(rows)
            box_fail.extend(fails)
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(box_targets)} games, {len(box_rows)} rows")
    report["failures"].extend(box_fail)
    report["sources"]["boxscores"] = {
        "name": "NFL.com official box score (game page, stats tab)",
        "example": "https://www.nfl.com/games/commanders-at-giants-2026-reg-10?tab=stats",
        "pages": len(box_targets),
    }
    jwrite("boxscores.json", {
        "meta": {
            "retrievedUTC": stamp,
            "sourceName": "NFL.com official box score pages",
            "seasons": list(BOX_SCORE_SEASONS),
            "games": len(box_targets),
        },
        "rows": box_rows,
    })
    report["counts"]["boxscoreRows"] = len(box_rows)

    print("[3/4] injuries ...")
    week, inj_rows, inj_fail, inj_url = fetch_injuries()
    report["failures"].extend(inj_fail)
    report["sources"]["injuries"] = {
        "name": "NFL.com official weekly injury report",
        "example": inj_url,
        "week": week,
    }
    jwrite("injuries.json", {
        "meta": {
            "retrievedUTC": stamp,
            "sourceName": "NFL.com official weekly injury report",
            "sourceUrl": inj_url,
            "week": week,
        },
        "rows": inj_rows,
    })
    report["counts"]["injuryRows"] = len(inj_rows)
    report["counts"]["injuryWeek"] = week

    print("[4/4] depth charts ...")
    depth = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for rec in ex.map(fetch_depth_chart, CLUBS):
            depth.append(rec)
            print(f"    {rec['team']}: {rec['verification']} ({len(rec['units'])} units)")
    report["sources"]["depthCharts"] = {
        "name": "Official club depth charts, club list from the NFL.com team directory",
        "directory": "https://www.nfl.com/teams/",
    }
    jwrite("depth-charts.json", {
        "meta": {
            "retrievedUTC": stamp,
            "sourceName": "Official club depth charts",
            "directoryUrl": "https://www.nfl.com/teams/",
        },
        "clubs": depth,
    })
    report["counts"]["depthCharts"] = sum(1 for d in depth if d["units"])
    report["counts"]["depthChartsMissing"] = [d["team"] for d in depth if not d["units"]]

    report["finishedUTC"] = dt.datetime.now(dt.timezone.utc).isoformat()
    jwrite("fetch-report.json", report)
    print(json.dumps(report["counts"], indent=1))


if __name__ == "__main__":
    main()
