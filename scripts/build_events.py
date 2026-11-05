#!/usr/bin/env python3
"""
Build the normalized event feed the website reads.

Layers
------
1. VERIFIED   – data straight from an official source (MLB StatsAPI; 49ers.com;
                gostanford.com; calbears.com; westwoodonesports.com).
2. ESTIMATED  – the official source has not published dates/times yet. We model the
                league's *structure* (when it has historically played) and label every
                row `estimated`. No matchups are invented: estimated rows are either
                real published fixtures with an estimated START TIME, or league-level
                broadcast windows / slate-days with opponents unknown.

Output: data/events-<year>.json  (2026, 2027, 2028, 2029)
"""
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

# ---------------------------------------------------------------- constants
DURATION = {
    "mlb": 165, "mlb-post": 195,
    "nfl": 185, "nfl-post": 195,
    "ncaaf": 200,
}
MLB_HIGH = {"San Francisco Giants", "Athletics", "Oakland Athletics"}
MLB_SOURCE = "https://statsapi.mlb.com/api/v1/schedule"

PLACEHOLDER_HOURS = set(range(0, 13))  # UTC hour that cannot be a real MLB first pitch

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def d(s):
    return date.fromisoformat(s)


def pt_of(utc_iso):
    """ISO UTC string -> aware datetime in Pacific."""
    try:
        return datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(PT)
    except Exception:
        return None


def hhmm(dt):
    return f"{dt.hour:02d}:{dt.minute:02d}"


def add_min(hhmm_str, minutes):
    h, m = map(int, hhmm_str.split(":"))
    total = h * 60 + m + minutes
    return f"{(total // 60) % 24:02d}:{total % 60:02d}", total // 1440


# ---------------------------------------------------------------- MLB
def is_placeholder(iso):
    dt = pt_of(iso)
    if dt is None:
        return True
    utc_dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return utc_dt.hour in PLACEHOLDER_HOURS or utc_dt.minute == 33


def learn_mlb_start_model(games_2026):
    """Modal Pacific start time per (home team, weekday) from the released 2026 season."""
    per_team = defaultdict(Counter)
    per_wd = defaultdict(Counter)
    for g in games_2026:
        if g["type"] != "R" or is_placeholder(g["utc"]):
            continue
        dt = pt_of(g["utc"])
        per_team[(g["home"], dt.weekday())][hhmm(dt)] += 1
        per_wd[dt.weekday()][hhmm(dt)] += 1
    team_model = {k: c.most_common(1)[0][0] for k, c in per_team.items()}
    wd_model = {k: c.most_common(1)[0][0] for k, c in per_wd.items()}
    wd_model[None] = Counter({v: n for v, n in Counter(
        t for c in per_wd.values() for t in c.elements()).items()}).most_common(1)[0][0]
    return team_model, wd_model


def mlb_events(year, raw, team_model, wd_model):
    out = []
    for g in raw["games"]:
        if g["type"] not in ("R", "F", "D", "L", "W", "A", "S"):
            continue
        dt = pt_of(g["utc"])
        if dt is None:
            continue
        placeholder = is_placeholder(g["utc"])
        post = g["type"] in ("F", "D", "L", "W")
        start = hhmm(dt)
        basis = "published by MLB StatsAPI"
        if placeholder:
            start = team_model.get((g["home"], dt.weekday())) or wd_model.get(dt.weekday()) or "19:05"
            basis = (f"MLB has published the {year} date and matchup but not the first-pitch time "
                     f"(the feed carries a TBD placeholder). Start estimated from the most common "
                     f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dt.weekday()]} home start time for "
                     f"{g['home']} in the released 2026 season.")
        dur = DURATION["mlb-post"] if post else DURATION["mlb"]
        label = f"{g['away']} at {g['home']}"
        if g["type"] == "A":
            label = f"MLB All-Star Game at {g['home']}"
        elif post:
            label = f"{g['typeLabel']}: {g['away']} at {g['home']}"
        out.append({
            "id": f"mlb-{year}-{g['id']}",
            "league": "MLB",
            "priority": "high" if (g["home"] in MLB_HIGH or g["away"] in MLB_HIGH) else "normal",
            "tags": (["mlb"] + (["mlb-giants"] if "Giants" in (g["home"] + g["away"]) else [])
                     + (["mlb-athletics"] if "Athletics" in (g["home"] + g["away"]) else [])),
            "date": dt.date().isoformat(),
            "start": start,
            "durationMin": dur,
            "title": label,
            "away": g["away"],
            "home": g["home"],
            "venue": g["venue"],
            "seasonType": ("postseason" if post else
                           {"S": "preseason", "A": "special", "R": "regular"}.get(g["type"], "other")),
            "timeStatus": "estimated" if placeholder else "verified",
            "timeBasis": basis,
            "status": "estimated" if placeholder else "verified",
            "dateStatus": "verified",
            "source": MLB_SOURCE,
            "sourceLabel": "MLB StatsAPI (official league data service)",
            "sourceUrl": f"https://www.mlb.com/schedule/{dt.date().isoformat()}",
        })
    return out


