"""
fetch_nba_bio.py — pull 2022-23 NBA player height/weight from LeagueDashPlayerBioStats.

Run once:  python fetch_nba_bio.py
Output:    nba_bio_2023.csv  (player, height_in, weight_lbs)

PLAYER_HEIGHT_INCHES is a pre-computed float column — no string parsing needed.
PLAYER_WEIGHT is in lbs.
"""

import time
import unicodedata
import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerBioStats
from nba_api.stats.library.http import NBAStatsHTTP

SEASON  = "2022-23"
TIMEOUT = 90

NBAStatsHTTP.headers.update({
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token":  "true",
    "Origin":             "https://www.nba.com",
})


def normalize_name(name):
    nfkd = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def main():
    print(f"Fetching NBA bio stats for {SEASON}…", end=" ", flush=True)

    for attempt in range(1, 4):
        try:
            df = LeagueDashPlayerBioStats(
                season=SEASON,
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

    out = "nba_bio_2023.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} players → {out}")
    print(f"  height coverage: {df['height_in'].notna().sum()}/{len(df)}")
    print(f"  weight coverage: {df['weight_lbs'].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main()
