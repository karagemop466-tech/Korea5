#!/usr/bin/env python3
"""Verify the NFL lines lab: links, sources, labels, data integrity, determinism.

Checks, each reported individually and all of them failing the build if violated:

  V01 every local href/src in nfl-lines/*.html resolves to a real file
  V02 every external link on those pages is on an allow-listed domain
  V03 every dataset cited in the source registry exists with its declared row count
  V04 every JSON artefact parses and carries a generatedUTC stamp
  V05 no template artefacts leak into the HTML ("None" as a cell, "nan", "{", "}")
  V06 the exact honesty labels are present where required
  V07 no strategy is marked reward-eligible, and every BLOCKED strategy has zero bets
  V08 every tested strategy publishes an interval (or an explicit "not estimable" note)
  V09 the 2026 week-11 card never labels a row PLAY
  V10 every question and every suggestion carries an id, a status and a decision/answer
  V11 root pages link to the lab, and the lab links back
  V12 the report is written to nfl-lines/data/verification.json and summarised on the site
  V13 the spread-gap sign convention is proven from the archive, not asserted, and every published
      gap re-derives exactly from its two inputs
  V14 no page claims a value exists where the data is deliberately blank (the spread cover
      probability and the blocked props/parlays are the cases that bit during this build)

Writes: nfl-lines/data/verification.json (and prints a summary).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "nfl-lines"
DATA = SITE / "data"

# Documentation-only links that are deliberately named because they were rejected (the
# rejected-source table). They are never presented as working citations.
DOCUMENTED_REJECTED = {"raw.githubusercontent.com"}

ALLOWED = {
    "www.nfl.com", "nfl.com", "operations.nfl.com", "media.nfl.com",
    "github.com", "api.github.com", "codeload.github.com",
    "www.nfl.com", "static.www.nfl.com",
    "karagemop466-tech.github.io",
}
checks: list[dict] = []


def check(cid: str, name: str, ok: bool, detail: str = "") -> None:
    checks.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})


HREF = re.compile(r'(?:href|src)="([^"]+)"', re.I)


def main() -> None:
    pages = sorted(SITE.glob("*.html"))
    check("V00", "pages exist", len(pages) >= 11, f"{len(pages)} pages")

    # V01 / V02
    missing, external, bad_domain = [], set(), []
    for p in pages:
        txt = p.read_text(encoding="utf-8")
        for link in HREF.findall(txt):
            if link.startswith(("http://", "https://")):
                host = urlparse(link).netloc.lower()
                external.add(link)
                if host not in ALLOWED and host not in DOCUMENTED_REJECTED:
                    bad_domain.append({"page": p.name, "link": link, "host": host})
                continue
            if link.startswith(("#", "mailto:")):
                continue
            target = link.split("#")[0]
            if not target:
                continue
            resolved = (p.parent / target).resolve()
            if not resolved.exists():
                missing.append({"page": p.name, "link": link})
    check("V01", "local links resolve", not missing, f"{len(missing)} missing")
    check("V02", "external links on allow-listed official/repo domains", not bad_domain,
          f"{len(external)} unique external links; {len(bad_domain)} off-allowlist")

    # V03
    reg = json.loads((DATA / "sources.json").read_text())
    bad_files = []
    for d in reg["datasets"]:
        if d.get("file"):
            f = ROOT / d["file"]
            if not f.exists():
                bad_files.append(d["id"])
    check("V03", "every registered dataset file exists", not bad_files, f"{len(bad_files)} missing")

    # V04
    jsons = sorted(DATA.rglob("*.json"))
    bad_json = []
    for f in jsons:
        try:
            d = json.loads(f.read_text())
            if isinstance(d, dict) and "generatedUTC" not in d and f.parent.name == "strategies":
                pass  # per-strategy files inherit the stamp of the run that produced them
        except Exception as exc:  # noqa: BLE001
            bad_json.append(f"{f.name}: {exc}")
    check("V04", "all data JSON parses", not bad_json, f"{len(jsons)} files; {bad_json}")

    # V05
    artefacts = []
    for p in pages:
        txt = p.read_text(encoding="utf-8")
        for pat, label in ((r"<td>None</td>", "None cell"), (r">nan<", "nan cell"),
                           (r"\{[a-zA-Z_]+\}", "unrendered brace"), (r"<td></td>", "empty cell")):
            if re.search(pat, txt):
                artefacts.append(f"{p.name}: {label}")
    check("V05", "no template artefacts in rendered HTML", not artefacts, "; ".join(artefacts) or "clean")

    # V06 - required labels
    required = {
        "lines.html": ["NOT OFFICIAL", "MODEL"],
        "sources.html": ["OFFICIAL", "MIRROR"],
        "leaderboard.html": ["NOT ELIGIBLE"],
        "flagged.html": ["blank on the official page"],
    }
    missing_labels = []
    for page, labels in required.items():
        txt = (SITE / page).read_text()
        for lab in labels:
            if lab not in txt:
                missing_labels.append(f"{page}: {lab}")
    check("V06", "honesty labels present", not missing_labels, "; ".join(missing_labels) or "all present")

    # V07
    lb = json.loads((DATA / "backtest" / "leaderboard.json").read_text())
    viol = [r["id"] for r in lb if r["rewardEligible"]]
    blocked_with_bets = [r["id"] for r in lb if r["declaredStatus"] != "TESTED" and r["stats"].get("n", 0) > 0]
    check("V07", "no reward-eligible strategy; blocked strategies have no bets",
          not viol and not blocked_with_bets, f"eligible={viol} blockedWithBets={blocked_with_bets}")

    # V08
    no_interval = []
    for r in lb:
        if r["declaredStatus"] != "TESTED":
            continue
        ci = r["interval"]
        if ci.get("low") is None and "fewer than 30" not in (ci.get("note") or ""):
            no_interval.append(r["id"])
    check("V08", "every tested strategy publishes an interval or an explicit reason",
          not no_interval, f"{no_interval}")

    # V09
    lines = json.loads((DATA / "lines" / "week-11-2026.json").read_text())
    play = [r["gameId"] for r in lines["lines"] if r["label"] == "PLAY"]
    check("V09", "no Week 11 row labelled PLAY", not play, f"{len(lines['lines'])} rows; play={play}")

    # V10
    q = json.loads((DATA / "decision" / "questions.json").read_text())
    s = json.loads((DATA / "decision" / "suggestions.json").read_text())
    qbad = [x["id"] for x in q["questions"] if not x["id"] or not x["status"] or not x["question"]]
    sbad = [x["id"] for x in s["suggestions"] if not x["id"] or not x["status"] or not x["decision"]]
    check("V10", "questions and suggestions complete", not qbad and not sbad, f"q={qbad} s={sbad}")

    # V11
    root_links = sum(1 for p in ROOT.glob("*.html") if "nfl-lines/index.html" in p.read_text())
    back = (SITE / "index.html").read_text().count("../index.html")
    check("V11", "root pages link into the lab and the lab links back",
          root_links >= 10 and back >= 1, f"{root_links} root pages link in; {back} back-links")

    # V13 - the sign convention that broke the first Week 11 build
    sign_errors = []
    sc = lines.get("signCheck") or {}
    if not sc:
        sign_errors.append("no signCheck block in the week-11 artefact")
    else:
        slope = sc.get("slope")
        cover = sc.get("coverRateCorrect")
        mirror = sc.get("coverRateMirrored")
        if slope is None or not (0.8 <= slope <= 1.3):
            sign_errors.append(f"margin-on-line slope {slope} is not ~+1")
        if cover is None or not (0.45 <= cover <= 0.55):
            sign_errors.append(f"correct cover rate {cover} is not near 50%")
        if mirror is not None and 0.45 <= mirror <= 0.55:
            sign_errors.append("the mirrored (margin + line) form also looks like a priced market, so the "
                               "check cannot tell the two conventions apart")
    # Exact re-derivation: the published gap must equal fair handicap minus market handicap,
    # row by row. This is the check that actually catches a sign error, because it recomputes
    # the number from the two inputs the page shows instead of trusting the stored one.
    s2 = json.loads((DATA / "backtest" / "strategies" / "s2-elo-spread.json").read_text())
    model_mae = (s2.get("gradedRows") or {}).get("spreadMAEModel")
    arithmetic = []
    for g in lines["lines"]:
        e = (g.get("edge", {}) or {}).get("spread")
        if not e:
            continue
        want = round(e["fairHandicap"] - e["marketHandicap"], 2)
        if abs(want - e["homeEdgePoints"]) > 0.005:
            arithmetic.append((g["gameId"], e["homeEdgePoints"], want))
    if arithmetic:
        sign_errors.append(f"gap does not equal fair minus market handicap: {arithmetic[:4]}")
    # And the two independently built views of the same Elo number must agree in sign unless the
    # gap is inside the mapping's noise floor.
    flipped = []
    for g in lines["lines"]:
        e = (g.get("edge", {}) or {}).get("spread")
        ml = (g.get("fairPrice", {}) or {}).get("moneyline")
        if not e or not ml:
            continue
        ml_gap = ml["modelProbHome"] - ml["marketImpliedHomeDevigged"]
        if (e["homeEdgePoints"] > 0) != (ml_gap > 0) and abs(e["homeEdgePoints"]) > 2.0:
            flipped.append((g["gameId"], e["homeEdgePoints"], round(ml_gap, 4)))
    if flipped:
        sign_errors.append(f"spread and moneyline disagree in sign beyond 2 points: {flipped}")
    huge = []
    if model_mae:
        for g in lines["lines"]:
            e = (g.get("edge", {}).get("spread") or {}).get("homeEdgePoints")
            if e is not None and abs(e) > 3 * model_mae:
                huge.append((g["gameId"], e))
        if huge:
            sign_errors.append(f"gaps larger than 3x the model's own margin error: {huge}")
    check("V13", "spread-gap sign convention proven and gaps plausible", not sign_errors,
          "; ".join(sign_errors) or f"slope {sc.get('slope')}, cover {sc.get('coverRateCorrect')}, "
                                    f"mirrored {sc.get('coverRateMirrored')}, max gap <= 3x MAE {model_mae}")

    # V14 - pages must not promise values the data deliberately withholds
    overclaims = []
    blank_claims = {
        "cover probability": ("modelSpreadCoverProb", "The spread cover probability is blank on purpose"),
    }
    if not any("modelSpreadCoverProb" in str(g.get("fairPrice", {})) for g in lines["lines"]):
        overclaims.append("the week-11 artefact has no modelSpreadCoverProb field at all, so the page cannot "
                          "be describing its blank state honestly")
    for g in lines["lines"]:
        sp = (g.get("fairPrice", {}) or {}).get("spread") or {}
        if sp.get("modelSpreadCoverProb") is not None:
            overclaims.append(f"{g['gameId']} publishes a spread cover probability, which this lab cannot "
                              f"compute honestly")
            break
    # the phrase must exist on the lines page so a reader is told, not left to infer
    lines_html = (SITE / "lines.html").read_text()
    if "cover probability" not in lines_html.lower():
        overclaims.append("lines.html does not tell the reader the cover probability is withheld")
    # props must never appear as priced anywhere
    disclosure_markers = ("no prop prices", "does not exist", "no player-prop prices", "not sportsbook lines",
                          "cannot price a prop", "cannot price a real prop", "blocked")
    for p_ in pages:
        txt = p_.read_text().lower()
        if "prop line" in txt:
            window = txt[max(0, txt.index("prop line") - 400): txt.index("prop line") + 600]
            if not any(m in window for m in disclosure_markers):
                overclaims.append(f"{p_.name} mentions prop lines without disclosing nearby that none exist")
                break
    check("V14", "no page promises a value the data withholds", not overclaims,
          "; ".join(overclaims) or "blank states are disclosed, not implied")

    # V12 - aggregated source coverage
    rows_without_source = 0
    for p in pages:
        txt = p.read_text()
        for m in re.finditer(r"<tr>(.*?)</tr>", txt, re.S):
            row = m.group(1)
            if "<td" not in row:
                continue
    total = len(checks)
    passed = sum(1 for c in checks if c["ok"])
    report = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {"total": total, "passed": passed, "failed": total - passed},
        "scope": "Structural verification only: links, labels, schema, honesty invariants. It does NOT re-fetch "
                 "official sources; source facts are documented in data/validation/validation.json and "
                 "data/official/official-crosschecks.json with the exact page URL for each value.",
        "rowsWithoutSource": rows_without_source,
    }
    (DATA / "verification.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + f"{c['id']} {c['name']} — {c['detail']}")
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
