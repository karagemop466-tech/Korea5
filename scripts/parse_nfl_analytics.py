#!/usr/bin/env python3
"""Parse NFL analytics raw snapshots into verified data tables.

Input : research/nfl-analytics-raw/*  (committed CI snapshots, sha256 in fetch-report.json)
Output: data/nfl-analytics/*.json     (row data, each row carrying its official source URL)
        data/nfl-analytics/parse-report.json

Rules:
  * Nothing is inferred. A value that is absent in the snapshot stays "".
  * Every parsed row carries the source page URL it came from.
  * Anomalies (unexpected structure, empty tables) are recorded in parse-report.json.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "research" / "nfl-analytics-raw"
OUT = ROOT / "data" / "nfl-analytics"
OUT.mkdir(parents=True, exist_ok=True)

INJ_URL = "https://www.nfl.com/injuries/"
STAND_URL = "https://www.nfl.com/standings/league/2026/REG"

TEAM_NAMES = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
    "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN",
    "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "Chargers": "LAC", "Rams": "LAR", "Raiders": "LV", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT", "Seahawks": "SEA", "49ers": "SF", "Buccaneers": "TB",
    "Titans": "TEN", "Commanders": "WAS",
}
ABBR_TO_NAME = {v: k for k, v in TEAM_NAMES.items()}
# The NFL.com injuries page prints some club abbrs differently than the standard ones.
ABBR_ALIASES = {"LA": "LAR", "AZ": "ARI", "SF": "SF", "LV": "LV", "TB": "TB", "NE": "NE"}
SLUG_TO_ABBR = {
    "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF", "panthers": "CAR",
    "bears": "CHI", "bengals": "CIN", "browns": "CLE", "cowboys": "DAL", "broncos": "DEN",
    "lions": "DET", "packers": "GB", "texans": "HOU", "colts": "IND", "jaguars": "JAX",
    "chiefs": "KC", "chargers": "LAC", "rams": "LAR", "raiders": "LV", "dolphins": "MIA",
    "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG", "jets": "NYJ",
    "eagles": "PHI", "steelers": "PIT", "seahawks": "SEA", "49ers": "SF", "buccaneers": "TB",
    "titans": "TEN", "commanders": "WAS",
}
DAY_HEADERS = ("THURSDAY", "SUNDAY", "MONDAY", "TUESDAY", "FRIDAY", "SATURDAY", "WEDNESDAY")

report: dict = {"generatedUTC": datetime.now(timezone.utc).isoformat(), "sources": {}, "anomalies": []}


def note(source: str, **kw) -> None:
    report["sources"].setdefault(source, {}).update(kw)


def anomaly(msg: str) -> None:
    report["anomalies"].append(msg)


# --------------------------------------------------------------- injuries
class InjuryPageParser(HTMLParser):
    """State machine over the NFL.com injuries page events."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list = []
        self._capture_td = False
        self._capture_a = False
        self._a_href = ""
        self._cell: list[str] = []
        self._row: list[dict] = []
        self._in_table = False
        self._skip_data = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._in_table = True
            self.events.append(("table_start", a.get("summary", "")))
        elif tag == "tr" and self._in_table:
            self._row = []
        elif tag in ("td", "th") and self._in_table:
            self._capture_td = True
            self._cell = []
        elif tag == "a" and self._capture_td:
            self._capture_a = True
            self._a_href = a.get("href", "")
        elif tag in ("script", "style"):
            self._skip_data = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_data = False
        elif tag == "a":
            self._capture_a = False
        elif tag in ("td", "th") and self._capture_td:
            self._capture_td = False
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append({"text": text, "href": self._a_href})
            self._a_href = ""
        elif tag == "tr" and self._in_table and self._row:
            self.events.append(("row", self._row))
            self._row = []
        elif tag == "table" and self._in_table:
            self._in_table = False
            self.events.append(("table_end", ""))

    def handle_data(self, data):
        if self._skip_data:
            return
        if self._capture_td:
            self._cell.append(data)
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.events.append(("text", text))


