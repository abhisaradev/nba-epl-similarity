"""
cluster.py — discover cross-sport player archetypes (Approach A: pooled).

Pools soccer + NBA player-seasons into ONE space (on the shared, within-sport-
normalized dimension axes) and clusters them together, so each archetype that
emerges is a mix of players from both sports — the project's thesis made literal.

Goalkeepers are dropped: they have no cross-sport analogue and otherwise form a
degenerate soccer-only cluster (confirmed in testing — GKs self-segregate).

The soccer/NBA mix per cluster is the validation headline: if clusters come out
mixed, the within-sport normalization genuinely makes the sports comparable; a
sport-segregated cluster flags either a GK-type artifact or a real structural
gap where the sports don't overlap (worth reporting either way).

Outputs:
  archetype_assignments.csv  — player, sport, cluster, archetype
  prints a summary: archetype label, size, soccer/NBA split, exemplars per sport
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

import pipeline

FEATURE_SUFFIXES = ("__vol", "__eff")


def _shared_axes(a, b):
    fa = [c for c in a.columns if c.endswith(FEATURE_SUFFIXES)]
    return [c for c in fa if c in b.columns]


def _drop_goalkeepers(feats, soccer_csv):
    """Remove GKs by FBref Pos column (no cross-sport analogue)."""
    raw = pd.read_csv(soccer_csv)
    if "Pos" not in raw.columns:
        return feats
    gk = set(raw.loc[raw["Pos"].astype(str).str.contains("GK", na=False), "player"])
    return feats[~feats["player"].isin(gk)].copy()


def build_pool(soccer_csv, nba_csv, min_soccer, min_nba):
    soccer = pipeline.feature_frame(soccer_csv, "soccer", min_soccer)
    nba    = pipeline.feature_frame(nba_csv, "nba", min_nba)
    soccer = _drop_goalkeepers(soccer, soccer_csv)
    axes = _shared_axes(soccer, nba)
    pool = pd.concat(
        [soccer[["player", "sport"] + axes], nba[["player", "sport"] + axes]],
        ignore_index=True,
    )
    return pool, axes


def _choose_k(X, ks):
    best = None
    print("Choosing k by silhouette (higher = cleaner separation):")
    for k in ks:
        km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(X)
        s = silhouette_score(X, km.labels_)
        print(f"  k={k}: {s:.3f}")
        if best is None or s > best[1]:
            best = (k, s, km)
    print(f"  -> picked k={best[0]} (silhouette {best[1]:.3f})\n")
    return best[0], best[2]


def _label(centroid, axes, n_top=2):
    s = pd.Series(centroid, index=axes).sort_values(ascending=False)
    pretty = [a.replace("__vol", " (vol)").replace("__eff", " (eff)").replace("_", " ")
              for a in s.head(n_top).index]
    return " + ".join(pretty)


def cluster(soccer_csv="soccer.csv", nba_csv="nba.csv",
            min_soccer=900, min_nba=500, ks=(6, 7, 8)):
    pool, axes = build_pool(soccer_csv, nba_csv, min_soccer, min_nba)
    X = StandardScaler().fit_transform(pool[axes].fillna(50).values)

    k, km = _choose_k(X, ks)
    pool["cluster"] = km.labels_
    labels = {c: _label(km.cluster_centers_[c], axes) for c in range(k)}
    pool["archetype"] = pool["cluster"].map(labels)

    rows = []
    for c in range(k):
        idx = np.where(km.labels_ == c)[0]
        d = np.linalg.norm(X[idx] - km.cluster_centers_[c], axis=1)
        sub = pool.iloc[idx].assign(_d=d).sort_values("_d")   # nearest = most typical
        socc = sub[sub.sport == "soccer"]["player"].head(3).tolist()
        nbap = sub[sub.sport == "nba"]["player"].head(3).tolist()
        rows.append({
            "cluster": c, "archetype": labels[c],
            "n_soccer": int((sub.sport == "soccer").sum()),
            "n_nba": int((sub.sport == "nba").sum()),
            "soccer_exemplars": ", ".join(socc),
            "nba_exemplars": ", ".join(nbap),
        })
    summary = pd.DataFrame(rows)

    pool[["player", "sport", "cluster", "archetype"]].to_csv(
        "archetype_assignments.csv", index=False)
    return pool, summary


if __name__ == "__main__":
    pool, summary = cluster()
    print("=== CROSS-SPORT ARCHETYPES ===")
    for _, r in summary.iterrows():
        mix = "MIXED" if min(r.n_soccer, r.n_nba) > 0 else "*** SPORT-SEGREGATED ***"
        print(f"\n[{r.cluster}] {r.archetype}")
        print(f"    {r.n_soccer} soccer + {r.n_nba} nba   ({mix})")
        print(f"    soccer: {r.soccer_exemplars}")
        print(f"    nba:    {r.nba_exemplars}")
    seg = summary[(summary.n_soccer == 0) | (summary.n_nba == 0)]
    print(f"\n{len(summary)} archetypes, {len(summary)-len(seg)} mixed across both sports.")
    if len(seg):
        print(f"{len(seg)} sport-segregated (worth a look): "
              + ", ".join(seg["archetype"]))
    print("wrote archetype_assignments.csv")
