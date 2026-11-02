#!/usr/bin/env python3
"""
Turn the event feed into the answers the site shows:

  * per-day busy / free windows in Pacific time
  * ranked vacation windows (7 / 14 / 21 days) for 2027, 2028 and 2029
  * year-by-year summary statistics

Everything is computed from data/events-<year>.json; nothing is hard-coded here.

Scopes
------
all    every MLB game (all 30 clubs), every NFL game, Stanford, Cal, Westwood One
radio  only games the planner can show airing on AM/FM radio in San Francisco
       (Giants, Athletics, 49ers, Stanford, Cal, Westwood One national)
high   high-priority only (Giants, Athletics, 49ers, Stanford, Cal, Westwood One)

Output: data/derived/analysis.json
"""
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

YEARS = (2026, 2027, 2028, 2029, 2030)
TODAY = date(2026, 11, 2)
HORIZON_END = date(2030, 2, 28)

RADIO_TAGS = {"mlb-giants", "mlb-athletics", "nfl-49ers", "ncaaf-stanford", "ncaaf-cal",
              "westwoodone"}


def scope_ok(ev, scope):
    tags = set(ev.get("tags", []))
    if scope == "all":
        return True
    if scope == "radio":
        return bool(tags & RADIO_TAGS)
    if scope == "high":
        return ev.get("priority") == "high"
    return True


def intervals(ev):
    """[(start_minutes, end_minutes)] for one event on one day (may exceed 1440)."""
    if not ev.get("start"):
        return [(0, 1440)]
    base = [ev["start"]]
    mins = [(ev["start"], ev["durationMin"])]
    if ev.get("altWindow"):
        mins.append((ev["altWindow"]["start"], ev["altWindow"]["durationMin"]))
    if ev.get("startWindow"):
        a, b = ev["startWindow"].split("-")
        h1, m1 = map(int, a.split(":"))
        h2, m2 = map(int, b.split(":"))
        mins.append((a, ((h2 * 60 + m2) - (h1 * 60 + m1))))
    out = []
    for s, dur in mins:
        h, m = map(int, s.split(":"))
        out.append((h * 60 + m, h * 60 + m + dur))
    return out


def merge(ivs):
    ivs = sorted(ivs)
    out = []
    for s, e in ivs:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def clip(ivs, lo=0, hi=1440):
    return [(max(s, lo), min(e, hi)) for s, e in ivs if e > lo and s < hi]