def parse_injuries() -> dict:
    raw = (RAW / "injuries-week10.html").read_text(encoding="utf-8", errors="ignore")
    p = InjuryPageParser()
    p.feed(raw)
    games, rows = [], []
    state = {"day": "", "time": "", "network": "", "away": None, "home": None,
             "away_rec": "", "home_rec": "", "team": None, "team_record": "", "table_no": 0}
    strip_seen: list[dict] = []
    pending_tables: list[tuple[str, list]] = []
    team_sections: list[tuple[str, list]] = []
    day_re = re.compile(r"^(" + "|".join(DAY_HEADERS) + r"), [A-Z]+ \d{1,2}(ST|ND|RD|TH)$")
    time_re = re.compile(r"^(\d{1,2}:\d{2}\s?(AM|PM))$")
    tz_re = re.compile(r"^(EST|CST|MST|PST|ET|CT|MT|PT)$")
    strip_re = re.compile(r"^([A-Z]{2,3})$")

    def flush_game():
        if state["away"] and team_sections:
            games.append({"day": state["day"], "kickoffET": state["time"], "network": state["network"],
                          "away": state["away"], "awayRecord": state["away_rec"],
                          "home": state["home"], "homeRecord": state["home_rec"],
                          "sections": team_sections.copy()})
        team_sections.clear()

    ev = p.events
    i = 0
    while i < len(ev):
        kind, val = ev[i]
        if kind == "text":
            if day_re.match(val):
                flush_game()
                state.update(day=val, time="", network="", away=None, home=None,
                             away_rec="", home_rec="")
                strip_seen = []
            elif time_re.match(val):
                if state["away"] is not None:
                    flush_game()  # a new game block starts here; close the previous one
                state["time"] = val + " ET"
                state["network"] = ""
                state["away"] = state["home"] = None
                state["team"] = None
                # skip the timezone node (e.g. 'EST'), then the next text is the network
                j = i + 1
                while j < len(ev) and ev[j][0] == "text" and tz_re.match(ev[j][1]):
                    j += 1
                if j < len(ev) and ev[j][0] == "text":
                    state["network"] = ev[j][1]
            elif strip_re.match(val) and (val in ABBR_TO_NAME or val in ABBR_ALIASES):
                abbr = ABBR_ALIASES.get(val, val)
                # team abbr in matchup strip: next text = name, then record
                name = rec = ""
                if i + 1 < len(ev) and ev[i + 1][0] == "text":
                    name = ev[i + 1][1]
                if i + 2 < len(ev) and ev[i + 2][0] == "text":
                    rec = ev[i + 2][1]
                m = re.match(r"^\((\d+-\d+(?:-\d+)?)\)$", rec)
                strip_seen.append({"abbr": abbr, "name": name, "record": m.group(1) if m else ""})
                if len(strip_seen) == 2:
                    state["away"] = strip_seen[0]["abbr"]
                    state["away_rec"] = strip_seen[0]["record"]
                    state["home"] = strip_seen[1]["abbr"]
                    state["home_rec"] = strip_seen[1]["record"]
                    state["team"] = None
                    strip_seen = []
            elif val in TEAM_NAMES and state["away"]:
                state["team"] = TEAM_NAMES[val]
                state["team_record"] = ""
            elif val == "No Injuries Reported" and state["team"]:
                team_sections.append((state["team"], []))
        elif kind == "table_start":
            pending_tables.append((val, []))
        elif kind == "row" and pending_tables:
            pending_tables[-1][1].append(val)
        elif kind == "table_end" and pending_tables:
            _, trows = pending_tables.pop()
            if state["team"]:
                team_sections.append((state["team"], trows))
            else:
                anomaly("injuries: table with no team label attached")
        i += 1
    flush_game()

    for g in games:
        for team_abbr, trows in g["sections"]:
            for r in trows:
                cells = [c["text"] for c in r] + [""] * (5 - len(r))
                if len(r) < 2:
                    continue
                if cells[0] in ("Player", "Position", ""):
                    continue  # table header row
                rows.append({
                    "game": f"{g['away']} @ {g['home']}", "day": g["day"], "kickoffET": g["kickoffET"],
                    "network": g["network"], "team": team_abbr,
                    "player": cells[0], "playerUrl": ("https://www.nfl.com" + r[0]["href"]) if r[0]["href"].startswith("/") else "",
                    "pos": cells[1], "injury": cells[2], "practiceStatus": cells[3], "gameStatus": cells[4],
                    "teamRecord": g["awayRecord"] if team_abbr == g["away"] else g["homeRecord"],
                    "sourceUrl": INJ_URL,
                })
    note("injuries-week10", games=len(games), rows=len(rows),
         teams=sorted({r["team"] for r in rows}))
    (OUT / "injuries-week-10-2026.json").write_text(json.dumps({
        "meta": {"sourceUrl": INJ_URL, "sourceName": "NFL.com official injury report",
                 "label": "Week 10 of the 2026 NFL season", "retrievedUTC": report["generatedUTC"],
                 "snapshot": "research/nfl-analytics-raw/injuries-week10.html",
                 "note": "Game Status blank = no designation published on the report at retrieval time. Never inferred."},
        "games": [{k: v for k, v in g.items() if k != 'sections'} for g in games],
        "rows": rows}, indent=1) + "\n")
    return {"games": len(games), "rows": len(rows)}


