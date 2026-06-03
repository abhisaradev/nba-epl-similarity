# Project Files Reference

Living reference for the NBA ↔ EPL cross-sport similarity project. Updated whenever a module changes materially. This is the right place to understand why a file exists, what design decisions it encodes, and what's on the roadmap.

---

## Architecture overview

```
Raw CSVs (gitignored)
      │
      ▼
ingest_data.py   →  processed/<id>.csv  (one per league-season)
      │
      ▼
pipeline.py      →  within-season normalised feature frames
      │
      ├── similarity.py   cross-sport nearest-neighbour comps (v1 headline)
      ├── cluster.py      single-pool k-means, one archetype run (v1/v2 shared)
      ├── drift.py        FROZEN archetypes + drift over 9 NBA seasons (v2)
      └── era_trends.py   RAW league averages over time — absolute tide (v2)
```

**The two v2 analysis modules answer different questions and must stay separate:**

| Module | Normalization | What it can see | What it's blind to |
|---|---|---|---|
| `drift.py` | within-season percentile ranks | structural role re-sorting (which archetypes gain/lose players) | uniform league-wide shifts (e.g. everyone shooting more threes equally) |
| `era_trends.py` | none — raw league averages | absolute era shifts (3PAr rising, FTr falling) | whether the shift is tactical choice vs pace/volume |

---

## File-by-file

### Data pipeline

#### `datasets.py`
Registry of every dataset the project knows about. Each entry specifies: sport, season string (`true_season`), raw-file paths, processed-CSV path, and minutes threshold. Downstream code calls `datasets.get(id)` and never hardcodes a filename.

**Design decisions:**
- `NBA_SEASONS` list + `_nba_entry()` generates all 9 NBA entries programmatically — adding a new season is one list append.
- `_nba_id()` converts `'2015-16'` → `'nba_1516'` (consistent ID scheme used everywhere).
- FBref uses identical table layouts across all leagues, so a new soccer league is just a new DATASETS entry pointing at its files.
- **Provenance fix (v2):** The original `nba_2223` entry pointed at bbref `NBA_Stats_Per_Game_2023*.csv` files. Those files were mislabeled — they contain 2023-24 data (verified via LeBron per-game spot-check, corr 1.0). That bbref entry is retired. All NBA datasets now come from `nba_api` via `nbaapi_*_<YYYY>.csv`. The `nba_2223` ID now correctly maps to genuine 2022-23 data from nba_api.

---

#### `ingest_data.py`
Registry-driven merge: takes a dataset ID, resolves raw-file paths from `datasets.py`, dispatches to `build_soccer()` or `build_nba()`, and writes `processed/<id>.csv`.

**FBref soccer merge details:**
- Loads the 7 FBref tables (main, shooting, defensive, GSC, passing, possession, misc) and merges on Player.
- Column rename maps handle FBref's duplicate column names (e.g. `Cmp`/`Cmp.1`/`Cmp.2`/`Cmp.3` → `Cmp_Total`/`Cmp_Short`/`Cmp_Med`/`Cmp_Long`).
- `_dedup_fbref()` keeps the row with the most minutes for mid-season transfers.
- Bio (height/weight from FIFA 23) merged via **token-sort key** (`'Son Heung-min'` == `'Heung-Min Son'`) + subset fallback for single-name players (`'Gabriel'` ↔ `'Gabriel Magalhães'`).
- `ALIAS_FBREF_TO_FIFA`: manual bridge for 12 players whose FBref name shares no token with their FIFA registered name (Casemiro, Rodri, Jorginho, etc.).
- Six players missing from FIFA 23 entirely (Mitoma, Mainoo, Son, etc. — 2023-24 arrivals the 2022 game predates); they stay without bio.
- Bio coverage gate: refuses to proceed if weight coverage over the 900-minute pool is below 85%.

**nba_api merge details:**
- `build_nba()` handles two source shapes: two-file (bbref per-game + advanced) and single-file (nba_api base+advanced combined, both registry keys pointing at same file).
- `_dedup_nba()` keeps the season-total row (`Team ∈ {TOT, 2TM, 3TM, 4TM}`) for traded players.
- `3PAr`/`FTr` recomputed from per-game `3PA`/`FGA`/`FTA` (consistent definition; overwrites the nba_api version which uses season totals and drifts slightly).
- `interior_score`: display-only paint dominance (0–100), mean of two within-table percentiles. Not a similarity input — radar/breakdown read-out only.
- Tracking (hustle) stats merged separately via diacritic-normalised name key.

**Imperial/metric columns:** Config uses imperial (height_in, weight_lbs, BMI = 703×lbs/in²) because it matches nba_api's native units. Metric columns (height_cm, weight_kg) are derived and carried alongside for display.

---

#### `pipeline.py`
The cross-sport bridge. Converts one sport's processed CSV into normalised dimension axes.

