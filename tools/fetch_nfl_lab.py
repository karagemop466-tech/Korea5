#!/usr/bin/env python3
"""NFL Signal Lab official-data fetcher (runs on GitHub Actions: the Arena sandbox has no outbound network).

Collects ONLY data the NFL publishes itself, and never fills a field the official page does not carry:

  1. 2026 by-week schedule pages       -> per-game result rows (status, scores, venue, teams)
  2. 2026 official standings (per week) -> team points for/against and win-loss record
  3. 2026 weekly official injury pages   -> per-player practice / game status rows
  4. nfl.com/inactives page + injuries page discovery dumps -> which official structure carries them
  5. endpoint probe                       -> HTTP status for candidate official endpoints

Outputs (committed by .github/workflows/nfl-lab.yml):
  official/lab/results-2026.json
  official/lab/standings-2026.json
  official/lab/injuries-2026.json
  official/lab/inactives-2026.json
  official/lab/discovery.json
  official/lab/probe-report.json
  official/lab/fetch-report.json

Honesty rules enforced here:
  * every row carries `sourceUrl` + `sourceName` pointing at the exact official page it came from;
  * a value absent from the official payload stays null and is counted in `extraction` stats;
  * nothing is transcribed by hand, so nothing can be invented;
  * parse failures are reported, not papered over.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import html as html_lib
import urllib.request

OUT = "official/lab"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5SignalLab/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}
SEASON = 2026
WEEKS = list(range(1, 19))
SCHEDULE_BASE = f"https://www.nfl.com/schedules/{SEASON}/by-week/"
INJURY_URL = "https://www.nfl.com/injuries/"
INACTIVE_URL = "https://www.nfl.com/inactives/"
TRANSACTIONS_URL = "https://www.nfl.com/transactions/"
TEAM_STATS_URL = f"https://www.nfl.com/stats/team-stats/?season={SEASON}&statType=season&sort=points&category=points"
PROBE_ENDPOINTS = [
    ("nfl.com injuries landing", INJURY_URL),
    ("nfl.com inactives page", INACTIVE_URL),
    ("nfl.com transactions", TRANSACTIONS_URL),
    ("nfl.com stats portal", "https://www.nfl.com/stats/"),
    ("nfl.com team stats", "https://www.nfl.com/stats/team-stats/"),
    ("nfl.com player stats", "https://www.nfl.com/stats/player-stats/"),
    ("nfl.com depth-charts (league)", "https://www.nfl.com/depth-charts/"),
    ("nfl.com club depth chart", "https://www.nfl.com/teams/san-francisco-49ers/depth-chart/"),
    ("nfl.com club roster", "https://www.nfl.com/teams/san-francisco-49ers/roster/"),
    ("nfl.com 2026-27 important dates", "https://www.nfl.com/news/2026-27-national-football-league-important-dates"),
    ("operations.nfl.com 2026 rulebook", "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"),
    ("operations.nfl.com homepage", "https://operations.nfl.com/"),
    ("api.nfl.com season games", f"https://api.nfl.com/season/{SEASON}/games/?seasonType=REG&week=9"),
    ("api.nfl.com club injuries", "https://api.nfl.com/club/san-francisco-49ers/teams/current/injuries.json"),
    ("static.www.nfl.com game injury CSV",
     "https://static.www.nfl.com/public/stats/statistics/games/injuries/2026/reg/2026110801.csv"),
    ("static.www.nfl.com game inactives CSV",
     "https://static.www.nfl.com/public/stats/statistics/games/inactives/2026/reg/2026110801.csv"),
]

notes: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    notes.append(msg[-300:])


def get(url, tries=3, timeout=45, text=True):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            return body.decode("utf-8", "replace") if text else body
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(0.8 + attempt)
    log(f"  ! fetch failed {url}: {type(last).__name__}: {last}")
    return None


def status_of(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def jwrite(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


# --------------------------------------------------------------- payload mining
def page_payloads(page: str):
    """Yield (origin, obj) for every JSON payload embedded in an NFL.com page.

    Two shapes exist on nfl.com today: dehydrated react-query objects pushed through
    `self.__next_f.push(...)`, and a `__NEXT_DATA__` script block.
    """
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
        stack = [(obj, 0)]
        while stack:
            cur, depth = stack.pop()
            if depth > 8:
                continue
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    yield ("rsc", cur)
                stack.extend((v, depth + 1) for v in cur.values())
            elif isinstance(cur, list):
                stack.extend((v, depth + 1) for v in cur)
    for raw in re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S):
        try:
            yield ("nextdata", json.loads(raw))
        except Exception:
            continue


def payload_data(pairs):
    """(key, data) for every payload on a page, from both react-query and __NEXT_DATA__ shapes."""
    for origin, q in pairs:
        if origin == "rsc":
            data = (q.get("state") or {}).get("data")
            if data is not None:
                yield str((q.get("queryKey") or ["?"])[0]), data
        else:
            props = ((q.get("props") or {}).get("pageProps")) or q.get("data") or q
            if isinstance(props, dict):
                for k, v in props.items():
                    if isinstance(v, (dict, list)):
                        yield f"nextdata:{k}", v


def walk(node, pred, out, depth=0, cap=4000):
    if depth > 26 or len(out) >= cap:
        return
    if isinstance(node, dict):
        if pred(node):
            out.append(node)
        for v in node.values():
            walk(v, pred, out, depth + 1, cap)
    elif isinstance(node, list):
        for v in node:
            walk(v, pred, out, depth + 1, cap)


def dig(node, names, depth=0):
    """First scalar found under any key in `names` (case-insensitive), searching dicts then lists."""
    if depth > 14:
        return None
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k.lower() in names and isinstance(node[k], (str, int, float, bool)):
                return node[k]
        for v in node.values():
            got = dig(v, names, depth + 1)
            if got is not None:
                return got
    elif isinstance(node, list):
        for v in node:
            got = dig(v, names, depth + 1)
            if got is not None:
                return got
    return None


def as_int(v):
    try:
        if v is None or isinstance(v, bool):
            return None
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def game_status_name(g):
    st = g.get("status")
    if isinstance(st, dict):
        return str(dig(st, {"name", "state", "type", "label"}) or "").upper()
    return str(st or "").upper()


def text_scores(page: str):
    """Fallback score reader: the by-week page also renders an accessible score string per game,
    e.g. "Jaguars 33, Ravens 10, FINAL". Keyed by the two nicknames, matched case-insensitively.
    Used only when the structured payload carries no score, and recorded per row as scoreSource."""
    out: dict[tuple[str, str], tuple[int, int]] = {}
    pat = re.compile(r"([A-Za-z0-9][A-Za-z .'\-]{1,28}?)\s+(\d{1,2})\s*,\s*"
                     r"([A-Za-z0-9][A-Za-z .'\-]{1,28}?)\s+(\d{1,2})\s*,\s*FINAL")
    for a, ap, h, hp in pat.findall(page):
        key = (a.strip().split()[-1].lower(), h.strip().split()[-1].lower())
        out.setdefault(key, (int(ap), int(hp)))
    return out


# ---------------------------------------------------------------------- results
def parse_results(pairs, url, week_label, page_scores=None):
    games: list[dict] = []
    for _key, data in pairs:
        # Only the weekly-game-details shape carries results; the ways-to-watch shape on the
        # same page has the same ids but no score or status, so require a richer marker.
        walk(data, lambda d: bool(d.get("id")) and ("awayTeamStandings" in d or "summary" in d), games)
    rows, seen = [], set()
    page_scores = page_scores or {}
    for g in games:
        gid = str(g.get("id"))
        if gid in seen:
            continue
        seen.add(gid)
        away_obj = g.get("awayTeam") or {}
        home_obj = g.get("homeTeam") or {}
        summary = g.get("summary") or {}
        away = away_obj.get("fullName") or dig(away_obj, {"nameshort", "nickname"})
        home = home_obj.get("fullName") or dig(home_obj, {"nameshort", "nickname"})
        status = game_status_name(g) or str(g.get("status") or "").upper()
        # Scores live either on the team object, or in a per-team score block elsewhere
        # in the payload (summary.scores[].current.value). Match by team id, never by order.
        score_blocks: list[dict] = []
        walk(g, lambda d: isinstance(d, dict) and "team" in d
             and any(k in d for k in ("current", "points", "value", "score", "totals")), score_blocks, cap=200)

        def team_points(team_obj):
            direct = as_int(dig(team_obj, {"points", "totalpoints"}))
            if direct is not None:
                return direct
            tid = str(dig(team_obj, {"id"}) or "")
            for blk in score_blocks:
                t = blk.get("team")
                if not isinstance(t, dict):
                    continue
                if tid and str(dig(t, {"id"}) or "") == tid:
                    got = as_int(dig(blk, {"points", "value", "score"}))
                    if got is None:
                        got = as_int(dig(blk.get("current") or {}, {"value", "points"}))
                    return got
            return None

        a_pts = team_points(away_obj)
        h_pts = team_points(home_obj)
        score_source = "gamePayload" if (a_pts is not None and h_pts is not None) else None
        if a_pts is None or h_pts is None:
            nick = lambda n: (str(n or "").strip().split()[-1].lower() if n else "")
            alt = page_scores.get((nick(away), nick(home)))
            if alt:
                a_pts, h_pts, score_source = alt[0], alt[1], "pageScoreText"
        slug = None
        for e in (g.get("externalIds") or []):
            if isinstance(e, dict) and e.get("source") == "slug" and e.get("id"):
                slug = e["id"]
                break
        is_final = status in ("FINAL", "F", "FINAL_OVERTIME", "STATUS_FINAL", "FINAL/TIE") or "FINAL" in status
        winner = None
        if a_pts is not None and h_pts is not None:
            winner = "away" if a_pts > h_pts else ("home" if h_pts > a_pts else "tie")
        rows.append({
            "gameId": gid,
            "season": SEASON,
            "seasonType": g.get("seasonType"),
            "week": g.get("week"),
            "weekType": g.get("weekType"),
            "weekLabel": week_label,
            "dateUTC": g.get("time") or g.get("date"),
            "away": away,
            "home": home,
            "awayAbbr": dig(away_obj, {"abbreviation", "abbr"}),
            "homeAbbr": dig(home_obj, {"abbreviation", "abbr"}),
            "awayPoints": a_pts,
            "homePoints": h_pts,
            "status": status or None,
            "winner": winner,
            "venue": (g.get("venue") or {}).get("name") if isinstance(g.get("venue"), dict) else None,
            "category": g.get("category"),
            "scoreSource": score_source,
            "sourceUrl": (f"https://www.nfl.com/games/{slug}" if slug else url),
            "listUrl": url,
            "sourceName": "NFL.com official 2026 by-week schedule page (embedded game payload)",
            "verification": "verified" if (a_pts is not None and h_pts is not None)
                            else ("final-without-scores" if is_final else "scheduled"),
        })
    return rows, games


def parse_standings(pairs, url):
    """Official per-week standings snapshots: team, record, points for/against, splits."""
    blobs: list[dict] = []
    for key, data in pairs:
        if "Standings" not in key:
            continue
        walk(data, lambda d: isinstance(d.get("standings"), list), blobs)
    rows, seen = [], set()
    for blob in blobs:
        season = blob.get("season")
        season_type = blob.get("seasonType")
        for wk in (blob.get("weeks") or []):
            week = wk.get("week")
            for entry in (wk.get("standings") or []):
                team = dig(entry.get("team"), {"fullname", "nameshort"}) if isinstance(entry.get("team"), dict) else None
                if not team:
                    continue
                pts = dig(entry, {"points"})
                pfor = None
                pag = None
                if isinstance(pts, dict):
                    pfor = as_int(pts.get("for"))
                    pag = as_int(pts.get("against"))
                if pfor is None:
                    pfor = as_int(dig(entry, {"pointsfor", "pointsscored", "pf"}))
                    pag = as_int(dig(entry, {"pointsagainst", "pointsallowed", "pa"}))
                overall = entry.get("overall") or entry.get("winLossTies") or {}
                rec = {
                    "season": season, "seasonType": season_type, "week": week, "team": team,
                    "abbr": dig(entry.get("team"), {"abbreviation"}),
                    "wins": as_int(dig(overall if isinstance(overall, dict) else {}, {"wins"})),
                    "losses": as_int(dig(overall if isinstance(overall, dict) else {}, {"losses"})),
                    "ties": as_int(dig(overall if isinstance(overall, dict) else {}, {"ties"})),
                    "pointsFor": pfor, "pointsAgainst": pag,
                    "homeWins": as_int(dig(entry.get("home"), {"wins"})) if isinstance(entry.get("home"), dict) else None,
                    "homeLosses": as_int(dig(entry.get("home"), {"losses"})) if isinstance(entry.get("home"), dict) else None,
                    "awayWins": as_int(dig(entry.get("away"), {"wins"})) if isinstance(entry.get("away"), dict) else None,
                    "awayLosses": as_int(dig(entry.get("away"), {"losses"})) if isinstance(entry.get("away"), dict) else None,
                    "divisionRank": as_int(dig(entry.get("division"), {"rank"})) if isinstance(entry.get("division"), dict) else None,
                    "sourceUrl": url,
                    "sourceName": "NFL.com official standings (embedded by-week payload)",
                    "verification": "verified" if (pfor is not None and pag is not None) else "partial",
                }
                key2 = (week, team)
                if key2 in seen:
                    continue
                seen.add(key2)
                rows.append(rec)
    return rows, blobs


# --------------------------------------------------------------------- injuries
PLAYER_KEYS = {"playername", "full_name", "fullname", "player", "name", "lastname"}


def mine_players(node, out, depth=0, cap=1200):
    """Find dicts that look like one player's report row, keeping the enclosing context."""
    if depth > 26 or len(out) >= cap:
        return
    if isinstance(node, dict):
        low = {k.lower() for k in node.keys()}
        if low & PLAYER_KEYS and low & {"position", "pos", "injury", "injurydescription", "practicestatus",
                                        "gamestatus", "status", "injurytype", "statusdescription"}:
            out.append(node)
            return
        for v in node.values():
            mine_players(v, out, depth + 1, cap)
    elif isinstance(node, list):
        for v in node:
            mine_players(v, out, depth + 1, cap)


