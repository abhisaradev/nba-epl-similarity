"""
fetch_all_seasons.py — pull base + tracking + bio from nba_api for a list of
seasons, one consistent source. Resilient: a failure in one (season, endpoint)
is logged and skipped so the rest of the run continues.

Run:  python fetch_all_seasons.py 2015-16 2016-17 ...    (seasons as args)
      python fetch_all_seasons.py                         (defaults to the full
                                                           pre-2023-24 backfill)
"""

import sys
import time

import fetch_nba_base
import fetch_nba_tracking
import fetch_nba_bio

DEFAULT_SEASONS = [
    "2015-16", "2016-17", "2017-18", "2018-19",
    "2019-20", "2020-21", "2021-22", "2022-23",
]

SLEEP_BETWEEN_SEASONS = 3   # be polite to stats.nba.com


def run(seasons):
    failures = []
    for i, season in enumerate(seasons):
        print(f"\n{'='*60}\nSEASON {season}\n{'='*60}")
        for name, mod in (("base", fetch_nba_base),
                          ("tracking", fetch_nba_tracking),
                          ("bio", fetch_nba_bio)):
            try:
                mod.main(season)
            except Exception as exc:
                msg = f"{season} / {name}: {type(exc).__name__}: {exc}"
                print(f"  !! FAILED {msg} — continuing")
                failures.append(msg)
        if i < len(seasons) - 1:
            time.sleep(SLEEP_BETWEEN_SEASONS)

    print(f"\n{'='*60}\nDONE — {len(seasons)} seasons attempted")
    if failures:
        print(f"{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("no failures")


if __name__ == "__main__":
    run(sys.argv[1:] or DEFAULT_SEASONS)
