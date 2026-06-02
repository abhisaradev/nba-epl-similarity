"""
pipeline.py — ingest -> normalize (within sport) -> composite dimension axes.

Stages map 1:1 to the architecture diagram:
    load_sport()        Raw stats
    add_per_minute()    Clean + per-90 / per-36   (you likely do this upstream)
    normalize()         Within-sport z-scores / percentile ranks   <-- the bridge
    build_dimensions()  ~7 composite axes (volume + efficiency kept separate)
"""

import numpy as np
import pandas as pd

import config


# --------------------------------------------------------------------- ingest
def load_sport(csv_path, min_minutes, minutes_col="minutes"):
    """Load one sport's player-season CSV and apply the minutes filter.

    The minutes filter is critical — per-90/per-36 rates are noise below a
    sample threshold (the same lesson as the stable-minutes filter elsewhere).
    """
    df = pd.read_csv(csv_path)
    df = df[df[minutes_col] >= min_minutes].copy()
    df = df.reset_index(drop=True)
    return df


# ----------------------------------------------------------------- normalize
def _percentile_rank(s: pd.Series) -> pd.Series:
    """Distribution-agnostic. 0..1. Robust to the right-skew in count stats."""
    return s.rank(pct=True)


def _zscore(s: pd.Series) -> pd.Series:
    """Standardization. Assumes roughly normal — over-rewards the extreme tail."""
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def normalize(df, columns, method="percentile"):
    """Normalize the given columns WITHIN this dataframe (i.e. within one sport).

    Inverse stats (lower-is-better) are sign-flipped so higher always = better.
    method: 'percentile' (default) | 'zscore' | 'robust'
    Returns a new dataframe of normalized columns, same index.
    """
    out = pd.DataFrame(index=df.index)
    for col in columns:
        if col not in df.columns:
            # column not wired yet (e.g. a v2 stat) — skip quietly
            continue
        s = df[col].astype(float)
        if col in config.INVERSE_STATS:
            s = -s
        if method == "percentile":
            out[col] = _percentile_rank(s)
        elif method == "zscore":
            out[col] = _zscore(s)
        elif method == "robust":
            iqr = s.quantile(0.75) - s.quantile(0.25)
            out[col] = (s - s.median()) / (iqr if iqr else 1.0)
        else:
            raise ValueError(f"unknown method: {method}")
    return out


# ------------------------------------------------------------ dimension axes
def build_dimensions(df, sport, method="percentile", dims=None):
    """Composite raw stats into per-dimension VOLUME and EFFICIENCY axes.

    Output columns look like:  scoring_threat__vol,  scoring_threat__eff, ...
    Keeping vol/eff separate is deliberate — averaging them re-introduces the
    Curry failure mode. A dimension with no efficiency stats yields only __vol.
    """
    dims = dims or config.core_dimensions()
    pieces = []

    for dim_name, spec in dims.items():
        for kind, suffix in (("volume", "vol"), ("efficiency", "eff")):
            cols = spec[sport].get(kind, [])
            if not cols:
                continue
            norm = normalize(df, cols, method=method)
            if norm.shape[1] == 0:
                continue
            # composite = mean of the normalized stats within this axis
            axis = norm.mean(axis=1)
            axis.name = f"{dim_name}__{suffix}"
            pieces.append(axis)

    features = pd.concat(pieces, axis=1)
    return features


def feature_frame(csv_path, sport, min_minutes,
                  method="percentile", id_cols=("player",), minutes_col="minutes"):
    """End-to-end: csv -> filtered -> normalized dimension axes, with id columns
    carried alongside for labelling the output table."""
    raw = load_sport(csv_path, min_minutes, minutes_col=minutes_col)
    feats = build_dimensions(raw, sport, method=method)
    ids = raw[list(id_cols)].copy()
    ids["sport"] = sport
    # Carry display-only columns through untouched (they don't end in the
    # feature suffixes, so similarity/breakdown ignore them as inputs, but the
    # radar can still read interior_score off the frame).
    if "interior_score" in raw.columns:
        ids["interior_score"] = raw["interior_score"].values
    return ids.join(feats)
