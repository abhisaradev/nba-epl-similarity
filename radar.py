"""
radar.py — overlaid radar comparing two players across the similarity axes.

Two readability upgrades over v1:
  * a dashed "league median" ring at 50 — every spoke now has a reference, so
    you can see at a glance where a player is genuinely exceptional vs average.
  * spoke labels scale with the query player's strengths-weighting, so the
    picture matches the math (the axes driving the match read larger/bolder).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import breakdown
import similarity


def radar(df_a, player_a, df_b, player_b, out_path=None, title=None,
          weighting="strengths"):
    pa, pb = breakdown.profile(df_a, player_a), breakdown.profile(df_b, player_b)
    shared = [c for c in pa.index if c in pb.index]
    labels = [breakdown._pretty(c) for c in shared]
    a_vals = [float(pa[c]) if pa[c] == pa[c] else 0.0 for c in shared]
    b_vals = [float(pb[c]) if pb[c] == pb[c] else 0.0 for c in shared]

    # query player's axis weights -> emphasize the spokes driving the match
    w = similarity._weights(np.array(a_vals) / 100.0, shared, weighting)
    wn = (w - w.min()) / (w.max() - w.min() + 1e-9)

    angles = np.linspace(0, 2 * np.pi, len(shared), endpoint=False).tolist()
    a_vals += a_vals[:1]; b_vals += b_vals[:1]; angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels)
    for tick, weight in zip(ax.get_xticklabels(), wn):
        tick.set_fontsize(8 + 6 * weight)
        tick.set_fontweight("bold" if weight > 0.6 else "normal")
    ax.set_yticks([20, 40, 60, 80]); ax.set_yticklabels(["20", "40", "60", "80"],
                                                         fontsize=7, color="grey")
    # league median reference ring
    ax.plot(np.linspace(0, 2*np.pi, 200), [50]*200, ls="--", lw=1,
            color="grey", alpha=0.6)

    ax.plot(angles, a_vals, lw=2, color="#1f77b4", label=player_a)
    ax.fill(angles, a_vals, alpha=0.25, color="#1f77b4")
    ax.plot(angles, b_vals, lw=2, color="#d62728", label=player_b)
    ax.fill(angles, b_vals, alpha=0.25, color="#d62728")

    ax.set_title(title or f"{player_a}  vs  {player_b}", fontsize=14, pad=28)
    # display-only interior-scoring readout (not part of the match math)
    ia, ib = breakdown.interior_score(df_a, player_a), breakdown.interior_score(df_b, player_b)
    if ia is not None and ib is not None:
        note = f"interior score (display only):  {player_a} {ia:.0f}  ·  {player_b} {ib:.0f}"
        ax.annotate(note, xy=(0.5, -0.06), xycoords="axes fraction", ha="center",
                    fontsize=8, color="grey")
        print(note)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.10))
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=140, bbox_inches="tight"); print(f"saved {out_path}")
    return fig


if __name__ == "__main__":
    import pipeline
    soccer = pipeline.feature_frame("soccer.csv", "soccer", 900)
    nba    = pipeline.feature_frame("nba.csv", "nba", 500)
    q = soccer[soccer["player"].str.contains("Haaland", case=False, na=False)].iloc[[0]]
    top = similarity.nearest(q, nba, k=1).iloc[0]["player"]
    print("Haaland ->", top)
    radar(soccer, q.iloc[0]["player"], nba, top, out_path="haaland_radar_v2.png")