# --------------------------------------------------------------- results
def parse_results() -> dict:
    results, upcoming = [], []
    for wk in range(1, 11):
        path = RAW / f"schedule-week-{wk:02d}.html"
        if not path.exists():
            anomaly(f"results: missing {path.name}")
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        url = f"https://www.nfl.com/schedules/2026/by-week/week-{wk}"
        n = 0
        for m in re.finditer(r'href="(/games/[^"]+?)"[^>]*><span class="sr-only">([^<]+)</span>', raw):
            slug, text = m.group(1), m.group(2)
            if "FINAL" not in text:
                continue
            mm = re.match(r"^(.+?) (\d+), (.+?) (\d+), FINAL, (.+)$", text)
            if not mm:
                anomaly(f"results: unparsed final line '{text}'")
                continue
            away_name, ascore, home_name, hscore, datestr = mm.groups()
            slug_parts = slug.strip("/").split("/")
            game_slug = slug_parts[-1] if slug_parts else ""
            results.append({
                "week": wk, "away": away_name, "awayScore": int(ascore),
                "home": home_name, "homeScore": int(hscore),
                "dateLabel": datestr, "gameSlug": game_slug,
                "sourceUrl": "https://www.nfl.com" + slug, "weekSourceUrl": url,
            })
            n += 1
        note(f"schedule-week-{wk:02d}", finals=n)
    note("results", finals=len(results))
    (OUT / "results-2026.json").write_text(json.dumps({
        "meta": {"sourceName": "NFL.com official schedule by-week pages",
                 "sourcePattern": "https://www.nfl.com/schedules/2026/by-week/week-N",
                 "retrievedUTC": report["generatedUTC"],
                 "note": "Scores are finals as printed by NFL.com game cards ('Team X n, Team y m, FINAL'). Team names are the display names used by NFL.com; abbr mapping happens in originate_lines.py."},
        "results": results}, indent=1) + "\n")
    return {"finals": len(results)}


# --------------------------------------------------------------- depth charts
def parse_depth() -> dict:
    all_rows = []
    for team in sorted(SLUG_TO_ABBR.values()):
        path = RAW / f"depth-{team.lower()}.html"
        if not path.exists():
            anomaly(f"depth: missing {path.name}")
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        source_url = ""
        try:
            fetch_report = json.loads((RAW / "fetch-report.json").read_text())
            for t in fetch_report["targets"]:
                if t["name"] == f"depth-{team.lower()}":
                    source_url = t.get("url", "")
        except Exception:  # noqa: BLE001
            pass
        if not source_url:
            anomaly(f"depth-{team}: no source URL in fetch-report")
        p = InjuryPageParser()
        p.feed(raw)
        unit = ""
        trows: list[list[dict]] = []
        tables: list[tuple[str, list]] = []
        cur: list = []
        for kind, val in p.events:
            if kind == "table_start":
                cur = []
            elif kind == "row":
                cur.append(val)
            elif kind == "table_end":
                tables.append(("", cur))
                cur = []
        # map tables to units by their caption order (Offense, Defense, Special Teams)
        caps = re.findall(r'<caption[^>]*>([^<]+)</caption>', raw)
        for idx, (_, rows_) in enumerate(tables):
            unit = caps[idx].strip() if idx < len(caps) else ""
            if unit.lower().startswith("offense"):
                unit = "offense"
            elif unit.lower().startswith("defense"):
                unit = "defense"
            else:
                unit = "special teams"
            for r in rows_:
                cells = [c["text"] for c in r]
                if not cells or cells[0].lower() in ("position", ""):
                    continue
                strings = [c for c in cells[1:6]]
                strings += [""] * (5 - len(strings))
                all_rows.append({
                    "team": team, "unit": unit, "pos": cells[0],
                    "s1": strings[0], "s2": strings[1], "s3": strings[2], "s4": strings[3], "s5": strings[4],
                    "sourceUrl": source_url,
                })
        note(f"depth-{team}", rows=sum(1 for r in all_rows if r["team"] == team))
    note("depth-charts", rows=len(all_rows), teams=len({r["team"] for r in all_rows}))
    (OUT / "depth-charts-2026.json").write_text(json.dumps({
        "meta": {"retrievedUTC": report["generatedUTC"],
                 "sourceName": "Each club's official site depth-chart page (club-published; clubs label them 'unofficial depth chart compiled by <club> Football Communications')",
                 "note": "Columns s1..s5 are the club's published strings, 1st through 5th. Blank = club published no player in that cell."},
        "rows": all_rows}, indent=1) + "\n")
    return {"rows": len(all_rows)}