def parse_injury_like(pairs, url, label):
    rows, cands = [], []
    for _key, data in pairs:
        mine_players(data, cands)
    seen = set()
    for d in cands:
        low = {k.lower(): v for k, v in d.items()}

        def pick(names):
            for n in names:
                v = low.get(n)
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, dict):
                    got = dig(v, {"description", "label", "name", "value", "code", "statustype"})
                    if got is not None:
                        return str(got)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    got = dig(v[0], {"description", "label", "name", "value"})
                    if got is not None:
                        return str(got)
            return None

        player = pick(("player", "playername", "full_name", "fullname", "name"))
        if not player and "firstName" in low:
            player = f"{low.get('firstName')} {low.get('lastName')}".strip()
        if not player:
            continue
        pos = pick(("position", "pos"))
        inj = pick(("injurydescription", "injury", "injurytype", "description"))
        prac = pick(("practicestatus", "practiceparticipation", "practice", "practicestatusdescription",
                     "practicestatuscode"))
        game = pick(("gamestatus", "gamestatusdescription", "status", "gameparticipation", "statusdescription"))
        upd = pick(("statusdate", "updateddate", "reportdate", "date", "lastupdated", "updatedat"))
        club = pick(("club", "clubabbr", "team", "teamabbr", "abbreviation"))
        key = (label, player, pos, prac, game)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "label": label, "player": player, "position": pos, "injury": inj,
            "practiceStatus": prac, "gameStatus": game, "team": club,
            "reportedDate": upd,
            "sourceUrl": url,
            "sourceName": "NFL.com official injury report page (embedded payload)",
            "verification": "verified" if (prac or game) else "present-no-status",
        })
    return rows, cands


