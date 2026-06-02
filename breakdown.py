"""
breakdown.py — per-axis comparison between two players.

The single similarity number answers "how close?"; this answers "close HOW?".
Works on the normalized feature frames produced by pipeline.feature_frame(), so
the values are already percentile ranks within each player's own league-season.
Sport- and league-agnostic: pass any two feature frames (EPL vs NBA, EPL vs
La Liga, NBA 2023 vs NBA 2024 — all valid).
"""

import pandas as pd

FEATURE_SUFFIXES = ("__vol", "__eff")


def feature_cols(df):
    return [c for c in df.columns if c.endswith(FEATURE_SUFFIXES)]


def interior_score(df, player):
    """DISPLAY ONLY — not part of the similarity math. Returns the player's
    interior-scoring percentile (0-100, high = paint/box dominator, low =
    perimeter), if an 'interior_score' column was added during ingest. Lets the
    radar/table still SHOW where a player scores even though location is now
    folded inside scoring_threat rather than living as its own axis.
    Returns None if the column isn't present."""
    if "interior_score" not in df.columns:
        return None
    row = _row(df, player)
    val = row["interior_score"]
    return None if pd.isna(val) else float(val)


def _row(df, player):
    m = df[df["player"] == player]
    if len(m) == 0:  # fall back to a forgiving partial match
        m = df[df["player"].str.contains(player, case=False, na=False)]
    if len(m) == 0:
        raise KeyError(f"player not found: {player!r}")
    return m.iloc[0]


def _pretty(col):
    return (col.replace("__vol", " (vol)")
               .replace("__eff", " (eff)")
               .replace("_", " "))


def profile(df, player, as_pct=True):
    """A player's per-axis normalized profile. 0-100 percentile if as_pct."""
    row = _row(df, player)
    vals = row[feature_cols(df)].astype(float)
    return vals * 100.0 if as_pct else vals


def compare(df_a, player_a, df_b, player_b):
    """Side-by-side per-axis table. Sorted by gap (biggest mismatch first)."""
    pa, pb = profile(df_a, player_a), profile(df_b, player_b)
    shared = [c for c in pa.index if c in pb.index]
    out = pd.DataFrame({
        "dimension": [_pretty(c) for c in shared],
        player_a:    [pa[c] for c in shared],
        player_b:    [pb[c] for c in shared],
    })
    out["gap"] = (out[player_a] - out[player_b]).abs()
    return out.sort_values("gap").reset_index(drop=True)


def print_compare(df_a, player_a, df_b, player_b):
    t = compare(df_a, player_a, df_b, player_b)
    print(f"\n{player_a}  vs  {player_b}   (percentile within own league)\n")
    print(t.to_string(index=False, float_format=lambda x: f"{x:5.0f}"))
    print(f"\nmean abs gap: {t['gap'].mean():.1f}   "
          f"(lower = tighter match; the small-gap rows are why they're comps)")
    return t