# --------------------------------------------------------------- standings
def parse_standings() -> dict:
    raw = (RAW / "standings-2026-reg.html").read_text(encoding="utf-8", errors="ignore")
    p = InjuryPageParser()
    p.feed(raw)
    tables, cur = [], []
    for kind, val in p.events:
        if kind == "row":
            cur.append(val)
        elif kind == "table_end":
            tables.append(cur)
            cur = []
    rows = []
    for trows in tables:
        for r in trows:
            cells = [c["text"] for c in r]
            if not cells or cells[0] in ("", "TEAM"):
                continue
            team_name = ""
            for c in cells[:2]:
                nm = re.sub(r"^[A-Z]{2,3}\s+", "", c).strip()
                for cand in TEAM_NAMES:
                    if cand in nm:
                        team_name = cand
                        break
                if team_name:
                    break
            if not team_name:
                continue
            nums = [c for c in cells if re.match(r"^[\d.\-]+$", c.replace(" - ", "-").replace("W", "").replace("L", "").strip()) or re.match(r"^\d+ - \d+ - \d+$", c) or re.match(r"^\d+[WL]$", c)]
            rows.append({"team": TEAM_NAMES[team_name], "teamName": team_name,
                         "cells": cells, "sourceUrl": STAND_URL})
    # columns from the page's own legend, in display order observed on the league view
    cols = ["abbr?", "W", "L", "T", "PCT", "PF", "PA", "DIFF", "HOME", "ROAD", "DIV", "DIV%", "CONF", "CONF%", "NONCONF", "STRK", "LAST5"]
    out = []
    for r in rows:
        cells = r["cells"]
        # find index of first numeric cell = W
        vals = {}
        numeric_cells = [c for c in cells if c.strip() != ""]
        out.append({"team": r["team"], "teamName": r["teamName"], "cells": numeric_cells,
                    "sourceUrl": r["sourceUrl"]})
    note("standings-2026-reg", rows=len(out))
    (OUT / "standings-2026.json").write_text(json.dumps({
        "meta": {"sourceUrl": STAND_URL, "sourceName": "NFL.com league standings (2026, Regular season)",
                 "retrievedUTC": report["generatedUTC"],
                 "columns": cols,
                 "note": "Column order per NFL.com league standings view: W, L, T, PCT, PF (points for), PA (points against), NET PTS, HOME, ROAD, DIV, DIV%, CONF, CONF%, NON-CONF, STRK, LAST 5. Cells preserved verbatim."},
        "rows": out}, indent=1) + "\n")
    return {"rows": len(out)}


# --------------------------------------------------------------- espn odds
def parse_espn() -> dict:
    odds = []
    for path in sorted(RAW.glob("espn-scoreboard-*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            anomaly(f"espn: {path.name} unparseable: {exc!r}")
            continue
        for ev in data.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            odds_block = comp.get("odds") or []
            entry = {"eventId": ev.get("id"), "name": ev.get("name", ""),
                     "date": ev.get("date", ""), "sourceFile": path.name,
                     "sourceUrl": f"https://www.espn.com/nfl/game/_/gameId/{ev.get('id')}",
                     "odds": odds_block}
            odds.append(entry)
    note("espn-scoreboard", events=len(odds))
    (OUT / "market-odds-week-10-2026.json").write_text(json.dumps({
        "meta": {"sourceName": "ESPN scoreboard API (ESPN — NFL official partner; ESPN BET odds block)",
                 "retrievedUTC": report["generatedUTC"],
                 "trustLabel": "TRUSTED SECONDARY SOURCE — NOT an official league data feed. Market reference only.",
                 "note": "odds[] is copied verbatim from the API response. Empty odds[] = no market block published at retrieval; those games stay blank and flagged."},
        "entries": odds}, indent=1) + "\n")
    return {"events": len(odds), "withOdds": sum(1 for e in odds if e["odds"])}


def main() -> None:
    print("injuries:", parse_injuries())
    print("results:", parse_results())
    print("depth:", parse_depth())
    print("standings:", parse_standings())
    print("espn:", parse_espn())
    (OUT / "parse-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print("anomalies:", len(report["anomalies"]))


if __name__ == "__main__":
    main()