def fmt(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def main():
    events = []
    for y in YEARS:
        p = f"data/events-{y}.json"
        if not os.path.exists(p):
            continue
        events += json.load(open(p))["events"]

    by_day = defaultdict(list)
    for e in events:
        by_day[e["date"]].append(e)

    days = {}
    d0 = TODAY
    while d0 <= HORIZON_END:
        iso = d0.isoformat()
        evs = by_day.get(iso, [])
        rec = {}
        for scope in ("all", "radio", "high"):
            sel = [e for e in evs if scope_ok(e, scope)]
            ivs = merge([iv for e in sel for iv in intervals(e)])
            today = clip(ivs)
            rec[scope] = {
                "busy": [[fmt(s), fmt(e)] for s, e in today],
                "hours": round(sum(e - s for s, e in today) / 60, 2),
                "games": len(sel),
            }
        days[iso] = rec
        d0 += timedelta(days=1)

    # ---- vacation ranking
    dates = sorted(days)
    idx = {d: i for i, d in enumerate(dates)}

    def window_stats(start_idx, length, scope):
        busy_days = 0
        busy_hours = 0.0
        conflicts = defaultdict(int)
        for k in range(start_idx, min(start_idx + length, len(dates))):
            rec = days[dates[k]][scope]
            if rec["hours"] > 0:
                busy_days += 1
                busy_hours += rec["hours"]
                conflicts[dates[k]] = rec["games"]
        return busy_days, round(busy_hours, 1), conflicts

    rank_dates = [d for d in dates if date(2027, 1, 1) <= date.fromisoformat(d) <= date(2029, 12, 31)]
    rank_idx = {d: i for i, d in enumerate(dates)}

    vacations = {}
    for scope in ("all", "radio", "high"):
        vacations[scope] = {}
        for length in (7, 14, 21):
            cands = []
            starts = [d for d in rank_dates
                      if date.fromisoformat(d) + timedelta(days=length - 1) <= date(2029, 12, 31)]
            for sd in starts:
                i = rank_idx[sd]
                bd, bh, conf = window_stats(i, length, scope)
                cands.append({
                    "start": dates[i],
                    "end": dates[i + length - 1],
                    "busyDays": bd,
                    "freeDays": length - bd,
                    "busyHours": bh,
                    "score": (length - bd) * 100 - bh,
                    "conflictDays": dict(sorted(conf.items())),
                })
            cands.sort(key=lambda c: (-c["score"], c["start"]))
            hours_ranked = sorted(cands, key=lambda c: (c["busyHours"] / length, c["start"]))
            picked, seen = [], []
            for c in cands:
                s = idx[c["start"]]
                if any(abs(s - p) < max(3, length // 2) for p in seen):
                    continue
                picked.append(c)
                seen.append(s)
                if len(picked) >= 8:
                    break
            hpick, hseen = [], []
            for c in hours_ranked:
                s0 = idx[c["start"]]
                if any(abs(s0 - q) < max(3, length // 2) for q in hseen):
                    continue
                hpick.append(c)
                hseen.append(s0)
                if len(hpick) >= 5:
                    break
            vacations[scope][str(length)] = picked
            vacations.setdefault(scope + "-hours", {})[str(length)] = hpick

    # ---- yearly summary
    summary = {}
    for y in (2026, 2027, 2028, 2029):
        ydays = [d for d in dates if d.startswith(str(y))]
        if not ydays:
            continue
        per_scope = {}
        for scope in ("all", "radio", "high"):
            free = [d for d in ydays if days[d][scope]["hours"] == 0]
            # longest fully-free streak
            best = cur = 0
            for d in ydays:
                cur = cur + 1 if days[d][scope]["hours"] == 0 else 0
                best = max(best, cur)
            per_scope[scope] = {
                "freeDays": len(free),
                "days": len(ydays),
                "longestFreeStreak": best,
                "busyHours": round(sum(days[d][scope]["hours"] for d in ydays), 0),
            }
        league_counts = defaultdict(int)
        for e in events:
            if e["date"].startswith(str(y)):
                league_counts[e["league"]] += 1
        summary[str(y)] = {"scopes": per_scope, "leagueEvents": dict(league_counts)}

    # ---- contiguous free stretches (all scope), per year
    streaks = {}
    for scope in ("all", "radio"):
        streaks[scope] = {}
        for y in (2026, 2027, 2028, 2029, 2030):
            yd = [d for d in dates if d.startswith(str(y))]
            runs, cur = [], []
            for d in yd:
                if days[d][scope]["hours"] == 0:
                    cur.append(d)
                else:
                    if cur:
                        runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
            runs.sort(key=lambda r: (-len(r), r[0]))
            streaks[scope][str(y)] = [
                {"start": r[0], "end": r[-1], "days": len(r)} for r in runs[:8]
            ]

    payload = {
        "meta": {
            "generatedUTC": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "today": TODAY.isoformat(),
            "horizon": [TODAY.isoformat(), HORIZON_END.isoformat()],
            "timezone": "America/Los_Angeles (PST/PDT)",
            "scopes": {
                "all": "Every MLB game (all 30 clubs), every NFL game, Stanford, Cal and Westwood One.",
                "radio": "Only games that air on AM/FM radio in San Francisco: Giants, Athletics, 49ers, Stanford, Cal, Westwood One.",
                "high": "High-priority teams only: Giants, Athletics, 49ers, Stanford, Cal, Westwood One.",
            },
        },
        "summary": summary,
        "freeStreaks": streaks,
        "vacations": vacations,
        "days": days,
    }
    os.makedirs("data/derived", exist_ok=True)
    with open("data/derived/analysis.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")
    print(f"days={len(days)} size={os.path.getsize('data/derived/analysis.json')}")
    for y, s in summary.items():
        a = s["scopes"]["all"]
        print(f"  {y}: freeDays(all)={a['freeDays']}/{a['days']} longestStreak={a['longestFreeStreak']} "
              f"radioFree={s['scopes']['radio']['freeDays']}")
    for scope in ("all", "radio"):
        for L in (7, 14):
            top = vacations[scope][str(L)][0]
            print(f"  best {L}d [{scope}]: {top['start']}..{top['end']} freeDays={top['freeDays']} "
                  f"busyHours={top['busyHours']}")


if __name__ == "__main__":
    main()