# ---------------------------------------------------------------- curated files
def curated_events():
    out = []
    p = "data/curated/nfl-2026-49ers.json"
    if os.path.exists(p):
        cur = json.load(open(p))
        when = {e["id"]: e for e in cur["events"]}
        for e in cur["events"]:
            if e.get("timeStatus") == "bye":
                continue
            if not e.get("date"):
                continue  # handled as a window below
            start = e.get("startPT")
            out.append({
                "id": e["id"], "league": "NFL", "priority": "high",
                "tags": ["nfl", "nfl-49ers"],
                "date": e["date"],
                "start": start,
                "durationMin": DURATION["nfl"],
                "title": (f"{e['opponent']} at San Francisco 49ers" if e.get("homeAway") == "home"
                          else f"San Francisco 49ers at {e['opponent']}" if e.get("homeAway") == "away"
                          else "San Francisco 49ers"),
                "teams": ["San Francisco 49ers", e.get("opponent")],
                "venue": e.get("venue"), "tv": e.get("tv"), "radio": e.get("radio", []),
                "seasonType": e.get("seasonType", "regular"), "week": e.get("week"),
                "timeStatus": ("verified" if e.get("timeStatus") == "verified" else
                               "not-published" if e.get("timeStatus") == "not-published" else "tba"),
                "status": "verified" if e.get("timeStatus") == "verified" else "verified-date-only",
                "result": e.get("result"), "note": e.get("note"),
                "source": "https://www.49ers.com/schedule/2026/",
                "sourceLabel": "49ers.com official schedule",
                "sourceUrl": "https://www.49ers.com/schedule/2026/",
                "verifyTokens": e.get("verifyTokens", []),
            })
        # Week 18 has no confirmed date: emit both candidate days
        w18 = when.get("nfl-2026-w18")
        if w18:
            for day in ("2027-01-09", "2027-01-10"):
                out.append({
                    "id": f"nfl-2026-w18-{day}", "league": "NFL", "priority": "high",
                    "tags": ["nfl", "nfl-49ers"], "date": day, "start": None,
                    "durationMin": DURATION["nfl"],
                    "title": "San Francisco 49ers at Arizona Cardinals (Week 18 — date not yet set by the NFL)",
                    "teams": ["San Francisco 49ers", "Arizona Cardinals"], "venue": w18.get("venue"),
                    "radio": w18.get("radio", []), "seasonType": "regular", "week": "W18",
                    "timeStatus": "tba", "startWindow": "12:00-23:30", "status": "unconfirmed-date",
                    "note": "49ers.com lists Week 18 as TBD. Both days of the league's final-weekend window are blocked.",
                    "source": "https://www.49ers.com/schedule/2026/",
                    "sourceLabel": "49ers.com official schedule",
                    "sourceUrl": "https://www.49ers.com/schedule/2026/",
                    "verifyTokens": ["WEEK 18", "Cardinals"],
                })

    p = "data/curated/westwoodone-2026.json"
    if os.path.exists(p):
        cur = json.load(open(p))
        for e in cur["events"]:
            start = None
            basis = None
            if e.get("startET"):
                h, m = map(int, e["startET"].split(":"))
                start = f"{(h - 3) % 24:02d}:{m:02d}"
                basis = "Westwood One publishes Eastern time; converted to Pacific at ET-3h (PST)."
            ncaa = e["id"].endswith("ncaa")
            out.append({
                "id": e["id"], "league": "NCAAF" if ncaa else "NFL",
                "priority": "normal" if ncaa else "high",
                "tags": ["westwoodone"] + (["ncaaf"] if ncaa else ["nfl"]),
                "date": e["date"], "start": start,
                "durationMin": DURATION["ncaaf"] if ncaa else DURATION["nfl"],
                "title": (f"{e['away']} at {e['home']}" if e.get("away") and e.get("home")
                          else f"{e['label']} — participants TBA"),
                "away": e.get("away"), "home": e.get("home"), "venue": e.get("venue"),
                "nationalRadio": "Westwood One Sports (national)",
                "seasonType": "regular", "label": e.get("label"),
                "timeStatus": "verified" if start else "unverified",
                "timeBasis": basis, "status": "verified" if start else "unverified",
                "conflict": e.get("conflict"), "note": e.get("note"),
                "source": "https://www.westwoodonesports.com/nfl-schedule/",
                "sourceLabel": "Westwood One Sports official NFL schedule",
                "sourceUrl": e.get("eventUrl"),
                "verifyTokens": e.get("verifyTokens", []),
            })

    p = "data/curated/ncaaf-2026.json"
    if os.path.exists(p):
        cur = json.load(open(p))
        for e in cur["events"]:
            out.append({
                "id": e["id"], "league": "NCAAF",
                "priority": "high",
                "tags": ["ncaaf", "ncaaf-stanford" if e["team"] == "Stanford" else "ncaaf-cal"],
                "date": e["date"], "start": e.get("startPT"),
                "startWindow": e.get("startWindow"),
                "durationMin": DURATION["ncaaf"],
                "title": (f"{e['team']} {'vs' if e.get('homeAway') == 'home' else 'at'} "
                          f"{e['opponent'] or 'opponent TBD'}"
                          + (f" — {e['gameName']}" if e.get("gameName") else "")),
                "team": e["team"], "opponent": e.get("opponent"), "venue": e.get("venue"),
                "radio": e.get("radio", []), "seasonType": "regular",
                "timeStatus": ("verified" if e.get("timeStatus") == "verified" else "tba"),
                "startWindow": e.get("startWindow") or (None if e.get("startPT") else "12:00-23:30"),
                "status": ("verified" if e.get("timeStatus") == "verified" else "date-only"),
                "result": e.get("result"), "conflict": e.get("conflict"), "note": e.get("note"),
                "source": e["source"],
                "sourceLabel": "Official school athletics site",
                "sourceUrl": e["source"],
                "verifyTokens": e.get("verifyTokens", []),
            })
    return out