# ------------------------------------------------------------------- discovery
def discover(url, name, extra_re=None):
    page = get(url)
    if not page:
        return {"url": url, "fetched": False}
    pairs = list(page_payloads(page))
    payload_index = []
    for key, data in pairs:
        kinds = []
        sample = json.dumps(data, ensure_ascii=False)[:900] if not isinstance(data, str) else data[:900]
        n_list = 0
        stack = [(data, 0)]
        while stack:
            cur, d = stack.pop()
            if d > 10:
                continue
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        n_list = max(n_list, len(v))
                        kinds.append(f"{k}[{len(v)}]:{','.join(sorted(v[0].keys())[:12])}")
                    stack.append((v, d + 1))
            elif isinstance(cur, list):
                for v in cur:
                    stack.append((v, d + 1))
        kinds = list(dict.fromkeys(kinds))[:12]
        payload_index.append({"queryKey": key[:160], "largestList": n_list,
                              "lists": kinds[:8], "sample": sample})
    api_urls = sorted({u for u in re.findall(r'https?://[^"\'\\ ]{6,220}', page)
                       if re.search(r"(api\.nfl\.com|/api/|injur|inactiv|depth|transaction)", u)})[:60]
    hrefs = sorted({h for h in re.findall(r'href="(/[^"]*(?:injur|inactiv|depth|transaction)[^"]*)"', page)})[:60]
    out = {
        "url": url, "fetched": True, "bytes": len(page),
        "payloadCount": len(pairs),
        "payloadIndex": payload_index[:40],
        "apiUrls": api_urls,
        "relatedHrefs": hrefs,
    }
    if extra_re:
        out["matches"] = {k: sorted({m for m in re.findall(v, page)})[:20] for k, v in extra_re.items()}
    return out


