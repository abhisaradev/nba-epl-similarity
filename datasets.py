"""
datasets.py — registry so the model runs on ANY (league, season).

Why this works with zero changes to the math: every player is normalized
*within their own dataset*, so the reference population is always that exact
league-season. That means any pairing is valid:
    epl_2324  vs  nba_2324     the headline cross-sport comp (same season)
    nba_1516  vs  nba_2324     same league, era-over-era evolution
    laliga_2324 vs nba_2324    different soccer league, no code change

Two practical wins:
  * FBref uses an IDENTICAL table layout for every league it covers, so the
    soccer ingest code works unchanged for La Liga / Serie A / Bundesliga /
    Ligue 1 — a new league is just a new entry pointing at its CSVs.
  * nba_api is identical across NBA seasons and takes a season string, so every
    NBA season is generated from one helper below (one consistent source).

NBA PROVENANCE NOTE: the original bbref CSVs (NBA_Stats_Per_Game_2023*.csv) were
labelled "2023" but actually contain 2023-24 data (verified: their per-game
stats match nba_api's 2023-24 exactly, corr 1.0). That bbref-sourced `nba_2223`
entry has been RETIRED. All NBA datasets now come from nba_api via the
nbaapi_*_<YYYY>.csv files (YYYY = season end year). Hustle/tracking stats don't
exist before 2015-16, so that's the earliest season.

`true_season` is the ACTUAL season the data covers. Files live in the project
root, so `raw_dir` is ".".
"""

import os

# NBA seasons available from nba_api with full tracking+hustle coverage.
NBA_SEASONS = [
    "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
    "2020-21", "2021-22", "2022-23", "2023-24",
]


def _season_yy(season):
    """'2015-16' -> '2016' (season end year, used in the nbaapi_ filenames)."""
    return "20" + season.split("-")[1]


def _nba_id(season):
    """'2015-16' -> 'nba_1516'."""
    return "nba_" + season[2:4] + season.split("-")[1]


def _nba_entry(season):
    yy = _season_yy(season)
    return {
        "sport": "nba",
        "true_season": season,
        "season": season,                # for nba_api / fetch scripts
        "raw_dir": ".",
        "tables": {
            # base + advanced live in ONE nba_api file; pointing both keys at it
            # makes build_nba() take its single-file path (no per_game↔advanced
            # merge). tracking + bio are separate nba_api pulls.
            "per_game": f"nbaapi_base_{yy}.csv",
            "advanced": f"nbaapi_base_{yy}.csv",
            "tracking": f"nbaapi_tracking_{yy}.csv",
            "bio":      f"nbaapi_bio_{yy}.csv",
        },
        "processed": f"processed/{_nba_id(season)}.csv",
        "min_minutes": 500,
    }


DATASETS = {
    "epl_2324": {
        "sport": "soccer",
        "true_season": "2023-24",        # FBref EPL stats season
        "raw_dir": ".",
        "tables": {
            "main":       "PL_Stats_2023.csv",
            "shooting":   "PL_Stats_2023 - Shooting.csv",
            "defensive":  "PL_Stats_2023 - Defensive Actions.csv",
            "gsc":        "PL_Stats_2023 - Goal and Shot Creation.csv",
            "passing":    "PL_Stats_2023 - Passing.csv",
            "possession": "PL_Stats_2023 - Possession.csv",
            "misc":       "PL_Stats_2023 - Miscellaneous.csv",
            "bio":        "soccer_bio_2023.csv",   # FIFA 23 height/weight (soccer-only)
        },
        "processed": "processed/epl_2324.csv",
        "min_minutes": 900,
    },
}

# One NBA dataset per season, all from nba_api (nba_1516 … nba_2324).
for _s in NBA_SEASONS:
    DATASETS[_nba_id(_s)] = _nba_entry(_s)

# RETIRED: "nba_2223" used to point at the bbref NBA_Stats_Per_Game_2023*.csv
# files, but those were mislabeled 2023-24 data (see provenance note above). The
# id nba_2223 now correctly maps to genuine 2022-23 data from nba_api.

# ---- soccer expansion template: uncomment, point at files, done ----
# "laliga_2324": {
#     "sport": "soccer", "true_season": "2023-24", "raw_dir": "data/raw/laliga_2324",
#     "tables": {  # same FBref filenames, different folder
#         "main": "LaLiga_Stats.csv", "shooting": "...", ..., "bio": "laliga_bio.csv",
#     },
#     "processed": "processed/laliga_2324.csv", "min_minutes": 900,
# },


def get(dataset_id):
    if dataset_id not in DATASETS:
        raise KeyError(f"unknown dataset {dataset_id!r}. known: {list(DATASETS)}")
    return DATASETS[dataset_id]


def raw_path(dataset_id, table):
    d = get(dataset_id)
    return os.path.join(d["raw_dir"], d["tables"][table])


def processed_path(dataset_id):
    return get(dataset_id)["processed"]