# ---------------------------------------------------------------- upstream NFL feed
def nfl_2026_full():
    """Every 2026 NFL game, from the NFL.com by-week pages.

    This feed is produced by the repo's parallel data pipeline (`data/upstream/nfl-2026.json`,
    fetched from nfl.com/schedules by-week pages). 49ers rows are skipped here because the
    club's own page already supplies them with radio affiliates.
    """
    p = "data/upstream/nfl-2026.json"
    if not os.path.exists(p):
        return []
    d = json.load(open(p))
    out = []
    for g in d.get("games", []):
        teams = f"{g.get('away') or ''} {g.get('home') or ''}"
        if "49ers" in teams:
            continue
        if not g.get("datePT"):
            continue
        season = {"PRE": "preseason", "REG": "regular", "POST": "postseason"}.get(g.get("seasonType"), "regular")
        tv = g.get("tv") or []
        out.append({
            "id": f"nfl2026-{g['id']}",
            "league": "NFL",
            "priority": "high",
            "tags": ["nfl"] + (["westwoodone"] if g.get("nationalRadio") else []),
            "date": g["datePT"],
            "start": g.get("startPT"),
            "durationMin": DURATION["nfl"],
            "title": f"{g.get('away')} at {g.get('home')}",
            "away": g.get("away"), "home": g.get("home"),
            "venue": g.get("venue"),
            "tv": ", ".join(tv) if tv else None,
            "nationalRadio": g.get("nationalRadio"),
            "seasonType": season,
            "week": g.get("weekLabel") or (f"W{g.get('week')}" if g.get("week") else None),
            "timeStatus": g.get("timeStatus", "verified"),
            "status": "verified" if g.get("verification") == "verified" else "unconfirmed",
            "dateStatus": "verified",
            "source": g.get("sourceName") or "NFL.com official schedule",
            "sourceLabel": "NFL.com game page",
            "sourceUrl": g.get("sourceUrl") or "https://www.nfl.com/schedules/2026/",
        })
    return out


# ---------------------------------------------------------------- de-duplication
def fold_westwoodone(by_year):
    """One row per game.

    Westwood One publishes the start of its *broadcast*, which runs 15-75 minutes before
    kickoff. Rather than showing the same game twice with two different times, the network
    row is folded into the game row: the broadcast start becomes the row's start (that is
    when the radio is busy) and the official kickoff is kept alongside it.
    """
    for y, evs in list(by_year.items()):
        index = {}
        for e in evs:
            if e["league"] == "NFL" and " at " in (e.get("title") or ""):
                a, h = e["title"].split(" at ", 1)
                index[(e["date"], frozenset([a, h]))] = e
        drop = []
        for e in evs:
            if "westwoodone" not in e.get("tags", []) or not e.get("away") or not e.get("home"):
                continue
            tgt = index.get((e["date"], frozenset([e["away"], e["home"]])))
            if not tgt or tgt is e:
                continue
            tgt["nationalRadio"] = "Westwood One Sports (national)"
            tgt["westwoodOneStart"] = e.get("start")
            tgt["westwoodOneUrl"] = e.get("sourceUrl")
            if e.get("start") and (not tgt.get("start") or e["start"] < tgt["start"]):
                tgt["kickoff"] = tgt.get("start")
                tgt["start"] = e["start"]
            if tgt.get("kickoff"):
                tgt["note"] = (f"On air from {tgt['start']} PT (Westwood One pre-game show); "
                               f"kickoff {tgt['kickoff']} PT per the NFL schedule.")
            if "westwoodone" not in tgt.setdefault("tags", []):
                tgt["tags"].append("westwoodone")
            drop.append(e)
        for d in drop:
            evs.remove(d)