# --------------------------------------------------------------------- inactives
def parse_inactives(pairs, url):
    rows, cands = [], []
    for _key, data in pairs:
        mine_players(data, cands)
    seen = set()
    for d in cands:
        low = {k.lower(): v for k, v in d.items()}
        name = None
        for n in ("player", "playername", "full_name", "name"):
            v = low.get(n)
            if isinstance(v, str) and v.strip():
                name = v.strip()
            elif isinstance(v, dict):
                name = dig(v, {"fullname", "displayname", "name"})
            if name:
                break
        if not name:
            continue
        st = None
        for n in ("status", "inactivestatus", "statusdescription", "type"):
            v = low.get(n)
            if isinstance(v, str):
                st = v.strip()
                break
            if isinstance(v, dict):
                st = dig(v, {"description", "label", "name", "value"})
                if st:
                    st = str(st)
                    break
        key = (str(name), str(st))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "player": str(name), "position": dig(d, {"position", "pos"}),
            "status": st,
            "team": dig(d, {"club", "team", "abbreviation"}),
            "gameId": dig(d, {"gameid", "gameId"}),
            "sourceUrl": url,
            "sourceName": "NFL.com inactives page (embedded payload)",
            "verification": "verified" if st else "present-no-status",
        })
    return rows, cands



