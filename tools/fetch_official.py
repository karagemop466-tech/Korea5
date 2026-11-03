#!/usr/bin/env python3
"""Fetch official schedule/broadcast data for the Korea5 free-time planner.

Runs on GitHub Actions (runners have outbound internet). Every record written by
this script carries an official source URL. Nothing is invented: if a field is
absent from the official page it is left null/blank and reported in the fetch
report so it can be listed on the Flagged for Review page.

Outputs (committed by the workflow):
  official/nfl-2026.json         all NFL preseason + regular-season games, nfl.com
  official/westwoodone.json      Westwood One Sports national radio broadcasts
  official/w1-stations.json      Westwood One station-finder rows for San Francisco
  official/mlb-tbd.json          startTimeTBD flags from MLB StatsAPI
  official/fetch-report.json     counts, failures, retrieval time, source URLs
"""
import concurrent.futures
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

OUT = "official"
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; Korea5FreeTime/1.0; +official-source-verification)",
    "Accept-Language": "en-US,en;q=0.9",
}
PT = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

NFL_WEEK_SLUGS = (
    [("hall-of-fame-game", "Hall of Fame Game"), ("preseason-week-1", "Preseason Week 1"),
     ("preseason-week-2", "Preseason Week 2"), ("preseason-week-3", "Preseason Week 3")]
    + [(f"week-{i}", f"Week {i}") for i in range(1, 19)]
    + [("wild-card-weekend", "Wild Card Weekend"),
       ("divisional-playoffs", "Divisional Playoffs"),
       ("conference-championships", "Conference Championships"),
       ("super-bowl-sunday", "Super Bowl")]
)
NFL_BASE = "https://www.nfl.com/schedules/{season}/by-week/"
W1_PAGE_SIZE = 100
# A guard against an upstream pagination loop. Reaching it is a failure, not a
# reason to silently publish the first few pages as a complete schedule.
W1_MAX_PAGES = 20

W1_BASE = "https://www.westwoodonesports.com"
W1_WIDGETS = {
    "NFL": ("https://www.westwoodonesports.com/nfl-schedule/", 47029),
    "NCAA Football": ("https://www.westwoodonesports.com/ncaa-football/", 47030),
    "NCAA Basketball": ("https://www.westwoodonesports.com/ncaa-basketball/", 47031),
    "U.S. Soccer": ("https://www.westwoodonesports.com/us-soccer/", 47032),
    "Golf": ("https://www.westwoodonesports.com/golf/", 47033),
    "NCAA MCWS": ("https://www.westwoodonesports.com/ncaa-mcws/", 47420),
    "NCAA WCWS": ("https://www.westwoodonesports.com/ncaa-wcws/", 47419),
    "NCAA Lacrosse": ("https://www.westwoodonesports.com/ncaa-lacrosse/", 47418),
    "NCAA Hockey": ("https://www.westwoodonesports.com/ncaa-hockey/", 47044),
}


def get(url, tries=3, timeout=60):
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
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def pt_parts(utc_iso):
    """Convert an explicitly zoned ISO timestamp to Pacific date/time.

    A naive timestamp is not evidence of a UTC kickoff; do not silently assume
    its zone. ZoneInfo accounts for daylight saving and midnight crossings.
    """
    if not isinstance(utc_iso, str):
        raise ValueError("timestamp must be a string")
    d = dt.datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timestamp has no timezone")
    p = d.astimezone(PT)
    return p.date().isoformat(), p.strftime("%H:%M"), p.tzname()


# --------------------------------------------------------------------------- NFL
def extract_rsc_queries(page):
    """Yield dehydrated react-query objects from NFL.com RSC payloads."""
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
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "queryKey" in cur and "state" in cur:
                    yield cur
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def nfl_week_identity(slug):
    """The by-week slug's expected season type and week, not inferred games."""
    if slug == "hall-of-fame-game":
        return "PRE", 0
    m = re.fullmatch(r"preseason-week-(\d+)", slug)
    if m:
        return "PRE", int(m.group(1))
    m = re.fullmatch(r"week-(\d+)", slug)
    if m:
        return "REG", int(m.group(1))
    post = {"wild-card-weekend": 1, "divisional-playoffs": 2,
            "conference-championships": 3, "super-bowl-sunday": 4}
    if slug in post:
        return "POST", post[slug]
    raise ValueError(f"unrecognized NFL week slug: {slug}")


