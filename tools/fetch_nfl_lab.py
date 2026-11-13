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


SOURCES: list[dict] = []


def get(url, tries=3, timeout=45, text=True):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            SOURCES.append({"url": url, "ok": True, "httpStatus": r.status,
                            "bytes": len(body), "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                            "contentType": r.headers.get("Content-Type", "")})
            return body.decode("utf-8", "replace") if text else body
        except Exception as e:  # noqa: BLE001 - diagnostics only
            last = e
            time.sleep(0.8 + attempt)
    log(f"  ! fetch failed {url}: {type(last).__name__}: {last}")
    SOURCES.append({"url": url, "ok": False, "httpStatus": None,
                    "error": f"{type(last).__name__}: {last}",
                    "at": dt.datetime.now(dt.timezone.utc).isoformat()})
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


SCORE_TEXT_RE = re.compile(
    r"(?P<away>[A-Za-z0-9][A-Za-z .'\-]{1,28}?)\s+(?P<as>\d{1,2})\s*,\s*"
    r"(?P<home>[A-Za-z0-9][A-Za-z .'\-]{1,28}?)\s+(?P<hs>\d{1,2})\s*,\s*(?P<state>FINAL(?:/OT)?|FINAL, TIED)")


ANCHOR_RE = re.compile(r'<a[^>]*href="(?:https?://www\.nfl\.com)?/games/([a-z0-9\-]+)"[^>]*>(.*?)</a>',
                       re.S | re.I)


def page_scores_by_slug(page: str):
    """Bind every published FINAL score to its own game slug, with a nickname integrity check.

    The by-week page carries one accessible string per game, e.g.
    "49ers 27, Rams 7, FINAL, Thursday, September 10th", inside that game's own link to
    /games/<slug>. Two passes are run over the page because some cards are emitted as real HTML and
    others sit inside an HTML-escaped JSON attribute: raw, then entity-decoded.

    A score is accepted only when the two nicknames in the label agree with the away/home clubs of
    the game it is being attached to, so a neighbouring card can never lend its number. Mismatches
    are counted and reported instead of being resolved silently.
    """
    out: dict[str, tuple[int, int, str, str]] = {}
    un = html_lib.unescape(page)
    # Some game cards are emitted as real HTML; others sit inside a JSON string in a data attribute
    # where the quotes are backslash-escaped. Every form is read; none of them is guessed.
    for variant in (page, un, un.replace('\\"', '"')):
        for slug, inner in ANCHOR_RE.findall(variant):
            text = strip_tags(inner)
            m = SCORE_TEXT_RE.search(text)
            if m:
                out.setdefault(slug, (int(m.group("as")), int(m.group("hs")),
                                      m.group("away").strip().lower(), m.group("home").strip().lower()))
    return out


# ---------------------------------------------------------------------- results
def parse_results(pairs, url, week_label, page_scores=None):
    games: list[dict] = []
    for _key, data in pairs:
        # Only the weekly-game-details shape carries results; the ways-to-watch shape on the
        # same page has the same ids but no score or status, so require a richer marker.
        walk(data, lambda d: bool(d.get("id")) and ("awayTeamStandings" in d or "summary" in d), games)
    rows, seen = [], set()
    by_slug = page_scores or {}
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

        slug = None
        for e in (g.get("externalIds") or []):
            if isinstance(e, dict) and e.get("source") == "slug" and e.get("id"):
                slug = e["id"]
                break
        a_pts = team_points(away_obj)
        h_pts = team_points(home_obj)
        score_source = "gamePayload" if (a_pts is not None and h_pts is not None) else None
        score_mismatch = None
        if (a_pts is None or h_pts is None) and slug and slug in by_slug:
            alt = by_slug[slug]
            nick = lambda n: (str(n or "").strip().split()[-1].lower() if n else "")
            if nick(away) == alt[2].split()[-1] and nick(home) == alt[3].split()[-1]:
                a_pts, h_pts, score_source = alt[0], alt[1], "pageScoreLink"
            else:
                score_mismatch = f"label says {alt[2]} {alt[0]} / {alt[3]} {alt[1]}, row says " \
                                 f"{away} / {home}"
        is_final = ("FINAL" in status.upper()) or (a_pts is not None and h_pts is not None)
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
            "scoreMismatch": score_mismatch,
            "sourceUrl": (f"https://www.nfl.com/games/{slug}" if slug else url),
            "listUrl": url,
            "sourceName": "NFL.com official 2026 by-week schedule page (embedded game payload)",
            "verification": "verified" if (a_pts is not None and h_pts is not None)
                            else ("final-without-scores" if is_final else "scheduled"),
            "scoreSourceNote": ("official page label says FINAL" if (a_pts is not None and score_source) else None),
        })
    return rows, games


