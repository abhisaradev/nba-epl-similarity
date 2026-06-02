# Cross-Sport Similarity: Premier League ⇄ NBA

A model that asks "who is the NBA version of this footballer?" (and vice versa) by
scoring every player on the **same set of dimensions** and finding nearest
neighbours *across* sports. Mohamed Salah's closest NBA comp, Rodri's, Haaland's —
computed, not vibes.

The core problem is that soccer and basketball stats live in different units and
distributions. The bridge is **within-sport normalization**: every stat is turned
into a percentile rank *inside its own league-season* before any cross-sport
comparison happens, so "90th-percentile shot volume" means the same thing in both
sports even though the raw numbers don't.

## Example results

Three cross-sport comps, each player overlaid against their nearest NBA neighbour
on the seven dimension axes (dashed ring = league median; spoke size scales with
the query player's defining strengths):

| Erling Haaland → Lauri Markkanen | William Saliba → Anthony Davis | Rodri → Nikola Jokić |
|:---:|:---:|:---:|
| ![Haaland vs Markkanen](examples/haaland_vs_markkanen.png) | ![Saliba vs Davis](examples/saliba_vs_davis.png) | ![Rodri vs Jokić](examples/rodri_vs_jokic.png) |

### Discovered cross-sport archetypes (k=6)

Pooled k-means over both sports (`cluster.py`). Five of six clusters mix soccer and
NBA players — the validation that within-sport normalization makes the sports
comparable. Cluster 1 is NBA-only (a structural gap, not a GK artifact).
Full table: [`examples/archetypes_summary.csv`](examples/archetypes_summary.csv).

| # | Archetype (defining axes) | Soccer | NBA | Soccer exemplars | NBA exemplars |
|---|---|:---:|:---:|---|---|
| 0 | physicality | 77 | 73 | Ben Mee, Mathias Jørgensen, Levi Colwill | Onyeka Okongwu, Paul Reed, Daniel Theis |
| 1 | ball progression | 0 | 43 | — *(NBA-only)* | Duop Reath, Jaime Jaquez Jr., Kris Murray |
| 2 | playmaking | 59 | 61 | Mohammed Kudus, Harry Wilson, James Maddison | Malik Monk, Coby White, Austin Reaves |
| 3 | defensive effectiveness | 63 | 74 | Danilo, Declan Rice, Jefferson Lerma | Franz Wagner, Jalen Johnson, Aaron Gordon |
| 4 | scoring threat | 62 | 15 | Lyle Foster, Abdoulaye Doucouré, Jacob Bruun Larsen | Jerami Grant, Corey Kispert, Duncan Robinson |
| 5 | possession security + playmaking (eff) | 51 | 94 | Ibrahim Sangaré, Oliver Arblaster, Harrison Reed | Julian Champagnie, Shake Milton, Pat Connaughton |

## The dimensions

Players are scored on **7 core dimensions**, each split into a **volume** axis and
an **efficiency** axis (kept separate on purpose — averaging them re-introduces the
"high-usage inefficient scorer looks like a low-usage sniper" failure mode):

| Dimension | What it captures |
|---|---|
| `scoring_threat` | Shot volume + finishing efficiency, with **shot location** folded in (interior vs perimeter) |
| `playmaking` | Chance creation, assists, passing into dangerous areas |
| `ball_progression` | Moving the ball/possession up the field or court |
| `possession_security` | Ball retention, turnover avoidance |
| `defensive_effectiveness` | Tackles/steals/blocks, interceptions, defensive reliability |
| `physicality` | What you're *built* like — height, weight, BMI, aerial/rebound duels |
| `engine` | How much you *motor* — recoveries, hustle activity |

`config.py` defines the dimension → stat mapping per sport; this is the single
place to re-wire which raw columns feed each axis.

### Build index (physicality)

Bio measurements (height, weight) drive a **BMI-based "build" signal** —
imperial `BMI = 703 · weight_lbs / height_in²`. This is the mass-for-frame read:
a 5'8"/170 lb compact player scores denser/stronger than a 6'0"/140 lb lanky one,
exactly as intended. A manual `ALIAS_FBREF_TO_FIFA` map in `ingest_data.py`
bridges players whose FBref display name shares no token with their FIFA
registered name (e.g. Rodri → "Rodrigo Hernández Cascante").

### Shot location

Where a player scores from is folded into `scoring_threat` efficiency rather than
living as its own axis (a standalone interior axis dragged high-volume scorers
toward low-usage putback centers). A **display-only `interior_score`** (0–100) is
also computed for the radar/breakdown readout so location is still visible:
- NBA: low 3PAr + high FTr → high interior (Giannis ≈ 92, Curry ≈ 37)
- Soccer: close average shot distance + high non-penalty xG/shot

## Matching

`similarity.py` ranks cross-sport nearest neighbours. The default
**strengths-weighting** weights each axis by how far *above* the league median the
query player sits — so players match on what they're distinctively **good at**,
not on shared absences (fixes "Haaland matches low-usage shooters because they're
both bad defenders"). Euclidean by default; Mahalanobis and cosine available.

## Archetype clustering

`cluster.py` pools both sports into one space and runs k-means (k chosen by
silhouette, 6–8) to discover **cross-sport archetypes** — clusters that mix soccer
and NBA players are the thesis made literal. Goalkeepers are dropped (no
cross-sport analogue). The soccer/NBA split per cluster is the validation headline:
mixed clusters mean the normalization genuinely makes the sports comparable.

## Pipeline

```
ingest_data.py   raw league/bio CSVs  →  soccer.csv, nba.csv  (wide merged tables)
pipeline.py      filter by minutes → within-sport normalize → 7 dimension axes
similarity.py    weighted cross-sport nearest-neighbour ranking
breakdown.py     per-axis "close HOW?" comparison between two players
radar.py         overlaid radar chart of two players across the axes
cluster.py       pooled k-means → archetype_assignments.csv
config.py        dimension schema (the one place to re-wire stats → axes)
```

Run order: `python ingest_data.py` → then any of `similarity.py`, `radar.py`,
`cluster.py`.

## Data provenance & licensing

**Data files are NOT included in this repository** — they're large and/or not ours
to redistribute. The code expects these inputs locally (all git-ignored):

| Data | Source | Season |
|---|---|---|
| EPL player stats (`PL_Stats_2023*.csv`) | FBref | **2023–24** |
| NBA player stats (`NBA_Stats_*.csv`) | Basketball-Reference | **2022–23** |
| NBA tracking (`nba_tracking_2023.csv`) | NBA.com Stats | 2022–23 |
| Soccer bio height/weight (`soccer_bio_2023.csv`) | FIFA dataset (Hugging Face) | **FIFA 23** |
| NBA bio height/weight (`nba_bio_2023.csv`) | NBA.com | 2022–23 |

> ⚠️ **Note the one-year season offset:** the FBref EPL stats are 2023–24, while
> the NBA stats and the FIFA-sourced soccer bio are 2022–23 / FIFA 23. This is why
> a handful of 2023–24 EPL arrivals (Mitoma, Mainoo, Quansah, Son, Tomiyasu, Endo)
> have no FIFA-23 bio row and run on aerials-only physicality.

## Requirements

Python 3 with `pandas`, `numpy`, `scipy`, `scikit-learn`, `matplotlib`.

```
pip install pandas numpy scipy scikit-learn matplotlib
```