def fetch_nfl_week(item):
    """Read only the requested season/week from NFL.com's embedded query.

    NFL.com can return a different season or the current week when a URL is
    unavailable. Accepting that fallback would mislabel games, so both the query
    and each game must identify the requested season, type and week. An empty
    postseason query is allowed: future opponents may not yet be known.
    """
    if len(item) == 3:
        season, slug, label = item
    else:
        slug, label = item
        season = 2026
    season = int(season)
    season_type, week = nfl_week_identity(slug)
    url = NFL_BASE.format(season=season) + slug
    failures = []
    page = get(url)
    if page is None:
        return [], [f"{slug}: page fetch failed"], url
    games = []
    seen = set()
    found_query = False
    for q in extract_rsc_queries(page):
        key = q.get("queryKey") or []
        if not isinstance(key, list) or len(key) < 2 or key[0] != "useFetchFootballWeeklyGameDetails":
            continue
        params = key[1]
        if not isinstance(params, dict):
            continue
        if (str(params.get("season")) != str(season) or params.get("seasonType") != season_type
                or str(params.get("week")) != str(week)):
            continue
        data = (q.get("state") or {}).get("data")
        if not isinstance(data, list):
            continue
        found_query = True
        for g in data:
            if not isinstance(g, dict):
                failures.append(f"{slug}: malformed game record")
                continue
            gid = g.get("id")
            if not gid:
                failures.append(f"{slug}: game without id")
                continue
            if (str(g.get("season")) != str(season) or g.get("seasonType") != season_type
                    or str(g.get("week")) != str(week)):
                failures.append(f"{slug}/{gid}: game season/week does not match the requested page")
                continue
            if gid in seen:
                continue
            seen.add(gid)
            slugs = [x.get("id") for x in (g.get("externalIds") or [])
                     if isinstance(x, dict) and x.get("source") == "slug"
                     and isinstance(x.get("id"), str) and re.fullmatch(r"[a-z0-9-]+", x["id"])]
            game_url = ("https://www.nfl.com/games/" + slugs[0]) if slugs else url
            raw_time = g.get("time")
            date_pt = start_pt = timezone = None
            if raw_time:
                try:
                    date_pt, start_pt, timezone = pt_parts(raw_time)
                except (ValueError, TypeError, OverflowError) as e:
                    failures.append(f"{slug}/{gid}: invalid or unzoned time {raw_time!r}: {e}")
            valid_time = start_pt is not None
            audio = ((g.get("broadcastInfo") or {}).get("audioNetworks") or [])
            w1 = any("WESTWOOD_ONE" in str(a.get("audience", "")) for a in audio if isinstance(a, dict))
            away = (g.get("awayTeam") or {}).get("fullName")
            home = (g.get("homeTeam") or {}).get("fullName")
            games.append({
                "id": f"nfl-{season}-{gid}",
                "league": "NFL",
                "season": season,
                "seasonType": g.get("seasonType"),
                "week": g.get("week"),
                "weekType": g.get("weekType"),
                "weekLabel": label,
                "category": g.get("category"),
                "away": away,
                "home": home,
                "title": (f"{away} at {home}" if away and home else None),
                "venue": (g.get("venue") or {}).get("name"),
                "status": g.get("status"),
                "startUTC": raw_time if valid_time else None,
                "datePT": date_pt,
                "startPT": start_pt,
                "timezone": timezone,
                "nationalRadio": "Westwood One Sports (national)" if w1 else None,
                "audioNetworks": [a.get("audience") for a in audio if isinstance(a, dict)],
                "tv": (g.get("broadcastInfo") or {}).get("homeNetworkChannels"),
                "priority": "high" if (w1 or "49ers" in (str(away) + str(home))) else "normal",
                "sourceUrl": game_url,
                "sourceName": "NFL.com official schedule/game page",
                "verification": "verified" if valid_time else "unverified-no-time",
                "timeStatus": "verified" if valid_time else "unverified",
            })
    if not found_query:
        failures.append(f"{slug}: no matching {season}/{season_type}/week-{week} query found")
    elif not games and season_type != "POST":
        failures.append(f"{slug}: matching schedule query was empty")
    return games, failures, url


