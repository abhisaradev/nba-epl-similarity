"""
drift.py — archetype DRIFT over time, built on FROZEN cross-sport archetypes.

Reuses cluster.py's pooled-clustering approach, but instead of re-clustering per
season (which would make drift an artifact of changed scaling) it does this once:

  FREEZE  pool EPL 2023-24 + all nine NBA seasons (every player-season a row,
          LeBron appears 9×), drop GKs, fit ONE StandardScaler, sweep k=6-8 by
          silhouette, and save {scaler, centroids, axes, labels} to disk.
  ASSIGN  transform every player-season with the FROZEN scaler and snap to the
          nearest FROZEN centroid; record the centroid distance (= fit quality).

Two readings on top of the frozen assignments:
  READING B (league drift)  NBA season × archetype composition + stacked area.
  READING A (player drift)  one player's archetype trajectory across seasons.

The scaler + centroids are NEVER re-fit downstream. Everything reads them back
from archetypes_frozen.pkl.
"""

import os
import pickle

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler

import datasets
import pipeline
import cluster   # reuse _drop_goalkeepers, _shared_axes, _choose_k, _label

FROZEN_PATH = "archetypes_frozen.pkl"
ASSIGN_PATH = "archetype_drift_assignments.csv"
EPL_DATASET = "epl_2324"
NBA_DATASETS = sorted(d for d in datasets.DATASETS if d.startswith("nba_"))

# Feature values are within-sport percentiles in 0..1; 0.5 = neutral median.
# (cluster.py fills with 50, which is fine when there are ~no NaNs, but on 0..1
# data a stray 50 would wreck the StandardScaler fit — exactly the kind of
# scaling artifact we must avoid here, so we fill with the 0..1 median.)
_FILL = 0.5


def _feature_frame(dataset_id):
    d = datasets.get(dataset_id)
    csv = datasets.processed_path(dataset_id)
    feats = pipeline.feature_frame(csv, d["sport"], d["min_minutes"])
    feats["season"] = d["true_season"]
    feats["dataset"] = dataset_id
    if d["sport"] == "soccer":
        feats = cluster._drop_goalkeepers(feats, csv)   # GKs have no analogue
    return feats


def build_full_pool():
    """One row per player-season across EPL 2023-24 + all nine NBA seasons,
    on the cross-sport shared __vol/__eff axes."""
    frames = [_feature_frame(EPL_DATASET)] + [_feature_frame(d) for d in NBA_DATASETS]
    soccer, first_nba = frames[0], frames[1]
    axes = cluster._shared_axes(soccer, first_nba)
    cols = ["player", "sport", "season", "dataset"] + axes
    pool = pd.concat([f[cols] for f in frames], ignore_index=True)
    return pool, axes


# ── FREEZE ──────────────────────────────────────────────────────────────────

def freeze(ks=(6, 7, 8)):
    pool, axes = build_full_pool()
    n_soccer = int((pool.sport == "soccer").sum())
    n_nba = int((pool.sport == "nba").sum())
    print(f"Pooling {len(pool)} player-seasons "
          f"({n_soccer} soccer-season rows + {n_nba} nba-season rows) "
          f"on {len(axes)} shared axes.\n")

    scaler = StandardScaler().fit(pool[axes].fillna(_FILL).values)
    X = scaler.transform(pool[axes].fillna(_FILL).values)

    k, km = cluster._choose_k(X, ks)
    labels = {c: cluster.apply_name(cluster._label(km.cluster_centers_[c], axes))
              for c in range(k)}

    frozen = {
        "scaler": scaler,
        "centroids": km.cluster_centers_,
        "axes": axes,
        "labels": labels,
        "k": k,
    }
    with open(FROZEN_PATH, "wb") as fh:
        pickle.dump(frozen, fh)
    print(f"Froze {k} archetypes on {len(pool)} player-seasons → {FROZEN_PATH}")
    return frozen


def load_frozen():
    with open(FROZEN_PATH, "rb") as fh:
        return pickle.load(fh)


# ── ASSIGN ──────────────────────────────────────────────────────────────────

