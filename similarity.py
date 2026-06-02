"""
similarity.py — weighted cross-sport nearest-neighbour ranking.

weighting (default "strengths"):
    "equal"      every axis counts the same (original behaviour)
    "strengths"  weight each axis by how far ABOVE the league median the QUERY
                 player sits — match on what a player is distinctively GOOD at,
                 ignore distinctive ABSENCES (fixes the Haaland->shooter bug)
    "symmetric"  weight by deviation in either direction (good OR bad)
On top of the mode, config.DIMENSION_WEIGHTS applies a manual multiplier per
dimension (all 1.0 by default = inert).

metric:
    "euclidean"   weighted straight-line distance (default)
    "mahalanobis" decorrelates axes; IGNORES the weighting above (handles it via
                  covariance). Use for the writeup comparison.
    "cosine"      profile shape only — magnitude-blind, not recommended here.
"""
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
import config

FEATURE_SUFFIXES = ("__vol", "__eff")


def feature_cols(df):
    return [c for c in df.columns if c.endswith(FEATURE_SUFFIXES)]


def _align(a, b):
    return [c for c in feature_cols(a) if c in feature_cols(b)]


def _manual_mult(axis):
    dim = axis.rsplit("__", 1)[0]
    return config.DIMENSION_WEIGHTS.get(dim, 1.0)


def _weights(query_vec, axes, weighting, floor=5.0):
    q = np.asarray(query_vec, float) * 100.0  # percentile 0..1 -> 0..100
    if weighting == "equal":
        w = np.ones(len(axes))
    elif weighting == "strengths":
        w = np.maximum(q - 50.0, 0.0) + floor
    elif weighting == "symmetric":
        w = np.abs(q - 50.0) + floor
    else:
        raise ValueError(weighting)
    w = w * np.array([_manual_mult(a) for a in axes])
    return w / w.sum()


def _candidate_distances(query_row, candidates, axes, weighting, metric):
    qv = query_row[axes].astype(float).fillna(0.5).to_numpy()
    C = candidates[axes].astype(float).fillna(0.5).to_numpy()
    if metric == "cosine":
        return cdist(qv[None, :], C, metric="cosine")[0]
    if metric == "mahalanobis":
        cov = np.cov(np.vstack([qv[None, :], C]).T)
        VI = np.linalg.pinv(cov)
        return cdist(qv[None, :], C, metric="mahalanobis", VI=VI)[0]
    # weighted euclidean
    w = _weights(qv, axes, weighting)
    return np.sqrt((w * (C - qv) ** 2).sum(axis=1))


def _sim(d):
    return 100.0 / (1.0 + d)


def nearest(query_row, candidates, k=10, weighting="strengths", metric="euclidean"):
    if isinstance(query_row, pd.DataFrame):
        query_row = query_row.iloc[0]
    axes = [c for c in feature_cols(candidates) if c in query_row.index]
    d = _candidate_distances(query_row, candidates, axes, weighting, metric)
    order = np.argsort(d)[:k]
    out = candidates.iloc[order][["player", "sport"]].copy()
    out["distance"] = d[order]
    out["similarity"] = _sim(d[order])
    return out.reset_index(drop=True)


def ranked_table(soccer, nba, k=10, weighting="strengths", metric="euclidean"):
    axes = _align(soccer, nba)
    rows = []
    for i in range(len(soccer)):
        q = soccer.iloc[i]
        d = _candidate_distances(q, nba, axes, weighting, metric)
        for rank, j in enumerate(np.argsort(d)[:k], 1):
            rows.append({"soccer_player": q["player"], "nba_comp": nba.iloc[j]["player"],
                         "rank": rank, "distance": d[j], "similarity": _sim(d[j])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import pipeline
    soccer = pipeline.feature_frame("soccer.csv", "soccer", 900)
    nba    = pipeline.feature_frame("nba.csv", "nba", 500)
    for name in ["Erling Haaland", "William Saliba", "Rodri", "Kevin De Bruyne"]:
        q = soccer[soccer["player"].str.contains(name.split()[-1], case=False, na=False)]
        if len(q) == 0:
            print(name, "not found"); continue
        top = nearest(q.iloc[[0]], nba, k=5)
        print(f"{q.iloc[0]['player']:22s} -> " + ", ".join(top["player"]))
