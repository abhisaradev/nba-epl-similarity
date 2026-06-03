# Project File Reference

A living document explaining every file in the NBA/EPL Cross-Sport Similarity project.
Update this whenever a new file is added or the purpose of an existing one changes.

---

## The Core Model (the engine)

**`config.py`** — the brain of the whole project. Defines the 7 dimensions, which raw stats
feed each one, which stats are inverted (lower = better), and the per-dimension weight knobs
(all 1.0 = inert by default). Every major design decision lives here: the Curry rule
(volume and efficiency kept as separate axes so high-volume players don't collapse onto
low-volume efficient ones), the physicality/engine split (build/strength vs motor/hustle,
from the Kanté insight), and the shot-location fold (interior dominance folded into scoring
efficiency, not a standalone axis, so putback centers don't masquerade as dominant scorers).
Change this file to change what the model measures.

**`pipeline.py`** — the normalizer and cross-sport bridge. Reads a merged CSV for one
sport/season, applies within-sport percentile ranking to every stat (so "90th-percentile
passer in EPL" = 90, same as "90th-percentile passer in NBA"), then builds the composite
dimension axes (__vol and __eff suffixes). This within-season normalization is what makes
cross-sport comparison valid — and it's also why the model is blind to league-wide volume
shifts over time (a design property, not a bug). Also carries display-only columns
(interior_score) through without letting them enter the similarity math.

**`similarity.py`** — the matcher. Takes a query player's feature frame and finds their
nearest neighbors in the other sport using weighted Euclidean distance. Default weighting
mode is "strengths-only": each axis is weighted by how far above the league median the
query player sits, so the match emphasizes their distinctive traits rather than treating
all dimensions equally. This fixed the original Haaland-to-floor-spacer bug (Haaland's
low involvement was being weighted, pulling him toward low-usage shooters).

**`breakdown.py`** — the explainer. Shows *why* two players matched: a per-axis percentile
comparison table with gaps, plus the `interior_score()` helper that reads the display-only
interior score (0–100, high = paint dominator) off the feature frame. The interior score
is display-only — it doesn't enter the similarity math, since interior dominance is already
folded into scoring efficiency.

**`radar.py`** — the visualizer. Generates overlaid radar chart PNGs: one polygon per
player on the 14 shared axes (7 dimensions × vol/eff), a dashed median ring, weight-scaled
axis labels (bolder = more distinctive for the query player), and an interior-score
annotation at the bottom showing the display-only readout. Saves PNGs to wherever
`out_path` points; the `__main__` block generates the Haaland radar by default.

**`cluster.py`** — the archetype discoverer (single-season, cross-sport). Pools one EPL
season + one NBA season, drops goalkeepers (they have no cross-sport analogue and would
self-segregate into a degenerate cluster), standardizes the shared axes, sweeps k=6–8 by
silhouette score, and picks the cleanest k. Each cluster is a cross-sport archetype — the
validation headline is that most clusters mix both sports, proving within-season
normalization genuinely makes the sports comparable. The NBA-only ball-progression cluster
is a real structural gap (not a bug) worth reporting: soccer progressors entangle with
playmakers, but the NBA has a distinct drive/transition role without a soccer mirror.

---

## The v2 Modules (multi-season, temporal analysis)

**`drift.py`** — archetype drift over time. The core v2 analysis. Pools EPL 2023-24 + all
nine NBA seasons (~3,500 player-seasons), fits ONE StandardScaler and runs k-means once,
then freezes both the centroids and the scaler to disk (`archetypes_frozen.pkl`). Every
player-season across all datasets is then assigned to its nearest frozen archetype — never
re-clustered, never re-scaled. This frozen-centroid approach is what makes "drift" meaningful:
LeBron moving from archetype 3 to archetype 5 means something only if the archetype
definitions don't move. Produces two outputs: (A) league-wide composition over time (what
share of the NBA falls in each archetype each season → the stacked area chart), and (B)
individual player trajectories (a player's archetype + distance-to-centroid across every
season they appear in). Uses fillna(0.5) NOT fillna(50) — the axes are 0–1 percentile
fractions, and 50 would inject catastrophic outliers, especially in 2015-16 where hustle
stats (engine__vol) are missing for 60% of players.

**`era_trends.py`** — the complementary cross-era lens. Where drift.py measures structural
re-sorting (blind to tides by construction), era_trends.py measures raw league averages
over time — deliberately NOT within-season normalized. Computes league-average shooting
and efficiency signals for each NBA season (3PAr, FTr, TS%, eFG%, TOV%, AST%) indexed to
their 2015-16 value so signals on different scales are comparable. Shows both rate (3PAr =
3PA/FGA) and raw (3PA/game) so the pace-vs-style question is visible: if 3PAr rises while
FGA/game stays flat, the 3-point boom is a style choice, not just pace inflation. Confirmed:
3PAr rose 0.282 → 0.402 (+42.6%) while FGA/game rose only +6.7% — the rise is almost
entirely the rate. Does not touch the cross-sport model or the frozen archetypes.

---

## The Data Plumbing

**`ingest_data.py`** — the builder. The most complex file. Registry-driven: reads the
datasets.py entry for a given dataset_id, dispatches to build_soccer() or build_nba() by
sport, reads filenames from the registry instead of hardcoded strings, and writes to
processed/<id>.csv plus backward-compat aliases (soccer.csv, nba.csv). Preserves all
guards and logic: ALIAS_FBREF_TO_FIFA map for players whose FBref name shares no token
with their FIFA long_name (e.g. Rodri → "Rodrigo Hernández Cascante"), token-sort +
subset-fallback name matching for bio merges, row-count guard (merge must not change row
count), bio coverage gate (fails loudly if weight coverage < 85%), BMI computation
(703 * lbs / in²), 3PAr/FTr computed per-game (overwriting bbref Advanced versions for
consistency), and display-only interior_score on both tables.

**`datasets.py`** — the registry. One entry per dataset. Each entry records the sport,
the true season (important — the original bbref NBA files were mislabeled as 2022-23 but
actually contained 2023-24 data, caught via LeBron spot-check, now retired), the raw_dir,
a tables dict pointing at the actual filenames, the processed output path, and min_minutes.
NBA datasets are generated programmatically from NBA_SEASONS (2015-16 through 2023-24),
all from nba_api via nbaapi_* prefixed files. Adding a new season = one new entry or one
new season string. The backward-compat aliases in ingest_data.py point nba.csv at nba_2324
(2023-24 nba_api), correctly pairing with the 2023-24 EPL data for the headline comparison.

**`fetch_nba_base.py`** — pulls per-game + advanced base stats from nba_api
(LeagueDashPlayerStats), maps nba_api column names to the exact bbref column names that
ingest_data.build_nba() and config.py expect. Critical: _PCT columns are 0–1 in nba_api
but some are 0–100 in bbref — the script handles the rescaling. TM_TOV_PCT is already
on the bbref scale (~0–20) and must NOT be ×100. DBPM is bbref-only and comes back NaN
throughout — this is expected and noted. Output: nbaapi_base_<YYYY>.csv.

**`fetch_nba_tracking.py`** — pulls drives, touches, potential assists, contested shots,
box-outs, and DEF_RATING from nba_api (five endpoints: Possessions, Drives, Passing,
Hustle, Advanced). Parameterized by season string; defaults to 2022-23. Uses retry/backoff
and patched Chrome headers (the nba-stats-origin / nba-stats-token fields the API requires).
Output: nbaapi_tracking_<YYYY>.csv.

**`fetch_nba_bio.py`** — pulls height (inches) and weight (lbs) from
LeagueDashPlayerBioStats. PLAYER_HEIGHT_INCHES is a pre-computed float — no string parsing.
Output: nbaapi_bio_<YYYY>.csv.

**`fetch_all_seasons.py`** — resilient batch driver. Runs all three fetch scripts across a
list of seasons with per-step try/except (a failure in one season/endpoint logs and
continues rather than killing the whole run), plus a 3-second inter-season sleep to be
polite to the API. The driver caught and recovered from 2020-21 JSONDecodeErrors (a known
nba_api hiccup) during the initial backfill.

---

## The Examples Folder (what renders on GitHub)

`examples/haaland_vs_markkanen.png` — radar: Erling Haaland vs Lauri Markkanen. The
headline EPL→NBA comp. Shows the "tall, do-it-yourself scoring forward" shape: high scoring
threat, physicality, low everything else. Interior score annotation (Haaland 87, Markkanen
55) shows the one place the match is loose — Haaland is a far more interior scorer.

`examples/saliba_vs_davis.png` — radar: William Saliba vs Anthony Davis. The "two-way
defensive anchor" shape: fat across defense/physicality/engine, thin on scoring/playmaking.
Interior scores match (89/89) — both dominate near their own goal/rim.

`examples/rodri_vs_jokic.png` — radar: Rodri vs Nikola Jokić. The tightest overlap of
the three — nearly the whole wheel filled on playmaking, possession, ball progression,
physicality. The best comp on the board: both are the deep-lying brain of an elite team.

`examples/archetypes_summary.csv` — the k=6 single-season cross-sport archetype table
(cluster.py output): archetype label, soccer count, NBA count, exemplars from each sport.
5 of 6 clusters mix both sports — the validation that within-season normalization works.

`examples/nba_archetype_drift.png` — stacked area chart (drift.py output): how the NBA's
archetype composition shifts 2015-16 → 2023-24 using frozen cross-sport archetypes. Shows
structural re-sorting — the big-man decline is visible, the 3-point boom is NOT (because
within-season normalization erases uniform tides by construction; that's a feature, not a
bug). Complements era_trends.

`examples/nba_archetype_drift.csv` — the underlying composition data for the drift chart.

`examples/nba_era_trends.png` — indexed trend lines (era_trends.py output): raw league
averages over time, indexed to 2015-16 = 100. The complementary lens to drift.py. The
3-point revolution is now visible (3PAr +42.6%, FGA/game only +6.7% — style choice, not
pace). Two modules, two different questions, each honest about what it sees.

`examples/nba_era_trends.csv` — the underlying trend data for the era trends chart.

---

## Generated Outputs (in root / processed/, gitignored)

`archetypes_frozen.pkl` — the frozen StandardScaler + k-means centroids from drift.py.
The yardstick everything is measured against. Never re-fit after the initial freeze or
drift becomes meaningless. Defined over ~3,500 player-seasons (EPL 2023-24 + all 9 NBA
seasons pooled) so no single era dominates the archetype definitions.

`archetype_drift_assignments.csv` — every player-season's assigned archetype and distance
to centroid (output of drift.py's assign step). High distance = player doesn't fit any
archetype cleanly (cross-sport coarseness showing up honestly).

`soccer.csv` / `soccer_merged.csv` — backward-compat alias for processed/epl_2324.csv.
The 2023-24 EPL merged table (570 rows, 152 columns) with all bio merges, BMI, interior
score. What similarity.py and cluster.py read by default.

`nba.csv` / `nba_merged.csv` — backward-compat alias for processed/nba_2324.csv. The
2023-24 NBA merged table from nba_api. Correctly pairs with the 2023-24 EPL data for the
headline cross-sport comparison.

`processed/epl_2324.csv` — the canonical EPL 2023-24 processed table.

`processed/nba_1516.csv` through `processed/nba_2324.csv` — all nine NBA seasons (2015-16
through 2023-24), each built via ingest_data.build(), each with 3PAr/FTr/interior_score,
100% bio coverage, DBPM all-NaN (bbref-only, not in nba_api).

---

## Raw Data (gitignored — lives only on your machine, never committed)

`PL_Stats_2023.csv` + 6 supplementary tables — **IRREPLACEABLE**. A snapshot of FBref's
full advanced EPL stats from before Opta/Stats Perform pulled their data (~January 2026).
These tables no longer exist at the source. Backed up separately (confirmed). The entire
soccer side of the model runs on these files. Contains: standard stats, shooting, defensive
actions, goal and shot creation, passing, possession, miscellaneous.

`soccer_bio_2023.csv` — FIFA 23 (update 9) height/weight for ~18,100 players, extracted
from male_players.csv (5GB Hugging Face/Kaggle file). 98.2% coverage on the 900-minute
EPL pool after the ALIAS_FBREF_TO_FIFA map. 6 players missing (Mitoma, Mainoo, Quansah,
Son, Tomiyasu, Endo) — 2023-24 arrivals the FIFA 23 (2022) game predates.

`male_players.csv` — the 5GB FIFA 23 source file. Gitignored permanently. Never enters
the repo; soccer_bio_2023.csv is the pre-extracted lightweight version.

`NBA_Stats_Per_Game_2023.csv` + `NBA_Stats_Per_Game_2023 - Advanced.csv` — the original
bbref files. MISLABELED: despite the "2023" name, these contain 2023-24 season data
(verified via LeBron stats: perfect 1.0000 correlation to nba_api 2023-24, clearly
different from real 2022-23). Retained for reference but retired from the pipeline.

`nbaapi_base_<YYYY>.csv`, `nbaapi_tracking_<YYYY>.csv`, `nbaapi_bio_<YYYY>.csv` — raw
nba_api pulls for each season (YYYY = season end year: 2016 = 2015-16). All nine seasons
present (2016–2024). Inputs to ingest_data.build() via the datasets.py registry.

`nba_bio_2023.csv`, `nba_tracking_2023.csv` — the original nba_api pulls that predated
the nbaapi_ prefix convention. Still valid; the 2022-23 season's nbaapi_bio_2023.csv
supersedes them but they're kept as originals.

---

## Key Design Decisions (so future sessions don't re-debate settled questions)

**Within-season normalization is intentional and load-bearing.** It's what makes
cross-sport comparison valid AND what makes the model blind to league-wide tides. Don't
change it without knowing both effects. The two-lens approach (drift.py + era_trends.py)
is the answer to "but what about the 3-point boom" — not re-normalization.

**Strengths-only weighting (not equal, not symmetric).** Equal weighting failed because
Haaland's low involvement got weighted, pulling him to low-usage shooters. Symmetric
weighting failed for similar reasons. Strengths-only: weight each axis by how far ABOVE
league median the query player sits.

**Interior score is display-only.** The 3PAr/FTr (NBA) and Dist/npxG-per-shot (soccer)
signals are folded INTO scoring_threat efficiency, not a standalone axis. Standalone pulled
Haaland to putback centers (high interior score + low volume = same as Haaland's interior
score but wrong on everything else). Folded-in, the volume axis in the same dimension
separates them correctly. The display-only interior_score column surfaces the signal on
the radar/breakdown without it entering the distance calculation.

**DBPM is always NaN.** Basketball-reference's Defensive Box Plus/Minus is a bbref
proprietary computation not available in nba_api. Expected, documented, not a bug.

**The bbref nba_2223 files were mislabeled.** NBA_Stats_Per_Game_2023*.csv contains
2023-24 data. Verified via LeBron spot-check (perfect 1.0000 PTS correlation to nba_api
2023-24; clearly different from real 2022-23 at 28.9 PTS/55G). Retired from pipeline.

**Soccer advanced stats are a one-season snapshot.** FBref removed all Opta/Stats Perform
advanced data ~January 2026. The PL_Stats_2023* files are a snapshot from before the
removal. Future multi-season soccer expansion requires a new source (StatsBomb open data
is the planned route for multi-league expansion, but needs an events-to-season-stats
aggregation layer — a separate sub-project, not yet built).

---

## Roadmap (logged, not yet built)

- Hand-name the archetypes (6-line dict, quick win — functional labels → evocative names)
- CLAUDE.md for session continuity (Claude Code reads it automatically)
- Team-context / usage normalization (share-of-team metrics to separate player from system)
- StatsBomb open-data aggregator for multi-league soccer expansion (2015-16 Big-5 is free)
- FIFA/EA FC PlayStyles as categorical archetype-labeling tags (off-ball workaround)
- Legends mode (reduced-feature variant on historical box-score-equivalent stats only)
- Interactive website (input player + year → see counterpart, capstone feature)
