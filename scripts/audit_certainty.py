#!/usr/bin/env python3
"""Publish epistemic limits; validate locally, never equate links with verification."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'verification/report.json').read_text())
sources = [
    ('Schedule completeness', 'No complete multi-sport and station-specific coverage certificate exists in the repository. Absence from a feed is not proof of no game.', 'https://www.nfl.com/schedules/'),
    ('Future MLB', 'Inherited 2027 dates and TBD flags require fresh official review; inherited 2028–29 calendar blocks are scenarios, not released fixtures.', 'https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2027&gameType=R'),
    ('Westwood One local carriage', 'Network affiliation alone does not establish that a specific station will carry a specific event. Local blackouts and programming conflicts must be checked.', 'https://www.westwoodonesports.com/station-finder/'),
    ('All Westwood One sports', 'The inherited event grid is not evidence of exhaustive future coverage or local carriage. Other sports remain high-priority candidates, not confirmed local broadcasts.', 'https://www.westwoodonesports.com/'),
    ('Game end times', 'Game lengths and overrun buffers are planning estimates. Regulation clocks and halftime rules do not establish real broadcast duration; future exact free minutes are unknown.', 'https://operations.nfl.com/the-rules/'),
    ('Stanford', 'Future opponents, dates and kickoff times require field-by-field source review. Conflicting inherited dates are not silently reconciled.', 'https://gostanford.com/sports/football/schedule'),
    ('Cal', 'An incomplete school schedule cannot certify that omitted days are free.', 'https://calbears.com/sports/football/schedule'),
    ('All-games versus AM/FM scope', 'Every MLB/NFL game may block personal-interest mode, but not every game has established terrestrial carriage in San Francisco.', 'https://www.mlb.com/giants/schedule/watch'),
    ('Verification strength', 'Inherited token checks can match unrelated parts of a page; snapshot matches are historical evidence, not live re-verification. Link and schema tests only validate structure.', 'https://www.nfl.com/schedules/'),
]
rows = ''.join('<tr><td>'+html.escape(a)+'</td><td>'+html.escape(b)+'</td><td>Needs review</td><td><a href="'+html.escape(c, quote=True)+'">Official reference</a></td></tr>' for a,b,c in sources)
page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Certainty audit · Free Time Vacation</title><link rel="stylesheet" href="assets/style.css"></head><body><header class="top"><div class="wrap topbar"><strong>FREE TIME / VACATION</strong><nav class="main"><a href="index.html">Dashboard</a><a href="extra/calendar.html">Scoreboard</a><a href="extra/vacation.html">Vacation</a><a href="extra/flagged.html">Flagged for Review</a></nav></div></header><main class="wrap"><h1>Flagged for Review: certainty audit</h1><p class="lede">Reviewed 2026-11-03. The plan now names a best window — the two weeks between the conference championships and the Super Bowl — and labels the evidence behind every part of it. None of it is a guarantee.</p><div class="callout"><strong>What “free” can mean here.</strong> A green interval is a model gap in loaded records. It is not a verified absence of live radio programming. Confirmed start times still have estimated end times. Unknown fields remain unknown.</div><h2>Executive finding</h2><p><strong>2027: Feb 1 – Feb 13 is the longest run with nothing on the radio (13 consecutive calendar days).</strong> The two anchors are official — MLB's 2027 season opens Mar 24/25 and runs to Sep 26, and Super Bowl LXI is Sun Feb 14, 2027 — while the NFL playoff round dates around it are modelled. 2028 (Jan 31 – Feb 12) and 2029 (Jan 29 – Feb 10) follow the same structure but are labelled ESTIMATION because neither season's schedule is released. Counting the Pro Bowl exhibition as well as league games shortens the clean run to six calendar days in every year.</p><p style="margin-top:8px">What is still not verified: every individual kickoff time, every game's real end time, and whether each event actually airs on a receivable AM/FM signal at an Outer Sunset address. Treat the window as a strongly evidenced planning target, not a certified booking guarantee.</p><h2>Evidence limits, line by line</h2><div class="scroll"><table><thead><tr><th>Area</th><th>Finding</th><th>Status</th><th>Reference</th></tr></thead><tbody>'''+rows+'''</tbody></table></div><h2>Verification disclosure</h2><p>Official references above are manual-review destinations, not a claim that their contents were freshly retrieved in this sandbox. Outbound access to official sports hosts is restricted. Inherited data and reports have not been relabelled as freshly verified.</p><p>Historical verification report: '''+html.escape(report.get('generatedUTC','unknown'))+'''. Its token checks are limited and include snapshot fallback. Complete line-by-line official validation and complete 94122 radio reception/carriage verification remain outstanding.</p><p><a href="verification/report.json">Historical source-check report</a> · <a href="verification/certainty.json">Current certainty policy</a> · <a href="extra/flagged.html">Inherited irregularities</a> · <a href="research/EXECUTIVE-SUMMARY.md">Executive summary</a></p><h2>Time and duration</h2><p>Display America/Los_Angeles (PST in winter, PDT in summer). No fixed PST conversion is used for the year-round plan. An average duration is not a guaranteed end time. Halftime is part of a football game's elapsed duration, not a separate sports-free interval.</p></main></body></html>'''
(ROOT / 'certainty.html').write_text(page)
# A persistent, prominent correction on inherited pages; all generators can run first.
for path in list(ROOT.glob('*.html')) + list((ROOT/'extra').glob('*.html')) + list((ROOT/'nfl-lines').glob('*.html')):
    if path.name == 'certainty.html':
        continue
    text = path.read_text()
    prefix = '../' if path.parent.name in ('extra', 'nfl-lines') else ''
    warning = ('<aside id="certainty-notice" class="callout warn" role="note"><strong>Planning estimates — not certified free time.</strong> '
               'Schedules and local AM/FM carriage are incomplete. Any “free”, “fully free”, “exact” or “verified gap” wording below describes loaded records only; it does not certify absence of games. '
               f'<a href="{prefix}certainty.html">Flagged for Review: certainty audit</a>.</aside>')
    text = re.sub(r'<aside id="certainty-notice".*?</aside>', '', text, flags=re.S)
    text = text.replace('<main class="wrap">', '<main class="wrap">'+warning, 1)
    path.write_text(text)
policy = {'reviewDate': '2026-11-03', 'completeCoverageCertified': False,
          'certifiedVacationWindows': {str(y): {str(n): None for n in (7,14,21)} for y in (2027,2028,2029)},
          'freshOfficialSourceVerification': False,
          'historicalReportUTC': report.get('generatedUTC'),
          'findings': [{'area':a, 'finding':b, 'status':'needs review', 'sourceUrl':c} for a,b,c in sources]}
(ROOT/'verification/certainty.json').write_text(json.dumps(policy, indent=2)+'\n')
# Fail if source links or prominent notices are lost.
for path in list(ROOT.glob('*.html')) + list((ROOT/'extra').glob('*.html')) + list((ROOT/'nfl-lines').glob('*.html')):
    assert path.name == 'certainty.html' or 'id="certainty-notice"' in path.read_text(), path
vacation = json.loads((ROOT/'extra/data/vacation.json').read_text())
assert all(not v['scheduleReleased'] and v['free'] == 0 for v in vacation['years'].values())
assert all(not w['fullyFree'] for year in vacation['windows'].values() for windows in year.values() for w in windows)
print('Certainty audit passed: no certified future windows; all published pages disclose incomplete coverage.')
