"""
fetch_nba_tracking.py — pull 2022-23 tracking stats from stats.nba.com.

Run once:  python fetch_nba_tracking.py
Output:    nba_tracking_2023.csv  (keyed on diacritic-stripped player name)

Endpoints:
  LeagueDashPtStats  Possessions  → TOUCHES, PTS_PER_TOUCH
  LeagueDashPtStats  Drives       → DRIVES, DRIVE_FG_PCT
  LeagueDashPtStats  Passing      → POTENTIAL_AST
  LeagueHustleStatsPlayer         → CONTESTED_SHOTS, BOX_OUTS
  LeagueDashPlayerStats Advanced  → DEF_RATING
"""

import time
import unicodedata
import pandas as pd
from nba_api.stats.endpoints import (
    LeagueDashPtStats,
    LeagueHustleStatsPlayer,
    LeagueDashPlayerStats,
)

SEASON  = "2022-23"
TIMEOUT = 90   # stats.nba.com is slow and sometimes requires a long wait

# Augment the library's built-in Chrome 145 headers rather than replacing them.
# Passing a custom headers= dict to endpoints *replaces* the defaults and strips
# modern fields (Sec-Ch-Ua, Sec-Fetch-Dest …) that the site checks.
from nba_api.stats.library.http import NBAStatsHTTP
NBAStatsHTTP.headers.update({
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token":  "true",
    "Origin":             "https://www.nba.com",
})


def normalize_name(name):
    """Strip diacritics: Dončić → Doncic, Jokić → Jokic."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _fetch(label, endpoint_cls, retries=3, **kwargs):
    for attempt in range(1, retries + 1):
        try:
            print(f"  fetching {label}…", end=" ", flush=True)
            # No headers= kwarg: let the library use its built-in Chrome 145
            # defaults (already patched above with the nba-stats-token fields).
            df = endpoint_cls(
                season=SEASON,
                timeout=TIMEOUT,
                **kwargs,
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


def _keep(df, *cols):
    """Return only the columns that exist; warn about any that don't."""
    present = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"    ⚠ columns not found (skipped): {missing}")
    return df[present]


def main():
    print(f"Fetching NBA tracking stats for {SEASON}\n")

    # ── Possessions: touches, points per touch ────────────────────────────────
    # player_or_team defaults to "Team"; must set "Player" for player-level rows
    poss = _keep(
        _fetch("Possessions", LeagueDashPtStats,
               pt_measure_type="Possessions", per_mode_simple="PerGame",
               player_or_team="Player"),
        "PLAYER_NAME", "TOUCHES", "PTS_PER_TOUCH",
    )

    # ── Drives: drives, drive FG% ─────────────────────────────────────────────
    drv = _keep(
        _fetch("Drives", LeagueDashPtStats,
               pt_measure_type="Drives", per_mode_simple="PerGame",
               player_or_team="Player"),
        "PLAYER_NAME", "DRIVES", "DRIVE_FGA", "DRIVE_FG_PCT",
    )

    # ── Passing: potential assists ────────────────────────────────────────────
    pas = _keep(
        _fetch("Passing", LeagueDashPtStats,
               pt_measure_type="Passing", per_mode_simple="PerGame",
               player_or_team="Player"),
        "PLAYER_NAME", "POTENTIAL_AST",
    )

    # ── Hustle: contested shots, box outs ─────────────────────────────────────
    hus = _keep(
        _fetch("Hustle", LeagueHustleStatsPlayer, per_mode_time="PerGame"),
        "PLAYER_NAME", "CONTESTED_SHOTS", "BOX_OUTS", "DEF_BOXOUTS",
    )

    # ── Advanced: defensive rating ────────────────────────────────────────────
    # param is measure_type_detailed_defense; per-mode is per_mode_detailed
    adv = _keep(
        _fetch("Advanced (DEF_RATING)", LeagueDashPlayerStats,
               measure_type_detailed_defense="Advanced",
               per_mode_detailed="PerGame"),
        "PLAYER_NAME", "DEF_RATING",
    )

    # ── Merge all five on PLAYER_NAME ─────────────────────────────────────────
    merged = poss
    for frame in (drv, pas, hus, adv):
        merged = merged.merge(frame, on="PLAYER_NAME", how="outer")

    # Normalize names so BBRef join works (Dončić → Doncic etc.)
    merged["player"] = merged["PLAYER_NAME"].apply(normalize_name)
    merged = merged.drop(columns=["PLAYER_NAME"])
    merged = merged[["player"] + [c for c in merged.columns if c != "player"]]

    out = "nba_tracking_2023.csv"
    merged.to_csv(out, index=False)
    print(f"\nWrote {len(merged)} players → {out}")
    print("Columns:", list(merged.columns))


if __name__ == "__main__":
    main()