def parse_standings(pairs, url):
    """Official standings snapshots (record, points for/against, splits) embedded on by-week pages."""
    blobs: list[dict] = []
    for key, data in pairs:
        if "Standings" not in key:
            continue
        walk(data, lambda d: isinstance(d.get("standings"), list), blobs)
    rows, seen = [], set()
    for blob in blobs:
        week = blob.get("week")
        season = blob.get("season")
        season_type = blob.get("seasonType")
        for entry in (blob.get("standings") or []):
            team_obj = entry.get("team") if isinstance(entry.get("team"), dict) else {}
            team = team_obj.get("fullName") or dig(team_obj, {"nameshort", "nickname"})
            if not team:
                continue
            pts = entry.get("points") if isinstance(entry.get("points"), dict) else None
            pfor = as_int((pts or {}).get("for"))
            pag = as_int((pts or {}).get("against"))
            overall = entry.get("overall") if isinstance(entry.get("overall"), dict) else {}
            rec = {
                "season": season if season is not None else SEASON,
                "seasonType": season_type or "REG",
                "week": week,
                "team": team,
                "abbr": dig(team_obj, {"abbreviation"}),
                "wins": as_int(overall.get("wins")),
                "losses": as_int(overall.get("losses")),
                "ties": as_int(overall.get("ties")),
                "pointsFor": pfor,
                "pointsAgainst": pag,
                "homeWins": as_int(dig(entry.get("home"), {"wins"})) if isinstance(entry.get("home"), dict) else None,
                "homeLosses": as_int(dig(entry.get("home"), {"losses"})) if isinstance(entry.get("home"), dict) else None,
                "awayWins": as_int(dig(entry.get("road"), {"wins"})) if isinstance(entry.get("road"), dict)
                           else (as_int(dig(entry.get("away"), {"wins"})) if isinstance(entry.get("away"), dict) else None),
                "divisionRank": as_int(dig(entry.get("division"), {"rank"})) if isinstance(entry.get("division"), dict) else None,
                "playoffClinched": dig(entry.get("clinched"), {"playoff"}) if isinstance(entry.get("clinched"), dict) else None,
                "sourceUrl": url,
                "sourceName": "NFL.com official standings (embedded by-week payload)",
                "verification": "verified" if (pfor is not None and pag is not None) else "record-only",
            }
            key2 = (week, team)
            if key2 in seen:
                continue
            seen.add(key2)
            rows.append(rec)
    return rows, blobs



def _teams(pairs, url):
    """All 32 clubs from the official `useFetchExperienceTeams` payload (id, name, abbreviation, slug)."""
    out, seen = [], set()
    for key, data in pairs:
        if "Teams" not in key:
            continue
        blobs: list[dict] = []
        walk(data, lambda d: isinstance(d.get("fullName"), str) and ("abbreviation" in d or "id" in d), blobs)
        for d in blobs:
            name = d.get("fullName")
            if not name or name in seen:
                continue
            seen.add(name)
            slug = dig(d, {"slug", "teamslug", "url", "href"})
            slug = str(slug or "").strip("/").split("/")[-1] or None
            out.append({
                "id": str(d.get("id")) if d.get("id") is not None else None,
                "fullName": name,
                "abbreviation": dig(d, {"abbreviation", "abbr"}),
                "conference": dig(d, {"conferenceabbr", "conference"}),
                "division": dig(d, {"divisionabbr", "division"}),
                "slug": slug,
                "sourceUrl": url,
                "sourceName": "NFL.com club list (embedded schedule payload)",
                "verification": "verified",
            })
    return out




