"""
era_trends.py — ABSOLUTE NBA league style trends over time (2015-16 → 2023-24).

SIBLING TO drift.py — DIFFERENT QUESTION. Keep them separate:
  * drift.py        within-season-normalized archetype re-sorting. By design it is
                    BLIND to league-wide tides (percentile ranks erase any shift
                    that lifts everyone equally — e.g. the 3-point revolution).
  * era_trends.py   the opposite lens: RAW league averages per season, explicitly
                    NOT within-season normalized. This is where a league-wide tide
                    like rising three-point volume becomes visible.

This module is self-contained: it reads processed/nba_<id>.csv directly and does
NOT import pipeline / cluster / drift, nor touch the frozen archetypes.

PACE CAVEAT (why rates, not counts): raw per-game counts (e.g. 3PA/game) rise
partly because the league plays faster (more possessions), not only because teams
choose threes more often. SHARES/RATES divide that out:
    3PAr = 3PA / FGA   (what FRACTION of a team's shots are threes)
is pace-independent — it isolates the *choice* to shoot threes. We report BOTH
3PAr (rate) and 3PA/game (raw) side by side so the pace contribution is explicit.

League average = mean across qualified players (minutes >= 500, the same filter
pipeline.load_sport uses), one vote per qualified player.

UNITS in the output table:
    3PAr, FTr, TS%, eFG%   fractions (0..1)        [native nba_api scale]
    TOV%, AST%             percent   (0..100)       [native nba_api scale]
    3PA_pg, FGA_pg         per-game counts
Mixed scales are intentional (native); the chart converts fractions to % and
puts raw 3PA/game on a secondary axis.

Outputs:
    examples/nba_era_trends.csv     season-by-season league averages
    examples/nba_era_trends.png     multi-line RAW trend chart (rendered on demand)
"""

import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import datasets   # only for the season list + processed-path convention

MIN_MINUTES = 500
SEASONS = list(datasets.NBA_SEASONS)            # 2015-16 ... 2023-24

# Columns the shooting/efficiency trends depend on (used for the thin-data check).
_SHOOTING_COLS = ["3PA", "FGA", "FTA", "PTS"]


def _load_qualified(season):
    """Processed NBA CSV for a season, filtered to qualified players."""
    ds = datasets._nba_id(season)
    df = pd.read_csv(datasets.processed_path(ds))
    return df[df["minutes"] >= MIN_MINUTES].copy()


def season_row(season):
    """League averages (mean across qualified players) of the style signals."""
    q = _load_qualified(season)
    threepar = (q["3PA"] / q["FGA"])            # == the 3PAr column (verified)
    ftr      = (q["FTA"] / q["FGA"])
    return {
        "season": season,
        "n_qualified": len(q),
        # --- spacing: rate vs raw (the pace caveat lives in this pair) ---
        "3PAr":   threepar.mean(),              # fraction of shots that are 3s
        "3PA_pg": q["3PA"].mean(),              # raw per-game (pace-contaminated)
        "FGA_pg": q["FGA"].mean(),              # context for the rate
        # --- other style signals (rates/shares, pace-robust) ---
        "FTr":    ftr.mean(),
        "TS%":    q["TS%"].mean(),
        "eFG%":   q["eFG%"].mean(),
        "TOV%":   q["TOV%"].mean(),
        "AST%":   q["AST%"].mean(),             # assist RATE (not raw assists)
    }


def build_table():
    """Season-by-season league-average table (one row per season)."""
    return pd.DataFrame([season_row(s) for s in SEASONS]).set_index("season")


def thin_data_report():
    """Per-season NaN counts in the shooting/efficiency inputs (item 4).

    drift.py's 2015-16 gap was hustle/engine (CONTESTED_SHOTS/BOX_OUTS); shooting
    columns should be fully populated everywhere. This confirms it explicitly.
    """
    rows = []
    for s in SEASONS:
        q = _load_qualified(s)
        rec = {"season": s, "n_qualified": len(q)}
        for c in _SHOOTING_COLS + ["3PAr", "FTr", "TS%", "eFG%", "TOV%", "AST%"]:
            rec[c] = int(q[c].isna().sum()) if c in q.columns else -1   # -1 = absent
        rows.append(rec)
    return pd.DataFrame(rows).set_index("season")


def write_csv(table, path="examples/nba_era_trends.csv"):
    os.makedirs("examples", exist_ok=True)
    table.round(4).to_csv(path)
    return path


# Signals to plot, in a stable order. Raw counts (3PA_pg, FGA_pg) are included
# alongside the 3PAr rate ON THE SAME INDEXED AXIS so the pace contribution is
# visible: if 3PA/game climbs faster than 3PAr, the gap is pace (FGA growth).
_PLOT_SIGNALS = ["3PAr", "3PA_pg", "FGA_pg", "FTr", "TS%", "eFG%", "TOV%", "AST%"]
_PRETTY = {
    "3PAr": "3PAr (3P share, rate)", "3PA_pg": "3PA/game (raw)",
    "FGA_pg": "FGA/game (raw)", "FTr": "FTr (FT rate)",
    "TS%": "TS%", "eFG%": "eFG%", "TOV%": "TOV%", "AST%": "AST%",
}