# ---------------------------------------------------------------- estimates
NFL_WINDOWS = [  # (suffix, weekday, startPT, minutes, label)
    ("sun-early", 6, "10:00", 210, "NFL Sunday early window"),
    ("sun-late", 6, "13:05", 210, "NFL Sunday late window"),
    ("snf", 6, "17:20", 195, "Sunday Night Football"),
    ("mnf", 0, "17:15", 195, "Monday Night Football"),
    ("tnf", 3, "17:15", 195, "Thursday Night Football"),
]


def nth_weekday(year, month, weekday, n):
    """n-th (1-based) weekday of month."""
    day = date(year, month, 1)
    shift = (weekday - day.weekday()) % 7
    return day + timedelta(days=shift + 7 * (n - 1))


def nfl_calendar(year):
    """Estimated NFL structure. Basis: the league's published 2026 schedule and its
    long-standing structural rules (18-week season, Kickoff Thursday after Labor Day,
    Super Bowl on the second Sunday of February)."""
    labor_day = nth_weekday(year, 9, 0, 1)
    kickoff = labor_day + timedelta(days=3)
    rows = []
    # preseason: three weeks of Thursday-Saturday games in August before kickoff
    for w in range(3, 0, -1):
        wk_start = kickoff - timedelta(days=7 * (w + 1))
        for wd, tag in ((3, "thu"), (5, "sat"), (6, "sun")):
            day = wk_start + timedelta(days=(wd - wk_start.weekday()) % 7)
            rows.append({
                "id": f"nfl-est-{year}-pre{w}-{tag}", "league": "NFL", "priority": "normal",
                "tags": ["nfl", "nfl-49ers", "estimate"], "date": day.isoformat(), "start": "17:00",
                "durationMin": DURATION["nfl"],
                "title": f"Preseason week {4 - w} games (matchups TBD)",
                "seasonType": "preseason", "timeStatus": "estimated", "status": "estimated",
                "timeBasis": "Estimated from the league's 2026 preseason structure.",
                "source": "https://www.nfl.com/schedules/", "sourceLabel": "Estimated — NFL structure",
                "sourceUrl": "https://www.nfl.com/schedules/",
            })
    # regular season: 18 weeks
    for wk in range(1, 19):
        wk_monday = kickoff + timedelta(days=7 * (wk - 1))
        for suffix, wd, start, mins, label in NFL_WINDOWS:
            day = wk_monday + timedelta(days=(wd - wk_monday.weekday()) % 7)
            rows.append({
                "id": f"nfl-est-{year}-w{wk:02d}-{suffix}", "league": "NFL",
                "priority": "normal",
                "tags": ["nfl", "estimate"] + (["nfl-49ers"] if suffix.startswith("sun") else []),
                "date": day.isoformat(), "start": start, "durationMin": mins,
                "title": f"Week {wk} — {label} (matchups TBD)",
                "seasonType": "regular", "week": f"W{wk}",
                "timeStatus": "estimated", "status": "estimated",
                "timeBasis": "Estimated window; the NFL has not released this season's schedule.",
                "source": "https://www.nfl.com/schedules/", "sourceLabel": "Estimated — NFL structure",
                "sourceUrl": "https://www.nfl.com/schedules/",
            })
    # Thanksgiving, Christmas, Black Friday
    tg = nth_weekday(year, 11, 3, 4)
    for start, label in (("09:30", "Thanksgiving early game"), ("13:30", "Thanksgiving late game"),
                         ("17:20", "Thanksgiving night game")):
        rows.append({
            "id": f"nfl-est-{year}-thanksgiving-{start.replace(':','')}", "league": "NFL",
            "priority": "normal", "tags": ["nfl", "westwoodone", "estimate"],
            "date": tg.isoformat(), "start": start, "durationMin": DURATION["nfl"],
            "title": f"{label} (matchups TBD)", "seasonType": "regular",
            "timeStatus": "estimated", "status": "estimated",
            "timeBasis": "Thanksgiving Day is a fixed NFL date (fourth Thursday of November).",
            "source": "https://www.nfl.com/schedules/", "sourceLabel": "Estimated — NFL structure",
            "sourceUrl": "https://www.nfl.com/schedules/",
        })
    return rows


