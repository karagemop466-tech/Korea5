#!/usr/bin/env python3
"""
NFL Lines Lab — leaderboard, tiers and (non-cash) rewards.

Reads nfl/data/model_results.json and writes nfl/data/lines-leaderboard.json.

The competition is deliberately PAPER-ONLY. Rewards are Lab Points and research
priority inside the lab; no money, no wagering, no prize of monetary value is
offered, because paying out on betting performance has legal and regulatory
consequences that this repository cannot satisfy. That is stated on the page.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DATA = "nfl/data"

TIER_LABEL = {
    "A": "Tier A — passes every pre-registered gate",
    "C": "Tier C — promising, not yet distinguishable from luck",
    "D": "Tier D — fails at least one gate",
}

REWARD = {
    "A": {"points": 1000, "perks": ["Featured on the dashboard", "Automatic entry into the locked prospective paper trial",
                                    "Named methodology review by a second session"]},
    "C": {"points": 300, "perks": ["Listed on the watch list", "Eligible for the next prospective trial window"]},
    "D": {"points": 50, "perks": ["Kept in the audit history — a failed strategy is never deleted"]},
}


def main() -> int:
    path = os.path.join(DATA, "model_results.json")
    if not os.path.exists(path):
        print("no model_results.json yet")
        return 1
    res = json.load(open(path, encoding="utf-8"))
    lb = res.get("leaderboard", [])

    rows = []
    for item in lb:
        tier = item.get("tier", "D")
        r = REWARD.get(tier, REWARD["D"])
        rows.append({
            "name": item["name"], "family": item["family"], "tier": tier,
            "tierLabel": TIER_LABEL.get(tier, tier),
            "score": item.get("score", 0.0), "labPoints": r["points"], "perks": r["perks"],
            "metrics": item.get("metrics", {}),
            "gates": item.get("gates", {}),
            "claim": item.get("claim", ""),
        })
    rows.sort(key=lambda x: (-{"A": 2, "C": 1, "D": 0}[x["tier"]], -x["score"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    out = {
        "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "competition": {
            "title": "NFL Lines Lab strategy competition",
            "basis": "Score = pre-registered deflated skill × sample-size shrink × calibration factor. "
                     "Raw win rate is never a ranking input.",
            "rewards": "Lab Points and research priority only. No money or prize of monetary value is offered, "
                       "and no wager is placed or facilitated by this repository.",
            "tieBreak": "Higher deflated skill, then larger sample, then better calibration slope.",
        },
        "tiers": TIER_LABEL,
        "rows": rows,
    }
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "lines-leaderboard.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"leaderboard: {len(rows)} strategies")
    for r in rows[:8]:
        print(f"  #{r['rank']} {r['tier']} {r['score']:>8} pts={r['labPoints']:>5} {r['name'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
