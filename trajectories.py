"""
trajectories.py — player archetype trajectory deep-dives using the
already-computed frozen-archetype assignments from drift.py.

Loads archetype_drift_assignments.csv directly — does NOT re-run the freeze.
The frozen scaler + centroids stay untouched in archetypes_frozen.pkl.

Outputs:
  examples/player_trajectories.csv     summary row per player (5+ season players)
  examples/trajectory_highlight.png    step-line chart: top-3 drifters + LeBron
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ASSIGN_CSV = "archetype_drift_assignments.csv"

# Canonical season order
SEASONS = [
    "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
    "2020-21", "2021-22", "2022-23", "2023-24",
]
SEASON_RANK = {s: i for i, s in enumerate(SEASONS)}

# Archetype y-axis order for the chart: defensive/physical → offensive/creative
ARCH_ORDER = [
    "The Enforcer",
    "The Glue Guy",
    "The Workhorse",
    "The Connector",
    "The Creator",
    "The Playmaker",
    "The Scorer",
]
ARCH_Y = {a: i for i, a in enumerate(ARCH_ORDER)}

# Hand-written intuition notes for the top 3 drifters (written after
# inspecting who they are and their career histories).
DRIFTER_NOTES = {
    "Alec Burks": (
        "Career journeyman (Utah → Cleveland → Sacramento → Golden State → "
        "New York → Detroit → others); his role genuinely flipped from off-ball "
        "scorer to primary ball-handler multiple times as teams needed different "
        "things from him — the model tracks every deployment shift."
    ),
    "Seth Curry": (
        "Pure shooter (Scorer) who was periodically asked to act as a secondary "
        "ball-handler and playmaker in Dallas and Philadelphia; his oscillation "
        "between Scorer, Playmaker, and Connector reflects real team-specific role "
        "assignments rather than a sustained evolution."
    ),
    "Bobby Portis": (
        "Physical backup big in Chicago who cycled between hustle roles (Glue Guy) "
        "and rim-running (Enforcer) before finding a defined identity in Milwaukee "
        "as a high-usage sixth-man — the late-career consolidation to Workhorse/"
        "Enforcer mirrors his emergence as a real offensive weapon."
    ),
}


# ── helpers ──────────────────────────────────────────────────────────────────

def load():
    a = pd.read_csv(ASSIGN_CSV)
    a["season_rank"] = a["season"].map(SEASON_RANK)
    return a.sort_values(["player", "season_rank"]).reset_index(drop=True)


def _transitions(archs):
    """Count season-to-season archetype changes."""
    return sum(1 for i in range(1, len(archs)) if archs[i] != archs[i - 1])


def _aba(archs):
    """True if any archetype recurs after being absent for at least one season."""
    seen = set()
    for i, a in enumerate(archs):
        if a in seen and (i == 0 or archs[i - 1] != a):
            return True
        seen.add(a)
    return False


def _traj_str(archs):
    return " → ".join(archs)


# ── step 2: interesting trajectory metrics ────────────────────────────────────

def build_summary(data):
    """One summary row per player who appears in 5+ seasons."""
    nba = data[data.sport == "nba"]
    rows = []
    for player, grp in nba.groupby("player"):
        grp = grp.sort_values("season_rank")
        archs = grp["archetype"].tolist()
        n = len(grp)
        if n < 5:
            continue
        trans = _transitions(archs)
        rows.append({
            "player":              player,
            "sport":               "nba",
            "seasons_present":     n,
            "archetypes_seen":     len(set(archs)),
            "n_changes":           trans,
            "aba_pattern":         _aba(archs),
            "most_common_archetype": grp["archetype"].value_counts().index[0],
            "_trajectory":         _traj_str(archs),
        })

    # Include the single EPL season too
    soc = data[data.sport == "soccer"]
    for player, grp in soc.groupby("player"):
        archs = grp["archetype"].tolist()
        rows.append({
            "player":              player,
            "sport":               "soccer",
            "seasons_present":     len(grp),
            "archetypes_seen":     1,
            "n_changes":           0,
            "aba_pattern":         False,
            "most_common_archetype": archs[0],
            "_trajectory":         archs[0],
        })

    return pd.DataFrame(rows)


def top_drifters(summary, n=10):
    nba = summary[summary.sport == "nba"]
    return nba.nlargest(n, "n_changes")[
        ["player", "seasons_present", "archetypes_seen", "n_changes", "aba_pattern",
         "most_common_archetype", "_trajectory"]
    ].reset_index(drop=True)


def top_stable(summary, n=10):
    nba = summary[summary.sport == "nba"]
    zero = nba[nba.n_changes == 0].nlargest(n, "seasons_present")
    return zero[["player", "seasons_present", "most_common_archetype"]].reset_index(drop=True)


def aba_players(summary, n=10):
    nba = summary[(summary.sport == "nba") & (summary.aba_pattern)]
    return nba.nlargest(n, "n_changes")[
        ["player", "seasons_present", "n_changes", "_trajectory"]
    ].reset_index(drop=True)


# ── step 3/4: print trajectories ─────────────────────────────────────────────

def get_traj(player, data):
    rows = data[data.player == player]
    if rows.empty:
        rows = data[data.player.str.contains(player, case=False, na=False)]
    return rows.sort_values("season_rank")[
        ["season", "sport", "archetype", "distance"]
    ].reset_index(drop=True)


def print_traj(player, data, note=None):
    t = get_traj(player, data)
    print(f"\n{'─'*70}")
    print(f"  {player}")
    print(f"{'─'*70}")
    if t.empty:
        print("  (not found in assignments)")
        return t
    for _, r in t.iterrows():
        print(f"  {r.season}   {r.archetype:<22s}  dist={r.distance:.2f}")
    n_arch = t.archetype.nunique()
    trans = _transitions(t.archetype.tolist())
    print(f"  → {len(t)} seasons · {n_arch} archetype(s) · {trans} transition(s)")
    if note:
        print(f"\n  ✎ {note}")
    return t


# ── step 6: trajectory chart ──────────────────────────────────────────────────

def plot_trajectories(players_data, data, title_suffix="", path="examples/trajectory_highlight.png"):
    """
    Step-line chart: x = season index, y = archetype (categorical).
    players_data: list of (name, color, linestyle, label)
    """
    os.makedirs("examples", exist_ok=True)

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_facecolor("#f9f9f9")
    fig.patch.set_facecolor("white")

    legend_handles = []

    for name, color, ls, label in players_data:
        t = get_traj(name, data)
        if t.empty:
            continue
        xs = t["season"].map(SEASON_RANK).values
        ys = t["archetype"].map(ARCH_Y).values

        # step-line: draw horizontal then vertical segments
        ax.step(xs, ys, where="post", color=color, lw=2.5,
                linestyle=ls, zorder=3)
        ax.scatter(xs, ys, color=color, s=60, zorder=4)

        # label at the last data point — stagger vertically to avoid overlap
        y_offset = {"LeBron James": 8, "Alec Burks": -10, "Seth Curry": 8}.get(name, 0)
        ax.annotate(
            label,
            xy=(xs[-1], ys[-1]),
            xytext=(6, y_offset), textcoords="offset points",
            color=color, fontsize=8.5, va="center", fontweight="bold",
        )
        legend_handles.append(
            mpatches.Patch(color=color, label=label)
        )

    # y-axis: archetype names
    ax.set_yticks(range(len(ARCH_ORDER)))
    ax.set_yticklabels(ARCH_ORDER, fontsize=10)
    ax.set_ylim(-0.5, len(ARCH_ORDER) - 0.5)

    # x-axis: season labels
    ax.set_xticks(range(len(SEASONS)))
    ax.set_xticklabels(SEASONS, rotation=40, ha="right", fontsize=9)
    ax.set_xlim(-0.3, len(SEASONS) - 0.3)

    # light horizontal gridlines per archetype band
    for y in range(len(ARCH_ORDER)):
        ax.axhline(y, color="white", lw=1.0, zorder=1)
    for y in np.arange(-0.5, len(ARCH_ORDER), 1):
        ax.axhline(y, color="#dddddd", lw=0.6, zorder=0)

    ax.set_xlabel("NBA season", fontsize=10)
    ax.set_ylabel("Archetype (frozen cross-sport)", fontsize=10)
    ax.set_title(
        "Archetype trajectories: top-3 drifters vs. LeBron James (stable baseline)\n"
        "(frozen cross-sport archetypes — within-season normalized)",
        fontsize=11, fontweight="bold",
    )
    ax.legend(handles=legend_handles, loc="lower left", fontsize=9, framealpha=0.85)

    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {path}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data = load()

    summary = build_summary(data)

    # ── STEP 2: print ranking tables ──────────────────────────────────────────
    drifters = top_drifters(summary, n=10)
    stable   = top_stable(summary, n=10)
    abas     = aba_players(summary, n=10)

    print("=" * 70)
    print("TOP 10 BIGGEST DRIFTERS  (most archetype transitions, 5+ seasons)")
    print("=" * 70)
    print(drifters[["player", "seasons_present", "archetypes_seen",
                     "n_changes", "_trajectory"]].to_string(index=False))

    print("\n" + "=" * 70)
    print("TOP 10 MOST STABLE  (0 transitions, 5+ seasons, sorted by seasons)")
    print("=" * 70)
    print(stable.to_string(index=False))

    print("\n" + "=" * 70)
    print("A→B→A RETURNERS  (archetype comes back after absence)")
    print("=" * 70)
    print(abas[["player", "seasons_present", "n_changes", "_trajectory"]
               ].head(8).to_string(index=False))

    # ── STEP 3/4: named player trajectories ──────────────────────────────────
    print("\n\n" + "=" * 70)
    print("VALIDATED STABLE PLAYERS")
    print("=" * 70)
    for name in ["LeBron James", "Stephen Curry", "Giannis Antetokounmpo"]:
        print_traj(name, data)

    top3 = drifters.head(3)["player"].tolist()
    print("\n\n" + "=" * 70)
    print("TOP 3 BIGGEST DRIFTERS — with intuition check")
    print("=" * 70)
    for name in top3:
        note = DRIFTER_NOTES.get(name)
        print_traj(name, data, note=note)

    print("\n\n" + "=" * 70)
    print("SOCCER SPOT-CHECKS (EPL 2023-24 — cross-sport landing archetype)")
    print("=" * 70)
    for name in ["Erling Haaland", "Rodri"]:
        print_traj(name, data)

    # ── STEP 5: summary CSV ───────────────────────────────────────────────────
    os.makedirs("examples", exist_ok=True)
    out_cols = ["player", "sport", "seasons_present", "archetypes_seen",
                "n_changes", "most_common_archetype"]
    summary[out_cols].sort_values(
        ["sport", "n_changes"], ascending=[True, False]
    ).to_csv("examples/player_trajectories.csv", index=False)
    print(f"\nwrote examples/player_trajectories.csv  "
          f"({len(summary)} rows: "
          f"{(summary.sport=='nba').sum()} NBA 5+-season players + "
          f"{(summary.sport=='soccer').sum()} EPL players)")

    # ── STEP 6: trajectory chart ──────────────────────────────────────────────
    # top-3 drifters in warm colors, LeBron in cool blue as stable baseline
    players_chart = [
        ("LeBron James",      "#2196F3", "-",  "LeBron James (stable baseline)"),
        (top3[0],             "#E53935", "--", top3[0]),
        (top3[1],             "#FB8C00", "--", top3[1]),
        (top3[2],             "#8E24AA", "--", top3[2]),
    ]
    plot_trajectories(players_chart, data, path="examples/trajectory_highlight.png")