def official_superbowl(game_year):
    """Officially published Super Bowl facts for the calendar year of the game.

    Each entry was fetched live from the official page on 2026-11-05. The entry for a year
    exists only when an official page publishes the DATE; host-only announcements (LXIII,
    2029) are recorded here for the row title but deliberately carry no date, so those rows
    stay dateStatus=estimated.
    """
    return {
        2027: {
            "date": "2027-02-14", "roman": "LXI", "host": "SoFi Stadium, Inglewood",
            "url": "https://media.nfl.com/football-information/2026/news/2026-kickoff-guide",
            "label": "2026 Kickoff Guide (NFL media) — 'Super Bowl LXI ... Sunday, February 14, 2027, at SoFi Stadium'",
        },
        2028: {
            "date": "2028-02-13", "roman": "LXII", "host": "Mercedes-Benz Stadium, Atlanta",
            "url": "https://www.mercedesbenzstadium.com/events/super-bowl-lxii",
            "label": "Super Bowl LXII event page (Mercedes-Benz Stadium) — February 13, 2028",
        },
        2029: {
            # Host official (NFL.com / media.nfl.com release, Mar 30 2026): Las Vegas, Allegiant Stadium.
            # The exact date (reported as Feb 11, 2029) appears only in press reports of the NFL's
            # social announcement, not on an official page — so NO "date" key here on purpose.
            "roman": "LXIII", "host": "Allegiant Stadium, Las Vegas",
            "url": "https://www.nfl.com/news/las-vegas-to-host-super-bowl-lxiii-in-2029",
            "label": "Host announcement (NFL.com) — Las Vegas, Allegiant Stadium, 2029 (date TBA)",
        },
    }.get(game_year)


def nfl_postseason_estimate(season_year):
    """Estimated NFL postseason for a season: runs into January/February of season_year+1.

    Super Bowl date: the official date is used whenever an official page publishes it (see
    official_superbowl); otherwise the second Sunday of February is an estimate.
    """
    official = official_superbowl(season_year + 1)
    if official and official.get("date"):
        sb = date.fromisoformat(official["date"])
    else:
        sb = nth_weekday(season_year + 1, 2, 6, 2)
    rows = []
    # Official 2026-27 NFL calendar (nfl.com/news/2026-27-national-football-league-important-dates):
    #   Wild Card Weekend Jan 16-18 2027 (Sat-Mon), Divisional Jan 23-24, Conference Championships Jan 31,
    #   Super Bowl LXI Feb 14 at SoFi Stadium. The same calendar lists NO Pro Bowl date.
    # Wild Card Monday is therefore added (sb-27 = Jan 18 2027). Its game times are not published.
    rounds = [
        ("wildcard-sat", sb - timedelta(days=29), "13:30", "Wild Card Saturday", "postseason"),
        ("wildcard-sun", sb - timedelta(days=28), "10:00", "Wild Card Sunday", "postseason"),
        ("wildcard-mon", sb - timedelta(days=27), "17:15", "Wild Card Monday", "postseason"),
        ("div-sat", sb - timedelta(days=22), "13:30", "Divisional Saturday", "postseason"),
        ("div-sun", sb - timedelta(days=21), "12:00", "Divisional Sunday", "postseason"),
        ("conf-sun", sb - timedelta(days=14), "12:00", "Conference Championships", "postseason"),
        # Planning block for both Pro Bowl candidates = Westwood One's official 2026 broadcast window
        # (event w1-527138, Tue Feb 3 2026, 16:30-19:30 PT, 180 min). Used only as a conservative block.
        ("probowl-a", sb - timedelta(days=7), "16:30", "Pro Bowl Games (date unverified — candidate A)", "A"),
        ("probowl-b", sb - timedelta(days=5), "16:30", "Pro Bowl Games (date unverified — candidate B)", "B"),
        ("superbowl", sb, "15:30", "Super Bowl", "postseason"),
    ]
    for suffix, day, start, label, kind in rounds:
        allstar = kind in ("A", "B")
        is_sb = suffix == "superbowl"
        sb_date_official = bool(is_sb and official and official.get("date")
                                and day.isoformat() == official["date"])
        if is_sb and official:
            title = f"Super Bowl {official['roman']} at {official['host']} (participants TBD)"
        elif allstar:
            title = label
        else:
            title = f"{label} (participants TBD)"
        if allstar:
            basis = ("UNVERIFIED DATE. The NFL's official 2026-27 calendar does not list the 2027 Pro Bowl Games. "
                     "Both candidate dates are blocked (conservative). Candidate A = Sunday Feb 7, from an aggregator "
                     "site. Candidate B = Tuesday Feb 9, the Tuesday of Super Bowl week, which a secondary source "
                     "reports for 2027 and which matches the 2026 pattern (the 2026 Pro Bowl Games were on Tue Feb 3 "
                     "2026). Westwood One carried the 2026 Pro Bowl Games on Feb 3 2026, 4:30-7:30 PM PT, so both "
                     "candidates are also put in the radio tier. The 16:30 start and 180-minute window are that "
                     "2026 broadcast window, used as a planning block only.")
        elif sb_date_official:
            basis = ("Super Bowl date officially published — " + official["label"]
                     + ". The kickoff time is not published; the 15:30 PT start and the 195-minute block "
                       "remain planning estimates.")
        else:
            basis = ("Round window from the NFL's official 2026-27 calendar (Wild Card Jan 16-18, Divisional "
                     "Jan 23-24, Conference Championships Jan 31, Super Bowl LXI Feb 14). The day inside a "
                     "multi-day window, the matchups and the kickoff times are estimated."
                     if season_year == 2026 else
                     "Estimated from the NFL's structural calendar: the playoffs run from mid-January, with the "
                     "Super Bowl on the second Sunday of February. Matchups and times are estimated.")
        row = {
            "id": f"nfl-est-{season_year}-{suffix}", "league": "NFL",
            "priority": "high" if not allstar else "normal",
            "tags": (["nfl", "nfl-allstar", "westwoodone", "estimate"] if allstar
                     else (["nfl", "westwoodone", "estimate"] if suffix != "wildcard-mon"
                           else ["nfl", "estimate"])),
            "date": day.isoformat(), "start": start,
            "durationMin": 180 if allstar else DURATION["nfl-post"],
            "title": title,
            "seasonType": "special" if allstar else "postseason",
            "timeStatus": "estimated", "status": "estimated",
            "timeBasis": basis,
            "source": "https://www.nfl.com/news/2026-27-national-football-league-important-dates"
                      if season_year == 2026 else "https://www.nfl.com/schedules/",
            "sourceLabel": "Official NFL 2026-27 calendar (dates) / estimated structure",
            "sourceUrl": "https://www.nfl.com/news/2026-27-national-football-league-important-dates"
                         if season_year == 2026 else "https://www.nfl.com/schedules/",
            "dateStatus": "verified" if sb_date_official else "estimated",
        }
        if sb_date_official:
            row["dateSource"] = official["url"]
            row["dateSourceLabel"] = official["label"]
        rows.append(row)
    return rows