# ------------------------------------------------------------------ Westwood One
def w1_grid_url(widget_id, rng, offset):
    q = urllib.parse.urlencode({
        "id": widget_id, "range": rng, "offset": offset, "limit": 100,
        "timezone": "America/New_York", "widgetTitle": "Event Display",
    })
    return f"{W1_BASE}/more/eventGrid/?{q}"


class W1GridParser(HTMLParser):
    """Parse the requested grid only, excluding unrelated sidebar event widgets."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.root_depth = None
        self.found_root = False
        self.event_depth = None
        self.field_depth = None
        self.field = None
        self.fragments = []
        self.current = None
        self.events = []
        self.malformed = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "div":
            self.depth += 1
            if attrs.get("id") == "eventCalendar_more":
                self.root_depth = self.depth
                self.found_root = True
            elif self.root_depth is not None and self.current is None and "event" in classes:
                self.event_depth = self.depth
                self.current = {"eventId": None, "title": None, "venue": None,
                                "description": None, "monthDay": None}
            elif self.current is not None and self.field is None:
                fields = {"name": "title", "venue": "venue", "description": "description", "date": "monthDay"}
                self.field = next((value for key, value in fields.items() if key in classes), None)
                if self.field:
                    self.field_depth = self.depth
                    self.fragments = []
        if tag == "a" and self.current is not None and not self.current["eventId"]:
            m = re.search(r"/events/(\d+)(?:/|$|\?)", attrs.get("href") or "")
            if m:
                self.current["eventId"] = m.group(1)

    def handle_data(self, text):
        if self.field is not None:
            self.fragments.append(text)

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self.field is not None and self.depth == self.field_depth:
            self.current[self.field] = "".join(self.fragments).strip() or None
            self.field = None
            self.field_depth = None
            self.fragments = []
        if self.current is not None and self.depth == self.event_depth:
            if self.current["eventId"]:
                self.events.append(self.current)
            else:
                self.malformed += 1
            self.current = None
            self.event_depth = None
        if self.depth == self.root_depth:
            self.root_depth = None
        self.depth -= 1


def parse_w1_grid_checked(page):
    parser = W1GridParser()
    parser.feed(page)
    if not parser.found_root:
        return [], "expected eventCalendar_more grid missing"
    if parser.root_depth is not None or parser.malformed:
        return parser.events, f"incomplete grid or {parser.malformed} events without identifiers"
    return parser.events, None


def parse_w1_grid(page):
    """Return event stubs; acquisition uses the checked variant above."""
    return parse_w1_grid_checked(page)[0]


class W1TimeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.times = {"start_time": [], "end_time": []}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in self.times:
            if name in (attrs.get("class") or "").split():
                self.times[name].append(attrs.get("data-time"))


def parse_w1_detail(event_id, category, stub, page):
    rec = {
        "id": "w1-" + event_id,
        "league": "Westwood One Sports",
        "sport": category,
        "priority": "high",
        "tags": ["westwoodone", "national-radio"],
        "title": stub.get("title"),
        "venue": stub.get("venue"),
        "description": stub.get("description"),
        "monthDay": stub.get("monthDay"),
        "sourceUrl": f"{W1_BASE}/events/{event_id}/",
        "sourceName": "Westwood One Sports official event page",
        "startUTC": None, "endUTC": None, "datePT": None, "startPT": None,
        "endPT": None, "timezone": None, "durationMin": None,
        "timeStatus": "unverified", "endStatus": "unverified",
        "verification": "unverified-no-time", "parseErrors": [],
    }
    if page is None:
        rec["verification"] = "unverified-page-fetch"
        rec["parseErrors"].append("event page fetch failed")
        return rec
    times = W1TimeParser()
    times.feed(page)
    ld = re.search(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S)
    if ld:
        try:
            obj = json.loads(html.unescape(ld.group(1)))
            if isinstance(obj, dict):
                rec["title"] = rec["title"] or obj.get("name")
                rec["description"] = rec["description"] or obj.get("description")
                if not rec["venue"]:
                    loc = obj.get("location") or {}
                    rec["venue"] = loc.get("name") if isinstance(loc, dict) else None
        except (ValueError, TypeError):
            pass

    def timestamp(name):
        values = times.times[name]
        if len(values) > 1:
            rec["parseErrors"].append(f"multiple {name} attributes")
            return None
        if not values:
            return None
        raw = values[0]
        if not raw or not raw.isdigit():
            rec["parseErrors"].append(f"invalid {name} attribute")
            return None
        try:
            return dt.datetime.fromtimestamp(int(raw), UTC)
        except (ValueError, OverflowError, OSError):
            rec["parseErrors"].append(f"invalid {name} epoch")
            return None

    start = timestamp("start_time")
    end = timestamp("end_time")
    if start:
        p = start.astimezone(PT)
        rec.update({"startUTC": start.isoformat().replace("+00:00", "Z"),
                    "datePT": p.date().isoformat(), "startPT": p.strftime("%H:%M"),
                    "timezone": p.tzname(), "timeStatus": "verified"})
    if end and start and end <= start:
        rec["parseErrors"].append("listed end is not after start")
        end = None
    if end:
        rec["endUTC"] = end.isoformat().replace("+00:00", "Z")
        rec["endPT"] = end.astimezone(PT).strftime("%H:%M")
        rec["endStatus"] = "published-event-end"
        if start:
            rec["durationMin"] = int((end - start).total_seconds() // 60)
    if start and end and not rec["parseErrors"]:
        rec["verification"] = "verified"
    elif start:
        rec["verification"] = "unverified-no-end"
    return rec


def fetch_w1():
    stubs = {}
    grid_sources = []
    failures = []
    for category, (_page_url, wid) in W1_WIDGETS.items():
        for rng in ("current", "past"):
            for number in range(W1_MAX_PAGES):
                offset = number * W1_PAGE_SIZE
                u = w1_grid_url(wid, rng, offset)
                page = get(u)
                grid_sources.append(u)
                if page is None:
                    failures.append(f"W1 {category}/{rng}/{offset}: grid fetch failed")
                    break
                rows, error = parse_w1_grid_checked(page)
                if error:
                    failures.append(f"W1 {category}/{rng}/{offset}: {error}")
                    break
                for r in rows:
                    stubs.setdefault(r["eventId"], dict(r, category=category, widgetId=wid))
                if len(rows) < W1_PAGE_SIZE:
                    break
                if number == W1_MAX_PAGES - 1:
                    failures.append(f"W1 {category}/{rng}: pagination limit reached; results may be truncated")
                time.sleep(0.15)

    def one(item):
        eid, stub = item
        page = get(f"{W1_BASE}/events/{eid}/", tries=2, timeout=45)
        return parse_w1_detail(eid, stub["category"], stub, page)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        events = list(ex.map(one, stubs.items()))
    for event in events:
        for error in event["parseErrors"]:
            failures.append(f"W1 {event['id']}: {error}")
    if not stubs:
        failures.append("W1: all schedule grids were empty; cannot validate the refresh")
    elif not any(e.get("startUTC") for e in events):
        failures.append("W1: no event detail contained a usable start time")
    events.sort(key=lambda e: (e.get("startUTC") or "9999", e["id"]))
    return events, grid_sources, failures


# ------------------------------------------------------------------ W1 stations
class W1StationParser(HTMLParser):
    """Keep each sport's own station list and its original season caption."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.panel_depth = None
        self.panel = None
        self.panels = []
        self.capture = None
        self.fragments = []
        self.cells = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "div":
            self.depth += 1
            if "vc_tta-panel" in classes and self.panel is None:
                self.panel_depth = self.depth
                self.panel = {"sport": None, "caption": None, "rows": []}
        if self.panel is None:
            return
        if tag == "span" and "vc_tta-title-text" in classes and self.panel["sport"] is None:
            self.capture, self.fragments = "title", []
        elif tag == "caption":
            self.capture, self.fragments = "caption", []
        elif tag == "tr":
            self.cells = []
        elif tag == "td" and self.cells is not None:
            self.capture, self.fragments = "cell", []

    def handle_data(self, text):
        if self.capture:
            self.fragments.append(text)

    def handle_endtag(self, tag):
        if self.panel is not None:
            if tag == "span" and self.capture == "title":
                self.panel["sport"] = "".join(self.fragments).strip() or None
                self.capture = None
            elif tag == "caption" and self.capture == "caption":
                self.panel["caption"] = "".join(self.fragments).strip() or None
                self.capture = None
            elif tag == "td" and self.capture == "cell":
                self.cells.append("".join(self.fragments).strip())
                self.capture = None
            elif tag == "tr" and self.cells is not None:
                if len(self.cells) == 2:
                    self.panel["rows"].append(self.cells)
                self.cells = None
            if tag == "div" and self.depth == self.panel_depth:
                self.panels.append(self.panel)
                self.panel = None
                self.panel_depth = None
        if tag == "div":
            self.depth -= 1


