# NBA ↔ EPL Cross-Sport Similarity — Session Context

This file is read automatically by Claude Code at the start of every session.
It captures the settled decisions, warnings, and context so you don't have to
re-derive them. For full per-file documentation see `PROJECT_FILES.md`.

---

## What this project is

A cross-sport player similarity model that answers "who is the NBA version of
this Premier League footballer?" Players from EPL and NBA are scored on seven
shared dimension axes using within-sport percentile normalization — the bridge
that makes cross-sport comparison valid. The model finds nearest neighbours
across sports using strengths-weighted Euclidean distance. The v2 extension adds
a multi-season NBA archetype drift analysis (`drift.py`) and a complementary
absolute era trends module (`era_trends.py`).

---

## Python environment

**Always use `/Users/abhi/anaconda3/bin/python`** — this is the only interpreter
with the required packages (numpy, pandas, sklearn, matplotlib, nba_api).
The system `/usr/bin/python3` does NOT have these packages.

---

## The 7 dimensions

Each dimension has a `__vol` (volume) and `__eff` (efficiency) axis, kept
separate deliberately — averaging them re-introduces the failure mode where a
high-volume inefficient scorer looks like a low-volume efficient sniper ("the
Curry rule"). `config.py` is the single place to change which raw stats feed
which axis.

| Dimension | Soccer inputs | NBA inputs |
|---|---|---|
| `scoring_threat` | Sh/90, SoT/90, npxG/90 (vol) · G/Sh, SoT%, Dist, npxG/Sh (eff) | FGA, PTS, 3PA (vol) · TS%, eFG%, 3P%, 3PAr, FTr (eff) |
| `playmaking` | xA, KP, SCA90 (vol) · PPA, CrsPA, GCA90 (eff) | AST, POTENTIAL_AST (vol) · AST%, ast_to_tov (eff) |
| `ball_progression` | PrgC, PrgP, PrgR (vol) · CPA, Succ% (eff) | DRIVES, TOUCHES (vol) · PTS_PER_TOUCH, DRIVE_FG_PCT (eff) |
| `possession_security` | Touches (vol) · Cmp%_Total, Mis, Dis (eff) | TOUCHES (vol) · TOV%, ast_to_tov (eff) |
| `defensive_effectiveness` | Int, Clr, Blocks (vol) · TklChallenge%, Won%, Err (eff) | STL, BLK, DEF_RATING (vol) · DBPM, DRB%, CONTESTED_SHOTS (eff) |
| `physicality` | Won, height_in, weight_lbs, bmi (vol) · Won% (eff) | TRB, height_in, weight_lbs, bmi (vol) · DRB% (eff) |
| `engine` | Recov (vol) | CONTESTED_SHOTS, BOX_OUTS (vol) |

---

## Key design decisions — do not re-debate these

### Within-season normalization is load-bearing
Every stat is percentile-ranked **within its own league-season** before any
cross-sport comparison. This is what makes the comparison valid: "90th-percentile
shot volume" means the same thing in EPL and NBA regardless of the raw numbers.
Side effect: the model is **blind to league-wide volume shifts over time** — a
uniform tide that lifts all boats equally disappears into the normalization.
This is a feature, not a bug. The answer to "but what about the 3-point boom?"
is `era_trends.py`, not changing the normalization.

### Strengths-only weighting (not equal, not symmetric)
Equal weighting failed: Haaland's low involvement was weighted, pulling him
toward low-usage floor spacers. Symmetric weighting had the same problem.
Strengths-only: each axis is weighted by how far **above the league median**
the query player sits. Only their distinctive strengths inform the match.

### Interior score is display-only
Shot location signals (`3PAr`/`FTr` for NBA; `Dist`/`npxG/Sh` for soccer) are
folded **into** `scoring_threat` efficiency — not a standalone axis. A
standalone interior axis dragged Haaland toward low-volume putback centres
(same interior score, wrong on everything else). Folded in, the volume axis in
the same dimension separates them correctly. The `interior_score` column
(0–100) surfaces this on the radar/breakdown without entering the distance math.

### DBPM is always NaN — expected, not a bug
Basketball-Reference's Defensive Box Plus/Minus is a proprietary bbref metric,
not available through nba_api. All nine NBA seasons will show DBPM = NaN
throughout. Do not try to fix it; it's documented.

### The bbref nba_2223 files were mislabeled
`NBA_Stats_Per_Game_2023*.csv` contains **2023-24** data despite the name.
Verified via LeBron spot-check (perfect 1.0000 PTS correlation to nba_api
2023-24; clearly off from true 2022-23 at 28.9 PTS/55G). That bbref source is
retired. All NBA data now comes from nba_api (`nbaapi_*_<YYYY>.csv`). The
dataset ID `nba_2223` now correctly maps to genuine 2022-23 nba_api data.

### fillna(0.5) in drift.py, NOT fillna(50)
The shared dimension axes are within-season percentile fractions in **0..1**.
`cluster.py` uses `fillna(50)` which is fine when NaNs are rare (50 ≈ median on
a 0..1 scale is 0.5, but the scaler sees 50 as an extreme outlier). In
`drift.py` the stakes are higher: NBA `engine__vol` (hustle stats) is missing
for ~60% of 2015-16 players — right at the start of the drift window. Filling
with 50 would manufacture a massive outlier blob in the first season and make
drift look like an artifact of the imputation. Always use `_FILL = 0.5`.

---

## File structure (brief — see PROJECT_FILES.md for full detail)

```
config.py          dimension schema (the one place to change what gets measured)
pipeline.py        within-sport normalize → __vol/__eff dimension axes
ingest_data.py     registry-driven build: raw CSVs → processed/<id>.csv
datasets.py        dataset registry (all file paths, season strings, thresholds)
similarity.py      strengths-weighted cross-sport nearest-neighbour lookup
cluster.py         single-season pooled k-means → cross-sport archetypes
drift.py           frozen archetypes → structural drift over 9 NBA seasons
era_trends.py      raw league-average style trends (absolute, not normalized)
radar.py           overlaid radar chart of two players
breakdown.py       per-axis percentile breakdown explaining a comp

fetch_nba_base.py       nba_api pull: per-game + advanced stats
fetch_nba_tracking.py   nba_api pull: drives, touches, hustle, DEF_RATING
fetch_nba_bio.py        nba_api pull: height + weight
fetch_all_seasons.py    batch orchestrator across all nine seasons
fetch_soccer_bio.py     FIFA 23 height/weight extractor

processed/          gitignored: one CSV per dataset (epl_2324, nba_1516 … nba_2324)
examples/           committed: curated charts and CSVs (rendered on GitHub)
archetypes_frozen.pkl   gitignored: frozen scaler + centroids (drift.py)
```

---

## Roadmap (as of v2.1)

- ~~Hand-name archetypes~~ ✓ (done — ARCHETYPE_NAMES dict in cluster.py)
- ~~CLAUDE.md for session continuity~~ ✓ (this file)
- Team-context / usage normalization (share-of-team metrics)
- StatsBomb open-data aggregator for multi-league soccer (2015-16 Big-5 is free)
- FIFA/EA FC PlayStyles as categorical archetype tags (off-ball signal)
- Legends mode (reduced-feature variant on historical box-score stats only)
- Interactive website (input player + year → see cross-sport counterpart)

---

## Data warnings — read before touching files

**`PL_Stats_2023*.csv` are IRREPLACEABLE.** FBref removed all Opta/Stats Perform
advanced data ~January 2026. These 7 CSV files are a pre-removal snapshot and
no longer exist at source. The entire soccer side of the model runs on them.
They are backed up separately. Never delete them; never overwrite them.

**`male_players.csv` is 5 GB.** It is the FIFA 23 source file. Permanently
gitignored. Never commit it. The pre-extracted `soccer_bio_2023.csv` is the
lightweight version that enters the pipeline.

**Always run `git check-ignore -v <file>` before staging any data file.**
The `.gitignore` has broad block rules with explicit `!examples/` negations.
A new raw-output file that doesn't match any block rule could slip through.
When in doubt: `git status --short` → look for any `nbaapi_*.csv`,
`processed/*.csv`, `*.pkl`, or `male_players.csv` in the staged list.
If any appear, stop and fix `.gitignore` first.
