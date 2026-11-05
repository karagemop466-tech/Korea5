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
TODAY = date(2026, 11, 5)
HORIZON_END = date(2030, 2, 28)

RADIO_TAGS = {"mlb-giants", "mlb-athletics", "nfl-49ers", "ncaaf-stanford", "ncaaf-cal",
              "westwoodone"}


def scope_ok(ev, scope):
    """`all` is the closed four-item "free" definition from the brief.

    `extended` additionally counts the other Bay Area AM/FM radio sports we found
    (tag `other-radio`) - currently the Golden State Warriors on 95.7 The Game.
    """
    tags = set(ev.get("tags", []))
    if scope == "all":
        return "other-radio" not in tags
    if scope == "extended":
        return True
    if scope == "radio":
        return bool(tags & RADIO_TAGS)
    if scope == "high":
        # The owner's team tier is the same set as the radio tier: Giants, Athletics, 49ers,
        # Stanford, Cal and Westwood One. It used to test only the `priority` field, which
        # left every estimated Giants/A's/49ers/Stanford/Cal row out of the scope.
        return bool(tags & RADIO_TAGS)
    return True


def intervals(ev):
    """[(start_minutes, end_minutes)] for one event on one day (may exceed 1440)."""
    if not ev.get("start"):
        # A game with no published kickoff time is blocked conservatively, but only across
        # the plausible playing window (see TBD_WINDOW in build_events.py), not all 24 hours.
        if ev.get("startWindow"):
            a, b = ev["startWindow"].split("-")
            h1, m1 = map(int, a.split(":"))
            h2, m2 = map(int, b.split(":"))
            return [(h1 * 60 + m1, h2 * 60 + m2)]
        return [(720, 1410)]
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
        for scope in ("all", "radio", "high", "extended"):
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
    for scope in ("all", "radio", "high", "extended"):
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
        for scope in ("all", "radio", "high", "extended"):
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
    for scope in ("all", "radio", "extended"):
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

    # ---- coverage of the "other Bay Area radio sports" group ---------------
    other_dates = sorted({e["date"] for e in events if "other-radio" in set(e.get("tags", []))})
    other_coverage = ({"start": other_dates[0], "end": other_dates[-1], "rows": len(other_dates)}
                      if other_dates else None)

    # ---- recommended window per year -------------------------------------
    # The single longest run of consecutive days on which nothing in scope airs.
    # Reported for both scopes so the site can answer "how long can I actually go?"
    # without pretending that an all-star exhibition is a league game.
    recommended = {}
    for y in (2027, 2028, 2029):
        entry = {"year": y, "scopes": {}}
        for scope in ("all", "radio", "extended"):
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
            if not runs:
                continue
            best = max(runs, key=lambda r: len(r))
            before = [d for d in yd if d < best[0] and days[d][scope]["hours"] > 0]
            after = [d for d in yd if d > best[-1] and days[d][scope]["hours"] > 0]
            inside = [e for e in events
                      if best[0] <= e["date"] <= best[-1] and scope_ok(e, scope)]
            entry["scopes"][scope] = {
                "start": best[0],
                "end": best[-1],
                "days": len(best),
                "fits": {str(n): len(best) >= n for n in (7, 14, 21)},
                "blockedBefore": before[-1] if before else None,
                "blockedAfter": after[0] if after else None,
                "eventsInside": len(inside),
            }
            if scope == "extended" and other_coverage:
                covered = (other_coverage["start"] <= f"{y}-01-01" and
                           other_coverage["end"] >= f"{y}-12-31")
                entry["scopes"][scope]["otherCoverage"] = other_coverage
                entry["scopes"][scope]["fullyCovered"] = covered
                entry["scopes"][scope]["coverageNote"] = (
                    None if covered else
                    f"Other-sport rows were ingested only for {other_coverage['start']} to "
                    f"{other_coverage['end']}. Outside that window this column equals the strict "
                    f"column, which is NOT evidence that {y} is clear of other Bay Area radio sport.")
        # Any modelled all-star exhibition inside the radio window is a caveat, not a game.
        rec = entry["scopes"].get("radio")
        if rec:
            rec["allStarInside"] = sorted({
                e["title"] for e in events
                if rec["start"] <= e["date"] <= rec["end"] and "nfl-allstar" in e.get("tags", [])
            })
        recommended[str(y)] = entry

    # ---- Pro Bowl date scenarios and tied longest runs --------------------
    # The 2027-29 Pro Bowl Games date is not in the NFL's official calendar. The base result blocks
    # both candidate dates (conservative). These scenarios show what each single assumption gives.
    def runs_excluding(yd, scope, keep):
        """All runs of days with nothing in scope; candidate Pro Bowl events are dropped unless keep()."""
        runs, cur = [], []
        for d in yd:
            evs = [e for e in by_day.get(d, []) if scope_ok(e, scope)
                   and (e.get("allstarCandidate") is None or keep(e))]
            busy = merge([iv for e in evs for iv in intervals(e)])
            if not busy:
                cur.append(d)
            else:
                if cur:
                    runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        return runs

    def summarize(runs):
        if not runs:
            return None, []
        top = max(len(r) for r in runs)
        ties = [{"start": r[0], "end": r[-1], "days": len(r)} for r in runs if len(r) == top]
        return ties[0], ties

    for y in (2027, 2028, 2029):
        yd = [d for d in dates if d.startswith(str(y))]
        cands = {}
        for e in events:
            if e.get("allstarCandidate") and e["date"].startswith(str(y)):
                cands[e["allstarCandidate"]] = e["date"]
        if str(y) not in recommended:
            continue
        block = {"candidates": cands, "scenarios": {}}
        for scope in ("all", "radio"):
            block["scenarios"][scope] = {}
            for label, keep in (
                ("bothCandidatesBlocked", lambda e: True),
                ("onlyCandidateA", lambda e: e.get("allstarCandidate") == "A"),
                ("onlyCandidateB", lambda e: e.get("allstarCandidate") == "B"),
                ("noProBowlGame", lambda e: False),
            ):
                best, ties = summarize(runs_excluding(yd, scope, keep))
                block["scenarios"][scope][label] = {"best": best, "ties": ties}
            base_runs = runs_excluding(yd, scope, lambda e: True)
            recommended[str(y)]["scopes"][scope]["ties"] = summarize(base_runs)[1]
        recommended[str(y)]["proBowl"] = block

    payload = {
        "meta": {
            "generatedUTC": (json.load(open("data/events-2027.json"))["meta"].get("generatedUTC")
                             if os.path.exists("data/events-2027.json") else "2026-11-02"),
            "today": TODAY.isoformat(),
            "horizon": [TODAY.isoformat(), HORIZON_END.isoformat()],
            "otherCoverage": other_coverage,
            "timezone": "America/Los_Angeles (PST/PDT)",
            "scopes": {
                "all": "Every MLB game (all 30 clubs), every NFL game, Stanford, Cal and Westwood One.",
                "radio": "Only games that air on AM/FM radio in San Francisco: Giants, Athletics, 49ers, Stanford, Cal, Westwood One national (including the Pro Bowl Games, carried by Westwood One in 2026).",
                "high": "Team tier: Giants, Athletics, 49ers, Stanford, Cal, Westwood One. Identical to the radio tier by construction, because the owner's priority list is these teams plus all MLB and NFL games, which the 'all' scope already blocks.",
                "extended": "The four-item definition plus other Bay Area AM/FM radio sports we found (Warriors on 95.7 The Game). Not part of the brief's closed definition - opt in.",
            },
        },
        "summary": summary,
        "freeStreaks": streaks,
        "recommended": recommended,
        "vacations": vacations,
        "days": days,
    }
    os.makedirs("data/derived", exist_ok=True)
    with open("data/derived/analysis.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")
    print(f"days={len(days)} size={os.path.getsize('data/derived/analysis.json')}")
    for y, r in recommended.items():
        for scope, w in r["scopes"].items():
            print(f"  recommended [{scope}] {y}: {w['start']}..{w['end']} = {w['days']}d"
                  f"  before={w['blockedBefore']} after={w['blockedAfter']}")
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
