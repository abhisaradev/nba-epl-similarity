"""
datasets.py — registry so the model runs on ANY (league, season).

Why this works with zero changes to the math: every player is normalized
*within their own dataset*, so the reference population is always that exact
league-season. That means any pairing is valid:
    epl_2023  vs  nba_2023     the headline cross-sport comp
    epl_2023  vs  epl_2024     same league, player evolution year-over-year
    laliga_2023 vs nba_2023    different soccer league, no code change

Two practical wins:
  * FBref uses an IDENTICAL table layout for every league it covers, so the
    soccer ingest code works unchanged for La Liga / Serie A / Bundesliga /
    Ligue 1 — a new league is just a new entry pointing at its CSVs.
  * basketball-reference is identical across NBA seasons; nba_api takes a
    season string, so new NBA seasons are also just new entries.

Adding a dataset = add an entry below. Nothing else changes.
"""

import os

DATASETS = {
    "epl_2023": {
        "sport": "soccer",
        "raw_dir": "data/raw/epl_2023",
        "tables": {
            "main":       "PL_Stats_2023.csv",
            "shooting":   "PL_Stats_2023 - Shooting.csv",
            "defensive":  "PL_Stats_2023 - Defensive Actions.csv",
            "gsc":        "PL_Stats_2023 - Goal and Shot Creation.csv",
            "passing":    "PL_Stats_2023 - Passing.csv",
            "possession": "PL_Stats_2023 - Possession.csv",
            "misc":       "PL_Stats_2023 - Miscellaneous.csv",
        },
        "processed": "data/processed/epl_2023.csv",
        "min_minutes": 900,
    },

    "nba_2023": {
        "sport": "nba",
        "season": "2022-23",            # for nba_api / tracking fetch
        "raw_dir": "data/raw/nba_2023",
        "tables": {
            "per_game": "NBA_Stats_Per_Game_2023.csv",
            "advanced": "NBA_Stats_Per_Game_2023 - Advanced.csv",
            "tracking": "nba_tracking_2023.csv",   # from fetch_nba_tracking.py
        },
        "processed": "data/processed/nba_2023.csv",
        "min_minutes": 500,
    },

    # ---- expansion templates: uncomment, point at files, done ----
    # "laliga_2023": {
    #     "sport": "soccer", "raw_dir": "data/raw/laliga_2023",
    #     "tables": {  # same FBref filenames, different folder
    #         "main": "LaLiga_Stats_2023.csv", "shooting": "...", ...
    #     },
    #     "processed": "data/processed/laliga_2023.csv", "min_minutes": 900,
    # },
    # "nba_2024": {
    #     "sport": "nba", "season": "2023-24", "raw_dir": "data/raw/nba_2024",
    #     "tables": {"per_game": "...", "advanced": "...", "tracking": "..."},
    #     "processed": "data/processed/nba_2024.csv", "min_minutes": 500,
    # },
}


def get(dataset_id):
    if dataset_id not in DATASETS:
        raise KeyError(f"unknown dataset {dataset_id!r}. known: {list(DATASETS)}")
    return DATASETS[dataset_id]


def raw_path(dataset_id, table):
    d = get(dataset_id)
    return os.path.join(d["raw_dir"], d["tables"][table])


def processed_path(dataset_id):
    return get(dataset_id)["processed"]