CLUB_LINK_RE = re.compile(
    r'<a[^>]*href="(?:https?://www\.nfl\.com)?/teams/([a-z0-9\-]+)/?"[^>]*>(?P<t>.*?)</a>', re.S | re.I)


def club_labels(page: str):
    """{clubSlug: displayed club name} from the club links the page itself renders."""
    out = {}
    for m in CLUB_LINK_RE.finditer(page):
        slug = m.group(1)
        label = re.sub(r"\s+", " ", strip_tags(m.group("t"))).strip()
        if label and len(label) <= 60 and slug not in out:
            out[slug] = label
    return out



def game_page_scores(page: str, url: str, away: str, home: str):
    """Score reader for a single game page: (awayPoints, homePoints, status, how).

    Three official shapes are tried in order - the accessible score string
    ("Jaguars 33, Ravens 10, FINAL"), the structured payload, and the page title. If none of them
    carries a score the row stays null; a missing score is reported, never estimated.
    """
    slug = (url or "").rsplit("/", 1)[-1]
    un = html_lib.unescape(page)
    for variant in (page, un, un.replace('\\"', '"')):
        own = re.search(r'/games/' + re.escape(slug) + r'[^>]*>(?P<body>.*?)</a>', variant, re.S | re.I)
        for text in ([own.group("body")] if own else []) + [variant[:200000]]:
            m = SCORE_TEXT_RE.search(strip_tags(text) if "<" in text else text)
            if m:
                return int(m.group("as")), int(m.group("hs")), "FINAL", "gamePageScoreText"
    pairs = list(payload_data(page_payloads(page)))
    blocks: list[dict] = []
    for _key, data in pairs:
        walk(data, lambda d: isinstance(d, dict) and "team" in d
             and any(k in d for k in ("current", "points", "value", "score")), blocks, cap=120)
    by_id: dict[str, int] = {}
    for blk in blocks:
        tid = str(dig(blk.get("team"), {"id"}) or "")
        pts = as_int(dig(blk, {"points", "value", "score"}))
        if pts is None:
            pts = as_int(dig(blk.get("current") or {}, {"value", "points"}))
        if tid and pts is not None:
            by_id[tid] = pts
    games: list[dict] = []
    for _key, data in pairs:
        walk(data, lambda d: "awayTeam" in d and "homeTeam" in d, games, cap=20)
    if games:
        a = by_id.get(str(dig(games[0].get("awayTeam"), {"id"}) or ""))
        h = by_id.get(str(dig(games[0].get("homeTeam"), {"id"}) or ""))
        if a is not None and h is not None:
            return a, h, game_status_name(games[0]) or "FINAL", "gamePagePayload"
    t = re.search(r"<title>[^<]*?(\d{1,2})\s*-\s*(\d{1,2})[^<]*</title>", page, re.I)
    if t:
        return int(t.group(2)), int(t.group(1)), "FINAL", "gamePageTitle"
    return None, None, None, None


# ------------------------------------------------------------- plain HTML tables
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<t(?P<k>[hd])[^>]*>(?P<v>.*?)</t(?P=k)>", re.S | re.I)
LINK_RE = re.compile(r'<a[^>]*href="(?P<h>[^"]+)"[^>]*>(?P<t>.*?)</a>', re.S | re.I)
HEAD_RE = re.compile(r"<h([1-6])[^>]*>(?P<v>.*?)</h\1>", re.S | re.I)