Stages:
1. `load_sport()` — reads CSV, applies minutes filter.
2. `normalize()` — within-sport percentile ranks (0..1) on each raw stat. Inverse stats (`INVERSE_STATS` in config) are sign-flipped so higher always means better. **Within-sport** is the key constraint: each player is ranked against only their own league-season, so "90th-percentile shot volume" means the same thing in EPL and NBA even though the raw numbers differ.
3. `build_dimensions()` — composites normalised stats into per-dimension `__vol` and `__eff` axes (kept separate — averaging them re-introduces the Curry failure mode where high-usage inefficient scorers look like low-usage snipers).
4. `feature_frame()` — end-to-end from CSV to labelled feature frame.

---

#### `config.py`
Dimension schema: which raw stats map to which dimension, per sport, split into `volume` and `efficiency` sub-axes.

**7 core dimensions:** `scoring_threat`, `playmaking`, `ball_progression`, `possession_security`, `defensive_effectiveness`, `physicality`, `engine`.

**Design decisions:**
- `scoring_threat` folds shot location (interior vs perimeter) into the efficiency axis rather than a standalone axis — a standalone interior axis pulled high-volume scorers toward low-usage putback centres (the "Giannis looks like a rim-runner" problem).
- `physicality` and `engine` were split from a single `athleticism_stature` dimension (the Kanté problem: great motor ≠ great frame).
- `INVERSE_STATS` sign-flips lower-is-better stats: `Dist` (closer shots), `3PAr` (fewer threes = more interior), `TOV`, `TOV%`, `DEF_RATING`.
- `DIMENSION_WEIGHTS`: all 1.0 (inert). Non-destructively bump a single dimension for sensitivity testing.

---

### Fetch scripts

#### `fetch_nba_base.py`
Pulls per-game + advanced + hustle stats from `nba_api` for one season. Writes `nbaapi_base_<YYYY>.csv`. Also derives `ast_to_tov`, `3PAr`, `FTr`.

#### `fetch_nba_tracking.py`
Pulls tracking stats (drives, touches, contested shots, box-outs, etc.) from `nba_api`. Writes `nbaapi_tracking_<YYYY>.csv`.

#### `fetch_nba_bio.py`
Pulls height/weight from `nba_api` CommonPlayerInfo. Writes `nbaapi_bio_<YYYY>.csv`.

#### `fetch_all_seasons.py`
Orchestrates the three fetch scripts across a list of seasons. Resilient: a single failed endpoint is logged and skipped. `SLEEP_BETWEEN_SEASONS = 3` seconds between seasons to be polite to stats.nba.com. Run with season args or defaults to the 8-season backfill.

#### `fetch_soccer_bio.py`
Extracts height/weight from the FIFA 23 `male_players.csv` and writes `soccer_bio_2023.csv`. The FIFA dataset is the only practical source of bio data for EPL players at scale.

---

### Analysis

#### `similarity.py`
Cross-sport nearest-neighbour lookup. Given a player + their sport, computes cosine similarity against every player in the other sport's feature frame and returns the top-N comps with a per-dimension breakdown.

#### `cluster.py`
One-time pooled k-means over both sports (on the shared `__vol`/`__eff` axes). Sweeps k=6–8 by silhouette. All-season cluster run picks k=7 (silhouette ~0.152 vs 0.149 for k=6). Single-season run with EPL+NBA2324 picks k=7 as well (marginal improvement over k=6). Writes `archetype_assignments.csv`. 

**Important:** this re-fits the scaler and k-means every run. That's correct for "what are the current-season archetypes?" It is NOT correct for measuring drift — see `drift.py`.

#### `drift.py`  ← v2
**Within-season structural drift.** Pools EPL 2023-24 + all 9 NBA seasons (3,535 player-seasons, LeBron appears 9×), fits ONE `StandardScaler` and k-means (k=7 by silhouette), and **freezes** the result to `archetypes_frozen.pkl`. Every downstream step transforms with the frozen scaler and snaps to the frozen centroids — never re-fits.

Two readings:
- **League drift (Reading B):** NBA season × archetype % composition → `examples/nba_archetype_drift.csv` + stacked-area PNG. Shows structural re-sorting: traditional-big share falls; connector/engine types rise.
- **Player drift (Reading A):** one player's archetype trajectory across seasons they appear in. LeBron, Curry, and Giannis all map to one archetype across all 9 seasons — confirming assignment stability.