def parse_w1_stations(page):
    url = W1_BASE + "/station-finder/"
    pack = {
        "sourceUrl": url,
        "sourceName": "Westwood One Sports official Station Finder",
        "market": "San Francisco, CA",
        "note": "The source lists affiliates by sport and season, not individual games or frequencies. "
                "Blackouts and conflicts may prevent carriage; reception in Outer Sunset 94122 is unverified. "
                "Digital secondary channels must not be assumed receivable on a standard analog radio.",
        "affiliates": [], "sportLists": [], "parseErrors": [],
    }
    if not page:
        pack["parseErrors"].append("station-finder page fetch failed")
        return pack
    parser = W1StationParser()
    parser.feed(page)
    if not parser.panels or parser.panel is not None:
        pack["parseErrors"].append("station-finder sport panels missing or incomplete")
        return pack
    affiliates = {}
    for panel in parser.panels:
        sport = panel["sport"]
        if not sport:
            pack["parseErrors"].append("station-finder panel without a sport title")
            continue
        calls = set()
        for cells in panel["rows"]:
            # Some tables label their columns in the opposite order.
            for city, call in (cells, cells[::-1]):
                if city.strip() == "San Francisco, CA" and re.fullmatch(r"[A-Z0-9]+-(?:AM|FM|F\d+)", call.strip()):
                    calls.add(call.strip())
        listing = {"sport": sport, "caption": panel["caption"], "callLetters": sorted(calls), "sourceUrl": url}
        pack["sportLists"].append(listing)
        for call in calls:
            station = affiliates.setdefault(call, {"market": "San Francisco, CA", "callLetters": call,
                                                   "listings": [], "analogReception": "unverified"})
            station["listings"].append({"sport": sport, "caption": panel["caption"]})
            if re.search(r"-F\d+$", call):
                station["receiverNote"] = "Secondary-channel notation; standard analog reception is not established."
    pack["affiliates"] = sorted(affiliates.values(), key=lambda r: r["callLetters"])
    if not pack["affiliates"]:
        pack["parseErrors"].append("no San Francisco affiliates found; check source and market")
    return pack


