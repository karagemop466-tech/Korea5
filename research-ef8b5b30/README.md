# Session `ef8b5b30` research notes

`tools/probe.py` downloads raw official pages inside GitHub Actions (the sandbox has no direct outbound
internet). Earlier CI runs force-added those raw bytes to `raw/` as a temporary handoff so this workspace could
inspect them. They are **generated artifacts**, not source data, and have been removed from Git; `.gitignore`
keeps `research-ef8b5b30/raw/` out of the repository.

The durable, source-linked outputs of that work are:

- `official/nfl-2026.json` — 321 official NFL.com by-week games.
- `official/westwoodone.json` — 580 official Westwood One Sports event windows.
- `official/w1-stations.json` — San Francisco affiliate rows from the official Station Finder.
- `official/mlb-tbd.json` — MLB StatsAPI `startTimeTBD` flags.
- `curated/rules.json` — verbatim timing excerpts extracted from the official NFL and NCAA rulebook PDFs.
- `curated/*.json` — source registry, season anchors, stations, durations, future NCAAF, estimates and flags.