**What this can and cannot see:**
- ✅ Role-structure / archetype-bundling drift (Gobert stays in the physicality cluster)
- ✅ Big-man decline (physical archetypes lose share)
- ❌ Uniform league-wide shifts (the 3-point revolution raises everyone's `3PAr` equally → within-season percentile ranks erase it). Use `era_trends.py` for that.

**Imputation note:** fills missing axes with 0.5 (neutral percentile), NOT `fillna(50)`. The `50` default is a leftover from a 0–100 percentile scale; on today's 0–1 axes it would inject wild outliers — and the 2015-16 `engine__vol` axis (CONTESTED_SHOTS/BOX_OUTS) is missing for ~60% of that season's players, right at the start of the drift window.

#### `era_trends.py`  ← v2
**Absolute era trends.** Reads processed NBA CSVs directly (no cross-sport model, no normalization). For each qualified player (minutes ≥ 500) in each season, computes league-average style signals and outputs a season-by-season table.

Signals tracked (all rates/shares where possible — pace-robust):
- `3PAr` = 3PA/FGA (three-point share) — the spacing signal
- `3PA_pg` raw per-game (shown alongside 3PAr to expose the pace contribution)
- `FGA_pg` raw per-game (denominator context)
- `FTr` = FTA/FGA (free-throw rate)
- `TS%`, `eFG%` (shooting efficiency)
- `TOV%`, `AST%` (turnover rate, assist rate)

**Rate vs. pace (the paired signals):** 3PAr and 3PA/game are both reported so you can see whether a raw-count rise is a *choice* (3PAr rises too) or just pace/volume (FGA/game rises proportionally). In practice: 3PAr +42.6%, 3PA/game +48.6%, FGA/game only +6.7% → almost entirely a rate/choice shift.

**Chart:** every signal indexed to 2015-16 = 100. Mixed scales (0..1 fractions vs 0..100 rates vs raw counts) don't distort each other; every line shows "% of its own starting value."

**What this can and cannot see:**
- ✅ Absolute era shifts: 3PAr rises (0.282 → 0.402), FTr falls, TS%/eFG% improve
- ❌ Structural / role-bundling changes (use `drift.py`)
- ❌ Knows nothing about EPL or cross-sport comparison

---

### Display / output

#### `radar.py`
Generates per-player radar charts overlaying a query player against their nearest NBA comp on the 7 dimension axes.

#### `breakdown.py`
Dimension-by-dimension stat breakdown for a given comp pair.

#### `pipeline.py`
(covered above — also used by radar/breakdown to load feature frames for display)

---

### Output artefacts (committed)

`examples/` is the only output directory committed to git. Everything else (raw CSVs, processed CSVs, pkl files, full assignment tables) is gitignored.

| File | What it is |
|---|---|
| `examples/haaland_vs_markkanen.png` | Radar: Haaland ↔ Markkanen |
| `examples/rodri_vs_jokic.png` | Radar: Rodri ↔ Jokić |
| `examples/saliba_vs_davis.png` | Radar: Saliba ↔ Davis |
| `examples/archetypes_summary.csv` | k=6 cluster.py archetype summary (v1) |
| `examples/nba_archetype_drift.csv` | Season × archetype % composition (drift.py) |
| `examples/nba_archetype_drift.png` | Stacked-area chart of archetype drift |
| `examples/nba_era_trends.csv` | League-average style signals by season |
| `examples/nba_era_trends.png` | All signals indexed to 2015-16 = 100 |

---

## Data provenance & gitignore

All raw and processed data files are gitignored. The `.gitignore` uses broad block rules (`nbaapi_*.csv`, `processed/`, `PL_Stats_2023*.csv`, etc.) with explicit negation exceptions for `examples/` so the curated output charts and tables can be committed.

| Source | Files | Notes |
|---|---|---|
| FBref | `PL_Stats_2023*.csv` (7 tables) | EPL 2023-24 season |
| FIFA 23 | `male_players.csv` (~700MB) | Bio source for EPL; not redistributed |
| nba_api | `nbaapi_base/tracking/bio_<YYYY>.csv` (9 seasons × 3 = 27 files) | All from stats.nba.com via the `nba_api` library |

---

## Roadmap

- **v3 idea — EPL multi-season drift:** FBref provides historical EPL tables in the same format. Adding `epl_1920`, `epl_2021`, etc. to `datasets.py` (one entry each) would let drift.py measure EPL structural change on the same frozen archetypes.
- **v3 idea — cross-era pooled normalization:** Current within-season normalization erases absolute volume shifts. A pooled-era scaler (normalize across all seasons together) would let the drift view see the 3-point revolution directly, at the cost of making "absolute vs relative" harder to reason about. Likely a third separate module rather than changing drift.py.
- **v3 idea — La Liga / Bundesliga:** FBref layout is identical; `datasets.py` expansion template already in comments.
- **v3 idea — era comps:** "Which EPL player from 2019-20 is most similar to this NBA player from 2023-24?" — cross-era AND cross-sport. Requires careful normalization choices.
- **speed_acceleration axis:** Deferred pending tracking data that gives per-player speed/distance (nba_api has this; EPL requires StatsBomb or similar).