def parse_tables(page: str, base_url: str):
    """Every HTML table on a page, with its header row and the nearest preceding heading.

    The official injury-report page renders one table per club. Nothing is invented: a cell that
    is empty in the source stays an empty string in the parsed row.
    """
    tables = []
    for m in re.finditer(r"<table[^>]*>(.*?)</table>", page, re.S | re.I):
        seg = m.group(1)
        trs = ROW_RE.findall(seg)
        if not trs:
            continue
        rows = []
        for tr in trs:
            cells = [(mm.group("k"), strip_tags(mm.group("v")), LINK_RE.search(mm.group("v")))
                     for mm in CELL_RE.finditer(tr)]
            if cells:
                rows.append(cells)
        headers = [c[1] for c in rows[0]] if rows and all(c[0] == "h" for c in rows[0]) else []
        body = rows[1:] if headers else rows
        context = page[max(0, m.start() - 6000):m.start()]
        heads = HEAD_RE.findall(context)
        heading = strip_tags(heads[-1][1]) if heads else None
        clubs = list(CLUB_LINK_RE.finditer(context))
        club = clubs[-1].group(1) if clubs else None
        club_label = re.sub(r"\s+", " ", strip_tags(clubs[-1].group("t"))).strip() if clubs else None
        tables.append({
            "headers": headers,
            "rows": body,
            "heading": heading,
            "clubSlug": club,
            "clubLabel": (club_label or None) if (club_label or None) not in ("",) else None,
            "url": base_url,
            "rawRowCount": len(body),
        })
    return tables


def table_rows_to_injuries(tables, label):
    """Normalise official injury-report tables into one row per player.

    The page columns are Player / Position / Injuries / Practice Status / Game Status. A column the
    page does not carry produces a null — never a guess.
    """
    rows = []
    for t in tables:
        hdr = [h.lower().strip() for h in t["headers"]]
        if "player" not in hdr:
            continue
        for cells in t["rows"]:
            texts = [c[1] for c in cells]
            if not texts or not texts[0].strip():
                continue
            link = next((c[2] for c in cells if c[2]), None)
            href = None
            if link:
                href = link.group("h")
                if href.startswith("/"):
                    href = "https://www.nfl.com" + href

            def get(name):
                for j, h in enumerate(hdr):
                    if h.startswith(name):
                        return texts[j] if j < len(texts) else None
                return None

            rows.append({
                "label": label,
                "section": t["heading"],
                "clubSlug": t["clubSlug"],
                "clubLabel": t.get("clubLabel"),
                "player": texts[0].strip(),
                "position": get("position") or None,
                "injury": get("injur") or None,
                "practiceStatus": get("practice") or None,
                "gameStatus": get("game") or None,
                "playerUrl": href,
                "sourceUrl": t["url"],
                "sourceName": "NFL.com official injury report (page table)",
                "verification": "verified" if (get("practice") or get("game")) else "present-no-status",
            })
    return rows



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
    pairs = list(payload_data(page_payloads(page)))
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


PLAYER_A = re.compile(r'<a[^>]*href="(?P<h>(?:https?://www\.nfl\.com)?/players/[^"]+)"[^>]*>(?P<t>.*?)</a>',
                      re.S | re.I)


POSITIONS = {"QB", "RB", "FB", "WR", "TE", "LT", "LG", "C", "RG", "RT", "OL", "DL", "DE", "DT", "NT",
             "LB", "ILB", "OLB", "MLB", "CB", "S", "FS", "SS", "DB", "K", "P", "LS", "G", "T", "EDGE",
             "OT", "OG", "OLB", "WR-RB", "ATH"}


