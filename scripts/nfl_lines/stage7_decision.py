#!/usr/bin/env python3
"""Stage 7 - decision-support registers.

Two things are produced:

  questions.json   - every question that must be answered before a decision can be made,
                     each with: what we know, what we do not know, what the answer would
                     change, the exact discovery step, the source that can settle it, and
                     the current status (ANSWERED / UNVERIFIED / BLOCKED).
  suggestions.json - a reviewable board of improvement proposals, each scored on value,
                     cost, risk and reversibility, with a recommended path and the decision
                     the owner actually has to make. Nothing is implemented until chosen --
                     except the items already built in this lab, which are marked DONE so
                     the reviewer can see the current state.

Every question and suggestion carries a source URL where one exists. Items with no possible
official source say so instead of linking a guess.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "nfl-lines" / "data" / "decision"
SITE = ROOT / "nfl-lines"

S = {
    "nfl_sched": "https://www.nfl.com/schedules/",
    "nfl_inj": "https://www.nfl.com/injuries/",
    "nfl_inj_w10": "https://www.nfl.com/injuries/league/2026/reg10",
    "nfl_stats": "https://www.nfl.com/stats/",
    "nfl_player": "https://www.nfl.com/stats/player-stats/",
    "nfl_team": "https://www.nfl.com/stats/team-stats/",
    "nfl_stand": "https://www.nfl.com/standings/",
    "nfl_tx": "https://www.nfl.com/transactions/",
    "nfl_depth": "https://www.nfl.com/teams/detroit-lions/depth-chart",
    "nfl_roster": "https://www.nfl.com/teams/detroit-lions/roster",
    "ops": "https://operations.nfl.com/the-rules/",
    "nfldata": "https://github.com/nflverse/nfldata",
    "nfldata_data": "https://github.com/nflverse/nfldata/tree/master/data",
    "nflverse": "https://github.com/nflverse/nflverse-data",
    "mirror": "https://github.com/mgiancola9/nfl-predictions",
    "games_csv": "https://github.com/nflverse/nfldata/blob/master/data/games.csv",
    "closing_csv": "https://github.com/nflverse/nfldata/blob/master/data/closing_lines.csv",
}

QUESTIONS = [
    # ---------------- data provenance
    dict(id="Q01", area="Data provenance", priority="blocking",
         question="Are the market prices this lab measures against official NFL values?",
         known="No. The archive's closing spread/total/moneyline come from the nflverse nfldata repository. "
               "The official NFL schedule pages carry no betting prices at all.",
         unknown="Which sportsbook or consensus produced each price, and the exact minute each was captured.",
         missingInfo="A price-level provenance field (book, capture timestamp) that the archive does not carry.",
         wouldChange="Whether any ROI figure can be called an 'official' price comparison. Today it cannot.",
         discovery="Re-check nfl.com schedule payloads for price keys (done: none) and, if a licensed price feed "
                   "is purchased, re-run the backtest against it.",
         source=S["nfl_sched"], status="ANSWERED-NO",
         answer="No — prices are non-official and are labelled NOT OFFICIAL on every page."),
    dict(id="Q02", area="Data provenance", priority="blocking",
         question="Does the results/schedule mirror agree with the league's own published numbers?",
         known="Yes, at the aggregate level. All 32 clubs' 2026 records and points for/against match "
               "nfl.com/standings exactly, and both recent Super Bowl results match their official game pages.",
         unknown="Player-level 2026 totals: the reachable mirror has no 2026 week-level player file.",
         missingInfo="A reachable 2026 player-week file, or an official per-player API.",
         wouldChange="Whether prop research could start. Without it, props stay blocked.",
         discovery="Retry the nflverse release asset from a network that permits release-assets host, or "
                   "scrape the official player game logs.",
         source=S["nfl_stand"], status="ANSWERED-PARTIAL",
         answer="Results and standings: 32/32 clubs agree. Player-level 2026: not verified."),
    dict(id="Q03", area="Data provenance", priority="high",
         question="Who owns the market-price data, and may it be redistributed?",
         known="The nflverse-data repository declares CC-BY-4.0. The nfldata repository from which the prices "
               "were read has no licence file in the tree at the commit used.",
         unknown="Whether the underlying price vendor permits redistribution of derived prices.",
         missingInfo="A written licence or permission covering derivative odds data.",
         wouldChange="Whether this site may publish price-derived figures at all.",
         discovery="Ask the nfldata maintainer for the provenance and licence of data/closing_lines.csv; "
                   "until answered, keep derived prices off the public pages and show model-vs-market gaps only.",
         source=S["nfldata"], status="UNVERIFIED",
         answer=""),
    dict(id="Q04", area="Data provenance", priority="medium",
         question="Can GitHub release binaries be used directly, instead of a third-party mirror?",
         known="No. This environment can reach github.com and api.github.com but not the release asset CDN "
               "(release-assets.githubusercontent.com).",
         unknown="Whether the restriction is environmental or global.",
         missingInfo="A CI runner (GitHub Actions) can reach the CDN; a local run cannot.",
         wouldChange="Which files are first-party rather than mirrored.",
         discovery="Run the same fetch in GitHub Actions and compare checksums with the mirror copy.",
         source=S["nflverse"], status="ANSWERED-NO",
         answer="Release CDN is unreachable here; mirror used and labelled. CI can do better."),

    # ---------------- line origination
    dict(id="Q05", area="Line origination", priority="blocking",
         question="What does 'originating my own line' mean here, precisely?",
         known="A fair line is produced for every 2026 Week 11 game that has a market number: fair spread, "
               "fair total, fair moneyline and the break-even price.",
         unknown="Whether the owner wants a pre-market number (before books post) or a comparison number "
                 "(after books post).",
         missingInfo="The intended use: deciding what to bet, or grading price accuracy.",
         wouldChange="The timing of the model snapshot and which error metric matters.",
         discovery="Read the Week 11 card; if the number arrives after the market, it is a comparison, "
                   "not an origination.",
         source=S["nfl_sched"], status="ANSWERED-PARTIAL",
         answer="Both numbers are published side by side so the distinction is visible."),
    dict(id="Q06", area="Line origination", priority="blocking",
         question="Is the fair-line model better than the closing market?",
         known="No. On 7,413 graded games the model's mean absolute margin error is 10.52 points; the closing "
               "number's is 10.48. The de-vigged closing moneyline outscores the ratings everywhere.",
         unknown="Whether a richer model (injuries, rest, weather, travel) closes that gap.",
         missingInfo="Those inputs are not in the archive.",
         wouldChange="Whether any line can be published as an alternative to the market rather than a "
                     "transparent benchmark.",
         discovery="Add one input at a time and require it to beat the current model on identical games.",
         source=S["nfl_stats"], status="ANSWERED-NO",
         answer="No — the market is better, and the site says so."),
    dict(id="Q07", area="Line origination", priority="high",
         question="How much of the fair line is a fixed constant rather than a model?",
         known="The probability-to-margin mapping is an OLS fit: intercept 0.34 points, slope 31.71 points per "
               "probability unit, fitted on 7,413 graded games. The league mean total is 44.29.",
         unknown="How stable those constants are out of sample.",
         missingInfo="A stability check across disjoint seasons.",
         wouldChange="Confidence in the fair spread for extreme probabilities.",
         discovery="Refit the mapping within each season and compare the coefficients.",
         source=S["nfldata_data"], status="ANSWERED-PARTIAL",
         answer="The mapping is explicit and printed on the page; nothing is hidden in a black box."),
    dict(id="Q08", area="Line origination", priority="high",
         question="Are the market numbers for an unplayed week final?",
         known="2026 Week 11 carries 13 games with prices in the archive, captured 2026-11-13.",
         unknown="Whether those are closing or current-in-progress prices.",
         missingInfo="A capture timestamp per price.",
         wouldChange="Whether the gap between the model and the number is exploitable or already closed.",
         discovery="Snapshot the same games again later and diff.",
         source=S["nfldata_data"], status="UNVERIFIED", answer=""),

    # ---------------- strategy / leaderboard
    dict(id="Q09", area="Strategy validation", priority="blocking",
         question="Has any strategy demonstrated skill rather than luck?",
         known="No. 8 strategies were tested on 300-5,000 graded bets each. None has a week-block bootstrap "
               "interval entirely above zero. The best point estimate (+0.4%) has an interval of -2.7% to +4.0%.",
         unknown="Whether a better-specified model would.",
         missingInfo="Better inputs, which are blocked (see Q10, Q11).",
         wouldChange="Nothing is reward-eligible until one strategy passes every gate.",
         discovery="Only a frozen prospective trial can promote a strategy (gate G7).",
         source=S["ops"], status="ANSWERED-NO",
         answer="No. Zero of 8 tested strategies earned a rank above 'unproven'."),
    dict(id="Q10", area="Strategy validation", priority="blocking",
         question="What is the pre-declared evidence bar for a strategy to be considered skilful?",
         known="Minimum 300 graded bets; a bootstrap interval that excludes zero ROI; a p-value corrected for "
               "the family of 8 tested strategies; and a frozen prospective trial.",
         unknown="Whether the owner accepts these thresholds.",
         missingInfo="A decision on thresholds, which is a policy choice, not a fact.",
         wouldChange="How many strategies appear on the leaderboard and which can earn rewards.",
         discovery="Choose the thresholds on the Suggestions page; the engine will re-label automatically.",
         source="", status="AWAITING-DECISION", answer=""),
    dict(id="Q11", area="Strategy validation", priority="high",
         question="Are player-prop and same-game-parlay strategies testable with what we have?",
         known="No. There are no prop prices of any kind, and parlay prices are the product of two leg prices, "
               "which is not how a book prices a correlated parlay.",
         unknown="Whether the same-game parlay prices any book quoted historically can be obtained.",
         missingInfo="A timestamped prop and SGP price archive.",
         wouldChange="Whether prop and combo strategies move from BLOCKED to TESTED.",
         discovery="Buy or licence a price archive; log it with a capture timestamp per quote.",
         source="", status="ANSWERED-NO",
         answer="Blocked. Declared, scored as zero evidence, and shown as BLOCKED — not hidden."),
    dict(id="Q12", area="Strategy validation", priority="high",
         question="Does a parlay's quoted payout reflect its true joint probability?",
         known="The archive has no SGP prices, so the two- and three-leg parlays were priced at the product of "
               "the leg decimals, which is an upper bound on what a book pays for correlated legs.",
         unknown="The real SGP hold and correlation adjustment for the legs used.",
         missingInfo="Book-specific SGP pricing rules.",
         wouldChange="The measured parlay ROI, which is currently the only positive point estimate (+10%) and "
                     "still statistically indistinguishable from zero.",
         discovery="Collect actual SGP quotes for the same legs and re-price.",
         source="", status="UNVERIFIED", answer=""),
    dict(id="Q13", area="Strategy validation", priority="medium",
         question="How correlated are the markets and players we would combine?",
         known="Measured: spread-cover vs over phi = +0.014 (n=7,109); moneyline vs over phi = +0.005 "
               "(n=5,220); QB passing yards vs his WR1 receiving yards phi = +0.29 (n=307); RB1 vs RB2 rushing "
               "phi = +0.07 (n=311); WR1 vs WR2 receiving phi = +0.003 (n=321).",
         unknown="Whether those correlations hold in the 2026 player data.",
         missingInfo="A 2026 player-week file.",
         wouldChange="How much a parlay's fair price moves away from the independent product.",
         discovery="Recompute when the 2026 file is reachable; the script is parameterised by season.",
         source=S["nfl_player"], status="ANSWERED-PARTIAL", answer=""),
    dict(id="Q14", area="Strategy validation", priority="high",
         question="Should the leaderboard rank by ROI at all?",
         known="Ranking by raw ROI rewards the highest-variance strategy. The three-leg parlay (n=384) shows "
               "+10.0% ROI with an interval from -30.9% to +57.3% — the widest on the board.",
         unknown="Whether the owner prefers risk-adjusted rank or evidence-weighted rank.",
         missingInfo="A scoring-policy decision.",
         wouldChange="The order of the leaderboard.",
         discovery="Pick a policy on the Suggestions page; the default here ranks by the lower bound of the "
                   "ROI interval.",
         source="", status="AWAITING-DECISION", answer=""),
    dict(id="Q15", area="Strategy validation", priority="high",
         question="What would reward a strategy, and what stops a lucky winner?",
         known="No strategy is reward-eligible. Eligibility requires passing all 8 gates including a frozen "
               "prospective trial and a human release review.",
         unknown="The actual reward mechanism, and whether real money is involved (legal review needed).",
         missingInfo="Owner decision plus legal review.",
         wouldChange="Whether the leaderboard can pay anything at all.",
         discovery="Paper-only first; record predictions before outcomes for a fixed horizon.",
         source="", status="AWAITING-DECISION", answer=""),

    # ---------------- injuries
    dict(id="Q16", area="Injuries & lineups", priority="blocking",
         question="Can official 1st/2nd/3rd/4th-string depth order be obtained from the NFL?",
         known="Not from this environment: nfl.com/teams/<club>/depth-chart returns HTTP 404. The roster page "
               "returns 200 but lists position and ACT status only, with no order.",
         unknown="Whether a depth chart exists behind a different official URL or an official API.",
         missingInfo="A confirmed official depth-order source.",
         wouldChange="Whether the tier column is read from the league or computed by this lab.",
         discovery="Probe nfl.com team sub-pages and the NFL's public data endpoints from CI.",
         source=S["nfl_depth"], status="ANSWERED-NO",
         answer="Not retrieved. Tiers are therefore computed from production and labelled as such."),
    dict(id="Q17", area="Injuries & lineups", priority="high",
         question="Which players are actually unavailable this week, and at what tier?",
         known="For three 2026 Week 10 games: 65 officially listed players, 8 Out, 1 Questionable, 56 with a "
               "blank game status. A production-based tier is attached to each.",
         unknown="The other Week 10 games and all of Week 11.",
         missingInfo="Transcription of the remaining official injury pages (or a parser for them).",
         wouldChange="The coverage of the tracker page.",
         discovery="Extend the capture to every game of the week; the page is keyed by season and week.",
         source=S["nfl_inj_w10"], status="ANSWERED-PARTIAL", answer=""),
    dict(id="Q18", area="Injuries & lineups", priority="blocking",
         question="How many points is a missing tier-1 player worth?",
         known="Measured on 414 club-weeks of 2025: tier-1 offence out -> own points 22.01 vs 22.98 "
               "(-0.97, interval -3.22 to +1.38). Tier-1 defence out -> points allowed 23.42 vs 22.62 "
               "(+0.80, interval -1.58 to +3.14). Quarterback alone: -4.99 points over 18 club-weeks, too "
               "small a sample to interval.",
         unknown="Whether the effect is causal, and how it scales with tier 2/3/4.",
         missingInfo="Multiple seasons with practice status and snap counts.",
         wouldChange="Whether injury adjustment can be a betting input at all.",
         discovery="Repeat across 2016-2025 once the full injury files are reachable; require stability.",
         source=S["nfl_inj"], status="ANSWERED-PARTIAL",
         answer="No measurable effect found beyond the quarterback point estimate, whose sample is too small."),
    dict(id="Q19", area="Injuries & lineups", priority="high",
         question="Does a backup replacing a starter show up in the score at all?",
         known="Only weakly. Position-group differences are all inside their intervals except the "
               "small-sample groups, which cannot be interval-estimated.",
         unknown="Whether an individual-level (not group-level) replacement effect exists.",
         missingInfo="Snap counts and participation data, absent here.",
         wouldChange="Whether a 'backup tier' feature would add information.",
         discovery="Join snap counts when reachable; measure the drop when the tier-1 player's snap share "
                   "is replaced.",
         source=S["nfl_tx"], status="UNVERIFIED", answer=""),
    dict(id="Q20", area="Injuries & lineups", priority="medium",
         question="Is the official injury report's blank status meaningful?",
         known="The page leaves Practice Status and Game Status blank for most listed players; 56 of 65 rows "
               "in the captured games are blank in at least one field.",
         unknown="Whether blank means 'no game designation' or 'not yet published'.",
         missingInfo="The league's documentation of the report format.",
         wouldChange="Whether a blank should be treated as available.",
         discovery="Compare the same report across practice days to see blanks fill in.",
         source=S["nfl_inj"], status="UNVERIFIED", answer=""),

    dict(id="Q23", area="Statistics", priority="blocking",
         question="Is the luck test correct when bet prices differ?",
         known="An earlier pooled break-even win-rate test was wrong for mixed prices: it compared win counts "
               "while the money depends on the price. It has been replaced by a per-bet null using the "
               "de-vigged closing market probability of the side taken, with 10,000 seeded simulations.",
         unknown="Nothing further — the defect was identified, corrected and recorded on the Method page.",
         missingInfo="None.",
         wouldChange="The three-leg parlay's significance fell from p = 0.0005 to p = 0.218. No other strategy "
                     "crosses the significance line.",
         discovery="Re-run the engine; the seed is fixed so the result is reproducible.",
         source="", status="ANSWERED",
         answer="Yes now, no before. The old figure was withdrawn, not hidden."),

    # ---------------- site / process
    dict(id="Q21", area="Site & process", priority="medium",
         question="Where do suggestions get reviewed before anything is built?",
         known="This lab adds a dedicated Suggestions page with a decision column and a recommended path.",
         unknown="Whether the owner wants a voting or scoring mechanism.",
         missingInfo="Owner preference.",
         wouldChange="Whether suggestions are ranked by the owner or by the lab.",
         discovery="Open the Suggestions page; each row names the decision required.",
         source=f"{SITE}/suggestions.html", status="ANSWERED",
         answer="Published, with cost/risk/reversibility and a recommendation per item."),
    dict(id="Q22", area="Site & process", priority="medium",
         question="How can a reader tell an official value from a model value at a glance?",
         known="Every row carries a source link and an OFFICIAL / MIRROR / MODEL / NOT OFFICIAL label.",
         unknown="Whether the labelling is legible enough in practice.",
         missingInfo="Owner feedback after review.",
         wouldChange="The badge design, not the data.",
         discovery="Review the Flagged page and the source badges on any table.",
         source=f"{SITE}/sources.html", status="ANSWERED", answer=""),
]

SUGGESTIONS = [
    dict(id="SG01", title="Publish the fair-line card before the market posts",
         decision="Do you want a pre-market number or a post-market comparison?",
         benefit="A pre-market number is a genuine origination; a post-market number is a benchmark.",
         risk="Pre-market lines have no liquidity check and will look wrong against the closing number.",
         cost="Low — the model already runs from graded history only.",
         reversibility="High",
         recommended="Start with the post-market comparison (today's build) and add a frozen 24-hours-before "
                     "snapshot once the schedule feed is wired to a cron job.",
         source=f"{SITE}/lines.html", status="PROPOSED"),
    dict(id="SG02", title="Licence a timestamped prop and SGP price archive",
         decision="Approve the spend, or accept that props stay blocked.",
         benefit="Unblocks prop and parlay strategies, the two families the owner explicitly asked for.",
         risk="Data rights, cost, and coverage gaps for lower-profile players.",
         cost="High (commercial licence)",
         reversibility="Medium",
         recommended="Do not build prop models before the price history exists; a model with no price cannot "
                     "be scored.",
         source="", status="BLOCKED-PENDING"),
    dict(id="SG03", title="Recover an official depth-chart feed",
         decision="Accept computed tiers, or fund a real depth-order source.",
         benefit="Turns the tier column from 'computed' into 'official', which is what the owner asked for.",
         risk="An unofficial depth source would immediately violate the no-hallucination rule.",
         cost="Medium",
         reversibility="High",
         recommended="Keep computed tiers labelled as computed. Chase the official page from CI, where the "
                     "404 may not reproduce.",
         source=S["nfl_depth"], status="PROPOSED"),
    dict(id="SG04", title="Score strategies on the interval lower bound, not ROI",
         decision="Confirm the leaderboard scoring policy.",
         benefit="Stops the highest-variance strategy from topping the board by luck.",
         risk="Conservative scoring can hide a genuinely good small-sample strategy.",
         cost="none",
         reversibility="High",
         recommended="Adopt it; it is already the default in this build.",
         source=f"{SITE}/leaderboard.html", status="DONE"),
    dict(id="SG05", title="Freeze a prospective paper trial for the two least-bad strategies",
         decision="Pick a horizon (e.g. the rest of 2026) and freeze the version.",
         benefit="Only a prospective, pre-registered trial can promote a strategy past gate G7.",
         risk="A short horizon will not settle anything; a long one delays the leaderboard.",
         cost="Low",
         reversibility="High",
         recommended="Freeze the totals-from-scoring-rates strategy (largest sample, smallest interval) for "
                     "the remainder of 2026.",
         source=f"{SITE}/gates.html", status="PROPOSED"),
    dict(id="SG06", title="Extend the injury tracker to every game of the week",
         decision="Approve the extra capture effort.",
         benefit="Makes the tracker usable for the actual slate instead of three games.",
         risk="Transcription error; each row needs its source URL and a blank-safe schema.",
         cost="Medium",
         reversibility="High",
         recommended="Parse the official page rather than transcribing it, and keep the verbatim capture as "
                     "the audit trail.",
         source=S["nfl_inj"], status="PROPOSED"),
    dict(id="SG07", title="Add snap counts and participation data",
         decision="Decide whether the extra data source is worth the licence/effort.",
         benefit="The only way to measure a backup's actual workload rather than infer it.",
         risk="Not reachable from this environment; would need CI or a licensed feed.",
         cost="Medium",
         reversibility="High",
         recommended="Do it before any injury-adjusted line is published.",
         source=S["nfl_tx"], status="BLOCKED-PENDING"),
    dict(id="SG08", title="Show a model-vs-market error table per season",
         decision="None — informational.",
         benefit="Makes it obvious where and when the model lost, instead of one summary number.",
         risk="None.",
         cost="Low", reversibility="High",
         recommended="Built. The per-season splits are on the Backtest page.",
         source=f"{SITE}/backtest.html", status="DONE"),
    dict(id="SG09", title="Separate 'no data' from 'zero' everywhere",
         decision="None — already the house rule.",
         benefit="Stops a blocked strategy being read as a losing strategy.",
         risk="None.",
         cost="none", reversibility="High",
         recommended="Built: blocked strategies show BLOCKED and a blank profit, never 0.",
         source=f"{SITE}/leaderboard.html", status="DONE"),
    dict(id="SG10", title="Add a monthly re-verification job",
         decision="Approve the CI cadence.",
         benefit="Keeps the official cross-checks (standings, injury pages, stats leaders) from going stale.",
         risk="CI minutes; silent drift if a page changes markup.",
         cost="Low", reversibility="High",
         recommended="Run the validator monthly and fail loudly on any mismatch, listing both numbers.",
         source=S["nfl_stand"], status="PROPOSED"),
    dict(id="SG11", title="Publish the licence status of the price archive",
         decision="Decide whether price-derived figures may be shown publicly.",
         benefit="Removes a legal unknown from the project.",
         risk="If the answer is 'no', the backtest pages must be removed.",
         cost="Low", reversibility="Medium",
         recommended="Ask the maintainer in writing; until then keep the figures labelled NOT OFFICIAL.",
         source=S["nfldata"], status="PROPOSED"),
    dict(id="SG12", title="Promote only after a full-season prospective trial",
         decision="Confirm the reward gate.",
         benefit="Prevents paying for luck.",
         risk="A full season is a long wait.",
         cost="none", reversibility="High",
         recommended="Adopt; the engine already refuses to mark anything reward-eligible.",
         source=f"{SITE}/gates.html", status="DONE"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    q_status = {}
    for q in QUESTIONS:
        q_status[q["status"]] = q_status.get(q["status"], 0) + 1
    s_status = {}
    for s in SUGGESTIONS:
        s_status[s["status"]] = s_status.get(s["status"], 0) + 1
    payload_q = {"generatedUTC": stamp, "questions": QUESTIONS,
                 "counts": {"total": len(QUESTIONS), **q_status},
                 "order": ["blocking", "high", "medium"],
                 "note": "ANSWERED items carry the answer. UNVERIFIED and AWAITING-DECISION items are the "
                         "open decisions; each names the exact discovery step that would settle it."}
    payload_s = {"generatedUTC": stamp, "suggestions": SUGGESTIONS,
                 "counts": {"total": len(SUGGESTIONS), **s_status},
                 "howToUse": "Read the decision column first. Nothing is implemented until a decision is "
                             "recorded here; DONE items are already live so the reviewer can judge them.",
                 "scoring": {"benefit": "expected improvement in decision quality",
                             "risk": "what could go wrong, and how badly",
                             "cost": "effort + money",
                             "reversibility": "how cheaply it can be undone"}}
    (OUT / "questions.json").write_text(json.dumps(payload_q, indent=1) + "\n", encoding="utf-8")
    (OUT / "suggestions.json").write_text(json.dumps(payload_s, indent=1) + "\n", encoding="utf-8")
    print(f"questions: {len(QUESTIONS)} {q_status}")
    print(f"suggestions: {len(SUGGESTIONS)} {s_status}")


if __name__ == "__main__":
    main()
