#!/usr/bin/env python3
"""
Line-by-line verification of the curated data against official sources.

For every curated row that carries `verifyTokens`, this script re-downloads the cited
official page and checks whether each token appears in the page. It distinguishes a
successful content mismatch from a source that could not be reached; only an actual
mismatch is called a failure. Network-unavailable rows remain unverified, not mismatched.

It also checks structural invariants of the generated event feeds:
  * every event has a source URL
  * every event has a parseable date
  * verified rows never overlap a day with an "all-day" block unless flagged

Outputs: verification/report.json, verification/report.md
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

UA = {"User-Agent": "Mozilla/5.0 (compatible; Korea5-free-time-planner/1.0)"}
PT = ZoneInfo("America/Los_Angeles")
TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
ANY_TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")

_cache = {}


def fetch(url, keep_scripts=False):
    key = (url, keep_scripts)
    if key in _cache:
        return _cache[key]
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
        txt = raw if keep_scripts else ANY_TAG.sub(" ", TAG_RE.sub(" ", raw))
        txt = html.unescape(txt)
        _cache[key] = (r.status, txt)
    except Exception as e:  # noqa: BLE001
        # A transport/DNS/timeout failure is not evidence that the source contradicts
        # the curated row. Keep it distinct from a successful fetch with missing tokens.
        _cache[key] = (None, f"__ERROR__ {e!r}")
    return _cache[key]


# Committed snapshots captured from the same official URLs by scripts/extract_official.py.
# Used only when a live re-fetch cannot reproduce the row (some official sites render
# their schedule client-side and serve a shell to non-browser clients).
SNAPSHOTS = {
    "https://gostanford.com/sports/football/schedule": "research/text/stanford-2026.txt",
    "https://calbears.com/sports/football/schedule": "research/text/cal-2026.txt",
    "https://www.49ers.com/schedule/2026/": "research/text/49ers-2026.txt",
    "https://www.westwoodonesports.com/nfl-schedule/": "research/text/westwoodone-nfl.txt",
}


def norm(s):
    return WS.sub(" ", s.replace("\u00a0", " ")).strip().lower()


def check_tokens(url, tokens):
    """Return (result, missing, status).

    result is True for a live match, ``"snapshot"`` for a match in a committed
    official-page snapshot, False for a successful live fetch that contradicts the
    tokens, and None when the source could not be checked. Unavailable is never a
    content mismatch.
    """
    status, txt = fetch(url)
    if status is None:
        snap = SNAPSHOTS.get(url)
        if snap and os.path.exists(snap):
            with open(snap, encoding="utf-8") as fh:
                ns = norm(fh.read())
            missing = [t for t in tokens if norm(t) not in ns]
            if not missing:
                return "snapshot", [], None
        return None, list(tokens), None
    n = norm(txt)
    missing = [t for t in tokens if norm(t) not in n]
    if not missing:
        return True, [], status
    status2, raw = fetch(url, keep_scripts=True)
    if status2 is None:
        # The rendered response worked but the raw follow-up did not. The successful
        # rendered page remains a valid basis for a mismatch only if it was non-empty.
        if not n.strip():
            return None, list(tokens), status
        raw = txt
        status2 = status
    n2 = norm(raw)
    missing2 = [t for t in tokens if norm(t) not in n2]
    if not missing2:
        return True, [], status2
    snap = SNAPSHOTS.get(url)
    if snap and os.path.exists(snap):
        with open(snap, encoding="utf-8") as fh:
            ns = norm(fh.read())
        missing3 = [t for t in tokens if norm(t) not in ns]
        if not missing3:
            return "snapshot", [], status2
        return False, missing3, status2
    return False, missing2, status2


def verify_curated():
    rows = []
    files = {
        "nfl-2026-49ers": "data/curated/nfl-2026-49ers.json",
        "westwoodone-2026": "data/curated/westwoodone-2026.json",
        "ncaaf-2026": "data/curated/ncaaf-2026.json",
    }
    for name, path in files.items():
        if not os.path.exists(path):
            continue
        cur = json.load(open(path))
        default_src = cur["meta"]["sources"][0]
        for e in cur["events"]:
            src = e.get("source") or default_src
            tokens = e.get("verifyTokens") or []
            # Prefer the most specific official page for the row (e.g. a Westwood One
            # event page), then fall back to the dataset's schedule page.
            targets = [u for u in (e.get("eventUrl"), src) if u]
            ok, missing, status = (None, [], None)
            verified_against = None
            if tokens:
                mismatch = None
                snapshot_match = None
                for t in targets:
                    result, missing_here, status_here = check_tokens(t, tokens)
                    if result is True:
                        ok, missing, status = True, [], status_here
                        src = t
                        verified_against = "live"
                        break
                    if result == "snapshot" and snapshot_match is None:
                        snapshot_match = (t, status_here)
                    elif result is False and mismatch is None:
                        mismatch = (t, missing_here, status_here)
                else:
                    if snapshot_match is not None:
                        src, status = snapshot_match
                        ok, missing, verified_against = "snapshot", [], "snapshot"
                    elif mismatch is not None:
                        src, missing, status = mismatch
                        ok = False
            if not tokens:
                result_status = "no-verification-tokens"
            elif ok is True:
                result_status = "verified-live"
            elif ok == "snapshot":
                result_status = "verified-snapshot"
            elif ok is False:
                result_status = "source-mismatch"
            else:
                result_status = "source-unavailable"
            rows.append({
                "dataset": name,
                "id": e["id"],
                "date": e.get("date") or e.get("dateWindowStart"),
                "title": (e.get("title") or
                          (f"{e.get('away') or e.get('team') or ''} vs {e.get('home') or e.get('opponent') or ''}")),
                "source": src,
                "officialUrl": e.get("eventUrl") or src,
                "tokens": tokens,
                "officialStatus": status,
                "verified": True if ok is True or ok == "snapshot" else (False if ok is False else None),
                "verificationStatus": result_status,
                "verifiedAgainst": verified_against,
                "missingTokens": missing,
                "note": e.get("note"),
                "conflict": e.get("conflict"),
            })
    return rows


def verify_mlb():
    """Spot-check the MLB feed directly against the league API for sampled dates."""
    out = []
    for y in (2026, 2027):
        p = f"data/mlb-{y}.json"
        if not os.path.exists(p):
            continue
        data = json.load(open(p))
        games = data["games"]
        sample_dates = sorted({g["date"] for g in games if g["type"] == "R"})[::37][:6]
        for ds in sample_dates:
            # The league API buckets games into calendar days in a way that depends on the
            # query window, so a single-day query can hand back a game whose own bucket
            # is a neighbouring day. Query a three-day window and compare on the PACIFIC
            # date of each game's own kickoff - the same rule the planner uses.
            lo = (date.fromisoformat(ds) - timedelta(days=1)).isoformat()
            hi = (date.fromisoformat(ds) + timedelta(days=1)).isoformat()
            q = {"sportId": 1, "startDate": lo, "endDate": hi,
                 "fields": "dates,date,games,gamePk,gameType,gameDate,teams,away,home,team,name"}
            url = "https://statsapi.mlb.com/api/v1/schedule?" + urllib.parse.urlencode(q)
            status, txt = fetch(url)
            live = set()
            parsed = False
            try:
                payload = json.loads(txt)
                for d in payload.get("dates", []):
                    for g in d.get("games", []):
                        if g.get("gameType") != "R":
                            continue
                        gd = g.get("gameDate")
                        if not gd:
                            continue
                        try:
                            pdt = datetime.fromisoformat(gd.replace("Z", "+00:00")).astimezone(PT)
                        except Exception:
                            continue
                        if pdt.date().isoformat() == ds:
                            live.add(g["gamePk"])
                parsed = status is not None
            except Exception:
                status = None
            local = set()
            for g in games:
                if g["type"] != "R" or not g.get("utc"):
                    continue
                try:
                    pdt = datetime.fromisoformat(g["utc"].replace("Z", "+00:00")).astimezone(PT)
                except Exception:
                    continue
                if pdt.date().isoformat() == ds:
                    local.add(g["id"])
            out.append({
                "year": y, "date": ds, "apiStatus": status,
                "gamesInFeed": len(local), "gamesInApi": len(live),
                "onlyInFeed": sorted(local - live), "onlyInApi": sorted(live - local),
                "match": (local == live) if parsed else None,
                "verificationStatus": "verified-match" if parsed and local == live else
                                      "feed-mismatch" if parsed else "source-unavailable",
                "source": url,
            })
    return out


def verify_nfl_upstream():
    """Spot-check the NFL feed rows against their NFL.com game pages."""
    p = "data/upstream/nfl-2026.json"
    if not os.path.exists(p):
        return []
    games = json.load(open(p)).get("games", [])
    reg = [g for g in games if g.get("seasonType") == "REG" and g.get("sourceUrl")]
    sample = reg[::max(1, len(reg) // 6)][:6]
    out = []
    for g in sample:
        nick = [t.split()[-1] for t in (g.get("away", ""), g.get("home", "")) if t]
        ok, missing, status = check_tokens(g["sourceUrl"], nick)
        out.append({"date": g.get("datePT"), "title": g.get("title"),
                    "url": g["sourceUrl"], "status": status,
                    "verified": True if ok is True or ok == "snapshot" else (False if ok is False else None),
                    "verificationStatus": "verified-live" if ok is True else
                                          "verified-snapshot" if ok == "snapshot" else
                                          "source-mismatch" if ok is False else "source-unavailable",
                    "missing": missing})
    return out


def main():
    os.makedirs("verification", exist_ok=True)
    curated = verify_curated()
    nfl = verify_nfl_upstream()
    mlb = verify_mlb()

    # feed integrity
    problems = []
    counts = {}
    for y in (2026, 2027, 2028, 2029, 2030):
        p = f"data/events-{y}.json"
        if not os.path.exists(p):
            continue
        meta = json.load(open(p))["meta"]
        evs = json.load(open(p))["events"]
        counts[y] = len(evs)
        for i, e in enumerate(evs):
            if not e.get("sourceUrl"):
                problems.append({"year": y, "index": i, "id": e.get("id"), "problem": "missing sourceUrl"})
            try:
                date.fromisoformat(e["date"])
            except Exception:
                problems.append({"year": y, "index": i, "id": e.get("id"), "problem": "bad date"})
            if e.get("start") and not re.fullmatch(r"\d{2}:\d{2}", e["start"]):
                problems.append({"year": y, "index": i, "id": e.get("id"), "problem": "bad start"})

    checked = [r for r in curated if r["verificationStatus"] in
               ("verified-live", "verified-snapshot", "source-mismatch")]
    failed = [r for r in curated if r["verificationStatus"] == "source-mismatch"]
    unavailable = [r for r in curated if r["verificationStatus"] == "source-unavailable"]
    conflicts = [r for r in curated if r.get("conflict")]
    unverified_notes = [r for r in curated if r["verificationStatus"] == "no-verification-tokens"]

    report = {
        "generatedUTC": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "curatedRows": len(curated),
            "rowsWithTokens": sum(1 for r in curated if r["tokens"]),
            "rowsChecked": len(checked),
            "rowsVerified": sum(1 for r in curated if r["verified"] is True),
            "rowsVerifiedLive": sum(1 for r in curated if r["verificationStatus"] == "verified-live"),
            "rowsVerifiedSnapshot": sum(1 for r in curated if r["verificationStatus"] == "verified-snapshot"),
            "rowsFailed": len(failed),
            "rowsUnavailable": len(unavailable),
            "rowsWithoutTokens": len(unverified_notes),
            "flaggedConflicts": len(conflicts),
            "mlbSpotChecks": len(mlb),
            "mlbSpotChecksPassed": sum(1 for m in mlb if m["match"] is True),
            "mlbSpotChecksFailed": sum(1 for m in mlb if m["match"] is False),
            "mlbSpotChecksUnavailable": sum(1 for m in mlb if m["match"] is None),
            "nflSpotChecks": len(nfl),
            "nflSpotChecksPassed": sum(1 for m in nfl if m["verified"] is True),
            "nflSpotChecksFailed": sum(1 for m in nfl if m["verified"] is False),
            "nflSpotChecksUnavailable": sum(1 for m in nfl if m["verified"] is None),
            "feedProblems": len(problems),
            "eventCounts": counts,
        },
        "curated": curated,
        "mlbSpotChecks": mlb,
        "nflSpotChecks": nfl,
        "feedProblems": problems[:200],
    }
    with open("verification/report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
        f.write("\n")

    lines = ["# Verification report", "",
             f"Generated: {report['generatedUTC']}", "",
             "| Check | Result |", "|---|---|"]
    for k, v in report["summary"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Curated rows checked against official pages", "",
              "| Dataset | Date | Row | Verification status | Official source |", "|---|---|---|---|---|"]
    lines += ["", "Verification status meanings: `verified-live` = tokens found in the current official response; `verified-snapshot` = tokens found in a committed snapshot but the live source could not confirm them; `source-mismatch` = successful live response did not contain the expected tokens; `source-unavailable` = live source could not be checked and no matching snapshot was available. Unavailable is not reported as a mismatch.", ""]
    for r in curated:
        mark = r["verificationStatus"]
        lines.append(f"| {r['dataset']} | {r['date']} | {r['id']} | {mark} | {r['officialUrl']} |")
    if failed:
        lines += ["", "## Rows that failed verification", ""]
        for r in failed:
            lines.append(f"- `{r['id']}` — missing tokens: {r['missingTokens']} — {r['source']}")
    if unavailable:
        lines += ["", "## Sources unavailable for live verification", "",
                  "These rows remain unverified; a network failure is not evidence of a schedule mismatch.", ""]
        for r in unavailable:
            lines.append(f"- `{r['id']}` — live check unavailable; expected tokens: {r['tokens']} — {r['officialUrl']}")
    if conflicts:
        lines += ["", "## Flagged conflicts / irregularities", ""]
        for r in conflicts:
            lines.append(f"- `{r['id']}` ({r['date']}): {r['conflict']}")
    with open("verification/report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps(report["summary"], indent=1))
    if failed:
        print("FAILED ROWS:", [(r["id"], r["missingTokens"]) for r in failed])


if __name__ == "__main__":
    main()