# ------------------------------------------------------------- news-article pages
POS_RE = re.compile(r"^(QB|RB|FB|WR|TE|LT|LG|C|RG|RT|OL|DL|DE|DT|NT|LB|ILB|OLB|MLB|CB|S|FS|SS|DB|"
                    r"K|P|LS|G|T|EDGE|OT|OG)[\.\s]", re.I)


def strings(node, depth=0):
    if depth > 26:
        return
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from strings(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v, depth + 1)


def strip_tags(fragment: str) -> str:
    frag = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    frag = re.sub(r"<br\s*/?>", " ", frag, flags=re.I)
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = html_lib.unescape(frag)
    return re.sub(r"\s+", " ", frag).strip()


def parse_article_players(html_text: str, page_url: str, source_label: str):
    """Extract (heading, item) pairs from an official NFL.com news article.

    Items are recognised as list entries that link to nfl.com/players/... — the league's own
    format for its weekly injury-report and game-day inactives articles. Position is read from
    the leading token of the item text; anything the article does not state stays None.
    """
    rows = []
    pat = re.compile(r"<(?P<tag>h[1-6]|li)[^>]*>(?P<body>.*?)</(?P=tag)>", re.S | re.I)
    heading = None
    for m in pat.finditer(html_text):
        body = strip_tags(m.group("body"))
        if not body:
            continue
        if m.group("tag").lower().startswith("h"):
            if len(body) <= 60:
                heading = body
            continue
        link = re.search(r'href="(?P<h>https?://www\.nfl\.com/players/[^"]+|/players/[^"]+)"', m.group("body"))
        if not link:
            continue
        text = body
        pos = None
        if POS_RE.match(text):
            pos = re.match(r"^([A-Za-z\.]+)", text).group(1).upper().replace(".", "")
            text = text[re.match(r"^[A-Za-z\.]+\s+", text).end():]
        note = None
        paren = re.findall(r"\(([^)]{2,140})\)", text)
        if paren:
            note = "; ".join(paren)
            text = re.sub(r"\s*\([^)]{2,140}\)", " ", text).strip()
        href = link.group("h")
        if href.startswith("/"):
            href = "https://www.nfl.com" + href
        rows.append({
            "section": heading,
            "player": re.sub(r"\s+", " ", text).strip(" -"),
            "position": pos,
            "note": note,
            "playerUrl": href,
            "articleUrl": page_url,
            "sourceName": source_label,
            "verification": "verified",
        })
    return rows