def ncaaf_calendar(year):
    """Estimated Stanford / Cal seasons: 12 games, Saturdays, late Aug - late Nov."""
    rows = []
    for team, tag in (("Stanford", "ncaaf-stanford"), ("California", "ncaaf-cal")):
        first = nth_weekday(year, 8, 5, 4)  # 4th Saturday of August (week zero/late Aug)
        weeks = 0
        day = first
        while weeks < 12 and day <= date(year, 12, 5):
            rows.append({
                "id": f"ncaaf-est-{year}-{tag}-{day.isoformat()}", "league": "NCAAF",
                "priority": "high", "tags": ["ncaaf", tag, "estimate"],
                "date": day.isoformat(), "start": "12:30", "durationMin": DURATION["ncaaf"],
                "title": f"{team} football — opponent and kickoff TBD",
                "seasonType": "regular", "timeStatus": "estimated", "status": "estimated",
                "timeBasis": ("The school has not released this season's schedule. Blocked as a Saturday "
                              "afternoon window (12:30 PT) with the note that kickoff could be later; "
                              "the planner also blocks 16:30-20:00 PT on the same date."),
                "altWindow": {"start": "16:30", "durationMin": 210},
                "source": "https://gostanford.com/sports/football/schedule" if team == "Stanford"
                          else "https://calbears.com/sports/football/schedule",
                "sourceLabel": "Estimated — school schedule not released",
                "sourceUrl": "https://gostanford.com/sports/football/schedule" if team == "Stanford"
                             else "https://calbears.com/sports/football/schedule",
            })
            weeks += 1
            day += timedelta(days=7)
    return rows


