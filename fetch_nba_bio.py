"""
fetch_nba_bio.py — pull NBA player height/weight from LeagueDashPlayerBioStats.

Run:    python fetch_nba_bio.py [SEASON]     # SEASON default "2022-23"
        python fetch_nba_bio.py 2023-24
Output: nbaapi_bio_<YYYY>.csv  (YYYY = season end year; player, height_in, weight_lbs)

PLAYER_HEIGHT_INCHES is a pre-computed float column — no string parsing needed.
PLAYER_WEIGHT is in lbs.
"""

import sys
import time
import unicodedata
import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerBioStats
from nba_api.stats.library.http import NBAStatsHTTP

DEFAULT_SEASON = "2022-23"
TIMEOUT = 90

NBAStatsHTTP.headers.update({
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token":  "true",
    "Origin":             "https://www.nba.com",
})


def season_suffix(season):
    """'2022-23' -> '2023', '2023-24' -> '2024' (the season end year)."""
    return "20" + season.split("-")[1]


def normalize_name(name):
    nfkd = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def main(season=DEFAULT_SEASON):
    print(f"Fetching NBA bio stats for {season}…", end=" ", flush=True)

    for attempt in range(1, 4):
        try:
            df = LeagueDashPlayerBioStats(
                season=season,
                timeout=TIMEOUT,
            ).get_data_frames()[0]
            print(f"{len(df)} players")
            break
        except Exception as exc:
            print(f"attempt {attempt} failed: {exc}")
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

    df = df[["PLAYER_NAME", "PLAYER_HEIGHT_INCHES", "PLAYER_WEIGHT"]].copy()
    df = df.rename(columns={
        "PLAYER_HEIGHT_INCHES": "height_in",
        "PLAYER_WEIGHT":        "weight_lbs",
    })
    df["height_in"]   = pd.to_numeric(df["height_in"],  errors="coerce")
    df["weight_lbs"]  = pd.to_numeric(df["weight_lbs"], errors="coerce")
    df["player"]      = df["PLAYER_NAME"].apply(normalize_name)
    df = df.drop(columns=["PLAYER_NAME"])
    df = df[["player", "height_in", "weight_lbs"]]
    df = df.drop_duplicates(subset=["player"])

    out = f"nbaapi_bio_{season_suffix(season)}.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} players → {out}")
    print(f"  height coverage: {df['height_in'].notna().sum()}/{len(df)}")
    print(f"  weight coverage: {df['weight_lbs'].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEASON)