def find_article_links(page: str, kinds=("injur", "inactiv")):
    """Official nfl.com/news article links discovered on the league's own injury/inactives pages."""
    out = []
    for href in re.findall(r'href="(/news/[^"]+)"', page):
        low = href.lower()
        if any(k in low for k in kinds):
            if href not in out:
                out.append(href)
    return out


def collect_articles(base_pages, max_pages=28):
    """Follow the official links only — no URL is constructed or guessed."""
    links: list[str] = []
    for url in base_pages:
        page = get(url)
        if not page:
            continue
        for href in find_article_links(page):
            full = "https://www.nfl.com" + href
            if full not in links:
                links.append(full)
    rows, failures, ok_pages = [], [], 0
    for url in links[:max_pages]:
        page = get(url)
        if not page:
            failures.append(url)
            continue
        candidates = [page]
        try:
            for _key, data in payload_data(page_payloads(page)):
                candidates.extend(s for s in strings(data) if "/players/" in s and "<li" in s.lower())
        except Exception as e:  # noqa: BLE001
            failures.append(f"{url}: payload error {e}")
        got = []
        for cand in candidates:
            got = parse_article_players(cand, url, "NFL.com official news article (injury report / inactives)")
            if got:
                break
        if got:
            ok_pages += 1
            rows.extend(got)
            log(f"article {url.split('/news/')[1][:58]}: {len(got)} rows")
        else:
            failures.append(f"{url}: no player list parsed")
            log(f"article {url}: 0 rows")
    return rows, links, failures, ok_pages