def parse_article_players(html_text: str, page_url: str, source_label: str):
    """Rows from an official NFL.com news article (weekly injury report / game-day inactives).

    One row per player link. Position is taken from the token the article puts directly before the
    name (list style "OUT: CB Name (injury)" and prose style "Denver Broncos cornerback Riley Moss");
    the note is the parenthetical the article attaches to that player; the sentence context is kept
    verbatim so a human can re-read the source. Nothing is inferred — if the article does not state a
    position or a status, the field stays null.
    """
    rows = []
    pat = re.compile(r"<(?P<tag>h[1-6]|li|p)[^>]*>(?P<body>.*?)</(?P=tag)>", re.S | re.I)
    heading = None
    for m in pat.finditer(html_text):
        body = m.group("body")
        links = list(PLAYER_A.finditer(body))
        if m.group("tag").lower().startswith("h") and not links:
            txt = strip_tags(body)
            if txt and len(txt) <= 60:
                heading = txt
            continue
        if not links:
            continue
        text_only = re.sub(r"\s+", " ", strip_tags(body)).strip()
        names = [strip_tags(lk.group("t")).strip() for lk in links]
        flat = body
        for i in reversed(range(len(links))):
            lk = links[i]
            flat = flat[:lk.start()] + f"\x00{i}\x00{names[i]}\x01" + flat[lk.end():]
        plain = re.sub(r"<[^>]+>", " ", flat)
        plain = html_lib.unescape(plain)
        plain = re.sub(r"[ \t]+", " ", plain)
        parts = re.split(r"\x00(\d+)\x00", plain)
        pre = re.sub(r"\s+", " ", parts[0]).strip()

        def position_from(before_text):
            toks = [t for t in re.findall(r"[A-Za-z\-]{1,6}", before_text) if t.upper() in POSITIONS]
            if toks:
                return toks[-1].upper()
            return None

        for i in range(1, len(parts) - 1, 2):
            idx = int(parts[i])
            seg = parts[i + 1]
            name, _, rest = seg.partition("\x01")
            name = name.strip()
            if not name:
                continue
            rest = re.sub(r"\s+", " ", rest).strip()
            before = pre if idx == 0 else re.sub(r"\s+", " ", parts[i - 1].split("\x01")[-1]).strip()
            pos = position_from(before)
            note = None
            pm = re.match(r"^\s*\(([^)]{2,160})\)", rest)
            if pm:
                note = pm.group(1).strip()
            status = None
            low_before = before.lower()
            for word in ("did not participate", "limited participation", "full participation",
                         "placed on injured reserve", "on injured reserve", "waived", "elevated",
                         "practice squad"):
                if word in low_before:
                    status = word.title()
                    break
            if not status:
                up = before.upper().replace(":", " ").split()
                if "OUT" in up:
                    status = "Out"
                elif "DOUBTFUL" in up:
                    status = "Doubtful"
                elif "QUESTIONABLE" in up:
                    status = "Questionable"
                elif "PROBABLE" in up:
                    status = "Probable"
            href = links[idx].group("h")
            if href.startswith("/"):
                href = "https://www.nfl.com" + href
            rows.append({
                "section": heading,
                "player": name,
                "position": pos,
                "note": note,
                "statusWord": status,
                "context": text_only[:400],
                "playerUrl": href,
                "articleUrl": page_url,
                "sourceName": source_label,
                "verification": "verified",
            })
    return rows


def page_diagnostics(page: str, url: str):
    low = page.lower()
    out = {"url": url, "bytes": len(page), "playerLinks": low.count("/players/"),
           "liTags": low.count("<li"), "payloads": len(list(page_payloads(page)))}
    i = low.find("/players/")
    if i > 0:
        out["firstPlayerLinkContext"] = re.sub(r"\s+", " ", page[max(0, i - 400):i + 400])[:800]
    return out


def find_article_links(page: str, kinds=("injur", "inactiv")):
    """Official nfl.com/news article links discovered on the league's own injury/inactives pages."""
    out = []
    for href in re.findall(r'href="(/news/[^"]+)"', page):
        low = href.lower()
        if any(k in low for k in kinds):
            if href not in out:
                out.append(href)
    return out


def collect_articles(base_pages, max_pages=30):
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
    rows, failures, ok_pages, kinds = [], [], 0, {}
    for url in links[:max_pages]:
        page = get(url)
        if not page:
            failures.append({"url": url, "reason": "fetch failed"})
            continue
        candidates = [page]
        try:
            for _key, data in payload_data(page_payloads(page)):
                candidates.extend(x for x in strings(data) if "/players/" in x and "<li" in x.lower())
        except Exception as e:  # noqa: BLE001
            failures.append({"url": url, "reason": f"payload error {e}"})
        got: list[dict] = []
        for cand in candidates:
            got = parse_article_players(cand, url, "NFL.com official news article")
            if got:
                break
        if got:
            ok_pages += 1
            kind = ("inactives" if "inactiv" in url.lower()
                    else ("injury-report" if "injury-report" in url.lower() else "other"))
            for r in got:
                r["articleKind"] = kind
            kinds[kind] = kinds.get(kind, 0) + len(got)
            rows.extend(got)
            log(f"article {url.split('/news/')[1][:56]}: {len(got)} rows ({kind})")
        else:
            failures.append(dict(page_diagnostics(page, url), reason="no player link parsed"))
            log(f"article {url}: 0 rows")
    return rows, links, failures, ok_pages, kinds

