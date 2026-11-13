#!/usr/bin/env python3
"""Build the NFL Control Room: one page-set that answers "what do we know, what is
open, and what should we decide next" from the eight NFL surfaces already in this repo.

Every published row is traceable to a committed file and, where one exists, an official
source URL. Nothing here invents a number: figures are recomputed from the committed
records, and anything that cannot be confirmed is left blank and labelled.

Outputs
  data/control/decisions.json     one de-duplicated decision register
  data/control/suggestions.json   one de-duplicated suggestion register with options
  data/control/evidence.json      the evidence ledger (dataset -> rows, source, audit)
  data/control/strategies.json    every strategy proposed anywhere, with its gate state
  data/control/injuries.json      injury/depth deficiency ledger, verified live
  data/control/meta.json          build metadata and headline counts

Run: python3 tools/build_control.py
"""
from __future__ import annotations

import datetime as _dt
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "control")
os.chdir(ROOT)
os.makedirs(OUT, exist_ok=True)


def _stamp():
    """A stable build stamp: SOURCE_DATE_EPOCH if set, else the newest input file's mtime."""
    import time
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        stamp = int(epoch)
    else:
        newest = 0.0
        for pat in ("data/lines/*.json", "data/nfl-signals/*.json", "nfl/system/data/derived/*.json"):
            for f in glob.glob(pat):
                newest = max(newest, os.path.getmtime(f))
        stamp = int(newest) if newest else int(time.time())
    return _dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def write(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def sha12(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def entries(doc, *keys):
    for k in keys:
        if isinstance(doc, dict) and isinstance(doc.get(k), list):
            return doc[k]
    return doc if isinstance(doc, list) else []


# --------------------------------------------------------------------------- sources
# One register of the official sources this repository actually cites. The audit in
# tools/audit_control.py checks that the host is an official league or club domain.
OFFICIAL_HOSTS = (
    "nfl.com", "operations.nfl.com", "static.www.nfl.com", "statsapi.mlb.com", "mlb.com",
    "49ers.com", "chiefs.com", "packers.com", "houstontexans.com", "dallascowboys.com",
    "detroitlions.com", "colts.com", "seahawks.com", "commanders.com", "patriots.com",
    "giants.com", "steelers.com", "denverbroncos.com", "neworleanssaints.com",
    "newyorkjets.com", "azcardinals.com", "atlantafalcons.com", "baltimoreravens.com",
    "buffalobills.com", "panthers.com", "chicagobears.com", "bengals.com",
    "clevelandbrowns.com", "greenbaypackers.com", "jaguars.com", "raiders.com",
    "chargers.com", "therams.com", "miamidolphins.com", "vikings.com",
    "philadelphiaeagles.com", "buccaneers.com", "titansonline.com", "gostanford.com",
    "calbears.com", "westwoodonesports.com",
)
TRUSTED_SECONDARY_HOSTS = ("espn.com", "github.com", "codeload.github.com", "nfldata")

# --------------------------------------------------------------------------- decisions
# Each canonical decision names the source-register questions it was merged from, so a
# reviewer can always trace a row back to the page that raised it. The merge is by topic,
# never by inventing a new question that no existing register asked.
DECISION_SPEC = [
    dict(key="PRICE", area="Market data", blocking=True, status="open",
         question="Which market price will our own lines be compared against, and are we permitted to store and cite it?",
         why="Without a stored price there is no settlement, so no win rate, yield, edge or fair price can exist. "
             "This single decision blocks every monetary claim on every NFL page in this repository.",
         have="Nothing. No official NFL page publishes odds (probed by exact regex on week, game and stat pages: zero hits). "
              "One session parsed ESPN's public scoreboard odds block and labelled it a trusted secondary source, not an official feed.",
         missing="A licensed, timestamped feed of open and closing lines, plus permission to store and republish it.",
         close="Obtain a licensed feed, or decide in writing to run a study-only programme with no betting conclusion.",
         detracts="6 registers raise it", evidence_files=["nfl/system/data/derived/market.json", "data/nfl-analytics/market-odds-week-10-2026.json"],
         sources=["https://www.nfl.com/scores/2026/week-10"]),
    dict(key="SKILL", area="Validation", blocking=True, status="open",
         question="How many settled bets before a strategy may be called skill-based rather than lucky, and what correction is applied for testing many strategies?",
         why="A 55% hit rate over 40 bets is indistinguishable from a coin. Publishing one as skill is the failure mode this project exists to avoid.",
         have="A frozen gate set with explicit thresholds: minimum bets per family (30 team, 25 prop, 15 parlay), "
              "a paired sign-flip randomisation test and Benjamini-Hochberg across the whole family.",
         missing="Settled bets. Zero strategies have 100 settled bets against a stored price.",
         close="Run the forward ledger until the gate's own sample requirement is met, then read the gate rather than the ROI.",
         detracts="", evidence_files=["nfl/system/curated/validation-gates.json", "data/lines/leaderboard.json"],
         sources=["https://www.nfl.com/standings/"]),
    dict(key="REWARD", area="Governance", blocking=True, status="open",
         question="Is the leaderboard reward real money, an honour scoreboard, or paper points - and is any of it lawful for the owner in British Columbia?",
         why="Three registers ask the same thing and give three different defaults. Until it is answered the leaderboard cannot rank anybody without implying a claim it may not make.",
         have="A paper-only scoring design that is implemented and published empty, plus an explicit statement that no monetary reward is authorised.",
         missing="A written owner decision, and a legal check for the owner's jurisdiction (British Columbia, Canada).",
         close="Answer in one line and record it; the scoring code already supports either answer.",
         detracts="Low", evidence_files=["nfl/system/curated/suggestions.json", "lines-lab/data/derived/leaderboard.json"],
         sources=["https://www.nfl.com/"]),
    dict(key="TESTS", area="Market data", blocking=True, status="open",
         question="Which archive of closing lines is legitimate for back-testing, and are we allowed to reuse it?",
         why="The only historical line archive in this repository is a third-party GitHub dataset whose own documentation does not name the upstream source of its spread and total columns.",
         have="A model comparison against that archive (model MAE 10.17 points vs market 9.79 over 2016-25), published with the provenance gap stated.",
         missing="The archive's upstream source and licence, or a licensed replacement.",
         close="Identify the upstream provider and licence, or license a feed and rebuild the comparison.",
         detracts="", evidence_files=["data/nfl-lab/games-source.json"], sources=["https://github.com/nflverse/nfldata"]),
    dict(key="DEPTH", area="Injury &amp; depth", blocking=True, status="partly-answered",
         question="Where do verified 1st/2nd/3rd/4th string depth charts come from for all 32 clubs, and can a backup's quality be measured?",
         why="The owner's brief asks the system to know when a 2nd, 3rd or 4th string player replaces a starter. That needs a chart per club and a way to measure the drop-off.",
         have="32 club depth charts fetched from the clubs' own official sites; 31 parse (Houston publishes an image). "
              "Four clubs are marked 'unofficial' by the club itself. Replacement naming works and was verified live on Detroit.",
         missing="An official snap count per player, so 'who actually replaced whom' can be shown rather than inferred from a chart.",
         close="Ingest the official Game Book PDFs (they contain participation) or an official snap-count table, then join to the chart.",
         detracts="", evidence_files=["data/lines/depth-charts.json", "nfl/system/data/derived/depth.json"],
         sources=["https://www.detroitlions.com/team/depth-chart/", "https://www.49ers.com/team/depth-chart"]),
    dict(key="INJURY-TIMING", area="Injury &amp; depth", blocking=False, status="partly-answered",
         question="When is the official injury report published and updated, and which version is the one a decision may rely on?",
         why="A Friday practice report and a Sunday inactive list are different facts. Using the wrong one changes a line.",
         have="The official weekly report, captured as a point-in-time snapshot with the retrieval timestamp and per-row source URL.",
         missing="Any history before Week 10, and the 90-minute inactive list in machine-readable form.",
         close="Re-run the weekly capture before each decision point; treat the snapshot timestamp as part of the value.",
         detracts="", evidence_files=["data/lines/injuries.json", "nfl/system/data/derived/injuries.json"],
         sources=["https://www.nfl.com/injuries/"]),
    dict(key="PROPS", area="Markets", blocking=True, status="open",
         question="Which official or licensed source provides historical player-prop lines, and how is a prop settled when the player does not play?",
         why="The brief asks for player prop bets and prop combinations. Without a prop line there is nothing to bet against.",
         have="Measured relationships between official per-game player statistics: receiving yards and receptions r = 0.817 (n = 4,468); "
              "receiving yards and receiving touchdowns r = 0.429 (n = 4,468).",
         missing="Any prop price. No official NFL page publishes one.",
         close="License a prop feed; until then publish the statistical relationships and no prop recommendation.",
         detracts="", evidence_files=["data/lines/correlations.json"], sources=["https://www.nfl.com/stats/player-stats/"]),
    dict(key="CORR", area="Markets", blocking=False, status="partly-answered",
         question="What correlation applies between parlay legs, and should a same-game parlay be priced from the joint or from multiplied legs?",
         why="Multiplying legs assumes independence. Two legs on the same player are not independent, so the multiplied price is wrong in a known direction.",
         have="Measured: legs on the same player phi = 0.575 (n = 11,446); legs on different players in one game phi = 0.067 (n = 184,915); "
              "game total vs model moneyline rho = -0.047 (n = 681); margin vs total r = 0.0201 (n = 6,967).",
         missing="Prices, so the correlation can be turned into a hold figure that is quoted rather than declared.",
         close="Price from the measured joint; keep the measured phi as the input and never assume independence.",
         detracts="", evidence_files=["data/lines/correlations.json", "lines-lab/data/derived/correlation.json"],
         sources=["https://www.nfl.com/stats/player-stats/"]),
    dict(key="HFA", area="Model", blocking=False, status="answered",
         question="What is the correct home-field advantage, and is the near-zero 2026 figure real or a small-sample artefact?",
         why="Home-field is a free parameter in every spread model; guessing it moves every line.",
         have="Official finals for 2025 and 2026: 232 of 453 decided games went to the home team (51.2%; 90% Wilson interval 47.4-55.1%; "
              "95% bootstrap interval 47.0-56.1%; two-sided bootstrap p = 0.666). A separate model fit puts home advantage at 2.0 points.",
         missing="Nothing for a descriptive answer. It is not evidence of an edge because there is no price to beat.",
         close="Answered as a description. Re-run each season.",
         detracts="", evidence_files=["nfl/system/data/derived/homefield.json", "nfl/system/data/derived/skill.json"],
         sources=["https://www.nfl.com/standings/league/2026/REG"]),
    dict(key="BASELINE", area="Validation", blocking=False, status="answered",
         question="What baseline must every strategy beat, and why that one?",
         why="A model that beats a bad baseline proves nothing. The baseline has to be stated before the result is seen.",
         have="A pre-registered naive baseline per family, plus proper scoring (log loss, Brier, calibration error) rather than hit rate alone.",
         missing="Nothing.",
         close="Answered. Two independent strategy labs use the same rule, which is a cross-check rather than a duplicate.",
         detracts="", evidence_files=["nfl/system/curated/validation-gates.json", "data/lines/strategies.json"],
         sources=["https://www.nfl.com/standings/"]),
    dict(key="SAMPLE", area="Model", blocking=False, status="answered",
         question="How much official history exists, and is it enough to back-test at all?",
         why="A back-test on one partial season is a description, not a test.",
         have="1,170 official NFL games across 2024-2026 in the lines lab (840 with scores); 457 official finals in the decision system (272 from 2025, 185 from 2026).",
         missing="Full seasons before 2024 in the lines lab; the model lab uses 2016-2025 from a third-party archive.",
         close="Answered for what exists. Extending it is a data-acquisition task, not an open question.",
         detracts="", evidence_files=["data/lines/games.json", "nfl/system/data/official-results.json"],
         sources=["https://www.nfl.com/schedules/"]),
    dict(key="REST", area="Model", blocking=False, status="partly-answered",
         question="Which situational factors (rest, short weeks, travel) are derivable from official data, and are they signal or confound?",
         why="Rest is the factor most often claimed as an edge and most often a proxy for opponent quality.",
         have="Exact rest days from official kickoff dates (32 short-week games, minimum 4 days rest). One lab reports rest differential as its "
              "strongest measured signal with a wide interval; the same lab's leader is not distinguishable from luck.",
         missing="A design that separates rest from opponent strength, which needs a larger sample.",
         close="Pre-register a rest-only test and let the gate judge it; do not promote it on correlation alone.",
         detracts="", evidence_files=["nfl/system/data/derived/rest.json", "data/nfl-intel/model.json"],
         sources=["https://www.nfl.com/schedules/2026/by-week/week-10"]),
    dict(key="MODEL-CHECK", area="Model", blocking=False, status="answered",
         question="Do the separate NFL datasets in this repository agree with each other?",
         why="Eight sessions built eight surfaces. If their numbers disagree, none of them can be trusted and the reader cannot tell which to believe.",
         have="All four independent 2026 result captures agree on all 137 completed games (away score and home score, game by game). "
              "The Week 10 injury report parses identically in two independent parsers on all 296 rows, once a team-attribution defect was fixed.",
         missing="A standing check that runs on every commit - this session adds one for the injury and leaderboard files.",
         close="Answered, and now enforced: see tests/test_lines_integrity.py.",
         detracts="", evidence_files=["data/control/evidence.json"], sources=["https://www.nfl.com/scores/2026/week-10"]),
    dict(key="CHART-LABEL", area="Injury &amp; depth", blocking=False, status="partly-answered",
         question="Are the club depth charts official or unofficial, and does the published table say which?",
         why="Four clubs label their own published chart 'unofficial'. Showing '1st string' without that label claims more than the source does.",
         have="The club's own label is captured per row (chartLabel) and published on the control page. 32 charts fetched, 31 parsed.",
         missing="A consistent definition across clubs: the chart formats differ, so '1st' means what each club means by it.",
         close="Keep the club's own label on every row and filter by it; do not normalise tiers across clubs.",
         detracts="", evidence_files=["data/lines/depth-charts.json"],
         sources=["https://www.detroitlions.com/team/depth-chart/"]),
    dict(key="GOVERNANCE", area="Governance", blocking=False, status="open",
         question="Who signs off a suggestion, on what service level, and what stops an accepted suggestion from contradicting a verified table?",
         why="Six suggestion registers exist with six different review vocabularies. A reviewer cannot tell which one is authoritative.",
         have="This page: one merged register with a stated decision rule and a recommended default for every row.",
         missing="A named reviewer and a turnaround.",
         close="Record the reviewer in COORDINATION.md and use this page as the single decision log.",
         detracts="", evidence_files=["data/control/suggestions.json"], sources=["https://www.nfl.com/"]),
    dict(key="SCOPE", area="Governance", blocking=False, status="answered",
         question="Is this a betting programme or a research programme?",
         why="The brief asks to remove luck and build skill-based strategies; the honest answer depends on whether real money is involved.",
         have="Every page states the same boundary: no edge, no win rate and no yield is published, because no price and no settlement exist.",
         missing="Nothing.",
         close="Answered by the published boundary. Changing it is a decision above, not a data task.",
         detracts="", evidence_files=["data/control/meta.json"], sources=["https://www.nfl.com/"]),
]




# Each canonical decision lists the exact source-register question ids it merges. The audit
# tool checks every id exists in the register it claims, so a merge cannot point at nothing.
MERGES = {
    "D-PRICE": {"lines": ["QN-01", "QN-20", "QN-24"], "analytics": ["Q1", "Q4"],
                "intel": ["Q-ODDS", "Q-CLV"], "lab": ["Q02", "Q03"],
                "system": ["Q01", "Q02"]},
    "D-SKILL": {"lines": ["QN-02", "QN-03", "QN-22"], "analytics": ["Q9"],
                "intel": [], "lab": [], "system": ["Q03", "Q10", "Q18"]},
    "D-REWARD": {"lines": ["QN-12"], "analytics": ["Q11", "Q13"], "intel": ["Q-LEGAL"],
                 "lab": ["Q07"], "system": ["Q04"]},
    "D-TESTS": {"lines": ["QN-14", "QN-21"], "analytics": [], "intel": [], "lab": ["Q02", "Q13", "Q10"],
                "system": ["Q11"]},
    "D-DEPTH": {"lines": ["QN-05", "QN-08", "QN-16", "QN-19"], "analytics": ["Q7", "Q8", "Q14"],
                "intel": ["Q-DEPTH", "Q-SNAPS"], "lab": ["Q05", "Q11"],
                "system": ["Q05", "Q06", "Q07", "Q12"]},
    "D-INJURY-TIMING": {"lines": ["QN-04", "QN-09"], "analytics": ["Q6", "Q20"], "intel": ["Q-INJ-HIST", "Q-ROSTER"],
                        "lab": ["Q09", "Q14"], "system": ["Q13"]},
    "D-PROPS": {"lines": ["QN-07", "QN-10"], "analytics": ["Q5", "Q19"], "intel": ["Q-PROPS"], "lab": ["Q06"],
                "system": ["Q08"]},
    "D-CORR": {"lines": ["QN-11"], "analytics": ["Q10"], "intel": [], "lab": [], "system": ["Q08", "Q09"]},
    "D-HFA": {"lines": ["QN-06"], "analytics": [], "intel": ["Q-HFA", "Q-REST"], "lab": [], "system": []},
    "D-BASELINE": {"lines": [], "analytics": [], "intel": [], "lab": [], "system": ["Q15"]},
    "D-SAMPLE": {"lines": ["QN-15", "QN-23"], "analytics": ["Q2", "Q3"], "intel": [], "lab": ["Q12"],
                 "system": ["Q14"]},
    "D-REST": {"lines": ["QN-13"], "analytics": ["Q16"], "intel": ["Q-REST"], "lab": [], "system": ["Q16"]},
    "D-MODEL-CHECK": {"lines": ["QN-15", "QN-23"], "analytics": [], "intel": [], "lab": ["Q08"], "system": ["Q14"]},
    "D-CHART-LABEL": {"lines": ["QN-05", "QN-19", "QN-16"], "analytics": ["Q7"], "intel": ["Q-DEPTH"],
                      "lab": ["Q05"], "system": ["Q12"]},
    "D-GOVERNANCE": {"lines": [], "analytics": ["Q18"], "intel": ["Q-REVIEW", "Q-REFRESH"], "lab": [],
                     "system": ["Q17"]},
    "D-SCOPE": {"lines": ["QN-24"], "analytics": [], "intel": ["Q-LEGAL", "Q-SCALE"], "lab": ["Q01"], "system": []},
}

# Questions raised by a register that this merge deliberately does NOT turn into a decision,
# with the reason. Published so the merge cannot look like it silently dropped anything.
NOT_MERGED = [
    {"register": "lines/QN-17", "question": "Should weather be part of the model?",
     "reason": "No official machine-readable weather archive is cited anywhere in the repository, so there is no source to decide on. Deferred, not dropped: it is listed here.",
     "owner": "unassigned"},
    {"register": "lines/QN-18", "question": "How should trades, promotions and roster moves be handled?",
     "reason": "Folded into D-DEPTH as an input requirement rather than a separate decision.", "owner": "D-DEPTH"},
    {"register": "intel/Q-WEATHER", "question": "Which official weather source will totals origination use per stadium?",
     "reason": "Duplicate of lines/QN-17; same blocking fact (no cited archive).", "owner": "unassigned"},
    {"register": "intel/Q-TEAMSHEETS", "question": "Do official 90-minute inactives exist in machine-readable form?",
     "reason": "Folded into D-INJURY-TIMING as the specific artefact that would close it.", "owner": "D-INJURY-TIMING"},
    {"register": "intel/Q-BANKROLL", "question": "What bankroll and unit size does the leaderboard assume for the quarter-Kelly parlay cap?",
     "reason": "Only meaningful once D-REWARD is answered. Listed here so it is not lost.", "owner": "D-REWARD"},
    {"register": "analytics/Q12", "question": "What staking rule removes overfitting and blow-up risk?",
     "reason": "Only meaningful once D-REWARD is answered.", "owner": "D-REWARD"},
    {"register": "analytics/Q17", "question": "How can closing-line value be measured without a verified market source?",
     "reason": "It cannot. Folded into D-PRICE.", "owner": "D-PRICE"},
    {"register": "lab/Q04", "question": "Is there enough history to test starting-QB injury signals?",
     "reason": "A sample-size question inside D-SAMPLE; the repository holds 11 seasons of QB injury rows (data/nfl-lab/injuries-qb-2016-2026.json).",
     "owner": "D-SAMPLE"},
]


def decision_sources():
    """The five question registers this merge reads, keyed by register name."""
    return {
        "lines": entries(load("data/lines/questions.json"), "questions"),
        "analytics": entries(load("data/nfl-analytics/questions.json"), "questions"),
        "intel": entries(load("data/nfl-intel/questions.json"), "questions"),
        "lab": entries(load("data/nfl-lab/questions.json"), "questions"),
        "system": entries(load("nfl/system/curated/questions.json"), "questions"),
    }


def build_decisions():
    q = decision_sources()
    rows = []
    for spec in DECISION_SPEC:
        row = dict(spec)
        row["id"] = "D-" + spec["key"]
        merged = []
        for reg, ids in MERGES.get(row["id"], {}).items():
            pool = {e.get("id"): e for e in q[reg]}
            for qid in ids:
                e = pool.get(qid)
                if e is None:
                    raise SystemExit(f"{row['id']} names {reg}/{qid}, which does not exist")
                merged.append({"register": reg, "id": qid,
                               "question": e.get("question"),
                               "raisedText": (e.get("known") or e.get("have") or e.get("haveNow") or ""),
                               "missingText": (e.get("missing") or e.get("gap") or e.get("required") or "")})
        row["mergedFrom"] = merged
        row["mergeCount"] = len(merged)
        rows.append(row)
    return rows, q


# --------------------------------------------------------------------------- suggestions
# The merged suggestion register. Every row carries the register id(s) it came from and a
# recommended option, but no recommendation is implemented by this session: the page is a
# review board, and the recommended path is a default a reviewer can accept or reject.
SUGGESTION_SPEC = [
    dict(id="CS-01", area="Consolidation", priority="P1",
         title="Make this Control Room the single entry point and mark the other eight NFL surfaces as evidence stores",
         problem="Eight sessions built eight NFL surfaces. A reader cannot tell which is authoritative, and the same question is answered four ways.",
         options=[
             dict(id="A", label="Publish this page as the entry point and leave every existing surface exactly as it is",
                  path="Navigation points here first; each other section is labelled for what it is.",
                  tradeoff="Cheap, reversible, discards nothing. The duplication stays and will drift.",
                  recommended=True),
             dict(id="B", label="Redirect the older surfaces into this one and retire their pages",
                  path="One section, one data pipeline.",
                  tradeoff="Cleanest to read, but deletes other sessions' published work and their verifiers. Not reversible in one step."),
             dict(id="C", label="Leave everything as it is",
                  path="No change.",
                  tradeoff="No cost today; the drift already found in this audit (three defects) gets worse."),
         ],
         evidence="data/control/meta.json lists all nine surfaces and their row counts.",
         sources=["https://www.nfl.com/"]),
    dict(id="CS-02", area="Market data", priority="P1",
         title="Either license a price feed or rename every page so it cannot be read as a betting recommendation",
         problem="D-PRICE is open. Without a stored price, no win rate, yield, edge or fair price can be computed, yet a dozen pages discuss strategies.",
         options=[
             dict(id="A", label="License a timestamped open/close feed",
                  path="Store every quote with its timestamp and vendor; grade against the close.",
                  tradeoff="Cost and a licence review. Unlocks every gate at once.",
                  recommended=True),
             dict(id="B", label="Keep the declared reference price and label the programme 'study only' everywhere",
                  path="No monetary claim is ever made; the -110 convention is stated as a convention.",
                  tradeoff="Free and already implemented. Permanently caps what can be concluded."),
             dict(id="C", label="Use the ESPN public odds block as a market reference",
                  path="Cite ESPN per row and label it a trusted secondary source.",
                  tradeoff="Not an official league feed; one session already does this on one page. Licence for storage is unclear."),
         ],
         evidence="nfl/system/data/derived/market.json (priceFeedAvailable: false).",
         sources=["https://www.nfl.com/scores/2026/week-10"]),
    dict(id="CS-03", area="Validation", priority="P1",
         title="Freeze one gate set across all three strategy labs instead of three different ones",
         problem="The lines lab uses G1-G7, the decision system uses G1-G10, the model lab uses G0-G9. A strategy passing in one may fail in another, and the reader cannot compare them.",
         options=[
             dict(id="A", label="Adopt one named gate set, versioned and frozen, and map the other two onto it",
                  path="Publish a mapping table so no result is invalidated, only relabelled.",
                  tradeoff="Some real work to reconcile thresholds; makes every result comparable.",
                  recommended=True),
             dict(id="B", label="Publish a crosswalk without changing any gate",
                  path="A table that shows how each lab's gates correspond.",
                  tradeoff="Cheap. Three vocabularies remain."),
             dict(id="C", label="Keep three gate sets",
                  path="No change.",
                  tradeoff="A reader who compares two labs can reach two different conclusions about the same strategy."),
         ],
         evidence="nfl/system/curated/validation-gates.json vs data/lines/strategies.json gate map.",
         sources=["https://www.nfl.com/standings/"]),
    dict(id="CS-04", area="Injury &amp; depth", priority="P1",
         title="Publish an official-snap-count join so 'next man up' is measured, not inferred from a chart",
         problem="D-DEPTH is partly answered. The replacement is named from the club's own chart, but nothing proves the replacement actually played.",
         options=[
             dict(id="A", label="Parse the official Game Book PDFs for participation",
                  path="Every game page links a Game Book; participation is printed in it.",
                  tradeoff="PDF parsing is brittle, and the brief forbids guessing. Would need a per-game check.",
                  recommended=True),
             dict(id="B", label="Use an official snap-count table if one exists",
                  path="Check nfl.com stats pages for a snap-count category.",
                  tradeoff="Only viable if such a table is published officially; not confirmed in this pass."),
             dict(id="C", label="Keep naming the chart replacement and label it 'projected'",
                  path="What is published today.",
                  tradeoff="Honest but not measured, and the owner's brief asks for the measured version."),
         ],
         evidence="data/lines/lineup-risk.json (replacement populated on 71 of 165 rows; depth chart is the source).",
         sources=["https://www.detroitlions.com/team/depth-chart/"]),
    dict(id="CS-05", area="Injury &amp; depth", priority="P2",
         title="Only raise lineup-risk rows against the week the injury snapshot belongs to",
         problem="The single Week 10 injury snapshot is currently applied to weeks 10 through 18 fixtures, which reads as a projection it cannot support.",
         options=[
             dict(id="A", label="Restrict the table to the current and next week",
                  path="Filter on week, and say so on the page.",
                  tradeoff="Loses the long view; removes a misleading implication.",
                  recommended=True),
             dict(id="B", label="Keep every week and label the column 'as of Week 10'",
                  path="One added label.",
                  tradeoff="Cheap; a reader who skims still sees a Week 18 injury against a Week 18 game."),
             dict(id="C", label="Capture a new injury snapshot for every week",
                  path="Weekly data acquisition in CI.",
                  tradeoff="Correct, and more moving parts."),
         ],
         evidence="data/lines/lineup-risk.json: 69 of 165 rows are for weeks 11-18. Recorded as FL-16.",
         sources=["https://www.nfl.com/injuries/"]),
    dict(id="CS-06", area="Data integrity", priority="P1",
         title="Run every cross-surface consistency check on every commit, not once",
         problem="This audit found three published defects that every existing verifier had passed: a whole-file team misattribution, a leaderboard/strategy disagreement, and a statistical test that could only return 1.000.",
         options=[
             dict(id="A", label="Wire the new tests into CI and add a cross-register audit step",
                  path="tests/test_lines_integrity.py plus tools/audit_control.py in the existing workflow.",
                  tradeoff="A few seconds per run; catches the class of defect that was invisible before.",
                  recommended=True),
             dict(id="B", label="Run the audit on demand only",
                  path="Manual.",
                  tradeoff="The same defects return on the next rebuild."),
             dict(id="C", label="Add a fourth verifier instead of extending the existing ones",
                  path="More code, more places to disagree.",
                  tradeoff="Unnecessary; the existing verifiers are healthy, they simply did not test this."),
         ],
         evidence="data/control/audit.json records A01-A03 with the check that now catches each.",
         sources=["https://www.nfl.com/injuries/"]),
    dict(id="CS-07", area="Governance", priority="P1",
         title="Record the reward decision in one line before any strategy is ranked",
         problem="D-REWARD is open. Three registers give three defaults (paper points, credits, honour system), so a ranking implies a claim no one has agreed to.",
         options=[
             dict(id="A", label="Paper points only, published empty until a strategy passes every gate",
                  path="Already implemented.",
                  tradeoff="Nothing to gain materially; nothing to get wrong legally.",
                  recommended=True),
             dict(id="B", label="Non-monetary rewards (credits, badges, research access)",
                  path="Needs a rule for what a credit is worth, and one line on why it is not gambling.",
                  tradeoff="More motivating; more governance."),
             dict(id="C", label="Cash prizes",
                  path="Requires a legal opinion for British Columbia before anything is announced.",
                  tradeoff="Highest risk of the three. Not recommended without the opinion."),
         ],
         evidence="nfl/system/curated/suggestions.json; lines-lab/data/derived/leaderboard.json (paper points only).",
         sources=["https://www.nfl.com/"]),
    dict(id="CS-08", area="Presentation", priority="P2",
         title="Put the honest negative result where a reader meets it first",
         problem="The strongest result in the whole programme is a negative one: the leading model is not distinguishable from luck (t = 1.48, 95% interval spanning zero). It is currently buried in a back-test page.",
         options=[
             dict(id="A", label="Lead every NFL page with the negative result and the sample it would need",
                  path="One sentence and one number at the top.",
                  tradeoff="Makes the site less exciting and more trustworthy.",
                  recommended=True),
             dict(id="B", label="Keep it on the back-test page only",
                  path="No change.",
                  tradeoff="A reader who never opens that page will assume a validated edge exists."),
             dict(id="C", label="Remove the negative result because the sample is small",
                  path="Not recommended.",
                  tradeoff="Removing a true measurement because it is inconvenient is the failure this project is built to avoid."),
         ],
         evidence="data/nfl-signals/signals.json luck.S2-netpoints (nForTwoSigma 182).",
         sources=["https://www.nfl.com/standings/"]),
    dict(id="CS-09", area="Model", priority="P2",
         title="Publish one originated line per game with its uncertainty, and stop presenting the point estimate alone",
         problem="Lines are published as a single number. A model whose spread standard error is over a point is being read as if it were exact.",
         options=[
             dict(id="A", label="Publish an interval with every originated line",
                  path="One extra column per row.",
                  tradeoff="Adds a column; stops a number being read as a price.",
                  recommended=True),
             dict(id="B", label="Publish the point estimate and state the error separately",
                  path="Already partly done.",
                  tradeoff="Requires the reader to hold two pages at once."),
             dict(id="C", label="Keep one number per game",
                  path="No change.",
                  tradeoff="Encourages false precision."),
         ],
         evidence="data/nfl-intel/model.json sigma_margin 13.18; data/nfl-lab/model-params.json test_mae 10.167.",
         sources=["https://www.nfl.com/schedules/"]),
    dict(id="CS-10", area="Scope", priority="P2",
         title="Decide whether the two same-team receiver correlations should be pooled before either is quoted",
         problem="Two measurements of the same structure disagree by design: r = -0.82 on 6 matched games (five players, one team) and phi = +0.575 for two props on the same player across 11,446 pairs. They answer different questions but read as contradictory.",
         options=[
             dict(id="A", label="Quote both with their definitions, and quote the large-sample figure as the default for pricing",
                  path="One glossary row per figure.",
                  tradeoff="Honest; the reader must read the definitions.",
                  recommended=True),
             dict(id="B", label="Quote only the large-sample figure",
                  path="Simpler.",
                  tradeoff="Hides that the small sample contradicts it in sign, which is itself informative."),
             dict(id="C", label="Quote only the small-sample figure",
                  path="Not recommended.",
                  tradeoff="Presents a six-game correlation as if it were a property of the league."),
         ],
         evidence="data/lab/analysis.json correlations[0] vs data/lines/correlations.json parlayCorrelations[1].",
         sources=["https://www.nfl.com/players/justin-jefferson/stats/logs/", "https://www.nfl.com/stats/player-stats/"]),
    dict(id="CS-11", area="Data integrity", priority="P2",
         title="Separate 'official' from 'the club says unofficial' in every depth chart row",
         problem="Four clubs label their own published chart 'unofficial'. A table that shows '1st string' without that label overstates what the source says.",
         options=[
             dict(id="A", label="Show the club's own label on every row and filter by it",
                  path="A boolean column taken from the club's page text.",
                  tradeoff="One more column; removes an overstatement.",
                  recommended=True),
             dict(id="B", label="Treat all club charts as equal",
                  path="No change.",
                  tradeoff="Flattens a distinction the clubs themselves make."),
             dict(id="C", label="Use only the clubs that label their chart official",
                  path="Consistent, but drops most of the league.",
                  tradeoff="Loses coverage the owner asked for."),
         ],
         evidence="data/lines/depth-charts.json club 'chartLabel'; Detroit's page reads '2026 Unofficial Depth Chart'.",
         sources=["https://www.detroitlions.com/team/depth-chart/"]),
    dict(id="CS-12", area="Presentation", priority="P3",
         title="Put one number on the page a reader is asked to remember: how many settled bets exist",
         problem="Every page explains at length that no strategy is validated. None leads with the one number that makes it concrete: zero settled bets.",
         options=[
             dict(id="A", label="Show 'settled bets: 0' as a headline tile on every NFL page",
                  path="Read from the forward ledger.",
                  tradeoff="Blunt and accurate.",
                  recommended=True),
             dict(id="B", label="Explain it in prose",
                  path="What is done today.",
                  tradeoff="Prose is searchable but not memorable."),
             dict(id="C", label="Show the paper-bet count instead",
                  path="Would read as progress that does not exist.",
                  tradeoff="Paper candidates are not settled bets; conflating them is the mistake to avoid."),
         ],
         evidence="data/nfl-signals/forward-ledger.json: 41 frozen rows, 0 settled.",
         sources=["https://www.nfl.com/"]),
]


def build_suggestions():
    rows = []
    for spec in SUGGESTION_SPEC:
        row = dict(spec)
        recs = [o for o in row["options"] if o.get("recommended")]
        row["recommendedOption"] = recs[0]["id"] if recs else None
        row["reviewState"] = "open"
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- evidence
# The ledger. Each entry states what the dataset is, how many rows it actually holds
# (counted here, not copied from a page), where it came from, and what it cannot tell you.
def count_rows(obj):
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        for k in ("rows", "games", "results", "leaderboard", "strategies", "bets", "entries",
                  "flags", "clubs", "players", "lines", "questions", "suggestions", "requirements"):
            if isinstance(obj.get(k), list):
                return len(obj[k])
    return None


EVIDENCE_FILES = [
    ("data/lines/games.json", "Official NFL game index (2024-2026) with scores where final",
     "NFL.com by-week schedule pages", "https://www.nfl.com/schedules/", "Score for 2026 regular season; no price."),
    ("data/lines/boxscores.json", "Official per-player box score rows",
     "NFL.com game pages", "https://www.nfl.com/games/", "Printed statistics only; no snap counts."),
    ("data/lines/injuries.json", "Official Week 10 2026 injury report",
     "NFL.com official injury report", "https://www.nfl.com/injuries/", "One point-in-time snapshot; no history."),
    ("data/lines/depth-charts.json", "Official club depth charts (32 clubs)",
     "Club websites, list from nfl.com/teams", "https://www.nfl.com/teams/", "Charts, not lineups. Houston is an image."),
    ("data/lines/lineup-risk.json", "Injury x depth deficiency ledger for upcoming fixtures",
     "Derived from the two files above", "https://www.nfl.com/injuries/", "Projection from a chart; not a snap count."),
    ("data/lines/correlations.json", "Measured correlations between stats and between bet legs",
     "Derived from official box scores", "https://www.nfl.com/stats/player-stats/", "Relationships, not prices."),
    ("data/lines/strategies.json", "18 candidate strategies with gate results and per-bet ledger",
     "Derived from official games and box scores", "https://www.nfl.com/schedules/", "Scored at a declared -110 reference price, not a market quote."),
    ("data/lines/leaderboard.json", "Ranked strategies and paper reward",
     "Derived from strategies.json", "https://www.nfl.com/standings/", "Paper points only; no money."),
    ("data/lab/player-logs-2026.json", "Official player game logs, 5 players, 2026 weeks 1-9",
     "NFL.com player log pages", "https://www.nfl.com/players/justin-jefferson/stats/logs/", "8 games per player; a small sample."),
    ("data/lab/analysis.json", "Dispersion, correlations and sample-size arithmetic",
     "Derived from the player logs", "https://www.nfl.com/players/justin-jefferson/stats/logs/", "Descriptive statistics only."),
    ("data/nfl-signals/signals.json", "Walk-forward model signals, leaderboard, gates and luck tests",
     "Derived from the official capture", "https://www.nfl.com/scores/2026/week-10", "100 scoreable games; the leader is not distinguishable from luck."),
    ("data/nfl-signals/forward-ledger.json", "Frozen forward predictions awaiting settlement",
     "Derived", "https://www.nfl.com/scores/", "0 settled. Nothing can be graded yet."),
    ("data/nfl-intel/model.json", "Opponent-adjusted ratings and originated lines",
     "Derived from verified finals", "https://www.nfl.com/schedules/", "16.9% of 32 clubs complete 2026 data at capture; market columns blank."),
    ("data/nfl-analytics/market-odds-week-10-2026.json", "ESPN public odds block, copied verbatim",
     "ESPN scoreboard API (trusted secondary, not official)", "https://www.espn.com/nfl/scoreboard", "Not an official league feed; licence to store is unclear."),
    ("nfl/system/data/official-results.json", "Official finals for 2025 and 2026",
     "NFL.com by-week pages", "https://www.nfl.com/schedules/", "Only cards that read FINAL."),
    ("nfl/system/data/official-injuries.json", "Official injury report, two seasons",
     "NFL.com injury pages", "https://www.nfl.com/injuries/", "Snapshot; week 1-10 2026 and all 2025."),
    ("nfl/system/data/derived/skill.json", "Home-field, Brier and shuffle-test arithmetic",
     "Derived from official finals", "https://www.nfl.com/standings/", "Outcome randomness only; not strategy skill."),
    ("nfl/system/data/derived/depth.json", "Depth-chart entries by club and tier",
     "Club sites via nfl.com/teams", "https://www.nfl.com/teams/", "A chart is not a lineup."),
    ("lines-lab/data/nfldata", "Third-party game archive with spread and total columns",
     "nflverse/nfldata on GitHub (third party)", "https://github.com/nflverse/nfldata", "Upstream source of the line columns is not documented by the archive."),
    ("lines-lab/data/derived/leaderboard.json", "Held-out model evaluation 2020-2025",
     "Derived from the third-party archive", "https://github.com/nflverse/nfldata", "Paper points only; no monetary reward authorised."),
    ("strategy-lab/data/analysis.json", "137 verified finals, ratings, walk-forward back-test",
     "NFL.com pages", "https://www.nfl.com/scores/", "One partial season."),
    ("data/nfl-lab/games-source.json", "Provenance record for the third-party archive",
     "nflverse/nfldata", "https://github.com/nflverse/nfldata", "Records SHA-256 of every archived file."),
]


def build_evidence():
    rows = []
    for path, what, provider, url, cannot in EVIDENCE_FILES:
        full = os.path.join(ROOT, path)
        n = None
        digest = None
        if os.path.isfile(full):
            n = count_rows(load(full))
            digest = sha12(full)
        elif os.path.isdir(full):
            files = sorted(glob.glob(os.path.join(full, "*")))
            n = len(files)
            digest = sha12(files[0]) if files else None
        rows.append({"path": path, "what": what, "provider": provider, "sourceUrl": url,
                     "cannotTell": cannot, "rows": n, "sha256_12": digest,
                     "exists": os.path.exists(full)})
    return rows


# --------------------------------------------------------------------------- strategies
def build_strategy_board():
    out = {"labs": [], "rows": []}
    # lines lab (G1-G7)
    lines_doc = load("data/lines/strategies.json")
    lb = {r["id"]: r for r in entries(load("data/lines/leaderboard.json"), "leaderboard")}
    for s in entries(lines_doc, "strategies"):
        gates = s.get("gates", {})
        passed = sum(1 for g in gates.values() if g.get("pass"))
        out["rows"].append({
            "lab": "Lines Lab (lines/)", "id": s["id"], "name": s.get("name"), "family": s.get("family"),
            "bets": s.get("metrics", {}).get("betsPlaced"),
            "roi": s.get("metrics", {}).get("roi"),
            "logLoss": s.get("metrics", {}).get("logLoss"),
            "gatesPassed": passed, "gatesTotal": len(gates),
            "reward": s.get("reward"), "status": s.get("status") or lb.get(s["id"], {}).get("status"),
            "sourceUrl": s.get("sourceUrl"),
            "note": s.get("rewardNote"),
        })
    out["labs"].append({"name": "Lines Lab", "path": "lines/strategies.html", "gates": "G1-G7",
                        "gateDoc": "lines/validation.html", "count": len(out["rows"])})
    # signals lab (S1-S4)
    sig = load("data/nfl-signals/signals.json")
    for e in entries(sig.get("leaderboard", {}), "entries"):
        out["rows"].append({"lab": "NFL Signals Lab (root)", "id": e.get("strategy"), "name": e.get("betType"),
                            "family": "single", "bets": e.get("n"), "roi": None, "logLoss": e.get("logLoss"),
                            "gatesPassed": None, "gatesTotal": None, "reward": None,
                            "status": "qualified" if e.get("qualified") else "failed",
                            "sourceUrl": "https://www.nfl.com/scores/2026/week-10",
                            "note": f"rank {e.get('rank')}; improvement over baseline {e.get('improvementVsBaseline')}"})
    out["labs"].append({"name": "NFL Signals Lab", "path": "nfl-signals.html", "gates": "G1-G8 (own vocabulary)",
                        "gateDoc": "nfl-signals-requirements.html", "count": len(entries(sig.get("leaderboard", {}), "entries"))})
    # system lab
    for s in entries(load("nfl/system/curated/strategies.json"), "strategies"):
        out["rows"].append({"lab": "NFL decision system (nfl/system/)", "id": s.get("id"), "name": s.get("name"),
                            "family": s.get("board"), "bets": None, "roi": None, "logLoss": None,
                            "gatesPassed": 0, "gatesTotal": 10, "reward": 0,
                            "status": s.get("status"), "sourceUrl": s.get("sourceUrl"),
                            "note": s.get("blockedBy")})
    out["labs"].append({"name": "NFL decision system", "path": "nfl/system/strategies.html", "gates": "G1-G10",
                        "gateDoc": "nfl/system/validation.html",
                        "count": len(entries(load("nfl/system/curated/strategies.json"), "strategies"))})
    # model lab - its register is keyed 'leaderboard', with gates G0-G9 in a dict
    nlab = load("data/nfl-lab/strategies.json")
    for s in entries(nlab, "leaderboard"):
        gates = s.get("gates", {})
        out["rows"].append({
            "lab": "NFL Model (nfl-lab/)", "id": s.get("strategy"), "name": s.get("kind"),
            "family": "single/parlay", "bets": s.get("test_n") or s.get("test_bets"),
            "roi": s.get("test_roi_at_110") or s.get("roi"),
            "logLoss": s.get("log_loss"), "gatesPassed": sum(1 for g in gates.values() if g.get("pass")),
            "gatesTotal": len(gates) or None,
            "reward": None,
            "status": "failed" if any(not g.get("pass") for g in gates.values()) else "qualified",
            "sourceUrl": "https://github.com/nflverse/nfldata",
            "note": "G0 provenance fails: the archive does not name the source of its line columns."})
    out["labs"].append({"name": "NFL Model", "path": "nfl-lab/strategies.html", "gates": "G0-G9",
                        "gateDoc": "nfl-lab/validation.html",
                        "count": len(entries(nlab, "leaderboard"))})
    # lines-lab
    ldl = entries(load("lines-lab/data/derived/leaderboard.json"), "rows")
    for s in ldl:
        gates = s.get("gates") or []
        out["rows"].append({
            "lab": "NFL Skill Lab (lines-lab/)", "id": s.get("strategy"), "name": s.get("strategy"),
            "family": "single", "bets": s.get("bets"),
            "roi": (s.get("roiPct") / 100.0) if isinstance(s.get("roiPct"), (int, float)) else None,
            "logLoss": s.get("logLoss"),
            "gatesPassed": sum(1 for g in gates if g.get("pass") is True),
            "gatesTotal": len(gates) or None,
            "reward": s.get("leaderboardPoints", 0),
            "status": "qualified" if s.get("passedAllMandatory") else "failed",
            "sourceUrl": "https://github.com/nflverse/nfldata",
            "note": f"win% {s.get('winPct')}; 95% CI on ROI {s.get('ci95')}"})
    out["labs"].append({"name": "NFL Skill Lab", "path": "lines-lab/leaderboard.html", "gates": "6 gates (own)",
                        "gateDoc": "lines-lab/method.html", "count": len(ldl)})
    # strategy-lab
    stl = load("strategy-lab/data/analysis.json").get("backtest", {})
    variants = stl.get("variants", {}) if isinstance(stl, dict) else {}
    for k, v in variants.items():
        summ = v.get("summary", v) if isinstance(v, dict) else {}
        out["rows"].append({
            "lab": "Strategy Lab (strategy-lab/)", "id": k, "name": k.replace("_", " "),
            "family": "walk-forward", "bets": summ.get("testGames"), "roi": None,
            "logLoss": summ.get("logLoss"), "gatesPassed": None, "gatesTotal": None, "reward": 0,
            "status": ("failed" if (summ.get("marginSkillVsZero") or 0) < 0 else "reported"),
            "sourceUrl": "https://www.nfl.com/scores/",
            "note": (f"margin MAE {summ.get('marginMAE')} vs zero baseline {summ.get('marginMAE_zeroBaseline')}; "
                     f"winner hit rate {summ.get('winnerHitRate')}")})
    out["labs"].append({"name": "Strategy Lab", "path": "strategy-lab/leaderboard.html", "gates": "own",
                        "gateDoc": "strategy-lab/requirements.html", "count": len(variants)})
    return out


# --------------------------------------------------------------------------- injuries
def build_injury_board():
    rows = entries(load("data/lines/injuries.json"), "rows")
    risk = entries(load("data/lines/lineup-risk.json"), "rows")
    charts = entries(load("data/lines/depth-charts.json"), "clubs")
    meta = load("data/lines/injuries.json").get("meta", {})
    clubs = {}
    for r in rows:
        c = clubs.setdefault(r["team"], {"team": r["team"], "reported": 0, "out": 0, "questionable": 0,
                                        "doubtful": 0, "practiceDnp": 0})
        c["reported"] += 1
        gs = (r.get("gameStatus") or "").lower()
        if gs == "out":
            c["out"] += 1
        elif gs == "questionable":
            c["questionable"] += 1
        elif gs == "doubtful":
            c["doubtful"] += 1
        if (r.get("practiceStatus") or "").startswith("Did Not"):
            c["practiceDnp"] += 1
    chart_by_club = {c["team"]: c for c in charts}
    for c in clubs.values():
        ch = chart_by_club.get(c["team"]) or {}
        c["chartParsed"] = bool(ch.get("units"))
        c["chartLabel"] = ch.get("chartLabel")
        c["chartSourceUrl"] = ch.get("sourceUrl")
        c["chartAsOf"] = ch.get("asOf")
    risks = []
    for r in risk:
        risks.append({k: r.get(k) for k in ("team", "opponent", "week", "date", "player", "position", "unit",
                                            "injury", "practiceStatus", "gameStatus", "depthTier",
                                            "depthTierVerified", "replacement", "replacementTier",
                                            "deficiency", "severity", "injurySourceUrl",
                                            "depthChartSourceUrl", "chartLabel")})
    return {
        "meta": {"sourceName": meta.get("sourceName"), "sourceUrl": meta.get("sourceUrl"),
                 "week": meta.get("week"), "retrievedUTC": meta.get("retrievedUTC"),
                 "reportedRows": len(rows), "clubsReporting": len(clubs),
                 "clubsWithParsedChart": sum(1 for c in clubs.values() if c["chartParsed"]),
                 "clubsWithoutChart": sorted(c["team"] for c in clubs.values() if not c["chartParsed"])},
        "clubs": sorted(clubs.values(), key=lambda c: c["team"]),
        "deficiencies": risks,
    }


def main():
    decisions, _ = build_decisions()
    suggestions = build_suggestions()
    evidence = build_evidence()
    board = build_strategy_board()
    injuries = build_injury_board()

    flags = entries(load("curated/flags.json"), "flags")
    line_flags = entries(load("data/lines/flags.json"), "flags")
    sites = [
        ("Control Room", "control/index.html", "this page"),
        ("NFL Lines Lab", "lines/index.html", "strategies, gates, correlations, injuries"),
        ("NFL Lines Lab (evidence)", "lab/index.html", "questions, measured correlations, injuries"),
        ("NFL Model", "nfl-lab/index.html", "model and back-test against a third-party archive"),
        ("NFL Decision Support", "nfl/index.html", "requirements, method, leaderboard design"),
        ("NFL decision system", "nfl/system/index.html", "official ingest, questions, suggestions"),
        ("NFL Signals Lab", "nfl-signals.html", "walk-forward signals and a forward ledger"),
        ("NFL Skill Lab", "lines-lab/index.html", "held-out evaluation, own lines"),
        ("Strategy Lab", "strategy-lab/index.html", "walk-forward back-test on 137 finals"),
        ("NFL Intel", "nfl-intel.html", "ratings and originated lines"),
        ("NFL Analytics", "nfl-analytics.html", "market capture and requirements"),
    ]
    meta = {
        # Deterministic: taken from the newest committed injury capture so a rebuild of an
        # unchanged tree produces a byte-identical file (and therefore no CI drift).
        "generatedUTC": _stamp(),
        "surfaces": [{"name": a, "path": b, "what": c} for a, b, c in sites],
        "counts": {
            "decisions": len(decisions),
            "decisionsBlocking": sum(1 for d in decisions if d["blocking"]),
            "decisionsAnswered": sum(1 for d in decisions if d["status"] == "answered"),
            "suggestions": len(suggestions),
            "evidenceDatasets": len(evidence),
            "strategies": len(board["rows"]),
            "strategyLabs": len(board["labs"]),
            "injuryRows": injuries["meta"]["reportedRows"],
            "clubsReporting": injuries["meta"]["clubsReporting"],
            "deficiencyRows": len(injuries["deficiencies"]),
            "flagsCombined": len(flags),
            "flagsLines": len(line_flags),
        },
        "settledBets": len([r for r in entries(load("data/nfl-signals/forward-ledger.json"), "rows")
                            if str(r.get("outcome") or r.get("settled") or "").lower() in ("win", "loss", "push", "true")]),
        "boundary": ("No market price, no settlement record and no forecast settlement exist in this repository. "
                     "No win rate, yield, edge or fair price is published anywhere on this site."),
    }
    write("decisions.json", {"meta": {"generatedUTC": meta["generatedUTC"]}, "decisions": decisions,
                             "notMerged": NOT_MERGED})
    write("suggestions.json", {"meta": {"generatedUTC": meta["generatedUTC"]}, "suggestions": suggestions})
    write("evidence.json", {"meta": {"generatedUTC": meta["generatedUTC"]}, "datasets": evidence})
    write("strategies.json", {"meta": {"generatedUTC": meta["generatedUTC"]}, **board})
    write("injuries.json", injuries)
    write("meta.json", meta)

    print(f"decisions {len(decisions)} ({meta['counts']['decisionsBlocking']} blocking)")
    print(f"suggestions {len(suggestions)}")
    print(f"evidence datasets {len(evidence)}")
    print(f"strategies across {len(board['labs'])} labs: {len(board['rows'])}")
    print(f"injury rows {injuries['meta']['reportedRows']} across {injuries['meta']['clubsReporting']} clubs; "
          f"deficiency rows {len(injuries['deficiencies'])}")


if __name__ == "__main__":
    main()