def assign_all(frozen=None):
    """Snap every player-season to the nearest FROZEN centroid (frozen scaler)."""
    frozen = frozen or load_frozen()
    pool, _ = build_full_pool()
    axes, C = frozen["axes"], frozen["centroids"]

    X = frozen["scaler"].transform(pool[axes].fillna(_FILL).values)
    d = np.linalg.norm(X[:, None, :] - C[None, :, :], axis=2)   # (n_rows, k)
    nearest = d.argmin(axis=1)

    pool["cluster"] = nearest
    pool["archetype"] = [frozen["labels"][c] for c in nearest]
    pool["distance"] = d[np.arange(len(d)), nearest]
    out = pool[["player", "sport", "season", "dataset",
                "cluster", "archetype", "distance"]].copy()
    out.to_csv(ASSIGN_PATH, index=False)
    return out


# ── READING B: league drift ───────────────────────────────────────────────────

def league_drift(assignments, sport="nba"):
    sub = assignments[assignments.sport == sport]
    comp = (sub.groupby(["season", "archetype"]).size()
               .unstack(fill_value=0).sort_index())
    comp = comp.div(comp.sum(axis=1), axis=0) * 100.0     # % within each season

    os.makedirs("examples", exist_ok=True)
    comp.round(1).to_csv("examples/nba_archetype_drift.csv")

    fig, ax = plt.subplots(figsize=(12, 6.5))
    cols = list(comp.columns)
    ax.stackplot(range(len(comp.index)),
                 *[comp[c].values for c in cols], labels=cols, alpha=0.85)
    ax.set_xticks(range(len(comp.index)))
    ax.set_xticklabels(comp.index, rotation=45, ha="right")
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of qualified players")
    ax.set_title("NBA archetype mix, 2015-16 → 2023-24  (frozen cross-sport archetypes)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    fig.tight_layout()
    fig.savefig("examples/nba_archetype_drift.png", dpi=140, bbox_inches="tight")
    print("wrote examples/nba_archetype_drift.csv + .png")
    return comp


# ── READING A: player drift ───────────────────────────────────────────────────

def player_trajectory(name, assignments):
    rows = assignments[assignments.player == name]
    if len(rows) == 0:   # forgiving partial match
        rows = assignments[assignments.player.str.contains(name, case=False, na=False)]
    return rows.sort_values("season")[["season", "archetype", "distance"]].reset_index(drop=True)


def print_trajectory(name, assignments):
    traj = player_trajectory(name, assignments)
    print(f"\n{name} — archetype trajectory:")
    if len(traj) == 0:
        print("  (not found)")
        return traj
    for _, r in traj.iterrows():
        print(f"  {r['season']}:  {r['archetype']:<55s}  (dist {r['distance']:.2f})")
    n_arch = traj["archetype"].nunique()
    print(f"  -> {len(traj)} seasons, {n_arch} distinct archetype(s)")
    return traj


# ── VALIDATION ────────────────────────────────────────────────────────────────

def _exemplars(assignments, cluster_id, n=4):
    sub = assignments[assignments.cluster == cluster_id].sort_values("distance")
    return [f"{r.player} ({r.sport[:3]} {r.season})" for _, r in sub.head(n).iterrows()]


def validate(frozen, assignments):
    print("\n" + "=" * 78)
    print("VALIDATION 6a — frozen archetypes (defining axes + exemplars)")
    print("=" * 78)
    for c in range(frozen["k"]):
        print(f"\n[{c}] {frozen['labels'][c]}")
        print(f"    exemplars: {', '.join(_exemplars(assignments, c))}")

    print("\n" + "=" * 78)
    print("VALIDATION 6b — NBA league drift vs known history")
    print("=" * 78)
    comp = league_drift(assignments)
    first, last = comp.index[0], comp.index[-1]
    print(f"\nArchetype share change {first} → {last} (percentage points):")
    delta = (comp.loc[last] - comp.loc[first]).sort_values()
    for arch, dv in delta.items():
        print(f"  {dv:+6.1f} pp   {arch}")

    print("\n" + "=" * 78)
    print("VALIDATION 6c — stable-role player should be (mostly) flat")
    print("=" * 78)
    # Rudy Gobert: rim-running / rim-protecting center the entire window.
    print_trajectory("Rudy Gobert", assignments)


if __name__ == "__main__":
    frozen = freeze()
    assignments = assign_all(frozen)
    print(f"\nAssigned {len(assignments)} player-seasons → {ASSIGN_PATH}")

    validate(frozen, assignments)

    print("\n" + "=" * 78)
    print("READING A — example player trajectories")
    print("=" * 78)
    for name in ["LeBron James", "Stephen Curry", "Giannis Antetokounmpo"]:
        print_trajectory(name, assignments)