# ------------------------------------------------------------------------ main
def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    os.makedirs(OUT, exist_ok=True)

    # 1 + 2 — results and official standings, week by week ---------------------
    all_rows: list[dict] = []
    standing_rows: list[dict] = []
    mismatch_rows: list[dict] = []
    per_week: dict[str, int] = {}
    per_week_final: dict[str, int] = {}
    fallback_probe: dict[int, dict] = {}
    teams_found: dict[str, dict] = {}
    standings_weeks_seen: set[int] = set()
    standings_seen: set[tuple] = set()
    for wk in WEEKS:
        url = f"{SCHEDULE_BASE}week-{wk}"
        page = get(url)
        if page is None:
            per_week[f"Week {wk}"] = -1
            continue
        pairs = list(payload_data(page_payloads(page)))
        scores = page_scores_by_slug(page)
        fallback_probe[wk] = {
            "anchorCount": len(re.findall(r'href="[^"]*/games/[a-z0-9\-]+', page)),
            "scoreAnchorsParsed": len(scores),
            "rawSample": (re.sub(r"\s+", " ", page[page.find("/games/") - 200:page.find("/games/") + 1400])
                          if "/games/" in page else ""),
        }
        rows, _games = parse_results(pairs, url, f"Week {wk}", scores)
        mismatch_rows.extend([r for r in rows if r.get("scoreMismatch")])
        srows, _blobs = parse_standings(pairs, url)
        per_week[f"Week {wk}"] = len(rows)
        per_week_final[f"Week {wk}"] = len([r for r in rows if r["verification"] == "verified"])
        for t in _teams(pairs, url):
            teams_found.setdefault(t["slug"] or t["fullName"], t)
        standings_weeks_seen |= {r["week"] for r in srows if isinstance(r["week"], int)}
        all_rows.extend(rows)
        for r in srows:
            k = (r["week"], r["team"])
            if k not in standings_seen:
                standings_seen.add(k)
                standing_rows.append(r)
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
    jwrite("score-fallback-probe.json", {
        "meta": {"purpose": "Why the page-level score fallback does or does not find scores, per week page.",
                 "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat()},
        "weeks": fallback_probe,
    })
    # Any past game whose by-week row carries no score is re-read from the game's own official page.
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    gaps = [r for r in all_rows if r["awayPoints"] is None and (r.get("dateUTC") or "9999") < today]
    filled = 0
    gap_context = {}
    for r in gaps[:140]:
        wk_page = get(r.get("listUrl") or "")
        slug = (r["sourceUrl"] or "").rsplit("/", 1)[-1]
        forms = {}
        if wk_page:
            un = html_lib.unescape(wk_page)
            for vname, vtext in (("raw", wk_page), ("unescaped", un), ("dequoted", un.replace('\\"', '"'))):
                forms[vname] = {
                    "slugPresent": slug in vtext,
                    "scoreLabelNear": bool(SCORE_TEXT_RE.search(strip_tags(vtext))) and slug in vtext,
                }
        gap_context.setdefault(slug, {"forms": forms, "away": r.get("away"), "home": r.get("home")})
        if wk_page and r["sourceUrl"].rsplit("/", 1)[-1] in wk_page:
            slug = r["sourceUrl"].rsplit("/", 1)[-1]
            i = wk_page.find(slug)
            m = ANCHOR_RE.search(wk_page, max(0, i - 4000), i + 6000)
            gap_context[slug] = {
                "anchorFound": bool(m),
                "anchorText": strip_tags(m.group(2))[:200] if m else None,
                "raw": re.sub(r"\s+", " ", wk_page[max(0, i - 300):i + 900])[:1200],
            }
        gpage = get(r["sourceUrl"])
        if not gpage:
            continue
        a, h, st, how = game_page_scores(gpage, r["sourceUrl"], r.get("away") or "", r.get("home") or "")
        if a is None or h is None:
            continue
        r["awayPoints"], r["homePoints"] = a, h
        r["scoreSource"] = how
        if st:
            r["status"] = st
        r["winner"] = "away" if a > h else ("home" if h > a else "tie")
        r["verification"] = "verified"
        filled += 1
    log(f"score gap fill: {filled}/{len(gaps)} past games recovered from their own game page")
    jwrite("gap-context.json", {
        "meta": {"purpose": "Exact official markup around each game whose score could not be bound, so the "
                             "parser is fixed against evidence rather than assumption.",
                 "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat()},
        "samples": gap_context,
    })
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

    label_pages = [get(INJURY_URL), get(INACTIVE_URL)]
    slug_to_label: dict[str, str] = {}
    for lp in label_pages:
        if lp:
            for k, v in club_labels(lp).items():
                slug_to_label.setdefault(k, v)
    for t in teams_found.values():
        for slug, label in slug_to_label.items():
            if label.lower().split()[-1] == t["fullName"].lower().split()[-1]:
                t["slug"] = slug
                break
    jwrite("teams-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} club registry (official club list embedded on the by-week pages)",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "clubs": len(teams_found),
            "clubLabelsOnInjuryPage": len(slug_to_label),
            "sourcePages": [f"{SCHEDULE_BASE}week-{w}" for w in WEEKS[:1]],
            "usedFor": "Joining the injury-report page's /teams/<slug> context to a club name; the join key is "
                       "the league's own slug, and a club that cannot be matched stays null.",
        },
        "clubs": sorted(teams_found.values(), key=lambda t: t["fullName"]),
    })
    by_slug = {t["slug"]: t for t in teams_found.values() if t.get("slug")}
    by_abbr = {t["abbreviation"]: t for t in teams_found.values() if t.get("abbreviation")}

    # 3 — weekly official injury reports ---------------------------------------
    inj_rows: list[dict] = []
    inj_counts: dict[str, int] = {}
    # The official page ignores ?season/&week in the server-rendered markup (verified: identical
    # tables for weeks 9, 10 and 11), so only the landing page is requested and labelled "current".
    inj_week_params = [""]
    t_labels_url = "https://www.nfl.com/injuries/ (club link rendered above each team table)"
    inj_shapes: dict[str, dict] = {}
    for i, param in enumerate(inj_week_params):
        url = INJURY_URL + param
        page = get(url)
        label = "current" if not param else param.split("week=")[1]
        if page is None:
            inj_counts[label] = -1
            continue
        tables = parse_tables(page, url)
        rows = table_rows_to_injuries(tables, label)
        for r in rows:
            club = by_slug.get(r["clubSlug"])
            r["team"] = club["fullName"] if club else (r.get("clubLabel") or None)
            r["teamAbbr"] = club["abbreviation"] if club else None
            r["teamJoinSource"] = club["sourceUrl"] if club else t_labels_url
        inj_counts[label] = len(rows)
        inj_shapes[label] = {
            "tables": len(tables),
            "tableHeadings": [t["heading"] for t in tables][:40],
            "headers": [t["headers"] for t in tables[:3]],
            "rowCounts": [t["rawRowCount"] for t in tables][:40],
        }
        inj_rows.extend(rows)
        log(f"injuries {label}: {len(rows)} rows from {len(tables)} tables")
    jwrite("injuries-2026.json", {
        "meta": {
            "dataset": f"NFL {SEASON} official weekly injury report rows (nfl.com/injuries)",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(inj_rows),
            "perRequest": inj_counts,
            "pageShape": inj_shapes,
            "sourcePages": [INJURY_URL + p for p in inj_week_params],
            "sourceName": "NFL.com official injury report",
            "note": "Practice participation and game status are separate official fields; the page does not "
                    "publish depth-chart order, so backup tier is never inferred here.",
        },
        "rows": inj_rows,
    })

    # 3b — official weekly injury-report and game-day inactives ARTICLES ----------------
    art_rows, art_links, art_fail, art_ok, art_kinds = collect_articles([INJURY_URL, INACTIVE_URL])
    # Join each article section heading (e.g. "GIANTS", "NEW YORK GIANTS") to the official club list.
    # Unmatched headings stay null rather than being guessed.
    by_fullname = {t["fullName"]: t for t in teams_found.values()}
    by_nick = {}
    for t in teams_found.values():
        words = re.sub(r"[^A-Za-z ]", " ", t["fullName"]).split()
        by_nick.setdefault(words[-1].lower(), t)
        by_nick.setdefault(t["fullName"].lower(), t)
    for r in art_rows:
        sec = (r.get("section") or "").strip().lower()
        club = None
        if sec:
            if sec in by_nick:
                club = by_nick[sec]
            else:
                tail = [w for w in re.sub(r"[^a-z ]", " ", sec).split() if w]
                if tail:
                    club = by_nick.get(tail[-1])
        r["team"] = club["fullName"] if club else None
        r["teamAbbr"] = club["abbreviation"] if club else None
        r["teamJoin"] = "official club list" if club else None
        if not r["team"]:
            ctx = (r.get("context") or "")
            pos = ctx.find(r.get("player") or "\u0000")
            head = ctx[:pos] if pos > 0 else ctx
            for full, t2 in by_fullname.items():
                if full in head:
                    r["team"] = t2["fullName"]
                    r["teamAbbr"] = t2["abbreviation"]
                    r["teamJoin"] = "club named in the article sentence"
                    break
    jwrite("articles-2026.json", {
        "meta": {
            "dataset": "NFL.com official news articles for weekly injury reports and game-day inactives",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "rows": len(art_rows),
            "pagesParsed": art_ok,
            "linksDiscovered": art_links,
            "failures": art_fail,
            "rowsByKind": art_kinds,
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

    jwrite("source-registry.json", {
        "meta": {
            "purpose": "Audit trail of every official page this fetcher touched, with the HTTP result and "
                       "payload size, so each dataset can be traced back to a live official source.",
            "retrievedUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
            "requests": len(SOURCES),
            "failures": len([x for x in SOURCES if not x.get("ok")]),
        },
        "sources": SOURCES,
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
            "scoreLabelMismatches": [{k: r[k] for k in ("slug", "away", "home", "scoreMismatch")}
                                     for r in mismatch_rows[:20]],
            "gapContextSamples": len(gap_context),
            "gapFilledFromGamePages": filled,
            "pastGamesStillMissingScores": len([r for r in all_rows
                                                if r["awayPoints"] is None
                                                and (r.get("dateUTC") or "9999") < today]),
            "standingsRows": len(standing_rows),
            "injuryRows": len(inj_rows),
            "inactivesRows": len(ina_rows),
            "articleRows": len(art_rows),
            "articlePagesParsed": art_ok,
        },
        "extraction": {
            "gamesWithoutScores": len([r for r in all_rows if r["awayPoints"] is None]),
            "standingsWithoutPoints": len([r for r in standing_rows if r["pointsFor"] is None]),
            "injuriesWithoutTeam": len([r for r in inj_rows if not r["clubSlug"]]),
            "injuriesWithoutPosition": len([r for r in inj_rows if not r["position"]]),
            "injuryUniquePlayers": len({(r["player"], r["label"]) for r in inj_rows}),
            "articleSections": len({r.get("section") for r in art_rows if r.get("section")}),
        },
        "perWeek": per_week,
        "perWeekFinal": per_week_final,
        "injuryPerRequest": inj_counts,
        "standingsWeeks": sorted(standings_weeks_seen),
        "notes": notes[-30:],
    })
    log(f"wrote {OUT}: games={len(all_rows)} final={len(finals)} standings={len(standing_rows)} "
        f"injuries={len(inj_rows)} inactives={len(ina_rows)}")


def _entry():
    try:
        main()
    except Exception:  # noqa: BLE001 - surface the traceback as a committed artifact
        import traceback
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "error.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    _entry()
