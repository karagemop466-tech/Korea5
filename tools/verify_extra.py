#!/usr/bin/env python3
"""Line-by-line verification of the combined site.

Checks:
  * every local href/src in root and extra HTML resolves to a real file;
  * every external link on the extra pages is on an approved official domain;
  * every data-table row in the extra pages has an official source link;
  * calendar/verification/vacation JSON integrity, blank-value and TBD rules;
  * exact ESTIMATION label presence, flag coverage, nav coverage, Prev/Next/Today labels.

Writes extra/data/link-report.json and extra/links.html. Exits 1 on any failure.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
EXTRA = ROOT / "extra"
DATA = EXTRA / "data"

EST_LABEL = "ESTIMATION — not a real verified released schedule"
APPROVED_DOMAINS = {
    "mlb.com", "www.mlb.com", "statsapi.mlb.com",
    "nfl.com", "www.nfl.com", "media.nfl.com", "operations.nfl.com",
    "49ers.com", "www.49ers.com",
    "gostanford.com", "www.gostanford.com",
    "calbears.com", "www.calbears.com",
    "westwoodonesports.com", "www.westwoodonesports.com",
    "thesportsleader.com", "www.thesportsleader.com",
    "espn.com", "www.espn.com",
    "ncaa.org", "www.ncaa.org", "ncaaorg.s3.amazonaws.com", "static.www.nfl.com",
    "collegefootballplayoff.com", "www.collegefootballplayoff.com",
    "karagemop466-tech.github.io", "buffedlizard55-lab.github.io",
    "profootballnetwork.com", "www.profootballnetwork.com",
    "github.com", "www.github.com",
    "images.sidearmdev.com", "dxbhsrqyrr690.cloudfront.net",
}

DATA_TABLE_IDS = ("nfltbl", "w1tbl", "sttbl", "antbl", "du1", "du2", "du3", "nftbl", "estbl", "srtbl", "flt")

checks = []
def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})

missing_local = []
external_domains = set()
extra_external_domains = set()
rows_missing_source = []
empty_attrs = []

html_files = sorted(list(ROOT.glob("*.html")) + list(EXTRA.glob("*.html")))
attr_re = re.compile(r'(?:href|src)="([^"]*)"', re.I)

for f in html_files:
    txt = f.read_text(encoding="utf-8")
    for raw in attr_re.findall(txt):
        if not raw.strip():
            empty_attrs.append((str(f.relative_to(ROOT)), raw))
            continue
        u = html.unescape(raw)
        if u.startswith(("http://", "https://")):
            host = urlparse(u).hostname or ""
            external_domains.add(host)
            if f.parent == EXTRA:
                extra_external_domains.add(host)
                if host not in APPROVED_DOMAINS:
                    check(f"external domain {host} on {f.name}", False, u)
            continue
        if u.startswith(("#", "mailto:", "data:", "javascript:")):
            continue
        path = u.split("#", 1)[0].split("?", 1)[0]
        if not path:
            continue
        target = (f.parent / path).resolve()
        generated_this_run = (target == (EXTRA / "links.html").resolve())
        if not target.exists() and not generated_this_run:
            missing_local.append({"file": str(f.relative_to(ROOT)), "link": u, "resolved": str(target)})
    # data-table rows need an official source link
    for tid in DATA_TABLE_IDS:
        m = re.search(r'<table[^>]*id="' + re.escape(tid) + r'"[^>]*>(.*?)</table>', txt, re.S | re.I)
        if not m:
            continue
        body = m.group(1)
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
            if "<th" in tr.lower():
                continue
            if 'href="http' not in tr:
                rows_missing_source.append({"file": f.name, "table": tid, "row": re.sub(r"<[^>]+>", " ", tr)[:160].strip()})

check("no empty href/src attributes", not empty_attrs, str(empty_attrs[:3]))
check("no broken local links", not missing_local, "; ".join(f'{x["file"]}: {x["link"]}' for x in missing_local[:5]))
check("no data-table row is missing an official source link", not rows_missing_source, str(rows_missing_source[:3]))
check("external links on extra pages use approved official domains", all(
    h in APPROVED_DOMAINS for h in extra_external_domains), ", ".join(sorted(h for h in extra_external_domains if h not in APPROVED_DOMAINS)))

# JSON integrity
def jload(p):
    return json.loads(p.read_text(encoding="utf-8"))

cal = jload(DATA / "calendar.json")
check("calendar covers 2026-11-02 to 2030-02-28", cal["meta"]["start"] == "2026-11-02" and cal["meta"]["end"] == "2030-02-28")
check("calendar has 1215 days", len(cal["days"]) == 1215, str(len(cal["days"])))
check("every calendar day has all five buckets", all(set(v) >= {"verified", "estimated", "tba", "anchors", "future"} for v in cal["days"].values()))
check("calendar verified rows all have start times", all(e["start"] for v in cal["days"].values() for e in v["verified"]))
check("calendar TBA rows all have blank start times", all(not e["start"] for v in cal["days"].values() for e in v["tba"]))
check("calendar rows all have source URLs", all(e.get("sourceUrl") for v in cal["days"].values() for g in ("verified", "estimated", "tba") for e in v[g]))

ver = jload(DATA / "verification.json")
check("build verification has zero failures", not ver["failures"], str(ver["failures"][:3]))
check("build verification has 16 checks", len(ver["checks"]) == 16, str(len(ver["checks"])))

vac = jload(DATA / "vacation.json")
check("vacation ranking covers 2027, 2028, 2029", set(vac["windows"]) == {"2027", "2028", "2029"})
check("2028 and 2029 are marked scheduleReleased=false", not vac["years"]["2028"]["scheduleReleased"] and not vac["years"]["2029"]["scheduleReleased"])
check("no 2027 window is fully free", not any(w["fullyFree"] for k in vac["windows"]["2027"] for w in vac["windows"]["2027"][k]))

# Curated files
for name in ("sources.json", "season-anchors.json", "stations.json", "durations.json", "ncaaf-future.json", "estimates.json", "flags.json", "rules.json"):
    try:
        jload(ROOT / "curated" / name)
        check(f"curated/{name} parses", True)
    except Exception as exc:  # noqa: BLE001
        check(f"curated/{name} parses", False, repr(exc))

est = jload(ROOT / "curated/estimates.json")
check("every estimate window carries exact ESTIMATION label", all(w["label"] == EST_LABEL for w in est["windows"]))
flag_ids = {f["id"] for f in jload(ROOT / "curated/flags.json")["flags"]}
flagged_html = (EXTRA / "flagged.html").read_text(encoding="utf-8")
check("all flag IDs appear on Flagged for Review page", all(fid in flagged_html for fid in flag_ids), str(sorted(fid for fid in flag_ids if fid not in flagged_html)))
check("Flagged for Review page is clearly labelled", "Flagged for Review" in flagged_html and EST_LABEL in flagged_html)
check("estimates page carries exact ESTIMATION label", EST_LABEL in (EXTRA / "estimates.html").read_text(encoding="utf-8"))
check("root pages link to the official-feed hub", all("extra/index.html" in p.read_text(encoding="utf-8") for p in ROOT.glob("*.html")))
cal_html = (ROOT / "calendar.html").read_text(encoding="utf-8")
check("root calendar has Prev, Next and Today buttons", all(s in cal_html for s in ("← Prev", "Next →", ">Today<")))
check("root dashboard Super Bowl wording corrected", "sits before Super Bowl LXI" in (ROOT / "index.html").read_text(encoding="utf-8"))
check("extra hub and all 14 extra pages exist", len(list(EXTRA.glob("*.html"))) >= 14, str(len(list(EXTRA.glob("*.html")))))

report = {
    "meta": {"name": "Combined line-by-line link and source verification", "compiledUTC": "2026-11-02"},
    "checks": checks,
    "counts": {
        "htmlFiles": len(html_files),
        "externalDomains": len(external_domains),
        "missingLocal": len(missing_local),
        "rowsMissingSource": len(rows_missing_source),
        "emptyAttrs": len(empty_attrs),
    },
    "missingLocal": missing_local,
    "rowsMissingSource": rows_missing_source,
    "externalDomains": sorted(external_domains),
}
(DATA / "link-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

# extra/links.html
def esc(v):
    return html.escape(str(v), quote=True)

PASS = '<span class="tag ver">PASS</span>'
FAIL = '<span class="tag flag">FAIL</span>'
APPROVED = '<span class="tag ver">approved</span>'
REVIEW = '<span class="tag flag">review</span>'
rows = "".join(
    f"<tr><td>{esc(c['name'])}</td><td>{PASS if c['ok'] else FAIL}</td><td>{esc(c['detail'])}</td></tr>"
    for c in checks)
domain_rows = "".join(f"<tr><td>{esc(d)}</td><td>{APPROVED if d in APPROVED_DOMAINS else REVIEW}</td></tr>" for d in sorted(external_domains))
missing_rows = "".join(f"<tr><td>{esc(m['file'])}</td><td>{esc(m['link'])}</td><td>{esc(m['resolved'])}</td></tr>" for m in missing_local)
doc = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Local link &amp; source-link report · FREE TIME VACATION</title>
<link rel="stylesheet" href="../assets/style.css"><link rel="stylesheet" href="assets/extra.css"></head>
<body><header class="top"><div class="wrap topbar"><div class="brand"><span class="dot"></span> FREE TIME / VACATION</div>
<nav class="main"><a href="index.html">Official feeds</a><a href="verification.html">Line-by-line verification</a><a href="links.html" class="active">Link report</a></nav></div></header>
<main class="wrap"><h1>Local link &amp; source-link report</h1>
<p class="lede">Every local <code>href</code>/<code>src</code> in the root and extra pages was resolved against the
filesystem. Every data-table row was checked for an official source link. External hosts are listed for manual review.</p>
<div class="callout"><strong>Result:</strong> {len(checks)} checks, {sum(1 for c in checks if c['ok'])} passed,
{sum(1 for c in checks if not c['ok'])} failed; {len(missing_local)} broken local links,
{len(rows_missing_source)} rows missing source links.</div>
<h2>Checks</h2><div class="scroll"><table><thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Broken local links</h2><div class="scroll"><table><thead><tr><th>File</th><th>Link</th><th>Resolved path</th></tr></thead><tbody>{missing_rows or '<tr><td colspan="3">None</td></tr>'}</tbody></table></div>
<h2>External hosts seen</h2><div class="scroll"><table><thead><tr><th>Host</th><th>Status</th></tr></thead><tbody>{domain_rows}</tbody></table></div>
<h2>Rows missing an official source link</h2><p class="small">{esc(len(rows_missing_source))} rows. See <code>extra/data/link-report.json</code>.</p>
</main><footer><div class="wrap"><p>Generated by <code>tools/verify_extra.py</code> · compiled 2026-11-02</p></div></footer></body></html>'''
(EXTRA / "links.html").write_text(doc, encoding="utf-8")

failed = [c for c in checks if not c["ok"]]
print(json.dumps({"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed),
                  "missingLocal": len(missing_local), "rowsMissingSource": len(rows_missing_source),
                  "failedNames": [c["name"] for c in failed]}, indent=2))
raise SystemExit(1 if failed else 0)