def index_to_base(table, signals=_PLOT_SIGNALS):
    """Each signal rescaled so its 2015-16 value = 100 (a line at 120 = +20%).

    Indexing is what lets 0..1 rates (3PAr, TS%) and 0..100 rates (TOV%, AST%)
    and raw counts (3PA/game) share ONE axis without the small movers flattening:
    every line is now '% of its own starting value'.
    """
    base = table.iloc[0]
    return pd.DataFrame({s: table[s] / base[s] * 100.0 for s in signals},
                        index=table.index)


def plot_trends(table, path="examples/nba_era_trends.png"):
    """RAW league trends, every signal INDEXED to 2015-16 = 100 (% change from the
    start). Explicitly NOT within-season normalized — the absolute-tide sibling of
    drift.py's structural view."""
    os.makedirs("examples", exist_ok=True)
    idx = index_to_base(table)
    x = np.arange(len(table.index))

    # order the legend by total move (biggest mover first) for readability
    order = (idx.iloc[-1] - 100).abs().sort_values(ascending=False).index.tolist()
    colors = plt.cm.tab10(np.linspace(0, 1, len(order)))

    fig, ax = plt.subplots(figsize=(12.5, 7.5))
    ax.axhline(100, color="grey", lw=1, ls=":", zorder=0)
    ax.text(0, 100.4, "2015-16 baseline (no change)", color="grey", fontsize=8)
    for col, c in zip(order, colors):
        end = idx[col].iloc[-1]
        ax.plot(x, idx[col].values, marker="o", lw=2, color=c,
                label=f"{_PRETTY[col]}   (→{end:.0f}, {end-100:+.0f}%)")

    ax.set_xticks(x)
    ax.set_xticklabels(table.index, rotation=45, ha="right")
    ax.set_ylabel("indexed to 2015-16 = 100   (% of starting value)")
    ax.set_title("NBA RAW league style trends, 2015-16 → 2023-24\n"
                 "ABSOLUTE league averages, indexed to 2015-16 = 100 — "
                 "NOT within-season normalized (sibling to drift.py's structural view)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8,
              frameon=False, title="signal  (→ end index, % change)")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def print_signal_changes(table):
    """Item 3 — per-signal 2015-16 → 2023-24 change (native value + % change)."""
    first, last = table.index[0], table.index[-1]
    print("=" * 64)
    print(f"Per-signal change, {first} -> {last}  (RAW league averages)")
    print("=" * 64)
    print(f"{'signal':<22} {'2015-16':>9} {'2023-24':>9} {'Δ':>9} {'%Δ':>8}")
    print("-" * 64)
    rows = (table.iloc[-1] - table.iloc[0]).reindex(_PLOT_SIGNALS)
    pct = (rows / table.iloc[0].reindex(_PLOT_SIGNALS) * 100)
    order = pct.abs().sort_values(ascending=False).index
    for s in order:
        v0, v1 = table.iloc[0][s], table.iloc[-1][s]
        fmt = "{:9.3f}" if v0 < 5 else "{:9.2f}"
        print(f"{_PRETTY[s]:<22} {fmt.format(v0)} {fmt.format(v1)} "
              f"{fmt.format(v1 - v0)} {pct[s]:+7.1f}%")


def validate(table):
    """Item 3 — confirm 3PAr RISES 2015-16 → 2023-24; show rate vs raw pace."""
    print("=" * 70)
    print("VALIDATION — 3PAr (rate) should RISE across the window")
    print("(raw 3PA/game shown beside it to separate rate from pace)")
    print("=" * 70)
    print(f"{'season':>9} | {'3PAr':>6} | {'3PA/g':>6} | {'FGA/g':>6} | n")
    print("-" * 46)
    for s, r in table.iterrows():
        print(f"{s:>9} | {r['3PAr']:6.3f} | {r['3PA_pg']:6.2f} | "
              f"{r['FGA_pg']:6.2f} | {int(r['n_qualified'])}")

    first, last = table.index[0], table.index[-1]
    d_rate = table.loc[last, "3PAr"] - table.loc[first, "3PAr"]
    d_raw  = table.loc[last, "3PA_pg"] - table.loc[first, "3PA_pg"]
    monotonic_ish = (table["3PAr"].diff().dropna() >= -0.005).all()
    print("-" * 46)
    print(f"3PAr  {first} -> {last}: {table.loc[first,'3PAr']:.3f} -> "
          f"{table.loc[last,'3PAr']:.3f}  ({d_rate:+.3f}, "
          f"{d_rate/table.loc[first,'3PAr']*100:+.1f}%)  "
          f"{'RISES' if d_rate > 0 else 'does NOT rise'}")
    print(f"3PA/g {first} -> {last}: {table.loc[first,'3PA_pg']:.2f} -> "
          f"{table.loc[last,'3PA_pg']:.2f}  ({d_raw:+.2f})")
    print(f"rate trend non-decreasing (within 0.005 tol): {monotonic_ish}")


if __name__ == "__main__":
    table = build_table()
    csv = write_csv(table)
    print(f"wrote {csv}\n")
    validate(table)
    print("\n--- thin-data check (NaNs in shooting/efficiency inputs) ---")
    print(thin_data_report().to_string())
    # Chart intentionally NOT rendered here — hold for confirmation of the
    # 3PAr rise before visualizing/interpreting (call plot_trends(table)).