def mlb_season_estimate(year):
    """MLB 2028/2029: the schedule is not released. Model the league calendar.

    Opening Day is the last Thursday of March in recent MLB seasons; the regular season
    runs ~186 days to the last Sunday of September; the postseason starts ~2 days later
    and ends by the first days of November.
    """
    # last Thursday of March
    day = date(year, 3, 31)
    while day.weekday() != 3:
        day -= timedelta(days=1)
    opening = day
    # last Sunday of September
    end = date(year, 9, 30)
    while end.weekday() != 6:
        end -= timedelta(days=1)
    rows = []
    # spring training
    st_start = nth_weekday(year, 2, 5, 3)  # third Saturday of February
    d0 = st_start
    while d0 < opening:
        rows.append({
            "id": f"mlb-est-{year}-st-{d0.isoformat()}", "league": "MLB", "priority": "normal",
            "tags": ["mlb", "mlb-giants", "mlb-athletics", "estimate"], "date": d0.isoformat(), "start": "13:05",
            "durationMin": DURATION["mlb"],
            "title": "Spring Training slate (matchups TBD)",
            "seasonType": "preseason", "timeStatus": "estimated", "status": "estimated",
            "timeBasis": ("MLB has not released this season's schedule. Spring Training games have begun "
                          "in the third week of February in every recent season."),
            "source": "https://www.mlb.com/schedule", "sourceLabel": "Estimated — MLB calendar",
            "sourceUrl": "https://www.mlb.com/schedule",
        })
        d0 += timedelta(days=1)
    # regular season: every day, one slate row
    d0 = opening
    while d0 <= end:
        rows.append({
            "id": f"mlb-est-{year}-reg-{d0.isoformat()}", "league": "MLB", "priority": "normal",
            "tags": ["mlb", "mlb-giants", "mlb-athletics", "estimate"],
            "date": d0.isoformat(), "start": "13:05",
            "durationMin": DURATION["mlb"] + 240,
            "title": "Full MLB slate (15 games incl. Giants and Athletics, matchups TBD)",
            "seasonType": "regular", "timeStatus": "estimated", "status": "estimated",
            "timeBasis": ("MLB has not released this season's schedule. Modelled as a full daily slate "
                          "from Opening Day (last Thursday of March) to the last Sunday of September, "
                          "which is how every recent MLB season is structured."),
            "source": "https://www.mlb.com/schedule", "sourceLabel": "Estimated — MLB calendar",
            "sourceUrl": "https://www.mlb.com/schedule",
        })
        d0 += timedelta(days=1)
    # all-star break
    asg = nth_weekday(year, 7, 1, 2)  # second Tuesday of July
    rows.append({
        "id": f"mlb-est-{year}-asg", "league": "MLB", "priority": "normal",
        "tags": ["mlb", "estimate"], "date": asg.isoformat(), "start": "17:00",
        "durationMin": DURATION["mlb"] + 45,
        "title": "MLB All-Star Game (venue TBD)", "seasonType": "special",
        "timeStatus": "estimated", "status": "estimated",
        "timeBasis": "The All-Star Game has been played on the second Tuesday of July in every recent season.",
        "source": "https://www.mlb.com/schedule", "sourceLabel": "Estimated — MLB calendar",
        "sourceUrl": "https://www.mlb.com/schedule",
    })
    # postseason
    d0 = end + timedelta(days=2)
    labels = {0: "Wild Card Series", 7: "Division Series", 14: "League Championship Series",
              21: "World Series"}
    for offset, label in labels.items():
        day2 = d0 + timedelta(days=offset)
        for i in range(3 if offset < 14 else 5):
            dd = day2 + timedelta(days=i)
            rows.append({
                "id": f"mlb-est-{year}-post-{offset}-{i}", "league": "MLB", "priority": "normal",
                "tags": ["mlb", "estimate"], "date": dd.isoformat(), "start": "17:00",
                "durationMin": DURATION["mlb-post"],
                "title": f"{label} (teams TBD)", "seasonType": "postseason",
                "timeStatus": "estimated", "status": "estimated",
                "timeBasis": ("MLB has not released this season's schedule. Postseason rounds modelled on "
                              "the 2026 structure (Wild Card from the Tuesday after the final regular-season day)."),
                "source": "https://www.mlb.com/schedule", "sourceLabel": "Estimated — MLB calendar",
                "sourceUrl": "https://www.mlb.com/schedule",
            })
    return rows


def westwoodone_estimate(year):
    """W1 national NFL: mirrors the NFL national windows (SNF/MNF/TNF + Thanksgiving)."""
    rows = []
    for e in nfl_calendar(year):
        if e["id"].endswith("-snf") or e["id"].endswith("-mnf") or e["id"].endswith("-tnf"):
            rows.append({
                "id": e["id"].replace("nfl-est", "w1-est"), "league": "NFL", "priority": "high",
                "tags": ["westwoodone", "nfl", "estimate"], "date": e["date"], "start": e["start"],
                "durationMin": e["durationMin"],
                "title": f"Westwood One national radio — {e['title'].split('— ')[-1]}",
                "nationalRadio": "Westwood One Sports (national)",
                "seasonType": e["seasonType"], "timeStatus": "estimated", "status": "estimated",
                "timeBasis": ("Westwood One carries the NFL's national windows. The network has not published "
                              f"its {year} schedule; the windows are modelled on the NFL calendar."),
                "source": "https://www.westwoodonesports.com/nfl-schedule/",
                "sourceLabel": "Estimated — Westwood One national windows",
                "sourceUrl": "https://www.westwoodonesports.com/nfl-schedule/",
            })
    return rows