# ------------------------------------------------------------------------ main
def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    os.makedirs(OUT, exist_ok=True)

    # 1 + 2 — results and official standings, week by week ---------------------
    all_rows: list[dict] = []
    standing_rows: list[dict] = []
    per_week: dict[str, int] = {}
    per_week_final: dict[str, int] = {}
    standings_weeks_seen: set[int] = set()
    for wk in WEEKS:
        url = f"{SCHEDULE_BASE}week-{wk}"
        page = get(url)
        if page is None:
            per_week[f"Week {wk}"] = -1
            continue
        pairs = list(payload_data(page_payloads(page)))
        rows, _games = parse_results(pairs, url, f"Week {wk}", text_scores(page))
        srows, _blobs = parse_standings(pairs, url)
        per_week[f"Week {wk}"] = len(rows)
        per_week_final[f"Week {wk}"] = len([r for r in rows if r["verification"] == "verified"])
        standings_weeks_seen |= {r["week"] for r in srows if isinstance(r["week"], int)}
        all_rows.extend(rows)
        standing_rows.extend(srows)
        log(f"week {wk}: games={len(rows)} final={per_week_final[f'Week {wk}']} standingsRows={len(srows)}")

    best: dict[str, dict] = {}
    for r in all_rows:
        cur = best.get(r["gameId"])
        if cur is None:
            best[r["gameId"]] = r
        else:
            rank = lambda x: (x["awayPoints"] is not None, x["verification"] == "verified")
            if rank(r) > rank(cur):
                best[r["gameId"]] = r
    all_rows = sorted(best.values(), key=lambda r: (r["dateUTC"] or "", str(r["gameId"])))
    finals = [r for r in all_rows if r["verification"] == "verified"]
    jwrite("results-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} games captured from official nfl.com by-week pages (embedded payload)",
            "retrievedUTC": started,
            "games": len(all_rows),
            "final": len(finals),
            "perWeek": per_week,
            "perWeekFinal": per_week_final,
            "sourceName": "NFL.com official schedule (by-week)",
            "sourcePages": [f"{SCHEDULE_BASE}week-{w}" for w in WEEKS],
            "note": "Scores come from the same embedded payload the page renders. Games the payload "
                    "does not carry scores for keep null and are labelled scheduled/final-without-scores.",
        },
        "games": all_rows,
    })
    jwrite("standings-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} official standings snapshots (record, points for/against, splits)",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(standing_rows),
            "weeksSeen": sorted(standings_weeks_seen),
            "sourcePages": [f"{SCHEDULE_BASE}week-{w}" for w in WEEKS],
            "sourceName": "NFL.com official standings (embedded by-week payload)",
        },
        "rows": standing_rows,
    })

    # 3 — weekly official injury reports ---------------------------------------
    inj_rows: list[dict] = []
    inj_counts: dict[str, int] = {}
    inj_week_params = ["", *[f"?season={SEASON}&week={w}" for w in range(9, 12)]]
    for i, param in enumerate(inj_week_params):
        url = INJURY_URL + param
        page = get(url)
        label = "current" if not param else param.split("week=")[1]
        if page is None:
            inj_counts[label] = -1
            continue
        rows, _c = parse_injury_like(list(payload_data(page_payloads(page))), url, label)
        inj_counts[label] = len(rows)
        inj_rows.extend(rows)
        log(f"injuries {label}: {len(rows)} rows")
    jwrite("injuries-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} official weekly injury report rows (nfl.com/injuries)",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(inj_rows),
            "perRequest": inj_counts,
            "sourcePages": [INJURY_URL + p for p in inj_week_params],
            "sourceName": "NFL.com official injury report",
            "note": "Practice participation and game status are separate official fields; the page does not "
                    "publish depth-chart order, so backup tier is never inferred here.",
        },
        "rows": inj_rows,
    })

    # 3b — official weekly injury-report and game-day inactives ARTICLES ----------------
    art_rows, art_links, art_fail, art_ok = collect_articles([INJURY_URL, INACTIVE_URL])
    jwrite("articles-2026.json", {
        "meta": {
            "dataset": "NFL.com official news articles for weekly injury reports and game-day inactives",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(art_rows),
            "pagesParsed": art_ok,
            "linksDiscovered": art_links,
            "failures": art_fail,
            "sourceName": "NFL.com news article pages (league-published)",
            "method": "Links are taken from nfl.com/injuries/ and nfl.com/inactives/ themselves; the page that "
                      "carries no player list is recorded as a failure instead of being filled in.",
        },
        "rows": art_rows,
    })
    # 4 — inactives + structural discovery dumps -------------------------------
    page = get(INACTIVE_URL)
    ina_rows: list[dict] = []
    if page:
        ina_rows, _ = parse_inactives(list(payload_data(page_payloads(page))), INACTIVE_URL)
    jwrite("inactives-2026.json", {
        "meta": {
            "dataset": "NFL.com inactives page rows (game-day inactive designations)",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(ina_rows),
            "sourceUrl": INACTIVE_URL,
            "sourceName": "NFL.com inactives",
            "note": "Zero rows means the page renders from a client-side call the static HTML does not contain.",
        },
        "rows": ina_rows,
    })
    discovery = {
        "meta": {
            "purpose": "Structural reconnaissance so parsers are developed against evidence, not guesses: "
                       "which embedded payloads exist, which API URLs the page references, and the exact "
                       "field names in each list.",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        "injuries": discover(INJURY_URL, "injuries"),
        "inactives": discover(INACTIVE_URL, "inactives"),
        "transactions": discover(TRANSACTIONS_URL, "transactions"),
        "teamStats": discover(TEAM_STATS_URL, "team-stats"),
        "scheduleWeek9": discover(f"{SCHEDULE_BASE}week-9", "schedule-week-9"),
    }
    jwrite("discovery.json", discovery)

    # 5 — endpoint probe --------------------------------------------------------
    probe = []
    for name, url in PROBE_ENDPOINTS:
        code, ctype = status_of(url)
        probe.append({"name": name, "url": url, "httpStatus": code,
                      "contentType": ctype if isinstance(ctype, str) else str(ctype),
                      "reachable": code == 200,
                      "meaning": "200 OK — public official page" if code == 200 else
                                 ("401 — exists but requires authorisation (licensed endpoint)" if code == 401 else
                                  ("404 — not published at this address" if code == 404 else "unreachable"))})
        log(f"probe {name}: {code}")
    jwrite("probe-report.json", {
        "meta": {
            "purpose": "Record which official endpoints exist for results / injury / inactive / depth data. "
                       "Drives the source-availability table on the site. Non-200 answers are findings, not errors.",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "method": "HTTP GET status from the CI runner (sandbox has no outbound network)",
        },
        "endpoints": probe,
    })

    jwrite("fetch-report.json", {
        "meta": {
            "script": "tools/fetch_nfl_lab.py",
            "startedUTC": started,
            "finishedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "python": sys.version.split()[0],
        },
        "counts": {
            "games": len(all_rows),
            "gamesFinalWithScores": len(finals),
            "standingsRows": len(standing_rows),
            "injuryRows": len(inj_rows),
            "inactivesRows": len(ina_rows),
            "articleRows": len(art_rows),
            "articlePagesParsed": art_ok,
        },
        "extraction": {
            "gamesWithoutScores": len([r for r in all_rows if r["awayPoints"] is None]),
            "standingsWithoutPoints": len([r for r in standing_rows if r["pointsFor"] is None]),
            "injuriesWithoutTeam": len([r for r in inj_rows if not r["team"]]),
            "injuriesWithoutPosition": len([r for r in inj_rows if not r["position"]]),
        },
        "perWeek": per_week,
        "perWeekFinal": per_week_final,
        "injuryPerRequest": inj_counts,
        "standingsWeeks": sorted(standings_weeks_seen),
        "notes": notes[-30:],
    })
    log(f"wrote {OUT}: games={len(all_rows)} final={len(finals)} standings={len(standing_rows)} "
        f"injuries={len(inj_rows)} inactives={len(ina_rows)}")


if __name__ == "__main__":
    main()