def fetch_w1_stations():
    return parse_w1_stations(get(W1_BASE + "/station-finder/"))


# ------------------------------------------------------------------- MLB TBD flags
def fetch_mlb_tbd(years=(2026, 2027, 2028, 2029)):
    flags = {}
    sources = []
    failures = []
    fields = "dates,date,games,gamePk,gameDate,gameType,status,startTimeTBD,detailedState"
    for year in years:
        for m in range(2, 12):
            start = dt.date(year, m, 1)
            end = dt.date(year + (m // 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
            u = "https://statsapi.mlb.com/api/v1/schedule?" + urllib.parse.urlencode({
                "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
                "fields": fields,
            })
            sources.append(u)
            raw = get(u, tries=2)
            if raw is None:
                failures.append(f"MLB {year}-{m:02d}: fetch failed")
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError) as e:
                failures.append(f"MLB {year}-{m:02d}: JSON error {e}")
                continue
            if not isinstance(data, dict) or not isinstance(data.get("dates"), list):
                failures.append(f"MLB {year}-{m:02d}: response has no dates list")
                continue
            for d in data["dates"]:
                if not isinstance(d, dict) or not isinstance(d.get("games"), list):
                    failures.append(f"MLB {year}-{m:02d}: malformed date record")
                    continue
                for g in d["games"]:
                    if not isinstance(g, dict) or not g.get("gamePk"):
                        failures.append(f"MLB {year}-{m:02d}: game without id")
                        continue
                    status = g.get("status") if isinstance(g.get("status"), dict) else {}
                    tbd = status.get("startTimeTBD")
                    # Missing or malformed means unknown, never confirmed false.
                    if not isinstance(tbd, bool):
                        failures.append(f"MLB {year}-{m:02d}/{g['gamePk']}: startTimeTBD missing or invalid")
                        tbd = None
                    flags[str(g["gamePk"])] = {
                        "startTimeTBD": tbd,
                        "detailedState": status.get("detailedState"),
                        "gameDate": g.get("gameDate"),
                        "gameType": g.get("gameType"),
                    }
    return {
        "sourceUrl": "https://statsapi.mlb.com/api/v1/schedule",
        "sourceName": "MLB StatsAPI (official Major League Baseball data service)",
        "note": "startTimeTBD is MLB's own flag. True or missing does not confirm a first-pitch time; "
                "gameDate may be a placeholder. A missing flag causes the refresh to fail safely.",
        "sourceQueries": sources,
        "flags": flags,
    }, failures


def main():
    report = {
        "generatedUTC": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sources": {}, "failures": [], "warnings": [], "counts": {},
    }

    print("NFL 2026 by-week pages, including postseason ...")
    nfl = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for item, (games, fails, _url) in zip(NFL_WEEK_SLUGS, ex.map(fetch_nfl_week, NFL_WEEK_SLUGS)):
            nfl.extend(games)
            # Before the calendar year of the playoffs, an unpublished playoff
            # query is not evidence of an empty postseason. Preserve the warning.
            optional_post = nfl_week_identity(item[0])[0] == "POST" and dt.datetime.now(PT).date() < dt.date(2027, 1, 1)
            if fails and optional_post:
                report["warnings"].extend(f"Postseason unconfirmed: {failure}" for failure in fails)
            else:
                report["failures"].extend(fails)
    if not nfl:
        report["failures"].append("NFL: no games acquired")
    nfl.sort(key=lambda g: (g.get("startUTC") or "9999", g["id"]))
    nfl_payload = {
        "meta": {
            "sourceUrl": "https://www.nfl.com/schedules/2026/by-week/week-9",
            "sourceName": "NFL.com official 2026 schedule (by-week pages)",
            "sourcePages": [NFL_BASE.format(season=2026) + s for s, _ in NFL_WEEK_SLUGS],
            "retrievedUTC": report["generatedUTC"],
            "note": "Records come from matching NFL.com season/week queries. Pacific times are converted from "
                    "explicitly zoned timestamps. An empty or unavailable postseason query does not prove that "
                    "no game will be scheduled; see fetch-report.json and the official NFL pages.",
        },
        "games": nfl,
    }
    report["counts"]["nflGames"] = len(nfl)
    report["sources"]["nfl"] = "https://www.nfl.com/schedules/2026/by-week/week-9"

    print("Westwood One events ...")
    w1, grid_sources, w1_fail = fetch_w1()
    report["failures"].extend(w1_fail)
    w1_payload = {
        "meta": {
            "sourceUrl": "https://www.westwoodonesports.com/nfl-schedule/",
            "sourceName": "Westwood One Sports official schedule and event pages",
            "categoryPages": {k: v[0] for k, v in W1_WIDGETS.items()},
            "gridQueries": grid_sources,
            "retrievedUTC": report["generatedUTC"],
            "note": "The listed event start/end epochs are converted to UTC and Pacific; a listed end is not "
                    "proof of the actual broadcast end or a game's duration. Local AM/FM carriage is unverified "
                    "unless confirmed separately by an affiliate. All W1 events are treated as high priority.",
        },
        "events": w1,
    }
    report["counts"]["westwoodOneEvents"] = len(w1)
    report["sources"]["westwoodone"] = "https://www.westwoodonesports.com/nfl-schedule/"

    print("Westwood One station finder ...")
    stations = fetch_w1_stations()
    report["failures"].extend(f"W1 station finder: {error}" for error in stations["parseErrors"])
    report["counts"]["w1SfAffiliates"] = len(stations["affiliates"])

    print("MLB startTimeTBD flags ...")
    mlb_tbd, mlb_fail = fetch_mlb_tbd()
    report["failures"].extend(mlb_fail)
    if not mlb_tbd["flags"]:
        report["failures"].append("MLB: no flags acquired")
    report["counts"]["mlbTbdFlags"] = len(mlb_tbd["flags"])
    report["sources"]["mlb"] = "https://statsapi.mlb.com/api/v1/schedule"

    print(json.dumps(report, indent=2))
    if report["failures"]:
        print("Refresh incomplete: existing official snapshots were not replaced.", file=sys.stderr)
        return 1
    # Do not overwrite last-known-good snapshots until every required fetch and
    # parse has succeeded. The report retains optional postseason warnings.
    jwrite("nfl-2026.json", nfl_payload)
    jwrite("westwoodone.json", w1_payload)
    jwrite("w1-stations.json", stations)
    jwrite("mlb-tbd.json", mlb_tbd)
    jwrite("fetch-report.json", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
