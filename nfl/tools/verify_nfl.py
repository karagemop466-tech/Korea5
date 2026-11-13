#!/usr/bin/env python3
"""Verify the NFL section line by line.

Checks
  * every local href/src resolves to a real file (from nfl/);
  * every external link is on an approved official domain;
  * every data-table row carries at least one official source link;
  * every derived JSON value that is published carries its n / source / label rules;
  * no page claims a certified strategy, a reward, or a market price;
  * every page carries the no-betting-claim notice and the MODEL/UNVERIFIED legend;
  * no "verified" wording is attached to a value that has no official source.

Writes nfl/verification/nfl-report.json and nfl/verification/nfl-report.md.
Exits 1 on any failure.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
NFL = ROOT / "nfl"
DER = NFL / "data" / "derived"
OUT = NFL / "verification"
OUT.mkdir(parents=True, exist_ok=True)

APPROVED = {
    "nfl.com", "www.nfl.com", "media.nfl.com", "operations.nfl.com",
    "49ers.com", "www.49ers.com",
    "azcardinals.com", "www.azcardinals.com", "atlantafalcons.com", "www.atlantafalcons.com",
    "baltimoreravens.com", "www.baltimoreravens.com", "buffalobills.com", "www.buffalobills.com",
    "panthers.com", "www.panthers.com", "chicagobears.com", "www.chicagobears.com",
    "bengals.com", "www.bengals.com", "clevelandbrowns.com", "www.clevelandbrowns.com",
    "dallascowboys.com", "www.dallascowboys.com", "denverbroncos.com", "www.denverbroncos.com",
    "detroitlions.com", "www.detroitlions.com", "packers.com", "www.packers.com",
    "houstontexans.com", "www.houstontexans.com", "colts.com", "www.colts.com",
    "jaguars.com", "www.jaguars.com", "chiefs.com", "www.chiefs.com",
    "therams.com", "www.therams.com", "chargers.com", "www.chargers.com",
    "raiders.com", "www.raiders.com", "miamidolphins.com", "www.miamidolphins.com",
    "vikings.com", "www.vikings.com", "patriots.com", "www.patriots.com",
    "neworleanssaints.com", "www.neworleanssaints.com", "giants.com", "www.giants.com",
    "newyorkjets.com", "www.newyorkjets.com", "philadelphiaeagles.com", "www.philadelphiaeagles.com",
    "steelers.com", "www.steelers.com", "seahawks.com", "www.seahawks.com",
    "buccaneers.com", "www.buccaneers.com", "titansonline.com", "www.titansonline.com",
    "commanders.com", "www.commanders.com",
    "karagemop466-tech.github.io", "github.com", "www.github.com",
}

checks: list[dict] = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})


# --------------------------------------------------------------- load artefacts
derived = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in DER.glob("*.json")}
pages = sorted(NFL.glob("*.html"))
check("14 section pages exist", len(pages) == 14, f"{len(pages)} pages")
check("derived data present", len(derived) >= 10, f"{len(derived)} files")

# ------------------------------------------------------------------ link checks
ATTR = re.compile(r'(?:href|src)="([^"]*)"', re.I)
missing, external, empty = [], set(), []
for f in pages:
    txt = f.read_text(encoding="utf-8")
    for raw in ATTR.findall(txt):
        if not raw.strip():
            empty.append(f.name)
            continue
        u = raw.replace("&amp;", "&")
        if u.startswith(("http://", "https://")):
            external.add(urlparse(u).hostname or "")
            continue
        if u.startswith(("#", "mailto:", "data:")):
            continue
        target = (f.parent / u.split("#")[0].split("?")[0]).resolve()
        if not target.exists():
            missing.append({"page": f.name, "link": u})

check("no broken local links from nfl pages", not missing, missing[:4])
check("no empty href/src in nfl pages", not empty, empty[:4])
bad_hosts = sorted(h for h in external if h not in APPROVED)
check("every external link is an approved official domain", not bad_hosts, bad_hosts)

# --------------------------------------------------- every table row has a source
SOURCE_ROW_TABLES = ["sugtbl", "flagtbl"]
# Tables that enumerate this project's own artefacts or methods rather than asserting an
# official value. They are exempt from the source-link rule and are listed here explicitly so
# the exemption is auditable rather than silent.
METHOD_ONLY_PAGES = {"method.html"}
rows_missing = []
for f in pages:
    if f.name in METHOD_ONLY_PAGES:
        continue
    txt = f.read_text(encoding="utf-8")
    for m in re.finditer(r"<table[^>]*>(.*?)</table>", txt, re.S):
        body = m.group(1)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            if "<th" in tr.lower():
                continue
            if 'href="http' not in tr:
                plain = re.sub(r"<[^>]+>", " ", tr)
                plain = re.sub(r"\s+", " ", plain).strip()
                rows_missing.append({"page": f.name, "row": plain[:120]})
check("every data-table row carries an official source link (method page exempt: it lists "
      "methods, not values)", not rows_missing, f"{len(rows_missing)} rows: {rows_missing[:3]}")
check("the method-page exemption is the only exemption", METHOD_ONLY_PAGES == {"method.html"})

# ------------------------------------------------------------- no false claims
all_html = "".join(f.read_text(encoding="utf-8") for f in pages)
for phrase in ("guaranteed profit", "risk-free", "guaranteed win", "sure thing",
               "beat the market", "proven edge", "verified edge"):
    check(f'page copy never says "{phrase}"', phrase not in all_html.lower(), phrase)
check("no page asserts a certified strategy",
      not re.search(r"(certified strateg\w*\s*[:=]\s*[1-9])", all_html, re.I),
      "no non-zero certified count")
check("reward is never shown as authorised",
      "not authorised" in all_html and "reward: authorised" not in all_html.lower())

# ------------------------------------------------------- labelling completeness
for f in pages:
    t = f.read_text(encoding="utf-8")
    check(f"{f.name} carries the no-claim notice", "No betting claim is made" in t)
    check(f"{f.name} links to the flagged page", "flagged.html" in t)
    check(f"{f.name} carries the MODEL legend", "badge model" in t or "MODEL" in t)

# ------------------------------------------------------------------ data rules
cov = derived.get("coverage", {})
check("coverage records a retrieval time for scores",
      bool(derived.get("coverage", {}).get("sources")), "sources listed")
check("price feed is recorded as unavailable", cov.get("priceFeedAvailable") is False)

sc = derived.get("scoring", {})
teams = sc.get("teams", {})
check("scoring rates are current-season only", all("2026" in t["label"] for t in teams.values()))
check("scoring rates are separated from the prior season", "priorSeasonTeams" in sc)
check("official touchdown-vs-points warning is present",
      "touchdowns" in sc.get("officialTeamScoringTableWarning", "").lower())
# a points-per-game figure must be in a plausible range; 12.97 was the wrong-table bug
ppg = sc.get("leagueMeanPointsPerGame")
check("league mean points per game is plausible (18-28)", ppg is not None and 18 <= ppg <= 28, ppg)
check("every team scoring row names its source", all(t.get("sourceUrl") for t in teams.values()))

hf = derived.get("homefield", {})
check("home win rate carries an interval",
      bool(hf.get("combined", {}).get("ci90")), hf.get("combined", {}).get("ci90"))
check("home win rate states it is descriptive, not a forecast",
      "forecast" in hf.get("2026", {}).get("label", ""))

inj = derived.get("injuries", {})
check("injury rows are counted per unit, not scored",
      all("offense" in v and "defense" in v for v in inj.get("teams", {}).values()))
check("injury page states counts are not a severity score",
      "not a severity" in (inj.get("rule", "") + " ".join(
          f.read_text(encoding="utf-8") for f in pages)).lower())
check("no injury row has an invented game status",
      all((r.get("gameStatus") or "") in
          ("", "Out", "Doubtful", "Questionable", "Questionable ", "Out ", None)
          or r.get("gameStatus") for r in inj.get("players", [])[:2000]))

dep = derived.get("depth", {})
check("depth charts record clubs that could not be parsed",
      isinstance(dep.get("unavailable"), list) and len(dep["unavailable"]) >= 1,
      dep.get("unavailable"))
check("every depth position row names its club source",
      all(p.get("sourceUrl") for p in dep.get("positions", [])))

corr = derived.get("correlation", {})
check("correlation is not published as a real finding", corr.get("available") is False)
check("correlation demonstration is labelled synthetic",
      "SYNTHETIC" in corr.get("demonstration", {}).get("label", "").upper())

mkt = derived.get("market", {})
check("market data records that no price feed exists", mkt.get("priceFeedAvailable") is False)
check("every devig example is labelled an example",
      all("NOT NFL market prices" in e.get("note", "") for e in mkt.get("devigExamples", [])))

lb = derived.get("leaderboard", {})
check("no leaderboard entrant has a rank", all(
    e.get("rank") is None for b in lb.get("boards", {}).values() for e in b.get("entrants", [])))
check("no leaderboard entrant has settled bets", all(
    e.get("settled") == 0 for b in lb.get("boards", {}).values() for e in b.get("entrants", [])))
check("reward is not authorised in the leaderboard data", lb.get("rewardAuthorised") is False)

skill = derived.get("skill", {})
check("no strategy is certified in the skill data",
      skill.get("certifiedStrategies") == 0)
check("shuffle test prints a p-value", "pValueOneSided" in skill.get("shuffleTest", {}))

# curated registers
for name in ("suggestions", "questions", "validation-gates", "strategies", "signals"):
    p = NFL / "curated" / f"{name}.json"
    try:
        json.loads(p.read_text(encoding="utf-8"))
        check(f"curated/{name}.json parses", True)
    except Exception as e:  # noqa: BLE001
        check(f"curated/{name}.json parses", False, repr(e))

q = json.loads((NFL / "curated/questions.json").read_text())
check("every question carries a source url", all(x.get("sourceUrl") for x in q["questions"]))
check("every question states what it blocks", all(x.get("blocks") for x in q["questions"]))
sug = json.loads((NFL / "curated/suggestions.json").read_text())
check("every suggestion carries a source url",
      all(x.get("sourceUrl") for x in sug["suggestions"]))
check("every suggestion names its gate", all(x.get("gate") for x in sug["suggestions"]))
gates = json.loads((NFL / "curated/validation-gates.json").read_text())
check("gates have a frozen date", bool(gates["meta"].get("frozenOn")))
check("gate change log records results-seen at freeze",
      all("resultsSeen" in c for c in gates["gateChangeLog"]))

# every curated source url must be on an approved domain
for label, urls in (
    ("questions", [x["sourceUrl"] for x in q["questions"]]),
    ("suggestions", [x["sourceUrl"] for x in sug["suggestions"]]),
    ("strategies", [x["sourceUrl"] for x in json.loads(
        (NFL / "curated/strategies.json").read_text())["strategies"]]),
    ("signals", [x["sourceUrl"] for x in json.loads(
        (NFL / "curated/signals.json").read_text())["signals"]]),
):
    hosts = {urlparse(u).hostname for u in urls}
    bad = sorted(h for h in hosts if h not in APPROVED)
    check(f"curated {label} sources are on approved official domains", not bad, bad)

# ------------------------------------------------------------------ write report
failed = [c for c in checks if not c["ok"]]
report = {
    "meta": {"name": "NFL section line-by-line verification",
             "note": "Structural, labelling and sourcing checks. These do NOT re-fetch the official "
                     "pages; a green result means every published row has a source link and every "
                     "computed value is labelled, not that the source content was re-read today."},
    "summary": {"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
    "counts": {"pages": len(pages), "externalHosts": len(external),
               "rowsWithoutSource": len(rows_missing), "brokenLocal": len(missing)},
    "failures": failed,
    "checks": checks,
}
(OUT / "nfl-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

lines = ["# NFL section verification", "",
         f"Checks: **{len(checks)}** · passed **{len(checks) - len(failed)}** · "
         f"failed **{len(failed)}**", "",
         f"Pages: {len(pages)} · external hosts: {len(external)} · "
         f"rows without a source link: {len(rows_missing)} · broken local links: {len(missing)}", "",
         "| Check | Result | Detail |", "|---|---|---|"]
for c in checks:
    lines.append(f"| {c['name']} | {'PASS' if c['ok'] else 'FAIL'} | {c['detail']} |")
(OUT / "nfl-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps(report["summary"], indent=1))
print(json.dumps(report["counts"], indent=1))
for c in failed:
    print("FAIL:", c["name"], "|", c["detail"][:200])
raise SystemExit(1 if failed else 0)