# ---------------------------------------------------------------- main
def windows_for(ev):
    """Return [(start_hhmm, minutes)] occupied by an event, including alternate windows."""
    if not ev.get("start"):
        # date-only: block the whole day conservatively
        return [("00:00", 1440)]
    out = [(ev["start"], ev["durationMin"])]
    if ev.get("altWindow"):
        out.append((ev["altWindow"]["start"], ev["altWindow"]["durationMin"]))
    if ev.get("startWindow"):
        a, b = ev["startWindow"].split("-")
        h1, m1 = map(int, a.split(":"))
        h2, m2 = map(int, b.split(":"))
        out.append((a, ((h2 * 60 + m2) - (h1 * 60 + m1))))
    return out


def main():
    os.makedirs("data", exist_ok=True)
    mlb_raw = {}
    for y in (2026, 2027):
        p = f"data/mlb-{y}.json"
        if os.path.exists(p):
            mlb_raw[y] = json.load(open(p))
    team_model, wd_model = learn_mlb_start_model(mlb_raw.get(2026, {"games": []})["games"])

    cur = curated_events()
    by_year = defaultdict(list)
    for e in cur:
        e["dateStatus"] = "verified"
        by_year[int(e["date"][:4])].append(e)

    for y in (2026, 2027):
        if y in mlb_raw:
            for e in mlb_events(y, mlb_raw[y], team_model, wd_model):
                by_year[int(e["date"][:4])].append(e)
            if y == 2027:
                # 2027 postseason is not scheduled yet -> estimate
                for e in mlb_season_estimate(2027):
                    if e["seasonType"] == "postseason":
                        by_year[2027].append(e)
    # 2026 postseason is published; nothing to add.

    for y in (2027, 2028, 2029):
        est = []
        if y != 2027:  # 2027 MLB regular season is already published
            est += mlb_season_estimate(y)
        est += nfl_calendar(y)
        est += ncaaf_calendar(y)
        est += westwoodone_estimate(y)
        est += nfl_postseason_estimate(y)
        for e in est:
            by_year[int(e["date"][:4])].append(e)
    for e in nfl_2026_full():
        by_year[2026].append(e)
    # the 2026 NFL season's postseason has not been seeded yet: estimate it too
    for e in nfl_postseason_estimate(2026):
        by_year[int(e["date"][:4])].append(e)
    for e in nfl_postseason_estimate(2026):
        if e["id"].endswith(("-snf", "-mnf", "-tnf")):
            pass

    # 2028/2029 MLB postseason estimates fall in the following year only if cross-year; none do.

    fold_westwoodone(by_year)

    # Re-bucket by the calendar year of each event's date so the site can load one file
    # per year without cross-year gaps (NFL playoffs and January bowls spill into January).
    rebucketed = defaultdict(list)
    for y, evs in by_year.items():
        for e in evs:
            rebucketed[int(e["date"][:4])].append(e)
    by_year = rebucketed

    # Deterministic build stamp: derived from the inputs, so re-running the pipeline on the
    # same data produces byte-identical files (which keeps CI rebuilds conflict-free).
    stamps = [m.get("meta", {}).get("retrievedUTC", "") for m in mlb_raw.values()]
    build_stamp = max([s0 for s0 in stamps if s0] or ["2026-11-02"])
    meta_common = {
        "durations": DURATION,
        "timezone": "America/Los_Angeles",
        "generatedUTC": build_stamp,
        "mlbStartModel2026": {"teams": {f"{k[0]}|{k[1]}": v for k, v in list(team_model.items())[:999]},
                              "weekday": {str(k): v for k, v in wd_model.items()}},
    }
    for y, evs in sorted(by_year.items()):
        evs.sort(key=lambda e: (e["date"], e.get("start") or "99:99", e["id"]))
        verified = sum(1 for e in evs if e["status"] == "verified")
        basis_map, basis_idx = {}, {}
        src_map, src_idx = {}, {}
        for e in evs:
            e.setdefault("dateStatus", "estimated")
            e.pop("verifyTokens", None)
            b = e.pop("timeBasis", None)
            if b:
                if b not in basis_idx:
                    basis_idx[b] = f"b{len(basis_idx)}"
                    basis_map[basis_idx[b]] = b
                e["b"] = basis_idx[b]
            sl = (e.pop("source", None), e.pop("sourceLabel", None))
            if sl[0]:
                if sl not in src_idx:
                    src_idx[sl] = f"s{len(src_idx)}"
                    src_map[src_idx[sl]] = {"url": sl[0], "label": sl[1]}
                e["s"] = src_idx[sl]
        payload = {
            "meta": {**meta_common, "year": y, "events": len(evs), "verified": verified,
                     "estimated": len(evs) - verified,
                     "basis": basis_map, "sources": src_map},
            "events": evs,
        }
        with open(f"data/events-{y}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
        print(f"{y}: {len(evs)} events ({verified} verified, {len(evs)-verified} estimated)")


if __name__ == "__main__":
    main()
