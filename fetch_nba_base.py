"""
fetch_nba_base.py — pull per-game + advanced base stats from nba_api
(LeagueDashPlayerStats), mapped to the EXACT bbref column names that
ingest_data.build_nba() and config.py expect, so the nba_api-sourced season is a
drop-in for the old bbref CSVs.

Run:    python fetch_nba_base.py [SEASON]     # SEASON default "2022-23"
        python fetch_nba_base.py 2023-24
Output: nbaapi_base_<YYYY>.csv   (YYYY = season end year)

Two measures merged on PLAYER_ID:
  Base measure (PerGame)     → counting stats (FGA, 3PA, FTA, PTS, AST, TOV, …)
  Advanced measure (PerGame) → TS%, eFG%, AST%, DRB%, TOV%, USG%, …

Scale note: nba_api *_PCT fields are 0–1. bbref keeps the shooting splits
(FG%/3P%/FT%/eFG%/TS%) on 0–1 too, but the rate stats (DRB%/AST%/TOV%/USG%/…)
on 0–100. We rescale the latter ×100 so values land in the same range as the
bbref-sourced season.

Not available from nba_api (bbref-only): DBPM (used by config) is emitted as NaN;
PER / Win Shares / BPM / VORP / 2P splits are dropped (config doesn't use them).
DEF_RATING is intentionally NOT included here — it comes from the tracking file,
exactly as it did for the bbref-sourced season (avoids a double column).
"""

import sys
import time
import unicodedata
import numpy as np
import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats
from nba_api.stats.library.http import NBAStatsHTTP

DEFAULT_SEASON = "2022-23"
TIMEOUT = 90

NBAStatsHTTP.headers.update({
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token":  "true",
    "Origin":             "https://www.nba.com",
})

# nba_api -> bbref name. ×1 (same scale as bbref).
_BASE_RENAME = {
    "TEAM_ABBREVIATION": "Team", "AGE": "Age", "GP": "G", "MIN": "MP",
    "FGM": "FG", "FGA": "FGA", "FG_PCT": "FG%",
    "FG3M": "3P", "FG3A": "3PA", "FG3_PCT": "3P%",
    "FTM": "FT", "FTA": "FTA", "FT_PCT": "FT%",
    "OREB": "ORB", "DREB": "DRB", "REB": "TRB",
    "AST": "AST", "TOV": "TOV", "STL": "STL", "BLK": "BLK", "PF": "PF", "PTS": "PTS",
}
# Advanced columns that are ALREADY on bbref's scale (no rescale):
#  - TS_PCT / EFG_PCT are 0–1 in both nba_api and bbref.
#  - TM_TOV_PCT is a turnovers-per-100 ratio (~0–20), same range as bbref TOV%
#    (different formula, but comparable scale — do NOT ×100).
_ADV_RENAME_UNIT = {"TS_PCT": "TS%", "EFG_PCT": "eFG%", "TM_TOV_PCT": "TOV%"}
# Rate stats that are 0–1 fractions in nba_api but 0–100 in bbref, so ×100.
_ADV_RENAME_PCT100 = {
    "AST_PCT": "AST%", "DREB_PCT": "DRB%", "OREB_PCT": "ORB%",
    "REB_PCT": "TRB%", "USG_PCT": "USG%",
}


def season_suffix(season):
    """'2022-23' -> '2023', '2023-24' -> '2024' (the season end year)."""
    return "20" + season.split("-")[1]


def normalize_name(name):
    """Strip diacritics: Dončić → Doncic, Jokić → Jokic."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _fetch(label, measure, season, retries=3):
    for attempt in range(1, retries + 1):
        try:
            print(f"  fetching {label}…", end=" ", flush=True)
            df = LeagueDashPlayerStats(
                season=season,
                measure_type_detailed_defense=measure,
                per_mode_detailed="PerGame",
                timeout=TIMEOUT,
            ).get_data_frames()[0]
            print(f"{len(df)} rows")
            time.sleep(0.6)
            return df
        except Exception as exc:
            print(f"attempt {attempt} failed: {type(exc).__name__}: {exc}")
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"  retrying in {wait}s…")
            time.sleep(wait)


def main(season=DEFAULT_SEASON):
    print(f"Fetching NBA base + advanced stats for {season}\n")

    base = _fetch("Base (PerGame)", "Base", season)
    adv = _fetch("Advanced (PerGame)", "Advanced", season)

    base_cols = ["PLAYER_ID", "PLAYER_NAME"] + list(_BASE_RENAME)
    b = base[base_cols].rename(columns=_BASE_RENAME)

    adv_pct = list(_ADV_RENAME_UNIT) + list(_ADV_RENAME_PCT100)
    a = adv[["PLAYER_ID"] + adv_pct].rename(
        columns={**_ADV_RENAME_UNIT, **_ADV_RENAME_PCT100})
    for bbref_name in _ADV_RENAME_PCT100.values():
        a[bbref_name] = pd.to_numeric(a[bbref_name], errors="coerce") * 100.0

    df = b.merge(a, on="PLAYER_ID", how="outer")

    # Diacritic-stripped name key, matching the tracking/bio fetch + bbref join.
    df["Player"] = df["PLAYER_NAME"].apply(normalize_name)
    df = df.drop(columns=["PLAYER_ID", "PLAYER_NAME"])

    # bbref-only stat config expects but nba_api doesn't provide -> NaN.
    df["DBPM"] = np.nan

    # Order: Player/Team/Age first, then the rest as mapped.
    lead = ["Player", "Team", "Age"]
    df = df[lead + [c for c in df.columns if c not in lead]]
    df = df.drop_duplicates(subset=["Player"])

    out = f"nbaapi_base_{season_suffix(season)}.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} players → {out}")
    print("Columns:", list(df.columns))
    print("  (DBPM intentionally all-NaN — bbref-only; DEF_RATING comes from tracking)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEASON)
